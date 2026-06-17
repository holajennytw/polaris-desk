"""Ingest a TW ticker's Chinese 法說會 presentations into the configured
BigQuery dataset (intended: polaris_core with BQ_ALLOW_CORE_WRITE=1).

Fetch (if missing) → chunk (doc_type=presentation, published_at) → embed (768) →
write. Idempotent: skips any (ticker, period) already present as a presentation.

The fetch skill *sometimes* mislabels the fiscal year by +89 in the filename
(e.g. 1935Q1 = 2024Q1); we correct any period whose year falls outside 2020–2027
BEFORE chunking, so chunk_id / fiscal_period are right from the start (no post-hoc
relabel, no collision with existing rows). Periods already in range pass through.

Usage (from repo root):
    BQ_ALLOW_CORE_WRITE=1 .venv/bin/python scripts/ingest_ticker.py 2324
    BQ_ALLOW_CORE_WRITE=1 .venv/bin/python scripts/ingest_ticker.py 2330 --periods 2024Q1,2024Q2,2024Q3,2024Q4
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import subprocess
import sys
import time

from google.cloud import bigquery

from polaris.config import settings
from polaris.ingestion.chunker import chunk_pages, extract_pages
from polaris.ingestion.pipeline import ingest_chunks
from polaris.llm.gemini import active_llm
from polaris.vectorstore import get_vector_store

FETCH = ".claude/skills/fetch-tw-earnings-call/scripts/fetch_earnings_call.py"
FN = re.compile(
    r"^(\d+)_(\d{8})([ME])(\d+)_(\d{4}Q\d)_concall_(presentation|transcript)\.pdf$"
)
PACE = 0.7  # ~85 embeds/min, under free-tier 100/min


def correct_period(raw: str) -> str:
    """Fix the fetch-skill +89-year bug: 1935Q1 → 2024Q1. In-range periods unchanged."""
    year = int(raw[:4])
    return f"{year + 89}{raw[4:]}" if not (2020 <= year <= 2027) else raw


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="ingest_ticker")
    ap.add_argument("ticker")
    ap.add_argument("--periods", default="",
                    help="comma-separated CORRECTED periods to keep (e.g. 2024Q1,2024Q2); "
                         "empty = all Chinese presentations found")
    ap.add_argument("--from", dest="yr_from", default="2024")
    ap.add_argument("--to", dest="yr_to", default="2025")
    args = ap.parse_args(argv)

    ticker = args.ticker
    want = {p.strip() for p in args.periods.split(",") if p.strip()}

    client = active_llm()
    if client is None:
        print("❌ no GEMINI_API_KEY", file=sys.stderr)
        return 1
    store = get_vector_store()
    bq = bigquery.Client(project=settings.gcp_project)
    DS = f"{settings.gcp_project}.{settings.bq_dataset}.chunks"
    print(f"target: {ticker} → {settings.bq_dataset} "
          f"(allow_core_write={getattr(settings, 'bq_allow_core_write', False)})", flush=True)

    # Probe embedding quota before doing any work.
    try:
        client.embed("配額探測")
    except Exception as exc:  # noqa: BLE001
        if "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc):
            print("❌ embedding quota exhausted (429) — retry later. Nothing ingested.",
                  file=sys.stderr)
            return 2
        raise

    def paced_embed(text: str) -> list[float]:
        v = client.embed(text)
        time.sleep(PACE)
        return v

    def already(period: str) -> bool:
        job = bq.query(
            f"SELECT COUNT(*) c FROM `{DS}` "
            "WHERE ticker=@t AND fiscal_period=@p AND doc_type='presentation'",
            job_config=bigquery.QueryJobConfig(query_parameters=[
                bigquery.ScalarQueryParameter("t", "STRING", ticker),
                bigquery.ScalarQueryParameter("p", "STRING", period),
            ]),
        )
        return next(iter(job)).c > 0

    dirs = glob.glob(f"data/{ticker}_*")
    if not dirs:
        print(f"[{ticker}] fetching…", flush=True)
        subprocess.run([sys.executable, FETCH, "--ticker", ticker,
                        "--from", args.yr_from, "--to", args.yr_to], check=False)
        dirs = glob.glob(f"data/{ticker}_*")
    if not dirs:
        print(f"[{ticker}] NO DATA after fetch", file=sys.stderr)
        return 3

    # one Chinese presentation per corrected period
    by_period: dict[str, tuple[str, str]] = {}
    for pdf in sorted(glob.glob(f"{dirs[0]}/*.pdf")):
        m = FN.match(os.path.basename(pdf))
        if not m:
            continue
        _tk, date, lang, _nn, raw_period, doctype = m.groups()
        if lang != "M" or doctype != "presentation":
            continue
        period = correct_period(raw_period)
        if want and period not in want:
            continue
        by_period.setdefault(period, (pdf, date))

    if not by_period:
        print(f"[{ticker}] no matching Chinese presentations", flush=True)
        return 0

    total = 0
    for period, (pdf, date) in sorted(by_period.items()):
        if already(period):
            print(f"[{ticker} {period}] exists — skip", flush=True)
            continue
        published = f"{date[:4]}-{date[4:6]}-{date[6:8]}"
        pages = extract_pages(pdf)
        chunks = chunk_pages(pages, ticker=ticker, period=period,
                             source=os.path.basename(pdf),
                             doc_type="presentation", published_at=published)
        if not chunks:
            print(f"[{ticker} {period}] 0 chunks (scanned?) — skip", flush=True)
            continue
        rep = ingest_chunks(chunks, store=store, embed=paced_embed)
        total += rep.ingested
        q = f" quarantine={len(rep.quarantined)}" if rep.quarantined else ""
        print(f"[{ticker} {period}] ingested {rep.ingested}/{rep.total}{q} "
              f"(pub {published})", flush=True)

    print(f"DONE — {ticker}: total newly ingested {total} chunks into {settings.bq_dataset}",
          flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
