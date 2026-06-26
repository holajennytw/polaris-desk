"""Eval runner：每題跑系統、收齊 Ragas 四件套（R5 開工指南 §1、§3）。

- 場景 1/3/4：走 5 節點 workflow（``app.invoke({"query": ...})``）。
- 場景 2（同業比較）：走 Deep Research（``run_deep_research``），
  evidence（Citation）轉 contexts。
- 場景 5（peer-compare）：走 ``/peer-compare`` 引擎（P1 接地觸點 Q076–Q080 的正式路徑）；
  公司欄格式為 ``<a_ticker>;<b_ticker>``，季別欄為財務期間。

R4 接真檢索後 contexts 自動變真語料，本 runner 一行不用改
（workflow / deep research 的回傳契約不變）。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from polaris.eval.dataset import EvalItem


@dataclass
class EvalRecord:
    """單題執行結果 = Ragas 四件套 + 合規/引用中繼資料。"""

    item: EvalItem
    answer: str
    contexts: list[str] = field(default_factory=list)
    ground_truth: str = ""
    compliance_status: str = "unknown"
    citation_count: int = 0
    #: visual_reader 是否觸發（任一 citation origin=='vision'）——#3 觸發門檻校準訊號。
    escalated: bool = False


def _run_workflow(question: str) -> dict:
    from polaris.graph.workflow import build_workflow

    app = build_workflow()
    return app.invoke({"query": question})


def _run_deep_research(question: str) -> dict:
    from polaris.graph.deep_research.agent import run_deep_research

    r = run_deep_research(question)
    return {
        "answer": r.final_answer,
        "contexts": [{"text": c.snippet} for c in r.evidence],
        "citations": r.evidence,
        "compliance_status": r.compliance_status,
    }


def _run_peer_compare(question: str, *, item=None) -> dict:
    """場景 5：呼叫 peer-compare 引擎（P1 接地觸點）；需公司欄 = '<a>;<b>'。"""
    from polaris.api import peer_compare as _peer_compare_fn

    # Parse tickers from EvalItem.company field ("2330;2454").
    company = (item.company if item else "") or ""
    tickers = [t.strip() for t in company.split(";") if t.strip()]
    if len(tickers) < 2:  # 無雙 ticker → fallback 到 deep research
        return _run_deep_research(question)

    period = (item.period if item else "") or "2025Q1"
    fiscal_period = period.split(";")[0].strip() or "2025Q1"

    from polaris.api import PeerCompareRequest

    req = PeerCompareRequest(
        a_ticker=tickers[0],
        b_ticker=tickers[1],
        fiscal_period=fiscal_period,
        question=question,
    )
    try:
        resp = _peer_compare_fn(req)
    except Exception:  # noqa: BLE001 — 無結構化資料（如離線 CI 無 BigQuery）→ 退 Deep Research
        return _run_deep_research(question)
    return {
        "answer": resp.summary,
        "contexts": [{"text": k.a.citations[0].src + " " + k.b.citations[0].src} for k in resp.kpis],
        "citations": [],
        "compliance_status": resp.compliance_status,
    }


#: 場景 → 檢索後端分派。未列者落 ``_run_workflow``（5 節點文字 workflow）。
#: 場景 3（圖表題）ColPali 已退役：Vision-OCR 入庫已把圖表文字灌進索引，
#: 看圖題改走文字 workflow（colpali_* 模組仍保留但 eval 不再分派至此）。
#: 場景 5（peer-compare）：P1 接地觸點專用路徑（需公司欄 = '<a>;<b>'）。
_DISPATCH = {
    "2": _run_deep_research,  # 同業比較 → Deep Research
    "5": _run_peer_compare,   # peer-compare 接地觸點
}


def run_item(item: EvalItem) -> EvalRecord:
    """跑一題，回 :class:`EvalRecord`。

    場景 2→Deep Research，場景 5→peer-compare，其餘→workflow。
    """
    fn = _DISPATCH.get(item.scenario, _run_workflow)
    import inspect as _inspect
    if "item" in _inspect.signature(fn).parameters:
        result = fn(item.question, item=item)
    else:
        result = fn(item.question)
    contexts = [c.get("text", "") for c in result.get("contexts", []) if c.get("text")]
    citations = result.get("citations", [])
    return EvalRecord(
        item=item,
        answer=result.get("answer", ""),
        contexts=contexts,
        ground_truth=item.golden_answer,
        compliance_status=result.get("compliance_status", "unknown"),
        citation_count=len(citations),
        escalated=any(getattr(c, "origin", None) == "vision" for c in citations),
    )


def run_dataset(items: list[EvalItem]) -> list[EvalRecord]:
    return [run_item(item) for item in items]


__all__ = ["EvalRecord", "run_dataset", "run_item"]
