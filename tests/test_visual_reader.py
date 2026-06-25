"""visual_reader 節點測試（Phase B：查詢期 vision 讀圖 escalation）。

全程 0 外呼：extractor / page_image_fn 注入 fake。flag 預設關 → 節點 no-op。
"""
from __future__ import annotations

from polaris.graph.nodes.visual_reader import (
    VisualTarget,
    parse_target,
    read_visual_pages,
    should_escalate,
    visual_reader,
)
from polaris.ingestion.vision_schema import KeyValue, PageExtraction


# ── fakes ────────────────────────────────────────────────────────────────────

class FakeExtractor:
    """回固定 PageExtraction，記錄收到的 doc_type；0 外呼。"""

    def __init__(self, extraction: PageExtraction) -> None:
        self._extraction = extraction
        self.calls: list[bytes] = []

    def extract(self, image_bytes: bytes, *, doc_type: str) -> PageExtraction:
        self.calls.append(image_bytes)
        self.doc_type = doc_type
        return self._extraction


def _ctx(source_id: str, text: str = "", **kw) -> dict:
    base = {"source_id": source_id, "text": text, "company": "2330",
            "period": "2025Q3", "origin": "bm25"}
    base.update(kw)
    return base


_EXTRACTION = PageExtraction(
    page_summary="2025Q3 營收結構",
    key_values=[KeyValue(label="HPC 佔比", value=52.0, unit="%")],
    confidence=0.9,
)


# ── parse_target ─────────────────────────────────────────────────────────────

class TestParseTarget:
    def test_extracts_page_from_chunk_id(self):
        t = parse_target(_ctx("2330-2025Q3-p009-c001"))
        assert t == VisualTarget(
            source_id="2330-2025Q3-p009-c001", company="2330",
            period="2025Q3", page=9,
        )

    def test_returns_none_for_non_page_source(self):
        # URL hash / stub-id 無 -pNNN- 段 → 無法定位頁 → None（不瞎猜）
        assert parse_target(_ctx("news-abcdef123456")) is None
        assert parse_target(_ctx("stub-q3")) is None

    def test_returns_none_when_source_id_missing(self):
        assert parse_target({"text": "x"}) is None


# ── should_escalate ──────────────────────────────────────────────────────────

class TestShouldEscalate:
    def test_chart_question_with_numberless_contexts_escalates(self):
        q = "從這張營收結構圖看，第三季哪個部門佔比最高？"
        contexts = [_ctx("2330-2025Q3-p009-c001", text="本季營運概況說明")]
        assert should_escalate(q, contexts) is True

    def test_chart_question_with_numeric_contexts_does_not_escalate(self):
        # 文字脈絡已含數字 → 文字路足夠，不必付 vision 成本
        q = "從這張營收結構圖看，第三季哪個部門佔比最高？"
        contexts = [_ctx("2330-2025Q3-p009-c001", text="HPC 佔比 52%")]
        assert should_escalate(q, contexts) is False

    def test_non_chart_question_never_escalates(self):
        q = "台積電 2025Q3 法說會說了什麼？"
        contexts = [_ctx("2330-2025Q3-p009-c001", text="純文字無數字")]
        assert should_escalate(q, contexts) is False


class TestShouldEscalateTunable:
    """觸發門檻 numberless_floor 交由 eval 校準（#3）。"""

    _Q = "從這張營收結構圖看，哪個部門佔比最高？"
    _MIXED = [
        _ctx("2330-2025Q3-p009-c001", text="HPC 佔比 52%"),  # 有數字
        _ctx("2330-2025Q3-p010-c001", text="本季概況"),       # 無數字
    ]

    def test_default_floor_requires_all_numberless(self):
        # floor=1.0（預設）：一半脈絡已有數字 → 不升級（保留原行為）
        assert should_escalate(self._Q, self._MIXED) is False

    def test_lower_floor_escalates_on_partial_numberless(self):
        # floor=0.5：50% 脈絡無數字 ≥ 0.5 → 升級（更積極）
        assert should_escalate(self._Q, self._MIXED, numberless_floor=0.5) is True


# ── read_visual_pages ────────────────────────────────────────────────────────

class TestReadVisualPages:
    def test_renders_and_flattens_top_page(self):
        extractor = FakeExtractor(_EXTRACTION)
        contexts = [_ctx("2330-2025Q3-p009-c001", text="無數字")]
        out = read_visual_pages(
            "營收結構圖", contexts,
            extractor=extractor, page_image_fn=lambda t: b"PNG",
        )
        assert len(out) == 1
        assert out[0]["origin"] == "vision"
        assert "HPC 佔比: 52%" in out[0]["text"]
        assert out[0]["source_id"] == "2330-2025Q3-p009-c001"
        assert extractor.doc_type == "presentation"

    def test_skips_target_when_image_unavailable(self):
        # page_image_fn 回 None（查詢期定位不到 PDF）→ 誠實略過，不編造
        extractor = FakeExtractor(_EXTRACTION)
        contexts = [_ctx("2330-2025Q3-p009-c001", text="無數字")]
        out = read_visual_pages(
            "營收結構圖", contexts,
            extractor=extractor, page_image_fn=lambda t: None,
        )
        assert out == []
        assert extractor.calls == []  # 沒圖就不呼叫抽取器

    def test_respects_max_pages_and_dedupes(self):
        extractor = FakeExtractor(_EXTRACTION)
        contexts = [
            _ctx("2330-2025Q3-p009-c001", text="a"),
            _ctx("2330-2025Q3-p009-c002", text="b"),  # 同頁不同 chunk → 去重
            _ctx("2330-2025Q3-p010-c001", text="c"),
            _ctx("2330-2025Q3-p011-c001", text="d"),
        ]
        out = read_visual_pages(
            "圖", contexts, extractor=extractor,
            page_image_fn=lambda t: b"PNG", max_pages=2,
        )
        pages = {(o["source_id"]) for o in out}
        assert len(out) == 2  # 去重後 9/10/11 三頁，取前 2
        assert "2330-2025Q3-p009-c001" in pages


# ── visual_reader node ───────────────────────────────────────────────────────

class TestVisualReaderNode:
    def test_noop_when_flag_disabled(self, monkeypatch):
        from polaris.config import settings
        monkeypatch.setattr(settings, "visual_reader", False, raising=False)
        state = {"query": "營收結構圖", "contexts": [_ctx("2330-2025Q3-p009-c001")]}
        assert visual_reader(state) == {}

    def test_escalates_when_flag_on_and_trigger_met(self, monkeypatch):
        from polaris.config import settings
        from polaris.graph.nodes import visual_reader as vr_mod

        monkeypatch.setattr(settings, "visual_reader", True, raising=False)
        monkeypatch.setattr(vr_mod, "active_vision_extractor",
                            lambda: FakeExtractor(_EXTRACTION))
        monkeypatch.setattr(vr_mod, "_default_page_image_fn", lambda t: b"PNG")

        contexts = [_ctx("2330-2025Q3-p009-c001", text="無數字")]
        state = {"query": "從這張營收結構圖看，哪個部門佔比最高？", "contexts": contexts}
        patch = visual_reader(state)
        # 原 contexts 保留 + 追加 vision context
        assert len(patch["contexts"]) == 2
        assert patch["contexts"][-1]["origin"] == "vision"

    def test_noop_when_extractor_gate_closed(self, monkeypatch):
        from polaris.config import settings
        from polaris.graph.nodes import visual_reader as vr_mod

        monkeypatch.setattr(settings, "visual_reader", True, raising=False)
        monkeypatch.setattr(vr_mod, "active_vision_extractor", lambda: None)
        state = {"query": "營收結構圖", "contexts": [_ctx("2330-2025Q3-p009-c001", text="無數字")]}
        assert visual_reader(state) == {}


# ── workflow wiring (retriever → visual_reader → writer) ─────────────────────

class TestWorkflowWiring:
    def test_vision_citation_flows_to_answer(self, monkeypatch):
        """flag 開 + retriever 回缺數字圖表頁 → visual_reader 補 vision 脈絡，
        該脈絡經 writer 變成 origin='vision' 的 citation 進到最終結果。"""
        from polaris.config import settings
        from polaris.graph.nodes import stubs
        from polaris.graph.nodes import visual_reader as vr_mod
        from polaris.graph.nodes.trace import traced

        monkeypatch.setattr(settings, "visual_reader", True, raising=False)
        monkeypatch.setattr(vr_mod, "active_vision_extractor",
                            lambda: FakeExtractor(_EXTRACTION))
        monkeypatch.setattr(vr_mod, "_default_page_image_fn", lambda t: b"PNG")

        @traced("retriever")
        def stub_retriever(state):
            return {"contexts": [_ctx("2330-2025Q3-p009-c001", text="本季概況（無數字）")]}

        monkeypatch.setattr(stubs, "retriever", stub_retriever)

        from polaris.graph.workflow import build_workflow
        result = build_workflow().invoke({"query": "從這張營收結構圖看，哪個部門佔比最高？"})

        assert result.get("halt") is not True
        origins = {c.origin for c in result.get("citations", [])}
        assert "vision" in origins

    def test_flag_off_workflow_unchanged(self, monkeypatch):
        """flag 關（預設）→ visual_reader no-op，workflow 端到端照跑、不 halt。"""
        from polaris.config import settings

        monkeypatch.setattr(settings, "visual_reader", False, raising=False)
        from polaris.graph.workflow import build_workflow
        result = build_workflow().invoke({"query": "台積電 2025Q1 營收？"})
        assert result.get("halt") is not True
        assert result.get("answer", "").strip()
