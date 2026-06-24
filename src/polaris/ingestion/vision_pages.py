"""逐頁產出 page text：文字頁用 pypdf、低文字/簡報頁用 vision。

render + extractor + page_texts 皆可注入 → 單測 0 外呼、0 pymupdf。
真實呼叫端見 scripts/vision_ingest_pilot.py。
"""
from __future__ import annotations

import time
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
    on_error: Callable[[int, Exception], None] | None = None,
    pause: float = 0.0,
    sleep: Callable[[float], None] = time.sleep,
) -> list[str]:
    """回每頁的 page text。低文字/簡報頁以 vision 抽取攤平取代。

    單頁 render/抽取失敗（如用盡重試的 429）**不弄垮整批**：該頁回空白（誠實略過，
    與掃描頁抽不出文字一致——絕不瞎掰數字），並把 ``(page_num, exc)`` 交給 ``on_error``
    供呼叫端記錄（Gate1 標記失敗頁）。

    ``pause``>0 時，每個 **vision 頁**抽取後 sleep ``pause`` 秒（文字頁不算，因不外呼）：
    主動把請求速率壓在 Vertex preview 模型的 QPM 之下，避免整批 back-to-back 連發撞出
    429 風暴（實測：有間隔的呼叫順利、無間隔的整批連發會被限流）。``sleep`` 可注入測試。
    """
    texts = page_texts if page_texts is not None else extract_pages(pdf_path)
    out: list[str] = []
    for i, text in enumerate(texts, start=1):
        if should_vision_route(text, doc_type=doc_type):
            try:
                png = render(pdf_path, i)
                out.append(flatten_extraction(extractor.extract(png, doc_type=doc_type)))
            except Exception as exc:  # noqa: BLE001 — 單頁失敗略過、不丟整批
                if on_error is not None:
                    on_error(i, exc)
                out.append("")
            if pause > 0:
                sleep(pause)
        else:
            out.append(text)
    return out
