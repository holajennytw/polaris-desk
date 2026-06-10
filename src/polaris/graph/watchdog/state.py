"""Watchdog Agent 輸出狀態（specs/003 / R3 開工指南 §3）。

``WatchdogAlert`` 是 ``run_watchdog`` 的輸出契約，也是 R7 Alert Inbox 的消費介面。
severity 分級規則：
- alert   → 重大訊息（重大 = 法規要求揭露的重要事項）
- watch   → 法說公告 / 財報公告（定期重要揭露）
- info    → 其他例行公告
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from polaris.graph.state import Citation
from polaris.graph.watchdog.events import MopsDocType

WatchdogSeverity = Literal["info", "watch", "alert"]
WatchdogComplianceStatus = Literal["passed", "blocked"]

#: doc_type → severity 映射（固定規則，不由 LLM 決定）。
_SEVERITY_MAP: dict[MopsDocType, WatchdogSeverity] = {
    "重大訊息": "alert",
    "法說公告": "watch",
    "財報公告": "watch",
    "其他": "info",
}


def classify_severity(doc_type: MopsDocType) -> WatchdogSeverity:
    """依 doc_type 決定 severity（確定性，不走 LLM）。"""
    return _SEVERITY_MAP.get(doc_type, "info")


@dataclass
class WatchdogAlert:
    """Watchdog 輸出契約（R7 Alert Inbox + NotificationService 消費端）。"""

    event_id: str
    ticker: str
    summary: str
    compliance_status: WatchdogComplianceStatus
    severity: WatchdogSeverity
    evidence: list[Citation] = field(default_factory=list)


__all__ = [
    "WatchdogAlert",
    "WatchdogComplianceStatus",
    "WatchdogSeverity",
    "classify_severity",
]
