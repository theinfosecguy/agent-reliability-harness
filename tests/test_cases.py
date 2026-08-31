from __future__ import annotations

import unittest

from reliability_harness.cases import load_casepack, select_cases


class CasePackTests(unittest.TestCase):
    def test_casepack_is_versioned_and_demo_labelled(self) -> None:
        metadata, cases = load_casepack()
        self.assertEqual(metadata["schema_version"], "1.0")
        self.assertEqual(metadata["casepack_version"], "1.0.0")
        self.assertTrue(metadata["label"].startswith("SAMPLE/DEMO"))
        self.assertTrue(all(case.version == "1.0.0" for case in cases))

    def test_smoke_is_fast_subset_of_full(self) -> None:
        _, smoke = select_cases("smoke")
        _, full = select_cases("full")
        self.assertEqual(len(smoke), 3)
        self.assertEqual(len(full), 10)
        self.assertLess({case.id for case in smoke}, {case.id for case in full})

    def test_all_requested_fault_modes_are_present(self) -> None:
        _, cases = load_casepack()
        transport_faults = {fault.kind for case in cases for fault in case.faults}
        special_faults = {
            case.special.get("fault_label") for case in cases if case.special.get("fault_label")
        }
        self.assertTrue(
            {"429", "5xx", "timeout", "malformed_result", "5xx_after_commit"}
            <= transport_faults
        )
        self.assertTrue(
            {"duplicate_event", "interrupted_resumed_run", "stale_state"} <= special_faults
        )

    def test_unknown_suite_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown suite"):
            select_cases("overnight")


if __name__ == "__main__":
    unittest.main()
