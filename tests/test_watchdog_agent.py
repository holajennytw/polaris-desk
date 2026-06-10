"""Watchdog Agent 測試（specs/003）。

全程 TDD、token=0：確定性 fallback 走確定性路徑（無金鑰）；
NFR-031 紅線由 compliance_agent floor 守住（不需真 LLM）。
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from polaris.graph.watchdog.agent import run_watchdog, _fallback_summary, _build_evidence
from polaris.graph.watchdog.events import MopsEvent, load_mock_events
from polaris.graph.watchdog.state import WatchdogAlert, classify_severity
from tests.conftest import ApiError, FakeLLM

FIXTURE = Path(__file__).parent / "fixtures" / "watchdog_events.json"

TS = datetime(2026, 6, 10, 9, 0)


def make_event(**overrides) -> MopsEvent:
    base = dict(
        event_id="mops-2330-20260610-001",
        ticker="2330",
        published_at=TS,
        doc_type="重大訊息",
        title="台積電董事會決議現金增資",
        content="本公司董事會決議通過現金增資500億元，供先進製程擴廠。",
    )
    base.update(overrides)
    return MopsEvent(**base)


# ── MopsEvent 模型 ───────────────────────────────────────────────────────────

class TestMopsEvent:
    def test_valid_event(self):
        ev = make_event()
        assert ev.ticker == "2330"
        assert ev.doc_type == "重大訊息"

    def test_frozen(self):
        from pydantic import ValidationError
        ev = make_event()
        with pytest.raises(ValidationError):
            ev.ticker = "9999"  # type: ignore[misc]

    def test_load_mock_events(self):
        events = load_mock_events(FIXTURE)
        assert len(events) == 5
        assert all(isinstance(e, MopsEvent) for e in events)

    def test_load_event_ids_unique(self):
        events = load_mock_events(FIXTURE)
        ids = [e.event_id for e in events]
        assert len(ids) == len(set(ids))


# ── severity 分級 ────────────────────────────────────────────────────────────

class TestClassifySeverity:
    @pytest.mark.parametrize("doc_type,expected", [
        ("重大訊息", "alert"),
        ("法說公告", "watch"),
        ("財報公告", "watch"),
        ("其他", "info"),
    ])
    def test_severity_map(self, doc_type, expected):
        assert classify_severity(doc_type) == expected


# ── fallback 摘要 ────────────────────────────────────────────────────────────

class TestFallbackSummary:
    def test_contains_doc_type_and_ticker(self):
        ev = make_event()
        s = _fallback_summary(ev)
        assert "重大訊息" in s
        assert "2330" in s
        assert ev.title in s

    def test_truncates_long_content(self):
        ev = make_event(content="X" * 500)
        s = _fallback_summary(ev)
        assert len(s) < 500

    def test_empty_content_no_summary_line(self):
        ev = make_event(content="")
        s = _fallback_summary(ev)
        assert "事件摘要" not in s

    def test_deterministic(self):
        ev = make_event()
        assert _fallback_summary(ev) == _fallback_summary(ev)


# ── 接地證據 ─────────────────────────────────────────────────────────────────

class TestBuildEvidence:
    def test_evidence_has_event_id(self):
        ev = make_event()
        evidence = _build_evidence(ev)
        assert len(evidence) == 1
        assert evidence[0].source_id == ev.event_id
        assert evidence[0].origin == "news"
        assert ev.title in evidence[0].snippet


# ── run_watchdog — 基本流 ────────────────────────────────────────────────────

class TestRunWatchdog:
    def test_produces_alert(self):
        alert = run_watchdog(make_event())
        assert isinstance(alert, WatchdogAlert)
        assert alert.event_id == "mops-2330-20260610-001"
        assert alert.ticker == "2330"
        assert alert.summary
        assert alert.evidence

    def test_severity_from_doc_type(self):
        assert run_watchdog(make_event(doc_type="重大訊息")).severity == "alert"
        assert run_watchdog(make_event(
            event_id="e2", doc_type="法說公告",
        )).severity == "watch"
        assert run_watchdog(make_event(
            event_id="e3", doc_type="財報公告",
        )).severity == "watch"
        assert run_watchdog(make_event(
            event_id="e4", doc_type="其他",
        )).severity == "info"

    def test_compliance_status_passed_for_clean_event(self):
        alert = run_watchdog(make_event())
        assert alert.compliance_status == "passed"

    def test_deterministic_no_client(self):
        """SC-NC-004：同事件兩次跑，結果完全一致。"""
        ev = make_event()
        a1 = run_watchdog(ev)
        a2 = run_watchdog(ev)
        assert a1.summary == a2.summary
        assert a1.compliance_status == a2.compliance_status
        assert a1.severity == a2.severity


# ── NFR-031 紅線 ─────────────────────────────────────────────────────────────

class TestComplianceGate:
    def test_redteam_event_content_blocked(self):
        """事件 content 含「建議買進」→ compliance blocked，摘要為安全訊息。"""
        from polaris.graph.compliance import BUYSELL_KEYWORDS, SAFE_MESSAGE
        ev = make_event(
            event_id="mops-9999-redteam-001",
            ticker="9999",
            title="某公司重大利多",
            content="獲利前景看好，建議買進！股價偏低，是加碼好時機，看多後市。",
        )
        alert = run_watchdog(ev)
        assert alert.compliance_status == "blocked"
        assert alert.summary == SAFE_MESSAGE
        for kw in BUYSELL_KEYWORDS:
            assert kw not in alert.summary

    def test_fixture_redteam_blocked(self):
        """fixture 內的紅隊事件（mops-9999-redteam-001）必定被攔。"""
        events = load_mock_events(FIXTURE)
        redteam = next(e for e in events if "redteam" in e.event_id)
        alert = run_watchdog(redteam)
        assert alert.compliance_status == "blocked"

    def test_fixture_clean_events_all_passed(self):
        """fixture 內的 4 筆正常事件應全部通過合規。"""
        events = load_mock_events(FIXTURE)
        clean = [e for e in events if "redteam" not in e.event_id]
        for ev in clean:
            alert = run_watchdog(ev)
            assert alert.compliance_status == "passed", (
                f"{ev.event_id} 不應被攔：summary={alert.summary!r}"
            )


# ── smart 層（FakeLLM）──────────────────────────────────────────────────────

class TestSmartLayer:
    def test_uses_llm_when_client_provided(self):
        """有 client 時用 LLM 回傳的摘要（FakeLLM 固定回 '事件已確認。'）。"""
        client = FakeLLM(response="台積電宣布現金增資500億元，供先進製程擴廠。")
        alert = run_watchdog(make_event(), client=client)
        assert alert.compliance_status == "passed"
        assert "台積電" in alert.summary or "500" in alert.summary

    def test_llm_violation_blocked_by_floor(self):
        """LLM 產出含買賣建議 → floor 攔住，不穿透。"""
        client = FakeLLM(response="建議買進台積電，逢低布局。")
        alert = run_watchdog(make_event(), client=client)
        assert alert.compliance_status == "blocked"

    def test_llm_failure_falls_back_to_deterministic(self):
        """LLM 拋例外 → 退 fallback，不讓 agent 掛掉。"""
        client = FakeLLM(error=ApiError(503), fail_times=99)
        alert = run_watchdog(make_event(), client=client)
        assert alert.summary  # fallback 產出非空
        assert alert.compliance_status == "passed"


# ── CLI smoke ────────────────────────────────────────────────────────────────

def test_cli_main_prints_alerts_and_stats(capsys):
    from polaris.graph.watchdog.__main__ import main

    exit_code = main([str(FIXTURE)])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "Watchdog Alert" in out
    assert "passed=" in out and "blocked=1" in out
    # 紅隊事件的買賣建議不得出現在輸出（SAFE_MESSAGE 安全）
    from polaris.graph.compliance import BUYSELL_KEYWORDS
    for kw in BUYSELL_KEYWORDS:
        assert kw not in out
