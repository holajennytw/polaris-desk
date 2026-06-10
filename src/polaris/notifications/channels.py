"""通知出口管道（specs/002 / FR-NC-008、009）。

``SlackWebhookChannel`` 採注入式 transport seam（同 Deep Research ``search`` /
Watchdog ``event`` 套路）：預設實作用 stdlib ``urllib``（incoming webhook 就是
一個 HTTP POST，不為此加 ``slack_sdk`` 依賴）；測試一律注入 recorder / raiser
→ CI 0 真實外呼。

- ``webhook_url`` 為空 → channel 自我停用（``send()`` no-op、0 外呼）。
  URL 屬金鑰：只進 ``.env``（``Settings.slack_webhook_url``），永不 commit。
- 暫時性失敗由 ``call_with_retry`` 重試；用盡後 **拋出**，由 service 層
  接手記錄降級（通知不無聲丟失、生產者也不被外送失敗弄垮）。
"""
from __future__ import annotations

import json
import urllib.request
from typing import Callable, Protocol

from polaris.notifications.model import Notification
from polaris.retry import call_with_retry

Transport = Callable[[str, dict], None]


class Channel(Protocol):
    """通知出口介面；新增管道（Email / LINE，Phase 2+）實作同一契約。"""

    def send(self, notification: Notification) -> None: ...


def _urllib_transport(url: str, payload: dict) -> None:
    """預設 transport：POST JSON 到 webhook（僅在真的設定 URL 時被呼叫）。"""
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10):  # noqa: S310 — webhook URL 來自 .env
        pass


def _format_text(notification: Notification) -> str:
    """payload 形狀見 contracts/notification-pipeline.md §Slack payload。"""
    return (
        f"[{notification.severity.upper()}] {notification.type} — "
        f"{notification.title}：{notification.summary}"
        f"（evt {notification.event_id}）"
    )


class SlackWebhookChannel:
    """內部團隊 Slack incoming webhook 管道（N6/N7 營運告警）。"""

    def __init__(
        self,
        webhook_url: str,
        *,
        transport: Transport | None = None,
        sleep: Callable[[float], None] | None = None,
        attempts: int = 3,
    ) -> None:
        self.webhook_url = webhook_url
        self.attempts = attempts
        self._transport = transport if transport is not None else _urllib_transport
        self._sleep = sleep

    @property
    def enabled(self) -> bool:
        return bool(self.webhook_url)

    def send(self, notification: Notification) -> None:
        if not self.enabled:
            return
        payload = {"text": _format_text(notification)}
        call_with_retry(
            lambda: self._transport(self.webhook_url, payload),
            attempts=self.attempts,
            sleep=self._sleep,
        )


__all__ = ["Channel", "SlackWebhookChannel", "Transport"]
