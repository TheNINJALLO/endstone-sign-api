from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[2]
PYTHON = sys.executable
VERSION = "0.2.1"
SLUG = "endstone-sign-api"


class SignReleaseToolTests(unittest.TestCase):
    def run_tool(self, name: str, *arguments: str, check: bool = True):
        result = subprocess.run(
            [PYTHON, str(ROOT / "scripts" / name), *arguments],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        if check and result.returncode != 0:
            self.fail(result.stdout)
        return result

    @staticmethod
    def fake_pe() -> bytes:
        payload = bytearray(512)
        payload[:2] = b"MZ"
        payload[0x3C:0x40] = (0x80).to_bytes(4, "little")
        payload[0x80:0x84] = b"PE\0\0"
        payload[0x84:0x86] = (0x8664).to_bytes(2, "little")
        payload[0x94:0x96] = (0xF0).to_bytes(2, "little")
        payload[0x98:0x9A] = (0x20B).to_bytes(2, "little")
        return bytes(payload)

    @staticmethod
    def add_fake_stage(stage: Path) -> None:
        payloads = {
            "plugins/endstone_sign_bds_1_26_33.dll": SignReleaseToolTests.fake_pe(),
            "include/endstone_sign/sign_api.h": b"#pragma once\n",
            "include/endstone_sign/live_service.h": b"#pragma once\n",
            "docs/API.md": b"# API\n",
            "docs/ARCHITECTURE.md": b"# Architecture\n",
            "examples/cpp/plugin_integration_examples.cpp": b"// examples\n",
            "examples/python/full_sign_control.py": b"# example\n",
            "README.md": b"# Endstone Sign API\n",
            "LICENSE": b"Apache-2.0\n",
            "CHANGELOG.md": b"# Changelog\n",
            "SOURCE_RELEASE.json": b'{"version":"0.2.1"}\n',
            "compatibility/versions.json": b'{"api":"0.2.1"}\n',
        }
        for module in (
            "__init__.py",
            "events.py",
            "model.py",
            "native.py",
            "placement.py",
            "schema.py",
            "service.py",
        ):
            payloads[f"python/endstone_sign/{module}"] = b""
        for relative, payload in payloads.items():
            path = stage / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)

    def test_package_release_creates_production_assets_and_manifest(self) -> None:
        scratch = ROOT / "build" / "sign-release-tool-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            workspace = Path(temporary)
            stage = workspace / "stage"
            release = workspace / "release"
            self.add_fake_stage(stage)
            self.run_tool(
                "package_release.py",
                "--project", "sign",
                "--version", VERSION,
                "--bds", "1.26.33",
                "--platform", "windows-x64",
                "--stage", str(stage),
                "--release-dir", str(release),
            )
            stem = f"{SLUG}-v{VERSION}-bds-1.26.33-windows-x64"
            expected = {
                "endstone_sign_bds_1_26_33.dll",
                f"{stem}.zip",
                f"{stem}.sha256",
            }
            self.assertEqual({path.name for path in release.iterdir()}, expected)
            archive = release / f"{stem}.zip"
            with ZipFile(archive) as zf:
                names = {item.filename for item in zf.infolist() if not item.is_dir()}
                self.assertFalse(any(name.endswith(".whl") for name in names))
                self.assertFalse(any("probe" in name.casefold() for name in names))
                manifest = json.loads(zf.read(f"{stem}/PACKAGE_MANIFEST.json"))
                self.assertEqual(manifest["project"], SLUG)
                self.assertEqual(manifest["bds_package"], "1.26.33.1")
                self.assertNotIn("tester_wheel", manifest)
                declared = {entry["path"] for entry in manifest["files"]}
                self.assertIn("plugins/endstone_sign_bds_1_26_33.dll", declared)
            checksums: dict[str, str] = {}
            for line in (release / f"{stem}.sha256").read_text(encoding="utf-8").splitlines():
                digest, name = line.split(maxsplit=1)
                checksums[name.strip()] = digest
            self.assertEqual(len(checksums), 2)
            for name, digest in checksums.items():
                self.assertEqual(hashlib.sha256((release / name).read_bytes()).hexdigest(), digest)
            verified = self.run_tool(
                "verify_release_assets.py",
                "--slug", SLUG,
                "--version", VERSION,
                "--bds", "1.26.33",
                "--platform", "windows-x64",
                "--release-dir", str(release),
            )
            self.assertIn("Verified production release assets", verified.stdout)

    def test_package_release_rejects_unsafe_and_unsupported_inputs(self) -> None:
        scratch = ROOT / "build" / "sign-release-tool-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            stage = Path(temporary) / "stage"
            stage.mkdir()
            unsafe = self.run_tool(
                "package_release.py", "--project", "sign", "--version", "../escape",
                "--bds", "1.26.33", "--platform", "windows-x64",
                "--stage", str(stage), "--release-dir", str(Path(temporary) / "release"),
                check=False,
            )
            self.assertNotEqual(unsafe.returncode, 0)
            self.assertIn("Invalid version value", unsafe.stdout)
            wrong_bds = self.run_tool(
                "package_release.py", "--project", "sign", "--version", VERSION,
                "--bds", "1.26.32", "--platform", "windows-x64",
                "--stage", str(stage), "--release-dir", str(Path(temporary) / "release"),
                check=False,
            )
            self.assertNotEqual(wrong_bds.returncode, 0)
            self.assertIn("Unsupported BDS build", wrong_bds.stdout)

    def test_combined_verifier_requires_exact_three_file_linux_set(self) -> None:
        scratch = ROOT / "build" / "sign-release-tool-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            release = Path(temporary)
            stem = f"{SLUG}-v{VERSION}-bds-1.26.33"
            names = {
                "endstone_sign_bds_1_26_33.so",
                f"{stem}-linux-x64.zip",
                f"{stem}-linux-x64.sha256",
            }
            for name in names:
                (release / name).write_bytes(b"x")
            passed = self.run_tool(
                "verify_combined_release_assets.py",
                "--slug", SLUG,
                "--version", VERSION,
                "--bds", "1.26.33",
                "--release-dir", str(release),
            )
            self.assertIn("Verified 3 release assets", passed.stdout)
            (release / "endstone_sign_tester.whl").write_text("unexpected", encoding="utf-8")
            failed = self.run_tool(
                "verify_combined_release_assets.py",
                "--slug", SLUG,
                "--version", VERSION,
                "--bds", "1.26.33",
                "--release-dir", str(release),
                check=False,
            )
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn("endstone_sign_tester.whl", failed.stdout)


if __name__ == "__main__":
    unittest.main()
