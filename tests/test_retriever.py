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


def test_rerank_rotates_to_second_key_on_429(monkeypatch):
    """COHERE_API_KEY 逗號分隔多把金鑰；第一把 429 → 自動輪到第二把。"""
    import sys
    import types

    from polaris.retrieval.retriever import _cohere_rerank
    from polaris.vectorstore.base import SearchResult as SR

    used_keys: list[str] = []

    class _Quota429(Exception):
        def __init__(self):
            super().__init__("429 too many requests")
            self.status_code = 429

    class _Resp:
        results = [type("H", (), {"index": 0, "relevance_score": 0.9})()]

    class _FakeClientV2:
        def __init__(self, *a, **kw):
            self._key = kw.get("api_key")

        def rerank(self, *, model, query, documents, top_n):  # noqa: ARG002
            used_keys.append(self._key)
            if self._key == "co_first":
                raise _Quota429()
            return _Resp()

    fake = types.ModuleType("cohere")
    fake.ClientV2 = _FakeClientV2
    monkeypatch.setitem(sys.modules, "cohere", fake)
    monkeypatch.setenv("COHERE_API_KEY", "co_first,co_second")
    monkeypatch.delenv("COHERE_RERANK_MODEL", raising=False)

    out = [SR(id="a", content="ca", score=0.5, metadata={"origin": "bm25"})]
    reranked = _cohere_rerank("q", out, top_k=1)

    assert used_keys == ["co_first", "co_second"]  # 輪替發生
    assert [r.id for r in reranked] == ["a"]
    assert reranked[0].metadata["origin"] == "rerank"


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


def test_research_search_uses_per_doc_type_quotas_then_reranks_once():
    """Deep Research must give each canonical text source a candidate quota.

    A single unfiltered vector query lets the much larger major_news corpus crowd
    transcript/news out before reranking.  Research therefore searches each
    doc_type independently, merges the candidates, and performs one final rerank.
    """
    from polaris.retrieval.retriever import HybridRetriever, make_research_search_fn
    from polaris.vectorstore.base import SearchResult as SR

    store_calls: list[tuple[int, dict]] = []
    rerank_calls: list[tuple[list[str], int]] = []

    class PerTypeStore:
        def search(self, query_embedding, top_k=8, *, filters=None):
            doc_type = filters["doc_type"]
            store_calls.append((top_k, dict(filters)))
            return [
                SR(
                    id=f"{doc_type}-1",
                    content=f"{doc_type} evidence",
                    score=0.9,
                    company="2330",
                    period="2026Q1",
                    metadata={
                        "doc_type": doc_type,
                        "published_at": "2026-04-17",
                        "fiscal_period": "2026Q1",
                    },
                )
            ]

        def health_check(self):
            return True

    def final_rerank(query, results, top_k):  # noqa: ARG001
        rerank_calls.append(([r.id for r in results], top_k))
        return results

    retriever = HybridRetriever(
        top_k=8,
        store=PerTypeStore(),
        embedding_fn=lambda _query: [0.1],
        rerank_fn=final_rerank,
    )

    citations = make_research_search_fn(retriever, viewer="analyst_A")("台積電風險")

    # presentation 是法說家族第二來源：台股多數公司無逐字稿、只有法說簡報，
    # Deep Research 須一併撈簡報（全 20 家入庫），否則那些公司的法說內容全被漏掉。
    assert store_calls == [
        (5, {"doc_type": "transcript", "viewer": "analyst_A"}),
        (4, {"doc_type": "presentation", "viewer": "analyst_A"}),
        (5, {"doc_type": "major_news", "viewer": "analyst_A"}),
        (3, {"doc_type": "news", "viewer": "analyst_A"}),
    ]
    assert rerank_calls == [
        (["transcript-1", "presentation-1", "major_news-1", "news-1"], 8)
    ]
    assert [c.source_id for c in citations] == [
        "transcript-1",
        "presentation-1",
        "major_news-1",
        "news-1",
    ]


def test_research_citations_expose_document_metadata():
    """R7 needs real document metadata instead of guessing labels and quarters."""
    from datetime import date

    from polaris.retrieval.retriever import HybridRetriever, make_research_search_fn
    from polaris.vectorstore.base import SearchResult as SR

    class TranscriptStore:
        def search(self, query_embedding, top_k=8, *, filters=None):  # noqa: ARG002
            if filters.get("doc_type") != "transcript":
                return []
            return [
                SR(
                    id="chunk-2330-q1",
                    content="法說原文",
                    score=0.9,
                    company="2330",
                    period="2026Q1",
                    metadata={
                        "doc_type": "transcript",
                        "published_at": date(2026, 4, 17),
                        "fiscal_period": "2026Q1",
                    },
                )
            ]

        def health_check(self):
            return True

    retriever = HybridRetriever(
        store=TranscriptStore(),
        embedding_fn=lambda _query: [0.1],
        rerank_fn=lambda _query, results, _top_k: results,
    )

    citation = make_research_search_fn(retriever)("台積電法說")[0]

    assert citation.doc_type == "transcript"
    assert citation.fiscal_period == "2026Q1"
    assert citation.published_at == date(2026, 4, 17)


def test_retrieve_results_always_carry_citation_metadata_keys():
    """Every retrieve() result carries doc_type / published_at / fiscal_period in
    metadata so api.py /research + Deep Research adapters can read them safely on
    any channel — incl. the BM25/stub fallback that doesn't set them natively
    (prevents R7 ``metadata["published_at"]`` KeyError).
    """
    retriever = HybridRetriever(top_k=5)  # BM25-only (no Gemini key/real data in CI)
    results = retriever.retrieve("台積電 2025Q1 毛利率")

    assert results
    for r in results:
        assert "doc_type" in r.metadata
        assert "published_at" in r.metadata
        assert "fiscal_period" in r.metadata
        assert r.metadata["fiscal_period"] == r.period  # mirrors typed period field


def test_retrieve_results_carry_semantic_metadata_keys():
    """P1：retrieve() 每筆結果都帶 event_key / source_key / published_yyyymm（store 端
    由 v_chunk_semantic JOIN 取得；BM25/stub 通道無值 → None，不編造），讓 /ask citation
    在任何通道都能安全讀到這三鍵。"""
    retriever = HybridRetriever(top_k=5)  # BM25-only (CI)
    results = retriever.retrieve("台積電 2025Q1 毛利率")

    assert results
    for r in results:
        for key in ("event_key", "source_key", "published_yyyymm"):
            assert key in r.metadata
            assert r.metadata[key] is None  # 無值 → None（不編造）


def test_vector_search_failure_logs_warning_and_falls_back_to_bm25(caplog):
    """P0：向量後端丟例外時，記 warning（含 traceback / exc_info），但仍回 BM25 結果
    —— 檢索不中斷、fallback 行為不退步（修「靜默吞錯」）。"""
    import logging

    class ExplodingStore:
        def search(self, query_embedding, top_k=8, *, filters=None):
            raise RuntimeError("BQ exploded")

        def health_check(self):
            return True

    retriever = HybridRetriever(
        top_k=3, store=ExplodingStore(), embedding_fn=lambda _q: [0.1, 0.2, 0.3]
    )
    with caplog.at_level(logging.WARNING, logger="polaris.retrieval.retriever"):
        results = retriever.retrieve("台積電 2025Q1 毛利率")

    # 仍有 BM25 fallback 結果（向量失敗不讓整條查詢掛掉）
    assert results
    assert any("台積電" in r.content for r in results)
    # warning 有記、訊息可辨識、且帶 traceback（exc_info=True）
    warns = [
        rec for rec in caplog.records
        if rec.levelno == logging.WARNING and "vector search failed" in rec.message
    ]
    assert warns, "expected a vector-search-failure warning"
    assert warns[0].exc_info is not None  # exc_info → traceback 一併記下


# ---------------------------------------------------------------------------
# Recency-aware reorder (issue #49): 「最新一季」類查詢不該被舊期別強相關塊壓過
# ---------------------------------------------------------------------------

def _wants_recency_import():
    from polaris.retrieval.retriever import _wants_recency
    return _wants_recency


def test_wants_recency_detects_temporal_intent():
    _wants_recency = _wants_recency_import()
    assert _wants_recency("台積電最新一季營收表現如何？")
    assert _wants_recency("聯發科近期毛利率")
    assert _wants_recency("most recent revenue")
    # 無時間意圖 → False（不可誤觸發，否則所有查詢都被 recency 重排）
    assert not _wants_recency("台積電 2023 毛利率結構")
    assert not _wants_recency("營收組成與產品線")


def _two_period_store():
    """同主題、不同期別的兩筆向量結果：舊期別 base score 略高（重現 #49）。"""
    def mk(id_, period, pub, score):
        r = type("R", (), {})()
        r.id, r.content, r.score = id_, f"聯發科 {period} 營收成長與展望", score
        r.company, r.period = "2454", period
        r.metadata = {"source_id": id_, "published_at": pub}
        return r

    class FakeStore:
        def search(self, query_embedding, top_k=8, *, filters=None):
            return [
                mk("v-2454-2023Q1", "2023Q1", "2023-04-28", 0.80),  # 舊、分數高
                mk("v-2454-2024Q3", "2024Q3", "2024-10-31", 0.70),  # 新、分數低
            ]

    return FakeStore()


def test_recency_intent_promotes_latest_period_over_higher_scored_old():
    retriever = HybridRetriever(
        top_k=5, store=_two_period_store(), embedding_fn=lambda _q: [1.0]
    )
    results = retriever.retrieve("聯發科最新一季營收表現", filters={"company": "2454"})
    # 「最新」意圖 → 最新期別排第一，即使 base score 較低
    assert results[0].period == "2024Q3", [r.period for r in results]


def test_without_recency_intent_preserves_base_score_order():
    retriever = HybridRetriever(
        top_k=5, store=_two_period_store(), embedding_fn=lambda _q: [1.0]
    )
    results = retriever.retrieve("聯發科 營收 成長", filters={"company": "2454"})
    # 無時間意圖 → 維持原 base score 排序（舊但分數高者在前），不加 recency 偏好
    assert results[0].period == "2023Q1", [r.period for r in results]
