# Sign placement model

## Materials

The typed API includes oak, spruce, birch, jungle, acacia, dark oak, mangrove, cherry, bamboo, crimson, warped, and pale oak.

## Block identifiers

- Oak standing: `minecraft:standing_sign`
- Oak wall: `minecraft:wall_sign`
- Other standing: `minecraft:<material>_standing_sign`
- Other wall: `minecraft:<material>_wall_sign`
- Hanging: `minecraft:<material>_hanging_sign`

`minecraft:<material>_sign` is an item identifier, not a placeable sign block identifier, and is rejected.

## States

### Standing

`ground_sign_direction`: integer `0..15`.

### Wall

`facing_direction`: north `2`, south `3`, west `4`, east `5`.

### Hanging

- `attached_bit`: Boolean chain attachment state.
- `facing_direction`: `2..5`.
- `ground_sign_direction`: `0..15`.
- `hanging`: `true` for ceiling-hanging, `false` for wall-hanging.

Use the provided state constructors rather than hand-building the map.
