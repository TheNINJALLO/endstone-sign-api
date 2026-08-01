#include "endstone_sign/service.h"

#include "endstone_sign/placement.h"

#include <map>
#include <stdexcept>
#include <type_traits>
#include <utility>

namespace endstone_sign {
namespace {

SignActorContext withOrigin(SignActorContext actor, SignMutationOrigin origin) {
    if (actor.origin == SignMutationOrigin::Unknown) actor.origin = origin;
    return actor;
}

SignSnapshot snapshotFromPlace(const SignPlaceRequest &request) {
    SignSnapshot snapshot;
    snapshot.location = request.location;
    snapshot.block_identifier = request.block_identifier;
    snapshot.states = request.states;
    snapshot.kind = classifySign(snapshot.block_identifier, snapshot.states);
    snapshot.front = request.front;
    snapshot.back = request.back;
    snapshot.waxed = request.waxed;
    snapshot.locked_for_editing_by = request.locked_for_editing_by;
    snapshot.locked_for_editing_xuid = request.locked_for_editing_xuid;
    snapshot.remote_profanity_filter_enabled = request.remote_profanity_filter_enabled;
    snapshot.local_profanity_filter_enabled = request.local_profanity_filter_enabled;
    snapshot.actor_status = SignActorStatus::Captured;
    snapshot.revision = calculateSignRevision(snapshot);
    return snapshot;
}

SignSnapshot applyPatchToSnapshot(SignSnapshot snapshot, const SignPatch &patch) {
    if (patch.block_identifier) snapshot.block_identifier = *patch.block_identifier;
    for (const auto &[key, value] : patch.state_updates)
        snapshot.states.insert_or_assign(key, value);
    for (const auto &key : patch.state_removals) snapshot.states.erase(key);
    if (patch.front) snapshot.front = applyTextPatch(snapshot.front, *patch.front);
    if (patch.back) snapshot.back = applyTextPatch(snapshot.back, *patch.back);
    if (patch.waxed) snapshot.waxed = *patch.waxed;
    if (patch.locked_for_editing_by)
        snapshot.locked_for_editing_by = *patch.locked_for_editing_by;
    if (patch.locked_for_editing_xuid) {
        if (patch.locked_for_editing_xuid->empty()) snapshot.locked_for_editing_xuid.reset();
        else snapshot.locked_for_editing_xuid = *patch.locked_for_editing_xuid;
    }
    if (patch.remote_profanity_filter_enabled)
        snapshot.remote_profanity_filter_enabled = *patch.remote_profanity_filter_enabled;
    if (patch.local_profanity_filter_enabled)
        snapshot.local_profanity_filter_enabled = *patch.local_profanity_filter_enabled;
    snapshot.kind = classifySign(snapshot.block_identifier, snapshot.states);
    snapshot.canonical_snbt.clear();
    snapshot.revision = calculateSignRevision(snapshot);
    return snapshot;
}

bool isLockOnlyPatch(const SignPatch &patch) noexcept {
    return !patch.block_identifier && patch.state_updates.empty() && patch.state_removals.empty() &&
           !patch.front && !patch.back && !patch.waxed &&
           (patch.locked_for_editing_by || patch.locked_for_editing_xuid) &&
           !patch.remote_profanity_filter_enabled && !patch.local_profanity_filter_enabled;
}

std::pair<SignEventKind, SignEventKind> patchEventKinds(
    const SignPatch &patch,
    const SignSnapshot &before,
    const SignSnapshot &after) noexcept {
    if (isLockOnlyPatch(patch)) {
        const bool was_locked = before.locked_for_editing_by >= 0 ||
                                before.locked_for_editing_xuid.has_value();
        const bool is_locked = after.locked_for_editing_by >= 0 ||
                               after.locked_for_editing_xuid.has_value();
        if (!was_locked && is_locked)
            return {SignEventKind::BeforeLock, SignEventKind::AfterLock};
        if (was_locked && !is_locked)
            return {SignEventKind::BeforeUnlock, SignEventKind::AfterUnlock};
    }
    return {SignEventKind::BeforeChange, SignEventKind::AfterChange};
}

} // namespace

bool patchIsEmpty(const SignPatch &patch) noexcept {
    return !patch.block_identifier && patch.state_updates.empty() && patch.state_removals.empty() &&
           !patch.front && !patch.back && !patch.waxed && !patch.locked_for_editing_by &&
           !patch.locked_for_editing_xuid && !patch.remote_profanity_filter_enabled &&
           !patch.local_profanity_filter_enabled;
}

SignService::SignService(
    std::shared_ptr<ISignAdapter> adapter,
    SignValidationLimits limits,
    std::shared_ptr<SignEventBus> event_bus)
    : adapter_(std::move(adapter)), limits_(limits),
      event_bus_(event_bus ? std::move(event_bus) : std::make_shared<SignEventBus>()) {
    if (!adapter_) throw std::invalid_argument("SignService requires an adapter");
    adapter_->bindEventBus(event_bus_);
}

std::optional<std::string> SignService::validateLocation(
    const SignLocation &location) const {
    if (location.dimension.empty()) return "dimension must not be empty";
    if (!isValidUtf8(location.dimension) || location.dimension.find('\0') != std::string::npos)
        return "dimension is not a valid UTF-8 identifier";
    return std::nullopt;
}

std::optional<std::string> SignService::validatePlacement(
    const SignPlaceRequest &request) const {
    if (const auto error = validateLocation(request.location)) return error;
    if (!isVanillaSignIdentifier(request.block_identifier))
        return "block identifier is not a supported vanilla sign block";
    if (const auto error = validateSignBlockStates(request.block_identifier, request.states))
        return error;
    if (const auto error = validateSignText(request.front, limits_))
        return "front text: " + *error;
    if (const auto error = validateSignText(request.back, limits_))
        return "back text: " + *error;
    if (request.locked_for_editing_by < -1)
        return "editor lock runtime ID must be -1 or non-negative";
    if (request.locked_for_editing_xuid) {
        if (!isValidUtf8(*request.locked_for_editing_xuid) ||
            request.locked_for_editing_xuid->find('\0') != std::string::npos) {
            return "editor lock XUID is not valid UTF-8";
        }
        if (request.locked_for_editing_xuid->size() > limits_.max_owner_bytes)
            return "editor lock XUID exceeds the configured byte limit";
    }
    return std::nullopt;
}

std::optional<std::string> SignService::validatePatch(
    const SignPatch &patch,
    const SignSnapshot &current) const {
    if (const auto error = validateLocation(patch.location)) return error;
    if (patch.block_identifier && !isVanillaSignIdentifier(*patch.block_identifier))
        return "replacement block identifier is not a supported vanilla sign block";
    if (patch.front) {
        if (const auto error = validateTextPatch(*patch.front, limits_))
            return "front patch: " + *error;
    }
    if (patch.back) {
        if (const auto error = validateTextPatch(*patch.back, limits_))
            return "back patch: " + *error;
    }
    if (patch.locked_for_editing_by && *patch.locked_for_editing_by < -1)
        return "editor lock runtime ID must be -1 or non-negative";
    if (patch.locked_for_editing_xuid) {
        if (!isValidUtf8(*patch.locked_for_editing_xuid) ||
            patch.locked_for_editing_xuid->find('\0') != std::string::npos) {
            return "editor lock XUID is not valid UTF-8";
        }
        if (patch.locked_for_editing_xuid->size() > limits_.max_owner_bytes)
            return "editor lock XUID exceeds the configured byte limit";
    }

    const auto candidate = applyPatchToSnapshot(current, patch);
    if (const auto error = validateSignBlockStates(
            candidate.block_identifier, candidate.states)) {
        return error;
    }
    if (const auto error = validateSignText(candidate.front, limits_))
        return "front text: " + *error;
    if (const auto error = validateSignText(candidate.back, limits_))
        return "back text: " + *error;
    return std::nullopt;
}

bool SignService::publishBefore(
    SignEventKind kind,
    const SignLocation &location,
    const SignActorContext &actor,
    std::optional<SignSnapshot> before,
    std::optional<SignSnapshot> after,
    std::string &reason) const {
    SignEvent event{
        kind,
        location,
        actor,
        std::move(before),
        std::move(after),
        true,
        false,
        {},
    };
    event_bus_->publish(event);
    if (!event.cancelled) return true;
    reason = event.cancellation_reason.empty()
                 ? "sign operation cancelled"
                 : event.cancellation_reason;
    return false;
}

void SignService::publishAfter(
    SignEventKind kind,
    const SignLocation &location,
    const SignActorContext &actor,
    std::optional<SignSnapshot> before,
    std::optional<SignSnapshot> after) const {
    SignEvent event{
        kind,
        location,
        actor,
        std::move(before),
        std::move(after),
        false,
        false,
        {},
    };
    event_bus_->publish(event);
}

std::optional<SignSnapshot> SignService::capture(const SignLocation &location) {
    if (validateLocation(location)) return std::nullopt;
    auto snapshot = adapter_->capture(location);
    if (snapshot) {
        snapshot->kind = classifySign(snapshot->block_identifier, snapshot->states);
        snapshot->revision = calculateSignRevision(*snapshot);
    }
    return snapshot;
}

SignApplyResult SignService::apply(
    const SignPatch &patch,
    bool force,
    SignActorContext actor) {
    actor = withOrigin(std::move(actor), patch.origin);
    auto current = capture(patch.location);
    if (!current)
        return {SignApplyStatus::NotASign, "the target block is not an accessible sign", 0};
    if (patchIsEmpty(patch))
        return {SignApplyStatus::Applied, "sign unchanged", current->revision};
    if (patch.expected_revision && !force && *patch.expected_revision != current->revision)
        return {SignApplyStatus::Conflict, "sign revision changed", current->revision};
    if (const auto error = validatePatch(patch, *current))
        return {SignApplyStatus::InvalidPatch, *error, current->revision};

    const auto candidate = applyPatchToSnapshot(*current, patch);
    const auto [before_kind, after_kind] = patchEventKinds(patch, *current, candidate);
    std::string reason;
    if (!publishBefore(
            before_kind, patch.location, actor, current, candidate, reason)) {
        return {SignApplyStatus::Cancelled, reason, current->revision};
    }
    auto result = adapter_->apply(patch, force);
    if (result.ok()) {
        publishAfter(after_kind, patch.location, actor, current, capture(patch.location));
    }
    return result;
}

SignApplyResult SignService::place(
    const SignPlaceRequest &request,
    bool force,
    SignActorContext actor) {
    actor = withOrigin(std::move(actor), request.origin);
    if (const auto error = validatePlacement(request))
        return {SignApplyStatus::InvalidPatch, *error, 0};

    const auto before = capture(request.location);
    if (request.expected_destination_revision && !force) {
        const auto actual = before ? before->revision : 0;
        if (*request.expected_destination_revision != actual)
            return {SignApplyStatus::Conflict, "destination revision changed", actual};
    }
    const auto expected_after = snapshotFromPlace(request);
    std::string reason;
    if (!publishBefore(
            SignEventKind::BeforePlace,
            request.location,
            actor,
            before,
            expected_after,
            reason)) {
        return {SignApplyStatus::Cancelled, reason, before ? before->revision : 0};
    }
    auto result = adapter_->place(request, force);
    if (result.ok()) {
        publishAfter(
            SignEventKind::AfterPlace,
            request.location,
            actor,
            before,
            capture(request.location));
    }
    return result;
}

SignApplyResult SignService::remove(
    const SignRemoveRequest &request,
    bool force,
    SignActorContext actor) {
    actor = withOrigin(std::move(actor), request.origin);
    if (const auto error = validateLocation(request.location))
        return {SignApplyStatus::InvalidPatch, *error, 0};
    const auto before = capture(request.location);
    if (!before)
        return {SignApplyStatus::NotASign, "the target block is not an accessible sign", 0};
    if (request.expected_revision && !force && *request.expected_revision != before->revision)
        return {SignApplyStatus::Conflict, "sign revision changed", before->revision};

    std::string reason;
    if (!publishBefore(
            SignEventKind::BeforeRemove,
            request.location,
            actor,
            before,
            std::nullopt,
            reason)) {
        return {SignApplyStatus::Cancelled, reason, before->revision};
    }
    auto result = adapter_->remove(request, force);
    if (result.ok()) {
        publishAfter(
            SignEventKind::AfterRemove,
            request.location,
            actor,
            before,
            std::nullopt);
    }
    return result;
}

SignApplyResult SignService::cloneSign(
    const SignCloneRequest &request,
    bool force,
    SignActorContext actor) {
    actor = withOrigin(std::move(actor), request.origin);
    if (request.source == request.destination)
        return {SignApplyStatus::InvalidPatch, "source and destination must differ", 0};
    const auto source = capture(request.source);
    if (!source) return {SignApplyStatus::NotASign, "source sign not found", 0};
    if (request.expected_source_revision && !force &&
        *request.expected_source_revision != source->revision) {
        return {SignApplyStatus::Conflict, "source sign revision changed", source->revision};
    }

    SignPlaceRequest place_request;
    place_request.location = request.destination;
    place_request.block_identifier = source->block_identifier;
    place_request.states = source->states;
    place_request.front = source->front;
    place_request.back = source->back;
    place_request.waxed = source->waxed;
    place_request.locked_for_editing_by =
        request.copy_editor_lock ? source->locked_for_editing_by : -1;
    if (request.copy_editor_lock)
        place_request.locked_for_editing_xuid = source->locked_for_editing_xuid;
    place_request.remote_profanity_filter_enabled =
        source->remote_profanity_filter_enabled;
    place_request.local_profanity_filter_enabled =
        source->local_profanity_filter_enabled;
    place_request.replace_policy = request.replace_policy;
    place_request.send_client_update = request.send_client_update;
    place_request.origin = request.origin;

    SignTransaction transaction;
    transaction.force = force;
    transaction.rollback_on_failure = true;
    transaction.audit_reason = "clone sign";
    transaction.operations.emplace_back(place_request);
    auto result = transact(transaction, actor);
    if (!result.ok()) return {result.status, result.message, 0};
    const auto destination = capture(request.destination);
    return {
        SignApplyStatus::Applied,
        "sign cloned",
        destination ? destination->revision : 0,
    };
}

SignApplyResult SignService::moveSign(
    const SignMoveRequest &request,
    bool force,
    SignActorContext actor) {
    actor = withOrigin(std::move(actor), request.origin);
    if (request.source == request.destination)
        return {SignApplyStatus::InvalidPatch, "source and destination must differ", 0};
    const auto source = capture(request.source);
    if (!source) return {SignApplyStatus::NotASign, "source sign not found", 0};
    if (request.expected_source_revision && !force &&
        *request.expected_source_revision != source->revision) {
        return {SignApplyStatus::Conflict, "source sign revision changed", source->revision};
    }

    SignPlaceRequest place_request;
    place_request.location = request.destination;
    place_request.block_identifier = source->block_identifier;
    place_request.states = source->states;
    place_request.front = source->front;
    place_request.back = source->back;
    place_request.waxed = source->waxed;
    place_request.locked_for_editing_by =
        request.copy_editor_lock ? source->locked_for_editing_by : -1;
    if (request.copy_editor_lock)
        place_request.locked_for_editing_xuid = source->locked_for_editing_xuid;
    place_request.remote_profanity_filter_enabled =
        source->remote_profanity_filter_enabled;
    place_request.local_profanity_filter_enabled =
        source->local_profanity_filter_enabled;
    place_request.replace_policy = request.replace_policy;
    place_request.send_client_update = request.send_client_update;
    place_request.origin = request.origin;

    SignRemoveRequest remove_request;
    remove_request.location = request.source;
    remove_request.expected_revision = source->revision;
    remove_request.send_client_update = request.send_client_update;
    remove_request.origin = request.origin;

    SignTransaction transaction;
    transaction.force = force;
    transaction.rollback_on_failure = true;
    transaction.audit_reason = "move sign";
    transaction.operations.emplace_back(place_request);
    transaction.operations.emplace_back(remove_request);

    auto result = transact(transaction, actor);
    if (!result.ok()) return {result.status, result.message, source->revision};
    const auto destination = capture(request.destination);
    return {
        SignApplyStatus::Applied,
        "sign moved",
        destination ? destination->revision : 0,
    };
}

std::optional<SignApplyResult> SignService::prepareTransactionEvents(
    const SignTransaction &transaction,
    const SignActorContext &actor,
    std::vector<PreparedEvent> &events) {
    std::map<SignLocation, std::optional<SignSnapshot>> projected;
    auto state_for = [&](const SignLocation &location) -> std::optional<SignSnapshot> & {
        const auto found = projected.find(location);
        if (found != projected.end()) return found->second;
        auto [inserted, _] = projected.emplace(location, capture(location));
        return inserted->second;
    };

    for (const auto &operation : transaction.operations) {
        const auto error = std::visit(
            [&](const auto &entry) -> std::optional<SignApplyResult> {
                using T = std::decay_t<decltype(entry)>;
                if constexpr (std::is_same_v<T, SignPlaceRequest>) {
                    if (const auto validation = validatePlacement(entry))
                        return SignApplyResult{SignApplyStatus::InvalidPatch, *validation, 0};
                    auto &current = state_for(entry.location);
                    const auto current_revision = current ? current->revision : 0;
                    if (entry.expected_destination_revision && !transaction.force &&
                        *entry.expected_destination_revision != current_revision) {
                        return SignApplyResult{
                            SignApplyStatus::Conflict,
                            "destination revision changed",
                            current_revision,
                        };
                    }
                    if (current && !transaction.force &&
                        entry.replace_policy != SignReplacePolicy::Force) {
                        return SignApplyResult{
                            SignApplyStatus::BlockOccupied,
                            "destination already contains a sign",
                            current_revision,
                        };
                    }
                    auto after = snapshotFromPlace(entry);
                    events.push_back({
                        SignEventKind::BeforePlace,
                        SignEventKind::AfterPlace,
                        entry.location,
                        withOrigin(actor, entry.origin),
                        current,
                        after,
                    });
                    current = std::move(after);
                    return std::nullopt;
                } else if constexpr (std::is_same_v<T, SignPatch>) {
                    auto &current = state_for(entry.location);
                    if (!current) {
                        return SignApplyResult{
                            SignApplyStatus::NotASign,
                            "transaction patch target is not an accessible sign",
                            0,
                        };
                    }
                    if (entry.expected_revision && !transaction.force &&
                        *entry.expected_revision != current->revision) {
                        return SignApplyResult{
                            SignApplyStatus::Conflict,
                            "sign revision changed",
                            current->revision,
                        };
                    }
                    if (const auto validation = validatePatch(entry, *current)) {
                        return SignApplyResult{
                            SignApplyStatus::InvalidPatch,
                            *validation,
                            current->revision,
                        };
                    }
                    const auto before = *current;
                    auto after = applyPatchToSnapshot(before, entry);
                    const auto [before_kind, after_kind] =
                        patchEventKinds(entry, before, after);
                    events.push_back({
                        before_kind,
                        after_kind,
                        entry.location,
                        withOrigin(actor, entry.origin),
                        before,
                        after,
                    });
                    current = std::move(after);
                    return std::nullopt;
                } else {
                    if (const auto validation = validateLocation(entry.location))
                        return SignApplyResult{SignApplyStatus::InvalidPatch, *validation, 0};
                    auto &current = state_for(entry.location);
                    if (!current) {
                        return SignApplyResult{
                            SignApplyStatus::NotASign,
                            "transaction remove target is not an accessible sign",
                            0,
                        };
                    }
                    if (entry.expected_revision && !transaction.force &&
                        *entry.expected_revision != current->revision) {
                        return SignApplyResult{
                            SignApplyStatus::Conflict,
                            "sign revision changed",
                            current->revision,
                        };
                    }
                    events.push_back({
                        SignEventKind::BeforeRemove,
                        SignEventKind::AfterRemove,
                        entry.location,
                        withOrigin(actor, entry.origin),
                        current,
                        std::nullopt,
                    });
                    current.reset();
                    return std::nullopt;
                }
            },
            operation);
        if (error) return error;
    }
    return std::nullopt;
}

SignTransactionResult SignService::transact(
    const SignTransaction &transaction,
    SignActorContext actor) {
    if (transaction.operations.empty())
        return {SignApplyStatus::Applied, "empty transaction", {}, false};
    if (transaction.operations.size() > 1 && !adapter_->capabilities().atomic_transactions) {
        return {
            SignApplyStatus::Unsupported,
            "adapter does not provide atomic sign transactions",
            {},
            false,
        };
    }

    std::vector<PreparedEvent> events;
    events.reserve(transaction.operations.size());
    if (const auto error = prepareTransactionEvents(transaction, actor, events)) {
        return {error->status, error->message, {*error}, false};
    }

    for (const auto &event : events) {
        std::string reason;
        if (!publishBefore(
                event.before_kind,
                event.location,
                event.actor,
                event.before,
                event.expected_after,
                reason)) {
            return {
                SignApplyStatus::Cancelled,
                reason,
                {{SignApplyStatus::Cancelled, reason, event.before ? event.before->revision : 0}},
                false,
            };
        }
    }

    auto result = adapter_->transact(transaction);
    if (!result.ok()) return result;

    for (const auto &event : events) {
        publishAfter(
            event.after_kind,
            event.location,
            event.actor,
            event.before,
            capture(event.location));
    }
    return result;
}

SignApplyResult SignService::openEditor(
    endstone::Player &player,
    const SignOpenEditorRequest &request,
    SignActorContext actor) {
    if (actor.origin == SignMutationOrigin::Unknown)
        actor.origin = SignMutationOrigin::Player;
    if (const auto error = validateLocation(request.location))
        return {SignApplyStatus::InvalidPatch, *error, 0};
    const auto current = capture(request.location);
    if (!current)
        return {SignApplyStatus::NotASign, "the target block is not an accessible sign", 0};
    if (request.expected_revision && *request.expected_revision != current->revision)
        return {SignApplyStatus::Conflict, "sign revision changed", current->revision};
    if (current->waxed && !request.bypass_wax) {
        return {
            SignApplyStatus::PermissionDenied,
            "waxed signs cannot be opened for editing",
            current->revision,
        };
    }

    std::string reason;
    if (!publishBefore(
            SignEventKind::BeforeOpenEditor,
            request.location,
            actor,
            current,
            current,
            reason)) {
        return {SignApplyStatus::Cancelled, reason, current->revision};
    }
    auto result = adapter_->openEditor(player, request);
    if (result.ok()) {
        publishAfter(
            SignEventKind::AfterOpenEditor,
            request.location,
            actor,
            current,
            capture(request.location));
    }
    return result;
}

SignCapabilities SignService::capabilities() const noexcept {
    return adapter_->capabilities();
}

std::string SignService::adapterName() const {
    return std::string(adapter_->name());
}

} // namespace endstone_sign
