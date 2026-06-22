"""Tests for P0/P1 vector-search fixes.

1. _vector_search failure → warning log emitted + BM25 fallback still returns results
2. BigQueryStore SQL uses VECTOR_SEARCH on chunks + LEFT JOIN v_chunk_semantic
3. /ask citation response includes event_key / source_key / published_yyyymm (nullable)
4. Existing ticker / doc_type / fiscal_period filters do not regress
"""
from __future__ import annotations

import logging

from polaris.config import Settings
from polaris.graph.nodes.stubs import _real_contexts
from polaris.graph.nodes.writer_agent import build_citations
from polaris.graph.state import Citation
from polaris.retrieval.retriever import (
    PUBLIC_VIEWER,
    HybridRetriever,
    _matches_filters,
)
from polaris.vectorstore.base import SearchResult as SR
from polaris.vectorstore.bigquery_store import BigQueryStore


# ---------------------------------------------------------------------------
# 1. Vector search failure → warning log + BM25 fallback
# ---------------------------------------------------------------------------

class _FailStore:
    def search(self, *_a, **_kw):
        raise RuntimeError("simulated BQ error")


def test_vector_search_failure_emits_warning(caplog):
    retriever = HybridRetriever(
        store=_FailStore(),
        embedding_fn=lambda q: [0.1] * 3,
    )
    with caplog.at_level(logging.WARNING, logger="polaris.retrieval.retriever"):
        retriever.retrieve("台積電 2025Q1 毛利率")

    warning_msgs = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    assert any("Vector search" in m or "vector" in m.lower() for m in warning_msgs), (
        f"Expected a warning about vector search failure, got: {warning_msgs}"
    )
    assert any("exc_info" in r.__dict__ or r.exc_info for r in caplog.records
               if r.levelno == logging.WARNING), "Expected exc_info=True on warning"


def test_vector_search_failure_bm25_fallback_still_returns_results(caplog):
    """Even when the vector store raises, BM25 fallback must still produce results."""
    retriever = HybridRetriever(
        store=_FailStore(),
        embedding_fn=lambda q: [0.1] * 3,
    )
    with caplog.at_level(logging.WARNING, logger="polaris.retrieval.retriever"):
        results = retriever.retrieve("台積電 2025Q1 毛利率")

    assert len(results) > 0, "BM25 fallback should return stub results"
    assert all(r.metadata.get("origin") in ("bm25", "stub") for r in results)


# ---------------------------------------------------------------------------
# 2. SQL: VECTOR_SEARCH on chunks + LEFT JOIN v_chunk_semantic
# ---------------------------------------------------------------------------


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

    def load_table_from_json(self, rows, table):
        return FakeBQJob()


def make_settings(**kw) -> Settings:
    return Settings(_env_file=None, **kw)


def test_search_sql_uses_vector_search_on_chunks_not_view():
    """VECTOR_SEARCH base must stay on chunks (has embedding); view is JOIN only."""
    client = FakeBQClient()
    store = BigQueryStore(make_settings(), client=client)
    store.search([0.1] * 4, top_k=3)
    sql = client.queries[0]
    assert "VECTOR_SEARCH" in sql
    assert ".chunks" in sql, "VECTOR_SEARCH base must be the chunks table"


def test_search_sql_joins_v_chunk_semantic():
    """After VECTOR_SEARCH, SQL must JOIN v_chunk_semantic to pick up metadata."""
    client = FakeBQClient()
    store = BigQueryStore(make_settings(), client=client)
    store.search([0.1] * 4, top_k=3)
    sql = client.queries[0]
    assert "v_chunk_semantic" in sql, "SQL must LEFT JOIN v_chunk_semantic"
    assert "LEFT JOIN" in sql.upper()


def test_search_returns_three_metadata_fields_from_join():
    """SearchResult.metadata must include event_key / source_key / published_yyyymm."""
    client = FakeBQClient(rows=[{
        "chunk_id": "c1", "chunk_text": "txt", "ticker": "2330",
        "fiscal_period": "2025Q1", "doc_type": "transcript",
        "published_at": None, "distance": 0.1,
        "event_key": "earnings_call",
        "source_key": "PRIMARY_EC_TRANSCRIPT",
        "published_yyyymm": 202504,
    }])
    store = BigQueryStore(make_settings(), client=client)
    results = store.search([0.1] * 4, top_k=1)
    meta = results[0].metadata
    assert meta["event_key"] == "earnings_call"
    assert meta["source_key"] == "PRIMARY_EC_TRANSCRIPT"
    assert meta["published_yyyymm"] == 202504


def test_search_three_metadata_fields_nullable_when_absent():
    """When JOIN returns NULL (e.g. unknown doc_type), fields must be None."""
    client = FakeBQClient(rows=[{
        "chunk_id": "c2", "chunk_text": "txt", "ticker": "2330",
        "fiscal_period": "2025Q1", "doc_type": "other",
        "published_at": None, "distance": 0.2,
        "event_key": None, "source_key": None, "published_yyyymm": None,
    }])
    store = BigQueryStore(make_settings(), client=client)
    results = store.search([0.1] * 4, top_k=1)
    meta = results[0].metadata
    assert meta["event_key"] is None
    assert meta["source_key"] is None
    assert meta["published_yyyymm"] is None


# ---------------------------------------------------------------------------
# 3. Citation model + /ask response includes three nullable fields
# ---------------------------------------------------------------------------

def test_citation_model_has_three_nullable_fields():
    c = Citation(
        source_id="x", snippet="y", origin="embedding",
        event_key="earnings_call", source_key="PRIMARY_EC_TRANSCRIPT", published_yyyymm=202504,
    )
    assert c.event_key == "earnings_call"
    assert c.source_key == "PRIMARY_EC_TRANSCRIPT"
    assert c.published_yyyymm == 202504


def test_citation_model_three_fields_default_to_none():
    c = Citation(source_id="x", snippet="y", origin="stub")
    assert c.event_key is None
    assert c.source_key is None
    assert c.published_yyyymm is None


def test_build_citations_propagates_three_fields():
    contexts = [{
        "source_id": "c1",
        "snippet": "法說摘要",
        "origin": "embedding",
        "company": "2330",
        "event_key": "earnings_call",
        "source_key": "PRIMARY_EC_TRANSCRIPT",
        "published_yyyymm": 202504,
    }]
    cites = build_citations(contexts)
    assert cites[0].event_key == "earnings_call"
    assert cites[0].source_key == "PRIMARY_EC_TRANSCRIPT"
    assert cites[0].published_yyyymm == 202504


def test_build_citations_three_fields_null_when_missing():
    contexts = [{"source_id": "s", "snippet": "x", "origin": "bm25"}]
    cites = build_citations(contexts)
    assert cites[0].event_key is None
    assert cites[0].source_key is None
    assert cites[0].published_yyyymm is None


def test_real_contexts_propagates_three_fields():
    """_real_contexts must pass event_key/source_key/published_yyyymm from SearchResult.metadata."""

    class _FakeRetriever:
        def retrieve(self, _query, *, filters=None):
            return [SR(
                id="c1", content="txt", score=0.9,
                company="2330", period="2025Q1",
                metadata={
                    "origin": "vector",
                    "event_key": "earnings_call",
                    "source_key": "PRIMARY_EC_TRANSCRIPT",
                    "published_yyyymm": 202504,
                },
            )]

    ctxs = _real_contexts(_FakeRetriever(), "台積電法說", quarters=None, viewer=PUBLIC_VIEWER)
    assert ctxs[0]["event_key"] == "earnings_call"
    assert ctxs[0]["source_key"] == "PRIMARY_EC_TRANSCRIPT"
    assert ctxs[0]["published_yyyymm"] == 202504


# ---------------------------------------------------------------------------
# 4. Existing ticker / doc_type / fiscal_period filters must not regress
# ---------------------------------------------------------------------------

def test_existing_doc_type_filter_not_regressed():
    transcript = SR(id="t", content="x", score=1.0, company="2330", period="2025Q1",
                    metadata={"doc_type": "transcript"})
    news = SR(id="n", content="x", score=1.0, company="2330", period="2025Q1",
              metadata={"doc_type": "news"})
    assert _matches_filters(transcript, {"doc_type": "transcript"}) is True
    assert _matches_filters(news, {"doc_type": "transcript"}) is False


def test_existing_company_filter_not_regressed():
    r = SR(id="c", content="x", score=1.0, company="2330", period="2025Q1", metadata={})
    assert _matches_filters(r, {"company": "2330"}) is True
    assert _matches_filters(r, {"company": "2454"}) is False


def test_existing_period_filter_not_regressed():
    r = SR(id="c", content="x", score=1.0, company="2330", period="2025Q1", metadata={})
    assert _matches_filters(r, {"period": "2025Q1"}) is True
    assert _matches_filters(r, {"period": "2024Q4"}) is False


def test_bm25_fallback_results_have_nullable_three_fields():
    """After _ensure_citation_metadata, BM25 results must carry None for the three new fields."""
    retriever = HybridRetriever(top_k=2)
    results = retriever.retrieve("台積電 2025Q1 毛利率")
    for r in results:
        assert "event_key" in r.metadata
        assert "source_key" in r.metadata
        assert "published_yyyymm" in r.metadata
