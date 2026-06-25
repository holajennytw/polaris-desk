"""Vision-OCR 全量入庫 — Vertex Batch Prediction（非同步、繞過 QPM、單價較低）。

線上即時路（vision_ingest_pilot.py）撞 gemini-3-preview 的每分鐘配額會很慢；本腳本
改用 **Batch Prediction**：把所有頁渲成 PNG → 組成 GCS 上的請求 JSONL → 提交一個批次
作業 → 後台高吞吐跑完 → 下載輸出 → 解析 → 切塊 → 入 dev dataset。

⚠️ 重要：
- Vertex batch 需 **GCS 來源/輸出** 與 **regional endpoint**（非 global）＋ **batch 支援的
  GA 模型**（preview 模型多半不支援 batch）。故本腳本用 `--model`（預設 GA flash）＋
  `--location`（預設 us-central1），與線上路的 global/preview 不同。
- 寫入只進 dev dataset（`BQ_DATASET`，非 polaris_core）；embedding 仍需 `GEMINI_API_KEY`。
- 本腳本為**離線一次性**、重 I/O，不進 CI；純資料轉換在 `polaris.ingestion.vision_batch`
  （已單測）。Batch 輸出檔名/格式以**首次實跑**為準，必要時依實際輸出微調解析。

用法：
  export GEMINI_API_KEY=$(gcloud secrets versions access latest --secret=gemini-api-key --project=polaris-desk-team)
  uv pip install -e '.[vision]'
  uv run python scripts/vision_batch_ingest.py --ticker 2330 --ticker 2891 \
      --gcs-bucket gs://<bucket> --model gemini-2.5-flash --location us-central1 --ingest
"""
from __future__ import annotations

import argparse
import glob
import json
import re
import time
from pathlib import Path


def _meta_from_filename(name: str) -> dict:
    # [ME] 前允許可選底線：部分 GDrive 策展檔名為 2317_20250514_M002_... 格式。
    m = re.match(r"(?P<t>\d+)_(?P<d>\d{8})_?[ME]\d+_(?P<p>\w+?)_concall_(?P<dt>\w+)\.pdf", name)
    if not m:
        return {}
    d = m.group("d")
    return {"ticker": m.group("t"), "period": m.group("p"), "doc_type": m.group("dt"),
            "published_at": f"{d[:4]}-{d[4:6]}-{d[6:]}", "source": name}


_VISION_PROMPT = (
    "你是財報投影片『轉錄器』。只轉錄這張投影片上看得到的文字與數字，不要推論、不要計算、"
    "不要補充頁面上沒有的東西。每個圖表的標籤與數值、單位如實抽出；有表格轉成 markdown。"
    "看不清的數值填 null。"
    "confidence 用 0 到 1 之間的小數表示整體把握度（1=非常確定，不是百分比、不是 1–5 分）。"
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", action="append", required=True)
    ap.add_argument("--gcs-bucket", required=True, help="gs://bucket[/prefix]（batch 來源/輸出）")
    ap.add_argument("--model", default="gemini-2.5-flash", help="batch 支援的 GA 模型")
    ap.add_argument("--location", default="us-central1", help="Vertex batch regional endpoint")
    ap.add_argument("--dpi", type=int, default=150)
    ap.add_argument("--poll", type=int, default=60, help="輪詢間隔秒")
    ap.add_argument("--ingest", action="store_true", help="解析後寫 DEV dataset（非 polaris_core）")
    args = ap.parse_args()

    from polaris.config import settings
    from polaris.ingestion.chunker import chunk_pages
    from polaris.ingestion.vision_batch import build_request_line, parse_response_line
    from polaris.ingestion.vision_extract import render_page
    from polaris.ingestion.vision_to_text import flatten_extraction, should_vision_route

    if args.ingest and settings.bq_dataset == "polaris_core":
        print("✋ 拒絕：--ingest 不可寫 polaris_core（憲法 III）。請設 BQ_DATASET=polaris_dev_<name>。")
        return

    try:
        from google import genai
        from google.cloud import storage
    except ImportError as exc:
        print(f"⏳ 需要 google-genai + google-cloud-storage + .[vision]：{exc}")
        return

    base = args.gcs_bucket.rstrip("/")
    bucket_name = base.split("/")[2]
    prefix = "/".join(base.split("/")[3:]) or "vision_batch"
    gcs = storage.Client(project=settings.gcp_project)
    bucket = gcs.bucket(bucket_name)
    client = genai.Client(vertexai=True, project=settings.gcp_project, location=args.location)

    for ticker in args.ticker:
        pdfs = sorted(glob.glob(f"data/{ticker}_*/{ticker}_*M*_concall_*.pdf"))
        # 1) 渲染所有 vision 頁、組請求行 + 同序 manifest
        lines: list[str] = []
        manifest: list[dict] = []  # 與 lines 同序：{pdf, page, doc_type, ...}
        pdf_pages: dict[str, list[str]] = {}     # pdf -> 每頁 page_text（文字頁先填 pypdf）
        from polaris.ingestion.chunker import extract_pages
        for pdf in pdfs:
            meta = _meta_from_filename(Path(pdf).name)
            if not meta:
                continue
            texts = extract_pages(pdf)
            pdf_pages[pdf] = list(texts)
            for i, text in enumerate(texts, start=1):
                if should_vision_route(text, doc_type=meta["doc_type"]):
                    png = render_page(pdf, i, dpi=args.dpi)
                    lines.append(json.dumps(build_request_line(png, prompt=_VISION_PROMPT)))
                    manifest.append({"pdf": pdf, "page": i})
        if not lines:
            print(f"{ticker}: 無 vision 頁，跳過")
            continue
        print(f"{ticker}: {len(lines)} 個請求 → 上傳 GCS", flush=True)

        # 2) 上傳輸入 JSONL
        in_blob = bucket.blob(f"{prefix}/{ticker}/input.jsonl")
        in_blob.upload_from_string("\n".join(lines), content_type="application/jsonl")
        src_uri = f"gs://{bucket_name}/{prefix}/{ticker}/input.jsonl"
        dest_uri = f"gs://{bucket_name}/{prefix}/{ticker}/output/"

        # 3) 提交 batch + 輪詢
        from google.genai import types
        job = client.batches.create(
            model=args.model, src=src_uri,
            config=types.CreateBatchJobConfig(dest=dest_uri),
        )
        print(f"  batch job: {job.name} state={job.state}", flush=True)
        terminal = {"JOB_STATE_SUCCEEDED", "JOB_STATE_FAILED", "JOB_STATE_CANCELLED",
                    "JOB_STATE_EXPIRED"}
        while str(job.state).split(".")[-1] not in terminal:
            time.sleep(args.poll)
            job = client.batches.get(name=job.name)
            print(f"  ...{job.state}", flush=True)
        if "SUCCEEDED" not in str(job.state):
            print(f"  ✗ batch 未成功：{job.state}；跳過 {ticker}")
            continue

        # 4) 下載輸出（保序）→ 解析 → 回填每頁文字
        out_blobs = sorted(gcs.list_blobs(bucket_name, prefix=f"{prefix}/{ticker}/output/"),
                           key=lambda b: b.name)
        resp_lines: list[dict] = []
        for b in out_blobs:
            if b.name.endswith(".jsonl") or "prediction" in b.name:
                for ln in b.download_as_text().splitlines():
                    if ln.strip():
                        resp_lines.append(json.loads(ln))
        if len(resp_lines) != len(manifest):
            print(f"  ⚠️ 輸出 {len(resp_lines)} 行 ≠ 請求 {len(manifest)} 行；依序對應、缺者留空")
        for entry, resp in zip(manifest, resp_lines):
            pe = parse_response_line(resp)
            entry["text"] = flatten_extraction(pe) if pe is not None else ""
        # 把 vision 頁文字回填到 pdf_pages（其餘頁維持 pypdf 文字）
        for entry in manifest:
            if "text" in entry:
                pdf_pages[entry["pdf"]][entry["page"] - 1] = entry["text"]

        # 5) 切塊
        all_chunks: list[dict] = []
        for pdf, pages in pdf_pages.items():
            meta = _meta_from_filename(Path(pdf).name)
            all_chunks.extend(chunk_pages(
                pages, ticker=meta["ticker"], period=meta["period"], source=meta["source"],
                doc_type=meta["doc_type"], published_at=meta["published_at"]))
        Path("data/vision_chunks").mkdir(parents=True, exist_ok=True)
        out_jsonl = Path("data/vision_chunks") / f"{ticker}_batch.jsonl"
        out_jsonl.write_text("\n".join(json.dumps(c, ensure_ascii=False) for c in all_chunks),
                             encoding="utf-8")
        print(f"{ticker}: {len(all_chunks)} 塊 → {out_jsonl}", flush=True)

        # 6) 入庫（dev）
        if args.ingest:
            from polaris.ingestion.pipeline import ingest_chunks
            from polaris.llm.gemini import active_llm
            from polaris.vectorstore import get_vector_store
            llm = active_llm()
            if llm is None:
                print("  ⏸ 跳過入庫：需 GEMINI_API_KEY（embedding）。JSONL 已產出。")
                continue
            rep = ingest_chunks(all_chunks, store=get_vector_store(), embed=llm.embed)
            print(f"  ingested {rep.ingested} / quarantined {len(rep.quarantined)}"
                  f" → {settings.bq_dataset}", flush=True)


if __name__ == "__main__":
    main()
