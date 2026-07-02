"""D15 — Deep Research v0 ReAct loop（polaris.graph.deep_research.agent）。

純 Python bounded loop：smart(LLM)/確定性 fallback 雙路徑、≤6 迴圈、evidence 累積、
最終結論過 D9 Compliance（NFR-031）。全程無金鑰可跑（stub_search + 確定性政策）。
"""
from __future__ import annotations

from polaris.graph.deep_research import agent as ag
from polaris.graph.deep_research.state import DeepResearchResult
from polaris.graph.state import Citation


class _ScriptedLLM:
    """每次 generate 回 responses 下一則；用盡回 default（避免 compliance 取用時爆）。"""

    def __init__(self, responses, default="CLEAN"):
        self._responses = list(responses)
        self._default = default
        self.calls = []

    def generate(self, prompt, *, flash=False, system_instruction=None):
        self.calls.append({"prompt": prompt, "flash": flash})
        return self._responses.pop(0) if self._responses else self._default


class _BoomLLM:
    def __init__(self):
        self.calls = []

    def generate(self, prompt, *, flash=False, system_instruction=None):
        self.calls.append(prompt)
        raise RuntimeError("boom")  # 非暫時性 → call_with_retry 立即 re-raise（不 sleep）


class TestStubSearch:
    def test_returns_citations(self):
        out = ag.stub_search("台積電 營收")
        assert out and all(isinstance(c, Citation) for c in out)

    def test_deterministic(self):
        assert [c.source_id for c in ag.stub_search("x")] == [
            c.source_id for c in ag.stub_search("x")
        ]

    def test_distinct_per_query(self):
        assert ag.stub_search("台積電 營收")[0].source_id != ag.stub_search("台積電 毛利率")[0].source_id


class TestDeterministicRun:
    def test_runs_to_answered_with_evidence(self):
        r = ag.run_deep_research("台積電 2025Q1 體質")
        assert isinstance(r, DeepResearchResult)
        assert r.status == "answered"
        assert len(r.evidence) >= 3
        assert 1 <= r.iterations <= 6
        assert r.final_answer.strip()
        assert r.compliance_status == "passed"
        assert any(s.action == "search" for s in r.react_steps)
        assert any(s.action == "finish" for s in r.react_steps)

    def test_deterministic_repeatable(self):
        r1 = ag.run_deep_research("台積電 Q1")
        r2 = ag.run_deep_research("台積電 Q1")
        assert r1.final_answer == r2.final_answer
        assert [c.source_id for c in r1.evidence] == [c.source_id for c in r2.evidence]
        assert r1.iterations == r2.iterations

    def test_no_buysell_in_answer(self):
        from polaris.graph.compliance import BUYSELL_KEYWORDS

        r = ag.run_deep_research("該買台積電嗎")
        assert all(kw not in r.final_answer for kw in BUYSELL_KEYWORDS)


class TestBounded:
    def test_exhausts_at_max_loops_when_no_evidence(self):
        r = ag.run_deep_research("Q", search=lambda q: [], max_loops=3)
        assert r.iterations == 3
        assert r.status == "exhausted"
        assert r.final_answer.strip()  # 不崩、誠實結論


class TestSmartPath:
    def test_llm_finish_single_iteration(self):
        client = _ScriptedLLM(["Thought: 夠了\nAction: finish\nAction Input: 根據引用，營收成長。"])
        r = ag.run_deep_research("台積電 Q1", client=client)
        assert r.status == "answered"
        assert r.final_answer == "根據引用，營收成長。"
        assert r.iterations == 1
        assert r.compliance_status == "passed"

    def test_llm_search_then_finish(self):
        client = _ScriptedLLM(
            [
                "Thought: 找\nAction: search\nAction Input: 台積電 營收",
                "Thought: 再找\nAction: search\nAction Input: 台積電 毛利率",
                "Thought: 夠了\nAction: finish\nAction Input: 綜合結論。",
            ]
        )
        r = ag.run_deep_research("台積電 Q1", client=client, search=ag.stub_search)
        assert r.status == "answered"
        assert r.iterations == 3
        assert len(r.evidence) == 2
        assert [s.action for s in r.react_steps] == ["search", "search", "finish"]

    def test_llm_failure_degrades_to_deterministic(self, no_retry_sleep):
        r = ag.run_deep_research("台積電 Q1", client=_BoomLLM())
        assert r.status == "answered"  # 退確定性仍完成
        assert len(r.evidence) >= 3


class TestClientAutoWiring:
    """run_deep_research auto-wires the LLM client from active_llm() when none is
    passed (mirrors the search default), so the deployed /research uses Gemini
    reasoning when a key is present and the deterministic path when absent."""

    def test_autowires_active_llm_when_client_none(self, monkeypatch):
        # LLM present → reasoning is LLM-driven: it finishes on iteration 1, which
        # the deterministic policy never does (that always searches first).
        client = _ScriptedLLM(["Thought: 夠了\nAction: finish\nAction Input: 結論摘要。"])
        monkeypatch.setattr(ag, "active_llm", lambda: client)

        r = ag.run_deep_research("台積電 Q1", search=ag.stub_search)  # no client passed

        assert client.calls  # LLM was invoked for reasoning
        assert r.iterations == 1  # LLM finished immediately; deterministic would search first
        assert r.final_answer == "結論摘要。"

    def test_no_key_falls_back_to_deterministic(self, monkeypatch):
        monkeypatch.setattr(ag, "active_llm", lambda: None)

        r = ag.run_deep_research("台積電 2025Q1 體質", search=ag.stub_search)

        # deterministic facet policy: searches until >=3 evidence, then finishes
        assert r.status == "answered"
        assert len(r.evidence) >= 3
        assert r.iterations >= 3


class TestSearchAutoWiring:
    """issue #77：跨公司檢索污染修復——run_deep_research 沒收到 search 時，必須從
    使用者原始問題偵測公司並透傳給 active_search_fn，讓每輪 ReAct 檢索都硬過濾在
    正確公司範圍內（不管 LLM 那輪自己下的 tool_input 有沒有帶公司名）。"""

    def test_autowires_active_search_fn_with_companies_detected_from_question(
        self, monkeypatch
    ):
        calls: list[dict] = []

        def fake_active_search_fn(viewer, *, companies=None):
            calls.append({"viewer": viewer, "companies": companies})
            return ag.stub_search

        from polaris.retrieval import retriever as retriever_module

        monkeypatch.setattr(retriever_module, "active_search_fn", fake_active_search_fn)
        monkeypatch.setattr(ag, "active_llm", lambda: None)

        ag.run_deep_research("台積電 2025Q1 法說會重點")

        assert len(calls) == 1
        assert calls[0]["companies"] == ["2330"]

    def test_no_company_detected_passes_none(self, monkeypatch):
        calls: list[dict] = []

        def fake_active_search_fn(viewer, *, companies=None):
            calls.append({"viewer": viewer, "companies": companies})
            return ag.stub_search

        from polaris.retrieval import retriever as retriever_module

        monkeypatch.setattr(retriever_module, "active_search_fn", fake_active_search_fn)
        monkeypatch.setattr(ag, "active_llm", lambda: None)

        ag.run_deep_research("半導體產業展望如何？")

        assert len(calls) == 1
        assert calls[0]["companies"] == []


class TestCompliance:
    def test_advisory_finish_blocked(self):
        from polaris.graph.compliance import SAFE_MESSAGE

        client = _ScriptedLLM(["Thought:\nAction: finish\nAction Input: 我建議買進台積電。"])
        r = ag.run_deep_research("台積電", client=client)
        assert r.compliance_status == "blocked"
        assert r.final_answer == SAFE_MESSAGE


class TestSearchSeam:
    def test_injected_search_used(self):
        calls = []

        def fake_search(q):
            calls.append(q)
            return [Citation(source_id=f"x-{len(calls)}", snippet="片段", origin="stub")]

        r = ag.run_deep_research("Q", search=fake_search)
        assert calls  # 注入的 search 被呼叫
        assert r.status == "answered"


class TestViewerParam:
    """viewer identity flows through run_deep_research (issue #32)."""

    def test_viewer_default_is_public_sentinel(self):
        """Omitting viewer succeeds and defaults to the public sentinel principal."""
        import inspect

        from polaris.retrieval.retriever import PUBLIC_VIEWER

        assert inspect.signature(ag.run_deep_research).parameters["viewer"].default == PUBLIC_VIEWER
        r = ag.run_deep_research("台積電")
        assert r.status in {"answered", "exhausted"}

    def test_viewer_accepted_and_stored_in_state(self):
        """viewer is accepted without error; custom value is fine."""
        r = ag.run_deep_research("台積電", viewer="analyst_A")
        assert r.status in {"answered", "exhausted"}

    def test_viewer_aware_search_fn_receives_viewer_via_closure(self):
        """Pattern for R4: wrap search_fn with viewer via closure."""
        captured_viewer: list[str] = []

        def viewer_aware_search(q: str, *, viewer: str) -> list[Citation]:
            captured_viewer.append(viewer)
            return [Citation(source_id=f"v-{viewer}", snippet="片段", origin="stub")]

        viewer = "analyst_A"
        r = ag.run_deep_research(
            "台積電",
            viewer=viewer,
            search=lambda q: viewer_aware_search(q, viewer=viewer),
        )
        assert r.status in {"answered", "exhausted"}
        assert all(v == "analyst_A" for v in captured_viewer)


class TestComparisonMode:
    """比較型問題（≥2 檔代號）：逐檔檢索 + 依公司分組的同業比較合成。"""

    def test_extract_tickers_finds_distinct_codes_in_order(self):
        assert ag._extract_tickers("比較 2330 與 2454 對 AI 需求的看法") == ["2330", "2454"]
        assert ag._extract_tickers("2330 2330 體質") == ["2330"]  # 去重保序
        assert ag._extract_tickers("台積電體質如何") == []

    def test_comparison_question_groups_evidence_by_ticker(self):
        import re

        def search(q):
            m = re.search(r"\d{4}", q)
            t = m.group(0) if m else "x"
            return [Citation(source_id=f"c-{t}", snippet=f"{t} 對 AI 需求看好", origin="stub", company=t)]

        r = ag.run_deep_research(
            "比較 2330 與 2454 對 AI 需求的看法", search=search, min_citations=2
        )
        assert "同業比較" in r.final_answer
        assert "2330：" in r.final_answer
        assert "2454：" in r.final_answer
        # 兩家證據各自歸組（grounded by construction：每條列帶來源）
        assert "（來源：c-2330）" in r.final_answer
        assert "（來源：c-2454）" in r.final_answer

    def test_comparison_deterministic_searches_each_ticker(self):
        seen_queries: list[str] = []

        def search(q):
            seen_queries.append(q)
            return [Citation(source_id=f"s-{len(seen_queries)}", snippet="片段", origin="stub")]

        ag.run_deep_research("比較 2330 與 2454 的展望", search=search, min_citations=4)
        assert any("2330" in q for q in seen_queries)
        assert any("2454" in q for q in seen_queries)

    def test_single_ticker_question_uses_plain_summary(self):
        r = ag.run_deep_research("台積電 2025Q1 體質", search=ag.stub_search)
        assert "同業比較" not in r.final_answer
        assert "研究摘要" in r.final_answer
