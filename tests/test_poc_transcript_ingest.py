"""PoC 法說稿切塊測試（scripts/poc_transcript_ingest.py）。

issue #50 的「相同 bug、不同路徑」：poc 的 ``chunk_text`` 自帶一份純字元硬切
（``text[i:i+size]``），把英文逐字稿的單字從中間腰斬（'turnover' → 'tu' +
'rnover'），碎字洩進 embedding / 檢索 / 答案。這條路徑正是把法說逐字稿灌進
``polaris_core.chunks`` 的那條，重跑會重現 bug。

本測試鎖死契約：poc 切塊**不得把英文單字腰斬**（與
``tests/test_ingestion_chunker.py::test_long_english_paragraph_not_split_mid_word``
同準則），逼 poc 重用 ``polaris.ingestion.chunker`` 的詞界回退邏輯。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_POC_PATH = Path(__file__).resolve().parent.parent / "scripts" / "poc_transcript_ingest.py"
_spec = importlib.util.spec_from_file_location("poc_transcript_ingest", _POC_PATH)
poc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(poc)


def test_long_english_paragraph_not_split_mid_word():
    # 強制多塊：'turnover' ×400 ≈ 3600 字 > CHUNK_CHARS，會走硬切路徑。
    words = ("turnover " * 400).strip()
    chunks = poc.chunk_text(words)
    assert len(chunks) > 1
    for c in chunks:
        fragments = [t for t in c.split() if t != "turnover"]
        assert not fragments, f"單字被腰斬：{fragments}"
