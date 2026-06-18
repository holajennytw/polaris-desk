"""CLI demo：``python -m polaris.graph.news <news.json>``。

讀 mock 新聞 → 依 ticker 分組 → 各跑新聞評估卡 → 印描述 / 證據 / 矛盾 / 合規狀態。
無金鑰走確定性 fallback（token=0、可重現）。
"""
from __future__ import annotations

import sys
from collections import OrderedDict
from pathlib import Path

from polaris.graph.news.card import evaluate_news
from polaris.graph.news.model import NewsItem, load_mock_items


def _group_by_ticker(items: list[NewsItem]) -> "OrderedDict[str, list[NewsItem]]":
    groups: OrderedDict[str, list[NewsItem]] = OrderedDict()
    for item in items:
        groups.setdefault(item.ticker, []).append(item)
    return groups


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("用法：python -m polaris.graph.news <news.json>", file=sys.stderr)
        return 2

    items = load_mock_items(Path(args[0]))
    groups = _group_by_ticker(items)
    print(f"=== 新聞評估卡（{len(items)} 則新聞、{len(groups)} 家公司）===")
    for ticker, group in groups.items():
        card = evaluate_news(group)
        tag = "🚨 BLOCKED" if card.compliance_status == "blocked" else "[OK]"
        print(f"\n{tag} {ticker}（{len(group)} 則）")
        print(card.description)
        if card.evidence:
            print("證據：" + "; ".join(c.source_id for c in card.evidence))
        for con in card.contradictions:
            print(f"⚠ 矛盾（{con.topic}）：" + " ↔ ".join(c.source_id for c in con.statements))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
