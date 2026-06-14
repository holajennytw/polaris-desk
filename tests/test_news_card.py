"""新聞評估卡測試（FR-006 / R3 spec）。

全程 token=0：無金鑰走確定性 fallback；NFR-031 紅線由 compliance floor 守住。
卡片只「描述 / 標證據 / 標矛盾」，**0 買賣建議**（憲法 I）。
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from polaris.graph.compliance import BUYSELL_KEYWORDS, SAFE_MESSAGE
from polaris.graph.news.card import evaluate_news
from polaris.graph.news.model import NewsCard, NewsContradiction, NewsItem, load_mock_items
from tests.conftest import ApiError, FakeLLM

FIXTURE = Path(__file__).parent / "fixtures" / "news_items.json"
TS = datetime(2026, 6, 10, 9, 0)


def make_item(**overrides) -> NewsItem:
    base = dict(
        item_id="news-2330-001",
        ticker="2330",
        published_at=TS,
        source="經濟日報",
        url="https://example.com/n/1",
        title="台積電 2025Q1 營收較去年同期成長",
        content="台積電公布 2025 年第一季營收，較去年同期成長，主因 AI 與高效能運算需求。",
    )
    base.update(overrides)
    return NewsItem(**base)


# ── NewsItem 模型 ────────────────────────────────────────────────────────────

class TestNewsItem:
    def test_valid(self):
        it = make_item()
        assert it.ticker == "2330"
        assert it.source == "經濟日報"

    def test_frozen(self):
        from pydantic import ValidationError
        it = make_item()
        with pytest.raises(ValidationError):
            it.ticker = "9999"  # type: ignore[misc]

    def test_load_mock_items(self):
        items = load_mock_items(FIXTURE)
        assert len(items) >= 4
        assert all(isinstance(i, NewsItem) for i in items)


# ── 描述 + 接地證據（fallback，無金鑰）──────────────────────────────────────

class TestDescribeAndEvidence:
    def test_card_has_neutral_description(self):
        card = evaluate_news([make_item()])
        assert isinstance(card, NewsCard)
        assert card.ticker == "2330"
        assert card.compliance_status == "passed"
        assert card.description.strip()

    def test_evidence_grounded_to_each_item(self):
        items = [make_item(), make_item(item_id="news-2330-002", title="台積電擴廠公告", source="工商時報")]
        card = evaluate_news(items)
        assert len(card.evidence) == 2
        ids = {c.source_id for c in card.evidence}
        assert ids == {"news-2330-002", "news-2330-001"}
        assert all(c.origin == "news" for c in card.evidence)

    def test_sources_deduped(self):
        items = [make_item(), make_item(item_id="n2", source="經濟日報", title="另一則")]
        card = evaluate_news(items)
        assert card.sources == ["經濟日報"]

    def test_empty_items_raises(self):
        with pytest.raises(ValueError):
            evaluate_news([])


# ── 標矛盾 ───────────────────────────────────────────────────────────────────

class TestContradictions:
    def test_flags_conflicting_outlook_with_both_sources(self):
        pos = make_item(item_id="n-pos", ticker="2454",
                        title="聯發科 2026Q1 營收創新高、獲利成長",
                        content="聯發科第一季營收創同期新高，獲利優於市場預期。")
        neg = make_item(item_id="n-neg", ticker="2454",
                        title="分析師：聯發科 Q2 恐下滑、需求疲弱",
                        content="分析師指出終端需求疲弱，聯發科第二季營收恐下滑。")
        card = evaluate_news([pos, neg])
        assert len(card.contradictions) == 1
        con = card.contradictions[0]
        assert isinstance(con, NewsContradiction)
        cited = {c.source_id for c in con.statements}
        assert cited == {"n-pos", "n-neg"}
        assert all(c.origin == "news" for c in con.statements)

    def test_no_contradiction_when_aligned(self):
        a = make_item(item_id="a", title="台積電營收成長、獲利創新高")
        b = make_item(item_id="b", title="台積電產能擴張、需求樂觀")
        card = evaluate_news([a, b])
        assert card.contradictions == []


# ── NFR-031 紅線（最重要）────────────────────────────────────────────────────

class TestComplianceGate:
    def test_redteam_buysell_blocked_and_scrubbed(self):
        clean = make_item()
        redteam = make_item(
            item_id="news-redteam",
            title="某分析師喊進台積電",
            content="獲利前景看好，建議買進！股價偏低，是加碼好時機，看多後市。",
        )
        card = evaluate_news([clean, redteam])
        assert card.compliance_status == "blocked"
        assert card.description == SAFE_MESSAGE
        # 攔截後不外溢任何證據 / 矛盾原文
        assert card.evidence == []
        assert card.contradictions == []
        # 整張卡渲染出來不得含任何買賣關鍵字
        blob = card.description + " " + " ".join(card.sources)
        for kw in BUYSELL_KEYWORDS:
            assert kw not in blob

    def test_fixture_redteam_blocked(self):
        items = load_mock_items(FIXTURE)
        redteam = [i for i in items if "redteam" in i.item_id]
        assert redteam, "fixture 應含至少一則紅隊新聞"
        card = evaluate_news(redteam)
        assert card.compliance_status == "blocked"
        assert card.description == SAFE_MESSAGE


# ── 確定性 + smart 層 ────────────────────────────────────────────────────────

class TestDeterminismAndSmart:
    def test_deterministic_no_client(self):
        items = [make_item()]
        a, b = evaluate_news(items), evaluate_news(items)
        assert a.description == b.description
        assert a.compliance_status == b.compliance_status
        assert [c.source_id for c in a.evidence] == [c.source_id for c in b.evidence]

    def test_smart_layer_used_when_client(self):
        client = FakeLLM(response="台積電 2025Q1 營收較去年同期成長，主因 AI 需求。")
        card = evaluate_news([make_item()], client=client)
        assert card.compliance_status == "passed"
        assert "台積電" in card.description or "AI" in card.description

    def test_smart_violation_blocked_by_floor(self):
        client = FakeLLM(response="這檔建議買進，逢低布局。")
        card = evaluate_news([make_item()], client=client)
        assert card.compliance_status == "blocked"
        assert card.description == SAFE_MESSAGE

    def test_smart_failure_falls_back(self):
        client = FakeLLM(error=ApiError(503), fail_times=99)
        card = evaluate_news([make_item()], client=client)
        assert card.description.strip()
        assert card.compliance_status == "passed"


# ── CLI smoke ────────────────────────────────────────────────────────────────

def test_cli_prints_card(capsys):
    from polaris.graph.news.__main__ import main
    exit_code = main([str(FIXTURE)])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "新聞評估卡" in out
    for kw in BUYSELL_KEYWORDS:
        assert kw not in out
