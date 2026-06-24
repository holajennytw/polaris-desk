# Vision-OCR-to-text Ingestion Implementation Plan

> ✅ **DONE 2026-06-24** — 全 8 task + 3 個實跑韌性修補已 merge `jenny/main`（`147838b`），745 測試綠。
> pilot（2330+2891）已寫入 `polaris_dev_wayne` 並實測檢索命中。
> 測試/驗證怎麼跑 → [`docs/vision-OCR_測試與驗證指南.md`](../../vision-OCR_測試與驗證指南.md)。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 圖表/掃描頁用 Gemini vision 抽成結構化文字，當作該頁的 page text 餵進**既有** `chunk_pages → ingest_chunks` 流程，進 `chunks` 表 → 文字 3 路 / `/ask`（零新索引、零 /ask 路由）。

**Architecture:** vision 只「補頁面文字」——`extract_pages_with_vision` 對有文字層的頁沿用 pypdf，對低文字/簡報頁 render 成圖 → `VisionExtractor`（階梯 Flash/Pro，structured JSON）→ `flatten_extraction` 攤平成文字。下游 chunking / sanitize / embed / store 完全不動。所有外呼走注入式 seam，預設 gate 關 → CI 0 外呼。

**Tech Stack:** Python 3.13、pydantic、google-genai（Vertex，現役）、pymupdf（新 optional `[vision]`）、既有 `ingestion/chunker.py`+`pipeline.py`。

**Spec:** `docs/superpowers/specs/2026-06-23-vision-ocr-to-text-ingestion-design.md`

---

## File Structure

- **Create** `src/polaris/ingestion/vision_schema.py` — pydantic 抽取結果模型（`Series`/`Chart`/`PageExtraction`）。
- **Create** `src/polaris/ingestion/vision_to_text.py` — 純函式：`should_vision_route`（頁路由判斷）、`flatten_extraction`（結果→文字）。
- **Create** `src/polaris/ingestion/vision_extract.py` — `VisionExtractor`（注入式、階梯）、`render_page`、`active_vision_extractor`（gated 工廠）。
- **Create** `src/polaris/ingestion/vision_pages.py` — `extract_pages_with_vision`（逐頁產出 page text；注入 render + extractor）。
- **Modify** `src/polaris/config.py` — 新增 `vision_extraction` gate 等設定。
- **Modify** `pyproject.toml` — 新增 optional `[vision]` extra（pymupdf）。
- **Create** `scripts/vision_ingest_pilot.py` — pilot：data/<ticker> PDF → page text → chunk → JSONL + Gate1 報告（寫 dev dataset，**不碰 polaris_core**）。
- **Create** 對應 `tests/test_vision_schema.py` / `test_vision_to_text.py` / `test_vision_extract.py` / `test_vision_pages.py`。

---

## Task 1: 抽取結果模型 `vision_schema.py`

**Files:**
- Create: `src/polaris/ingestion/vision_schema.py`
- Test: `tests/test_vision_schema.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_vision_schema.py
from polaris.ingestion.vision_schema import PageExtraction


def test_parses_structured_extraction():
    raw = {
        "page_summary": "2025Q1 製程別營收占比",
        "charts": [{"chart_type": "pie", "title": "製程別",
                    "series": [{"label": "5奈米", "value": 36, "unit": "%"},
                               {"label": "3奈米", "value": 22, "unit": "%"}]}],
        "table_markdown": None,
        "key_values": [{"label": "毛利率", "value": 58.8, "unit": "%"}],
        "confidence": 0.95,
    }
    p = PageExtraction.model_validate(raw)
    assert p.confidence == 0.95
    assert p.charts[0].series[0].label == "5奈米"
    assert p.key_values[0].value == 58.8


def test_value_nullable_no_hallucinated_number():
    p = PageExtraction.model_validate(
        {"page_summary": "x", "charts": [{"chart_type": "bar", "title": None,
         "series": [{"label": "1Q25", "value": None, "unit": "十億"}]}],
         "table_markdown": None, "key_values": [], "confidence": 0.5})
    assert p.charts[0].series[0].value is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev python -m pytest tests/test_vision_schema.py -q`
Expected: FAIL — `ModuleNotFoundError: polaris.ingestion.vision_schema`

- [ ] **Step 3: Write minimal implementation**

```python
# src/polaris/ingestion/vision_schema.py
"""Vision 抽取結果的結構化模型（structured output 的 response_schema）。

value 一律可為 None：頁面上沒印出的數值就留 null，不得編造（接地 / NFR-031）。
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class Series(BaseModel):
    label: str
    value: float | None = None
    unit: str | None = None


class Chart(BaseModel):
    chart_type: str
    title: str | None = None
    series: list[Series] = Field(default_factory=list)


class KeyValue(BaseModel):
    label: str
    value: float | None = None
    unit: str | None = None


class PageExtraction(BaseModel):
    page_summary: str = ""
    charts: list[Chart] = Field(default_factory=list)
    table_markdown: str | None = None
    key_values: list[KeyValue] = Field(default_factory=list)
    confidence: float = 0.0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --extra dev python -m pytest tests/test_vision_schema.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/polaris/ingestion/vision_schema.py tests/test_vision_schema.py
git commit -m "feat(ingestion): vision extraction pydantic schema (nullable values, no hallucination)"
```

---

## Task 2: 純函式 `vision_to_text.py`（頁路由 + 攤平）

**Files:**
- Create: `src/polaris/ingestion/vision_to_text.py`
- Test: `tests/test_vision_to_text.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_vision_to_text.py
from polaris.ingestion.vision_schema import PageExtraction
from polaris.ingestion.vision_to_text import should_vision_route, flatten_extraction


def test_route_scanned_or_presentation():
    assert should_vision_route("", doc_type="transcript") is True          # 0 字 → 掃描頁
    assert should_vision_route("  \n ", doc_type="transcript") is True     # 全空白
    assert should_vision_route("短", doc_type="presentation") is True      # 簡報頁一律 vision
    assert should_vision_route("這是一段有完整文字層的逐字稿內容，超過門檻。",
                               doc_type="transcript") is False             # 有文字 → 文字路


def test_flatten_includes_values_skips_nulls():
    p = PageExtraction.model_validate(
        {"page_summary": "2025Q1 製程別", "charts": [{"chart_type": "pie",
         "title": "製程別", "series": [{"label": "5奈米", "value": 36, "unit": "%"},
                                      {"label": "3奈米", "value": 22, "unit": "%"},
                                      {"label": "未標示", "value": None, "unit": "%"}]}],
         "table_markdown": "| a | b |\n|---|---|\n| 1 | 2 |",
         "key_values": [{"label": "毛利率", "value": 58.8, "unit": "%"}], "confidence": 0.9})
    text = flatten_extraction(p)
    assert "2025Q1 製程別" in text
    assert "5奈米: 36%" in text and "3奈米: 22%" in text
    assert "未標示" not in text          # null 值不輸出（不編造）
    assert "毛利率: 58.8%" in text
    assert "| a | b |" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev python -m pytest tests/test_vision_to_text.py -q`
Expected: FAIL — `ModuleNotFoundError: polaris.ingestion.vision_to_text`

- [ ] **Step 3: Write minimal implementation**

```python
# src/polaris/ingestion/vision_to_text.py
"""Vision 路由判斷 + 結果攤平（純函式，零外呼，好單測）。"""
from __future__ import annotations

from .vision_schema import PageExtraction

#: 頁面非空白字元少於此 → 視為掃描/圖檔頁（pypdf 抽不出文字）。
_TEXT_FLOOR = 20


def should_vision_route(page_text: str, *, doc_type: str) -> bool:
    """簡報頁一律走 vision；其餘頁文字過少（掃描頁）才走 vision。"""
    if doc_type == "presentation":
        return True
    return len("".join((page_text or "").split())) < _TEXT_FLOOR


def _fmt(value: float | None, unit: str | None) -> str:
    return f"{value}{unit or ''}"


def flatten_extraction(p: PageExtraction) -> str:
    """PageExtraction → 可讀且可檢索的 page text。None 值一律略過（接地、不編造）。"""
    lines: list[str] = []
    if p.page_summary:
        lines.append(p.page_summary)
    for kv in p.key_values:
        if kv.value is not None:
            lines.append(f"{kv.label}: {_fmt(kv.value, kv.unit)}")
    for chart in p.charts:
        title = chart.title or chart.chart_type
        pairs = [f"{s.label}: {_fmt(s.value, s.unit)}" for s in chart.series
                 if s.value is not None]
        if pairs:
            lines.append(f"{title}（{chart.chart_type}）: " + "、".join(pairs))
    if p.table_markdown:
        lines.append(p.table_markdown)
    return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --extra dev python -m pytest tests/test_vision_to_text.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/polaris/ingestion/vision_to_text.py tests/test_vision_to_text.py
git commit -m "feat(ingestion): vision page router + flatten-to-text (skip null values)"
```

---

## Task 3: `VisionExtractor`（注入式、階梯 Flash→Pro）

**Files:**
- Create: `src/polaris/ingestion/vision_extract.py`
- Test: `tests/test_vision_extract.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_vision_extract.py
from polaris.ingestion.vision_schema import PageExtraction
from polaris.ingestion.vision_extract import VisionExtractor


def _mk(conf, label="flash"):
    return PageExtraction(page_summary=label, confidence=conf)


def test_flash_only_when_confident():
    calls = []
    flash = lambda img: (calls.append("flash") or _mk(0.95, "flash"))
    pro = lambda img: (calls.append("pro") or _mk(0.99, "pro"))
    ex = VisionExtractor(flash_fn=flash, pro_fn=pro, confidence_floor=0.6)
    out = ex.extract(b"img", doc_type="presentation")
    assert out.page_summary == "flash"
    assert calls == ["flash"]            # 信心夠 → 不升 Pro


def test_escalate_to_pro_on_low_confidence():
    calls = []
    flash = lambda img: (calls.append("flash") or _mk(0.3, "flash"))
    pro = lambda img: (calls.append("pro") or _mk(0.97, "pro"))
    ex = VisionExtractor(flash_fn=flash, pro_fn=pro, confidence_floor=0.6)
    out = ex.extract(b"img", doc_type="presentation")
    assert out.page_summary == "pro"
    assert calls == ["flash", "pro"]


def test_financial_statement_uses_pro_directly():
    calls = []
    flash = lambda img: (calls.append("flash") or _mk(0.95))
    pro = lambda img: (calls.append("pro") or _mk(0.99, "pro"))
    ex = VisionExtractor(flash_fn=flash, pro_fn=pro, confidence_floor=0.6)
    out = ex.extract(b"img", doc_type="financial_statement")
    assert out.page_summary == "pro"
    assert calls == ["pro"]              # 財報表直接 Pro（密集數字）
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev python -m pytest tests/test_vision_extract.py -q`
Expected: FAIL — `ImportError: cannot import name 'VisionExtractor'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/polaris/ingestion/vision_extract.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --extra dev python -m pytest tests/test_vision_extract.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/polaris/ingestion/vision_extract.py tests/test_vision_extract.py
git commit -m "feat(ingestion): VisionExtractor tiered Flash->Pro (injectable, CI-free)"
```

---

## Task 4: config gate + `active_vision_extractor` 工廠

**Files:**
- Modify: `src/polaris/config.py`（在 `top_k` 附近新增）
- Modify: `src/polaris/ingestion/vision_extract.py`（append 工廠 + 真 Gemini fn）
- Test: `tests/test_vision_extract.py`（append）

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_vision_extract.py
from polaris.config import Settings
import polaris.config as cfg
from polaris.ingestion.vision_extract import active_vision_extractor


def test_factory_none_when_gate_off(monkeypatch):
    monkeypatch.setattr(cfg, "settings", Settings(_env_file=None, vision_extraction=False))
    assert active_vision_extractor() is None     # 預設關 → CI 0 外呼、不 import genai


def test_factory_returns_extractor_when_gate_on(monkeypatch):
    monkeypatch.setattr(cfg, "settings",
                        Settings(_env_file=None, vision_extraction=True))
    ex = active_vision_extractor()
    assert ex is not None
    assert hasattr(ex, "extract")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev python -m pytest tests/test_vision_extract.py -q`
Expected: FAIL — `ImportError: cannot import name 'active_vision_extractor'`

- [ ] **Step 3: Write minimal implementation**

Add to `src/polaris/config.py` (after `top_k: int = 8`):

```python
    # --- Vision-OCR ingestion（圖表/掃描頁→文字，spec 2026-06-23）---
    # 預設關：active_vision_extractor() 回 None → CI 0 外呼、不 import genai/pymupdf。
    # 設 VISION_EXTRACTION=1 + 裝 .[vision] 才啟用（離線 ingestion 用）。
    vision_extraction: bool = False
    vision_confidence_floor: float = 0.6
```

Append to `src/polaris/ingestion/vision_extract.py`:

```python
_VISION_PROMPT = (
    "你是財報投影片『轉錄器』。只轉錄這張投影片上看得到的文字與數字，"
    "不要推論、不要計算、不要補充頁面上沒有的東西。每個圖表的標籤與數值、"
    "單位如實抽出；有表格轉成 markdown。看不清的數值填 null。"
)


def _gemini_extract_fn(model: str) -> ExtractFn:
    """真 Gemini structured-output 抽取 fn。client 延遲到**首次呼叫**才建
    （故 active_vision_extractor 只組 closure、不碰 ADC/網路 → 工廠單測 CI-safe）。"""
    cache: dict = {}

    def _client():
        if "c" not in cache:
            from google import genai

            from polaris.config import settings
            cache["c"] = genai.Client(
                vertexai=True, project=settings.gcp_project,
                location=settings.vertex_location,
            )
        return cache["c"]

    def _fn(image_bytes: bytes) -> PageExtraction:
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

    return _fn


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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --extra dev python -m pytest tests/test_vision_extract.py -q`
Expected: PASS (5 passed)。注意 `test_factory_returns_extractor_when_gate_on` 只建物件、不呼叫 `extract`，故不會真的連 Vertex。

- [ ] **Step 5: Commit**

```bash
git add src/polaris/config.py src/polaris/ingestion/vision_extract.py tests/test_vision_extract.py
git commit -m "feat(ingestion): gated active_vision_extractor (Vertex structured output)"
```

---

## Task 5: `render_page` + `[vision]` optional 相依

**Files:**
- Modify: `src/polaris/ingestion/vision_extract.py`（append `render_page`）
- Modify: `pyproject.toml`（`[project.optional-dependencies]` 新增 `vision`）
- Test: `tests/test_vision_extract.py`（append，無 pymupdf 則 skip）

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_vision_extract.py
import pytest


def test_render_page_smoke():
    fitz = pytest.importorskip("fitz")   # 無 pymupdf 環境 → skip（CI 不裝）
    import tempfile, os
    from polaris.ingestion.vision_extract import render_page
    doc = fitz.open()
    doc.new_page(width=200, height=120)
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        doc.save(f.name); path = f.name
    png = render_page(path, 1, dpi=72)
    os.unlink(path)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"   # PNG magic
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev python -m pytest tests/test_vision_extract.py::test_render_page_smoke -q`
Expected: FAIL（或 skip 若無 pymupdf）— `ImportError: cannot import name 'render_page'`

- [ ] **Step 3: Write minimal implementation**

Append to `src/polaris/ingestion/vision_extract.py`:

```python
def render_page(pdf_path: str, page_num: int, *, dpi: int = 150) -> bytes:
    """PDF 第 page_num 頁（1-based）→ PNG bytes（延遲 import pymupdf）。"""
    import fitz

    doc = fitz.open(pdf_path)
    try:
        return doc[page_num - 1].get_pixmap(dpi=dpi).tobytes("png")
    finally:
        doc.close()
```

Add to `pyproject.toml` under `[project.optional-dependencies]`:

```toml
# 圖表/掃描頁 vision ingestion（spec 2026-06-23）：頁面渲染。google-genai 已是核心相依。
# 預設 / CI 不裝 → vision gate 關、不 import。跑 ingestion 才 `uv pip install -e '.[vision]'`。
vision = [
    "pymupdf>=1.24",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --with pymupdf --extra dev python -m pytest tests/test_vision_extract.py::test_render_page_smoke -q`
Expected: PASS（裝了 pymupdf）；不帶 `--with pymupdf` 時為 skipped。

- [ ] **Step 5: Commit**

```bash
git add src/polaris/ingestion/vision_extract.py pyproject.toml tests/test_vision_extract.py
git commit -m "feat(ingestion): render_page (pymupdf) + [vision] optional extra"
```

---

## Task 6: `extract_pages_with_vision`（逐頁產出 page text）

**Files:**
- Create: `src/polaris/ingestion/vision_pages.py`
- Test: `tests/test_vision_pages.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_vision_pages.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev python -m pytest tests/test_vision_pages.py -q`
Expected: FAIL — `ModuleNotFoundError: polaris.ingestion.vision_pages`

- [ ] **Step 3: Write minimal implementation**

```python
# src/polaris/ingestion/vision_pages.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --extra dev python -m pytest tests/test_vision_pages.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/polaris/ingestion/vision_pages.py tests/test_vision_pages.py
git commit -m "feat(ingestion): extract_pages_with_vision (text pages via pypdf, charts via vision)"
```

---

## Task 7: Pilot 腳本 `scripts/vision_ingest_pilot.py`

**Files:**
- Create: `scripts/vision_ingest_pilot.py`

> 重相依 + 真外呼，故為 script 非 CI test。import-safe：gate 關或缺相依時印提示並 return。
> **寫入只到 dev dataset（`Settings.bq_dataset`，預設別設成 polaris_core）；不碰 polaris_core。**

- [ ] **Step 1: Write the script**

```python
# scripts/vision_ingest_pilot.py
"""Vision-OCR ingestion pilot（spec 2026-06-23）。

對 data/<ticker>_*/ 下的法說 PDF：逐頁 → vision 補圖表頁文字 → 切塊 → JSONL，
並產出 Gate1 報告（每頁 summary + confidence）供人工抽查。可選 --ingest 寫 dev dataset。

用法（GPU 不需要，純 Gemini API）：
  export GEMINI_USE_VERTEX=1 VISION_EXTRACTION=1
  uv pip install -e '.[vision]'
  uv run python scripts/vision_ingest_pilot.py --ticker 2330 --ticker 2891
  # 產出 data/vision_chunks/<ticker>.jsonl + data/vision_chunks/<ticker>_gate1.csv
  # 過 Gate1 後再 --ingest（寫 DEV_DATASET），polaris_core 由 R4 另行載入
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import re
from pathlib import Path


def _meta_from_filename(name: str) -> dict:
    # 2330_20250417M01_2025Q1_concall_presentation.pdf
    m = re.match(r"(?P<t>\d+)_(?P<d>\d{8})[ME]\d+_(?P<p>\w+?)_concall_(?P<dt>\w+)\.pdf", name)
    if not m:
        return {}
    d = m.group("d")
    return {"ticker": m.group("t"), "period": m.group("p"),
            "doc_type": m.group("dt"),
            "published_at": f"{d[:4]}-{d[4:6]}-{d[6:]}",
            "source": name}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", action="append", required=True)
    ap.add_argument("--out", default="data/vision_chunks")
    ap.add_argument("--ingest", action="store_true", help="寫 DEV dataset（非 polaris_core）")
    args = ap.parse_args()

    from polaris.config import settings
    from polaris.ingestion.chunker import chunk_pages
    from polaris.ingestion.vision_extract import active_vision_extractor
    from polaris.ingestion.vision_pages import extract_pages_with_vision

    extractor = active_vision_extractor()
    if extractor is None:
        print("⏳ vision gate 關（設 VISION_EXTRACTION=1 + 裝 .[vision]）。")
        return
    if args.ingest and settings.bq_dataset == "polaris_core":
        print("✋ 拒絕：--ingest 不可寫 polaris_core（憲法 III）。請設 DEV dataset。")
        return

    Path(args.out).mkdir(parents=True, exist_ok=True)
    for ticker in args.ticker:
        pdfs = sorted(glob.glob(f"data/{ticker}_*/{ticker}_*M*_concall_*.pdf"))
        all_chunks: list[dict] = []
        gate1_rows: list[dict] = []
        for pdf in pdfs:
            meta = _meta_from_filename(Path(pdf).name)
            if not meta:
                continue
            pages = extract_pages_with_vision(pdf, doc_type=meta["doc_type"], extractor=extractor)
            for i, txt in enumerate(pages, start=1):
                gate1_rows.append({"pdf": Path(pdf).name, "page": i,
                                   "text_preview": txt[:160].replace("\n", " ")})
            chunks = chunk_pages(pages, ticker=meta["ticker"], period=meta["period"],
                                 source=meta["source"], doc_type=meta["doc_type"],
                                 published_at=meta["published_at"])
            all_chunks.extend(chunks)
            print(f"  {Path(pdf).name}: {len(pages)} 頁 → {len(chunks)} 塊")

        jsonl = Path(args.out) / f"{ticker}.jsonl"
        jsonl.write_text("\n".join(json.dumps(c, ensure_ascii=False) for c in all_chunks),
                         encoding="utf-8")
        gate1 = Path(args.out) / f"{ticker}_gate1.csv"
        with gate1.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["pdf", "page", "text_preview"])
            w.writeheader(); w.writerows(gate1_rows)
        print(f"{ticker}: {len(all_chunks)} 塊 → {jsonl}；Gate1 抽查表 → {gate1}")

        if args.ingest:
            from polaris.ingestion.pipeline import ingest_chunks
            from polaris.llm.gemini import active_llm
            from polaris.vectorstore import get_vector_store
            llm = active_llm()
            report = ingest_chunks(all_chunks, store=get_vector_store(),
                                   embed=llm.embed)
            print(f"  ingested {report.ingested} / quarantined {len(report.quarantined)}"
                  f" → {settings.bq_dataset}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify import-safe (gate off)**

Run: `uv run python scripts/vision_ingest_pilot.py --ticker 2330`
Expected: 印 `⏳ vision gate 關…` 並 return（未設 VISION_EXTRACTION）。

- [ ] **Step 3: Ruff + commit**

```bash
uv run --extra dev ruff check scripts/vision_ingest_pilot.py
git add scripts/vision_ingest_pilot.py
git commit -m "feat(ingestion): vision-OCR pilot script (JSONL + Gate1 report; dev dataset only)"
```

---

## Task 8: 全套測試 + lint 綠燈

- [ ] **Step 1: Run full suite**

Run: `uv run --extra dev python -m pytest -q`
Expected: 全綠（既有 + 新增 vision 測試），新測試不需 pymupdf/genai（render smoke 為 skip）。

- [ ] **Step 2: Ruff**

Run: `uv run --extra dev ruff check src/polaris/ingestion/ scripts/vision_ingest_pilot.py`
Expected: All checks passed!

- [ ] **Step 3: Commit any fixes**

```bash
git add -A && git commit -m "test(ingestion): vision-OCR suite green" || echo "nothing to commit"
```

---

## Pilot 執行（程式併入後，由我跑；非 CI）

1. `export GEMINI_USE_VERTEX=1 VISION_EXTRACTION=1`；`uv pip install -e '.[vision]'`
2. 已有 `data/2330_*`（PoC 抓過）；另抓 `python3 .claude/skills/fetch-tw-earnings-call/scripts/fetch_earnings_call.py --ticker 2891 --from 2025 --to 2025`
3. `uv run python scripts/vision_ingest_pilot.py --ticker 2330 --ticker 2891`
4. **Gate1**：R1 抽查 `data/vision_chunks/*_gate1.csv` vs 原頁，數字準確率 ≥95%。
5. 過 Gate1 → 設 DEV dataset 後 `--ingest` 寫 dev 驗 `/ask`；**polaris_core 由 R4 一鍵載入**（憲法 III）。
