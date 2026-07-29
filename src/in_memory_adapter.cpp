#include "endstone_sign/in_memory_adapter.h"

#include "endstone_sign/placement.h"

#include <type_traits>
#include <utility>

namespace endstone_sign {

std::string_view InMemorySignAdapter::name() const noexcept {
    return "in-memory-sign-adapter-v2";
}

SignCapabilities InMemorySignAdapter::capabilities() const noexcept {
    SignCapabilities caps;
    caps.capture = true;
    caps.place = true;
    caps.remove = true;
    caps.replace = true;
    caps.clone = true;
    caps.move = true;
    caps.atomic_transactions = true;
    caps.read_text = true;
    caps.write_text = true;
    caps.front_and_back = true;
    caps.per_line_write = true;
    caps.text_objects = true;
    caps.filtered_text = true;
    caps.owner_xuid = true;
    caps.text_color = true;
    caps.glowing = true;
    caps.hide_glow_outline = true;
    caps.persist_formatting = true;
    caps.waxed = true;
    caps.editor_lock = true;
    caps.api_edit_events = true;
    caps.exact_build_match = true;
    caps.exact_binary_hash_match = true;
    caps.symbols_validated = true;
    caps.stage_probe_passed = true;
    // Native-only client behavior is intentionally false for this reference adapter.
    caps.open_editor = false;
    caps.player_edit_events = false;
    caps.client_updates = false;
    caps.restart_persistence = false;
    return caps;
}

std::optional<SignSnapshot> InMemorySignAdapter::capture(const SignLocation &location) {
    std::scoped_lock lock(mutex_);
    const auto it = signs_.find(location);
    if (it == signs_.end()) return std::nullopt;
    auto snapshot = it->second;
    snapshot.kind = classifySign(snapshot.block_identifier, snapshot.states);
    snapshot.revision = calculateSignRevision(snapshot);
    return snapshot;
}

SignApplyResult InMemorySignAdapter::applyTo(
    SignMap &signs,
    const SignPatch &patch,
    bool force) {
    const auto it = signs.find(patch.location);
    if (it == signs.end()) return {SignApplyStatus::NotASign, "sign not found", 0};

    auto current = it->second;
    current.kind = classifySign(current.block_identifier, current.states);
    current.revision = calculateSignRevision(current);
    if (patch.expected_revision && !force && *patch.expected_revision != current.revision)
        return {SignApplyStatus::Conflict, "sign revision changed", current.revision};

    if (patch.block_identifier) current.block_identifier = *patch.block_identifier;
    for (const auto &[key, value] : patch.state_updates)
        current.states.insert_or_assign(key, value);
    for (const auto &key : patch.state_removals) current.states.erase(key);
    if (patch.front) current.front = applyTextPatch(current.front, *patch.front);
    if (patch.back) current.back = applyTextPatch(current.back, *patch.back);
    if (patch.waxed) current.waxed = *patch.waxed;
    if (patch.locked_for_editing_by)
        current.locked_for_editing_by = *patch.locked_for_editing_by;
    if (patch.locked_for_editing_xuid) {
        if (patch.locked_for_editing_xuid->empty()) current.locked_for_editing_xuid.reset();
        else current.locked_for_editing_xuid = *patch.locked_for_editing_xuid;
    }
    if (patch.remote_profanity_filter_enabled)
        current.remote_profanity_filter_enabled = *patch.remote_profanity_filter_enabled;
    if (patch.local_profanity_filter_enabled)
        current.local_profanity_filter_enabled = *patch.local_profanity_filter_enabled;
    current.kind = classifySign(current.block_identifier, current.states);
    current.actor_status = SignActorStatus::Captured;
    current.canonical_snbt.clear();
    current.revision = calculateSignRevision(current);
    it->second = current;
    return {SignApplyStatus::Applied, "sign patch applied", current.revision};
}

SignApplyResult InMemorySignAdapter::placeInto(
    SignMap &signs,
    const SignPlaceRequest &request,
    bool force) {
    const auto existing = signs.find(request.location);
    if (request.expected_destination_revision && !force) {
        const auto actual = existing == signs.end()
                                ? 0
                                : calculateSignRevision(existing->second);
        if (*request.expected_destination_revision != actual)
            return {SignApplyStatus::Conflict, "destination revision changed", actual};
    }
    if (existing != signs.end() && !force &&
        request.replace_policy != SignReplacePolicy::Force) {
        return {
            SignApplyStatus::BlockOccupied,
            "destination already contains a sign",
            calculateSignRevision(existing->second),
        };
    }

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
    signs.insert_or_assign(request.location, snapshot);
    return {SignApplyStatus::Applied, "sign placed", snapshot.revision};
}

SignApplyResult InMemorySignAdapter::removeFrom(
    SignMap &signs,
    const SignRemoveRequest &request,
    bool force) {
    const auto existing = signs.find(request.location);
    if (existing == signs.end()) return {SignApplyStatus::NotASign, "sign not found", 0};
    const auto revision = calculateSignRevision(existing->second);
    if (request.expected_revision && !force && *request.expected_revision != revision)
        return {SignApplyStatus::Conflict, "sign revision changed", revision};
    signs.erase(existing);
    return {
        SignApplyStatus::Applied,
        request.drop_item ? "sign removed with item drop" : "sign removed",
        0,
    };
}

SignApplyResult InMemorySignAdapter::apply(const SignPatch &patch, bool force) {
    std::scoped_lock lock(mutex_);
    return applyTo(signs_, patch, force);
}

SignApplyResult InMemorySignAdapter::place(const SignPlaceRequest &request, bool force) {
    std::scoped_lock lock(mutex_);
    return placeInto(signs_, request, force);
}

SignApplyResult InMemorySignAdapter::remove(const SignRemoveRequest &request, bool force) {
    std::scoped_lock lock(mutex_);
    return removeFrom(signs_, request, force);
}

SignTransactionResult InMemorySignAdapter::transact(const SignTransaction &transaction) {
    std::scoped_lock lock(mutex_);
    SignMap candidate = signs_;
    SignTransactionResult result;
    result.operation_results.reserve(transaction.operations.size());

    for (const auto &operation : transaction.operations) {
        auto operation_result = std::visit(
            [&](const auto &entry) -> SignApplyResult {
                using T = std::decay_t<decltype(entry)>;
                if constexpr (std::is_same_v<T, SignPlaceRequest>)
                    return placeInto(candidate, entry, transaction.force);
                else if constexpr (std::is_same_v<T, SignPatch>)
                    return applyTo(candidate, entry, transaction.force);
                else
                    return removeFrom(candidate, entry, transaction.force);
            },
            operation);
        result.operation_results.push_back(operation_result);
        if (!operation_result.ok()) {
            result.status = SignApplyStatus::TransactionFailed;
            result.message = "transaction stopped: " + operation_result.message;
            if (transaction.rollback_on_failure) {
                result.rolled_back = true;
                return result;
            }
            signs_ = std::move(candidate);
            return result;
        }
    }

    signs_ = std::move(candidate);
    result.status = SignApplyStatus::Applied;
    result.message = "transaction applied atomically";
    return result;
}

SignApplyResult InMemorySignAdapter::openEditor(
    endstone::Player &,
    const SignOpenEditorRequest &) {
    return {
        SignApplyStatus::Unsupported,
        "the in-memory adapter has no native Bedrock client editor",
        0,
    };
}

void InMemorySignAdapter::upsert(SignSnapshot snapshot) {
    std::scoped_lock lock(mutex_);
    snapshot.kind = classifySign(snapshot.block_identifier, snapshot.states);
    snapshot.actor_status = SignActorStatus::Captured;
    snapshot.revision = calculateSignRevision(snapshot);
    signs_.insert_or_assign(snapshot.location, std::move(snapshot));
}

bool InMemorySignAdapter::erase(const SignLocation &location) {
    std::scoped_lock lock(mutex_);
    return signs_.erase(location) != 0;
}

std::size_t InMemorySignAdapter::size() const {
    std::scoped_lock lock(mutex_);
    return signs_.size();
}

} // namespace endstone_sign
