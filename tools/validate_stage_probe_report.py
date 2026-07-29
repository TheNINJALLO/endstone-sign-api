#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_native_manifest import REQUIRED_PROBES  # noqa: E402

HEX64 = re.compile(r"^[0-9a-f]{64}$")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    data = json.loads(args.report.read_text(encoding="utf-8"))
    failures: list[str] = []
    if data.get("schema") != 1:
        failures.append("schema")
    if data.get("bds_package_version") != "1.26.33.1":
        failures.append("bds_package_version")
    if data.get("endstone_version") != "0.11.6":
        failures.append("endstone_version")
    for key in ("server_executable_sha256", "plugin_sha256", "log_sha256", "world_backup_sha256"):
        if not HEX64.fullmatch(str(data.get(key, ""))):
            failures.append(key)
    for key in ("platform", "world_seed", "started_at_utc", "completed_at_utc", "operator"):
        if not data.get(key):
            failures.append(key)
    results = data.get("results", {})
    if set(results) != REQUIRED_PROBES:
        failures.append("exact result set")
    for probe in sorted(REQUIRED_PROBES):
        entry = results.get(probe, {})
        if entry.get("passed") is not True:
            failures.append(f"results.{probe}.passed")
        if not entry.get("evidence"):
            failures.append(f"results.{probe}.evidence")
    if data.get("passed") is not True:
        failures.append("passed")
    if failures:
        print("stage probe INVALID")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(hashlib.sha256(args.report.read_bytes()).hexdigest())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
