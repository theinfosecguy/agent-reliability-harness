"""Load and validate versioned JSON case packs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import CaseDefinition, FaultSpec


CASEPACK_PATH = Path(__file__).with_name("casepacks") / "v1.json"
SUPPORTED_FAULTS = {
    "429",
    "5xx",
    "timeout",
    "malformed_result",
    "5xx_after_commit",
}
REQUIRED_TOOLS = {
    "lookup_order",
    "get_refund_policy",
    "issue_refund",
    "notify_customer",
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _validate_raw(raw: dict[str, Any]) -> None:
    _require(raw.get("schema_version") == "1.0", "unsupported case-pack schema")
    _require(raw.get("label", "").startswith("SAMPLE/DEMO"), "case pack must be demo-labelled")
    _require(isinstance(raw.get("cases"), list) and raw["cases"], "case pack has no cases")

    ids: set[str] = set()
    for case in raw["cases"]:
        case_id = case.get("id")
        _require(isinstance(case_id, str) and case_id, "case id is required")
        _require(case_id not in ids, f"duplicate case id: {case_id}")
        ids.add(case_id)
        _require(isinstance(case.get("version"), str), f"{case_id}: version is required")
        _require(set(case.get("suites", ())) <= {"smoke", "full"}, f"{case_id}: invalid suite")
        expected_tools = set(case.get("expected", {}).get("tool_sequence", ()))
        _require(expected_tools == REQUIRED_TOOLS, f"{case_id}: expected tool set is incomplete")
        for fault in case.get("faults", ()):
            _require(fault.get("kind") in SUPPORTED_FAULTS, f"{case_id}: unsupported fault")
            _require(fault.get("tool") in REQUIRED_TOOLS, f"{case_id}: invalid fault tool")
            _require(isinstance(fault.get("attempt"), int), f"{case_id}: fault attempt must be int")


def load_casepack(path: Path | None = None) -> tuple[dict[str, Any], list[CaseDefinition]]:
    """Load the bundled case pack, returning metadata and typed cases."""

    source = path or CASEPACK_PATH
    with source.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    _validate_raw(raw)
    cases = [
        CaseDefinition(
            id=item["id"],
            version=item["version"],
            suites=tuple(item["suites"]),
            description=item["description"],
            request=dict(item["request"]),
            initial_order=dict(item["initial_order"]),
            expected=dict(item["expected"]),
            faults=tuple(FaultSpec(**fault) for fault in item.get("faults", ())),
            special=dict(item.get("special", {})),
        )
        for item in raw["cases"]
    ]
    metadata = {key: value for key, value in raw.items() if key != "cases"}
    return metadata, cases


def select_cases(suite: str, path: Path | None = None) -> tuple[dict[str, Any], list[CaseDefinition]]:
    """Return cases for a named suite; full contains all smoke cases too."""

    if suite not in {"smoke", "full"}:
        raise ValueError(f"unknown suite: {suite}")
    metadata, cases = load_casepack(path)
    selected = [case for case in cases if suite in case.suites]
    if not selected:
        raise ValueError(f"suite contains no cases: {suite}")
    return metadata, selected
