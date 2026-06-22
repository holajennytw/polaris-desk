"""VectorStore 兩後端實作測試（G2 未關項：BigQueryStore + pgvector fallback）。

注入式 fake client / conn → 0 GCP / 0 DB 外呼、不需 google-cloud-bigquery /
psycopg 安裝；驗證 SQL 形狀、參數、polaris_core 寫入防呆、health_check 語意。
"""
from __future__ import annotations

import pytest

from polaris.config import Settings
from polaris.vectorstore.base import Document
from polaris.vectorstore.bigquery_store import BigQueryStore
from polaris.vectorstore.pgvector_store import PgVectorStore, _vector_literal

EMB = [0.1] * 4  # 測試用短向量（真環境 768，由 schema 守）


def make_settings(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


def make_doc(**overrides) -> Document:
    base = dict(
        id="2330-2025Q1-c001",
        content="台積電 2025Q1 法說摘要片段。",
        embedding=EMB,
        company="2330",
        period="2025Q1",
        metadata={"doc_id": "2330-2025Q1", "page": 3},
    )
    base.update(overrides)
    return Document(**base)


# ── BigQuery fakes ───────────────────────────────────────────────────────────

class FakeBQJob:
    def __init__(self, rows=None, error=None):
        self._rows = rows or []
        self._error = error

    def result(self):
        if self._error:
            raise self._error
        return self._rows


class FakeBQClient:
    """記錄 query / load 呼叫；可注入回傳列與錯誤。"""

    def __init__(self, rows=None, error=None):
        self.queries: list[str] = []
        self.loaded: list[tuple[list[dict], str]] = []
        self._rows = rows or []
        self._error = error

    def query(self, sql, job_config=None):
        self.queries.append(sql)
        return FakeBQJob(self._rows, self._error)

    def load_table_from_json(self, rows, table):
        self.loaded.append((rows, table))
        return FakeBQJob(error=self._error)


# ── BigQueryStore ────────────────────────────────────────────────────────────

class TestBigQueryStore:
    def test_health_check_ok(self):
        client = FakeBQClient()
        store = BigQueryStore(make_settings(), client=client)
        assert store.health_check() is True
        assert client.queries == ["SELECT 1"]

    def test_health_check_failure_returns_false_not_raises(self):
        client = FakeBQClient(error=ConnectionError("no creds"))
        store = BigQueryStore(make_settings(), client=client)
        assert store.health_check() is False

    def test_add_documents_refuses_core_dataset_by_default(self):
        """憲法 III：polaris_core 預設唯讀，client 端防呆直接拒寫。"""
        client = FakeBQClient()
        store = BigQueryStore(make_settings(bq_dataset="polaris_core"), client=client)
        with pytest.raises(PermissionError, match="polaris_core"):
            store.add_documents([make_doc()])
        assert client.loaded == []  # 0 寫入

    def test_add_documents_to_dev_dataset_canonical_columns(self):
        """寫入用 canonical 欄名（SOP §4：chunk_id/ticker/fiscal_period/chunk_text）。"""
        client = FakeBQClient()
        store = BigQueryStore(
            make_settings(bq_dataset="polaris_dev_wayne"), client=client
        )
        store.add_documents(
            [make_doc(metadata={"doc_type": "presentation", "published_at": "2025-04-17"})]
        )
        rows, table = client.loaded[0]
        assert table == "polaris-desk-team.polaris_dev_wayne.chunks"
        assert rows[0]["chunk_id"] == "2330-2025Q1-c001"
        assert rows[0]["ticker"] == "2330"
        assert rows[0]["fiscal_period"] == "2025Q1"
        assert rows[0]["chunk_text"].startswith("台積電")
        assert rows[0]["doc_type"] == "presentation"  # 取自 metadata
        assert rows[0]["published_at"] == "2025-04-17"  # 取自 metadata
        assert rows[0]["embedding"] == EMB
        assert "id" not in rows[0] and "company" not in rows[0]  # 舊欄名不再使用

    def test_add_documents_core_allowed_with_explicit_flag(self):
        """ingestion 帳號（R1/R4）設 BQ_ALLOW_CORE_WRITE=1 才解鎖。"""
        client = FakeBQClient()
        store = BigQueryStore(
            make_settings(bq_dataset="polaris_core", bq_allow_core_write=True),
            client=client,
        )
        store.add_documents([make_doc()])
        assert len(client.loaded) == 1

    def test_add_documents_empty_noop(self):
        client = FakeBQClient()
        BigQueryStore(make_settings(), client=client).add_documents([])
        assert client.loaded == []

    def test_search_uses_vector_search_cosine(self):
        from datetime import date

        client = FakeBQClient(rows=[
            {"chunk_id": "c1", "chunk_text": "片段", "ticker": "2330",
             "fiscal_period": "2025Q1", "doc_type": "presentation",
             "published_at": date(2025, 4, 17), "distance": 0.2},
        ])
        store = BigQueryStore(make_settings(), client=client)
        results = store.search(EMB, top_k=5)
        sql = client.queries[0]
        assert "VECTOR_SEARCH" in sql
        assert "COSINE" in sql
        assert results[0].id == "c1"
        assert results[0].content == "片段"
        assert results[0].company == "2330"
        assert results[0].period == "2025Q1"
        assert results[0].score == pytest.approx(0.8)  # 1 - distance
        assert results[0].metadata == {
            "doc_type": "presentation", "published_at": "2025-04-17"
        }

    def test_search_filters_map_to_canonical_columns(self):
        """介面 filter 鍵（company/period）→ canonical 欄（ticker/fiscal_period）。"""
        client = FakeBQClient()
        store = BigQueryStore(make_settings(), client=client)
        store.search(EMB, filters={"company": "2330", "period": "2024Q3"})
        sql = client.queries[0]
        assert "ticker = @ticker" in sql
        assert "fiscal_period = @fiscal_period" in sql
        assert "company = @" not in sql and " period = @" not in sql  # 舊欄名不再使用

    def test_search_viewer_filter_sql(self):
        """viewer filter generates owner IS NULL OR owner = @viewer clause."""
        client = FakeBQClient()
        store = BigQueryStore(make_settings(), client=client)
        store.search(EMB, filters={"viewer": "analyst_A"})
        sql = client.queries[0]
        assert "owner IS NULL OR owner = @viewer" in sql
        # NULL-safe: pre-backfill rows (confidential = NULL) stay visible
        assert "NOT COALESCE(confidential, FALSE) OR owner = @viewer" in sql

    def test_search_joins_semantic_view_for_event_source_published(self):
        """P1：VECTOR_SEARCH 仍對 chunks（唯一含 embedding），向量命中後再用 chunk_id
        LEFT JOIN v_chunk_semantic 補 event_key / source_key / published_yyyymm，落到
        SearchResult.metadata。"""
        client = FakeBQClient(rows=[
            {"chunk_id": "c1", "chunk_text": "台積電法說片段", "ticker": "2330",
             "fiscal_period": "2026Q1", "doc_type": "transcript",
             "published_at": None, "distance": 0.1,
             "event_key": "earnings_call", "source_key": "PRIMARY_EC_TRANSCRIPT",
             "published_yyyymm": 202604},
        ])
        store = BigQueryStore(make_settings(), client=client)
        results = store.search(EMB, top_k=5)
        sql = client.queries[0]

        # VECTOR_SEARCH 的 base 子查詢必須是 chunks，不能換成無 embedding 的 view
        vs_block = sql[sql.index("VECTOR_SEARCH("):sql.index("LEFT JOIN")]
        assert "chunks`" in vs_block
        assert "v_chunk_semantic" not in vs_block  # ⚠️ view 無 embedding，不可進 VECTOR_SEARCH
        # 命中後才 LEFT JOIN 語意 view 取三欄
        join_block = sql[sql.index("LEFT JOIN"):]
        assert "v_chunk_semantic" in join_block
        assert "sem.chunk_id = vs.chunk_id" in join_block
        for col in ("sem.event_key", "sem.source_key", "sem.published_yyyymm"):
            assert col in sql
        # 三欄落到 metadata（有值才帶；published_yyyymm 維持 INT64 不轉字串）
        md = results[0].metadata
        assert md["event_key"] == "earnings_call"
        assert md["source_key"] == "PRIMARY_EC_TRANSCRIPT"
        assert md["published_yyyymm"] == 202604

    def test_search_semantic_fields_null_when_view_has_no_match(self):
        """P1：LEFT JOIN 無對應語意列 → 三欄 NULL（允許 null、不編造）；此時 metadata
        不放這三鍵（None 被濾掉），由下游 _ensure_citation_metadata 補回 None。"""
        client = FakeBQClient(rows=[
            {"chunk_id": "c9", "chunk_text": "片段", "ticker": "2330",
             "fiscal_period": "2026Q1", "doc_type": "transcript",
             "published_at": None, "distance": 0.3,
             "event_key": None, "source_key": None, "published_yyyymm": None},
        ])
        store = BigQueryStore(make_settings(), client=client)
        md = store.search(EMB)[0].metadata
        assert "event_key" not in md and "source_key" not in md
        assert "published_yyyymm" not in md  # None → 不編造、不放鍵

    def test_search_filters_still_apply_inside_vector_search_with_join(self):
        """P1 不可退步：加了語意 JOIN 後，ticker / fiscal_period / doc_type 過濾仍在
        VECTOR_SEARCH 的 base 子查詢內（先濾向量候選，而非 JOIN 後才濾）。"""
        client = FakeBQClient()
        store = BigQueryStore(make_settings(), client=client)
        store.search(EMB, filters={"company": "2330", "period": "2026Q1",
                                   "doc_type": "transcript"})
        sql = client.queries[0]
        vs_block = sql[sql.index("VECTOR_SEARCH("):sql.index("LEFT JOIN")]
        assert "ticker = @ticker" in vs_block
        assert "fiscal_period = @fiscal_period" in vs_block
        assert "doc_type = @doc_type" in vs_block

    def test_add_documents_writes_owner_and_confidential(self):
        client = FakeBQClient()
        store = BigQueryStore(make_settings(bq_dataset="polaris_dev_test"), client=client)
        doc = make_doc(metadata={"owner": "client_B", "confidential": True})
        store.add_documents([doc])
        rows, _ = client.loaded[0]
        assert rows[0]["owner"] == "client_B"
        assert rows[0]["confidential"] is True


# ── pgvector fakes ───────────────────────────────────────────────────────────

class FakeCursor:
    def __init__(self, rows=None, error=None):
        self.executed: list[tuple[str, list]] = []
        self._rows = rows or []
        self._error = error

    def execute(self, sql, args=None):
        if self._error:
            raise self._error
        self.executed.append((sql, list(args or [])))

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return (1,)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeConn:
    def __init__(self, rows=None, error=None):
        self.cur = FakeCursor(rows, error)
        self.commits = 0

    def cursor(self):
        return self.cur

    def commit(self):
        self.commits += 1


# ── PgVectorStore ────────────────────────────────────────────────────────────

class TestPgVectorStore:
    def test_vector_literal(self):
        assert _vector_literal([0.1, 0.2]) == "[0.1,0.2]"

    def test_health_check_ok_and_fail(self):
        assert PgVectorStore(make_settings(), conn=FakeConn()).health_check() is True
        bad = FakeConn(error=ConnectionError("db down"))
        assert PgVectorStore(make_settings(), conn=bad).health_check() is False

    def test_add_documents_upsert(self):
        conn = FakeConn()
        store = PgVectorStore(make_settings(), conn=conn)
        store.add_documents([make_doc()])
        sql, args = conn.cur.executed[0]
        assert "ON CONFLICT (id) DO UPDATE" in sql
        assert args[0] == "2330-2025Q1-c001"
        assert args[1] == "2330-2025Q1"  # doc_id 取自 metadata
        assert conn.commits == 1

    def test_search_must_use_cosine_operator(self):
        """效能雷 §1–2：必須 <=> + ORDER BY ... LIMIT 才走 HNSW 索引。"""
        conn = FakeConn(rows=[
            ("c1", "片段", "2330", "2025Q1", {"page": 3}, 0.85),
        ])
        store = PgVectorStore(make_settings(), conn=conn)
        results = store.search(EMB, top_k=5, filters={"company": "2330"})
        sql, args = conn.cur.executed[0]
        assert "<=>" in sql
        assert "<->" not in sql and "<#>" not in sql  # 用錯算子會全表掃描
        assert "ORDER BY embedding <=>" in sql
        assert "LIMIT" in sql
        assert "company = %s" in sql
        assert args[-1] == 5  # top_k
        assert results[0].score == pytest.approx(0.85)

    def test_search_viewer_filter_sql(self):
        """viewer filter generates owner/confidential WHERE clauses."""
        conn = FakeConn()
        store = PgVectorStore(make_settings(), conn=conn)
        store.search(EMB, top_k=3, filters={"viewer": "analyst_A"})
        sql, args = conn.cur.executed[0]
        assert "owner IS NULL OR owner = %s" in sql
        assert "NOT COALESCE(confidential, FALSE) OR owner = %s" in sql
        # viewer value appears twice (owner filter + confidential bypass)
        assert args.count("analyst_A") == 2

    def test_add_documents_writes_owner_and_confidential(self):
        conn = FakeConn()
        store = PgVectorStore(make_settings(), conn=conn)
        doc = make_doc(metadata={"doc_id": "doc-1", "owner": "client_B", "confidential": True})
        store.add_documents([doc])
        sql, args = conn.cur.executed[0]
        assert "owner" in sql
        assert "confidential" in sql
        assert "client_B" in args
        assert True in args


# ── factory 整合 ─────────────────────────────────────────────────────────────

def test_factory_returns_implementations():
    from polaris.vectorstore import get_vector_store

    bq = get_vector_store(make_settings(vector_backend="bigquery"))
    pg = get_vector_store(make_settings(vector_backend="pgvector"))
    assert isinstance(bq, BigQueryStore)
    assert isinstance(pg, PgVectorStore)
