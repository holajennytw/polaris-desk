"""Deep Research v0 — 自寫 ReAct loop（R2 W3 D15）。

純 Python bounded loop（AQ-03 決策 + 用戶選定 v0 編排）：
- **smart**（有金鑰）：`build_react_prompt` → Gemini（包 D7 retry）→ `parse_react_action`。
- **確定性 fallback**（無金鑰 / LLM 失敗）：facet 政策輪流 search 到 ≥min_citations 才 finish。
- evidence 依 source_id 去重累積；迴圈受 `should_continue`（≤max_loops）守門。
- 最終結論一律過 D9 Compliance Agent（NFR-031）。

`search` 為注入式 seam（v0 用 :func:`stub_search`，token-free）；R4 真實
`VectorStore.search` 之後接這即可，loop 不變。
"""
from __future__ import annotations

import logging
import os
import re
from collections.abc import Callable, Sequence

from polaris.graph.deep_research.react import (
    DEFAULT_TOOLS,
    REACT_SYSTEM_PROMPT,
    ReActAction,
    build_react_prompt,
    parse_react_action,
)
from polaris.graph.deep_research.state import (
    DeepResearchResult,
    ReActStep,
    dedup_evidence,
    is_fully_traceable,
    is_traceable_prose,
    numbers_grounded,
    should_continue,
)
from polaris.graph.nodes import compliance_agent
from polaris.graph.prompts import SYNTHESIS_SYSTEM_PROMPT
from polaris.graph.state import Citation
from polaris.llm.gemini import active_llm
from polaris.retrieval.retriever import PUBLIC_VIEWER
from polaris.retry import call_with_retry

log = logging.getLogger(__name__)

SearchFn = Callable[[str], list[Citation]]

#: 確定性 fallback 政策輪流檢索的面向。
_FACETS = ("營收", "毛利率", "風險與展望")

# Outcome constants for deep_research synthesis logging (R6 risk mitigation).
OUTCOME_POLISHED = "polished"
OUTCOME_GATE_TRACEABLE = "gate_traceable"
OUTCOME_GATE_NUMBERS = "gate_numbers"
OUTCOME_LLM_ERROR = "llm_error"
OUTCOME_NO_KEY = "no_key"
OUTCOME_COMPLIANCE_REJECTED = "compliance_rejected"
OUTCOME_FALLBACK = "fallback"


def stub_search(query: str) -> list[Citation]:
    """確定性、token-free 的 search 工具：不同 query → 不同 source_id。"""
    slug = re.sub(r"\s+", "-", (query or "").strip()) or "query"
    return [
        Citation(
            source_id=f"stub-{slug[:48]}",
            snippet=f"（stub 證據）關於「{query}」的法說 / 財報摘要片段。",
            origin="stub",
        )
    ]


def _extract_tickers(question: str) -> list[str]:
    """從問題抽出去重保序的 ticker 清單（≥2 檔 → 視為比較型問題）。

    走 :func:`polaris.ontology.detect_tickers` 實體解析（canonical 中文名或
    已知 4 碼代號），而非裸 ``\\d{4}`` 正則——後者會把「2025Q1」的年份誤抓成
    公司代號，造成跨季比較題（如 Q007「2025Q1 相比 2024Q4」）被誤判為比較型、
    用假代號「2025」「2024」分組（issue #77 R4 排查點名的 bug）。
    """
    from polaris.ontology import detect_tickers

    return detect_tickers(question)


def _deterministic_action(question: str, state: dict, min_citations: int) -> ReActAction:
    if len(state["evidence"]) >= min_citations:
        return ReActAction(tool="finish", tool_input="", is_finish=True)
    tickers = _extract_tickers(question)
    if len(tickers) >= 2:
        # 比較型：輪流為每檔做檢索（代號前綴偏置 retriever），確保兩家都有證據、
        # 不會一面倒；保留原問題語意（如「AI 需求」）。每輪完整輪替一圈公司後再換
        # facet——查詢字串每輪都不同，避免固定兩句查詢重複命中同批結果、去重後
        # 證據累積不到 min_citations 就 exhausted。
        ticker = tickers[state["iteration"] % len(tickers)]
        facet = _FACETS[(state["iteration"] // len(tickers)) % len(_FACETS)]
        return ReActAction(
            tool="search", tool_input=f"{ticker} {question} {facet}", is_finish=False
        )
    facet = _FACETS[state["iteration"] % len(_FACETS)]
    return ReActAction(tool="search", tool_input=f"{question} {facet}", is_finish=False)


def _decide(question: str, state: dict, client, min_citations: int) -> ReActAction:
    """決定下一個行動。有金鑰走 LLM（含 D7 retry）；任何失敗 → 退確定性政策。"""
    if client is not None:
        try:
            steps: Sequence[dict] = [s.model_dump() for s in state["react_steps"]]
            prompt = build_react_prompt(question, steps, DEFAULT_TOOLS)
            raw = call_with_retry(
                lambda: client.generate(
                    prompt, flash=True, system_instruction=REACT_SYSTEM_PROMPT
                )
            )
            return parse_react_action(raw)
        except Exception:  # noqa: BLE001 — fail-to-deterministic（不讓 agent 掛掉）
            pass
    return _deterministic_action(question, state, min_citations)


def _summarize(found: Sequence[Citation]) -> str:
    if not found:
        return "（無新證據）"
    return "取得引用：" + "、".join(c.source_id for c in found)


def _belongs_to_ticker(citation: Citation, ticker: str) -> bool:
    """引用是否歸屬某檔：優先 company 欄；退而求其次 source_id / snippet 內含代號。

    真實 retriever 的 ``company`` 欄放 canonical 中文名（見 ``_result_to_citation``），
    故同時比對 ticker 與中文名；stub / 部分來源無 company，以代號子字串補強。
    """
    from polaris.ontology import company_name

    company = citation.company or ""
    if company == ticker or (company and company == company_name(ticker)):
        return True
    return ticker in (citation.source_id or "") or ticker in (citation.snippet or "")


def _synthesize_comparison(
    question: str, evidence: Sequence[Citation], tickers: Sequence[str], *, exhausted: bool
) -> str:
    """比較型收尾：依公司分組逐點列出，讓研究助理「帶出」兩家對比而非無差別清單。

    每條列仍帶（來源：sid）→ 句句可溯源 by construction（D16）；區段標題 / 註記非
    ``- `` 開頭，豁免於 ``is_fully_traceable`` 的條列檢查。
    """
    sections: list[str] = []
    claimed: set[int] = set()
    for ticker in tickers:
        items = [c for c in evidence if _belongs_to_ticker(c, ticker)]
        for c in items:
            claimed.add(id(c))
        if items:
            points = "\n".join(f"- {c.snippet}（來源：{c.source_id}）" for c in items)
            sections.append(f"{ticker}：\n{points}")
        else:
            sections.append(f"{ticker}：（無可溯源引用，資料不足）")
    others = [c for c in evidence if id(c) not in claimed]
    if others:
        points = "\n".join(f"- {c.snippet}（來源：{c.source_id}）" for c in others)
        sections.append(f"其他：\n{points}")
    text = (
        f"關於「{question}」的同業比較（依據 {len(evidence)} 條引用）：\n"
        + "\n".join(sections)
        + "\n本回答僅描述事實與來源，不提供買賣建議。"
    )
    if exhausted and len(evidence) < 3:
        text += "\n（註：引用不足 3 條，結論暫定、待補證據。）"
    return text


def _synthesize(question: str, evidence: Sequence[Citation], *, exhausted: bool = False) -> str:
    """確定性收尾結論（不含買賣建議；引用不足誠實標註）。

    偵測到比較型問題（≥2 檔代號）→ 改走依公司分組的同業比較格式。
    """
    if not evidence:
        return f"關於「{question}」目前找不到可溯源的引用，資料不足、無法形成結論。"
    tickers = _extract_tickers(question)
    if len(tickers) >= 2:
        return _synthesize_comparison(question, evidence, tickers, exhausted=exhausted)
    # 逐點：一條 evidence 一個 bullet + 來源標記 → 句句可溯源 by construction（D16）。
    points = "\n".join(f"- {c.snippet}（來源：{c.source_id}）" for c in evidence)
    text = (
        f"關於「{question}」的研究摘要（依據 {len(evidence)} 條引用）：\n"
        f"{points}\n"
        "本回答僅描述事實與來源，不提供買賣建議。"
    )
    if exhausted and len(evidence) < 3:
        text += "\n（註：引用不足 3 條，結論暫定、待補證據。）"
    return text


def _polish_synthesize(
    question: str,
    base: str,
    evidence: Sequence[Citation],
    *,
    client,
) -> tuple[str, str]:
    """嘗試用 Gemini Flash 把確定性條列 ``base`` 潤飾成流暢散文（P0 接地觸點）。

    Returns ``(output_text, outcome)``。不過閘門 / 例外 / 無金鑰 → 回 ``(base, outcome)``。
    Flag ``DEEP_RESEARCH_LLM_SYNTHESIS`` 必須為 ``"1"`` 才啟動；預設關（token=0）。
    """
    if os.getenv("DEEP_RESEARCH_LLM_SYNTHESIS", "0") != "1":
        return base, OUTCOME_FALLBACK

    if client is None:
        log.info("deep_research.synthesis outcome=%s", OUTCOME_NO_KEY)
        return base, OUTCOME_NO_KEY

    try:
        prose = call_with_retry(
            lambda: client.generate(base, flash=True, system_instruction=SYNTHESIS_SYSTEM_PROMPT)
        )
    except Exception:  # noqa: BLE001
        log.info("deep_research.synthesis outcome=%s", OUTCOME_LLM_ERROR)
        return base, OUTCOME_LLM_ERROR

    if not is_traceable_prose(prose, evidence):
        log.info("deep_research.synthesis outcome=%s", OUTCOME_GATE_TRACEABLE)
        return base, OUTCOME_GATE_TRACEABLE

    if not numbers_grounded(prose, evidence):
        log.info("deep_research.synthesis outcome=%s", OUTCOME_GATE_NUMBERS)
        return base, OUTCOME_GATE_NUMBERS

    log.info("deep_research.synthesis outcome=%s", OUTCOME_POLISHED)
    return prose, OUTCOME_POLISHED


def _act(question: str, state: dict, action: ReActAction, search: SearchFn) -> None:
    if action.is_finish or action.tool == "finish":
        answer = (action.tool_input or "").strip() or _synthesize(question, state["evidence"])
        state["react_steps"].append(
            ReActStep(thought="證據足夠，產出結論", action="finish", action_input=action.tool_input)
        )
        state["final_answer"] = answer
        state["status"] = "answered"
    elif action.tool == "search":
        found = search(action.tool_input or question)
        state["evidence"] = dedup_evidence(state["evidence"], found)
        state["react_steps"].append(
            ReActStep(
                thought=f"需要更多關於「{action.tool_input}」的證據",
                action="search",
                action_input=action.tool_input,
                observation=_summarize(found),
            )
        )
    else:
        # 未知工具 → 安全當 finish（與 parser 的 malformed→finish 一致）
        state["react_steps"].append(
            ReActStep(thought="未知行動，安全收斂", action="finish")
        )
        state["final_answer"] = _synthesize(question, state["evidence"])
        state["status"] = "answered"
    state["iteration"] += 1


def run_deep_research(
    question: str,
    *,
    client=None,
    search: SearchFn | None = None,
    max_loops: int = 6,
    min_citations: int = 3,
    viewer: str = PUBLIC_VIEWER,
) -> DeepResearchResult:
    """跑通 Deep Research ReAct loop，回 :class:`DeepResearchResult`。

    ``search`` 預設為 ``None``，自動使用 :func:`~polaris.retrieval.retriever.active_search_fn`
    （BM25 + vector + Cohere Rerank，viewer-filtered）。
    Tests 可注入確定性 ``search=stub_search`` 以避開 store 依賴；
    ``search=lambda q: []`` 可測無證據路徑。

    ``client`` 預設為 ``None``，自動使用 :func:`~polaris.llm.gemini.active_llm`：有金鑰
    → Gemini 驅動 ReAct 推理 + smart compliance（spec D15 smart 路徑）；無金鑰 → ``None``
    → 確定性 facet 政策 + floor compliance（token-free CI）。任一 LLM 失敗仍 fail-to-
    deterministic（見 :func:`_decide`）。硬上限 / verify-or-synthesize / NFR-031 不受影響。

    ``viewer`` 是存取控制身分（issue #32），透傳進 ``active_search_fn(viewer)``；
    注入自訂 search fn 時 viewer 由呼叫端透過 closure 帶入（見 :func:`make_retriever_search_fn`）。

    修 issue #77 跨公司檢索污染 + 期別錯配：從**使用者原始問題**（``question``，非
    ReAct 每輪自己下的 tool_input——那可能已被 LLM 拆解成不含公司名/季別的短語，
    例如「毛利率」）偵測公司名／代號與季別（Temporal Anchoring），透過 closure 綁進
    預設 search fn，讓每一輪檢索都硬過濾在正確公司與季別範圍內；未偵測到 → 不加
    對應過濾，維持原行為（時間中性 / 未指名公司的問題仍全域檢索）。
    """
    if search is None:
        from polaris.graph import temporal
        from polaris.ontology import detect_tickers
        from polaris.retrieval.retriever import active_search_fn as _active_search_fn

        period = temporal.parse_period(question, anchor=temporal.active_anchor())
        search = _active_search_fn(
            viewer,
            companies=detect_tickers(question),
            periods=list(period.quarters) or None,
        )
    if client is None:
        client = active_llm()
    state: dict = {
        "iteration": 0,
        "status": "running",
        "react_steps": [],
        "evidence": [],
        "final_answer": "",
        "viewer": viewer,  # available for search fn wiring when real store is connected
    }
    while should_continue(state, max_loops=max_loops):
        action = _decide(question, state, client, min_citations)
        _act(question, state, action, search)

    if state["status"] != "answered":
        state["status"] = "exhausted"
        if not state["final_answer"]:
            state["final_answer"] = _synthesize(question, state["evidence"], exhausted=True)

    # D16 句句可溯源硬保證：候選答案（含 LLM 自由文）未通過且有 evidence →
    # 改用結構化 grounded 摘要（接地 > 文采；LLM 推理仍保留在 react_steps）。
    if state["evidence"] and not is_fully_traceable(state["final_answer"], state["evidence"]):
        state["final_answer"] = _synthesize(question, state["evidence"])

    # P0 接地觸點：flag 開時嘗試 Gemini 潤飾（確定性 fallback 維持現狀）。
    state["final_answer"], _ = _polish_synthesize(
        question, state["final_answer"], state["evidence"], client=client
    )

    # NFR-031：最終結論一律過 D9 Compliance Agent。
    answer, compliance_status = compliance_agent.review(state["final_answer"], client)

    return DeepResearchResult(
        question=question,
        final_answer=answer,
        evidence=state["evidence"],
        react_steps=state["react_steps"],
        iterations=state["iteration"],
        status=state["status"],
        compliance_status=compliance_status,
    )


__all__ = [
    "stub_search",
    "run_deep_research",
    "SearchFn",
    "_polish_synthesize",
    "OUTCOME_POLISHED",
    "OUTCOME_GATE_TRACEABLE",
    "OUTCOME_GATE_NUMBERS",
    "OUTCOME_LLM_ERROR",
    "OUTCOME_NO_KEY",
    "OUTCOME_COMPLIANCE_REJECTED",
    "OUTCOME_FALLBACK",
]
