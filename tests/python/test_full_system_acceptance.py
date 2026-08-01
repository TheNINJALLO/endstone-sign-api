from __future__ import annotations

import copy
from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
TESTER = ROOT / "examples/python/sign_api_tester_plugin/src/endstone_sign_tester"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


automation = load_module("full_acceptance_automation", TESTER / "automation.py")
stage_tools = load_module("full_acceptance_stage", TESTER / "report.py")
sys.path.insert(0, str(ROOT / "tools"))
validator = load_module(
    "full_acceptance_validator", ROOT / "tools/validate_full_system_acceptance.py"
)


class FullSystemAcceptanceValidatorTests(unittest.TestCase):
    SERVER_PAYLOAD = b"alpha7 exact Bedrock server fixture"
    PLUGIN_PAYLOAD = b"alpha7 native plugin fixture"
    TESTER_WHEEL_PAYLOAD = b"alpha7 tester wheel fixture"
    LOG_PAYLOAD = b"alpha7 server log fixture"
    BACKUP_PAYLOAD = b"alpha7 world backup fixture"

    @staticmethod
    def snapshot(
        case: dict,
        revision: int,
        *,
        coordinates: dict | None = None,
        identifier: str | None = None,
        front_lines: list[str] | None = None,
        back_lines: list[str] | None = None,
        front_updates: dict | None = None,
        waxed: bool = False,
    ) -> dict:
        front = {
            "lines": list(front_lines or ["", "", "", ""]),
            "filtered_message": "",
            "text_object": "",
            "message_is_text_object": False,
            "owner_xuid": "",
            "argb": 0xFF000000,
            "glowing": False,
            "hide_glow_outline": False,
            "persist_formatting": True,
        }
        front.update(front_updates or {})
        location = coordinates or case["sign"]
        return {
            "found": True,
            "dimension": case["dimension"],
            **location,
            "block_identifier": identifier or case["identifier"],
            "kind": case["kind"],
            "states": copy.deepcopy(case["states"]),
            "front": front,
            "back": {
                "lines": list(back_lines or ["", "", "", ""]),
                "filtered_message": "",
                "text_object": "",
                "message_is_text_object": False,
                "owner_xuid": "",
                "argb": 0xFF000000,
                "glowing": False,
                "hide_glow_outline": False,
                "persist_formatting": True,
            },
            "waxed": waxed,
            "locked_for_editing_by": -1,
            "locked_for_editing_xuid": None,
            "remote_profanity_filter_enabled": False,
            "local_profanity_filter_enabled": False,
            "movable": True,
            "actor_status": "experimental_text_captured",
            "revision": revision,
        }

    @staticmethod
    def applied(revision: int) -> dict:
        return {"ok": True, "status": "applied", "revision": revision}

    def add_case_execution(self, matrix: dict, case: dict, base_revision: int) -> tuple[dict, int]:
        support_before = {**case["support"], "type": "minecraft:air"}
        support_after = {
            **case["support"],
            "type": matrix["config"]["support_block"],
        }
        automation.add_step(
            matrix,
            case,
            operation="create_support",
            status="passed",
            mutation_attempted=True,
            request={
                **case["support"],
                "dimension": case["dimension"],
                "type": matrix["config"]["support_block"],
            },
            response={"ok": True, "before": "minecraft:air", "after": matrix["config"]["support_block"]},
            before=support_before,
            after=support_after,
            reason="support transitioned from air to the configured block",
        )

        revision = base_revision
        case["placement_revision"] = revision
        blank = self.snapshot(case, revision)
        automation.add_step(
            matrix,
            case,
            operation="place_blank",
            status="passed",
            mutation_attempted=True,
            request={
                **case["sign"],
                "dimension": case["dimension"],
                "block_identifier": case["identifier"],
                "states": copy.deepcopy(case["states"]),
                "force": False,
            },
            response=self.applied(revision),
            before={**case["sign"], "type": "minecraft:air"},
            after=blank,
            reason="blank sign placement returned a concrete revision",
        )
        automation.add_step(
            matrix,
            case,
            operation="capture_placed",
            status="passed",
            response=blank,
            after=blank,
            reason="blank placement readback matched identifier, state, and location",
        )

        front_lines = ["", "", "", ""]
        back_lines = ["", "", "", ""]
        current = blank
        mutations = (
            ("front", "capture_front", {"side": "front", "lines": case["front_lines"]}),
            ("back", "capture_back", {"side": "back", "lines": case["back_lines"]}),
            (
                "line_edit",
                "capture_line_edit",
                {"side": "front", "lines": case["edited_front_lines"]},
            ),
            (
                "color",
                "capture_color",
                {
                    "side": "front",
                    "lines": case["edited_front_lines"],
                    "argb": matrix["config"]["argb"],
                    "glowing": None,
                    "waxed": None,
                },
            ),
            (
                "glow",
                "capture_glow",
                {
                    "side": "front",
                    "lines": case["edited_front_lines"],
                    "argb": None,
                    "glowing": matrix["config"]["glowing"],
                    "waxed": None,
                },
            ),
            (
                "wax",
                "capture_wax",
                {
                    "side": "front",
                    "lines": case["edited_front_lines"],
                    "argb": None,
                    "glowing": None,
                    "waxed": matrix["config"]["waxed"],
                },
            ),
            (
                "unwax",
                "capture_unwax",
                {
                    "side": "front",
                    "lines": case["edited_front_lines"],
                    "argb": None,
                    "glowing": None,
                    "waxed": False,
                },
            ),
        )
        for operation, capture_operation, values in mutations:
            before = current
            request = {
                **case["sign"],
                "dimension": case["dimension"],
                "expected_revision": revision,
                "force": False,
                **copy.deepcopy(values),
            }
            revision += 1
            if operation == "front":
                front_lines = list(case["front_lines"])
            elif operation == "back":
                back_lines = list(case["back_lines"])
            elif operation == "line_edit":
                front_lines = list(case["edited_front_lines"])
            front_updates = {
                "argb": matrix["config"]["argb"],
                "glowing": matrix["config"]["glowing"],
            }
            if operation in {"front", "back", "line_edit"}:
                front_updates = {
                    "argb": current["front"]["argb"],
                    "glowing": current["front"]["glowing"],
                }
            elif operation == "color":
                front_updates["glowing"] = current["front"]["glowing"]
            waxed = (
                matrix["config"]["waxed"]
                if operation == "wax"
                else False
                if operation == "unwax"
                else current["waxed"]
            )
            current = self.snapshot(
                case,
                revision,
                front_lines=front_lines,
                back_lines=back_lines,
                front_updates=front_updates,
                waxed=waxed,
            )
            automation.add_step(
                matrix,
                case,
                operation=operation,
                status="passed",
                mutation_attempted=True,
                request=request,
                response=self.applied(revision),
                before=before,
                after=current,
                reason=f"{operation} applied at the expected revision",
            )
            automation.add_step(
                matrix,
                case,
                operation=capture_operation,
                status="passed",
                response=current,
                before=current,
                after=current,
                reason=f"{capture_operation} readback matched the requested value",
            )
        return current, revision

    def add_run_execution(
        self, matrix: dict, source_case: dict, source: dict, revision: int
    ) -> tuple[dict, int]:
        current = source
        extended = (
            ("capture_filtered_text", "filtered_message", "a7-filter"),
            (
                "capture_text_object",
                "text_object",
                '{"rawtext":[{"text":"a7"}]}',
            ),
            ("capture_owner_xuid", "owner_xuid", "a7-owner"),
            ("capture_hide_glow_outline", "hide_glow_outline", None),
            ("capture_persist_formatting", "persist_formatting", None),
        )
        for operation, field, value in extended:
            before = copy.deepcopy(current)
            expected_value = (
                not bool(before["front"][field]) if value is None else value
            )
            values = {field: expected_value}
            if operation == "capture_text_object":
                values["message_is_text_object"] = True
            applied_capture = copy.deepcopy(before)
            revision += 1
            applied_capture["revision"] = revision
            applied_capture["front"].update(values)
            applied_result = self.applied(revision)
            revision += 1
            restored_capture = copy.deepcopy(before)
            restored_capture["revision"] = revision
            automation.add_step(
                matrix,
                None,
                operation=operation,
                status="passed",
                mutation_attempted=True,
                request={
                    "target": {"dimension": source_case["dimension"], **source_case["sign"]},
                    "expected_revision": before["revision"],
                    "values": values,
                },
                response={
                    "apply": applied_result,
                    "applied_capture": applied_capture,
                    "restore": self.applied(revision),
                    "restored_capture": restored_capture,
                },
                before=before,
                after=restored_capture,
                reason=f"{field} round-tripped and restored through two revisions",
            )
            current = restored_capture

        lock_before = copy.deepcopy(current)
        revision += 1
        lock_capture = copy.deepcopy(lock_before)
        lock_capture.update(
            {
                "revision": revision,
                "locked_for_editing_by": 2147483007,
                "locked_for_editing_xuid": None,
            }
        )
        restore_state = {
            "locked_for_editing_by": lock_before["locked_for_editing_by"],
            "locked_for_editing_xuid": lock_before["locked_for_editing_xuid"],
            "snapshot": copy.deepcopy(lock_before),
        }
        matrix["run_probe"]["lock_restore"] = restore_state
        automation.add_step(
            matrix,
            None,
            operation="capture_editor_lock",
            status="passed",
            mutation_attempted=True,
            request={
                "target": {"dimension": source_case["dimension"], **source_case["sign"]},
                "locked_for_editing_by": 2147483007,
                "xuid": None,
            },
            response={"apply": self.applied(revision), "capture": lock_capture},
            before=lock_before,
            after=lock_capture,
            reason="editor lock sentinel and XUID were observed",
        )

        revision += 1
        unlocked_capture = copy.deepcopy(lock_before)
        unlocked_capture["revision"] = revision
        automation.add_step(
            matrix,
            None,
            operation="capture_editor_unlock",
            status="passed",
            mutation_attempted=True,
            request={
                "target": {"dimension": source_case["dimension"], **source_case["sign"]},
                "restore": copy.deepcopy(restore_state),
            },
            response={"apply": self.applied(revision), "capture": unlocked_capture},
            before=lock_capture,
            after=unlocked_capture,
            reason="editor lock fields returned to the exact saved state",
        )
        current = unlocked_capture

        unchanged = copy.deepcopy(current)
        automation.add_step(
            matrix,
            None,
            operation="capture_api_edit_event_cancelled",
            status="passed",
            mutation_attempted=True,
            request={
                "target": {"dimension": source_case["dimension"], **source_case["sign"]},
                "expected_revision": revision,
                "lines": ["cancel", "must", "not", "apply"],
            },
            response={
                "probe": {
                    "ok": True,
                    "status": "cancelled",
                    "event_observed": True,
                    "event_cancelled": True,
                    "state_unchanged": True,
                    "listener_removed": True,
                },
                "capture": unchanged,
            },
            before=unchanged,
            after=unchanged,
            reason="cancelled API edit emitted an event and left state unchanged",
        )

        replace_before = copy.deepcopy(current)
        alternate = "minecraft:spruce_standing_sign"
        revision += 1
        replaced_capture = copy.deepcopy(replace_before)
        replaced_capture.update({"block_identifier": alternate, "revision": revision})
        replace_revision = revision
        revision += 1
        restored_capture = copy.deepcopy(replace_before)
        restored_capture["revision"] = revision
        automation.add_step(
            matrix,
            None,
            operation="capture_replace",
            status="passed",
            mutation_attempted=True,
            request={
                "target": {"dimension": source_case["dimension"], **source_case["sign"]},
                "alternate_identifier": alternate,
                "expected_revision": replace_before["revision"],
            },
            response={
                "replace": self.applied(replace_revision),
                "replace_capture": replaced_capture,
                "restore": self.applied(revision),
                "restored_capture": restored_capture,
            },
            before=replace_before,
            after=restored_capture,
            reason="replacement identifier was captured and original state restored",
        )
        current = restored_capture

        run_probe = matrix["run_probe"]
        clone_plan = run_probe["clone"]
        clone_revision = revision + 1000
        clone_destination = copy.deepcopy(current)
        clone_destination.update(clone_plan["sign"])
        clone_destination["revision"] = clone_revision
        automation.add_step(
            matrix,
            None,
            operation="capture_clone",
            status="passed",
            mutation_attempted=True,
            request={
                "source": {"dimension": source_case["dimension"], **source_case["sign"]},
                "destination": {"dimension": clone_plan["dimension"], **clone_plan["sign"]},
            },
            response={
                "support": {
                    "ok": True,
                    "before": "minecraft:air",
                    "after": matrix["config"]["support_block"],
                },
                "clone": {"ok": True, "status": "applied", "revision": clone_revision},
                "source_after": copy.deepcopy(current),
                "destination_after": clone_destination,
            },
            before=copy.deepcopy(current),
            after=clone_destination,
            reason="clone preserved source state and produced exact destination state",
        )

        move_plan = run_probe["move"]
        move_revision = clone_revision + 1
        move_destination = copy.deepcopy(clone_destination)
        move_destination.update(move_plan["sign"])
        move_destination["revision"] = move_revision
        automation.add_step(
            matrix,
            None,
            operation="capture_move",
            status="passed",
            mutation_attempted=True,
            request={
                "source": {"dimension": clone_plan["dimension"], **clone_plan["sign"]},
                "destination": {"dimension": move_plan["dimension"], **move_plan["sign"]},
            },
            response={
                "support": {
                    "ok": True,
                    "before": "minecraft:air",
                    "after": matrix["config"]["support_block"],
                },
                "move": {"ok": True, "status": "applied", "revision": move_revision},
                "source_air": True,
                "source_after": {
                    "found": False,
                    "dimension": clone_plan["dimension"],
                    **clone_plan["sign"],
                },
                "destination_after": move_destination,
            },
            before=clone_destination,
            after=move_destination,
            reason="move cleared the clone cell and preserved state at destination",
        )

        guard = run_probe["atomic_guard"]
        atomic_before = copy.deepcopy(current)
        atomic_after = copy.deepcopy(current)
        automation.add_step(
            matrix,
            None,
            operation="capture_atomic_rollback",
            status="passed",
            mutation_attempted=True,
            request={
                "first": {"dimension": source_case["dimension"], **source_case["sign"]},
                "blocked_destination": {"dimension": guard["dimension"], **guard["location"]},
                "guard_block": guard["block_identifier"],
            },
            response={
                "transaction": {
                    "ok": True,
                    "rolled_back": True,
                    "transaction_rejected": True,
                    "first_sign_unchanged": True,
                },
                "first_after": atomic_after,
                "guard_after_transaction": guard["block_identifier"],
                "guard_removed": True,
                "guard_capture": {
                    "found": False,
                    "dimension": guard["dimension"],
                    **guard["location"],
                },
            },
            before={"first": atomic_before, "guard_type": "minecraft:air"},
            after={"first": atomic_after, "guard_type": "minecraft:air"},
            reason="failed atomic transaction rolled back and guard cleanup was verified",
        )
        return current, revision

    def add_case_cleanup(self, matrix: dict, case: dict, current: dict, revision: int) -> None:
        case["expected_revision"] = revision
        case["owned_sign"] = False
        case["owned_support"] = False
        automation.add_step(
            matrix,
            case,
            operation="cleanup_remove_sign",
            status="passed",
            mutation_attempted=True,
            request={
                "dimension": case["dimension"],
                **case["sign"],
                "expected_revision": revision,
            },
            response={"ok": True, "status": "applied", "revision": 0},
            before=current,
            after={
                "found": False,
                "type": "minecraft:air",
                "dimension": case["dimension"],
                **case["sign"],
            },
            reason="owned sign was removed with its exact expected revision",
        )
        automation.add_step(
            matrix,
            case,
            operation="cleanup_remove_support",
            status="passed",
            mutation_attempted=True,
            request={
                "dimension": case["dimension"],
                **case["support"],
                "type": "minecraft:air",
            },
            response={"ok": True, "status": "applied"},
            before={
                **case["support"],
                "type": matrix["config"]["support_block"],
            },
            after={**case["support"], "type": "minecraft:air"},
            reason="owned support transitioned back to air",
        )
        case["status"] = "passed"

    def make_reports(self):
        config = automation.load_acceptance_config()
        capabilities = {
            name: True for name in automation.REQUIRED_QUALIFICATION_CAPABILITIES
        }
        matrix = automation.new_run_report(
            plugin_version="0.2.1a1",
            platform="linux-x64",
            operator="tester",
            dimension="Overworld",
            anchor={"x": 10, "y": 64, "z": 10},
            config=config,
            bridge_status={"available": True, "capabilities": capabilities},
            acceptance_mode=True,
        )
        matrix["server_executable_sha256"] = hashlib.sha256(
            self.SERVER_PAYLOAD
        ).hexdigest()
        matrix["plugin_sha256"] = hashlib.sha256(self.PLUGIN_PAYLOAD).hexdigest()
        matrix["tester_wheel_sha256"] = hashlib.sha256(
            self.TESTER_WHEEL_PAYLOAD
        ).hexdigest()
        matrix["world_seed"] = "12345"
        matrix["world_name"] = "test-world"
        matrix["plugin_discovery"] = {"status": "selected"}
        matrix["tester_wheel_discovery"] = {"status": "selected"}
        automation.add_step(
            matrix,
            None,
            operation="binary_evidence",
            status="passed",
            response={
                "server_executable_sha256": matrix["server_executable_sha256"],
                "plugin_sha256": matrix["plugin_sha256"],
                "tester_wheel_sha256": matrix["tester_wheel_sha256"],
                "world_name": matrix["world_name"],
                "world_seed": matrix["world_seed"],
                "plugin_discovery": copy.deepcopy(matrix["plugin_discovery"]),
                "tester_wheel_discovery": copy.deepcopy(matrix["tester_wheel_discovery"]),
            },
            reason="all supplied binaries and world identity were bound to the run",
        )
        automation.add_step(
            matrix,
            None,
            operation="capability_preflight",
            status="passed",
            response=copy.deepcopy(matrix["bridge_status"]),
            reason="all required native bridge capabilities were available",
        )
        automation.add_step(
            matrix,
            None,
            operation="block_descriptor_preflight",
            status="passed",
            response={"ok": True, "failures": []},
            reason="every planned block descriptor resolved",
        )
        automation.add_step(
            matrix,
            None,
            operation="arena_air_preflight",
            status="passed",
            response={"ok": True, "conflicts": []},
            reason="all matrix and scratch cells were air before mutation",
        )

        final_states: dict[str, tuple[dict, int]] = {}
        for index, case in enumerate(matrix["cases"]):
            final_states[case["id"]] = self.add_case_execution(
                matrix, case, (index + 1) * 1000 + 1
            )
        source_case = matrix["cases"][0]
        source_state, source_revision = final_states[source_case["id"]]
        final_states[source_case["id"]] = self.add_run_execution(
            matrix, source_case, source_state, source_revision
        )
        for case in matrix["cases"]:
            state, revision = final_states[case["id"]]
            self.add_case_cleanup(matrix, case, state, revision)
        matrix["run_probe_cleanup_completed_at_utc"] = automation.utc_now()
        matrix["cleanup"].update(
            {"state": "completed", "completed_at_utc": automation.utc_now()}
        )

        stage = stage_tools.new_report(
            platform="linux-x64",
            operator="tester",
            dimension="Overworld",
            x=10,
            y=65,
            z=10,
        )
        stage["server_executable_sha256"] = matrix["server_executable_sha256"]
        stage["plugin_sha256"] = matrix["plugin_sha256"]
        stage["tester_wheel_sha256"] = matrix["tester_wheel_sha256"]
        stage["log_sha256"] = hashlib.sha256(self.LOG_PAYLOAD).hexdigest()
        stage["world_backup_sha256"] = hashlib.sha256(self.BACKUP_PAYLOAD).hexdigest()
        stage["world_seed"] = "12345"
        stage["tester_version"] = "0.2.1a1"
        stage["matrix_run_id"] = matrix["run_id"]
        stage["matrix_config_sha256"] = matrix["config_sha256"]
        stage["world_name"] = matrix["world_name"]
        for probe in stage_tools.PROBE_NAMES:
            stage_tools.record_result(stage, probe, True, f"observed {probe}")
        self.assertEqual(stage_tools.finish_report(stage), [])

        automation.finish_run(matrix, "completed")
        automation.apply_stage_report(matrix, stage)
        self.assertTrue(matrix["qualification"]["eligible"])
        return matrix, stage

    def run_validator(
        self,
        matrix: dict,
        stage: dict,
        *,
        server_payload: bytes | None = None,
        include_server: bool = True,
    ) -> SimpleNamespace:
        scratch = ROOT / "build" / "full-system-acceptance-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            folder = Path(temporary)
            matrix_path = folder / "matrix.json"
            stage_path = folder / "stage.json"
            matrix_path.write_text(json.dumps(matrix), encoding="utf-8")
            stage_path.write_text(json.dumps(stage), encoding="utf-8")
            server_path = folder / "bedrock_server"
            plugin_path = folder / "plugin.so"
            tester_wheel_path = (
                folder
                / "endstone_sign_tester-0.2.1a1-cp314-cp314-linux_x86_64.whl"
            )
            log_path = folder / "server.log"
            backup_path = folder / "world-backup.zip"
            server_path.write_bytes(
                self.SERVER_PAYLOAD if server_payload is None else server_payload
            )
            plugin_path.write_bytes(self.PLUGIN_PAYLOAD)
            tester_wheel_path.write_bytes(self.TESTER_WHEEL_PAYLOAD)
            log_path.write_bytes(self.LOG_PAYLOAD)
            backup_path.write_bytes(self.BACKUP_PAYLOAD)
            arguments = [
                str(ROOT / "tools/validate_full_system_acceptance.py"),
                str(matrix_path),
                str(stage_path),
            ]
            if include_server:
                arguments.extend(("--server-executable", str(server_path)))
            arguments.extend(
                (
                    "--plugin-binary",
                    str(plugin_path),
                    "--tester-wheel",
                    str(tester_wheel_path),
                    "--server-log",
                    str(log_path),
                    "--world-backup",
                    str(backup_path),
                )
            )
            output = io.StringIO()
            errors = io.StringIO()
            expected_hash = hashlib.sha256(self.SERVER_PAYLOAD).hexdigest()
            with (
                mock.patch.dict(
                    validator.EXPECTED_SERVER_SHA256,
                    {"linux-x64": expected_hash},
                    clear=True,
                ),
                mock.patch.object(sys, "argv", arguments),
                redirect_stdout(output),
                redirect_stderr(errors),
            ):
                try:
                    return_code = validator.main()
                except SystemExit as error:
                    return_code = int(error.code or 0)
            return SimpleNamespace(
                returncode=return_code,
                stdout=output.getvalue() + errors.getvalue(),
            )

    def test_complete_evidence_passes(self) -> None:
        result = self.run_validator(*self.make_reports())
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("full-system acceptance VALID", result.stdout)

    def test_any_closed_layer_fails(self) -> None:
        matrix, stage = self.make_reports()
        matrix["bridge_status"]["capabilities"]["atomic_transactions"] = False
        automation.refresh_qualification(matrix)
        result = self.run_validator(matrix, stage)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("matrix.capabilities.atomic_transactions", result.stdout)

    def test_missing_case_operation_fails_even_with_stale_green_verdict(self) -> None:
        matrix, stage = self.make_reports()
        matrix["cases"][0]["steps"] = [
            step
            for step in matrix["cases"][0]["steps"]
            if step["operation"] != "place_blank"
        ]
        result = self.run_validator(matrix, stage)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing operations: place_blank", result.stdout)

    def test_missing_preflight_fails_even_with_stale_green_verdict(self) -> None:
        matrix, stage = self.make_reports()
        matrix["run_steps"] = [
            step
            for step in matrix["run_steps"]
            if step["operation"] != "arena_air_preflight"
        ]
        result = self.run_validator(matrix, stage)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("matrix required preflight evidence", result.stdout)

    def test_name_only_step_without_mutation_evidence_fails(self) -> None:
        matrix, stage = self.make_reports()
        place = next(
            step
            for step in matrix["cases"][0]["steps"]
            if step["operation"] == "place_blank"
        )
        place["mutation_attempted"] = False
        result = self.run_validator(matrix, stage)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing operations: place_blank", result.stdout)

    def test_replayed_stage_report_from_another_run_fails(self) -> None:
        matrix, stage = self.make_reports()
        stage["matrix_run_id"] = "20260730T000000Z-deadbeef"
        result = self.run_validator(matrix, stage)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("matrix/stage run_id mismatch", result.stdout)

    def test_supplied_tester_wheel_must_match_recorded_hash(self) -> None:
        matrix, stage = self.make_reports()
        stage["tester_wheel_sha256"] = "f" * 64
        matrix["tester_wheel_sha256"] = "f" * 64
        matrix["stage_report"]["tester_wheel_sha256"] = "f" * 64
        result = self.run_validator(matrix, stage)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("tester_wheel_sha256 does not match supplied file", result.stdout)

    def test_supplied_server_executable_must_match_exact_platform_hash(self) -> None:
        result = self.run_validator(
            *self.make_reports(), server_payload=b"wrong Bedrock server executable"
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "server_executable_sha256 does not match the exact platform executable",
            result.stdout,
        )

    def test_server_executable_argument_is_required(self) -> None:
        result = self.run_validator(*self.make_reports(), include_server=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn("--server-executable", result.stdout)

    def test_generic_ok_response_is_not_semantic_run_evidence(self) -> None:
        matrix, stage = self.make_reports()
        step = next(
            step
            for step in matrix["run_steps"]
            if step["operation"] == "capture_clone"
        )
        step["response"] = {"ok": True}
        self.assertTrue(matrix["qualification"]["eligible"])
        result = self.run_validator(matrix, stage)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "matrix.run_probe.capture_clone semantic evidence", result.stdout
        )

    def test_cleanup_requires_public_air_readback(self) -> None:
        matrix, stage = self.make_reports()
        cleanup = next(
            step
            for step in matrix["cases"][0]["steps"]
            if step["operation"] == "cleanup_remove_sign"
        )
        cleanup["after"] = {
            "found": True,
            "type": matrix["cases"][0]["identifier"],
            "dimension": matrix["cases"][0]["dimension"],
            **matrix["cases"][0]["sign"],
        }
        result = self.run_validator(matrix, stage)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("cleanup_remove_sign semantic evidence", result.stdout)

    def test_case_cleanup_ownership_requires_exact_false_boolean(self) -> None:
        base_matrix, stage = self.make_reports()
        for replacement in (None, 0, "false"):
            with self.subTest(replacement=replacement):
                matrix = copy.deepcopy(base_matrix)
                if replacement is None:
                    del matrix["cases"][0]["owned_sign"]
                else:
                    matrix["cases"][0]["owned_sign"] = replacement
                result = self.run_validator(matrix, stage)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("cleanup ownership schema", result.stdout)

    def test_scratch_cleanup_schema_requires_zero_revision_and_empty_snapshot(self) -> None:
        base_matrix, stage = self.make_reports()
        mutations = (
            ("expected_revision", False),
            ("expected_revision", 1),
            ("expected_snapshot", []),
            ("expected_snapshot", {"found": False}),
        )
        for field, replacement in mutations:
            with self.subTest(field=field, replacement=replacement):
                matrix = copy.deepcopy(base_matrix)
                matrix["run_probe"]["clone"][field] = replacement
                result = self.run_validator(matrix, stage)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(
                    "matrix run-probe clone cleanup evidence incomplete",
                    result.stdout,
                )

    def test_scratch_ownership_requires_exact_false_booleans(self) -> None:
        base_matrix, stage = self.make_reports()
        mutations = (
            ("clone", "owned_sign", 0),
            ("clone", "owned_support", "false"),
            ("move", "owned_sign", None),
            ("move", "owned_support", 0),
        )
        for name, field, replacement in mutations:
            with self.subTest(name=name, field=field, replacement=replacement):
                matrix = copy.deepcopy(base_matrix)
                if replacement is None:
                    del matrix["run_probe"][name][field]
                else:
                    matrix["run_probe"][name][field] = replacement
                result = self.run_validator(matrix, stage)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(
                    f"matrix run-probe {name} ownership schema", result.stdout
                )

    def test_cleanup_checkpoints_require_utc_timestamp_strings(self) -> None:
        base_matrix, stage = self.make_reports()
        mutations = (
            ("run_probe_cleanup_completed_at_utc", 0),
            ("cleanup.completed_at_utc", "not-a-timestamp"),
        )
        for field, replacement in mutations:
            with self.subTest(field=field):
                matrix = copy.deepcopy(base_matrix)
                if field.startswith("cleanup."):
                    matrix["cleanup"]["completed_at_utc"] = replacement
                else:
                    matrix[field] = replacement
                result = self.run_validator(matrix, stage)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(field, result.stdout)

    def test_atomic_guard_ownership_requires_exact_false_boolean(self) -> None:
        matrix, stage = self.make_reports()
        matrix["run_probe"]["atomic_guard"]["owned"] = 0
        result = self.run_validator(matrix, stage)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "matrix atomic rollback guard ownership schema", result.stdout
        )


if __name__ == "__main__":
    unittest.main()
