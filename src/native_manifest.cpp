#include "endstone_sign/native_manifest.h"

#include <algorithm>
#include <array>
#include <ranges>
#include <string>

namespace endstone_sign {
namespace {

constexpr std::array RequiredSymbols{
    NativeSignSymbol::SignActorSave,
    NativeSignSymbol::SignActorLoad,
    NativeSignSymbol::GetMessage,
    NativeSignSymbol::GetRawMessage,
    NativeSignSymbol::GetSignTextColor,
    NativeSignSymbol::GetIsGlowing,
    NativeSignSymbol::GetHideGlowOutline,
    NativeSignSymbol::GetIsWaxed,
    NativeSignSymbol::GetIsLockedForEditing,
    NativeSignSymbol::SetMessageForServerScripting,
    NativeSignSymbol::SetSignTextColor,
    NativeSignSymbol::SetIsGlowing,
    NativeSignSymbol::SetHideGlowOutline,
    NativeSignSymbol::SetWaxed,
    NativeSignSymbol::SetLockedForEditing,
    NativeSignSymbol::ClearLockedForEditing,
    NativeSignSymbol::RequestOpenSignEditor,
    NativeSignSymbol::UpdateTextFromClient,
    NativeSignSymbol::FireBlockEntityChanged,
};

} // namespace

std::span<const NativeSignSymbol> requiredNativeSignSymbols() noexcept {
    return RequiredSymbols;
}

bool NativeSignManifest::complete() const noexcept {
    if (binary.platform.empty() || binary.bds_package_version.empty() ||
        binary.archive_sha256.empty() || binary.executable_sha256.empty() ||
        binary.executable_size == 0 || endstone_version.empty() ||
        !disposable_world_probe_passed || disposable_world_probe_sha256.empty()) {
        return false;
    }
    for (const auto required : RequiredSymbols) {
        const auto it = std::ranges::find_if(
            symbols,
            [required](const NativeSymbolResolution &entry) {
                return entry.symbol == required;
            });
        if (it == symbols.end() || !it->resolved || !it->unique ||
            !it->signature_verified || !it->behavior_verified || it->rva == 0) {
            return false;
        }
    }
    return true;
}

std::vector<std::string> NativeSignManifest::missingRequirements() const {
    std::vector<std::string> missing;
    if (binary.platform.empty()) missing.emplace_back("binary.platform");
    if (binary.bds_package_version.empty()) missing.emplace_back("binary.bds_package_version");
    if (binary.archive_sha256.empty()) missing.emplace_back("binary.archive_sha256");
    if (binary.executable_sha256.empty()) missing.emplace_back("binary.executable_sha256");
    if (binary.executable_size == 0) missing.emplace_back("binary.executable_size");
    if (endstone_version.empty()) missing.emplace_back("endstone_version");
    if (!disposable_world_probe_passed)
        missing.emplace_back("disposable_world_probe_passed");
    if (disposable_world_probe_sha256.empty())
        missing.emplace_back("disposable_world_probe_sha256");

    for (const auto required : RequiredSymbols) {
        const auto it = std::ranges::find_if(
            symbols,
            [required](const NativeSymbolResolution &entry) {
                return entry.symbol == required;
            });
        const auto name = std::string(nativeSignSymbolName(required));
        if (it == symbols.end()) {
            missing.emplace_back(name);
            continue;
        }
        if (!it->resolved) missing.emplace_back(name + ".resolved");
        if (!it->unique) missing.emplace_back(name + ".unique");
        if (!it->signature_verified) missing.emplace_back(name + ".signature_verified");
        if (!it->behavior_verified) missing.emplace_back(name + ".behavior_verified");
        if (it->rva == 0) missing.emplace_back(name + ".rva");
    }
    return missing;
}

} // namespace endstone_sign
