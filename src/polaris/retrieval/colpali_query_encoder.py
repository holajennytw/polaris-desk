"""ColPali v1.2 query 端編碼器（#133）：query → 多向量 token embeddings →
mean-pool 成單一 128 維，與 R4 page 端（``colpali_pages``，``n_patches`` 個 patch
向量 mean-pool）同空間。

設計重點：
- **重相依延遲 import**：``torch`` + ``colpali-engine`` + ColPali v1.2 權重（~5GB，需 GPU）
  只在實際編碼時載入。``active_colpali_query_fn`` 預設回 None（gate 關），故 import
  本模組不會拉進 torch、CI 0 下載 0 外呼。
- **pool 必須對齊 page 端**：page 向量是 patch embeddings 的 **mean-pool**（單一 128 維）；
  query 端同樣把 query token embeddings mean-pool 成單一 128 維才同空間。pooling 換了
  就不同空間、round-trip 會接近隨機——故 :func:`mean_pool` 抽成純函式單測鎖住。
- **驗收**：同空間與否要靠 ``scripts/colpali_roundtrip_check.py``（真權重 + live 表 +
  R4 gold 樣本）跑命中率 ≥70%（TD-01 門檻）。本模組只保證「形狀/池化正確」，
  「語意同空間」需該腳本在 GPU 環境實跑確認。
"""
from __future__ import annotations

from collections.abc import Callable, Sequence


def mean_pool(token_vectors: Sequence[Sequence[float]]) -> list[float]:
    """多向量 token embeddings → 單一向量（逐維平均）。

    對齊 page 端 patch mean-pool。空輸入回 []（呼叫端據此 skip，不查 store）。
    """
    rows = [list(v) for v in token_vectors]
    if not rows:
        return []
    dim = len(rows[0])
    if any(len(v) != dim for v in rows):
        raise ValueError("token 向量維度不一致，無法 mean-pool")
    sums = [0.0] * dim
    for v in rows:
        for i, x in enumerate(v):
            sums[i] += x
    n = len(rows)
    return [s / n for s in sums]


class ColpaliV12QueryEncoder:
    """colpali-v1.2 query 編碼器。``encode(query) -> list[float]``（mean-pool 後 128 維）。

    ``_load`` / ``_embed_tokens`` 為 seam：測試可注入 fake backbone（回 token 向量），
    不需 torch/權重即可驗 encode→pool 串接；真環境延遲載入 colpali-engine。
    """

    def __init__(
        self,
        model_name: str = "vidore/colpali-v1.2",
        *,
        device: str | None = None,
        pool: Callable[[Sequence[Sequence[float]]], list[float]] = mean_pool,
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.pool = pool
        self._model = None
        self._processor = None

    def _resolve_device(self) -> str:
        if self.device:
            return self.device
        import torch  # 延遲：gate 開才需要

        return "cuda" if torch.cuda.is_available() else "cpu"

    def _load(self) -> None:
        """延遲載入 ColPali v1.2 模型 + processor（torch + colpali-engine + 權重）。"""
        if self._model is not None:
            return
        import torch
        from colpali_engine.models import ColPali, ColPaliProcessor

        device = self._resolve_device()
        model = ColPali.from_pretrained(
            self.model_name,
            torch_dtype=torch.bfloat16 if device == "cuda" else torch.float32,
            device_map=device,
        )
        model.train(False)  # 推論模式（等同 torch eval-mode）
        self._model = model
        self._processor = ColPaliProcessor.from_pretrained(self.model_name)

    def _embed_tokens(self, query: str) -> list[list[float]]:
        """query → 每個 query token 的 128 維 embedding（late-interaction 多向量）。"""
        import torch

        self._load()
        batch = self._processor.process_queries([query]).to(self._model.device)
        with torch.no_grad():
            out = self._model(**batch)  # [1, n_tokens, 128]
        return out[0].float().cpu().tolist()

    def encode(self, query: str) -> list[float]:
        """query → 單一 128 維向量（與 colpali_pages 同空間）。"""
        return self.pool(self._embed_tokens(query))
