from __future__ import annotations

from polaris.eval.dataset import EvalItem
from polaris.eval.judges import JudgeVote
from polaris.eval.runner import EvalRecord
from polaris.eval.score import RAGAS_THRESHOLDS, _env_positive_int, ragas_score, score_records


def make_record(*, contexts: list[str] | None = None) -> EvalRecord:
    item = EvalItem(
        item_id="Q1",
        scenario="1",
        question="question",
        golden_answer="ground truth",
    )
    return EvalRecord(
        item=item,
        answer="grounded answer",
        contexts=["context"] if contexts is None else contexts,
        ground_truth=item.golden_answer,
        citations=[{"source_id": "s1", "snippet": "context", "origin": "embedding"}],
        compliance_status="passed",
        context_source="embedding",
    )


def test_smoke_mode_does_not_call_ragas():
    def fail(_records):
        raise AssertionError("RAGAS must not run in smoke mode")

    report = score_records([make_record()], mode="smoke", ragas_evaluator=fail)

    assert report.scores[0].passed is True


def test_ragas_maps_per_case_scores_and_threshold_boundaries():
    values = dict(RAGAS_THRESHOLDS)
    report = score_records(
        [make_record()],
        mode="flash",
        ragas_evaluator=lambda records: [values],
    )

    assert report.scores[0].ragas == values
    assert report.scores[0].passed is True


def test_ragas_nan_is_a_fail_closed_score():
    report = score_records(
        [make_record()],
        mode="flash",
        ragas_evaluator=lambda records: [
            {
                "context_precision": float("nan"),
                "faithfulness": 1.0,
                "answer_relevancy": 1.0,
            }
        ],
    )

    assert report.scores[0].passed is False
    assert "context_precision_below_0.85" in report.scores[0].failed_reasons


def test_ragas_runtime_limit_uses_safe_positive_default(monkeypatch):
    monkeypatch.setenv("RAGAS_MAX_WORKERS", "0")
    assert _env_positive_int("RAGAS_MAX_WORKERS", 4) == 4

    monkeypatch.setenv("RAGAS_MAX_WORKERS", "3")
    assert _env_positive_int("RAGAS_MAX_WORKERS", 4) == 3


def test_empty_contexts_are_unscorable_and_not_sent_to_ragas():
    record = make_record(contexts=[])
    called = False

    def evaluator(_records):
        nonlocal called
        called = True
        return []

    scores = ragas_score([record], evaluator=evaluator)
    report = score_records([record], mode="flash", ragas_evaluator=evaluator)

    assert called is False
    assert scores["Q1"]["faithfulness"] is None
    assert report.scores[0].scorable is False
    assert "unscorable_empty_contexts" in report.scores[0].failed_reasons


def test_gate_requires_two_of_three_judges(monkeypatch):
    votes = [
        JudgeVote("gemini", "g", True, "ok"),
        JudgeVote("openai", "o", True, "ok"),
        JudgeVote("anthropic", "a", False, "not enough"),
    ]
    monkeypatch.setattr(
        "polaris.eval.score.judge_records",
        lambda records, clients=None: {"Q1": votes},
    )

    report = score_records(
        [make_record()],
        mode="gate",
        ragas_evaluator=lambda records: [dict(RAGAS_THRESHOLDS)],
        judge_clients={},
    )

    assert report.scores[0].passed is True
