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
    """回傳 ColPali query 編碼器（128 維，與 page 端同模型同池化），gate 關 → None。

    #133：page 端為 colpali-v1.2、patch mean-pool 成 128 維。query 端同模型同池化
    （見 :mod:`polaris.retrieval.colpali_query_encoder`）。重相依（torch + colpali-engine
    + ~5GB 權重、需 GPU）只在 ``COLPALI_QUERY_ENCODER=1`` 時載入：

    - **gate 關（預設 / CI）**：回 None → 第 4 路關閉、0 import、0 下載、確定性。
    - **gate 開**：建 :class:`~polaris.retrieval.colpali_query_encoder.ColpaliV12QueryEncoder`，
      回其 ``encode``。同空間（命中率 ≥70%）須由 ``scripts/colpali_roundtrip_check.py``
      在 GPU 環境配 R4 gold 樣本實跑確認後才正式採用（TD-01 門檻）。
    """
    from ..config import settings

    if not getattr(settings, "colpali_query_encoder", False):
        return None
    from .colpali_query_encoder import ColpaliV12QueryEncoder

    encoder = ColpaliV12QueryEncoder(
        settings.colpali_model, device=settings.colpali_device or None
    )
    return encoder.encode


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
