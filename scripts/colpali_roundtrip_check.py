"""Phase 1 驗收：ColPali 第 4 路 round-trip 命中率自檢。

對 N 個已知頁下對應 query，期望該 page_id 進 top-k。命中率 ≥70%（TD-01 門檻）= 對齊成功。
需要：#133 的 query encoder 已接（active_colpali_query_fn 回非 None）+ live BigQuery 憑證。

用法：uv run python scripts/colpali_roundtrip_check.py
"""
from __future__ import annotations

# (query 文字, 期望命中的 page_id) — 待 R4 在 #133 附 gold 樣本後填入；
# 暫以空清單佔位，實跑前替換為真 gold。
GOLD: list[tuple[str, str]] = [
    # ("台積電 2025Q3 毛利率", "pg-2330-2025Q3-9"),
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
