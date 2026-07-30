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

struct CanonicalSignIdentifier {
    SignMaterial material;
    SignKind kind;
};

std::optional<CanonicalSignIdentifier> parseCanonicalSignIdentifier(
    const std::string &identifier) noexcept {
    constexpr std::string_view Namespace = "minecraft:";
    if (!identifier.starts_with(Namespace)) return std::nullopt;

    std::string_view name(identifier);
    name.remove_prefix(Namespace.size());
    if (name == "standing_sign") {
        return CanonicalSignIdentifier{SignMaterial::Oak, SignKind::Standing};
    }
    if (name == "wall_sign") {
        return CanonicalSignIdentifier{SignMaterial::Oak, SignKind::Wall};
    }
    if (name == "darkoak_standing_sign") {
        return CanonicalSignIdentifier{SignMaterial::DarkOak, SignKind::Standing};
    }
    if (name == "darkoak_wall_sign") {
        return CanonicalSignIdentifier{SignMaterial::DarkOak, SignKind::Wall};
    }

    constexpr std::string_view HangingSuffix = "_hanging_sign";
    if (name.ends_with(HangingSuffix)) {
        name.remove_suffix(HangingSuffix.size());
        if (const auto material = materialFromPrefix(name)) {
            return CanonicalSignIdentifier{*material, SignKind::CeilingHanging};
        }
        return std::nullopt;
    }

    const auto parse_wood_sign = [&name](const std::string_view suffix,
                                         const SignKind kind)
        -> std::optional<CanonicalSignIdentifier> {
        if (!name.ends_with(suffix)) return std::nullopt;
        auto prefix = name;
        prefix.remove_suffix(suffix.size());
        const auto material = materialFromPrefix(prefix);
        if (!material || *material == SignMaterial::Oak ||
            *material == SignMaterial::DarkOak) {
            return std::nullopt;
        }
        return CanonicalSignIdentifier{*material, kind};
    };
    if (const auto standing =
            parse_wood_sign("_standing_sign", SignKind::Standing)) {
        return standing;
    }
    return parse_wood_sign("_wall_sign", SignKind::Wall);
}

} // namespace

std::span<const SignMaterial> allSignMaterials() noexcept { return Materials; }

std::string signBlockIdentifier(SignMaterial material, SignKind kind) {
    if (kind == SignKind::Unknown)
        throw std::invalid_argument("cannot create an identifier for an unknown sign kind");

    const auto material_name = std::string(signMaterialName(material));
    switch (kind) {
    case SignKind::Standing:
        if (material == SignMaterial::Oak) return "minecraft:standing_sign";
        if (material == SignMaterial::DarkOak)
            return "minecraft:darkoak_standing_sign";
        return "minecraft:" + material_name + "_standing_sign";
    case SignKind::Wall:
        if (material == SignMaterial::Oak) return "minecraft:wall_sign";
        if (material == SignMaterial::DarkOak)
            return "minecraft:darkoak_wall_sign";
        return "minecraft:" + material_name + "_wall_sign";
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
    const auto parsed = parseCanonicalSignIdentifier(identifier);
    return parsed ? std::optional<SignMaterial>{parsed->material} : std::nullopt;
}

SignKind classifySignIdentifier(const std::string &identifier) noexcept {
    const auto parsed = parseCanonicalSignIdentifier(identifier);
    return parsed ? parsed->kind : SignKind::Unknown;
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
    return parseCanonicalSignIdentifier(identifier).has_value();
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
