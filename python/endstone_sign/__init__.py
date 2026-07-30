"""Complete sign lifecycle contract and exact-build activation framework for Endstone."""

from .events import SignEventBus, SignEventListener
from .model import (
    CardinalDirection,
    SignActorContext,
    SignActorStatus,
    SignApplyResult,
    SignApplyStatus,
    SignCapabilities,
    SignCloneRequest,
    SignEvent,
    SignEventKind,
    SignKind,
    SignLines,
    SignLocation,
    SignMaterial,
    SignMoveRequest,
    SignMutationOrigin,
    SignOpenEditorRequest,
    SignOperation,
    SignPatch,
    SignPlaceRequest,
    SignRemoveRequest,
    SignReplacePolicy,
    SignSide,
    SignSnapshot,
    SignStateValue,
    SignText,
    SignTextPatch,
    SignTransaction,
    SignTransactionResult,
    SignValidationLimits,
    apply_text_patch,
    calculate_revision,
    flatten_lines,
    patch_is_empty,
    split_message,
    validate_sign_text,
    validate_text_patch,
)
from .native import (
    NativeBinaryIdentity,
    NativeSignManifest,
    NativeSignSymbol,
    NativeSymbolResolution,
    REQUIRED_NATIVE_SIGN_SYMBOLS,
)
from .placement import (
    ALL_SIGN_MATERIALS,
    classify_identifier,
    classify_sign,
    is_vanilla_sign_identifier,
    make_ceiling_hanging_sign_states,
    make_standing_sign_states,
    make_wall_hanging_sign_states,
    make_wall_sign_states,
    material_from_sign_identifier,
    sign_block_identifier,
    validate_sign_block_states,
)
from .schema import (
    SignNbtProjection,
    SignSideProjection,
    apply_nbt_projection,
    make_nbt_projection,
    make_side_projection,
    sign_text_from_projection,
)
from .service import InMemorySignAdapter, InMemorySignService, SignAdapter, SignService

__version__ = "0.2.0a6"
__service_name__ = "endstone:sign:v2"
__service_abi__ = 2

__all__ = [name for name in globals() if not name.startswith("_")]
