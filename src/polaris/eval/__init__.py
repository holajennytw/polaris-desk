"""Polaris Desk R5 Eval 公開 API。"""
from polaris.eval.dataset import EvalItem, load_dataset, validate_dataset
from polaris.eval.runner import (
    EvalRecord,
    normalize_contexts,
    read_records_jsonl,
    run_dataset,
    run_item,
    write_records_jsonl,
)
from polaris.eval.score import EvaluationReport, SmokeReport, score_records, smoke_score

__all__ = [
    "EvalItem",
    "EvalRecord",
    "EvaluationReport",
    "SmokeReport",
    "load_dataset",
    "normalize_contexts",
    "read_records_jsonl",
    "run_dataset",
    "run_item",
    "score_records",
    "smoke_score",
    "validate_dataset",
    "write_records_jsonl",
]
