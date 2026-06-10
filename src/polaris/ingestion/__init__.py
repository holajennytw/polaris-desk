"""Ingestion（R4 / SOP §4）：切塊 → 淨化 / 驗證 → embed → 入庫。"""
from polaris.ingestion.chunker import chunk_pages, extract_pages, write_jsonl
from polaris.ingestion.pipeline import (
    IngestReport,
    ingest_chunks,
    ingest_file,
    load_chunks,
)
from polaris.ingestion.sanitize import (
    MAX_CONTENT_CHARS,
    sanitize_text,
    validate_for_ingestion,
)

__all__ = [
    "MAX_CONTENT_CHARS",
    "IngestReport",
    "chunk_pages",
    "extract_pages",
    "ingest_chunks",
    "ingest_file",
    "load_chunks",
    "sanitize_text",
    "validate_for_ingestion",
    "write_jsonl",
]
