# Endstone Sign API

**Release:** `v0.2.0-alpha.8`

**Service ABI:** `endstone:sign:v2`  
**Target:** Minecraft Bedrock Dedicated Server package `1.26.33.1`, runtime `26.33`, Endstone `v0.11.6`

Endstone Sign API defines complete, typed control over the entire Bedrock sign lifecycle. It covers standing signs, wall signs, ceiling-hanging signs, and wall-hanging signs in both C++ and Python.

## Current release status

The **portable API, reference adapter, validation, event system, NBT projection, and transaction engine are complete and tested**. Alpha.8 ships the consolidated final qualification candidate around the deliberately partial native probe adapter. It fixes successful capability-preflight evidence so the strict validator can recognize a gate that genuinely passed. Its standalone native downloads use the install-ready `endstone_sign_bds_1_26_33.so`/`.dll` names; tester discovery remains compatible with the longer alpha.3 filenames.

Alpha.8 does not turn unavailable native operations on by changing capability
flags. `/signprobe accept` runs the complete 48-case profile, starts the exact
31-probe stage report, and makes every closed capability, failed or skipped
step, pending client/reconnect/restart checkpoint, identity mismatch, or cleanup
conflict a release blocker. Exact-binary, ownership, revision, native-readback,
and rollback safety gates remain mandatory.

Alpha.5 is superseded: its hosted Linux matrix passed the first 20 cases, then
aborted at dark-oak standing placement because that release generated
`minecraft:dark_oak_standing_sign`; Bedrock uses the legacy
`minecraft:darkoak_standing_sign` spelling. The returned alpha.6 hosted matrix
passed all 48 default material/form cases, including the corrected legacy
dark-oak standing and wall identifiers.

On Linux x64, the probe adapter exposes front/back plain-text read/write only when the running `bedrock_server` is the exact official `1.26.33.1` executable (SHA-256 `61995841f21baf9bfab96e0d9b0cb798501dcc9789dab68e496f3b8e3bc83375`) and all three full native function hashes, the live Sign/HangingSign vtable, and the libc++ string layout match. Every write preserves and verifies the owner, performs native readback, and attempts verified rollback on failure.

This first probe is intentionally limited to normal unfiltered string signs whose old text, new four-line message (including three newline separators), and owner XUID each fit the 22-byte libc++ small-string representation. It rejects text objects, filtered text, advanced properties, combined structural edits, and every binary mismatch before mutation. Alpha.6 additionally requires the exact executable hash inside every structural mutation, resolves all 50 support/cleanup/sign descriptors before the first world write, and enumerates Endstone's pre-populated block registry before the native descriptor boundary. The Windows candidate is read-only until its independent binary and text boundaries are verified.

Start the alpha.8 qualification session with one command:

```text
/signprobe accept 100 64 100 confirm
```

After the 48 material/form cases, the same scheduled runner exercises the 12
remaining server-side operations through the native Python bridge: filtered
text, text-object JSON, owner XUID, hidden glow outline, formatting
persistence, editor lock/unlock, cancellable API edits, replacement, clone,
move, and atomic rollback. Mutations are captured and restored where
applicable. Clone and move use two preflighted runner-owned scratch cells; the
rollback check uses a temporary occupied guard block to force a real
adapter-level failure after the first transaction operation. Every scratch
block is revision/ownership tracked and must be removed by matrix cleanup.

The session deliberately cannot report `qualification_passed` until all 31
probes have evidence and ownership-aware cleanup has completed. Client UI,
player-edit, reconnect, and restart checks still require the operator/client
actions described by the tester; after those checkpoints, run matrix cleanup
(do not call `/signprobe remove` on the retained sign), hash the final
log/post-cleanup backup, and run `/signprobe finish`. Cleanup evidence projects
the `remove` probe automatically.

The seven guided client/player/reconnect/restart results are operator-attested
evidence. The offline validator binds them to the exact run, world, binaries,
log, and backup, but it cannot independently observe a Bedrock client screen or
reconnect action. An official-release review must inspect those evidence notes
and the bound log/artifacts rather than treating a non-empty note as automatic
client proof.

Validate the two resulting files and their bound artifacts with:

```bash
python tools/validate_full_system_acceptance.py \
  latest-matrix-report.json linux-x64-1.26.33.1-stage-probe.json \
  --server-executable ./bedrock_server \
  --plugin-binary plugins/endstone_sign_bds_1_26_33.so \
  --tester-wheel plugins/endstone_sign_tester-0.2.0a8-cp314-cp314-linux_x86_64.whl \
  --server-log acceptance-server.log \
  --world-backup post-cleanup-world-backup.zip
```

On Windows, pass the exact `bedrock_server.exe` and the Windows `.dll` and
tester wheel paths instead.

Run and validate Linux and Windows independently before considering an official
release. The validator requires 48/48 cases, 31/31 probes, every functional
capability except the final stage-pass flag, zero failed/skipped/manual entries,
matching binary identity, and conflict-free cleanup. The current partial Linux
adapter and diagnostic-only Windows adapter are expected to remain blocked
until their missing native layers are implemented and reviewed.

The supported-scope diagnostic matrix remains available:

```text
/signprobe run 100 64 100 confirm
```

The anchor and every planned sign/support cell must be air. The runner creates
solid fixture supports through Endstone's public block API, places blank signs
through `endstone:sign:v2`, then verifies structural capture, front/back raw
text, opposite-side preservation, and an individual-line change one operation
per scheduled tick. Its default text includes raw `§` color codes while staying
inside the exact 22-byte limit. Run `/signprobe config` to print the generated
`matrix-config.toml` path in the tester's plugin data directory, then edit it to
select materials, forms, text, spacing, ARGB, glow, wax, cleanup, and scheduling
behavior.

ARGB color, glow, wax, filtered text, text objects, owner data, formatting
flags, editor locking, clone, move, and atomic operations are present in the
coverage report. Acceptance mode now has an executable bridge path for every
server-side operation, but a path is not called when its native capability is
false; that skip blocks qualification. Client
rendering, editor UI acknowledgement, player edits, reconnect, and restart
persistence remain explicit manual checkpoints. Therefore an automated report
always has `activation_eligible: false`, even when every currently supported
server-side check passes.

The inherited alpha.6 matrix result was: every supported server-side case passed;
expected capability-gated and manual entries remained skipped or pending. It
does not claim that advanced operations, all stage probes, or complete-control
activation passed. Cleanup was disabled for that run, so suite-owned removal
was not exercised.

The probe registers a **partial experimental** `endstone:sign:v2` service; `complete_control` remains false. A verified complete-control bridge remains closed until all of these are simultaneously true:

1. The runtime is BDS `26.33` with Endstone `0.11.6`.
2. The running executable SHA-256 matches a reviewed platform manifest for official package `1.26.33.1`.
3. Every required native symbol has an exact RVA, fingerprint, signature review, and behavior review.
4. The player-edit hook is cancellable before the game mutates the sign.
5. A reviewed native bridge source matches its recorded SHA-256.
6. Every disposable-world stage probe passes, including client refresh, reconnect, restart persistence, and rollback.

Activation also requires the reviewed manifest to reference SHA-256-bound stage
and matrix reports. The verifier parses both reports and binds their platform,
executable, artifacts, run, configuration, world, target, exact 31-probe
coverage, and successful qualification verdict; copied pass booleans in the
manifest cannot substitute for those reports.

Until then, advanced operations report `unsupported` and the verified generated manifest stays closed. The tester checks each mutation capability first and records `mutation_attempted: false` when a gate is closed.

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
GitHub releases package both platform SDK ZIPs, native plugins, and the matching platform-specific tester wheels.

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

The separate alpha.6 Linux byte-candidate ledger can also be checked without
changing any activation evidence. Add the exact local ELF path to reproduce
the full hashes and unique entry fingerprints:

```bash
python tools/verify_native_symbol_candidates.py
python tools/verify_native_symbol_candidates.py /path/to/bedrock_server
```

Passing this audit is not signature, ABI, behavior, or live-server proof; the
native manifest remains blocked.

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
- `native/audits/`: non-activating static candidate evidence.
- `native/probes/`: disposable-world probe contract.
- `tools/`: archive hashing, manifest verification, probe validation, and activation.
- `tests/`: portable C++ and Python regression tests.
- `examples/`: C++ and Python usage examples.

## Safety policy

This project never commits or redistributes BDS executables, PDB files, generated private headers, full symbol dumps, or decompiler output. Public manifests contain only the minimum reviewed addresses, fingerprints, signatures, and proof notes required to bind this API to one exact binary.
