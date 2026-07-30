from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools import verify_native_symbol_candidates as auditor


ROOT = Path(__file__).resolve().parents[2]
PYTHON = sys.executable


class NativeSymbolCandidateTests(unittest.TestCase):
    SEGMENT_OFFSET = 0x200
    SEGMENT_RVA = 0x1000
    SEGMENT_SIZE = 0x400
    DECOY_OFFSET = 0x700
    DECOY_RVA = 0x2000
    DECOY_SIZE = 0x100

    @staticmethod
    def _candidate_payload(marker: int, size: int) -> bytes:
        prefix = bytes([marker]) + bytes(range(1, 24))
        return prefix + bytes([marker ^ 0x55]) * (size - len(prefix))

    def make_fixture(
        self,
        *,
        candidate_executable: bool = True,
        duplicate_fingerprint: bool = False,
        duplicate_in_non_executable_segment: bool = False,
        overlapping_load_segment: bool = False,
    ) -> tuple[bytes, dict[str, object]]:
        definitions = (
            (
                "alpha6_set_message",
                "set_message_for_server_scripting",
                "SetMessage",
                self.SEGMENT_RVA + 0x40,
                40,
                0xF1,
            ),
            (
                "alpha6_get_raw_message",
                "get_raw_message",
                "GetRawMessage",
                self.SEGMENT_RVA + 0xC0,
                39,
                0xF2,
            ),
            (
                "alpha6_is_string_message",
                "",
                "IsStringMessage",
                self.SEGMENT_RVA + self.SEGMENT_SIZE - 27,
                27,
                0xF3,
            ),
        )
        program_count = 3 if duplicate_in_non_executable_segment else 2
        payload = bytearray(0xB00 if program_count == 3 else 0x900)
        identity = bytearray(16)
        identity[:4] = b"\x7fELF"
        identity[4:7] = bytes((2, 1, 1))
        header = auditor.ELF_HEADER.pack(
            bytes(identity),
            auditor.ET_DYN,
            auditor.EM_X86_64,
            1,
            0,
            auditor.ELF_HEADER.size,
            0,
            0,
            auditor.ELF_HEADER.size,
            auditor.PROGRAM_HEADER.size,
            program_count,
            0,
            0,
            0,
        )
        payload[: len(header)] = header
        headers = [
            auditor.PROGRAM_HEADER.pack(
                auditor.PT_LOAD,
                5 if candidate_executable else 4,
                self.SEGMENT_OFFSET,
                self.SEGMENT_RVA,
                0,
                self.SEGMENT_SIZE,
                self.SEGMENT_SIZE,
                0x100,
            ),
            auditor.PROGRAM_HEADER.pack(
                auditor.PT_LOAD,
                5,
                self.DECOY_OFFSET,
                self.SEGMENT_RVA + 0x100
                if overlapping_load_segment
                else self.DECOY_RVA,
                0,
                self.DECOY_SIZE,
                self.DECOY_SIZE,
                0x100,
            ),
        ]
        if program_count == 3:
            headers.append(
                auditor.PROGRAM_HEADER.pack(
                    auditor.PT_LOAD,
                    4,
                    0x900,
                    0x3000,
                    0,
                    0x100,
                    0x100,
                    0x100,
                )
            )
        for index, program_header in enumerate(headers):
            start = auditor.ELF_HEADER.size + index * auditor.PROGRAM_HEADER.size
            payload[start : start + len(program_header)] = program_header

        raw_candidates: list[dict[str, object]] = []
        function_payloads: dict[str, bytes] = {}
        for candidate_id, related, constant, rva, size, marker in definitions:
            function = self._candidate_payload(marker, size)
            file_offset = self.SEGMENT_OFFSET + (rva - self.SEGMENT_RVA)
            payload[file_offset : file_offset + size] = function
            function_payloads[candidate_id] = function
            raw_candidates.append(
                {
                    "id": candidate_id,
                    "related_manifest_symbol": related,
                    "adapter_constant": constant,
                    "rva": rva,
                    "size": size,
                    "sha256": hashlib.sha256(function).hexdigest(),
                    "fingerprint_hex": function[:24].hex(),
                }
            )
        if duplicate_fingerprint:
            duplicate = function_payloads["alpha6_set_message"][:24]
            start = self.DECOY_OFFSET + 0x20
            payload[start : start + len(duplicate)] = duplicate
        if duplicate_in_non_executable_segment:
            duplicate = function_payloads["alpha6_set_message"][:24]
            payload[0x920 : 0x920 + len(duplicate)] = duplicate

        binary = bytes(payload)
        document: dict[str, object] = {
            "schema": 1,
            "document_type": auditor.DOCUMENT_TYPE,
            "activation_eligible": False,
            "claim": auditor.CLAIM,
            "platform": "linux-x64",
            "bds_package_version": "1.26.33.1",
            "runtime_bds": "26.33",
            "executable": {
                "filename": "bedrock_server",
                "elf_type": "ET_DYN",
                "sha256": hashlib.sha256(binary).hexdigest(),
                "size": len(binary),
            },
            "candidates": raw_candidates,
        }
        return binary, document

    @staticmethod
    def make_manifest(document: dict[str, object]) -> dict[str, object]:
        executable = deepcopy(document["executable"])
        assert isinstance(executable, dict)
        executable.pop("elf_type")
        return {
            "status": "blocked",
            "platform": document["platform"],
            "bds_package_version": document["bds_package_version"],
            "runtime_bds": document["runtime_bds"],
            "executable": executable,
            "symbols": [
                {
                    "id": symbol,
                    "rva": 0,
                    "fingerprint_hex": "",
                    "resolved": False,
                    "unique": False,
                    "signature_verified": False,
                    "behavior_verified": False,
                }
                for symbol in sorted(auditor.REQUIRED_MANIFEST_SYMBOLS)
            ],
        }

    @staticmethod
    def make_adapter(document: dict[str, object]) -> str:
        lines: list[str] = []
        candidates = document["candidates"]
        assert isinstance(candidates, list)
        for candidate in candidates:
            assert isinstance(candidate, dict)
            prefix = candidate["adapter_constant"]
            lines.extend(
                (
                    f"static constexpr std::uintptr_t {prefix}Rva = "
                    f"0x{candidate['rva']:X};",
                    f"static constexpr std::size_t {prefix}Size = {candidate['size']};",
                    f"static constexpr std::string_view {prefix}Sha256 =",
                    f'    "{candidate["sha256"]}";',
                )
            )
        return "\n".join(lines) + "\n"

    def verify_fixture(self, binary: bytes, document: dict[str, object]) -> None:
        ledger = auditor.validate_ledger_document(document)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bedrock_server"
            path.write_bytes(binary)
            auditor.verify_executable(path, ledger)

    def test_committed_ledger_is_bound_but_never_activation_eligible(self) -> None:
        ledger = auditor.load_ledger()
        auditor.verify_manifest_binding(ledger)
        auditor.verify_adapter_bindings(ledger)
        self.assertEqual(len(ledger.candidates), 3)

        result = subprocess.run(
            [PYTHON, "tools/verify_native_symbol_candidates.py"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("STATIC CANDIDATE ledger validation PASSED", result.stdout)
        self.assertIn("EXACT ELF BYTE AUDIT NOT PERFORMED", result.stdout)
        self.assertIn("no ABI, signature, or behavior proof", result.stdout)
        self.assertIn("activation remains CLOSED", result.stdout)

    def test_synthetic_exact_elf_passes_with_distinct_file_offsets_and_end_boundary(
        self,
    ) -> None:
        binary, document = self.make_fixture()
        candidates = document["candidates"]
        assert isinstance(candidates, list)
        final_candidate = candidates[-1]
        assert isinstance(final_candidate, dict)
        self.assertNotEqual(self.SEGMENT_OFFSET, self.SEGMENT_RVA)
        self.assertEqual(
            final_candidate["rva"] + final_candidate["size"],
            self.SEGMENT_RVA + self.SEGMENT_SIZE,
        )
        self.verify_fixture(binary, document)

    def test_identity_mismatch_fails_before_candidate_claim(self) -> None:
        binary, document = self.make_fixture()
        executable = document["executable"]
        assert isinstance(executable, dict)
        executable["sha256"] = "0" * 64
        ledger = auditor.validate_ledger_document(document)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bedrock_server"
            path.write_bytes(binary)
            with self.assertRaisesRegex(
                auditor.AuditError, "executable SHA-256 mismatch"
            ):
                auditor.verify_executable(path, ledger)

    def test_tampered_function_fails_full_range_hash(self) -> None:
        binary, document = self.make_fixture()
        tampered = bytearray(binary)
        candidates = document["candidates"]
        assert isinstance(candidates, list) and isinstance(candidates[0], dict)
        first = candidates[0]
        file_offset = self.SEGMENT_OFFSET + int(first["rva"]) - self.SEGMENT_RVA
        tampered[file_offset + int(first["size"]) - 1] ^= 0x01
        executable = document["executable"]
        assert isinstance(executable, dict)
        executable["sha256"] = hashlib.sha256(tampered).hexdigest()
        ledger = auditor.validate_ledger_document(document)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bedrock_server"
            path.write_bytes(tampered)
            with self.assertRaisesRegex(
                auditor.AuditError, "full byte-range SHA-256 mismatch"
            ):
                auditor.verify_executable(path, ledger)

    def test_candidate_must_be_in_an_executable_load_segment(self) -> None:
        binary, document = self.make_fixture(candidate_executable=False)
        ledger = auditor.validate_ledger_document(document)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bedrock_server"
            path.write_bytes(binary)
            with self.assertRaisesRegex(
                auditor.AuditError, "exactly one.*executable PT_LOAD"
            ):
                auditor.verify_executable(path, ledger)

    def test_fingerprint_must_be_unique_across_executable_segments(self) -> None:
        binary, document = self.make_fixture(duplicate_fingerprint=True)
        ledger = auditor.validate_ledger_document(document)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bedrock_server"
            path.write_bytes(binary)
            with self.assertRaisesRegex(
                auditor.AuditError, "fingerprint is not unique"
            ):
                auditor.verify_executable(path, ledger)

    def test_duplicate_fingerprint_in_non_executable_segment_is_ignored(self) -> None:
        binary, document = self.make_fixture(duplicate_in_non_executable_segment=True)
        self.verify_fixture(binary, document)

    def test_overlapping_load_segments_are_rejected_as_ambiguous(self) -> None:
        binary, document = self.make_fixture(overlapping_load_segment=True)
        ledger = auditor.validate_ledger_document(document)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bedrock_server"
            path.write_bytes(binary)
            with self.assertRaisesRegex(
                auditor.AuditError, "virtual memory ranges overlap"
            ):
                auditor.verify_executable(path, ledger)

    def test_ledger_rejects_activation_fields_and_duplicate_json_keys(self) -> None:
        _binary, document = self.make_fixture()
        document["status"] = "verified"
        with self.assertRaisesRegex(auditor.AuditError, "unexpected status"):
            auditor.validate_ledger_document(document)

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "ledger.json"
            path.write_text('{"schema":1,"schema":1}', encoding="utf-8")
            with self.assertRaisesRegex(auditor.AuditError, "duplicate key 'schema'"):
                auditor.load_ledger(path)

    def test_adapter_binding_and_blocked_manifest_drift_fail_closed(self) -> None:
        _binary, document = self.make_fixture()
        ledger = auditor.validate_ledger_document(document)
        manifest = self.make_manifest(document)
        source = self.make_adapter(document)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest_path = root / "manifest.json"
            source_path = root / "adapter.cpp"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            source_path.write_text(source, encoding="utf-8")
            auditor.verify_manifest_binding(ledger, manifest_path)
            auditor.verify_adapter_bindings(ledger, source_path)

            source_path.write_text(
                source.replace("SetMessageRva = 0x1040", "SetMessageRva = 0x1041"),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(auditor.AuditError, "drifted"):
                auditor.verify_adapter_bindings(ledger, source_path)

            symbols = manifest["symbols"]
            assert isinstance(symbols, list)
            related = next(
                entry
                for entry in symbols
                if isinstance(entry, dict)
                and entry.get("id") == "set_message_for_server_scripting"
            )
            related["resolved"] = True
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(auditor.AuditError, "remain unverified"):
                auditor.verify_manifest_binding(ledger, manifest_path)

            duplicate_manifest = self.make_manifest(document)
            duplicate_symbols = duplicate_manifest["symbols"]
            assert isinstance(duplicate_symbols, list)
            duplicate_symbols.append(deepcopy(duplicate_symbols[0]))
            manifest_path.write_text(json.dumps(duplicate_manifest), encoding="utf-8")
            with self.assertRaisesRegex(auditor.AuditError, "duplicates symbol ID"):
                auditor.verify_manifest_binding(ledger, manifest_path)

    def test_candidate_ledger_is_rejected_by_activation_tools_without_output(
        self,
    ) -> None:
        protected = (
            ROOT / "include/endstone_sign/generated/native_manifest_data.h",
            ROOT / "native/manifests/linux-x64-1.26.33.1.json",
            ROOT / "native/manifests/windows-x64-1.26.33.1.json",
        )
        before = {
            path: hashlib.sha256(path.read_bytes()).hexdigest() for path in protected
        }
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "must-not-exist.h"
            verify = subprocess.run(
                [
                    PYTHON,
                    "tools/verify_native_manifest.py",
                    str(auditor.DEFAULT_LEDGER),
                ],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            activate = subprocess.run(
                [
                    PYTHON,
                    "tools/activate_verified_manifest.py",
                    str(auditor.DEFAULT_LEDGER),
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertNotEqual(verify.returncode, 0, verify.stdout)
            self.assertIn("gate CLOSED", verify.stdout)
            self.assertNotEqual(activate.returncode, 0, activate.stdout)
            self.assertIn("activation refused", activate.stdout)
            self.assertFalse(output.exists())
        after = {
            path: hashlib.sha256(path.read_bytes()).hexdigest() for path in protected
        }
        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
