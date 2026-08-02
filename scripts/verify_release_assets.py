#!/usr/bin/env python3
"""Verify one platform's production Sign API release assets."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
from zipfile import ZipFile


SLUG = "endstone-sign-api"
SUPPORTED_BDS = {"1.26.33"}
SUPPORTED_PLATFORMS = {"linux-x64", "windows-x64"}
EXPECTED_API_MODULES = {
    "endstone_sign/__init__.py",
    "endstone_sign/events.py",
    "endstone_sign/model.py",
    "endstone_sign/native.py",
    "endstone_sign/placement.py",
    "endstone_sign/schema.py",
    "endstone_sign/service.py",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def safe_archive_path(path: str) -> bool:
    candidate = PurePosixPath(path)
    return (
        bool(candidate.parts)
        and "\\" not in path
        and not candidate.is_absolute()
        and ".." not in candidate.parts
    )


def verify_native_format(payload: bytes, platform: str, label: str) -> None:
    if platform.startswith("windows"):
        if len(payload) < 0x40 or not payload.startswith(b"MZ"):
            raise SystemExit(f"Unexpected PE format for {label}")
        pe_offset = int.from_bytes(payload[0x3C:0x40], "little")
        if pe_offset + 26 > len(payload) or payload[pe_offset : pe_offset + 4] != b"PE\0\0":
            raise SystemExit(f"Invalid PE header for {label}")
        if int.from_bytes(payload[pe_offset + 4 : pe_offset + 6], "little") != 0x8664:
            raise SystemExit(f"PE binary is not x86-64: {label}")
        if int.from_bytes(payload[pe_offset + 24 : pe_offset + 26], "little") != 0x20B:
            raise SystemExit(f"PE binary is not PE32+ x86-64: {label}")
        return
    if (
        len(payload) < 20
        or not payload.startswith(b"\x7fELF")
        or payload[4] != 2
        or payload[5] != 1
        or int.from_bytes(payload[18:20], "little") != 62
    ):
        raise SystemExit(f"ELF binary is not little-endian x86-64: {label}")


def verify_linux_runtime(plugin: Path) -> None:
    readelf = shutil.which("readelf")
    if not readelf:
        raise SystemExit("GNU readelf is required to validate Linux release linkage")
    dynamic = subprocess.run(
        [readelf, "--dynamic", str(plugin)], check=True, capture_output=True, text=True
    ).stdout
    nonportable = re.compile(r"^(?:libstdc\+\+|libc\+\+|libc\+\+abi|libgcc_s)\.so(?:\.|$)")
    for line in dynamic.splitlines():
        if "(NEEDED)" in line:
            match = re.search(r"\[([^]]+)\]", line)
            needed = "" if match is None else match.group(1)
            if nonportable.match(needed):
                raise SystemExit(f"Linux plugin depends on non-bundled C++ runtime {needed}")
        if "(RPATH)" not in line and "(RUNPATH)" not in line:
            continue
        match = re.search(r"\[([^]]*)\]", line)
        entries = [] if match is None else match.group(1).split(":")
        unsafe = [
            entry
            for entry in entries
            if entry and entry != "$ORIGIN" and not entry.startswith("$ORIGIN/")
        ]
        if unsafe:
            raise SystemExit(f"Linux plugin contains non-relocatable RPATH entries: {unsafe}")


def verify_checksum_file(checksums: Path, expected: dict[str, str]) -> None:
    declared: dict[str, str] = {}
    for line in checksums.read_text(encoding="utf-8").splitlines():
        parts = line.split(maxsplit=1)
        if len(parts) != 2 or not re.fullmatch(r"[0-9a-fA-F]{64}", parts[0]):
            raise SystemExit(f"Malformed checksum line in {checksums}: {line!r}")
        name = parts[1].lstrip(" *")
        if name in declared:
            raise SystemExit(f"Duplicate checksum entry in {checksums}: {name}")
        declared[name] = parts[0].casefold()
    if declared != expected:
        raise SystemExit(
            f"Checksum manifest mismatch in {checksums}: expected {expected}, got {declared}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--bds", required=True)
    parser.add_argument("--platform", choices=sorted(SUPPORTED_PLATFORMS), required=True)
    parser.add_argument("--release-dir", type=Path, default=Path("dist/release"))
    args = parser.parse_args()

    if args.slug != SLUG:
        raise SystemExit(f"Unsupported project slug: {args.slug!r}")
    if args.bds not in SUPPORTED_BDS:
        raise SystemExit(f"Unsupported BDS build: {args.bds}")

    stem = f"{args.slug}-v{args.version}-bds-{args.bds}-{args.platform}"
    suffix = ".dll" if args.platform.startswith("windows") else ".so"
    plugin_name = f"endstone_sign_bds_{args.bds.replace('.', '_')}{suffix}"
    raw = args.release_dir / plugin_name
    archive_path = args.release_dir / f"{stem}.zip"
    checksums = args.release_dir / f"{stem}.sha256"
    expected_files = {raw.name, archive_path.name, checksums.name}
    actual_files = {path.name for path in args.release_dir.iterdir() if path.is_file()}
    if actual_files != expected_files:
        raise SystemExit(
            f"Release directory must contain exactly three production assets: "
            f"missing={sorted(expected_files - actual_files)}, "
            f"extra={sorted(actual_files - expected_files)}"
        )
    for path in (raw, archive_path, checksums):
        if path.stat().st_size == 0:
            raise SystemExit(f"Empty release asset: {path}")

    raw_payload = raw.read_bytes()
    verify_native_format(raw_payload, args.platform, str(raw))
    if b"endstone:sign:probe:v1" in raw_payload or b"/signprobe" in raw_payload:
        raise SystemExit("Production plugin contains a diagnostic probe command/service marker")
    if args.platform == "linux-x64":
        verify_linux_runtime(raw)
    verify_checksum_file(
        checksums,
        {raw.name: sha256_file(raw), archive_path.name: sha256_file(archive_path)},
    )

    root = f"{stem}/"
    with ZipFile(archive_path) as archive:
        bad = archive.testzip()
        if bad:
            raise SystemExit(f"Corrupt ZIP member: {bad}")
        members = [item.filename for item in archive.infolist() if not item.is_dir()]
        if len(members) != len(set(members)):
            raise SystemExit("Release archive contains duplicate file names")
        unsafe = [name for name in members if not safe_archive_path(name)]
        if unsafe:
            raise SystemExit(f"Release archive contains unsafe paths: {unsafe}")
        if any(not name.startswith(root) for name in members):
            raise SystemExit("Release archive must have exactly one versioned root directory")

        required = {
            f"{root}plugins/{plugin_name}",
            f"{root}include/endstone_sign/sign_api.h",
            f"{root}include/endstone_sign/live_service.h",
            f"{root}python/endstone_sign/__init__.py",
            f"{root}docs/API.md",
            f"{root}docs/ARCHITECTURE.md",
            f"{root}examples/cpp/plugin_integration_examples.cpp",
            f"{root}examples/python/full_sign_control.py",
            f"{root}README.md",
            f"{root}LICENSE",
            f"{root}CHANGELOG.md",
            f"{root}SOURCE_RELEASE.json",
            f"{root}compatibility/versions.json",
            f"{root}PACKAGE_MANIFEST.json",
        }
        missing = required.difference(members)
        if missing:
            raise SystemExit(f"Release archive is missing production files: {sorted(missing)}")

        forbidden_markers = (
            "/sign_api_tester_plugin/",
            "/endstone_sign_tester/",
            "/native/probes/",
            "/tools/validate_stage_probe_report.py",
            "/tools/validate_full_system_acceptance.py",
            "/docs/STAGE_PROBE.md",
        )
        forbidden = [
            name
            for name in members
            if name.endswith(".whl")
            or "_endstone_sign_live" in name
            or "live_probe_service" in name
            or any(marker in name for marker in forbidden_markers)
        ]
        if forbidden:
            raise SystemExit(f"Production archive contains diagnostic payloads: {forbidden}")

        archived_plugin = archive.read(f"{root}plugins/{plugin_name}")
        if archived_plugin != raw_payload:
            raise SystemExit("Standalone plugin does not match the SDK archive plugin")

        manifest = json.loads(archive.read(f"{root}PACKAGE_MANIFEST.json"))
        if manifest.get("version") != args.version or manifest.get("platform") != args.platform:
            raise SystemExit("PACKAGE_MANIFEST release identity mismatch")
        if manifest.get("primary_plugin") != f"plugins/{plugin_name}":
            raise SystemExit("PACKAGE_MANIFEST primary plugin mismatch")
        if "tester_wheel" in manifest:
            raise SystemExit("Production PACKAGE_MANIFEST must not declare a tester wheel")
        records = manifest.get("files")
        if not isinstance(records, list):
            raise SystemExit("PACKAGE_MANIFEST files must be a list")
        expected_payloads = {
            name[len(root) :]
            for name in members
            if name != f"{root}PACKAGE_MANIFEST.json"
        }
        by_path = {
            record.get("path"): record
            for record in records
            if isinstance(record, dict) and isinstance(record.get("path"), str)
        }
        if set(by_path) != expected_payloads:
            raise SystemExit("PACKAGE_MANIFEST file set does not match archive contents")
        for relative, record in by_path.items():
            payload = archive.read(f"{root}{relative}")
            if record.get("size") != len(payload) or record.get("sha256") != sha256_bytes(payload):
                raise SystemExit(f"PACKAGE_MANIFEST digest mismatch for {relative}")

        packaged_modules = {
            name[len(f"{root}python/") :]
            for name in members
            if name.startswith(f"{root}python/endstone_sign/")
        }
        missing_modules = EXPECTED_API_MODULES.difference(packaged_modules)
        if missing_modules:
            raise SystemExit(f"SDK is missing Python reference modules: {sorted(missing_modules)}")

    print(f"Verified production release assets for {args.platform}: {raw.name}, {archive_path.name}, {checksums.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
