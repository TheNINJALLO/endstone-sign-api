#pragma once

#include "endstone_sign/text.h"
#include "endstone_sign/types.h"

#include <cstdint>
#include <optional>
#include <string>

namespace endstone_sign {

enum class SignActorStatus {
    Captured,
    ChunkUnavailable,
    NoBlockActor,
    WrongBlockActorType,
    SymbolGateClosed,
    AdapterError,
};

struct SignSnapshot {
    SignLocation location;
    std::string block_identifier;
    SignKind kind{SignKind::Unknown};
    SignStates states;
    SignText front;
    SignText back;
    bool waxed{};
    std::int64_t locked_for_editing_by{-1};
    std::optional<std::string> locked_for_editing_xuid;
    bool remote_profanity_filter_enabled{};
    bool local_profanity_filter_enabled{};
    bool movable{true};
    SignActorStatus actor_status{SignActorStatus::Captured};
    std::string canonical_snbt;
    std::uint64_t revision{};
};

[[nodiscard]] std::uint64_t calculateSignRevision(const SignSnapshot &snapshot) noexcept;

} // namespace endstone_sign
