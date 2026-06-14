"""CLI demo：``python -m polaris.graph.watchdog [events.json] [--notify]``。

讀 mock 事件 fixture（預設：隨套件內建 5 筆）、跑完整 Watchdog 管線、印 alerts 與統計。
``--notify``：同步把 alert 送進 NotificationService，展示完整 Watchdog→通知中心管線。
無金鑰走確定性 fallback（token=0、可重現）。
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from polaris.graph.watchdog.agent import run_watchdog
from polaris.graph.watchdog.events import load_mock_events

#: 隨套件出貨的內建示範事件（5 筆：4 正常 + 1 紅隊）。
_DEFAULT_EVENTS = Path(__file__).resolve().parent / "data" / "watchdog_events.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m polaris.graph.watchdog",
        description="Watchdog Agent demo — 讀 mock MOPS 事件、跑合規掃描、印 alert",
    )
    parser.add_argument(
        "events",
        nargs="?",
        default=str(_DEFAULT_EVENTS),
        help="事件 JSON 檔（預設：內建 5 筆示範事件）",
    )
    parser.add_argument(
        "--notify",
        action="store_true",
        help="送進 NotificationService，展示 Watchdog→通知中心全管線",
    )
    args = parser.parse_args(argv)

    events = load_mock_events(Path(args.events))
    counts: Counter[str] = Counter()
    print(f"=== Watchdog Alert（共 {len(events)} 則事件）===")

    if args.notify:
        from polaris.graph.watchdog.notify import watch_and_notify
        from polaris.notifications.service import NotificationService

        svc = NotificationService()
        for event in events:
            alert, outcome = watch_and_notify(event, svc)
            counts[alert.compliance_status] += 1
            status_tag = "🚨 BLOCKED" if alert.compliance_status == "blocked" else f"[{alert.severity.upper()}]"
            print(f"{status_tag} {alert.ticker} — {alert.summary[:80]}")
            print(f"         → notification: {outcome.status}")
        unread = svc.inbox.unread_count()
        print(f"\npassed={counts['passed']} blocked={counts['blocked']}"
              f"  (events={len(events)})  inbox_unread={unread}")
    else:
        for event in events:
            alert = run_watchdog(event)
            counts[alert.compliance_status] += 1
            status_tag = "🚨 BLOCKED" if alert.compliance_status == "blocked" else f"[{alert.severity.upper()}]"
            print(f"{status_tag} {alert.ticker} — {alert.summary[:80]}")
        print(
            f"\npassed={counts['passed']} blocked={counts['blocked']}"
            f"  (events={len(events)})"
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
