"""polaris.api — thin FastAPI 後端（W4 / R7 Vercel 對接）。

實作 R7 開工指南 §2 已公布契約：GET /healthz、POST /ask、POST /research。
**欄位名一字不差**（source_id / compliance_status / react_steps …）——R7 直接拿 mock
換真後端、零重工。token-free：fallback 模式（無 Gemini 金鑰）即可端到端驗。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from polaris.api import app

VALID_COMPLIANCE = {"passed", "blocked", "unknown"}


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class TestHealthz:
    def test_healthz_returns_200_ok(self, client):
        r = client.get("/healthz")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_health_alias_returns_200_ok(self, client):
        """`/health` mirrors `/healthz`. Cloud Run's Google Front End intercepts
        the exact path `/healthz` (returns its own 404 before reaching the
        container), so the cloud-reachable health probe must live at `/health`."""
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
        assert r.json() == client.get("/healthz").json()


class TestAsk:
    def test_ask_returns_contract_shape(self, client):
        r = client.post("/ask", json={"query": "台積電 2025Q1 毛利率如何？"})
        assert r.status_code == 200
        body = r.json()
        # 契約欄位（R7 §2a）：一字不差
        assert set(("answer", "compliance_status", "citations", "trace")) <= body.keys()
        assert isinstance(body["answer"], str) and body["answer"]
        assert body["compliance_status"] in VALID_COMPLIANCE
        assert isinstance(body["citations"], list)
        assert isinstance(body["trace"], list)

    def test_ask_citations_have_contract_fields(self, client):
        r = client.post("/ask", json={"query": "台積電最近兩季營收"})
        for c in r.json()["citations"]:
            assert set(("source_id", "snippet", "origin")) <= c.keys()

    def test_ask_trace_reflects_five_nodes(self, client):
        # 5 節點 workflow trace 不變量：每筆 trace 有 node_name/status
        trace = client.post("/ask", json={"query": "台積電 2025Q1 營收"}).json()["trace"]
        for t in trace:
            assert "node_name" in t and "status" in t

    def test_ask_missing_query_is_422(self, client):
        assert client.post("/ask", json={}).status_code == 422

    def test_ask_viewer_accepted_and_forwarded(self, client):
        """viewer field (issue #32) is accepted and forwarded to the workflow."""
        r = client.post("/ask", json={"query": "台積電毛利率", "viewer": "analyst_A"})
        assert r.status_code == 200
        assert r.json()["compliance_status"] in VALID_COMPLIANCE

    def test_ask_viewer_defaults_to_public_sentinel(self, client):
        """Omitting viewer still succeeds (default = public sentinel principal)."""
        r = client.post("/ask", json={"query": "台積電"})
        assert r.status_code == 200


class TestResearch:
    def test_research_returns_contract_shape(self, client):
        r = client.post(
            "/research",
            json={"question": "比較台積電與聯發科最近兩季毛利率變化"},
        )
        assert r.status_code == 200
        body = r.json()
        # 契約欄位（R7 §2b）：一字不差
        assert set(
            ("final_answer", "evidence", "react_steps", "status", "compliance_status")
        ) <= body.keys()
        assert isinstance(body["final_answer"], str)
        assert body["status"] in {"answered", "exhausted"}
        assert body["compliance_status"] in VALID_COMPLIANCE
        assert isinstance(body["evidence"], list)
        assert isinstance(body["react_steps"], list)

    def test_research_steps_have_thought_and_action(self, client):
        steps = client.post(
            "/research", json={"question": "台積電最近一季風險"}
        ).json()["react_steps"]
        for s in steps:
            assert "thought" in s and "action" in s

    def test_research_missing_question_is_422(self, client):
        assert client.post("/research", json={}).status_code == 422

    def test_research_viewer_accepted(self, client):
        """viewer field (issue #32) is accepted and forwarded to run_deep_research."""
        r = client.post("/research", json={"question": "台積電毛利率", "viewer": "analyst_A"})
        assert r.status_code == 200
        assert r.json()["compliance_status"] in VALID_COMPLIANCE

    def test_research_viewer_defaults_to_public_sentinel(self, client):
        """Omitting viewer still succeeds (default = public sentinel principal)."""
        r = client.post("/research", json={"question": "台積電"})
        assert r.status_code == 200


class _StubStructuredStore:
    """記錄呼叫 + 回 canned 列；讓結構化端點測試 0 GCP / 0 金鑰。"""

    def __init__(self):
        self.calls: list[tuple] = []

    def list_companies(self):
        return [
            {"ticker": "2330", "company_name": "台積電", "english_name": "TSMC",
             "market": "上市", "industry_id": "IND_FOUNDRY", "industry_name": "晶圓代工",
             "is_financial": False, "aliases": "台積電,TSMC,2330"},
        ]

    def list_financials(self, *, ticker=None, period=None, metric=None, limit=None):
        self.calls.append(("financials", ticker, period, metric, limit))
        return [
            {"ticker": "2330", "fiscal_period": "2025Q4", "metric_id": "eps",
             "value": 13.94, "unit": "新台幣元/股", "source_id": "src-1",
             "published_at": "2026-01-16"},
        ]

    def list_events(self, *, ticker=None, event_type=None, limit=None):
        self.calls.append(("events", ticker, event_type, limit))
        return [
            {"event_id": "evt-1", "ticker": "2330", "event_type": "monthly_revenue",
             "published_at": "2026-06-10", "title": "5月營收", "source_url": "https://mops"},
        ]


@pytest.fixture
def stub_store(monkeypatch):
    from polaris import api

    store = _StubStructuredStore()
    monkeypatch.setattr(api, "_structured_store", store)
    return store


class TestCompanies:
    def test_returns_company_dim_rows(self, client, stub_store):
        r = client.get("/companies")
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body, list) and body
        assert {"ticker", "company_name", "english_name", "industry_name",
                "is_financial", "aliases"} <= body[0].keys()
        assert body[0]["ticker"] == "2330"


class TestFinancials:
    def test_returns_contract_shape(self, client, stub_store):
        r = client.get("/financials")
        assert r.status_code == 200
        row = r.json()[0]
        assert {"ticker", "fiscal_period", "metric_id", "value", "unit",
                "source_id", "published_at"} <= row.keys()

    def test_filters_forwarded(self, client, stub_store):
        client.get("/financials?ticker=2330&period=2025Q4&metric=eps&limit=5")
        assert stub_store.calls[-1] == ("financials", "2330", "2025Q4", "eps", 5)

    def test_limit_out_of_range_is_422(self, client, stub_store):
        assert client.get("/financials?limit=0").status_code == 422
        assert client.get("/financials?limit=9999").status_code == 422


class TestEvents:
    def test_returns_contract_shape(self, client, stub_store):
        r = client.get("/events")
        assert r.status_code == 200
        row = r.json()[0]
        assert {"event_id", "ticker", "event_type", "published_at",
                "title", "source_url"} <= row.keys()

    def test_type_filter_forwarded_as_event_type(self, client, stub_store):
        client.get("/events?ticker=2330&type=monthly_revenue")
        assert stub_store.calls[-1] == ("events", "2330", "monthly_revenue", None)


class TestRouting:
    def test_unknown_path_404(self, client):
        assert client.get("/definitely-not-a-route").status_code == 404


class TestParseOrigins:
    def test_splits_strips_and_drops_empties(self):
        from polaris import api

        assert api._parse_origins("http://a, http://b ,, http://c ") == [
            "http://a",
            "http://b",
            "http://c",
        ]


class TestCORS:
    def test_allowed_origin_gets_cors_header(self, client):
        # 預設允許 localhost:3000（Next.js dev）→ R7 前端跨域可呼叫
        r = client.get("/healthz", headers={"Origin": "http://localhost:3000"})
        assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"

    def test_preflight_options_ask_allowed(self, client):
        r = client.options(
            "/ask",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert r.status_code in (200, 204)
        assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"

    def test_disallowed_origin_not_echoed(self, client):
        # 未列入允許清單的來源不得被 echo（不是萬用 *）
        r = client.get("/healthz", headers={"Origin": "https://evil.example.com"})
        assert r.headers.get("access-control-allow-origin") != "https://evil.example.com"


class TestBlankInput:
    def test_blank_query_is_422(self, client):
        assert client.post("/ask", json={"query": "   "}).status_code == 422

    def test_blank_question_is_422(self, client):
        assert client.post("/research", json={"question": "  "}).status_code == 422


class TestAlerts:
    def test_alerts_returns_200_list(self, client):
        r = client.get("/alerts")
        assert r.status_code == 200
        assert isinstance(r.json(), list)
        assert len(r.json()) > 0

    def test_alerts_have_contract_fields(self, client):
        # R7 §2c 契約欄位（一字不差）
        required = {"event_id", "ticker", "summary", "compliance_status", "severity", "evidence"}
        for alert in client.get("/alerts").json():
            assert required <= alert.keys()

    def test_alerts_compliance_status_valid(self, client):
        valid = {"passed", "blocked"}
        for alert in client.get("/alerts").json():
            assert alert["compliance_status"] in valid

    def test_alerts_severity_valid(self, client):
        valid = {"info", "watch", "alert"}
        for alert in client.get("/alerts").json():
            assert alert["severity"] in valid

    def test_alerts_evidence_has_citation_fields(self, client):
        for alert in client.get("/alerts").json():
            for ev in alert["evidence"]:
                assert {"source_id", "snippet", "origin"} <= ev.keys()

    def test_alerts_no_buysell_in_summaries(self, client):
        # NFR-031：所有摘要不得含買賣建議關鍵字
        forbidden = {"建議買進", "建議賣出", "加碼", "減碼", "看多", "看空"}
        for alert in client.get("/alerts").json():
            for kw in forbidden:
                assert kw not in alert["summary"]
