from polaris.retrieval.retriever import HybridRetriever


def test_retriever_returns_ranked_results():
    retriever = HybridRetriever(top_k=2)

    results = retriever.retrieve("台積電 2025Q1 毛利率")

    assert len(results) > 0
    assert results[0].score > 0
    assert "台積電" in results[0].content


def test_retriever_respects_period_filter():
    retriever = HybridRetriever(top_k=5)

    results = retriever.retrieve("台積電 毛利率", filters={"period": "2025Q1"})

    assert len(results) > 0
    assert all(r.period == "2025Q1" for r in results)


def test_retriever_empty_query_returns_empty_list():
    retriever = HybridRetriever()

    assert retriever.retrieve("") == []
    assert retriever.retrieve("   ") == []


def test_retriever_uses_bm25_keyword_ranking():
    retriever = HybridRetriever(top_k=1)

    results = retriever.retrieve("AI 需求 營收")

    assert len(results) == 1
    assert results[0].id == "stub-2330-2024Q4-revenue"
    assert results[0].metadata["origin"] == "bm25"


def test_retriever_merges_vector_search_results():
    vector_result = type("Result", (), {})()
    vector_result.id = "vector-2454-2025Q1-gm"
    vector_result.content = "聯發科 2025Q1 法說摘要：毛利率與產品組合相關。"
    vector_result.score = 0.91
    vector_result.company = "2454"
    vector_result.period = "2025Q1"
    vector_result.metadata = {"source_id": "vector-2454-2025Q1-gm"}

    class FakeStore:
        def __init__(self):
            self.calls = []

        def search(self, query_embedding, top_k=8, *, filters=None):
            self.calls.append((query_embedding, top_k, filters))
            return [vector_result]

    store = FakeStore()
    retriever = HybridRetriever(
        top_k=3,
        store=store,
        embedding_fn=lambda query: [0.1, 0.2, 0.3],
    )

    results = retriever.retrieve("聯發科 2025Q1 毛利率", filters={"period": "2025Q1"})

    assert store.calls == [([0.1, 0.2, 0.3], 3, {"period": "2025Q1"})]
    assert results[0].id == "vector-2454-2025Q1-gm"
    assert results[0].metadata["origin"] == "vector"


def test_retriever_deduplicates_bm25_and_vector_results():
    vector_result = type("Result", (), {})()
    vector_result.id = "stub-2330-2025Q1-gm"
    vector_result.content = "台積電 2025Q1 法說摘要：毛利率受到匯率影響。"
    vector_result.score = 0.99
    vector_result.company = "2330"
    vector_result.period = "2025Q1"
    vector_result.metadata = {"source_id": "stub-2330-2025Q1-gm"}

    class FakeStore:
        def search(self, query_embedding, top_k=8, *, filters=None):
            return [vector_result]

    retriever = HybridRetriever(
        top_k=5,
        store=FakeStore(),
        embedding_fn=lambda query: [1.0],
    )

    results = retriever.retrieve("台積電 2025Q1 毛利率")

    ids = [result.id for result in results]
    assert ids.count("stub-2330-2025Q1-gm") == 1
    merged = next(result for result in results if result.id == "stub-2330-2025Q1-gm")
    assert merged.score == 0.99
    assert merged.metadata["retrieval_channels"] == ["bm25", "vector"]


def test_retriever_viewer_filter_passed_to_store():
    """HybridRetriever passes viewer to store.search; store enforces owner filter (issue #32).

    The contract: HybridRetriever brings viewer into store.search(filters={...}).
    Real stores (BigQuery/pgvector) enforce the filter as SQL; this test uses a
    store that simulates that behaviour.
    """
    from polaris.vectorstore.base import SearchResult as SR

    all_docs = [
        SR(id="private-client-b", content="機密：Client B 投資組合 XYZ。",
           score=1.0, metadata={"owner": "client_B"}),
        SR(id="public-tsmc", content="台積電 2025Q1 法說摘要。",
           score=1.0, metadata={}),
    ]

    class OwnerFilteringStore:
        """Simulates a real store that enforces owner-based access control."""
        def __init__(self):
            self.received_filters: dict | None = None

        def search(self, query_embedding, top_k=8, *, filters=None):
            self.received_filters = filters
            viewer = (filters or {}).get("viewer")
            return [
                d for d in all_docs
                if d.metadata.get("owner") is None or d.metadata.get("owner") == viewer
            ]

        def health_check(self):
            return True

    store = OwnerFilteringStore()
    retriever = HybridRetriever(top_k=5, store=store, embedding_fn=lambda _q: [0.1])

    results = retriever.retrieve("投資組合", filters={"viewer": "analyst_A"})

    # Verify viewer was forwarded to store.search (issue #32 contract)
    assert store.received_filters == {"viewer": "analyst_A"}
    ids = [r.id for r in results]
    assert "private-client-b" not in ids
    assert "public-tsmc" in ids


def test_retriever_viewer_filter_allows_matching_owner():
    """owner-scoped doc IS visible to the matching principal (issue #32)."""
    from polaris.vectorstore.base import SearchResult as SR

    my_doc = SR(id="client-a-doc", content="Client A 專屬法說摘要。",
                score=1.0, metadata={"owner": "analyst_A"})

    class OwnerFilteringStore:
        def search(self, query_embedding, top_k=8, *, filters=None):
            viewer = (filters or {}).get("viewer")
            return [d for d in [my_doc]
                    if d.metadata.get("owner") is None or d.metadata.get("owner") == viewer]

        def health_check(self):
            return True

    retriever = HybridRetriever(top_k=5, store=OwnerFilteringStore(),
                                embedding_fn=lambda _q: [0.1])
    results = retriever.retrieve("Client A", filters={"viewer": "analyst_A"})
    assert any(r.id == "client-a-doc" for r in results)


def test_retriever_bm25_viewer_filter_blocks_owner_scoped():
    """BM25 path: _matches_filters enforces viewer on in-memory corpus (issue #32)."""
    from polaris.retrieval.retriever import _matches_filters
    from polaris.vectorstore.base import SearchResult as SR

    public = SR(id="pub", content="公開", score=1.0, metadata={})
    owned = SR(id="priv", content="私有", score=1.0, metadata={"owner": "client_B"})

    assert _matches_filters(public, {"viewer": "analyst_A"}) is True
    assert _matches_filters(owned, {"viewer": "analyst_A"}) is False
    assert _matches_filters(owned, {"viewer": "client_B"}) is True


def test_retriever_bm25_confidential_filter_matches_store_sql():
    """BM25 path gates on confidential too, agreeing with the store SQL filter.

    A confidential doc with no owner must NOT leak to an arbitrary viewer — the
    store SQL is ``(NOT COALESCE(confidential, FALSE) OR owner = viewer)``; the
    in-memory path has to make the same call (issue #32).
    """
    from polaris.retrieval.retriever import _matches_filters
    from polaris.vectorstore.base import SearchResult as SR

    confidential_public = SR(id="mnpi", content="MNPI", score=1.0,
                             metadata={"confidential": True})
    confidential_owned = SR(id="mnpi-b", content="MNPI", score=1.0,
                            metadata={"owner": "client_B", "confidential": True})

    # ownerless-but-confidential leaks under owner-only logic; must be blocked
    assert _matches_filters(confidential_public, {"viewer": "analyst_A"}) is False
    # owner sees their own confidential doc
    assert _matches_filters(confidential_owned, {"viewer": "client_B"}) is True
    assert _matches_filters(confidential_owned, {"viewer": "analyst_A"}) is False


# ---------------------------------------------------------------------------
# Cohere Rerank (3rd retrieval path)
# ---------------------------------------------------------------------------

def test_retriever_rerank_fn_called_and_reorders():
    """Injected rerank_fn is called and its output ordering is used verbatim.

    Strategy: BM25-only retrieval (no store/embedding_fn) on the built-in corpus
    with a generous top_k so we know all candidates going into rerank.  The fake
    reranker reverses the list and stamps origin="rerank"; we assert the final
    order matches the reranker's output, not the original BM25 order.
    """
    from polaris.retrieval.retriever import HybridRetriever
    from polaris.vectorstore.base import SearchResult as SR

    recorded: list[tuple[str, list[str], int]] = []

    def fake_rerank(query: str, results: list, top_k: int) -> list:
        recorded.append((query, [r.id for r in results], top_k))
        # Reverse the candidate list; inject origin=rerank
        reranked = []
        for i, r in enumerate(reversed(results)):
            meta = {**r.metadata, "origin": "rerank",
                    "retrieval_channels": list(r.metadata.get("retrieval_channels", [])) + ["rerank"]}
            reranked.append(SR(id=r.id, content=r.content,
                               score=1.0 - i * 0.1,
                               company=r.company, period=r.period,
                               metadata=meta))
        return reranked[:top_k]

    retriever = HybridRetriever(top_k=3, rerank_fn=fake_rerank)
    results = retriever.retrieve("台積電 毛利率")

    # rerank_fn was invoked exactly once
    assert len(recorded) == 1
    assert recorded[0][0] == "台積電 毛利率"
    # rerank_fn's output is used: first result has origin=rerank
    assert results[0].metadata["origin"] == "rerank"
    assert "rerank" in results[0].metadata["retrieval_channels"]
    # ordering came from the reranker (highest score = 1.0)
    assert results[0].score == 1.0


def test_retriever_no_rerank_fn_and_no_api_key_skips_gracefully():
    """Without COHERE_API_KEY and no rerank_fn, retrieve still returns results."""
    import os
    os.environ.pop("COHERE_API_KEY", None)

    from polaris.retrieval.retriever import HybridRetriever

    retriever = HybridRetriever(top_k=3)
    results = retriever.retrieve("台積電 毛利率")

    assert len(results) > 0
    assert results[0].score > 0


def test_retriever_rerank_exception_falls_back_to_bm25_order():
    """_cohere_rerank's try/except: Cohere failure leaves BM25+vector order intact."""
    import os

    from polaris.retrieval.retriever import HybridRetriever

    os.environ.pop("COHERE_API_KEY", None)
    retriever = HybridRetriever(top_k=3)
    results = retriever.retrieve("台積電 毛利率")
    assert len(results) > 0


def test_rerank_uses_clientv2_and_valid_model(monkeypatch):
    """成功路徑：走 cohere.ClientV2 + client.rerank，型號為有效的 rerank-v3.5。

    鎖住 2026-06 修正前的 bug（v1 `Client` 呼 .v2.rerank + 不存在的 rerank-v4.0）。
    """
    import sys
    import types

    from polaris.retrieval.retriever import _cohere_rerank
    from polaris.vectorstore.base import SearchResult as SR

    captured: dict = {}

    class _Hit:
        def __init__(self, index, score):
            self.index = index
            self.relevance_score = score

    class _Resp:
        # 反轉順序 → 證明 rerank 真的有套用
        results = [_Hit(1, 0.9), _Hit(0, 0.1)]

    class _FakeClientV2:
        def __init__(self, *a, **kw):
            captured["api_key"] = kw.get("api_key")

        def rerank(self, *, model, query, documents, top_n):
            captured["model"] = model
            captured["n_docs"] = len(documents)
            return _Resp()

    fake = types.ModuleType("cohere")
    fake.ClientV2 = _FakeClientV2
    monkeypatch.setitem(sys.modules, "cohere", fake)
    monkeypatch.setenv("COHERE_API_KEY", "test-key")
    monkeypatch.delenv("COHERE_RERANK_MODEL", raising=False)

    out = [
        SR(id="a", content="ca", score=0.5, metadata={"origin": "bm25"}),
        SR(id="b", content="cb", score=0.4, metadata={"origin": "vector"}),
    ]
    reranked = _cohere_rerank("q", out, top_k=2)

    assert captured["model"] == "rerank-v3.5"  # 有效型號（非 rerank-v4.0）
    assert captured["api_key"] == "test-key"
    assert [r.id for r in reranked] == ["b", "a"]  # 依 rerank 分數重排
    assert reranked[0].metadata["origin"] == "rerank"
    assert "rerank" in reranked[0].metadata["retrieval_channels"]


def test_rerank_model_override_via_env(monkeypatch):
    """COHERE_RERANK_MODEL 可覆寫型號（部署彈性）。"""
    import sys
    import types

    from polaris.retrieval.retriever import _cohere_rerank
    from polaris.vectorstore.base import SearchResult as SR

    captured: dict = {}

    class _Resp:
        results = []  # 空結果 → 回空 list，足以驗證型號傳遞

    class _FakeClientV2:
        def __init__(self, *a, **kw):
            pass

        def rerank(self, *, model, query, documents, top_n):
            captured["model"] = model
            return _Resp()

    fake = types.ModuleType("cohere")
    fake.ClientV2 = _FakeClientV2
    monkeypatch.setitem(sys.modules, "cohere", fake)
    monkeypatch.setenv("COHERE_API_KEY", "test-key")
    monkeypatch.setenv("COHERE_RERANK_MODEL", "rerank-multilingual-v3.0")

    _cohere_rerank("q", [SR(id="a", content="ca", score=0.5, metadata={})], top_k=1)
    assert captured["model"] == "rerank-multilingual-v3.0"


def test_rerank_skip_logs_debug_when_no_key(caplog):
    """No COHERE_API_KEY → debug log explains why rerank was skipped (review nit #5)."""
    import logging
    import os

    from polaris.retrieval.retriever import _cohere_rerank
    from polaris.vectorstore.base import SearchResult as SR

    os.environ.pop("COHERE_API_KEY", None)
    out = [SR(id="x", content="c", score=1.0, metadata={})]
    with caplog.at_level(logging.DEBUG, logger="polaris.retrieval.retriever"):
        result = _cohere_rerank("q", out, 3)
    assert result is out  # unchanged ordering
    assert any("skipping rerank" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Default viewer = public sentinel (review nit #4)
# ---------------------------------------------------------------------------

def test_active_search_fn_default_viewer_is_public_sentinel():
    """make_retriever_search_fn defaults to PUBLIC_VIEWER and forwards it to the store.

    A default/unauthenticated caller must therefore see public docs only — never
    an owner-scoped doc owned by a real principal.
    """
    from polaris.retrieval.retriever import (
        PUBLIC_VIEWER,
        HybridRetriever,
        make_retriever_search_fn,
    )
    from polaris.vectorstore.base import SearchResult as SR

    owned = SR(id="client-b", content="機密", score=1.0, metadata={"owner": "client_B"})
    public = SR(id="pub", content="公開", score=1.0, metadata={})

    captured: dict = {}

    class CapturingStore:
        def search(self, query_embedding, top_k=8, *, filters=None):
            captured["filters"] = filters
            viewer = (filters or {}).get("viewer")
            return [d for d in (owned, public)
                    if d.metadata.get("owner") in (None, viewer)]

        def health_check(self):
            return True

    retriever = HybridRetriever(top_k=5, store=CapturingStore(), embedding_fn=lambda _q: [0.1])
    search = make_retriever_search_fn(retriever)  # no viewer → sentinel default
    cites = search("投資組合")

    assert captured["filters"] == {"viewer": PUBLIC_VIEWER}
    ids = [c.source_id for c in cites]
    assert "client-b" not in ids   # owner-scoped doc hidden from default caller
    assert "pub" in ids


def test_make_retriever_search_fn_maps_vector_origin_to_embedding():
    """SearchResult origin 'vector' must map to the 'embedding' Citation literal.

    Citation.origin is a Literal without 'vector'; passing it through verbatim
    would raise a ValidationError once a real vector store is wired.
    """
    from polaris.retrieval.retriever import HybridRetriever, make_retriever_search_fn
    from polaris.vectorstore.base import SearchResult as SR

    class VectorStoreStub:
        def search(self, query_embedding, top_k=8, *, filters=None):
            # store results carry origin set by _normalize_vector_result → "vector"
            return [SR(id="v1", content="向量命中", score=0.9, metadata={})]

        def health_check(self):
            return True

    retriever = HybridRetriever(top_k=5, store=VectorStoreStub(), embedding_fn=lambda _q: [0.1])
    cites = make_retriever_search_fn(retriever)("台積電")

    assert any(c.source_id == "v1" for c in cites)
    assert all(c.origin in {"stub", "bm25", "embedding", "colpali", "rerank", "news"} for c in cites)
    assert next(c for c in cites if c.source_id == "v1").origin == "embedding"
