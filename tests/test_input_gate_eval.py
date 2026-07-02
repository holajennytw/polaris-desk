"""輸入端範圍 gate 對 eval 金標集的「不誤擋」回歸測試（確定性、token-free）。

驗兩件事，是 INPUT_GATE_SCOPE 上線前的安全門檻：
1. **注入 floor 零誤擋**：142 題正當投研題無一命中 :func:`flags_injection`。
2. **floor 正向放行覆蓋率高**：≥95% 的真問題被確定性 floor 放行、**根本不會進 LLM**，
   故與 LLM 分類器行為無關即安全；殘餘尾巴（非 canonical 標的的產業題）才交 LLM。

另反向驗明顯離題題「不」被 floor 誤放行（才能落到 LLM 被擋）。擴充關鍵字集時，這裡的
覆蓋率會變動——調 ``COVERAGE_FLOOR`` 前先確認新題確實被涵蓋、且離題題仍為 0。
"""
from __future__ import annotations

import csv
from pathlib import Path

from polaris.graph.input_gate import flags_injection, looks_in_scope

_QUESTIONS_CSV = (
    Path(__file__).resolve().parents[1]
    / "src" / "polaris" / "eval" / "data" / "questions_v1.csv"
)

#: 覆蓋率下限（實測 97.2%）。留裕度給金標集微調，跌破即需檢視關鍵字集。
COVERAGE_FLOOR = 0.95

#: 明顯離題題：必須「不」被 floor 正向放行（否則永遠到不了 LLM smart 層、擋不掉）。
_OFF_TOPIC_SAMPLES = (
    "今天天氣如何",
    "幫我寫一首情詩",
    "推薦台北好吃的餐廳",
    "幫我翻譯這段英文句子",
    "解釋一下量子力學",
    "幫我規劃東京五日遊",
)


def _load_questions() -> list[str]:
    with _QUESTIONS_CSV.open(encoding="utf-8-sig") as f:
        return [q for row in csv.DictReader(f) if (q := (row.get("問題") or "").strip())]


def test_no_injection_false_positive_on_golden_set() -> None:
    questions = _load_questions()
    assert questions, "eval 金標集為空，路徑或欄名可能改了"
    flagged = [q for q in questions if flags_injection(q)]
    assert flagged == [], f"注入 floor 誤擋正當投研題：{flagged}"


def test_scope_floor_coverage_meets_threshold() -> None:
    questions = _load_questions()
    allowed = sum(1 for q in questions if looks_in_scope(q))
    coverage = allowed / len(questions)
    assert coverage >= COVERAGE_FLOOR, (
        f"floor 正向放行覆蓋率 {coverage:.1%} < {COVERAGE_FLOOR:.0%}；"
        "殘餘題會全落到 LLM smart 層，誤擋風險上升"
    )


def test_off_topic_not_floor_allowed() -> None:
    leaked = [q for q in _OFF_TOPIC_SAMPLES if looks_in_scope(q)]
    assert leaked == [], f"離題題被 floor 誤放行、到不了 LLM：{leaked}"
