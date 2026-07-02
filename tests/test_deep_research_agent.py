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
    """issue #77：跨公司檢索污染 + 期別錯配修復——run_deep_research 沒收到 search
    時，必須從使用者原始問題偵測公司與季別並透傳給 active_search_fn，讓每輪 ReAct
    檢索都硬過濾在正確範圍內（不管 LLM 那輪自己下的 tool_input 有沒有帶）。"""

    @staticmethod
    def _capture_active_search_fn(monkeypatch) -> list[dict]:
        calls: list[dict] = []

        def fake_active_search_fn(viewer, *, companies=None, periods=None):
            calls.append({"viewer": viewer, "companies": companies, "periods": periods})
            return ag.stub_search

        from polaris.retrieval import retriever as retriever_module

        monkeypatch.setattr(retriever_module, "active_search_fn", fake_active_search_fn)
        monkeypatch.setattr(ag, "active_llm", lambda: None)
        return calls

    def test_autowires_companies_and_periods_detected_from_question(self, monkeypatch):
        calls = self._capture_active_search_fn(monkeypatch)

        ag.run_deep_research("台積電 2025Q1 法說會重點")

        assert len(calls) == 1
        assert calls[0]["companies"] == ["2330"]
        assert calls[0]["periods"] == ["2025Q1"]

    def test_no_company_or_period_detected_passes_empty(self, monkeypatch):
        calls = self._capture_active_search_fn(monkeypatch)

        ag.run_deep_research("半導體產業展望如何？")

        assert len(calls) == 1
        assert calls[0]["companies"] == []
        assert calls[0]["periods"] is None  # 時間中性 → 不加期別過濾

    def test_relative_period_resolved_via_anchor(self, monkeypatch):
        calls = self._capture_active_search_fn(monkeypatch)

        ag.run_deep_research("台積電最近兩季的毛利率")

        # CI 無憑證 → anchor 為 DEFAULT_ANCHOR（2025Q1），最近兩季 = 2025Q1 + 2024Q4
        assert calls[0]["periods"] == ["2025Q1", "2024Q4"]


class TestCoverageNote:
    """issue #85 Q035：比較題含未收錄公司（如和碩）時，不能只回籠統「資料不足」，
    要誠實說明資料覆蓋範圍——使用者才分得清「沒資料」與「系統不收錄這家」。"""

    def test_comparison_with_uncovered_company_gets_note(self):
        text = ag._synthesize("請比較鴻海與和碩 2025Q1 的 EMS 代工營收來源", [])
        assert "資料不足" in text
        assert "僅「鴻海」為本系統收錄公司" in text
        assert "20 家" in text

    def test_note_also_added_when_single_side_has_evidence(self):
        ev = [Citation(source_id="c-2317", snippet="鴻海片段", origin="stub")]
        text = ag._synthesize("請比較鴻海與和碩 2025Q1 的 EMS 代工營收來源", ev)
        assert "c-2317" in text
        assert "僅「鴻海」為本系統收錄公司" in text

    def test_cross_quarter_comparison_not_flagged(self):
        """單一公司 + 多季別（Q007 型）是合法題型，不得誤觸覆蓋提示。"""
        text = ag._synthesize("台積電 2025Q1 相比 2024Q4 營收變化", [])
        assert "收錄公司" not in text

    def test_two_covered_companies_not_flagged(self):
        ev = [
            Citation(source_id="c-2330", snippet="台積電片段", origin="stub"),
            Citation(source_id="c-2454", snippet="聯發科片段", origin="stub"),
        ]
        text = ag._synthesize("比較台積電與聯發科的毛利率", ev)
        assert "收錄公司" not in text

    def test_non_comparison_question_not_flagged(self):
        text = ag._synthesize("和碩 2025Q1 營收如何", [])
        # 非比較題不觸發（單問未收錄公司仍回一般「資料不足」，不誤導）
        assert "收錄公司" not in text


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
        # 實體解析：中文名也解析得出 ticker（issue #77 R4 排查建議）
        assert ag._extract_tickers("台積電體質如何") == ["2330"]
        assert ag._extract_tickers("比較台積電與聯發科的毛利率") == ["2330", "2454"]

    def test_extract_tickers_ignores_years_and_quarters(self):
        """裸 \\d{4} 會把年份誤抓成代號 → 跨季比較題被誤判為比較型（issue #77）。"""
        assert ag._extract_tickers("台積電 2025Q1 相比 2024Q4 營收變化") == ["2330"]
        assert ag._extract_tickers("2024 全年四季的營收趨勢") == []

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


class TestStructuredEarlyExit:
    """降 /research 延遲：單一公司財務數字題直接查 financial_metrics 早停（issue：單題 >90s）。

    守則：只有單一公司 + 指標關鍵字 + 季別才早停；比較題（≥2 家）與質化題不觸發；
    無金鑰時整個捷徑停用（維持 CI 確定性）。
    """

    @staticmethod
    def _fake_store(rows):
        # 用 autospec 綁真 StructuredStore 簽章：誤傳未知 kwarg 會 raise TypeError，讓
        # 「捷徑因 list_financials 簽章漂移而靜默失效」這類 bug 在 CI 就炸出來。
        from unittest.mock import create_autospec

        from polaris.structured_store import StructuredStore

        mock_cls = create_autospec(StructuredStore)
        mock_cls.return_value.list_financials.return_value = rows
        return mock_cls

    # 真表（v_financial_metrics_semantic）無 metric_name 欄位 → 走 _METRIC_LABELS 映射。
    _ROW = {
        "metric_id": "revenue", "value": 8386000, "unit": "新台幣千元",
        "source_id": "2330_2026-03-31_finmind_fs",
    }

    def test_seed_single_company_metric(self, monkeypatch):
        import polaris.llm.gemini as gem
        import polaris.structured_store as ss
        monkeypatch.setattr(gem, "available", lambda: True)
        monkeypatch.setattr(ss, "StructuredStore", self._fake_store([self._ROW]))
        seeds = ag._structured_seed("台積電 2026Q1 營業收入", ag.PUBLIC_VIEWER)
        assert seeds and seeds[0].source_id == "2330_2026-03-31_finmind_fs"
        assert seeds[0].company == "台積電"

    def test_seed_formats_number_and_maps_label(self, monkeypatch):
        # 大整數 → 千分位（非科學記號 8.386e+06）；無 metric_name → 中文標籤映射
        import polaris.llm.gemini as gem
        import polaris.structured_store as ss
        monkeypatch.setattr(gem, "available", lambda: True)
        monkeypatch.setattr(ss, "StructuredStore", self._fake_store([self._ROW]))
        snippet = ag._structured_seed("台積電 2026Q1 營業收入", ag.PUBLIC_VIEWER)[0].snippet
        assert "8,386,000" in snippet and "e+" not in snippet
        assert "營業收入" in snippet and "revenue" not in snippet

    def test_seed_skips_comparison(self, monkeypatch):
        import polaris.llm.gemini as gem
        import polaris.structured_store as ss
        monkeypatch.setattr(gem, "available", lambda: True)
        monkeypatch.setattr(ss, "StructuredStore", self._fake_store([self._ROW]))
        # ≥2 家 → 不早停（避免只拿到單邊就收尾弄壞比較）
        assert ag._structured_seed("比較台積電與聯發科 2026Q1 營業收入", ag.PUBLIC_VIEWER) == []

    def test_seed_skips_when_a_metric_missing(self, monkeypatch):
        # 問營收+毛利率但只查得到營收 → 不給半套答案，退回 ReAct 補齊
        import polaris.llm.gemini as gem
        import polaris.structured_store as ss
        monkeypatch.setattr(gem, "available", lambda: True)
        monkeypatch.setattr(ss, "StructuredStore", self._fake_store([self._ROW]))
        assert ag._structured_seed("台積電 2026Q1 營收與毛利率", ag.PUBLIC_VIEWER) == []

    def test_wanted_metrics_longest_match(self):
        # 「毛利率」不可同時誤命中子字串「毛利」（否則完整性守門永遠不早停）
        assert ag._wanted_metrics("台積電 2026q1 毛利率") == {"gross_margin"}
        assert ag._wanted_metrics("台積電 2026q1 營業利益率") == {"operating_margin"}

    def test_seed_skips_non_metric_question(self, monkeypatch):
        import polaris.llm.gemini as gem
        monkeypatch.setattr(gem, "available", lambda: True)
        # 無指標關鍵字（質化題）→ 不早停
        assert ag._structured_seed("台積電 2026Q1 法說會重點", ag.PUBLIC_VIEWER) == []

    def test_seed_disabled_without_key(self, monkeypatch):
        import polaris.llm.gemini as gem
        monkeypatch.setattr(gem, "available", lambda: False)
        assert ag._structured_seed("台積電 2026Q1 營業收入", ag.PUBLIC_VIEWER) == []

    def test_run_deep_research_early_exits_and_skips_loop(self, monkeypatch):
        seed = [Citation(source_id="fm-2330-2026Q1-revenue",
                         snippet="台積電 2026Q1 營業收入 838.6 十億元", origin="bm25", company="台積電")]
        monkeypatch.setattr(ag, "_structured_seed", lambda q, v: seed)
        searched: list[str] = []
        r = ag.run_deep_research(
            "台積電 2026Q1 營業收入", client="UNUSED",
            search=lambda q: (searched.append(q) or []),
        )
        assert r.status == "answered"
        assert r.iterations == 1
        assert searched == []  # 早停 → 完全沒進 ReAct 檢索迴圈
        assert any(c.source_id == "fm-2330-2026Q1-revenue" for c in r.evidence)
