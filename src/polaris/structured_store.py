"""唯讀查 ``polaris_core`` 給 API（結構化表 + 受 ACL 保護的單筆 chunk）。

R7 前端「結構化資料走 API」分層的後端：把三張非機密的事實/維度表包成穩定
端點，前端不必直連 BigQuery、也不耦合實體 schema（欄位改名只動這層）。

設計與 :class:`polaris.vectorstore.bigquery_store.BigQueryStore` 同套：

- **client 注入式 seam**：測試注入 fake client → CI 0 GCP 外呼、0 金鑰；真環境
  延遲 import ``google.cloud.bigquery``。
- **只讀**：僅 ``SELECT``，不寫入；故無 ``polaris_core`` 寫入防呆（那是寫入端的事）。
- ``chunks`` **不在此**：有 ``owner``/``confidential`` 存取控制，須走 ``/ask``、
  ``/research`` 的 retriever 過濾，不在結構化讀層裸查。
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
        SELECT ticker, fiscal_period, metric_id, value, unit, source_id, published_at
        FROM `{self._dataset()}.financial_metrics`
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
        """事件列（時間倒序；可依 ticker / event_type 過濾）。

        不回傳 ``body`` / ``raw_json``（可能很大）——列表/時間軸用 title + 來源連結即可。
        """
        clauses: list[str] = []
        params: dict[str, Any] = {}
        if ticker is not None:
            clauses.append("ticker = @ticker")
            params["ticker"] = ticker
        if event_type is not None:
            clauses.append("event_type = @event_type")
            params["event_type"] = event_type
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params["lim"] = _clamp_limit(limit)
        sql = f"""
        SELECT event_id, ticker, event_type, published_at, title, source_url
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
