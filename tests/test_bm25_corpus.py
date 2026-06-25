"""BM25 真實 corpus 載入測試（issue #30：取代 3 筆 hardcoded stub）。

啟動時從 canonical ``polaris_core.v_chunk_semantic`` 載入最新 N 季 chunks 建 BM25
語料；無金鑰 / 載入失敗 → 退回確定性 stub（CI token-free 不變）。

注入式 fake client → 0 GCP 外呼，與 test_vectorstore_impl.py 同套路。
"""
from __future__ import annotations

from datetime import date

import polaris.retrieval.retriever as R
from polaris.config import Settings
from polaris.retrieval.retriever import HybridRetriever, active_bm25_corpus
from polaris.vectorstore.base import SearchResult
from polaris.vectorstore.bigquery_store import BigQueryStore


def make_settings(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


class FakeBQJob:
    def __init__(self, rows=None):
        self._rows = rows or []

    def result(self):
        return self._rows


class FakeBQClient:
    def __init__(self, rows=None):
        self.queries: list[str] = []
        self._rows = rows or []

    def query(self, sql, job_config=None):
        self.queries.append(sql)
        return FakeBQJob(self._rows)


_VIEW_ROW = {
    "chunk_id": "2330-2026Q1-c001",
    "chunk_text": "台積電 2026Q1 法說：AI 與高效能運算需求帶動營收成長。",
    "ticker": "2330",
    "fiscal_period": "2026Q1",
    "doc_type": "transcript",
    "published_at": date(2026, 4, 16),
    "event_key": "evt-2330-2026Q1",
    "source_key": "src-mops-2330",
    "published_yyyymm": "202604",
}


# ── BigQueryStore.load_bm25_corpus ────────────────────────────────────────────

def test_load_bm25_corpus_queries_semantic_view_latest_periods():
    client = FakeBQClient(rows=[_VIEW_ROW])
    store = BigQueryStore(make_settings(), client=client)

    store.load_bm25_corpus(periods=2)

    sql = client.queries[0]
    assert "v_chunk_semantic" in sql
    assert "ORDER BY fiscal_period DESC" in sql
    assert "@periods" in sql
    # BM25 只要文字 + 引用欄，絕不掃 768-float embedding（quota：~4 MiB not 65 MiB）
    assert "embedding" not in sql


def test_load_bm25_corpus_maps_rows_to_search_results():
    client = FakeBQClient(rows=[_VIEW_ROW])
    store = BigQueryStore(make_settings(), client=client)

    corpus = store.load_bm25_corpus(periods=2)

    assert len(corpus) == 1
    item = corpus[0]
    assert isinstance(item, SearchResult)
    assert item.id == "2330-2026Q1-c001"
    assert item.company == "2330"
    assert item.period == "2026Q1"
    assert item.content.startswith("台積電")
    # doc_type 進 metadata → 讓 BM25 通道也能套 doc_type filter（stub 做不到）
    assert item.metadata["doc_type"] == "transcript"
    # citation 三欄帶進來（解 #6：BM25 結果也有來源）
    assert item.metadata["event_key"] == "evt-2330-2026Q1"
    assert item.metadata["source_key"] == "src-mops-2330"
    assert item.metadata["published_yyyymm"] == "202604"
    assert item.metadata["published_at"] == "2026-04-16"


def test_load_bm25_corpus_empty_when_no_rows():
    store = BigQueryStore(make_settings(), client=FakeBQClient(rows=[]))
    assert store.load_bm25_corpus() == []


# ── HybridRetriever 對注入 corpus 做 BM25 排序 ────────────────────────────────

def _real_corpus() -> list[SearchResult]:
    return [
        SearchResult(
            id="real-2330-2026Q1",
            content="台積電 2026Q1 法說：AI 需求帶動營收成長。",
            score=0.0,
            company="2330",
            period="2026Q1",
            metadata={"doc_type": "transcript"},
        ),
        SearchResult(
            id="real-2317-2026Q1",
            content="鴻海 2026Q1 法說：雲端網路與電腦終端營收占比。",
            score=0.0,
            company="2317",
            period="2026Q1",
            metadata={"doc_type": "transcript"},
        ),
    ]


def test_retriever_ranks_over_injected_corpus():
    r = HybridRetriever(top_k=3, bm25_corpus=_real_corpus())

    results = r.retrieve("AI 需求 營收")

    assert results[0].id == "real-2330-2026Q1"
    assert results[0].metadata["origin"] == "bm25"


def test_injected_corpus_supports_doc_type_filter():
    """real corpus 帶 doc_type → doc_type filter 真正生效（stub 語料做不到）。"""
    r = HybridRetriever(top_k=5, bm25_corpus=_real_corpus())

    kept = r.retrieve("AI 需求", filters={"doc_type": "transcript"})
    assert len(kept) >= 1
    assert all(x.metadata.get("doc_type") == "transcript" for x in kept)

    dropped = r.retrieve("AI 需求", filters={"doc_type": "news"})
    assert dropped == []


# ── active_bm25_corpus 閘控（無金鑰 → stub；有金鑰 → 真實；失敗 → stub）─────────

def test_active_bm25_corpus_falls_back_to_stub_without_key(monkeypatch):
    monkeypatch.setattr("polaris.llm.gemini.available", lambda: False)
    R._cached_real_corpus.cache_clear()

    corpus = active_bm25_corpus()

    assert [c.id for c in corpus] == [c.id for c in R._FALLBACK_CORPUS]


def test_active_bm25_corpus_uses_real_when_available(monkeypatch):
    monkeypatch.setattr("polaris.llm.gemini.available", lambda: True)
    monkeypatch.setattr(R, "_load_real_corpus", lambda: _real_corpus())
    R._cached_real_corpus.cache_clear()

    corpus = active_bm25_corpus()

    assert [c.id for c in corpus] == ["real-2330-2026Q1", "real-2317-2026Q1"]


def test_active_bm25_corpus_falls_back_to_stub_on_load_failure(monkeypatch):
    monkeypatch.setattr("polaris.llm.gemini.available", lambda: True)
    monkeypatch.setattr(R, "_load_real_corpus", lambda: [])  # 載入失敗回空
    R._cached_real_corpus.cache_clear()

    corpus = active_bm25_corpus()

    assert [c.id for c in corpus] == [c.id for c in R._FALLBACK_CORPUS]
