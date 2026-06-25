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


_VISION_PROMPT = (
    "你是財報投影片『轉錄器』。只轉錄這張投影片上看得到的文字與數字，"
    "不要推論、不要計算、不要補充頁面上沒有的東西。每個圖表的標籤與數值、"
    "單位如實抽出；有表格轉成 markdown。看不清的數值填 null。"
    "confidence 用 0 到 1 之間的小數表示整體把握度（1=非常確定，不是百分比、不是 1–5 分）。"
)


def _gemini_extract_fn(model: str) -> ExtractFn:
    """真 Gemini structured-output 抽取 fn。client 延遲到**首次呼叫**才建
    （故 active_vision_extractor 只組 closure、不碰 ADC/網路 → 工廠單測 CI-safe）。"""
    cache: dict = {}
    import threading
    _lock = threading.Lock()

    def _client():
        # 雙重檢查鎖：並行模式下多執行緒首呼不會各自建一個 client。
        if "c" not in cache:
            with _lock:
                if "c" not in cache:
                    from google import genai

                    from polaris.config import settings
                    cache["c"] = genai.Client(
                        vertexai=True, project=settings.gcp_project,
                        location=settings.vertex_location,
                    )
        return cache["c"]

    def _once(image_bytes: bytes) -> PageExtraction:
        from google.genai import types
        resp = _client().models.generate_content(
            model=model,
            contents=[_VISION_PROMPT,
                      types.Part.from_bytes(data=image_bytes, mime_type="image/png")],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=PageExtraction,
                temperature=0.0,
            ),
        )
        return PageExtraction.model_validate_json(resp.text)

    def _fn(image_bytes: bytes) -> PageExtraction:
        # 視覺批次（數百頁）會撞 Vertex preview 模型的每分鐘配額（429 RESOURCE_EXHAUSTED）。
        # call_with_retry 已把 429 視為暫時性 → 退避重試；視覺路用較長視窗（配額多以分鐘為
        # 單位重置），讓整批自我節流通過，而非一撞 429 就整批崩潰。
        from polaris.retry import call_with_retry
        return call_with_retry(
            lambda: _once(image_bytes),
            attempts=6, base_delay=2.0, max_delay=60.0,
        )

    return _fn


def render_page(pdf_path: str, page_num: int, *, dpi: int = 150) -> bytes:
    """PDF 第 page_num 頁（1-based）→ PNG bytes（延遲 import pymupdf）。"""
    import fitz

    doc = fitz.open(pdf_path)
    try:
        return doc[page_num - 1].get_pixmap(dpi=dpi).tobytes("png")
    finally:
        doc.close()


def render_page_bytes(pdf_bytes: bytes, page_num: int, *, dpi: int = 150) -> bytes:
    """記憶體 PDF bytes（如 GCS 下載）第 page_num 頁（1-based）→ PNG bytes。"""
    import fitz

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        return doc[page_num - 1].get_pixmap(dpi=dpi).tobytes("png")
    finally:
        doc.close()


def active_vision_extractor() -> "VisionExtractor | None":
    """gate 開才回真抽取器；否則 None（第 4 路 ingestion 關閉、CI 0 外呼）。"""
    from polaris.config import settings

    if not getattr(settings, "vision_extraction", False):
        return None
    return VisionExtractor(
        flash_fn=_gemini_extract_fn(settings.gemini_model_flash),
        pro_fn=_gemini_extract_fn(settings.gemini_model_pro),
        confidence_floor=settings.vision_confidence_floor,
    )
