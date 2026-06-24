from polaris.ingestion.vision_schema import PageExtraction
from polaris.ingestion.vision_pages import extract_pages_with_vision


class FakeExtractor:
    def __init__(self): self.calls = []
    def extract(self, image_bytes, *, doc_type):
        self.calls.append(doc_type)
        return PageExtraction(page_summary="VISION:製程別 5奈米: 36%", confidence=0.95)


def test_text_pages_kept_vision_only_for_low_text():
    # 第 1 頁有文字層、第 2 頁是掃描（空字串）
    page_texts = ["這是一段完整文字層的內容，超過門檻足夠長。", ""]
    ex = FakeExtractor()
    out = extract_pages_with_vision(
        "x.pdf", doc_type="transcript", extractor=ex,
        page_texts=page_texts, render=lambda p, n, dpi=150: b"PNG",
    )
    assert out[0] == page_texts[0]                 # 文字頁原樣保留
    assert "VISION:製程別" in out[1]               # 掃描頁走 vision 攤平
    assert ex.calls == ["transcript"]              # 只對第 2 頁呼叫


def test_presentation_all_pages_vision():
    ex = FakeExtractor()
    out = extract_pages_with_vision(
        "x.pdf", doc_type="presentation", extractor=ex,
        page_texts=["有文字也走 vision（簡報）", "另一頁"],
        render=lambda p, n, dpi=150: b"PNG",
    )
    assert all("VISION:" in t for t in out)
    assert ex.calls == ["presentation", "presentation"]


class FlakyExtractor:
    """第 2 頁抽取拋例外（模擬抽取失敗 / 用盡重試的 429）。"""
    def extract(self, image_bytes, *, doc_type):
        raise RuntimeError("boom")


def test_one_page_failure_does_not_abort_batch():
    errors = []
    out = extract_pages_with_vision(
        "x.pdf", doc_type="presentation", extractor=FlakyExtractor(),
        page_texts=["第一頁", "第二頁"],
        render=lambda p, n, dpi=150: b"PNG",
        on_error=lambda i, exc: errors.append((i, str(exc))),
    )
    assert out == ["", ""]                 # 失敗頁 → 誠實空白（不弄垮整批、不瞎掰）
    assert errors == [(1, "boom"), (2, "boom")]   # 每頁失敗都回報，供 Gate1 標記
