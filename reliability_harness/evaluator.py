"""Evaluation runner and assertion engine."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from pathlib import Path
from typing import Any

from .agents import IMPLEMENTATIONS
from .cases import select_cases
from .models import CaseDefinition, TraceEvent, TraceRecorder
from .runtime import AgentInterrupted, SyntheticStore, ToolRuntime


ASSERTION_NAMES = (
    "tool_choice",
    "tool_order",
    "tool_arguments",
    "final_state",
    "retry_recovery",
    "idempotency",
    "event_resume_handling",
    "trace_completeness",
)
SUCCESS_OUTCOMES = {"ok", "idempotent_replay"}


def _seed(case_id: str, trial: int) -> int:
    digest = hashlib.sha256(f"sample-demo:{case_id}:{trial}".encode()).hexdigest()
    return int(digest[:8], 16)


def _contains(actual: Any, expected: Any) -> bool:
    """Recursive partial equality for expected state and argument assertions."""

    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            key in actual and _contains(actual[key], value)
            for key, value in expected.items()
        )
    if isinstance(expected, list):
        return actual == expected
    return actual == expected


def _successful_tool_events(events: list[TraceEvent]) -> list[TraceEvent]:
    return [
        event
        for event in events
        if event.event_type == "tool_call" and event.outcome in SUCCESS_OUTCOMES
    ]


def _assertions(
    case: CaseDefinition,
    store: SyntheticStore,
    events: list[TraceEvent],
) -> tuple[dict[str, bool], dict[str, Any]]:
    expected_sequence = case.expected["tool_sequence"]
    tool_events = [event for event in events if event.event_type == "tool_call"]
    successful = _successful_tool_events(events)
    attempted_tools = {event.tool for event in tool_events}
    expected_tools = set(expected_sequence)

    tool_choice = attempted_tools == expected_tools

    first_success: dict[str, int] = {}
    for index, event in enumerate(successful):
        first_success.setdefault(str(event.tool), index)
    tool_order = all(tool in first_success for tool in expected_sequence) and all(
        first_success[left] < first_success[right]
        for left, right in zip(expected_sequence, expected_sequence[1:])
    )

    argument_results: dict[str, bool] = {}
    for tool, expected_args in case.expected["required_args"].items():
        argument_results[tool] = any(
            event.tool == tool and _contains(event.args, expected_args)
            for event in successful
        )
    tool_arguments = all(argument_results.values())

    snapshot = store.snapshot()
    final_state = _contains(snapshot["order"], case.expected["final_order"])
    completed = any(event.event_type == "agent_complete" for event in events)

    retry_faults = {
        fault.tool: fault.kind
        for fault in case.faults
        if fault.kind
        in {"429", "5xx", "timeout", "malformed_result", "5xx_after_commit"}
    }
    retry_checks = {
        tool: sum(event.tool == tool for event in tool_events) >= 2
        for tool in retry_faults
    }
    retry_recovery = completed and all(retry_checks.values()) if retry_faults else True
    if case.special.get("stale_state"):
        retry_recovery = (
            completed
            and any(event.outcome == "stale_state" for event in tool_events)
            and sum(event.tool == "lookup_order" for event in tool_events) >= 2
        )

    issue_events = [event for event in tool_events if event.tool == "issue_refund"]
    notify_events = [event for event in tool_events if event.tool == "notify_customer"]
    mutation_key_safe = True
    for mutation_events in (issue_events, notify_events):
        if len(mutation_events) > 1:
            keys = [event.idempotency_key for event in mutation_events]
            mutation_key_safe = mutation_key_safe and all(keys) and len(set(keys)) == 1
    idempotency = (
        snapshot["order"]["refund_effect_count"] == 1
        and len(snapshot["order"]["notifications"]) == 1
        and mutation_key_safe
    )

    event_resume_handling = True
    if case.special.get("event_copies", 1) > 1:
        event_resume_handling = case.request[
            "event_id"
        ] in store.processed_events and any(
            event.event_type == "duplicate_ignored" for event in events
        )
    if case.special.get("interrupt_after_tool"):
        event_resume_handling = (
            case.request["event_id"] in store.processed_events
            and any(event.event_type == "agent_resume" for event in events)
            and completed
        )

    trace_completeness = bool(events) and all(
        isinstance(event.latency_ms, int)
        and event.latency_ms >= 0
        and isinstance(event.cost_usd, float)
        and event.cost_usd >= 0
        and event.sequence == index
        for index, event in enumerate(events, start=1)
    )

    assertions = {
        "tool_choice": tool_choice,
        "tool_order": tool_order,
        "tool_arguments": tool_arguments,
        "final_state": final_state,
        "retry_recovery": retry_recovery,
        "idempotency": idempotency,
        "event_resume_handling": event_resume_handling,
        "trace_completeness": trace_completeness,
    }
    diagnostics = {
        "attempted_tools": sorted(str(tool) for tool in attempted_tools),
        "successful_tool_order": [event.tool for event in successful],
        "argument_checks": argument_results,
        "retry_checks": retry_checks,
        "completed": completed,
        "final_order": snapshot["order"],
    }
    return assertions, diagnostics


def _run_trial(case: CaseDefinition, implementation: str, trial: int) -> dict[str, Any]:
    event_id = case.request["event_id"]
    trace = TraceRecorder(implementation, case.id, trial, event_id)
    store = SyntheticStore.from_case(case)
    runtime = ToolRuntime(case, store, trace, _seed(case.id, trial))
    agent = IMPLEMENTATIONS[implementation]()
    errors: list[dict[str, str]] = []

    for copy_number in range(1, int(case.special.get("event_copies", 1)) + 1):
        resume_attempt = 0
        while True:
            try:
                agent.run(case.request, runtime)
                break
            except AgentInterrupted as exc:
                resume_attempt += 1
                errors.append(
                    {"type": type(exc).__name__, "code": exc.code, "message": str(exc)}
                )
                runtime.record_agent_event(
                    "harness_resume",
                    copy_number=copy_number,
                    resume_attempt=resume_attempt,
                )
                if resume_attempt >= 2:
                    runtime.record_agent_event("agent_error", code="resume_exhausted")
                    break
            except Exception as exc:  # The harness records a sample agent failure and continues scoring.
                errors.append(
                    {
                        "type": type(exc).__name__,
                        "code": str(getattr(exc, "code", "unhandled")),
                        "message": str(exc),
                    }
                )
                runtime.record_agent_event(
                    "agent_error",
                    code=str(getattr(exc, "code", "unhandled")),
                    exception=type(exc).__name__,
                )
                break

    assertions, diagnostics = _assertions(case, store, trace.events)
    passed_count = sum(assertions.values())
    return {
        "case_id": case.id,
        "case_version": case.version,
        "description": case.description,
        "faults": [
            {"tool": fault.tool, "attempt": fault.attempt, "kind": fault.kind}
            for fault in case.faults
        ],
        "special_fault": case.special.get("fault_label"),
        "implementation": implementation,
        "trial": trial,
        "seed": _seed(case.id, trial),
        "passed": passed_count == len(ASSERTION_NAMES),
        "assertion_score": passed_count,
        "assertion_total": len(ASSERTION_NAMES),
        "assertions": assertions,
        "diagnostics": diagnostics,
        "errors": errors,
        "final_state": store.snapshot(),
        "telemetry": {
            "trace_event_count": len(trace.events),
            "latency_ms": sum(event.latency_ms for event in trace.events),
            "cost_usd": round(sum(event.cost_usd for event in trace.events), 8),
        },
        "trace": [event.to_dict() for event in trace.events],
    }


def _summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        grouped[result["implementation"]].append(result)

    summary: dict[str, Any] = {}
    for implementation in ("unreliable", "fixed"):
        rows = grouped[implementation]
        passed_assertions = sum(row["assertion_score"] for row in rows)
        total_assertions = sum(row["assertion_total"] for row in rows)
        passed_trials = sum(bool(row["passed"]) for row in rows)
        completed_trials = sum(bool(row["diagnostics"]["completed"]) for row in rows)
        summary[implementation] = {
            "label": "BEFORE — deliberately unreliable sample"
            if implementation == "unreliable"
            else "AFTER — fixed sample",
            "score_percent": round(100 * passed_assertions / total_assertions, 2),
            "assertions_passed": passed_assertions,
            "assertions_total": total_assertions,
            "trials_passed": passed_trials,
            "trials_total": len(rows),
            "trial_pass_rate_percent": round(100 * passed_trials / len(rows), 2),
            "completion_rate_percent": round(100 * completed_trials / len(rows), 2),
            "latency_ms": sum(row["telemetry"]["latency_ms"] for row in rows),
            "cost_usd": round(sum(row["telemetry"]["cost_usd"] for row in rows), 8),
        }

    summary["improvement"] = {
        "assertion_score_delta_points": round(
            summary["fixed"]["score_percent"] - summary["unreliable"]["score_percent"],
            2,
        ),
        "trial_pass_rate_delta_points": round(
            summary["fixed"]["trial_pass_rate_percent"]
            - summary["unreliable"]["trial_pass_rate_percent"],
            2,
        ),
    }
    return summary


def _release_gate(
    summary: dict[str, Any],
    min_assertion_score: float,
    min_trial_pass_rate: float,
) -> dict[str, Any]:
    for name, value in (
        ("min_assertion_score", min_assertion_score),
        ("min_trial_pass_rate", min_trial_pass_rate),
    ):
        if not 0.0 <= value <= 100.0:
            raise ValueError(f"{name} must be between 0 and 100")

    fixed = summary["fixed"]
    checks = {
        "assertion_score": {
            "actual_percent": fixed["score_percent"],
            "minimum_percent": float(min_assertion_score),
            "passed": fixed["score_percent"] >= min_assertion_score,
        },
        "fully_passing_trials": {
            "actual_percent": fixed["trial_pass_rate_percent"],
            "minimum_percent": float(min_trial_pass_rate),
            "passed": fixed["trial_pass_rate_percent"] >= min_trial_pass_rate,
        },
    }
    return {
        "passed": all(check["passed"] for check in checks.values()),
        "checks": checks,
    }


def evaluate(
    suite: str = "full",
    trials: int | None = None,
    casepack_path: Path | None = None,
    min_assertion_score: float = 100.0,
    min_trial_pass_rate: float = 100.0,
) -> dict[str, Any]:
    """Run both implementations against a deterministic case suite."""

    if trials is None:
        trials = 2 if suite == "smoke" else 5
    if trials < 1:
        raise ValueError("trials must be at least 1")
    casepack, cases = select_cases(suite, casepack_path)
    results = [
        _run_trial(case, implementation, trial)
        for case in cases
        for implementation in ("unreliable", "fixed")
        for trial in range(1, trials + 1)
    ]
    summary = _summarize(results)
    return {
        "label": "SAMPLE/DEMO — deterministic AI-agent reliability scorecard",
        "disclaimer": casepack["disclaimer"],
        "report_schema_version": "1.0",
        "deterministic_report_time": "2000-01-01T00:00:00Z",
        "suite": suite,
        "trials_per_case": trials,
        "casepack_version": casepack["casepack_version"],
        "case_count": len(cases),
        "implementations": ["unreliable", "fixed"],
        "assertion_names": list(ASSERTION_NAMES),
        "summary": summary,
        "release_gate": _release_gate(
            summary,
            min_assertion_score=min_assertion_score,
            min_trial_pass_rate=min_trial_pass_rate,
        ),
        "results": results,
    }
