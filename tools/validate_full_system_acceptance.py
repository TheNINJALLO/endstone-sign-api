#!/usr/bin/env python3
"""Validate one platform's strict alpha.8 full-system qualification evidence."""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import re

from verify_native_manifest import REQUIRED_PROBES


ROOT = Path(__file__).resolve().parents[1]
AUTOMATION_PATH = (
    ROOT
    / "examples"
    / "python"
    / "sign_api_tester_plugin"
    / "src"
    / "endstone_sign_tester"
    / "automation.py"
)
AUTOMATION_SPEC = importlib.util.spec_from_file_location(
    "full_system_acceptance_automation", AUTOMATION_PATH
)
if AUTOMATION_SPEC is None or AUTOMATION_SPEC.loader is None:
    raise SystemExit(f"Could not load packaged acceptance profile: {AUTOMATION_PATH}")
AUTOMATION = importlib.util.module_from_spec(AUTOMATION_SPEC)
AUTOMATION_SPEC.loader.exec_module(AUTOMATION)


BDS_PACKAGE = "1.26.33.1"
ENDSTONE_VERSION = "0.11.6"
TESTER_VERSION = "0.2.0a8"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
MATERIALS = set(AUTOMATION.MATERIALS)
KINDS = set(AUTOMATION.KINDS)
REQUIRED_CAPABILITIES = set(AUTOMATION.REQUIRED_QUALIFICATION_CAPABILITIES)
REQUIRED_CASE_OPERATIONS = set(AUTOMATION.REQUIRED_CASE_OPERATIONS)
MUTATING_CASE_OPERATIONS = set(AUTOMATION.MUTATING_CASE_OPERATIONS)
REQUIRED_RUN_OPERATIONS = set(AUTOMATION.REQUIRED_RUN_OPERATIONS)
REQUIRED_PREFLIGHT_OPERATIONS = set(AUTOMATION.REQUIRED_PREFLIGHT_OPERATIONS)
EXPECTED_SERVER_SHA256 = {
    "linux-x64": "61995841f21baf9bfab96e0d9b0cb798501dcc9789dab68e496f3b8e3bc83375",
    "windows-x64": "4a0b867eee6c24310f405410b17e9794441b81ed8f2976cdd4cef54d0c441829",
}
EXPECTED_TESTER_WHEEL = {
    "linux-x64": "endstone_sign_tester-0.2.0a8-cp314-cp314-linux_x86_64.whl",
    "windows-x64": "endstone_sign_tester-0.2.0a8-cp314-cp314-win_amd64.whl",
}

CASE_OPERATION_ORDER = (
    "create_support",
    "place_blank",
    "capture_placed",
    "front",
    "capture_front",
    "back",
    "capture_back",
    "line_edit",
    "capture_line_edit",
    "color",
    "capture_color",
    "glow",
    "capture_glow",
    "wax",
    "capture_wax",
    "unwax",
    "capture_unwax",
    "cleanup_remove_sign",
    "cleanup_remove_support",
)
RUN_OPERATION_ORDER = (
    "capture_filtered_text",
    "capture_text_object",
    "capture_owner_xuid",
    "capture_hide_glow_outline",
    "capture_persist_formatting",
    "capture_editor_lock",
    "capture_editor_unlock",
    "capture_api_edit_event_cancelled",
    "capture_replace",
    "capture_clone",
    "capture_move",
    "capture_atomic_rollback",
)
PREFLIGHT_OPERATION_ORDER = (
    "binary_evidence",
    "capability_preflight",
    "block_descriptor_preflight",
    "arena_air_preflight",
)
SNAPSHOT_CORE_FIELDS = (
    "block_identifier",
    "kind",
    "states",
    "front",
    "back",
    "waxed",
    "locked_for_editing_by",
    "locked_for_editing_xuid",
    "remote_profanity_filter_enabled",
    "local_profanity_filter_enabled",
    "movable",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path, label: str, failures: list[str]) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        failures.append(f"{label} could not be read: {error}")
        return {}
    if not isinstance(value, dict):
        failures.append(f"{label} root must be an object")
        return {}
    return value


def _mapping(value: object) -> dict:
    return value if type(value) is dict else {}


def _positive_revision(value: object) -> bool:
    return type(value) is int and 0 < value <= 0xFFFFFFFFFFFFFFFF


def _valid_utc_timestamp(value: object) -> bool:
    if type(value) is not str or not value.strip():
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    offset = parsed.utcoffset()
    return offset is not None and offset.total_seconds() == 0


def _location_matches(value: object, expected: dict, *, dimension: str | None = None) -> bool:
    location = _mapping(value)
    if any(
        type(location.get(axis)) is not int
        or location.get(axis) != expected.get(axis)
        for axis in ("x", "y", "z")
    ):
        return False
    return dimension is None or location.get("dimension") == dimension


def _snapshot_core(snapshot: object) -> dict:
    value = _mapping(snapshot)
    return {field: value.get(field) for field in SNAPSHOT_CORE_FIELDS}


def _valid_text_face(value: object) -> bool:
    face = _mapping(value)
    lines = face.get("lines")
    return (
        type(lines) is list
        and len(lines) == 4
        and all(type(line) is str for line in lines)
        and type(face.get("filtered_message")) is str
        and type(face.get("text_object")) is str
        and type(face.get("message_is_text_object")) is bool
        and type(face.get("owner_xuid")) is str
        and type(face.get("argb")) is int
        and 0 <= face["argb"] <= 0xFFFFFFFF
        and type(face.get("glowing")) is bool
        and type(face.get("hide_glow_outline")) is bool
        and type(face.get("persist_formatting")) is bool
    )


def _snapshot_matches_case(
    snapshot: object,
    case: dict,
    *,
    revision: int | None = None,
    front_lines: list[str] | None = None,
    back_lines: list[str] | None = None,
) -> bool:
    value = _mapping(snapshot)
    if (
        value.get("found") is not True
        or value.get("block_identifier") != case.get("identifier")
        or value.get("kind") != case.get("kind")
        or value.get("dimension") != case.get("dimension")
        or not _location_matches(value, _mapping(case.get("sign")))
        or not _positive_revision(value.get("revision"))
        or not _valid_text_face(value.get("front"))
        or not _valid_text_face(value.get("back"))
        or type(value.get("waxed")) is not bool
        or type(value.get("locked_for_editing_by")) is not int
        or (
            value.get("locked_for_editing_xuid") is not None
            and type(value.get("locked_for_editing_xuid")) is not str
        )
        or type(value.get("remote_profanity_filter_enabled")) is not bool
        or type(value.get("local_profanity_filter_enabled")) is not bool
        or type(value.get("movable")) is not bool
        or type(value.get("actor_status")) is not str
    ):
        return False
    states = _mapping(value.get("states"))
    if any(
        key not in states
        or type(states[key]) is not type(expected)
        or states[key] != expected
        for key, expected in _mapping(case.get("states")).items()
    ):
        return False
    if revision is not None and value.get("revision") != revision:
        return False
    if front_lines is not None and list(_mapping(value.get("front")).get("lines") or []) != front_lines:
        return False
    if back_lines is not None and list(_mapping(value.get("back")).get("lines") or []) != back_lines:
        return False
    return True


def _valid_step_base(step: object, operation: str, *, mutation: bool) -> bool:
    value = _mapping(step)
    return (
        value.get("operation") == operation
        and value.get("status") == "passed"
        and type(value.get("mutation_attempted")) is bool
        and value.get("mutation_attempted") is mutation
        and _valid_utc_timestamp(value.get("at_utc"))
        and isinstance(value.get("reason"), str)
        and bool(value["reason"].strip())
    )


def _unique_steps(
    steps: object,
    operations: tuple[str, ...],
    label: str,
    failures: list[str],
) -> dict[str, dict]:
    if type(steps) is not list or any(type(step) is not dict for step in steps):
        failures.append(f"{label} steps must be an array of objects")
        return {}
    selected: dict[str, dict] = {}
    positions: list[int] = []
    for operation in operations:
        matches = [
            (index, step)
            for index, step in enumerate(steps)
            if step.get("operation") == operation
        ]
        if len(matches) != 1:
            failures.append(f"{label}.{operation} must appear exactly once")
            continue
        positions.append(matches[0][0])
        selected[operation] = matches[0][1]
    if len(positions) == len(operations) and positions != sorted(positions):
        failures.append(f"{label} required operations are out of order")
    return selected


def _applied_response(value: object) -> tuple[bool, int]:
    response = _mapping(value)
    revision = response.get("revision")
    return (
        response.get("ok") is True
        and response.get("status") == "applied"
        and _positive_revision(revision),
        revision if type(revision) is int else 0,
    )


def _validate_preflight_evidence(matrix: dict, failures: list[str]) -> None:
    steps = _unique_steps(
        matrix.get("run_steps"),
        PREFLIGHT_OPERATION_ORDER,
        "matrix.preflight",
        failures,
    )
    binary = steps.get("binary_evidence")
    if binary is not None:
        response = _mapping(binary.get("response"))
        if not _valid_step_base(binary, "binary_evidence", mutation=False) or any(
            response.get(field) != matrix.get(field)
            for field in (
                "server_executable_sha256",
                "plugin_sha256",
                "tester_wheel_sha256",
                "world_name",
                "world_seed",
            )
        ) or _mapping(response.get("plugin_discovery")).get("status") != "selected" or _mapping(
            response.get("tester_wheel_discovery")
        ).get("status") != "selected":
            failures.append("matrix.preflight.binary_evidence semantic evidence")

    capability = steps.get("capability_preflight")
    if capability is not None:
        response = _mapping(capability.get("response"))
        capabilities = _mapping(response.get("capabilities"))
        if (
            not _valid_step_base(capability, "capability_preflight", mutation=False)
            or response.get("available") is not True
            or any(capabilities.get(name) is not True for name in REQUIRED_CAPABILITIES)
        ):
            failures.append("matrix.preflight.capability_preflight semantic evidence")

    for operation, empty_field in (
        ("block_descriptor_preflight", "failures"),
        ("arena_air_preflight", "conflicts"),
    ):
        step = steps.get(operation)
        if step is None:
            continue
        response = _mapping(step.get("response"))
        if (
            not _valid_step_base(step, operation, mutation=False)
            or type(response.get(empty_field)) is not list
            or response[empty_field]
        ):
            failures.append(f"matrix.preflight.{operation} semantic evidence")


def _validate_case_evidence(
    case: dict,
    config: dict,
    *,
    source_case: bool,
    failures: list[str],
) -> tuple[int, int]:
    case_id = str(case.get("id") or "unknown")
    label = f"matrix.case.{case_id}"
    selected = _unique_steps(case.get("steps"), CASE_OPERATION_ORDER, label, failures)
    if len(selected) != len(CASE_OPERATION_ORDER):
        return 0, 0
    sign = _mapping(case.get("sign"))
    support = _mapping(case.get("support"))
    dimension = str(case.get("dimension") or "")

    create = selected["create_support"]
    create_request = _mapping(create.get("request"))
    if (
        not _valid_step_base(create, "create_support", mutation=True)
        or not _location_matches(create_request, support)
        or create_request.get("type") != config.get("support_block")
        or _mapping(create.get("before")).get("type") != "minecraft:air"
        or _mapping(create.get("after")).get("type") != config.get("support_block")
    ):
        failures.append(f"{label}.create_support semantic evidence")

    place = selected["place_blank"]
    place_request = _mapping(place.get("request"))
    place_ok, placement_revision = _applied_response(place.get("response"))
    if (
        not _valid_step_base(place, "place_blank", mutation=True)
        or not _location_matches(place_request, sign, dimension=dimension)
        or place_request.get("block_identifier") != case.get("identifier")
        or place_request.get("states") != case.get("states")
        or place_request.get("force") is not False
        or _mapping(place.get("before")).get("type") != "minecraft:air"
        or not place_ok
        or case.get("placement_revision") != placement_revision
    ):
        failures.append(f"{label}.place_blank semantic evidence")

    capture = selected["capture_placed"]
    if (
        not _valid_step_base(capture, "capture_placed", mutation=False)
        or not _snapshot_matches_case(
            capture.get("response"),
            case,
            revision=placement_revision,
            front_lines=["", "", "", ""],
            back_lines=["", "", "", ""],
        )
        or _mapping(capture.get("response")).get("actor_status")
        != "experimental_text_captured"
    ):
        failures.append(f"{label}.capture_placed semantic evidence")

    revision = placement_revision
    expected_front = ["", "", "", ""]
    expected_back = ["", "", "", ""]
    expected_argb: object | None = None
    expected_glowing: object | None = None
    expected_waxed: object | None = None
    pairs = (
        ("front", "capture_front", "front"),
        ("back", "capture_back", "back"),
        ("line_edit", "capture_line_edit", "line"),
        ("color", "capture_color", "color"),
        ("glow", "capture_glow", "glow"),
        ("wax", "capture_wax", "wax"),
        ("unwax", "capture_unwax", "unwax"),
    )
    for mutation_name, capture_name, kind in pairs:
        mutation = selected[mutation_name]
        request = _mapping(mutation.get("request"))
        mutation_ok, next_revision = _applied_response(mutation.get("response"))
        request_valid = (
            _valid_step_base(mutation, mutation_name, mutation=True)
            and _location_matches(request, sign, dimension=dimension)
            and _positive_revision(request.get("expected_revision"))
            and request.get("expected_revision") == revision
            and request.get("force", False) is False
        )
        if kind == "front":
            expected_front = list(case.get("front_lines") or [])
            request_valid = request_valid and request.get("side") == "front" and request.get(
                "lines"
            ) == expected_front
        elif kind == "back":
            expected_back = list(case.get("back_lines") or [])
            request_valid = request_valid and request.get("side") == "back" and request.get(
                "lines"
            ) == expected_back
        elif kind == "line":
            expected_front = list(case.get("edited_front_lines") or [])
            request_valid = request_valid and request.get("side") == "front" and request.get(
                "lines"
            ) == expected_front
        elif kind == "color":
            expected_argb = config.get("argb")
            request_valid = (
                request_valid
                and request.get("side") == "front"
                and request.get("lines") == expected_front
                and request.get("argb") == expected_argb
                and request.get("glowing") is None
                and request.get("waxed") is None
            )
        elif kind == "glow":
            expected_glowing = config.get("glowing")
            request_valid = (
                request_valid
                and request.get("side") == "front"
                and request.get("lines") == expected_front
                and request.get("argb") is None
                and request.get("glowing") is expected_glowing
                and request.get("waxed") is None
            )
        elif kind == "wax":
            expected_waxed = config.get("waxed")
            request_valid = (
                request_valid
                and request.get("side") == "front"
                and request.get("lines") == expected_front
                and request.get("argb") is None
                and request.get("glowing") is None
                and request.get("waxed") is expected_waxed
            )
        else:
            expected_waxed = False
            request_valid = (
                request_valid
                and request.get("side") == "front"
                and request.get("lines") == expected_front
                and request.get("argb") is None
                and request.get("glowing") is None
                and request.get("waxed") is False
            )
        captured = _mapping(selected[capture_name].get("response"))
        capture_valid = (
            _valid_step_base(selected[capture_name], capture_name, mutation=False)
            and _snapshot_matches_case(
                captured,
                case,
                revision=next_revision,
                front_lines=expected_front,
                back_lines=expected_back,
            )
        )
        front = _mapping(captured.get("front"))
        if expected_argb is not None:
            capture_valid = capture_valid and front.get("argb") == expected_argb
        if expected_glowing is not None:
            capture_valid = capture_valid and front.get("glowing") is expected_glowing
        if expected_waxed is not None:
            capture_valid = capture_valid and captured.get("waxed") is expected_waxed
        if (
            not request_valid
            or not mutation_ok
            or next_revision == revision
            or not capture_valid
        ):
            failures.append(f"{label}.{mutation_name}/{capture_name} semantic evidence")
        revision = next_revision

    cleanup_sign = selected["cleanup_remove_sign"]
    cleanup_request = _mapping(cleanup_sign.get("request"))
    cleanup_response = _mapping(cleanup_sign.get("response"))
    cleanup_before = _mapping(cleanup_sign.get("before"))
    cleanup_after = _mapping(cleanup_sign.get("after"))
    cleanup_revision = cleanup_request.get("expected_revision")
    if (
        not _valid_step_base(cleanup_sign, "cleanup_remove_sign", mutation=True)
        or not _location_matches(cleanup_request, sign, dimension=dimension)
        or not _positive_revision(cleanup_revision)
        or cleanup_revision != case.get("expected_revision")
        or not _snapshot_matches_case(
            cleanup_before,
            case,
            revision=cleanup_revision,
            front_lines=expected_front,
            back_lines=expected_back,
        )
        or cleanup_response.get("ok") is not True
        or cleanup_response.get("status") != "applied"
        or type(cleanup_response.get("revision")) is not int
        or cleanup_response.get("revision") != 0
        or not _location_matches(cleanup_after, sign, dimension=dimension)
        or cleanup_after.get("found") is not False
        or cleanup_after.get("type") != "minecraft:air"
    ):
        failures.append(f"{label}.cleanup_remove_sign semantic evidence")
    if not source_case and cleanup_revision != revision:
        failures.append(f"{label}.revision chain before cleanup")

    cleanup_support = selected["cleanup_remove_support"]
    cleanup_support_request = _mapping(cleanup_support.get("request"))
    if (
        not _valid_step_base(cleanup_support, "cleanup_remove_support", mutation=True)
        or not _location_matches(cleanup_support_request, support)
        or cleanup_support_request.get("type") != "minecraft:air"
        or _mapping(cleanup_support.get("before")).get("type")
        != config.get("support_block")
        or _mapping(cleanup_support.get("after")).get("type") != "minecraft:air"
    ):
        failures.append(f"{label}.cleanup_remove_support semantic evidence")
    return revision, cleanup_revision if type(cleanup_revision) is int else 0


def _support_result_valid(value: object, support_block: str) -> bool:
    result = _mapping(value)
    return (
        result.get("ok") is True
        and result.get("before") == "minecraft:air"
        and result.get("after") == support_block
    )


def _validate_run_evidence(
    matrix: dict,
    config: dict,
    run_probe: dict,
    source_case: dict,
    *,
    initial_revision: int,
    cleanup_revision: int,
    failures: list[str],
) -> None:
    selected = _unique_steps(
        matrix.get("run_steps"), RUN_OPERATION_ORDER, "matrix.run_probe", failures
    )
    if len(selected) != len(RUN_OPERATION_ORDER) or not _positive_revision(
        initial_revision
    ):
        return
    current_revision = initial_revision
    source_sign = _mapping(source_case.get("sign"))

    extended = {
        "capture_filtered_text": ("filtered_message", "a7-filter"),
        "capture_text_object": ("text_object", '{"text":"a7"}'),
        "capture_owner_xuid": ("owner_xuid", "a7-owner"),
        "capture_hide_glow_outline": ("hide_glow_outline", None),
        "capture_persist_formatting": ("persist_formatting", None),
    }
    for operation, (field, fixed_value) in extended.items():
        step = selected[operation]
        request = _mapping(step.get("request"))
        response = _mapping(step.get("response"))
        before = _mapping(step.get("before"))
        applied = _mapping(response.get("apply"))
        applied_capture = _mapping(response.get("applied_capture"))
        restored = _mapping(response.get("restore"))
        restored_capture = _mapping(response.get("restored_capture"))
        applied_ok, applied_revision = _applied_response(applied)
        restored_ok, restored_revision = _applied_response(restored)
        before_front = _mapping(before.get("front"))
        expected_value = (
            not bool(before_front.get(field)) if fixed_value is None else fixed_value
        )
        values = _mapping(request.get("values"))
        expected_values = {field: expected_value}
        if operation == "capture_text_object":
            expected_values["message_is_text_object"] = True
        applied_front = _mapping(applied_capture.get("front"))
        semantic = (
            _valid_step_base(step, operation, mutation=True)
            and _location_matches(request.get("target"), source_sign)
            and _snapshot_matches_case(before, source_case, revision=current_revision)
            and values == expected_values
            and applied_ok
            and _snapshot_matches_case(
                applied_capture, source_case, revision=applied_revision
            )
            and applied_front.get(field) == expected_value
            and restored_ok
            and _snapshot_matches_case(
                restored_capture, source_case, revision=restored_revision
            )
            and _snapshot_core(restored_capture) == _snapshot_core(before)
            and step.get("after") == restored_capture
            and applied_revision != current_revision
            and restored_revision != applied_revision
        )
        if operation == "capture_text_object":
            semantic = (
                semantic
                and values.get("message_is_text_object") is True
                and applied_front.get("message_is_text_object") is True
            )
        if not semantic:
            failures.append(f"matrix.run_probe.{operation} semantic evidence")
        current_revision = restored_revision

    lock = selected["capture_editor_lock"]
    lock_request = _mapping(lock.get("request"))
    lock_response = _mapping(lock.get("response"))
    lock_before = _mapping(lock.get("before"))
    lock_apply = _mapping(lock_response.get("apply"))
    lock_capture = _mapping(lock_response.get("capture"))
    lock_ok, lock_revision = _applied_response(lock_apply)
    restore_state = _mapping(run_probe.get("lock_restore"))
    if (
        not _valid_step_base(lock, "capture_editor_lock", mutation=True)
        or not _snapshot_matches_case(
            lock_before, source_case, revision=current_revision
        )
        or lock_request.get("locked_for_editing_by") != 2147483007
        or lock_request.get("xuid") != "a7-lock"
        or not lock_ok
        or lock_revision == current_revision
        or not _snapshot_matches_case(
            lock_capture, source_case, revision=lock_revision
        )
        or lock_capture.get("locked_for_editing_by") != 2147483007
        or lock_capture.get("locked_for_editing_xuid") != "a7-lock"
        or lock.get("after") != lock_capture
        or restore_state.get("snapshot") != lock_before
        or restore_state.get("locked_for_editing_by")
        != lock_before.get("locked_for_editing_by")
        or restore_state.get("locked_for_editing_xuid")
        != lock_before.get("locked_for_editing_xuid")
    ):
        failures.append("matrix.run_probe.capture_editor_lock semantic evidence")
    current_revision = lock_revision

    unlock = selected["capture_editor_unlock"]
    unlock_response = _mapping(unlock.get("response"))
    unlock_apply = _mapping(unlock_response.get("apply"))
    unlock_capture = _mapping(unlock_response.get("capture"))
    unlock_ok, unlock_revision = _applied_response(unlock_apply)
    if (
        not _valid_step_base(unlock, "capture_editor_unlock", mutation=True)
        or unlock.get("before") != lock_capture
        or _mapping(unlock.get("request")).get("restore") != restore_state
        or not unlock_ok
        or unlock_revision == current_revision
        or not _snapshot_matches_case(
            unlock_capture, source_case, revision=unlock_revision
        )
        or _snapshot_core(unlock_capture) != _snapshot_core(lock_before)
        or unlock.get("after") != unlock_capture
    ):
        failures.append("matrix.run_probe.capture_editor_unlock semantic evidence")
    current_revision = unlock_revision

    api = selected["capture_api_edit_event_cancelled"]
    api_request = _mapping(api.get("request"))
    api_response = _mapping(api.get("response"))
    api_probe = _mapping(api_response.get("probe"))
    api_before = _mapping(api.get("before"))
    api_after = _mapping(api.get("after"))
    if (
        not _valid_step_base(api, "capture_api_edit_event_cancelled", mutation=True)
        or not _location_matches(api_request.get("target"), source_sign)
        or not _positive_revision(api_request.get("expected_revision"))
        or api_request.get("expected_revision") != current_revision
        or not _snapshot_matches_case(
            api_before, source_case, revision=current_revision
        )
        or any(
            api_probe.get(field) is not True
            for field in (
                "ok",
                "event_observed",
                "event_cancelled",
                "state_unchanged",
                "listener_removed",
            )
        )
        or api_probe.get("status") != "cancelled"
        or not _snapshot_matches_case(
            api_after, source_case, revision=current_revision
        )
        or api_response.get("capture") != api_after
        or _snapshot_core(api_after) != _snapshot_core(api_before)
    ):
        failures.append(
            "matrix.run_probe.capture_api_edit_event_cancelled semantic evidence"
        )

    replace = selected["capture_replace"]
    replace_request = _mapping(replace.get("request"))
    replace_response = _mapping(replace.get("response"))
    replace_before = _mapping(replace.get("before"))
    replaced = _mapping(replace_response.get("replace"))
    replaced_capture = _mapping(replace_response.get("replace_capture"))
    restored = _mapping(replace_response.get("restore"))
    restored_capture = _mapping(replace_response.get("restored_capture"))
    replaced_ok, replaced_revision = _applied_response(replaced)
    restored_ok, restored_revision = _applied_response(restored)
    replaced_core = _snapshot_core(replaced_capture)
    replace_before_core = _snapshot_core(replace_before)
    alternate = (
        "minecraft:birch_standing_sign"
        if replace_before.get("block_identifier") == "minecraft:spruce_standing_sign"
        else "minecraft:spruce_standing_sign"
    )
    if (
        not _valid_step_base(replace, "capture_replace", mutation=True)
        or not _snapshot_matches_case(
            replace_before, source_case, revision=current_revision
        )
        or not _location_matches(replace_request.get("target"), source_sign)
        or replace_request.get("alternate_identifier") != alternate
        or not replaced_ok
        or replaced_revision == current_revision
        or replaced_capture.get("found") is not True
        or replaced_capture.get("dimension") != source_case.get("dimension")
        or not _location_matches(replaced_capture, source_sign)
        or replaced_capture.get("block_identifier") != alternate
        or replaced_capture.get("revision") != replaced_revision
        or any(
            replaced_core.get(field) != replace_before_core.get(field)
            for field in SNAPSHOT_CORE_FIELDS
            if field != "block_identifier"
        )
        or not restored_ok
        or restored_revision == replaced_revision
        or not _snapshot_matches_case(
            restored_capture, source_case, revision=restored_revision
        )
        or _snapshot_core(restored_capture) != _snapshot_core(replace_before)
        or replace.get("after") != restored_capture
    ):
        failures.append("matrix.run_probe.capture_replace semantic evidence")
    current_revision = restored_revision

    clone = selected["capture_clone"]
    clone_request = _mapping(clone.get("request"))
    clone_response = _mapping(clone.get("response"))
    clone_before = _mapping(clone.get("before"))
    source_after = _mapping(clone_response.get("source_after"))
    destination_after = _mapping(clone_response.get("destination_after"))
    clone_result = _mapping(clone_response.get("clone"))
    clone_ok, clone_revision = _applied_response(clone_result)
    clone_scratch = _mapping(run_probe.get("clone"))
    if (
        not _valid_step_base(clone, "capture_clone", mutation=True)
        or not _snapshot_matches_case(
            clone_before, source_case, revision=current_revision
        )
        or not _location_matches(clone_request.get("source"), source_sign)
        or not _location_matches(
            clone_request.get("destination"), _mapping(clone_scratch.get("sign"))
        )
        or not _support_result_valid(
            clone_response.get("support"), str(config.get("support_block") or "")
        )
        or not clone_ok
        or not _snapshot_matches_case(
            source_after, source_case, revision=current_revision
        )
        or destination_after.get("found") is not True
        or destination_after.get("dimension") != clone_scratch.get("dimension")
        or not _location_matches(
            destination_after, _mapping(clone_scratch.get("sign"))
        )
        or destination_after.get("revision") != clone_revision
        or _snapshot_core(destination_after) != _snapshot_core(clone_before)
        or clone.get("after") != destination_after
    ):
        failures.append("matrix.run_probe.capture_clone semantic evidence")

    move = selected["capture_move"]
    move_request = _mapping(move.get("request"))
    move_response = _mapping(move.get("response"))
    move_before = _mapping(move.get("before"))
    move_source_after = _mapping(move_response.get("source_after"))
    move_destination_after = _mapping(move_response.get("destination_after"))
    move_result = _mapping(move_response.get("move"))
    move_ok, move_revision = _applied_response(move_result)
    move_scratch = _mapping(run_probe.get("move"))
    if (
        not _valid_step_base(move, "capture_move", mutation=True)
        or not _location_matches(move_request.get("source"), _mapping(clone_scratch.get("sign")))
        or not _location_matches(
            move_request.get("destination"), _mapping(move_scratch.get("sign"))
        )
        or not _support_result_valid(
            move_response.get("support"), str(config.get("support_block") or "")
        )
        or not move_ok
        or move_before != destination_after
        or move_response.get("source_air") is not True
        or move_source_after.get("found") is True
        or move_destination_after.get("found") is not True
        or move_destination_after.get("dimension") != move_scratch.get("dimension")
        or not _location_matches(
            move_destination_after, _mapping(move_scratch.get("sign"))
        )
        or move_destination_after.get("revision") != move_revision
        or _snapshot_core(move_destination_after) != _snapshot_core(move_before)
        or move.get("after") != move_destination_after
    ):
        failures.append("matrix.run_probe.capture_move semantic evidence")

    atomic = selected["capture_atomic_rollback"]
    atomic_request = _mapping(atomic.get("request"))
    atomic_response = _mapping(atomic.get("response"))
    atomic_before = _mapping(_mapping(atomic.get("before")).get("first"))
    atomic_after = _mapping(_mapping(atomic.get("after")).get("first"))
    transaction = _mapping(atomic_response.get("transaction"))
    guard = _mapping(run_probe.get("atomic_guard"))
    if (
        not _valid_step_base(atomic, "capture_atomic_rollback", mutation=True)
        or not _location_matches(atomic_request.get("first"), source_sign)
        or not _location_matches(
            atomic_request.get("blocked_destination"), _mapping(guard.get("location"))
        )
        or atomic_request.get("guard_block") != guard.get("block_identifier")
        or not _snapshot_matches_case(
            atomic_before, source_case, revision=current_revision
        )
        or any(
            transaction.get(field) is not True
            for field in (
                "ok",
                "rolled_back",
                "transaction_rejected",
                "first_sign_unchanged",
            )
        )
        or atomic_response.get("guard_after_transaction")
        != guard.get("block_identifier")
        or atomic_response.get("guard_removed") is not True
        or _mapping(atomic_response.get("guard_capture")).get("found") is True
        or _mapping(atomic_response.get("first_after")) != atomic_after
        or not _snapshot_matches_case(
            atomic_after, source_case, revision=current_revision
        )
        or _snapshot_core(atomic_after) != _snapshot_core(atomic_before)
        or _mapping(atomic.get("after")).get("guard_type") != "minecraft:air"
    ):
        failures.append("matrix.run_probe.capture_atomic_rollback semantic evidence")

    if current_revision != cleanup_revision:
        failures.append("matrix source-case revision chain before cleanup")


def validate_stage(stage: dict, failures: list[str]) -> None:
    if stage.get("schema") != 1:
        failures.append("stage.schema")
    if stage.get("bds_package_version") != BDS_PACKAGE:
        failures.append("stage.bds_package_version")
    if stage.get("endstone_version") != ENDSTONE_VERSION:
        failures.append("stage.endstone_version")
    if stage.get("tester_version") != TESTER_VERSION:
        failures.append("stage.tester_version")
    if stage.get("passed") is not True:
        failures.append("stage.passed")
    platform = str(stage.get("platform") or "")
    if platform not in EXPECTED_SERVER_SHA256:
        failures.append("stage.platform")
    for field in (
        "server_executable_sha256",
        "plugin_sha256",
        "tester_wheel_sha256",
        "log_sha256",
        "world_backup_sha256",
    ):
        if not HEX64.fullmatch(str(stage.get(field) or "")):
            failures.append(f"stage.{field}")
    if platform in EXPECTED_SERVER_SHA256 and stage.get(
        "server_executable_sha256"
    ) != EXPECTED_SERVER_SHA256[platform]:
        failures.append("stage.server_executable_sha256 exact manifest mismatch")
    for field in ("platform", "world_seed", "started_at_utc", "completed_at_utc", "operator"):
        if not stage.get(field):
            failures.append(f"stage.{field}")
    for field in ("started_at_utc", "completed_at_utc"):
        if not _valid_utc_timestamp(stage.get(field)):
            failures.append(f"stage.{field} UTC timestamp")
    results = dict(stage.get("results") or {})
    if set(results) != REQUIRED_PROBES:
        failures.append("stage exact 31-probe result set")
        return
    for probe in sorted(REQUIRED_PROBES):
        entry = dict(results.get(probe) or {})
        if entry.get("passed") is not True:
            failures.append(f"stage.results.{probe}.passed")
        evidence = str(entry.get("evidence") or "").strip()
        if not evidence or evidence == "not yet recorded":
            failures.append(f"stage.results.{probe}.evidence")


def validate_matrix(matrix: dict, stage: dict, failures: list[str]) -> None:
    if matrix.get("schema") != 1 or matrix.get("kind") != "automated-sign-matrix":
        failures.append("matrix schema/kind")
    if matrix.get("mode") != "full_system_acceptance":
        failures.append("matrix.mode")
    if matrix.get("plugin_version") != TESTER_VERSION:
        failures.append("matrix.plugin_version")
    if matrix.get("bds_package_version") != BDS_PACKAGE:
        failures.append("matrix.bds_package_version")
    if matrix.get("endstone_version") != ENDSTONE_VERSION:
        failures.append("matrix.endstone_version")
    if matrix.get("platform") != stage.get("platform"):
        failures.append("matrix/stage platform mismatch")
    if matrix.get("operator") != stage.get("operator"):
        failures.append("matrix/stage operator mismatch")
    if matrix.get("world_name") != stage.get("world_name"):
        failures.append("matrix/stage world_name mismatch")
    if stage.get("matrix_run_id") != matrix.get("run_id"):
        failures.append("matrix/stage run_id mismatch")
    if stage.get("matrix_config_sha256") != matrix.get("config_sha256"):
        failures.append("matrix/stage config hash mismatch")
    if matrix.get("state") != "completed":
        failures.append("matrix.state")
    if matrix.get("outcome") != "qualification_passed":
        failures.append("matrix.outcome")
    if matrix.get("activation_eligible") is not False:
        failures.append("matrix.activation_eligible must remain false pending review")

    qualification = dict(matrix.get("qualification") or {})
    if qualification.get("eligible") is not True:
        failures.append("matrix.qualification.eligible")
    if list(qualification.get("blockers") or []):
        failures.append("matrix.qualification.blockers")

    for field in (
        "server_executable_sha256",
        "plugin_sha256",
        "tester_wheel_sha256",
    ):
        value = str(matrix.get(field) or "")
        if not HEX64.fullmatch(value):
            failures.append(f"matrix.{field}")
        if value != stage.get(field):
            failures.append(f"matrix/stage {field} mismatch")
    if str(matrix.get("world_seed") or "") != str(stage.get("world_seed") or ""):
        failures.append("matrix/stage world_seed mismatch")
    target = dict(stage.get("target") or {})
    cases = list(matrix.get("cases") or [])
    first_sign = dict(cases[0].get("sign") or {}) if cases else {}
    if target.get("dimension") != matrix.get("dimension") or any(
        target.get(axis) != first_sign.get(axis) for axis in ("x", "y", "z")
    ):
        failures.append("matrix/stage target mismatch")

    config = dict(matrix.get("config") or {})
    expected_config_hash = hashlib.sha256(
        json.dumps(
            config, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
    ).hexdigest()
    if matrix.get("config_sha256") != expected_config_hash:
        failures.append("matrix.config_sha256")
    expected_config = AUTOMATION.load_acceptance_config()
    if config != expected_config:
        failures.append("matrix config differs from packaged acceptance profile")

    expected_pairs = {(material, kind) for material in MATERIALS for kind in KINDS}
    actual_pairs = {
        (str(case.get("material") or ""), str(case.get("kind") or ""))
        for case in cases
    }
    if len(cases) != 48 or actual_pairs != expected_pairs:
        failures.append("matrix exact 12-material x 4-form case set")
    try:
        expected_cases = AUTOMATION.build_cases(
            expected_config,
            str(matrix.get("dimension") or ""),
            dict(matrix.get("anchor") or {}),
        )
    except Exception as error:
        failures.append(f"matrix acceptance plan could not be reconstructed: {error}")
        expected_cases = []
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
    if len(expected_cases) != len(cases) or any(
        any(saved.get(field) != expected.get(field) for field in immutable_fields)
        for saved, expected in zip(cases, expected_cases)
    ):
        failures.append("matrix cases differ from reconstructed immutable plan")
    try:
        expected_probe = AUTOMATION.build_run_probe_plan(
            expected_config,
            str(matrix.get("dimension") or ""),
            dict(matrix.get("anchor") or {}),
        )
    except Exception as error:
        failures.append(f"matrix run-probe plan could not be reconstructed: {error}")
        expected_probe = {}
    run_probe = _mapping(matrix.get("run_probe"))
    if type(matrix.get("run_probe")) is not dict:
        failures.append("matrix.run_probe must be an object")
    if run_probe.get("source_case_id") != expected_probe.get("source_case_id"):
        failures.append("matrix run-probe source differs from immutable plan")
    for name in ("clone", "move"):
        scratch = _mapping(run_probe.get(name))
        expected_scratch = _mapping(expected_probe.get(name))
        if any(
            scratch.get(field) != expected_scratch.get(field)
            for field in ("dimension", "sign", "support")
        ):
            failures.append(f"matrix run-probe {name} scratch plan mismatch")
        if (
            type(run_probe.get(name)) is not dict
            or scratch.get("owned_sign") is not False
            or scratch.get("owned_support") is not False
        ):
            failures.append(f"matrix run-probe {name} ownership schema")
        if (
            type(scratch.get("expected_revision")) is not int
            or scratch.get("expected_revision") != 0
            or type(scratch.get("expected_snapshot")) is not dict
            or scratch.get("expected_snapshot") != {}
        ):
            failures.append(f"matrix run-probe {name} cleanup evidence incomplete")
    guard = _mapping(run_probe.get("atomic_guard"))
    expected_guard = _mapping(expected_probe.get("atomic_guard"))
    if any(
        guard.get(field) != expected_guard.get(field)
        for field in ("dimension", "location", "block_identifier")
    ):
        failures.append("matrix atomic rollback guard plan mismatch")
    if type(run_probe.get("atomic_guard")) is not dict or guard.get("owned") is not False:
        failures.append("matrix atomic rollback guard ownership schema")
    if any(case.get("status") != "passed" for case in cases):
        failures.append("matrix cases not all passed")
    for case in cases:
        if case.get("owned_sign") is not False or case.get("owned_support") is not False:
            failures.append(f"matrix case {case.get('id')} cleanup ownership schema")

    cleanup_checkpoint = matrix.get("run_probe_cleanup_completed_at_utc")
    if not _valid_utc_timestamp(cleanup_checkpoint):
        failures.append("matrix.run_probe_cleanup_completed_at_utc")

    _validate_preflight_evidence(matrix, failures)
    case_revisions: dict[str, tuple[int, int]] = {}
    source_id = str(run_probe.get("source_case_id") or "")
    for case in cases:
        case_revisions[str(case.get("id") or "")] = _validate_case_evidence(
            case,
            expected_config,
            source_case=case.get("id") == source_id,
            failures=failures,
        )
    source_case = next(
        (case for case in cases if case.get("id") == source_id), None
    )
    if source_case is None:
        failures.append("matrix run-probe source case is missing")
    else:
        initial_revision, cleanup_revision = case_revisions.get(source_id, (0, 0))
        _validate_run_evidence(
            matrix,
            expected_config,
            run_probe,
            source_case,
            initial_revision=initial_revision,
            cleanup_revision=cleanup_revision,
            failures=failures,
        )

    summary = dict(matrix.get("summary") or {})
    for field in ("cases_failed", "steps_failed", "steps_skipped", "coverage_unsupported", "coverage_manual"):
        if int(summary.get(field) or 0) != 0:
            failures.append(f"matrix.summary.{field}")
    if int(summary.get("cases_passed") or 0) != 48:
        failures.append("matrix.summary.cases_passed")
    steps = list(matrix.get("run_steps") or [])
    for case in cases:
        steps.extend(list(case.get("steps") or []))
    if any(step.get("status") in {"failed", "skipped", "cancelled"} for step in steps):
        failures.append("matrix contains a failed, skipped, or cancelled step")
    for case in cases:
        passed_operations = {
            str(step.get("operation") or "")
            for step in list(case.get("steps") or [])
            if AUTOMATION.qualification_step_has_evidence(
                step,
                mutation_required=(
                    str(step.get("operation") or "") in MUTATING_CASE_OPERATIONS
                ),
            )
        }
        missing_case_operations = sorted(REQUIRED_CASE_OPERATIONS - passed_operations)
        if missing_case_operations:
            failures.append(
                f"matrix case {case.get('id')} missing operations: "
                + ", ".join(missing_case_operations)
            )
    passed_preflight_operations = {
        str(step.get("operation") or "")
        for step in matrix.get("run_steps") or []
        if AUTOMATION.qualification_step_has_evidence(
            step, mutation_required=False
        )
    }
    if not REQUIRED_PREFLIGHT_OPERATIONS.issubset(passed_preflight_operations):
        failures.append("matrix required preflight evidence")
    evidenced_run_operations = {
        str(step.get("operation") or "")
        for step in matrix.get("run_steps") or []
        if AUTOMATION.qualification_step_has_evidence(step, mutation_required=True)
    }
    missing_run_operations = sorted(
        REQUIRED_RUN_OPERATIONS - evidenced_run_operations
    )
    if missing_run_operations:
        failures.append(
            "matrix missing full-system operations: " + ", ".join(missing_run_operations)
        )

    coverage = dict(matrix.get("coverage") or {})
    if set(coverage) != REQUIRED_PROBES:
        failures.append("matrix exact 31-probe coverage set")
    else:
        for probe in sorted(REQUIRED_PROBES):
            entry = dict(coverage.get(probe) or {})
            if entry.get("status") != "passed":
                failures.append(f"matrix.coverage.{probe}.status")
            if not str(entry.get("evidence") or "").strip():
                failures.append(f"matrix.coverage.{probe}.evidence")

    cleanup = _mapping(matrix.get("cleanup"))
    if type(matrix.get("cleanup")) is not dict or cleanup.get("state") != "completed":
        failures.append("matrix.cleanup.state")
    if type(cleanup.get("conflicts")) is not list or cleanup.get("conflicts") != []:
        failures.append("matrix.cleanup.conflicts")
    cleanup_completed = cleanup.get("completed_at_utc")
    if not _valid_utc_timestamp(cleanup_completed):
        failures.append("matrix.cleanup.completed_at_utc")

    status = dict(matrix.get("bridge_status") or {})
    if status.get("available") is not True:
        failures.append("matrix.bridge_status.available")
    capabilities = dict(status.get("capabilities") or {})
    for capability in sorted(REQUIRED_CAPABILITIES):
        if capabilities.get(capability) is not True:
            failures.append(f"matrix.capabilities.{capability}")
    discovery = dict(matrix.get("plugin_discovery") or {})
    if discovery.get("status") != "selected":
        failures.append("matrix.plugin_discovery.status")
    tester_discovery = dict(matrix.get("tester_wheel_discovery") or {})
    if tester_discovery.get("status") != "selected":
        failures.append("matrix.tester_wheel_discovery.status")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Require 48/48 cases, 31/31 probes, zero skips, all native capabilities, "
            "matching binary identity, and conflict-free cleanup for one platform."
        )
    )
    parser.add_argument("matrix_report", type=Path)
    parser.add_argument("stage_report", type=Path)
    parser.add_argument("--server-executable", type=Path, required=True)
    parser.add_argument("--plugin-binary", type=Path, required=True)
    parser.add_argument("--tester-wheel", type=Path, required=True)
    parser.add_argument("--server-log", type=Path, required=True)
    parser.add_argument("--world-backup", type=Path, required=True)
    args = parser.parse_args()

    failures: list[str] = []
    matrix = load_json(args.matrix_report, "matrix report", failures)
    stage = load_json(args.stage_report, "stage report", failures)
    if stage:
        validate_stage(stage, failures)
    if matrix and stage:
        validate_matrix(matrix, stage, failures)
    expected_wheel_name = EXPECTED_TESTER_WHEEL.get(str(stage.get("platform") or ""))
    if expected_wheel_name and args.tester_wheel.name != expected_wheel_name:
        failures.append(
            "tester wheel filename does not match the report platform: "
            f"expected {expected_wheel_name}"
        )
    for path, field in (
        (args.server_executable, "server_executable_sha256"),
        (args.plugin_binary, "plugin_sha256"),
        (args.tester_wheel, "tester_wheel_sha256"),
        (args.server_log, "log_sha256"),
        (args.world_backup, "world_backup_sha256"),
    ):
        try:
            actual = sha256(path)
        except OSError as error:
            failures.append(f"could not hash {path}: {error}")
            continue
        if actual != stage.get(field):
            failures.append(f"{field} does not match supplied file {path}")
        if field == "server_executable_sha256":
            platform = str(stage.get("platform") or "")
            expected = EXPECTED_SERVER_SHA256.get(platform)
            if expected is None or actual != expected:
                failures.append(
                    "server_executable_sha256 does not match the exact platform executable"
                )
            if matrix and actual != matrix.get("server_executable_sha256"):
                failures.append(
                    "server_executable_sha256 does not match the matrix report"
                )
    if failures:
        print("full-system acceptance INVALID")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("full-system acceptance VALID")
    print(f"matrix_sha256={sha256(args.matrix_report)}")
    print(f"stage_sha256={sha256(args.stage_report)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
