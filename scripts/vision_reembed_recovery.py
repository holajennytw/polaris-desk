"""Vision 入庫補救：把 data/vision_chunks/*.jsonl 中「尚未進 BQ」的塊批次 re-embed 後補入。

背景：線上 pilot 以 concurrency 抽取＋逐塊 embed，會在 AI Studio 免費層
`embed_content_free_tier_requests`（1000 req/分鐘）上爆量 → 後段塊全被 quarantine。
但**視覺抽取結果已落地 JSONL**（昂貴的那步已完成），故補救無需重抽：

  1. 掃 data/vision_chunks/<ticker>.jsonl（所有或 --ticker 指定）。
  2. 查 BQ 已存在的 chunk_id（同一 dataset），只挑「缺的」。
  3. **批次** embed（一個請求帶 contents=[...] 多筆 → 1 request 抵 N 筆，遠低於 1000/分）。
  4. sanitize/validate 後組 Document，經 get_vector_store() 補入（idempotent upsert）。

憲法：embedding 仍走 AI Studio api_key（gemini-embedding-2 / 768），與 polaris_core 向量空間一致；
寫入只進 dev dataset（BQ_DATASET，非 polaris_core——store 層另有防呆）。

用法：
  export GEMINI_API_KEY=$(gcloud secrets versions access latest --secret=gemini-api-key --project=polaris-desk-team)
  export BQ_DATASET=polaris_dev_wayne VECTOR_BACKEND=bigquery
  uv run python scripts/vision_reembed_recovery.py            # 全部 JSONL
  uv run python scripts/vision_reembed_recovery.py --ticker 2881 --ticker 2454
"""
from __future__ import annotations

import argparse
import glob
import json
import time
from pathlib import Path


def _embed_batch_fn(keys: list[str], *, model: str, dim: int):
    """回傳 embed_many(texts)->list[vec]；多把 key 輪替、429 換把。"""
    from google import genai
    from google.genai import types

    from polaris.retry import call_with_retry, is_quota_error

    clients = [genai.Client(api_key=k) for k in keys]

    def _one_request(texts: list[str]) -> list[list[float]]:
        last_exc = None
        for c in clients:  # 逐把試，429 配額爆了換下一把
            try:
                resp = c.models.embed_content(
                    model=model, contents=texts,
                    config=types.EmbedContentConfig(output_dimensionality=dim),
                )
                return [list(e.values) for e in resp.embeddings]
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if not is_quota_error(exc):
                    raise
        assert last_exc is not None
        raise last_exc

    def embed_many(texts: list[str]) -> list[list[float]]:
        # 全把都 429 → call_with_retry 退避重試（免費層分鐘窗，視窗較長）。
        return call_with_retry(lambda: _one_request(texts),
                               attempts=8, base_delay=5.0, max_delay=70.0)

    return embed_many


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", action="append", help="只補這些 ticker（預設全部 JSONL）")
    ap.add_argument("--dir", default="data/vision_chunks")
    ap.add_argument("--batch", type=int, default=48, help="每個 embed 請求帶幾筆（壓在 token/req 上限內）")
    ap.add_argument("--sleep", type=float, default=3.0,
                    help="批次之間暫停秒數；batch=48 + sleep=3 ≈ 960 contents/分，壓在免費層分鐘窗下")
    args = ap.parse_args()

    from polaris.config import settings
    from polaris.ingestion.sanitize import sanitize_text, validate_for_ingestion
    from polaris.vectorstore import get_vector_store
    from polaris.vectorstore.base import Document

    if settings.bq_dataset == "polaris_core":
        print("✋ 拒絕：BQ_DATASET=polaris_core（憲法 III）。設 polaris_dev_<name> 後重跑。")
        return

    import os
    keys = [k.strip() for k in os.environ.get("GEMINI_API_KEY", "").split(",") if k.strip()]
    if not keys:
        print("⏸ 需要 GEMINI_API_KEY（embedding）。"); return

    # 1) 收集目標 JSONL 的所有塊
    if args.ticker:
        paths = [f"{args.dir}/{t}.jsonl" for t in args.ticker]
    else:
        paths = sorted(glob.glob(f"{args.dir}/*.jsonl"))
    raw_by_id: dict[str, dict] = {}
    for p in paths:
        if not Path(p).exists():
            print(f"  (跳過不存在) {p}"); continue
        for line in Path(p).read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                raw_by_id[str(r["id"])] = r
    print(f"JSONL 共 {len(raw_by_id)} 塊（{len(paths)} 檔）")

    # 2) 查 BQ 已存在的 chunk_id（只補缺的）
    from google.cloud import bigquery
    bq = bigquery.Client(project=settings.gcp_project)
    table = f"{settings.gcp_project}.{settings.bq_dataset}.chunks"
    existing = {row["chunk_id"] for row in bq.query(
        f"SELECT chunk_id FROM `{table}`").result()}
    missing_ids = [i for i in raw_by_id if i not in existing]
    print(f"BQ 已有 {len(existing)} 塊；缺 {len(missing_ids)} 塊待補")
    if not missing_ids:
        print("✅ 無缺漏，無需補救。"); return

    # 3) sanitize/validate → 準備待 embed 清單
    pending: list[tuple[str, str, dict]] = []  # (id, clean_content, raw)
    skipped = 0
    for i in missing_ids:
        raw = raw_by_id[i]
        content = sanitize_text(raw.get("content", ""))
        if validate_for_ingestion(i, content):
            skipped += 1; continue
        pending.append((i, content, raw))
    if skipped:
        print(f"  ({skipped} 塊未過 validate，略過)")

    # 4) 批次 embed + 補入
    embed_many = _embed_batch_fn(keys, model=settings.embedding_model,
                                 dim=settings.embedding_dim)
    store = get_vector_store()
    done = 0
    n_req = 0
    for s in range(0, len(pending), args.batch):
        group = pending[s:s + args.batch]
        try:
            vecs = embed_many([c for _, c, _ in group])
        except Exception as exc:  # noqa: BLE001 — 配額耗盡等 → 優雅停（不崩、可續跑）
            print(f"\n⏸ embed 在第 {s} 塊後停止：{type(exc).__name__}: {str(exc)[:160]}")
            print(f"   已補 {done} 塊；剩 {len(pending) - done} 塊。配額恢復後重跑本腳本即續"
                  f"（已入庫者自動略過）。")
            break
        n_req += 1
        docs = [Document(id=i, content=c, embedding=v,
                         company=raw.get("company"), period=raw.get("period"),
                         metadata=dict(raw.get("metadata", {})))
                for (i, c, raw), v in zip(group, vecs)]
        store.add_documents(docs)
        done += len(docs)
        print(f"  補入 {done}/{len(pending)}（req#{n_req}）", flush=True)
        if args.sleep > 0 and s + args.batch < len(pending):
            time.sleep(args.sleep)
    else:
        print(f"✅ 補救完成：{done} 塊 → {settings.bq_dataset}（{n_req} 個 embed 請求）")


if __name__ == "__main__":
    main()
