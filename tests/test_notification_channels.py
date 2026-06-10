"""SlackWebhookChannel 測試（specs/002 T017 / US4）。

recorder transport 收到正確 payload、暫時性錯誤經 retry 成功、
用盡即拋（service 層負責降級記錄）、webhook_url 空 → 0 次外呼。
"""
from __future__ import annotations

import pytest

from polaris.notifications.channels import SlackWebhookChannel
from tests.conftest import ApiError
from tests.test_notification_model import make_notification

URL = "https://hooks.slack.invalid/services/T000/B000/XXX"


class RecorderTransport:
    def __init__(self, fail_times: int = 0, error: BaseException | None = None):
        self.calls: list[tuple[str, dict]] = []
        self._fail_times = fail_times
        self._error = error if error is not None else ApiError(503)

    def __call__(self, url: str, payload: dict) -> None:
        self.calls.append((url, payload))
        if self._fail_times > 0:
            self._fail_times -= 1
            raise self._error


def test_send_posts_expected_payload():
    transport = RecorderTransport()
    ch = SlackWebhookChannel(URL, transport=transport)
    n = make_notification(audience="internal", severity="alert", type="pipeline_health",
                          compliance_status="skipped")
    ch.send(n)
    assert len(transport.calls) == 1
    url, payload = transport.calls[0]
    assert url == URL
    text = payload["text"]
    assert "[ALERT]" in text
    assert "pipeline_health" in text
    assert n.title in text
    assert n.event_id in text


def test_transient_failure_retried_then_succeeds():
    transport = RecorderTransport(fail_times=2)  # 前 2 次 503，第 3 次成功
    ch = SlackWebhookChannel(URL, transport=transport, sleep=lambda _s: None, attempts=3)
    ch.send(make_notification())
    assert len(transport.calls) == ch.attempts


def test_retry_exhausted_raises_for_service_to_record():
    transport = RecorderTransport(fail_times=99)
    ch = SlackWebhookChannel(URL, transport=transport, sleep=lambda _s: None, attempts=3)
    with pytest.raises(ApiError):
        ch.send(make_notification())
    assert len(transport.calls) == ch.attempts


def test_empty_url_disables_channel_zero_calls():
    transport = RecorderTransport()
    ch = SlackWebhookChannel("", transport=transport)
    assert ch.enabled is False
    ch.send(make_notification())
    assert transport.calls == []
