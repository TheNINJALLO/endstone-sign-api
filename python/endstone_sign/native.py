from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class NativeSignSymbol(str, Enum):
    SIGN_ACTOR_SAVE = "sign_actor_save"
    SIGN_ACTOR_LOAD = "sign_actor_load"
    GET_MESSAGE = "get_message"
    GET_RAW_MESSAGE = "get_raw_message"
    GET_SIGN_TEXT_COLOR = "get_sign_text_color"
    GET_IS_GLOWING = "get_is_glowing"
    GET_HIDE_GLOW_OUTLINE = "get_hide_glow_outline"
    GET_IS_WAXED = "get_is_waxed"
    GET_IS_LOCKED_FOR_EDITING = "get_is_locked_for_editing"
    SET_MESSAGE_FOR_SERVER_SCRIPTING = "set_message_for_server_scripting"
    SET_SIGN_TEXT_COLOR = "set_sign_text_color"
    SET_IS_GLOWING = "set_is_glowing"
    SET_HIDE_GLOW_OUTLINE = "set_hide_glow_outline"
    SET_WAXED = "set_waxed"
    SET_LOCKED_FOR_EDITING = "set_locked_for_editing"
    CLEAR_LOCKED_FOR_EDITING = "clear_locked_for_editing"
    REQUEST_OPEN_SIGN_EDITOR = "request_open_sign_editor"
    UPDATE_TEXT_FROM_CLIENT = "update_text_from_client"
    FIRE_BLOCK_ENTITY_CHANGED = "fire_block_entity_changed"


REQUIRED_NATIVE_SIGN_SYMBOLS: tuple[NativeSignSymbol, ...] = tuple(NativeSignSymbol)


@dataclass(frozen=True, slots=True)
class NativeBinaryIdentity:
    platform: str = ""
    bds_package_version: str = ""
    archive_sha256: str = ""
    executable_sha256: str = ""
    executable_size: int = 0


@dataclass(frozen=True, slots=True)
class NativeSymbolResolution:
    symbol: NativeSignSymbol
    mangled_name: str = ""
    pattern: str = ""
    rva: int = 0
    resolved: bool = False
    unique: bool = False
    signature_verified: bool = False
    behavior_verified: bool = False


@dataclass(frozen=True, slots=True)
class NativeSignManifest:
    binary: NativeBinaryIdentity = NativeBinaryIdentity()
    endstone_version: str = ""
    symbols: tuple[NativeSymbolResolution, ...] = ()
    disposable_world_probe_passed: bool = False
    disposable_world_probe_sha256: str = ""

    @property
    def complete(self) -> bool:
        return not self.missing_requirements()

    def missing_requirements(self) -> tuple[str, ...]:
        missing: list[str] = []
        if not self.binary.platform:
            missing.append("binary.platform")
        if not self.binary.bds_package_version:
            missing.append("binary.bds_package_version")
        if not self.binary.archive_sha256:
            missing.append("binary.archive_sha256")
        if not self.binary.executable_sha256:
            missing.append("binary.executable_sha256")
        if self.binary.executable_size <= 0:
            missing.append("binary.executable_size")
        if not self.endstone_version:
            missing.append("endstone_version")
        if not self.disposable_world_probe_passed:
            missing.append("disposable_world_probe_passed")
        if not self.disposable_world_probe_sha256:
            missing.append("disposable_world_probe_sha256")

        by_symbol = {entry.symbol: entry for entry in self.symbols}
        for required in REQUIRED_NATIVE_SIGN_SYMBOLS:
            entry = by_symbol.get(required)
            if entry is None:
                missing.append(required.value)
                continue
            if not entry.resolved:
                missing.append(f"{required.value}.resolved")
            if not entry.unique:
                missing.append(f"{required.value}.unique")
            if not entry.signature_verified:
                missing.append(f"{required.value}.signature_verified")
            if not entry.behavior_verified:
                missing.append(f"{required.value}.behavior_verified")
            if entry.rva <= 0:
                missing.append(f"{required.value}.rva")
        return tuple(missing)
