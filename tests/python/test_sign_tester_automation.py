from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
AUTOMATION_SOURCE = (
    ROOT
    / "examples"
    / "python"
    / "sign_api_tester_plugin"
    / "src"
    / "endstone_sign_tester"
    / "automation.py"
)
DEFAULT_CONFIG = AUTOMATION_SOURCE.with_name("default-config.toml")
SPEC = importlib.util.spec_from_file_location("sign_tester_automation", AUTOMATION_SOURCE)
assert SPEC is not None and SPEC.loader is not None
automation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(automation)


class SignTesterAutomationTests(unittest.TestCase):
    def load_default(self):
        return automation.load_config(DEFAULT_CONFIG)

    def test_default_plan_covers_every_material_and_form_without_collisions(self) -> None:
        config = self.load_default()
        cases = automation.build_cases(
            config, "Overworld", {"x": 100, "y": 64, "z": -100}
        )
        self.assertEqual(len(cases), 48)
        self.assertEqual(
            {(case["material"], case["kind"]) for case in cases},
            {
                (material, kind)
                for material in automation.MATERIALS
                for kind in automation.KINDS
            },
        )
        touched = [
            tuple(case[role][axis] for axis in ("x", "y", "z"))
            for case in cases
            for role in ("sign", "support")
        ]
        self.assertEqual(len(touched), len(set(touched)))
        for case in cases:
            self.assertIn("§", case["front_lines"][2])
            for lines in (
                case["front_lines"],
                case["back_lines"],
                case["edited_front_lines"],
            ):
                self.assertLessEqual(
                    len("\n".join(lines).encode("utf-8")),
                    automation.SAFE_TRANSFERRED_MESSAGE_BYTES,
                )

    def test_default_plan_uses_only_exact_canonical_bds_descriptors(self) -> None:
        identifiers = {
            "oak": (
                "minecraft:standing_sign",
                "minecraft:wall_sign",
                "minecraft:oak_hanging_sign",
            ),
            "spruce": (
                "minecraft:spruce_standing_sign",
                "minecraft:spruce_wall_sign",
                "minecraft:spruce_hanging_sign",
            ),
            "birch": (
                "minecraft:birch_standing_sign",
                "minecraft:birch_wall_sign",
                "minecraft:birch_hanging_sign",
            ),
            "jungle": (
                "minecraft:jungle_standing_sign",
                "minecraft:jungle_wall_sign",
                "minecraft:jungle_hanging_sign",
            ),
            "acacia": (
                "minecraft:acacia_standing_sign",
                "minecraft:acacia_wall_sign",
                "minecraft:acacia_hanging_sign",
            ),
            "dark_oak": (
                "minecraft:darkoak_standing_sign",
                "minecraft:darkoak_wall_sign",
                "minecraft:dark_oak_hanging_sign",
            ),
            "mangrove": (
                "minecraft:mangrove_standing_sign",
                "minecraft:mangrove_wall_sign",
                "minecraft:mangrove_hanging_sign",
            ),
            "cherry": (
                "minecraft:cherry_standing_sign",
                "minecraft:cherry_wall_sign",
                "minecraft:cherry_hanging_sign",
            ),
            "bamboo": (
                "minecraft:bamboo_standing_sign",
                "minecraft:bamboo_wall_sign",
                "minecraft:bamboo_hanging_sign",
            ),
            "crimson": (
                "minecraft:crimson_standing_sign",
                "minecraft:crimson_wall_sign",
                "minecraft:crimson_hanging_sign",
            ),
            "warped": (
                "minecraft:warped_standing_sign",
                "minecraft:warped_wall_sign",
                "minecraft:warped_hanging_sign",
            ),
            "pale_oak": (
                "minecraft:pale_oak_standing_sign",
                "minecraft:pale_oak_wall_sign",
                "minecraft:pale_oak_hanging_sign",
            ),
        }
        expected = {
            (material, kind): values[0 if kind == "standing" else 1 if kind == "wall" else 2]
            for material, values in identifiers.items()
            for kind in automation.KINDS
        }
        cases = automation.build_cases(
            self.load_default(), "Overworld", {"x": 0, "y": 64, "z": 0}
        )
        self.assertEqual(set(identifiers), set(automation.MATERIALS))
        self.assertEqual(
            {(case["material"], case["kind"]): case["identifier"] for case in cases},
            expected,
        )
        self.assertEqual(
            automation.sign_identifier("dark_oak", "standing"),
            "minecraft:darkoak_standing_sign",
        )
        self.assertEqual(
            automation.sign_identifier("dark_oak", "wall"),
            "minecraft:darkoak_wall_sign",
        )
        self.assertEqual(
            automation.sign_identifier("dark_oak", "ceiling_hanging"),
            "minecraft:dark_oak_hanging_sign",
        )
        self.assertNotIn(
            "minecraft:dark_oak_standing_sign",
            {case["identifier"] for case in cases},
        )

    def test_every_activation_probe_has_an_explicit_automation_disposition(self) -> None:
        template = json.loads(
            (ROOT / "native" / "probes" / "STAGE_PROBE_TEMPLATE.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(set(automation.PROBE_COVERAGE), set(template["results"]))
        self.assertTrue(
            all(
                specification["mode"]
                in {
                    "automated",
                    "automated_capability",
                    "cleanup_capability",
                    "capability",
                    "manual",
                }
                for specification in automation.PROBE_COVERAGE.values()
            )
        )

    def test_plan_uses_complete_canonical_states_for_all_four_forms(self) -> None:
        cases = automation.build_cases(
            self.load_default(), "Overworld", {"x": 0, "y": 64, "z": 0}
        )
        by_kind = {case["kind"]: case for case in cases[:4]}
        self.assertEqual(by_kind["standing"]["states"], {"ground_sign_direction": 0})
        self.assertEqual(by_kind["wall"]["states"], {"facing_direction": 2})
        self.assertEqual(
            by_kind["ceiling_hanging"]["states"],
            {
                "attached_bit": False,
                "facing_direction": 2,
                "ground_sign_direction": 0,
                "hanging": True,
            },
        )
        self.assertEqual(by_kind["wall_hanging"]["states"]["hanging"], False)

    def test_config_rejects_unknown_keys_and_unsafe_text_before_planning(self) -> None:
        source = DEFAULT_CONFIG.read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.toml"
            path.write_text(source + "\nunknown_key = true\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unknown matrix config keys"):
                automation.load_config(path)
            path.write_text(
                source.replace(
                    'front_lines = ["{material_code}", "{kind_code}", "§aF", ""]',
                    'front_lines = ["this text is far too long", "{kind_code}", "§aF", ""]',
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "22"):
                automation.load_config(path)

    def test_config_validates_the_actual_monotonic_case_index(self) -> None:
        config = self.load_default()
        config["materials"] = list(automation.MATERIALS[:10])
        config["front_lines"] = ["", "", "", ""]
        config["back_lines"] = ["", "", "", ""]
        config["line_edit_value"] = "{index}" + ("x" * 18)
        with self.assertRaisesRegex(ValueError, "22"):
            automation.validate_config(config)

    def test_run_report_path_rejects_traversal(self) -> None:
        config = self.load_default()
        report = automation.new_run_report(
            plugin_version="0.2.0",
            platform="linux-x64",
            operator="tester",
            dimension="Overworld",
            anchor={"x": 1, "y": 64, "z": 2},
            config=config,
            bridge_status={},
        )
        report["run_id"] = "../outside"
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, "run_id"):
                automation.save_run_report(Path(temporary), report)

    def test_skipped_advanced_steps_never_make_report_activation_eligible(self) -> None:
        config = self.load_default()
        report = automation.new_run_report(
            plugin_version="0.2.0",
            platform="linux-x64",
            operator="tester",
            dimension="Overworld",
            anchor={"x": 1, "y": 64, "z": 2},
            config=config,
            bridge_status={"available": True},
        )
        first = report["cases"][0]
        first["status"] = "passed"
        automation.add_step(
            report,
            first,
            operation="wax",
            status="skipped",
            required_capabilities=("waxed",),
            mutation_attempted=False,
            reason="waxed capability is closed",
        )
        automation.finish_run(report, "completed")
        self.assertFalse(report["activation_eligible"])
        self.assertEqual(report["summary"]["steps_skipped"], 1)
        self.assertEqual(report["summary"]["mutations_attempted"], 0)

    def test_full_system_acceptance_requires_every_layer_and_cleanup(self) -> None:
        config = self.load_default()
        capabilities = {
            name: True for name in automation.REQUIRED_QUALIFICATION_CAPABILITIES
        }
        report = automation.new_run_report(
            plugin_version="0.2.0",
            platform="linux-x64",
            operator="tester",
            dimension="Overworld",
            anchor={"x": 1, "y": 64, "z": 2},
            config=config,
            bridge_status={"available": True, "capabilities": capabilities},
            acceptance_mode=True,
        )
        report["server_executable_sha256"] = "a" * 64
        report["plugin_sha256"] = "b" * 64
        report["tester_wheel_sha256"] = "c" * 64
        report["world_seed"] = "123"
        report["world_name"] = "test-world"
        for case in report["cases"]:
            case["status"] = "passed"
        report["cleanup"].update(
            {"state": "completed", "completed_at_utc": automation.utc_now()}
        )
        automation.finish_run(report, "completed")
        self.assertEqual(report["outcome"], "qualification_blocked")
        self.assertFalse(report["qualification"]["eligible"])

        for case in report["cases"]:
            case["steps"].extend(
                {
                    "operation": operation,
                    "status": "passed",
                    "at_utc": automation.utc_now(),
                    "reason": "structured test evidence",
                    "mutation_attempted": (
                        operation in automation.MUTATING_CASE_OPERATIONS
                    ),
                    "response": {"ok": True},
                }
                for operation in automation.REQUIRED_CASE_OPERATIONS
            )
        report["run_steps"].extend(
            {
                "operation": operation,
                "status": "passed",
                "at_utc": automation.utc_now(),
                "reason": "structured test evidence",
                "mutation_attempted": True,
                "response": {"ok": True},
            }
            for operation in automation.REQUIRED_RUN_OPERATIONS
        )
        report["run_steps"].extend(
            {
                "operation": operation,
                "status": "passed",
                "at_utc": automation.utc_now(),
                "reason": "structured preflight evidence",
                "mutation_attempted": False,
                "response": {"ok": True},
            }
            for operation in automation.REQUIRED_PREFLIGHT_OPERATIONS
        )
        automation.finish_run(report, "completed")

        stage = {
            "passed": True,
            "completed_at_utc": automation.utc_now(),
            "tester_version": "0.2.0",
            "matrix_run_id": report["run_id"],
            "matrix_config_sha256": report["config_sha256"],
            "platform": "linux-x64",
            "operator": "tester",
            "world_name": "test-world",
            "world_seed": "123",
            "target": {"dimension": "Overworld", **report["cases"][0]["sign"]},
            "server_executable_sha256": "a" * 64,
            "plugin_sha256": "b" * 64,
            "tester_wheel_sha256": "c" * 64,
            "results": {
                probe: {"passed": True, "evidence": f"observed {probe}"}
                for probe in automation.PROBE_COVERAGE
            },
        }
        automation.apply_stage_report(report, stage)
        self.assertEqual(report["outcome"], "qualification_passed")
        self.assertTrue(report["qualification"]["eligible"])
        self.assertFalse(report["activation_eligible"])

        for capability in automation.REQUIRED_QUALIFICATION_CAPABILITIES:
            with self.subTest(capability=capability):
                report["bridge_status"]["capabilities"][capability] = False
                automation.refresh_qualification(report)
                self.assertEqual(report["outcome"], "qualification_blocked")
                self.assertTrue(
                    any(
                        capability in blocker
                        for blocker in report["qualification"]["blockers"]
                    )
                )
                report["bridge_status"]["capabilities"][capability] = True
        automation.refresh_qualification(report)
        self.assertTrue(report["qualification"]["eligible"])

    def test_default_config_and_run_report_are_written_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            data_folder = Path(temporary)
            config_path = automation.install_default_config(data_folder)
            config = automation.load_config(config_path)
            report = automation.new_run_report(
                plugin_version="0.2.0",
                platform="linux-x64",
                operator="tester",
                dimension="Overworld",
                anchor={"x": 1, "y": 64, "z": 2},
                config=config,
                bridge_status={},
            )
            archive = automation.save_run_report(data_folder, report)
            self.assertTrue(archive.is_file())
            self.assertFalse(archive.with_suffix(".json.tmp").exists())
            latest = automation.load_latest_report(data_folder)
            self.assertEqual(latest["run_id"], report["run_id"])
            self.assertEqual(json.loads(archive.read_text(encoding="utf-8")), latest)


if __name__ == "__main__":
    unittest.main()
