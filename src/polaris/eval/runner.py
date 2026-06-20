"""Eval runner：每題跑系統、收齊 Ragas 四件套（R5 開工指南 §1、§3）。

- 場景 1/3/4：走 5 節點 workflow（``app.invoke({"query": ...})``）。
- 場景 2（同業比較）：走 Deep Research（``run_deep_research``），
  evidence（Citation）轉 contexts。

R4 接真檢索後 contexts 自動變真語料，本 runner 一行不用改
（workflow / deep research 的回傳契約不變）。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from polaris.eval.dataset import EvalItem
from polaris.retrieval.colpali_retriever import active_colpali_retriever


@dataclass
class EvalRecord:
    """單題執行結果 = Ragas 四件套 + 合規/引用中繼資料。"""

    item: EvalItem
    answer: str
    contexts: list[str] = field(default_factory=list)
    ground_truth: str = ""
    compliance_status: str = "unknown"
    citation_count: int = 0


def _run_workflow(question: str) -> dict:
    from polaris.graph.workflow import build_workflow

    app = build_workflow()
    return app.invoke({"query": question})


def _run_visual(question: str) -> dict:
    """場景 3（圖表題）走第 4 路 ColPali 視覺檢索（gated）。

    依賴 R4 的 query encoder（issue #133）。未接前 ``active_colpali_retriever()`` 回 None，
    這裡**刻意拋錯**而非靜默退回文字 workflow——看圖題用文字代跑會把「視覺路沒接」
    誤報成「檢索失敗」，違反誠實原則。encoder 到位後本函式自動走真檢索，分派不用動。

    Phase 1 只做檢索（回頁參照 contexts/citations，origin=colpali）；
    讀圖表數字回答見 Phase 2（render PDF 頁圖 → vision）。
    """
    from polaris.graph.state import Citation
    from polaris.ontology import company_name

    retriever = active_colpali_retriever()
    if retriever is None:
        raise NotImplementedError(
            "場景 3（圖表 ColPali）query encoder 尚未接（見 issue #133）；"
            "在 ColPali 查詢端編碼落地前不得用文字 workflow 代跑看圖題。"
        )
    results = retriever.retrieve(question)
    citations = [
        Citation(
            source_id=r.id,
            snippet=r.content,
            origin="colpali",
            company=company_name(r.company),
        )
        for r in results
    ]
    return {
        "answer": "",  # Phase 1 只檢索；讀數字回答見 Phase 2
        "contexts": [{"text": r.content} for r in results],
        "citations": citations,
        "compliance_status": "n/a",
    }


def _run_deep_research(question: str) -> dict:
    from polaris.graph.deep_research.agent import run_deep_research

    r = run_deep_research(question)
    return {
        "answer": r.final_answer,
        "contexts": [{"text": c.snippet} for c in r.evidence],
        "citations": r.evidence,
        "compliance_status": r.compliance_status,
    }


#: 場景 → 檢索後端分派。未列者落 ``_run_workflow``（5 節點文字 workflow）。
_DISPATCH = {
    "2": _run_deep_research,  # 同業比較
    "3": _run_visual,         # 圖表 ColPali（第 4 路，gated，依賴 #133）
}


def run_item(item: EvalItem) -> EvalRecord:
    """跑一題，回 :class:`EvalRecord`。場景 2→Deep Research、場景 3→ColPali，其餘→workflow。"""
    result = _DISPATCH.get(item.scenario, _run_workflow)(item.question)
    contexts = [c.get("text", "") for c in result.get("contexts", []) if c.get("text")]
    return EvalRecord(
        item=item,
        answer=result.get("answer", ""),
        contexts=contexts,
        ground_truth=item.golden_answer,
        compliance_status=result.get("compliance_status", "unknown"),
        citation_count=len(result.get("citations", [])),
    )


def run_dataset(items: list[EvalItem]) -> list[EvalRecord]:
    return [run_item(item) for item in items]


__all__ = ["EvalRecord", "run_dataset", "run_item"]
