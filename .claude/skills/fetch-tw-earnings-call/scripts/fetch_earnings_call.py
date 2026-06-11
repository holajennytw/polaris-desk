#!/usr/bin/env python3
"""抓台股法說會簡報/逐字稿（中英），跨股票代號。

混合來源：vendor adapter（TodayIR…）+ MOPS 法人說明會一覽表底層 → md5 去重合併。
繞過 MOPS 反爬：直接打公司 IR 權威來源。輸出 data/<ticker>_<name>/ + manifest.json。
本檔含可單元測的純邏輯（dedupe / assign_filenames）與 I/O 編排（main）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import urllib.request
from collections import defaultdict
from datetime import date
from pathlib import Path

import ec_companies
import ec_mops
import ec_todayir
from ec_model import Doc, build_filename, parse_roc_date

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
ADAPTERS = [ec_todayir]


def http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 (trusted IR hosts)
        return r.read()


def download_blobs(docs: list[Doc], http_get) -> dict[str, bytes]:
    """逐 URL 下載；單筆失敗只警告略過，不讓整批失敗。"""
    blobs: dict[str, bytes] = {}
    for url in sorted({d.source_url for d in docs}):
        try:
            blobs[url] = http_get(url)
        except OSError as e:  # URLError/HTTPError 皆為 OSError 子類
            print(f"下載失敗，略過 {url}：{e}", file=sys.stderr)
    return blobs


def dedupe_by_content(docs: list[Doc], blobs: dict[str, bytes]) -> list[Doc]:
    """同內容（md5 相同）只留第一筆；blobs 以 source_url 取位元組。"""
    seen: set[str] = set()
    kept: list[Doc] = []
    for d in docs:
        data = blobs.get(d.source_url)
        if data is None:
            continue
        h = hashlib.md5(data).hexdigest()  # noqa: S324 (僅去重)
        if h in seen:
            continue
        seen.add(h)
        kept.append(d)
    return kept


def assign_filenames(docs: list[Doc], blobs: dict[str, bytes]) -> list[tuple[Doc, str]]:
    """去重後依 (event_date, lang) 給 001+ 流水並產生檔名。"""
    kept = dedupe_by_content(docs, blobs)
    counter: dict[tuple[str, str], int] = defaultdict(int)
    named: list[tuple[Doc, str]] = []
    for d in sorted(kept, key=lambda x: (x.fiscal_period, x.lang, x.source_url)):
        key = (d.event_date, d.lang)
        counter[key] += 1
        named.append((d, build_filename(d, counter[key])))
    return named


def merge_by_key(docs: list[Doc]) -> list[Doc]:
    """每 (fiscal_period, lang, doc_type) 只留一份；先到者優先（resolve_docs 讓 adapter 先於 MOPS）。

    處理跨來源同一場法說會的重複：TodayIR 與 MOPS 的同季同語言簡報即使位元組不同
    （重存版本），仍視為同一份，留公司 IR（adapter）那份。
    """
    best: dict[tuple[str, str, str], Doc] = {}
    order: list[tuple[str, str, str]] = []
    for d in docs:
        key = (d.fiscal_period, d.lang, d.doc_type)
        if key not in best:
            best[key] = d
            order.append(key)
    return [best[k] for k in order]


def event_date_from_pdf(pdf_bytes: bytes) -> tuple[str, str]:
    """用 pdftotext 抽首頁日期 → (ISO, 'pdf_first_page')；失敗回 ('', 'unknown')。"""
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        f.write(pdf_bytes)
        f.flush()
        try:
            txt = subprocess.run(
                ["pdftotext", "-f", "1", "-l", "1", "-layout", f.name, "-"],
                capture_output=True, text=True, check=False, timeout=30,
            ).stdout
        except (OSError, subprocess.SubprocessError):
            return "", "unknown"
    iso = parse_roc_date(txt)
    return (iso, "pdf_first_page") if iso else ("", "unknown")


def resolve_docs(ticker: str, years: list[int]) -> tuple[str, list[Doc]]:
    """跑命中的 vendor adapter + MOPS 底層，回 (company_name, docs)。"""
    info = ec_companies.lookup(ticker)
    docs: list[Doc] = []
    for ad in ADAPTERS:
        if info and ad.supports(ticker, info):
            docs += ad.fetch(ticker, years, http_get, info)
    docs += ec_mops.fetch(ticker, years, http_get)
    # 不在 registry 的代號 → 公司名取來源列表所載（MOPS 表有公司名稱欄）
    company = info["name"] if info else next((d.company for d in docs if d.company), ticker)
    return company, docs


def run(ticker: str, years: list[int], out_dir: Path) -> list[dict]:
    company, docs = resolve_docs(ticker, years)
    if not docs:
        print(f"查無 {ticker} 的法說會記錄（已試 vendor adapter + MOPS 底層）。", file=sys.stderr)
        return []
    blobs = download_blobs(docs, http_get)
    # 補 event_date（adapter 來源沒日期者，用 PDF 首頁）
    enriched: list[Doc] = []
    for d in docs:
        if not d.event_date and d.source_url in blobs:
            iso, src = event_date_from_pdf(blobs[d.source_url])
            d = Doc(**{**d.__dict__, "event_date": iso, "date_source": src})
        enriched.append(d)
    merged = merge_by_key(enriched)
    named = assign_filenames(merged, blobs)

    out_dir.mkdir(parents=True, exist_ok=True)
    fetched_at = date.today().isoformat()
    manifest: list[dict] = []
    n_transcript = 0
    for d, fname in named:
        data = blobs[d.source_url]
        (out_dir / fname).write_bytes(data)
        n_transcript += d.doc_type == "transcript"
        manifest.append({
            "file": fname, "ticker": d.ticker, "company": company,
            "doc_type": d.doc_type, "fiscal_period": d.fiscal_period, "lang": d.lang,
            "event_date": d.event_date, "date_source": d.date_source,
            "source_url": d.source_url, "source_page": d.source_page,
            "fetched_at": fetched_at, "md5": hashlib.md5(data).hexdigest(),  # noqa: S324
            "bytes": len(data),
        })
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"下載 {len(manifest)} 份到 {out_dir}/（presentation {len(manifest)-n_transcript}、transcript {n_transcript}）")
    if n_transcript == 0:
        print(f"註：{company}（{ticker}）無公開 transcript，manifest 僅列簡報。")
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", required=True)
    ap.add_argument("--from", dest="y_from", type=int, default=2021)
    ap.add_argument("--to", dest="y_to", type=int, default=date.today().year)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    years = list(range(args.y_from, args.y_to + 1))
    info = ec_companies.lookup(args.ticker)
    name = info["name"] if info else args.ticker
    out = Path(args.out) if args.out else Path("data") / f"{args.ticker}_{name}"
    run(args.ticker, years, out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
