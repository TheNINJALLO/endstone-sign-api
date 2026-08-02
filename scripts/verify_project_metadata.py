#!/usr/bin/env python3
"""Verify synchronized metadata and the production-only stable release surface."""
from __future__ import annotations

import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
failures: list[str] = []


def text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def expect(condition: bool, label: str) -> None:
    if not condition:
        failures.append(label)


source = json.loads(text("SOURCE_RELEASE.json"))
compat = json.loads(text("compatibility/versions.json"))
release = source.get("version")
cmake = text("CMakeLists.txt")
pyproject = text("pyproject.toml")
init = text("python/endstone_sign/__init__.py")
version_header = text("include/endstone_sign/version.h")
plugin = text("src/plugin.cpp")
adapter = text("src/experimental_bds_26_30_adapter.cpp")
builder = text("scripts/build_exact.py")
packager = text("scripts/package_release.py")
asset_verifier = text("scripts/verify_release_assets.py")
combined_verifier = text("scripts/verify_combined_release_assets.py")
readme = text("README.md")
api_doc = text("docs/API.md")
architecture = text("docs/ARCHITECTURE.md")
cpp_examples = text("examples/cpp/README.md")
workflow = text(".github/workflows/ci.yml")
release_workflow = text(".github/workflows/release.yml")
generated = text("include/endstone_sign/generated/native_manifest_data.h")

expect(release == "0.2.1", "SOURCE_RELEASE stable version")
expect(source.get("service") == "endstone:sign:v2", "source service identity")
expect(source.get("service_abi") == 2, "source service ABI")
expect(source.get("platforms") == ["linux-x64"], "Linux-only production platform")
expect(source.get("official_bds_packages") == ["1.26.33.1"], "official BDS package")
expect(source.get("endstone_tags") == ["v0.11.6"], "Endstone version pin")

match = re.search(r"project\(endstone_sign VERSION ([0-9.]+)", cmake)
expect(bool(match) and match.group(1) == release, "CMake project version")
expect('version = "0.2.1"' in pyproject, "Python project stable version")
expect('__version__ = "0.2.1"' in init, "Python package stable version")
expect('ReleaseVersion = "0.2.1"' in version_header, "C++ stable release version")
expect('ServiceName = "endstone:sign:v2"' in version_header, "C++ service name")
expect("ServiceAbiVersion = 2" in version_header, "C++ service ABI")

expect(not (ROOT / "src/live_probe_service.cpp").exists(), "obsolete command service source removed")
expect(not (ROOT / "include/endstone_sign/live_probe_service.h").exists(),
       "obsolete command service header removed")
expect(not (ROOT / "src/live_python_bindings.cpp").exists(),
       "obsolete diagnostic extension source removed")
expect(not (ROOT / "examples/python/sign_api_tester_plugin").exists(),
       "obsolete command plugin removed")
expect("LiveSignProbeService" not in plugin, "production plugin excludes probe provider")
expect("SignProbeServiceName" not in plugin, "production plugin excludes probe registration")
expect("accepted_release &&" in plugin and "complete native control is unavailable" in plugin,
       "accepted release refuses partial-service fallback")
expect("ENDSTONE_SIGN_BUILD_LIVE_PYTHON" not in cmake, "diagnostic bridge build mode removed")
expect("ENDSTONE_SIGN_BUILD_LIVE_PYTHON" not in builder, "exact builder has no diagnostic bridge")
expect("build_test_wheel.py" not in builder, "exact builder does not build tester wheel")
expect("MINIMUM_PYTHON = (3, 11)" in builder, "exact builder supports CPython 3.11+")
expect("ENDSTONE_SIGN_SUPPORTED_NATIVE_RELEASE=ON" in builder, "exact builder enables supported tier")
expect("ENDSTONE_SIGN_ACCEPTED_NATIVE_RELEASE=ON" in builder, "exact builder enables accepted tier")
expect("ENDSTONE_SIGN_ACCEPTED_NATIVE_RELEASE" in cmake, "CMake accepted-release option")
expect("accepted v0.2.1 native release is Linux x86-64 only" in cmake,
       "CMake accepted release is Linux-only")
expect("ENDSTONE_SIGN_ACCEPTED_NATIVE_RELEASE" in adapter, "native accepted-release capability gate")

expect("install(DIRECTORY tools DESTINATION" not in cmake, "SDK excludes activation/probe tools")
expect("install(DIRECTORY examples DESTINATION" not in cmake, "SDK excludes complete test examples tree")
expect("tester_wheel" not in packager, "production manifest excludes tester wheel")
expect("release_wheel" not in packager, "production packaging excludes wheel payload")
expect("exactly three production assets" in asset_verifier, "platform verifier enforces production set")
expect("diagnostic payloads" in asset_verifier, "platform verifier rejects diagnostic payloads")
expect("endstone_sign_tester" not in combined_verifier, "combined verifier excludes tester wheel")

for document, label in (
    (readme, "README"),
    (api_doc, "API guide"),
    (architecture, "architecture guide"),
    (cpp_examples, "C++ examples guide"),
):
    expect("/signprobe" not in document, f"{label} has no probe commands")
    expect("qualification candidate" not in document.casefold(), f"{label} has no candidate language")
expect("v0.2.1" in readme and "v0.2.1-alpha" not in readme, "README stable release identity")
expect("plugin_integration_examples.cpp" in readme, "README production integrations")
expect("registers no player or console commands" in readme, "README headless API command policy")

expect(compat.get("api") == release, "compatibility release")
expect(compat.get("service") == "endstone:sign:v2", "compatibility service")
expect(compat.get("service_abi") == 2, "compatibility ABI")
adapters = compat.get("adapters") or []
expect(len(adapters) == 1, "one compatibility adapter")
if adapters:
    entry = adapters[0]
    expect(entry.get("status") == "stable", "stable adapter status")
    expect(entry.get("runtime_bds") == "26.33", "compatibility runtime")
    expect(entry.get("official_package") == "1.26.33.1", "compatibility package")
    expect(entry.get("endstone") == "0.11.6", "compatibility Endstone")
    expect(entry.get("native_service_registration") is True, "native registration")
    expect(entry.get("supported_native_service_registration") is True, "supported registration")
    expect(entry.get("verified_native_service_registration") is True, "accepted registration")
    expect(entry.get("complete_control") is True, "complete-control stable contract")
    expect(entry.get("known_unavailable_capabilities") == [], "no unavailable stable capabilities")

# A normal source build remains closed. Only scripts/build_exact.py enables the
# exact, accepted release flags after checking the pinned package/runtime.
for required in (
    'ExecutableSha256 = ""',
    "ExecutableSize = 0",
    "ManifestComplete = false",
    "SymbolsBehaviorVerified = false",
    "DisposableWorldProbePassed = false",
):
    expect(required in generated, f"source-default native gate: {required}")

for platform in ("linux-x64", "windows-x64"):
    manifest = json.loads(text(f"native/manifests/{platform}-1.26.33.1.json"))
    expect(manifest.get("status") == "blocked", f"{platform} source manifest remains closed")
    expect(manifest.get("bds_package_version") == "1.26.33.1", f"{platform} manifest package")

expect("RELEASE_VERSION: 0.2.1" in workflow, "CI stable release version")
expect("RELEASE_VERSION: 0.2.1" in release_workflow, "tag workflow stable release version")
expect("verify_release_assets.py" in workflow, "CI verifies production assets")
expect("verify_release_assets.py" in release_workflow, "release verifies production assets")
expect("verify_combined_release_assets.py" in release_workflow, "release verifies combined assets")
expect("*.whl" not in release_workflow, "release workflow publishes no tester wheel")
expect("wheel==" not in workflow and "wheel==" not in release_workflow,
       "exact jobs install no wheel-packaging dependency")
expect("--prerelease --latest=false" not in release_workflow, "stable release is not a prerelease")
expect("--prerelease=true" not in release_workflow, "stable release never enables prerelease state")
expect("--latest" in release_workflow, "stable release is marked latest")

if failures:
    raise SystemExit("metadata verification failed:\n- " + "\n- ".join(failures))
print("verified production metadata for endstone-sign-api 0.2.1")
