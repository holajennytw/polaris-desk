#!/usr/bin/env python3
"""把 polaris_dev_wayne.chunks（vision-OCR pilot 產物）遷移進 polaris_core.chunks。

背景：vision-OCR-to-text ingestion（見
docs/superpowers/specs/2026-06-23-vision-ocr-to-text-ingestion-design.md）已過
R1 Gate1（2026-06-24，128 個數字、100% 準確率，見 GitHub issue #24），正式放行
vision chunk 寫入 polaris_core。本腳本由 R4 執行載入。

來源只有一張表、已是 768 維（同 canonical schema），故不像
scripts/migrate_jenny_chunks_to_core.py 需要拆 3072 維隔離表。

寫入用 ``INSERT ... SELECT ... WHERE chunk_id NOT IN (...)``，chunk_id 已存在則跳過
——可重跑 upsert，也適合配 `/loop` 每小時重跑、邊掃描邊補新寫入的 chunk。

doc_type 守門：vision-OCR pilot 目前只產 ``presentation``；若來源出現其他
doc_type（例如 financial_statement 升 Pro 抽取的頁面），先印警告不擋（之後放大
範圍時這條會自然變寬，不需要每次改腳本）。

寫 ``polaris_core`` 需 ``BQ_ALLOW_CORE_WRITE=1``（憲法 III / SOP §3.4，R1/R4 限定）。

用法：
    python scripts/migrate_wayne_chunks_to_core.py --dry-run   # 只盤點，不寫入
    python scripts/migrate_wayne_chunks_to_core.py             # 實際遷移（可重跑）
"""
from __future__ import annotations

import argparse
import sys

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

from polaris.config import settings

SOURCE_DATASET = "polaris_dev_wayne"
CORE_DATASET = "polaris_core"
EXPECTED_DIM = 768

CANONICAL_COLUMNS = (
    "chunk_id, ticker, doc_type, fiscal_period, published_at, "
    "chunk_text, embedding, owner, confidential"
)


def _dim_guard(bq, table: str, expected_dim: int) -> int:
    """回傳 ARRAY_LENGTH(embedding) != expected_dim 的列數（應為 0）。"""
    row = list(bq.query(
        f"SELECT COUNTIF(ARRAY_LENGTH(embedding) != {expected_dim}) bad "
        f"FROM `{table}`"
    ).result())[0]
    return row["bad"]


def _doc_type_check(bq, table: str) -> None:
    rows = list(bq.query(
        f"SELECT DISTINCT doc_type FROM `{table}`"
    ).result())
    types = sorted(r["doc_type"] for r in rows)
    if types != ["presentation"]:
        print(f"⚠️  {table} 含非預期 doc_type：{types}（pilot 文件記載只應有 presentation，請確認來源）")
    else:
        print(f"doc_type 檢查通過：{table} 只有 presentation（{len(types)} 種）")


def _pending_count(bq, src: str, dst: str) -> int:
    row = list(bq.query(f"""
        SELECT COUNT(*) n
        FROM `{src}` s
        WHERE s.chunk_id NOT IN (
            SELECT chunk_id FROM `{dst}`
        )
    """).result())[0]
    return row["n"]


def _migrate(bq, project: str, *, dry_run: bool) -> int:
    src = f"{project}.{SOURCE_DATASET}.chunks"
    dst = f"{project}.{CORE_DATASET}.chunks"

    print(f"\n=== {src} -> {dst} ===")
    _doc_type_check(bq, src)

    bad = _dim_guard(bq, src, EXPECTED_DIM)
    if bad:
        sys.exit(f"維度守門失敗：{src} 有 {bad} 列 embedding 不是 {EXPECTED_DIM} 維，拒絕遷移")

    pending = _pending_count(bq, src, dst)
    print(f"待寫入：{pending} 列（{src} 中 chunk_id 尚未存在於 {dst}）")
    if dry_run or pending == 0:
        return pending

    bq.query(f"""
        INSERT INTO `{dst}` ({CANONICAL_COLUMNS})
        SELECT {CANONICAL_COLUMNS}
        FROM `{src}` s
        WHERE s.chunk_id NOT IN (SELECT chunk_id FROM `{dst}`)
    """).result()
    print(f"完成：{pending} 列已寫入 {dst}")
    return pending


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="只盤點，不寫入")
    args = parser.parse_args()

    if not args.dry_run and not settings.bq_allow_core_write:
        sys.exit("拒寫 polaris_core：需 BQ_ALLOW_CORE_WRITE=1（憲法 III / SOP §3.4，R1/R4 限定）")

    from google.cloud import bigquery  # 延遲 import（同 store 層慣例）

    bq = bigquery.Client(project=settings.gcp_project)
    _migrate(bq, settings.gcp_project, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
