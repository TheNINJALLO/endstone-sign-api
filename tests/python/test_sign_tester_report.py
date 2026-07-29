from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
REPORT_SOURCE = (
    ROOT
    / "examples"
    / "python"
    / "sign_api_tester_plugin"
    / "src"
    / "endstone_sign_tester"
    / "report.py"
)
SPEC = importlib.util.spec_from_file_location("sign_tester_report", REPORT_SOURCE)
assert SPEC is not None and SPEC.loader is not None
report_tools = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(report_tools)


class SignTesterReportTests(unittest.TestCase):
    def make_report(self):
        return report_tools.new_report(
            platform="linux-x64",
            operator="tester",
            dimension="overworld",
            x=1,
            y=64,
            z=-2,
        )

    def test_probe_set_matches_repository_template(self) -> None:
        template = json.loads(
            (ROOT / "native" / "probes" / "STAGE_PROBE_TEMPLATE.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(set(report_tools.PROBE_NAMES), set(template["results"]))
        self.assertEqual(len(report_tools.PROBE_NAMES), len(set(report_tools.PROBE_NAMES)))

    def test_round_trip_and_atomic_save(self) -> None:
        report = self.make_report()
        scratch = ROOT / "build" / "sign-tester-report-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            path = Path(temporary) / "stage-probe.json"
            report_tools.save_report(path, report)
            self.assertFalse(path.with_suffix(".json.tmp").exists())
            self.assertEqual(report_tools.load_report(path), report)

    def test_result_and_metadata_validation(self) -> None:
        report = self.make_report()
        with self.assertRaisesRegex(ValueError, "unknown probe"):
            report_tools.record_result(report, "not_a_probe", True, "evidence")
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            report_tools.record_result(report, report_tools.PROBE_NAMES[0], True, " ")
        with self.assertRaisesRegex(ValueError, "64-character"):
            report_tools.set_metadata(report, "plugin_sha256", "abcd")
        with self.assertRaisesRegex(ValueError, "not editable"):
            report_tools.set_metadata(report, "passed", "true")

    def test_finish_fails_closed_then_passes_with_complete_evidence(self) -> None:
        report = self.make_report()
        initial = report_tools.finish_report(report)
        self.assertTrue(initial)
        self.assertFalse(report["passed"])
        for field in report_tools.HASH_FIELDS:
            report_tools.set_metadata(report, field, "a" * 64)
        report_tools.set_metadata(report, "world_seed", "123456")
        for probe in report_tools.PROBE_NAMES:
            report_tools.record_result(report, probe, True, f"observed {probe}")
        self.assertEqual(report_tools.finish_report(report), [])
        self.assertTrue(report["passed"])
        self.assertTrue(report["completed_at_utc"])

    def test_invocation_journal_is_bounded(self) -> None:
        report = self.make_report()
        for index in range(110):
            report_tools.append_invocation(report, "capture", {"index": index}, {"ok": True})
        self.assertEqual(len(report["invocations"]), 100)
        self.assertEqual(report["invocations"][0]["request"]["index"], 10)


if __name__ == "__main__":
    unittest.main()
