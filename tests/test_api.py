"""polaris.api — thin FastAPI 後端（W4 / R7 Vercel 對接）。

實作 R7 開工指南 §2 已公布契約：GET /healthz、POST /ask、POST /research。
**欄位名一字不差**（source_id / compliance_status / react_steps …）——R7 直接拿 mock
換真後端、零重工。token-free：fallback 模式（無 Gemini 金鑰）即可端到端驗。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from polaris.api import app
from polaris.retrieval.retriever import PUBLIC_VIEWER

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

    def test_ask_citations_include_semantic_fields(self, client):
        """P1：/ask citation 一律帶 event_key / source_key / published_yyyymm 三鍵。
        stub / 無金鑰路徑值為 null，但鍵必須存在（nullable）→ 前端契約穩定，不會
        因為某筆無語意 metadata 就少欄。"""
        r = client.post("/ask", json={"query": "台積電 2025Q1 營收"})
        cites = r.json()["citations"]
        assert cites  # 至少一筆引用
        for c in cites:
            assert set(("event_key", "source_key", "published_yyyymm")) <= c.keys()

    def test_ask_trace_reflects_five_nodes(self, client):
        # 5 節點 workflow trace 不變量：每筆 trace 有 node_name/status
        trace = client.post("/ask", json={"query": "台積電 2025Q1 營收"}).json()["trace"]
        for t in trace:
            assert "node_name" in t and "status" in t

    def test_ask_missing_query_is_422(self, client):
        assert client.post("/ask", json={}).status_code == 422

    def test_ask_ignores_client_supplied_viewer(self, client, monkeypatch):
        """security review #1: a client-supplied ``viewer`` must NOT become the ACL
        principal. Anonymous request → workflow sees the public sentinel, never the
        attacker-chosen owner id."""
        from polaris import api

        captured: dict = {}

        class _FakeWorkflow:
            def invoke(self, state):
                captured["viewer"] = state.get("viewer")
                return {"answer": "ok", "compliance_status": "unknown"}

        monkeypatch.setattr(api, "build_workflow", lambda: _FakeWorkflow())
        r = client.post("/ask", json={"query": "台積電毛利率", "viewer": "analyst_A"})
        assert r.status_code == 200
        assert captured["viewer"] == PUBLIC_VIEWER  # 外部 viewer 被忽略

    def test_ask_viewer_derived_from_logged_in_identity(self, client, monkeypatch):
        """Logged-in request → viewer is the verified Google ``sub`` (server-derived)."""
        from polaris import api
        from polaris.auth import current_user

        captured: dict = {}

        class _FakeWorkflow:
            def invoke(self, state):
                captured["viewer"] = state.get("viewer")
                return {"answer": "ok", "compliance_status": "unknown"}

        monkeypatch.setattr(api, "build_workflow", lambda: _FakeWorkflow())
        api.app.dependency_overrides[current_user] = lambda: {"sub": "u1"}
        try:
            # body still attacker-controls viewer; must be ignored in favour of sub
            r = client.post("/ask", json={"query": "台積電", "viewer": "analyst_A"})
        finally:
            api.app.dependency_overrides.pop(current_user, None)
        assert r.status_code == 200
        assert captured["viewer"] == "u1"

    def test_ask_query_over_max_length_is_422(self, client):
        """security review #3: 超長 query → 422，不餵進 LLM / retrieval。"""
        r = client.post("/ask", json={"query": "台" * 3000})
        assert r.status_code == 422


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

    def test_research_ignores_client_supplied_viewer(self, client, monkeypatch):
        """security review #1: client-supplied viewer is ignored; anonymous → public."""
        from polaris import api

        captured: dict = {}

        class _R:
            final_answer, evidence, react_steps = "ok", [], []
            status, compliance_status = "answered", "unknown"

        def fake_run(question, *, viewer):
            captured["viewer"] = viewer
            return _R()

        monkeypatch.setattr(api, "run_deep_research", fake_run)
        r = client.post("/research", json={"question": "台積電毛利率", "viewer": "analyst_A"})
        assert r.status_code == 200
        assert captured["viewer"] == PUBLIC_VIEWER

    def test_research_viewer_derived_from_logged_in_identity(self, client, monkeypatch):
        """Logged-in request → viewer is the verified Google ``sub``."""
        from polaris import api
        from polaris.auth import current_user

        captured: dict = {}

        class _R:
            final_answer, evidence, react_steps = "ok", [], []
            status, compliance_status = "answered", "unknown"

        def fake_run(question, *, viewer):
            captured["viewer"] = viewer
            return _R()

        monkeypatch.setattr(api, "run_deep_research", fake_run)
        api.app.dependency_overrides[current_user] = lambda: {"sub": "u1"}
        try:
            r = client.post("/research", json={"question": "台積電", "viewer": "analyst_A"})
        finally:
            api.app.dependency_overrides.pop(current_user, None)
        assert r.status_code == 200
        assert captured["viewer"] == "u1"

    def test_research_question_over_max_length_is_422(self, client):
        """security review #3: 超長 question → 422。"""
        r = client.post("/research", json={"question": "台" * 3000})
        assert r.status_code == 422


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
            {"event_id": "evt-1", "ticker": "2330", "event_key": "monthly_revenue",
             "published_at": "2026-06-10", "title": "5月營收", "source_url": "https://mops"},
        ]

    def get_chunk(self, source_id, *, viewer):
        self.calls.append(("chunk", source_id, viewer))
        if source_id == "missing":
            return None
        return {
            "chunk_id": source_id,
            "ticker": "2330",
            "doc_type": "transcript",
            "fiscal_period": "2026Q1",
            "published_at": "2026-04-17",
            "chunk_text": "台積電法說會原文內容。",
        }


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
        assert {"event_id", "ticker", "event_key", "published_at",
                "title", "source_url"} <= row.keys()

    def test_type_filter_forwarded_as_event_type(self, client, stub_store):
        client.get("/events?ticker=2330&type=monthly_revenue")
        assert stub_store.calls[-1] == ("events", "2330", "monthly_revenue", None)


class TestChunk:
    def test_returns_doc_viewer_contract(self, client, stub_store):
        r = client.get("/chunk/chunk-2330-q1")

        assert r.status_code == 200
        body = r.json()
        assert body == {
            "source_id": "chunk-2330-q1",
            "title": "2330_2026Q1_法說逐字稿",
            "doc_type": "transcript",
            "kind_label": "法說逐字稿",
            "ticker": "2330",
            "fiscal_period": "2026Q1",
            "published_at": "2026-04-17",
            "page": None,
            "trust": "high",
            "content": "台積電法說會原文內容。",
            "highlight": "台積電法說會原文內容。",
            "hl_tokens": [],
        }
        # security review #1: anonymous caller is the public sentinel, NOT any owner
        assert stub_store.calls[-1] == ("chunk", "chunk-2330-q1", PUBLIC_VIEWER)

    def test_ignores_client_supplied_viewer_query(self, client, stub_store):
        """security review #1: ``?viewer=`` 不再是 ACL principal——被忽略，仍走公開身分。"""
        client.get("/chunk/chunk-2330-q1?viewer=analyst_A")
        assert stub_store.calls[-1] == ("chunk", "chunk-2330-q1", PUBLIC_VIEWER)

    def test_viewer_derived_from_logged_in_identity(self, client, stub_store):
        from polaris import api
        from polaris.auth import current_user

        api.app.dependency_overrides[current_user] = lambda: {"sub": "u1"}
        try:
            client.get("/chunk/chunk-2330-q1?viewer=analyst_A")
        finally:
            api.app.dependency_overrides.pop(current_user, None)
        assert stub_store.calls[-1] == ("chunk", "chunk-2330-q1", "u1")

    def test_missing_or_inaccessible_chunk_is_404(self, client, stub_store):
        assert client.get("/chunk/missing").status_code == 404


class TestContradiction:
    def test_flags_conflicting_guidance_qualifiers(self, client):
        r = client.post(
            "/contradiction",
            json={
                "kpis": [
                    {
                        "label": "全年美元營收指引",
                        "value": "中段 25%",
                        "unit": "",
                        "delta": None,
                        "trend": None,
                    }
                ],
                "summary": [
                    {
                        "text": "全年美元營收成長將達 25% 以上。",
                        "cite": "chunk-2330-q1",
                        "page": "p.7",
                    }
                ],
            },
        )

        assert r.status_code == 200
        alert = r.json()["alerts"][0]
        assert alert["origin"] == "contradiction"
        assert alert["level"] == "mid"
        assert alert["cite_key"] == "chunk-2330-q1"
        assert "中段 25%" in alert["summary"]
        assert "25% 以上" in alert["summary"]

    def test_returns_info_when_no_provable_conflict(self, client):
        r = client.post(
            "/contradiction",
            json={
                "kpis": [{"label": "毛利率", "value": "57.8", "unit": "%"}],
                "summary": [
                    {
                        "text": "本季毛利率為 57.8%。",
                        "cite": "chunk-2330-q1",
                        "page": "",
                    }
                ],
            },
        )

        assert r.status_code == 200
        assert r.json()["alerts"][0]["level"] == "info"
        assert r.json()["alerts"][0]["title"] == "交叉比對通過"


class TestPeerCompare:
    def test_returns_real_financials_trend_and_nested_call_citations(self, client, monkeypatch):
        from polaris import api
        from polaris.graph.state import Citation

        class PeerStore:
            def list_financials(self, *, ticker=None, period=None, metric=None, limit=None):
                rows = {
                    "2330": [
                        {"ticker": "2330", "fiscal_period": "2026Q1", "metric_id": "gross_margin", "value": 57.8, "unit": "%", "source_id": "fin-a-q1"},
                        {"ticker": "2330", "fiscal_period": "2026Q1", "metric_id": "operating_margin", "value": 47.5, "unit": "%", "source_id": "fin-a-op"},
                        {"ticker": "2330", "fiscal_period": "2025Q4", "metric_id": "gross_margin", "value": 56.1, "unit": "%", "source_id": "fin-a-q4"},
                    ],
                    "2454": [
                        {"ticker": "2454", "fiscal_period": "2026Q1", "metric_id": "gross_margin", "value": 38.3, "unit": "%", "source_id": "fin-b-q1"},
                        {"ticker": "2454", "fiscal_period": "2026Q1", "metric_id": "operating_margin", "value": 20.1, "unit": "%", "source_id": "fin-b-op"},
                        {"ticker": "2454", "fiscal_period": "2025Q4", "metric_id": "gross_margin", "value": 37.9, "unit": "%", "source_id": "fin-b-q4"},
                    ],
                }[ticker]
                if period is not None:
                    rows = [row for row in rows if row["fiscal_period"] == period]
                if metric is not None:
                    rows = [row for row in rows if row["metric_id"] == metric]
                return rows[: limit or 200]

        search_calls: list[tuple[str, str, str]] = []

        def fake_search(ticker, period, question):
            search_calls.append((ticker, period, question))
            return [
                Citation(
                    source_id=f"call-{ticker}",
                    snippet=f"{ticker} 法說原文",
                    origin="embedding",
                    company=ticker,
                    doc_type="transcript",
                    fiscal_period=period,
                )
            ]

        monkeypatch.setattr(api, "_structured_store", PeerStore())
        monkeypatch.setattr(api, "_search_peer_calls", fake_search)

        r = client.post(
            "/peer-compare",
            json={
                "a_ticker": "2330",
                "b_ticker": "2454",
                "fiscal_period": "2026Q1",
                "question": "比較毛利率與法說重點",
            },
        )

        assert r.status_code == 200
        body = r.json()
        assert body["a_ticker"] == "2330"
        assert body["b_ticker"] == "2454"
        assert body["fiscal_period"] == "2026Q1"
        assert body["kpis"][0]["label"] == "毛利率"
        assert body["kpis"][0]["a"]["v"] == "57.80%"
        assert body["kpis"][0]["a"]["citations"][0]["src"] == "fin-a-q1"
        assert body["kpis"][0]["a"]["citations"][0]["page"] == "2026Q1"
        assert body["kpis"][0]["diff"] == "19.50pp"
        assert body["kpis"][0]["better"] == "a"
        assert body["financial"][0]["metric"] == "毛利率"
        assert body["financial"][0]["note"] == "差異 19.50pp"
        assert body["calls"][0]["dim"] == "法說會"
        assert body["calls"][0]["topic"] == "比較毛利率與法說重點"
        assert body["calls"][0]["a"]["cite"] == "call-2330"
        assert body["calls"][0]["a"]["quote"] == "2330 法說原文"
        assert body["calls"][0]["a"]["tone"] == "neu"
        assert body["calls"][0]["b"]["cite"] == "call-2454"
        # trend 現只取 revenue/revenue_yoy（_TREND_METRICS），毛利率不再進 trend；
        # 此 fixture 無營收指標 → trend 為空。
        assert body["trend"] == []
        assert body["valuation"] == []  # PE/PB 不在目前 canonical metric 清單，不造假
        assert body["compliance_status"] == "passed"
        assert search_calls == [
            ("2330", "2026Q1", "比較毛利率與法說重點"),
            ("2454", "2026Q1", "比較毛利率與法說重點"),
        ]
        # 比較摘要應為「多行條列」（首行總覽 + 每行一個重點），讓前端 PeerSummaryPanel
        # 能渲染成 bullet point；且每行不得自帶「・」前綴（否則前端會雙重 bullet）。
        summary_lines = [ln for ln in body["summary"].split("\n") if ln.strip()]
        assert len(summary_lines) >= 2
        assert not any(ln.lstrip().startswith("・") for ln in summary_lines)

    def _peer_store(self):
        """最小 PeerStore：兩家各一筆毛利率，確保 kpis 非空。"""

        class _Store:
            def list_financials(self, *, ticker=None, period=None, metric=None, limit=None):
                rows = {
                    "2330": [{"ticker": "2330", "fiscal_period": "2026Q1", "metric_id": "gross_margin", "value": 57.8, "unit": "%", "source_id": "fa"}],
                    "2454": [{"ticker": "2454", "fiscal_period": "2026Q1", "metric_id": "gross_margin", "value": 38.3, "unit": "%", "source_id": "fb"}],
                }.get(ticker, [])
                if period is not None:
                    rows = [r for r in rows if r["fiscal_period"] == period]
                if metric is not None:
                    rows = [r for r in rows if r["metric_id"] == metric]
                return rows[: limit or 200]

        return _Store()

    def test_llm_summary_normalized_to_clean_bullets(self, client, monkeypatch):
        """LLM 即使回傳帶「・」前綴的多行，後端會去前綴並保留多行（前端自加項目符號）。"""
        from polaris import api
        from polaris.graph.state import Citation
        from polaris.llm import gemini

        class FakeLLM:
            def generate(self, prompt, flash=False, **kw):
                return "台積電整體領先聯發科。\n・毛利率：台積電 57.8% vs 聯發科 38.3%\n- 規模優勢明顯"

        monkeypatch.setattr(api, "_structured_store", self._peer_store())
        monkeypatch.setattr(api, "_search_peer_calls", lambda t, p, q: [Citation(source_id=f"c-{t}", snippet="原文", origin="embedding", company=t, doc_type="transcript", fiscal_period=p)])
        monkeypatch.setattr(gemini, "active_llm", lambda: FakeLLM())

        r = client.post("/peer-compare", json={"a_ticker": "2330", "b_ticker": "2454", "fiscal_period": "2026Q1", "question": "比較毛利率"})
        assert r.status_code == 200
        lines = [ln for ln in r.json()["summary"].split("\n") if ln.strip()]
        assert len(lines) == 3
        assert not any(ln.startswith(("・", "-", "*")) for ln in lines)

    def test_llm_single_paragraph_falls_back_to_structured_bullets(self, client, monkeypatch):
        """LLM 若仍回單段落（無換行），後端沿用結構化條列，確保前端仍能渲染 bullet。"""
        from polaris import api
        from polaris.llm import gemini

        class FakeLLM:
            def generate(self, prompt, flash=False, **kw):
                return "台積電毛利率高於聯發科，整體表現領先，這是一段沒有換行的敘述文字。"

        monkeypatch.setattr(api, "_structured_store", self._peer_store())
        monkeypatch.setattr(api, "_search_peer_calls", lambda t, p, q: [])
        monkeypatch.setattr(gemini, "active_llm", lambda: FakeLLM())

        r = client.post("/peer-compare", json={"a_ticker": "2330", "b_ticker": "2454", "fiscal_period": "2026Q1", "question": "比較毛利率"})
        assert r.status_code == 200
        lines = [ln for ln in r.json()["summary"].split("\n") if ln.strip()]
        assert len(lines) >= 2  # 結構化條列：總覽 + 至少一項指標

    def test_bulletize_summary_strips_prefixes_and_blank_lines(self):
        from polaris.api import _bulletize_summary

        out = _bulletize_summary("總覽句子\n・第一點\n- 第二點\n\n3. 第三點\n   \n* 第四點")
        assert out.split("\n") == ["總覽句子", "第一點", "第二點", "第三點", "第四點"]
        assert _bulletize_summary("只有一段沒有換行").count("\n") == 0

    def test_peer_call_search_uses_existing_retriever_bridge(self, monkeypatch):
        from polaris import api
        from polaris.graph.state import Citation
        from polaris.retrieval import retriever as retriever_module

        captured: dict = {}
        expected = [Citation(source_id="call-2330", snippet="原文", origin="embedding")]

        def fake_factory(*, viewer, filters):
            captured["viewer"] = viewer
            captured["filters"] = filters

            def search(question):
                captured["question"] = question
                return expected

            return search

        monkeypatch.setattr(retriever_module, "make_retriever_search_fn", fake_factory)

        assert api._search_peer_calls("2330", "2026Q1", "比較毛利率") == expected
        assert captured == {
            "viewer": "__public__",
            "filters": {
                "company": "2330",
                "period": "2026Q1",
                "doc_type": "transcript",
            },
            "question": "比較毛利率",
        }

    def test_peer_call_prefers_transcript_and_skips_presentation(self, monkeypatch):
        """有逐字稿時就用逐字稿，不再多查簡報（4 家大型股維持高訊號來源）。"""
        from polaris import api
        from polaris.graph.state import Citation
        from polaris.retrieval import retriever as retriever_module

        seen: list[str] = []
        transcript = [Citation(source_id="call-2330", snippet="逐字稿原文", origin="embedding")]

        def fake_factory(*, viewer, filters):  # noqa: ARG001
            seen.append(filters["doc_type"])
            doc_type = filters["doc_type"]
            return lambda _q: transcript if doc_type == "transcript" else []

        monkeypatch.setattr(retriever_module, "make_retriever_search_fn", fake_factory)

        assert api._search_peer_calls("2330", "2026Q1", "比較毛利率") == transcript
        assert seen == ["transcript"]  # 逐字稿非空 → 不查 presentation

    def test_peer_call_falls_back_to_presentation_without_transcript(self, monkeypatch):
        """多數台股無逐字稿：逐字稿查空時退回法說簡報（全 20 家入庫），不再回空引用。"""
        from polaris import api
        from polaris.graph.state import Citation
        from polaris.retrieval import retriever as retriever_module

        seen: list[str] = []
        presentation = [Citation(source_id="pres-2891", snippet="法說簡報原文", origin="embedding")]

        def fake_factory(*, viewer, filters):  # noqa: ARG001
            seen.append(filters["doc_type"])
            doc_type = filters["doc_type"]
            return lambda _q: [] if doc_type == "transcript" else presentation

        monkeypatch.setattr(retriever_module, "make_retriever_search_fn", fake_factory)

        result = api._search_peer_calls("2891", "2026Q1", "比較毛利率")
        assert result == presentation
        assert seen == ["transcript", "presentation"]  # 先逐字稿、空了才退簡報


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


class TestSuggestions:
    """GET /suggestions — 前端 useSuggestions hook 的提示問句來源（契約：
    {suggestions: list[str], source: "rule"|"llm", is_generating: bool}）。"""

    def test_suggestions_default_mode_contract_shape(self, client):
        r = client.get("/suggestions")
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body["suggestions"], list) and body["suggestions"]
        assert all(isinstance(s, str) and s for s in body["suggestions"])
        assert body["source"] in {"rule", "llm"}
        assert isinstance(body["is_generating"], bool)

    def test_suggestions_research_mode(self, client):
        r = client.get("/suggestions?mode=research")
        assert r.status_code == 200
        assert r.json()["suggestions"]

    def test_suggestions_peer_mode_differs(self, client):
        research = client.get("/suggestions?mode=research").json()["suggestions"]
        peer = client.get("/suggestions?mode=peer").json()["suggestions"]
        assert peer and peer != research

    def test_suggestions_invalid_mode_rejected(self, client):
        assert client.get("/suggestions?mode=nope").status_code == 422

    def test_suggestions_no_buysell(self, client):
        # NFR-031：提示問句不得含買賣建議關鍵字
        forbidden = {"建議買進", "建議賣出", "加碼", "減碼", "看多", "看空", "目標價"}
        for mode in ("research", "peer"):
            for s in client.get(f"/suggestions?mode={mode}").json()["suggestions"]:
                for kw in forbidden:
                    assert kw not in s
