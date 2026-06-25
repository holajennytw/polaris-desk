"""visual_reader 查詢期 PDF 來源解析測試（#2）。

源 PDF 真實慣例（見 scripts/vision_ingest_pilot.py）：
``data/{ticker}_*/{ticker}_*_{period}_concall_{type}.pdf``，
例 ``2330_20250417M01_2025Q1_concall_presentation.pdf``。

解析 0 外呼：本地用 tmp_path；gs:// 用注入 fake storage client；render 注入 fake。
"""
from __future__ import annotations

from polaris.graph.nodes.visual_reader import (
    VisualTarget,
    _default_page_image_fn,
    _fetch_gcs_pdf_bytes,
    _find_local_pdf,
)

_TARGET = VisualTarget("2330-2025Q1-p009-c001", "2330", "2025Q1", 9)


# ── 本地解析（真實檔名慣例）─────────────────────────────────────────────────

class TestFindLocalPdf:
    def _make(self, root, name):
        d = root / "2330_2025Q1_concall"
        d.mkdir(exist_ok=True)
        (d / name).write_bytes(b"%PDF-1.4")

    def test_finds_presentation_by_convention(self, tmp_path):
        self._make(tmp_path, "2330_20250417M01_2025Q1_concall_presentation.pdf")
        got = _find_local_pdf(str(tmp_path), "2330", "2025Q1")
        assert got and got.endswith("2330_20250417M01_2025Q1_concall_presentation.pdf")

    def test_prefers_presentation_over_transcript(self, tmp_path):
        self._make(tmp_path, "2330_20250417M01_2025Q1_concall_transcript.pdf")
        self._make(tmp_path, "2330_20250417M01_2025Q1_concall_presentation.pdf")
        got = _find_local_pdf(str(tmp_path), "2330", "2025Q1")
        assert got.endswith("presentation.pdf")  # 圖在簡報，不取逐字稿

    def test_returns_none_when_absent(self, tmp_path):
        assert _find_local_pdf(str(tmp_path), "2330", "2025Q1") is None

    def test_returns_none_when_root_missing(self):
        assert _find_local_pdf("/no/such/dir", "2330", "2025Q1") is None


# ── gs:// 解析（注入 fake client）────────────────────────────────────────────

class _FakeBlob:
    def __init__(self, name: str, data: bytes) -> None:
        self.name = name
        self._data = data

    def download_as_bytes(self) -> bytes:
        return self._data


class _FakeGcsClient:
    def __init__(self, blobs: list[_FakeBlob]) -> None:
        self._blobs = blobs

    def list_blobs(self, bucket: str, prefix: str | None = None):
        return [b for b in self._blobs if b.name.startswith(prefix or "")]


class TestFetchGcsPdfBytes:
    def test_downloads_matching_presentation_blob(self):
        client = _FakeGcsClient([
            _FakeBlob("pdfs/2330/2330_20250417M01_2025Q1_concall_transcript.pdf", b"T"),
            _FakeBlob("pdfs/2330/2330_20250417M01_2025Q1_concall_presentation.pdf", b"P"),
        ])
        out = _fetch_gcs_pdf_bytes("gs://my-bucket/pdfs", "2330", "2025Q1", client=client)
        assert out == b"P"  # 取 presentation

    def test_returns_none_when_no_match(self):
        client = _FakeGcsClient([_FakeBlob("pdfs/2454/x.pdf", b"X")])
        assert _fetch_gcs_pdf_bytes("gs://my-bucket/pdfs", "2330", "2025Q1", client=client) is None


# ── _default_page_image_fn 路由 ──────────────────────────────────────────────

class TestDefaultPageImageFn:
    def test_none_when_corpus_unset(self, monkeypatch):
        from polaris.config import settings
        monkeypatch.setattr(settings, "pdf_corpus_dir", "", raising=False)
        assert _default_page_image_fn(_TARGET) is None

    def test_local_corpus_renders_found_pdf(self, tmp_path, monkeypatch):
        from polaris.config import settings
        from polaris.graph.nodes import visual_reader as vr

        d = tmp_path / "2330_2025Q1_concall"
        d.mkdir()
        (d / "2330_20250417M01_2025Q1_concall_presentation.pdf").write_bytes(b"%PDF")
        monkeypatch.setattr(settings, "pdf_corpus_dir", str(tmp_path), raising=False)
        monkeypatch.setattr(vr, "render_page", lambda path, page, **kw: b"PNG:" + str(page).encode())
        assert _default_page_image_fn(_TARGET) == b"PNG:9"

    def test_gcs_corpus_fetches_and_renders_from_bytes(self, monkeypatch):
        from polaris.config import settings
        from polaris.graph.nodes import visual_reader as vr

        monkeypatch.setattr(settings, "pdf_corpus_dir", "gs://my-bucket/pdfs", raising=False)
        captured = {}

        def fake_fetch(uri_root, ticker, period, **kw):
            captured["args"] = (uri_root, ticker, period)
            return b"%PDF-gcs"

        monkeypatch.setattr(vr, "_fetch_gcs_pdf_bytes", fake_fetch)
        monkeypatch.setattr(vr, "render_page_bytes",
                            lambda data, page, **kw: b"PNG-gcs:" + str(page).encode())
        assert _default_page_image_fn(_TARGET) == b"PNG-gcs:9"
        assert captured["args"] == ("gs://my-bucket/pdfs", "2330", "2025Q1")
