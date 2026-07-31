#pragma once

#include <cstdint>
#include <string_view>

namespace endstone_sign {

inline constexpr std::string_view ReleaseVersion = "0.2.0-alpha.8";
inline constexpr std::string_view ServiceName = "endstone:sign:v2";
inline constexpr std::uint32_t ServiceAbiVersion = 2;
inline constexpr std::string_view TargetBdsPackage = "1.26.33.1";
inline constexpr std::string_view TargetBdsRuntime = "26.33";
inline constexpr std::string_view TargetEndstoneVersion = "0.11.6";

} // namespace endstone_sign
