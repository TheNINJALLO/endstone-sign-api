"""Load only the exact package-local Sign API native bridge."""
from __future__ import annotations

import importlib
from types import ModuleType


BRIDGE_MODULE = "_endstone_sign_live"
BUNDLED_BRIDGE_MODULE = f"{__package__}.{BRIDGE_MODULE}"


def import_live_bridge(expected_version: str) -> ModuleType:
    try:
        bridge = importlib.import_module(BUNDLED_BRIDGE_MODULE)
    except ModuleNotFoundError as error:
        if error.name != BUNDLED_BRIDGE_MODULE:
            raise
        raise ModuleNotFoundError(
            "Sign API's package-local bridge is missing. Install the matching "
            f"{expected_version} CPython 3.14 tester wheel for this server platform.",
            name=BUNDLED_BRIDGE_MODULE,
        ) from error
    bridge_version = getattr(bridge, "__version__", None)
    if bridge_version != expected_version:
        raise RuntimeError(
            f"Sign API bridge version {bridge_version!r} does not match tester "
            f"version {expected_version!r}. Remove older tester wheels and reinstall "
            "the wheel bundled with this native plugin."
        )
    return bridge
