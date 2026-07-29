from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from threading import RLock
from typing import Protocol

from .events import SignEventBus
from .model import (
    SignActorContext,
    SignActorStatus,
    SignApplyResult,
    SignApplyStatus,
    SignCapabilities,
    SignCloneRequest,
    SignEvent,
    SignEventKind,
    SignLocation,
    SignMoveRequest,
    SignMutationOrigin,
    SignOpenEditorRequest,
    SignOperation,
    SignPatch,
    SignPlaceRequest,
    SignRemoveRequest,
    SignReplacePolicy,
    SignSnapshot,
    SignText,
    SignTransaction,
    SignTransactionResult,
    SignValidationLimits,
    apply_text_patch,
    calculate_revision,
    patch_is_empty,
    validate_sign_text,
    validate_text_patch,
)
from .placement import classify_sign, is_vanilla_sign_identifier, validate_sign_block_states


class SignAdapter(Protocol):
    @property
    def name(self) -> str: ...
    @property
    def capabilities(self) -> SignCapabilities: ...
    def capture(self, location: SignLocation) -> SignSnapshot | None: ...
    def apply(self, patch: SignPatch, *, force: bool = False) -> SignApplyResult: ...
    def place(self, request: SignPlaceRequest, *, force: bool = False) -> SignApplyResult: ...
    def remove(self, request: SignRemoveRequest, *, force: bool = False) -> SignApplyResult: ...
    def transact(self, transaction: SignTransaction) -> SignTransactionResult: ...
    def open_editor(self, player: object, request: SignOpenEditorRequest) -> SignApplyResult: ...


def _with_origin(actor: SignActorContext, origin: SignMutationOrigin) -> SignActorContext:
    return actor if actor.origin is not SignMutationOrigin.UNKNOWN else replace(actor, origin=origin)


def _snapshot_from_place(request: SignPlaceRequest) -> SignSnapshot:
    snapshot = SignSnapshot(
        location=request.location,
        block_identifier=request.block_identifier,
        kind=classify_sign(request.block_identifier, dict(request.states)),
        states=dict(request.states),
        front=request.front,
        back=request.back,
        waxed=request.waxed,
        locked_for_editing_by=request.locked_for_editing_by,
        locked_for_editing_xuid=request.locked_for_editing_xuid,
        remote_profanity_filter_enabled=request.remote_profanity_filter_enabled,
        local_profanity_filter_enabled=request.local_profanity_filter_enabled,
        actor_status=SignActorStatus.CAPTURED,
    )
    return replace(snapshot, revision=calculate_revision(snapshot))


def _apply_patch_to_snapshot(current: SignSnapshot, patch: SignPatch) -> SignSnapshot:
    states = dict(current.states)
    states.update(patch.state_updates)
    for key in patch.state_removals:
        states.pop(key, None)
    lock_xuid = current.locked_for_editing_xuid
    if patch.locked_for_editing_xuid is not None:
        lock_xuid = patch.locked_for_editing_xuid or None
    result = replace(
        current,
        block_identifier=current.block_identifier if patch.block_identifier is None else patch.block_identifier,
        states=states,
        front=current.front if patch.front is None else apply_text_patch(current.front, patch.front),
        back=current.back if patch.back is None else apply_text_patch(current.back, patch.back),
        waxed=current.waxed if patch.waxed is None else patch.waxed,
        locked_for_editing_by=(
            current.locked_for_editing_by
            if patch.locked_for_editing_by is None
            else patch.locked_for_editing_by
        ),
        locked_for_editing_xuid=lock_xuid,
        remote_profanity_filter_enabled=(
            current.remote_profanity_filter_enabled
            if patch.remote_profanity_filter_enabled is None
            else patch.remote_profanity_filter_enabled
        ),
        local_profanity_filter_enabled=(
            current.local_profanity_filter_enabled
            if patch.local_profanity_filter_enabled is None
            else patch.local_profanity_filter_enabled
        ),
    )
    result = replace(result, kind=classify_sign(result.block_identifier, dict(result.states)))
    return replace(result, revision=calculate_revision(result))


def _patch_event_kinds(
    patch: SignPatch,
    before: SignSnapshot,
    after: SignSnapshot,
) -> tuple[SignEventKind, SignEventKind]:
    touches_lock = patch.locked_for_editing_by is not None or patch.locked_for_editing_xuid is not None
    if touches_lock:
        was_locked = before.locked_for_editing_by >= 0 or before.locked_for_editing_xuid is not None
        is_locked = after.locked_for_editing_by >= 0 or after.locked_for_editing_xuid is not None
        if not was_locked and is_locked:
            return SignEventKind.BEFORE_LOCK, SignEventKind.AFTER_LOCK
        if was_locked and not is_locked:
            return SignEventKind.BEFORE_UNLOCK, SignEventKind.AFTER_UNLOCK
    return SignEventKind.BEFORE_CHANGE, SignEventKind.AFTER_CHANGE


class InMemorySignAdapter:
    """Atomic reference adapter for tests and plugin development.

    It implements the complete data/lifecycle contract but intentionally cannot open the
    Bedrock client editor, intercept actual player sign packets, notify clients, or prove
    restart persistence. Therefore ``complete_control`` remains false.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._signs: dict[SignLocation, SignSnapshot] = {}

    @property
    def name(self) -> str:
        return "in-memory-sign-adapter-v2"

    @property
    def capabilities(self) -> SignCapabilities:
        return SignCapabilities(
            capture=True,
            place=True,
            remove=True,
            replace=True,
            clone=True,
            move=True,
            atomic_transactions=True,
            read_text=True,
            write_text=True,
            front_and_back=True,
            per_line_write=True,
            text_objects=True,
            filtered_text=True,
            owner_xuid=True,
            text_color=True,
            glowing=True,
            hide_glow_outline=True,
            persist_formatting=True,
            waxed=True,
            editor_lock=True,
            api_edit_events=True,
            exact_build_match=True,
            exact_binary_hash_match=True,
            symbols_validated=True,
            stage_probe_passed=True,
        )

    def upsert(self, snapshot: SignSnapshot) -> None:
        snapshot = replace(
            deepcopy(snapshot),
            kind=classify_sign(snapshot.block_identifier, dict(snapshot.states)),
            actor_status=SignActorStatus.CAPTURED,
        )
        snapshot = replace(snapshot, revision=calculate_revision(snapshot))
        with self._lock:
            self._signs[snapshot.location] = snapshot

    def erase(self, location: SignLocation) -> bool:
        with self._lock:
            return self._signs.pop(location, None) is not None

    def capture(self, location: SignLocation) -> SignSnapshot | None:
        with self._lock:
            snapshot = self._signs.get(location)
            if snapshot is None:
                return None
            snapshot = deepcopy(snapshot)
        snapshot = replace(
            snapshot,
            kind=classify_sign(snapshot.block_identifier, dict(snapshot.states)),
        )
        return replace(snapshot, revision=calculate_revision(snapshot))

    @staticmethod
    def _apply_to(
        signs: dict[SignLocation, SignSnapshot],
        patch: SignPatch,
        *,
        force: bool,
    ) -> SignApplyResult:
        current = signs.get(patch.location)
        if current is None:
            return SignApplyResult(SignApplyStatus.NOT_A_SIGN, "sign not found")
        current = replace(current, revision=calculate_revision(current))
        if patch.expected_revision is not None and not force and patch.expected_revision != current.revision:
            return SignApplyResult(SignApplyStatus.CONFLICT, "sign revision changed", current.revision)
        updated = _apply_patch_to_snapshot(current, patch)
        signs[patch.location] = updated
        return SignApplyResult(SignApplyStatus.APPLIED, "sign patch applied", updated.revision)

    @staticmethod
    def _place_into(
        signs: dict[SignLocation, SignSnapshot],
        request: SignPlaceRequest,
        *,
        force: bool,
    ) -> SignApplyResult:
        existing = signs.get(request.location)
        actual_revision = 0 if existing is None else calculate_revision(existing)
        if (
            request.expected_destination_revision is not None
            and not force
            and request.expected_destination_revision != actual_revision
        ):
            return SignApplyResult(SignApplyStatus.CONFLICT, "destination revision changed", actual_revision)
        if existing is not None and not force and request.replace_policy is not SignReplacePolicy.FORCE:
            return SignApplyResult(
                SignApplyStatus.BLOCK_OCCUPIED,
                "destination already contains a sign",
                actual_revision,
            )
        snapshot = _snapshot_from_place(request)
        signs[request.location] = snapshot
        return SignApplyResult(SignApplyStatus.APPLIED, "sign placed", snapshot.revision)

    @staticmethod
    def _remove_from(
        signs: dict[SignLocation, SignSnapshot],
        request: SignRemoveRequest,
        *,
        force: bool,
    ) -> SignApplyResult:
        existing = signs.get(request.location)
        if existing is None:
            return SignApplyResult(SignApplyStatus.NOT_A_SIGN, "sign not found")
        revision = calculate_revision(existing)
        if request.expected_revision is not None and not force and request.expected_revision != revision:
            return SignApplyResult(SignApplyStatus.CONFLICT, "sign revision changed", revision)
        del signs[request.location]
        message = "sign removed with item drop" if request.drop_item else "sign removed"
        return SignApplyResult(SignApplyStatus.APPLIED, message)

    def apply(self, patch: SignPatch, *, force: bool = False) -> SignApplyResult:
        with self._lock:
            return self._apply_to(self._signs, patch, force=force)

    def place(self, request: SignPlaceRequest, *, force: bool = False) -> SignApplyResult:
        with self._lock:
            return self._place_into(self._signs, request, force=force)

    def remove(self, request: SignRemoveRequest, *, force: bool = False) -> SignApplyResult:
        with self._lock:
            return self._remove_from(self._signs, request, force=force)

    def transact(self, transaction: SignTransaction) -> SignTransactionResult:
        with self._lock:
            candidate = deepcopy(self._signs)
            results: list[SignApplyResult] = []
            for operation in transaction.operations:
                if isinstance(operation, SignPlaceRequest):
                    result = self._place_into(candidate, operation, force=transaction.force)
                elif isinstance(operation, SignPatch):
                    result = self._apply_to(candidate, operation, force=transaction.force)
                elif isinstance(operation, SignRemoveRequest):
                    result = self._remove_from(candidate, operation, force=transaction.force)
                else:
                    result = SignApplyResult(SignApplyStatus.INVALID_PATCH, "unknown sign operation")
                results.append(result)
                if not result.ok:
                    if transaction.rollback_on_failure:
                        return SignTransactionResult(
                            SignApplyStatus.TRANSACTION_FAILED,
                            f"transaction stopped: {result.message}",
                            tuple(results),
                            True,
                        )
                    self._signs = candidate
                    return SignTransactionResult(
                        SignApplyStatus.TRANSACTION_FAILED,
                        f"transaction partially applied: {result.message}",
                        tuple(results),
                        False,
                    )
            self._signs = candidate
            return SignTransactionResult(
                SignApplyStatus.APPLIED,
                "transaction applied atomically",
                tuple(results),
                False,
            )

    def open_editor(self, player: object, request: SignOpenEditorRequest) -> SignApplyResult:
        del player, request
        return SignApplyResult(
            SignApplyStatus.UNSUPPORTED,
            "the in-memory adapter has no native Bedrock client editor",
        )


class SignService:
    def __init__(
        self,
        adapter: SignAdapter,
        *,
        limits: SignValidationLimits = SignValidationLimits(),
        event_bus: SignEventBus | None = None,
    ) -> None:
        self._adapter = adapter
        self._limits = limits
        self._event_bus = event_bus or SignEventBus()

    @property
    def adapter_name(self) -> str:
        return self._adapter.name

    @property
    def capabilities(self) -> SignCapabilities:
        return self._adapter.capabilities

    @property
    def event_bus(self) -> SignEventBus:
        return self._event_bus

    @staticmethod
    def _validate_location(location: SignLocation) -> str | None:
        if not location.dimension:
            return "dimension must not be empty"
        try:
            location.dimension.encode("utf-8", "strict")
        except UnicodeEncodeError:
            return "dimension is not valid UTF-8"
        if "\x00" in location.dimension:
            return "dimension contains a NUL byte"
        return None

    def _validate_placement(self, request: SignPlaceRequest) -> str | None:
        if error := self._validate_location(request.location):
            return error
        if not is_vanilla_sign_identifier(request.block_identifier):
            return "block identifier is not a supported vanilla placeable sign block"
        if error := validate_sign_block_states(request.block_identifier, request.states):
            return error
        if error := validate_sign_text(request.front, self._limits):
            return f"front text: {error}"
        if error := validate_sign_text(request.back, self._limits):
            return f"back text: {error}"
        if request.locked_for_editing_by < -1:
            return "editor lock runtime ID must be -1 or non-negative"
        if request.locked_for_editing_xuid is not None:
            try:
                lock_size = len(request.locked_for_editing_xuid.encode("utf-8", "strict"))
            except UnicodeEncodeError:
                return "editor lock XUID is not valid UTF-8"
            if "\x00" in request.locked_for_editing_xuid:
                return "editor lock XUID contains a NUL byte"
            if lock_size > self._limits.max_owner_bytes:
                return "editor lock XUID exceeds the configured byte limit"
        return None

    def _validate_patch(self, patch: SignPatch, current: SignSnapshot) -> str | None:
        if error := self._validate_location(patch.location):
            return error
        if patch.block_identifier is not None and not is_vanilla_sign_identifier(patch.block_identifier):
            return "replacement block identifier is not a supported vanilla placeable sign block"
        if patch.front is not None:
            if error := validate_text_patch(patch.front, self._limits):
                return f"front patch: {error}"
            if error := validate_sign_text(apply_text_patch(current.front, patch.front), self._limits):
                return f"front text: {error}"
        if patch.back is not None:
            if error := validate_text_patch(patch.back, self._limits):
                return f"back patch: {error}"
            if error := validate_sign_text(apply_text_patch(current.back, patch.back), self._limits):
                return f"back text: {error}"
        if patch.locked_for_editing_by is not None and patch.locked_for_editing_by < -1:
            return "editor lock runtime ID must be -1 or non-negative"
        if any(not key for key in patch.state_updates):
            return "block state key must not be empty"
        if any(not key for key in patch.state_removals):
            return "block state removal key must not be empty"
        candidate = _apply_patch_to_snapshot(current, patch)
        if error := validate_sign_block_states(candidate.block_identifier, candidate.states):
            return error
        return None

    def _publish_before(
        self,
        kind: SignEventKind,
        location: SignLocation,
        actor: SignActorContext,
        before: SignSnapshot | None,
        after: SignSnapshot | None,
    ) -> str | None:
        event = SignEvent(kind, location, actor, before, after, cancellable=True)
        self._event_bus.publish(event)
        if event.cancelled:
            return event.cancellation_reason or "sign operation cancelled"
        return None

    def _publish_after(
        self,
        kind: SignEventKind,
        location: SignLocation,
        actor: SignActorContext,
        before: SignSnapshot | None,
        after: SignSnapshot | None,
    ) -> None:
        self._event_bus.publish(SignEvent(kind, location, actor, before, after))

    def capture(self, location: SignLocation) -> SignSnapshot | None:
        if self._validate_location(location):
            return None
        snapshot = self._adapter.capture(location)
        if snapshot is None:
            return None
        snapshot = replace(snapshot, kind=classify_sign(snapshot.block_identifier, dict(snapshot.states)))
        return replace(snapshot, revision=calculate_revision(snapshot))

    def apply(
        self,
        patch: SignPatch,
        *,
        force: bool = False,
        actor: SignActorContext = SignActorContext(),
    ) -> SignApplyResult:
        actor = _with_origin(actor, patch.origin)
        current = self.capture(patch.location)
        if current is None:
            return SignApplyResult(SignApplyStatus.NOT_A_SIGN, "the target block is not an accessible sign")
        if patch_is_empty(patch):
            return SignApplyResult(SignApplyStatus.APPLIED, "sign unchanged", current.revision)
        if patch.expected_revision is not None and not force and patch.expected_revision != current.revision:
            return SignApplyResult(SignApplyStatus.CONFLICT, "sign revision changed", current.revision)
        if error := self._validate_patch(patch, current):
            return SignApplyResult(SignApplyStatus.INVALID_PATCH, error, current.revision)
        candidate = _apply_patch_to_snapshot(current, patch)
        before_kind, after_kind = _patch_event_kinds(patch, current, candidate)
        if reason := self._publish_before(before_kind, patch.location, actor, current, candidate):
            return SignApplyResult(SignApplyStatus.CANCELLED, reason, current.revision)
        result = self._adapter.apply(patch, force=force)
        if result.ok:
            self._publish_after(after_kind, patch.location, actor, current, self.capture(patch.location))
        return result

    def place(
        self,
        request: SignPlaceRequest,
        *,
        force: bool = False,
        actor: SignActorContext = SignActorContext(),
    ) -> SignApplyResult:
        actor = _with_origin(actor, request.origin)
        if error := self._validate_placement(request):
            return SignApplyResult(SignApplyStatus.INVALID_PATCH, error)
        before = self.capture(request.location)
        actual = 0 if before is None else before.revision
        if (
            request.expected_destination_revision is not None
            and not force
            and request.expected_destination_revision != actual
        ):
            return SignApplyResult(SignApplyStatus.CONFLICT, "destination revision changed", actual)
        after = _snapshot_from_place(request)
        if reason := self._publish_before(SignEventKind.BEFORE_PLACE, request.location, actor, before, after):
            return SignApplyResult(SignApplyStatus.CANCELLED, reason, actual)
        result = self._adapter.place(request, force=force)
        if result.ok:
            self._publish_after(SignEventKind.AFTER_PLACE, request.location, actor, before, self.capture(request.location))
        return result

    def remove(
        self,
        request: SignRemoveRequest,
        *,
        force: bool = False,
        actor: SignActorContext = SignActorContext(),
    ) -> SignApplyResult:
        actor = _with_origin(actor, request.origin)
        if error := self._validate_location(request.location):
            return SignApplyResult(SignApplyStatus.INVALID_PATCH, error)
        before = self.capture(request.location)
        if before is None:
            return SignApplyResult(SignApplyStatus.NOT_A_SIGN, "the target block is not an accessible sign")
        if request.expected_revision is not None and not force and request.expected_revision != before.revision:
            return SignApplyResult(SignApplyStatus.CONFLICT, "sign revision changed", before.revision)
        if reason := self._publish_before(SignEventKind.BEFORE_REMOVE, request.location, actor, before, None):
            return SignApplyResult(SignApplyStatus.CANCELLED, reason, before.revision)
        result = self._adapter.remove(request, force=force)
        if result.ok:
            self._publish_after(SignEventKind.AFTER_REMOVE, request.location, actor, before, None)
        return result

    def clone_sign(
        self,
        request: SignCloneRequest,
        *,
        force: bool = False,
        actor: SignActorContext = SignActorContext(),
    ) -> SignApplyResult:
        if request.source == request.destination:
            return SignApplyResult(SignApplyStatus.INVALID_PATCH, "source and destination must differ")
        source = self.capture(request.source)
        if source is None:
            return SignApplyResult(SignApplyStatus.NOT_A_SIGN, "source sign not found")
        if (
            request.expected_source_revision is not None
            and not force
            and request.expected_source_revision != source.revision
        ):
            return SignApplyResult(SignApplyStatus.CONFLICT, "source sign revision changed", source.revision)
        operations: list[SignOperation] = [SignPlaceRequest(
            location=request.destination,
            block_identifier=source.block_identifier,
            states=dict(source.states),
            front=source.front,
            back=source.back,
            waxed=source.waxed,
            locked_for_editing_by=(source.locked_for_editing_by if request.copy_editor_lock else -1),
            locked_for_editing_xuid=(source.locked_for_editing_xuid if request.copy_editor_lock else None),
            remote_profanity_filter_enabled=source.remote_profanity_filter_enabled,
            local_profanity_filter_enabled=source.local_profanity_filter_enabled,
            replace_policy=request.replace_policy,
            send_client_update=request.send_client_update,
            origin=request.origin,
        )]
        result = self.transact(
            SignTransaction(tuple(operations), force=force, audit_reason="clone sign"),
            actor=actor,
        )
        if not result.ok:
            return SignApplyResult(result.status, result.message)
        destination = self.capture(request.destination)
        return SignApplyResult(
            SignApplyStatus.APPLIED,
            "sign cloned",
            0 if destination is None else destination.revision,
        )

    def move_sign(
        self,
        request: SignMoveRequest,
        *,
        force: bool = False,
        actor: SignActorContext = SignActorContext(),
    ) -> SignApplyResult:
        if request.source == request.destination:
            return SignApplyResult(SignApplyStatus.INVALID_PATCH, "source and destination must differ")
        source = self.capture(request.source)
        if source is None:
            return SignApplyResult(SignApplyStatus.NOT_A_SIGN, "source sign not found")
        if (
            request.expected_source_revision is not None
            and not force
            and request.expected_source_revision != source.revision
        ):
            return SignApplyResult(SignApplyStatus.CONFLICT, "source sign revision changed", source.revision)
        operations: list[SignOperation] = [SignPlaceRequest(
            location=request.destination,
            block_identifier=source.block_identifier,
            states=dict(source.states),
            front=source.front,
            back=source.back,
            waxed=source.waxed,
            locked_for_editing_by=(source.locked_for_editing_by if request.copy_editor_lock else -1),
            locked_for_editing_xuid=(source.locked_for_editing_xuid if request.copy_editor_lock else None),
            remote_profanity_filter_enabled=source.remote_profanity_filter_enabled,
            local_profanity_filter_enabled=source.local_profanity_filter_enabled,
            replace_policy=request.replace_policy,
            send_client_update=request.send_client_update,
            origin=request.origin,
        )]
        operations.append(SignRemoveRequest(
            location=request.source,
            expected_revision=source.revision,
            send_client_update=request.send_client_update,
            origin=request.origin,
        ))
        result = self.transact(
            SignTransaction(tuple(operations), force=force, audit_reason="move sign"),
            actor=actor,
        )
        if not result.ok:
            return SignApplyResult(result.status, result.message, source.revision)
        destination = self.capture(request.destination)
        return SignApplyResult(
            SignApplyStatus.APPLIED,
            "sign moved",
            0 if destination is None else destination.revision,
        )

    def _prepare_transaction_events(
        self,
        transaction: SignTransaction,
        actor: SignActorContext,
    ) -> tuple[SignApplyResult | None, list[tuple[SignEventKind, SignEventKind, SignLocation, SignActorContext, SignSnapshot | None, SignSnapshot | None]]]:
        projected: dict[SignLocation, SignSnapshot | None] = {}
        events: list[tuple[SignEventKind, SignEventKind, SignLocation, SignActorContext, SignSnapshot | None, SignSnapshot | None]] = []

        def state_for(location: SignLocation) -> SignSnapshot | None:
            if location not in projected:
                projected[location] = self.capture(location)
            return projected[location]

        for operation in transaction.operations:
            if isinstance(operation, SignPlaceRequest):
                if error := self._validate_placement(operation):
                    return SignApplyResult(SignApplyStatus.INVALID_PATCH, error), []
                before = state_for(operation.location)
                actual = 0 if before is None else before.revision
                if (
                    operation.expected_destination_revision is not None
                    and not transaction.force
                    and operation.expected_destination_revision != actual
                ):
                    return SignApplyResult(SignApplyStatus.CONFLICT, "destination revision changed", actual), []
                if (
                    before is not None
                    and not transaction.force
                    and operation.replace_policy is not SignReplacePolicy.FORCE
                ):
                    return SignApplyResult(SignApplyStatus.BLOCK_OCCUPIED, "destination already contains a sign", actual), []
                after = _snapshot_from_place(operation)
                projected[operation.location] = after
                op_actor = _with_origin(actor, operation.origin)
                events.append((SignEventKind.BEFORE_PLACE, SignEventKind.AFTER_PLACE, operation.location, op_actor, before, after))
            elif isinstance(operation, SignPatch):
                before = state_for(operation.location)
                if before is None:
                    return SignApplyResult(SignApplyStatus.NOT_A_SIGN, "patch target is not an accessible sign"), []
                if (
                    operation.expected_revision is not None
                    and not transaction.force
                    and operation.expected_revision != before.revision
                ):
                    return SignApplyResult(SignApplyStatus.CONFLICT, "sign revision changed", before.revision), []
                if error := self._validate_patch(operation, before):
                    return SignApplyResult(SignApplyStatus.INVALID_PATCH, error, before.revision), []
                after = _apply_patch_to_snapshot(before, operation)
                projected[operation.location] = after
                before_kind, after_kind = _patch_event_kinds(operation, before, after)
                op_actor = _with_origin(actor, operation.origin)
                events.append((before_kind, after_kind, operation.location, op_actor, before, after))
            elif isinstance(operation, SignRemoveRequest):
                if error := self._validate_location(operation.location):
                    return SignApplyResult(SignApplyStatus.INVALID_PATCH, error), []
                before = state_for(operation.location)
                if before is None:
                    return SignApplyResult(SignApplyStatus.NOT_A_SIGN, "remove target is not an accessible sign"), []
                if (
                    operation.expected_revision is not None
                    and not transaction.force
                    and operation.expected_revision != before.revision
                ):
                    return SignApplyResult(SignApplyStatus.CONFLICT, "sign revision changed", before.revision), []
                projected[operation.location] = None
                op_actor = _with_origin(actor, operation.origin)
                events.append((SignEventKind.BEFORE_REMOVE, SignEventKind.AFTER_REMOVE, operation.location, op_actor, before, None))
            else:
                return SignApplyResult(SignApplyStatus.INVALID_PATCH, "unknown sign operation"), []

        for before_kind, _, location, op_actor, before, after in events:
            if reason := self._publish_before(before_kind, location, op_actor, before, after):
                revision = 0 if before is None else before.revision
                return SignApplyResult(SignApplyStatus.CANCELLED, reason, revision), []
        return None, events

    def transact(
        self,
        transaction: SignTransaction,
        *,
        actor: SignActorContext = SignActorContext(),
    ) -> SignTransactionResult:
        if not transaction.operations:
            return SignTransactionResult(SignApplyStatus.APPLIED, "empty transaction")
        if len(transaction.operations) > 1 and not self.capabilities.atomic_transactions:
            return SignTransactionResult(
                SignApplyStatus.UNSUPPORTED,
                "adapter does not provide atomic sign transactions",
            )
        rejected, events = self._prepare_transaction_events(transaction, actor)
        if rejected is not None:
            return SignTransactionResult(rejected.status, rejected.message, (rejected,))
        result = self._adapter.transact(transaction)
        if result.ok:
            for _, after_kind, location, op_actor, before, projected_after in events:
                actual_after = None if projected_after is None else self.capture(location)
                self._publish_after(after_kind, location, op_actor, before, actual_after)
        return result

    def open_editor(
        self,
        player: object,
        request: SignOpenEditorRequest,
        *,
        actor: SignActorContext = SignActorContext(),
    ) -> SignApplyResult:
        if error := self._validate_location(request.location):
            return SignApplyResult(SignApplyStatus.INVALID_PATCH, error)
        current = self.capture(request.location)
        if current is None:
            return SignApplyResult(SignApplyStatus.NOT_A_SIGN, "the target block is not an accessible sign")
        if request.expected_revision is not None and request.expected_revision != current.revision:
            return SignApplyResult(SignApplyStatus.CONFLICT, "sign revision changed", current.revision)
        if current.waxed and not request.bypass_wax:
            return SignApplyResult(
                SignApplyStatus.PERMISSION_DENIED,
                "waxed signs cannot be opened for editing",
                current.revision,
            )
        if reason := self._publish_before(
            SignEventKind.BEFORE_OPEN_EDITOR,
            request.location,
            actor,
            current,
            current,
        ):
            return SignApplyResult(SignApplyStatus.CANCELLED, reason, current.revision)
        result = self._adapter.open_editor(player, request)
        if result.ok:
            self._publish_after(
                SignEventKind.AFTER_OPEN_EDITOR,
                request.location,
                actor,
                current,
                self.capture(request.location),
            )
        return result


class InMemorySignService(SignService):
    """Compatibility convenience wrapper around ``SignService`` and the reference adapter."""

    def __init__(
        self,
        *,
        max_line_bytes: int = 384,
        max_total_bytes: int = 1536,
        limits: SignValidationLimits | None = None,
        event_bus: SignEventBus | None = None,
    ) -> None:
        self.reference_adapter = InMemorySignAdapter()
        effective_limits = limits or SignValidationLimits(
            max_line_bytes=max_line_bytes,
            max_total_bytes=max_total_bytes,
        )
        super().__init__(self.reference_adapter, limits=effective_limits, event_bus=event_bus)

    def upsert(self, snapshot: SignSnapshot) -> None:
        self.reference_adapter.upsert(snapshot)

    def erase(self, location: SignLocation) -> bool:
        return self.reference_adapter.erase(location)
