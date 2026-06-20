"""ColpaliRetriever：把 query 經注入 encode_query 編 128 維 → 查 store → SearchResult。

encoder 缺席（None）= 第 4 路未接（待 #133）→ 回 []，不炸（CI friendly）。
"""
from __future__ import annotations

from polaris.retrieval.colpali_retriever import ColpaliRetriever, active_colpali_retriever
from polaris.vectorstore.base import SearchResult


class FakeStore:
    def __init__(self):
        self.calls = []

    def search(self, query_embedding, top_k=8, *, filters=None):
        self.calls.append((query_embedding, top_k, filters))
        return [
            SearchResult(
                id="pg-1", content="2330 2025Q3 第 9 頁圖表（x.pdf）", score=0.9,
                company="2330", period="2025Q3", metadata={"origin": "colpali", "page_num": 9},
            )
        ]


def test_retrieve_encodes_query_and_returns_colpali_results():
    store = FakeStore()
    retriever = ColpaliRetriever(encode_query=lambda t: [0.2] * 8, store=store, top_k=5)
    [res] = retriever.retrieve("台積電 2025Q3 毛利率", filters={"company": "2330"})
    assert res.metadata["origin"] == "colpali"
    # 確實把編碼後的向量與 filter 傳進 store
    qe, k, filters = store.calls[0]
    assert qe == [0.2] * 8 and k == 5 and filters == {"company": "2330"}


def test_retrieve_without_encoder_returns_empty_not_raises():
    store = FakeStore()
    retriever = ColpaliRetriever(encode_query=None, store=store, top_k=5)
    assert retriever.retrieve("任何 query") == []
    assert store.calls == []  # encoder 缺席 → 不查 store


def test_active_colpali_retriever_is_none_until_encoder_wired():
    # #133 的 query encoder 尚未接 → 工廠回 None（第 4 路關閉，CI 0 外呼）
    assert active_colpali_retriever() is None
