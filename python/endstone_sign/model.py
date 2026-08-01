from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum, IntEnum
import hashlib
import json
from typing import Any, Mapping, TypeAlias


SignStateValue: TypeAlias = bool | int | str
SignLines: TypeAlias = tuple[str, str, str, str]


class SignSide(str, Enum):
    FRONT = "front"
    BACK = "back"


class SignKind(str, Enum):
    STANDING = "standing"
    WALL = "wall"
    CEILING_HANGING = "ceiling_hanging"
    WALL_HANGING = "wall_hanging"
    UNKNOWN = "unknown"


class SignMaterial(str, Enum):
    OAK = "oak"
    SPRUCE = "spruce"
    BIRCH = "birch"
    JUNGLE = "jungle"
    ACACIA = "acacia"
    DARK_OAK = "dark_oak"
    MANGROVE = "mangrove"
    CHERRY = "cherry"
    BAMBOO = "bamboo"
    CRIMSON = "crimson"
    WARPED = "warped"
    PALE_OAK = "pale_oak"


class CardinalDirection(IntEnum):
    NORTH = 2
    SOUTH = 3
    WEST = 4
    EAST = 5


class SignMutationOrigin(str, Enum):
    API = "api"
    PLAYER = "player"
    COMMAND = "command"
    STRUCTURE = "structure"
    WORLD_LOAD = "world_load"
    UNKNOWN = "unknown"


class SignReplacePolicy(str, Enum):
    REQUIRE_AIR = "require_air"
    REPLACEABLE_ONLY = "replaceable_only"
    FORCE = "force"


class SignEventKind(str, Enum):
    BEFORE_PLACE = "before_place"
    AFTER_PLACE = "after_place"
    BEFORE_CHANGE = "before_change"
    AFTER_CHANGE = "after_change"
    BEFORE_REMOVE = "before_remove"
    AFTER_REMOVE = "after_remove"
    BEFORE_OPEN_EDITOR = "before_open_editor"
    AFTER_OPEN_EDITOR = "after_open_editor"
    BEFORE_LOCK = "before_lock"
    AFTER_LOCK = "after_lock"
    BEFORE_UNLOCK = "before_unlock"
    AFTER_UNLOCK = "after_unlock"
    PLAYER_EDIT_RECEIVED = "player_edit_received"


class SignApplyStatus(str, Enum):
    APPLIED = "applied"
    CONFLICT = "conflict"
    CANCELLED = "cancelled"
    CHUNK_UNAVAILABLE = "chunk_unavailable"
    NOT_A_SIGN = "not_a_sign"
    BLOCK_OCCUPIED = "block_occupied"
    UNSUPPORTED = "unsupported"
    INVALID_PATCH = "invalid_patch"
    PERMISSION_DENIED = "permission_denied"
    ADAPTER_UNAVAILABLE = "adapter_unavailable"
    RUNTIME_MISMATCH = "runtime_mismatch"
    BINARY_IDENTITY_MISMATCH = "binary_identity_mismatch"
    SYMBOL_VALIDATION_FAILED = "symbol_validation_failed"
    TRANSACTION_FAILED = "transaction_failed"
    ROLLBACK_FAILED = "rollback_failed"
    ADAPTER_ERROR = "adapter_error"


class SignActorStatus(str, Enum):
    CAPTURED = "captured"
    CHUNK_UNAVAILABLE = "chunk_unavailable"
    NO_BLOCK_ACTOR = "no_block_actor"
    WRONG_BLOCK_ACTOR_TYPE = "wrong_block_actor_type"
    SYMBOL_GATE_CLOSED = "symbol_gate_closed"
    ADAPTER_ERROR = "adapter_error"


@dataclass(frozen=True, order=True, slots=True)
class SignLocation:
    dimension: str = "overworld"
    x: int = 0
    y: int = 0
    z: int = 0


@dataclass(frozen=True, slots=True)
class SignText:
    lines: SignLines = ("", "", "", "")
    filtered_message: str = ""
    text_object: str = ""
    message_is_text_object: bool = False
    argb: int = 0xFF000000
    glowing: bool = False
    hide_glow_outline: bool = False
    persist_formatting: bool = True
    owner_xuid: str = ""


@dataclass(frozen=True, slots=True)
class SignTextPatch:
    lines: SignLines | None = None
    line_updates: Mapping[int, str] = field(default_factory=dict)
    message: str | None = None
    filtered_message: str | None = None
    text_object: str | None = None
    message_is_text_object: bool | None = None
    argb: int | None = None
    glowing: bool | None = None
    hide_glow_outline: bool | None = None
    persist_formatting: bool | None = None
    owner_xuid: str | None = None


@dataclass(frozen=True, slots=True)
class SignSnapshot:
    location: SignLocation
    block_identifier: str
    kind: SignKind = SignKind.UNKNOWN
    states: Mapping[str, SignStateValue] = field(default_factory=dict)
    front: SignText = field(default_factory=SignText)
    back: SignText = field(default_factory=SignText)
    waxed: bool = False
    locked_for_editing_by: int = -1
    locked_for_editing_xuid: str | None = None
    remote_profanity_filter_enabled: bool = False
    local_profanity_filter_enabled: bool = False
    movable: bool = True
    actor_status: SignActorStatus = SignActorStatus.CAPTURED
    canonical_snbt: str = ""
    revision: int = 0


@dataclass(frozen=True, slots=True)
class SignPatch:
    location: SignLocation
    expected_revision: int | None = None
    block_identifier: str | None = None
    state_updates: Mapping[str, SignStateValue] = field(default_factory=dict)
    state_removals: frozenset[str] = frozenset()
    front: SignTextPatch | None = None
    back: SignTextPatch | None = None
    waxed: bool | None = None
    locked_for_editing_by: int | None = None
    locked_for_editing_xuid: str | None = None
    remote_profanity_filter_enabled: bool | None = None
    local_profanity_filter_enabled: bool | None = None
    send_client_update: bool = True
    persist: bool = True
    origin: SignMutationOrigin = SignMutationOrigin.API


@dataclass(frozen=True, slots=True)
class SignPlaceRequest:
    location: SignLocation
    block_identifier: str = "minecraft:standing_sign"
    states: Mapping[str, SignStateValue] = field(default_factory=dict)
    front: SignText = field(default_factory=SignText)
    back: SignText = field(default_factory=SignText)
    waxed: bool = False
    locked_for_editing_by: int = -1
    locked_for_editing_xuid: str | None = None
    remote_profanity_filter_enabled: bool = False
    local_profanity_filter_enabled: bool = False
    replace_policy: SignReplacePolicy = SignReplacePolicy.REQUIRE_AIR
    expected_destination_revision: int | None = None
    send_client_update: bool = True
    persist: bool = True
    origin: SignMutationOrigin = SignMutationOrigin.API


@dataclass(frozen=True, slots=True)
class SignRemoveRequest:
    location: SignLocation
    expected_revision: int | None = None
    drop_item: bool = False
    send_client_update: bool = True
    origin: SignMutationOrigin = SignMutationOrigin.API


@dataclass(frozen=True, slots=True)
class SignCloneRequest:
    source: SignLocation
    destination: SignLocation
    expected_source_revision: int | None = None
    replace_policy: SignReplacePolicy = SignReplacePolicy.REQUIRE_AIR
    copy_editor_lock: bool = False
    send_client_update: bool = True
    origin: SignMutationOrigin = SignMutationOrigin.API


@dataclass(frozen=True, slots=True)
class SignMoveRequest:
    source: SignLocation
    destination: SignLocation
    expected_source_revision: int | None = None
    replace_policy: SignReplacePolicy = SignReplacePolicy.REQUIRE_AIR
    copy_editor_lock: bool = False
    send_client_update: bool = True
    origin: SignMutationOrigin = SignMutationOrigin.API


@dataclass(frozen=True, slots=True)
class SignOpenEditorRequest:
    location: SignLocation
    side: SignSide = SignSide.FRONT
    expected_revision: int | None = None
    acquire_lock: bool = True
    bypass_wax: bool = False


SignOperation: TypeAlias = SignPlaceRequest | SignPatch | SignRemoveRequest


@dataclass(frozen=True, slots=True)
class SignTransaction:
    operations: tuple[SignOperation, ...] = ()
    force: bool = False
    rollback_on_failure: bool = True
    audit_reason: str = ""


@dataclass(frozen=True, slots=True)
class SignApplyResult:
    status: SignApplyStatus
    message: str
    resulting_revision: int = 0

    @property
    def ok(self) -> bool:
        return self.status is SignApplyStatus.APPLIED


@dataclass(frozen=True, slots=True)
class SignTransactionResult:
    status: SignApplyStatus
    message: str
    operation_results: tuple[SignApplyResult, ...] = ()
    rolled_back: bool = False

    @property
    def ok(self) -> bool:
        return self.status is SignApplyStatus.APPLIED


@dataclass(frozen=True, slots=True)
class SignCapabilities:
    capture: bool = False
    place: bool = False
    remove: bool = False
    replace: bool = False
    clone: bool = False
    move: bool = False
    atomic_transactions: bool = False
    read_text: bool = False
    write_text: bool = False
    front_and_back: bool = False
    per_line_write: bool = False
    text_objects: bool = False
    filtered_text: bool = False
    owner_xuid: bool = False
    text_color: bool = False
    glowing: bool = False
    hide_glow_outline: bool = False
    persist_formatting: bool = False
    waxed: bool = False
    editor_lock: bool = False
    open_editor: bool = False
    player_edit_events: bool = False
    api_edit_events: bool = False
    client_updates: bool = False
    restart_persistence: bool = False
    exact_build_match: bool = False
    exact_binary_hash_match: bool = False
    symbols_validated: bool = False
    stage_probe_passed: bool = False

    @property
    def supported_release(self) -> bool:
        return all((
            self.capture,
            self.place,
            self.remove,
            self.replace,
            self.clone,
            self.move,
            self.atomic_transactions,
            self.read_text,
            self.write_text,
            self.front_and_back,
            self.per_line_write,
            self.filtered_text,
            self.owner_xuid,
            self.hide_glow_outline,
            self.persist_formatting,
            self.api_edit_events,
            self.client_updates,
            self.exact_build_match,
            self.exact_binary_hash_match,
            self.symbols_validated,
        ))

    @property
    def complete_control(self) -> bool:
        return all((
            self.capture,
            self.place,
            self.remove,
            self.replace,
            self.clone,
            self.move,
            self.atomic_transactions,
            self.read_text,
            self.write_text,
            self.front_and_back,
            self.per_line_write,
            self.text_objects,
            self.filtered_text,
            self.owner_xuid,
            self.text_color,
            self.glowing,
            self.hide_glow_outline,
            self.persist_formatting,
            self.waxed,
            self.editor_lock,
            self.open_editor,
            self.player_edit_events,
            self.api_edit_events,
            self.client_updates,
            self.restart_persistence,
            self.exact_build_match,
            self.exact_binary_hash_match,
            self.symbols_validated,
            self.stage_probe_passed,
        ))


@dataclass(frozen=True, slots=True)
class SignActorContext:
    origin: SignMutationOrigin = SignMutationOrigin.UNKNOWN
    actor_name: str = ""
    actor_xuid: str = ""
    plugin_name: str = ""


@dataclass(slots=True)
class SignEvent:
    kind: SignEventKind
    location: SignLocation
    actor: SignActorContext = field(default_factory=SignActorContext)
    before: SignSnapshot | None = None
    after: SignSnapshot | None = None
    cancellable: bool = False
    cancelled: bool = False
    cancellation_reason: str = ""


@dataclass(frozen=True, slots=True)
class SignValidationLimits:
    max_line_bytes: int = 384
    max_total_bytes: int = 1536
    max_filtered_bytes: int = 1536
    max_text_object_bytes: int = 8192
    max_owner_bytes: int = 128
    allow_formatting_codes: bool = True


def _utf8_length(value: str) -> int:
    try:
        return len(value.encode("utf-8", "strict"))
    except UnicodeEncodeError as exc:
        raise ValueError("text is not valid UTF-8") from exc


def flatten_lines(lines: SignLines) -> str:
    if len(lines) != 4:
        raise ValueError("a Bedrock sign has exactly four lines")
    return "\n".join(lines)


def split_message(message: str) -> SignLines:
    _utf8_length(message)
    if "\x00" in message or "\r" in message:
        raise ValueError("sign message contains a forbidden control character")
    parts = message.split("\n")
    if len(parts) > 4:
        raise ValueError("sign message contains more than four lines")
    parts.extend([""] * (4 - len(parts)))
    return tuple(parts)  # type: ignore[return-value]


def validate_sign_text(
    text: SignText,
    limits: SignValidationLimits = SignValidationLimits(),
) -> str | None:
    if len(text.lines) != 4:
        return "a Bedrock sign has exactly four lines"
    total = 0
    for index, line in enumerate(text.lines, 1):
        try:
            size = _utf8_length(line)
        except ValueError:
            return f"line {index} is not valid UTF-8"
        if "\x00" in line or "\n" in line or "\r" in line:
            return f"line {index} contains a forbidden control character"
        if not limits.allow_formatting_codes and "§" in line:
            return f"line {index} contains a formatting code"
        if size > limits.max_line_bytes:
            return f"line {index} exceeds the configured byte limit"
        total += size
    if total > limits.max_total_bytes:
        return "sign text exceeds the configured total byte limit"

    for label, value, maximum in (
        ("filtered message", text.filtered_message, limits.max_filtered_bytes),
        ("text object", text.text_object, limits.max_text_object_bytes),
        ("text owner XUID", text.owner_xuid, limits.max_owner_bytes),
    ):
        try:
            size = _utf8_length(value)
        except ValueError:
            return f"{label} is not valid UTF-8"
        if "\x00" in value or (label != "text owner XUID" and "\r" in value):
            return f"{label} contains a forbidden control character"
        if size > maximum:
            return f"{label} exceeds the configured byte limit"
    if not 0 <= text.argb <= 0xFFFFFFFF:
        return "ARGB color must fit in an unsigned 32-bit value"
    return None


def validate_text_patch(
    patch: SignTextPatch,
    limits: SignValidationLimits = SignValidationLimits(),
) -> str | None:
    if patch.lines is not None and patch.message is not None:
        return "whole-line replacement and message replacement cannot be combined"
    if patch.lines is not None and len(patch.lines) != 4:
        return "a Bedrock sign has exactly four lines"
    for index, line in patch.line_updates.items():
        if type(index) is not int or not 0 <= index <= 3:
            return "line update index must be between 0 and 3"
        try:
            size = _utf8_length(line)
        except ValueError:
            return "line update is not valid UTF-8"
        if "\x00" in line or "\n" in line or "\r" in line:
            return "line update contains a forbidden control character"
        if not limits.allow_formatting_codes and "§" in line:
            return "line update contains a formatting code"
        if size > limits.max_line_bytes:
            return "line update exceeds the configured byte limit"
    if patch.message is not None:
        try:
            split_message(patch.message)
        except ValueError as exc:
            return str(exc)
    candidate = SignText(
        lines=patch.lines or ("", "", "", ""),
        filtered_message=patch.filtered_message or "",
        text_object=patch.text_object or "",
        message_is_text_object=patch.message_is_text_object or False,
        argb=0xFF000000 if patch.argb is None else patch.argb,
        owner_xuid=patch.owner_xuid or "",
    )
    # Only validate optional non-line fields here. Full resulting text is checked by the service.
    for label, value, maximum in (
        ("filtered message", candidate.filtered_message, limits.max_filtered_bytes),
        ("text object", candidate.text_object, limits.max_text_object_bytes),
        ("text owner XUID", candidate.owner_xuid, limits.max_owner_bytes),
    ):
        try:
            size = _utf8_length(value)
        except ValueError:
            return f"{label} is not valid UTF-8"
        if "\x00" in value:
            return f"{label} contains a NUL byte"
        if size > maximum:
            return f"{label} exceeds the configured byte limit"
    if patch.argb is not None and not 0 <= patch.argb <= 0xFFFFFFFF:
        return "ARGB color must fit in an unsigned 32-bit value"
    return None


def apply_text_patch(base: SignText, patch: SignTextPatch) -> SignText:
    lines = base.lines
    if patch.lines is not None:
        lines = patch.lines
    if patch.message is not None:
        lines = split_message(patch.message)
    mutable_lines = list(lines)
    for index, line in patch.line_updates.items():
        if not 0 <= index <= 3:
            raise ValueError("line update index must be between 0 and 3")
        mutable_lines[index] = line
    return replace(
        base,
        lines=tuple(mutable_lines),  # type: ignore[arg-type]
        filtered_message=base.filtered_message if patch.filtered_message is None else patch.filtered_message,
        text_object=base.text_object if patch.text_object is None else patch.text_object,
        message_is_text_object=(
            base.message_is_text_object
            if patch.message_is_text_object is None
            else patch.message_is_text_object
        ),
        argb=base.argb if patch.argb is None else patch.argb,
        glowing=base.glowing if patch.glowing is None else patch.glowing,
        hide_glow_outline=(
            base.hide_glow_outline
            if patch.hide_glow_outline is None
            else patch.hide_glow_outline
        ),
        persist_formatting=(
            base.persist_formatting
            if patch.persist_formatting is None
            else patch.persist_formatting
        ),
        owner_xuid=base.owner_xuid if patch.owner_xuid is None else patch.owner_xuid,
    )


def _state_payload(value: SignStateValue) -> tuple[str, Any]:
    if type(value) is bool:
        return ("bool", value)
    if type(value) is int:
        return ("int", value)
    return ("string", value)


def _text_payload(text: SignText) -> dict[str, Any]:
    return {
        "lines": list(text.lines),
        "filtered_message": text.filtered_message,
        "text_object": text.text_object,
        "message_is_text_object": text.message_is_text_object,
        "argb": text.argb & 0xFFFFFFFF,
        "glowing": text.glowing,
        "hide_glow_outline": text.hide_glow_outline,
        "persist_formatting": text.persist_formatting,
        "owner_xuid": text.owner_xuid,
    }


def calculate_revision(snapshot: SignSnapshot) -> int:
    payload = {
        "location": [snapshot.location.dimension, snapshot.location.x, snapshot.location.y, snapshot.location.z],
        "block_identifier": snapshot.block_identifier,
        "kind": snapshot.kind.value,
        "states": [[key, *_state_payload(value)] for key, value in sorted(snapshot.states.items())],
        "front": _text_payload(snapshot.front),
        "back": _text_payload(snapshot.back),
        "waxed": snapshot.waxed,
        "locked_for_editing_by": snapshot.locked_for_editing_by,
        "locked_for_editing_xuid": snapshot.locked_for_editing_xuid,
        "remote_profanity_filter_enabled": snapshot.remote_profanity_filter_enabled,
        "local_profanity_filter_enabled": snapshot.local_profanity_filter_enabled,
        "movable": snapshot.movable,
        "actor_status": snapshot.actor_status.value,
        "canonical_snbt": snapshot.canonical_snbt,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return int.from_bytes(hashlib.blake2b(encoded, digest_size=8).digest(), "big")


def patch_is_empty(patch: SignPatch) -> bool:
    return not any((
        patch.block_identifier is not None,
        bool(patch.state_updates),
        bool(patch.state_removals),
        patch.front is not None,
        patch.back is not None,
        patch.waxed is not None,
        patch.locked_for_editing_by is not None,
        patch.locked_for_editing_xuid is not None,
        patch.remote_profanity_filter_enabled is not None,
        patch.local_profanity_filter_enabled is not None,
    ))
