"""Portable example. Replace InMemorySignService with the live provider in an Endstone plugin."""
from endstone_sign import (
    CardinalDirection,
    InMemorySignService,
    SignCloneRequest,
    SignKind,
    SignLocation,
    SignMaterial,
    SignMoveRequest,
    SignPatch,
    SignPlaceRequest,
    SignText,
    SignTextPatch,
    make_wall_hanging_sign_states,
    sign_block_identifier,
)

service = InMemorySignService()
shop = SignLocation("overworld", 100, 70, 100)
backup = SignLocation("overworld", 101, 70, 100)
relocated = SignLocation("overworld", 102, 70, 100)

placed = service.place(SignPlaceRequest(
    location=shop,
    block_identifier=sign_block_identifier(SignMaterial.CHERRY, SignKind.WALL_HANGING),
    states=make_wall_hanging_sign_states(CardinalDirection.NORTH),
    front=SignText(lines=("The Kingdom", "Market", "", ""), glowing=True),
    back=SignText(lines=("Staff Only", "", "", "")),
))
assert placed.ok

snapshot = service.capture(shop)
assert snapshot is not None
changed = service.apply(SignPatch(
    location=shop,
    expected_revision=snapshot.revision,
    front=SignTextPatch(
        line_updates={2: "Open 24/7"},
        argb=0xFFFFAA00,
        hide_glow_outline=True,
    ),
    waxed=True,
))
assert changed.ok

assert service.clone_sign(SignCloneRequest(shop, backup)).ok
assert service.move_sign(SignMoveRequest(backup, relocated)).ok
