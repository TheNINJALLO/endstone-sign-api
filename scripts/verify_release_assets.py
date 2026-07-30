#!/usr/bin/env python3
"""Verify one platform's exact Sign API release assets before publication."""
from __future__ import annotations

import argparse
import base64
import configparser
import csv
from email.parser import Parser
import hashlib
from io import BytesIO, StringIO
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
from zipfile import ZipFile


SLUG = "endstone-sign-api"
WHEEL_PREFIX = "endstone_sign_tester"
BRIDGE_MODULE = "_endstone_sign_live"
TESTER_PACKAGE = PurePosixPath("endstone_sign_tester")
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


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_native_format(payload: bytes, platform: str, label: str) -> None:
    if platform.startswith("windows"):
        if len(payload) < 0x40 or not payload.startswith(b"MZ"):
            raise SystemExit(f"Unexpected PE format for {label}")
        pe_offset = int.from_bytes(payload[0x3C:0x40], "little")
        if pe_offset + 26 > len(payload) or payload[pe_offset : pe_offset + 4] != b"PE\0\0":
            raise SystemExit(f"Invalid PE header for {label}")
        if int.from_bytes(payload[pe_offset + 4 : pe_offset + 6], "little") != 0x8664:
            raise SystemExit(f"PE binary is not x86-64: {label}")
        optional_size = int.from_bytes(payload[pe_offset + 20 : pe_offset + 22], "little")
        if optional_size < 2 or int.from_bytes(
            payload[pe_offset + 24 : pe_offset + 26], "little"
        ) != 0x20B:
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


def pep440_version(release: str) -> str:
    match = re.fullmatch(r"(\d+\.\d+\.\d+)(?:-(alpha|beta|rc)\.(\d+))?", release)
    if not match:
        raise SystemExit(f"Unsupported release version: {release!r}")
    base, phase, serial = match.groups()
    if phase is None:
        return base
    return f"{base}{ {'alpha': 'a', 'beta': 'b', 'rc': 'rc'}[phase] }{serial}"


def safe_archive_path(path: str) -> bool:
    candidate = PurePosixPath(path)
    return (
        bool(candidate.parts)
        and "\\" not in path
        and not candidate.is_absolute()
        and ".." not in candidate.parts
    )


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


def verify_record(archive: ZipFile, names: list[str]) -> None:
    record_files = [name for name in names if name.endswith(".dist-info/RECORD")]
    if len(record_files) != 1:
        raise SystemExit(f"Tester wheel must contain one RECORD, found {record_files}")
    rows = list(csv.reader(StringIO(archive.read(record_files[0]).decode("utf-8"))))
    if any(len(row) != 3 for row in rows):
        raise SystemExit("Tester wheel RECORD contains a malformed row")
    recorded = {row[0]: (row[1], row[2]) for row in rows}
    if len(recorded) != len(rows) or set(recorded) != set(names):
        raise SystemExit("Tester wheel RECORD file set does not match archive contents")
    for name in names:
        declared_hash, declared_size = recorded[name]
        if name == record_files[0]:
            if declared_hash or declared_size:
                raise SystemExit("Tester wheel RECORD must not hash itself")
            continue
        payload = archive.read(name)
        digest = base64.urlsafe_b64encode(hashlib.sha256(payload).digest()).rstrip(b"=").decode()
        if declared_hash != f"sha256={digest}" or declared_size != str(len(payload)):
            raise SystemExit(f"Tester wheel RECORD mismatch for {name}")


def verify_wheel(
    payload: bytes,
    *,
    filename: str,
    platform: str,
    version: str,
    expected_bridge: bytes,
) -> None:
    wheel_platform = "win_amd64" if platform.startswith("windows") else "linux_x86_64"
    expected_tag = f"cp314-cp314-{wheel_platform}"
    expected_marker = ".cp314-" if platform.startswith("windows") else ".cpython-314-"
    with ZipFile(BytesIO(payload)) as archive:
        bad = archive.testzip()
        if bad:
            raise SystemExit(f"Corrupt tester wheel member: {bad}")
        names = [item.filename for item in archive.infolist() if not item.is_dir()]
        if len(names) != len(set(names)):
            raise SystemExit("Tester wheel contains duplicate file names")
        unsafe = [name for name in names if not safe_archive_path(name)]
        if unsafe:
            raise SystemExit(f"Tester wheel contains unsafe paths: {unsafe}")
        verify_record(archive, names)

        wheel_files = [name for name in names if name.endswith(".dist-info/WHEEL")]
        if len(wheel_files) != 1:
            raise SystemExit("Tester wheel must contain exactly one WHEEL metadata file")
        wheel_metadata = Parser().parsestr(archive.read(wheel_files[0]).decode("utf-8"))
        if wheel_metadata.get("Root-Is-Purelib") != "false":
            raise SystemExit("Tester wheel with a native bridge cannot be pure Python")
        if wheel_metadata.get_all("Tag", []) != [expected_tag]:
            raise SystemExit(f"Tester wheel tag mismatch: {wheel_metadata.get_all('Tag', [])}")
        if not filename.endswith(f"-{expected_tag}.whl"):
            raise SystemExit(f"Tester wheel filename does not match tag {expected_tag}")

        metadata_files = [name for name in names if name.endswith(".dist-info/METADATA")]
        if len(metadata_files) != 1:
            raise SystemExit("Tester wheel must contain exactly one METADATA file")
        metadata = Parser().parsestr(archive.read(metadata_files[0]).decode("utf-8"))
        if metadata.get("Name") != "endstone-sign-tester":
            raise SystemExit(f"Unexpected tester project name: {metadata.get('Name')!r}")
        if metadata.get("Version") != pep440_version(version):
            raise SystemExit(f"Unexpected tester version: {metadata.get('Version')!r}")
        if metadata.get("Requires-Python") != "==3.14.*":
            raise SystemExit(f"Unexpected Requires-Python: {metadata.get('Requires-Python')!r}")
        if metadata.get_all("Requires-Dist", []) != ["endstone==0.11.6"]:
            raise SystemExit(f"Unexpected tester dependencies: {metadata.get_all('Requires-Dist', [])}")

        entry_files = [name for name in names if name.endswith(".dist-info/entry_points.txt")]
        if len(entry_files) != 1:
            raise SystemExit("Tester wheel must contain exactly one entry_points.txt")
        parser = configparser.ConfigParser()
        parser.optionxform = str
        parser.read_string(archive.read(entry_files[0]).decode("utf-8"))
        if parser.sections() != ["endstone"] or dict(parser["endstone"]) != {
            "sign-tester": "endstone_sign_tester:SignApiTesterPlugin"
        }:
            raise SystemExit("Tester wheel has an unexpected Endstone entry point")

        missing_api = EXPECTED_API_MODULES.difference(names)
        if missing_api:
            raise SystemExit(f"Tester wheel is missing vendored API modules: {sorted(missing_api)}")
        bridges = [
            name
            for name in names
            if PurePosixPath(name).parent == TESTER_PACKAGE
            and PurePosixPath(name).name.startswith(f"{BRIDGE_MODULE}.")
            and PurePosixPath(name).suffix.lower() in {".pyd", ".so"}
        ]
        if len(bridges) != 1:
            raise SystemExit(f"Tester wheel must contain one package-local bridge, found {bridges}")
        bridge_name = PurePosixPath(bridges[0]).name
        if expected_marker not in bridge_name:
            raise SystemExit(f"Tester bridge does not carry the CPython 3.14 ABI marker: {bridge_name}")
        bridge_payload = archive.read(bridges[0])
        verify_native_format(bridge_payload, platform, f"tester bridge {bridge_name}")
        if bridge_payload != expected_bridge:
            raise SystemExit("Tester wheel bridge does not match the exact staged bridge")


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
    raw = args.release_dir / f"endstone_sign_bds_{args.bds.replace('.', '_')}{suffix}"
    archive_path = args.release_dir / f"{stem}.zip"
    checksums = args.release_dir / f"{stem}.sha256"
    wheel_platform = "win_amd64" if args.platform.startswith("windows") else "linux_x86_64"
    wheel = args.release_dir / (
        f"{WHEEL_PREFIX}-{pep440_version(args.version)}-cp314-cp314-{wheel_platform}.whl"
    )
    for path in (raw, archive_path, wheel, checksums):
        if not path.is_file() or path.stat().st_size == 0:
            raise SystemExit(f"Missing or empty release asset: {path}")
    verify_native_format(raw.read_bytes(), args.platform, str(raw))
    verify_checksum_file(
        checksums,
        {
            raw.name: sha256_file(raw),
            archive_path.name: sha256_file(archive_path),
            wheel.name: sha256_file(wheel),
        },
    )

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
        archive_root = f"{stem}/"
        manifests = [name for name in members if name.endswith("/PACKAGE_MANIFEST.json")]
        if manifests != [f"{archive_root}PACKAGE_MANIFEST.json"]:
            raise SystemExit(f"Expected one root PACKAGE_MANIFEST.json, found {manifests}")
        manifest = json.loads(archive.read(manifests[0]))
        expected_fields = {
            "schema": 1,
            "project": args.slug,
            "version": args.version,
            "bds": args.bds,
            "bds_package": "1.26.33.1",
            "endstone": "0.11.6",
            "platform": args.platform,
        }
        for key, value in expected_fields.items():
            if manifest.get(key) != value:
                raise SystemExit(
                    f"Package manifest mismatch for {key}: expected {value!r}, got {manifest.get(key)!r}"
                )

        declared = manifest.get("files")
        if not isinstance(declared, list):
            raise SystemExit("PACKAGE_MANIFEST.json files must be a list")
        declared_members: set[str] = set()
        for entry in declared:
            if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
                raise SystemExit(f"Malformed package manifest entry: {entry!r}")
            relative = entry["path"]
            if not safe_archive_path(relative):
                raise SystemExit(f"Unsafe path in package manifest: {relative}")
            member = archive_root + relative
            if member in declared_members:
                raise SystemExit(f"Duplicate path in package manifest: {relative}")
            declared_members.add(member)
            try:
                payload = archive.read(member)
            except KeyError as error:
                raise SystemExit(f"Manifest file missing from archive: {relative}") from error
            if entry.get("size") != len(payload) or entry.get("sha256") != sha256_bytes(payload):
                raise SystemExit(f"Manifest digest or size mismatch for {relative}")
        actual_payload = set(members) - {manifests[0]}
        if declared_members != actual_payload:
            raise SystemExit(
                "Archive/manifest file-set mismatch; "
                f"missing={sorted(declared_members - actual_payload)}, "
                f"extra={sorted(actual_payload - declared_members)}"
            )

        primary = manifest.get("primary_plugin")
        if not isinstance(primary, str) or archive_root + primary not in declared_members:
            raise SystemExit(f"Invalid primary_plugin: {primary!r}")
        if archive.read(archive_root + primary) != raw.read_bytes():
            raise SystemExit("Raw plugin does not match the primary plugin in the ZIP")
        bundled_wheel = f"{archive_root}plugins/{wheel.name}"
        if manifest.get("tester_wheel") != f"plugins/{wheel.name}":
            raise SystemExit("Package manifest tester_wheel is incorrect")
        if bundled_wheel not in declared_members:
            raise SystemExit("Complete ZIP is missing its tester wheel")
        wheel_payload = archive.read(bundled_wheel)
        if sha256_bytes(wheel_payload) != sha256_file(wheel):
            raise SystemExit("Standalone tester wheel does not match the wheel in the ZIP")

        supported_suffixes = {".dll", ".pyd"} if args.platform.startswith("windows") else {".so"}
        native_members = [
            name
            for name in members
            if PurePosixPath(name).suffix.lower() in {".dll", ".pyd", ".so", ".dylib"}
        ]
        wrong_platform = [
            name for name in native_members if PurePosixPath(name).suffix.lower() not in supported_suffixes
        ]
        if wrong_platform:
            raise SystemExit(f"Archive contains native binaries for the wrong platform: {wrong_platform}")
        for name in native_members:
            verify_native_format(archive.read(name), args.platform, f"archive member {name}")
        python_dir = PurePosixPath(archive_root) / "python"
        bridges = [
            name
            for name in native_members
            if PurePosixPath(name).parent == python_dir
            and PurePosixPath(name).name.startswith(f"{BRIDGE_MODULE}.")
        ]
        if len(bridges) != 1:
            raise SystemExit(f"Expected exactly one staged {BRIDGE_MODULE}, found {bridges}")
        bridge_payload = archive.read(bridges[0])
        verify_wheel(
            wheel_payload,
            filename=wheel.name,
            platform=args.platform,
            version=args.version,
            expected_bridge=bridge_payload,
        )

    verify_wheel(
        wheel.read_bytes(),
        filename=wheel.name,
        platform=args.platform,
        version=args.version,
        expected_bridge=bridge_payload,
    )
    if args.platform == "linux-x64":
        verify_linux_runtime(raw)
    print(f"Verified exact Sign API release assets for {args.platform}: {stem}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
