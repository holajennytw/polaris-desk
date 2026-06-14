#!/usr/bin/env python3
"""把 3072 維隔離 chunks 重算成 768 維後補進 canonical chunks 表。

背景（PR #68 缺口 #1）：jenny 的 96 筆 transcript chunks 用 3072 維入庫，
違反憲法 768/cosine，合併時隔離在
``polaris_dev_wayne_staging.chunks_pending_reembed``（原向量保留）。
本腳本給 **GEMINI_API_KEY 持有者**一鍵補課：

    讀 <source>.chunks_pending_reembed → gemini-embedding-2 @768 重算
    → APPEND 進 <target>.chunks（已存在的 chunk_id 自動跳過，可重跑）

依 repo 既有契約：金鑰/模型/維度全走 ``polaris.config.settings``（.env）；
寫 ``polaris_core`` 仍須 ``BQ_ALLOW_CORE_WRITE=1``（憲法 III，與 BigQueryStore
同一道防呆）——一般人寫自己的 staging/scratch 即可。

用法：
    python scripts/reembed_pending_chunks.py --dry-run      # 只盤點，不花 token
    python scripts/reembed_pending_chunks.py                # staging 補課（預設）
    python scripts/reembed_pending_chunks.py --target-dataset polaris_core  # R1/R4
"""
from __future__ import annotations

import argparse
import sys
import time

from polaris.config import settings
from polaris.llm.gemini import GeminiClient, available

#: 免費層 gemini-embedding-2 配額 100 req/min → 留安全邊際節流到 ~75 req/min。
_PACE_SECONDS = 0.8


def _embed_with_retry(llm: GeminiClient, text: str, *, max_retries: int = 5) -> list[float]:
    """單筆 embed＋429 退避重試（免費層 per-minute 配額用完就等下一個窗口）。"""
    for attempt in range(max_retries):
        try:
            return llm.embed(text)
        except Exception as e:  # noqa: BLE001 — 只攔 429，其他照拋
            if "429" not in str(e) or attempt == max_retries - 1:
                raise
            wait = 20 * (attempt + 1)
            print(f"  429 quota，等 {wait}s 後重試（{attempt + 1}/{max_retries}）")
            time.sleep(wait)
    raise RuntimeError("unreachable")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-dataset", default="polaris_dev_wayne_staging",
        help="隔離表所在 dataset（表名固定 chunks_pending_reembed）",
    )
    parser.add_argument(
        "--target-dataset", default="polaris_dev_wayne_staging",
        help="重算後寫入的 dataset（表名固定 chunks）",
    )
    parser.add_argument("--dry-run", action="store_true", help="只盤點待辦列數，不呼叫 API")
    args = parser.parse_args()

    if args.target_dataset == "polaris_core" and not settings.bq_allow_core_write:
        sys.exit("拒寫 polaris_core：需 BQ_ALLOW_CORE_WRITE=1（憲法 III，R1/R4 限定）")

    from google.cloud import bigquery  # 延遲 import（同 store 層慣例）

    project = settings.gcp_project
    src = f"{project}.{args.source_dataset}.chunks_pending_reembed"
    dst = f"{project}.{args.target_dataset}.chunks"
    bq = bigquery.Client(project=project)

    pending = list(bq.query(f"""
        SELECT p.chunk_id, p.ticker, p.doc_type, p.fiscal_period,
               p.published_at, p.chunk_text
        FROM `{src}` p
        LEFT JOIN `{dst}` c USING (chunk_id)
        WHERE c.chunk_id IS NULL
          AND p.chunk_text IS NOT NULL AND TRIM(p.chunk_text) != ''
        ORDER BY p.chunk_id
    """).result())
    print(f"待重算：{len(pending)} 列（{src} → {dst}）")
    if args.dry_run or not pending:
        return 0

    if not available():
        sys.exit("缺 GEMINI_API_KEY（.env）——本腳本要重算 embedding，無金鑰無法執行")
    assert settings.embedding_dim == 768, f"EMBEDDING_DIM={settings.embedding_dim}，憲法定 768"

    llm = GeminiClient()
    rows = []
    for i, r in enumerate(pending):
        emb = _embed_with_retry(llm, r["chunk_text"])
        time.sleep(_PACE_SECONDS)
        assert len(emb) == settings.embedding_dim, (r["chunk_id"], len(emb))
        rows.append({
            "chunk_id": r["chunk_id"],
            "ticker": r["ticker"],
            "doc_type": r["doc_type"],
            "fiscal_period": r["fiscal_period"],
            "published_at": r["published_at"].isoformat() if r["published_at"] else None,
            "chunk_text": r["chunk_text"],
            "embedding": emb,
        })
        if (i + 1) % 20 == 0:
            print(f"  embedded {i + 1}/{len(pending)}")

    job_config = bigquery.LoadJobConfig(
        write_disposition="WRITE_APPEND",
        schema=[
            bigquery.SchemaField("chunk_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("ticker", "STRING"),
            bigquery.SchemaField("doc_type", "STRING"),
            bigquery.SchemaField("fiscal_period", "STRING"),
            bigquery.SchemaField("published_at", "DATE"),
            bigquery.SchemaField("chunk_text", "STRING"),
            bigquery.SchemaField("embedding", "FLOAT64", mode="REPEATED"),
        ],
    )
    bq.load_table_from_json(rows, dst, job_config=job_config).result()
    print(f"完成：{len(rows)} 列已寫入 {dst}（768 維）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
