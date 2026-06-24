from polaris.ingestion.vision_schema import PageExtraction
from polaris.ingestion.vision_to_text import should_vision_route, flatten_extraction


def test_route_scanned_or_presentation():
    assert should_vision_route("", doc_type="transcript") is True          # 0 字 → 掃描頁
    assert should_vision_route("  \n ", doc_type="transcript") is True     # 全空白
    assert should_vision_route("短", doc_type="presentation") is True      # 簡報頁一律 vision
    assert should_vision_route("這是一段有完整文字層的逐字稿內容，超過門檻。",
                               doc_type="transcript") is False             # 有文字 → 文字路


def test_flatten_includes_values_skips_nulls():
    p = PageExtraction.model_validate(
        {"page_summary": "2025Q1 製程別", "charts": [{"chart_type": "pie",
         "title": "製程別", "series": [{"label": "5奈米", "value": 36, "unit": "%"},
                                      {"label": "3奈米", "value": 22, "unit": "%"},
                                      {"label": "未標示", "value": None, "unit": "%"}]}],
         "table_markdown": "| a | b |\n|---|---|\n| 1 | 2 |",
         "key_values": [{"label": "毛利率", "value": 58.8, "unit": "%"}], "confidence": 0.9})
    text = flatten_extraction(p)
    assert "2025Q1 製程別" in text
    assert "5奈米: 36%" in text and "3奈米: 22%" in text
    assert "未標示" not in text          # null 值不輸出（不編造）
    assert "毛利率: 58.8%" in text
    assert "| a | b |" in text
