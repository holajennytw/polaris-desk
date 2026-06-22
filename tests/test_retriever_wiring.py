"""Last-mile retrieval wiring (R2): real query-embedding + real polaris_core.

Two gaps these tests pin down:
1. ``HybridRetriever`` never wired a real ``embedding_fn`` → vector search was
   silently skipped everywhere (incl. Deep Research's ``active_search_fn``).
   It must pull :func:`active_embedding_fn` when none is injected.
2. The 5-node workflow's ``retriever`` node returned a hard-coded stub corpus.
   When a real retriever is available it must return real, period+viewer-scoped
   contexts; with no key (CI) it stays on the deterministic stub path.
"""
from __future__ import annotations

import polaris.retrieval.retriever as rmod
from polaris.graph.nodes import stubs
from polaris.graph.state import PeriodSpec
from polaris.retrieval.retriever import HybridRetriever
from polaris.vectorstore.base import SearchResult


# ── Gap 1: HybridRetriever auto-wires the active embedding fn ──────────────

def test_hybrid_retriever_autowires_active_embedding_fn(monkeypatch):
    """No injected embedding_fn → retriever pulls active_embedding_fn so the
    vector channel actually queries the store (the bug: it stayed disabled)."""
    monkeypatch.setattr(rmod, "active_embedding_fn", lambda: (lambda q: [0.1, 0.2, 0.3]))

    vr = SearchResult(
        id="vector-2454-2026Q1",
        content="聯發科 2026Q1 法說：毛利率與產品組合。",
        score=0.9,
        company="2454",
        period="2026Q1",
        metadata={"source_id": "vector-2454-2026Q1"},
    )

    class FakeStore:
        def __init__(self):
            self.calls = []

        def search(self, query_embedding, top_k=8, *, filters=None):
            self.calls.append((query_embedding, top_k, filters))
            return [vr]

    store = FakeStore()
    retriever = HybridRetriever(top_k=3, store=store)  # NOTE: no embedding_fn

    results = retriever.retrieve("聯發科毛利率", filters={"period": "2026Q1"})

    assert store.calls == [([0.1, 0.2, 0.3], 3, {"period": "2026Q1"})]
    assert any(r.id == "vector-2454-2026Q1" for r in results)


def test_hybrid_retriever_no_embedding_when_active_returns_none(monkeypatch):
    """CI / no key: active_embedding_fn() → None → vector channel stays off
    (store.search never called), preserving token-free deterministic behavior."""
    monkeypatch.setattr(rmod, "active_embedding_fn", lambda: None)

    class FakeStore:
        def __init__(self):
            self.calls = []

        def search(self, query_embedding, top_k=8, *, filters=None):
            self.calls.append((query_embedding, top_k, filters))
            return []

    store = FakeStore()
    retriever = HybridRetriever(top_k=3, store=store)
    retriever.retrieve("台積電毛利率", filters={"period": "2025Q1"})

    assert store.calls == []


# ── Gap 2: 5-node retriever node uses the real retriever when available ────

def test_retriever_node_uses_real_retriever_when_available(monkeypatch):
    sr = SearchResult(
        id="2330-2026Q1-x",
        content="台積電 2026Q1 毛利率討論。",
        score=0.7,
        company="2330",
        period="2026Q1",
        metadata={"origin": "vector"},
    )

    class FakeRetriever:
        def __init__(self):
            self.calls = []

        def retrieve(self, query, *, filters=None):
            self.calls.append((query, filters))
            return [sr]

    fake = FakeRetriever()
    monkeypatch.setattr(stubs, "active_retriever", lambda: fake)

    state = {
        "query": "台積電毛利率",
        "period": PeriodSpec(hint="", kind="quarter", quarters=["2026Q1"]),
        "viewer": "__public__",
    }
    out = stubs.retriever(state)
    contexts = out["contexts"]

    assert len(contexts) == 1
    assert contexts[0]["source_id"] == "2330-2026Q1-x"
    assert contexts[0]["text"] == "台積電 2026Q1 毛利率討論。"
    # vector → embedding (Citation literal); period + viewer forwarded as filters
    assert contexts[0]["origin"] == "embedding"
    # company（偵測自「台積電」）+ period + viewer 一起當 filters（修 R6 cross-company）
    assert fake.calls == [
        ("台積電毛利率", {"viewer": "__public__", "company": "2330", "period": "2026Q1"})
    ]


def test_retriever_node_dedups_across_quarters(monkeypatch):
    """Two quarters in the period → one retrieve per quarter, same chunk_id
    surfacing in both is kept once."""
    shared = SearchResult(
        id="dup-1", content="共用片段", score=0.8, company="2330", period="2026Q1", metadata={}
    )
    only_q4 = SearchResult(
        id="q4-1", content="Q4 片段", score=0.7, company="2330", period="2025Q4", metadata={}
    )

    class FakeRetriever:
        def retrieve(self, query, *, filters=None):
            return [shared] if filters.get("period") == "2026Q1" else [shared, only_q4]

    monkeypatch.setattr(stubs, "active_retriever", lambda: FakeRetriever())

    state = {
        "query": "比較最近兩季",
        "period": PeriodSpec(hint="", kind="recent_quarters", quarters=["2026Q1", "2025Q4"]),
        "viewer": "__public__",
    }
    contexts = stubs.retriever(state)["contexts"]
    ids = [c["source_id"] for c in contexts]
    assert ids == ["dup-1", "q4-1"]


def test_retriever_node_falls_back_to_stub_when_no_real_retriever(monkeypatch):
    """No key (CI): active_retriever() → None → deterministic stub corpus path,
    identical to pre-wiring behavior (guards existing temporal/e2e tests)."""
    monkeypatch.setattr(stubs, "active_retriever", lambda: None)

    state = {
        "query": "台積電",
        "period": PeriodSpec(hint="", kind="quarter", quarters=["2025Q1"]),
        "viewer": "__public__",
    }
    contexts = stubs.retriever(state)["contexts"]
    assert contexts == [stubs._STUB_CORPUS["2025Q1"]]
