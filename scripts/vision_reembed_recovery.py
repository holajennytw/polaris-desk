"""Vision 入庫補救：把 data/vision_chunks/*.jsonl 中「尚未進 BQ」的塊 re-embed 後補入。

背景：線上 pilot 以 concurrency 抽取＋逐塊 embed，會在 AI Studio 免費層
`embed_content_free_tier_requests`（**1000 requests/天/專案**）上爆量 → 後段塊全被 quarantine。
但**視覺抽取結果已落地 JSONL**（昂貴的那步已完成），故補救無需重抽：

  1. 掃 data/vision_chunks/<ticker>.jsonl（所有或 --ticker 指定）。
  2. 查 BQ 已存在的 chunk_id（同一 dataset），只挑「缺的」。
  3. 逐塊 embed（⚠️ gemini-embedding-2 不支援批次：contents=[多段] 只回 1 個向量、
     其餘被丟棄 → 1 request = 1 chunk）。多把 key 逗號分隔、狀態式輪替（用罄才換把），
     全把皆 429（當日耗盡）即優雅停、可續跑。BQ 寫入仍批量（--store-batch）。
  4. sanitize/validate 後組 Document，經 get_vector_store() 補入（idempotent upsert）。

額度規劃：N 塊 ≈ N requests；每個 GCP 專案 1000/天。需要 ⌈N/1000⌉ 把「不同專案」的 key
（同專案多把共用同一 1000）。當日不夠就分天跑或多專案 key。

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


def _make_embed_one(keys: list[str], *, model: str, dim: int):
    """回傳 embed_one(text)->vec。

    ⚠️ gemini-embedding-2 **一次只 embed 一段**（contents=[多段] 只回 1 個向量、
    其餘被丟棄）→ 不能批次，1 request = 1 chunk，免費層 1000 requests/天/專案。
    多把 key（逗號分隔）狀態式輪替：用目前這把直到 429，才換下一把並記住，
    避免每塊都從用罄的把重試。全把皆 429（當日配額耗盡）→ 拋出 → 上層優雅停。
    """
    from google import genai
    from google.genai import types

    from polaris.retry import call_with_retry, is_quota_error

    clients: list = [genai.Client(api_key=k) for k in keys]
    state = {"i": 0}  # 目前使用中的 key index

    def _embed(idx: int, text: str) -> list[float]:
        resp = clients[idx].models.embed_content(
            model=model, contents=text,
            config=types.EmbedContentConfig(output_dimensionality=dim),
        )
        return list(resp.embeddings[0].values)

    def _try_once(text: str) -> list[float]:
        last_exc: Exception | None = None
        n = len(clients)
        for off in range(n):  # 從目前 key 起逐把試
            idx = (state["i"] + off) % n
            try:
                vec = _embed(idx, text)
                state["i"] = idx  # 記住這把還能用
                return vec
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                # google-genai 偶發 "client has been closed"（httpx 連線被關）→ 重建該把再試一次
                if isinstance(exc, RuntimeError) and "closed" in str(exc).lower():
                    clients[idx] = genai.Client(api_key=keys[idx])
                    try:
                        vec = _embed(idx, text)
                        state["i"] = idx
                        return vec
                    except Exception as exc2:  # noqa: BLE001
                        last_exc = exc2
                        if not is_quota_error(exc2):
                            raise
                    continue
                if not is_quota_error(exc):
                    raise
        assert last_exc is not None
        raise last_exc

    def embed_one(text: str) -> list[float]:
        # 瞬時 429（分鐘尖峰）退避重試；當日耗盡則少次數快速放棄 → 上層停。
        return call_with_retry(lambda: _try_once(text),
                               attempts=3, base_delay=3.0, max_delay=20.0)

    return embed_one


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", action="append", help="只補這些 ticker（預設全部 JSONL）")
    ap.add_argument("--dir", default="data/vision_chunks")
    ap.add_argument("--store-batch", type=int, default=100,
                    help="每幾塊寫一次 BQ（embed 仍是 1 req/塊；這只是 BQ load 批量）")
    ap.add_argument("--sleep", type=float, default=0.0,
                    help="每塊 embed 之間暫停秒數（日配額是硬上限，通常設 0 即可）")
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
            if not line.strip():
                continue
            try:  # 抽取可能正在寫同一檔 → 容忍尾端半截行，下次重跑會補齊
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
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

    # 4) 逐塊 embed（1 req/塊，模型不支援批次）→ 累積到 store-batch 才寫 BQ
    embed_one = _make_embed_one(keys, model=settings.embedding_model,
                                dim=settings.embedding_dim)
    store = get_vector_store()
    buf: list[Document] = []
    done = 0
    stopped = False

    def _flush() -> None:
        nonlocal done
        if buf:
            store.add_documents(buf)
            done += len(buf)
            buf.clear()
            print(f"  補入 {done}/{len(pending)}", flush=True)

    for n, (i, c, raw) in enumerate(pending):
        try:
            vec = embed_one(c)
        except Exception as exc:  # noqa: BLE001 — 全把配額耗盡 → 優雅停（先把已 embed 的寫掉）
            print(f"\n⏸ embed 在第 {n} 塊停止：{type(exc).__name__}: {str(exc)[:160]}")
            stopped = True
            break
        buf.append(Document(id=i, content=c, embedding=vec,
                            company=raw.get("company"), period=raw.get("period"),
                            metadata=dict(raw.get("metadata", {}))))
        if len(buf) >= args.store_batch:
            _flush()
        if args.sleep > 0:
            time.sleep(args.sleep)
    _flush()  # 寫掉尾批（含 stop 前已 embed 的）

    if stopped:
        print(f"   已補 {done} 塊；剩 {len(pending) - done} 塊。配額恢復後重跑本腳本即續"
              f"（已入庫者自動略過）。")
    else:
        print(f"✅ 補救完成：{done} 塊 → {settings.bq_dataset}（{done} 個 embed 請求）")


if __name__ == "__main__":
    main()
