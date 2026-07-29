#pragma once

#include "endstone_sign/patch.h"
#include "endstone_sign/snapshot.h"

#include <cstdint>
#include <optional>
#include <string>
#include <variant>
#include <vector>

namespace endstone_sign {

struct SignPlaceRequest {
    SignLocation location;
    std::string block_identifier{"minecraft:standing_sign"};
    SignStates states;
    SignText front;
    SignText back;
    bool waxed{};
    std::int64_t locked_for_editing_by{-1};
    std::optional<std::string> locked_for_editing_xuid;
    bool remote_profanity_filter_enabled{};
    bool local_profanity_filter_enabled{};
    SignReplacePolicy replace_policy{SignReplacePolicy::RequireAir};
    std::optional<std::uint64_t> expected_destination_revision;
    bool send_client_update{true};
    bool persist{true};
    SignMutationOrigin origin{SignMutationOrigin::Api};
};

struct SignRemoveRequest {
    SignLocation location;
    std::optional<std::uint64_t> expected_revision;
    bool drop_item{};
    bool send_client_update{true};
    SignMutationOrigin origin{SignMutationOrigin::Api};
};

struct SignCloneRequest {
    SignLocation source;
    SignLocation destination;
    std::optional<std::uint64_t> expected_source_revision;
    SignReplacePolicy replace_policy{SignReplacePolicy::RequireAir};
    bool copy_editor_lock{};
    bool send_client_update{true};
    SignMutationOrigin origin{SignMutationOrigin::Api};
};

struct SignMoveRequest {
    SignLocation source;
    SignLocation destination;
    std::optional<std::uint64_t> expected_source_revision;
    SignReplacePolicy replace_policy{SignReplacePolicy::RequireAir};
    bool copy_editor_lock{};
    bool send_client_update{true};
    SignMutationOrigin origin{SignMutationOrigin::Api};
};

struct SignOpenEditorRequest {
    SignLocation location;
    SignSide side{SignSide::Front};
    std::optional<std::uint64_t> expected_revision;
    bool acquire_lock{true};
    bool bypass_wax{};
};

using SignOperation = std::variant<SignPlaceRequest, SignPatch, SignRemoveRequest>;

struct SignTransaction {
    std::vector<SignOperation> operations;
    bool force{};
    bool rollback_on_failure{true};
    std::string audit_reason;
};

struct SignTransactionResult {
    SignApplyStatus status{SignApplyStatus::AdapterError};
    std::string message;
    std::vector<SignApplyResult> operation_results;
    bool rolled_back{};
    [[nodiscard]] bool ok() const noexcept { return status == SignApplyStatus::Applied; }
};

} // namespace endstone_sign
