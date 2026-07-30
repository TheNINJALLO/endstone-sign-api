#!/usr/bin/env python3
"""Audit non-activating Linux ELF byte candidates for the exact BDS binary.

This tool is deliberately separate from the native activation manifest.  A
successful result proves only that committed byte candidates match one exact
executable and have unique entry fingerprints in its executable load ranges.
It does not prove a C++ signature, ABI contract, behavior, or activation
eligibility, and it never writes a manifest or generated header.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import mmap
import os
from pathlib import Path
import re
import stat
import struct
from typing import BinaryIO, Mapping


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER = ROOT / "native/audits/linux-x64-1.26.33.1-text-symbol-candidates.json"
DEFAULT_MANIFEST = ROOT / "native/manifests/linux-x64-1.26.33.1.json"
DEFAULT_ADAPTER = ROOT / "src/experimental_bds_26_30_adapter.cpp"

DOCUMENT_TYPE = "linux-elf-byte-candidates"
CLAIM = "static candidate byte evidence only; no ABI, signature, or behavior proof"
HEX64 = re.compile(r"\A[0-9a-f]{64}\Z")
HEX_BYTES = re.compile(r"\A(?:[0-9a-f]{2})+\Z")
U64_MAX = (1 << 64) - 1
ELF_HEADER = struct.Struct("<16sHHIQQQIHHHHHH")
PROGRAM_HEADER = struct.Struct("<IIQQQQQQ")
ET_DYN = 3
EM_X86_64 = 62
PT_LOAD = 1
PF_X = 1
PN_XNUM = 0xFFFF
MAX_PROGRAM_HEADERS = 4096
MAX_LEDGER_BYTES = 64 * 1024
MAX_JSON_BYTES = 2 * 1024 * 1024

ROOT_KEYS = {
    "schema",
    "document_type",
    "activation_eligible",
    "claim",
    "platform",
    "bds_package_version",
    "runtime_bds",
    "executable",
    "candidates",
}
EXECUTABLE_KEYS = {"filename", "elf_type", "sha256", "size"}
CANDIDATE_KEYS = {
    "id",
    "related_manifest_symbol",
    "adapter_constant",
    "rva",
    "size",
    "sha256",
    "fingerprint_hex",
}
EXPECTED_CANDIDATES = {
    "alpha6_set_message": ("set_message_for_server_scripting", "SetMessage"),
    "alpha6_get_raw_message": ("get_raw_message", "GetRawMessage"),
    "alpha6_is_string_message": ("", "IsStringMessage"),
}
REQUIRED_MANIFEST_SYMBOLS = {
    "sign_actor_save",
    "sign_actor_load",
    "get_message",
    "get_raw_message",
    "get_sign_text_color",
    "get_is_glowing",
    "get_hide_glow_outline",
    "get_is_waxed",
    "get_is_locked_for_editing",
    "set_message_for_server_scripting",
    "set_sign_text_color",
    "set_is_glowing",
    "set_hide_glow_outline",
    "set_waxed",
    "set_locked_for_editing",
    "clear_locked_for_editing",
    "request_open_sign_editor",
    "update_text_from_client",
    "fire_block_entity_changed",
}


class AuditError(ValueError):
    """Raised when candidate evidence fails closed."""


@dataclass(frozen=True)
class ExecutableIdentity:
    filename: str
    sha256: str
    size: int
    elf_type: str


@dataclass(frozen=True)
class Candidate:
    id: str
    related_manifest_symbol: str
    adapter_constant: str
    rva: int
    size: int
    sha256: str
    fingerprint: bytes


@dataclass(frozen=True)
class CandidateLedger:
    platform: str
    bds_package_version: str
    runtime_bds: str
    executable: ExecutableIdentity
    candidates: tuple[Candidate, ...]


@dataclass(frozen=True)
class LoadSegment:
    flags: int
    file_offset: int
    virtual_address: int
    file_size: int
    memory_size: int

    @property
    def executable(self) -> bool:
        return bool(self.flags & PF_X)


def _checked_add(left: int, right: int, label: str) -> int:
    if left < 0 or right < 0 or left > U64_MAX or right > U64_MAX - left:
        raise AuditError(f"{label} overflows an unsigned 64-bit range")
    return left + right


def _checked_multiply(left: int, right: int, label: str) -> int:
    if left < 0 or right < 0 or (right and left > U64_MAX // right):
        raise AuditError(f"{label} overflows an unsigned 64-bit range")
    return left * right


def _exact_keys(value: Mapping[str, object], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual == expected:
        return
    details: list[str] = []
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing:
        details.append(f"missing {', '.join(missing)}")
    if extra:
        details.append(f"unexpected {', '.join(extra)}")
    raise AuditError(f"{label} fields are invalid ({'; '.join(details)})")


def _object_without_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise AuditError(f"JSON contains duplicate key {key!r}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> object:
    raise AuditError(f"JSON contains unsupported constant {value}")


def _load_json(path: Path, maximum_size: int) -> object:
    try:
        payload = path.read_bytes()
    except OSError as error:
        raise AuditError(f"could not read {path}: {error}") from error
    if len(payload) > maximum_size:
        raise AuditError(f"{path} exceeds the {maximum_size}-byte safety limit")
    try:
        text = payload.decode("utf-8", errors="strict")
        return json.loads(
            text,
            object_pairs_hook=_object_without_duplicates,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeError, json.JSONDecodeError) as error:
        raise AuditError(
            f"could not parse strict UTF-8 JSON from {path}: {error}"
        ) from error


def _require_string(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise AuditError(f"{label} must be a string")
    return value


def _require_positive_u64(value: object, label: str) -> int:
    if type(value) is not int or not 0 < value <= U64_MAX:
        raise AuditError(f"{label} must be a positive unsigned 64-bit integer")
    return value


def validate_ledger_document(document: object) -> CandidateLedger:
    if not isinstance(document, Mapping):
        raise AuditError("candidate ledger root must be an object")
    _exact_keys(document, ROOT_KEYS, "candidate ledger")
    if document["schema"] != 1 or type(document["schema"]) is not int:
        raise AuditError("candidate ledger schema must be integer 1")
    if document["document_type"] != DOCUMENT_TYPE:
        raise AuditError(f"candidate ledger document_type must be {DOCUMENT_TYPE!r}")
    if document["activation_eligible"] is not False:
        raise AuditError(
            "candidate ledger must explicitly set activation_eligible=false"
        )
    if document["claim"] != CLAIM:
        raise AuditError(
            "candidate ledger must retain the non-activating evidence claim"
        )
    if document["platform"] != "linux-x64":
        raise AuditError("candidate ledger must target linux-x64")
    if document["bds_package_version"] != "1.26.33.1":
        raise AuditError("candidate ledger must target BDS package 1.26.33.1")
    if document["runtime_bds"] != "26.33":
        raise AuditError("candidate ledger must target runtime BDS 26.33")

    raw_executable = document["executable"]
    if not isinstance(raw_executable, Mapping):
        raise AuditError("candidate ledger executable must be an object")
    _exact_keys(raw_executable, EXECUTABLE_KEYS, "candidate ledger executable")
    filename = _require_string(raw_executable["filename"], "executable.filename")
    if filename != "bedrock_server":
        raise AuditError("candidate ledger executable.filename must be bedrock_server")
    elf_type = _require_string(raw_executable["elf_type"], "executable.elf_type")
    if elf_type != "ET_DYN":
        raise AuditError("candidate ledger executable.elf_type must be ET_DYN")
    executable_hash = _require_string(raw_executable["sha256"], "executable.sha256")
    if not HEX64.fullmatch(executable_hash):
        raise AuditError(
            "executable.sha256 must be 64 lowercase hexadecimal characters"
        )
    executable_size = _require_positive_u64(raw_executable["size"], "executable.size")

    raw_candidates = document["candidates"]
    if not isinstance(raw_candidates, list):
        raise AuditError("candidate ledger candidates must be an array")
    candidates: list[Candidate] = []
    for index, raw in enumerate(raw_candidates):
        label = f"candidate[{index}]"
        if not isinstance(raw, Mapping):
            raise AuditError(f"{label} must be an object")
        _exact_keys(raw, CANDIDATE_KEYS, label)
        candidate_id = _require_string(raw["id"], f"{label}.id")
        related = _require_string(
            raw["related_manifest_symbol"], f"{label}.related_manifest_symbol"
        )
        adapter_constant = _require_string(
            raw["adapter_constant"], f"{label}.adapter_constant"
        )
        rva = _require_positive_u64(raw["rva"], f"{label}.rva")
        size = _require_positive_u64(raw["size"], f"{label}.size")
        _checked_add(rva, size, f"{label} range")
        function_hash = _require_string(raw["sha256"], f"{label}.sha256")
        if not HEX64.fullmatch(function_hash):
            raise AuditError(
                f"{label}.sha256 must be 64 lowercase hexadecimal characters"
            )
        fingerprint_hex = _require_string(
            raw["fingerprint_hex"], f"{label}.fingerprint_hex"
        )
        if not HEX_BYTES.fullmatch(fingerprint_hex):
            raise AuditError(
                f"{label}.fingerprint_hex must be lowercase hexadecimal bytes"
            )
        fingerprint = bytes.fromhex(fingerprint_hex)
        if len(fingerprint) != 24:
            raise AuditError(f"{label}.fingerprint_hex must contain exactly 24 bytes")
        if len(fingerprint) > size:
            raise AuditError(f"{label} fingerprint exceeds its candidate byte range")
        candidates.append(
            Candidate(
                candidate_id,
                related,
                adapter_constant,
                rva,
                size,
                function_hash,
                fingerprint,
            )
        )

    by_id = {candidate.id: candidate for candidate in candidates}
    if len(by_id) != len(candidates) or set(by_id) != set(EXPECTED_CANDIDATES):
        raise AuditError(
            "candidate ledger must contain the exact three alpha.6 candidate IDs"
        )
    for candidate_id, (related, adapter_constant) in EXPECTED_CANDIDATES.items():
        candidate = by_id[candidate_id]
        if candidate.related_manifest_symbol != related:
            raise AuditError(
                f"{candidate_id} has an unexpected related manifest symbol"
            )
        if candidate.adapter_constant != adapter_constant:
            raise AuditError(
                f"{candidate_id} has an unexpected adapter constant binding"
            )

    ordered = sorted(candidates, key=lambda candidate: candidate.rva)
    for previous, current in zip(ordered, ordered[1:]):
        if current.rva < previous.rva + previous.size:
            raise AuditError(
                f"candidate byte ranges overlap: {previous.id}, {current.id}"
            )
    if len({candidate.rva for candidate in candidates}) != len(candidates):
        raise AuditError("candidate RVAs must be unique")

    return CandidateLedger(
        "linux-x64",
        "1.26.33.1",
        "26.33",
        ExecutableIdentity(filename, executable_hash, executable_size, elf_type),
        tuple(candidates),
    )


def load_ledger(path: Path = DEFAULT_LEDGER) -> CandidateLedger:
    return validate_ledger_document(_load_json(path, MAX_LEDGER_BYTES))


def verify_manifest_binding(
    ledger: CandidateLedger, manifest_path: Path = DEFAULT_MANIFEST
) -> None:
    document = _load_json(manifest_path, MAX_JSON_BYTES)
    if not isinstance(document, Mapping):
        raise AuditError("blocked native manifest root must be an object")
    if document.get("status") != "blocked":
        raise AuditError("related native manifest must remain blocked")
    for key, expected in (
        ("platform", ledger.platform),
        ("bds_package_version", ledger.bds_package_version),
        ("runtime_bds", ledger.runtime_bds),
    ):
        if document.get(key) != expected:
            raise AuditError(f"candidate ledger does not match manifest {key}")
    executable = document.get("executable")
    if not isinstance(executable, Mapping):
        raise AuditError("related native manifest executable is invalid")
    if (
        executable.get("filename") != ledger.executable.filename
        or executable.get("sha256") != ledger.executable.sha256
        or executable.get("size") != ledger.executable.size
    ):
        raise AuditError(
            "candidate ledger executable identity does not match the blocked manifest"
        )
    raw_symbols = document.get("symbols")
    if not isinstance(raw_symbols, list):
        raise AuditError("related native manifest symbols are invalid")
    symbols: dict[str, Mapping[str, object]] = {}
    for entry in raw_symbols:
        if not isinstance(entry, Mapping) or not isinstance(entry.get("id"), str):
            raise AuditError("related native manifest contains an invalid symbol entry")
        symbol_id = entry["id"]
        if symbol_id in symbols:
            raise AuditError(
                f"related native manifest duplicates symbol ID {symbol_id}"
            )
        symbols[symbol_id] = entry
    if set(symbols) != REQUIRED_MANIFEST_SYMBOLS:
        raise AuditError(
            "related native manifest must contain the exact required symbol set"
        )
    for candidate in ledger.candidates:
        if not candidate.related_manifest_symbol:
            continue
        entry = symbols.get(candidate.related_manifest_symbol)
        if not isinstance(entry, Mapping):
            raise AuditError(
                f"related native manifest lacks {candidate.related_manifest_symbol}"
            )
        if any(
            entry.get(flag) is not False
            for flag in (
                "resolved",
                "unique",
                "signature_verified",
                "behavior_verified",
            )
        ):
            raise AuditError(
                f"manifest symbol {candidate.related_manifest_symbol} must remain unverified"
            )
        if entry.get("rva") != 0 or entry.get("fingerprint_hex") != "":
            raise AuditError(
                f"static candidate evidence must not populate manifest symbol "
                f"{candidate.related_manifest_symbol}"
            )


def _one_source_value(source: str, pattern: str, label: str) -> str:
    matches = re.findall(pattern, source, flags=re.MULTILINE)
    if len(matches) != 1:
        raise AuditError(f"adapter must contain exactly one {label} constant")
    return matches[0]


def verify_adapter_bindings(
    ledger: CandidateLedger, adapter_path: Path = DEFAULT_ADAPTER
) -> None:
    try:
        source = adapter_path.read_text(encoding="utf-8", errors="strict")
    except (OSError, UnicodeError) as error:
        raise AuditError(
            f"could not read adapter source {adapter_path}: {error}"
        ) from error
    for candidate in ledger.candidates:
        prefix = re.escape(candidate.adapter_constant)
        source_rva = int(
            _one_source_value(
                source,
                rf"\b{prefix}Rva\s*=\s*0x([0-9A-Fa-f]+)\s*;",
                f"{candidate.adapter_constant}Rva",
            ),
            16,
        )
        source_size = int(
            _one_source_value(
                source,
                rf"\b{prefix}Size\s*=\s*([0-9]+)\s*;",
                f"{candidate.adapter_constant}Size",
            )
        )
        source_hash = _one_source_value(
            source,
            rf"\b{prefix}Sha256\s*=\s*\r?\n?\s*\"([0-9a-f]{{64}})\"\s*;",
            f"{candidate.adapter_constant}Sha256",
        )
        if (source_rva, source_size, source_hash) != (
            candidate.rva,
            candidate.size,
            candidate.sha256,
        ):
            raise AuditError(
                f"candidate {candidate.id} drifted from its adapter constants"
            )


def _read_exact(stream: BinaryIO, offset: int, size: int, label: str) -> bytes:
    try:
        stream.seek(offset)
        payload = stream.read(size)
    except OSError as error:
        raise AuditError(f"could not read {label}: {error}") from error
    if len(payload) != size:
        raise AuditError(f"{label} is truncated")
    return payload


def parse_load_segments(stream: BinaryIO, file_size: int) -> tuple[LoadSegment, ...]:
    header = _read_exact(stream, 0, ELF_HEADER.size, "ELF header")
    (
        identity,
        elf_type,
        machine,
        version,
        _entry,
        program_offset,
        _section_offset,
        _flags,
        header_size,
        program_entry_size,
        program_count,
        _section_entry_size,
        _section_count,
        _section_names,
    ) = ELF_HEADER.unpack(header)
    if identity[:4] != b"\x7fELF":
        raise AuditError("executable is not an ELF file")
    if identity[4] != 2 or identity[5] != 1:
        raise AuditError("ELF must be 64-bit little-endian")
    if identity[6] != 1 or version != 1:
        raise AuditError("ELF version must be 1")
    if elf_type != ET_DYN:
        raise AuditError("exact executable ELF type must be ET_DYN")
    if machine != EM_X86_64:
        raise AuditError("ELF machine must be x86-64")
    if header_size != ELF_HEADER.size:
        raise AuditError("ELF header size is invalid")
    if program_entry_size != PROGRAM_HEADER.size:
        raise AuditError("ELF program-header entry size is invalid")
    if program_count in (0, PN_XNUM) or program_count > MAX_PROGRAM_HEADERS:
        raise AuditError("ELF program-header count is unsupported")
    table_size = _checked_multiply(
        program_count, program_entry_size, "ELF program-header table size"
    )
    if program_offset < header_size:
        raise AuditError("ELF program-header table overlaps the ELF header")
    table_end = _checked_add(
        program_offset, table_size, "ELF program-header table range"
    )
    if table_end > file_size:
        raise AuditError("ELF program-header table is outside the executable")

    table = _read_exact(stream, program_offset, table_size, "ELF program-header table")
    segments: list[LoadSegment] = []
    for index in range(program_count):
        offset = index * program_entry_size
        (
            segment_type,
            flags,
            file_offset,
            virtual_address,
            _physical_address,
            segment_file_size,
            memory_size,
            alignment,
        ) = PROGRAM_HEADER.unpack_from(table, offset)
        if segment_type != PT_LOAD:
            continue
        if segment_file_size > memory_size:
            raise AuditError(f"ELF PT_LOAD[{index}] file size exceeds memory size")
        file_end = _checked_add(
            file_offset, segment_file_size, f"ELF PT_LOAD[{index}] file range"
        )
        _checked_add(
            virtual_address, memory_size, f"ELF PT_LOAD[{index}] virtual range"
        )
        if file_end > file_size:
            raise AuditError(f"ELF PT_LOAD[{index}] extends past the executable")
        if alignment not in (0, 1):
            if alignment & (alignment - 1):
                raise AuditError(
                    f"ELF PT_LOAD[{index}] alignment is not a power of two"
                )
            if virtual_address % alignment != file_offset % alignment:
                raise AuditError(
                    f"ELF PT_LOAD[{index}] alignment congruence is invalid"
                )
        segments.append(
            LoadSegment(
                flags,
                file_offset,
                virtual_address,
                segment_file_size,
                memory_size,
            )
        )
    if not any(segment.executable and segment.file_size for segment in segments):
        raise AuditError("ELF has no file-backed executable PT_LOAD range")
    ordered = sorted(
        (segment for segment in segments if segment.memory_size),
        key=lambda segment: segment.virtual_address,
    )
    for previous, current in zip(ordered, ordered[1:]):
        previous_end = _checked_add(
            previous.virtual_address,
            previous.memory_size,
            "ELF PT_LOAD virtual memory range",
        )
        if current.virtual_address < previous_end:
            raise AuditError("ELF PT_LOAD virtual memory ranges overlap")
    return tuple(segments)


def _map_candidate(candidate: Candidate, segments: tuple[LoadSegment, ...]) -> int:
    end = _checked_add(candidate.rva, candidate.size, f"candidate {candidate.id} range")
    matches: list[int] = []
    for segment in segments:
        if not segment.executable:
            continue
        segment_end = _checked_add(
            segment.virtual_address,
            segment.file_size,
            "executable PT_LOAD virtual file range",
        )
        if segment.virtual_address <= candidate.rva and end <= segment_end:
            delta = candidate.rva - segment.virtual_address
            matches.append(
                _checked_add(
                    segment.file_offset, delta, f"candidate {candidate.id} file offset"
                )
            )
    if len(matches) != 1:
        raise AuditError(
            f"candidate {candidate.id} must map to exactly one file-backed executable PT_LOAD"
        )
    return matches[0]


def _fingerprint_virtual_matches(
    mapped: mmap.mmap,
    fingerprint: bytes,
    segments: tuple[LoadSegment, ...],
) -> set[int]:
    matches: set[int] = set()
    for segment in segments:
        if not segment.executable or segment.file_size < len(fingerprint):
            continue
        start = segment.file_offset
        end = segment.file_offset + segment.file_size
        position = mapped.find(fingerprint, start, end)
        while position >= 0:
            matches.add(segment.virtual_address + (position - segment.file_offset))
            position = mapped.find(fingerprint, position + 1, end)
    return matches


def _identity_tuple(info: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def verify_executable(path: Path, ledger: CandidateLedger) -> None:
    try:
        stream = path.open("rb", buffering=0)
    except OSError as error:
        raise AuditError(f"could not open exact executable {path}: {error}") from error
    with stream:
        try:
            before = os.fstat(stream.fileno())
        except OSError as error:
            raise AuditError(
                f"could not inspect exact executable {path}: {error}"
            ) from error
        if not stat.S_ISREG(before.st_mode):
            raise AuditError("exact executable path must be a regular file")
        if before.st_size != ledger.executable.size:
            raise AuditError("exact executable size mismatch")
        digest = hashlib.sha256()
        try:
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
        except OSError as error:
            raise AuditError(
                f"could not hash exact executable {path}: {error}"
            ) from error
        if digest.hexdigest() != ledger.executable.sha256:
            raise AuditError("exact executable SHA-256 mismatch")

        segments = parse_load_segments(stream, before.st_size)
        try:
            mapped = mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ)
        except (OSError, ValueError) as error:
            raise AuditError(
                f"could not map exact executable read-only: {error}"
            ) from error
        with mapped:
            for candidate in ledger.candidates:
                file_offset = _map_candidate(candidate, segments)
                payload = mapped[file_offset : file_offset + candidate.size]
                if len(payload) != candidate.size:
                    raise AuditError(
                        f"candidate {candidate.id} byte range is truncated"
                    )
                if hashlib.sha256(payload).hexdigest() != candidate.sha256:
                    raise AuditError(
                        f"candidate {candidate.id} full byte-range SHA-256 mismatch"
                    )
                if not payload.startswith(candidate.fingerprint):
                    raise AuditError(
                        f"candidate {candidate.id} entry fingerprint mismatch"
                    )
                matches = _fingerprint_virtual_matches(
                    mapped, candidate.fingerprint, segments
                )
                if matches != {candidate.rva}:
                    raise AuditError(
                        f"candidate {candidate.id} entry fingerprint is not unique at its RVA"
                    )
        try:
            after = os.fstat(stream.fileno())
        except OSError as error:
            raise AuditError(
                f"could not re-inspect exact executable {path}: {error}"
            ) from error
        if _identity_tuple(after) != _identity_tuple(before):
            raise AuditError("exact executable changed while it was being audited")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "executable",
        nargs="?",
        type=Path,
        help="optional exact bedrock_server ELF to audit offline",
    )
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--adapter", type=Path, default=DEFAULT_ADAPTER)
    args = parser.parse_args()
    try:
        ledger = load_ledger(args.ledger)
        verify_manifest_binding(ledger, args.manifest)
        verify_adapter_bindings(ledger, args.adapter)
        if args.executable is None:
            print("STATIC CANDIDATE ledger validation PASSED")
            print("EXACT ELF BYTE AUDIT NOT PERFORMED")
        else:
            verify_executable(args.executable, ledger)
            print(
                f"STATIC CANDIDATE byte audit PASSED: "
                f"{len(ledger.candidates)}/3 exact ranges and unique entry fingerprints"
            )
        print(CLAIM)
        print("native activation remains CLOSED")
        return 0
    except AuditError as error:
        print(f"STATIC CANDIDATE audit FAILED: {error}")
        print("native activation remains CLOSED")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
