from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts import verify_bds_sign_identifiers as verifier


ROOT = Path(__file__).resolve().parents[2]

class BdsSignIdentifierInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.inventory = verifier.load_inventory()

    def test_committed_inventory_is_bound_and_matches_portable_generators(self) -> None:
        verifier.verify_manifest_bindings(self.inventory)
        verifier.verify_static_generators(self.inventory)

        self.assertEqual(len(self.inventory.identifiers), 36)
        self.assertEqual(len(set(self.inventory.identifiers)), 36)
        self.assertEqual(
            self.inventory.materials["dark_oak"],
            {
                "standing": "minecraft:darkoak_standing_sign",
                "wall": "minecraft:darkoak_wall_sign",
                "hanging": "minecraft:dark_oak_hanging_sign",
            },
        )
        self.assertTrue(
            verifier.FORBIDDEN_ALIASES.isdisjoint(self.inventory.identifiers)
        )

    def test_inventory_rejects_invalid_dark_oak_alias(self) -> None:
        document = json.loads(verifier.DEFAULT_INVENTORY.read_text(encoding="utf-8"))
        document = deepcopy(document)
        document["materials"]["dark_oak"]["standing"] = (
            "minecraft:dark_oak_standing_sign"
        )

        with self.assertRaisesRegex(
            verifier.VerificationError, "selected/generated invalid dark-oak aliases"
        ):
            verifier.validate_inventory_document(document)

    def test_generated_output_rejects_invalid_dark_oak_alias(self) -> None:
        generated = verifier.derive_canonical_materials()
        generated["dark_oak"]["wall"] = "minecraft:dark_oak_wall_sign"

        with self.assertRaisesRegex(
            verifier.VerificationError, "selected/generated invalid dark-oak aliases"
        ):
            verifier.validate_generated_materials(
                "fake generator", generated, self.inventory
            )

    def test_fake_binary_scan_handles_identifiers_across_chunk_boundaries(self) -> None:
        payload = b"prefix\x00" + b"\xff".join(
            identifier.encode("ascii") for identifier in self.inventory.identifiers
        ) + b"\x00suffix"
        identity = verifier.ExecutableIdentity(
            "bedrock_server",
            hashlib.sha256(payload).hexdigest(),
            len(payload),
        )
        with tempfile.TemporaryDirectory() as temporary:
            binary = Path(temporary) / "bedrock_server"
            binary.write_bytes(payload)
            scan = verifier.verify_live_binary(
                binary,
                identity,
                self.inventory.identifiers,
                chunk_size=7,
            )

        self.assertEqual(scan.missing, ())
        self.assertEqual(scan.found, frozenset(self.inventory.identifiers))

    def test_fake_binary_missing_identifier_fails_without_dumping_content(self) -> None:
        private_sentinel = b"PROPRIETARY_SENTINEL_MUST_NOT_BE_REPORTED"
        payload = private_sentinel + b"\x00" + b"\x00".join(
            identifier.encode("ascii")
            for identifier in self.inventory.identifiers[:-1]
        )
        identity = verifier.ExecutableIdentity(
            "bedrock_server",
            hashlib.sha256(payload).hexdigest(),
            len(payload),
        )
        with tempfile.TemporaryDirectory() as temporary:
            binary = Path(temporary) / "bedrock_server"
            binary.write_bytes(payload)
            with self.assertRaises(verifier.VerificationError) as caught:
                verifier.verify_live_binary(
                    binary,
                    identity,
                    self.inventory.identifiers,
                    chunk_size=13,
                )

        message = str(caught.exception)
        self.assertIn(self.inventory.identifiers[-1], message)
        self.assertNotIn(private_sentinel.decode("ascii"), message)

    def test_fake_binary_must_match_bound_identity(self) -> None:
        payload = b"\x00".join(
            identifier.encode("ascii") for identifier in self.inventory.identifiers
        )
        wrong_identity = verifier.ExecutableIdentity(
            "bedrock_server",
            "0" * 64,
            len(payload),
        )
        with tempfile.TemporaryDirectory() as temporary:
            binary = Path(temporary) / "bedrock_server"
            binary.write_bytes(payload)
            with self.assertRaisesRegex(
                verifier.VerificationError, "exact executable SHA-256 mismatch"
            ):
                verifier.verify_live_binary(
                    binary,
                    wrong_identity,
                    self.inventory.identifiers,
                )

    def test_binary_scan_refuses_invalid_alias_selection_before_reading(self) -> None:
        with self.assertRaisesRegex(
            verifier.VerificationError, "selected/generated invalid dark-oak aliases"
        ):
            verifier.scan_binary(
                Path("file-does-not-need-to-exist"),
                ["minecraft:dark_oak_standing_sign"],
            )

    def test_static_only_cli_does_not_claim_live_verification(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "verify_bds_sign_identifiers.py"),
                "--platform",
                "linux-x64",
            ],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("STATIC identifier inventory verification PASSED", result.stdout)
        self.assertIn("LIVE binary identifier verification NOT PERFORMED", result.stdout)


if __name__ == "__main__":
    unittest.main()
