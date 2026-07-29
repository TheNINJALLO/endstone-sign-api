from __future__ import annotations

import subprocess
import sys
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
PYTHON = sys.executable


class NativeToolTests(unittest.TestCase):
    def run_tool(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [PYTHON, *arguments],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )

    def test_fail_closed_guard(self) -> None:
        result = self.run_tool("tools/verify_fail_closed.py")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("fail-closed", result.stdout)

    def test_blocked_manifests_are_valid_but_cannot_activate(self) -> None:
        for platform in ("linux-x64", "windows-x64"):
            manifest = f"native/manifests/{platform}-1.26.33.1.json"
            structural = self.run_tool(
                "tools/verify_native_manifest.py",
                manifest,
                "--allow-incomplete",
            )
            self.assertEqual(structural.returncode, 0, structural.stdout)
            self.assertIn("gate CLOSED", structural.stdout)

            strict = self.run_tool("tools/verify_native_manifest.py", manifest)
            self.assertNotEqual(strict.returncode, 0)
            self.assertIn("executable.sha256", strict.stdout)

            activation = self.run_tool("tools/activate_verified_manifest.py", manifest)
            self.assertNotEqual(activation.returncode, 0)
            self.assertIn("activation refused", activation.stdout)

    def test_empty_stage_probe_template_is_rejected(self) -> None:
        result = self.run_tool(
            "tools/validate_stage_probe_report.py",
            "native/probes/STAGE_PROBE_TEMPLATE.json",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("stage probe INVALID", result.stdout)


if __name__ == "__main__":
    unittest.main()
