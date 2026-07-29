#pragma once

#include "endstone_sign/text.h"
#include "endstone_sign/types.h"

#include <cstdint>
#include <optional>
#include <string>
#include <string_view>

namespace endstone_sign {

enum class SignActorStatus {
    Captured,
    ExperimentalTextCaptured,
    ChunkUnavailable,
    NoBlockActor,
    WrongBlockActorType,
    SymbolGateClosed,
    AdapterError,
};

[[nodiscard]] constexpr std::string_view
signActorStatusName(SignActorStatus status) noexcept {
    switch (status) {
    case SignActorStatus::Captured: return "captured";
    case SignActorStatus::ExperimentalTextCaptured:
        return "experimental_text_captured";
    case SignActorStatus::ChunkUnavailable: return "chunk_unavailable";
    case SignActorStatus::NoBlockActor: return "no_block_actor";
    case SignActorStatus::WrongBlockActorType: return "wrong_block_actor_type";
    case SignActorStatus::SymbolGateClosed: return "symbol_gate_closed";
    case SignActorStatus::AdapterError: return "adapter_error";
    }
    return "adapter_error";
}

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
