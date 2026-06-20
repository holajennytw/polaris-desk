# ColPali 第 4 路檢索（Phase 1）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把既有 `polaris_core.colpali_pages`（5701 頁、128 維池化向量）接成第 4 路視覺檢索（gated、場景 3、`origin="colpali"`），Phase 1 只做「檢索 + 命中率自檢」，不做回答。

**Architecture:** 新增 `BigQueryColpaliStore`（只讀 `colpali_pages`，128 維 cosine `VECTOR_SEARCH`）與 `ColpaliRetriever`（把 query 經注入的 `encode_query` 編成 128 維 → 查表 → 回 `SearchResult`，`origin="colpali"`）。query encoder 是**唯一外部相依**（待 issue #133 由 R4 提供），全程以注入點處理：缺席時優雅 skip（CI 0 外呼），到位時一行接上。**零資料架構變更**（只讀既有表）。

**Tech Stack:** Python 3.13、Google BigQuery `VECTOR_SEARCH`、pytest（注入 fake client，沿用 `tests/test_vectorstore_impl.py` 套路）。

---

## 前置事實（已查證，實作者必讀）

- 表 `polaris-desk-team.polaris_core.colpali_pages` schema：`page_id, ticker, fiscal_period, doc_type, source_file, page_num, event_date, published_at, embedding(REPEATED FLOAT, len=128), n_patches, fetched_at, event_key, source_key, published_year, published_month, published_yyyymm`。
- **無 `owner`/`confidential` 欄** → 此表**不做** viewer ACL filter（與 `chunks` 不同）。
- `embedding` 是**單一 128 維**（已池化），故用一般 cosine `VECTOR_SEARCH`，非多向量 MaxSim。
- 既有型別/集合**已含 `"colpali"`**：`CitationOrigin`（`src/polaris/graph/state.py:23`）、`_CITATION_ORIGINS`（`stubs.py:78`、`retriever.py:384`）、`_citation_origin`（`retriever.py:386` 把未知映 `bm25`，但 `colpali` 在集合內會原樣保留）→ **無需改動這些**。
- Settings 欄位：`settings.gcp_project`（預設 `polaris-desk-team`）、`settings.bq_dataset`（預設 `polaris_core`）、`settings.top_k`（預設 8）。
- BigQuery client 注入套路：`BigQueryStore.__init__(settings, *, client=None)`、`_get_client()`、`_run_query(sql, params)`、`_build_job_config(params)`（fake client 回 None 即可）。

## File Structure

- **Create** `src/polaris/vectorstore/colpali_store.py` — `BigQueryColpaliStore`：只讀 `colpali_pages` 的 128 維 cosine 檢索，回 `SearchResult`（`origin="colpali"`）。
- **Create** `tests/test_colpali_store.py` — 注入 FakeBQClient，驗 SQL 形狀 / 參數 / 結果對映 / origin。
- **Create** `src/polaris/retrieval/colpali_retriever.py` — `ColpaliRetriever`（注入 `encode_query`）+ `active_colpali_retriever()`（encoder 缺席回 None）。
- **Create** `tests/test_colpali_retriever.py` — stub encoder + fake store，驗檢索與 skip 語意。
- **Modify** `src/polaris/eval/runner.py:36-66` — `_run_visual` 改用 `active_colpali_retriever()`；缺席時拋更新後的 NotImplementedError（指向 #133，非「W3」）。
- **Modify** `tests/test_eval_pipeline.py:86-91` — 場景 3：無 encoder 仍拋（更新 match 字串）；新增「注入 stub retriever → 回 colpali contexts」案例。
- **Create** `scripts/colpali_roundtrip_check.py` — Phase 1 驗收工具：給真 `encode_query` + live 表，跑已知頁 round-trip，報命中率（import-safe，無 encoder/憑證時印提示不炸）。

---

## Task 1: `BigQueryColpaliStore`（只讀 colpali_pages 的 128 維 cosine 檢索）

**Files:**
- Create: `src/polaris/vectorstore/colpali_store.py`
- Test: `tests/test_colpali_store.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_colpali_store.py
"""BigQueryColpaliStore 測試：注入 fake client，0 GCP 外呼。

驗 VECTOR_SEARCH(COSINE) 於 colpali_pages、filter 對映、結果→SearchResult、origin=colpali。
"""
from __future__ import annotations

from polaris.config import Settings
from polaris.vectorstore.colpali_store import BigQueryColpaliStore

QE = [0.1] * 8  # 測試用短向量（真環境 128，由 schema 守）


def make_settings(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


class FakeBQJob:
    def __init__(self, rows=None):
        self._rows = rows or []

    def result(self):
        return self._rows


class FakeBQClient:
    def __init__(self, rows=None):
        self.queries: list[str] = []
        self._rows = rows or []

    def query(self, sql, job_config=None):
        self.queries.append(sql)
        return FakeBQJob(self._rows)


def _row():
    return {
        "page_id": "pg-2330-2025Q3-9",
        "ticker": "2330",
        "fiscal_period": "2025Q3",
        "doc_type": "presentation",
        "source_file": "2330_..._presentation.pdf",
        "page_num": 9,
        "published_at": "2025-10-16",
        "distance": 0.25,
    }


def test_search_emits_vector_search_cosine_on_colpali_pages():
    client = FakeBQClient(rows=[_row()])
    store = BigQueryColpaliStore(make_settings(), client=client)
    store.search(QE, top_k=5)
    sql = client.queries[0]
    assert "VECTOR_SEARCH" in sql
    assert "colpali_pages" in sql
    assert "COSINE" in sql


def test_search_maps_row_to_searchresult_with_colpali_origin():
    client = FakeBQClient(rows=[_row()])
    store = BigQueryColpaliStore(make_settings(), client=client)
    [res] = store.search(QE, top_k=5)
    assert res.id == "pg-2330-2025Q3-9"
    assert res.company == "2330"
    assert res.period == "2025Q3"
    assert res.metadata["origin"] == "colpali"
    assert res.metadata["page_num"] == 9
    assert res.metadata["source_file"].endswith(".pdf")
    # 無文字層 → snippet 用可讀的頁參照，含頁碼供接地
    assert "9" in res.content and "2330" in res.content
    # cosine 距離 → 相似度（越大越像）
    assert abs(res.score - 0.75) < 1e-9


def test_search_filters_by_company_and_period_only_no_viewer():
    client = FakeBQClient(rows=[])
    store = BigQueryColpaliStore(make_settings(), client=client)
    store.search(QE, top_k=5, filters={"company": "2330", "period": "2025Q3", "viewer": "someone"})
    sql = client.queries[0]
    assert "ticker = @ticker" in sql
    assert "fiscal_period = @fiscal_period" in sql
    # colpali_pages 無 owner 欄 → 不得出現 viewer/owner 過濾
    assert "owner" not in sql and "viewer" not in sql
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_colpali_store.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'polaris.vectorstore.colpali_store'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/polaris/vectorstore/colpali_store.py
"""第 4 路視覺檢索的雲端後端：只讀 polaris_core.colpali_pages（128 維 cosine）。

- ColPali 頁向量已由 R4 入庫（5701 頁，patch 池化成單一 128 維）；本類別只**讀**。
- 無 owner/confidential 欄 → 不做 viewer ACL filter（與 chunks 不同）。
- 表內無文字層 → SearchResult.content 用可讀頁參照（含頁碼）供引用接地。
- client 注入式 seam（同 BigQueryStore）：測試注入 fake client → 0 GCP 外呼。
"""
from __future__ import annotations

from typing import Any

from .base import SearchResult

#: 介面 filter 鍵 → colpali_pages 欄名（無 viewer：此表無 owner 欄）。
_FILTER_COLUMNS = {
    "company": "ticker",
    "period": "fiscal_period",
    "doc_type": "doc_type",
}


class BigQueryColpaliStore:
    """colpali_pages 的 128 維 cosine 檢索（只讀）。"""

    def __init__(self, settings, *, client=None) -> None:
        self.settings = settings
        self._client = client

    def _get_client(self):
        if self._client is None:
            from google.cloud import bigquery
            self._client = bigquery.Client(project=self.settings.gcp_project)
        return self._client

    @property
    def _table(self) -> str:
        return f"{self.settings.gcp_project}.{self.settings.bq_dataset}.colpali_pages"

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 8,
        *,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        params: dict[str, Any] = {"qe": query_embedding, "k": top_k}
        clauses = []
        for key, column in _FILTER_COLUMNS.items():
            if filters and filters.get(key) is not None:
                clauses.append(f"{column} = @{column}")
                params[column] = filters[key]
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

        sql = f"""
        SELECT base.page_id, base.ticker, base.fiscal_period, base.doc_type,
               base.source_file, base.page_num, base.published_at, distance
        FROM VECTOR_SEARCH(
            (SELECT * FROM `{self._table}` {where}),
            'embedding',
            (SELECT @qe AS embedding),
            top_k => @k,
            distance_type => 'COSINE'
        )
        ORDER BY distance
        """
        rows = self._run_query(sql, params)
        return [self._to_result(row) for row in rows]

    @staticmethod
    def _to_result(row: dict) -> SearchResult:
        ticker = row.get("ticker")
        period = row.get("fiscal_period")
        page_num = row.get("page_num")
        source_file = row.get("source_file")
        # 無文字層 → 可讀頁參照當 snippet（接地要頁碼）
        content = f"{ticker} {period} 第 {page_num} 頁圖表（{source_file}）"
        published = row.get("published_at")
        return SearchResult(
            id=row["page_id"],
            content=content,
            score=1.0 - float(row["distance"]),
            company=ticker,
            period=period,
            metadata={
                "origin": "colpali",
                "retrieval_channels": ["colpali"],
                "page_num": page_num,
                "source_file": source_file,
                "doc_type": row.get("doc_type"),
                "published_at": (
                    published.isoformat() if hasattr(published, "isoformat") else published
                ),
            },
        )

    def _run_query(self, sql: str, params: dict[str, Any]) -> list[dict]:
        client = self._get_client()
        job_config = self._build_job_config(params)
        return [dict(row) for row in client.query(sql, job_config=job_config).result()]

    @staticmethod
    def _build_job_config(params: dict[str, Any]):
        try:
            from google.cloud import bigquery
        except ImportError:
            return None
        qp = []
        for name, value in params.items():
            if isinstance(value, list):
                qp.append(bigquery.ArrayQueryParameter(name, "FLOAT64", value))
            elif isinstance(value, int):
                qp.append(bigquery.ScalarQueryParameter(name, "INT64", value))
            else:
                qp.append(bigquery.ScalarQueryParameter(name, "STRING", value))
        return bigquery.QueryJobConfig(query_parameters=qp)

    def health_check(self) -> bool:
        try:
            self._get_client().query("SELECT 1").result()
        except Exception:  # noqa: BLE001
            return False
        return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_colpali_store.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: Commit**

```bash
git add src/polaris/vectorstore/colpali_store.py tests/test_colpali_store.py
git commit -m "feat(retrieval): BigQueryColpaliStore — read-only 128-dim cosine over colpali_pages"
```

---

## Task 2: `ColpaliRetriever`（注入 encode_query；encoder 缺席優雅 skip）

**Files:**
- Create: `src/polaris/retrieval/colpali_retriever.py`
- Test: `tests/test_colpali_retriever.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_colpali_retriever.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_colpali_retriever.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'polaris.retrieval.colpali_retriever'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/polaris/retrieval/colpali_retriever.py
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
    return ColpaliRetriever(encode_query=fn, store=BigQueryColpaliStore(settings), top_k=settings.top_k)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_colpali_retriever.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: Commit**

```bash
git add src/polaris/retrieval/colpali_retriever.py tests/test_colpali_retriever.py
git commit -m "feat(retrieval): ColpaliRetriever (gated) with injectable query encoder (#133 seam)"
```

---

## Task 3: eval 場景 3 改接 ColPali（缺 encoder 仍誠實拋錯，指向 #133）

**Files:**
- Modify: `src/polaris/eval/runner.py:36-66`
- Test: `tests/test_eval_pipeline.py:86-91`

- [ ] **Step 1: Write the failing test**（更新場景 3 既有測試 + 新增 stub 注入案例）

```python
# tests/test_eval_pipeline.py — 取代既有 test（約 :86-91）的場景 3 區塊
def test_scenario3_raises_until_colpali_encoder_wired():
    """場景 3（圖表 ColPali）：query encoder（#133）未接前明確拋錯，不靜默走文字。"""
    from polaris.eval.runner import _run_visual
    import pytest
    with pytest.raises(NotImplementedError, match="#133"):
        _run_visual("台積電 2025Q3 毛利率走勢圖")


def test_scenario3_runs_colpali_when_retriever_injected(monkeypatch):
    """encoder 到位（注入 stub retriever）→ 回 colpali contexts。"""
    from polaris.eval import runner
    from polaris.vectorstore.base import SearchResult

    class StubRetriever:
        def retrieve(self, query, *, filters=None):
            return [SearchResult(
                id="pg-1", content="2330 2025Q3 第 9 頁圖表（x.pdf）", score=0.9,
                company="2330", period="2025Q3", metadata={"origin": "colpali", "page_num": 9},
            )]

    monkeypatch.setattr(runner, "active_colpali_retriever", lambda: StubRetriever())
    result = runner._run_visual("台積電 2025Q3 毛利率走勢圖")
    assert result["contexts"][0]["text"].endswith("（x.pdf）")
    assert result["citations"][0].origin == "colpali"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_eval_pipeline.py -k scenario3 -v`
Expected: FAIL（舊 `_run_visual` match "ColPali" 不含 "#133"；且 `active_colpali_retriever` 未在 runner 匯入）

- [ ] **Step 3: Modify `runner.py`**（取代 `_run_visual` 與相關 import/註解）

```python
# src/polaris/eval/runner.py — 頂部 import 區加：
from polaris.retrieval.colpali_retriever import active_colpali_retriever

# 取代既有 _run_visual（連同過時的「W3 排程」docstring）：
def _run_visual(question: str) -> dict:
    """場景 3（圖表題）走第 4 路 ColPali 視覺檢索（gated）。

    依賴 R4 的 query encoder（issue #133）。未接前 active_colpali_retriever() 回 None，
    這裡**刻意拋錯**而非靜默退回文字 workflow——看圖題用文字代跑會把「視覺路沒接」
    誤報成「檢索失敗」，違反誠實原則。encoder 到位後本函式自動走真檢索，分派不用動。
    """
    from polaris.graph.state import Citation
    from polaris.ontology import company_name

    retriever = active_colpali_retriever()
    if retriever is None:
        raise NotImplementedError(
            "場景 3（圖表 ColPali）query encoder 尚未接（見 issue #133）；"
            "在 ColPali 查詢端編碼落地前不得用文字 workflow 代跑看圖題。"
        )
    results = retriever.retrieve(question)
    citations = [
        Citation(
            source_id=r.id,
            snippet=r.content,
            origin="colpali",
            company=company_name(r.company),
        )
        for r in results
    ]
    return {
        "answer": "",  # Phase 1 只檢索；讀數字回答見 Phase 2
        "contexts": [{"text": r.content} for r in results],
        "citations": citations,
        "compliance_status": "n/a",
    }
```

並更新 `_DISPATCH` 上方註解：`"3": _run_visual,  # 圖表 ColPali（第 4 路，gated，依賴 #133）`。

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_eval_pipeline.py -k scenario3 -v`
Expected: PASS（2 passed）

- [ ] **Step 5: Commit**

```bash
git add src/polaris/eval/runner.py tests/test_eval_pipeline.py
git commit -m "feat(eval): route scenario 3 to ColPali retriever; raise pointing to #133 until encoder wired"
```

---

## Task 4: round-trip 命中率自檢工具（Phase 1 驗收）

**Files:**
- Create: `scripts/colpali_roundtrip_check.py`

> 此工具需「真 encode_query（#133 到位）+ live BigQuery 憑證」才有意義，故為 script 非 CI test。
> 必須 import-safe：缺 encoder/憑證時印提示並 return，不拋。

- [ ] **Step 1: Write the script**

```python
# scripts/colpali_roundtrip_check.py
"""Phase 1 驗收：ColPali 第 4 路 round-trip 命中率自檢。

對 N 個已知頁下對應 query，期望該 page_id 進 top-k。命中率 ≥70%（TD-01 門檻）= 對齊成功。
需要：#133 的 query encoder 已接（active_colpali_query_fn 回非 None）+ live BigQuery 憑證。

用法：uv run python scripts/colpali_roundtrip_check.py
"""
from __future__ import annotations

# (query 文字, 期望命中的 page_id) — 待 R4 在 #133 附 gold 樣本後填入；
# 暫以「該頁所屬 ticker+fiscal_period 的概念查詢」佔位，實跑前替換為真 gold。
GOLD: list[tuple[str, str]] = [
    # ("台積電 2025Q3 毛利率", "pg-2330-2025Q3-9"),
]


def main() -> None:
    from polaris.config import settings
    from polaris.retrieval.colpali_retriever import active_colpali_query_fn
    from polaris.vectorstore.colpali_store import BigQueryColpaliStore

    fn = active_colpali_query_fn()
    if fn is None:
        print("⏳ ColPali query encoder 未接（見 #133）；無法 round-trip。先補 active_colpali_query_fn。")
        return
    if not GOLD:
        print("⏳ 尚無 gold 樣本；請填入 GOLD（query, 期望 page_id），或向 R4 索取（#133）。")
        return

    store = BigQueryColpaliStore(settings)
    hit, total = 0, len(GOLD)
    for query, expected_page_id in GOLD:
        vector = fn(query)
        results = store.search(vector, top_k=5)
        got = [r.id for r in results]
        ok = expected_page_id in got
        hit += int(ok)
        print(f"{'✅' if ok else '❌'} {query!r} → top5={got}（期望 {expected_page_id}）")
    rate = hit / total if total else 0.0
    print(f"\n命中率 {hit}/{total} = {rate:.0%}（門檻 ≥70%）：{'PASS' if rate >= 0.70 else 'FAIL'}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run to verify import-safe (no encoder yet)**

Run: `uv run python scripts/colpali_roundtrip_check.py`
Expected: 印「⏳ ColPali query encoder 未接（見 #133）…」並正常結束（exit 0），不拋。

- [ ] **Step 3: Commit**

```bash
git add scripts/colpali_roundtrip_check.py
git commit -m "feat(eval): colpali round-trip hit-rate self-check script (gated on #133 encoder)"
```

---

## Task 5: 修正過時 ColPali 註解（retriever.py 仍寫「cut」）

**Files:**
- Modify: `src/polaris/retrieval/retriever.py:7`

- [ ] **Step 1: 更新 docstring 行**

把 `src/polaris/retrieval/retriever.py:7` 的：
```
- ColPali 已於 G3 前評估後 cut（TD-01）
```
改為：
```
- ColPali 視覺檢索為獨立第 4 路（gated，場景 3），見 colpali_retriever / colpali_store；
  資料早於 R4 入庫 colpali_pages，TD-01 僅 cut「R3 整合」、非資料（TD-02 復原，待 PM 簽核）
```

- [ ] **Step 2: 全測試綠**

Run: `uv run pytest -q`
Expected: 全綠（既有 + 新增 colpali 測試），ruff clean。

Run: `make lint && make test`（若有 Makefile target）
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/polaris/retrieval/retriever.py
git commit -m "docs(retrieval): correct stale ColPali 'cut' comment — 4th path restored via colpali_pages (TD-02)"
```

---

## Phase 1 完成定義（Definition of Done）

- [ ] `BigQueryColpaliStore` 只讀 `colpali_pages`、128 維 cosine、回 `origin="colpali"`、無 viewer filter。
- [ ] `ColpaliRetriever` 注入 encoder；缺席回 `[]`、`active_colpali_retriever()` 回 None。
- [ ] eval 場景 3：無 encoder 拋錯指向 #133；注入 stub 時回 colpali contexts。
- [ ] round-trip 工具 import-safe；待 #133 + gold 樣本即可量命中率（門檻 ≥70%）。
- [ ] 過時「cut」註解已修正。
- [ ] 全測試綠、ruff clean、CI 0 外呼（無金鑰/憑證）。

## 落地後（不在 Phase 1）

- **接 #133 的真 encoder**：在 `active_colpali_query_fn()` 接上 R4 的 checkpoint+池化（或推論端點）→ 跑 round-trip 驗收 ≥70%。
- **Phase 2（回答）**：由 `source_file` 定位原始 PDF → `pdftoppm` render 頁圖 → Gemini vision 讀數字 → 回答接地（需 R4 提供 PDF 存放位置）。
- **TD-02 簽核**：PM 確認 4-way 復原後，更新憲法 §檢索。
