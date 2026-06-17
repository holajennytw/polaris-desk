"""ticker→中文名對照（polaris.ontology）：行為 + 對 seed CSV 的同步守門。"""
from __future__ import annotations

import csv
from pathlib import Path

from polaris.ontology import company_label, company_name
from polaris.ontology.companies import _COMPANY_NAMES

SEED = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "r6"
    / "ontology"
    / "seeds"
    / "company_dim.csv"
)


def _seed_names() -> dict[str, str]:
    with SEED.open(encoding="utf-8") as f:
        return {row["ticker"]: row["company_name"] for row in csv.DictReader(f)}


def test_in_sync_with_seed_csv():
    """內嵌對照必須與 seed company_dim.csv 完全一致（防漂移）。"""
    assert _COMPANY_NAMES == _seed_names()


def test_known_ticker_returns_canonical_name():
    assert company_name("2330") == "台積電"
    assert company_name("2412") == "中華電"  # 正名後（非「中華電信」）


def test_unknown_or_empty_returns_none():
    assert company_name("9999") is None
    assert company_name("") is None
    assert company_name(None) is None


def test_label_known_and_unknown():
    assert company_label("2330") == "台積電（2330）"
    assert company_label("9999") == "9999"  # 未知 → 退回 ticker
    assert company_label(None) == ""
