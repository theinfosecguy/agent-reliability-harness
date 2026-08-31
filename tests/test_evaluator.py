from __future__ import annotations

import unittest

from reliability_harness.evaluator import ASSERTION_NAMES, _release_gate, evaluate


class EvaluatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = evaluate("full", trials=2)

    def test_evaluation_is_byte_for_byte_deterministic_as_data(self) -> None:
        first = evaluate("smoke", trials=2)
        second = evaluate("smoke", trials=2)
        self.assertEqual(first, second)

    def test_fixed_implementation_passes_every_assertion(self) -> None:
        fixed = [
            row for row in self.report["results"] if row["implementation"] == "fixed"
        ]
        self.assertTrue(fixed)
        self.assertTrue(all(row["passed"] for row in fixed))
        self.assertTrue(all(all(row["assertions"].values()) for row in fixed))
        self.assertEqual(self.report["summary"]["fixed"]["score_percent"], 100.0)

    def test_unreliable_implementation_exposes_real_failures(self) -> None:
        before = self.report["summary"]["unreliable"]
        after = self.report["summary"]["fixed"]
        self.assertLess(before["score_percent"], 60.0)
        self.assertGreater(after["score_percent"], before["score_percent"])
        self.assertLess(
            before["trial_pass_rate_percent"], after["trial_pass_rate_percent"]
        )

    def test_ambiguous_commit_reuses_idempotency_key(self) -> None:
        result = next(
            row
            for row in self.report["results"]
            if row["case_id"] == "ambiguous_5xx_after_commit"
            and row["implementation"] == "fixed"
            and row["trial"] == 1
        )
        calls = [event for event in result["trace"] if event["tool"] == "issue_refund"]
        self.assertEqual(
            [event["outcome"] for event in calls],
            ["error_after_commit", "idempotent_replay"],
        )
        self.assertEqual(len({event["idempotency_key"] for event in calls}), 1)
        self.assertEqual(result["final_state"]["order"]["refund_effect_count"], 1)

    def test_interrupted_run_resumes_from_checkpoint(self) -> None:
        result = next(
            row
            for row in self.report["results"]
            if row["case_id"] == "interrupted_then_resumed"
            and row["implementation"] == "fixed"
            and row["trial"] == 1
        )
        event_types = [event["event_type"] for event in result["trace"]]
        self.assertIn("harness_resume", event_types)
        self.assertIn("agent_resume", event_types)
        self.assertEqual(result["final_state"]["order"]["refund_effect_count"], 1)

    def test_stale_state_refreshes_authoritative_amount(self) -> None:
        result = next(
            row
            for row in self.report["results"]
            if row["case_id"] == "stale_order_state"
            and row["implementation"] == "fixed"
            and row["trial"] == 1
        )
        successful_refund = next(
            event
            for event in result["trace"]
            if event["tool"] == "issue_refund" and event["outcome"] == "ok"
        )
        self.assertEqual(successful_refund["args"]["amount"], 90.0)
        self.assertEqual(result["final_state"]["order"]["refunded_amount"], 90.0)

    def test_every_trace_event_has_latency_cost_and_sequence(self) -> None:
        for result in self.report["results"]:
            for expected_sequence, event in enumerate(result["trace"], start=1):
                self.assertEqual(event["sequence"], expected_sequence)
                self.assertIsInstance(event["latency_ms"], int)
                self.assertGreaterEqual(event["latency_ms"], 0)
                self.assertIsInstance(event["cost_usd"], float)
                self.assertGreaterEqual(event["cost_usd"], 0.0)

    def test_score_has_all_declared_assertions(self) -> None:
        for result in self.report["results"]:
            self.assertEqual(tuple(result["assertions"]), ASSERTION_NAMES)

    def test_default_release_gate_passes(self) -> None:
        gate = self.report["release_gate"]
        self.assertTrue(gate["passed"])
        self.assertTrue(all(check["passed"] for check in gate["checks"].values()))

    def test_release_gate_fails_below_threshold(self) -> None:
        summary = {
            "fixed": {
                "score_percent": 97.5,
                "trial_pass_rate_percent": 92.0,
            }
        }
        gate = _release_gate(
            summary, min_assertion_score=98.0, min_trial_pass_rate=95.0
        )
        self.assertFalse(gate["passed"])
        self.assertFalse(gate["checks"]["assertion_score"]["passed"])
        self.assertFalse(gate["checks"]["fully_passing_trials"]["passed"])

    def test_release_gate_rejects_invalid_threshold(self) -> None:
        with self.assertRaisesRegex(ValueError, "between 0 and 100"):
            evaluate("smoke", trials=1, min_assertion_score=100.1)


if __name__ == "__main__":
    unittest.main()
