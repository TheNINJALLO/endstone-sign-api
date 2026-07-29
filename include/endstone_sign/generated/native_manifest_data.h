#pragma once

#include "endstone_sign/native_manifest.h"

#include <array>
#include <cstdint>
#include <string_view>

namespace endstone_sign::generated {

struct GeneratedSymbolEntry {
    NativeSignSymbol symbol{};
    std::uint64_t rva{};
    std::array<std::uint8_t, 24> fingerprint{};
    std::uint8_t fingerprint_size{};
};

inline constexpr std::string_view BdsPackageVersion = "1.26.33.1";
inline constexpr std::string_view EndstoneVersion = "0.11.6";

#ifdef _WIN32
inline constexpr std::string_view Platform = "windows-x64";
inline constexpr std::string_view ArchiveSha256 =
    "fc6c0ad6f82cfb11c65c6756a1a8e49b21ffa8cc203da587df59df365d82a2ad";
#else
inline constexpr std::string_view Platform = "linux-x64";
inline constexpr std::string_view ArchiveSha256 =
    "68c52ababde987741029de091c09cd736fe894bc1fe99cf20f9ed5c659f0c180";
#endif

// This file is deliberately closed in source control. The activation tool only
// rewrites it after exact executable identity, every required symbol, ABI
// signatures, behavior review, and the disposable-world probe have all passed.
inline constexpr std::string_view ExecutableSha256 = "";
inline constexpr std::uint64_t ExecutableSize = 0;
inline constexpr bool ManifestComplete = false;
inline constexpr bool SymbolsBehaviorVerified = false;
inline constexpr bool DisposableWorldProbePassed = false;
inline constexpr std::array<GeneratedSymbolEntry, 0> Symbols{};

} // namespace endstone_sign::generated
