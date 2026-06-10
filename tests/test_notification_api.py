"""通知中心 HTTP 端點測試（specs/002 — api.py thin 轉接層）。

驗證 HTTP ↔ NotificationService 的轉接與契約欄位；管線語意本體
在 test_notification_service.py，這裡只測邊界行為。全程 token-free。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from polaris.api import app

client = TestClient(app)

EVENT = {
    "event_id": "api-2330-001",
    "type": "watchdog_alert",
    "audience": "user",
    "ticker": "2330",
    "title": "2330 發布重大訊息",
    "body": "董事會決議……",
    "severity": "watch",
    "occurred_at": "2026-03-15T08:30:00",
    "evidence": [
        {"source_id": "mops-2330-20260315", "snippet": "董事會決議…", "origin": "news"}
    ],
}


@pytest.fixture(autouse=True)
def fresh_inbox():
    """每個測試前重置 in-memory 收件匣（單例隔離）。"""
    client.post("/notifications/reset")
    yield


def test_list_empty():
    r = client.get("/notifications")
    assert r.status_code == 200
    assert r.json() == {"items": [], "unread_count": 0, "delivery_failures": []}


def test_publish_event_delivered_and_listed():
    r = client.post("/notifications/events", json=EVENT)
    assert r.status_code == 200
    assert r.json()["status"] == "delivered"
    listed = client.get("/notifications").json()
    assert listed["unread_count"] == 1
    item = listed["items"][0]
    assert item["title"] == EVENT["title"]
    assert item["compliance_status"] == "passed"
    assert item["evidence"][0]["source_id"] == "mops-2330-20260315"


def test_publish_redteam_event_blocked_with_incident():
    bad = {**EVENT, "event_id": "api-bad-001", "title": "9999 利多消息，建議買進"}
    r = client.post("/notifications/events", json=bad)
    assert r.json()["status"] == "blocked"
    items = client.get("/notifications").json()["items"]
    assert len(items) == 1 and items[0]["type"] == "compliance_incident"
    assert "建議買進" not in items[0]["title"] + items[0]["summary"]


def test_publish_invalid_event_rejected_http_200():
    """拒收是管線的正常 outcome，不是傳輸層錯誤。"""
    r = client.post("/notifications/events", json={"event_id": "x", "type": "data_ingested"})
    assert r.status_code == 200
    assert r.json()["status"] == "rejected"


def test_list_filters_by_ticker_and_type():
    client.post("/notifications/events", json=EVENT)
    client.post("/notifications/events", json={
        **EVENT, "event_id": "api-2891-001", "ticker": "2891", "type": "watchlist_event",
    })
    assert len(client.get("/notifications", params={"ticker": "2330"}).json()["items"]) == 1
    assert len(client.get("/notifications", params={"type": "watchlist_event"}).json()["items"]) == 1


def test_mark_read_and_404():
    client.post("/notifications/events", json=EVENT)
    nid = client.get("/notifications").json()["items"][0]["notification_id"]
    r = client.post(f"/notifications/{nid}/read")
    assert r.status_code == 200 and r.json()["read_at"] is not None
    assert client.get("/notifications").json()["unread_count"] == 0
    assert client.post("/notifications/ntf-nope/read").status_code == 404


def test_reset_clears_inbox_and_dedupe_state():
    client.post("/notifications/events", json=EVENT)
    client.post("/notifications/reset")
    assert client.get("/notifications").json()["items"] == []
    # 去重狀態也歸零：同 event_id 重發應 delivered 而非 deduped
    assert client.post("/notifications/events", json=EVENT).json()["status"] == "delivered"


def test_demo_page_served():
    r = client.get("/demo/notifications")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "通知中心" in r.text
    assert "/notifications/events" in r.text  # 頁面打的是同源真實端點
