#pragma once

#include "endstone_sign/types.h"

#include <cstdint>
#include <optional>
#include <span>
#include <string>
#include <string_view>

namespace endstone_sign {

enum class SignMaterial {
    Oak,
    Spruce,
    Birch,
    Jungle,
    Acacia,
    DarkOak,
    Mangrove,
    Cherry,
    Bamboo,
    Crimson,
    Warped,
    PaleOak,
};

enum class CardinalDirection : std::int32_t {
    North = 2,
    South = 3,
    West = 4,
    East = 5,
};

[[nodiscard]] constexpr std::string_view signMaterialName(SignMaterial material) noexcept {
    switch (material) {
    case SignMaterial::Oak: return "oak";
    case SignMaterial::Spruce: return "spruce";
    case SignMaterial::Birch: return "birch";
    case SignMaterial::Jungle: return "jungle";
    case SignMaterial::Acacia: return "acacia";
    case SignMaterial::DarkOak: return "dark_oak";
    case SignMaterial::Mangrove: return "mangrove";
    case SignMaterial::Cherry: return "cherry";
    case SignMaterial::Bamboo: return "bamboo";
    case SignMaterial::Crimson: return "crimson";
    case SignMaterial::Warped: return "warped";
    case SignMaterial::PaleOak: return "pale_oak";
    }
    return "oak";
}

[[nodiscard]] std::span<const SignMaterial> allSignMaterials() noexcept;
[[nodiscard]] std::string signBlockIdentifier(SignMaterial material, SignKind kind);
[[nodiscard]] std::optional<SignMaterial> materialFromSignIdentifier(
    const std::string &identifier) noexcept;
[[nodiscard]] SignKind classifySignIdentifier(const std::string &identifier) noexcept;
[[nodiscard]] SignKind classifySign(
    const std::string &identifier,
    const SignStates &states) noexcept;
[[nodiscard]] bool isVanillaSignIdentifier(const std::string &identifier) noexcept;

[[nodiscard]] SignStates makeStandingSignStates(std::int32_t rotation);
[[nodiscard]] SignStates makeWallSignStates(CardinalDirection facing);
[[nodiscard]] SignStates makeCeilingHangingSignStates(
    std::int32_t rotation,
    bool chains_attached);
[[nodiscard]] SignStates makeWallHangingSignStates(CardinalDirection facing);
[[nodiscard]] std::optional<std::string> validateSignBlockStates(
    const std::string &identifier,
    const SignStates &states);

} // namespace endstone_sign
