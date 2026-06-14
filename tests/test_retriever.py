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
