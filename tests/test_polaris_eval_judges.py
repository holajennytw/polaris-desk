from polaris.eval.dataset import EvalItem
from polaris.eval.judges import JudgeVote, judge_records, majority_passed, parse_verdict
from polaris.eval.runner import EvalRecord


def test_judge_json_verdict_and_majority():
    valid = parse_verdict("gemini", "model", '{"verdict":"PASS","reason":"grounded"}')
    malformed = parse_verdict("openai", "model", "not json")

    assert valid.passed is True
    assert malformed.passed is False
    assert malformed.error
    assert majority_passed(
        [
            valid,
            JudgeVote("openai", "model", True, "ok"),
            JudgeVote("anthropic", "model", False, "fail"),
        ]
    )
    assert not majority_passed([valid, malformed])


def test_provider_exception_is_recorded_as_fail_closed():
    item = EvalItem(
        item_id="Q1",
        scenario="1",
        question="question",
        golden_answer="answer",
    )
    record = EvalRecord(item=item, answer="answer", contexts=["context"])

    votes = judge_records(
        [record],
        clients={
            "gemini": ("model", lambda model, prompt: '{"verdict":"PASS","reason":"ok"}'),
            "openai": ("model", lambda model, prompt: (_ for _ in ()).throw(TimeoutError())),
            "anthropic": ("model", lambda model, prompt: "invalid"),
        },
    )["Q1"]

    assert [vote.passed for vote in votes] == [True, False, False]
    assert votes[1].error
    assert votes[2].error
