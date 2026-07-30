"""Strict planning and evidence helpers for the disposable-world sign matrix."""
from __future__ import annotations

import hashlib
import json
import re
import tomllib
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MATERIALS = (
    "oak",
    "spruce",
    "birch",
    "jungle",
    "acacia",
    "dark_oak",
    "mangrove",
    "cherry",
    "bamboo",
    "crimson",
    "warped",
    "pale_oak",
)
KINDS = ("standing", "wall", "ceiling_hanging", "wall_hanging")
MATERIAL_CODES = {
    "oak": "oak",
    "spruce": "spr",
    "birch": "bir",
    "jungle": "jun",
    "acacia": "aca",
    "dark_oak": "d_oak",
    "mangrove": "man",
    "cherry": "che",
    "bamboo": "bam",
    "crimson": "cri",
    "warped": "war",
    "pale_oak": "p_oak",
}
KIND_CODES = {
    "standing": "stand",
    "wall": "wall",
    "ceiling_hanging": "ceil",
    "wall_hanging": "whang",
}
SAFE_TRANSFERRED_MESSAGE_BYTES = 22
MAX_MATRIX_CASES = 48
RUN_ID = re.compile(r"\A\d{8}T\d{6}Z-[0-9a-f]{8}\Z")
ALLOWED_CONFIG_KEYS = frozenset(
    {
        "schema",
        "delay_ticks",
        "stop_on_failure",
        "cleanup_after_run",
        "support_block",
        "spacing",
        "columns",
        "rotation",
        "facing",
        "chains_attached",
        "max_cases",
        "max_radius",
        "materials",
        "kinds",
        "front_lines",
        "back_lines",
        "line_edit_index",
        "line_edit_value",
        "test_advanced_fields",
        "argb",
        "glowing",
        "waxed",
    }
)
PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
ALLOWED_PLACEHOLDERS = frozenset(
    {"material", "material_code", "kind", "kind_code", "side", "index"}
)

# Every activation probe has an explicit automation disposition. A matrix run
# can therefore say what it did not test instead of silently leaving false
# entries that look like execution failures.
PROBE_COVERAGE: dict[str, dict[str, str]] = {
    "standing_sign_place": {"mode": "automated", "operation": "capture_placed"},
    "wall_sign_place": {"mode": "automated", "operation": "capture_placed"},
    "ceiling_hanging_sign_place": {"mode": "automated", "operation": "capture_placed"},
    "wall_hanging_sign_place": {"mode": "automated", "operation": "capture_placed"},
    "front_text_read_write": {"mode": "automated", "operation": "capture_front"},
    "back_text_read_write": {"mode": "automated", "operation": "capture_back"},
    "individual_line_edit": {"mode": "automated", "operation": "capture_line_edit"},
    "filtered_text_round_trip": {"mode": "capability", "capability": "filtered_text"},
    "text_object_round_trip": {"mode": "capability", "capability": "text_objects"},
    "owner_xuid_round_trip": {"mode": "capability", "capability": "owner_xuid"},
    "text_color_round_trip": {
        "mode": "automated_capability",
        "capability": "text_color",
        "operation": "capture_color",
    },
    "glow_round_trip": {
        "mode": "automated_capability",
        "capability": "glowing",
        "operation": "capture_glow",
    },
    "hide_glow_outline_round_trip": {
        "mode": "capability",
        "capability": "hide_glow_outline",
    },
    "persist_formatting_round_trip": {
        "mode": "capability",
        "capability": "persist_formatting",
    },
    "wax": {
        "mode": "automated_capability",
        "capability": "waxed",
        "operation": "capture_wax",
    },
    "unwax": {
        "mode": "automated_capability",
        "capability": "waxed",
        "operation": "capture_unwax",
    },
    "editor_lock": {"mode": "capability", "capability": "editor_lock"},
    "editor_unlock": {"mode": "capability", "capability": "editor_lock"},
    "open_editor_front": {"mode": "manual", "capability": "open_editor"},
    "open_editor_back": {"mode": "manual", "capability": "open_editor"},
    "player_edit_event_observed": {
        "mode": "manual",
        "capability": "player_edit_events",
    },
    "player_edit_event_cancelled": {
        "mode": "manual",
        "capability": "player_edit_events",
    },
    "api_edit_event_cancelled": {"mode": "manual", "capability": "api_edit_events"},
    "replace": {"mode": "capability", "capability": "replace"},
    "clone": {"mode": "capability", "capability": "clone"},
    "move": {"mode": "capability", "capability": "move"},
    "remove": {
        "mode": "cleanup_capability",
        "capability": "remove",
        "operation": "cleanup_remove_sign",
    },
    "atomic_rollback": {"mode": "capability", "capability": "atomic_transactions"},
    "client_refresh": {"mode": "manual", "capability": "client_updates"},
    "player_reconnect": {"mode": "manual"},
    "server_restart_persistence": {
        "mode": "manual",
        "capability": "restart_persistence",
    },
}
KIND_PROBES = {
    "standing_sign_place": "standing",
    "wall_sign_place": "wall",
    "ceiling_hanging_sign_place": "ceiling_hanging",
    "wall_hanging_sign_place": "wall_hanging",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def config_path(data_folder: Path) -> Path:
    return data_folder / "matrix-config.toml"


def latest_report_path(data_folder: Path) -> Path:
    return data_folder / "latest-matrix-report.json"


def run_report_path(data_folder: Path, run_id: str) -> Path:
    if RUN_ID.fullmatch(run_id) is None:
        raise ValueError("matrix run_id is invalid")
    runs = (data_folder / "runs").resolve()
    candidate = (runs / f"{run_id}.json").resolve()
    if candidate.parent != runs:
        raise ValueError("matrix report path escapes the runs directory")
    return candidate


def install_default_config(data_folder: Path) -> Path:
    destination = config_path(data_folder)
    if destination.exists():
        return destination
    template = Path(__file__).with_name("default-config.toml")
    payload = template.read_text(encoding="utf-8")
    _atomic_write_text(destination, payload)
    return destination


def _require_int(config: dict[str, Any], name: str, minimum: int, maximum: int) -> int:
    value = config.get(name)
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be an integer from {minimum} through {maximum}")
    return value


def _require_bool(config: dict[str, Any], name: str) -> bool:
    value = config.get(name)
    if type(value) is not bool:
        raise ValueError(f"{name} must be true or false")
    return value


def _require_unique_choices(
    config: dict[str, Any], name: str, allowed: tuple[str, ...]
) -> list[str]:
    values = config.get(name)
    if not isinstance(values, list) or not values:
        raise ValueError(f"{name} must be a non-empty array")
    if not all(isinstance(value, str) for value in values):
        raise ValueError(f"{name} entries must be strings")
    if len(values) != len(set(values)):
        raise ValueError(f"{name} must not contain duplicates")
    invalid = [value for value in values if value not in allowed]
    if invalid:
        raise ValueError(f"unsupported {name}: {', '.join(invalid)}")
    return values


def _require_lines(config: dict[str, Any], name: str) -> list[str]:
    lines = config.get(name)
    if not isinstance(lines, list) or len(lines) != 4 or not all(
        isinstance(line, str) for line in lines
    ):
        raise ValueError(f"{name} must contain exactly four strings")
    for line in lines:
        if any(character in line for character in ("\0", "\n", "\r")):
            raise ValueError(f"{name} contains a forbidden control character")
        unknown = sorted(set(PLACEHOLDER.findall(line)) - ALLOWED_PLACEHOLDERS)
        if unknown:
            raise ValueError(f"{name} contains unknown placeholders: {', '.join(unknown)}")
    return lines


def load_config(path: Path) -> dict[str, Any]:
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as error:
        raise ValueError(f"could not read matrix config: {error}") from error
    return validate_config(raw)


def validate_config(raw: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("matrix config root must be a table")
    unknown = sorted(set(raw) - ALLOWED_CONFIG_KEYS)
    missing = sorted(ALLOWED_CONFIG_KEYS - set(raw))
    if unknown:
        raise ValueError(f"unknown matrix config keys: {', '.join(unknown)}")
    if missing:
        raise ValueError(f"missing matrix config keys: {', '.join(missing)}")
    if raw.get("schema") != 1:
        raise ValueError("matrix config schema must be 1")

    config = dict(raw)
    config["delay_ticks"] = _require_int(config, "delay_ticks", 1, 200)
    config["spacing"] = _require_int(config, "spacing", 3, 16)
    config["columns"] = _require_int(config, "columns", 1, 16)
    config["rotation"] = _require_int(config, "rotation", 0, 15)
    config["facing"] = _require_int(config, "facing", 2, 5)
    config["max_cases"] = _require_int(config, "max_cases", 1, MAX_MATRIX_CASES)
    config["max_radius"] = _require_int(config, "max_radius", 3, 128)
    for name in (
        "stop_on_failure",
        "cleanup_after_run",
        "chains_attached",
        "test_advanced_fields",
        "glowing",
        "waxed",
    ):
        config[name] = _require_bool(config, name)
    support_block = config.get("support_block")
    if (
        not isinstance(support_block, str)
        or not support_block.startswith("minecraft:")
        or support_block == "minecraft:air"
        or any(character in support_block for character in ("\0", "\n", "\r", " "))
    ):
        raise ValueError("support_block must be a non-air minecraft identifier")
    config["materials"] = _require_unique_choices(config, "materials", MATERIALS)
    config["kinds"] = _require_unique_choices(config, "kinds", KINDS)
    config["front_lines"] = _require_lines(config, "front_lines")
    config["back_lines"] = _require_lines(config, "back_lines")
    config["line_edit_index"] = _require_int(config, "line_edit_index", 0, 3)
    line_edit_value = config.get("line_edit_value")
    if not isinstance(line_edit_value, str) or any(
        character in line_edit_value for character in ("\0", "\n", "\r")
    ):
        raise ValueError("line_edit_value must be one line of text")
    argb = config.get("argb")
    if type(argb) is not int or not 0 <= argb <= 0xFFFFFFFF:
        raise ValueError("argb must be an integer from 0 through 0xffffffff")
    if config["test_advanced_fields"]:
        if argb == 0xFF000000:
            raise ValueError("argb must differ from the default black value for a round trip")
        if config["glowing"] is not True:
            raise ValueError("glowing must be true when test_advanced_fields is enabled")
        if config["waxed"] is not True:
            raise ValueError("waxed must be true so the matrix can test both wax and unwax")

    case_count = len(config["materials"]) * len(config["kinds"])
    if case_count > config["max_cases"]:
        raise ValueError(
            f"matrix has {case_count} cases but max_cases is {config['max_cases']}"
        )
    case_index = 0
    for material in config["materials"]:
        for kind in config["kinds"]:
            for side, name in (("front", "front_lines"), ("back", "back_lines")):
                lines = render_lines(config[name], material, kind, side, case_index)
                require_safe_message(lines, name)
            edited = render_lines(
                config["front_lines"], material, kind, "front", case_index
            )
            edited[config["line_edit_index"]] = render_value(
                line_edit_value, material, kind, "front", case_index
            )
            if edited == render_lines(
                config["front_lines"], material, kind, "front", case_index
            ):
                raise ValueError("line_edit_value must change the selected front line")
            require_safe_message(edited, "line_edit_value")
            case_index += 1
    return config


def config_sha256(config: dict[str, Any]) -> str:
    payload = json.dumps(config, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def render_value(template: str, material: str, kind: str, side: str, index: int) -> str:
    values = {
        "material": material,
        "material_code": MATERIAL_CODES[material],
        "kind": kind,
        "kind_code": KIND_CODES[kind],
        "side": side,
        "index": str(index),
    }
    try:
        return template.format_map(values)
    except (KeyError, ValueError) as error:
        raise ValueError(f"invalid text template {template!r}: {error}") from error


def render_lines(
    templates: list[str], material: str, kind: str, side: str, index: int
) -> list[str]:
    return [render_value(value, material, kind, side, index) for value in templates]


def require_safe_message(lines: list[str], label: str) -> None:
    flattened = "\n".join(lines).encode("utf-8")
    if len(flattened) > SAFE_TRANSFERRED_MESSAGE_BYTES:
        raise ValueError(
            f"{label} renders to {len(flattened)} UTF-8 bytes; exact Linux probe limit "
            f"is {SAFE_TRANSFERRED_MESSAGE_BYTES}"
        )


def sign_identifier(material: str, kind: str) -> str:
    if kind == "standing":
        return (
            "minecraft:standing_sign"
            if material == "oak"
            else f"minecraft:{material}_standing_sign"
        )
    if kind == "wall":
        return (
            "minecraft:wall_sign"
            if material == "oak"
            else f"minecraft:{material}_wall_sign"
        )
    return f"minecraft:{material}_hanging_sign"


def sign_states(config: dict[str, Any], kind: str) -> dict[str, Any]:
    if kind == "standing":
        return {"ground_sign_direction": config["rotation"]}
    if kind == "wall":
        return {"facing_direction": config["facing"]}
    if kind == "ceiling_hanging":
        return {
            "attached_bit": config["chains_attached"],
            "facing_direction": 2,
            "ground_sign_direction": config["rotation"],
            "hanging": True,
        }
    return {
        "attached_bit": False,
        "facing_direction": config["facing"],
        "ground_sign_direction": 0,
        "hanging": False,
    }


def support_location(sign: dict[str, int], kind: str, facing: int) -> dict[str, int]:
    x, y, z = sign["x"], sign["y"], sign["z"]
    if kind == "standing":
        return {"x": x, "y": y - 1, "z": z}
    if kind == "ceiling_hanging":
        return {"x": x, "y": y + 1, "z": z}
    offsets = {
        2: (0, 0, 1),
        3: (0, 0, -1),
        4: (1, 0, 0),
        5: (-1, 0, 0),
    }
    dx, dy, dz = offsets[facing]
    return {"x": x + dx, "y": y + dy, "z": z + dz}


def build_cases(
    config: dict[str, Any], dimension: str, anchor: dict[str, int]
) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    touched: set[tuple[int, int, int]] = set()
    index = 0
    for material in config["materials"]:
        for kind in config["kinds"]:
            column = index % config["columns"]
            row = index // config["columns"]
            sign = {
                "x": anchor["x"] + column * config["spacing"],
                "y": anchor["y"] + 1,
                "z": anchor["z"] + row * config["spacing"],
            }
            support = support_location(sign, kind, config["facing"])
            for location in (sign, support):
                key = (location["x"], location["y"], location["z"])
                if key in touched:
                    raise ValueError(f"matrix cell collision at {key}")
                touched.add(key)
                if max(abs(location["x"] - anchor["x"]), abs(location["z"] - anchor["z"])) > config["max_radius"]:
                    raise ValueError("matrix exceeds max_radius")
                if not -(2**31) <= location["x"] < 2**31 or not -(2**31) <= location["z"] < 2**31:
                    raise ValueError("matrix coordinate exceeds signed 32-bit range")
                if not -64 <= location["y"] <= 319:
                    raise ValueError("matrix y coordinate must stay from -64 through 319")
            front = render_lines(config["front_lines"], material, kind, "front", index)
            back = render_lines(config["back_lines"], material, kind, "back", index)
            edited_front = list(front)
            edited_front[config["line_edit_index"]] = render_value(
                config["line_edit_value"], material, kind, "front", index
            )
            cases.append(
                {
                    "id": f"{index + 1:02d}-{material}-{kind}",
                    "index": index,
                    "material": material,
                    "kind": kind,
                    "dimension": dimension,
                    "sign": sign,
                    "support": support,
                    "identifier": sign_identifier(material, kind),
                    "states": sign_states(config, kind),
                    "front_lines": front,
                    "back_lines": back,
                    "edited_front_lines": edited_front,
                    "status": "pending",
                    "owned_support": False,
                    "owned_sign": False,
                    "placement_revision": 0,
                    "expected_revision": 0,
                    "steps": [],
                }
            )
            index += 1
    return cases


def new_run_report(
    *,
    plugin_version: str,
    platform: str,
    operator: str,
    dimension: str,
    anchor: dict[str, int],
    config: dict[str, Any],
    bridge_status: dict[str, Any],
) -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{timestamp}-{uuid.uuid4().hex[:8]}"
    capabilities = dict(bridge_status.get("capabilities") or {})
    coverage: dict[str, dict[str, Any]] = {}
    for probe, specification in PROBE_COVERAGE.items():
        mode = specification["mode"]
        capability = specification.get("capability")
        if mode == "manual":
            disposition = "manual_required"
        elif capability and capabilities.get(capability) is not True:
            disposition = "unsupported"
        else:
            disposition = "pending"
        coverage[probe] = {
            **specification,
            "status": disposition,
            "evidence": "not yet recorded",
        }
    return {
        "schema": 1,
        "kind": "automated-sign-matrix",
        "plugin_version": plugin_version,
        "bds_package_version": "1.26.33.1",
        "endstone_version": "0.11.6",
        "run_id": run_id,
        "state": "planned",
        "outcome": "incomplete",
        "activation_eligible": False,
        "platform": platform,
        "operator": operator,
        "dimension": dimension,
        "anchor": dict(anchor),
        "started_at_utc": utc_now(),
        "completed_at_utc": "",
        "config_sha256": config_sha256(config),
        "config": deepcopy(config),
        "bridge_status": deepcopy(bridge_status),
        "server_executable_sha256": "",
        "plugin_sha256": "",
        "plugin_discovery": {},
        "world_name": "",
        "world_seed": "",
        "cursor": {"case_index": 0, "phase": "preflight"},
        "cases": build_cases(config, dimension, anchor),
        "run_steps": [],
        "manual_checkpoints": [
            "bedrock_client_rendering",
            "open_editor_ui_acknowledgement",
            "player_edit_packet_observation_and_cancellation",
            "player_reconnect",
            "server_restart_persistence",
        ],
        "coverage": coverage,
        "cleanup": {"state": "not_started", "conflicts": [], "completed_at_utc": ""},
        "summary": {
            "cases_total": len(config["materials"]) * len(config["kinds"]),
            "cases_passed": 0,
            "cases_failed": 0,
            "steps_passed": 0,
            "steps_failed": 0,
            "steps_skipped": 0,
            "mutations_attempted": 0,
        },
    }


def add_step(
    report: dict[str, Any],
    case: dict[str, Any] | None,
    *,
    operation: str,
    status: str,
    required_capabilities: list[str] | tuple[str, ...] = (),
    mutation_attempted: bool = False,
    request: dict[str, Any] | None = None,
    response: Any = None,
    before: Any = None,
    after: Any = None,
    reason: str = "",
) -> dict[str, Any]:
    if status not in {"passed", "failed", "skipped", "cancelled"}:
        raise ValueError(f"invalid matrix step status: {status}")
    step = {
        "at_utc": utc_now(),
        "case_id": None if case is None else case["id"],
        "operation": operation,
        "status": status,
        "required_capabilities": list(required_capabilities),
        "mutation_attempted": bool(mutation_attempted),
        "request": request or {},
        "response": response,
        "before": before,
        "after": after,
        "reason": reason,
    }
    target = report["run_steps"] if case is None else case["steps"]
    target.append(step)
    refresh_summary(report)
    return step


def refresh_summary(report: dict[str, Any]) -> None:
    cases = report.get("cases", [])
    steps = list(report.get("run_steps", []))
    for case in cases:
        steps.extend(case.get("steps", []))
    report["summary"] = {
        "cases_total": len(cases),
        "cases_passed": sum(case.get("status") == "passed" for case in cases),
        "cases_failed": sum(case.get("status") == "failed" for case in cases),
        "steps_passed": sum(step.get("status") == "passed" for step in steps),
        "steps_failed": sum(step.get("status") == "failed" for step in steps),
        "steps_skipped": sum(step.get("status") == "skipped" for step in steps),
        "mutations_attempted": sum(bool(step.get("mutation_attempted")) for step in steps),
        "coverage_passed": sum(
            entry.get("status") == "passed"
            for entry in dict(report.get("coverage") or {}).values()
        ),
        "coverage_unsupported": sum(
            entry.get("status") == "unsupported"
            for entry in dict(report.get("coverage") or {}).values()
        ),
        "coverage_manual": sum(
            entry.get("status") == "manual_required"
            for entry in dict(report.get("coverage") or {}).values()
        ),
    }


def refresh_coverage(report: dict[str, Any]) -> None:
    coverage = dict(report.get("coverage") or {})
    capabilities = dict(dict(report.get("bridge_status") or {}).get("capabilities") or {})
    cases = list(report.get("cases") or [])
    for probe, specification in PROBE_COVERAGE.items():
        entry = coverage[probe]
        mode = specification["mode"]
        capability = specification.get("capability")
        if mode == "manual":
            entry["status"] = "manual_required"
            entry["evidence"] = "requires Bedrock client/operator or restart evidence"
            continue
        if capability and capabilities.get(capability) is not True:
            entry["status"] = "unsupported"
            entry["evidence"] = f"capability {capability} was false; mutation was not attempted"
            continue
        operation = specification.get("operation")
        if not operation:
            entry["status"] = "not_run"
            entry["evidence"] = "capability is advertised but no safe automated probe is implemented"
            continue
        selected = cases
        if probe in KIND_PROBES:
            selected = [case for case in cases if case.get("kind") == KIND_PROBES[probe]]
        required_operations = (
            ("place_blank", "capture_placed")
            if probe in KIND_PROBES
            else (operation,)
        )
        matching_steps = [
            [
                next(
                    (
                        step
                        for step in reversed(list(case.get("steps") or []))
                        if step.get("operation") == required_operation
                    ),
                    None,
                )
                for required_operation in required_operations
            ]
            for case in selected
        ]
        flat_steps = [step for case_steps in matching_steps for step in case_steps]
        if selected and all(step and step.get("status") == "passed" for step in flat_steps):
            entry["status"] = "passed"
            entry["evidence"] = f"{operation} passed for {len(selected)} selected case(s)"
        elif any(step and step.get("status") == "failed" for step in flat_steps):
            entry["status"] = "failed"
            entry["evidence"] = f"one or more {operation} checks failed"
        elif any(step and step.get("status") == "skipped" for step in flat_steps):
            skipped = [step for step in flat_steps if step and step.get("status") == "skipped"]
            if skipped and all(
                "test_advanced_fields=false" in str(step.get("reason") or "")
                for step in skipped
            ):
                entry["status"] = "not_run"
                entry["evidence"] = f"{operation} was disabled by matrix configuration"
            else:
                entry["status"] = "unsupported"
                entry["evidence"] = f"{operation} was capability-gated without mutation"
        else:
            entry["status"] = "pending"
            entry["evidence"] = f"{operation} has not completed for every selected case"
    report["coverage"] = coverage
    refresh_summary(report)


def finish_run(report: dict[str, Any], state: str) -> None:
    if state not in {"completed", "failed", "cancelled", "interrupted"}:
        raise ValueError(f"invalid terminal matrix state: {state}")
    refresh_coverage(report)
    report["state"] = state
    report["completed_at_utc"] = utc_now()
    if state == "completed" and not report["summary"]["cases_failed"]:
        report["outcome"] = "supported_scope_passed"
    elif state == "cancelled":
        report["outcome"] = "cancelled"
    elif state == "interrupted":
        report["outcome"] = "incomplete"
    else:
        report["outcome"] = "failed"
    # Client/manual checkpoints and closed native capabilities mean an automated
    # report is never itself sufficient to activate a verified native manifest.
    report["activation_eligible"] = False


def save_run_report(data_folder: Path, report: dict[str, Any]) -> Path:
    payload = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    archive = run_report_path(data_folder, str(report["run_id"]))
    _atomic_write_text(archive, payload)
    _atomic_write_text(latest_report_path(data_folder), payload)
    return archive


def load_latest_report(data_folder: Path) -> dict[str, Any]:
    path = latest_report_path(data_folder)
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"could not load latest matrix report: {error}") from error
    if report.get("schema") != 1 or report.get("kind") != "automated-sign-matrix":
        raise ValueError("latest matrix report has an incompatible schema or kind")
    run_report_path(data_folder, str(report.get("run_id") or ""))
    return report


def _atomic_write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(path)
