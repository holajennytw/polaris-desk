from polaris.ingestion.vision_schema import PageExtraction


def test_parses_structured_extraction():
    raw = {
        "page_summary": "2025Q1 製程別營收占比",
        "charts": [{"chart_type": "pie", "title": "製程別",
                    "series": [{"label": "5奈米", "value": 36, "unit": "%"},
                               {"label": "3奈米", "value": 22, "unit": "%"}]}],
        "table_markdown": None,
        "key_values": [{"label": "毛利率", "value": 58.8, "unit": "%"}],
        "confidence": 0.95,
    }
    p = PageExtraction.model_validate(raw)
    assert p.confidence == 0.95
    assert p.charts[0].series[0].label == "5奈米"
    assert p.key_values[0].value == 58.8


def test_value_nullable_no_hallucinated_number():
    p = PageExtraction.model_validate(
        {"page_summary": "x", "charts": [{"chart_type": "bar", "title": None,
         "series": [{"label": "1Q25", "value": None, "unit": "十億"}]}],
         "table_markdown": None, "key_values": [], "confidence": 0.5})
    assert p.charts[0].series[0].value is None
