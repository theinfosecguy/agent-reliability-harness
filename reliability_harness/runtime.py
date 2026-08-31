"""Synthetic tools, state, and deterministic fault injection."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

from .models import CaseDefinition, FaultSpec, TraceRecorder


class ToolError(RuntimeError):
    """Base class for synthetic tool failures."""

    code = "tool_error"


class RetryableToolError(ToolError):
    """A retryable synthetic transport or service failure."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class MalformedToolResult(ToolError):
    code = "malformed_result"


class StaleStateError(ToolError):
    code = "stale_state"


class AgentInterrupted(ToolError):
    code = "interrupted"


@dataclass
class SyntheticStore:
    """Isolated in-memory state for one case trial."""

    order: dict[str, Any]
    idempotency_results: dict[str, dict[str, Any]] = field(default_factory=dict)
    processed_events: set[str] = field(default_factory=set)
    checkpoints: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def from_case(cls, case: CaseDefinition) -> "SyntheticStore":
        order = copy.deepcopy(case.initial_order)
        order.setdefault("status", "paid")
        order.setdefault("refunded_amount", 0.0)
        order.setdefault("refund_effect_count", 0)
        order.setdefault("notifications", [])
        order.setdefault("version", 1)
        return cls(order=order)

    def snapshot(self) -> dict[str, Any]:
        """Return a stable, JSON-compatible state snapshot."""

        return {
            "order": copy.deepcopy(self.order),
            "processed_events": sorted(self.processed_events),
            "checkpoints": copy.deepcopy(self.checkpoints),
            "idempotency_key_count": len(self.idempotency_results),
        }


class ToolRuntime:
    """Executes local tools and injects faults declared by a case."""

    BASE_LATENCY_MS = {
        "lookup_order": 12,
        "get_refund_policy": 8,
        "issue_refund": 24,
        "notify_customer": 15,
    }
    BASE_COST_USD = {
        "lookup_order": 0.00004,
        "get_refund_policy": 0.00003,
        "issue_refund": 0.00009,
        "notify_customer": 0.00005,
    }

    def __init__(
        self,
        case: CaseDefinition,
        store: SyntheticStore,
        trace: TraceRecorder,
        seed: int,
    ) -> None:
        self.case = case
        self.store = store
        self.trace = trace
        self.seed = seed
        self.attempts: dict[str, int] = {}
        self._stale_injected = False
        self._interrupt_injected = False

    def _fault(self, tool: str, attempt: int) -> FaultSpec | None:
        return next(
            (fault for fault in self.case.faults if fault.tool == tool and fault.attempt == attempt),
            None,
        )

    def _latency(self, tool: str, attempt: int) -> int:
        # Seed jitter is deterministic and deliberately small.
        return self.BASE_LATENCY_MS[tool] + attempt + (self.seed % 3)

    def _record_tool(
        self,
        tool: str,
        attempt: int,
        args: dict[str, Any],
        *,
        outcome: str,
        error_code: str | None = None,
        idempotency_key: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.trace.record(
            "tool_call",
            latency_ms=self._latency(tool, attempt),
            cost_usd=self.BASE_COST_USD[tool],
            tool=tool,
            attempt=attempt,
            args=copy.deepcopy(args),
            outcome=outcome,
            error_code=error_code,
            idempotency_key=idempotency_key,
            details=details,
        )

    def record_agent_event(self, event_type: str, **details: Any) -> None:
        self.trace.record(event_type, latency_ms=0, cost_usd=0.0, details=details)

    def call(
        self,
        tool: str,
        args: dict[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Call a synthetic tool.

        Faults are keyed to exact attempt numbers, making every trial replayable.
        """

        if tool not in self.BASE_LATENCY_MS:
            raise ValueError(f"unknown tool: {tool}")
        attempt = self.attempts.get(tool, 0) + 1
        self.attempts[tool] = attempt
        fault = self._fault(tool, attempt)

        if fault and fault.kind in {"429", "5xx", "timeout"}:
            code = {"429": "429", "5xx": "503", "timeout": "timeout"}[fault.kind]
            self._record_tool(
                tool,
                attempt,
                args,
                outcome="error",
                error_code=code,
                idempotency_key=idempotency_key,
                details={"injected_fault": fault.kind, "phase": "before_execution"},
            )
            raise RetryableToolError(code, f"injected {fault.kind} on {tool}")

        # An idempotency replay represents an already accepted mutation. Resolve
        # it before re-evaluating optimistic-concurrency preconditions, which may
        # legitimately have changed because of that first mutation.
        cache_key = f"{tool}:{idempotency_key}" if idempotency_key else None
        if cache_key and cache_key in self.store.idempotency_results:
            result = copy.deepcopy(self.store.idempotency_results[cache_key])
            self._record_tool(
                tool,
                attempt,
                args,
                outcome="idempotent_replay",
                idempotency_key=idempotency_key,
            )
            return result

        if tool == "issue_refund" and self.case.special.get("stale_state") and not self._stale_injected:
            self._stale_injected = True
            patch = self.case.special.get("concurrent_order_patch", {})
            self.store.order.update(copy.deepcopy(patch))
            self.store.order["version"] += 1
            self.trace.record(
                "synthetic_concurrent_update",
                latency_ms=1,
                cost_usd=0.0,
                details={"new_version": self.store.order["version"], "patch": patch},
            )

        if tool == "issue_refund":
            supplied_version = args.get("expected_version")
            if supplied_version is not None and supplied_version != self.store.order["version"]:
                self._record_tool(
                    tool,
                    attempt,
                    args,
                    outcome="stale_state",
                    error_code="stale_state",
                    idempotency_key=idempotency_key,
                    details={"actual_version": self.store.order["version"]},
                )
                raise StaleStateError("order changed after it was read")

        result = self._execute(tool, args)
        if cache_key:
            self.store.idempotency_results[cache_key] = copy.deepcopy(result)

        if fault and fault.kind == "malformed_result":
            malformed = {"malformed": True}
            self._record_tool(
                tool,
                attempt,
                args,
                outcome="malformed",
                error_code="malformed_result",
                idempotency_key=idempotency_key,
                details={"injected_fault": fault.kind},
            )
            return malformed

        if fault and fault.kind == "5xx_after_commit":
            self._record_tool(
                tool,
                attempt,
                args,
                outcome="error_after_commit",
                error_code="503",
                idempotency_key=idempotency_key,
                details={"injected_fault": fault.kind, "phase": "after_execution"},
            )
            raise RetryableToolError("503", f"injected 5xx after {tool} committed")

        interrupt_tool = self.case.special.get("interrupt_after_tool")
        if tool == interrupt_tool and not self._interrupt_injected:
            self._interrupt_injected = True
            self._record_tool(
                tool,
                attempt,
                args,
                outcome="interrupted_after_commit",
                error_code="interrupted",
                idempotency_key=idempotency_key,
                details={"injected_fault": "interrupted_resumed_run"},
            )
            raise AgentInterrupted(f"interrupted after {tool} committed")

        self._record_tool(
            tool,
            attempt,
            args,
            outcome="ok",
            idempotency_key=idempotency_key,
        )
        return copy.deepcopy(result)

    def _execute(self, tool: str, args: dict[str, Any]) -> dict[str, Any]:
        order = self.store.order
        if args.get("order_id") and args["order_id"] != order["order_id"]:
            raise ToolError("unknown synthetic order")

        if tool == "lookup_order":
            return {
                "order_id": order["order_id"],
                "amount": order["amount"],
                "currency": order["currency"],
                "status": order["status"],
                "version": order["version"],
            }
        if tool == "get_refund_policy":
            return {
                "reason": args["reason"],
                "eligible": True,
                "max_refund": order["amount"],
                "currency": order["currency"],
            }
        if tool == "issue_refund":
            amount = float(args["amount"])
            order["refunded_amount"] = round(order["refunded_amount"] + amount, 2)
            order["refund_effect_count"] += 1
            order["status"] = "refunded"
            order["version"] += 1
            return {
                "refund_id": f"refund-{order['order_id']}-{order['refund_effect_count']}",
                "amount": amount,
                "currency": args["currency"],
                "order_version": order["version"],
            }
        if tool == "notify_customer":
            notification = {
                "channel": args["channel"],
                "message": "refund_confirmed",
            }
            order["notifications"].append(notification)
            return {"delivered": True, **notification}
        raise ValueError(f"unknown tool: {tool}")

    def checkpoint(self, event_id: str, state: dict[str, Any]) -> None:
        self.store.checkpoints[event_id] = copy.deepcopy(state)

    def mark_processed(self, event_id: str) -> None:
        self.store.processed_events.add(event_id)
