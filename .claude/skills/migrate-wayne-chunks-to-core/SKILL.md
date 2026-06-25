---
name: migrate-wayne-chunks-to-core
description: Scan polaris_dev_wayne.chunks (vision-OCR presentation pilot, R1 Gate1 PASSED 2026-06-24) for chunk_ids not yet in polaris_core.chunks and ingest them as R4. Use when asked to sync/migrate/ingest wayne's dev chunks into polaris_core, or to run this on a recurring schedule until the source dataset stops growing.
---

# Migrate polaris_dev_wayne.chunks → polaris_core.chunks

Loads R4 (`@holajennytw`) is the only role permitted to write `polaris_core`
(constitution III). `polaris_dev_wayne.chunks` holds the vision-OCR-to-text
ingestion pilot (法說簡報 presentation pages, design:
`docs/superpowers/specs/2026-06-23-vision-ocr-to-text-ingestion-design.md`).
R1 Gate1 passed 2026-06-24 (128/128 numbers verified, 100% accuracy, see
GitHub issue #24) — vision chunks are cleared to land in canonical.

The source dataset is **still actively growing** (more tickers/quarters are
being pilot-ingested by R wayne over time), so this needs repeat runs, not a
single one-shot migration.

## What it does

Runs `scripts/migrate_wayne_chunks_to_core.py`, which:
1. Asserts `polaris_dev_wayne.chunks` only contains `doc_type=presentation`
   (warns, does not block, if that ever changes — e.g. a financial_statement
   page escalated to Pro extraction).
2. Dim-guards embeddings are 768 (same space as `polaris_core`, no reembed
   needed — unlike the 3072-dim jenny migration in
   `scripts/migrate_jenny_chunks_to_core.py`).
3. Computes `chunk_id NOT IN (SELECT chunk_id FROM polaris_core.chunks)` —
   only the delta gets written. Idempotent: safe to rerun every time, whether
   0 or thousands of rows are pending.
4. `INSERT ... SELECT` the delta into `polaris_core.chunks`.

## Usage

```bash
cd C:/polaris-desk-main
export GCP_PROJECT=polaris-desk-team
export BQ_ALLOW_CORE_WRITE=1          # R4-only unlock, constitution III / SOP §3.4
unset GOOGLE_APPLICATION_CREDENTIALS   # use gcloud ADC (holajennytw), NOT service_account_key.json —
                                       # that key's SA lacks read access to polaris_dev_wayne
uv run python scripts/migrate_wayne_chunks_to_core.py --dry-run   # plan first
uv run python scripts/migrate_wayne_chunks_to_core.py             # then write
```

Dry-run prints `待寫入：N 列` (pending row count) without writing. The real
run prints the same count then `完成：N 列已寫入 ...`.

**After a real (non-dry-run) ingest that writes 1+ rows**, re-apply
`migrations/2026-06-18_chunks_add_event_source_published_attrs_semantic.sql`
so `polaris_core.v_chunk_semantic` keeps tagging `doc_type=presentation` rows
with `event_key=earnings_call` / `source_key=PRIMARY_COMPANY_IR` instead of
NULL:

```bash
uv run python -c "
from google.cloud import bigquery
bq = bigquery.Client(project='polaris-desk-team')
sql = open('migrations/2026-06-18_chunks_add_event_source_published_attrs_semantic.sql', encoding='utf-8').read()
bq.query(sql).result()
print('view applied')
"
```

It's `CREATE OR REPLACE VIEW` — idempotent and safe to re-run every time,
including when there was nothing new to ingest.

## When running this on a recurring schedule

Each firing should just re-run the real (non-dry-run) command above, then
re-apply the view migration. Both steps are no-ops when there's nothing new
(`待寫入：0 列`, `CREATE OR REPLACE VIEW` re-applying the same SQL). There is no fixed end
condition encoded in the script itself, since wayne's pilot ingestion cadence
is external to this skill. The caller (cron prompt / human) decides when to
stop recurring — e.g. after a couple of consecutive `待寫入：0 列` runs once
wayne's pilot is declared complete.

## Notes

- This is a thin wrapper skill; all logic lives in
  `scripts/migrate_wayne_chunks_to_core.py` — edit the script, not this file,
  if the migration logic needs to change.
- Never write to `polaris_core` without `BQ_ALLOW_CORE_WRITE=1` — the script
  refuses otherwise.
