"""scripts/accept_watchdog.py 的 CI 驗收測試（token-free）。

用 importlib 從檔案載入（scripts/ 非套件），跑預設事件集 → 應 PASS、exit 0、
且輸出不含任何買賣關鍵字（NFR-031）。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "accept_watchdog.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("accept_watchdog", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_accept_watchdog_default_events_pass(capsys):
    module = _load_script()
    rc = module.main([])
    out = capsys.readouterr().out

    assert rc == 0
    assert "PASS" in out

    from polaris.graph.compliance import BUYSELL_KEYWORDS
    for kw in BUYSELL_KEYWORDS:
        assert kw not in out


def test_check_events_flags_severity_and_redteam():
    """直接打 check_events：紅隊集應全 blocked、正常事件 severity 正確。"""
    module = _load_script()
    from polaris.graph.watchdog import load_mock_events

    fixture = Path(__file__).resolve().parent / "fixtures" / "watchdog_events.json"
    problems, passed, blocked = module.check_events(load_mock_events(fixture))

    assert problems == []          # 內建事件集應全數通過契約檢查
    assert blocked == 1            # 只有 1 筆紅隊
    assert passed == 4


def test_check_events_flags_normal_event_that_gets_blocked():
    """正常（非 redteam）事件若被合規攔下 → check_events 必須回 problems。"""
    module = _load_script()
    from datetime import datetime

    from polaris.graph.watchdog.events import MopsEvent

    blocked_normal = MopsEvent(
        event_id="mops-normal-blocked-001",   # 非 redteam
        ticker="2330",
        published_at=datetime(2026, 6, 10, 9, 0),
        doc_type="重大訊息",
        title="某公司公告",
        content="獲利看好，建議買進，逢低加碼。",   # 觸發合規攔截 → blocked
    )
    problems, passed, blocked = module.check_events([blocked_normal])

    assert blocked == 1 and passed == 0
    assert any("正常事件被攔" in p for p in problems)
