from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from reliability_harness.evaluator import evaluate
from reliability_harness.reporting import render_markdown, write_reports


class ReportingTests(unittest.TestCase):
    def test_markdown_is_explicitly_demo_labelled(self) -> None:
        markdown = render_markdown(evaluate("smoke", trials=1))
        self.assertTrue(markdown.startswith("# SAMPLE/DEMO"))
        self.assertIn("Before: unreliable demo", markdown)
        self.assertIn("After: fixed demo", markdown)
        self.assertIn("simulated demo telemetry", markdown)

    def test_json_and_markdown_reports_are_written(self) -> None:
        report = evaluate("smoke", trials=1)
        with tempfile.TemporaryDirectory() as directory:
            json_path, markdown_path = write_reports(report, Path(directory))
            self.assertTrue(json_path.is_file())
            self.assertTrue(markdown_path.is_file())
            self.assertEqual(json.loads(json_path.read_text()), report)

    def test_cli_one_command_smoke_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "reliability_harness",
                    "--suite",
                    "smoke",
                    "--trials",
                    "1",
                    "--output-dir",
                    directory,
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("after (fixed):       100.00%", completed.stdout)
            self.assertTrue((Path(directory) / "sample_demo_smoke_scorecard.json").is_file())


if __name__ == "__main__":
    unittest.main()
