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
    concurrency: int = 1,
) -> list[str]:
    """回每頁的 page text。低文字/簡報頁以 vision 抽取攤平取代。

    單頁 render/抽取失敗（如用盡重試的 429）**不弄垮整批**：該頁回空白（誠實略過，
    與掃描頁抽不出文字一致——絕不瞎掰數字），並把 ``(page_num, exc)`` 交給 ``on_error``
    供呼叫端記錄（Gate1 標記失敗頁）。on_error 一律照頁序呼叫。

    ``concurrency``>1 時用 thread pool 同時發 N 個 vision 請求（vision 是 I/O-bound，
    執行緒有效）→ 吞吐約 N 倍，直到吃滿 Vertex 配額。輸出與 on_error 仍嚴格照頁序。

    ``pause``>0 時，**每送出一個 vision 請求後** sleep ``pause`` 秒（文字頁不算）：
    控制送出速率、壓在 QPM 之下避免 429 風暴。``sleep`` 可注入測試。
    """
    texts = page_texts if page_texts is not None else extract_pages(pdf_path)
    out: list[str] = [""] * len(texts)
    # 先分流：哪些頁要走 vision（記 0-based index），文字頁直接落位。
    vision_idx: list[int] = []
    for i, text in enumerate(texts):
        if should_vision_route(text, doc_type=doc_type):
            vision_idx.append(i)
        else:
            out[i] = text

    def _extract(i: int):
        """回 (index, text 或 Exception)。例外不在此拋，交回主執行緒照頁序處理。"""
        try:
            png = render(pdf_path, i + 1)
            return i, flatten_extraction(extractor.extract(png, doc_type=doc_type))
        except Exception as exc:  # noqa: BLE001 — 單頁失敗略過、不丟整批
            return i, exc

    def _place(i: int, res) -> None:
        if isinstance(res, Exception):
            if on_error is not None:
                on_error(i + 1, res)
            out[i] = ""
        else:
            out[i] = res

    if concurrency <= 1:
        for i in vision_idx:
            _place(*_extract(i))
            if pause > 0:
                sleep(pause)
    else:
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = []
            for i in vision_idx:
                futures.append(pool.submit(_extract, i))
                if pause > 0:
                    sleep(pause)  # 控制送出速率（in-flight 上限由 max_workers 把關）
            for fut in futures:  # 依送出（=頁）順序收集 → on_error 照頁序
                _place(*fut.result())
    return out
