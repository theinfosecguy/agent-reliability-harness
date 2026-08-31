"""Deliberately unreliable and fixed sample agent implementations."""

from __future__ import annotations

from typing import Any, Callable

from .runtime import MalformedToolResult, RetryableToolError, StaleStateError, ToolRuntime


Validator = Callable[[dict[str, Any]], bool]


class UnreliableAgent:
    """A plausible happy-path implementation with intentional reliability gaps.

    It has no retry policy, idempotency keys, checkpointing, duplicate-event
    protection, response validation, or optimistic concurrency control. It also
    trusts a caller-supplied refund amount instead of the authoritative order.
    """

    name = "unreliable"

    def run(self, request: dict[str, Any], runtime: ToolRuntime) -> None:
        runtime.record_agent_event("agent_start", implementation_note="happy_path_only")
        order = runtime.call("lookup_order", {"order_id": request["order_id"]})
        runtime.call("get_refund_policy", {"reason": request["reason"]})
        amount = request.get("requested_amount", order["amount"])
        runtime.call(
            "issue_refund",
            {
                "order_id": request["order_id"],
                "amount": amount,
                "currency": order["currency"],
            },
        )
        runtime.call(
            "notify_customer",
            {"order_id": request["order_id"], "channel": request["channel"]},
        )
        runtime.record_agent_event("agent_complete")


class FixedAgent:
    """A small state machine with retries, validation, dedupe, and checkpoints."""

    name = "fixed"
    max_attempts = 3

    @staticmethod
    def _valid_order(result: dict[str, Any]) -> bool:
        return {
            "order_id",
            "amount",
            "currency",
            "status",
            "version",
        } <= set(result)

    @staticmethod
    def _valid_policy(result: dict[str, Any]) -> bool:
        return {"eligible", "max_refund", "currency"} <= set(result)

    @staticmethod
    def _valid_refund(result: dict[str, Any]) -> bool:
        return {"refund_id", "amount", "currency", "order_version"} <= set(result)

    @staticmethod
    def _valid_notification(result: dict[str, Any]) -> bool:
        return result.get("delivered") is True

    def _call_with_retry(
        self,
        runtime: ToolRuntime,
        tool: str,
        args: dict[str, Any],
        validator: Validator,
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        last_error: Exception | None = None
        for local_attempt in range(1, self.max_attempts + 1):
            try:
                result = runtime.call(tool, args, idempotency_key=idempotency_key)
                if not validator(result):
                    raise MalformedToolResult(f"invalid result from {tool}")
                return result
            except (RetryableToolError, MalformedToolResult) as exc:
                last_error = exc
                runtime.record_agent_event(
                    "retry_scheduled",
                    tool=tool,
                    local_attempt=local_attempt,
                    reason=getattr(exc, "code", type(exc).__name__),
                )
                if local_attempt == self.max_attempts:
                    raise
        raise AssertionError(f"retry loop exited unexpectedly: {last_error}")

    def _issue_refund(
        self,
        request: dict[str, Any],
        runtime: ToolRuntime,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        event_id = request["event_id"]
        for concurrency_attempt in range(1, self.max_attempts + 1):
            order = state["order"]
            amount = min(float(order["amount"]), float(state["policy"]["max_refund"]))
            args = {
                "order_id": request["order_id"],
                "amount": amount,
                "currency": order["currency"],
                "expected_version": order["version"],
            }
            try:
                return self._call_with_retry(
                    runtime,
                    "issue_refund",
                    args,
                    self._valid_refund,
                    idempotency_key=f"{event_id}:refund",
                )
            except StaleStateError:
                runtime.record_agent_event(
                    "stale_state_refresh",
                    concurrency_attempt=concurrency_attempt,
                )
                state["order"] = self._call_with_retry(
                    runtime,
                    "lookup_order",
                    {"order_id": request["order_id"]},
                    self._valid_order,
                )
                runtime.checkpoint(event_id, state)
                if concurrency_attempt == self.max_attempts:
                    raise
        raise AssertionError("concurrency retry loop exited unexpectedly")

    def run(self, request: dict[str, Any], runtime: ToolRuntime) -> None:
        event_id = request["event_id"]
        if event_id in runtime.store.processed_events:
            runtime.record_agent_event("duplicate_ignored")
            return

        existing = runtime.store.checkpoints.get(event_id)
        state = dict(existing) if existing else {"stage": "start"}
        runtime.record_agent_event("agent_resume" if existing else "agent_start")

        if state["stage"] == "start":
            state["order"] = self._call_with_retry(
                runtime,
                "lookup_order",
                {"order_id": request["order_id"]},
                self._valid_order,
            )
            state["stage"] = "order_loaded"
            runtime.checkpoint(event_id, state)

        if state["stage"] == "order_loaded":
            state["policy"] = self._call_with_retry(
                runtime,
                "get_refund_policy",
                {"reason": request["reason"]},
                self._valid_policy,
            )
            state["stage"] = "policy_checked"
            runtime.checkpoint(event_id, state)

        if state["stage"] == "policy_checked":
            state["refund"] = self._issue_refund(request, runtime, state)
            state["stage"] = "refunded"
            runtime.checkpoint(event_id, state)

        if state["stage"] == "refunded":
            state["notification"] = self._call_with_retry(
                runtime,
                "notify_customer",
                {"order_id": request["order_id"], "channel": request["channel"]},
                self._valid_notification,
                idempotency_key=f"{event_id}:notification",
            )
            state["stage"] = "notified"
            runtime.checkpoint(event_id, state)

        if state["stage"] == "notified":
            runtime.mark_processed(event_id)
            state["stage"] = "complete"
            runtime.checkpoint(event_id, state)
            runtime.record_agent_event("agent_complete")


IMPLEMENTATIONS = {
    UnreliableAgent.name: UnreliableAgent,
    FixedAgent.name: FixedAgent,
}
