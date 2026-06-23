"""ColPali v1.2 query 編碼器測試（#133）：純函式 mean-pool + encode→pool 串接 +
gate 行為。不需 torch / colpali-engine / 權重（注入 fake backbone）→ CI 0 下載 0 外呼。
"""
from __future__ import annotations

import pytest

from polaris.config import Settings
from polaris.retrieval.colpali_query_encoder import ColpaliV12QueryEncoder, mean_pool


def make_settings(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


# ── mean_pool 純函式（鎖住與 page 端同池化）──────────────────────────────────

def test_mean_pool_averages_per_dimension():
    assert mean_pool([[1.0, 2.0], [3.0, 4.0]]) == [2.0, 3.0]


def test_mean_pool_single_vector_is_itself():
    assert mean_pool([[0.5, -0.5, 1.0]]) == [0.5, -0.5, 1.0]


def test_mean_pool_empty_returns_empty():
    # 空 → []，呼叫端據此 skip、不查 store
    assert mean_pool([]) == []


def test_mean_pool_rejects_ragged_dims():
    with pytest.raises(ValueError, match="維度不一致"):
        mean_pool([[1.0, 2.0], [3.0]])


def test_mean_pool_preserves_128_dim():
    tokens = [[float(i)] * 128 for i in range(5)]
    pooled = mean_pool(tokens)
    assert len(pooled) == 128
    assert pooled[0] == pytest.approx(2.0)  # mean(0..4)


# ── encode→pool 串接（注入 fake backbone，不碰 torch）─────────────────────────

def test_encode_pools_token_embeddings_to_single_vector():
    enc = ColpaliV12QueryEncoder("vidore/colpali-v1.2")
    # 繞過 _load + torch：直接注入 token 向量來源
    enc._embed_tokens = lambda q: [[1.0, 1.0], [3.0, 5.0]]  # type: ignore[method-assign]
    assert enc.encode("台積電 2025Q3 毛利率") == [2.0, 3.0]


def test_encode_uses_injected_pool():
    enc = ColpaliV12QueryEncoder("vidore/colpali-v1.2", pool=lambda toks: [9.0])
    enc._embed_tokens = lambda q: [[1.0], [2.0]]  # type: ignore[method-assign]
    assert enc.encode("q") == [9.0]


def test_resolve_device_honours_explicit_setting():
    # 指定 device 時不需 import torch（不走 cuda 偵測分支）
    enc = ColpaliV12QueryEncoder("vidore/colpali-v1.2", device="cpu")
    assert enc._resolve_device() == "cpu"


# ── gate 行為（active_colpali_query_fn）──────────────────────────────────────

def test_active_query_fn_none_when_gate_off(monkeypatch):
    """預設 COLPALI_QUERY_ENCODER 關 → None、第 4 路關閉、不 import 重相依。"""
    import polaris.retrieval.colpali_retriever as cr

    monkeypatch.setattr(cr, "settings", make_settings(colpali_query_encoder=False), raising=False)
    # settings 在函式內 from ..config import settings 取，故 patch config.settings
    import polaris.config as cfg

    monkeypatch.setattr(cfg, "settings", make_settings(colpali_query_encoder=False))
    assert cr.active_colpali_query_fn() is None
    assert cr.active_colpali_retriever() is None


def test_active_query_fn_returns_encoder_when_gate_on(monkeypatch):
    """gate 開 → 回 colpali-v1.2 encoder 的 encode（callable，未實際載權重）。"""
    import polaris.config as cfg
    import polaris.retrieval.colpali_retriever as cr

    on = make_settings(colpali_query_encoder=True, colpali_model="vidore/colpali-v1.2",
                       colpali_device="cpu")
    monkeypatch.setattr(cfg, "settings", on)
    fn = cr.active_colpali_query_fn()
    assert callable(fn)
    # 綁定到 ColpaliV12QueryEncoder.encode，且尚未載入模型（lazy）
    assert fn.__name__ == "encode"
