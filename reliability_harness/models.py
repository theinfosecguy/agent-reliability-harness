"""Core data types used by the demo harness."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class FaultSpec:
    """A deterministic fault injected into one numbered tool attempt."""

    tool: str
    attempt: int
    kind: str


@dataclass(frozen=True)
class CaseDefinition:
    """One versioned, synthetic evaluation case."""

    id: str
    version: str
    suites: tuple[str, ...]
    description: str
    request: dict[str, Any]
    initial_order: dict[str, Any]
    expected: dict[str, Any]
    faults: tuple[FaultSpec, ...] = ()
    special: dict[str, Any] = field(default_factory=dict)


@dataclass
class TraceEvent:
    """A single deterministic trace event.

    Every event, including orchestration events, carries latency and cost fields.
    This keeps report consumers simple and makes missing telemetry testable.
    """

    sequence: int
    elapsed_ms: int
    event_type: str
    implementation: str
    case_id: str
    trial: int
    event_id: str
    latency_ms: int
    cost_usd: float
    tool: str | None = None
    attempt: int | None = None
    args: dict[str, Any] | None = None
    outcome: str = "ok"
    error_code: str | None = None
    idempotency_key: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "elapsed_ms": self.elapsed_ms,
            "event_type": self.event_type,
            "implementation": self.implementation,
            "case_id": self.case_id,
            "trial": self.trial,
            "event_id": self.event_id,
            "latency_ms": self.latency_ms,
            "cost_usd": round(self.cost_usd, 8),
            "tool": self.tool,
            "attempt": self.attempt,
            "args": self.args,
            "outcome": self.outcome,
            "error_code": self.error_code,
            "idempotency_key": self.idempotency_key,
            "details": self.details,
        }


class TraceRecorder:
    """Records deterministic traces using simulated rather than wall-clock time."""

    def __init__(self, implementation: str, case_id: str, trial: int, event_id: str):
        self.implementation = implementation
        self.case_id = case_id
        self.trial = trial
        self.event_id = event_id
        self._elapsed_ms = 0
        self.events: list[TraceEvent] = []

    def record(
        self,
        event_type: str,
        *,
        latency_ms: int = 0,
        cost_usd: float = 0.0,
        tool: str | None = None,
        attempt: int | None = None,
        args: dict[str, Any] | None = None,
        outcome: str = "ok",
        error_code: str | None = None,
        idempotency_key: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> TraceEvent:
        self._elapsed_ms += latency_ms
        event = TraceEvent(
            sequence=len(self.events) + 1,
            elapsed_ms=self._elapsed_ms,
            event_type=event_type,
            implementation=self.implementation,
            case_id=self.case_id,
            trial=self.trial,
            event_id=self.event_id,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            tool=tool,
            attempt=attempt,
            args=args,
            outcome=outcome,
            error_code=error_code,
            idempotency_key=idempotency_key,
            details=details or {},
        )
        self.events.append(event)
        return event
