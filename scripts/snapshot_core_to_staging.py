#!/usr/bin/env python3
"""把 polaris_core 的所有表複製一份快照進 polaris_dev_wayne_staging。

每張來源表 `<table>` 會複製成 `<table>_<MMDD>_v<n>`：
- MMDD：今天日期（UTC+8，Asia/Taipei）
- v<n>：同一天重跑會自動遞增版號（不覆寫已存在的快照）

用 BigQuery Table Copy job（非 CTAS），完整保留 schema / partitioning / clustering。
只讀 `polaris_core`、只寫自己的 `polaris_dev_wayne_staging`，不需要
``BQ_ALLOW_CORE_WRITE``（沒有寫 polaris_core）。

用法：
    python scripts/snapshot_core_to_staging.py --dry-run   # 只列出會建立的快照表
    python scripts/snapshot_core_to_staging.py             # 實際複製
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

from polaris.config import settings

SOURCE_DATASET = "polaris_core"
TARGET_DATASET = "polaris_dev_wayne_staging"


def _today_mmdd_utc8() -> str:
    return datetime.now(ZoneInfo("Asia/Taipei")).strftime("%m%d")


def _next_version(bq, project: str, table: str, mmdd: str) -> int:
    prefix = f"{table}_{mmdd}_v"
    rows = bq.query(f"""
        SELECT table_name
        FROM `{project}.{TARGET_DATASET}.INFORMATION_SCHEMA.TABLES`
        WHERE table_name LIKE '{prefix}%'
    """).result()
    versions = []
    for r in rows:
        suffix = r["table_name"][len(prefix):]
        if suffix.isdigit():
            versions.append(int(suffix))
    return max(versions, default=0) + 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="只列出會建立的快照表，不複製")
    args = parser.parse_args()

    from google.cloud import bigquery  # 延遲 import（同 store 層慣例）

    project = settings.gcp_project
    bq = bigquery.Client(project=project)

    tables = list(bq.query(f"""
        SELECT table_name
        FROM `{project}.{SOURCE_DATASET}.INFORMATION_SCHEMA.TABLES`
        WHERE table_type = 'BASE TABLE'
        ORDER BY table_name
    """).result())
    if not tables:
        print(f"{SOURCE_DATASET} 沒有表，沒事可做")
        return 0

    mmdd = _today_mmdd_utc8()
    print(f"快照日期（UTC+8）：{mmdd} ｜ {SOURCE_DATASET} -> {TARGET_DATASET}")

    for row in tables:
        table = row["table_name"]
        version = _next_version(bq, project, table, mmdd)
        dst_table = f"{table}_{mmdd}_v{version}"
        src_ref = f"{project}.{SOURCE_DATASET}.{table}"
        dst_ref = f"{project}.{TARGET_DATASET}.{dst_table}"
        print(f"  {src_ref} -> {dst_ref}")
        if args.dry_run:
            continue
        job_config = bigquery.CopyJobConfig(write_disposition="WRITE_EMPTY")
        bq.copy_table(src_ref, dst_ref, job_config=job_config).result()

    if args.dry_run:
        print(f"\n（dry-run）共 {len(tables)} 張表待複製")
    else:
        print(f"\n完成：{len(tables)} 張表已複製進 {TARGET_DATASET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
