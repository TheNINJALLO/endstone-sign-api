from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools import verify_native_manifest as verifier


class NativeManifestBindingTests(unittest.TestCase):
    @staticmethod
    def _write_json(path: Path, value: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    @staticmethod
    def _sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _write_verified_fixture(self, root: Path) -> tuple[Path, dict, dict, dict]:
        platform = "linux-x64"
        executable_hash = "61995841f21baf9bfab96e0d9b0cb798501dcc9789dab68e496f3b8e3bc83375"
        plugin_hash = "a" * 64
        tester_hash = "b" * 64
        config = {"profile": "alpha9-full-system-qualification"}
        config_hash = hashlib.sha256(
            json.dumps(
                config, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ).encode("utf-8")
        ).hexdigest()
        run_id = "20260730T120000Z-01234567"
        target = {"dimension": "Overworld", "x": 10, "y": 65, "z": 10}

        stage = {
            "schema": 1,
            "platform": platform,
            "bds_package_version": "1.26.33.1",
            "endstone_version": "0.11.6",
            "tester_version": verifier.EXPECTED_TESTER_VERSION,
            "server_executable_sha256": executable_hash,
            "plugin_sha256": plugin_hash,
            "tester_wheel_sha256": tester_hash,
            "log_sha256": "c" * 64,
            "world_backup_sha256": "d" * 64,
            "world_seed": "12345",
            "world_name": "Alpha9Qualification",
            "started_at_utc": "2026-07-30T12:00:00+00:00",
            "completed_at_utc": "2026-07-30T13:00:00+00:00",
            "operator": "tester",
            "matrix_run_id": run_id,
            "matrix_config_sha256": config_hash,
            "target": target,
            "passed": True,
            "results": {
                probe: {"passed": True, "evidence": f"observed {probe}"}
                for probe in verifier.REQUIRED_PROBES
            },
        }
        stage_path = root / "native/probes/linux-stage.json"
        self._write_json(stage_path, stage)

        matrix = {
            "schema": 1,
            "kind": "automated-sign-matrix",
            "mode": "full_system_acceptance",
            "plugin_version": verifier.EXPECTED_TESTER_VERSION,
            "bds_package_version": "1.26.33.1",
            "endstone_version": "0.11.6",
            "platform": platform,
            "run_id": run_id,
            "config": config,
            "config_sha256": config_hash,
            "server_executable_sha256": executable_hash,
            "plugin_sha256": plugin_hash,
            "tester_wheel_sha256": tester_hash,
            "world_name": stage["world_name"],
            "world_seed": stage["world_seed"],
            "operator": stage["operator"],
            "dimension": target["dimension"],
            "state": "completed",
            "outcome": "qualification_passed",
            "activation_eligible": False,
            "qualification": {"eligible": True, "blockers": []},
            "coverage": {
                probe: {"status": "passed", "evidence": f"observed {probe}"}
                for probe in verifier.REQUIRED_PROBES
            },
            "stage_report": {
                "passed": True,
                "server_executable_sha256": executable_hash,
                "plugin_sha256": plugin_hash,
                "tester_wheel_sha256": tester_hash,
            },
            "cases": [{"sign": {axis: target[axis] for axis in ("x", "y", "z")}}],
        }
        matrix_path = root / "native/probes/linux-matrix.json"
        self._write_json(matrix_path, matrix)

        bridge_path = root / "src/verified_bds_26_30_adapter.cpp"
        bridge_path.parent.mkdir(parents=True, exist_ok=True)
        bridge_path.write_text("// reviewed fixture\n", encoding="utf-8")

        manifest = {
            "schema": 1,
            "status": "verified",
            "platform": platform,
            "bds_package_version": "1.26.33.1",
            "runtime_bds": "26.33",
            "endstone_version": "0.11.6",
            "archive_sha256": verifier.EXPECTED_ARCHIVES[platform],
            "executable": {
                "filename": "bedrock_server",
                "sha256": executable_hash,
                "size": 232842872,
            },
            "abi": {
                "reviewed": True,
                "reviewer": "reviewer",
                "review_commit": "0123456789abcdef",
                "sign_actor_base_offset": 16,
                "sign_text_side_size": 320,
                "color_argument_contract": "reviewed",
                "calling_convention_notes": "reviewed",
            },
            "symbols": [
                {
                    "id": symbol,
                    "rva": index + 1,
                    "fingerprint_hex": "90",
                    "resolved": True,
                    "unique": True,
                    "signature_verified": True,
                    "behavior_verified": True,
                    "verification_notes": "reviewed fixture",
                }
                for index, symbol in enumerate(sorted(verifier.REQUIRED_SYMBOLS))
            ],
            "player_edit_hook": {
                "installed": True,
                "cancellable_before_mutation": True,
                "original_call_preserved": True,
                "disconnect_cleanup_verified": True,
            },
            "stage_probe": {
                "report_path": "native/probes/linux-stage.json",
                "report_sha256": self._sha256(stage_path),
                "matrix_report_path": "native/probes/linux-matrix.json",
                "matrix_report_sha256": self._sha256(matrix_path),
                "passed": True,
                "results": {probe: True for probe in verifier.REQUIRED_PROBES},
            },
            "bridge": {
                "source_path": "src/verified_bds_26_30_adapter.cpp",
                "source_sha256": self._sha256(bridge_path),
                "reviewed": True,
            },
        }
        manifest_path = root / "native/manifests/linux.json"
        self._write_json(manifest_path, manifest)
        return manifest_path, manifest, stage, matrix

    def test_bound_stage_and_matrix_fixture_opens_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest_path, _, _, _ = self._write_verified_fixture(root)
            self.assertEqual(verifier.validate(manifest_path, root), [])

    def test_manifest_result_booleans_cannot_mask_failed_stage_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest_path, manifest, stage, _ = self._write_verified_fixture(root)
            stage["results"]["wax"]["passed"] = False
            stage_path = root / manifest["stage_probe"]["report_path"]
            self._write_json(stage_path, stage)
            manifest["stage_probe"]["report_sha256"] = self._sha256(stage_path)
            self._write_json(manifest_path, manifest)

            failures = verifier.validate(manifest_path, root)
            self.assertIn("stage report results.wax.passed", failures)
            self.assertIn("stage_probe.results.wax report match", failures)

    def test_missing_matrix_report_cannot_open_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest_path, manifest, _, _ = self._write_verified_fixture(root)
            manifest["stage_probe"]["matrix_report_path"] = (
                "native/probes/missing-matrix.json"
            )
            self._write_json(manifest_path, manifest)

            self.assertIn(
                "stage_probe.matrix_report_path",
                verifier.validate(manifest_path, root),
            )

    def test_matrix_run_identity_mismatch_cannot_open_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest_path, manifest, _, matrix = self._write_verified_fixture(root)
            matrix["run_id"] = "20260730T120000Z-deadbeef"
            matrix_path = root / manifest["stage_probe"]["matrix_report_path"]
            self._write_json(matrix_path, matrix)
            manifest["stage_probe"]["matrix_report_sha256"] = self._sha256(
                matrix_path
            )
            self._write_json(manifest_path, manifest)

            self.assertIn(
                "matrix/stage run ID match",
                verifier.validate(manifest_path, root),
            )


if __name__ == "__main__":
    unittest.main()
