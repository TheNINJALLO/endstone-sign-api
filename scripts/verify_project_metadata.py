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
tester_automation = text(
    "examples/python/sign_api_tester_plugin/src/endstone_sign_tester/automation.py"
)
tester_default_config = text(
    "examples/python/sign_api_tester_plugin/src/endstone_sign_tester/default-config.toml"
)
live_bindings = text("src/live_python_bindings.cpp")
live_probe_service = text("src/live_probe_service.cpp")
readme = text("README.md")
readme_banner = text("docs/assets/banner.svg")
workflow = text(".github/workflows/ci.yml")
release_workflow = text(".github/workflows/release.yml")
generated = text("include/endstone_sign/generated/native_manifest_data.h")
experimental_identity = text("cmake/experimental_runtime_identity.h.in")
version_header = text("include/endstone_sign/version.h")
acceptance_validator = text("tools/validate_full_system_acceptance.py")

release = source.get("version")
expect(source.get("name") == "endstone-sign-api", "SOURCE_RELEASE name")
expect(release == "0.2.1-alpha.2", "SOURCE_RELEASE version")
expect(source.get("service") == "endstone:sign:v2", "SOURCE_RELEASE service")
expect(source.get("service_abi") == 2, "SOURCE_RELEASE service ABI")
expect(source.get("official_bds_packages") == ["1.26.33.1"], "exact official BDS package")
expect(source.get("runtime_bds") == ["1.26.33", "26.33"], "exact runtime BDS values")
expect(source.get("endstone_tags") == ["v0.11.6"], "exact Endstone tag")

match = re.search(r"project\(endstone_sign VERSION ([0-9.]+)", cmake)
expect(bool(match) and match.group(1) == "0.2.1", "CMake project version")
expect('set(ENDSTONE_BDS_BUILD "1.26.33"' in cmake, "CMake BDS runtime target")
expect('set(ENDSTONE_BDS_PACKAGE "1.26.33.1"' in cmake, "CMake BDS package target")
expect('GIT_TAG v0.11.6' in cmake, "CMake Endstone tag")
expect('version = "0.2.1a2"' in pyproject, "Python project version")
expect('__version__ = "0.2.1a2"' in init, "Python package version")
expect('version = "0.2.1a2"' in tester_pyproject, "tester wheel version")
expect('version = "0.2.1a2"' in tester_plugin, "tester plugin version")
expect('module.attr("__version__") = ENDSTONE_SIGN_PYTHON_VERSION' in live_bindings,
       "live bridge build-derived version")
expect('out["supported_release"] = caps.supportedRelease()' in live_bindings,
       "live bridge supported release status")
expect('ENDSTONE_SIGN_PYTHON_VERSION="${ENDSTONE_SIGN_PYTHON_VERSION}"' in cmake,
       "CMake live bridge PEP 440 version definition")
expect('module.def("place"' in live_bindings, "live bridge blank placement binding")
for binding in (
    "set_extended_text",
    "set_editor_lock",
    "replace",
    "clone",
    "move",
    "probe_atomic_rejection",
    "probe_api_event_cancellation",
    "add_event_listener",
    "remove_event_listener",
):
    expect(
        f'module.def("{binding}"' in live_bindings,
        f"live bridge full-system binding: {binding}",
    )
expect('loadProbeService(server)' in live_bindings and
       'event.actor.plugin_name' in live_probe_service and
       'std::atomic<bool> active' in live_probe_service,
       "ABI-safe auxiliary API-cancellation probe service")
expect('"default-config.toml"' in tester_pyproject, "tester config package data")
expect('PROBE_COVERAGE' in tester_automation, "automated matrix probe coverage")
expect('materials = [' in tester_default_config and 'kinds = [' in tester_default_config,
       "default automated matrix material/form configuration")
expect('/signprobe (run)<action: SignProbeRunAction>' in tester_plugin,
       "automated matrix command")
expect('/signprobe (accept)<action: SignProbeAcceptAction>' in tester_plugin,
       "strict full-system acceptance command")
expect('RUN_PROBE_PHASES' in tester_plugin and
       '_matrix_run_probe_tick' in tester_plugin and
       'probe_atomic_rejection' in tester_plugin,
       "full-system live run-probe executor")
expect('qualification_passed' in tester_automation,
       "strict full-system qualification verdict")
expect('REQUIRED_CAPABILITIES' in acceptance_validator and
       'full-system acceptance VALID' in acceptance_validator and
       '"--tester-wheel"' in acceptance_validator,
       "strict full-system acceptance validator")
expect('__service_name__ = "endstone:sign:v2"' in init, "Python service name")
expect('__service_abi__ = 2' in init, "Python service ABI")
expect('ReleaseVersion = "0.2.1-alpha.2"' in version_header, "C++ release version")
expect('ServiceName = "endstone:sign:v2"' in version_header, "C++ service name")
expect('ServiceAbiVersion = 2' in version_header, "C++ service ABI")
expect('src="docs/assets/banner.svg"' in readme, "README project banner")
expect("v0.2.1-alpha.2" in readme, "README candidate version")
expect("Endstone Sign API" in readme_banner, "README banner title")
expect("SERVICE ABI V2" in readme_banner, "README banner service ABI")
expect("supportedRelease()" in readme, "README supported native service contract")
expect("plugin_integration_examples.cpp" in readme,
       "README plugin integration examples")

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
    expect(adapter.get("native_service_registration") is True,
           "native service registration")
    expect(adapter.get("supported_native_service_registration") is True,
           "supported native service registration")
    expect(adapter.get("verified_native_service_registration") is False,
           "verified native service registration closed")
    expect(adapter.get("complete_control") is False, "native complete control closed")

for required in (
    'ExecutableSha256 = ""',
    'ExecutableSize = 0',
    'ManifestComplete = false',
    'SymbolsBehaviorVerified = false',
    'DisposableWorldProbePassed = false',
):
    expect(required in generated, f"generated native gate: {required}")
for required, placeholder in (
    ("ExperimentalManifestPlatform", "@ENDSTONE_SIGN_MANIFEST_PLATFORM@"),
    ("ExperimentalBdsPackageVersion", "@ENDSTONE_SIGN_MANIFEST_PACKAGE@"),
    ("ExperimentalRuntimeBdsVersion", "@ENDSTONE_SIGN_MANIFEST_RUNTIME@"),
    ("ExperimentalExecutableSha256",
     "@ENDSTONE_SIGN_MANIFEST_EXECUTABLE_SHA256@"),
    ("ExperimentalExecutableSize", "@ENDSTONE_SIGN_MANIFEST_EXECUTABLE_SIZE@"),
):
    expect(required in experimental_identity and placeholder in experimental_identity,
           f"experimental runtime identity: {required}")
expect("cmake/experimental_runtime_identity.h.in" in cmake,
       "CMake configures experimental runtime identity")
expect("ENDSTONE_SIGN_MANIFEST_EXECUTABLE_SHA256 GET" in cmake,
       "CMake reads experimental executable hash from manifest")
expect("ENDSTONE_SIGN_MANIFEST_EXECUTABLE_SIZE GET" in cmake,
       "CMake reads experimental executable size from manifest")
expect("${CMAKE_CURRENT_BINARY_DIR}/generated" in cmake,
       "sign_api includes generated internal headers")
expect("install(DIRECTORY tools DESTINATION . COMPONENT sign_package" in cmake,
       "exact package installs full-system validator tools")
expect("install(DIRECTORY examples DESTINATION . COMPONENT sign_package" in cmake,
       "exact package installs validator acceptance profile")
verified_bridge = text("src/verified_bds_26_30_adapter.cpp")
expect('#define ENDSTONE_SIGN_VERIFIED_NATIVE_IMPLEMENTATION 1' in verified_bridge and
       'makeVerifiedBds2630SignAdapter' in verified_bridge,
       "verified bridge guarded implementation wrapper")

expected_hashes = {
    "linux-x64": "68c52ababde987741029de091c09cd736fe894bc1fe99cf20f9ed5c659f0c180",
    "windows-x64": "fc6c0ad6f82cfb11c65c6756a1a8e49b21ffa8cc203da587df59df365d82a2ad",
}
expected_executables = {
    "linux-x64": (
        "61995841f21baf9bfab96e0d9b0cb798501dcc9789dab68e496f3b8e3bc83375",
        232842872,
    ),
    "windows-x64": (
        "4a0b867eee6c24310f405410b17e9794441b81ed8f2976cdd4cef54d0c441829",
        207171408,
    ),
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
        stage_probe = manifest.get("stage_probe", {})
        expect("matrix_report_path" in stage_probe,
               f"{platform} activation matrix path gate")
        expect("matrix_report_sha256" in stage_probe,
               f"{platform} activation matrix hash gate")

expect('EXPECTED_TESTER_VERSION = "0.2.1a2"' in
       text("tools/verify_native_manifest.py"),
       "native manifest verifier tester version")

for required in (
    "python scripts/verify_project_metadata.py",
    "python scripts/verify_bds_sign_identifiers.py --platform linux-x64",
    "python tools/verify_native_symbol_candidates.py",
    "python tools/verify_fail_closed.py",
    "--allow-incomplete",
    "python -m unittest discover",
    "ctest --test-dir",
):
    expect(required in workflow, f"workflow contains {required}")
expect("symbol-gate-pending" not in workflow, "workflow has no stale prototype gate")
expect("RELEASE_VERSION: 0.2.1-alpha.2" in workflow, "CI release version")
expect("RELEASE_VERSION: 0.2.1-alpha.2" in release_workflow,
       "tag workflow release version")
expect("ENDSTONE_SIGN_SUPPORTED_NATIVE_RELEASE=ON" in text("scripts/build_exact.py"),
       "exact builder supported release mode")
expect("--prerelease --latest=false" in release_workflow and
       '--title "Endstone Sign API $RELEASE_TAG"' in release_workflow,
       "candidate tag workflow publishes a non-latest prerelease")
expect("python scripts/verify_bds_sign_identifiers.py --platform linux-x64"
       in release_workflow, "tag workflow identifier inventory verification")
expect("python tools/verify_native_symbol_candidates.py" in release_workflow,
       "tag workflow static symbol-candidate ledger verification")

if failures:
    raise SystemExit("metadata verification failed:\n- " + "\n- ".join(failures))
print(f"verified metadata for endstone-sign-api {release}")
