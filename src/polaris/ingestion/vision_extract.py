"""Gemini vision 抽取器（階梯 Flash→Pro）+ 渲染 + gated 工廠。

外呼（Gemini）以注入式 fn 處理：測試注入 fake → 0 外呼。預設 gate 關
（active_vision_extractor 回 None）→ CI 不 import google-genai / pymupdf。
"""
from __future__ import annotations

from collections.abc import Callable

from .vision_schema import PageExtraction

ExtractFn = Callable[[bytes], PageExtraction]


class VisionExtractor:
    """``extract(image_bytes, doc_type) -> PageExtraction``，階梯升級。"""

    def __init__(self, *, flash_fn: ExtractFn, pro_fn: ExtractFn,
                 confidence_floor: float = 0.6) -> None:
        self.flash_fn = flash_fn
        self.pro_fn = pro_fn
        self.confidence_floor = confidence_floor

    def extract(self, image_bytes: bytes, *, doc_type: str) -> PageExtraction:
        if doc_type == "financial_statement":
            return self.pro_fn(image_bytes)       # 密集數字直接 Pro
        out = self.flash_fn(image_bytes)
        if out.confidence < self.confidence_floor:
            return self.pro_fn(image_bytes)       # 低信心 → 升 Pro
        return out
