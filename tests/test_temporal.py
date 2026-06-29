"""D6 — Temporal Anchoring（FR-007）：把「最近兩季 / 2024 全年」解析成季別清單。

季別字串格式對齊 vectorstore 慣例（"2024Q3"），供 retriever 以
filters={"period": ...} 取對應期間資料。相對期間（最近 N 季）以可注入的
anchor 解析，預設 "2025Q1"（待 R4 提供 DB 最新季別後改為動態）。
"""
from __future__ import annotations

import pytest

from polaris.graph import temporal


@pytest.fixture(autouse=True)
def _isolate_anchor_cache():
    """active_anchor 的 process 級 lru_cache 會跨測試外洩；每測前後清乾淨，避免某測
    注入的 anchor（如 2026Q1）污染依預設 anchor 的 E2E 測試。"""
    temporal._cached_anchor.cache_clear()
    yield
    temporal._cached_anchor.cache_clear()


class TestParseAbsoluteQuarter:
    def test_compact_form(self):
        spec = temporal.parse_period("台積電 2024Q3 毛利率")
        assert spec.kind == "quarter"
        assert spec.quarters == ["2024Q3"]

    def test_spaced_form(self):
        # 對齊既有 e2e 範例問句「台積電 2025 Q1 營收 YoY 是多少？」
        spec = temporal.parse_period("台積電 2025 Q1 營收 YoY 是多少？")
        assert spec.kind == "quarter"
        assert spec.quarters == ["2025Q1"]

    def test_chinese_quarter_form(self):
        spec = temporal.parse_period("2024年第三季營運重點")
        assert spec.kind == "quarter"
        assert spec.quarters == ["2024Q3"]


class TestParseFiscalYear:
    def test_full_year(self):
        spec = temporal.parse_period("2024全年營收")
        assert spec.kind == "fiscal_year"
        assert spec.quarters == ["2024Q1", "2024Q2", "2024Q3", "2024Q4"]

    def test_year_only(self):
        spec = temporal.parse_period("2023年的表現")
        assert spec.kind == "fiscal_year"
        assert spec.quarters == ["2023Q1", "2023Q2", "2023Q3", "2023Q4"]


class TestParseRecentQuarters:
    def test_recent_two_quarters_default_anchor(self):
        spec = temporal.parse_period("最近兩季毛利率趨勢")
        assert spec.kind == "recent_quarters"
        assert spec.quarters == ["2025Q1", "2024Q4"]

    def test_recent_one_quarter(self):
        assert temporal.parse_period("最近一季").quarters == ["2025Q1"]

    def test_jin_three_quarters_crosses_year_boundary(self):
        assert temporal.parse_period("近三季").quarters == ["2025Q1", "2024Q4", "2024Q3"]

    def test_custom_anchor(self):
        spec = temporal.parse_period("最近兩季", anchor="2024Q2")
        assert spec.quarters == ["2024Q2", "2024Q1"]


class TestActiveAnchor:
    """動態 anchor（解 issue：『最近一季』曾凍結在 2025Q1）：有憑證 → DB 最新已公布季，
    無憑證（CI）→ DEFAULT_ANCHOR，與 stub 語料最新季一致、保持確定性。"""

    def test_falls_back_to_default_when_unavailable(self, monkeypatch):
        from polaris.llm import gemini

        monkeypatch.setattr(gemini, "available", lambda: False)
        temporal._cached_anchor.cache_clear()
        assert temporal.active_anchor() == temporal.DEFAULT_ANCHOR

    def test_uses_store_latest_reported_quarter_when_available(self, monkeypatch):
        monkeypatch.setattr(temporal, "_latest_reported_quarter", lambda: "2026Q1")
        temporal._cached_anchor.cache_clear()
        assert temporal.active_anchor() == "2026Q1"

    def test_planner_resolves_recent_against_active_anchor(self, monkeypatch):
        from polaris.graph.nodes import stubs

        monkeypatch.setattr(temporal, "active_anchor", lambda: "2026Q1")
        out = stubs.planner({"query": "最近一季營收年增率表現如何？"})
        assert out["period"].kind == "recent_quarters"
        assert out["period"].quarters == ["2026Q1"]


class TestParseNone:
    def test_no_temporal_phrase(self):
        spec = temporal.parse_period("台積電毛利率為什麼下滑")
        assert spec.kind == "none"
        assert spec.quarters == []


class TestDeterminism:
    def test_same_input_same_output(self):
        q = "比較最近兩季"
        assert temporal.parse_period(q) == temporal.parse_period(q)


class TestTemporalAnchoringE2E:
    """端到端：planner 解析期間 → state['period']；retriever 只取對應季別資料。"""

    def _run(self, query: str):
        from polaris.graph.workflow import build_workflow

        return build_workflow().invoke({"query": query})

    def test_period_recorded_in_state(self):
        result = self._run("台積電最近兩季毛利率趨勢")
        period = result.get("period")
        assert period is not None
        assert period.kind == "recent_quarters"
        assert period.quarters == ["2025Q1", "2024Q4"]

    def test_fiscal_year_pulls_four_quarters(self):
        result = self._run("台積電 2024全年 營收")
        quarters = {c["period"] for c in result["contexts"]}
        assert quarters == {"2024Q1", "2024Q2", "2024Q3", "2024Q4"}

    def test_recent_two_quarters_pulls_two(self):
        result = self._run("台積電最近兩季營收")
        quarters = {c["period"] for c in result["contexts"]}
        assert quarters == {"2025Q1", "2024Q4"}

    def test_single_quarter_pulls_one(self):
        result = self._run("台積電 2025 Q1 營收 YoY 是多少？")
        assert [c["period"] for c in result["contexts"]] == ["2025Q1"]

    def test_uncovered_period_returns_no_context_and_admits_gap(self):
        # honest demo：問未入庫季別 → 不編造，answer 表明資料不足
        result = self._run("台積電 2030Q1 營收")
        assert result["contexts"] == []
        assert "資料不足" in result["answer"]

    def test_unreported_next_quarter_pivots_to_anchor_with_note(self, monkeypatch):
        """顯式問『剛結束、財報尚未公布的下一季』（已公布到 2025Q1 時問 2025Q2）→
        補退回最新已公布季檢索 + period_note 誠實說明，而非乾回『資料不足』。"""
        monkeypatch.setattr(temporal, "active_anchor", lambda: "2025Q1")
        result = self._run("台積電 2025Q2 每股盈餘")
        note = result.get("period_note", "")
        assert "2025Q2" in note and "尚未公布" in note and "2025Q1" in note
        # 退回季別（最新已公布季）有被加入檢索
        assert "2025Q1" in {c["period"] for c in result["contexts"]}
        # 答案誠實提到尚未公布（fallback 草稿帶 note；CI 無金鑰走 fallback）
        assert "尚未公布" in result["answer"]

    def test_no_temporal_phrase_returns_default_context(self):
        result = self._run("台積電毛利率為什麼下滑")
        assert len(result["contexts"]) >= 1
