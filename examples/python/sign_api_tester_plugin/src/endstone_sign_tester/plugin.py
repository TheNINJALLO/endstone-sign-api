"""Endstone commands for exercising the exact native Sign API and recording evidence."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from endstone.command import Command, CommandSender
from endstone.plugin import Plugin

from ._bridge_loader import import_live_bridge
from .report import (
    EDITABLE_METADATA,
    PROBE_NAMES,
    append_invocation,
    file_sha256,
    finish_report,
    load_report,
    new_report,
    record_result,
    report_path,
    save_report,
    set_metadata,
)


class SignApiTesterPlugin(Plugin):
    """Operator-only, explicit-coordinate probe harness for disposable worlds."""

    api_version = "0.11"
    version = "0.2.0a4"
    description = "Exact Sign API command probes and stage-report recorder"
    depend = ["sign_api"]

    commands = {
        "signprobe": {
            "description": "Exercise Sign API and record disposable-world evidence",
            "usages": [
                "/signprobe (help)<action: SignProbeHelpAction>",
                "/signprobe (status)<action: SignProbeStatusAction>",
                "/signprobe (begin)<action: SignProbeBeginAction> <x: int> <y: int> <z: int>",
                "/signprobe (capture)<action: SignProbeCaptureAction>",
                (
                    "/signprobe (text)<action: SignProbeTextAction> "
                    "(front|back)<side: SignProbeTextSide> <lines: message>"
                ),
                (
                    "/signprobe (glow)<action: SignProbeGlowAction> "
                    "(front|back)<side: SignProbeGlowSide> <enabled: bool>"
                ),
                "/signprobe (wax)<action: SignProbeWaxAction> <enabled: bool>",
                (
                    "/signprobe (color)<action: SignProbeColorAction> "
                    "(front|back)<side: SignProbeColorSide> <argb: str>"
                ),
                (
                    "/signprobe (editor)<action: SignProbeEditorAction> "
                    "(front|back)<side: SignProbeEditorSide>"
                ),
                "/signprobe (remove)<action: SignProbeRemoveAction> (confirm)<confirmation: SignProbeConfirm>",
                "/signprobe (record)<action: SignProbeRecordAction> <probe: str> <passed: bool> <evidence: message>",
                "/signprobe (meta)<action: SignProbeMetaAction> <field: str> <value: message>",
                "/signprobe (finish)<action: SignProbeFinishAction>",
                "/signprobe (path)<action: SignProbePathAction>",
            ],
            "aliases": ["sp"],
            "permissions": ["signprobe.admin"],
        }
    }
    permissions = {
        "signprobe.admin": {
            "description": "Allows destructive Sign API tests in a disposable world",
            "default": "op",
        }
    }

    def on_enable(self) -> None:
        self.live_bridge = None
        self.bridge_error = "bridge was not initialized"
        try:
            bridge = import_live_bridge(self.version)
            if not bridge.available(self.server):
                self.bridge_error = "endstone:sign:v2 is not registered"
            else:
                self.live_bridge = bridge
                self.bridge_error = ""
        except Exception as error:
            self.bridge_error = str(error)
        if self.live_bridge is None:
            self.logger.error(f"Sign tester native bridge unavailable: {self.bridge_error}")
        else:
            self.logger.warning(
                "Sign API tester enabled. Use only in a backed-up disposable world; "
                "mutation commands use explicit coordinates recorded by /signprobe begin."
            )

    @staticmethod
    def _platform() -> str:
        return "windows-x64" if sys.platform == "win32" else "linux-x64"

    @staticmethod
    def _sender_name(sender: CommandSender) -> str:
        return str(getattr(sender, "name", "console") or "console")

    @staticmethod
    def _dimension(sender: CommandSender) -> str | None:
        location = getattr(sender, "location", None)
        dimension = getattr(location, "dimension", None)
        if dimension is None:
            dimension = getattr(sender, "dimension", None)
        if dimension is None:
            return None
        name = getattr(dimension, "name", None)
        return str(name) if name else None

    def _path(self) -> Path:
        return report_path(Path(self.data_folder), self._platform())

    def _load(self, sender: CommandSender) -> dict[str, Any] | None:
        path = self._path()
        if not path.is_file():
            sender.send_message("Run /signprobe begin <x> <y> <z> first.")
            return None
        try:
            return load_report(path)
        except Exception as error:
            sender.send_message(f"Could not load stage report: {error}")
            return None

    def _bridge(self, sender: CommandSender) -> Any | None:
        if self.live_bridge is not None:
            return self.live_bridge
        try:
            bridge = import_live_bridge(self.version)
            if bridge.available(self.server):
                self.live_bridge = bridge
                self.bridge_error = ""
                return bridge
            self.bridge_error = "endstone:sign:v2 is not registered"
        except Exception as error:
            self.bridge_error = str(error)
        sender.send_message(f"Native Sign API unavailable: {self.bridge_error}")
        return None

    @staticmethod
    def _target(report: dict[str, Any]) -> tuple[str, int, int, int]:
        target = report["target"]
        return (
            str(target["dimension"]),
            int(target["x"]),
            int(target["y"]),
            int(target["z"]),
        )

    @staticmethod
    def _send_json(sender: CommandSender, label: str, value: Any) -> None:
        rendered = json.dumps(value, sort_keys=True, default=str)
        if len(rendered) > 900:
            rendered = rendered[:897] + "..."
        sender.send_message(f"{label}: {rendered}")

    @staticmethod
    def _discover_native_plugin(
        working_directory: Path,
        suffix: str,
        executable: Path | None = None,
    ) -> tuple[Path | None, dict[str, Any]]:
        platform = "windows-x64" if suffix == ".dll" else "linux-x64"
        patterns = (
            f"endstone_sign_bds_1_26_33{suffix}",
            (
                "endstone-sign-api-v0.2.0-alpha.3-bds-1.26.33-"
                f"{platform}{suffix}"
            ),
        )

        def normalized(path: Path) -> Path:
            try:
                return path.resolve(strict=False)
            except OSError:
                return path.absolute()

        working_directory = normalized(working_directory)
        roots = [working_directory / "plugins"]
        if executable is not None:
            roots.append(normalized(executable).parent / "plugins")

        unique_roots: dict[Path, Path] = {}
        for root in roots:
            unique_roots.setdefault(normalized(root), root)

        unique_candidates: dict[Path, Path] = {}
        for root in unique_roots.values():
            for pattern in patterns:
                for path in root.rglob(pattern):
                    if path.is_file():
                        unique_candidates.setdefault(normalized(path), path)
        candidates = sorted(
            unique_candidates.values(), key=lambda path: path.as_posix()
        )

        def display(path: Path) -> str:
            try:
                return normalized(path).relative_to(working_directory).as_posix()
            except ValueError:
                return normalized(path).as_posix()

        relative_candidates = [display(path) for path in candidates]
        discovery = {
            "pattern": " or ".join(f"plugins/**/{pattern}" for pattern in patterns),
            "patterns": [f"plugins/**/{pattern}" for pattern in patterns],
            "roots": [display(root) for root in unique_roots.values()],
            "candidates": relative_candidates,
        }
        if not candidates:
            return None, {"status": "not_found", **discovery}
        if len(candidates) > 1:
            return None, {"status": "ambiguous", **discovery}
        return candidates[0], {"status": "selected", **discovery}

    @staticmethod
    def _write_text_preflight(bridge: Any, server: Any) -> tuple[bool, str]:
        try:
            status = dict(bridge.status(server))
        except Exception as error:
            return (
                False,
                "could not verify native Sign API write_text capability; "
                f"mutation was not attempted: {error}",
            )
        try:
            capabilities = dict(status.get("capabilities") or {})
        except (TypeError, ValueError):
            capabilities = {}
        if capabilities.get("write_text") is not True:
            adapter = str(status.get("adapter") or "unknown")
            return (
                False,
                "native Sign API write_text capability is disabled for adapter "
                f"{adapter!r}; mutation was not attempted",
            )
        return True, ""

    def _save_invocation(
        self,
        report: dict[str, Any],
        operation: str,
        request: dict[str, Any],
        response: Any,
    ) -> None:
        append_invocation(report, operation, request, response)
        save_report(self._path(), report)

    def _capture(
        self, sender: CommandSender, report: dict[str, Any], *, record: bool = True
    ) -> dict[str, Any] | None:
        bridge = self._bridge(sender)
        if bridge is None:
            return None
        dimension, x, y, z = self._target(report)
        request = {"dimension": dimension, "x": x, "y": y, "z": z}
        try:
            response = dict(bridge.capture(self.server, dimension, x, y, z))
        except Exception as error:
            response = {"found": False, "error": str(error)}
        if record:
            self._save_invocation(report, "capture", request, response)
        return response

    @staticmethod
    def _lines(snapshot: dict[str, Any], side: str) -> list[str]:
        lines = list(dict(snapshot.get(side) or {}).get("lines") or [])
        if len(lines) != 4 or not all(isinstance(line, str) for line in lines):
            raise ValueError(f"capture did not return four {side} lines")
        return lines

    @staticmethod
    def _parse_lines(raw: str) -> list[str]:
        lines = [part.strip() for part in raw.split("|")]
        if len(lines) > 4:
            raise ValueError("provide at most four lines separated with |")
        return lines + [""] * (4 - len(lines))

    def _set_text(
        self,
        sender: CommandSender,
        report: dict[str, Any],
        *,
        side: str,
        lines: list[str],
        argb: int | None = None,
        glowing: bool | None = None,
        waxed: bool | None = None,
    ) -> dict[str, Any] | None:
        bridge = self._bridge(sender)
        if bridge is None:
            return None
        dimension, x, y, z = self._target(report)
        request = {
            "dimension": dimension,
            "x": x,
            "y": y,
            "z": z,
            "side": side,
            "lines": lines,
            "argb": argb,
            "glowing": glowing,
            "waxed": waxed,
            "force": False,
        }
        write_text_ready, preflight_message = self._write_text_preflight(
            bridge, self.server
        )
        if not write_text_ready:
            response = {
                "ok": False,
                "status": "unsupported",
                "message": preflight_message,
                "revision": 0,
                "mutation_attempted": False,
            }
            self._save_invocation(report, "set_text", request, response)
            return response
        try:
            response = dict(
                bridge.set_text(
                    self.server,
                    dimension,
                    x,
                    y,
                    z,
                    side,
                    lines,
                    argb,
                    glowing,
                    waxed,
                    False,
                )
            )
        except Exception as error:
            response = {"ok": False, "status": "exception", "message": str(error)}
        self._save_invocation(report, "set_text", request, response)
        return response

    def on_command(self, sender: CommandSender, command: Command, args: list[str]) -> bool:
        if command.name not in {"signprobe", "sp"}:
            return False
        action = args[0].casefold() if args else "help"
        handler = getattr(self, f"_handle_{action}", None)
        if handler is None:
            self._handle_help(sender, [])
            return True
        try:
            return bool(handler(sender, args[1:]))
        except Exception as error:
            self.logger.error(f"Sign probe command failed: {error}")
            sender.send_message(f"Sign probe failed safely: {error}")
            return True

    def _handle_help(self, sender: CommandSender, args: list[str]) -> bool:
        sender.send_message("Sign API tester (disposable worlds only)")
        sender.send_message("/signprobe status")
        sender.send_message("/signprobe begin <x> <y> <z> - set explicit target")
        sender.send_message("/signprobe capture")
        sender.send_message("/signprobe text <front|back> line1|line2|line3|line4")
        sender.send_message("/signprobe glow <front|back> <true|false>")
        sender.send_message("/signprobe wax <true|false>")
        sender.send_message("/signprobe color <front|back> <0xAARRGGBB>")
        sender.send_message("/signprobe editor <front|back>")
        sender.send_message("/signprobe remove confirm")
        sender.send_message("/signprobe record <probe> <true|false> <evidence>")
        sender.send_message("/signprobe meta <field> <value>; /signprobe finish; /signprobe path")
        return True

    def _handle_status(self, sender: CommandSender, args: list[str]) -> bool:
        bridge = self._bridge(sender)
        if bridge is None:
            return True
        try:
            status = dict(bridge.status(self.server))
        except Exception as error:
            status = {"available": False, "error": str(error)}
        self._send_json(sender, "Native status", status)
        report = self._load(sender)
        if report is not None:
            self._save_invocation(report, "status", {}, status)
        return True

    def _handle_begin(self, sender: CommandSender, args: list[str]) -> bool:
        if len(args) != 3:
            sender.send_message("Usage: /signprobe begin <x> <y> <z>")
            return True
        dimension = self._dimension(sender)
        if dimension is None:
            sender.send_message("Run begin as a player in the target dimension.")
            return True
        try:
            x, y, z = (int(value) for value in args)
        except ValueError:
            sender.send_message("Coordinates must be integers.")
            return True
        report = new_report(
            platform=self._platform(),
            operator=self._sender_name(sender),
            dimension=dimension,
            x=x,
            y=y,
            z=z,
        )
        server_candidates = [
            Path.cwd()
            / ("bedrock_server.exe" if sys.platform == "win32" else "bedrock_server"),
            Path(sys.executable),
        ]
        if sys.platform != "win32":
            try:
                server_candidates.append(Path("/proc/self/exe").resolve(strict=True))
            except OSError:
                pass
        server_executable: Path | None = None
        for candidate in server_candidates:
            if candidate.is_file() and candidate.name.startswith("bedrock_server"):
                report["server_executable_sha256"] = file_sha256(candidate)
                server_executable = candidate
                break
        plugin_suffix = ".dll" if sys.platform == "win32" else ".so"
        plugin, discovery = self._discover_native_plugin(
            Path.cwd(), plugin_suffix, server_executable or Path(sys.executable)
        )
        if plugin is not None:
            report["plugin_sha256"] = file_sha256(plugin)
            discovery["sha256"] = report["plugin_sha256"]
        append_invocation(
            report,
            "plugin_discovery",
            {"pattern": discovery["pattern"]},
            discovery,
        )
        if discovery["status"] == "not_found":
            sender.send_message(
                "No native Sign API plugin binary was found; plugin_sha256 remains empty. "
                f"Expected {discovery['pattern']}."
            )
        elif discovery["status"] == "ambiguous":
            sender.send_message(
                "Multiple native Sign API plugin binaries were found; plugin_sha256 remains "
                "empty until exactly one candidate remains: "
                + ", ".join(discovery["candidates"])
            )
        save_report(self._path(), report)
        sender.send_message(
            f"Stage report started for {dimension} ({x}, {y}, {z}): {self._path()}"
        )
        return True

    def _handle_capture(self, sender: CommandSender, args: list[str]) -> bool:
        report = self._load(sender)
        if report is None:
            return True
        response = self._capture(sender, report)
        if response is not None:
            self._send_json(sender, "Capture", response)
        return True

    def _handle_text(self, sender: CommandSender, args: list[str]) -> bool:
        if len(args) < 2 or args[0].casefold() not in {"front", "back"}:
            sender.send_message("Usage: /signprobe text <front|back> line1|line2|line3|line4")
            return True
        report = self._load(sender)
        if report is None:
            return True
        lines = self._parse_lines(" ".join(args[1:]))
        response = self._set_text(sender, report, side=args[0].casefold(), lines=lines)
        if response is not None:
            self._send_json(sender, "Set text", response)
        return True

    def _handle_glow(self, sender: CommandSender, args: list[str]) -> bool:
        if len(args) != 2 or args[0].casefold() not in {"front", "back"}:
            sender.send_message("Usage: /signprobe glow <front|back> <true|false>")
            return True
        enabled = args[1].casefold()
        if enabled not in {"true", "false"}:
            sender.send_message("enabled must be true or false")
            return True
        report = self._load(sender)
        if report is None:
            return True
        snapshot = self._capture(sender, report, record=False)
        if not snapshot or not snapshot.get("found"):
            sender.send_message("Capture the target sign before changing glow.")
            return True
        side = args[0].casefold()
        response = self._set_text(
            sender, report, side=side, lines=self._lines(snapshot, side),
            glowing=enabled == "true",
        )
        if response is not None:
            self._send_json(sender, "Set glow", response)
        return True

    def _handle_wax(self, sender: CommandSender, args: list[str]) -> bool:
        if len(args) != 1 or args[0].casefold() not in {"true", "false"}:
            sender.send_message("Usage: /signprobe wax <true|false>")
            return True
        report = self._load(sender)
        if report is None:
            return True
        snapshot = self._capture(sender, report, record=False)
        if not snapshot or not snapshot.get("found"):
            sender.send_message("Capture the target sign before changing wax.")
            return True
        response = self._set_text(
            sender,
            report,
            side="front",
            lines=self._lines(snapshot, "front"),
            waxed=args[0].casefold() == "true",
        )
        if response is not None:
            self._send_json(sender, "Set wax", response)
        return True

    def _handle_color(self, sender: CommandSender, args: list[str]) -> bool:
        if len(args) != 2 or args[0].casefold() not in {"front", "back"}:
            sender.send_message("Usage: /signprobe color <front|back> <0xAARRGGBB>")
            return True
        try:
            argb = int(args[1], 0)
            if not 0 <= argb <= 0xFFFFFFFF:
                raise ValueError
        except ValueError:
            sender.send_message("ARGB must be an integer from 0 through 0xFFFFFFFF.")
            return True
        report = self._load(sender)
        if report is None:
            return True
        snapshot = self._capture(sender, report, record=False)
        if not snapshot or not snapshot.get("found"):
            sender.send_message("Capture the target sign before changing color.")
            return True
        side = args[0].casefold()
        response = self._set_text(
            sender, report, side=side, lines=self._lines(snapshot, side), argb=argb
        )
        if response is not None:
            self._send_json(sender, "Set color", response)
        return True

    def _handle_editor(self, sender: CommandSender, args: list[str]) -> bool:
        if len(args) != 1 or args[0].casefold() not in {"front", "back"}:
            sender.send_message("Usage: /signprobe editor <front|back>")
            return True
        report = self._load(sender)
        bridge = self._bridge(sender)
        if report is None or bridge is None:
            return True
        dimension, x, y, z = self._target(report)
        side = args[0].casefold()
        request = {"dimension": dimension, "x": x, "y": y, "z": z, "side": side}
        try:
            response = dict(bridge.open_editor(self.server, sender, dimension, x, y, z, side))
        except Exception as error:
            response = {"ok": False, "status": "exception", "message": str(error)}
        self._save_invocation(report, "open_editor", request, response)
        self._send_json(sender, "Open editor", response)
        return True

    def _handle_remove(self, sender: CommandSender, args: list[str]) -> bool:
        if args != ["confirm"]:
            sender.send_message("Usage: /signprobe remove confirm")
            return True
        report = self._load(sender)
        bridge = self._bridge(sender)
        if report is None or bridge is None:
            return True
        dimension, x, y, z = self._target(report)
        request = {"dimension": dimension, "x": x, "y": y, "z": z, "force": False}
        try:
            response = dict(bridge.remove(self.server, dimension, x, y, z, False))
        except Exception as error:
            response = {"ok": False, "status": "exception", "message": str(error)}
        self._save_invocation(report, "remove", request, response)
        self._send_json(sender, "Remove", response)
        return True

    def _handle_record(self, sender: CommandSender, args: list[str]) -> bool:
        if len(args) < 3:
            sender.send_message("Usage: /signprobe record <probe> <true|false> <evidence>")
            return True
        probe, raw_passed = args[0], args[1].casefold()
        if probe not in PROBE_NAMES:
            sender.send_message(f"Unknown probe. Valid names: {', '.join(PROBE_NAMES)}")
            return True
        if raw_passed not in {"true", "false"}:
            sender.send_message("passed must be true or false")
            return True
        report = self._load(sender)
        if report is None:
            return True
        record_result(report, probe, raw_passed == "true", " ".join(args[2:]))
        save_report(self._path(), report)
        sender.send_message(f"Recorded {probe}: passed={raw_passed}")
        return True

    def _handle_meta(self, sender: CommandSender, args: list[str]) -> bool:
        if len(args) < 2 or args[0] not in EDITABLE_METADATA:
            sender.send_message(f"Editable metadata: {', '.join(sorted(EDITABLE_METADATA))}")
            return True
        report = self._load(sender)
        if report is None:
            return True
        set_metadata(report, args[0], " ".join(args[1:]))
        save_report(self._path(), report)
        sender.send_message(f"Updated report metadata: {args[0]}")
        return True

    def _handle_finish(self, sender: CommandSender, args: list[str]) -> bool:
        report = self._load(sender)
        if report is None:
            return True
        failures = finish_report(report)
        save_report(self._path(), report)
        if failures:
            preview = ", ".join(failures[:12])
            suffix = f" (+{len(failures) - 12} more)" if len(failures) > 12 else ""
            sender.send_message(f"Report remains incomplete: {preview}{suffix}")
        else:
            sender.send_message(f"Stage report complete and ready to return: {self._path()}")
        return True

    def _handle_path(self, sender: CommandSender, args: list[str]) -> bool:
        sender.send_message(f"Stage report path: {self._path()}")
        return True
