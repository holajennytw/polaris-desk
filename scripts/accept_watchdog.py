#!/usr/bin/env python3
"""Watchdog 驗收（token-free / CI-safe）。

對一組 mock MOPS 事件跑完整 Watchdog 管線，並**斷言**輸出契約 + NFR-031 紅線。
無金鑰走確定性 fallback（0 外呼、0 token）——雲端 / CI 直接可跑。

驗收項目：
- 每筆事件 → ``WatchdogAlert``，必填欄位齊（event_id / ticker / summary /
  compliance_status / severity）、evidence 至少 1 條（接地）。
- ``severity`` 依 ``doc_type`` 規則正確（重大訊息=alert、法說/財報=watch、其他=info）。
- 紅隊事件（event_id 含 ``redteam``）→ ``compliance_status="blocked"``、
  ``summary == SAFE_MESSAGE``。
- 正常事件 → ``compliance_status="passed"``。
- 整體輸出（summary + evidence 片段）**0 買賣建議**（NFR-031）。
- 確定性：同事件兩次 ``run_watchdog`` 結果一致（SC-NC-004）。

用法::

    python scripts/accept_watchdog.py [events.json]   # 省略則用內建 demo 事件集

退出碼：``0`` = PASS；``1`` = FAIL（印出每條不符項）。
"""
from __future__ import annotations

import sys
from pathlib import Path

from polaris.graph.compliance import BUYSELL_KEYWORDS, SAFE_MESSAGE
from polaris.graph.watchdog import load_mock_events, run_watchdog
from polaris.graph.watchdog.state import classify_severity

_DEFAULT_EVENTS = (
    Path(__file__).resolve().parent.parent
    / "src" / "polaris" / "graph" / "watchdog" / "data" / "watchdog_events.json"
)

_REQUIRED_FIELDS = ("event_id", "ticker", "summary", "compliance_status", "severity")


def check_events(events) -> tuple[list[str], int, int]:
    """回 (problems, passed, blocked)。problems 為空 ⇒ 驗收通過。"""
    problems: list[str] = []
    rendered: list[str] = []
    passed = blocked = 0

    for event in events:
        alert = run_watchdog(event)
        again = run_watchdog(event)

        for field in _REQUIRED_FIELDS:
            if not getattr(alert, field, None):
                problems.append(f"{event.event_id}: 缺必填欄位 {field}")
        if not alert.evidence:
            problems.append(f"{event.event_id}: evidence 空（接地缺）")

        expected_sev = classify_severity(event.doc_type)
        if alert.severity != expected_sev:
            problems.append(f"{event.event_id}: severity={alert.severity} 應為 {expected_sev}")

        if (alert.summary, alert.compliance_status, alert.severity) != (
            again.summary, again.compliance_status, again.severity
        ):
            problems.append(f"{event.event_id}: 非確定性（兩次結果不同）")

        if "redteam" in event.event_id:
            if alert.compliance_status != "blocked":
                problems.append(f"{event.event_id}: 紅隊未被攔（{alert.compliance_status}）")
            if alert.summary != SAFE_MESSAGE:
                problems.append(f"{event.event_id}: 紅隊 summary 非 SAFE_MESSAGE")

        if alert.compliance_status == "passed":
            passed += 1
        else:
            blocked += 1
        rendered.append(alert.summary + " " + " ".join(c.snippet for c in alert.evidence))

    blob = "\n".join(rendered)
    for kw in BUYSELL_KEYWORDS:
        if kw in blob:
            problems.append(f"NFR-031 破口：輸出含買賣關鍵字「{kw}」")

    return problems, passed, blocked


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    path = Path(args[0]) if args else _DEFAULT_EVENTS

    events = load_mock_events(path)
    problems, passed, blocked = check_events(events)

    print(f"=== Watchdog 驗收（{len(events)} 事件 · {path.name}）===")
    print(f"passed={passed} blocked={blocked} · 檢查：契約欄位 / severity 規則 / 紅隊攔截 / 確定性 / NFR-031")
    if not problems:
        print("✅ PASS：欄位齊、severity 正確、紅隊攔成 SAFE_MESSAGE、0 買賣建議、確定性。")
        return 0
    print("❌ FAIL：")
    for p in problems:
        print("  -", p)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
