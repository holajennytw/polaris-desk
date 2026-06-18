"""新聞評估卡（@R3，FR-006）：只描述 / 標證據 / 標矛盾，0 買賣建議（NFR-031）。"""
from __future__ import annotations

from polaris.graph.news.card import evaluate_news
from polaris.graph.news.model import (
    NewsCard,
    NewsContradiction,
    NewsItem,
    load_mock_items,
)

__all__ = [
    "evaluate_news",
    "NewsItem",
    "NewsCard",
    "NewsContradiction",
    "load_mock_items",
]
