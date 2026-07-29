"""Strict stage-probe report creation and persistence helpers."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BDS_PACKAGE = "1.26.33.1"
ENDSTONE_VERSION = "0.11.6"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
PROBE_NAMES = (
    "standing_sign_place",
    "wall_sign_place",
    "ceiling_hanging_sign_place",
    "wall_hanging_sign_place",
    "front_text_read_write",
    "back_text_read_write",
    "individual_line_edit",
    "filtered_text_round_trip",
    "text_object_round_trip",
    "owner_xuid_round_trip",
    "text_color_round_trip",
    "glow_round_trip",
    "hide_glow_outline_round_trip",
    "persist_formatting_round_trip",
    "wax",
    "unwax",
    "editor_lock",
    "editor_unlock",
    "open_editor_front",
    "open_editor_back",
    "player_edit_event_observed",
    "player_edit_event_cancelled",
    "api_edit_event_cancelled",
    "replace",
    "clone",
    "move",
    "remove",
    "atomic_rollback",
    "client_refresh",
    "player_reconnect",
    "server_restart_persistence",
)
HASH_FIELDS = (
    "server_executable_sha256",
    "plugin_sha256",
    "log_sha256",
    "world_backup_sha256",
)
EDITABLE_METADATA = frozenset((*HASH_FIELDS, "world_seed", "operator"))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def new_report(
    *,
    platform: str,
    operator: str,
    dimension: str,
    x: int,
    y: int,
    z: int,
) -> dict[str, Any]:
    if platform not in {"linux-x64", "windows-x64"}:
        raise ValueError(f"unsupported stage-probe platform: {platform}")
    return {
        "schema": 1,
        "platform": platform,
        "bds_package_version": BDS_PACKAGE,
        "endstone_version": ENDSTONE_VERSION,
        "server_executable_sha256": "",
        "plugin_sha256": "",
        "world_seed": "",
        "started_at_utc": utc_now(),
        "completed_at_utc": "",
        "operator": operator,
        "passed": False,
        "results": {
            probe: {"passed": False, "evidence": "not yet recorded"}
            for probe in PROBE_NAMES
        },
        "log_sha256": "",
        "world_backup_sha256": "",
        "target": {"dimension": dimension, "x": x, "y": y, "z": z},
        "invocations": [],
    }


def report_path(data_folder: Path, platform: str) -> Path:
    return data_folder / f"{platform}-{BDS_PACKAGE}-stage-probe.json"


def save_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_report(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != 1 or set(data.get("results", {})) != set(PROBE_NAMES):
        raise ValueError("stage-probe report has an incompatible schema or result set")
    return data


def record_result(
    report: dict[str, Any], probe: str, passed: bool, evidence: str
) -> None:
    if probe not in PROBE_NAMES:
        raise ValueError(f"unknown probe {probe!r}")
    evidence = evidence.strip()
    if not evidence:
        raise ValueError("probe evidence must not be empty")
    report["results"][probe] = {
        "passed": bool(passed),
        "evidence": evidence[:4096],
    }
    report["passed"] = False
    report["completed_at_utc"] = ""


def set_metadata(report: dict[str, Any], field: str, value: str) -> None:
    if field not in EDITABLE_METADATA:
        raise ValueError(f"metadata field is not editable: {field}")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"metadata field {field} must not be empty")
    if field in HASH_FIELDS:
        normalized = normalized.casefold()
        if not HEX64.fullmatch(normalized):
            raise ValueError(f"{field} must be a lowercase 64-character SHA-256")
    report[field] = normalized
    report["passed"] = False
    report["completed_at_utc"] = ""


def append_invocation(
    report: dict[str, Any], operation: str, request: dict[str, Any], response: Any
) -> None:
    entries = report.setdefault("invocations", [])
    entries.append(
        {
            "at_utc": utc_now(),
            "operation": operation,
            "request": request,
            "response": response,
        }
    )
    del entries[:-100]


def completion_failures(report: dict[str, Any]) -> list[str]:
    failures = [field for field in HASH_FIELDS if not HEX64.fullmatch(str(report.get(field, "")))]
    for field in ("platform", "world_seed", "started_at_utc", "operator"):
        if not report.get(field):
            failures.append(field)
    results = report.get("results", {})
    if set(results) != set(PROBE_NAMES):
        failures.append("exact result set")
    else:
        for probe in PROBE_NAMES:
            entry = results[probe]
            if entry.get("passed") is not True or not entry.get("evidence"):
                failures.append(probe)
    return failures


def finish_report(report: dict[str, Any]) -> list[str]:
    failures = completion_failures(report)
    report["completed_at_utc"] = utc_now()
    report["passed"] = not failures
    return failures
