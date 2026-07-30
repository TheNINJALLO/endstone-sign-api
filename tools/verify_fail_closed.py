#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
header = (ROOT / "include/endstone_sign/generated/native_manifest_data.h").read_text(encoding="utf-8")
plugin = (ROOT / "src/plugin.cpp").read_text(encoding="utf-8")
adapter = (ROOT / "src/bds_26_30_adapter.cpp").read_text(encoding="utf-8")
experimental_adapter = (ROOT / "src/experimental_bds_26_30_adapter.cpp").read_text(
    encoding="utf-8"
)
cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
failures: list[str] = []
for required in (
    'ExecutableSha256 = ""',
    'ExecutableSize = 0',
    'ManifestComplete = false',
    'SymbolsBehaviorVerified = false',
    'DisposableWorldProbePassed = false',
):
    if required not in header:
        failures.append(f"generated header is not closed: {required}")
if "if (!caps.completeControl())" not in plugin or "refused to register" not in plugin:
    failures.append("plugin service-registration refusal is missing")
if "BinaryIdentityMismatch" not in adapter or "SymbolValidationFailed" not in adapter:
    failures.append("guarded native adapter failure modes are missing")
if (
    "structural Sign mutation requires the exact BDS executable" not in experimental_adapter
    or experimental_adapter.count("return binaryIdentityMismatch();") < 4
    or "result.capture = structural_mutation_gate" not in experimental_adapter
    or "force placement is disabled" not in experimental_adapter
    or "experimental removal requires a nonzero expected revision" not in experimental_adapter
):
    failures.append("experimental structural mutation hash gates are missing")
if "ENDSTONE_SIGN_VERIFIED_NATIVE_BRIDGE" not in cmake:
    failures.append("verified native bridge option is missing")
if (ROOT / "src/verified_bds_26_30_adapter.cpp").exists():
    failures.append("unverified native bridge source is present")
if failures:
    raise SystemExit("fail-closed verification failed:\n- " + "\n- ".join(failures))
print("native Sign API boundary is fail-closed")
