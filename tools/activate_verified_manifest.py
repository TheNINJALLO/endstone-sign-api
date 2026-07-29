#!/usr/bin/env python3
"""Generate the closed-to-open C++ manifest header after all proof gates pass."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_native_manifest import validate  # noqa: E402

SYMBOL_ENUM = {
    "sign_actor_save": "SignActorSave",
    "sign_actor_load": "SignActorLoad",
    "get_message": "GetMessage",
    "get_raw_message": "GetRawMessage",
    "get_sign_text_color": "GetSignTextColor",
    "get_is_glowing": "GetIsGlowing",
    "get_hide_glow_outline": "GetHideGlowOutline",
    "get_is_waxed": "GetIsWaxed",
    "get_is_locked_for_editing": "GetIsLockedForEditing",
    "set_message_for_server_scripting": "SetMessageForServerScripting",
    "set_sign_text_color": "SetSignTextColor",
    "set_is_glowing": "SetIsGlowing",
    "set_hide_glow_outline": "SetHideGlowOutline",
    "set_waxed": "SetWaxed",
    "set_locked_for_editing": "SetLockedForEditing",
    "clear_locked_for_editing": "ClearLockedForEditing",
    "request_open_sign_editor": "RequestOpenSignEditor",
    "update_text_from_client": "UpdateTextFromClient",
    "fire_block_entity_changed": "FireBlockEntityChanged",
}


def bytes_array(hex_value: str) -> tuple[str, int]:
    raw = bytes.fromhex(hex_value)
    if len(raw) > 24:
        raise SystemExit("fingerprints must be at most 24 bytes")
    padded = raw + b"\x00" * (24 - len(raw))
    return ", ".join(f"0x{value:02X}" for value in padded), len(raw)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("include/endstone_sign/generated/native_manifest_data.h"),
    )
    args = parser.parse_args()
    missing = validate(args.manifest, args.root)
    if missing:
        raise SystemExit("activation refused:\n- " + "\n- ".join(missing))
    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    entries: list[str] = []
    for symbol in data["symbols"]:
        fingerprint, size = bytes_array(symbol["fingerprint_hex"])
        entries.append(
            "    {NativeSignSymbol::%s, 0x%XULL, {%s}, %d},"
            % (SYMBOL_ENUM[symbol["id"]], symbol["rva"], fingerprint, size)
        )
    lines = [
        "#pragma once", "", '#include "endstone_sign/native_manifest.h"', "",
        "#include <array>", "#include <cstdint>", "#include <string_view>", "",
        "namespace endstone_sign::generated {", "",
        "struct GeneratedSymbolEntry {",
        "    NativeSignSymbol symbol{};",
        "    std::uint64_t rva{};",
        "    std::array<std::uint8_t, 24> fingerprint{};",
        "    std::uint8_t fingerprint_size{};",
        "};", "",
        'inline constexpr std::string_view BdsPackageVersion = "1.26.33.1";',
        'inline constexpr std::string_view EndstoneVersion = "0.11.6";',
        f'inline constexpr std::string_view Platform = "{data["platform"]}";',
        f'inline constexpr std::string_view ArchiveSha256 = "{data["archive_sha256"]}";',
        f'inline constexpr std::string_view ExecutableSha256 = "{data["executable"]["sha256"]}";',
        f'inline constexpr std::uint64_t ExecutableSize = {data["executable"]["size"]}ULL;',
        "inline constexpr bool ManifestComplete = true;",
        "inline constexpr bool SymbolsBehaviorVerified = true;",
        "inline constexpr bool DisposableWorldProbePassed = true;",
        f"inline constexpr std::array<GeneratedSymbolEntry, {len(entries)}> Symbols{{{{",
        *entries,
        "}};", "", "} // namespace endstone_sign::generated", "",
    ]
    output = args.output if args.output.is_absolute() else args.root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
