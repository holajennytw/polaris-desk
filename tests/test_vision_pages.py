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


def test_throttle_paces_vision_calls_only():
    # 文字頁不該觸發節流（不呼叫 vision）；只有 vision 頁之間 pause。
    slept = []
    ex = FakeExtractor()
    out = extract_pages_with_vision(
        "x.pdf", doc_type="transcript", extractor=ex,
        page_texts=["這是一段完整文字層的內容，超過門檻足夠長。", "", ""],  # 1 文字頁 + 2 掃描頁
        render=lambda p, n, dpi=150: b"PNG",
        pause=1.5, sleep=slept.append,
    )
    assert "VISION:" in out[1] and "VISION:" in out[2]
    assert slept == [1.5, 1.5]            # 只在 2 個 vision 頁後各 pause 一次


class EchoExtractor:
    """回傳 render 出的 bytes 內容（= 頁碼），用來驗並行下輸出仍照頁序。"""
    def extract(self, image_bytes, *, doc_type):
        return PageExtraction(page_summary=f"V:{image_bytes.decode()}", confidence=0.9)


def test_concurrency_preserves_page_order():
    out = extract_pages_with_vision(
        "x.pdf", doc_type="presentation", extractor=EchoExtractor(),
        page_texts=["a", "b", "c", "d", "e"],
        render=lambda p, n, dpi=150: str(n).encode(),   # png 內容 = 頁碼
        concurrency=3,
    )
    assert out == ["V:1", "V:2", "V:3", "V:4", "V:5"]    # 並行但輸出仍照頁序


def test_concurrency_failure_reported_per_page_in_order():
    class Flaky:
        def extract(self, image_bytes, *, doc_type):
            if image_bytes == b"3":          # 第 3 頁失敗
                raise RuntimeError("boom")
            return PageExtraction(page_summary=f"V:{image_bytes.decode()}", confidence=0.9)
    errs = []
    out = extract_pages_with_vision(
        "x.pdf", doc_type="presentation", extractor=Flaky(),
        page_texts=["a", "b", "c", "d"],
        render=lambda p, n, dpi=150: str(n).encode(),
        concurrency=4, on_error=lambda i, exc: errs.append(i),
    )
    assert out == ["V:1", "V:2", "", "V:4"]   # 失敗頁誠實空白、其餘照常
    assert errs == [3]                        # 失敗頁回報（頁碼）


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
