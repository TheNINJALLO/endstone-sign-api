#!/usr/bin/env python3
"""Package an exact Sign API stage into standalone and complete release assets."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


PROJECTS = {
    "sign": {
        "slug": "endstone-sign-api",
        "plugin_prefix": "endstone_sign_bds_",
        "supported_bds": {"1.26.33"},
    }
}
SUPPORTED_PLATFORMS = {"linux-x64", "windows-x64"}
SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Package exact Sign API build outputs.")
    parser.add_argument("--project", choices=PROJECTS, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--bds", required=True)
    parser.add_argument("--platform", choices=sorted(SUPPORTED_PLATFORMS), required=True)
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--release-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    for label, value in (
        ("version", args.version),
        ("bds", args.bds),
        ("platform", args.platform),
    ):
        if not SAFE_COMPONENT.fullmatch(value):
            raise SystemExit(f"Invalid {label} value: {value!r}")
    info = PROJECTS[args.project]
    if args.bds not in info["supported_bds"]:
        raise SystemExit(
            f"Unsupported BDS build for {info['slug']}: {args.bds}; "
            f"expected one of {sorted(info['supported_bds'])}"
        )

    stage = args.stage.resolve()
    release_dir = args.release_dir.resolve()
    if not stage.is_dir():
        raise SystemExit(f"Install stage does not exist: {stage}")
    if release_dir == stage or release_dir.is_relative_to(stage):
        raise SystemExit("Release directory must not be inside the install stage")

    candidates = [
        path
        for path in stage.rglob("*")
        if path.is_file()
        and path.suffix.lower() in {".dll", ".so"}
        and path.name.startswith(info["plugin_prefix"])
    ]
    if len(candidates) != 1:
        names = ", ".join(str(path) for path in candidates) or "none"
        raise SystemExit(f"Expected exactly one packaged plugin, found {len(candidates)}: {names}")
    plugin = candidates[0]
    expected_suffix = ".dll" if args.platform.startswith("windows") else ".so"
    if plugin.suffix.lower() != expected_suffix:
        raise SystemExit(
            f"Plugin suffix {plugin.suffix!r} does not match platform {args.platform}"
        )
    expected_plugin_name = (
        f"{info['plugin_prefix']}{args.bds.replace('.', '_')}{expected_suffix}"
    )
    if plugin.name != expected_plugin_name:
        raise SystemExit(
            f"Packaged plugin name {plugin.name!r} does not match exact build "
            f"{expected_plugin_name!r}"
        )
    if plugin.stat().st_size == 0:
        raise SystemExit(f"Packaged plugin is empty: {plugin}")

    release_dir.mkdir(parents=True, exist_ok=True)
    release_stem = f"{info['slug']}-v{args.version}-bds-{args.bds}-{args.platform}"
    raw_plugin = release_dir / expected_plugin_name
    shutil.copy2(plugin, raw_plugin)

    manifest_path = stage / "PACKAGE_MANIFEST.json"
    files = []
    for path in sorted(stage.rglob("*")):
        if path.is_file() and path != manifest_path:
            files.append(
                {
                    "path": path.relative_to(stage).as_posix(),
                    "size": path.stat().st_size,
                    "sha256": sha256(path),
                }
            )
    manifest = {
        "schema": 1,
        "project": info["slug"],
        "version": args.version,
        "bds": args.bds,
        "bds_package": "1.26.33.1",
        "endstone": "0.11.6",
        "platform": args.platform,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "primary_plugin": plugin.relative_to(stage).as_posix(),
        "files": files,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    archive = release_dir / f"{release_stem}.zip"
    with ZipFile(archive, "w", compression=ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(stage.rglob("*")):
            if path.is_file():
                zf.write(
                    path,
                    arcname=f"{release_stem}/{path.relative_to(stage).as_posix()}",
                )

    checksums = release_dir / f"{release_stem}.sha256"
    checksums.write_text(
        f"{sha256(raw_plugin)}  {raw_plugin.name}\n"
        f"{sha256(archive)}  {archive.name}\n",
        encoding="utf-8",
    )

    print(raw_plugin)
    print(archive)
    print(checksums)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - command-line safety net
        print(f"packaging failed: {exc}", file=sys.stderr)
        raise
