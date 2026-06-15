"""Thin FastAPI 後端（W4）—— 把既有引擎包成 HTTP 給 R7 前端 / Cloud Run 用。

實作 **R7 開工指南 §2 已公布契約**（`docs/R7_frontend_開工指南.md`）：

- ``GET  /healthz``  → 健康探針（Cloud Run；重用 :func:`polaris.server.health_payload`）
- ``POST /ask``      → 5 節點 workflow：``{query}`` → ``{answer, compliance_status, citations, trace}``
- ``POST /research`` → Deep Research ReAct：``{question}`` → ``{final_answer, evidence, react_steps, status, compliance_status}``

通知中心（specs/002，R7 Alert Inbox 升級版的後端契約 + 互動 demo）：

- ``GET  /notifications``               → 收件匣列表 + 未讀數（query: ``ticker`` / ``type``）
- ``POST /notifications/events``        → 發布事件進真實管線，回 ``PublishOutcome``
- ``POST /notifications/{id}/read``     → 標已讀
- ``POST /notifications/reset``         → 重置收件匣（demo / 測試隔離用）
- ``GET  /demo/notifications``          → 互動 demo 頁（單檔 HTML，吃上面四個端點）

Watchdog（specs/003，R7 Alert Inbox 消費端）：

- ``GET  /alerts``                      → mock MOPS 事件跑 Watchdog，回 WatchdogAlert 陣列（token-free）

**欄位名一字不差**（``source_id`` / ``compliance_status`` / ``react_steps`` …）；改契約＝R2/R3/R7 一起改。
這層只做「HTTP ↔ 既有函式」的薄轉接：不碰 graph/state/compliance/Deep Research 本體。
無金鑰時引擎走 fallback → 本 API 仍可端到端回應（token-free、CI 可測）。

跑法：``python -m polaris.api``（uvicorn，監聽 ``$PORT``；Cloud Run 會注入）。
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, field_validator

from polaris.config import settings
from polaris.graph.deep_research.agent import run_deep_research
from polaris.graph.deep_research.state import ReActStep
from polaris.graph.state import Citation, NodeTrace
from polaris.graph.watchdog import load_mock_events, run_watchdog
from polaris.graph.workflow import build_workflow
from polaris.notifications import (
    Notification,
    NotificationService,
    PublishOutcome,
    SlackWebhookChannel,
)
from polaris.server import health_payload, resolve_port

_WATCHDOG_MOCK_EVENTS = (
    Path(__file__).resolve().parent / "graph" / "watchdog" / "data" / "watchdog_events.json"
)

app = FastAPI(
    title="Polaris Desk API",
    version="0.1.0",
    description="台股法遵與投研 Agent-Augmented Research Workflow — thin HTTP 後端（W4）",
)


def _parse_origins(raw: str) -> list[str]:
    """逗號分隔的 CORS 來源字串 → 清單（strip + 去空）。"""
    return [o.strip() for o in raw.split(",") if o.strip()]


# R7 前端（Vercel）跨域呼叫本 API → 需 CORS allowlist（secure-by-default，非萬用 *）。
app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_origins(settings.cors_origins),
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# --- 請求 / 回應模型（回應重用引擎既有 pydantic 型別 → 序列化不會與引擎漂移）---
def _reject_blank(value: str) -> str:
    """空白（含全形空白）視同未輸入 → 422，不把垃圾餵進引擎。"""
    if not value.strip():
        raise ValueError("不可為空白")
    return value


class AskRequest(BaseModel):
    query: str = Field(min_length=1, description="自然語言問題")
    # issue #32: viewer identity for owner-based document access control.
    # Omit or set null to use the default public principal.
    viewer: str = Field(default="demo_principal", description="存取控制身分（issue #32）")

    _not_blank = field_validator("query")(_reject_blank)


class AskResponse(BaseModel):
    answer: str
    compliance_status: str
    citations: list[Citation]
    trace: list[NodeTrace]


class ResearchRequest(BaseModel):
    question: str = Field(min_length=1, description="開放式研究問題")
    # issue #32: viewer identity forwarded to Deep Research search fn.
    viewer: str = Field(default="demo_principal", description="存取控制身分（issue #32）")

    _not_blank = field_validator("question")(_reject_blank)


class ResearchResponse(BaseModel):
    final_answer: str
    evidence: list[Citation]
    react_steps: list[ReActStep]
    status: str
    compliance_status: str


@app.get("/healthz", tags=["ops"])
def healthz() -> dict[str, str]:
    """Cloud Run 健康探針：證明套件 import + 設定載入（不含祕密）。"""
    return health_payload()


@app.post("/ask", response_model=AskResponse, tags=["research"])
def ask(req: AskRequest) -> AskResponse:
    """跑 5 節點 workflow，回帶引用 + 合規狀態 + 每節點 trace 的答案。

    ``viewer`` 透傳進 workflow state（issue #32）：retriever 依此做 owner-scoped 過濾。
    """
    result = build_workflow().invoke({"query": req.query, "viewer": req.viewer})
    return AskResponse(
        answer=result.get("answer", ""),
        compliance_status=result.get("compliance_status", "unknown"),
        citations=result.get("citations") or [],
        trace=result.get("trace") or [],
    )


@app.post("/research", response_model=ResearchResponse, tags=["research"])
def research(req: ResearchRequest) -> ResearchResponse:
    """跑 Deep Research ReAct loop（≤6 迴圈 / ≥3 引用 / 過合規），回結論 + 證據 + 步驟。

    ``viewer`` 透傳進 run_deep_research（issue #32）：R4 真實 search fn 接入後
    可依此做 owner-scoped 過濾；stub_search 無 owner 欄位，目前為 no-op。
    """
    r = run_deep_research(req.question, viewer=req.viewer)
    return ResearchResponse(
        final_answer=r.final_answer,
        evidence=r.evidence,
        react_steps=r.react_steps,
        status=r.status,
        compliance_status=r.compliance_status,
    )


# --- 通知中心（specs/002）— thin 轉接到 NotificationService ------------------
#
# Phase 1 收件匣為 in-memory（spec Assumptions；BigQuery 持久化 = Phase 2 / PRD
# OQ-1）→ process 內單例。reset 端點供 demo / 測試取得乾淨狀態。

_DEMO_HTML = Path(__file__).parent / "notifications" / "demo.html"


def _new_notification_service() -> NotificationService:
    return NotificationService(
        channels=[SlackWebhookChannel(settings.slack_webhook_url)],
    )


_notification_service = _new_notification_service()


class NotificationListResponse(BaseModel):
    items: list[Notification]
    unread_count: int
    delivery_failures: list[str]


@app.get("/notifications", response_model=NotificationListResponse, tags=["notifications"])
def list_notifications(
    ticker: str | None = None, type: str | None = None  # noqa: A002 — 對齊契約欄位名
) -> NotificationListResponse:
    """收件匣列表（created_at 倒序）+ 未讀數 + 外送降級記錄。"""
    inbox = _notification_service.inbox
    return NotificationListResponse(
        items=inbox.list(ticker=ticker, type=type),  # type: ignore[arg-type] — 未知 type 僅比對不中
        unread_count=inbox.unread_count(),
        delivery_failures=list(inbox.delivery_failures),
    )


@app.post("/notifications/events", response_model=PublishOutcome, tags=["notifications"])
def publish_event(event: dict) -> PublishOutcome:
    """發布事件進**真實管線**（去重→接地→合規閘門→訂閱→digest/派送）。

    壞事件回 ``status=rejected``（HTTP 200——拒收是管線的正常 outcome，
    不是傳輸層錯誤；生產者依 ``status`` 分支）。
    """
    return _notification_service.publish(event)


@app.post("/notifications/{notification_id}/read", response_model=Notification,
          tags=["notifications"])
def mark_notification_read(notification_id: str) -> Notification:
    """標已讀；查無該通知 → 404。``read_at`` 取 API 邊界當下時間
    （確定性約束只管管線內部；牆鐘是邊界輸入，同事件 ``occurred_at`` 的角色）。"""
    updated = _notification_service.inbox.mark_read(notification_id, at=datetime.now())
    if updated is None:
        raise HTTPException(status_code=404, detail=f"notification not found: {notification_id}")
    return updated


@app.post("/notifications/reset", tags=["notifications"])
def reset_notifications() -> dict[str, str]:
    """重置為全新收件匣（in-memory 單例換新；demo / 測試隔離用）。"""
    global _notification_service
    _notification_service = _new_notification_service()
    return {"status": "reset"}


@app.get("/demo/notifications", response_class=HTMLResponse, tags=["notifications"])
def notifications_demo() -> HTMLResponse:
    """互動 demo 頁：收件匣 UI/UX + 事件模擬器（吃同源 /notifications 端點）。"""
    return HTMLResponse(_DEMO_HTML.read_text(encoding="utf-8"))


# --- Watchdog（specs/003）— R7 Alert Inbox 消費端 ----------------------------

class AlertResponse(BaseModel):
    """R7 Alert Inbox 契約（docs/R7_frontend_開工指南.md §2c）。欄位名一字不差。"""

    event_id: str
    ticker: str
    summary: str
    compliance_status: str
    severity: str
    evidence: list[Citation]


@app.get("/alerts", response_model=list[AlertResponse], tags=["watchdog"])
def alerts() -> list[AlertResponse]:
    """跑 mock MOPS 事件集 → WatchdogAlert 陣列（token-free fallback，CI 可測）。

    R7 Alert Inbox 直接消費本端點；severity 上色、blocked 標紅。
    無 Gemini 金鑰時 Watchdog 走確定性 fallback（token=0）。
    """
    return [
        AlertResponse(
            event_id=a.event_id,
            ticker=a.ticker,
            summary=a.summary,
            compliance_status=a.compliance_status,
            severity=a.severity,
            evidence=a.evidence,
        )
        for a in (run_watchdog(e) for e in load_mock_events(_WATCHDOG_MOCK_EVENTS))
    ]


def main() -> None:  # pragma: no cover - 進入點，由 `python -m polaris.api` 啟動
    import uvicorn

    port = resolve_port()
    print(f"Polaris Desk API on 0.0.0.0:{port} — POST /ask · POST /research · GET /healthz")
    uvicorn.run(app, host="0.0.0.0", port=port)  # noqa: S104 — 容器內需綁全介面


if __name__ == "__main__":  # pragma: no cover
    main()
