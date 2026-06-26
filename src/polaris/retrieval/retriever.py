"""3-way 混合檢索：BM25 keyword + vector + Cohere Rerank。

- BM25 keyword ranking：確定性，無 API key 即可用
- Vector search：透過可注入的 embedding_fn + VectorStore.search 介面接入
- Cohere Rerank（opt-in）：``COHERE_API_KEY`` 存在且傳入 ``rerank_fn`` 時啟用；
  無 key 則 skip，結果仍為 BM25+vector merge，確定性可重現（CI friendly）
- ColPali 視覺檢索為獨立第 4 路（gated，場景 3），見 colpali_retriever / colpali_store；
  資料早於 R4 入庫 colpali_pages，TD-01 僅 cut「R3 整合」、非資料（TD-02 復原經 PM 簽核
  2026-06-23；#133 encoder 已併入。prod 啟用仍 gated，待 ≥70% round-trip 閘——
  見 scripts/colpali_roundtrip_check.py）
"""
from __future__ import annotations

import functools
import logging
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from rank_bm25 import BM25Okapi

from ..ontology import company_name
from ..vectorstore import SearchResult, VectorStore, get_vector_store


logger = logging.getLogger(__name__)

EmbeddingFn = Callable[[str], list[float]]


def active_embedding_fn() -> "EmbeddingFn | None":
    """Real query-embedding fn (gemini-embedding-2) when a Gemini key is present,
    else None so the vector channel stays disabled (BM25-only, token-free CI).

    Mirrors :func:`~polaris.llm.gemini.active_llm` /
    :func:`~polaris.compression.compressors.active_compressor`: no key → no
    client constructed, no google-genai import, deterministic CI.
    """
    from polaris.llm.gemini import active_llm

    client = active_llm()
    return client.embed if client is not None else None

# Cohere rerank callable: (query, results, top_k) -> list[SearchResult]
# Injected so tests never call the real Cohere API.
RerankFn = Callable[[str, list[SearchResult], int], list[SearchResult]]

# Sentinel principal for the default/unauthenticated caller (issue #32, review
# follow-up). A namespaced value that cannot collide with a real owner id, so a
# default caller sees public docs only — never owner-scoped docs that happen to
# be owned by a placeholder string. Access logic is ``owner IS NULL OR
# owner == viewer``; with this sentinel the right-hand side never matches a real
# owner, leaving public (owner=None) docs as the only visible set.
PUBLIC_VIEWER = "__public__"


_FALLBACK_CORPUS = [
    SearchResult(
        id="stub-2330-2025Q1-gm",
        content="台積電 2025Q1 法說摘要：毛利率受到匯率、產品組合與產能利用率影響。",
        score=0.0,
        company="2330",
        period="2025Q1",
        metadata={"source_id": "stub-2330-2025Q1-gm", "origin": "keyword_fallback"},
    ),
    SearchResult(
        id="stub-2330-2024Q4-revenue",
        content="台積電 2024Q4 法說摘要：營收成長主要來自高效能運算與 AI 相關需求。",
        score=0.0,
        company="2330",
        period="2024Q4",
        metadata={"source_id": "stub-2330-2024Q4-revenue", "origin": "keyword_fallback"},
    ),
    SearchResult(
        id="stub-2317-2025Q1-segment",
        content="鴻海 2025Q1 法說摘要：營收組成涵蓋消費智能、雲端網路、電腦終端與元件。",
        score=0.0,
        company="2317",
        period="2025Q1",
        metadata={"source_id": "stub-2317-2025Q1-segment", "origin": "keyword_fallback"},
    ),
]


# BM25 真實語料載入（issue #30）──────────────────────────────────────────────
#
# 啟動時從 canonical ``polaris_core.v_chunk_semantic`` 取最新數季 chunks 建 BM25
# 語料，取代上面 3 筆 hardcoded stub。無金鑰（CI / 本地無憑證）或載入失敗 → 退回
# ``_FALLBACK_CORPUS``，CI 仍 0 外呼、確定性不變。閘控訊號沿用 gemini.available()
# （與 active_embedding_fn / active_retriever 一致）：prod 兩把憑證俱在 → 真實語料。

#: 預設載入最新幾季（issue #30：最新 2 季 ~2,900 列 / ~4 MiB，可調）。
BM25_CORPUS_PERIODS = 2


def _load_real_corpus() -> list[SearchResult]:
    """從 VECTOR_BACKEND 後端載入真實 BM25 語料；失敗或後端不支援 → 回 []。

    同時載入 financial_metrics 合成語料（讓財務指標查詢可溯源），兩路合併。
    """
    store = get_vector_store()
    results: list[SearchResult] = []

    loader = getattr(store, "load_bm25_corpus", None)
    if loader is None:  # pgvector fallback 後端未實作 → 用 stub
        return []
    try:
        results.extend(loader(periods=BM25_CORPUS_PERIODS))
    except Exception:  # noqa: BLE001 — 載入失敗不可中斷檢索，退回 stub（記 warning）
        logger.warning(
            "BM25 real corpus load failed; falling back to stub corpus", exc_info=True
        )
        return []

    fin_loader = getattr(store, "load_financial_corpus", None)
    if fin_loader is not None:
        try:
            results.extend(fin_loader())
        except Exception:  # noqa: BLE001 — 財務語料失敗不中斷，僅記 warning
            logger.warning(
                "Financial metrics corpus load failed; BM25 will lack structured metrics",
                exc_info=True,
            )

    return results


@functools.lru_cache(maxsize=1)
def _cached_real_corpus() -> tuple[SearchResult, ...]:
    """整個 process 只讀一次（issue #30：每次 app 重啟載入一次，非 polling）。"""
    return tuple(_load_real_corpus())


def active_bm25_corpus() -> list[SearchResult]:
    """有憑證 → 真實 polaris_core 語料（快取一次）；否則 / 載入失敗 → stub。"""
    from polaris.llm.gemini import available

    if not available():
        return list(_FALLBACK_CORPUS)
    real = _cached_real_corpus()
    return list(real) if real else list(_FALLBACK_CORPUS)


def _token_list(text: str) -> list[str]:
    """Tokenize mixed Chinese/English finance text for deterministic BM25.

    The CJK branch adds short n-grams so queries like ``毛利率`` still match
    longer chunks such as ``毛利率受到匯率影響``.
    """
    tokens: list[str] = []
    for match in re.findall(r"[A-Za-z0-9]+|[\u4e00-\u9fff]+", text.lower()):
        if re.fullmatch(r"[\u4e00-\u9fff]+", match):
            if len(match) <= 4:
                tokens.append(match)
            for size in (2, 3):
                tokens.extend(match[i : i + size] for i in range(len(match) - size + 1))
        else:
            tokens.append(match)
    return tokens


def _matches_filters(result: SearchResult, filters: dict | None) -> bool:
    if not filters:
        return True
    for key, value in filters.items():
        if value is None:
            continue
        if key == "company" and result.company != value:
            return False
        if key == "period" and result.period != value:
            return False
        if key == "doc_type" and result.metadata.get("doc_type") != value:
            # 法說題只取 transcript（修 R6：問法說會卻抓到新聞/重大訊息）。與 store
            # 的 doc_type SQL 過濾一致；stub 語料無 doc_type → 設此過濾時自然被排除。
            return False
        if key == "viewer":
            # Owner-based access control (issue #32): public docs (owner=None) are always
            # visible; owner-scoped docs only visible to the matching principal.  This must
            # agree with the store SQL filter (bigquery/pgvector) — both gate on owner AND
            # confidential, so a confidential doc never leaks via the BM25 path either.
            owner = result.metadata.get("owner")
            if owner is not None and owner != value:
                return False
            if result.metadata.get("confidential") and owner != value:
                return False
    return True


def _copy_result(result: SearchResult, *, score: float, origin: str) -> SearchResult:
    metadata = dict(result.metadata)
    metadata["origin"] = origin
    metadata["retrieval_channels"] = [origin]
    return SearchResult(
        id=result.id,
        content=result.content,
        score=score,
        company=result.company,
        period=result.period,
        metadata=metadata,
    )


def _normalize_vector_result(result: SearchResult) -> SearchResult:
    metadata = dict(result.metadata)
    metadata["origin"] = "vector"
    metadata["retrieval_channels"] = ["vector"]
    return SearchResult(
        id=result.id,
        content=result.content,
        score=float(result.score),
        company=result.company,
        period=result.period,
        metadata=metadata,
    )


# Citation-facing metadata keys that downstream adapters (api.py /research,
# Deep Research SearchResult→Citation) read off SearchResult.metadata. The
# vector (BigQuery) path already populates them; BM25/stub results don't — so
# the final output is normalised to always carry the keys, letting consumers do
# metadata["published_at"] safely on any channel (issue: R7 /research KeyError).
_CITATION_METADATA_KEYS = (
    "doc_type",
    "published_at",
    "fiscal_period",
    # P1：v_chunk_semantic 三欄（store 端以 chunk_id JOIN 取得）；BM25/stub 通道無值
    # → 補 None（不編造），讓下游 /ask citation 在任何通道都能安全讀到這三鍵。
    "event_key",
    "source_key",
    "published_yyyymm",
)


def _ensure_citation_metadata(result: SearchResult) -> SearchResult:
    missing = [k for k in _CITATION_METADATA_KEYS if k not in result.metadata]
    if not missing:
        return result
    metadata = dict(result.metadata)
    for key in missing:
        # fiscal_period mirrors the typed period field; others default to None.
        metadata[key] = result.period if key == "fiscal_period" else None
    return SearchResult(
        id=result.id,
        content=result.content,
        score=result.score,
        company=result.company,
        period=result.period,
        metadata=metadata,
    )


def _strip_leading_fragment(text: str) -> str:
    """讀取時止血（issue #50 存量）：去掉 chunk 開頭的半截英文字。

    舊切塊器 / 逐字稿 ingester 以固定字元數硬切，chunk 常起於單字中間（如
    'rnover days...'，原為 'turnover'），碎字會洩進 LLM 答案與 citation
    snippet。chunk 起頭若是 **小寫 ASCII 字母** 視為被切斷的殘字 → 丟掉第一個
    以空白分隔的 token。大寫（真句首）、CJK、數字開頭皆視為正常邊界、不動。
    只有一個 token（切了會清空）時保留原文，避免 content 變空。

    注意：只清理「呈現給使用者 / LLM 的文字」，不改 store；既有 embedding 仍是
    用碎字算的（向量層雜訊需 re-embed 才會根治，見 issue #50）。
    """
    stripped = text.lstrip()
    if not stripped or not (stripped[0].isascii() and stripped[0].islower()):
        return text
    parts = stripped.split(None, 1)
    return parts[1] if len(parts) == 2 else text


def _trim_result_content(result: SearchResult) -> SearchResult:
    """回傳 content 經 :func:`_strip_leading_fragment` 修剪後的新 SearchResult。"""
    trimmed = _strip_leading_fragment(result.content)
    if trimmed == result.content:
        return result
    return SearchResult(
        id=result.id,
        content=trimmed,
        score=result.score,
        company=result.company,
        period=result.period,
        metadata=result.metadata,
    )


def _cohere_rerank(query: str, results: list[SearchResult], top_k: int) -> list[SearchResult]:
    """Default Cohere rerank implementation using ``COHERE_API_KEY`` from env.

    Falls back gracefully if the key is absent or the Cohere call fails —
    caller receives ``results`` unchanged and BM25+vector ordering holds.
    """
    import os

    from polaris.config import _split_keys
    from polaris.retry import is_quota_error

    # 逗號分隔多把金鑰（單把無逗號 = 1 元素，向後相容）；429 配額耗盡輪下一把。
    api_keys = _split_keys(os.environ.get("COHERE_API_KEY", ""))
    if not api_keys:
        logger.debug("COHERE_API_KEY not set; skipping rerank, keeping BM25+vector order")
        return results
    # `rerank-v3.5` 為 Cohere 多語 rerank 文件型號（適合中英財報），可用
    # COHERE_RERANK_MODEL 覆寫。注意：需「有效」金鑰；型號錯或 key 失效會走下方
    # except 降級成 BM25+vector（不阻斷檢索）。
    model = os.environ.get("COHERE_RERANK_MODEL", "rerank-v3.5")
    try:
        import cohere  # type: ignore[import-untyped]

        docs = [r.content for r in results]
        # v2 rerank API 走 ClientV2 + client.rerank（舊 v1 `Client` 無 .rerank v2 契約）。
        response = None
        for idx, api_key in enumerate(api_keys):
            try:
                response = cohere.ClientV2(api_key=api_key).rerank(
                    model=model,
                    query=query,
                    documents=docs,
                    top_n=top_k,
                )
                break
            except Exception as exc:  # noqa: BLE001 — 429 輪下一把，其餘照拋給外層 except
                if is_quota_error(exc) and idx < len(api_keys) - 1:
                    logger.debug("Cohere 429 quota on key #%d; rotating to next", idx + 1)
                    continue
                raise
        reranked: list[SearchResult] = []
        for hit in response.results:
            original = results[hit.index]
            metadata = dict(original.metadata)
            metadata["origin"] = "rerank"
            metadata["retrieval_channels"] = list(
                metadata.get("retrieval_channels", [original.metadata.get("origin", "unknown")])
            )
            if "rerank" not in metadata["retrieval_channels"]:
                metadata["retrieval_channels"].append("rerank")
            reranked.append(
                SearchResult(
                    id=original.id,
                    content=original.content,
                    score=float(hit.relevance_score),
                    company=original.company,
                    period=original.period,
                    metadata=metadata,
                )
            )
        return reranked
    except Exception:  # noqa: BLE001 - rerank is optional; BM25+vector result stands
        logger.warning("Cohere rerank failed; falling back to BM25+vector order", exc_info=True)
        return results


# --- Recency-aware reorder (issue #49) -------------------------------------
# 「最新一季 / 近期」類查詢，舊期別的強相關塊常壓過最新期別。資料本就帶
# period / published_at，這裡在截斷 top_k 前依時間意圖做「有界」recency 加權：
# 只在偵測到時間意圖時啟用，且加權上限 = 候選最高分 × RECENCY_WEIGHT，足以
# 翻轉近似分數、但不足以把強相關舊文壓到不相關的新文之下（降級安全）。
_RECENCY_TERMS = (
    "最新", "最近", "近期", "近一季", "近兩季", "近幾季", "本季", "這季", "當季",
    "latest", "most recent", "recent", "current quarter", "this quarter",
)
_PERIOD_RE = re.compile(r"(\d{4})\s*[Qq]([1-4])")
_DATE_RE = re.compile(r"(\d{4})-(\d{2})")
# 加權係數：newest 候選最多 +RECENCY_WEIGHT×max_score。0.5 → 可翻轉 ≲50%
# 分數差的近似排名，不會把 2× 強的舊文壓下去。
RECENCY_WEIGHT = 0.5


def _wants_recency(query: str) -> bool:
    """查詢是否表達『偏好最新期別』的時間意圖（中英關鍵詞）。"""
    q = (query or "").lower()
    return any(term in q for term in _RECENCY_TERMS)


def _recency_ordinal(result: SearchResult) -> float | None:
    """把 period / published_at 換算成可比較的『年』浮點（2024Q3 → 2024.5）。
    period 優先，缺則用 published_at / fiscal_period；都缺回 None（不參與加權）。"""
    period = result.period or ""
    m = _PERIOD_RE.search(period)
    if m:
        return int(m.group(1)) + (int(m.group(2)) - 1) / 4
    pub = str(result.metadata.get("published_at") or "")
    m = _DATE_RE.search(pub)
    if m:
        return int(m.group(1)) + (int(m.group(2)) - 1) / 12
    fp = str(result.metadata.get("fiscal_period") or "")
    m = _PERIOD_RE.search(fp)
    if m:
        return int(m.group(1)) + (int(m.group(2)) - 1) / 4
    return None


def _boost_recency(results: list[SearchResult]) -> list[SearchResult]:
    """對帶時間意圖的查詢，依 recency 線性加分（上限 max_score×RECENCY_WEIGHT）。
    時間資訊不足以區分（<2 個相異期別）時原樣返回，不動排序。"""
    ordinals = [_recency_ordinal(r) for r in results]
    present = [o for o in ordinals if o is not None]
    if len(set(present)) < 2:
        return results
    lo, hi = min(present), max(present)
    max_score = max((r.score for r in results), default=0.0)
    boosted: list[SearchResult] = []
    for result, ordinal in zip(results, ordinals, strict=True):
        if ordinal is None:
            boosted.append(result)
            continue
        fraction = (ordinal - lo) / (hi - lo)
        boosted.append(SearchResult(
            id=result.id,
            content=result.content,
            score=result.score + fraction * max_score * RECENCY_WEIGHT,
            company=result.company,
            period=result.period,
            metadata=result.metadata,
        ))
    return boosted


def _merge_results(results: list[SearchResult]) -> list[SearchResult]:
    merged: dict[str, SearchResult] = {}
    for result in results:
        existing = merged.get(result.id)
        if existing is None:
            merged[result.id] = result
            continue

        channels = list(existing.metadata.get("retrieval_channels", []))
        for channel in result.metadata.get("retrieval_channels", []):
            if channel not in channels:
                channels.append(channel)

        winner = result if result.score > existing.score else existing
        metadata: dict[str, Any] = dict(winner.metadata)
        metadata["retrieval_channels"] = channels
        merged[result.id] = SearchResult(
            id=winner.id,
            content=winner.content,
            score=winner.score,
            company=winner.company,
            period=winner.period,
            metadata=metadata,
        )
    return list(merged.values())


@dataclass
class HybridRetriever:
    top_k: int = 8
    store: VectorStore | None = None
    embedding_fn: EmbeddingFn | None = None
    # Cohere Rerank (3rd path, opt-in): inject a fake for tests; None = use
    # _cohere_rerank which reads COHERE_API_KEY and skips gracefully if absent.
    rerank_fn: RerankFn | None = field(default=None, repr=False)
    # BM25 語料（issue #30）：None = 依憑證自動載入真實 polaris_core 語料（CI 無金鑰
    # → stub）；測試可注入確定性語料。
    bm25_corpus: list[SearchResult] | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self.store is None:
            self.store = get_vector_store()
        # Auto-wire the real query-embedding fn when a Gemini key is present so the
        # vector channel actually runs (CI / no key → stays None → BM25-only).
        # This is what connects every HybridRetriever consumer — the 5-node node
        # AND Deep Research's active_search_fn — to real polaris_core vectors.
        if self.embedding_fn is None:
            self.embedding_fn = active_embedding_fn()
        if self.bm25_corpus is None:
            self.bm25_corpus = active_bm25_corpus()

    def _bm25_search(self, query: str, filters: dict | None) -> list[SearchResult]:
        candidates = [item for item in (self.bm25_corpus or []) if _matches_filters(item, filters)]
        query_tokens = _token_list(query)
        if not candidates or not query_tokens:
            return []

        corpus_tokens = [
            _token_list(f"{item.id} {item.company or ''} {item.period or ''} {item.content}")
            for item in candidates
        ]
        bm25 = BM25Okapi(corpus_tokens)
        bm25_scores = list(bm25.get_scores(query_tokens))
        raw_scores: list[float] = []
        for item_tokens, bm25_score in zip(corpus_tokens, bm25_scores, strict=True):
            overlap_score = len(set(query_tokens) & set(item_tokens)) / max(len(query_tokens), 1)
            raw_scores.append(float(bm25_score) if bm25_score > 0 else overlap_score)

        max_score = max(raw_scores) if raw_scores else 0.0

        ranked: list[SearchResult] = []
        for item, score in zip(candidates, raw_scores, strict=True):
            if score <= 0:
                continue
            normalized_score = (score / max_score) * 0.5 if max_score else 0.0
            ranked.append(_copy_result(item, score=normalized_score, origin="bm25"))
        return ranked

    def _vector_search(
        self,
        query: str,
        filters: dict | None,
        *,
        top_k: int | None = None,
    ) -> list[SearchResult]:
        if self.embedding_fn is None or self.store is None:
            return []
        try:
            query_embedding = self.embedding_fn(query)
            if not query_embedding:
                return []
            results = self.store.search(query_embedding, top_k or self.top_k, filters=filters)
        except Exception:  # noqa: BLE001 - vector backend is optional; BM25 stays available
            # P0：別吞錯 —— 記 warning（含 traceback）讓向量後端失敗看得見，但仍回 []
            # 讓 BM25 fallback 撐住這次查詢（檢索不中斷、行為不退步）。
            logger.warning(
                "vector search failed; falling back to BM25-only for this query",
                exc_info=True,
            )
            return []
        return [_normalize_vector_result(result) for result in results]

    def retrieve_candidates(
        self,
        query: str,
        *,
        filters: dict | None = None,
        top_k: int | None = None,
    ) -> list[SearchResult]:
        """Return merged BM25/vector candidates without running the reranker."""
        query = (query or "").strip()
        if not query:
            return []

        limit = top_k or self.top_k
        ranked = _merge_results([
            *self._bm25_search(query, filters),
            *self._vector_search(query, filters, top_k=limit),
        ])
        # 時間意圖（「最新一季 / 近期」）→ 在截斷 top_k 前做有界 recency 加權，
        # 避免最新期別被舊期別的強相關塊擠出候選（issue #49）。
        if _wants_recency(query):
            ranked = _boost_recency(ranked)
        ranked.sort(key=lambda r: r.score, reverse=True)
        return [_ensure_citation_metadata(r) for r in ranked[:limit]]

    def retrieve(self, query: str, *, filters: dict | None = None) -> list[SearchResult]:
        """3-path retrieval: BM25 keyword + optional vector + optional Cohere Rerank.

        Vector and Rerank are opt-in (no API quota spent in CI/local dev by default).
        Rerank uses ``rerank_fn`` if set, otherwise falls back to ``_cohere_rerank``
        which reads ``COHERE_API_KEY`` and skips gracefully when absent.
        """
        candidates = self.retrieve_candidates(query, filters=filters)
        if not candidates:
            return []

        reranker = self.rerank_fn if self.rerank_fn is not None else _cohere_rerank
        candidates = reranker(query.strip(), candidates, self.top_k)[: self.top_k]
        # Every result must carry the citation-facing metadata keys so downstream
        # adapters (api.py /research, Deep Research) can read metadata["doc_type"/
        # "published_at"] safely regardless of channel (incl. BM25/stub fallback).
        # _trim_result_content 去掉既有 chunk 開頭的半截英文字（issue #50 存量止血，
        # 不改 store）。
        return [_ensure_citation_metadata(_trim_result_content(r)) for r in candidates]


# ---------------------------------------------------------------------------
# Deep Research search-fn bridge (SearchResult → Citation adapter)
# ---------------------------------------------------------------------------

def make_retriever_search_fn(
    retriever: "HybridRetriever | None" = None,
    *,
    viewer: str = PUBLIC_VIEWER,
    filters: dict | None = None,
) -> "Callable[[str], list]":
    """Return a ``SearchFn``-compatible callable backed by :class:`HybridRetriever`.

    Adapts ``SearchResult → Citation`` so the result can be consumed by
    :func:`~polaris.graph.deep_research.agent.run_deep_research`.

    Viewer and any extra filters are merged and forwarded to
    ``retriever.retrieve(..., filters={viewer: ..., ...})`` — the store enforces
    owner-based access control (issue #32).

    ``retriever`` is injected for tests; ``None`` uses the default
    :class:`HybridRetriever` (BM25 + store from ``VECTOR_BACKEND`` env).
    """
    from polaris.graph.state import Citation

    r = retriever if retriever is not None else HybridRetriever()
    combined_filters: dict = {**(filters or {}), "viewer": viewer}

    def _search(query: str) -> list:
        return [_result_to_citation(sr, Citation) for sr in r.retrieve(query, filters=combined_filters)]

    return _search


RESEARCH_DOC_TYPE_QUOTAS: Mapping[str, int] = {
    "transcript": 5,
    # 法說家族第二來源：台股多數公司不提供逐字稿，但全 20 家都有法說簡報
    # （presentation，文字版已入 chunks）。少了它，無逐字稿的公司其法說內容會被整個
    # 漏掉——逐字稿目前僅 4/20 家入庫（2317/2330/2454/3034）。
    "presentation": 4,
    "major_news": 5,
    "news": 3,
}


def _result_to_citation(sr: SearchResult, citation_cls):
    raw_origin = sr.metadata.get("origin")
    allowed_origins = {"stub", "bm25", "embedding", "colpali", "rerank", "news", "vision"}
    if raw_origin == "vector":
        origin = "embedding"
    else:
        origin = raw_origin if raw_origin in allowed_origins else "bm25"
    return citation_cls(
        source_id=sr.id,
        snippet=sr.content,
        origin=origin,
        company=company_name(sr.company),
        ticker=sr.company,
        event_key=sr.metadata.get("event_key"),
        source_key=sr.metadata.get("source_key"),
        published_yyyymm=sr.metadata.get("published_yyyymm"),
        doc_type=sr.metadata.get("doc_type"),
        fiscal_period=sr.metadata.get("fiscal_period") or sr.period,
        page_num=sr.metadata.get("page_num"),
        source_file=sr.metadata.get("source_file"),
        published_at=sr.metadata.get("published_at"),
    )


def make_research_search_fn(
    retriever: "HybridRetriever | None" = None,
    *,
    viewer: str = PUBLIC_VIEWER,
    filters: dict | None = None,
    doc_type_quotas: Mapping[str, int] = RESEARCH_DOC_TYPE_QUOTAS,
) -> "Callable[[str], list]":
    """Build Deep Research search with per-source quotas and one final rerank."""
    from polaris.graph.state import Citation

    r = retriever if retriever is not None else HybridRetriever()
    common_filters = {**(filters or {}), "viewer": viewer}

    def _search(query: str) -> list:
        candidates: list[SearchResult] = []
        for doc_type, quota in doc_type_quotas.items():
            source_filters = {"doc_type": doc_type, **common_filters}
            candidates.extend(
                r.retrieve_candidates(query, filters=source_filters, top_k=quota)
            )

        merged = _merge_results(candidates)
        if not merged and r.embedding_fn is None:
            # Token-free CI has no canonical chunks and uses the built-in corpus.
            return make_retriever_search_fn(r, viewer=viewer, filters=filters)(query)

        reranker = r.rerank_fn if r.rerank_fn is not None else _cohere_rerank
        ranked = reranker(query, merged, r.top_k)[: r.top_k]
        return [_result_to_citation(_ensure_citation_metadata(sr), Citation) for sr in ranked]

    return _search


def active_retriever() -> "HybridRetriever | None":
    """Real :class:`HybridRetriever` (vector channel auto-enabled via
    :func:`active_embedding_fn`) when a Gemini key is available, else None so the
    5-node ``retriever`` node falls back to its deterministic stub corpus.

    Mirrors :func:`~polaris.llm.gemini.active_llm`.
    """
    from polaris.llm.gemini import available

    return HybridRetriever() if available() else None


def active_search_fn(viewer: str = PUBLIC_VIEWER) -> "Callable[[str], list]":
    """Active search fn for Deep Research: BM25 + vector + Cohere Rerank.

    Mirrors :func:`~polaris.llm.gemini.active_llm` and
    :func:`~polaris.compression.compressors.active_compressor`:

    - CI / no credentials: BM25-only from fallback corpus, fully deterministic
    - Production: BM25 + vector (``VECTOR_BACKEND``) + Cohere Rerank if key set
    - viewer forwarded to store for owner-scoped filtering (issue #32)
    """
    return make_research_search_fn(viewer=viewer)
