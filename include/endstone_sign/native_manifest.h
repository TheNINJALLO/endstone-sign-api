#pragma once

#include <cstdint>
#include <span>
#include <string>
#include <string_view>
#include <vector>

namespace endstone_sign {

enum class NativeSignSymbol {
    SignActorSave,
    SignActorLoad,
    GetMessage,
    GetRawMessage,
    GetSignTextColor,
    GetIsGlowing,
    GetHideGlowOutline,
    GetIsWaxed,
    GetIsLockedForEditing,
    SetMessageForServerScripting,
    SetSignTextColor,
    SetIsGlowing,
    SetHideGlowOutline,
    SetWaxed,
    SetLockedForEditing,
    ClearLockedForEditing,
    RequestOpenSignEditor,
    UpdateTextFromClient,
    FireBlockEntityChanged,
};

[[nodiscard]] constexpr std::string_view nativeSignSymbolName(
    NativeSignSymbol symbol) noexcept {
    switch (symbol) {
    case NativeSignSymbol::SignActorSave: return "sign_actor_save";
    case NativeSignSymbol::SignActorLoad: return "sign_actor_load";
    case NativeSignSymbol::GetMessage: return "get_message";
    case NativeSignSymbol::GetRawMessage: return "get_raw_message";
    case NativeSignSymbol::GetSignTextColor: return "get_sign_text_color";
    case NativeSignSymbol::GetIsGlowing: return "get_is_glowing";
    case NativeSignSymbol::GetHideGlowOutline: return "get_hide_glow_outline";
    case NativeSignSymbol::GetIsWaxed: return "get_is_waxed";
    case NativeSignSymbol::GetIsLockedForEditing: return "get_is_locked_for_editing";
    case NativeSignSymbol::SetMessageForServerScripting: return "set_message_for_server_scripting";
    case NativeSignSymbol::SetSignTextColor: return "set_sign_text_color";
    case NativeSignSymbol::SetIsGlowing: return "set_is_glowing";
    case NativeSignSymbol::SetHideGlowOutline: return "set_hide_glow_outline";
    case NativeSignSymbol::SetWaxed: return "set_waxed";
    case NativeSignSymbol::SetLockedForEditing: return "set_locked_for_editing";
    case NativeSignSymbol::ClearLockedForEditing: return "clear_locked_for_editing";
    case NativeSignSymbol::RequestOpenSignEditor: return "request_open_sign_editor";
    case NativeSignSymbol::UpdateTextFromClient: return "update_text_from_client";
    case NativeSignSymbol::FireBlockEntityChanged: return "fire_block_entity_changed";
    }
    return "unknown";
}

[[nodiscard]] std::span<const NativeSignSymbol> requiredNativeSignSymbols() noexcept;

struct NativeBinaryIdentity {
    std::string platform;
    std::string bds_package_version;
    std::string archive_sha256;
    std::string executable_sha256;
    std::uint64_t executable_size{};
};

struct NativeSymbolResolution {
    NativeSignSymbol symbol{};
    std::string mangled_name;
    std::string pattern;
    std::uint64_t rva{};
    bool resolved{};
    bool unique{};
    bool signature_verified{};
    bool behavior_verified{};
};

struct NativeSignManifest {
    NativeBinaryIdentity binary;
    std::string endstone_version;
    std::vector<NativeSymbolResolution> symbols;
    bool disposable_world_probe_passed{};
    std::string disposable_world_probe_sha256;

    [[nodiscard]] bool complete() const noexcept;
    [[nodiscard]] std::vector<std::string> missingRequirements() const;
};

} // namespace endstone_sign
