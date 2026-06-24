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


def test_confidence_normalized_to_unit_range():
    # 模型有時回 0–1 外的 confidence（實測 flash 回 5.0、pro 回 95.0）→ 正規化到 [0,1]，
    # 否則「低信心自動升 Pro」門檻（0.6）形同失效、Gate1 信心欄也失真。
    assert PageExtraction.model_validate({"confidence": 0.95}).confidence == 0.95   # 原樣
    assert PageExtraction.model_validate({"confidence": 95.0}).confidence == 0.95   # 百分比→小數
    assert PageExtraction.model_validate({"confidence": 5.0}).confidence == 0.05
    assert PageExtraction.model_validate({"confidence": 150}).confidence == 1.0     # clamp 上限
    assert PageExtraction.model_validate({"confidence": -1}).confidence == 0.0      # clamp 下限


def test_value_nullable_no_hallucinated_number():
    p = PageExtraction.model_validate(
        {"page_summary": "x", "charts": [{"chart_type": "bar", "title": None,
         "series": [{"label": "1Q25", "value": None, "unit": "十億"}]}],
         "table_markdown": None, "key_values": [], "confidence": 0.5})
    assert p.charts[0].series[0].value is None
