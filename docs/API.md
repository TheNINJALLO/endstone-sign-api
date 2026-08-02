# Sign API reference

## Service identity

| Field | Value |
|---|---|
| Service name | `endstone:sign:v2` |
| Service ABI | `2` |
| C++ interface | `endstone_sign::LiveSignService` |
| Stable release | `0.2.1` |
| Native target | Linux x86-64, exact BDS `1.26.33.1`, Endstone `0.11.6` |

Load the service through Endstone’s `ServiceManager`. Production plugins should
require `capabilities().completeControl()` before enabling features that depend
on the complete stable contract.

The API is deliberately headless. It defines no player or console commands;
consumer plugins own their command names, permissions, configuration, and user
experience.

## Core values

### `SignLocation`

Identifies a block by dimension and integer `x`, `y`, and `z` coordinates.

### `SignSnapshot`

A captured snapshot contains:

- location, block identifier, sign kind, and complete block-state map;
- independent `front` and `back` `SignText` values;
- waxed state;
- editor-lock runtime ID and optional XUID;
- local and remote profanity-filter flags;
- movable and actor-capture state;
- optional canonical SNBT;
- a deterministic revision covering every captured field.

### `SignText`

Each side contains exactly four lines plus filtered text, raw-text object data,
raw-text mode, ARGB color, glow, hidden glow-outline, formatting-persistence,
and owner-XUID state.

### `SignPatch` and `SignTextPatch`

Patches are sparse. Unset values are preserved. A text patch can replace all
four lines, change selected lines, switch raw-text mode, update filtered text,
and alter supported presentation or ownership fields.

## Operations

### `capture(location)`

Returns the complete current snapshot, or no value if the location is missing,
not loaded, or not a supported sign.

### `place(request, force=false)`

Creates a standing, wall, ceiling-hanging, or wall-hanging sign with initial
front/back text and supported native state. `replace_policy` is one of:

- `RequireAir`: destination must be air;
- `ReplaceableOnly`: destination must be replaceable;
- `Force`: caller explicitly permits destructive replacement.

### `apply(patch, force=false, actor={})`

Changes any supported combination of:

- block identifier and states;
- individual lines or complete messages on either side;
- filtered text and Bedrock raw-text object data;
- ARGB color and presentation flags;
- owner XUID;
- wax state;
- editor lock;
- profanity-filter flags.

Set `expected_revision` from a fresh capture. Set `send_client_update=true` for
immediate client visibility and `persist=true` for durable world state.

### `remove(request, force=false, actor={})`

Removes the sign with revision and policy checks. Callers must explicitly choose
whether a dropped item is requested.

### `replace(request)`, `cloneSign(request)`, and `moveSign(request)`

Replace changes the structural sign type/state while preserving requested
content. Clone copies a complete sign to a destination. Move performs an atomic
destination write plus source removal.

### `openEditor(player, request)`

Requests Bedrock’s native editor for the selected side. Wax, capability,
revision, player, and lock rules are evaluated before dispatch. The request can
optionally acquire the native editor lock.

### `transact(transaction, actor={})`

Preflights the entire operation list before mutation. A failure or cancellation
causes reverse-order rollback of already-applied operations. Consumers receive
the transaction result and individual operation outcomes.

## Results

Mutation methods return `SignApplyResult`. Important statuses include:

| Status | Meaning |
|---|---|
| `Applied` | Mutation and required readback completed |
| `Conflict` | `expected_revision` no longer matches |
| `Cancelled` | A cancellable before-event rejected the mutation |
| `Unsupported` | The running adapter does not expose the requested capability |
| `Invalid` | Request data or block states are invalid |
| `NotASign` | Target is absent or not a supported sign |
| `Failed` | Native mutation or verification failed |

Never treat a non-throwing call as success without inspecting the result.

## Events

Before-events are cancellable where the operation permits cancellation:

- before place, change, remove, and editor opening;
- before lock and unlock;
- player edit received before the original Bedrock mutation.

After-events are observational. Event payloads include location, actor/source
identity, and applicable before/after snapshots. Listeners run on the primary
server thread and must return quickly. Queue Discord, HTTP, database, or file
work to another thread.

## Revisions and threading

A revision includes block identity and states, both text sides, visual flags,
wax, lock, profanity flags, actor status, and canonical native state. Capture a
fresh revision immediately before every write. A conflict is a normal outcome
when another plugin or player has changed the sign.

All live service calls must run on Endstone’s primary thread. Schedule inbound
network events back to that thread before calling the API.

## Capabilities

`SignCapabilities` lets consumers fail closed on older or mismatched providers.
The stable exact-Linux release reports `completeControl()` only when every
lifecycle, text, presentation, editor, event, client-update, persistence,
runtime-identity, and accepted-release capability is available.

For forward compatibility, consumers should still check optional capabilities
that materially affect their behavior and provide a clear disable message when
requirements are unavailable.

## Placement

Use the typed helpers in `placement.h` rather than hand-assembling block states.
See [PLACEMENT.md](PLACEMENT.md) for material identifiers, sign forms, rotation,
facing, hanging, and attachment state rules.
