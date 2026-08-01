from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import sys
import tempfile
from types import ModuleType
from typing import Any
import unittest


ROOT = Path(__file__).resolve().parents[2]
PACKAGE_DIR = (
    ROOT
    / "examples"
    / "python"
    / "sign_api_tester_plugin"
    / "src"
    / "endstone_sign_tester"
)


def load_plugin_module() -> ModuleType:
    package_name = "_endstone_sign_tester_diagnostic_tests"
    package = ModuleType(package_name)
    package.__path__ = [str(PACKAGE_DIR)]  # type: ignore[attr-defined]
    sys.modules[package_name] = package

    fake_endstone = ModuleType("endstone")
    fake_command = ModuleType("endstone.command")
    fake_plugin = ModuleType("endstone.plugin")
    fake_command.Command = type("Command", (), {})  # type: ignore[attr-defined]
    fake_command.CommandSender = type("CommandSender", (), {})  # type: ignore[attr-defined]
    fake_plugin.Plugin = type("Plugin", (), {})  # type: ignore[attr-defined]

    names = ("endstone", "endstone.command", "endstone.plugin")
    previous = {name: sys.modules.get(name) for name in names}
    sys.modules["endstone"] = fake_endstone
    sys.modules["endstone.command"] = fake_command
    sys.modules["endstone.plugin"] = fake_plugin
    try:
        module_name = f"{package_name}.plugin"
        spec = importlib.util.spec_from_file_location(module_name, PACKAGE_DIR / "plugin.py")
        if spec is None or spec.loader is None:
            raise AssertionError("could not load tester plugin module")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        for name, value in previous.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value


PLUGIN_MODULE = load_plugin_module()
PLUGIN_CLASS = PLUGIN_MODULE.SignApiTesterPlugin


class FakeSender:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def send_message(self, message: str) -> None:
        self.messages.append(message)


class FakeBridge:
    def __init__(self, write_text: bool, **extra_capabilities: bool) -> None:
        self.write_text = write_text
        self.extra_capabilities = extra_capabilities
        self.set_text_calls: list[tuple[Any, ...]] = []

    def status(self, server: Any) -> dict[str, Any]:
        return {
            "available": True,
            "adapter": "test-adapter",
            "capabilities": {
                "exact_build_match": True,
                "exact_binary_hash_match": True,
                "capture": True,
                "client_updates": True,
                "read_text": self.write_text,
                "write_text": self.write_text,
                "front_and_back": self.write_text,
                **self.extra_capabilities,
            },
        }

    def set_text(self, *arguments: Any) -> dict[str, Any]:
        self.set_text_calls.append(arguments)
        return {"ok": True, "status": "applied", "message": "applied", "revision": 7}

    def capture(self, *arguments: Any) -> dict[str, Any]:
        return {"found": True, "revision": 6}


class SetTextHarness:
    def __init__(self, bridge: FakeBridge) -> None:
        self.server = object()
        self.bridge = bridge
        self.invocations: list[tuple[str, dict[str, Any], dict[str, Any]]] = []

    def _bridge(self, sender: FakeSender) -> FakeBridge:
        return self.bridge

    @staticmethod
    def _target(report: dict[str, Any]) -> tuple[str, int, int, int]:
        return PLUGIN_CLASS._target(report)

    @staticmethod
    def _write_text_preflight(bridge: Any, server: Any) -> tuple[bool, str]:
        return PLUGIN_CLASS._write_text_preflight(bridge, server)

    @staticmethod
    def _mutation_preflight(
        bridge: Any,
        server: Any,
        operation: str,
        required_capabilities: tuple[str, ...] | list[str],
    ) -> tuple[bool, str, dict[str, Any]]:
        return PLUGIN_CLASS._mutation_preflight(
            bridge, server, operation, required_capabilities
        )

    def _save_invocation(
        self,
        report: dict[str, Any],
        operation: str,
        request: dict[str, Any],
        response: dict[str, Any],
    ) -> None:
        self.invocations.append((operation, request, response))

    def _capture(
        self, sender: FakeSender, report: dict[str, Any], *, record: bool = True
    ) -> dict[str, Any]:
        return self.bridge.capture(self.server, *self._target(report))


class FakeMatrixBlock:
    def __init__(self) -> None:
        self.type = "minecraft:air"

    def set_type(self, block_type: str, apply_physics: bool = True) -> None:
        self.type = block_type


class FakeMatrixDimension:
    def __init__(self) -> None:
        self.blocks: dict[tuple[int, int, int], FakeMatrixBlock] = {}

    def get_block_at(self, x: int, y: int, z: int) -> FakeMatrixBlock:
        return self.blocks.setdefault((x, y, z), FakeMatrixBlock())


class FakeMatrixLevel:
    def __init__(self, dimension: FakeMatrixDimension) -> None:
        self.dimension = dimension
        self.name = "test-world"
        self.seed = 12345

    def get_dimension(self, name: str) -> FakeMatrixDimension:
        return self.dimension


class FakeMatrixLogger:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def info(self, message: str) -> None:
        self.messages.append(message)

    def error(self, message: str) -> None:
        self.messages.append(message)


class FakeMatrixServer:
    def __init__(self, dimension: FakeMatrixDimension) -> None:
        self.level = FakeMatrixLevel(dimension)

    def get_player(self, name: str) -> None:
        return None


class FakeBlockDescriptor:
    def __init__(self, block_type: str, states: dict[str, Any] | None = None) -> None:
        self.type = block_type
        self.block_states = dict(states or {})


class FakeDescriptorServer:
    def __init__(self, invalid: set[str] | None = None) -> None:
        self.invalid = set(invalid or ())
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def create_block_data(
        self, block_type: str, states: dict[str, Any] | None = None
    ) -> FakeBlockDescriptor:
        requested = dict(states or {})
        self.calls.append((block_type, requested))
        if block_type in self.invalid:
            raise ValueError(f"unknown block type: {block_type}")
        return FakeBlockDescriptor(block_type, requested)


class FakeMatrixBridge:
    def __init__(self, dimension: FakeMatrixDimension) -> None:
        self.dimension = dimension
        self.snapshots: dict[tuple[int, int, int], dict[str, Any]] = {}
        self.revision = 100
        self.advanced_calls = 0

    @staticmethod
    def _caps() -> dict[str, bool]:
        return {
            "exact_build_match": True,
            "exact_binary_hash_match": True,
            "capture": True,
            "client_updates": True,
            "place": True,
            "remove": True,
            "read_text": True,
            "write_text": True,
            "front_and_back": True,
            "per_line_write": True,
            "text_color": False,
            "glowing": False,
            "waxed": False,
        }

    def status(self, server: Any) -> dict[str, Any]:
        return {
            "available": True,
            "adapter": "fake-exact-matrix",
            "capabilities": self._caps(),
        }

    def place(
        self,
        server: Any,
        dimension: str,
        x: int,
        y: int,
        z: int,
        identifier: str,
        states: dict[str, Any],
    ) -> dict[str, Any]:
        block = self.dimension.get_block_at(x, y, z)
        if block.type != "minecraft:air":
            return {"ok": False, "status": "block_occupied", "revision": 0}
        block.type = identifier
        self.revision += 1
        kind = (
            "wall_hanging"
            if identifier.endswith("_hanging_sign") and states.get("hanging") is False
            else "ceiling_hanging"
            if identifier.endswith("_hanging_sign")
            else "wall"
            if identifier.endswith("wall_sign")
            else "standing"
        )
        self.snapshots[(x, y, z)] = {
            "found": True,
            "dimension": dimension,
            "x": x,
            "y": y,
            "z": z,
            "block_identifier": identifier,
            "kind": kind,
            "states": dict(states),
            "front": {
                "lines": ["", "", "", ""],
                "filtered_message": "",
                "text_object": "",
                "message_is_text_object": False,
                "argb": 0xFF000000,
                "glowing": False,
                "hide_glow_outline": False,
                "persist_formatting": True,
                "owner_xuid": "",
            },
            "back": {
                "lines": ["", "", "", ""],
                "filtered_message": "",
                "text_object": "",
                "message_is_text_object": False,
                "argb": 0xFF000000,
                "glowing": False,
                "hide_glow_outline": False,
                "persist_formatting": True,
                "owner_xuid": "",
            },
            "waxed": False,
            "locked_for_editing_by": -1,
            "locked_for_editing_xuid": None,
            "remote_profanity_filter_enabled": False,
            "local_profanity_filter_enabled": False,
            "movable": True,
            "actor_status": "captured",
            "revision": self.revision,
        }
        return {"ok": True, "status": "applied", "revision": self.revision}

    def capture(
        self, server: Any, dimension: str, x: int, y: int, z: int
    ) -> dict[str, Any]:
        snapshot = self.snapshots.get((x, y, z))
        return {"found": False} if snapshot is None else {
            **snapshot,
            "front": dict(snapshot["front"]),
            "back": dict(snapshot["back"]),
            "states": dict(snapshot["states"]),
        }

    def set_text(
        self,
        server: Any,
        dimension: str,
        x: int,
        y: int,
        z: int,
        side: str,
        lines: list[str],
        argb: int | None,
        glowing: bool | None,
        waxed: bool | None,
        force: bool,
        expected_revision: int | None,
    ) -> dict[str, Any]:
        if any(value is not None for value in (argb, glowing, waxed)):
            self.advanced_calls += 1
        snapshot = self.snapshots[(x, y, z)]
        if expected_revision != snapshot["revision"]:
            return {
                "ok": False,
                "status": "conflict",
                "revision": snapshot["revision"],
            }
        snapshot[side]["lines"] = list(lines)
        if argb is not None:
            snapshot[side]["argb"] = argb
        if glowing is not None:
            snapshot[side]["glowing"] = glowing
        if waxed is not None:
            snapshot["waxed"] = waxed
        self.revision += 1
        snapshot["revision"] = self.revision
        return {"ok": True, "status": "applied", "revision": self.revision}

    def remove(
        self,
        server: Any,
        dimension: str,
        x: int,
        y: int,
        z: int,
        force: bool,
        expected_revision: int,
    ) -> dict[str, Any]:
        snapshot = self.snapshots.get((x, y, z))
        if snapshot is None:
            return {"ok": False, "status": "not_a_sign", "revision": 0}
        if snapshot["revision"] != expected_revision:
            return {
                "ok": False,
                "status": "conflict",
                "revision": snapshot["revision"],
            }
        del self.snapshots[(x, y, z)]
        self.dimension.get_block_at(x, y, z).type = "minecraft:air"
        return {"ok": True, "status": "applied", "revision": 0}


class FakeFullSystemBridge(FakeMatrixBridge):
    @staticmethod
    def _caps() -> dict[str, bool]:
        return {
            "capture": True,
            "place": True,
            "remove": True,
            "replace": True,
            "clone": True,
            "move": True,
            "atomic_transactions": True,
            "read_text": True,
            "write_text": True,
            "front_and_back": True,
            "per_line_write": True,
            "text_objects": True,
            "filtered_text": True,
            "owner_xuid": True,
            "text_color": True,
            "glowing": True,
            "hide_glow_outline": True,
            "persist_formatting": True,
            "waxed": True,
            "editor_lock": True,
            "open_editor": True,
            "player_edit_events": True,
            "api_edit_events": True,
            "client_updates": True,
            "restart_persistence": True,
            "exact_build_match": True,
            "exact_binary_hash_match": True,
            "symbols_validated": True,
            "stage_probe_passed": False,
        }

    @staticmethod
    def _kind(identifier: str, states: dict[str, Any]) -> str:
        if identifier.endswith("_hanging_sign"):
            return "wall_hanging" if states.get("hanging") is False else "ceiling_hanging"
        return "wall" if identifier.endswith("wall_sign") else "standing"

    def _advance(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        self.revision += 1
        snapshot["revision"] = self.revision
        return {"ok": True, "status": "applied", "revision": self.revision}

    def set_extended_text(
        self,
        server: Any,
        dimension: str,
        x: int,
        y: int,
        z: int,
        side: str,
        filtered_message: str | None,
        text_object: str | None,
        message_is_text_object: bool | None,
        owner_xuid: str | None,
        hide_glow_outline: bool | None,
        persist_formatting: bool | None,
        force: bool,
        expected_revision: int,
    ) -> dict[str, Any]:
        snapshot = self.snapshots[(x, y, z)]
        if snapshot["revision"] != expected_revision:
            return {"ok": False, "status": "conflict", "revision": snapshot["revision"]}
        values = {
            "filtered_message": filtered_message,
            "text_object": text_object,
            "message_is_text_object": message_is_text_object,
            "owner_xuid": owner_xuid,
            "hide_glow_outline": hide_glow_outline,
            "persist_formatting": persist_formatting,
        }
        for name, value in values.items():
            if value is not None:
                snapshot[side][name] = value
        return self._advance(snapshot)

    def set_editor_lock(
        self,
        server: Any,
        dimension: str,
        x: int,
        y: int,
        z: int,
        locked_for_editing_by: int,
        locked_for_editing_xuid: str | None,
        force: bool,
        expected_revision: int,
    ) -> dict[str, Any]:
        snapshot = self.snapshots[(x, y, z)]
        if snapshot["revision"] != expected_revision:
            return {"ok": False, "status": "conflict", "revision": snapshot["revision"]}
        snapshot["locked_for_editing_by"] = locked_for_editing_by
        if locked_for_editing_xuid is not None:
            snapshot["locked_for_editing_xuid"] = locked_for_editing_xuid or None
        return self._advance(snapshot)

    def replace(
        self,
        server: Any,
        dimension: str,
        x: int,
        y: int,
        z: int,
        identifier: str,
        states: dict[str, Any],
        force: bool,
        expected_revision: int,
    ) -> dict[str, Any]:
        snapshot = self.snapshots[(x, y, z)]
        if snapshot["revision"] != expected_revision:
            return {"ok": False, "status": "conflict", "revision": snapshot["revision"]}
        snapshot["block_identifier"] = identifier
        snapshot["states"] = dict(states)
        snapshot["kind"] = self._kind(identifier, states)
        self.dimension.get_block_at(x, y, z).type = identifier
        return self._advance(snapshot)

    def clone(
        self,
        server: Any,
        dimension: str,
        source_x: int,
        source_y: int,
        source_z: int,
        destination_x: int,
        destination_y: int,
        destination_z: int,
        copy_editor_lock: bool,
        force: bool,
        expected_source_revision: int,
    ) -> dict[str, Any]:
        source = self.snapshots[(source_x, source_y, source_z)]
        if source["revision"] != expected_source_revision:
            return {"ok": False, "status": "conflict", "revision": source["revision"]}
        destination = copy.deepcopy(source)
        destination.update(
            {"x": destination_x, "y": destination_y, "z": destination_z}
        )
        if not copy_editor_lock:
            destination["locked_for_editing_by"] = -1
            destination["locked_for_editing_xuid"] = None
        self.snapshots[(destination_x, destination_y, destination_z)] = destination
        self.dimension.get_block_at(destination_x, destination_y, destination_z).type = str(
            destination["block_identifier"]
        )
        return self._advance(destination)

    def move(self, *args: Any) -> dict[str, Any]:
        (
            server,
            dimension,
            source_x,
            source_y,
            source_z,
            destination_x,
            destination_y,
            destination_z,
            copy_editor_lock,
            force,
            expected_source_revision,
        ) = args
        result = self.clone(
            server,
            dimension,
            source_x,
            source_y,
            source_z,
            destination_x,
            destination_y,
            destination_z,
            copy_editor_lock,
            force,
            expected_source_revision,
        )
        if result["ok"]:
            del self.snapshots[(source_x, source_y, source_z)]
            self.dimension.get_block_at(source_x, source_y, source_z).type = "minecraft:air"
        return result

    def probe_api_event_cancellation(self, *args: Any) -> dict[str, Any]:
        return {
            "ok": True,
            "status": "cancelled",
            "event_observed": True,
            "event_cancelled": True,
            "state_unchanged": True,
            "listener_removed": True,
        }

    def probe_atomic_rejection(self, *args: Any) -> dict[str, Any]:
        return {
            "ok": True,
            "status": "conflict",
            "transaction_rejected": True,
            "first_sign_unchanged": True,
            "rolled_back": True,
        }


def load_automation_module() -> ModuleType:
    module_name = "_endstone_sign_tester_automation_tests"
    spec = importlib.util.spec_from_file_location(module_name, PACKAGE_DIR / "automation.py")
    if spec is None or spec.loader is None:
        raise AssertionError("could not load automation module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


AUTOMATION_MODULE = load_automation_module()


class SignTesterDiagnosticTests(unittest.TestCase):
    def test_plugin_discovery_distinguishes_no_match_and_ambiguity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            working_directory = Path(temporary)
            selected, discovery = PLUGIN_CLASS._discover_native_plugin(
                working_directory, ".so"
            )
            self.assertIsNone(selected)
            self.assertEqual(discovery["status"], "not_found")
            self.assertEqual(discovery["candidates"], [])
            self.assertEqual(
                discovery["patterns"],
                [
                    "plugins/**/endstone_sign_bds_1_26_33.so",
                    (
                        "plugins/**/endstone-sign-api-v0.2.0-alpha.3-"
                        "bds-1.26.33-linux-x64.so"
                    ),
                ],
            )

            first = (
                working_directory
                / "plugins"
                / "first"
                / "endstone_sign_bds_1_26_33.so"
            )
            second = (
                working_directory
                / "plugins"
                / "second"
                / "endstone-sign-api-v0.2.0-alpha.3-bds-1.26.33-linux-x64.so"
            )
            unrelated = working_directory / "plugins" / "unrelated.so"
            first.parent.mkdir(parents=True)
            first.write_bytes(b"first")

            selected, discovery = PLUGIN_CLASS._discover_native_plugin(
                working_directory, ".so"
            )
            self.assertEqual(selected, first.resolve())
            self.assertEqual(discovery["status"], "selected")

            second.parent.mkdir(parents=True)
            second.write_bytes(b"second")
            unrelated.write_bytes(b"unrelated")
            selected, discovery = PLUGIN_CLASS._discover_native_plugin(
                working_directory, ".so"
            )
            self.assertIsNone(selected)
            self.assertEqual(discovery["status"], "ambiguous")
            self.assertEqual(
                discovery["candidates"],
                [
                    "plugins/first/endstone_sign_bds_1_26_33.so",
                    (
                        "plugins/second/"
                        "endstone-sign-api-v0.2.0-alpha.3-bds-1.26.33-linux-x64.so"
                    ),
                ],
            )

            first.unlink()
            selected, discovery = PLUGIN_CLASS._discover_native_plugin(
                working_directory, ".so"
            )
            self.assertEqual(selected, second.resolve())
            self.assertEqual(discovery["status"], "selected")

    def test_plugin_discovery_falls_back_to_server_executable_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            working_directory = workspace / "panel-working-directory"
            server_directory = workspace / "server"
            working_directory.mkdir()
            plugin = server_directory / "plugins" / "endstone_sign_bds_1_26_33.so"
            plugin.parent.mkdir(parents=True)
            plugin.write_bytes(b"plugin")

            selected, discovery = PLUGIN_CLASS._discover_native_plugin(
                working_directory,
                ".so",
                server_directory / "bedrock_server",
            )

            self.assertEqual(selected, plugin.resolve())
            self.assertEqual(discovery["status"], "selected")
            self.assertEqual(discovery["candidates"], [plugin.resolve().as_posix()])
            self.assertEqual(len(discovery["roots"]), 2)

    def test_plugin_discovery_accepts_legacy_windows_release_name(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            working_directory = Path(temporary)
            plugin = (
                working_directory
                / "plugins"
                / "endstone-sign-api-v0.2.0-alpha.3-bds-1.26.33-windows-x64.dll"
            )
            plugin.parent.mkdir()
            plugin.write_bytes(b"plugin")

            selected, discovery = PLUGIN_CLASS._discover_native_plugin(
                working_directory, ".dll"
            )

            self.assertEqual(selected, plugin.resolve())
            self.assertEqual(discovery["status"], "selected")

    def test_tester_wheel_discovery_requires_one_exact_version(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            working_directory = Path(temporary)
            plugins = working_directory / "plugins"
            plugins.mkdir()
            platform_tag = (
                "win_amd64" if sys.platform == "win32" else "linux_x86_64"
            )
            alpha7 = (
                plugins
                / f"endstone_sign_tester-0.2.0a7-cp314-cp314-{platform_tag}.whl"
            )
            stable = (
                plugins
                / f"endstone_sign_tester-0.2.0-cp314-cp314-{platform_tag}.whl"
            )
            alpha7.write_bytes(b"old")

            selected, discovery = PLUGIN_CLASS._discover_tester_wheel(
                working_directory, "0.2.0"
            )
            self.assertIsNone(selected)
            self.assertEqual(discovery["status"], "not_found")

            stable.write_bytes(b"current")
            selected, discovery = PLUGIN_CLASS._discover_tester_wheel(
                working_directory, "0.2.0"
            )
            self.assertEqual(selected, stable.resolve())
            self.assertEqual(discovery["status"], "selected")

    def test_write_text_preflight_blocks_mutation_and_records_why(self) -> None:
        bridge = FakeBridge(write_text=False)
        harness = SetTextHarness(bridge)
        sender = FakeSender()
        report = {"target": {"dimension": "Overworld", "x": 1, "y": 2, "z": 3}}

        response = PLUGIN_CLASS._set_text(
            harness,
            sender,
            report,
            side="back",
            lines=["test", "", "", ""],
        )

        self.assertEqual(bridge.set_text_calls, [])
        self.assertIsNotNone(response)
        self.assertEqual(response["status"], "unsupported")
        self.assertFalse(response["mutation_attempted"])
        self.assertIn("write_text gate is closed", response["message"])
        self.assertEqual(len(harness.invocations), 1)
        self.assertEqual(harness.invocations[0][0], "set_text")

    def test_write_text_preflight_allows_supported_mutation(self) -> None:
        bridge = FakeBridge(write_text=True)
        harness = SetTextHarness(bridge)
        report = {"target": {"dimension": "Overworld", "x": 1, "y": 2, "z": 3}}

        response = PLUGIN_CLASS._set_text(
            harness,
            FakeSender(),
            report,
            side="front",
            lines=["one", "two", "three", "four"],
        )

        self.assertEqual(len(bridge.set_text_calls), 1)
        self.assertFalse(bridge.set_text_calls[0][-2])
        self.assertEqual(bridge.set_text_calls[0][-1], 6)
        self.assertIsNotNone(response)
        self.assertTrue(response["ok"])
        self.assertEqual(harness.invocations[0][1]["expected_revision"], 6)
        self.assertEqual(harness.invocations[0][2]["status"], "applied")

    def test_successful_mutation_preflight_records_qualification_evidence(
        self,
    ) -> None:
        bridge = FakeBridge(write_text=True)

        ready, reason, status = PLUGIN_CLASS._mutation_preflight(
            bridge,
            object(),
            "automated matrix",
            ("read_text", "write_text", "front_and_back"),
        )

        self.assertTrue(ready)
        self.assertIn("gate passed", reason)
        self.assertIn("test-adapter", reason)
        self.assertTrue(status["available"])

    def test_advanced_fields_require_their_specific_capability(self) -> None:
        for field, keyword in (
            ("text_color", {"argb": 0xFF00FF00}),
            ("glowing", {"glowing": True}),
            ("waxed", {"waxed": True}),
        ):
            with self.subTest(field=field):
                bridge = FakeBridge(write_text=True, **{field: False})
                harness = SetTextHarness(bridge)
                response = PLUGIN_CLASS._set_text(
                    harness,
                    FakeSender(),
                    {"target": {"dimension": "Overworld", "x": 1, "y": 2, "z": 3}},
                    side="front",
                    lines=["safe", "", "", ""],
                    **keyword,
                )
                self.assertEqual(bridge.set_text_calls, [])
                self.assertEqual(response["status"], "unsupported")
                self.assertFalse(response["mutation_attempted"])
                self.assertIn(field, response["message"])

    def test_live_snapshot_binding_exports_diagnostics(self) -> None:
        source = (ROOT / "src" / "live_python_bindings.cpp").read_text(encoding="utf-8")
        self.assertIn('out["supported_release"] = caps.supportedRelease()', source)
        for field in (
            "remote_profanity_filter_enabled",
            "local_profanity_filter_enabled",
            "movable",
            "actor_status",
        ):
            self.assertIn(f'out["{field}"]', source)
        self.assertIn("signActorStatusName(snapshot.actor_status)", source)

    def test_live_bridge_exports_guarded_blank_place_and_safe_editor_flags(self) -> None:
        source = (ROOT / "src" / "live_python_bindings.cpp").read_text(encoding="utf-8")
        for operation in (
            "place",
            "set_extended_text",
            "set_editor_lock",
            "replace",
            "clone",
            "move",
            "probe_atomic_rejection",
            "probe_api_event_cancellation",
        ):
            self.assertIn(f'module.def("{operation}"', source)
        self.assertIn('py::arg("expected_revision") = py::none()', source)
        self.assertIn('py::arg("acquire_lock") = false', source)
        self.assertIn('py::arg("bypass_wax") = false', source)
        self.assertIn("loadProbeService(server)", source)
        probe_source = (ROOT / "src" / "live_probe_service.cpp").read_text(
            encoding="utf-8"
        )
        self.assertIn("event.actor.plugin_name", probe_source)
        self.assertIn("std::atomic<bool> active", probe_source)

    def test_matrix_resolves_every_descriptor_before_world_mutation(self) -> None:
        config = AUTOMATION_MODULE.load_config(PACKAGE_DIR / "default-config.toml")
        cases = AUTOMATION_MODULE.build_cases(
            config, "Overworld", {"x": 0, "y": 64, "z": 0}
        )
        server = FakeDescriptorServer()

        failures = PLUGIN_CLASS._matrix_descriptor_preflight(server, config, cases)

        self.assertEqual(failures, [])
        self.assertEqual(len(server.calls), 50)
        self.assertEqual(server.calls[0], ("minecraft:stone", {}))
        self.assertEqual(server.calls[1], ("minecraft:air", {}))
        self.assertEqual(
            server.calls[2],
            ("minecraft:standing_sign", {"ground_sign_direction": 0}),
        )

    def test_matrix_descriptor_preflight_rejects_bad_dark_oak_alias(self) -> None:
        config = AUTOMATION_MODULE.load_config(PACKAGE_DIR / "default-config.toml")
        config["materials"] = ["dark_oak"]
        config["kinds"] = ["standing"]
        cases = AUTOMATION_MODULE.build_cases(
            config, "Overworld", {"x": 0, "y": 64, "z": 0}
        )
        cases[0]["identifier"] = "minecraft:dark_oak_standing_sign"
        server = FakeDescriptorServer({"minecraft:dark_oak_standing_sign"})

        failures = PLUGIN_CLASS._matrix_descriptor_preflight(server, config, cases)

        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0]["case_id"], "01-dark_oak-standing")
        self.assertIn("unknown block type", failures[0]["reason"])

    def test_every_native_mutation_intent_is_a_durable_checkpoint(self) -> None:
        source = (PACKAGE_DIR / "plugin.py").read_text(encoding="utf-8")
        checkpoint_body = source.split("checkpoint_phases = {", 1)[1].split("}", 1)[0]
        for phase in (
            "place",
            "front",
            "back",
            "line_edit",
            "color",
            "glow",
            "wax",
            "unwax",
        ):
            with self.subTest(phase=phase):
                self.assertIn(f'"{phase}"', checkpoint_body)

    def test_structural_mutations_are_executable_hash_gated_inside_adapter(self) -> None:
        source = (ROOT / "src" / "experimental_bds_26_30_adapter.cpp").read_text(
            encoding="utf-8"
        )
        self.assertIn("structural Sign mutation requires the exact BDS executable", source)
        self.assertGreaterEqual(source.count("return binaryIdentityMismatch();"), 4)
        self.assertIn("result.capture = structural_mutation_gate", source)
        self.assertIn("force placement is disabled", source)
        self.assertIn("experimental removal requires a nonzero expected revision", source)

    def test_one_case_runner_places_and_verifies_text_without_advanced_calls(self) -> None:
        config = AUTOMATION_MODULE.load_config(PACKAGE_DIR / "default-config.toml")
        config["materials"] = ["oak"]
        config["kinds"] = ["standing"]
        config["cleanup_after_run"] = True
        dimension = FakeMatrixDimension()
        bridge = FakeMatrixBridge(dimension)
        report = AUTOMATION_MODULE.new_run_report(
            plugin_version="0.2.1a1",
            platform="linux-x64",
            operator="tester",
            dimension="Overworld",
            anchor={"x": 10, "y": 64, "z": 10},
            config=config,
            bridge_status=bridge.status(None),
        )
        report["state"] = "running"
        report["cursor"] = {"case_index": 0, "phase": "support"}
        with tempfile.TemporaryDirectory() as temporary:
            plugin = object.__new__(PLUGIN_CLASS)
            plugin.server = FakeMatrixServer(dimension)
            plugin.logger = FakeMatrixLogger()
            plugin.data_folder = temporary
            plugin.matrix_task = None
            plugin.matrix_cancel_requested = False
            context = {
                "mode": "run",
                "report": report,
                "bridge": bridge,
                "sender_name": "tester",
            }
            plugin.matrix_context = context
            plugin._schedule_matrix = lambda delay: None
            for _ in range(40):
                if plugin.matrix_context is None:
                    break
                plugin._matrix_run_tick(context)
            else:
                self.fail(f"runner did not finish: {report['cursor']}")

        self.assertEqual(report["state"], "completed")
        self.assertEqual(report["outcome"], "supported_scope_passed")
        self.assertEqual(report["cases"][0]["status"], "passed")
        self.assertEqual(bridge.advanced_calls, 0)
        self.assertEqual(report["coverage"]["standing_sign_place"]["status"], "passed")
        self.assertEqual(report["coverage"]["front_text_read_write"]["status"], "passed")
        self.assertEqual(report["coverage"]["back_text_read_write"]["status"], "passed")
        self.assertEqual(report["coverage"]["individual_line_edit"]["status"], "passed")
        self.assertEqual(report["coverage"]["wax"]["status"], "unsupported")
        self.assertEqual(report["cleanup"]["state"], "completed")
        self.assertTrue(report["cleanup"]["completed_at_utc"])
        case = report["cases"][0]
        self.assertEqual(
            dimension.get_block_at(**case["sign"]).type,
            "minecraft:air",
        )
        self.assertEqual(
            dimension.get_block_at(**case["support"]).type,
            "minecraft:air",
        )

    def test_placement_revision_mismatch_never_claims_ownership(self) -> None:
        config = AUTOMATION_MODULE.load_config(PACKAGE_DIR / "default-config.toml")
        config["materials"] = ["oak"]
        config["kinds"] = ["standing"]
        dimension = FakeMatrixDimension()
        bridge = FakeMatrixBridge(dimension)
        report = AUTOMATION_MODULE.new_run_report(
            plugin_version="0.2.1a1",
            platform="linux-x64",
            operator="tester",
            dimension="Overworld",
            anchor={"x": 15, "y": 64, "z": 15},
            config=config,
            bridge_status=bridge.status(None),
        )
        case = report["cases"][0]
        sign = case["sign"]
        placed = bridge.place(
            None,
            case["dimension"],
            sign["x"],
            sign["y"],
            sign["z"],
            case["identifier"],
            case["states"],
        )
        case["placement_revision"] = placed["revision"]
        bridge.snapshots[(sign["x"], sign["y"], sign["z"])]["revision"] += 1
        with tempfile.TemporaryDirectory() as temporary:
            plugin = object.__new__(PLUGIN_CLASS)
            plugin.server = FakeMatrixServer(dimension)
            plugin.data_folder = temporary
            plugin._schedule_matrix = lambda delay: None
            context = {
                "mode": "run",
                "report": report,
                "bridge": bridge,
                "plugin": plugin,
            }
            plugin._matrix_phase_capture_place(context, 0, case)
        self.assertFalse(case["owned_sign"])
        self.assertEqual(case["status"], "failed")

    def test_cleanup_preserves_support_when_capture_cannot_prove_air(self) -> None:
        config = AUTOMATION_MODULE.load_config(PACKAGE_DIR / "default-config.toml")
        config["materials"] = ["oak"]
        config["kinds"] = ["standing"]
        dimension = FakeMatrixDimension()
        bridge = FakeMatrixBridge(dimension)
        report = AUTOMATION_MODULE.new_run_report(
            plugin_version="0.2.1a1",
            platform="linux-x64",
            operator="tester",
            dimension="Overworld",
            anchor={"x": 18, "y": 64, "z": 18},
            config=config,
            bridge_status=bridge.status(None),
        )
        case = report["cases"][0]
        sign = case["sign"]
        support = case["support"]
        dimension.get_block_at(support["x"], support["y"], support["z"]).type = config[
            "support_block"
        ]
        placed = bridge.place(
            None,
            case["dimension"],
            sign["x"],
            sign["y"],
            sign["z"],
            case["identifier"],
            case["states"],
        )
        case["owned_support"] = True
        case["owned_sign"] = True
        case["expected_revision"] = placed["revision"]
        del bridge.snapshots[(sign["x"], sign["y"], sign["z"])]
        dimension.get_block_at(sign["x"], sign["y"], sign["z"]).type = (
            "minecraft:diamond_block"
        )
        plugin = object.__new__(PLUGIN_CLASS)
        plugin.server = FakeMatrixServer(dimension)
        context = {"mode": "cleanup", "report": report, "bridge": bridge, "plugin": plugin}

        self.assertFalse(plugin._matrix_cleanup_case(context, case, standalone=True))
        self.assertEqual(
            dimension.get_block_at(support["x"], support["y"], support["z"]).type,
            config["support_block"],
        )
        self.assertTrue(case["owned_support"])

    def test_cleanup_keeps_ownership_when_remove_does_not_produce_public_air(
        self,
    ) -> None:
        class LyingRemovalBridge(FakeMatrixBridge):
            def remove(
                self,
                server: Any,
                dimension: str,
                x: int,
                y: int,
                z: int,
                force: bool,
                expected_revision: int,
            ) -> dict[str, Any]:
                return {"ok": True, "status": "applied", "revision": 0}

        config = AUTOMATION_MODULE.load_config(PACKAGE_DIR / "default-config.toml")
        config["materials"] = ["oak"]
        config["kinds"] = ["standing"]
        dimension = FakeMatrixDimension()
        bridge = LyingRemovalBridge(dimension)
        report = AUTOMATION_MODULE.new_run_report(
            plugin_version="0.2.1a1",
            platform="linux-x64",
            operator="tester",
            dimension="Overworld",
            anchor={"x": 22, "y": 64, "z": 22},
            config=config,
            bridge_status=bridge.status(None),
        )
        case = report["cases"][0]
        sign = case["sign"]
        support = case["support"]
        dimension.get_block_at(**support).type = config["support_block"]
        placed = bridge.place(
            None,
            case["dimension"],
            sign["x"],
            sign["y"],
            sign["z"],
            case["identifier"],
            case["states"],
        )
        case["owned_support"] = True
        case["owned_sign"] = True
        case["expected_revision"] = placed["revision"]
        plugin = object.__new__(PLUGIN_CLASS)
        plugin.server = FakeMatrixServer(dimension)
        context = {"mode": "cleanup", "report": report, "bridge": bridge, "plugin": plugin}

        self.assertFalse(plugin._matrix_cleanup_case(context, case, standalone=True))
        self.assertTrue(case["owned_sign"])
        self.assertTrue(case["owned_support"])
        removal = next(
            step
            for step in case["steps"]
            if step["operation"] == "cleanup_remove_sign"
        )
        self.assertEqual(removal["status"], "failed")
        self.assertEqual(removal["after"]["type"], case["identifier"])

    def test_cleanup_report_validation_rejects_a_tampered_plan(self) -> None:
        config = AUTOMATION_MODULE.load_config(PACKAGE_DIR / "default-config.toml")
        dimension = FakeMatrixDimension()
        server = FakeMatrixServer(dimension)
        report = AUTOMATION_MODULE.new_run_report(
            plugin_version="0.2.1a1",
            platform=PLUGIN_CLASS._platform(),
            operator="tester",
            dimension="Overworld",
            anchor={"x": 30, "y": 64, "z": 30},
            config=config,
            bridge_status={},
        )
        report["state"] = "completed"
        report["world_name"] = server.level.name
        report["world_seed"] = str(server.level.seed)
        report["server_executable_sha256"] = "a" * 64
        report["plugin_sha256"] = "b" * 64
        report["tester_wheel_sha256"] = "c" * 64
        report["plugin_discovery"] = {"status": "selected"}
        report["tester_wheel_discovery"] = {"status": "selected"}
        sender = FakeSender()
        sender.location = type(
            "Location",
            (),
            {"dimension": type("Dimension", (), {"name": "Overworld"})()},
        )()
        with tempfile.TemporaryDirectory() as temporary:
            plugin = object.__new__(PLUGIN_CLASS)
            plugin.server = server
            plugin.data_folder = temporary
            plugin._binary_evidence = lambda: {
                "server_executable_sha256": "a" * 64,
                "plugin_sha256": "b" * 64,
                "plugin_discovery": {"status": "selected"},
                "tester_wheel_sha256": "c" * 64,
                "tester_wheel_discovery": {"status": "selected"},
            }
            AUTOMATION_MODULE.install_default_config(Path(temporary))
            self.assertEqual(plugin._validate_cleanup_report(sender, report), "")
            report["cases"][0]["sign"]["x"] += 1
            self.assertIn(
                "reconstructed plan",
                plugin._validate_cleanup_report(sender, report),
            )

    def test_full_system_run_probes_execute_through_live_bridge_surface(self) -> None:
        config = AUTOMATION_MODULE.load_acceptance_config()
        dimension = FakeMatrixDimension()
        bridge = FakeFullSystemBridge(dimension)
        report = AUTOMATION_MODULE.new_run_report(
            plugin_version="0.2.1a1",
            platform=PLUGIN_CLASS._platform(),
            operator="tester",
            dimension="Overworld",
            anchor={"x": 10, "y": 64, "z": 10},
            config=config,
            bridge_status=bridge.status(None),
            acceptance_mode=True,
        )
        for case in report["cases"][:2]:
            sign = case["sign"]
            placed = bridge.place(
                None,
                case["dimension"],
                sign["x"],
                sign["y"],
                sign["z"],
                case["identifier"],
                case["states"],
            )
            snapshot = bridge.snapshots[(sign["x"], sign["y"], sign["z"])]
            snapshot["front"]["lines"] = list(case["edited_front_lines"])
            snapshot["back"]["lines"] = list(case["back_lines"])
            case["owned_sign"] = True
            case["expected_revision"] = placed["revision"]
            case["status"] = "passed"

        plugin = object.__new__(PLUGIN_CLASS)
        plugin.server = FakeMatrixServer(dimension)
        plugin.logger = FakeMatrixLogger()
        plugin.data_folder = ROOT / "build" / "full-system-run-probe-test"
        Path(plugin.data_folder).mkdir(parents=True, exist_ok=True)
        terminal: list[tuple[str, str]] = []
        plugin._matrix_set_cursor = lambda context, case_index, phase: context[
            "report"
        ].update({"cursor": {"case_index": case_index, "phase": phase}})
        plugin._matrix_terminal = lambda state, message: terminal.append((state, message))
        context = {
            "mode": "run",
            "report": report,
            "bridge": bridge,
            "plugin": plugin,
            "sender_name": "tester",
        }

        for phase in PLUGIN_MODULE.RUN_PROBE_PHASES:
            plugin._matrix_run_probe_tick(context, phase)

        run_results = {
            step["operation"]: step["status"] for step in report["run_steps"]
        }
        self.assertEqual(
            {
                operation: run_results.get(operation)
                for operation in AUTOMATION_MODULE.REQUIRED_RUN_OPERATIONS
            },
            {
                operation: "passed"
                for operation in AUTOMATION_MODULE.REQUIRED_RUN_OPERATIONS
            },
        )
        self.assertEqual(terminal[-1][0], "completed")
        self.assertTrue(report["run_probe"]["move"]["owned_sign"])

        plugin._matrix_cleanup_probe_scratch(context)
        self.assertEqual(report["cleanup"]["conflicts"], [])
        for name in ("clone", "move"):
            self.assertFalse(report["run_probe"][name]["owned_sign"])
            self.assertFalse(report["run_probe"][name]["owned_support"])

    def test_run_probes_do_not_create_scratch_around_an_unowned_source(self) -> None:
        config = AUTOMATION_MODULE.load_acceptance_config()
        dimension = FakeMatrixDimension()
        bridge = FakeFullSystemBridge(dimension)
        report = AUTOMATION_MODULE.new_run_report(
            plugin_version="0.2.1a1",
            platform=PLUGIN_CLASS._platform(),
            operator="tester",
            dimension="Overworld",
            anchor={"x": 10, "y": 64, "z": 10},
            config=config,
            bridge_status=bridge.status(None),
            acceptance_mode=True,
        )
        case = report["cases"][0]
        sign = case["sign"]
        bridge.place(
            None,
            case["dimension"],
            sign["x"],
            sign["y"],
            sign["z"],
            case["identifier"],
            case["states"],
        )
        case["owned_sign"] = False
        case["expected_revision"] = 0

        plugin = object.__new__(PLUGIN_CLASS)
        plugin.server = FakeMatrixServer(dimension)
        plugin.data_folder = ROOT / "build" / "unowned-source-probe-test"
        Path(plugin.data_folder).mkdir(parents=True, exist_ok=True)
        context = {"report": report, "bridge": bridge, "plugin": plugin}

        plugin._matrix_run_clone_probe(context)
        plugin._matrix_run_atomic_probe(context)

        self.assertEqual(report["run_steps"][-2]["status"], "failed")
        self.assertEqual(report["run_steps"][-1]["status"], "failed")
        for name in ("clone", "move"):
            support = report["run_probe"][name]["support"]
            self.assertEqual(
                dimension.get_block_at(
                    support["x"], support["y"], support["z"]
                ).type,
                "minecraft:air",
            )
        guard = report["run_probe"]["atomic_guard"]
        location = guard["location"]
        self.assertEqual(
            dimension.get_block_at(location["x"], location["y"], location["z"]).type,
            "minecraft:air",
        )

    def test_cleanup_reports_unowned_planned_residue_after_a_crash_window(self) -> None:
        config = AUTOMATION_MODULE.load_acceptance_config()
        dimension = FakeMatrixDimension()
        bridge = FakeFullSystemBridge(dimension)
        report = AUTOMATION_MODULE.new_run_report(
            plugin_version="0.2.1a1",
            platform=PLUGIN_CLASS._platform(),
            operator="tester",
            dimension="Overworld",
            anchor={"x": 10, "y": 64, "z": 10},
            config=config,
            bridge_status=bridge.status(None),
            acceptance_mode=True,
        )
        clone = report["run_probe"]["clone"]
        support = clone["support"]
        dimension.get_block_at(support["x"], support["y"], support["z"]).type = config[
            "support_block"
        ]
        guard = report["run_probe"]["atomic_guard"]
        location = guard["location"]
        dimension.get_block_at(location["x"], location["y"], location["z"]).type = guard[
            "block_identifier"
        ]

        plugin = object.__new__(PLUGIN_CLASS)
        plugin.server = FakeMatrixServer(dimension)
        plugin.data_folder = ROOT / "build" / "unowned-residue-cleanup-test"
        Path(plugin.data_folder).mkdir(parents=True, exist_ok=True)
        context = {"report": report, "bridge": bridge, "plugin": plugin}

        plugin._matrix_cleanup_probe_scratch(context)

        reasons = " ".join(
            str(conflict.get("reason") or "")
            for conflict in report["cleanup"]["conflicts"]
        )
        self.assertIn("unowned guard block", reasons)
        self.assertIn("without verified runner ownership", reasons)
        self.assertEqual(
            dimension.get_block_at(support["x"], support["y"], support["z"]).type,
            config["support_block"],
        )
        self.assertEqual(
            dimension.get_block_at(location["x"], location["y"], location["z"]).type,
            guard["block_identifier"],
        )

    def test_acceptance_cleanup_ignores_editable_diagnostic_config(self) -> None:
        config = AUTOMATION_MODULE.load_acceptance_config()
        dimension = FakeMatrixDimension()
        server = FakeMatrixServer(dimension)
        report = AUTOMATION_MODULE.new_run_report(
            plugin_version="0.2.1a1",
            platform=PLUGIN_CLASS._platform(),
            operator="tester",
            dimension="Overworld",
            anchor={"x": 30, "y": 64, "z": 30},
            config=config,
            bridge_status={},
            acceptance_mode=True,
        )
        report["state"] = "completed"
        report["world_name"] = server.level.name
        report["world_seed"] = str(server.level.seed)
        report["server_executable_sha256"] = "a" * 64
        report["plugin_sha256"] = "b" * 64
        report["tester_wheel_sha256"] = "c" * 64
        report["plugin_discovery"] = {"status": "selected"}
        report["tester_wheel_discovery"] = {"status": "selected"}
        sender = FakeSender()
        sender.location = type(
            "Location",
            (),
            {"dimension": type("Dimension", (), {"name": "Overworld"})()},
        )()
        with tempfile.TemporaryDirectory() as temporary:
            plugin = object.__new__(PLUGIN_CLASS)
            plugin.server = server
            plugin.data_folder = temporary
            plugin._binary_evidence = lambda: {
                "server_executable_sha256": "a" * 64,
                "plugin_sha256": "b" * 64,
                "plugin_discovery": {"status": "selected"},
                "tester_wheel_sha256": "c" * 64,
                "tester_wheel_discovery": {"status": "selected"},
            }
            config_path = AUTOMATION_MODULE.install_default_config(Path(temporary))
            config_path.write_text("invalid = [", encoding="utf-8")
            self.assertEqual(plugin._validate_cleanup_report(sender, report), "")

    def test_acceptance_projects_automated_coverage_and_binds_stage(self) -> None:
        config = PLUGIN_MODULE.load_acceptance_config()
        platform = PLUGIN_CLASS._platform()
        matrix = PLUGIN_MODULE.new_run_report(
            plugin_version="0.2.1a1",
            platform=platform,
            operator="tester",
            dimension="Overworld",
            anchor={"x": 30, "y": 64, "z": 30},
            config=config,
            bridge_status={"capabilities": {}},
            acceptance_mode=True,
        )
        matrix["world_name"] = "test-world"
        matrix["world_seed"] = "12345"
        matrix["server_executable_sha256"] = "a" * 64
        matrix["plugin_sha256"] = "b" * 64
        matrix["tester_wheel_sha256"] = "c" * 64
        first_sign = matrix["cases"][0]["sign"]
        stage = PLUGIN_MODULE.new_report(
            platform=platform,
            operator="tester",
            dimension="Overworld",
            x=first_sign["x"],
            y=first_sign["y"],
            z=first_sign["z"],
        )
        stage.update(
            {
                "tester_version": "0.2.1a1",
                "matrix_run_id": matrix["run_id"],
                "matrix_config_sha256": matrix["config_sha256"],
                "world_name": "test-world",
                "world_seed": "12345",
                "server_executable_sha256": "a" * 64,
                "plugin_sha256": "b" * 64,
                "tester_wheel_sha256": "c" * 64,
            }
        )
        matrix["coverage"]["standing_sign_place"].update(
            {"status": "passed", "evidence": "48-case matrix evidence"}
        )
        with tempfile.TemporaryDirectory() as temporary:
            plugin = object.__new__(PLUGIN_CLASS)
            plugin.data_folder = temporary
            plugin.logger = FakeMatrixLogger()
            PLUGIN_MODULE.save_report(plugin._path(), stage)
            plugin._sync_acceptance_to_stage(matrix)
            projected = PLUGIN_MODULE.load_report(plugin._path())

        self.assertTrue(projected["results"]["standing_sign_place"]["passed"])
        self.assertEqual(
            projected["results"]["open_editor_front"]["evidence"],
            "not yet recorded",
        )
        stage["matrix_run_id"] = "20260730T000000Z-deadbeef"
        with self.assertRaisesRegex(ValueError, "matrix run ID"):
            PLUGIN_MODULE.apply_matrix_stage_report(matrix, stage)

    def test_cleanup_removes_matching_owned_cells_and_preserves_revision_conflicts(self) -> None:
        config = AUTOMATION_MODULE.load_config(PACKAGE_DIR / "default-config.toml")
        config["materials"] = ["oak"]
        config["kinds"] = ["standing"]
        dimension = FakeMatrixDimension()
        bridge = FakeMatrixBridge(dimension)
        report = AUTOMATION_MODULE.new_run_report(
            plugin_version="0.2.1a1",
            platform="linux-x64",
            operator="tester",
            dimension="Overworld",
            anchor={"x": 20, "y": 64, "z": 20},
            config=config,
            bridge_status=bridge.status(None),
        )
        case = report["cases"][0]
        support = case["support"]
        dimension.get_block_at(support["x"], support["y"], support["z"]).type = config[
            "support_block"
        ]
        case["owned_support"] = True
        sign = case["sign"]
        placed = bridge.place(
            None,
            case["dimension"],
            sign["x"],
            sign["y"],
            sign["z"],
            case["identifier"],
            case["states"],
        )
        case["owned_sign"] = True
        case["expected_revision"] = placed["revision"]
        report["cleanup"]["state"] = "running"
        plugin = object.__new__(PLUGIN_CLASS)
        plugin.server = FakeMatrixServer(dimension)
        plugin.logger = FakeMatrixLogger()
        plugin.data_folder = ROOT / "build" / "cleanup-checkpoint-test"
        Path(plugin.data_folder).mkdir(parents=True, exist_ok=True)
        context = {"mode": "cleanup", "report": report, "bridge": bridge, "plugin": plugin}

        self.assertTrue(plugin._matrix_cleanup_case(context, case, standalone=True))
        self.assertEqual(
            dimension.get_block_at(sign["x"], sign["y"], sign["z"]).type,
            "minecraft:air",
        )
        self.assertEqual(
            dimension.get_block_at(support["x"], support["y"], support["z"]).type,
            "minecraft:air",
        )

        # Recreate the owned cells, then simulate an outside edit by changing
        # the revision. Cleanup must preserve both cells and record a conflict.
        dimension.get_block_at(support["x"], support["y"], support["z"]).type = config[
            "support_block"
        ]
        case["owned_support"] = True
        placed = bridge.place(
            None,
            case["dimension"],
            sign["x"],
            sign["y"],
            sign["z"],
            case["identifier"],
            case["states"],
        )
        case["owned_sign"] = True
        case["expected_revision"] = placed["revision"]
        bridge.snapshots[(sign["x"], sign["y"], sign["z"])]["revision"] += 1
        self.assertFalse(plugin._matrix_cleanup_case(context, case, standalone=True))
        self.assertNotEqual(
            dimension.get_block_at(sign["x"], sign["y"], sign["z"]).type,
            "minecraft:air",
        )
        self.assertTrue(report["cleanup"]["conflicts"])


if __name__ == "__main__":
    unittest.main()
