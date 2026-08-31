from __future__ import annotations

import unittest

from reliability_harness.cases import load_casepack
from reliability_harness.models import TraceRecorder
from reliability_harness.runtime import SyntheticStore, ToolRuntime


class RuntimeTests(unittest.TestCase):
    def _happy_runtime(self) -> tuple[ToolRuntime, SyntheticStore]:
        _, cases = load_casepack()
        case = next(case for case in cases if case.id == "happy_refund")
        store = SyntheticStore.from_case(case)
        trace = TraceRecorder("fixed", case.id, 1, case.request["event_id"])
        return ToolRuntime(case, store, trace, seed=7), store

    def test_same_idempotency_key_returns_original_result_once(self) -> None:
        runtime, store = self._happy_runtime()
        args = {
            "order_id": "ord-happy",
            "amount": 120.0,
            "currency": "USD",
            "expected_version": 1,
        }
        first = runtime.call("issue_refund", args, idempotency_key="evt:refund")
        second = runtime.call("issue_refund", args, idempotency_key="evt:refund")
        self.assertEqual(first, second)
        self.assertEqual(store.order["refund_effect_count"], 1)
        self.assertEqual(store.order["refunded_amount"], 120.0)
        self.assertEqual(runtime.trace.events[-1].outcome, "idempotent_replay")

    def test_without_idempotency_key_mutation_repeats(self) -> None:
        runtime, store = self._happy_runtime()
        args = {"order_id": "ord-happy", "amount": 120.0, "currency": "USD"}
        runtime.call("issue_refund", args)
        runtime.call("issue_refund", args)
        self.assertEqual(store.order["refund_effect_count"], 2)
        self.assertEqual(store.order["refunded_amount"], 240.0)

    def test_snapshot_is_json_compatible_and_sorted(self) -> None:
        runtime, store = self._happy_runtime()
        runtime.mark_processed("z-event")
        runtime.mark_processed("a-event")
        self.assertEqual(store.snapshot()["processed_events"], ["a-event", "z-event"])


if __name__ == "__main__":
    unittest.main()
