#!/usr/bin/env python3
"""Validate a Sign API exact-binary manifest.

Without --allow-incomplete, any missing proof closes the gate with a non-zero exit.
"""
from __future__ import annotations

import argparse
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


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
    report_path = root / str(stage.get("report_path", ""))
    if not report_path.is_file():
        missing.append("stage_probe.report_path")
    elif HEX64.fullmatch(report_hash) and file_sha256(report_path) != report_hash:
        missing.append("stage_probe report SHA-256 match")

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
