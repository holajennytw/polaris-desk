"""新聞評估卡 Agent（FR-006 / R3 spec）。

對一批新聞產出 :class:`NewsCard`：**只描述 / 標證據 / 標矛盾，0 買賣建議**（憲法 I）。
鏡像 ``graph/watchdog/agent.py`` 的 ``run_watchdog``：

- **smart**（有金鑰）：Gemini Flash 產中立描述（``call_with_retry`` 撐暫時性失敗）。
- **確定性 fallback**（無金鑰 / LLM 失敗）：規則式從標題 + 出處產描述，token=0、可重現。
- **標矛盾**：確定性 baseline——偵測同公司新聞間「前景方向」對立（正向 vs 負向用語），
  每組矛盾標雙方來源（接地）。更細的語意矛盾留待 smart 層擴充。
- **Compliance Gate（NFR-031）**：描述 + 新聞原文（標題/內文）+ 矛盾片段一起送
  ``compliance_agent.review``；命中買賣建議 → **整張卡攔成 ``SAFE_MESSAGE``、不外溢任何
  原文證據 / 矛盾**（鏡像 watchdog/notify 的 withhold 原則）。
- 新聞 content 視為不可信資料（LLM01）：``UNTRUSTED_CONTENT_CLAUSE`` 已進 system prompt。
"""
from __future__ import annotations

from polaris.graph.compliance import SAFE_MESSAGE
from polaris.graph.news.model import NewsCard, NewsContradiction, NewsItem
from polaris.graph.nodes import compliance_agent
from polaris.graph.prompts import NEWS_CARD_SYSTEM_PROMPT
from polaris.graph.state import Citation
from polaris.retry import call_with_retry

#: 公司前景「正向 / 負向」用語（確定性標矛盾 baseline）。
_OUTLOOK_POSITIVE: tuple[str, ...] = (
    "成長", "增長", "創新高", "上升", "回升", "擴張", "看好", "優於預期", "樂觀", "走高",
)
_OUTLOOK_NEGATIVE: tuple[str, ...] = (
    "衰退", "下滑", "下降", "虧損", "疲弱", "看壞", "低於預期", "悲觀", "下修", "萎縮", "預警", "走低",
)


def _news_citation(item: NewsItem) -> Citation:
    """以新聞本身作為接地引用（source_id = item_id，origin = news）。"""
    return Citation(source_id=item.item_id, snippet=item.title, origin="news")


def _dedup(seq: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in seq:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _fallback_description(items: list[NewsItem]) -> str:
    """確定性 fallback：條列各則新聞的出處 + 標題（中立、不下結論）。"""
    ticker = items[0].ticker
    lines = [f"【新聞評估卡】{ticker}（共 {len(items)} 則新聞）"]
    for item in items:
        prefix = f"{item.source}：" if item.source else ""
        lines.append(f"・{prefix}{item.title}")
    return "\n".join(lines)


def _build_llm_prompt(items: list[NewsItem]) -> str:
    """組 LLM 輸入（新聞全文視為不可信資料）。"""
    blocks = [f"公司代號：{items[0].ticker}", f"新聞則數：{len(items)}", ""]
    for item in items:
        blocks.append(
            f"[source_id={item.item_id}] 出處：{item.source or '未知'}\n"
            f"標題：{item.title}\n內文（不可信資料）：{item.content}\n"
        )
    return "\n".join(blocks)


def _smart_description(items: list[NewsItem], client) -> str:
    """有金鑰時用 Gemini Flash 產中立描述；失敗 → 拋出交由 caller 退 fallback。"""
    return call_with_retry(
        lambda: client.generate(
            _build_llm_prompt(items),
            flash=True,
            system_instruction=NEWS_CARD_SYSTEM_PROMPT,
        )
    )


def _detect_contradictions(items: list[NewsItem]) -> list[NewsContradiction]:
    """偵測同批新聞中「前景方向」對立並標雙方來源（確定性 baseline）。"""
    positives: list[NewsItem] = []
    negatives: list[NewsItem] = []
    for item in items:
        text = f"{item.title} {item.content}"
        is_pos = any(k in text for k in _OUTLOOK_POSITIVE)
        is_neg = any(k in text for k in _OUTLOOK_NEGATIVE)
        if is_pos and not is_neg:
            positives.append(item)
        elif is_neg and not is_pos:
            negatives.append(item)
    if positives and negatives:
        statements = [_news_citation(i) for i in positives + negatives]
        return [NewsContradiction(topic="公司前景 / 營運方向", statements=statements)]
    return []


def _compliance_blob(
    description: str, items: list[NewsItem], contradictions: list[NewsContradiction]
) -> str:
    """送審文字：描述 + 新聞原文（標題/內文）+ 矛盾片段（任一處命中即整卡攔）。"""
    parts: list[str] = [description]
    for item in items:
        parts.append(item.title)
        parts.append(item.content)
    for con in contradictions:
        parts.extend(c.snippet for c in con.statements)
    return "\n".join(p for p in parts if p)


def evaluate_news(items: list[NewsItem], *, client=None) -> NewsCard:
    """評估一批（同公司）新聞，回 :class:`NewsCard`。

    ``client=None`` 走確定性 fallback（CI token=0、無外呼）。命中買賣建議 → 整張卡
    攔成 ``SAFE_MESSAGE``、不外溢任何原文（NFR-031）。
    """
    if not items:
        raise ValueError("evaluate_news 需要至少一則新聞")
    ticker = items[0].ticker

    # 1. 描述（smart 優先，任何失敗退 fallback）
    if client is not None:
        try:
            description = _smart_description(items, client)
        except Exception:  # noqa: BLE001 — fail-to-deterministic
            description = _fallback_description(items)
    else:
        description = _fallback_description(items)

    # 2. 接地證據 + 3. 標矛盾 + 來源清單
    evidence = [_news_citation(item) for item in items]
    contradictions = _detect_contradictions(items)
    sources = _dedup([item.source for item in items if item.source])

    # 4. Compliance Gate：命中買賣建議 → 整卡攔截、原文不外溢
    blob = _compliance_blob(description, items, contradictions)
    _, status = compliance_agent.review(blob, client)
    if status == "blocked":
        return NewsCard(
            ticker=ticker,
            description=SAFE_MESSAGE,
            compliance_status="blocked",
            evidence=[],
            contradictions=[],
            sources=sources,
        )

    return NewsCard(
        ticker=ticker,
        description=description,
        compliance_status="passed",
        evidence=evidence,
        contradictions=contradictions,
        sources=sources,
    )


__all__ = ["evaluate_news"]
