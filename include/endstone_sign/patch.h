#pragma once

#include "endstone_sign/text.h"
#include "endstone_sign/types.h"

#include <cstdint>
#include <optional>
#include <set>
#include <string>

namespace endstone_sign {

struct SignPatch {
    SignLocation location;
    std::optional<std::uint64_t> expected_revision;
    std::optional<std::string> block_identifier;
    SignStates state_updates;
    std::set<std::string> state_removals;
    std::optional<SignTextPatch> front;
    std::optional<SignTextPatch> back;
    std::optional<bool> waxed;
    std::optional<std::int64_t> locked_for_editing_by;
    std::optional<std::string> locked_for_editing_xuid;
    std::optional<bool> remote_profanity_filter_enabled;
    std::optional<bool> local_profanity_filter_enabled;
    bool send_client_update{true};
    bool persist{true};
    SignMutationOrigin origin{SignMutationOrigin::Api};
};

[[nodiscard]] bool patchIsEmpty(const SignPatch &patch) noexcept;

} // namespace endstone_sign
