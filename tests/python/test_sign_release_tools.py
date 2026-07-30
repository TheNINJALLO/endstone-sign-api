from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[2]
PYTHON = sys.executable
VERSION = "0.2.0-alpha.6"
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
        plugin = stage / "plugins" / "endstone_sign_bds_1_26_33.dll"
        plugin.parent.mkdir(parents=True)
        plugin.write_bytes(SignReleaseToolTests.fake_pe())
        bridge = stage / "python" / "_endstone_sign_live.cp314-win_amd64.pyd"
        bridge.parent.mkdir(parents=True)
        bridge_payload = SignReleaseToolTests.fake_pe()
        bridge.write_bytes(bridge_payload)
        wheel = stage / "plugins" / "endstone_sign_tester-0.2.0a6-cp314-cp314-win_amd64.whl"
        dist_info = "endstone_sign_tester-0.2.0a6.dist-info"
        files = {
            "endstone_sign_tester/__init__.py": b"",
            "endstone_sign_tester/plugin.py": b"",
            "endstone_sign_tester/report.py": b"",
            "endstone_sign_tester/automation.py": b"",
            "endstone_sign_tester/default-config.toml": b"schema = 1\n",
            "endstone_sign_tester/_bridge_loader.py": b"",
            "endstone_sign_tester/_endstone_sign_live.cp314-win_amd64.pyd": bridge_payload,
            "endstone_sign/__init__.py": b"",
            "endstone_sign/events.py": b"",
            "endstone_sign/model.py": b"",
            "endstone_sign/native.py": b"",
            "endstone_sign/placement.py": b"",
            "endstone_sign/schema.py": b"",
            "endstone_sign/service.py": b"",
            f"{dist_info}/METADATA": (
                b"Metadata-Version: 2.4\nName: endstone-sign-tester\n"
                b"Version: 0.2.0a6\nRequires-Python: ==3.14.*\n"
                b"Requires-Dist: endstone==0.11.6\n\n"
            ),
            f"{dist_info}/WHEEL": (
                b"Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: false\n"
                b"Tag: cp314-cp314-win_amd64\n\n"
            ),
            f"{dist_info}/entry_points.txt": (
                b"[endstone]\nsign-tester = endstone_sign_tester:SignApiTesterPlugin\n"
            ),
        }
        record_name = f"{dist_info}/RECORD"
        output = io.StringIO()
        writer = csv.writer(output, lineterminator="\n")
        for name, payload in files.items():
            digest = base64.urlsafe_b64encode(hashlib.sha256(payload).digest()).rstrip(b"=").decode()
            writer.writerow((name, f"sha256={digest}", str(len(payload))))
        writer.writerow((record_name, "", ""))
        files[record_name] = output.getvalue().encode()
        with ZipFile(wheel, "w") as archive:
            for name, payload in files.items():
                archive.writestr(name, payload)

    def test_package_release_creates_exact_assets_and_manifest(self) -> None:
        scratch = ROOT / "build" / "sign-release-tool-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            workspace = Path(temporary)
            stage = workspace / "stage"
            release = workspace / "release"
            self.add_fake_stage(stage)
            self.run_tool(
                "package_release.py",
                "--project",
                "sign",
                "--version",
                VERSION,
                "--bds",
                "1.26.33",
                "--platform",
                "windows-x64",
                "--stage",
                str(stage),
                "--release-dir",
                str(release),
            )
            stem = f"{SLUG}-v{VERSION}-bds-1.26.33-windows-x64"
            expected = {
                "endstone_sign_bds_1_26_33.dll",
                f"{stem}.zip",
                f"{stem}.sha256",
                "endstone_sign_tester-0.2.0a6-cp314-cp314-win_amd64.whl",
            }
            self.assertEqual({path.name for path in release.iterdir()}, expected)
            archive = release / f"{stem}.zip"
            with ZipFile(archive) as zf:
                manifest_name = f"{stem}/PACKAGE_MANIFEST.json"
                manifest = json.loads(zf.read(manifest_name))
                self.assertEqual(manifest["project"], SLUG)
                self.assertEqual(manifest["bds_package"], "1.26.33.1")
                self.assertEqual(manifest["endstone"], "0.11.6")
                declared = {entry["path"] for entry in manifest["files"]}
                self.assertIn("plugins/endstone_sign_bds_1_26_33.dll", declared)
                self.assertIn(manifest["tester_wheel"], declared)
            checksums = {}
            for line in (release / f"{stem}.sha256").read_text(encoding="utf-8").splitlines():
                digest, name = line.split(maxsplit=1)
                checksums[name.strip()] = digest
            self.assertEqual(len(checksums), 3)
            for name, digest in checksums.items():
                self.assertEqual(hashlib.sha256((release / name).read_bytes()).hexdigest(), digest)
            verified = self.run_tool(
                "verify_release_assets.py",
                "--slug",
                SLUG,
                "--version",
                VERSION,
                "--bds",
                "1.26.33",
                "--platform",
                "windows-x64",
                "--release-dir",
                str(release),
            )
            self.assertIn("Verified exact Sign API release assets", verified.stdout)

    def test_package_release_rejects_unsafe_and_unsupported_inputs(self) -> None:
        scratch = ROOT / "build" / "sign-release-tool-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            stage = Path(temporary) / "stage"
            stage.mkdir()
            unsafe = self.run_tool(
                "package_release.py",
                "--project",
                "sign",
                "--version",
                "../escape",
                "--bds",
                "1.26.33",
                "--platform",
                "windows-x64",
                "--stage",
                str(stage),
                "--release-dir",
                str(Path(temporary) / "release"),
                check=False,
            )
            self.assertNotEqual(unsafe.returncode, 0)
            self.assertIn("Invalid version value", unsafe.stdout)

            wrong_bds = self.run_tool(
                "package_release.py",
                "--project",
                "sign",
                "--version",
                VERSION,
                "--bds",
                "1.26.32",
                "--platform",
                "windows-x64",
                "--stage",
                str(stage),
                "--release-dir",
                str(Path(temporary) / "release"),
                check=False,
            )
            self.assertNotEqual(wrong_bds.returncode, 0)
            self.assertIn("Unsupported BDS build", wrong_bds.stdout)

            wrong_plugin = stage / "plugins" / "endstone_sign_bds_wrong.dll"
            wrong_plugin.parent.mkdir(parents=True)
            wrong_plugin.write_bytes(self.fake_pe())
            wrong_name = self.run_tool(
                "package_release.py",
                "--project",
                "sign",
                "--version",
                VERSION,
                "--bds",
                "1.26.33",
                "--platform",
                "windows-x64",
                "--stage",
                str(stage),
                "--release-dir",
                str(Path(temporary) / "wrong-name-release"),
                check=False,
            )
            self.assertNotEqual(wrong_name.returncode, 0)
            self.assertIn("does not match exact build", wrong_name.stdout)

    def test_combined_verifier_requires_exact_eight_file_set(self) -> None:
        scratch = ROOT / "build" / "sign-release-tool-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            release = Path(temporary)
            stem = f"{SLUG}-v{VERSION}-bds-1.26.33"
            names = {
                "endstone_sign_bds_1_26_33.so",
                f"{stem}-linux-x64.zip",
                f"{stem}-linux-x64.sha256",
                "endstone_sign_bds_1_26_33.dll",
                f"{stem}-windows-x64.zip",
                f"{stem}-windows-x64.sha256",
                "endstone_sign_tester-0.2.0a6-cp314-cp314-linux_x86_64.whl",
                "endstone_sign_tester-0.2.0a6-cp314-cp314-win_amd64.whl",
            }
            for name in names:
                (release / name).write_bytes(b"x")
            passed = self.run_tool(
                "verify_combined_release_assets.py",
                "--slug",
                SLUG,
                "--version",
                VERSION,
                "--bds",
                "1.26.33",
                "--release-dir",
                str(release),
            )
            self.assertIn("Verified 8 release assets", passed.stdout)
            (release / "extra.txt").write_text("unexpected", encoding="utf-8")
            failed = self.run_tool(
                "verify_combined_release_assets.py",
                "--slug",
                SLUG,
                "--version",
                VERSION,
                "--bds",
                "1.26.33",
                "--release-dir",
                str(release),
                check=False,
            )
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn("extra=['extra.txt']", failed.stdout)


if __name__ == "__main__":
    unittest.main()
