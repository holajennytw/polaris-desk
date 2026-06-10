"""Polaris Desk — Watchdog Agent（specs/003）公開 API。

事件驅動合規 Agent：MOPS 公告 → 合規摘要 → WatchdogAlert。
生產者只需 ``run_watchdog(event)``；R7 消費 ``WatchdogAlert``。
"""
from polaris.graph.watchdog.agent import run_watchdog
from polaris.graph.watchdog.events import MopsEvent, load_mock_events
from polaris.graph.watchdog.state import WatchdogAlert, WatchdogSeverity

__all__ = [
    "MopsEvent",
    "WatchdogAlert",
    "WatchdogSeverity",
    "load_mock_events",
    "run_watchdog",
]
