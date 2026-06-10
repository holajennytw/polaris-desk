"""通知中心資料模型（specs/002 / data-model.md）。

全部 frozen pydantic BaseModel（沿用 ``graph/state.Citation`` 模式）：
- ``NotificationEvent``：生產者（Watchdog / ingestion / eval / budget）發出的原始事件。
- ``Notification``：管線組裝後的派送單位；已讀以 ``model_copy`` 產新實例（維持 immutable）。
- ``PublishOutcome``：``NotificationService.publish()`` 的回傳契約。

確定性原則：通知時間戳一律取事件 ``occurred_at``，管線不呼叫 ``now()``
（research.md §1 / SC-NC-004）。
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polaris.graph.state import Citation

# ---------------------------------------------------------------------------
# 列舉型別
# ---------------------------------------------------------------------------

NotificationType = Literal[
    "watchdog_alert",        # N1 合規 / 重大訊息警示（Watchdog）
    "watchlist_event",       # N2 追蹤清單事件（法說公告、財報發布）
    "data_ingested",         # N3 新資料入庫
    "research_done",         # N4 Deep Research 完成
    "contradiction",         # N5 來源矛盾偵測
    "pipeline_health",       # N6 管線健康（ingestion 失敗、eval 掉分）
    "ops_alert",             # N7 成本警報
    "compliance_incident",   # N8 合規事故（internal）—— 保留給 service 在攔截時合成
]

Audience = Literal["user", "internal"]
Severity = Literal["info", "watch", "alert"]
DeliveryStatus = Literal["delivered", "deduped", "digested", "blocked", "rejected", "filtered"]
NotificationComplianceStatus = Literal["passed", "blocked", "skipped"]


# ---------------------------------------------------------------------------
# NotificationEvent
# ---------------------------------------------------------------------------

class NotificationEvent(BaseModel):
    """生產者發出的原始事件。``title`` / ``body`` 視為不可信文字。"""

    model_config = ConfigDict(frozen=True)

    event_id: str = Field(min_length=1, description="唯一識別碼；去重鍵")
    type: NotificationType
    audience: Audience
    ticker: str | None = Field(default=None)
    title: str = Field(min_length=1)
    body: str = Field(default="")
    severity: Severity = Field(default="info")
    occurred_at: datetime = Field(description="事件發生時間；即通知 created_at")
    evidence: list[Citation] = Field(default_factory=list)

    @model_validator(mode="after")
    def _reject_reserved_type(self) -> NotificationEvent:
        if self.type == "compliance_incident":
            raise ValueError("type 'compliance_incident' is reserved for the service")
        return self


# ---------------------------------------------------------------------------
# Notification
# ---------------------------------------------------------------------------

class Notification(BaseModel):
    """管線組裝後、可派送的標準通知（spec FR-NC-001）。"""

    model_config = ConfigDict(frozen=True)

    notification_id: str = Field(min_length=1)
    event_id: str = Field(min_length=1, description="來源事件識別碼（digest 時為首筆）")
    type: NotificationType
    audience: Audience
    ticker: str | None = Field(default=None)
    title: str = Field(min_length=1)
    summary: str = Field(default="", max_length=100)
    severity: Severity
    evidence: list[Citation] = Field(default_factory=list)
    deep_link: str = Field(default="")
    created_at: datetime
    read_at: datetime | None = Field(default=None)
    compliance_status: NotificationComplianceStatus
    digest_count: int = Field(default=1, ge=1)


# ---------------------------------------------------------------------------
# PublishOutcome
# ---------------------------------------------------------------------------

class PublishOutcome(BaseModel):
    """``publish()`` 回傳（contracts/notification-pipeline.md）。"""

    model_config = ConfigDict(frozen=True)

    status: DeliveryStatus
    notification: Notification | None = Field(default=None)
    reason: str = Field(default="")


__all__ = [
    "Audience",
    "DeliveryStatus",
    "Notification",
    "NotificationComplianceStatus",
    "NotificationEvent",
    "NotificationType",
    "PublishOutcome",
    "Severity",
]
