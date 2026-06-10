"""Polaris Desk Eval pipeline（R5 / G3 硬門檻 Eval ≥ 80%）— 公開 API。

題庫 CSV → runner（workflow / Deep Research）→ smoke 達標率 + Ragas（optional）。
"""
from polaris.eval.dataset import EvalItem, load_dataset
from polaris.eval.runner import EvalRecord, run_dataset, run_item
from polaris.eval.score import SmokeReport, smoke_score

__all__ = [
    "EvalItem",
    "EvalRecord",
    "SmokeReport",
    "load_dataset",
    "run_dataset",
    "run_item",
    "smoke_score",
]
