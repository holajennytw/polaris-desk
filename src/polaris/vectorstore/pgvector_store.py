"""本地向量庫實作：Postgres + pgvector（離線 / Demo fallback，Plan B）。

- **conn 注入式 seam**：測試注入 fake connection → CI 0 DB 外呼、不需 psycopg；
  真環境延遲 import。
- **查詢一定用 ``<=>``（cosine）**：索引建在 ``vector_cosine_ops``，用錯
  ``<->``（L2）/ ``<#>``（內積）會退化全表掃描（scripts/init_pgvector.sql
  效能三條雷 §1–2）。
- 維度 768 / cosine 與 BigQuery 後端兩端一致（憲法 §Additional）。
"""
from __future__ import annotations

import json
from typing import Any

from .base import Document, SearchResult, VectorStore


def _vector_literal(embedding: list[float]) -> str:
    """list[float] → pgvector 字面值 ``[0.1,0.2,...]``。"""
    return "[" + ",".join(repr(float(x)) for x in embedding) + "]"


class PgVectorStore(VectorStore):
    def __init__(self, settings, *, conn=None) -> None:
        self.settings = settings
        self._conn = conn  # 注入（測試）或延遲連線（真環境）

    def _connect(self):
        """延遲建立連線（第一次用到才連）。"""
        if self._conn is None:
            import psycopg  # 延遲 import
            self._conn = psycopg.connect(self.settings.database_url)
        return self._conn

    def add_documents(self, docs: list[Document]) -> None:
        if not docs:
            return
        conn = self._connect()
        with conn.cursor() as cur:
            for d in docs:
                cur.execute(
                    """
                    INSERT INTO chunks (id, doc_id, company, period, content,
                                        embedding, metadata, owner, confidential)
                    VALUES (%s, %s, %s, %s, %s, %s::vector, %s::jsonb, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        doc_id = EXCLUDED.doc_id,
                        company = EXCLUDED.company,
                        period = EXCLUDED.period,
                        content = EXCLUDED.content,
                        embedding = EXCLUDED.embedding,
                        metadata = EXCLUDED.metadata,
                        owner = EXCLUDED.owner,
                        confidential = EXCLUDED.confidential
                    """,
                    (
                        d.id,
                        d.metadata.get("doc_id", d.id),
                        d.company,
                        d.period,
                        d.content,
                        _vector_literal(d.embedding or []),
                        json.dumps(d.metadata, ensure_ascii=False),
                        d.metadata.get("owner"),
                        bool(d.metadata.get("confidential", False)),
                    ),
                )
        conn.commit()

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 8,
        *,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        clauses, args = [], []
        for key in ("company", "period"):
            if filters and filters.get(key) is not None:
                clauses.append(f"{key} = %s")
                args.append(filters[key])
        viewer = filters.get("viewer") if filters else None
        if viewer is not None:
            clauses.append("(owner IS NULL OR owner = %s)")
            args.append(viewer)
            clauses.append("(NOT COALESCE(confidential, FALSE) OR owner = %s)")
            args.append(viewer)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        qe = _vector_literal(query_embedding)
        # ⚠️ 一定用 <=>（cosine）且 ORDER BY ... LIMIT 形式 → 走 HNSW 索引
        sql = f"""
            SELECT id, content, company, period, metadata,
                   1 - (embedding <=> %s::vector) AS score
            FROM chunks
            {where}
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute(sql, [qe, *args, qe, top_k])
            rows = cur.fetchall()
        return [
            SearchResult(
                id=r[0],
                content=r[1],
                company=r[2],
                period=r[3],
                metadata=(r[4] if isinstance(r[4], dict) else json.loads(r[4] or "{}")),
                score=float(r[5]),
            )
            for r in rows
        ]

    def health_check(self) -> bool:
        try:
            conn = self._connect()
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        except Exception:  # noqa: BLE001 — 健檢回 bool、不拋
            return False
        return True
