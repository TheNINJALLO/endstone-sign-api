# Sign API reference

## Service identity

- Name: `endstone:sign:v2`
- ABI: `2`
- C++ provider: `LiveSignService`
- Python reference service: `SignService`

The live service is absent unless the exact native bridge reaches complete-control status.

## Snapshots

`SignSnapshot` contains:

- location and block identifier;
- classified sign kind;
- complete block-state map;
- independent `front` and `back` `SignText` values;
- waxed state;
- editor-lock runtime ID and optional XUID;
- remote and local profanity-filter flags;
- movable flag;
- actor capture status;
- optional canonical SNBT;
- deterministic revision.

`SignText` contains four lines plus filtered text, text-object data, text-object mode, ARGB color, glowing state, hidden glow-outline state, formatting-persistence state, and owner XUID.

## Operations

### `capture(location)`

Returns a complete snapshot or no value when the location is unavailable or is not a sign.

### `place(request, force=false)`

Creates a standing, wall, ceiling-hanging, or wall-hanging sign with complete initial front/back text, wax, editor-lock, and profanity-filter state. `replace_policy` is one of:

- `RequireAir`: destination must be empty;
- `ReplaceableOnly`: destination must be replaceable;
- `Force`: explicit destructive replacement.

### `apply(patch, force=false)`

Changes any combination of:

- sign block ID and states;
- individual lines or whole messages on either side;
- filtered text and text object data;
- ARGB color and visual flags;
- owner XUID;
- wax state;
- editor lock;
- profanity filter flags.

### `remove(request, force=false)`

Removes the sign, with an optional drop-item request.

### `cloneSign(request)` and `moveSign(request)`

Copy or relocate a complete sign. Moving is an atomic place-plus-remove transaction.

### `openEditor(player, request)`

Opens Bedrock's native editor for the requested side. Wax checks and revision checks happen first. The exact native bridge can optionally acquire the edit lock.

### `transact(transaction)`

Preflights all revisions, validation, permissions, and cancellable events before mutation. A supported adapter must apply the operation set atomically or roll it back.

## Events

Before events are cancellable:

- before place/change/remove/open editor;
- before lock/unlock.

After events are observational. Native player changes also emit `PlayerEditReceived`; cancellation must occur before the original Bedrock mutation call.

## Revision rules

Every snapshot revision includes block ID, states, both sides, wax, lock, profanity flags, actor status, and canonical SNBT. Pass `expected_revision` for optimistic concurrency. `force` must be an explicit caller decision.

## Capability contract

`completeControl()` is true only when every lifecycle, text, style, editor, event, client-update, persistence, exact-build, hash, symbol, and stage-probe capability is true. The plugin registers no service when it is false.
