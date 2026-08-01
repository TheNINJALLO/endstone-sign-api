# Endstone Sign API

**Release:** `v0.2.0-alpha.9`

**Service ABI:** `endstone:sign:v2`  
**Target:** Minecraft Bedrock Dedicated Server package `1.26.33.1`, runtime `26.33`, Endstone `v0.11.6`

Endstone Sign API defines complete, typed control over the entire Bedrock sign lifecycle. It covers standing signs, wall signs, ceiling-hanging signs, and wall-hanging signs in both C++ and Python.

## Current release status

The **portable API, reference adapter, validation, event system, NBT projection, and transaction engine are complete and tested**. Alpha.9 ships the consolidated full-system qualification candidate around the deliberately partial native probe adapter. It exposes exact-binary-gated replacement, clone, move, and multi-operation rollback so the strict runner can exercise every implemented structural layer in one session. Its standalone native downloads use the install-ready `endstone_sign_bds_1_26_33.so`/`.dll` names; tester discovery remains compatible with the longer alpha.3 filenames.

Alpha.9 turns on only implemented structural operations, and only when the
exact runtime and executable identity gates match. `/signprobe accept` runs the
complete 48-case profile, starts the exact 31-probe stage report, and makes
every remaining closed capability, failed or skipped step, pending
client/reconnect/restart checkpoint, identity mismatch, or cleanup conflict a
release blocker. Exact-binary, ownership, revision, native-readback, and
rollback safety gates remain mandatory.

Alpha.5 is superseded: its hosted Linux matrix passed the first 20 cases, then
aborted at dark-oak standing placement because that release generated
`minecraft:dark_oak_standing_sign`; Bedrock uses the legacy
`minecraft:darkoak_standing_sign` spelling. The returned alpha.6 hosted matrix
passed all 48 default material/form cases, including the corrected legacy
dark-oak standing and wall identifiers.

On Linux x64, the probe adapter exposes front/back plain-text read/write only when the running `bedrock_server` is the exact official `1.26.33.1` executable (SHA-256 `61995841f21baf9bfab96e0d9b0cb798501dcc9789dab68e496f3b8e3bc83375`) and all three full native function hashes, the live Sign/HangingSign vtable, and the libc++ string layout match. Every write preserves and verifies the owner, performs native readback, and attempts verified rollback on failure.

The native text boundary is intentionally limited to normal unfiltered string signs whose old text, new four-line message (including three newline separators), and owner XUID each fit the 22-byte libc++ small-string representation. It rejects text objects, filtered text, advanced properties, and every binary mismatch before text mutation. Alpha.9 can combine supported structural replacement with that guarded plain-text state and can restore it during transaction rollback. Alpha.6 additionally requires the exact executable hash inside every structural mutation, resolves all 50 support/cleanup/sign descriptors before the first world write, and enumerates Endstone's pre-populated block registry before the native descriptor boundary. The Windows candidate is read-only until its independent binary and text boundaries are verified.

## Full-release certification

A green GitHub build proves that the source compiles, tests pass, and the
release assets are internally consistent. It does **not** prove that every
native operation works against a real Bedrock client and world. Use the
following sequence for the final Linux qualification. Use a backed-up,
disposable world and the exact BDS `1.26.33.1` executable; do not run this on a
production world.

Download every alpha.9 asset and verify both the combined release manifest and
the Linux package manifest:

```bash
gh release download v0.2.0-alpha.9 \
  --repo TheNINJALLO/endstone-sign-api \
  --dir alpha9-assets
cd alpha9-assets
sha256sum --check SHA256SUMS.txt
sha256sum --check endstone-sign-api-v0.2.0-alpha.9-bds-1.26.33-linux-x64.sha256
```

Stop the test server, install the matching native plugin and CPython 3.14 tester
wheel together, and start it through
[Endstone `0.11.6`](https://endstone.dev/v0.11/getting-started/start-your-server/)
from the server root:

```bash
SERVER_ROOT=/srv/endstone-alpha9
install -D -m 0644 endstone_sign_bds_1_26_33.so \
  "$SERVER_ROOT/plugins/endstone_sign_bds_1_26_33.so"
install -D -m 0644 \
  endstone_sign_tester-0.2.0a9-cp314-cp314-linux_x86_64.whl \
  "$SERVER_ROOT/plugins/endstone_sign_tester-0.2.0a9-cp314-cp314-linux_x86_64.whl"
cd "$SERVER_ROOT"
endstone 2>&1 | tee acceptance-server.log
```

Run these commands as an operator/player in a clear arena. The anchor and the
entire default 28-by-17-block footprint must be air:

```text
/signprobe status
/signprobe accept 100 64 100 confirm
/signprobe runstatus
```

`status` must identify the exact adapter and executable and report every
qualification capability except `stage_probe_passed` as true. The acceptance
command then runs all 48 material/form cases and the 12 additional server-side
operations: filtered text, text-object JSON, owner XUID, hidden glow outline,
formatting persistence, editor lock/unlock, cancellable API edits, replacement,
clone, move, and atomic rollback. Any false capability, failure, skip, crash, or
cleanup conflict is a release blocker; do not hand-record it as a pass.

After the automated work reports that guided evidence remains, perform and
record the seven client/operator checkpoints. Replace the example evidence with
specific coordinates, observed values, timestamps, and bounded log references:

```text
/signprobe editor front
/signprobe record open_editor_front true Front editor opened for the retained sign at <coordinates>; observed <time/log reference>
/signprobe editor back
/signprobe record open_editor_back true Back editor opened for the retained sign at <coordinates>; observed <time/log reference>
/signprobe record player_edit_event_observed true Client edit produced the expected event at <coordinates>; log <reference>
/signprobe record player_edit_event_cancelled true Cancelled client edit left both sides and revision unchanged; log <reference>
/signprobe record client_refresh true Connected client immediately displayed the verified front and back values at <coordinates>
/signprobe record player_reconnect true After reconnect the client and capture returned the same verified values and revision
/signprobe record server_restart_persistence true After a full stop/start the client and capture returned the same verified values and revision
```

Run ownership-aware cleanup after the reconnect and restart checks. Do not run
`/signprobe remove` on the retained sign; successful cleanup supplies the
required `remove` evidence automatically.

```text
/signprobe cleanup confirm
/signprobe runstatus
/signprobe path
```

Stop the server cleanly, preserve an immutable copy of its final log, and make a
post-cleanup backup of the tested world. Hash those exact two files. Restart the
same server only to paste the two lowercase hashes and finish the report; the
validator must receive the immutable files that produced those hashes.

```bash
sha256sum acceptance-server.evidence.log post-cleanup-world-backup.zip
```

```text
/signprobe meta log_sha256 <acceptance-server.evidence.log-sha256>
/signprobe meta world_backup_sha256 <post-cleanup-world-backup.zip-sha256>
/signprobe finish
/signprobe runstatus
/signprobe path
```

Copy the two report paths printed by `/signprobe path` and validate the reports
against the exact five artifacts used by that run:

```bash
python tools/validate_full_system_acceptance.py \
  latest-matrix-report.json linux-x64-1.26.33.1-stage-probe.json \
  --server-executable ./bedrock_server \
  --plugin-binary plugins/endstone_sign_bds_1_26_33.so \
  --tester-wheel plugins/endstone_sign_tester-0.2.0a9-cp314-cp314-linux_x86_64.whl \
  --server-log acceptance-server.evidence.log \
  --world-backup post-cleanup-world-backup.zip
```

The only passing final line is `full-system acceptance VALID`. The validator
requires 48/48 cases, 31/31 probes, zero failed/skipped/manual coverage, every
pre-stage native capability, matching run/config/world/binary identity, and
conflict-free cleanup. The seven guided results are operator attestations, so a
release reviewer must also inspect their notes and bound log/backup rather than
treating non-empty text as independent client proof.

For a Linux-first release, this pass qualifies only the Linux artifact and the
Windows build must remain explicitly diagnostic/unsupported. If Windows live
support is claimed, repeat the entire session independently with the exact
Windows executable, `.dll`, and `win_amd64` tester wheel. The current partial
Linux adapter and diagnostic-only Windows adapter are expected to fail the
complete-control preflight until their remaining native boundaries and reviewed
manifests are implemented; a previously green supported-scope matrix is not the
same result as this strict acceptance run.

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

Until then, unavailable advanced operations report `unsupported` and the verified generated manifest stays closed. The tester checks each mutation capability first and records `mutation_attempted: false` when a gate is closed.

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

## Use the live API from another C++ plugin

The native plugin publishes `LiveSignService` through Endstone's service
manager under the exact name `endstone:sign:v2` and ABI `2`. Load that typed
service during your plugin's enable phase and keep the returned shared pointer.
A production consumer should require `completeControl()`; alpha.9 may register
an experimental partial service solely so the qualification tester can inspect
and exercise individually gated operations.

```cpp
#include "endstone_sign/live_service.h"

#include <endstone/plugin/service_manager.h>
#include <endstone/server.h>

#include <memory>
#include <string>

std::shared_ptr<endstone_sign::LiveSignService> loadSignApi(
    endstone::Server &server) {
    auto signs = server.getServiceManager().load<endstone_sign::LiveSignService>(
        std::string(endstone_sign::SignServiceName));
    if (!signs || !signs->capabilities().completeControl()) {
        return {};
    }
    return signs;
}
```

Capture immediately before a mutation, pass the returned revision, and inspect
the result instead of assuming the write succeeded:

```cpp
bool updateSign(
    const std::shared_ptr<endstone_sign::LiveSignService> &signs) {
    if (!signs) {
        return false;
    }
    const endstone_sign::SignLocation location{"overworld", 100, 70, 100};
    const auto snapshot = signs->capture(location);
    if (!snapshot) {
        return false;
    }

    endstone_sign::SignPatch patch;
    patch.location = location;
    patch.expected_revision = snapshot->revision;
    patch.front.emplace();
    patch.front->line_updates[0] = "Open 24/7";
    patch.front->argb = 0xFFFFAA00u;
    patch.front->glowing = true;

    const auto result = signs->apply(patch);
    // The caller should log/handle conflicts, cancellation, unsupported
    // capabilities, and adapter errors instead of treating them as success.
    return result.ok();
}
```

Never fall back to an older service name or bypass a false capability. For a
deliberately experimental disposable-world plugin, require the exact individual
capabilities used by each call—for the patch above: `capture`, `read_text`,
`write_text`, `front_and_back`, `per_line_write`, `text_color`, and `glowing`.
That does not make the overall adapter production-ready.

The Python package currently provides the complete typed contract and in-memory
reference adapter for plugin logic and unit tests. Alpha.9's
`_endstone_sign_live` module is a private qualification bridge bundled inside
the tester wheel, not a stable dependency for third-party Python plugins. Do
not import it from production plugins; a supported public Python live-service
binding must be released separately before that integration can be promised.

## Build the portable core

```bash
cmake -S . -B build \
  -DENDSTONE_SIGN_BUILD_TESTS=ON \
  -DENDSTONE_SIGN_BUILD_SHARED=ON \
  -DENDSTONE_SIGN_BUILD_PLUGIN=OFF
cmake --build build --parallel
ctest --test-dir build --output-on-failure
PYTHONPATH=python python -m unittest discover -s tests/python -v
```

For a maintainer-side Linux release build, use CPython 3.14 and run the exact
candidate builder and artifact verifier after the portable suite:

```bash
python scripts/verify_project_metadata.py
python scripts/build_exact.py \
  --bds 1.26.33 \
  --platform linux-x64 \
  --parallel 2
python scripts/verify_release_assets.py \
  --slug endstone-sign-api \
  --version 0.2.0-alpha.9 \
  --bds 1.26.33 \
  --platform linux-x64 \
  --release-dir dist/release
python tests/python/verify_test_wheel.py \
  dist/release/endstone_sign_tester-0.2.0a9-cp314-cp314-linux_x86_64.whl
```

These commands duplicate the source/package gates exercised by GitHub Actions.
They do not replace the live certification sequence above.

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

After a live validator pass, record its printed matrix and stage SHA-256 values
in the corresponding platform manifest together with the independently reviewed
ABI, symbols, behavior, bridge source, and evidence fields. Then require strict
verification without `--allow-incomplete` before generating activation data:

```bash
python tools/verify_native_manifest.py \
  native/manifests/linux-x64-1.26.33.1.json
python tools/activate_verified_manifest.py \
  native/manifests/linux-x64-1.26.33.1.json
```

Both commands must refuse the current blocked/incomplete manifest. Do not edit a
status boolean merely to make them pass; the verifier requires the bound report
files and independently checks their contents and hashes.

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
