"""R3 /ask 檢索過濾：問單一公司不混別家、法說題只取 transcript（修 R6 #1 / #2）。

全程 token=0：用 fake retriever 捕捉傳入的 filters，不碰真 BQ / Gemini。
"""
from __future__ import annotations

from polaris.graph.nodes.stubs import _real_contexts, _wants_earnings_call
from polaris.ontology import detect_tickers
from polaris.retrieval.retriever import PUBLIC_VIEWER, _matches_filters
from polaris.vectorstore.base import SearchResult as SR


# --- 公司偵測 ----------------------------------------------------------------

def test_detect_tickers_single_comparison_and_none():
    assert detect_tickers("問台積電 2026Q1 毛利率") == ["2330"]
    assert detect_tickers("台積電 vs 聯發科 毛利率") == ["2330", "2454"]
    assert detect_tickers("比較鴻海與聯詠") == ["2317", "3034"]
    assert detect_tickers("用 2330 法說") == ["2330"]          # 裸代號也認
    assert detect_tickers("毛利率怎麼算") == []                  # 無公司 → 空


def test_wants_earnings_call():
    assert _wants_earnings_call("台積電法說會重點") is True
    assert _wants_earnings_call("台積電 2026Q1 法人說明會") is True
    assert _wants_earnings_call("台積電毛利率") is False


# --- /ask retriever 節點傳的 filters ------------------------------------------

class _FakeRetriever:
    def __init__(self) -> None:
        self.filters_seen: list[dict] = []

    def retrieve(self, query, *, filters=None):
        self.filters_seen.append(dict(filters or {}))
        return []   # 只驗 filters，不回結果


def test_comparison_query_filters_each_company():
    fake = _FakeRetriever()
    _real_contexts(fake, "台積電 vs 聯發科 毛利率", quarters=None, viewer=PUBLIC_VIEWER)
    companies = [f.get("company") for f in fake.filters_seen]
    assert "2330" in companies and "2454" in companies   # 兩家都查，比較題不漏


def test_earnings_call_query_adds_doc_type_transcript():
    fake = _FakeRetriever()
    _real_contexts(fake, "台積電 法說會 營運重點", quarters=["2026Q1"], viewer=PUBLIC_VIEWER)
    assert fake.filters_seen == [
        {"viewer": PUBLIC_VIEWER, "company": "2330", "period": "2026Q1", "doc_type": "transcript"}
    ]


def test_no_company_detected_keeps_prior_behaviour():
    fake = _FakeRetriever()
    _real_contexts(fake, "毛利率怎麼算", quarters=None, viewer=PUBLIC_VIEWER)
    assert fake.filters_seen == [{"viewer": PUBLIC_VIEWER}]   # 沒偵測到公司 → 不加 company


# --- BM25 路徑 doc_type 過濾（與 store 一致）-----------------------------------

def test_matches_filters_doc_type_excludes_non_transcript():
    transcript = SR(id="t", content="x", score=1.0, company="2330", period="2026Q1",
                    metadata={"doc_type": "transcript"})
    news = SR(id="n", content="x", score=1.0, company="2330", period="2026Q1",
              metadata={"doc_type": "news"})
    no_dt = SR(id="s", content="x", score=1.0, company="2330", metadata={})

    assert _matches_filters(transcript, {"doc_type": "transcript"}) is True
    assert _matches_filters(news, {"doc_type": "transcript"}) is False
    assert _matches_filters(no_dt, {"doc_type": "transcript"}) is False   # 無 doc_type → 排除
