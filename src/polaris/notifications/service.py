"""NotificationService —— 通知管線唯一入口（specs/002 / FR-NC-002）。

管線順序：validate → 去重 → 證據檢查 → Compliance Gate → 訂閱過濾 →
digest 合併 / 派送 → 管道路由。契約見
``specs/002-notification-center/contracts/notification-pipeline.md``。

合規語意（NFR-031）：
- audience=user 文案必過 :func:`compliance_agent.review`（client=None 走
  6 關鍵字確定性 floor；fail-to-floor 內建）。
- blocked → 原通知不派送，合成 internal ``compliance_incident``（alert）——
  摘要用固定模板、不引用被攔原文，避免違規字眼二次外溢（research.md §4）。
- ``publish`` 永不對生產者拋例外：壞事件 → rejected；管道失敗 → 降級記錄。
"""
from __future__ import annotations

from pydantic import ValidationError

from polaris.graph.nodes import compliance_agent
from polaris.notifications.channels import Channel
from polaris.notifications.composer import Composer, summarize_event
from polaris.notifications.inbox import InAppInbox
from polaris.notifications.model import (
    Notification,
    NotificationEvent,
    PublishOutcome,
)
from polaris.notifications.subscriptions import Subscription


class NotificationService:
    """事件進、通知出。生產者只依賴 :meth:`publish`。"""

    def __init__(
        self,
        *,
        inbox: InAppInbox | None = None,
        channels: list[Channel] | None = None,
        subscription: Subscription | None = None,
        client=None,
    ) -> None:
        self.inbox = inbox if inbox is not None else InAppInbox()
        self.channels = list(channels) if channels is not None else []
        self.subscription = subscription if subscription is not None else Subscription()
        self.client = client
        self._composer = Composer()

    # ── 管線 ────────────────────────────────────────────────────────────

    def publish(self, event: NotificationEvent | dict) -> PublishOutcome:
        # 1. validate（FR-NC-011：壞事件拒收、不弄垮管線）
        if not isinstance(event, NotificationEvent):
            try:
                event = NotificationEvent.model_validate(event)
            except ValidationError as exc:
                return PublishOutcome(status="rejected", reason=f"invalid event: {exc}")

        # 2. 去重（FR-NC-005：exactly-once；同 id 不同內容以第一筆為準）
        if self._composer.is_duplicate(event):
            return PublishOutcome(
                status="deduped", reason=f"event_id already seen: {event.event_id}"
            )

        # 3. 接地檢查（FR-NC-004：沒有來源的事件不發通知）
        if event.audience == "user" and not event.evidence:
            return PublishOutcome(
                status="rejected", reason="user-facing event requires non-empty evidence"
            )

        # 4. Compliance Gate（FR-NC-003：user 文案必審；internal 不審改寫）
        if event.audience == "user":
            draft = f"{event.title}\n{summarize_event(event)}"
            _, status = compliance_agent.review(draft, self.client)
            if status == "blocked":
                incident = self._make_incident(event)
                self._deliver(incident)
                return PublishOutcome(
                    status="blocked",
                    notification=incident,
                    reason=f"compliance blocked event {event.event_id}; incident filed",
                )
            compliance_status = "passed"
        else:
            compliance_status = "skipped"

        notification = self._composer.build(event, compliance_status=compliance_status)

        # 5. 訂閱過濾（FR-NC-006；alert 恆放行由 Subscription 內建）
        if not self.subscription.allows(notification):
            return PublishOutcome(
                status="filtered", reason=f"subscription filtered {event.event_id}"
            )

        # 6. digest 合併（FR-NC-010：同鍵 info 併入既有通知）
        digest_id = self._composer.lookup_digest(event)
        if digest_id is not None:
            existing = self.inbox.get(digest_id)
            if existing is not None:
                merged = self._composer.merge_digest(existing, event)
                self.inbox.add(merged)
                return PublishOutcome(status="digested", notification=merged)

        # 7. 派送
        self._deliver(notification)
        self._composer.register_digest(notification)
        return PublishOutcome(status="delivered", notification=notification)

    # ── 內部 ────────────────────────────────────────────────────────────

    def _deliver(self, notification: Notification) -> None:
        """入收件匣（恆開管道）；internal 受眾另推外部管道，失敗降級記錄。"""
        self.inbox.add(notification)
        if notification.audience != "internal":
            return
        for channel in self.channels:
            try:
                channel.send(notification)
            except Exception as exc:  # noqa: BLE001 — FR-NC-009 降級不拋給生產者
                self.inbox.record_failure(
                    f"{type(channel).__name__} failed for "
                    f"{notification.notification_id}: {exc}"
                )

    @staticmethod
    def _make_incident(event: NotificationEvent) -> Notification:
        """合規事故通知（固定模板；不引用被攔原文）。"""
        notification_id = f"ntf-incident-{event.event_id}"
        return Notification(
            notification_id=notification_id,
            event_id=event.event_id,
            type="compliance_incident",
            audience="internal",
            ticker=event.ticker,
            title=f"合規事故：事件 {event.event_id} 文案遭攔截",
            summary="通知文案命中合規規則，已攔截未派送；請依憲法原則 I 記錄 incident 並補測試。",
            severity="alert",
            evidence=list(event.evidence),
            deep_link=f"/notifications/{notification_id}",
            created_at=event.occurred_at,
            compliance_status="skipped",
        )


__all__ = ["NotificationService"]
