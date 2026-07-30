#!/usr/bin/env python3
"""Verify the canonical sign identifiers used by an exact BDS executable.

Only the public executable identity and the expected public block identifiers
are reported. The scanner never emits strings, byte ranges, or other content
discovered in the proprietary server binary.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Callable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INVENTORY = (
    ROOT / "native" / "inventories" / "bds-1.26.33.1-sign-identifiers.json"
)
MATERIALS = (
    "oak",
    "spruce",
    "birch",
    "jungle",
    "acacia",
    "dark_oak",
    "mangrove",
    "cherry",
    "bamboo",
    "crimson",
    "warped",
    "pale_oak",
)
FORMS = ("standing", "wall", "hanging")
PLATFORMS = ("linux-x64", "windows-x64")
FORBIDDEN_ALIASES = frozenset(
    {
        "minecraft:dark_oak_standing_sign",
        "minecraft:dark_oak_wall_sign",
    }
)
SHA256 = re.compile(r"\A[0-9a-f]{64}\Z")


class VerificationError(ValueError):
    """Raised when inventory, generated identifiers, or binary evidence fails."""


@dataclass(frozen=True)
class ExecutableIdentity:
    filename: str
    sha256: str
    size: int


@dataclass(frozen=True)
class IdentifierInventory:
    bds_package_version: str
    runtime_bds: str
    executables: Mapping[str, ExecutableIdentity]
    materials: Mapping[str, Mapping[str, str]]

    @property
    def identifiers(self) -> tuple[str, ...]:
        return tuple(
            self.materials[material][form]
            for material in MATERIALS
            for form in FORMS
        )


@dataclass(frozen=True)
class BinaryScan:
    sha256: str
    size: int
    found: frozenset[str]
    missing: tuple[str, ...]


def derive_canonical_materials() -> dict[str, dict[str, str]]:
    """Derive the exact canonical identifier matrix, including legacy names."""
    result: dict[str, dict[str, str]] = {}
    for material in MATERIALS:
        if material == "oak":
            standing = "minecraft:standing_sign"
            wall = "minecraft:wall_sign"
        elif material == "dark_oak":
            # Standing/wall dark-oak identifiers predate the modern separator.
            standing = "minecraft:darkoak_standing_sign"
            wall = "minecraft:darkoak_wall_sign"
        else:
            standing = f"minecraft:{material}_standing_sign"
            wall = f"minecraft:{material}_wall_sign"
        result[material] = {
            "standing": standing,
            "wall": wall,
            "hanging": f"minecraft:{material}_hanging_sign",
        }
    return result


def _require_keys(value: Mapping[str, object], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual == expected:
        return
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    details: list[str] = []
    if missing:
        details.append(f"missing {', '.join(missing)}")
    if extra:
        details.append(f"unexpected {', '.join(extra)}")
    raise VerificationError(f"{label} fields are invalid ({'; '.join(details)})")


def _selected_identifiers(
    materials: Mapping[str, Mapping[str, str]],
) -> tuple[str, ...]:
    selected: list[str] = []
    for material, forms in materials.items():
        if not isinstance(forms, Mapping):
            raise VerificationError(f"identifier inventory material {material!r} is invalid")
        for form, identifier in forms.items():
            if not isinstance(identifier, str):
                raise VerificationError(
                    f"identifier inventory {material}.{form} must be a string"
                )
            selected.append(identifier)
    return tuple(selected)


def reject_forbidden_aliases(identifiers: Sequence[str], label: str) -> None:
    invalid = sorted(FORBIDDEN_ALIASES.intersection(identifiers))
    if invalid:
        raise VerificationError(
            f"{label} selected/generated invalid dark-oak aliases: {', '.join(invalid)}; "
            "BDS uses darkoak_standing_sign and darkoak_wall_sign"
        )


def validate_inventory_document(document: object) -> IdentifierInventory:
    if not isinstance(document, Mapping):
        raise VerificationError("identifier inventory root must be an object")
    _require_keys(
        document,
        {
            "schema",
            "bds_package_version",
            "runtime_bds",
            "executables",
            "materials",
            "forbidden_aliases",
        },
        "identifier inventory",
    )
    if document["schema"] != 1:
        raise VerificationError("identifier inventory schema must be 1")
    if document["bds_package_version"] != "1.26.33.1":
        raise VerificationError("identifier inventory must target BDS package 1.26.33.1")
    if document["runtime_bds"] != "26.33":
        raise VerificationError("identifier inventory must target runtime BDS 26.33")

    raw_forbidden = document["forbidden_aliases"]
    if not isinstance(raw_forbidden, list) or not all(
        isinstance(value, str) for value in raw_forbidden
    ):
        raise VerificationError("forbidden_aliases must be an array of strings")
    if set(raw_forbidden) != FORBIDDEN_ALIASES or len(raw_forbidden) != len(
        FORBIDDEN_ALIASES
    ):
        raise VerificationError(
            "forbidden_aliases must explicitly contain only the invalid "
            "dark_oak standing/wall aliases"
        )

    raw_materials = document["materials"]
    if not isinstance(raw_materials, Mapping):
        raise VerificationError("identifier inventory materials must be an object")
    reject_forbidden_aliases(
        _selected_identifiers(raw_materials), "committed identifier inventory"
    )
    _require_keys(raw_materials, set(MATERIALS), "identifier inventory materials")
    derived = derive_canonical_materials()
    materials: dict[str, dict[str, str]] = {}
    for material in MATERIALS:
        raw_forms = raw_materials[material]
        if not isinstance(raw_forms, Mapping):
            raise VerificationError(f"identifier inventory material {material!r} is invalid")
        _require_keys(raw_forms, set(FORMS), f"identifier inventory {material}")
        actual = dict(raw_forms)
        if actual != derived[material]:
            raise VerificationError(
                f"identifier inventory {material} does not match the canonical derivation"
            )
        materials[material] = dict(derived[material])

    identifiers = [
        materials[material][form] for material in MATERIALS for form in FORMS
    ]
    if len(identifiers) != 36 or len(set(identifiers)) != 36:
        raise VerificationError("identifier inventory must contain 36 unique identifiers")

    raw_executables = document["executables"]
    if not isinstance(raw_executables, Mapping):
        raise VerificationError("identifier inventory executables must be an object")
    _require_keys(raw_executables, set(PLATFORMS), "identifier inventory executables")
    executables: dict[str, ExecutableIdentity] = {}
    for platform in PLATFORMS:
        raw_identity = raw_executables[platform]
        if not isinstance(raw_identity, Mapping):
            raise VerificationError(f"executable identity for {platform} is invalid")
        _require_keys(raw_identity, {"filename", "sha256", "size"}, platform)
        filename = raw_identity["filename"]
        digest = raw_identity["sha256"]
        size = raw_identity["size"]
        expected_filename = "bedrock_server.exe" if platform == "windows-x64" else "bedrock_server"
        if filename != expected_filename:
            raise VerificationError(
                f"executable filename for {platform} must be {expected_filename}"
            )
        if not isinstance(digest, str) or SHA256.fullmatch(digest) is None:
            raise VerificationError(f"executable SHA-256 for {platform} is invalid")
        if type(size) is not int or size <= 0:
            raise VerificationError(f"executable size for {platform} is invalid")
        executables[platform] = ExecutableIdentity(filename, digest, size)

    return IdentifierInventory(
        bds_package_version="1.26.33.1",
        runtime_bds="26.33",
        executables=executables,
        materials=materials,
    )


def load_inventory(path: Path = DEFAULT_INVENTORY) -> IdentifierInventory:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise VerificationError(f"could not read identifier inventory: {error}") from error
    return validate_inventory_document(document)


def verify_manifest_bindings(
    inventory: IdentifierInventory,
    manifests_directory: Path = ROOT / "native" / "manifests",
) -> None:
    """Require inventory identities to match the committed native manifests."""
    for platform, identity in inventory.executables.items():
        path = manifests_directory / f"{platform}-{inventory.bds_package_version}.json"
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise VerificationError(f"could not read native manifest {path.name}: {error}") from error
        if not isinstance(manifest, Mapping):
            raise VerificationError(f"native manifest {path.name} root must be an object")
        executable = manifest.get("executable")
        if not isinstance(executable, Mapping):
            raise VerificationError(f"native manifest {path.name} has no executable identity")
        manifest_identity = (
            executable.get("filename"),
            executable.get("sha256"),
            executable.get("size"),
        )
        inventory_identity = (identity.filename, identity.sha256, identity.size)
        if (
            manifest.get("platform") != platform
            or manifest.get("bds_package_version") != inventory.bds_package_version
            or manifest.get("runtime_bds") != inventory.runtime_bds
            or manifest_identity != inventory_identity
        ):
            raise VerificationError(
                f"static identifier inventory identity does not match {path.name}"
            )


def validate_generated_materials(
    label: str,
    generated: Mapping[str, Mapping[str, str]],
    inventory: IdentifierInventory,
) -> None:
    reject_forbidden_aliases(_selected_identifiers(generated), label)
    if dict(generated) != dict(inventory.materials):
        expected = set(inventory.identifiers)
        actual = set(_selected_identifiers(generated))
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        details: list[str] = []
        if missing:
            details.append(f"missing {', '.join(missing)}")
        if extra:
            details.append(f"unexpected {', '.join(extra)}")
        if not details:
            details.append("material/form mapping differs")
        raise VerificationError(f"{label} differs from the inventory ({'; '.join(details)})")


def _load_module(name: str, path: Path) -> ModuleType:
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise VerificationError(f"could not load local module {path}")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def _generate_materials(
    materials: Sequence[str],
    generator: Callable[[str, str], str],
) -> dict[str, dict[str, str]]:
    generated: dict[str, dict[str, str]] = {}
    for material in materials:
        ceiling = generator(material, "ceiling_hanging")
        wall_hanging = generator(material, "wall_hanging")
        if ceiling != wall_hanging:
            raise VerificationError(
                f"generator produced two block identifiers for {material} hanging signs"
            )
        generated[material] = {
            "standing": generator(material, "standing"),
            "wall": generator(material, "wall"),
            "hanging": ceiling,
        }
    return generated


def verify_static_generators(inventory: IdentifierInventory) -> None:
    """Check the portable Python API and packaged tester against the inventory."""
    python_source = str(ROOT / "python")
    if python_source not in sys.path:
        sys.path.insert(0, python_source)
    try:
        from endstone_sign.model import SignKind, SignMaterial
        from endstone_sign.placement import sign_block_identifier
    except ImportError as error:
        raise VerificationError(f"could not import the local portable core: {error}") from error

    core_materials = tuple(material.value for material in SignMaterial)

    def core_generator(material: str, kind: str) -> str:
        return sign_block_identifier(SignMaterial(material), SignKind(kind))

    validate_generated_materials(
        "portable core generator",
        _generate_materials(core_materials, core_generator),
        inventory,
    )

    tester = _load_module(
        "_endstone_sign_inventory_tester_automation",
        ROOT
        / "examples"
        / "python"
        / "sign_api_tester_plugin"
        / "src"
        / "endstone_sign_tester"
        / "automation.py",
    )
    tester_materials = tuple(tester.MATERIALS)
    validate_generated_materials(
        "test-wheel generator",
        _generate_materials(tester_materials, tester.sign_identifier),
        inventory,
    )


def scan_binary(
    path: Path,
    identifiers: Sequence[str],
    *,
    chunk_size: int = 1024 * 1024,
) -> BinaryScan:
    """Hash a binary and search only for the supplied public identifiers."""
    reject_forbidden_aliases(identifiers, "binary scan identifier selection")
    if chunk_size <= 0:
        raise VerificationError("binary scan chunk_size must be positive")
    if not identifiers:
        raise VerificationError("binary scan requires at least one identifier")
    if len(set(identifiers)) != len(identifiers):
        raise VerificationError("binary scan identifiers must be unique")
    try:
        patterns = {identifier: identifier.encode("ascii") for identifier in identifiers}
    except UnicodeEncodeError as error:
        raise VerificationError("binary scan identifiers must be ASCII") from error
    maximum_pattern = max(len(pattern) for pattern in patterns.values())
    found: set[str] = set()
    digest = hashlib.sha256()
    size = 0
    overlap = b""
    try:
        with path.open("rb") as stream:
            while True:
                chunk = stream.read(chunk_size)
                if not chunk:
                    break
                digest.update(chunk)
                size += len(chunk)
                window = overlap + chunk
                for identifier, pattern in patterns.items():
                    if identifier not in found and pattern in window:
                        found.add(identifier)
                overlap = (
                    window[-(maximum_pattern - 1) :] if maximum_pattern > 1 else b""
                )
    except OSError as error:
        raise VerificationError(f"could not scan server executable: {error}") from error
    missing = tuple(identifier for identifier in identifiers if identifier not in found)
    return BinaryScan(digest.hexdigest(), size, frozenset(found), missing)


def verify_live_binary(
    path: Path,
    identity: ExecutableIdentity,
    identifiers: Sequence[str],
    *,
    chunk_size: int = 1024 * 1024,
) -> BinaryScan:
    scan = scan_binary(path, identifiers, chunk_size=chunk_size)
    if scan.size != identity.size:
        raise VerificationError(
            f"exact executable size mismatch: expected {identity.size}, got {scan.size}"
        )
    if scan.sha256 != identity.sha256:
        raise VerificationError(
            f"exact executable SHA-256 mismatch: expected {identity.sha256}, got {scan.sha256}"
        )
    if scan.missing:
        raise VerificationError(
            "exact executable is missing expected canonical identifiers: "
            + ", ".join(scan.missing)
        )
    return scan


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Check the public canonical sign inventory and optionally scan an exact, "
            "locally supplied BDS executable."
        )
    )
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--platform", required=True, choices=PLATFORMS)
    parser.add_argument(
        "--server-executable",
        type=Path,
        help="local exact bedrock_server path; the file is read but never copied",
    )
    args = parser.parse_args()

    try:
        inventory = load_inventory(args.inventory)
        verify_manifest_bindings(inventory)
        verify_static_generators(inventory)
        print(
            "STATIC identifier inventory verification PASSED: "
            f"{len(inventory.identifiers)} canonical identifiers; "
            "portable core and test-wheel generators match"
        )
        if args.server_executable is None:
            print(
                "LIVE binary identifier verification NOT PERFORMED: "
                "no --server-executable was supplied"
            )
            return 0
        identity = inventory.executables[args.platform]
        scan = verify_live_binary(
            args.server_executable,
            identity,
            inventory.identifiers,
        )
        print(
            "LIVE binary identifier verification PASSED: "
            f"{args.platform} exact SHA-256 {scan.sha256}; "
            f"{len(scan.found)}/{len(inventory.identifiers)} canonical identifiers present"
        )
        return 0
    except VerificationError as error:
        print(f"identifier inventory verification FAILED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
