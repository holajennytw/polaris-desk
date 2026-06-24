"""Vision-OCR ingestion pilot（spec 2026-06-23）。

對 data/<ticker>_*/ 下的法說 PDF：逐頁 → vision 補圖表頁文字 → 切塊 → JSONL，
並產出 Gate1 報告（每頁 summary + confidence）供人工抽查。可選 --ingest 寫 dev dataset。

用法（GPU 不需要，純 Gemini API）：
  export GEMINI_USE_VERTEX=1 VISION_EXTRACTION=1
  uv pip install -e '.[vision]'
  uv run python scripts/vision_ingest_pilot.py --ticker 2330 --ticker 2891
  # 產出 data/vision_chunks/<ticker>.jsonl + data/vision_chunks/<ticker>_gate1.csv
  # 過 Gate1 後再 --ingest（寫 DEV_DATASET），polaris_core 由 R4 另行載入
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import re
from pathlib import Path


def _meta_from_filename(name: str) -> dict:
    # 2330_20250417M01_2025Q1_concall_presentation.pdf
    m = re.match(r"(?P<t>\d+)_(?P<d>\d{8})[ME]\d+_(?P<p>\w+?)_concall_(?P<dt>\w+)\.pdf", name)
    if not m:
        return {}
    d = m.group("d")
    return {"ticker": m.group("t"), "period": m.group("p"),
            "doc_type": m.group("dt"),
            "published_at": f"{d[:4]}-{d[4:6]}-{d[6:]}",
            "source": name}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", action="append", required=True)
    ap.add_argument("--out", default="data/vision_chunks")
    ap.add_argument("--ingest", action="store_true", help="寫 DEV dataset（非 polaris_core）")
    args = ap.parse_args()

    from polaris.config import settings
    from polaris.ingestion.chunker import chunk_pages
    from polaris.ingestion.vision_extract import active_vision_extractor
    from polaris.ingestion.vision_pages import extract_pages_with_vision

    extractor = active_vision_extractor()
    if extractor is None:
        print("⏳ vision gate 關（設 VISION_EXTRACTION=1 + 裝 .[vision]）。")
        return
    # 入庫前置防呆（不影響 JSONL/Gate1 產出——抽取仍會跑完）：
    #   1) 永不寫 canonical polaris_core（憲法 III）；2) embedding 恆需 api_key。
    do_ingest = args.ingest
    if do_ingest and settings.bq_dataset == "polaris_core":
        print("✋ --ingest 已停用：不可寫 polaris_core（憲法 III）。設 BQ_DATASET=polaris_dev_<name>"
              " 後重跑即可入庫；本次仍會產出 JSONL + Gate1。")
        do_ingest = False
    if do_ingest:
        from polaris.llm.gemini import active_llm
        if active_llm() is None:
            print("⏸ --ingest 已停用：embedding 恆走 GEMINI_API_KEY（憲法：與 polaris_core 768"
                  " 向量空間一致，Vertex/ADC 無法替代）。設好金鑰後重跑 --ingest；本次仍會產出"
                  " JSONL + Gate1。")
            do_ingest = False

    Path(args.out).mkdir(parents=True, exist_ok=True)
    for ticker in args.ticker:
        pdfs = sorted(glob.glob(f"data/{ticker}_*/{ticker}_*M*_concall_*.pdf"))
        all_chunks: list[dict] = []
        gate1_rows: list[dict] = []
        for pdf in pdfs:
            meta = _meta_from_filename(Path(pdf).name)
            if not meta:
                continue
            pages = extract_pages_with_vision(pdf, doc_type=meta["doc_type"], extractor=extractor)
            for i, txt in enumerate(pages, start=1):
                gate1_rows.append({"pdf": Path(pdf).name, "page": i,
                                   "text_preview": txt[:160].replace("\n", " ")})
            chunks = chunk_pages(pages, ticker=meta["ticker"], period=meta["period"],
                                 source=meta["source"], doc_type=meta["doc_type"],
                                 published_at=meta["published_at"])
            all_chunks.extend(chunks)
            print(f"  {Path(pdf).name}: {len(pages)} 頁 → {len(chunks)} 塊")

        jsonl = Path(args.out) / f"{ticker}.jsonl"
        jsonl.write_text("\n".join(json.dumps(c, ensure_ascii=False) for c in all_chunks),
                         encoding="utf-8")
        gate1 = Path(args.out) / f"{ticker}_gate1.csv"
        with gate1.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["pdf", "page", "text_preview"])
            w.writeheader()
            w.writerows(gate1_rows)
        print(f"{ticker}: {len(all_chunks)} 塊 → {jsonl}；Gate1 抽查表 → {gate1}")

        if do_ingest:
            from polaris.ingestion.pipeline import ingest_chunks
            from polaris.llm.gemini import active_llm
            from polaris.vectorstore import get_vector_store
            llm = active_llm()
            report = ingest_chunks(all_chunks, store=get_vector_store(),
                                   embed=llm.embed)
            print(f"  ingested {report.ingested} / quarantined {len(report.quarantined)}"
                  f" → {settings.bq_dataset}")


if __name__ == "__main__":
    main()
