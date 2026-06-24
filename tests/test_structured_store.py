"""StructuredStore — polaris_core 結構化表唯讀查詢層（company_dim / financial_metrics / events）。

注入式 fake client → 0 GCP 外呼、不需 google-cloud-bigquery 安裝；驗 SQL 形狀、
參數、limit 夾擠、row→dict 轉換。同 test_vectorstore_impl.py 的 fake 套路。
"""
from __future__ import annotations

from polaris.config import Settings
from polaris.structured_store import _MAX_LIMIT, StructuredStore, _clamp_limit


def make_settings(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


class FakeBQJob:
    def __init__(self, rows=None):
        self._rows = rows or []

    def result(self):
        return self._rows


class FakeBQClient:
    """記錄 query 呼叫 + 注入回傳列。"""

    def __init__(self, rows=None):
        self.queries: list[str] = []
        self._rows = rows or []

    def query(self, sql, job_config=None):
        self.queries.append(sql)
        return FakeBQJob(self._rows)


def make_store(rows=None, **settings_overrides) -> tuple[StructuredStore, FakeBQClient]:
    client = FakeBQClient(rows=rows)
    return StructuredStore(make_settings(**settings_overrides), client=client), client


class TestClampLimit:
    def test_none_returns_default(self):
        assert _clamp_limit(None) == 200

    def test_caps_at_max(self):
        assert _clamp_limit(99999) == _MAX_LIMIT

    def test_floor_at_one(self):
        assert _clamp_limit(0) == 1
        assert _clamp_limit(-5) == 1


class TestListCompanies:
    def test_queries_company_dim_ordered(self):
        store, client = make_store(rows=[{"ticker": "2330", "company_name": "台積電"}])
        out = store.list_companies()
        assert out == [{"ticker": "2330", "company_name": "台積電"}]
        sql = client.queries[0]
        assert "company_dim" in sql
        assert "ORDER BY ticker" in sql

    def test_targets_configured_dataset(self):
        store, client = make_store(bq_dataset="polaris_core", gcp_project="polaris-desk-team")
        store.list_companies()
        assert "`polaris-desk-team.polaris_core.company_dim`" in client.queries[0]


class TestListFinancials:
    def test_no_filters_has_no_where(self):
        store, client = make_store()
        store.list_financials()
        sql = client.queries[0]
        assert "financial_metrics" in sql
        assert "WHERE" not in sql
        assert "LIMIT @lim" in sql

    def test_all_filters_build_where(self):
        store, client = make_store()
        store.list_financials(ticker="2330", period="2025Q4", metric="revenue")
        sql = client.queries[0]
        assert "ticker = @ticker" in sql
        assert "fiscal_period = @period" in sql
        assert "metric_id = @metric" in sql

    def test_partial_filter_only_includes_given(self):
        store, client = make_store()
        store.list_financials(ticker="2330")
        sql = client.queries[0]
        assert "ticker = @ticker" in sql
        assert "@period" not in sql
        assert "@metric" not in sql

    def test_rows_passthrough(self):
        row = {"ticker": "2330", "fiscal_period": "2025Q4", "metric_id": "eps", "value": 13.94}
        store, _ = make_store(rows=[row])
        assert store.list_financials() == [row]


class TestListEvents:
    def test_ordered_desc_and_lean_columns(self):
        store, client = make_store()
        store.list_events()
        sql = client.queries[0]
        assert "FROM `" in sql and ".events`" in sql
        assert "ORDER BY published_at DESC" in sql
        # body / raw_json 不在列表回應
        assert "body" not in sql
        assert "raw_json" not in sql

    def test_filters_by_ticker_and_type(self):
        store, client = make_store()
        store.list_events(ticker="2330", event_type="monthly_revenue")
        sql = client.queries[0]
        assert "ticker = @ticker" in sql
        assert "event_type = @event_type" in sql


class TestGetChunk:
    def test_reads_one_chunk_with_access_control(self):
        row = {
            "chunk_id": "chunk-2330-q1",
            "ticker": "2330",
            "doc_type": "transcript",
            "fiscal_period": "2026Q1",
            "published_at": "2026-04-17",
            "chunk_text": "法說原文",
        }
        store, client = make_store(rows=[row])

        assert store.get_chunk("chunk-2330-q1", viewer="analyst_A") == row

        sql = client.queries[0]
        assert "chunk_id = @source_id" in sql
        assert "owner IS NULL OR owner = @viewer" in sql
        assert "NOT COALESCE(confidential, FALSE) OR owner = @viewer" in sql
        assert "LIMIT 1" in sql

    def test_returns_none_when_chunk_is_not_visible_or_missing(self):
        store, _ = make_store(rows=[])

        assert store.get_chunk("missing", viewer="__public__") is None


class TestBuildJobConfig:
    def test_no_bigquery_installed_returns_none(self, monkeypatch):
        # 模擬測試環境無 google-cloud-bigquery：_build_job_config 應回 None（fake client 忽略）
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "google.cloud" or name.startswith("google.cloud"):
                raise ImportError("no bigquery")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        assert StructuredStore._build_job_config({"ticker": "2330", "lim": 5}) is None
