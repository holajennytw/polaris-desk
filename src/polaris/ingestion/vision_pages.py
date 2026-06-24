"""逐頁產出 page text：文字頁用 pypdf、低文字/簡報頁用 vision。

render + extractor + page_texts 皆可注入 → 單測 0 外呼、0 pymupdf。
真實呼叫端見 scripts/vision_ingest_pilot.py。
"""
from __future__ import annotations

from collections.abc import Callable

from .chunker import extract_pages
from .vision_extract import VisionExtractor, render_page
from .vision_to_text import flatten_extraction, should_vision_route

RenderFn = Callable[..., bytes]


def extract_pages_with_vision(
    pdf_path: str,
    *,
    doc_type: str,
    extractor: VisionExtractor,
    page_texts: list[str] | None = None,
    render: RenderFn = render_page,
) -> list[str]:
    """回每頁的 page text。低文字/簡報頁以 vision 抽取攤平取代。"""
    texts = page_texts if page_texts is not None else extract_pages(pdf_path)
    out: list[str] = []
    for i, text in enumerate(texts, start=1):
        if should_vision_route(text, doc_type=doc_type):
            png = render(pdf_path, i)
            out.append(flatten_extraction(extractor.extract(png, doc_type=doc_type)))
        else:
            out.append(text)
    return out
