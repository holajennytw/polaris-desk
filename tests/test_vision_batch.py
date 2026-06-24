import base64

from polaris.ingestion.vision_batch import (
    RESPONSE_SCHEMA,
    build_request_line,
    parse_response_line,
)


def test_build_request_line_inlines_image_and_schema():
    line = build_request_line(b"PNGBYTES", prompt="轉錄這頁")
    req = line["request"]
    parts = req["contents"][0]["parts"]
    assert parts[0]["text"] == "轉錄這頁"
    # 圖以 base64 inline
    assert base64.b64decode(parts[1]["inlineData"]["data"]) == b"PNGBYTES"
    assert parts[1]["inlineData"]["mimeType"] == "image/png"
    # structured output（Vertex responseSchema）
    gc = req["generationConfig"]
    assert gc["responseMimeType"] == "application/json"
    assert gc["responseSchema"] is RESPONSE_SCHEMA
    assert gc["temperature"] == 0.0


def test_parse_response_line_valid():
    out = {"response": {"candidates": [{"content": {"parts": [
        {"text": '{"page_summary":"x","key_values":[{"label":"毛利率","value":58.8,"unit":"%"}],"confidence":0.9}'}
    ]}}]}}
    p = parse_response_line(out)
    assert p is not None
    assert p.key_values[0].value == 58.8


def test_parse_response_line_missing_or_blocked_returns_none():
    assert parse_response_line({"response": {"candidates": []}}) is None      # 被封鎖/無候選
    assert parse_response_line({}) is None                                    # 整行缺 response
    assert parse_response_line({"response": {"candidates": [{"content": {"parts": [
        {"text": "not json"}]}}]}}) is None                                   # 壞 JSON → 不瞎掰
