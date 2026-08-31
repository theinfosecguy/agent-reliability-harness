"""JSON and Markdown scorecard writers."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def _fault_label(result: dict[str, Any]) -> str:
    labels = [fault["kind"] for fault in result["faults"]]
    if result.get("special_fault"):
        labels.append(result["special_fault"])
    return ", ".join(labels) if labels else "none"


def render_markdown(report: dict[str, Any]) -> str:
    """Render a compact before/after scorecard."""

    before = report["summary"]["unreliable"]
    after = report["summary"]["fixed"]
    improvement = report["summary"]["improvement"]
    lines = [
        "# SAMPLE/DEMO — AI Agent Reliability Scorecard",
        "",
        f"> {report['disclaimer']}",
        "",
        f"Suite: `{report['suite']}` · Case pack: `{report['casepack_version']}` · "
        f"Cases: {report['case_count']} · Repeated trials per case: {report['trials_per_case']}",
        "",
        "## Before / after",
        "",
        "| Implementation | Assertion score | Fully passing trials | Completion rate | Simulated latency | Simulated cost |",
        "|---|---:|---:|---:|---:|---:|",
        f"| Before: unreliable demo | {before['score_percent']:.2f}% "
        f"({before['assertions_passed']}/{before['assertions_total']}) | "
        f"{before['trial_pass_rate_percent']:.2f}% ({before['trials_passed']}/{before['trials_total']}) | "
        f"{before['completion_rate_percent']:.2f}% | {before['latency_ms']} ms | ${before['cost_usd']:.6f} |",
        f"| After: fixed demo | {after['score_percent']:.2f}% "
        f"({after['assertions_passed']}/{after['assertions_total']}) | "
        f"{after['trial_pass_rate_percent']:.2f}% ({after['trials_passed']}/{after['trials_total']}) | "
        f"{after['completion_rate_percent']:.2f}% | {after['latency_ms']} ms | ${after['cost_usd']:.6f} |",
        "",
        f"Improvement: **+{improvement['assertion_score_delta_points']:.2f} percentage points** "
        f"in assertion score and **+{improvement['trial_pass_rate_delta_points']:.2f} points** "
        "in fully passing trials.",
        "",
        "## Case results",
        "",
        "| Case | Injected fault | Before score | After score |",
        "|---|---|---:|---:|",
    ]

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    case_order: list[str] = []
    for result in report["results"]:
        key = (result["case_id"], result["implementation"])
        grouped[key].append(result)
        if result["case_id"] not in case_order:
            case_order.append(result["case_id"])

    for case_id in case_order:
        unreliable = grouped[(case_id, "unreliable")]
        fixed = grouped[(case_id, "fixed")]
        total_before = sum(row["assertion_total"] for row in unreliable)
        total_after = sum(row["assertion_total"] for row in fixed)
        score_before = 100 * sum(row["assertion_score"] for row in unreliable) / total_before
        score_after = 100 * sum(row["assertion_score"] for row in fixed) / total_after
        lines.append(
            f"| `{case_id}` | {_fault_label(unreliable[0])} | {score_before:.2f}% | {score_after:.2f}% |"
        )

    lines.extend(
        [
            "",
            "## Assertions",
            "",
            "Each trial independently checks tool choice, tool order, semantic arguments, final state, "
            "retry recovery, mutation idempotency, duplicate/resume handling, and trace completeness.",
            "",
            "The JSON scorecard contains every per-trial assertion, deterministic seed, final state, "
            "error, and trace event. Latency and cost values are simulated demo telemetry, not production benchmarks.",
            "",
        ]
    )
    return "\n".join(lines)


def write_reports(report: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"sample_demo_{report['suite']}_scorecard"
    json_path = output_dir / f"{stem}.json"
    markdown_path = output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, markdown_path
