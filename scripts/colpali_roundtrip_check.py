"""Phase 1 驗收：ColPali 第 4 路 round-trip 命中率自檢。

對 N 個已知頁下對應 query，期望該 page_id 進 top-k。命中率 ≥70%（TD-01 門檻）= 對齊成功。

需要（缺任一 → 印提示後 return，不炸）：
  1. **GPU 環境**（colpali-v1.2 是 PaliGemma-3B base，CPU 慢到不實用）。本機 Mac 無 GPU
     → 由 R4/R2 在 Colab 免費 GPU 或 R4 GCE 跑（見開發時程 6/12 拍板）。
  2. query encoder 已開：``COLPALI_QUERY_ENCODER=1`` 且裝了 ``.[colpali]``
     （colpali-engine + torch + colpali-v1.2 權重 ~5GB）。
  3. **HuggingFace token**：colpali-v1.2 依賴 *gated* ``google/paligemma-3b-mix-448``，
     需先在 HF 接受授權並 ``export HF_TOKEN=...``（或 ``huggingface-cli login``），否則 401。
  4. R4 gold 樣本：把 GOLD 填成 (query, 期望 page_id)——見下方 _CANDIDATE_PAGES 模板，
     page_id 是 polaris_core.colpali_pages 真值，R4 只需照該頁圖表內容補 query 文字。
  5. **池化對齊確認**：本 encoder 對 query token 做 **mean-pool**（見 colpali_query_encoder）；
     R4 須確認 page 端 colpali_pages 入庫時也是 mean-pool over patches，否則不同空間、命中率失真。
  6. live BigQuery 憑證（讀 polaris_core.colpali_pages）。

用法（GPU box）：
  export HF_TOKEN=...                       # gated paligemma 授權
  uv pip install -e '.[colpali]'
  COLPALI_QUERY_ENCODER=1 uv run python scripts/colpali_roundtrip_check.py
"""
from __future__ import annotations

# (query 文字, 期望命中的 page_id) — 實跑前由 R4 填真 gold。空清單時 main() 誠實 return。
GOLD: list[tuple[str, str]] = [
    # 範例格式（取消註解並換成真 query/page_id）：
    # ("台積電 2025Q3 各平台營收占比圖", "66aef70e-7102-431b-b2fe-28160f83e0dc"),
]

# R4 待辦模板：以下為 polaris_core.colpali_pages 的**真實** page_id（每檔抽一頁，page_num=5
# 中段，較可能是圖表頁）。R4 請：①開該頁看圖表內容 ②把它寫成自然語 query ③搬進上面 GOLD。
# 也歡迎挑更具辨識度的圖表頁（毛利率趨勢、營收分區、產能利用率…），命中率才有意義。
_CANDIDATE_PAGES = [
    # (ticker, fiscal_period, page_num, page_id) ← 由 live BQ 2026-06-23 取樣
    ("1216", "2025Q2", 5, "0408a631-15d8-4544-b07f-7004f719be85"),  # 統一
    ("2317", "2025Q4", 5, "daf58ecf-522e-46a9-bc4d-3b88cdb26b8d"),  # 鴻海
    ("2330", "2025Q2", 5, "66aef70e-7102-431b-b2fe-28160f83e0dc"),  # 台積電
    ("2454", "2025Q3", 5, "f0eeb07b-d009-4b29-81c5-558358eb1783"),  # 聯發科
    ("2891", "2025Q1", 5, "ac2a82cf-134e-4fb2-b4fd-6d8300fce98e"),  # 中信金
]


def main() -> None:
    from polaris.config import settings
    from polaris.retrieval.colpali_retriever import active_colpali_query_fn
    from polaris.vectorstore.colpali_store import BigQueryColpaliStore

    fn = active_colpali_query_fn()
    if fn is None:
        print("⏳ ColPali query encoder 未接（見 #133）；無法 round-trip。先補 active_colpali_query_fn。")
        return
    if not GOLD:
        print("⏳ 尚無 gold 樣本；請填入 GOLD（query, 期望 page_id），或向 R4 索取（#133）。")
        return

    store = BigQueryColpaliStore(settings)
    hit, total = 0, len(GOLD)
    for query, expected_page_id in GOLD:
        vector = fn(query)
        results = store.search(vector, top_k=5)
        got = [r.id for r in results]
        ok = expected_page_id in got
        hit += int(ok)
        print(f"{'✅' if ok else '❌'} {query!r} → top5={got}（期望 {expected_page_id}）")
    rate = hit / total if total else 0.0
    print(f"\n命中率 {hit}/{total} = {rate:.0%}（門檻 ≥70%）：{'PASS' if rate >= 0.70 else 'FAIL'}")


if __name__ == "__main__":
    main()
