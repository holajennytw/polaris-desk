"""visual_reader 節點（Phase B：查詢期 vision 讀圖 escalation）。

ColPali 退役後，看圖題（場景 3）預設走文字 workflow（Vision-OCR 入庫已把圖表
文字灌進索引）。但若檢索回來的文字脈絡**缺數字**，代表該圖表的數值沒被 OCR 進
那些 chunk —— 此時升級：render 被引用頁 → gemini vision 讀圖 → 攤平成文字脈絡
回給 writer。

設計原則（與 ingestion vision 路一致）：
- **flag-gated 預設關**（``settings.visual_reader``）→ prod 行為零變動、CI 0 外呼。
- **注入式外呼**：``VisionExtractor`` 與 ``page_image_fn`` 皆可注入，純函式好單測。
- **誠實不編造**：定位不到 PDF（``page_image_fn`` 回 None）或抽取空白 → 略過該頁，
  不憑空生脈絡（接地 / NFR-031）。

⚠️ 查詢期 PDF 來源未解：chunk ``source_id`` 只帶頁碼，不帶 PDF 路徑。``_default_page_
image_fn`` 目前依 ``settings.pdf_corpus_dir`` 的本地慣例解析；無設定 / 找不到檔 → 回
None（節點 no-op）。GCS / Drive 取檔為後續整合點。
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from polaris.ingestion.vision_extract import (
    active_vision_extractor,
    render_page,
    render_page_bytes,
)
from polaris.ingestion.vision_to_text import flatten_extraction
from polaris.ontology import company_name

#: chunk id 形如 ``{ticker}-{period}-p{page:03d}-c{seq:03d}``；抓頁碼。
_PAGE_RE = re.compile(r"-p(\d{1,4})-c\d+")

#: 看圖題關鍵詞：問題提到「圖 / 圖表 / 走勢 / 趨勢 / chart / figure」才考慮升級。
_CHART_HINTS = ("圖", "走勢", "趨勢", "chart", "figure", "diagram")


@dataclass(frozen=True)
class VisualTarget:
    """一個待讀的圖表頁：來源 chunk + 解析出的公司/季別/頁碼。"""

    source_id: str
    company: str | None
    period: str | None
    page: int


PageImageFn = Callable[[VisualTarget], "bytes | None"]


def parse_target(context: dict[str, Any]) -> VisualTarget | None:
    """contexts dict → :class:`VisualTarget`；無 ``-pNNN-c`` 頁段（URL/stub）回 None。"""
    sid = context.get("source_id") or ""
    m = _PAGE_RE.search(sid)
    if not m:
        return None
    return VisualTarget(
        source_id=sid,
        company=context.get("company"),
        period=context.get("period"),
        page=int(m.group(1)),
    )


def _has_number(text: str) -> bool:
    return any(ch.isdigit() for ch in text or "")


def should_escalate(question: str, contexts: list[dict[str, Any]]) -> bool:
    """看圖題且檢索文字脈絡全無數字 → 升級讀圖。

    保守觸發：只要任一脈絡已含數字（文字路已能答），就不付 vision 成本。門檻交由
    eval 校準（specs/004）。
    """
    if not any(h in (question or "") for h in _CHART_HINTS):
        return False
    return not any(_has_number(c.get("text", "")) for c in (contexts or []))


def read_visual_pages(
    question: str,
    contexts: list[dict[str, Any]],
    *,
    extractor: Any,
    page_image_fn: PageImageFn,
    doc_type: str = "presentation",
    max_pages: int = 2,
) -> list[dict[str, Any]]:
    """對被引用的前 ``max_pages`` 個圖表頁讀圖，回新增的 vision 脈絡 dict 清單。

    去重以 (company, period, page) 為鍵（同頁不同 chunk 只讀一次）。取不到頁圖
    （``page_image_fn`` 回 None）或抽取攤平為空 → 略過該頁，不編造。
    """
    targets: list[VisualTarget] = []
    seen: set[tuple] = set()
    for ctx in contexts or []:
        t = parse_target(ctx)
        if t is None:
            continue
        key = (t.company, t.period, t.page)
        if key in seen:
            continue
        seen.add(key)
        targets.append(t)
        if len(targets) >= max_pages:
            break

    out: list[dict[str, Any]] = []
    for t in targets:
        image = page_image_fn(t)
        if not image:
            continue
        text = flatten_extraction(extractor.extract(image, doc_type=doc_type))
        if not text.strip():
            continue
        out.append(
            {
                "source_id": t.source_id,
                "text": text,
                "period": t.period,
                "company": t.company,
                "company_name": company_name(t.company) if t.company else None,
                "origin": "vision",
                "event_key": None,
                "source_key": None,
                "published_yyyymm": None,
            }
        )
    return out


#: 源 PDF 檔名慣例（見 scripts/vision_ingest_pilot.py）：
#: ``{ticker}_{YYYYMMDD}M{nn}_{period}_concall_{type}.pdf``。看圖題優先取 presentation
#: （圖在簡報、不在逐字稿），否則退而取同期任一 concall PDF。
def _pdf_globs(ticker: str, period: str) -> tuple[str, str]:
    return (
        f"{ticker}_*_{period}_concall_presentation.pdf",
        f"{ticker}_*_{period}_concall_*.pdf",
    )


def _find_local_pdf(root: str, ticker: str, period: str) -> str | None:
    """在本地 ``root`` 遞迴找符合慣例的 PDF；presentation 優先。找不到 → None。"""
    from pathlib import Path

    base = Path(root)
    if not base.is_dir():
        return None
    for pat in _pdf_globs(ticker, period):
        hits = sorted(base.glob(f"**/{pat}"))
        if hits:
            return str(hits[0])
    return None


def _fetch_gcs_pdf_bytes(
    uri_root: str, ticker: str, period: str, *, client: Any = None
) -> bytes | None:
    """``gs://bucket/prefix`` 下依慣例找 PDF blob → 下載 bytes；presentation 優先。

    ``client`` 可注入（測試）；prod 延遲 import google-cloud-storage。找不到 → None。
    """
    if not uri_root.startswith("gs://"):
        return None
    rest = uri_root[len("gs://"):].rstrip("/")
    bucket, _, prefix = rest.partition("/")
    if client is None:
        from google.cloud import storage  # 延遲 import（重相依不進 CI 必經路徑）

        from polaris.config import settings
        client = storage.Client(project=settings.gcp_project)

    blobs = list(client.list_blobs(bucket, prefix=prefix or None))
    for suffix in (f"{period}_concall_presentation.pdf", f"{period}_concall_"):
        for b in blobs:
            name = b.name
            if name.endswith(".pdf") and f"/{ticker}_" in f"/{name}" and suffix in name:
                return b.download_as_bytes()
    return None


def _default_page_image_fn(target: VisualTarget) -> bytes | None:
    """prod 頁圖解析：``settings.pdf_corpus_dir`` 為本地目錄或 ``gs://`` URI。

    依真實檔名慣例找該公司/季別的 concall PDF → render 第 ``target.page`` 頁為 PNG。
    無設定 / 找不到 / render 失敗 → None（節點 no-op，誠實不編造）。
    """
    from polaris.config import settings

    corpus = getattr(settings, "pdf_corpus_dir", "") or ""
    if not corpus or not target.company or not target.period:
        return None
    try:
        if corpus.startswith("gs://"):
            data = _fetch_gcs_pdf_bytes(corpus, target.company, target.period)
            return render_page_bytes(data, target.page) if data else None
        path = _find_local_pdf(corpus, target.company, target.period)
        return render_page(path, target.page) if path else None
    except Exception:  # noqa: BLE001 — 取圖失敗不可弄垮 workflow，誠實退 None
        return None


def visual_reader(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph 節點：flag 開 + 觸發 + gate 開 → 追加 vision 脈絡；否則 no-op（回 {}）。

    never halts：讀圖是 best-effort 加分，失敗只是不加脈絡，不中斷 workflow。
    """
    from polaris.config import settings

    if not getattr(settings, "visual_reader", False):
        return {}

    question = state.get("query", "")
    contexts = state.get("contexts") or []
    if not should_escalate(question, contexts):
        return {}

    extractor = active_vision_extractor()
    if extractor is None:  # vision gate 關 → 無能力，誠實 no-op
        return {}

    try:
        new = read_visual_pages(
            question, contexts, extractor=extractor, page_image_fn=_default_page_image_fn
        )
    except Exception:  # noqa: BLE001 — best-effort 加分；任何外呼失敗都不得弄垮 workflow
        return {}
    if not new:
        return {}
    return {"contexts": contexts + new}


__all__ = [
    "VisualTarget",
    "parse_target",
    "should_escalate",
    "read_visual_pages",
    "visual_reader",
]
