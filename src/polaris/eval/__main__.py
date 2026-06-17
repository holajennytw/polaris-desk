"""CLI：``python -m polaris.eval [--quick N] [題庫.csv]``。

跑題庫 → smoke 達標率（+ Ragas 若 ``[eval]`` extra 就位）→ 印 Markdown 報告。
無金鑰 / CI：全程確定性、token=0（workflow / deep research 走 fallback）。

Ragas 真分啟動條件（同時滿足才跑）：
1. ``uv pip install -e '.[eval]'`` 已裝（ragas + langchain-google-genai）
2. ``GEMINI_API_KEY`` 或 ``GOOGLE_API_KEY`` 已設
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from polaris.eval.dataset import load_dataset
from polaris.eval.report import render_markdown
from polaris.eval.runner import run_dataset
from polaris.eval.score import ragas_available, ragas_score, smoke_score

#: 預設題庫（W2 75 題；隨套件出貨）。
DEFAULT_DATASET = Path(__file__).resolve().parent / "data" / "questions_v0.csv"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m polaris.eval")
    parser.add_argument("dataset", nargs="?", default=str(DEFAULT_DATASET))
    parser.add_argument(
        "--quick", type=int, metavar="N", default=0,
        help="只抽前 N 題（CI 用，省時間；0 = 全跑）",
    )
    args = parser.parse_args(argv)

    items = load_dataset(args.dataset)
    if args.quick:
        items = items[: args.quick]

    records = run_dataset(items)
    report = smoke_score(records)

    # Ragas 真分：有裝 extra + 有金鑰才跑，否則誠實回 None
    r_scores = ragas_score(records)

    # 真檢索是否上線（polaris_core）決定報告標註：有 active_retriever → 真語料煙測，
    # 否則（CI / 無金鑰）走 stub 語料路徑。誠實原則：標題別騙人。
    from polaris.retrieval.retriever import active_retriever

    is_stub = active_retriever() is None

    print(render_markdown(records, report, is_stub_corpus=is_stub, ragas_scores=r_scores))

    if not ragas_available():
        print("（Ragas 未安裝：`uv pip install -e '.[eval]'` 後可跑 CP/Faithfulness/AR）")
    elif r_scores is None:
        print("（Ragas 已安裝但無金鑰 → 真分略過。設 GEMINI_API_KEY 後重跑。）")

    # exit code：紅線（買賣建議 > 0）→ 1；其餘回 0（煙測分不設門檻，真分才設）
    redline_breached = any(not s.checks.get("no_buysell", True) for s in report.scores)
    return 1 if redline_breached else 0


if __name__ == "__main__":  # pragma: no cover — 由 CLI smoke 測 main()
    sys.exit(main())
