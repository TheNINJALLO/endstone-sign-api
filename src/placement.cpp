#include "endstone_sign/placement.h"

#include <array>
#include <stdexcept>
#include <string>
#include <string_view>

namespace endstone_sign {
namespace {

constexpr std::array Materials{
    SignMaterial::Oak,
    SignMaterial::Spruce,
    SignMaterial::Birch,
    SignMaterial::Jungle,
    SignMaterial::Acacia,
    SignMaterial::DarkOak,
    SignMaterial::Mangrove,
    SignMaterial::Cherry,
    SignMaterial::Bamboo,
    SignMaterial::Crimson,
    SignMaterial::Warped,
    SignMaterial::PaleOak,
};

std::optional<std::int32_t> integerState(
    const SignStates &states,
    std::string_view key) noexcept {
    const auto it = states.find(std::string(key));
    if (it == states.end()) return std::nullopt;
    if (const auto *value = std::get_if<std::int32_t>(&it->second)) return *value;
    return std::nullopt;
}

std::optional<bool> booleanState(
    const SignStates &states,
    std::string_view key) noexcept {
    const auto it = states.find(std::string(key));
    if (it == states.end()) return std::nullopt;
    if (const auto *value = std::get_if<bool>(&it->second)) return *value;
    return std::nullopt;
}

bool hasOnly(const SignStates &states, std::initializer_list<std::string_view> allowed) {
    for (const auto &[key, _] : states) {
        bool found = false;
        for (const auto candidate : allowed) {
            if (key == candidate) {
                found = true;
                break;
            }
        }
        if (!found) return false;
    }
    return true;
}

std::optional<SignMaterial> materialFromPrefix(std::string_view prefix) noexcept {
    for (const auto material : Materials) {
        if (prefix == signMaterialName(material)) return material;
    }
    return std::nullopt;
}

} // namespace

std::span<const SignMaterial> allSignMaterials() noexcept { return Materials; }

std::string signBlockIdentifier(SignMaterial material, SignKind kind) {
    if (kind == SignKind::Unknown)
        throw std::invalid_argument("cannot create an identifier for an unknown sign kind");

    const auto material_name = std::string(signMaterialName(material));
    switch (kind) {
    case SignKind::Standing:
        return material == SignMaterial::Oak
                   ? "minecraft:standing_sign"
                   : "minecraft:" + material_name + "_standing_sign";
    case SignKind::Wall:
        return material == SignMaterial::Oak
                   ? "minecraft:wall_sign"
                   : "minecraft:" + material_name + "_wall_sign";
    case SignKind::CeilingHanging:
    case SignKind::WallHanging:
        return "minecraft:" + material_name + "_hanging_sign";
    case SignKind::Unknown:
        break;
    }
    throw std::invalid_argument("unsupported sign kind");
}

std::optional<SignMaterial> materialFromSignIdentifier(
    const std::string &identifier) noexcept {
    if (identifier == "minecraft:standing_sign" || identifier == "minecraft:wall_sign")
        return SignMaterial::Oak;
    constexpr std::string_view Namespace = "minecraft:";
    if (!identifier.starts_with(Namespace)) return std::nullopt;
    std::string_view name(identifier);
    name.remove_prefix(Namespace.size());
    for (const auto suffix : {
             std::string_view("_standing_sign"),
             std::string_view("_wall_sign"),
             std::string_view("_hanging_sign")}) {
        if (name.ends_with(suffix)) {
            name.remove_suffix(suffix.size());
            return materialFromPrefix(name);
        }
    }
    return std::nullopt;
}

SignKind classifySignIdentifier(const std::string &identifier) noexcept {
    if (identifier == "minecraft:standing_sign" || identifier.ends_with("_standing_sign"))
        return SignKind::Standing;
    if (identifier == "minecraft:wall_sign" || identifier.ends_with("_wall_sign"))
        return SignKind::Wall;
    if (identifier.ends_with("_hanging_sign")) return SignKind::CeilingHanging;
    return SignKind::Unknown;
}

SignKind classifySign(
    const std::string &identifier,
    const SignStates &states) noexcept {
    const auto kind = classifySignIdentifier(identifier);
    if (kind != SignKind::CeilingHanging) return kind;
    const auto hanging = booleanState(states, "hanging");
    if (!hanging) return SignKind::CeilingHanging;
    return *hanging ? SignKind::CeilingHanging : SignKind::WallHanging;
}

bool isVanillaSignIdentifier(const std::string &identifier) noexcept {
    return classifySignIdentifier(identifier) != SignKind::Unknown &&
           materialFromSignIdentifier(identifier).has_value();
}

SignStates makeStandingSignStates(std::int32_t rotation) {
    return {{"ground_sign_direction", rotation}};
}

SignStates makeWallSignStates(CardinalDirection facing) {
    return {{"facing_direction", static_cast<std::int32_t>(facing)}};
}

SignStates makeCeilingHangingSignStates(
    std::int32_t rotation,
    bool chains_attached) {
    return {
        {"attached_bit", chains_attached},
        {"facing_direction", static_cast<std::int32_t>(CardinalDirection::North)},
        {"ground_sign_direction", rotation},
        {"hanging", true},
    };
}

SignStates makeWallHangingSignStates(CardinalDirection facing) {
    return {
        {"attached_bit", false},
        {"facing_direction", static_cast<std::int32_t>(facing)},
        {"ground_sign_direction", 0},
        {"hanging", false},
    };
}

std::optional<std::string> validateSignBlockStates(
    const std::string &identifier,
    const SignStates &states) {
    const auto kind = classifySignIdentifier(identifier);
    if (kind == SignKind::Unknown || !materialFromSignIdentifier(identifier))
        return "block identifier is not a supported vanilla sign block";

    if (kind == SignKind::Standing) {
        if (!hasOnly(states, {"ground_sign_direction"}))
            return "standing signs only accept ground_sign_direction";
        const auto rotation = integerState(states, "ground_sign_direction");
        if (states.contains("ground_sign_direction") && !rotation)
            return "ground_sign_direction must be an integer";
        if (rotation && (*rotation < 0 || *rotation > 15))
            return "ground_sign_direction must be between 0 and 15";
        return std::nullopt;
    }

    if (kind == SignKind::Wall) {
        if (!hasOnly(states, {"facing_direction"}))
            return "wall signs only accept facing_direction";
        const auto facing = integerState(states, "facing_direction");
        if (states.contains("facing_direction") && !facing)
            return "facing_direction must be an integer";
        if (facing && (*facing < 2 || *facing > 5))
            return "wall sign facing_direction must be 2, 3, 4, or 5";
        return std::nullopt;
    }

    if (!hasOnly(states, {
            "attached_bit", "facing_direction", "ground_sign_direction", "hanging"})) {
        return "hanging signs only accept attached_bit, facing_direction, "
               "ground_sign_direction, and hanging";
    }
    for (const auto key : {std::string_view("attached_bit"), std::string_view("hanging")}) {
        if (states.contains(std::string(key)) && !booleanState(states, key))
            return std::string(key) + " must be boolean";
    }
    const auto facing = integerState(states, "facing_direction");
    if (states.contains("facing_direction") && !facing)
        return "facing_direction must be an integer";
    if (facing && (*facing < 2 || *facing > 5))
        return "hanging sign facing_direction must be 2, 3, 4, or 5";
    const auto rotation = integerState(states, "ground_sign_direction");
    if (states.contains("ground_sign_direction") && !rotation)
        return "ground_sign_direction must be an integer";
    if (rotation && (*rotation < 0 || *rotation > 15))
        return "hanging sign ground_sign_direction must be between 0 and 15";
    return std::nullopt;
}

} // namespace endstone_sign
