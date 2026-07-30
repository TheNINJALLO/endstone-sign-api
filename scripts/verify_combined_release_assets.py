#!/usr/bin/env python3
"""Verify the exact cross-platform Sign API asset set before publishing."""
from __future__ import annotations

import argparse
import re
from pathlib import Path


SLUG = "endstone-sign-api"
WHEEL_PREFIX = "endstone_sign_tester"


def pep440_version(release: str) -> str:
    match = re.fullmatch(r"(\d+\.\d+\.\d+)(?:-(alpha|beta|rc)\.(\d+))?", release)
    if not match:
        raise SystemExit(f"Unsupported release version: {release!r}")
    base, phase, serial = match.groups()
    if phase is None:
        return base
    return f"{base}{ {'alpha': 'a', 'beta': 'b', 'rc': 'rc'}[phase] }{serial}"


def expected_assets(slug: str, release: str, bds: str) -> set[str]:
    if slug != SLUG:
        raise SystemExit(f"Unsupported project slug: {slug!r}")
    wheel_version = pep440_version(release)
    stem = f"{slug}-v{release}-bds-{bds}"
    plugin_stem = f"endstone_sign_bds_{bds.replace('.', '_')}"
    return {
        f"{plugin_stem}.so",
        f"{stem}-linux-x64.zip",
        f"{stem}-linux-x64.sha256",
        f"{plugin_stem}.dll",
        f"{stem}-windows-x64.zip",
        f"{stem}-windows-x64.sha256",
        f"{WHEEL_PREFIX}-{wheel_version}-cp314-cp314-linux_x86_64.whl",
        f"{WHEEL_PREFIX}-{wheel_version}-cp314-cp314-win_amd64.whl",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--bds", choices=("1.26.33",), required=True)
    parser.add_argument("--release-dir", type=Path, required=True)
    args = parser.parse_args()
    expected = expected_assets(args.slug, args.version, args.bds)
    entries = list(args.release_dir.iterdir()) if args.release_dir.is_dir() else []
    non_files = sorted(path.name for path in entries if not path.is_file())
    actual = {path.name: path.stat().st_size for path in entries if path.is_file()}
    missing = sorted(expected - set(actual))
    extra = sorted(set(actual) - expected)
    if non_files or missing or extra:
        raise SystemExit(
            "Release asset set mismatch: "
            f"missing={missing}, extra={extra}, non_files={non_files}"
        )
    empty = sorted(name for name, size in actual.items() if size <= 0)
    if empty:
        raise SystemExit(f"Release assets are empty: {empty}")
    print(f"Verified {len(actual)} release assets for {args.slug} {args.version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
