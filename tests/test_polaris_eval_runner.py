from __future__ import annotations

from types import SimpleNamespace

from polaris.eval.dataset import EvalItem
from polaris.eval.runner import (
    normalize_contexts,
    read_records_jsonl,
    run_dataset,
    write_records_jsonl,
)


class FakeApp:
    def __init__(self):
        self.calls = 0

    def invoke(self, payload):
        self.calls += 1
        return {
            "answer": f"answer: {payload['query']}",
            "contexts": [
                {"text": "dict context", "origin": "stub"},
                "string context",
                SimpleNamespace(page_content="object context"),
                None,
            ],
            "citations": [
                {"source_id": "stub-1", "snippet": "dict context", "origin": "stub"}
            ],
            "compliance_status": "passed",
        }


def make_item(item_id: str = "Q1", scenario: str = "1") -> EvalItem:
    return EvalItem(
        item_id=item_id,
        scenario=scenario,
        question=f"question {item_id}",
        golden_answer="ground truth",
    )


def test_normalize_contexts_supports_dict_string_object_and_none():
    contexts = normalize_contexts(
        [
            {"text": "dict"},
            "string",
            SimpleNamespace(text="text attr"),
            SimpleNamespace(page_content="page content"),
            None,
        ]
    )

    assert contexts == ["dict", "string", "text attr", "page content"]
    assert normalize_contexts(None) == []


def test_run_dataset_reuses_injected_workflow_and_marks_stub():
    app = FakeApp()

    records = run_dataset([make_item("Q1"), make_item("Q2")], app=app)

    assert app.calls == 2
    assert records[0].contexts == ["dict context", "string context", "object context"]
    assert records[0].context_count == 3
    assert records[0].is_stub is True
    assert records[0].is_smoke_test is True


def test_run_dataset_builds_workflow_only_once(monkeypatch):
    app = FakeApp()
    builds = 0

    def build():
        nonlocal builds
        builds += 1
        return app

    monkeypatch.setattr("polaris.graph.workflow.build_workflow", build)

    run_dataset([make_item("Q1"), make_item("Q2")])

    assert builds == 1
    assert app.calls == 2


def test_records_jsonl_round_trip(tmp_path):
    records = run_dataset([make_item()], app=FakeApp())
    path = write_records_jsonl(records, tmp_path / "records.jsonl")

    restored = read_records_jsonl(path)

    assert restored[0].to_dict() == records[0].to_dict()
