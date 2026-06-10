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


def _run_deep_research(question: str) -> dict:
    from polaris.graph.deep_research.agent import run_deep_research

    r = run_deep_research(question)
    return {
        "answer": r.final_answer,
        "contexts": [{"text": c.snippet} for c in r.evidence],
        "citations": r.evidence,
        "compliance_status": r.compliance_status,
    }


def run_item(item: EvalItem) -> EvalRecord:
    """跑一題，回 :class:`EvalRecord`。場景 2 走 Deep Research，其餘走 workflow。"""
    result = _run_deep_research(item.question) if item.scenario == "2" else _run_workflow(
        item.question
    )
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
