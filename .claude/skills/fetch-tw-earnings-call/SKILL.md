---
name: fetch-tw-earnings-call
description: Download Taiwan-listed companies' earnings-call (法說會) presentations and transcripts (Chinese + English) by ticker. Use when the user wants to fetch 法說會/法人說明會 簡報 or 逐字稿 for a TWSE/TPEx ticker (e.g. 2891 中信金, 2330 台積電), or mentions 公開資訊觀測站/MOPS being blocked for crawling. Bypasses MOPS anti-crawling by hitting authoritative IR sources directly.
---

# Fetch Taiwan Earnings-Call Materials

Downloads 法說會 (investor conference) **presentations** and **transcripts** for a given
ticker, Chinese and English, into `data/<ticker>_<name>/` with a `manifest.json`
that carries source provenance (引用接地, R4).

## Why not MOPS scraping
公開資訊觀測站 (MOPS) blocks aggressive crawling. This skill instead hits **authoritative
sources**: the company's IR site via a per-vendor adapter (richer — zh+en + transcript when
published) plus the MOPS 法人說明會一覽表 as a generic base that works for any ticker.
Results merge and dedupe by content md5.

## Usage
```bash
python3 .claude/skills/fetch-tw-earnings-call/scripts/fetch_earnings_call.py \
    --ticker 2891 --from 2021 --to 2026
# output: data/2891_中信金控/<files>.pdf + manifest.json
```

Options: `--ticker` (required), `--from`/`--to` (year range, default 2021..current),
`--out` (default `data/<ticker>_<name>`).

## Output naming
`<ticker>_<yyyymmdd><L><nn>_<period>_concall_<doctype>.pdf`
- `yyyymmdd` = 法說會 held date (from PDF first page; falls back to source listing date)
- `L` = `M` (中文) / `E` (英文); `nn` = per (ticker, date, lang) sequence from 01
- `period` = `YYYYQn`; `doctype` = `presentation` | `transcript`
- e.g. `2891_20260519M01_2026Q1_concall_presentation.pdf`

## Coverage
Companies in the registry (`ec_companies.py`) with a vendor adapter get zh+en + transcript.
Other tickers fall back to the MOPS base (presentation only, zh+en) — no registry entry
needed; the company name comes from the MOPS listing. To add a company, extend the
registry and (if a new IR vendor) add an adapter under `scripts/`.

## Notes
- Most TW companies do **not** publish transcripts; the skill fetches them only when present
  and notes their absence in the run summary. It never fabricates a manifest entry.
- Subject without 「第X季」 (e.g. 台塑化「說明近期營運概況」) → period inferred from the
  filename date as the most recently completed quarter; an explicit quarter in any subject
  for the same file wins.
- Failed downloads are warned on stderr and skipped; the rest of the batch still completes.
- This skill only downloads + writes a manifest. Parsing/chunking/embedding is R4 ingestion.
