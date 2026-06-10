"""Composer：事件 → 通知的組裝、去重、digest 合併（specs/002 / FR-NC-005、010）。

- 去重鍵 = ``event_id``（exactly-once；同 id 不同內容以第一筆為準）。
- digest 鍵 = ``(ticker, type, occurred_at.date())``，僅 ``severity=info`` 參與
  （watch/alert 不可被摺疊稀釋）。兩鍵分離的理由見 research.md §2。
- 確定性：``notification_id = f"ntf-{event_id}"``、``created_at = occurred_at``，
  全程不取 now()、不用 uuid。
"""
from __future__ import annotations

from datetime import date

from polaris.notifications.model import (
    Notification,
    NotificationComplianceStatus,
    NotificationEvent,
)

#: digest 合併摘要用的類型中文標籤。
_TYPE_LABELS: dict[str, str] = {
    "watchdog_alert": "合規警示",
    "watchlist_event": "追蹤事件",
    "data_ingested": "新資料入庫",
    "research_done": "研究完成",
    "contradiction": "來源矛盾",
    "pipeline_health": "管線健康",
    "ops_alert": "成本警報",
    "compliance_incident": "合規事故",
}

_DigestKey = tuple[str | None, str, date]

#: digest 合併時累積的最大證據筆數（防止高頻事件無限增長）。
_EVIDENCE_CAP = 50


def summarize_event(event: NotificationEvent) -> str:
    """摘要取 body（空則退回 title），截 100 字（FR-NC-001 上限）。"""
    text = event.body or event.title
    return text[:100]


class Composer:
    """無 I/O 的純組裝層；狀態只有去重 seen set 與 digest 鍵索引。"""

    def __init__(self) -> None:
        self._seen: set[str] = set()
        self._digest_index: dict[_DigestKey, str] = {}

    # ── 去重（FR-NC-005）─────────────────────────────────────────────────

    def is_duplicate(self, event: NotificationEvent) -> bool:
        """首次見到的 event_id 註冊後回 False；再見即 True（後到丟棄）。"""
        if event.event_id in self._seen:
            return True
        self._seen.add(event.event_id)
        return False

    # ── 組裝 ────────────────────────────────────────────────────────────

    def build(
        self, event: NotificationEvent, *, compliance_status: NotificationComplianceStatus
    ) -> Notification:
        notification_id = f"ntf-{event.event_id}"
        return Notification(
            notification_id=notification_id,
            event_id=event.event_id,
            type=event.type,
            audience=event.audience,
            ticker=event.ticker,
            title=event.title,
            summary=summarize_event(event),
            severity=event.severity,
            evidence=list(event.evidence),
            deep_link=f"/notifications/{notification_id}",
            created_at=event.occurred_at,
            compliance_status=compliance_status,
        )

    # ── digest 合併（FR-NC-010）──────────────────────────────────────────

    @staticmethod
    def _event_key(event: NotificationEvent) -> _DigestKey:
        return (event.ticker, event.type, event.occurred_at.date())

    def lookup_digest(self, event: NotificationEvent) -> str | None:
        """回可合併的既有通知 id；非 info 或無同鍵通知 → None。"""
        if event.severity != "info":
            return None
        return self._digest_index.get(self._event_key(event))

    def register_digest(self, notification: Notification) -> None:
        """登記 digest 候選（僅 info；watch/alert 一律單獨成則）。"""
        if notification.severity != "info":
            return
        key = (notification.ticker, notification.type, notification.created_at.date())
        self._digest_index[key] = notification.notification_id

    def merge_digest(
        self, existing: Notification, event: NotificationEvent
    ) -> Notification:
        """把新事件併入既有通知：計數 +1、證據累積、時間推進到最新一筆。

        標題 / 摘要改用**固定模板**（不引用新事件原文）——digest 合併發生在
        合規閘門之後，模板文案保證不引入未審字句。
        """
        count = existing.digest_count + 1
        prefix = f"{existing.ticker} " if existing.ticker else ""
        label = _TYPE_LABELS.get(existing.type, existing.type)
        return existing.model_copy(
            update={
                "title": f"{prefix}今日 {count} 則更新",
                "summary": f"{label} ×{count}",
                "digest_count": count,
                "evidence": (list(existing.evidence) + list(event.evidence))[:_EVIDENCE_CAP],
                "created_at": event.occurred_at,
            }
        )


__all__ = ["Composer", "summarize_event"]
