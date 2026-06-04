#!/usr/bin/env python3
"""PoC：法說稿 PDF → chunks（文字/語意軌）。

R4 的「照著改」起點，對應 docs/R4_ingestion_開工指南.md §3（法說單軌）。
**這是 PoC、不是正式 ingestion**：示範 解析→淨化→切塊→embedding→Document 的端到端形狀。

刻意**重用 repo 既有介面**（讓 R4 看到真實契約）：
- `polaris.ingestion.sanitize`（入庫前淨化，防投毒）
- `polaris.vectorstore.base.Document`（要組的物件）
- `polaris.llm.gemini.active_llm`（有金鑰→真 embed；無→確定性 placeholder，token=0）

依賴：poppler（pdftotext，本機已裝）；其餘走 repo 套件。

用法：
    python scripts/poc_transcript_ingest.py \\
        --pdf "/path/07_ConferenceCall/2330_TSMC/...Transcript....pdf" \\
        --stock-id 2330 --period 2024Q3 --doc-type transcript
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# 讓 scripts/ 直接跑也能 import polaris（不依賴已安裝）
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from polaris.config import settings  # noqa: E402
from polaris.ingestion.sanitize import sanitize_text, validate_for_ingestion  # noqa: E402
from polaris.llm.gemini import active_llm  # noqa: E402
from polaris.vectorstore.base import Document  # noqa: E402

CHUNK_CHARS = 600   # 中文每塊約 600 字
OVERLAP_CHARS = 80  # 約 13% 重疊（保住跨塊語意）


def pdf_text(pdf: str) -> str:
    return subprocess.run(
        ["pdftotext", "-layout", pdf, "-"], capture_output=True, text=True, check=False
    ).stdout


def chunk_text(text: str, size: int = CHUNK_CHARS, overlap: int = OVERLAP_CHARS) -> list[str]:
    """字元切塊 + 重疊（中文無空白分詞，先用字元切；正式版可換語意切塊）。"""
    text = " ".join(text.split())  # 壓掉多餘換行/空白
    if not text:
        return []
    step = max(1, size - overlap)
    return [text[i : i + size] for i in range(0, len(text), step) if text[i : i + size].strip()]


def embed(text: str, client) -> tuple[list[float], bool]:
    """有金鑰→真 embed；無→確定性 placeholder（全 0、長度=EMBEDDING_DIM，token=0）。"""
    if client is not None:
        return client.embed(text), True
    return [0.0] * settings.embedding_dim, False


def build_documents(
    chunks: list[str], *, stock_id: str, period: str, doc_type: str, client
) -> tuple[list[Document], bool]:
    docs: list[Document] = []
    real = False
    for i, raw in enumerate(chunks):
        content = sanitize_text(raw)                       # 入庫前淨化
        issues = validate_for_ingestion(f"{stock_id}-{i}", content)
        if issues:                                         # 空/過長 → skip
            continue
        vec, is_real = embed(content, client)
        real = real or is_real
        chunk_id = f"{stock_id}_{period}_{doc_type}_{i:04d}"
        docs.append(
            Document(
                id=chunk_id,
                content=content,
                embedding=vec,
                company=stock_id,
                period=period,
                metadata={
                    "doc_type": doc_type,
                    "source_id": chunk_id,                 # 接地（FR-003）
                    "published_at": None,                  # R4：填季末日
                },
            )
        )
    return docs, real


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="法說稿 PoC：PDF → chunks（文字軌）")
    ap.add_argument("--pdf", required=True, help="法說 PDF 路徑")
    ap.add_argument("--stock-id", required=True, help="股票代號，如 2330")
    ap.add_argument("--period", required=True, help="季別，如 2024Q3（對齊 temporal.py）")
    ap.add_argument("--doc-type", default="transcript", help="transcript / presentation")
    args = ap.parse_args(argv)

    if not Path(args.pdf).is_file():
        print(f"找不到檔案：{args.pdf}", file=sys.stderr)
        return 1

    raw = pdf_text(args.pdf)
    chunks = chunk_text(raw)
    client = active_llm()
    docs, real = build_documents(
        chunks, stock_id=args.stock_id, period=args.period, doc_type=args.doc_type, client=client
    )

    print(f"== 法說 PoC：{Path(args.pdf).name} ==")
    print(f"   抽到文字 {len(raw):,} 字 → 切 {len(chunks)} 塊 → 有效 Document {len(docs)} 筆")
    print(f"   embedding: {'真 Gemini（有金鑰）' if real else 'placeholder 全0（無金鑰，token=0）'}"
          f"，維度 {settings.embedding_dim}\n")

    for d in docs[:2]:  # 示範前 2 筆 → 對齊 chunks 表欄位
        print(f"  chunk_id={d.id}")
        print(f"    stock_id={d.company}  fiscal_period={d.period}  doc_type={d.metadata['doc_type']}")
        print(f"    chunk_text={d.content[:50]}…")
        print(f"    embedding[:4]={[round(x, 4) for x in d.embedding[:4]]}（len={len(d.embedding)}）\n")

    print("下一步（R4）：把這些 Document 交給 BigQueryStore.add_documents() 寫進 polaris_core.chunks。")
    print("（接口與映射見 docs/R4_ingestion_開工指南.md §4、§6；search 契約 R3 不變。）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
