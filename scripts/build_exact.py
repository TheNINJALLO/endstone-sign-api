#!/usr/bin/env python3
"""Build, stage, test, and package the exact Sign API Endstone plugin."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_RELEASE = json.loads((ROOT / "SOURCE_RELEASE.json").read_text(encoding="utf-8"))
PROJECT = "sign"
PROJECT_SLUG = "endstone-sign-api"
VERSION = SOURCE_RELEASE["version"]
SUPPORTED_PLATFORMS = {
    value
    for value in SOURCE_RELEASE.get("platforms", [])
    if isinstance(value, str)
}
SUPPORTED_BDS = {
    value
    for value in SOURCE_RELEASE.get("runtime_bds", [])
    if isinstance(value, str) and value.count(".") == 2
}
BDS_PACKAGE = "1.26.33.1"
BUILD_TARGETS = ("sign_api", "_endstone_sign_live")
INSTALL_COMPONENT = "sign_package"
BRIDGE_MODULE = "_endstone_sign_live"
REQUIRED_PYTHON = (3, 14)


def require(program: str, fallbacks: tuple[str, ...] = ()) -> str:
    resolved = shutil.which(program)
    if resolved:
        return resolved
    for candidate in fallbacks:
        if Path(candidate).is_file():
            return str(Path(candidate))
    raise SystemExit(f"Required program was not found: {program}")


def run(command: list[str], *, env: dict[str, str], log_file: Path | None = None) -> None:
    printable = subprocess.list2cmdline(command) if os.name == "nt" else " ".join(command)
    print(f"\n>>> {printable}", flush=True)
    if log_file is None:
        subprocess.run(command, check=True, env=env)
        return

    log_file.parent.mkdir(parents=True, exist_ok=True)
    tail: list[str] = []
    with log_file.open("a", encoding="utf-8", errors="replace") as handle:
        handle.write(f"\n>>> {printable}\n")
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="", flush=True)
            handle.write(line)
            tail.append(line.rstrip("\n"))
            if len(tail) > 500:
                tail.pop(0)
        return_code = process.wait()

    if return_code != 0:
        print("\n========== EXACT BUILD FAILURE TAIL ==========", file=sys.stderr)
        for line in tail[-300:]:
            print(line, file=sys.stderr)
        print(f"========== FULL LOG: {log_file} ==========", file=sys.stderr)
        raise subprocess.CalledProcessError(return_code, command)


def find_toolchain(folder: Path) -> Path:
    matches = list(folder.rglob("conan_toolchain.cmake"))
    if len(matches) != 1:
        raise SystemExit(
            f"Expected one conan_toolchain.cmake, found {len(matches)} in {folder}"
        )
    return matches[0]


def validate_source_release() -> None:
    if SOURCE_RELEASE.get("name") != PROJECT_SLUG:
        raise SystemExit(
            f"SOURCE_RELEASE.json project mismatch: expected {PROJECT_SLUG}, "
            f"got {SOURCE_RELEASE.get('name')}"
        )
    if SUPPORTED_BDS != {"1.26.33"}:
        raise SystemExit(
            "SOURCE_RELEASE.json must declare exact runtime BDS 1.26.33; "
            f"derived {sorted(SUPPORTED_BDS)}"
        )
    if BDS_PACKAGE not in SOURCE_RELEASE.get("official_bds_packages", []):
        raise SystemExit(
            f"SOURCE_RELEASE.json does not declare official package {BDS_PACKAGE}"
        )
    if "v0.11.6" not in SOURCE_RELEASE.get("endstone_tags", []):
        raise SystemExit("SOURCE_RELEASE.json must pin Endstone v0.11.6")
    if SUPPORTED_PLATFORMS != {"linux-x64"}:
        raise SystemExit(
            "SOURCE_RELEASE.json must declare this release as Linux x64 only; "
            f"derived {sorted(SUPPORTED_PLATFORMS)}"
        )


def validate_manifest(platform: str) -> Path:
    path = ROOT / "native" / "manifests" / f"{platform}-{BDS_PACKAGE}.json"
    if not path.is_file():
        raise SystemExit(f"Exact native manifest does not exist: {path}")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "platform": platform,
        "bds_package_version": BDS_PACKAGE,
        "runtime_bds": "26.33",
        "endstone_version": "0.11.6",
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            raise SystemExit(
                f"Native manifest mismatch for {key}: expected {value!r}, "
                f"got {manifest.get(key)!r}"
            )
    return path


def main() -> int:
    validate_source_release()
    parser = argparse.ArgumentParser(
        description="Build an exact BDS 1.26.33 Sign API plugin and test wheel."
    )
    parser.add_argument("--bds", required=True, choices=sorted(SUPPORTED_BDS))
    parser.add_argument("--platform", required=True, choices=sorted(SUPPORTED_PLATFORMS))
    parser.add_argument("--parallel", type=int, default=2)
    parser.add_argument(
        "--server-executable",
        type=Path,
        help=(
            "optional local exact bedrock_server path; enables live identifier "
            "inventory verification without copying the executable"
        ),
    )
    args = parser.parse_args()

    if sys.implementation.name != "cpython" or sys.version_info[:2] != REQUIRED_PYTHON:
        raise SystemExit(
            "The exact native Python bridge must be built with CPython 3.14; "
            f"running {sys.implementation.name} "
            f"{sys.version_info.major}.{sys.version_info.minor}"
        )
    host_windows = os.name == "nt"
    if args.platform.startswith("windows") != host_windows:
        raise SystemExit(f"Platform {args.platform} does not match host OS {os.name}")
    if not 1 <= args.parallel <= 4:
        raise SystemExit("--parallel must be between 1 and 4")
    manifest = validate_manifest(args.platform)
    env = os.environ.copy()

    inventory_check = [
        sys.executable,
        str(ROOT / "scripts" / "verify_bds_sign_identifiers.py"),
        "--platform",
        args.platform,
    ]
    if args.server_executable is not None:
        inventory_check += ["--server-executable", str(args.server_executable)]
    run(inventory_check, env=env)

    build_dir = ROOT / "build-exact" / args.bds / args.platform
    conan_dir = build_dir / "conan"
    stage_dir = ROOT / "dist" / "stage" / f"bds-{args.bds}-{args.platform}"
    release_dir = ROOT / "dist" / "release"
    diagnostics_dir = ROOT / "dist" / "diagnostics" / f"bds-{args.bds}-{args.platform}"
    log_file = diagnostics_dir / "exact-build.log"
    conan_home = ROOT / ".conan2-ci" / args.platform

    for directory in (build_dir, stage_dir, diagnostics_dir, conan_home):
        shutil.rmtree(directory, ignore_errors=True)
    release_dir.mkdir(parents=True, exist_ok=True)

    cmake = require("cmake")
    conan = require("conan")
    ninja = require("ninja", (r"C:\ProgramData\chocolatey\bin\ninja.exe",))
    env["CMAKE_BUILD_PARALLEL_LEVEL"] = str(args.parallel)
    env["CONAN_HOME"] = str(conan_home)

    if host_windows:
        clang_cl = require("clang-cl", (r"C:\Program Files\LLVM\bin\clang-cl.exe",))
        lld_link = require("lld-link", (r"C:\Program Files\LLVM\bin\lld-link.exe",))
        env["PATH"] = str(Path(clang_cl).parent) + os.pathsep + env.get("PATH", "")
        compiler_conf = 'tools.build:compiler_executables={"c":"clang-cl","cpp":"clang-cl"}'
    else:
        clang = require("clang-18")
        clangxx = require("clang++-18")
        lld = require(
            "ld.lld",
            ("/usr/lib/llvm-18/bin/ld.lld", "/usr/bin/ld.lld-18"),
        )
        env["CC"] = clang
        env["CXX"] = clangxx
        env["PATH"] = str(Path(lld).parent) + os.pathsep + env.get("PATH", "")
        compiler_conf = 'tools.build:compiler_executables={"c":"clang-18","cpp":"clang++-18"}'

    run(
        [conan, "remote", "add", "endstone", "https://conan.cloudsmith.io/endstone/conan/", "--force"],
        env=env,
        log_file=log_file,
    )
    run(
        [conan, "remote", "add", "conancenter", "https://center2.conan.io", "--force"],
        env=env,
        log_file=log_file,
    )
    run([conan, "profile", "detect", "--force", "--name", "exact"], env=env, log_file=log_file)

    conan_install = [
        conan,
        "install",
        str(ROOT),
        "--output-folder",
        str(conan_dir),
        "--build=missing",
        "--profile:host",
        "exact",
        "--profile:build",
        "exact",
        "-s:h",
        "build_type=Release",
        "-s:h",
        "compiler.cppstd=20",
        "-o:h",
        f"&:bds_build={args.bds}",
        "-s:b",
        "build_type=Release",
        "-c:h",
        "tools.cmake.cmaketoolchain:generator=Ninja",
        "-c:h",
        compiler_conf,
        "-c:b",
        "tools.cmake.cmaketoolchain:generator=Ninja",
    ]
    if not host_windows:
        conan_install += [
            "-s:h", "compiler=clang", "-s:h", "compiler.version=18",
            "-s:h", "compiler.libcxx=libc++",
        ]
    run(conan_install, env=env, log_file=log_file)
    toolchain = find_toolchain(conan_dir)

    configure = [
        cmake,
        "-S", str(ROOT),
        "-B", str(build_dir),
        "-G", "Ninja",
        "-DCMAKE_BUILD_TYPE=Release",
        f"-DCMAKE_TOOLCHAIN_FILE={toolchain}",
        f"-DCMAKE_MAKE_PROGRAM={ninja}",
        f"-DCMAKE_INSTALL_PREFIX={stage_dir}",
        "-DPYBIND11_FINDPYTHON=ON",
        f"-DPython_EXECUTABLE={sys.executable}",
        "-DENDSTONE_SIGN_BUILD_TESTS=OFF",
        "-DENDSTONE_SIGN_BUILD_SHARED=OFF",
        "-DENDSTONE_SIGN_BUILD_PLUGIN=ON",
        "-DENDSTONE_SIGN_BUILD_NATIVE_2630=ON",
        "-DENDSTONE_SIGN_BUILD_LIVE_PYTHON=ON",
        "-DENDSTONE_SIGN_VERIFIED_NATIVE_BRIDGE=OFF",
        "-DENDSTONE_SIGN_EXPERIMENTAL_NATIVE_BRIDGE=OFF",
        "-DENDSTONE_SIGN_SUPPORTED_NATIVE_RELEASE=ON",
        f"-DENDSTONE_BDS_BUILD={args.bds}",
        f"-DENDSTONE_BDS_PACKAGE={BDS_PACKAGE}",
        f"-DENDSTONE_SIGN_NATIVE_MANIFEST={manifest}",
    ]
    if host_windows:
        configure += [
            f"-DCMAKE_C_COMPILER={clang_cl}",
            f"-DCMAKE_CXX_COMPILER={clang_cl}",
            f"-DCMAKE_LINKER={lld_link}",
        ]
    else:
        configure += [
            f"-DCMAKE_C_COMPILER={clang}",
            f"-DCMAKE_CXX_COMPILER={clangxx}",
            f"-DCMAKE_LINKER={lld}",
        ]

    print(f"Building {PROJECT_SLUG} {VERSION} for BDS {args.bds} ({args.platform})")
    print(f"Targets: {', '.join(BUILD_TARGETS)}; parallel jobs: {args.parallel}")
    run([cmake, "--version"], env=env)
    run([conan, "--version"], env=env)
    run(configure, env=env, log_file=log_file)
    for target in BUILD_TARGETS:
        run(
            [
                cmake, "--build", str(build_dir), "--config", "Release",
                "--target", target, "--parallel", str(args.parallel), "--verbose",
            ],
            env=env,
            log_file=log_file,
        )
    run(
        [cmake, "--install", str(build_dir), "--config", "Release", "--component", INSTALL_COMPONENT],
        env=env,
        log_file=log_file,
    )

    bridge_candidates = [
        path
        for path in (stage_dir / "python").glob(f"{BRIDGE_MODULE}.*")
        if path.is_file() and path.suffix.lower() in {".pyd", ".so"}
    ]
    if len(bridge_candidates) != 1:
        raise SystemExit(
            f"Expected exactly one installed {BRIDGE_MODULE} bridge, found {bridge_candidates}"
        )
    run(
        [
            sys.executable, str(ROOT / "scripts" / "build_test_wheel.py"),
            "--bridge", str(bridge_candidates[0]),
            "--stage-dir", str(stage_dir),
            "--output-dir", str(release_dir),
        ],
        env=env,
        log_file=log_file,
    )
    common = [
        "--project", PROJECT,
        "--version", VERSION,
        "--bds", args.bds,
        "--platform", args.platform,
    ]
    run(
        [
            sys.executable, str(ROOT / "scripts" / "package_release.py"),
            *common, "--stage", str(stage_dir), "--release-dir", str(release_dir),
        ],
        env=env,
        log_file=log_file,
    )
    run(
        [
            sys.executable, str(ROOT / "scripts" / "verify_release_assets.py"),
            "--slug", PROJECT_SLUG, "--version", VERSION, "--bds", args.bds,
            "--platform", args.platform, "--release-dir", str(release_dir),
        ],
        env=env,
        log_file=log_file,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as error:
        print(f"Exact build failed with exit code {error.returncode}.", file=sys.stderr)
        raise SystemExit(error.returncode) from None
