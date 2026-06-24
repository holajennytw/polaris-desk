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
