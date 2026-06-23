"""ColPali 第 4 路 round-trip 驗收（gate ③，TD-01 ≥70% 門檻）—— 標準 runner。

跑一組 gold (query, 期望 page_id)，對 polaris_core.colpali_pages 做視覺檢索，
回 hit@k / MRR + 三項 sanity 控制，並寫出**機器可驗的** result JSON（給 PM 驗 gate）。

需要（缺任一 → 印提示後 return，不炸）：
  1. GPU 環境（colpali-v1.2 = PaliGemma-3B；CPU 慢到不實用）。
  2. COLPALI_QUERY_ENCODER=1 + 裝 `.[colpali]`（colpali-engine + torch + 權重 ~5GB）。
  3. HF token：colpali-v1.2 依賴 *gated* google/paligemma-3b-mix-448 → `export HF_TOKEN=...`。
  4. gold：data/gold/colpali_gold.json（見 docs/colpali_roundtrip_test_cases.md 的 schema），
     或本檔 inline GOLD。
  5. live BigQuery 憑證（讀 polaris_core.colpali_pages）。

用法（GPU box）：
  export HF_TOKEN=...
  uv pip install -e '.[colpali]'
  COLPALI_QUERY_ENCODER=1 uv run python scripts/colpali_roundtrip_check.py \
      --gold data/gold/colpali_gold.json --out logs/roundtrip_result.json

通過：hit@5 ≥ 0.70（gate ③）。把 --out 的 JSON 連同 gold commit、並貼 metrics 到 issue #17。
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

#: 後援 inline gold（當無 --gold 檔時用）。實跑請改用 data/gold/colpali_gold.json。
#: 真實 page_id 取自 live colpali_pages 2026-06-23；query 待 R1/R4 照圖表內容補。
GOLD: list[dict] = [
    # {"query": "台積電 2025Q2 各製程節點營收占比", "page_id": "66aef70e-7102-431b-b2fe-28160f83e0dc", "ticker": "2330"},
]

#: 負控制：與任何法說簡報無關的 query。期望 top1 相似度明顯低於 gold（防退化編碼器把
#: 任何 query 都對到高分頁）。非硬性 gate，作診斷。
NEGATIVE_CONTROLS = [
    "今天台北的天氣如何",
    "推薦一份蔬食午餐食譜",
    "如何申辦護照",
]

DIM_EXPECTED = 128
HIT_GATE = 0.70  # gate ③（TD-01）


def _load_gold(path: str | None) -> list[dict]:
    """讀 gold，容忍多種結構並在不符時報清楚的錯（不要再吐 dict() 的天書）。

    接受：① list[dict]；② {"items"|"queries"|"gold"|"data": [...]}；
    ③ 依 ticker 分組 {"2330": [...], "2317": [...]}（值全為 list → 攤平）；
    每筆可為 dict（含 query/page_id）或 [query, page_id, ticker?]。
    """
    if not path:
        return list(GOLD)
    raw = json.loads(Path(path).read_text(encoding="utf-8"))

    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        items = next((raw[k] for k in ("items", "queries", "gold", "data")
                      if isinstance(raw.get(k), list)), None)
        if items is None:
            vals = list(raw.values())
            if vals and all(isinstance(v, list) for v in vals):
                items = [it for v in vals for it in v]  # 依 ticker 分組 → 攤平
            else:
                raise ValueError(
                    "gold JSON 結構不符：頂層 dict 需有 'items' 清單，或是 list[dict]，"
                    f"或依 ticker 分組的 {{ticker: [...]}}。實際頂層鍵 = {list(raw)[:8]}"
                )
    else:
        raise ValueError(f"gold JSON 頂層型別需為 dict/list，實際 = {type(raw).__name__}")

    norm: list[dict] = []
    for i, it in enumerate(items):
        if isinstance(it, dict):
            d = dict(it)
        elif isinstance(it, (list, tuple)) and len(it) >= 2:
            d = {"query": it[0], "page_id": it[1]}
            if len(it) > 2:
                d["ticker"] = it[2]
        else:
            raise ValueError(
                f"gold 第 {i} 筆格式不符：需 dict（含 query/page_id）或 [query, page_id]，實際 = {it!r}"
            )
        if not d.get("query") or not d.get("page_id"):
            raise ValueError(f"gold 第 {i} 筆缺 query 或 page_id（key 名請用這兩個）：{d!r}")
        norm.append(d)
    return norm


def _rank_of(expected: str, got: list[str]) -> int | None:
    return got.index(expected) + 1 if expected in got else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", default="data/gold/colpali_gold.json",
                    help="gold JSON（{items:[{query,page_id,ticker?}]} 或 list）")
    ap.add_argument("--out", default="logs/roundtrip_result.json")
    ap.add_argument("--top-k", type=int, default=10, help="檢索深度（hit@1/5/10 都從這裡算）")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    from polaris.config import settings
    from polaris.retrieval.colpali_retriever import active_colpali_query_fn
    from polaris.vectorstore.colpali_store import BigQueryColpaliStore

    fn = active_colpali_query_fn()
    if fn is None:
        print("⏳ ColPali query encoder 未開（設 COLPALI_QUERY_ENCODER=1 + 裝 .[colpali]）。")
        return
    gold_path = args.gold if Path(args.gold).exists() else None
    gold = _load_gold(gold_path)
    if not gold:
        print(f"⏳ 尚無 gold（{args.gold} 不存在且 inline GOLD 空）。見 "
              "docs/colpali_roundtrip_test_cases.md 補 gold。")
        return

    store = BigQueryColpaliStore(settings)

    # ── TC-1 維度/合法性 ────────────────────────────────────────────────
    probe = fn(gold[0]["query"])
    tc1_ok = len(probe) == DIM_EXPECTED and all(isinstance(x, float) for x in probe) \
        and all(x == x for x in probe)  # NaN 檢查

    # ── TC-5 決定性（同 query 兩次） ────────────────────────────────────
    probe2 = fn(gold[0]["query"])
    det_delta = max((abs(a - b) for a, b in zip(probe, probe2)), default=0.0)

    # ── TC-3 全 gold round-trip ─────────────────────────────────────────
    per_query, gold_top1_sims = [], []
    for it in gold:
        q, expected = it["query"], it["page_id"]
        results = store.search(fn(q), top_k=args.top_k)
        got = [r.id for r in results]
        rank = _rank_of(expected, got)
        top1 = float(results[0].score) if results else 0.0
        gold_top1_sims.append(top1)
        rec = {"query": q, "expected": expected, "ticker": it.get("ticker"),
               "got": got[:5], "rank": rank, "hit_at_5": bool(rank and rank <= 5),
               "top1_sim": round(top1, 4)}
        per_query.append(rec)
        if args.verbose:
            mark = "✅" if rec["hit_at_5"] else "❌"
            print(f"{mark} rank={rank} {q!r} → {got[:5]}")

    n = len(per_query)
    hit1 = sum(r["rank"] == 1 for r in per_query) / n
    hit5 = sum(r["hit_at_5"] for r in per_query) / n
    hit10 = sum(bool(r["rank"]) for r in per_query) / n
    mrr = sum(1.0 / r["rank"] for r in per_query if r["rank"]) / n

    # ── TC-4 負控制 ─────────────────────────────────────────────────────
    neg = []
    for q in NEGATIVE_CONTROLS:
        results = store.search(fn(q), top_k=1)
        neg.append({"query": q, "top1_sim": round(float(results[0].score), 4) if results else 0.0})
    sep = (statistics.median(gold_top1_sims) - statistics.median([d["top1_sim"] for d in neg])) \
        if gold_top1_sims and neg else 0.0

    # ── TC-6 公司過濾完整性 ─────────────────────────────────────────────
    filt = next((it for it in gold if it.get("ticker")), None)
    tc6_ok = None
    if filt:
        fr = store.search(fn(filt["query"]), top_k=args.top_k, filters={"company": filt["ticker"]})
        tc6_ok = all(r.company == filt["ticker"] for r in fr) if fr else None

    verdict = "PASS" if hit5 >= HIT_GATE else "FAIL"
    result = {
        "model": settings.colpali_model, "pooling": "mean", "dim": DIM_EXPECTED,
        "distance": "cosine", "top_k": args.top_k,
        "gold_file": gold_path or "inline", "gold_count": n,
        "metrics": {"hit_at_1": round(hit1, 3), "hit_at_5": round(hit5, 3),
                    "hit_at_10": round(hit10, 3), "mrr": round(mrr, 3)},
        "controls": {
            "tc1_dim_ok": tc1_ok, "tc5_determinism_max_delta": det_delta,
            "tc4_gold_vs_neg_median_separation": round(sep, 4),
            "tc6_company_filter_ok": tc6_ok,
        },
        "negative_control": neg,
        "per_query": per_query,
        "gate": HIT_GATE, "verdict": verdict,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n| metric | value |\n|---|---|")
    for k, v in result["metrics"].items():
        print(f"| {k} | {v:.1%} |" if k != "mrr" else f"| {k} | {v:.3f} |")
    print(f"| TC-1 dim 128 | {'✅' if tc1_ok else '❌'} |")
    print(f"| TC-5 determinism Δ | {det_delta:.2e} |")
    print(f"| TC-4 gold−neg sep | {sep:+.3f} |")
    print(f"| TC-6 company filter | {tc6_ok} |")
    print(f"\n命中率 hit@5 = {hit5:.0%}（門檻 ≥70%）：**{verdict}** → {args.out}")


if __name__ == "__main__":
    main()
