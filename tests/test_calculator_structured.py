"""R3 calculator 接 BQ 結構化計算：毛利率推導 + 引用接地（eval Q001 根本解）。

全程 token=0：注入 fake StructuredStore，不碰真 BQ / Gemini。
無憑證 / 查無資料時 calculator 必須維持 v0 確定性假值（e2e determinism 不變）。
"""
from __future__ import annotations

from polaris.graph.nodes.stubs import _structured_calculations, calculator


class _FakeStore:
    """回台積電 2025Q1 的 revenue / revenue_yoy / gross_profit 三列（單位一致）。"""

    def __init__(self, rows_by_key: dict[tuple[str, str], list[dict]] | None = None) -> None:
        self.rows_by_key = rows_by_key if rows_by_key is not None else {
            ("2330", "2025Q1"): [
                {"metric_id": "revenue", "metric_name": "營業收入", "value": 839_254,
                 "unit": "百萬元", "source_id": "fm-2330-2025Q1-rev"},
                {"metric_id": "revenue_yoy", "metric_name": "營收年增率", "value": 41.6,
                 "unit": "%", "source_id": "fm-2330-2025Q1-yoy"},
                {"metric_id": "gross_profit", "metric_name": "營業毛利", "value": 493_407,
                 "unit": "百萬元", "source_id": "fm-2330-2025Q1-gp"},
            ]
        }
        self.calls: list[dict] = []

    def list_financials(self, *, ticker=None, period=None, granularity=None, **_kw):
        self.calls.append({"ticker": ticker, "period": period, "granularity": granularity})
        return self.rows_by_key.get((ticker, period), [])


def test_derives_gross_margin_from_gross_profit_and_revenue():
    """gross_margin 非入庫 metric_id（canonical 14 種只有 gross_profit）→ 必須推導。"""
    store = _FakeStore()

    calcs, contexts = _structured_calculations("台積電 2025Q1 毛利率", ["2025Q1"], store=store)

    entry = calcs["2330:2025Q1"]
    assert entry["gross_margin_pct"]["value"] == 58.79  # 493407/839254*100
    assert entry["gross_margin_pct"]["derived_from"] == [
        "fm-2330-2025Q1-gp", "fm-2330-2025Q1-rev",
    ]
    assert entry["revenue"]["source_id"] == "fm-2330-2025Q1-rev"
    assert entry["revenue_yoy"]["value"] == 41.6
    # 每個數字都有帶 source_id 的 context（引用接地：數字必有來源）
    sids = {c["source_id"] for c in contexts}
    assert {"fm-2330-2025Q1-rev", "fm-2330-2025Q1-yoy", "fm-2330-2025Q1-gp"} <= sids
    assert any("58.79" in c["text"] for c in contexts)  # 推導值出現在可引用文字中
    assert store.calls == [{"ticker": "2330", "period": "2025Q1", "granularity": "quarter"}]


def test_skips_derivation_when_units_mismatch():
    store = _FakeStore({
        ("2330", "2025Q1"): [
            {"metric_id": "revenue", "metric_name": "營業收入", "value": 839_254,
             "unit": "百萬元", "source_id": "r"},
            {"metric_id": "gross_profit", "metric_name": "營業毛利", "value": 493.4,
             "unit": "十億元", "source_id": "g"},
        ]
    })

    calcs, _contexts = _structured_calculations("台積電 2025Q1", ["2025Q1"], store=store)

    assert "gross_margin_pct" not in calcs["2330:2025Q1"]  # 單位不一致不硬除（不編數字）
    assert "revenue" in calcs["2330:2025Q1"]


def test_returns_none_without_company_or_quarters():
    store = _FakeStore()
    assert _structured_calculations("毛利率怎麼算", ["2025Q1"], store=store) is None
    assert _structured_calculations("台積電毛利率", None, store=store) is None
    assert _structured_calculations("台積電 2023Q4", ["2023Q4"], store=store) is None  # 查無資料


def test_calculator_node_falls_back_to_stub_without_credentials():
    """CI / 無金鑰：available() False → 維持 v0 確定性假值（e2e determinism 不變）。"""
    out = calculator({"query": "台積電 2025Q1 毛利率", "period": None, "contexts": []})
    assert out["calculations"] == {"YoY_pct": 12.34}
    assert "contexts" not in out  # stub 路徑不動 retriever 的 contexts


def test_calculator_node_merges_metric_contexts(monkeypatch):
    """真路徑：calculations 換成真值，metric contexts 併進 retriever 的 contexts。"""
    from polaris.graph import nodes

    store = _FakeStore()
    monkeypatch.setattr(
        nodes.stubs,
        "_structured_calculations",
        lambda query, quarters: _structured_calculations(query, quarters, store=store),
    )

    class _P:
        quarters = ["2025Q1"]

    prior = [{"source_id": "chunk-1", "text": "法說片段"}]
    out = calculator({"query": "台積電 2025Q1 毛利率", "period": _P(), "contexts": prior})

    assert "2330:2025Q1" in out["calculations"]
    assert out["contexts"][0] == prior[0]  # retriever 的 contexts 不能被蓋掉
    assert {c["source_id"] for c in out["contexts"][1:]} == {
        "fm-2330-2025Q1-rev", "fm-2330-2025Q1-yoy", "fm-2330-2025Q1-gp",
    }
