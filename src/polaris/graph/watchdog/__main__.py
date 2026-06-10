"""CLI demo：``python -m polaris.graph.watchdog <events.json>``。

讀 mock 事件 fixture、跑完整 Watchdog 管線、印 alerts 與統計。
無金鑰走確定性 fallback（token=0、可重現）。
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

from polaris.graph.watchdog.agent import run_watchdog
from polaris.graph.watchdog.events import load_mock_events


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("用法：python -m polaris.graph.watchdog <events.json>", file=sys.stderr)
        return 2

    events = load_mock_events(Path(args[0]))
    counts: Counter[str] = Counter()
    print(f"=== Watchdog Alert（共 {len(events)} 則事件）===")
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
