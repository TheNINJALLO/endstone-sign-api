from __future__ import annotations

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
    def __init__(self, write_text: bool) -> None:
        self.write_text = write_text
        self.set_text_calls: list[tuple[Any, ...]] = []

    def status(self, server: Any) -> dict[str, Any]:
        return {
            "available": True,
            "adapter": "test-adapter",
            "capabilities": {"write_text": self.write_text},
        }

    def set_text(self, *arguments: Any) -> dict[str, Any]:
        self.set_text_calls.append(arguments)
        return {"ok": True, "status": "applied", "message": "applied", "revision": 7}


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

    def _save_invocation(
        self,
        report: dict[str, Any],
        operation: str,
        request: dict[str, Any],
        response: dict[str, Any],
    ) -> None:
        self.invocations.append((operation, request, response))


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
            self.assertEqual(selected, first)
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
            self.assertEqual(selected, second)
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

            self.assertEqual(selected, plugin)
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

            self.assertEqual(selected, plugin)
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
        self.assertIn("write_text capability is disabled", response["message"])
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
        self.assertIsNotNone(response)
        self.assertTrue(response["ok"])
        self.assertEqual(harness.invocations[0][2]["status"], "applied")

    def test_live_snapshot_binding_exports_diagnostics(self) -> None:
        source = (ROOT / "src" / "live_python_bindings.cpp").read_text(encoding="utf-8")
        for field in (
            "remote_profanity_filter_enabled",
            "local_profanity_filter_enabled",
            "movable",
            "actor_status",
        ):
            self.assertIn(f'out["{field}"]', source)
        self.assertIn("signActorStatusName(snapshot.actor_status)", source)


if __name__ == "__main__":
    unittest.main()
