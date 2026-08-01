#pragma once

#include <compare>
#include <cstdint>
#include <map>
#include <optional>
#include <string>
#include <string_view>
#include <variant>

namespace endstone_sign {

struct SignLocation {
    std::string dimension{"overworld"};
    std::int32_t x{};
    std::int32_t y{};
    std::int32_t z{};
    auto operator<=>(const SignLocation &) const = default;
};

enum class SignSide : std::int32_t {
    Front = 0,
    Back = 1,
};

[[nodiscard]] constexpr std::string_view signSideName(SignSide side) noexcept {
    return side == SignSide::Front ? "front" : "back";
}

enum class SignKind {
    Standing,
    Wall,
    CeilingHanging,
    WallHanging,
    Unknown,
};

[[nodiscard]] constexpr std::string_view signKindName(SignKind kind) noexcept {
    switch (kind) {
    case SignKind::Standing: return "standing";
    case SignKind::Wall: return "wall";
    case SignKind::CeilingHanging: return "ceiling_hanging";
    case SignKind::WallHanging: return "wall_hanging";
    case SignKind::Unknown: return "unknown";
    }
    return "unknown";
}

enum class SignMutationOrigin {
    Api,
    Player,
    Command,
    Structure,
    WorldLoad,
    Unknown,
};

enum class SignReplacePolicy {
    RequireAir,
    ReplaceableOnly,
    Force,
};

enum class SignEventKind {
    BeforePlace,
    AfterPlace,
    BeforeChange,
    AfterChange,
    BeforeRemove,
    AfterRemove,
    BeforeOpenEditor,
    AfterOpenEditor,
    BeforeLock,
    AfterLock,
    BeforeUnlock,
    AfterUnlock,
    PlayerEditReceived,
};

using SignStateValue = std::variant<bool, std::int32_t, std::string>;
using SignStates = std::map<std::string, SignStateValue>;

enum class SignApplyStatus {
    Applied,
    Conflict,
    Cancelled,
    ChunkUnavailable,
    NotASign,
    BlockOccupied,
    Unsupported,
    InvalidPatch,
    PermissionDenied,
    AdapterUnavailable,
    RuntimeMismatch,
    BinaryIdentityMismatch,
    SymbolValidationFailed,
    TransactionFailed,
    RollbackFailed,
    AdapterError,
};

[[nodiscard]] constexpr std::string_view signApplyStatusName(SignApplyStatus status) noexcept {
    switch (status) {
    case SignApplyStatus::Applied: return "applied";
    case SignApplyStatus::Conflict: return "conflict";
    case SignApplyStatus::Cancelled: return "cancelled";
    case SignApplyStatus::ChunkUnavailable: return "chunk_unavailable";
    case SignApplyStatus::NotASign: return "not_a_sign";
    case SignApplyStatus::BlockOccupied: return "block_occupied";
    case SignApplyStatus::Unsupported: return "unsupported";
    case SignApplyStatus::InvalidPatch: return "invalid_patch";
    case SignApplyStatus::PermissionDenied: return "permission_denied";
    case SignApplyStatus::AdapterUnavailable: return "adapter_unavailable";
    case SignApplyStatus::RuntimeMismatch: return "runtime_mismatch";
    case SignApplyStatus::BinaryIdentityMismatch: return "binary_identity_mismatch";
    case SignApplyStatus::SymbolValidationFailed: return "symbol_validation_failed";
    case SignApplyStatus::TransactionFailed: return "transaction_failed";
    case SignApplyStatus::RollbackFailed: return "rollback_failed";
    case SignApplyStatus::AdapterError: return "adapter_error";
    }
    return "adapter_error";
}

struct SignApplyResult {
    SignApplyStatus status{SignApplyStatus::AdapterError};
    std::string message;
    std::uint64_t resulting_revision{};
    [[nodiscard]] bool ok() const noexcept { return status == SignApplyStatus::Applied; }
};

struct SignCapabilities {
    bool capture{};
    bool place{};
    bool remove{};
    bool replace{};
    bool clone{};
    bool move{};
    bool atomic_transactions{};
    bool read_text{};
    bool write_text{};
    bool front_and_back{};
    bool per_line_write{};
    bool text_objects{};
    bool filtered_text{};
    bool owner_xuid{};
    bool text_color{};
    bool glowing{};
    bool hide_glow_outline{};
    bool persist_formatting{};
    bool waxed{};
    bool editor_lock{};
    bool open_editor{};
    bool player_edit_events{};
    bool api_edit_events{};
    bool client_updates{};
    bool restart_persistence{};
    bool exact_build_match{};
    bool exact_binary_hash_match{};
    bool symbols_validated{};
    bool stage_probe_passed{};

    // Stable v0.2.0 consumers can require this narrower, exact-build contract.
    // Optional fields remain individually queryable and false until their live
    // probes are repaired and accepted.
    [[nodiscard]] constexpr bool supportedRelease() const noexcept {
        return capture && place && remove && replace && clone && move && atomic_transactions &&
               read_text && write_text && front_and_back && per_line_write && filtered_text &&
               owner_xuid && hide_glow_outline && persist_formatting && api_edit_events &&
               client_updates && exact_build_match && exact_binary_hash_match &&
               symbols_validated;
    }

    [[nodiscard]] constexpr bool completeControl() const noexcept {
        return capture && place && remove && replace && clone && move && atomic_transactions &&
               read_text && write_text && front_and_back && per_line_write && text_objects &&
               filtered_text && owner_xuid && text_color && glowing && hide_glow_outline &&
               persist_formatting && waxed && editor_lock && open_editor && player_edit_events &&
               api_edit_events && client_updates && restart_persistence && exact_build_match &&
               exact_binary_hash_match && symbols_validated && stage_probe_passed;
    }
};

} // namespace endstone_sign
