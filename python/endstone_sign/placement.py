from __future__ import annotations

from .model import CardinalDirection, SignKind, SignMaterial, SignStateValue


ALL_SIGN_MATERIALS: tuple[SignMaterial, ...] = tuple(SignMaterial)


def sign_block_identifier(material: SignMaterial, kind: SignKind) -> str:
    if kind is SignKind.UNKNOWN:
        raise ValueError("cannot create an identifier for an unknown sign kind")
    if kind is SignKind.STANDING:
        if material is SignMaterial.OAK:
            return "minecraft:standing_sign"
        if material is SignMaterial.DARK_OAK:
            return "minecraft:darkoak_standing_sign"
        return f"minecraft:{material.value}_standing_sign"
    if kind is SignKind.WALL:
        if material is SignMaterial.OAK:
            return "minecraft:wall_sign"
        if material is SignMaterial.DARK_OAK:
            return "minecraft:darkoak_wall_sign"
        return f"minecraft:{material.value}_wall_sign"
    if kind in (SignKind.CEILING_HANGING, SignKind.WALL_HANGING):
        return f"minecraft:{material.value}_hanging_sign"
    raise ValueError("unsupported sign kind")


_CANONICAL_SIGN_IDENTIFIERS: dict[str, tuple[SignMaterial, SignKind]] = {
    sign_block_identifier(material, kind): (material, kind)
    for material in ALL_SIGN_MATERIALS
    for kind in (SignKind.STANDING, SignKind.WALL, SignKind.CEILING_HANGING)
}


def material_from_sign_identifier(identifier: str) -> SignMaterial | None:
    parsed = _CANONICAL_SIGN_IDENTIFIERS.get(identifier)
    return parsed[0] if parsed is not None else None


def classify_identifier(identifier: str) -> SignKind:
    parsed = _CANONICAL_SIGN_IDENTIFIERS.get(identifier)
    return parsed[1] if parsed is not None else SignKind.UNKNOWN


def classify_sign(identifier: str, states: dict[str, SignStateValue] | object) -> SignKind:
    kind = classify_identifier(identifier)
    if kind is not SignKind.CEILING_HANGING:
        return kind
    mapping = states if isinstance(states, dict) else dict(states)  # type: ignore[arg-type]
    hanging = mapping.get("hanging")
    return SignKind.WALL_HANGING if hanging is False else SignKind.CEILING_HANGING


def is_vanilla_sign_identifier(identifier: str) -> bool:
    return classify_identifier(identifier) is not SignKind.UNKNOWN


def make_standing_sign_states(rotation: int) -> dict[str, SignStateValue]:
    return {"ground_sign_direction": rotation}


def make_wall_sign_states(facing: CardinalDirection) -> dict[str, SignStateValue]:
    return {"facing_direction": int(facing)}


def make_ceiling_hanging_sign_states(rotation: int, chains_attached: bool) -> dict[str, SignStateValue]:
    return {
        "attached_bit": chains_attached,
        "facing_direction": int(CardinalDirection.NORTH),
        "ground_sign_direction": rotation,
        "hanging": True,
    }


def make_wall_hanging_sign_states(facing: CardinalDirection) -> dict[str, SignStateValue]:
    return {
        "attached_bit": False,
        "facing_direction": int(facing),
        "ground_sign_direction": 0,
        "hanging": False,
    }


def validate_sign_block_states(identifier: str, states: object) -> str | None:
    try:
        mapping = dict(states)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return "block states must be a mapping"
    kind = classify_identifier(identifier)
    if kind is SignKind.UNKNOWN:
        return "block identifier is not a supported vanilla sign block"

    if kind is SignKind.STANDING:
        if not set(mapping).issubset({"ground_sign_direction"}):
            return "standing signs only accept ground_sign_direction"
        if "ground_sign_direction" in mapping:
            value = mapping["ground_sign_direction"]
            if type(value) is not int:
                return "ground_sign_direction must be an integer"
            if not 0 <= value <= 15:
                return "ground_sign_direction must be between 0 and 15"
        return None

    if kind is SignKind.WALL:
        if not set(mapping).issubset({"facing_direction"}):
            return "wall signs only accept facing_direction"
        if "facing_direction" in mapping:
            value = mapping["facing_direction"]
            if type(value) is not int:
                return "facing_direction must be an integer"
            if not 2 <= value <= 5:
                return "wall sign facing_direction must be 2, 3, 4, or 5"
        return None

    allowed = {"attached_bit", "facing_direction", "ground_sign_direction", "hanging"}
    if not set(mapping).issubset(allowed):
        return "hanging signs only accept attached_bit, facing_direction, ground_sign_direction, and hanging"
    for key in ("attached_bit", "hanging"):
        if key in mapping and type(mapping[key]) is not bool:
            return f"{key} must be boolean"
    if "facing_direction" in mapping:
        value = mapping["facing_direction"]
        if type(value) is not int:
            return "facing_direction must be an integer"
        if not 2 <= value <= 5:
            return "hanging sign facing_direction must be 2, 3, 4, or 5"
    if "ground_sign_direction" in mapping:
        value = mapping["ground_sign_direction"]
        if type(value) is not int:
            return "ground_sign_direction must be an integer"
        if not 0 <= value <= 15:
            return "hanging sign ground_sign_direction must be between 0 and 15"
    return None
