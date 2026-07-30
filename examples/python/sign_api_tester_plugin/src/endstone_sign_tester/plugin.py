"""Endstone commands for exercising the exact native Sign API and recording evidence."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from endstone.command import Command, CommandSender
from endstone.plugin import Plugin

from ._bridge_loader import import_live_bridge
from .automation import (
    add_step as add_matrix_step,
    build_cases as build_matrix_cases,
    config_sha256 as matrix_config_sha256,
    finish_run as finish_matrix_run,
    install_default_config,
    latest_report_path as latest_matrix_report_path,
    load_config as load_matrix_config,
    load_latest_report as load_latest_matrix_report,
    new_run_report,
    refresh_summary as refresh_matrix_summary,
    refresh_coverage as refresh_matrix_coverage,
    save_run_report,
    utc_now as matrix_utc_now,
    validate_config as validate_matrix_config,
)
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
    version = "0.2.0a6"
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
                (
                    "/signprobe (run)<action: SignProbeRunAction> "
                    "<x: int> <y: int> <z: int> "
                    "(confirm)<confirmation: SignProbeRunConfirm>"
                ),
                "/signprobe (runstatus)<action: SignProbeRunStatusAction>",
                "/signprobe (cancel)<action: SignProbeCancelAction>",
                (
                    "/signprobe (cleanup)<action: SignProbeCleanupAction> "
                    "(confirm)<confirmation: SignProbeCleanupConfirm>"
                ),
                "/signprobe (config)<action: SignProbeConfigAction>",
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
        self.matrix_context: dict[str, Any] | None = None
        self.matrix_task: Any | None = None
        self.matrix_cancel_requested = False
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
        try:
            install_default_config(Path(self.data_folder))
            latest = latest_matrix_report_path(Path(self.data_folder))
            if latest.is_file():
                previous = load_latest_matrix_report(Path(self.data_folder))
                if previous.get("state") in {"planned", "running"}:
                    add_matrix_step(
                        previous,
                        None,
                        operation="startup_recovery",
                        status="failed",
                        reason=(
                            "the server or tester stopped during this run; no mutation was "
                            "replayed automatically"
                        ),
                    )
                    finish_matrix_run(previous, "interrupted")
                    save_run_report(Path(self.data_folder), previous)
                    self.logger.warning(
                        "An unfinished Sign matrix run was marked interrupted. Use "
                        "/signprobe cleanup confirm after reviewing its report."
                    )
                elif dict(previous.get("cleanup") or {}).get("state") == "running":
                    previous["cleanup"]["state"] = "interrupted"
                    previous["cleanup"]["completed_at_utc"] = matrix_utc_now()
                    save_run_report(Path(self.data_folder), previous)
                    self.logger.warning(
                        "An unfinished Sign matrix cleanup was marked interrupted. "
                        "Review the report before retrying /signprobe cleanup confirm."
                    )
        except Exception as error:
            self.logger.error(f"Could not initialize Sign matrix configuration: {error}")

    def on_disable(self) -> None:
        task = self.matrix_task
        if task is not None:
            try:
                task.cancel()
            except Exception:
                pass
        context = self.matrix_context
        if context is not None:
            report = context["report"]
            if context.get("mode") == "run" and report.get("state") == "running":
                add_matrix_step(
                    report,
                    None,
                    operation="plugin_disable",
                    status="failed",
                    reason="tester disabled while the run was active",
                )
                finish_matrix_run(report, "interrupted")
            elif context.get("mode") == "cleanup":
                report["cleanup"]["state"] = "interrupted"
                report["cleanup"]["completed_at_utc"] = matrix_utc_now()
            try:
                save_run_report(Path(self.data_folder), report)
            except Exception:
                pass
        self.matrix_task = None
        self.matrix_context = None

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

    def _binary_evidence(self) -> dict[str, Any]:
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
        server_sha256 = ""
        for candidate in server_candidates:
            if candidate.is_file() and candidate.name.startswith("bedrock_server"):
                server_sha256 = file_sha256(candidate)
                server_executable = candidate
                break
        plugin_suffix = ".dll" if sys.platform == "win32" else ".so"
        plugin, discovery = self._discover_native_plugin(
            Path.cwd(), plugin_suffix, server_executable or Path(sys.executable)
        )
        plugin_sha256 = ""
        if plugin is not None:
            plugin_sha256 = file_sha256(plugin)
            discovery["sha256"] = plugin_sha256
        return {
            "server_executable_sha256": server_sha256,
            "plugin_sha256": plugin_sha256,
            "plugin_discovery": discovery,
        }

    @staticmethod
    def _mutation_preflight(
        bridge: Any,
        server: Any,
        operation: str,
        required_capabilities: tuple[str, ...] | list[str],
    ) -> tuple[bool, str, dict[str, Any]]:
        try:
            status = dict(bridge.status(server))
        except Exception as error:
            return (
                False,
                f"could not verify native Sign API {operation} capabilities; "
                f"mutation was not attempted: {error}",
                {},
            )
        try:
            capabilities = dict(status.get("capabilities") or {})
        except (TypeError, ValueError):
            capabilities = {}
        required = (
            "exact_build_match",
            "exact_binary_hash_match",
            "capture",
            "client_updates",
            *tuple(required_capabilities),
        )
        missing = [name for name in dict.fromkeys(required) if capabilities.get(name) is not True]
        if status.get("available") is not True:
            missing.insert(0, "available")
        if missing:
            adapter = str(status.get("adapter") or "unknown")
            return (
                False,
                f"native Sign API {operation} gate is closed for adapter {adapter!r}; "
                f"missing {', '.join(missing)}; mutation was not attempted",
                status,
            )
        return True, "", status

    @staticmethod
    def _write_text_preflight(bridge: Any, server: Any) -> tuple[bool, str]:
        ready, message, _ = SignApiTesterPlugin._mutation_preflight(
            bridge,
            server,
            "write_text",
            ("read_text", "write_text", "front_and_back"),
        )
        return ready, message

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
        feature_caps: list[str] = []
        if argb is not None:
            feature_caps.append("text_color")
        if glowing is not None:
            feature_caps.append("glowing")
        if waxed is not None:
            feature_caps.append("waxed")
        if write_text_ready and feature_caps:
            write_text_ready, preflight_message, _ = self._mutation_preflight(
                bridge,
                self.server,
                "set_text advanced fields",
                ("read_text", "write_text", "front_and_back", *feature_caps),
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
        before = self._capture(sender, report, record=False)
        expected_revision = (
            int(before["revision"])
            if before and before.get("found") and before.get("revision") is not None
            else 0
        )
        request["expected_revision"] = expected_revision
        if expected_revision <= 0:
            response = {
                "ok": False,
                "status": "conflict",
                "message": (
                    "set_text requires a successful capture with a nonzero revision; "
                    "no mutation was attempted"
                ),
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
                    expected_revision,
                )
            )
            response.setdefault("mutation_attempted", True)
        except Exception as error:
            response = {
                "ok": False,
                "status": "exception",
                "message": str(error),
                "mutation_attempted": True,
            }
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
        sender.send_message(
            "/signprobe run <x> <y> <z> confirm - automated 12-material x 4-form matrix"
        )
        sender.send_message(
            "/signprobe runstatus; /signprobe cancel; /signprobe cleanup confirm; "
            "/signprobe config"
        )
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
        binary_evidence = self._binary_evidence()
        report["server_executable_sha256"] = binary_evidence[
            "server_executable_sha256"
        ]
        report["plugin_sha256"] = binary_evidence["plugin_sha256"]
        discovery = binary_evidence["plugin_discovery"]
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
        request = {
            "dimension": dimension,
            "x": x,
            "y": y,
            "z": z,
            "side": side,
            "acquire_lock": False,
            "bypass_wax": True,
        }
        ready, message, _ = self._mutation_preflight(
            bridge, self.server, "open_editor", ("open_editor",)
        )
        if not ready:
            response = {
                "ok": False,
                "status": "unsupported",
                "message": message,
                "revision": 0,
                "mutation_attempted": False,
            }
            self._save_invocation(report, "open_editor", request, response)
            self._send_json(sender, "Open editor", response)
            return True
        try:
            response = dict(
                bridge.open_editor(
                    self.server,
                    sender,
                    dimension,
                    x,
                    y,
                    z,
                    side,
                    False,
                    True,
                )
            )
            response.setdefault("mutation_attempted", True)
        except Exception as error:
            response = {
                "ok": False,
                "status": "exception",
                "message": str(error),
                "mutation_attempted": True,
            }
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
        ready, message, _ = self._mutation_preflight(
            bridge, self.server, "remove", ("remove",)
        )
        if not ready:
            response = {
                "ok": False,
                "status": "unsupported",
                "message": message,
                "revision": 0,
                "mutation_attempted": False,
            }
            self._save_invocation(report, "remove", request, response)
            self._send_json(sender, "Remove", response)
            return True
        before = self._capture(sender, report, record=False)
        expected_revision = (
            int(before["revision"])
            if before and before.get("found") and before.get("revision") is not None
            else None
        )
        request["expected_revision"] = expected_revision
        if expected_revision is None or expected_revision <= 0:
            response = {
                "ok": False,
                "status": "conflict",
                "message": (
                    "remove requires a successful capture with a nonzero revision; "
                    "no mutation was attempted"
                ),
                "revision": 0,
                "mutation_attempted": False,
            }
            self._save_invocation(report, "remove", request, response)
            self._send_json(sender, "Remove", response)
            return True
        try:
            response = dict(
                bridge.remove(
                    self.server, dimension, x, y, z, False, expected_revision
                )
            )
            response.setdefault("mutation_attempted", True)
        except Exception as error:
            response = {
                "ok": False,
                "status": "exception",
                "message": str(error),
                "mutation_attempted": True,
            }
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
        sender.send_message(
            f"Latest matrix report path: {latest_matrix_report_path(Path(self.data_folder))}"
        )
        return True

    def _handle_config(self, sender: CommandSender, args: list[str]) -> bool:
        path = install_default_config(Path(self.data_folder))
        try:
            config = load_matrix_config(path)
        except Exception as error:
            sender.send_message(f"Matrix config is invalid: {error}")
            sender.send_message(f"Matrix config path: {path}")
            return True
        count = len(config["materials"]) * len(config["kinds"])
        sender.send_message(
            f"Matrix config is valid ({count} cases, delay={config['delay_ticks']} ticks): "
            f"{path}"
        )
        return True

    @staticmethod
    def _matrix_descriptor_preflight(
        server: Any, config: dict[str, Any], cases: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Resolve every exact block descriptor before the first world write.

        Endstone translates descriptor errors safely when create_block_data is
        invoked through its own Python binding.  The native Sign plugin cannot
        safely receive an exception thrown by the separately linked Endstone
        runtime, so no identifier/state pair may reach that boundary unless the
        running server has already resolved it exactly here.
        """

        failures: list[dict[str, Any]] = []
        for role, identifier in (
            ("support", config["support_block"]),
            ("cleanup", "minecraft:air"),
        ):
            try:
                descriptor = server.create_block_data(identifier)
                if descriptor is not None and str(descriptor.type) == identifier:
                    continue
                failures.append(
                    {
                        "role": role,
                        "identifier": identifier,
                        "reason": "Endstone did not resolve the exact fixture block type",
                    }
                )
            except Exception as error:
                failures.append(
                    {
                        "role": role,
                        "identifier": identifier,
                        "reason": str(error),
                    }
                )

        for case in cases:
            identifier = str(case["identifier"])
            requested_states = dict(case["states"])
            try:
                descriptor = server.create_block_data(identifier, requested_states)
                if descriptor is None:
                    raise ValueError("Endstone returned no block descriptor")
                actual_type = str(descriptor.type)
                actual_states = dict(descriptor.block_states)
                mismatched_states = {
                    key: {"expected": expected, "actual": actual_states.get(key)}
                    for key, expected in requested_states.items()
                    if key not in actual_states
                    or type(actual_states[key]) is not type(expected)
                    or actual_states[key] != expected
                }
                if actual_type != identifier or mismatched_states:
                    failures.append(
                        {
                            "case_id": case["id"],
                            "role": "sign",
                            "identifier": identifier,
                            "reason": "exact block descriptor readback mismatch",
                            "actual_type": actual_type,
                            "mismatched_states": mismatched_states,
                        }
                    )
            except Exception as error:
                failures.append(
                    {
                        "case_id": case["id"],
                        "role": "sign",
                        "identifier": identifier,
                        "states": requested_states,
                        "reason": str(error),
                    }
                )
        return failures

    def _handle_run(self, sender: CommandSender, args: list[str]) -> bool:
        if len(args) != 4 or args[3].casefold() != "confirm":
            sender.send_message("Usage: /signprobe run <x> <y> <z> confirm")
            return True
        if self.matrix_context is not None:
            sender.send_message("A Sign matrix run or cleanup is already active.")
            return True
        dimension_name = self._dimension(sender)
        if dimension_name is None:
            sender.send_message("Run the automated matrix as a player in the target dimension.")
            return True
        try:
            anchor = {"x": int(args[0]), "y": int(args[1]), "z": int(args[2])}
        except ValueError:
            sender.send_message("Matrix anchor coordinates must be integers.")
            return True
        bridge = self._bridge(sender)
        if bridge is None:
            return True
        try:
            config_file = install_default_config(Path(self.data_folder))
            config = load_matrix_config(config_file)
            bridge_status = dict(bridge.status(self.server))
            report = new_run_report(
                plugin_version=self.version,
                platform=self._platform(),
                operator=self._sender_name(sender),
                dimension=dimension_name,
                anchor=anchor,
                config=config,
                bridge_status=bridge_status,
            )
            report.update(self._binary_evidence())
            report["world_name"] = str(self.server.level.name)
            report["world_seed"] = str(self.server.level.seed)
        except Exception as error:
            sender.send_message(f"Could not plan the Sign matrix: {error}")
            return True

        identity_complete = (
            len(str(report.get("server_executable_sha256") or "")) == 64
            and len(str(report.get("plugin_sha256") or "")) == 64
            and dict(report.get("plugin_discovery") or {}).get("status") == "selected"
            and bool(str(report.get("world_name") or ""))
            and bool(str(report.get("world_seed") or ""))
        )
        add_matrix_step(
            report,
            None,
            operation="binary_evidence",
            status="passed" if identity_complete else "failed",
            response={
                "server_executable_sha256": report["server_executable_sha256"],
                "plugin_sha256": report["plugin_sha256"],
                "plugin_discovery": report["plugin_discovery"],
                "world_name": report["world_name"],
                "world_seed": report["world_seed"],
            },
            reason=(
                "server/plugin SHA-256 and world seed were recorded"
                if identity_complete
                else "server/plugin identity evidence is incomplete; no mutation was attempted"
            ),
        )
        if not identity_complete:
            finish_matrix_run(report, "failed")
            path = save_run_report(Path(self.data_folder), report)
            sender.send_message(
                "Matrix stopped before mutation because server/plugin identity evidence "
                "was incomplete. Remove duplicate plugins or fix the server plugin path."
            )
            sender.send_message(f"Matrix report: {path}")
            return True

        ready, reason, current_status = self._mutation_preflight(
            bridge,
            self.server,
            "automated matrix",
            ("place", "read_text", "write_text", "front_and_back", "per_line_write"),
        )
        if current_status:
            report["bridge_status"] = current_status
        add_matrix_step(
            report,
            None,
            operation="capability_preflight",
            status="passed" if ready else "failed",
            required_capabilities=[
                "exact_build_match",
                "exact_binary_hash_match",
                "capture",
                "client_updates",
                "place",
                "read_text",
                "write_text",
                "front_and_back",
                "per_line_write",
            ],
            reason=reason,
        )
        if not ready:
            finish_matrix_run(report, "failed")
            path = save_run_report(Path(self.data_folder), report)
            sender.send_message(f"Matrix stopped before mutation: {reason}")
            sender.send_message(f"Matrix report: {path}")
            return True

        descriptor_failures = self._matrix_descriptor_preflight(
            self.server, config, report["cases"]
        )
        add_matrix_step(
            report,
            None,
            operation="block_descriptor_preflight",
            status="failed" if descriptor_failures else "passed",
            response={"failures": descriptor_failures},
            reason=(
                "every exact support/sign identifier and state map resolved through "
                "Endstone before mutation"
                if not descriptor_failures
                else "one or more block descriptors were rejected before mutation"
            ),
        )
        if descriptor_failures:
            finish_matrix_run(report, "failed")
            path = save_run_report(Path(self.data_folder), report)
            sender.send_message(
                "Matrix stopped before mutation: "
                f"{len(descriptor_failures)} block descriptor failure(s)."
            )
            sender.send_message(f"Matrix report: {path}")
            return True

        conflicts: list[dict[str, Any]] = []
        try:
            dimension = self.server.level.get_dimension(dimension_name)
            for case in report["cases"]:
                for role in ("sign", "support"):
                    location = case[role]
                    block = dimension.get_block_at(
                        location["x"], location["y"], location["z"]
                    )
                    if str(block.type) != "minecraft:air":
                        conflicts.append(
                            {
                                "case_id": case["id"],
                                "role": role,
                                "location": dict(location),
                                "type": str(block.type),
                            }
                        )
        except Exception as error:
            conflicts.append({"error": str(error)})
        add_matrix_step(
            report,
            None,
            operation="arena_air_preflight",
            status="failed" if conflicts else "passed",
            response={"conflicts": conflicts},
            reason=(
                "every planned sign and support cell must be air; no block was changed"
                if conflicts
                else "all planned sign and support cells are air"
            ),
        )
        if conflicts:
            finish_matrix_run(report, "failed")
            path = save_run_report(Path(self.data_folder), report)
            sender.send_message(
                f"Matrix stopped before mutation: {len(conflicts)} arena cell conflict(s)."
            )
            sender.send_message(f"Matrix report: {path}")
            return True

        report["state"] = "running"
        report["cursor"] = {"case_index": 0, "phase": "support"}
        path = save_run_report(Path(self.data_folder), report)
        self.matrix_context = {
            "mode": "run",
            "report": report,
            "bridge": bridge,
            "sender_name": self._sender_name(sender),
        }
        self.matrix_cancel_requested = False
        try:
            self._schedule_matrix(config["delay_ticks"])
        except Exception as error:
            add_matrix_step(
                report,
                None,
                operation="scheduler_start",
                status="failed",
                reason=f"could not schedule the first matrix tick: {error}",
            )
            finish_matrix_run(report, "failed")
            path = save_run_report(Path(self.data_folder), report)
            self.matrix_context = None
            self.matrix_task = None
            sender.send_message(
                f"Matrix did not start because scheduling failed. Report: {path}"
            )
            return True
        sender.send_message(
            f"Started {len(report['cases'])}-case Sign matrix. One operation runs per "
            f"scheduled tick; report: {path}"
        )
        return True

    def _handle_runstatus(self, sender: CommandSender, args: list[str]) -> bool:
        context = self.matrix_context
        if context is not None:
            report = context["report"]
            cursor = report.get("cursor", {})
            sender.send_message(
                f"Matrix {context['mode']} active: state={report.get('state')}, "
                f"case={int(cursor.get('case_index', 0)) + 1}/{len(report.get('cases', []))}, "
                f"phase={cursor.get('phase', 'unknown')}"
            )
            self._send_json(sender, "Matrix summary", report.get("summary", {}))
            return True
        path = latest_matrix_report_path(Path(self.data_folder))
        if not path.is_file():
            sender.send_message("No automated Sign matrix report exists yet.")
            return True
        try:
            report = load_latest_matrix_report(Path(self.data_folder))
        except Exception as error:
            sender.send_message(str(error))
            return True
        sender.send_message(
            f"Latest matrix: state={report.get('state')}, outcome={report.get('outcome')}, "
            f"cleanup={dict(report.get('cleanup') or {}).get('state', 'unknown')}"
        )
        self._send_json(sender, "Matrix summary", report.get("summary", {}))
        sender.send_message(f"Matrix report: {path}")
        return True

    def _handle_cancel(self, sender: CommandSender, args: list[str]) -> bool:
        if self.matrix_context is None:
            sender.send_message("No Sign matrix run or cleanup is active.")
            return True
        self.matrix_cancel_requested = True
        sender.send_message(
            "Cancellation requested. The runner will stop at the next operation boundary."
        )
        return True

    def _validate_cleanup_report(
        self, sender: CommandSender, report: dict[str, Any]
    ) -> str:
        if report.get("plugin_version") != self.version:
            return "report plugin version does not match this tester"
        if report.get("platform") != self._platform():
            return "report platform does not match this server"
        if report.get("state") not in {"completed", "failed", "cancelled", "interrupted"}:
            return "the matrix run is not in a terminal state"
        dimension_name = report.get("dimension")
        if not isinstance(dimension_name, str) or not dimension_name:
            return "report dimension is invalid"
        if self._dimension(sender) != dimension_name:
            return "run cleanup as a player in the report's target dimension"
        if str(report.get("world_name") or "") != str(self.server.level.name):
            return "report world name does not match the loaded world"
        if str(report.get("world_seed") or "") != str(self.server.level.seed):
            return "report world seed does not match the loaded world"

        try:
            report_config = validate_matrix_config(dict(report.get("config") or {}))
            current_config = load_matrix_config(
                install_default_config(Path(self.data_folder))
            )
        except Exception as error:
            return f"matrix configuration could not be validated: {error}"
        report_hash = matrix_config_sha256(report_config)
        if report_hash != str(report.get("config_sha256") or ""):
            return "report configuration hash is invalid"
        if report_hash != matrix_config_sha256(current_config):
            return "matrix-config.toml changed after this run"

        anchor = report.get("anchor")
        if (
            not isinstance(anchor, dict)
            or set(anchor) != {"x", "y", "z"}
            or any(type(anchor[axis]) is not int for axis in ("x", "y", "z"))
        ):
            return "report anchor is invalid"
        try:
            planned = build_matrix_cases(report_config, dimension_name, anchor)
        except Exception as error:
            return f"report plan could not be reconstructed: {error}"
        cases = report.get("cases")
        if not isinstance(cases, list) or len(cases) != len(planned):
            return "report case count does not match the reconstructed plan"
        immutable_fields = (
            "id",
            "index",
            "material",
            "kind",
            "dimension",
            "sign",
            "support",
            "identifier",
            "states",
            "front_lines",
            "back_lines",
            "edited_front_lines",
        )
        for saved, expected in zip(cases, planned, strict=True):
            if not isinstance(saved, dict) or any(
                saved.get(field) != expected.get(field) for field in immutable_fields
            ):
                return "report case plan differs from the reconstructed plan"
            if type(saved.get("owned_sign")) is not bool or type(
                saved.get("owned_support")
            ) is not bool:
                return "report ownership flags are invalid"
            for field in ("placement_revision", "expected_revision"):
                revision = saved.get(field)
                if type(revision) is not int or not 0 <= revision <= 0xFFFFFFFFFFFFFFFF:
                    return f"report {field} is invalid"

        current_evidence = self._binary_evidence()
        if (
            len(str(report.get("server_executable_sha256") or "")) != 64
            or len(str(report.get("plugin_sha256") or "")) != 64
            or dict(report.get("plugin_discovery") or {}).get("status") != "selected"
            or str(report.get("server_executable_sha256") or "")
            != str(current_evidence.get("server_executable_sha256") or "")
            or str(report.get("plugin_sha256") or "")
            != str(current_evidence.get("plugin_sha256") or "")
            or dict(current_evidence.get("plugin_discovery") or {}).get("status")
            != "selected"
        ):
            return "server/plugin binary identity differs from the recorded run"
        return ""

    def _handle_cleanup(self, sender: CommandSender, args: list[str]) -> bool:
        if args != ["confirm"]:
            sender.send_message("Usage: /signprobe cleanup confirm")
            return True
        if self.matrix_context is not None:
            sender.send_message("Cancel or finish the active Sign matrix operation first.")
            return True
        bridge = self._bridge(sender)
        if bridge is None:
            return True
        try:
            report = load_latest_matrix_report(Path(self.data_folder))
        except Exception as error:
            sender.send_message(str(error))
            return True
        validation_error = self._validate_cleanup_report(sender, report)
        if validation_error:
            sender.send_message(
                f"Cleanup was not started because ownership evidence is invalid: "
                f"{validation_error}. No block was changed."
            )
            return True
        ready, reason, _ = self._mutation_preflight(
            bridge, self.server, "matrix cleanup", ("remove",)
        )
        if not ready:
            sender.send_message(f"Cleanup was not started: {reason}")
            return True
        report["cleanup"] = {
            "state": "running",
            "conflicts": [],
            "completed_at_utc": "",
        }
        report["cursor"] = {"case_index": 0, "phase": "cleanup"}
        save_run_report(Path(self.data_folder), report)
        self.matrix_context = {
            "mode": "cleanup",
            "report": report,
            "bridge": bridge,
            "sender_name": self._sender_name(sender),
        }
        self.matrix_cancel_requested = False
        try:
            self._schedule_matrix(int(report["config"]["delay_ticks"]))
        except Exception as error:
            add_matrix_step(
                report,
                None,
                operation="cleanup_scheduler_start",
                status="failed",
                reason=f"could not schedule the first cleanup tick: {error}",
            )
            report["cleanup"]["state"] = "failed"
            report["cleanup"]["completed_at_utc"] = matrix_utc_now()
            path = save_run_report(Path(self.data_folder), report)
            self.matrix_context = None
            self.matrix_task = None
            sender.send_message(
                f"Cleanup did not start because scheduling failed. Report: {path}"
            )
            return True
        sender.send_message(
            "Ownership-aware cleanup started. Changed or revision-conflicting cells will "
            "be preserved and reported."
        )
        return True

    def _schedule_matrix(self, delay: int) -> None:
        self.matrix_task = self.server.scheduler.run_task(
            self, self._matrix_tick, delay=max(1, int(delay))
        )

    def _matrix_message(self, message: str) -> None:
        context = self.matrix_context
        if context is not None:
            try:
                player = self.server.get_player(str(context["sender_name"]))
                if player is not None:
                    player.send_message(message)
            except Exception:
                pass
        self.logger.info(message)

    def _matrix_terminal(self, state: str, message: str) -> None:
        context = self.matrix_context
        if context is None:
            return
        report = context["report"]
        sender_name = str(context.get("sender_name") or "")
        if context["mode"] == "run":
            finish_matrix_run(report, state)
        else:
            report["cleanup"]["state"] = state
            report["cleanup"]["completed_at_utc"] = matrix_utc_now()
        path = save_run_report(Path(self.data_folder), report)
        self.matrix_task = None
        self.matrix_context = None
        self.matrix_cancel_requested = False
        rendered = f"{message} Report: {path}"
        try:
            player = self.server.get_player(sender_name)
            if player is not None:
                player.send_message(rendered)
        except Exception:
            pass
        self.logger.info(rendered)

    def _matrix_tick(self) -> None:
        self.matrix_task = None
        context = self.matrix_context
        if context is None:
            return
        report = context["report"]
        if self.matrix_cancel_requested:
            if context["mode"] == "run":
                add_matrix_step(
                    report,
                    None,
                    operation="cancel",
                    status="cancelled",
                    reason="operator requested cancellation at an operation boundary",
                )
                self._matrix_terminal("cancelled", "Sign matrix cancelled.")
            else:
                report["cleanup"]["state"] = "cancelled"
                self._matrix_terminal("cancelled", "Sign matrix cleanup cancelled.")
            return
        try:
            if context["mode"] == "cleanup":
                self._matrix_cleanup_tick(context)
            else:
                self._matrix_run_tick(context)
        except Exception as error:
            add_matrix_step(
                report,
                None,
                operation="runner_exception",
                status="failed",
                reason=str(error),
            )
            self.logger.error(f"Automated Sign matrix failed safely: {error}")
            self._matrix_terminal("failed", "Sign matrix stopped after an exception.")

    @staticmethod
    def _matrix_snapshot_matches(snapshot: dict[str, Any], case: dict[str, Any]) -> bool:
        if snapshot.get("found") is not True:
            return False
        if snapshot.get("block_identifier") != case["identifier"]:
            return False
        if snapshot.get("kind") != case["kind"]:
            return False
        states = dict(snapshot.get("states") or {})
        return all(states.get(key) == value for key, value in case["states"].items())

    @staticmethod
    def _matrix_capture(context: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
        sign = case["sign"]
        try:
            return dict(
                context["bridge"].capture(
                    context["plugin"].server,
                    case["dimension"],
                    sign["x"],
                    sign["y"],
                    sign["z"],
                )
            )
        except Exception as error:
            return {"found": False, "error": str(error)}

    def _matrix_set_cursor(
        self, context: dict[str, Any], case_index: int, phase: str
    ) -> None:
        report = context["report"]
        report["cursor"] = {"case_index": case_index, "phase": phase}
        # Full JSON serialization runs on the BDS primary thread. Checkpoint
        # immediately after every mutation/ownership transition and at case
        # boundaries; read-only phases are compacted into the next checkpoint.
        checkpoint_phases = {
            "support",
            "place",
            "capture_place",
            "front",
            "back",
            "line_edit",
            "color",
            "glow",
            "wax",
            "unwax",
            "capture_front",
            "capture_back",
            "capture_line_edit",
            "capture_color",
            "capture_glow",
            "capture_wax",
            "capture_unwax",
            "finish_case",
        }
        if phase in checkpoint_phases:
            save_run_report(Path(self.data_folder), report)
        self._schedule_matrix(int(report["config"]["delay_ticks"]))

    def _matrix_finish_case(
        self, context: dict[str, Any], case_index: int, case: dict[str, Any]
    ) -> None:
        if case.get("status") != "failed":
            case["status"] = "passed"
        report = context["report"]
        refresh_matrix_summary(report)
        if case["status"] == "failed" and report["config"]["stop_on_failure"]:
            self._matrix_finalize_inline_cleanup(report)
            self._matrix_terminal("failed", f"Sign matrix stopped at {case['id']}.")
            return
        next_index = case_index + 1
        if next_index >= len(report["cases"]):
            self._matrix_finalize_inline_cleanup(report)
            outcome = "completed" if not report["summary"]["cases_failed"] else "failed"
            self._matrix_terminal(
                "completed",
                f"Sign matrix {outcome}: {len(report['cases'])} cases processed.",
            )
            return
        self._matrix_set_cursor(context, next_index, "support")

    @staticmethod
    def _matrix_finalize_inline_cleanup(report: dict[str, Any]) -> None:
        if not bool(dict(report.get("config") or {}).get("cleanup_after_run")):
            return
        conflicts = list(dict(report.get("cleanup") or {}).get("conflicts") or [])
        report["cleanup"]["state"] = "conflicts" if conflicts else "completed"
        report["cleanup"]["completed_at_utc"] = matrix_utc_now()

    def _matrix_fail_case(
        self,
        report: dict[str, Any],
        case: dict[str, Any],
        *,
        operation: str,
        reason: str,
        mutation_attempted: bool = False,
        request: dict[str, Any] | None = None,
        response: Any = None,
        before: Any = None,
        after: Any = None,
        required_capabilities: tuple[str, ...] | list[str] = (),
    ) -> None:
        case["status"] = "failed"
        add_matrix_step(
            report,
            case,
            operation=operation,
            status="failed",
            required_capabilities=required_capabilities,
            mutation_attempted=mutation_attempted,
            request=request,
            response=response,
            before=before,
            after=after,
            reason=reason,
        )

    def _matrix_run_tick(self, context: dict[str, Any]) -> None:
        # The context stores no Player or Dimension object across ticks.
        context["plugin"] = self
        report = context["report"]
        cursor = report["cursor"]
        case_index = int(cursor["case_index"])
        phase = str(cursor["phase"])
        if case_index >= len(report["cases"]):
            self._matrix_terminal("completed", "Sign matrix completed.")
            return
        case = report["cases"][case_index]
        if phase == "support":
            self._matrix_phase_support(context, case_index, case)
        elif phase == "place":
            self._matrix_phase_place(context, case_index, case)
        elif phase == "capture_place":
            self._matrix_phase_capture_place(context, case_index, case)
        elif phase in {"front", "back", "line_edit"}:
            self._matrix_phase_text(context, case_index, case, phase)
        elif phase in {"capture_front", "capture_back", "capture_line_edit"}:
            self._matrix_phase_capture_text(context, case_index, case, phase)
        elif phase in {"color", "glow", "wax", "unwax"}:
            self._matrix_phase_advanced(context, case_index, case, phase)
        elif phase in {"capture_color", "capture_glow", "capture_wax", "capture_unwax"}:
            self._matrix_phase_capture_advanced(context, case_index, case, phase)
        elif phase == "cleanup":
            report["cleanup"]["state"] = "running"
            self._matrix_cleanup_case(context, case, standalone=False)
            self._matrix_set_cursor(context, case_index, "finish_case")
        elif phase == "finish_case":
            self._matrix_finish_case(context, case_index, case)
        else:
            raise ValueError(f"unknown matrix runner phase: {phase}")

    def _matrix_phase_support(
        self, context: dict[str, Any], case_index: int, case: dict[str, Any]
    ) -> None:
        report = context["report"]
        location = case["support"]
        dimension = self.server.level.get_dimension(case["dimension"])
        block = dimension.get_block_at(location["x"], location["y"], location["z"])
        before = {"type": str(block.type), "location": dict(location)}
        if before["type"] != "minecraft:air":
            self._matrix_fail_case(
                report,
                case,
                operation="create_support",
                reason="support cell changed after the air preflight; no mutation attempted",
                before=before,
            )
            next_phase = (
                "cleanup" if report["config"]["cleanup_after_run"] else "finish_case"
            )
            self._matrix_set_cursor(context, case_index, next_phase)
            return
        try:
            block.set_type(report["config"]["support_block"], False)
            after = {"type": str(block.type), "location": dict(location)}
            passed = after["type"] == report["config"]["support_block"]
        except Exception as error:
            after = {"error": str(error)}
            passed = False
        if passed:
            case["owned_support"] = True
            add_matrix_step(
                report,
                case,
                operation="create_support",
                status="passed",
                mutation_attempted=True,
                request={"type": report["config"]["support_block"], **location},
                before=before,
                after=after,
                reason="fixture support block created through Endstone's public block API",
            )
            self._matrix_set_cursor(context, case_index, "place")
            return
        self._matrix_fail_case(
            report,
            case,
            operation="create_support",
            reason="support block write did not read back as requested",
            mutation_attempted=True,
            before=before,
            after=after,
        )
        next_phase = "cleanup" if report["config"]["cleanup_after_run"] else "finish_case"
        self._matrix_set_cursor(context, case_index, next_phase)

    def _matrix_phase_place(
        self, context: dict[str, Any], case_index: int, case: dict[str, Any]
    ) -> None:
        report = context["report"]
        sign = case["sign"]
        terminal_phase = (
            "cleanup" if report["config"]["cleanup_after_run"] else "finish_case"
        )
        dimension = self.server.level.get_dimension(case["dimension"])
        before_type = str(
            dimension.get_block_at(sign["x"], sign["y"], sign["z"]).type
        )
        request = {
            "dimension": case["dimension"],
            **sign,
            "block_identifier": case["identifier"],
            "states": case["states"],
            "force": False,
        }
        if before_type != "minecraft:air":
            self._matrix_fail_case(
                report,
                case,
                operation="place_blank",
                reason="sign cell changed after the air preflight; no mutation attempted",
                request=request,
                before={"type": before_type},
                required_capabilities=("place",),
            )
            self._matrix_set_cursor(context, case_index, terminal_phase)
            return
        ready, reason, _ = self._mutation_preflight(
            context["bridge"], self.server, "place", ("place",)
        )
        if not ready:
            self._matrix_fail_case(
                report,
                case,
                operation="place_blank",
                reason=reason,
                request=request,
                required_capabilities=("place",),
            )
            self._matrix_set_cursor(context, case_index, terminal_phase)
            return
        try:
            response = dict(
                context["bridge"].place(
                    self.server,
                    case["dimension"],
                    sign["x"],
                    sign["y"],
                    sign["z"],
                    case["identifier"],
                    case["states"],
                )
            )
        except Exception as error:
            response = {"ok": False, "status": "exception", "message": str(error)}
        add_matrix_step(
            report,
            case,
            operation="place_blank",
            status="passed" if response.get("ok") is True else "failed",
            required_capabilities=("place",),
            mutation_attempted=True,
            request=request,
            response=response,
            before={"type": before_type},
            reason=str(response.get("message") or ""),
        )
        if response.get("ok") is not True:
            case["status"] = "failed"
            self._matrix_set_cursor(context, case_index, terminal_phase)
            return
        case["placement_revision"] = int(response.get("revision") or 0)
        self._matrix_set_cursor(context, case_index, "capture_place")

    def _matrix_phase_capture_place(
        self, context: dict[str, Any], case_index: int, case: dict[str, Any]
    ) -> None:
        report = context["report"]
        snapshot = self._matrix_capture(context, case)
        matches = self._matrix_snapshot_matches(snapshot, case)
        placement_revision = int(case.get("placement_revision") or 0)
        captured_revision = int(snapshot.get("revision") or 0)
        if matches and placement_revision > 0 and captured_revision == placement_revision:
            case["owned_sign"] = True
            case["expected_revision"] = captured_revision
            add_matrix_step(
                report,
                case,
                operation="capture_placed",
                status="passed",
                required_capabilities=("capture",),
                response=snapshot,
                reason="identifier, kind, canonical requested states, and revision read back",
            )
            if snapshot.get("actor_status") != "experimental_text_captured":
                self._matrix_fail_case(
                    report,
                    case,
                    operation="text_actor_preflight",
                    reason=(
                        "placed sign did not expose the exact experimental text actor; "
                        "text mutation was not attempted"
                    ),
                    after=snapshot,
                    required_capabilities=("read_text", "write_text"),
                )
                next_phase = (
                    "cleanup" if report["config"]["cleanup_after_run"] else "finish_case"
                )
                self._matrix_set_cursor(context, case_index, next_phase)
                return
            self._matrix_set_cursor(context, case_index, "front")
            return
        self._matrix_fail_case(
            report,
            case,
            operation="capture_placed",
            reason=(
                "placed sign did not read back with the expected identifier/kind/states "
                "and exact placement revision; ownership was not claimed"
            ),
            response=snapshot,
            required_capabilities=("capture",),
        )
        next_phase = "cleanup" if report["config"]["cleanup_after_run"] else "finish_case"
        self._matrix_set_cursor(context, case_index, next_phase)

    def _matrix_phase_text(
        self,
        context: dict[str, Any],
        case_index: int,
        case: dict[str, Any],
        phase: str,
    ) -> None:
        report = context["report"]
        sign = case["sign"]
        terminal_phase = (
            "cleanup" if report["config"]["cleanup_after_run"] else "finish_case"
        )
        if phase == "front":
            side, lines, next_phase = "front", case["front_lines"], "capture_front"
            required = ("read_text", "write_text", "front_and_back")
        elif phase == "back":
            side, lines, next_phase = "back", case["back_lines"], "capture_back"
            required = ("read_text", "write_text", "front_and_back")
        else:
            side, lines, next_phase = (
                "front",
                case["edited_front_lines"],
                "capture_line_edit",
            )
            required = (
                "read_text",
                "write_text",
                "front_and_back",
                "per_line_write",
            )
        ready, reason, _ = self._mutation_preflight(
            context["bridge"], self.server, phase, required
        )
        request = {
            "dimension": case["dimension"],
            **sign,
            "side": side,
            "lines": lines,
            "expected_revision": int(case.get("expected_revision") or 0),
        }
        if not ready:
            self._matrix_fail_case(
                report,
                case,
                operation=phase,
                reason=reason,
                request=request,
                required_capabilities=required,
            )
            self._matrix_set_cursor(context, case_index, terminal_phase)
            return
        expected_revision = int(case.get("expected_revision") or 0)
        if expected_revision <= 0:
            self._matrix_fail_case(
                report,
                case,
                operation=phase,
                reason="owned sign has no nonzero expected revision; no mutation attempted",
                request=request,
                required_capabilities=required,
            )
            self._matrix_set_cursor(context, case_index, terminal_phase)
            return
        try:
            response = dict(
                context["bridge"].set_text(
                    self.server,
                    case["dimension"],
                    sign["x"],
                    sign["y"],
                    sign["z"],
                    side,
                    lines,
                    None,
                    None,
                    None,
                    False,
                    expected_revision,
                )
            )
        except Exception as error:
            response = {"ok": False, "status": "exception", "message": str(error)}
        passed = response.get("ok") is True
        add_matrix_step(
            report,
            case,
            operation=phase,
            status="passed" if passed else "failed",
            required_capabilities=required,
            mutation_attempted=True,
            request=request,
            response=response,
            reason=str(response.get("message") or ""),
        )
        if not passed:
            case["status"] = "failed"
            self._matrix_set_cursor(context, case_index, terminal_phase)
            return
        case["expected_revision"] = int(
            response.get("revision") or case["expected_revision"]
        )
        self._matrix_set_cursor(context, case_index, next_phase)

    def _matrix_phase_capture_text(
        self,
        context: dict[str, Any],
        case_index: int,
        case: dict[str, Any],
        phase: str,
    ) -> None:
        report = context["report"]
        snapshot = self._matrix_capture(context, case)
        structure_matches = self._matrix_snapshot_matches(snapshot, case)
        revision_matches = (
            int(snapshot.get("revision") or 0)
            == int(case.get("expected_revision") or 0)
        )
        front = list(dict(snapshot.get("front") or {}).get("lines") or [])
        back = list(dict(snapshot.get("back") or {}).get("lines") or [])
        if phase == "capture_front":
            passed = structure_matches and revision_matches and front == case["front_lines"]
            next_phase = "back"
        elif phase == "capture_back":
            passed = (
                structure_matches
                and revision_matches
                and front == case["front_lines"]
                and back == case["back_lines"]
            )
            next_phase = "line_edit"
        else:
            passed = (
                structure_matches
                and revision_matches
                and front == case["edited_front_lines"]
                and back == case["back_lines"]
            )
            next_phase = "color"
        if passed:
            case["expected_revision"] = int(
                snapshot.get("revision") or case["expected_revision"]
            )
            add_matrix_step(
                report,
                case,
                operation=phase,
                status="passed",
                required_capabilities=("capture", "read_text"),
                response=snapshot,
                reason="exact four-line text and opposite-side preservation read back",
            )
            self._matrix_set_cursor(context, case_index, next_phase)
            return
        self._matrix_fail_case(
            report,
            case,
            operation=phase,
            reason=(
                "text readback, structural identity, or expected revision did not "
                "match the owned sign"
            ),
            response=snapshot,
            required_capabilities=("capture", "read_text"),
        )
        next_terminal = "cleanup" if report["config"]["cleanup_after_run"] else "finish_case"
        self._matrix_set_cursor(context, case_index, next_terminal)

    def _matrix_phase_advanced(
        self,
        context: dict[str, Any],
        case_index: int,
        case: dict[str, Any],
        phase: str,
    ) -> None:
        report = context["report"]
        next_capture = {
            "color": "capture_color",
            "glow": "capture_glow",
            "wax": "capture_wax",
            "unwax": "capture_unwax",
        }[phase]
        terminal_phase = (
            "cleanup" if report["config"]["cleanup_after_run"] else "finish_case"
        )
        next_without_call = {
            "color": "glow",
            "glow": "wax",
            "wax": "unwax",
            "unwax": terminal_phase,
        }[phase]
        feature = {
            "color": "text_color",
            "glow": "glowing",
            "wax": "waxed",
            "unwax": "waxed",
        }[phase]
        required = ("read_text", "write_text", "front_and_back", feature)
        if not report["config"]["test_advanced_fields"]:
            add_matrix_step(
                report,
                case,
                operation=phase,
                status="skipped",
                required_capabilities=required,
                reason="test_advanced_fields=false in matrix config",
            )
            self._matrix_set_cursor(context, case_index, next_without_call)
            return
        ready, reason, _ = self._mutation_preflight(
            context["bridge"], self.server, phase, required
        )
        if not ready:
            add_matrix_step(
                report,
                case,
                operation=phase,
                status="skipped",
                required_capabilities=required,
                mutation_attempted=False,
                reason=reason,
            )
            self._matrix_set_cursor(context, case_index, next_without_call)
            return
        sign = case["sign"]
        argb = report["config"]["argb"] if phase == "color" else None
        glowing = report["config"]["glowing"] if phase == "glow" else None
        waxed = (
            report["config"]["waxed"]
            if phase == "wax"
            else False if phase == "unwax" else None
        )
        request = {
            "dimension": case["dimension"],
            **sign,
            "side": "front",
            "lines": case["edited_front_lines"],
            "argb": argb,
            "glowing": glowing,
            "waxed": waxed,
            "expected_revision": int(case.get("expected_revision") or 0),
        }
        expected_revision = int(case.get("expected_revision") or 0)
        if expected_revision <= 0:
            self._matrix_fail_case(
                report,
                case,
                operation=phase,
                reason="owned sign has no nonzero expected revision; no mutation attempted",
                request=request,
                required_capabilities=required,
            )
            self._matrix_set_cursor(context, case_index, next_without_call)
            return
        try:
            response = dict(
                context["bridge"].set_text(
                    self.server,
                    case["dimension"],
                    sign["x"],
                    sign["y"],
                    sign["z"],
                    "front",
                    case["edited_front_lines"],
                    argb,
                    glowing,
                    waxed,
                    False,
                    expected_revision,
                )
            )
        except Exception as error:
            response = {"ok": False, "status": "exception", "message": str(error)}
        passed = response.get("ok") is True
        add_matrix_step(
            report,
            case,
            operation=phase,
            status="passed" if passed else "failed",
            required_capabilities=required,
            mutation_attempted=True,
            request=request,
            response=response,
            reason=str(response.get("message") or ""),
        )
        if not passed:
            case["status"] = "failed"
            self._matrix_set_cursor(context, case_index, next_without_call)
            return
        case["expected_revision"] = int(
            response.get("revision") or case["expected_revision"]
        )
        self._matrix_set_cursor(context, case_index, next_capture)

    def _matrix_phase_capture_advanced(
        self,
        context: dict[str, Any],
        case_index: int,
        case: dict[str, Any],
        phase: str,
    ) -> None:
        report = context["report"]
        snapshot = self._matrix_capture(context, case)
        structure_matches = self._matrix_snapshot_matches(snapshot, case)
        revision_matches = (
            int(snapshot.get("revision") or 0)
            == int(case.get("expected_revision") or 0)
        )
        front = dict(snapshot.get("front") or {})
        color_applied = any(
            step.get("operation") == "color" and step.get("status") == "passed"
            for step in case.get("steps", [])
        )
        glow_applied = any(
            step.get("operation") == "glow" and step.get("status") == "passed"
            for step in case.get("steps", [])
        )
        if phase == "capture_color":
            actual = front.get("argb")
            expected = report["config"]["argb"]
            next_phase = "glow"
        elif phase == "capture_glow":
            actual = front.get("glowing")
            expected = report["config"]["glowing"]
            next_phase = "wax"
        elif phase == "capture_wax":
            actual = snapshot.get("waxed")
            expected = report["config"]["waxed"]
            next_phase = "unwax"
        else:
            actual = snapshot.get("waxed")
            expected = False
            next_phase = (
                "cleanup" if report["config"]["cleanup_after_run"] else "finish_case"
            )
        preserved = True
        if color_applied:
            preserved = preserved and front.get("argb") == report["config"]["argb"]
        if glow_applied:
            preserved = (
                preserved and front.get("glowing") == report["config"]["glowing"]
            )
        passed = (
            structure_matches
            and revision_matches
            and actual == expected
            and preserved
            and list(front.get("lines") or []) == case["edited_front_lines"]
            and list(dict(snapshot.get("back") or {}).get("lines") or [])
            == case["back_lines"]
        )
        if passed:
            case["expected_revision"] = int(
                snapshot.get("revision") or case["expected_revision"]
            )
            add_matrix_step(
                report,
                case,
                operation=phase,
                status="passed",
                required_capabilities=("capture",),
                response=snapshot,
                reason=(
                    f"advanced value read back exactly as {expected!r}; earlier "
                    "advanced values were preserved"
                ),
            )
        else:
            self._matrix_fail_case(
                report,
                case,
                operation=phase,
                reason=(
                    f"advanced value readback {actual!r} did not equal {expected!r} "
                    "or the owned sign's structure/revision/text was not preserved"
                ),
                response=snapshot,
                required_capabilities=("capture",),
            )
        self._matrix_set_cursor(context, case_index, next_phase)

    def _matrix_cleanup_case(
        self, context: dict[str, Any], case: dict[str, Any], *, standalone: bool
    ) -> bool:
        report = context["report"]
        bridge = context["bridge"]
        conflict_reason = ""
        capture_absent = False
        if case.get("owned_sign"):
            snapshot = self._matrix_capture(context, case)
            expected_revision = int(case.get("expected_revision") or 0)
            if snapshot.get("found") is not True:
                capture_absent = True
            elif (
                not self._matrix_snapshot_matches(snapshot, case)
                or expected_revision == 0
                or int(snapshot.get("revision") or 0) != expected_revision
            ):
                conflict_reason = (
                    "owned sign no longer matches its expected identifier/revision; "
                    "it was preserved"
                )
            else:
                sign = case["sign"]
                ready, reason, _ = self._mutation_preflight(
                    bridge, self.server, "cleanup remove", ("remove",)
                )
                if not ready:
                    conflict_reason = reason
                else:
                    try:
                        response = dict(
                            bridge.remove(
                                self.server,
                                case["dimension"],
                                sign["x"],
                                sign["y"],
                                sign["z"],
                                False,
                                expected_revision,
                            )
                        )
                    except Exception as error:
                        response = {
                            "ok": False,
                            "status": "exception",
                            "message": str(error),
                        }
                    add_matrix_step(
                        report,
                        case,
                        operation="cleanup_remove_sign",
                        status="passed" if response.get("ok") is True else "failed",
                        required_capabilities=("remove",),
                        mutation_attempted=True,
                        request={
                            "dimension": case["dimension"],
                            **sign,
                            "expected_revision": expected_revision,
                        },
                        response=response,
                        before=snapshot,
                        reason=str(response.get("message") or ""),
                    )
                    if response.get("ok") is True:
                        case["owned_sign"] = False
                    else:
                        conflict_reason = "Sign API removal failed; support was preserved"
        sign_location = case["sign"]
        try:
            dimension = self.server.level.get_dimension(case["dimension"])
            sign_block_type = str(
                dimension.get_block_at(
                    sign_location["x"], sign_location["y"], sign_location["z"]
                ).type
            )
        except Exception as error:
            sign_block_type = ""
            conflict_reason = (
                conflict_reason
                or f"sign cell could not be read safely ({error}); sign and support were preserved"
            )
        if case.get("owned_sign") and capture_absent:
            if sign_block_type == "minecraft:air":
                case["owned_sign"] = False
            else:
                conflict_reason = (
                    conflict_reason
                    or "capture could not prove the owned sign exists and the public block "
                    "read did not prove air; sign and support were preserved"
                )
        if not case.get("owned_sign") and sign_block_type != "minecraft:air":
            conflict_reason = (
                conflict_reason
                or "sign cell is not air but has no verified owned revision; sign and support were preserved"
            )
        if (
            not case.get("owned_sign")
            and sign_block_type == "minecraft:air"
            and case.get("owned_support")
        ):
            support = case["support"]
            block = dimension.get_block_at(support["x"], support["y"], support["z"])
            before_type = str(block.type)
            if before_type != report["config"]["support_block"]:
                conflict_reason = (
                    conflict_reason
                    or "owned support no longer matches the configured support block; it was preserved"
                )
            else:
                try:
                    block.set_type("minecraft:air", False)
                    after_type = str(block.type)
                except Exception as error:
                    after_type = f"exception: {error}"
                passed = after_type == "minecraft:air"
                add_matrix_step(
                    report,
                    case,
                    operation="cleanup_remove_support",
                    status="passed" if passed else "failed",
                    mutation_attempted=True,
                    request={"type": "minecraft:air", **support},
                    before={"type": before_type},
                    after={"type": after_type},
                    reason="removed runner-owned support" if passed else "support removal failed",
                )
                if passed:
                    case["owned_support"] = False
                else:
                    conflict_reason = conflict_reason or "support removal failed"
        if conflict_reason:
            report["cleanup"].setdefault("conflicts", []).append(
                {"case_id": case["id"], "reason": conflict_reason}
            )
            add_matrix_step(
                report,
                case,
                operation="cleanup_conflict",
                status="failed",
                reason=conflict_reason,
            )
            if not standalone:
                case["status"] = "failed"
            return False
        return True

    def _matrix_cleanup_tick(self, context: dict[str, Any]) -> None:
        context["plugin"] = self
        report = context["report"]
        index = int(report["cursor"]["case_index"])
        if index >= len(report["cases"]):
            conflicts = report["cleanup"].get("conflicts", [])
            report["cleanup"]["state"] = "completed" if not conflicts else "conflicts"
            report["cleanup"]["completed_at_utc"] = matrix_utc_now()
            refresh_matrix_coverage(report)
            path = save_run_report(Path(self.data_folder), report)
            sender_name = str(context.get("sender_name") or "")
            self.matrix_context = None
            self.matrix_task = None
            self.matrix_cancel_requested = False
            rendered = (
                f"Matrix cleanup finished with {len(conflicts)} conflict(s). Report: {path}"
            )
            try:
                player = self.server.get_player(sender_name)
                if player is not None:
                    player.send_message(rendered)
            except Exception:
                pass
            self.logger.info(rendered)
            return
        case = report["cases"][index]
        self._matrix_cleanup_case(context, case, standalone=True)
        report["cursor"] = {"case_index": index + 1, "phase": "cleanup"}
        save_run_report(Path(self.data_folder), report)
        self._schedule_matrix(int(report["config"]["delay_ticks"]))
