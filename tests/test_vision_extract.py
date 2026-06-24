import os
import tempfile

import pytest

import polaris.config as cfg
from polaris.config import Settings
from polaris.ingestion.vision_extract import (
    VisionExtractor,
    active_vision_extractor,
    render_page,
)
from polaris.ingestion.vision_schema import PageExtraction


def _mk(conf, label="flash"):
    return PageExtraction(page_summary=label, confidence=conf)


def test_flash_only_when_confident():
    calls = []

    def flash(_img):
        calls.append("flash")
        return _mk(0.95, "flash")

    def pro(_img):
        calls.append("pro")
        return _mk(0.99, "pro")

    ex = VisionExtractor(flash_fn=flash, pro_fn=pro, confidence_floor=0.6)
    out = ex.extract(b"img", doc_type="presentation")
    assert out.page_summary == "flash"
    assert calls == ["flash"]            # 信心夠 → 不升 Pro


def test_escalate_to_pro_on_low_confidence():
    calls = []

    def flash(_img):
        calls.append("flash")
        return _mk(0.3, "flash")

    def pro(_img):
        calls.append("pro")
        return _mk(0.97, "pro")

    ex = VisionExtractor(flash_fn=flash, pro_fn=pro, confidence_floor=0.6)
    out = ex.extract(b"img", doc_type="presentation")
    assert out.page_summary == "pro"
    assert calls == ["flash", "pro"]


def test_financial_statement_uses_pro_directly():
    calls = []

    def flash(_img):
        calls.append("flash")
        return _mk(0.95)

    def pro(_img):
        calls.append("pro")
        return _mk(0.99, "pro")

    ex = VisionExtractor(flash_fn=flash, pro_fn=pro, confidence_floor=0.6)
    out = ex.extract(b"img", doc_type="financial_statement")
    assert out.page_summary == "pro"
    assert calls == ["pro"]              # 財報表直接 Pro（密集數字）

def test_factory_none_when_gate_off(monkeypatch):
    monkeypatch.setattr(cfg, "settings", Settings(_env_file=None, vision_extraction=False))
    assert active_vision_extractor() is None     # 預設關 → CI 0 外呼、不 import genai


def test_factory_returns_extractor_when_gate_on(monkeypatch):
    monkeypatch.setattr(cfg, "settings",
                        Settings(_env_file=None, vision_extraction=True))
    ex = active_vision_extractor()
    assert ex is not None
    assert hasattr(ex, "extract")

def test_render_page_smoke():
    fitz = pytest.importorskip("fitz")   # 無 pymupdf 環境 → skip（CI 不裝）
    doc = fitz.open()
    doc.new_page(width=200, height=120)
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        doc.save(f.name)
        path = f.name
    png = render_page(path, 1, dpi=72)
    os.unlink(path)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"   # PNG magic
