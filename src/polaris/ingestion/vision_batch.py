"""Vertex Batch Prediction 入庫的純函式：組請求行 + 解回應行。

Batch 是**非同步大批次**——一次送幾百~幾千頁，Google 後台高吞吐跑完再收結果，
**繞過每分鐘 QPM、單價較低**，適合全量 20 檔入庫（線上即時路撞 preview QPM 太慢）。

本模組只做純資料轉換（好單測、0 外呼）；GCS 上傳 / 提交 / 輪詢 / 下載等 I/O 在
``scripts/vision_batch_ingest.py``。請求與回應**照行序對應**（Vertex Gemini batch 的
GCS 輸出保序），page key 由呼叫端以同序 manifest 追蹤。
"""
from __future__ import annotations

import base64

from .vision_schema import PageExtraction

#: Vertex responseSchema（OpenAPI 子集，型別大寫）。對齊 :class:`PageExtraction`，
#: 手寫攤平避免 pydantic schema 的 $ref（Vertex 不吃 $ref）。
_NUM_NULLABLE = {"type": "NUMBER", "nullable": True}
_STR_NULLABLE = {"type": "STRING", "nullable": True}
_LABELLED_VALUE = {
    "type": "OBJECT",
    "properties": {"label": {"type": "STRING"}, "value": _NUM_NULLABLE, "unit": _STR_NULLABLE},
}
RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "page_summary": {"type": "STRING"},
        "charts": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "chart_type": {"type": "STRING"},
                    "title": _STR_NULLABLE,
                    "series": {"type": "ARRAY", "items": _LABELLED_VALUE},
                },
            },
        },
        "table_markdown": _STR_NULLABLE,
        "key_values": {"type": "ARRAY", "items": _LABELLED_VALUE},
        "confidence": {"type": "NUMBER"},
    },
}


def build_request_line(image_bytes: bytes, *, prompt: str) -> dict:
    """組一行 Vertex Gemini batch 請求（inline base64 PNG + structured output）。"""
    b64 = base64.b64encode(image_bytes).decode("ascii")
    return {
        "request": {
            "contents": [{
                "role": "user",
                "parts": [
                    {"text": prompt},
                    {"inlineData": {"mimeType": "image/png", "data": b64}},
                ],
            }],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": RESPONSE_SCHEMA,
                "temperature": 0.0,
            },
        }
    }


def parse_response_line(line: dict) -> PageExtraction | None:
    """從一行 batch 輸出抽 PageExtraction；缺漏 / 被封鎖 / 壞 JSON → None（誠實略過，不瞎掰）。"""
    try:
        cands = ((line or {}).get("response") or {}).get("candidates") or []
        if not cands:
            return None
        parts = (cands[0].get("content") or {}).get("parts") or []
        text = next((p.get("text") for p in parts if p.get("text")), None)
        if not text:
            return None
        return PageExtraction.model_validate_json(text)
    except Exception:  # noqa: BLE001 — 解析失敗一律當 None
        return None
