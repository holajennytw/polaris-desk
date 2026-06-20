"""第 4 路（gated）：ColPali 視覺檢索 retriever。

- query → 注入的 encode_query（128 維，與 colpali_pages 同空間）→ BigQueryColpaliStore.search。
- encode_query 是唯一外部相依（待 issue #133 由 R4 提供同模型同池化的編碼器）。
- 未接時 active_colpali_retriever() 回 None、retrieve() 回 []：第 4 路關閉，CI 0 外呼。
- gated：只給場景 3（圖表題）用，不混進文字 HybridRetriever 的排序。
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..vectorstore.base import SearchResult

EmbeddingFn = Callable[[str], list[float]]


class ColpaliRetriever:
    def __init__(self, *, encode_query: EmbeddingFn | None, store, top_k: int = 8) -> None:
        self.encode_query = encode_query
        self.store = store
        self.top_k = top_k

    def retrieve(self, query: str, *, filters: dict[str, Any] | None = None) -> list[SearchResult]:
        if self.encode_query is None:
            return []
        vector = self.encode_query(query)
        if not vector:
            return []
        return self.store.search(vector, self.top_k, filters=filters)


def active_colpali_query_fn() -> "EmbeddingFn | None":
    """回傳 ColPali query 編碼器（128 維，與 page 端同模型同池化），尚未接 → None。

    待 issue #133：R4 提供 checkpoint + 池化 + query 編碼途徑後，在此接上
    （in-process 模型或推論端點）。在那之前回 None，使第 4 路關閉、CI 確定性。
    """
    return None


def active_colpali_retriever() -> "ColpaliRetriever | None":
    """encoder 到位才回真 retriever；否則 None（第 4 路關閉）。"""
    fn = active_colpali_query_fn()
    if fn is None:
        return None
    from ..config import settings
    from ..vectorstore.colpali_store import BigQueryColpaliStore
    return ColpaliRetriever(
        encode_query=fn, store=BigQueryColpaliStore(settings), top_k=settings.top_k
    )
