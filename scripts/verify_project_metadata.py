#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
failures: list[str] = []


def expect(condition: bool, message: str) -> None:
    if not condition:
        failures.append(message)


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


source = json.loads(text("SOURCE_RELEASE.json"))
compat = json.loads(text("compatibility/versions.json"))
cmake = text("CMakeLists.txt")
pyproject = text("pyproject.toml")
init = text("python/endstone_sign/__init__.py")
tester_pyproject = text("examples/python/sign_api_tester_plugin/pyproject.toml")
tester_plugin = text(
    "examples/python/sign_api_tester_plugin/src/endstone_sign_tester/plugin.py"
)
live_bindings = text("src/live_python_bindings.cpp")
readme = text("README.md")
workflow = text(".github/workflows/ci.yml")
release_workflow = text(".github/workflows/release.yml")
generated = text("include/endstone_sign/generated/native_manifest_data.h")
version_header = text("include/endstone_sign/version.h")

release = source.get("version")
expect(source.get("name") == "endstone-sign-api", "SOURCE_RELEASE name")
expect(release == "0.2.0-alpha.2", "SOURCE_RELEASE version")
expect(source.get("service") == "endstone:sign:v2", "SOURCE_RELEASE service")
expect(source.get("service_abi") == 2, "SOURCE_RELEASE service ABI")
expect(source.get("official_bds_packages") == ["1.26.33.1"], "exact official BDS package")
expect(source.get("runtime_bds") == ["1.26.33", "26.33"], "exact runtime BDS values")
expect(source.get("endstone_tags") == ["v0.11.6"], "exact Endstone tag")

match = re.search(r"project\(endstone_sign VERSION ([0-9.]+)", cmake)
expect(bool(match) and match.group(1) == "0.2.0", "CMake project version")
expect('set(ENDSTONE_BDS_BUILD "1.26.33"' in cmake, "CMake BDS runtime target")
expect('set(ENDSTONE_BDS_PACKAGE "1.26.33.1"' in cmake, "CMake BDS package target")
expect('GIT_TAG v0.11.6' in cmake, "CMake Endstone tag")
expect('version = "0.2.0a2"' in pyproject, "Python project version")
expect('__version__ = "0.2.0a2"' in init, "Python package version")
expect('version = "0.2.0a2"' in tester_pyproject, "tester wheel version")
expect('version = "0.2.0a2"' in tester_plugin, "tester plugin version")
expect('module.attr("__version__") = "0.2.0a2"' in live_bindings,
       "live bridge version")
expect('__service_name__ = "endstone:sign:v2"' in init, "Python service name")
expect('__service_abi__ = 2' in init, "Python service ABI")
expect('ReleaseVersion = "0.2.0-alpha.2"' in version_header, "C++ release version")
expect('ServiceName = "endstone:sign:v2"' in version_header, "C++ service name")
expect('ServiceAbiVersion = 2' in version_header, "C++ service ABI")
expect("v0.2.0-alpha.2" in readme, "README release tag")
expect("does **not** register" in readme, "README native registration warning")

expect(compat.get("project") == "endstone-sign-api", "compatibility project")
expect(compat.get("api") == release, "compatibility release")
expect(compat.get("service") == "endstone:sign:v2", "compatibility service")
expect(compat.get("service_abi") == 2, "compatibility ABI")
adapters = compat.get("adapters", [])
expect(len(adapters) == 1, "one compatibility adapter")
if adapters:
    adapter = adapters[0]
    expect(adapter.get("runtime_bds") == "26.33", "compatibility runtime")
    expect(adapter.get("official_package") == "1.26.33.1", "compatibility package")
    expect(adapter.get("endstone") == "0.11.6", "compatibility Endstone")
    expect(adapter.get("native_service_registration") is False, "native service registration closed")
    expect(adapter.get("complete_control") is False, "native complete control closed")

for required in (
    'ExecutableSha256 = ""',
    'ExecutableSize = 0',
    'ManifestComplete = false',
    'SymbolsBehaviorVerified = false',
    'DisposableWorldProbePassed = false',
):
    expect(required in generated, f"generated native gate: {required}")
expect(not (ROOT / "src/verified_bds_26_30_adapter.cpp").exists(), "verified bridge must be absent")

expected_hashes = {
    "linux-x64": "68c52ababde987741029de091c09cd736fe894bc1fe99cf20f9ed5c659f0c180",
    "windows-x64": "fc6c0ad6f82cfb11c65c6756a1a8e49b21ffa8cc203da587df59df365d82a2ad",
}
expected_executables = {
    "linux-x64": (
        "61995841f21baf9bfab96e0d9b0cb798501dcc9789dab68e496f3b8e3bc83375",
        232842872,
    ),
    "windows-x64": ("", 0),
}
for platform, expected_hash in expected_hashes.items():
    manifest_path = ROOT / f"native/manifests/{platform}-1.26.33.1.json"
    expect(manifest_path.is_file(), f"{platform} manifest exists")
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        expect(manifest.get("status") == "blocked", f"{platform} manifest blocked")
        expect(manifest.get("archive_sha256") == expected_hash, f"{platform} archive hash")
        executable_hash, executable_size = expected_executables[platform]
        expect(manifest.get("executable", {}).get("sha256") == executable_hash,
               f"{platform} executable hash")
        expect(manifest.get("executable", {}).get("size") == executable_size,
               f"{platform} executable size")
        expect(len(manifest.get("symbols", [])) == 19, f"{platform} exact symbol count")
        expect(all(not entry.get("resolved") for entry in manifest.get("symbols", [])),
               f"{platform} no symbol marked resolved")

for required in (
    "python scripts/verify_project_metadata.py",
    "python tools/verify_fail_closed.py",
    "--allow-incomplete",
    "python -m unittest discover",
    "ctest --test-dir",
):
    expect(required in workflow, f"workflow contains {required}")
expect("symbol-gate-pending" not in workflow, "workflow has no stale prototype gate")
expect("RELEASE_VERSION: 0.2.0-alpha.2" in workflow, "CI release version")
expect("RELEASE_VERSION: 0.2.0-alpha.2" in release_workflow,
       "tag workflow release version")

if failures:
    raise SystemExit("metadata verification failed:\n- " + "\n- ".join(failures))
print(f"verified metadata for endstone-sign-api {release}")
