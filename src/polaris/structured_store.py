"""唯讀查 ``polaris_core`` 給 API（結構化表 + 受 ACL 保護的單筆 chunk）。

R7 前端「結構化資料走 API」分層的後端：把三張非機密的事實/維度表包成穩定
端點，前端不必直連 BigQuery、也不耦合實體 schema（欄位改名只動這層）。

設計與 :class:`polaris.vectorstore.bigquery_store.BigQueryStore` 同套：

- **client 注入式 seam**：測試注入 fake client → CI 0 GCP 外呼、0 金鑰；真環境
  延遲 import ``google.cloud.bigquery``。
- **只讀**：僅 ``SELECT``，不寫入；故無 ``polaris_core`` 寫入防呆（那是寫入端的事）。
- ``chunks`` **內容**不在此：有 ``owner``/``confidential`` 存取控制，須走 ``/ask``、
  ``/research`` 的 retriever 過濾，不在結構化讀層裸查 ``chunk_text``。
  例外：``list_library()`` 僅查文件級 metadata（不含 ``chunk_text``），無內容洩露風險。
"""
from __future__ import annotations

from typing import Any

#: 預設回傳上限（防止前端誤拉整表；可由端點 query 覆寫，仍受此上限約束）。
_DEFAULT_LIMIT = 200
_MAX_LIMIT = 1000


def _clamp_limit(limit: int | None) -> int:
    """把使用者給的 limit 夾在 [1, _MAX_LIMIT]；None → 預設。"""
    if limit is None:
        return _DEFAULT_LIMIT
    return max(1, min(int(limit), _MAX_LIMIT))


class StructuredStore:
    """polaris_core 結構化表的唯讀查詢層。"""

    def __init__(self, settings, *, client=None) -> None:
        self.settings = settings
        self._client = client  # 注入（測試）或延遲建立（真環境）

    def _get_client(self):
        if self._client is None:
            from google.cloud import bigquery  # 延遲 import（重相依不進 CI 必經路徑）
            self._client = bigquery.Client(project=self.settings.gcp_project)
        return self._client

    def _dataset(self) -> str:
        return f"{self.settings.gcp_project}.{self.settings.bq_dataset}"

    # ── companies（company_dim 維度表）─────────────────────────────────────

    def list_companies(self) -> list[dict]:
        """全部 canonical 公司（ticker→名稱/產業）。維度表小（~20 列），不分頁。"""
        sql = f"""
        SELECT ticker, company_name, english_name, market,
               industry_id, industry_name, is_financial, aliases
        FROM `{self._dataset()}.company_dim`
        ORDER BY ticker
        """
        return self._run_query(sql, {})

    # ── financials（financial_metrics 事實表）──────────────────────────────

    def list_financials(
        self,
        *,
        ticker: str | None = None,
        period: str | None = None,
        metric: str | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        """財務指標列（可依 ticker / fiscal_period / metric_id 過濾）。"""
        clauses: list[str] = []
        params: dict[str, Any] = {}
        if ticker is not None:
            clauses.append("ticker = @ticker")
            params["ticker"] = ticker
        if period is not None:
            clauses.append("fiscal_period = @period")
            params["period"] = period
        if metric is not None:
            clauses.append("metric_id = @metric")
            params["metric"] = metric
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params["lim"] = _clamp_limit(limit)
        sql = f"""
        SELECT ticker, fiscal_period, metric_id, metric_name, value, unit, source_id, published_at,
               year, month
        FROM `{self._dataset()}.v_financial_metrics_semantic`
        {where}
        ORDER BY published_at DESC, ticker, fiscal_period, metric_id
        LIMIT @lim
        """
        return self._run_query(sql, params)

    # ── events（events 事實表 — 事件流 / 時間軸）───────────────────────────

    def list_events(
        self,
        *,
        ticker: str | None = None,
        event_type: str | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        """事件列（時間倒序；可依 ticker / event_key 過濾）。

        不回傳 ``body`` / ``raw_json``（可能很大）——列表/時間軸用 title + 來源連結即可。
        欄位已於 2026-06 由 R6 更名：event_type → event_key，source_name → source_key。
        """
        clauses: list[str] = []
        params: dict[str, Any] = {}
        if ticker is not None:
            clauses.append("ticker = @ticker")
            params["ticker"] = ticker
        if event_type is not None:
            clauses.append("STARTS_WITH(event_key, @event_key)")
            params["event_key"] = event_type
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params["lim"] = _clamp_limit(limit)
        sql = f"""
        SELECT event_id, ticker, event_key, published_at, title, source_url, source_key
        FROM `{self._dataset()}.events`
        {where}
        ORDER BY published_at DESC, event_id
        LIMIT @lim
        """
        return self._run_query(sql, params)

    # ── chunk（引用展開；必須套用與向量檢索相同的 ACL）────────────────────

    def get_chunk(self, source_id: str, *, viewer: str) -> dict | None:
        """依 chunk_id 讀單一原文；查無或 viewer 無權限時一律回 ``None``。"""
        sql = f"""
        SELECT chunk_id, ticker, doc_type, fiscal_period, published_at, chunk_text
        FROM `{self._dataset()}.chunks`
        WHERE chunk_id = @source_id
          AND (owner IS NULL OR owner = @viewer)
          AND (NOT COALESCE(confidential, FALSE) OR owner = @viewer)
        LIMIT 1
        """
        rows = self._run_query(sql, {"source_id": source_id, "viewer": viewer})
        return rows[0] if rows else None

    # ── library（chunks + v_colpali_pages_semantic 文件級 metadata）──────────

    def list_library(
        self,
        *,
        ticker: str | None = None,
        doc_type: str | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        """文件庫清單：transcript（chunks）+ major_news（events）+ earnings_call（colpali）。

        只查文件級 metadata（不含 chunk_text / embedding），不涉及 ACL 存取控制。
        transcript：chunks 依 ticker+fiscal_period 去重；
        major_news：events 依 STARTS_WITH(event_key, 'major_news') 過濾，每筆 event 為一文件；
        earnings_call：colpali_pages 依 source_file 去重。
        """
        lim = _clamp_limit(limit)
        results: list[dict] = []

        # ── 1. chunks（transcript）— 不查 chunk_text ──────────────────────
        include_chunks = doc_type is None or doc_type == "transcript"
        if include_chunks:
            c_where: list[str] = ["c.doc_type = 'transcript'"]
            c_params: dict[str, Any] = {"lim_c": lim}
            if ticker:
                c_where.append("c.ticker = @c_ticker")
                c_params["c_ticker"] = ticker
            sql_c = f"""
            SELECT
                CONCAT(c.ticker, '_transcript_', COALESCE(c.fiscal_period, '')) AS id,
                c.ticker,
                COALESCE(ANY_VALUE(cd.company_name), c.ticker) AS company_name,
                'transcript' AS doc_type,
                COALESCE(c.fiscal_period, '') AS fiscal_period,
                CONCAT(c.ticker, ' ', COALESCE(c.fiscal_period, ''), ' transcript') AS source_file,
                CAST(MIN(c.published_at) AS STRING) AS published_at,
                '' AS fetched_at,
                COUNT(*) AS page_count,
                TRUE AS ingested
            FROM `{self._dataset()}.chunks` c
            LEFT JOIN `{self._dataset()}.company_dim` cd ON cd.ticker = c.ticker
            WHERE {' AND '.join(c_where)}
            GROUP BY c.ticker, c.fiscal_period
            ORDER BY MIN(c.published_at) DESC, c.ticker
            LIMIT @lim_c
            """
            results.extend(self._run_query(sql_c, c_params))

        # ── 2. events（major_news.*）— 每筆 event 為一文件 ────────────────
        include_major_news = doc_type is None or doc_type == "major_news"
        if include_major_news:
            mn_where: list[str] = ["STARTS_WITH(e.event_key, 'major_news')"]
            mn_params: dict[str, Any] = {"lim_mn": lim}
            if ticker:
                mn_where.append("e.ticker = @mn_ticker")
                mn_params["mn_ticker"] = ticker
            sql_mn = f"""
            SELECT
                e.event_id AS id,
                e.ticker,
                COALESCE(cd.company_name, e.ticker) AS company_name,
                'major_news' AS doc_type,
                '' AS fiscal_period,
                COALESCE(e.source_url, e.event_id) AS source_file,
                CAST(e.published_at AS STRING) AS published_at,
                '' AS fetched_at,
                1 AS page_count,
                TRUE AS ingested
            FROM `{self._dataset()}.events` e
            LEFT JOIN `{self._dataset()}.company_dim` cd ON cd.ticker = e.ticker
            WHERE {' AND '.join(mn_where)}
            ORDER BY e.published_at DESC, e.event_id
            LIMIT @lim_mn
            """
            results.extend(self._run_query(sql_mn, mn_params))

        # ── 2. v_colpali_pages_semantic（earnings_call 簡報）──────────────
        include_colpali = doc_type is None or doc_type == "earnings_call"
        if include_colpali:
            p_where: list[str] = []
            p_params: dict[str, Any] = {"lim_p": lim}
            if ticker:
                p_where.append("cp.ticker = @p_ticker")
                p_params["p_ticker"] = ticker
            p_where_clause = ("WHERE " + " AND ".join(p_where)) if p_where else ""
            sql_p = f"""
            SELECT
                cp.source_file AS id,
                cp.ticker,
                COALESCE(cd.company_name, cp.ticker) AS company_name,
                'earnings_call' AS doc_type,
                COALESCE(cp.fiscal_period, '') AS fiscal_period,
                cp.source_file,
                CAST(MIN(cp.published_at) AS STRING) AS published_at,
                CAST(MAX(cp.fetched_at) AS STRING) AS fetched_at,
                COUNT(*) AS page_count,
                TRUE AS ingested
            FROM `{self._dataset()}.colpali_pages` cp
            LEFT JOIN `{self._dataset()}.company_dim` cd ON cd.ticker = cp.ticker
            {p_where_clause}
            GROUP BY cp.source_file, cp.ticker, cp.fiscal_period, cd.company_name
            ORDER BY MIN(cp.published_at) DESC, cp.ticker
            LIMIT @lim_p
            """
            results.extend(self._run_query(sql_p, p_params))

        results.sort(key=lambda r: str(r.get("published_at") or ""), reverse=True)
        return results[:lim]

    # ── BigQuery 轉接（同 BigQueryStore 套路）──────────────────────────────

    def _run_query(self, sql: str, params: dict[str, Any]) -> list[dict]:
        client = self._get_client()
        job_config = self._build_job_config(params)
        return [dict(row) for row in client.query(sql, job_config=job_config).result()]

    @staticmethod
    def _build_job_config(params: dict[str, Any]):
        """組 QueryJobConfig；fake client（測試）回 None 即可忽略。

        鏡像 BigQueryStore._build_job_config，但本層只有 STRING / INT64 純量參數
        （無向量陣列）—— 兩層各自獨立，避免結構化讀層耦合向量庫。
        """
        try:
            from google.cloud import bigquery
        except ImportError:  # 測試環境（注入 fake client）不需真參數物件
            return None
        qp = []
        for name, value in params.items():
            if isinstance(value, bool):  # bool 是 int 的子型別 → 先攔，免被當 INT64
                qp.append(bigquery.ScalarQueryParameter(name, "BOOL", value))
            elif isinstance(value, int):
                qp.append(bigquery.ScalarQueryParameter(name, "INT64", value))
            else:
                qp.append(bigquery.ScalarQueryParameter(name, "STRING", value))
        return bigquery.QueryJobConfig(query_parameters=qp)
