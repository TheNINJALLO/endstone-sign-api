#!/usr/bin/env python3
"""Validate a Sign API exact-binary manifest.

Without --allow-incomplete, any missing proof closes the gate with a non-zero exit.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re

EXPECTED_ARCHIVES = {
    "linux-x64": "68c52ababde987741029de091c09cd736fe894bc1fe99cf20f9ed5c659f0c180",
    "windows-x64": "fc6c0ad6f82cfb11c65c6756a1a8e49b21ffa8cc203da587df59df365d82a2ad",
}
REQUIRED_SYMBOLS = {
    "sign_actor_save", "sign_actor_load", "get_message", "get_raw_message",
    "get_sign_text_color", "get_is_glowing", "get_hide_glow_outline",
    "get_is_waxed", "get_is_locked_for_editing", "set_message_for_server_scripting",
    "set_sign_text_color", "set_is_glowing", "set_hide_glow_outline", "set_waxed",
    "set_locked_for_editing", "clear_locked_for_editing", "request_open_sign_editor",
    "update_text_from_client", "fire_block_entity_changed",
}
REQUIRED_PROBES = {
    "standing_sign_place", "wall_sign_place", "ceiling_hanging_sign_place",
    "wall_hanging_sign_place", "front_text_read_write", "back_text_read_write",
    "individual_line_edit", "filtered_text_round_trip", "text_object_round_trip",
    "owner_xuid_round_trip", "text_color_round_trip", "glow_round_trip",
    "hide_glow_outline_round_trip", "persist_formatting_round_trip", "wax", "unwax",
    "editor_lock", "editor_unlock", "open_editor_front", "open_editor_back",
    "player_edit_event_observed", "player_edit_event_cancelled", "api_edit_event_cancelled",
    "replace", "clone", "move", "remove", "atomic_rollback", "client_refresh",
    "player_reconnect", "server_restart_persistence",
}
HEX64 = re.compile(r"^[0-9a-f]{64}$")
EXPECTED_TESTER_VERSION = "0.2.0"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _valid_utc_timestamp(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    offset = parsed.utcoffset()
    return offset is not None and offset.total_seconds() == 0


def _repository_file(
    root: Path, value: object, label: str, missing: list[str]
) -> Path | None:
    raw = str(value or "")
    relative = Path(raw)
    if not raw or relative.is_absolute() or ".." in relative.parts:
        missing.append(label)
        return None
    resolved_root = root.resolve()
    resolved = (resolved_root / relative).resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError:
        missing.append(label)
        return None
    if not resolved.is_file():
        missing.append(label)
        return None
    return resolved


def _read_json_object(path: Path, label: str, missing: list[str]) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        missing.append(f"{label} readable JSON object")
        return {}
    if not isinstance(value, dict):
        missing.append(f"{label} readable JSON object")
        return {}
    return value


def _validate_stage_report(
    report: dict, manifest: dict, manifest_stage: dict, missing: list[str]
) -> None:
    if report.get("schema") != 1:
        missing.append("stage report schema=1")
    if report.get("bds_package_version") != manifest.get("bds_package_version"):
        missing.append("stage report BDS package match")
    if report.get("endstone_version") != manifest.get("endstone_version"):
        missing.append("stage report Endstone version match")
    if report.get("platform") != manifest.get("platform"):
        missing.append("stage report platform match")
    if report.get("server_executable_sha256") != manifest.get("executable", {}).get(
        "sha256"
    ):
        missing.append("stage report executable SHA-256 match")
    if report.get("tester_version") != EXPECTED_TESTER_VERSION:
        missing.append(f"stage report tester_version={EXPECTED_TESTER_VERSION}")
    if report.get("passed") is not True:
        missing.append("stage report passed=true")

    for field in (
        "server_executable_sha256",
        "plugin_sha256",
        "tester_wheel_sha256",
        "log_sha256",
        "world_backup_sha256",
        "matrix_config_sha256",
    ):
        if not HEX64.fullmatch(str(report.get(field, ""))):
            missing.append(f"stage report {field}")
    for field in (
        "world_seed",
        "world_name",
        "operator",
        "matrix_run_id",
    ):
        if not str(report.get(field) or "").strip():
            missing.append(f"stage report {field}")
    for field in ("started_at_utc", "completed_at_utc"):
        if not _valid_utc_timestamp(report.get(field)):
            missing.append(f"stage report {field}")
    target = report.get("target")
    if not isinstance(target, dict) or not str(target.get("dimension") or "").strip() or any(
        type(target.get(axis)) is not int for axis in ("x", "y", "z")
    ):
        missing.append("stage report target")

    report_results = report.get("results")
    manifest_results = manifest_stage.get("results")
    if not isinstance(report_results, dict) or set(report_results) != REQUIRED_PROBES:
        missing.append("stage report exact result set")
        return
    for probe in sorted(REQUIRED_PROBES):
        entry = report_results.get(probe)
        actual_passed = entry.get("passed") if isinstance(entry, dict) else None
        if actual_passed is not True:
            missing.append(f"stage report results.{probe}.passed")
        evidence = str(entry.get("evidence") or "").strip() if isinstance(entry, dict) else ""
        if not evidence or evidence == "not yet recorded":
            missing.append(f"stage report results.{probe}.evidence")
        if (
            not isinstance(manifest_results, dict)
            or manifest_results.get(probe) is not actual_passed
        ):
            missing.append(f"stage_probe.results.{probe} report match")


def _validate_matrix_report(matrix: dict, stage: dict, missing: list[str]) -> None:
    if matrix.get("schema") != 1 or matrix.get("kind") != "automated-sign-matrix":
        missing.append("matrix report schema/kind")
    if matrix.get("mode") != "full_system_acceptance":
        missing.append("matrix report full_system_acceptance mode")
    if matrix.get("bds_package_version") != stage.get("bds_package_version"):
        missing.append("matrix/stage BDS package match")
    if matrix.get("endstone_version") != stage.get("endstone_version"):
        missing.append("matrix/stage Endstone version match")
    if matrix.get("plugin_version") != stage.get("tester_version"):
        missing.append("matrix/stage tester version match")
    if matrix.get("platform") != stage.get("platform"):
        missing.append("matrix/stage platform match")
    if matrix.get("run_id") != stage.get("matrix_run_id"):
        missing.append("matrix/stage run ID match")
    if matrix.get("config_sha256") != stage.get("matrix_config_sha256"):
        missing.append("matrix/stage config SHA-256 match")
    config = matrix.get("config")
    if isinstance(config, dict):
        calculated = hashlib.sha256(
            json.dumps(
                config, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ).encode("utf-8")
        ).hexdigest()
        if matrix.get("config_sha256") != calculated:
            missing.append("matrix report config SHA-256")
    else:
        missing.append("matrix report config")

    for field in (
        "server_executable_sha256",
        "plugin_sha256",
        "tester_wheel_sha256",
        "world_name",
        "operator",
    ):
        if matrix.get(field) != stage.get(field):
            missing.append(f"matrix/stage {field} match")
    if str(matrix.get("world_seed") or "") != str(stage.get("world_seed") or ""):
        missing.append("matrix/stage world_seed match")

    if matrix.get("state") != "completed":
        missing.append("matrix report state=completed")
    if matrix.get("outcome") != "qualification_passed":
        missing.append("matrix report outcome=qualification_passed")
    if matrix.get("activation_eligible") is not False:
        missing.append("matrix report activation_eligible=false pending review")
    qualification = matrix.get("qualification")
    if not isinstance(qualification, dict) or qualification.get("eligible") is not True:
        missing.append("matrix report qualification.eligible=true")
    elif list(qualification.get("blockers") or []):
        missing.append("matrix report qualification blockers empty")

    coverage = matrix.get("coverage")
    if not isinstance(coverage, dict) or set(coverage) != REQUIRED_PROBES:
        missing.append("matrix report exact coverage set")
    else:
        for probe in sorted(REQUIRED_PROBES):
            entry = coverage.get(probe)
            if not isinstance(entry, dict) or entry.get("status") != "passed":
                missing.append(f"matrix report coverage.{probe}.passed")

    embedded_stage = matrix.get("stage_report")
    if not isinstance(embedded_stage, dict) or embedded_stage.get("passed") is not True:
        missing.append("matrix report stage_report.passed=true")
    else:
        for field in (
            "server_executable_sha256",
            "plugin_sha256",
            "tester_wheel_sha256",
        ):
            if embedded_stage.get(field) != stage.get(field):
                missing.append(f"matrix embedded stage {field} match")

    cases = matrix.get("cases")
    target = stage.get("target")
    first_sign = cases[0].get("sign") if isinstance(cases, list) and cases and isinstance(cases[0], dict) else None
    if not isinstance(first_sign, dict) or not isinstance(target, dict) or any(
        first_sign.get(axis) != target.get(axis) for axis in ("x", "y", "z")
    ) or matrix.get("dimension") != target.get("dimension"):
        missing.append("matrix/stage target match")


def validate(path: Path, root: Path) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    missing: list[str] = []
    if data.get("schema") != 1:
        missing.append("schema=1")
    platform = data.get("platform")
    if platform not in EXPECTED_ARCHIVES:
        missing.append("supported platform")
    if data.get("bds_package_version") != "1.26.33.1":
        missing.append("bds_package_version=1.26.33.1")
    if data.get("runtime_bds") != "26.33":
        missing.append("runtime_bds=26.33")
    if data.get("endstone_version") != "0.11.6":
        missing.append("endstone_version=0.11.6")
    if platform in EXPECTED_ARCHIVES and data.get("archive_sha256") != EXPECTED_ARCHIVES[platform]:
        missing.append("official archive SHA-256")

    executable = data.get("executable", {})
    if not HEX64.fullmatch(str(executable.get("sha256", ""))):
        missing.append("executable.sha256")
    if not isinstance(executable.get("size"), int) or executable.get("size", 0) <= 0:
        missing.append("executable.size")

    abi = data.get("abi", {})
    for key in ("reviewed", "reviewer", "review_commit", "sign_actor_base_offset",
                "sign_text_side_size", "color_argument_contract", "calling_convention_notes"):
        value = abi.get(key)
        if value in (None, "", False):
            missing.append(f"abi.{key}")

    symbols = data.get("symbols", [])
    by_id = {entry.get("id"): entry for entry in symbols if isinstance(entry, dict)}
    if set(by_id) != REQUIRED_SYMBOLS:
        missing.append("exact required symbol set")
    for symbol in sorted(REQUIRED_SYMBOLS):
        entry = by_id.get(symbol, {})
        for flag in ("resolved", "unique", "signature_verified", "behavior_verified"):
            if entry.get(flag) is not True:
                missing.append(f"symbols.{symbol}.{flag}")
        if not isinstance(entry.get("rva"), int) or entry.get("rva", 0) <= 0:
            missing.append(f"symbols.{symbol}.rva")
        fingerprint = str(entry.get("fingerprint_hex", ""))
        if not fingerprint or len(fingerprint) % 2 or not re.fullmatch(r"[0-9a-fA-F]+", fingerprint):
            missing.append(f"symbols.{symbol}.fingerprint_hex")
        if not entry.get("verification_notes"):
            missing.append(f"symbols.{symbol}.verification_notes")

    hook = data.get("player_edit_hook", {})
    for key in ("installed", "cancellable_before_mutation", "original_call_preserved",
                "disconnect_cleanup_verified"):
        if hook.get(key) is not True:
            missing.append(f"player_edit_hook.{key}")

    stage = data.get("stage_probe", {})
    if stage.get("passed") is not True:
        missing.append("stage_probe.passed")
    report_hash = str(stage.get("report_sha256", ""))
    if not HEX64.fullmatch(report_hash):
        missing.append("stage_probe.report_sha256")
    results = stage.get("results", {})
    if set(results) != REQUIRED_PROBES:
        missing.append("exact required stage-probe set")
    for probe in sorted(REQUIRED_PROBES):
        if results.get(probe) is not True:
            missing.append(f"stage_probe.results.{probe}")
    report_path = _repository_file(
        root, stage.get("report_path"), "stage_probe.report_path", missing
    )
    report: dict = {}
    if report_path is not None:
        if HEX64.fullmatch(report_hash) and file_sha256(report_path) != report_hash:
            missing.append("stage_probe report SHA-256 match")
        report = _read_json_object(report_path, "stage report", missing)
        if report:
            _validate_stage_report(report, data, stage, missing)

    matrix_hash = str(stage.get("matrix_report_sha256", ""))
    if not HEX64.fullmatch(matrix_hash):
        missing.append("stage_probe.matrix_report_sha256")
    matrix_path = _repository_file(
        root,
        stage.get("matrix_report_path"),
        "stage_probe.matrix_report_path",
        missing,
    )
    if matrix_path is not None:
        if HEX64.fullmatch(matrix_hash) and file_sha256(matrix_path) != matrix_hash:
            missing.append("stage_probe matrix report SHA-256 match")
        matrix = _read_json_object(matrix_path, "matrix report", missing)
        if matrix and report:
            _validate_matrix_report(matrix, report, missing)

    bridge = data.get("bridge", {})
    if bridge.get("reviewed") is not True:
        missing.append("bridge.reviewed")
    bridge_hash = str(bridge.get("source_sha256", ""))
    if not HEX64.fullmatch(bridge_hash):
        missing.append("bridge.source_sha256")
    bridge_path = root / str(bridge.get("source_path", ""))
    if not bridge_path.is_file():
        missing.append("bridge.source_path")
    elif HEX64.fullmatch(bridge_hash) and file_sha256(bridge_path) != bridge_hash:
        missing.append("bridge source SHA-256 match")

    if data.get("status") != "verified":
        missing.append("status=verified")
    return missing


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--allow-incomplete", action="store_true")
    args = parser.parse_args()
    missing = validate(args.manifest, args.root)
    if missing:
        print(f"{args.manifest}: native activation gate CLOSED")
        for item in missing:
            print(f"- {item}")
        return 0 if args.allow_incomplete else 1
    print(f"{args.manifest}: native activation gate OPEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
