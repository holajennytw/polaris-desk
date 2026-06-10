"""切塊器測試（R4 / chunks JSONL 上游）。全程離線、不需 pypdf（.txt 路徑）。"""
from __future__ import annotations

import json

from polaris.ingestion.chunker import (
    DEFAULT_CHUNK_SIZE,
    chunk_page,
    chunk_pages,
    extract_pages,
    main,
    write_jsonl,
)
from polaris.ingestion.pipeline import ingest_chunks, load_chunks
from tests.test_ingestion_pipeline import FakeStore, fake_embed

PAGE_1 = "台積電 2025Q1 法說會。\n\n營收受 AI 需求帶動成長。\n\n毛利率受匯率影響。"
PAGE_2 = "資本支出維持高檔。\n\n海外擴廠按計畫進行。"


class TestChunkPage:
    def test_short_paragraphs_merged_into_one_chunk(self):
        chunks = chunk_page(PAGE_1)
        assert len(chunks) == 1
        assert "營收" in chunks[0] and "毛利率" in chunks[0]

    def test_respects_chunk_size_boundary(self):
        paras = "\n\n".join(["甲" * 300, "乙" * 300, "丙" * 300])
        chunks = chunk_page(paras, chunk_size=650)
        assert len(chunks) == 2  # 300+300 併一塊、第三段另起
        assert all(len(c) <= 650 for c in chunks)

    def test_long_paragraph_hard_split_with_overlap(self):
        text = "長" * 2000
        chunks = chunk_page(text, chunk_size=800, overlap=100)
        assert all(len(c) <= 800 for c in chunks)
        # 重疊：前塊尾 100 字 = 後塊頭 100 字
        assert chunks[0][-100:] == chunks[1][:100]

    def test_empty_or_whitespace_page_zero_chunks(self):
        assert chunk_page("") == []
        assert chunk_page("   \n\n  ") == []

    def test_sanitizes_before_chunking(self):
        chunks = chunk_page("內容<!-- injected -->​正常")
        assert "<!--" not in chunks[0]


class TestChunkPages:
    def test_ids_deterministic_and_page_grounded(self):
        chunks = chunk_pages([PAGE_1, PAGE_2], ticker="2330", period="2025Q1")
        assert chunks[0]["id"] == "2330-2025Q1-p001-c001"
        assert chunks[0]["metadata"]["page"] == 1
        assert chunks[1]["id"] == "2330-2025Q1-p002-c001"
        assert chunks[1]["metadata"]["page"] == 2
        ids = [c["id"] for c in chunks]
        assert len(ids) == len(set(ids))

    def test_rerun_identical(self):
        a = chunk_pages([PAGE_1], ticker="2330", period="2025Q1")
        b = chunk_pages([PAGE_1], ticker="2330", period="2025Q1")
        assert a == b

    def test_scanned_page_without_text_skipped(self):
        """掃描頁（無文字層）→ 0 塊、不瞎掰；其餘頁照常。"""
        chunks = chunk_pages(["", PAGE_2], ticker="2330", period="2025Q1")
        assert all(c["metadata"]["page"] == 2 for c in chunks)


class TestEndToEnd:
    def test_chunker_output_feeds_pipeline(self, tmp_path):
        """chunker JSONL → pipeline 入庫，契約對齊（整條資料路打通）。"""
        chunks = chunk_pages([PAGE_1, PAGE_2], ticker="2330", period="2025Q1",
                             source="2330_2025Q1.pdf")
        out = tmp_path / "chunks.jsonl"
        write_jsonl(chunks, out)
        store = FakeStore()
        report = ingest_chunks(load_chunks(out), store=store, embed=fake_embed)
        assert report.ingested == len(chunks)
        assert report.quarantined == []
        doc = store.added[0]
        assert doc.company == "2330"
        assert doc.metadata["page"] == 1
        assert doc.metadata["source"] == "2330_2025Q1.pdf"

    def test_extract_pages_txt(self, tmp_path):
        p = tmp_path / "transcript.txt"
        p.write_text(PAGE_1, encoding="utf-8")
        pages = extract_pages(p)
        assert len(pages) == 1 and "台積電" in pages[0]

    def test_cli_main_txt_to_jsonl(self, tmp_path, capsys):
        src = tmp_path / "2330.txt"
        src.write_text(PAGE_1, encoding="utf-8")
        out = tmp_path / "out.jsonl"
        code = main([str(src), "--ticker", "2330", "--period", "2025Q1",
                     "-o", str(out)])
        assert code == 0
        rows = [json.loads(line) for line in out.read_text().splitlines()]
        assert rows[0]["company"] == "2330"
        assert "1 頁" in capsys.readouterr().out


def test_default_chunk_size_sane():
    assert 400 <= DEFAULT_CHUNK_SIZE <= 1200  # 768 維 embedding 穩定區間
