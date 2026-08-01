# Endstone Sign API validation results

Release: `0.2.0`
Service ABI: `endstone:sign:v2`  
Validation date: `2026-08-01`

## Result

The portable C++20 and Python layers pass local validation. The stable Linux
native build is exact-gated to BDS `1.26.33.1` and Endstone `0.11.6`. Its
supported tier covers capture, placement/removal, front/back and per-line text,
filtered text, owner XUID, outline/formatting flags, API edit events,
replacement, clone, move, and atomic rollback.

The v0.2.0 evidence found one stale tester preflight—the release adapter reports
the valid actor state `captured`, while the alpha tester accepted only
`experimental_text_captured`—plus genuine failures in text objects and editor
lock/unlock. The stale preflight is fixed. The failed and uncompleted advanced
surfaces are explicitly false capabilities in the stable adapter, so they
cannot be invoked accidentally or counted toward `supportedRelease()`.

The stable tier still enforces exact executable identity, native
function/vtable/ABI fingerprints, primary-thread access, optimistic revisions,
native readback, client updates, and rollback. `completeControl()` remains
false. The strict 31-probe acceptance path remains as an optional development
gate for future capabilities.

The historical qualification notes below document how the supported native
scope and safety checks were established.

The returned alpha.4 Linux evidence verified the canonical plugin discovery,
exact executable identity, short unfiltered front/back text, client-visible
text, player reconnect, and server-restart persistence for that narrow text
case. It did not verify the other activation probes.

The returned alpha.5 matrix passed 20 complete oak, spruce, birch, jungle, and
acacia cases, including all four forms, before case 21 aborted during dark-oak
standing placement. Its plan generated the nonexistent
`minecraft:dark_oak_standing_sign`; the exact server contains the legacy
`minecraft:darkoak_standing_sign` spelling. Alpha.5 is superseded.

Alpha.6 corrects and strictly classifies the legacy dark-oak standing/wall
identifiers, resolves all 50 support/cleanup/sign descriptors through Endstone before
the first world write, checks the native block registry before
`createBlockData`, and records every mutation phase durably. A committed
36-identifier inventory matches the portable core, test wheel, both executable
identities, and a live scan of the exact Linux executable.

The returned alpha.6 hosted matrix passed all 48 default material/form cases,
including the corrected legacy dark-oak standing and wall identifiers. The
supported scope passed blank placement, structural capture, front/back short
raw-text write and readback, opposite-side preservation, and per-line editing.
Color, glow, wax, and unwax remained capability-gated and were skipped without
mutation; cleanup was disabled, so removal remained pending. Manual checkpoints
and other unsupported advanced operations were not converted into passes.
Accordingly, the report remains non-activating with `activation_eligible: false`
and `complete_control: false`.

Release packages contain disposable-world `.dll`/`.so` candidates and tester
wheels. They are experimental artifacts, not verified production plugins.

## Delivered contract

- Capture, place, replace, remove, clone, move, and atomic transactions.
- Standing, wall, ceiling-hanging, and wall-hanging signs.
- Oak, spruce, birch, jungle, acacia, dark oak, mangrove, cherry, bamboo, crimson, warped, and pale oak.
- Four independent lines on front and back.
- Whole-message changes and per-line changes.
- Filtered text, text objects, owner XUID, ARGB color, glow, hidden glow outline, and formatting persistence.
- Wax/unwax and editor lock/unlock.
- Native editor request contract for front and back.
- Cancellable API and player-edit event contract.
- Optimistic revisions and explicit force operations.
- Transaction preflight and rollback.
- Exact-binary activation manifests and fail-closed service registration.

## Portable C++ validation

| Check | Result |
|---|---|
| GNU C++ 14.2, C++20 | Passed |
| Clang 17, C++20 | Passed |
| `-Wall -Wextra -Wpedantic -Werror` | Passed |
| AddressSanitizer | Passed |
| UndefinedBehaviorSanitizer | Passed |
| CTest | `3/3` passed |
| C++ example compile/run | Passed |
| CMake install layout | Passed |
| Windows portable shared library (`endstone_sign_api.dll`) | Passed |
| Linux portable shared-library build | Passed in GitHub CI |

## Python validation

| Check | Result |
|---|---|
| Package compilation | Passed |
| Unit tests | `106/106` passed, including live-bridge execution of all 12 server-side full-system probes, semantic full-system evidence validation, hash-bound activation-stage/matrix verification, exact server/plugin/tester binding, public-air cleanup proof, immutable acceptance cleanup, matrix/stage projection, required-preflight enforcement, identifier inventory, descriptor preflight, and static candidate-ledger coverage |
| Python example | Passed |
| Pure Python wheel | Built and inspected |
| Native gate tool tests | Passed |

## Packaging validation

| Check | Result |
|---|---|
| Clean source ZIP extraction | Passed |
| Source ZIP CMake build and CTest | Passed |
| Source ZIP Python tests | `18/18` passed |
| Portable Linux SDK example compile/run | Passed |
| Packaged wheel isolated import and lifecycle smoke test | Passed |
| ZIP integrity | Passed |
| SHA-256 verification | Passed |
| BDS/PDB/debug database artifact exclusion | Passed |

## Native safety validation

| Check | Result |
|---|---|
| Official Windows archive hash pinned | Passed |
| Official Linux archive hash pinned | Passed |
| Exact Windows executable SHA-256/size pinned | Passed |
| Exact Linux executable SHA-256/size pinned | Passed |
| Linux text function full hashes independently reproduced | Passed |
| Non-activating Linux text candidate ledger exact-ELF audit | Passed, 3/3 ranges and unique entry fingerprints |
| Linux Sign/HangingSign vtable and side layout independently reproduced | Passed |
| libc++ SSO short plain-text and readback gates | Passed by source review and hosted matrix |
| Text-object, filtered-text, owner, and rollback executors/gates | Passed by source review and bridge-level regression; exact live probes pending |
| Incomplete Linux manifest reports gate closed | Passed |
| Incomplete Windows manifest reports gate closed | Passed |
| Strict manifest verification rejects incomplete proof | Passed |
| Activation tool rejects incomplete proof | Passed |
| Empty stage-probe template is rejected | Passed |
| Generated C++ manifest remains closed | Passed |
| Verified native bridge source absent | Passed |
| Plugin registration guarded by `completeControl()` | Passed by source guard |
| Structural mutations exact-executable-hash gated in adapter | Passed by source test; blank placement/capture passed in the hosted matrix |
| Canonical sign inventory matches portable/test-wheel generators | Passed, 36/36 identifiers |
| Exact Linux executable identifier scan | Passed, exact hash and 36/36 identifiers |
| Missing native block types rejected by cache-only enumeration before `createBlockData` | Passed by source guard and regression test |
| Tester resolves all support/cleanup/sign descriptors before mutation | Passed, 50 descriptors in the default plan |
| Default matrix is 12 materials × 4 forms without cell collisions | Passed by plan validation and hosted run, 48/48 cases |
| Advanced fields are capability-gated without native calls | Passed |
| Automated evidence never activates the native manifest | Passed |

## Exact native work still required

The following are intentionally unresolved and are required before a verified
complete-control live plugin may be built:

1. Run the optional `/signprobe accept` complete-control workflow on Linux and archive
   each `latest-matrix-report.json` together with the
   server log and post-test world-backup hashes.
2. Locate and behavior-confirm the remaining required symbols independently on
   Windows and Linux.
3. Complete review of every ABI signature and calling contract.
4. Implement and review `src/verified_bds_26_30_adapter.cpp`.
5. Install and validate the cancellable player-edit hook.
6. Pass all 31 disposable-world probes, including client refresh, reconnect,
   restart persistence, and rollback.
7. Generate the activated platform manifest and compile the verified plugin
   against Endstone `0.11.6`.

Until those steps pass, verified complete-control registration remains closed;
the exact-gated Linux probe registers only its explicitly reported partial
capabilities. Unsupported, skipped, and manual matrix coverage never counts as
a passing activation result.
