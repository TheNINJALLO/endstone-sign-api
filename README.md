# Endstone Sign API

**Release:** `v0.2.0-alpha.1`  
**Service ABI:** `endstone:sign:v2`  
**Target:** Minecraft Bedrock Dedicated Server package `1.26.33.1`, runtime `26.33`, Endstone `v0.11.6`

Endstone Sign API defines complete, typed control over the entire Bedrock sign lifecycle. It covers standing signs, wall signs, ceiling-hanging signs, and wall-hanging signs in both C++ and Python.

## Current release status

The **portable API, reference adapter, validation, event system, NBT projection, and transaction engine are complete and tested**. The exact native `SignBlockActor` bridge is intentionally closed in this source release.

The plugin does **not** register `endstone:sign:v2` unless all of these are simultaneously true:

1. The runtime is BDS `26.33` with Endstone `0.11.6`.
2. The running executable SHA-256 matches a reviewed platform manifest for official package `1.26.33.1`.
3. Every required native symbol has an exact RVA, fingerprint, signature review, and behavior review.
4. The player-edit hook is cancellable before the game mutates the sign.
5. A reviewed native bridge source matches its recorded SHA-256.
6. Every disposable-world stage probe passes, including client refresh, reconnect, restart persistence, and rollback.

Until then, the native plugin logs the missing requirements and refuses service registration. There are no guessed offsets, borrowed symbols, silent no-ops, or partial capabilities.

## Complete control contract

The API contract includes:

- Capture every sign property and both sides.
- Place every wood/material variant in standing, wall, ceiling-hanging, and wall-hanging forms.
- Replace a sign while preserving an explicit conflict policy.
- Remove a sign with optional item drop behavior.
- Clone or atomically move a sign.
- Edit all four lines individually or replace a complete message.
- Read and write front and back text independently.
- Read and write filtered text, text-object JSON, text ownership XUID, ARGB color, glow, hidden glow outline, and formatting persistence.
- Wax and unwax signs.
- Lock and unlock the native editor.
- Open the native front- or back-side editor for a player.
- Observe and cancel API edits and player edits.
- Use optimistic revisions to reject stale writes.
- Apply multi-sign changes atomically with rollback.
- Force a client block-actor refresh and require restart persistence in the native acceptance gate.

## Placement helpers

The API never makes plugin authors guess raw block-state values.

```python
from endstone_sign import (
    SignKind,
    SignLocation,
    SignMaterial,
    SignPlaceRequest,
    SignService,
    SignText,
    make_ceiling_hanging_sign_states,
    sign_block_identifier,
)

request = SignPlaceRequest(
    location=SignLocation("overworld", 100, 70, 100),
    block_identifier=sign_block_identifier(
        SignMaterial.CHERRY,
        SignKind.CEILING_HANGING,
    ),
    states=make_ceiling_hanging_sign_states(rotation=8, chains_attached=True),
    front=SignText(lines=("The Kingdom", "Market", "", ""), glowing=True),
    back=SignText(lines=("Staff Only", "", "", "")),
)

result = service.place(request)
```

Oak standing and wall signs use Bedrock's generic `minecraft:standing_sign` and `minecraft:wall_sign` block IDs. Other materials use material-specific standing and wall IDs. Hanging signs use the material-specific `_hanging_sign` ID and the typed hanging-state helpers.

## Editing and revision protection

```python
from endstone_sign import SignPatch, SignTextPatch

snapshot = service.capture(location)
assert snapshot is not None

result = service.apply(SignPatch(
    location=location,
    expected_revision=snapshot.revision,
    front=SignTextPatch(
        line_updates={1: "Open 24/7"},
        argb=0xFFFFAA00,
        glowing=True,
    ),
    back=SignTextPatch(message="Authorized\nPersonnel"),
    waxed=True,
))
```

A stale `expected_revision` returns `conflict`; it never silently overwrites a newer edit.

## Atomic transactions

```python
from endstone_sign import SignPatch, SignTransaction

result = service.transact(SignTransaction(
    operations=(
        SignPatch(location=left, expected_revision=left_revision, waxed=True),
        SignPatch(location=right, expected_revision=right_revision, waxed=True),
    ),
    rollback_on_failure=True,
    audit_reason="lock the shop signs",
))
```

Every operation is preflighted before mutation. The reference adapter commits against a private candidate map and publishes it only if the whole transaction succeeds.

## C++ service lookup

A successfully activated native plugin registers:

```cpp
inline constexpr std::string_view SignServiceName = "endstone:sign:v2";
inline constexpr std::uint32_t SignServiceAbiVersion = 2;
```

Consumers should treat failure to find that exact service as a hard compatibility failure. Do not fall back to an older ABI.

## Build the portable core

```bash
cmake -S . -B build \
  -DENDSTONE_SIGN_BUILD_TESTS=ON \
  -DENDSTONE_SIGN_BUILD_SHARED=ON \
  -DENDSTONE_SIGN_BUILD_PLUGIN=OFF
cmake --build build --parallel
ctest --test-dir build --output-on-failure
python -m unittest discover -s tests/python -v
```

The portable shared library is emitted as `endstone_sign_api.dll` on Windows
and `libendstone_sign_api.so` on Linux. It contains the tested API, transaction
engine, and in-memory adapter; it is not the native Endstone plugin. Tagged
GitHub releases package both platform SDKs and the tested pure-Python wheel.

## Exact native activation

The native path is documented in:

- `docs/SYMBOL_AUDIT.md`
- `docs/BUILD_EXACT.md`
- `docs/STAGE_PROBE.md`
- `native/manifests/*.json`

A manifest can be inspected safely while incomplete:

```bash
python tools/verify_native_manifest.py \
  native/manifests/linux-x64-1.26.33.1.json \
  --allow-incomplete
```

Activation refuses an incomplete manifest:

```bash
python tools/activate_verified_manifest.py \
  native/manifests/linux-x64-1.26.33.1.json
```

## Repository map

- `include/endstone_sign/`: public C++ API and native activation contract.
- `src/`: portable implementation plus the closed native boundary.
- `python/endstone_sign/`: pure Python reference API.
- `native/manifests/`: per-platform exact-binary proof manifests.
- `native/probes/`: disposable-world probe contract.
- `tools/`: archive hashing, manifest verification, probe validation, and activation.
- `tests/`: portable C++ and Python regression tests.
- `examples/`: C++ and Python usage examples.

## Safety policy

This project never commits or redistributes BDS executables, PDB files, generated private headers, full symbol dumps, or decompiler output. Public manifests contain only the minimum reviewed addresses, fingerprints, signatures, and proof notes required to bind this API to one exact binary.
