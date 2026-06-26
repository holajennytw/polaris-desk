"""切塊器：法說稿 PDF / 純文字 → chunks JSONL（pipeline 的上游）。

**切塊策略（預設值與理由）**：
- **頁為錨**：chunk 不跨頁，metadata 帶 ``page``——憲法 §II 要求引用到
  「法說稿頁碼」，跨頁塊會讓頁碼引用失真。
- **段落優先**：頁內先按段落（空行）聚合至 ``chunk_size``；超長段落硬切
  並帶 ``overlap`` 重疊，避免句子在邊界被腰斬後語意丟失。
- **chunk_size=800 字 / overlap=100**：中文法說稿資訊密度高，800 字
  （≈ 500–600 token）對 768 維 embedding 是穩定區間；R4 可依語料實測調整
  （參數都走 CLI flag，不用改碼）。
- id 形如 ``{ticker}-{period}-p{page:03d}-c{seq:03d}``：確定性、可重跑、
  與 pgvector / BigQuery 的 upsert 鍵相容。

PDF 文字抽取走 ``pypdf``（延遲 import）；掃描檔（無文字層）抽不出內容會
整頁 0 塊——這類檔需 OCR / ColPali 路線（R6），本切塊器誠實跳過不瞎掰。

可用：``python -m polaris.ingestion.chunker 2330.pdf --ticker 2330 --period 2025Q1``
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from polaris.ingestion.sanitize import is_low_information, sanitize_text

#: 預設切塊參數（理由見模組 docstring）。
DEFAULT_CHUNK_SIZE = 800
DEFAULT_OVERLAP = 100

_PARA_SPLIT = re.compile(r"\n\s*\n")


def _is_word_char(ch: str) -> bool:
    """ASCII 英數 = 視為單字內字元。CJK / 標點 / 空白皆為 False，
    故中文（無空格）的詞界回退自然不觸發、行為等同純字元硬切。"""
    return ch.isascii() and ch.isalnum()


def _split_long(text: str, chunk_size: int, overlap: int) -> list[str]:
    """超長段落硬切（帶重疊）。

    切點與「重疊接縫」兩處都避免落在 Latin 單字中間（issue #50：英文逐字稿
    'turnover' 被腰斬成 'tu'+'rnover'，碎字洩進 embedding/檢索/答案）。
    回退只在塊內找得到詞界時發生；整塊為單一巨型 token 則仍硬切以保進度。
    CJK 無 word char → 不觸發回退，與舊版純字元硬切逐字相同（確定性與重疊語意不變）。
    """
    if len(text) <= chunk_size:
        return [text]
    n = len(text)
    chunks: list[str] = []
    start = 0
    while start < n:
        # 接縫對齊：start 落在 Latin 單字中間時前移到詞界（上一塊已含完整字，半截不重複）。
        # 只跳「短的」接縫殘字（≤ overlap）；若這段 Latin run 本身超長（巨型 token，
        # 跨多塊），不可跳過否則會遺字 → 留給下方硬切。
        if start > 0 and _is_word_char(text[start]) and _is_word_char(text[start - 1]):
            nxt = start
            while nxt < n and _is_word_char(text[nxt]) and nxt - start <= overlap:
                nxt += 1
            if nxt < n and not _is_word_char(text[nxt]) and nxt - start <= overlap:
                start = nxt
        end = min(start + chunk_size, n)
        # 切點回退：end 落在 Latin 單字中間時後退到詞界（半截字留給下一塊）。
        if end < n and _is_word_char(text[end]) and _is_word_char(text[end - 1]):
            back = end
            while back > start and _is_word_char(text[back - 1]):
                back -= 1
            if back > start:  # 塊內找得到詞界才回退；否則硬切（單一巨型 token）
                end = back
        chunks.append(text[start:end])
        if end >= n:
            break
        start = max(end - overlap, start + 1)
    return chunks


def chunk_page(text: str, *, chunk_size: int = DEFAULT_CHUNK_SIZE,
               overlap: int = DEFAULT_OVERLAP) -> list[str]:
    """單頁文字 → 塊列表：段落聚合至 chunk_size，超長段落硬切帶重疊。"""
    clean = sanitize_text(text)
    if not clean:
        return []
    paragraphs = [p.strip() for p in _PARA_SPLIT.split(clean) if p.strip()]
    chunks: list[str] = []
    buf = ""
    for para in paragraphs:
        if len(para) > chunk_size:
            if buf:
                chunks.append(buf)
                buf = ""
            chunks.extend(_split_long(para, chunk_size, overlap))
            continue
        candidate = f"{buf}\n{para}" if buf else para
        if len(candidate) > chunk_size:
            chunks.append(buf)
            buf = para
        else:
            buf = candidate
    if buf:
        chunks.append(buf)
    # vision table_markdown 殘留的純分隔列 / 水平線會被硬切成純線條塊，無資訊且稀釋
    # 檢索——在源頭剔除（與 validate_for_ingestion 同準則，雙層防線）。
    return [c for c in chunks if not is_low_information(c)]


def chunk_pages(
    pages: list[str],
    *,
    ticker: str,
    period: str,
    doc_id: str | None = None,
    source: str = "",
    doc_type: str = "",
    published_at: str = "",
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> list[dict]:
    """多頁文字 → pipeline 輸入契約的 chunk dicts（id 確定性、頁碼接地）。

    ``doc_type``（如 ``presentation`` / ``transcript``）與 ``published_at``
    （ISO 日期，如 ``2025-04-17``）若提供就進 metadata —— BigQueryStore 的
    canonical ``doc_type`` / ``published_at`` 欄（cluster 鍵 + 接地日期）靠這兩
    個鍵填值，缺了會寫成 NULL、cluster/filter 形同失效。未提供則不塞空鍵。
    """
    doc = doc_id or f"{ticker}-{period}"
    out: list[dict] = []
    for page_no, text in enumerate(pages, start=1):
        for seq, content in enumerate(
            chunk_page(text, chunk_size=chunk_size, overlap=overlap), start=1
        ):
            out.append({
                "id": f"{ticker}-{period}-p{page_no:03d}-c{seq:03d}",
                "content": content,
                "company": ticker,
                "period": period,
                "metadata": {
                    "doc_id": doc,
                    "page": page_no,
                    **({"source": source} if source else {}),
                    **({"doc_type": doc_type} if doc_type else {}),
                    **({"published_at": published_at} if published_at else {}),
                },
            })
    return out


def extract_pages(path: str | Path) -> list[str]:
    """檔案 → 每頁文字。PDF 走 pypdf（延遲 import）；.txt/.md 視為單頁。"""
    p = Path(path)
    if p.suffix.lower() == ".pdf":
        from pypdf import PdfReader  # 延遲 import（重相依不進必經路徑）

        reader = PdfReader(str(p))
        return [page.extract_text() or "" for page in reader.pages]
    return [p.read_text(encoding="utf-8")]


def write_jsonl(chunks: list[dict], path: str | Path) -> None:
    Path(path).write_text(
        "\n".join(json.dumps(c, ensure_ascii=False) for c in chunks) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m polaris.ingestion.chunker",
        description="法說稿 PDF / 文字 → chunks JSONL（餵 polaris.ingestion 入庫）",
    )
    parser.add_argument("input", help="PDF 或 .txt/.md 檔")
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--period", required=True, help="例 2025Q1")
    parser.add_argument(
        "--doc-type", default="",
        help="文件型別（如 presentation / transcript）→ canonical doc_type 欄 + cluster 鍵",
    )
    parser.add_argument(
        "--published-at", default="",
        help="發布日 ISO 格式（如 2025-04-17）→ canonical published_at 欄（引用接地）",
    )
    parser.add_argument("--out", "-o", default="", help="輸出 JSONL（預設 <input>.chunks.jsonl）")
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    parser.add_argument("--overlap", type=int, default=DEFAULT_OVERLAP)
    args = parser.parse_args(argv)

    pages = extract_pages(args.input)
    chunks = chunk_pages(
        pages,
        ticker=args.ticker,
        period=args.period,
        source=Path(args.input).name,
        doc_type=args.doc_type,
        published_at=args.published_at,
        chunk_size=args.chunk_size,
        overlap=args.overlap,
    )
    out = args.out or f"{args.input}.chunks.jsonl"
    write_jsonl(chunks, out)
    empty_pages = sum(1 for p in pages if not sanitize_text(p))
    print(
        f"{Path(args.input).name}: {len(pages)} 頁 → {len(chunks)} 塊 → {out}"
        + (f"（{empty_pages} 頁無文字層，需 OCR/ColPali 路線）" if empty_pages else "")
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())


__all__ = [
    "DEFAULT_CHUNK_SIZE",
    "DEFAULT_OVERLAP",
    "chunk_page",
    "chunk_pages",
    "extract_pages",
    "write_jsonl",
]
