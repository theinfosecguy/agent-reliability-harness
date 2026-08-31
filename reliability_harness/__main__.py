"""Command-line entry point for the demo harness."""

from __future__ import annotations

import argparse
from pathlib import Path

from .evaluator import evaluate
from .reporting import write_reports


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the SAMPLE/DEMO deterministic AI-agent reliability evaluation."
    )
    parser.add_argument("--suite", choices=("smoke", "full"), default="full")
    parser.add_argument(
        "--trials",
        type=int,
        default=None,
        help="Repeated trials per case (defaults: smoke=2, full=5).",
    )
    parser.add_argument(
        "--casepack",
        type=Path,
        default=None,
        help="Optional path to a compatible versioned JSON case pack.",
    )
    parser.add_argument(
        "--min-assertion-score",
        type=float,
        default=100.0,
        help="Minimum fixed-implementation assertion score required for the release gate.",
    )
    parser.add_argument(
        "--min-trial-pass-rate",
        type=float,
        default=100.0,
        help="Minimum fixed-implementation fully passing trial rate required for the release gate.",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("reports"))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    report = evaluate(
        args.suite,
        args.trials,
        casepack_path=args.casepack,
        min_assertion_score=args.min_assertion_score,
        min_trial_pass_rate=args.min_trial_pass_rate,
    )
    json_path, markdown_path = write_reports(report, args.output_dir)
    before = report["summary"]["unreliable"]
    after = report["summary"]["fixed"]
    print("SAMPLE/DEMO deterministic AI-agent reliability evaluation")
    print(f"before (unreliable): {before['score_percent']:.2f}% assertion score")
    print(f"after (fixed):       {after['score_percent']:.2f}% assertion score")
    gate = report["release_gate"]
    print(f"release gate:        {'PASS' if gate['passed'] else 'FAIL'}")
    print(f"JSON: {json_path.resolve()}")
    print(f"Markdown: {markdown_path.resolve()}")
    return 0 if gate["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
