"""``python -m polaris.eval`` 正式 CLI。

smoke 為 token-free；flash 用 Gemini RAGAS；gate 使用全 130 題 RAGAS 與
Claude/GPT/Gemini 三方投票。所有模式皆輸出可追溯 artifacts。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from polaris.eval.dataset import load_dataset, validate_dataset
from polaris.eval.errors import EvalConfigurationError, EvalExecutionError
from polaris.eval.report import build_summary, write_eval_artifacts
from polaris.eval.runner import read_records_jsonl, run_dataset
from polaris.eval.score import score_records

DEFAULT_DATASET = Path(__file__).resolve().parent / "data" / "questions_v1.csv"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m polaris.eval")
    parser.add_argument("dataset_positional", nargs="?", type=Path)
    parser.add_argument("--dataset", type=Path)
    parser.add_argument("--mode", choices=("smoke", "flash", "gate"), default="smoke")
    parser.add_argument(
        "--quick",
        nargs="?",
        const=3,
        type=int,
        metavar="N",
        help="只執行前 N 題；省略 N 時預設 3 題",
    )
    parser.add_argument(
        "--skip-ragas",
        action="store_true",
        help="相容 alias：等同 --mode smoke",
    )
    parser.add_argument("--reuse-records", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("eval_reports"))
    args = parser.parse_args(argv)

    mode = "smoke" if args.skip_ragas else args.mode
    dataset_path = args.dataset or args.dataset_positional or DEFAULT_DATASET
    try:
        if args.reuse_records:
            records = read_records_jsonl(args.reuse_records)
            items = [record.item for record in records]
        else:
            items = load_dataset(dataset_path)
            if args.quick:
                items = items[: args.quick]
            records = run_dataset(items)

        if mode == "gate":
            validate_dataset(items, expected_count=130, required_gate_count=10)

        report = score_records(records, mode=mode)
        paths = write_eval_artifacts(
            records,
            report,
            output_dir=args.output_dir,
            dataset_path=dataset_path if not args.reuse_records else None,
        )
    except (EvalConfigurationError, EvalExecutionError, ValueError, OSError) as exc:
        print(f"Eval configuration/execution error: {exc}", file=sys.stderr)
        return 2

    summary = build_summary(records, report)
    print(
        f"Polaris eval ({mode}): {summary['pass_count']}/{summary['total_cases']} "
        f"({summary['pass_rate']:.2%})"
    )
    for name, path in paths.items():
        print(f"{name}: {path}")
    if summary["smoke_test"]:
        print("W1 分數只是 pipeline smoke test，不是真實 RAGAS 評估分數")
    return 0 if report.gate_passed else 1


if __name__ == "__main__":
    sys.exit(main())
