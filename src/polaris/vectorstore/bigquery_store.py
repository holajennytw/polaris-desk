"""雲端向量庫實作：BigQuery VECTOR_SEARCH（Q-03 預設後端）。

介面與 PgVectorStore 完全相同 —— 切換只改 .env 的 ``VECTOR_BACKEND``。

- **client 注入式 seam**（同 Deep Research ``search`` / Slack ``transport``
  套路）：測試注入 fake client → CI 0 GCP 外呼、0 金鑰；真環境延遲
  import ``google.cloud.bigquery``。
- **寫入保護（憲法 III / SOP §3.4）**：``add_documents`` 預設拒寫
  ``polaris_core``（共用 canonical 唯讀）；一般開發者寫自己的
  ``polaris_dev_<name>``。經 PM 同意的 ingestion 帳號（R1/R4）設
  ``BQ_ALLOW_CORE_WRITE=1`` 解鎖 —— 這是 client 端防呆，**不取代** server
  端 ACL（ACL 變更一律走 SOP §7 PR）。
- 維度 768 / 距離 cosine，與 pgvector fallback 兩端一致（憲法 §Additional）。
- **欄名對齊 canonical schema（SOP §4）**：BigQuery 端實體欄位是
  ``chunk_id / ticker / doc_type / fiscal_period / published_at / chunk_text /
  embedding``；介面層（Document / SearchResult）仍是 id / company / period /
  content / metadata，由本類別做雙向對映 —— 呼叫端與 pgvector fallback 都不用改。
"""
from __future__ import annotations

from typing import Any

from .base import Document, SearchResult, VectorStore

#: 共用 canonical dataset —— 預設唯讀（憲法 III）。
_CORE_DATASET = "polaris_core"

#: 介面 filter 鍵 → canonical 欄名（SOP §4 cluster 欄優先：ticker / doc_type）。
_FILTER_COLUMNS = {
    "company": "ticker",
    "period": "fiscal_period",
    "doc_type": "doc_type",
}


class BigQueryStore(VectorStore):
    def __init__(self, settings, *, client=None) -> None:
        self.settings = settings
        self._client = client  # 注入（測試）或延遲建立（真環境）

    def _get_client(self):
        if self._client is None:
            from google.cloud import bigquery  # 延遲 import（重相依不進 CI 必經路徑）
            self._client = bigquery.Client(project=self.settings.gcp_project)
        return self._client

    @property
    def _table(self) -> str:
        return f"{self.settings.gcp_project}.{self.settings.bq_dataset}.chunks"

    # ── 寫入（含 polaris_core 防呆）─────────────────────────────────────

    def add_documents(self, docs: list[Document]) -> None:
        if not docs:
            return
        if (
            self.settings.bq_dataset == _CORE_DATASET
            and not getattr(self.settings, "bq_allow_core_write", False)
        ):
            raise PermissionError(
                f"拒寫共用 canonical `{_CORE_DATASET}`（憲法 III：開發者寫自己的 "
                "polaris_dev_<name>；ingestion 帳號設 BQ_ALLOW_CORE_WRITE=1）"
            )
        rows = [
            {
                "chunk_id": d.id,
                "ticker": d.company,
                "doc_type": d.metadata.get("doc_type"),
                "fiscal_period": d.period,
                "published_at": d.metadata.get("published_at"),
                "chunk_text": d.content,
                "embedding": d.embedding,
            }
            for d in docs
        ]
        client = self._get_client()
        client.load_table_from_json(rows, self._table).result()

    # ── 檢索（VECTOR_SEARCH，cosine）───────────────────────────────────

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 8,
        *,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        where = ""
        params: dict[str, Any] = {"qe": query_embedding, "k": top_k}
        clauses = []
        for key, column in _FILTER_COLUMNS.items():
            if filters and filters.get(key) is not None:
                clauses.append(f"{column} = @{column}")
                params[column] = filters[key]
        if clauses:
            where = "WHERE " + " AND ".join(clauses)

        sql = f"""
        SELECT base.chunk_id, base.chunk_text, base.ticker, base.fiscal_period,
               base.doc_type, base.published_at, distance
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
        return [
            SearchResult(
                id=row["chunk_id"],
                content=row["chunk_text"],
                # cosine 距離 → 相似度分數（兩端後端同語意：越大越像）
                score=1.0 - float(row["distance"]),
                company=row.get("ticker"),
                period=row.get("fiscal_period"),
                # canonical 無 metadata JSON 欄 → 由欄位重組（引用接地要 doc_type / 日期）
                metadata={
                    k: v
                    for k, v in {
                        "doc_type": row.get("doc_type"),
                        "published_at": (
                            row["published_at"].isoformat()
                            if hasattr(row.get("published_at"), "isoformat")
                            else row.get("published_at")
                        ),
                    }.items()
                    if v is not None
                },
            )
            for row in rows
        ]

    def _run_query(self, sql: str, params: dict[str, Any]) -> list[dict]:
        client = self._get_client()
        job_config = self._build_job_config(params)
        return [dict(row) for row in client.query(sql, job_config=job_config).result()]

    @staticmethod
    def _build_job_config(params: dict[str, Any]):
        """組 QueryJobConfig；fake client（測試）回 None 即可忽略。"""
        try:
            from google.cloud import bigquery
        except ImportError:  # 測試環境（注入 fake client）不需真參數物件
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

    # ── 健康檢查（bq-smoke 零改碼轉真，見 diagnostics）─────────────────

    def health_check(self) -> bool:
        try:
            self._get_client().query("SELECT 1").result()
        except Exception:  # noqa: BLE001 — 健檢回 bool、不拋（診斷層分類 fail）
            return False
        return True
