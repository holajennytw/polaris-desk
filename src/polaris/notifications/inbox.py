"""In-app 收件匣（specs/002 / FR-NC-007）。

Phase 1 為 in-memory 單人收件匣；持久化（BigQuery 營運 dataset）是 Phase 2
（PRD OQ-1）。``Notification`` 維持 frozen——``mark_read`` 以 ``model_copy``
產生新實例替換存放，外部持有的物件永遠不變。
"""
from __future__ import annotations

from datetime import datetime

from polaris.notifications.model import Notification, NotificationType


class InAppInbox:
    """通知收件匣：未讀計數、時間倒序列表、標已讀、篩選、外送降級記錄。"""

    def __init__(self) -> None:
        self._items: dict[str, Notification] = {}
        #: 外送管道重試用盡後的降級記錄（FR-NC-009 不無聲丟失）。
        self.delivery_failures: list[str] = []

    def add(self, notification: Notification) -> None:
        """新增；同 ``notification_id`` 覆寫（digest 合併更新走這裡）。"""
        self._items[notification.notification_id] = notification

    def get(self, notification_id: str) -> Notification | None:
        return self._items.get(notification_id)

    def unread_count(self) -> int:
        return sum(1 for n in self._items.values() if n.read_at is None)

    def list(
        self,
        *,
        ticker: str | None = None,
        type: NotificationType | None = None,  # noqa: A002 — 對齊契約欄位名
    ) -> list[Notification]:
        """``created_at`` 倒序；可依公司代號 / 類型篩選。"""
        items = [
            n
            for n in self._items.values()
            if (ticker is None or n.ticker == ticker) and (type is None or n.type == type)
        ]
        return sorted(items, key=lambda n: n.created_at, reverse=True)

    def record_failure(self, msg: str) -> None:
        """外送管道重試用盡後的降級記錄（FR-NC-009 不無聲丟失）。"""
        self.delivery_failures.append(msg)

    def mark_read(self, notification_id: str, *, at: datetime) -> Notification | None:
        """標已讀；回更新後的新實例，查無回 None。``at`` 由呼叫端傳（不取 now）。"""
        current = self._items.get(notification_id)
        if current is None:
            return None
        updated = current.model_copy(update={"read_at": at})
        self._items[notification_id] = updated
        return updated


__all__ = ["InAppInbox"]
