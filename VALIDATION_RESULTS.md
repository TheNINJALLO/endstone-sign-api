# Endstone Sign API validation results

Release: `0.2.0-alpha.6`
Service ABI: `endstone:sign:v2`  
Validation date: `2026-07-29`

## Result

The portable C++20 and Python API layers pass local validation. The alpha.6
source contains an exact-gated Linux plain-text/structural matrix probe
candidate; the complete native bridge remains disabled because the remaining
symbol/ABI proof, player-edit hook, reviewed bridge, and disposable-world
probes are incomplete.

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
identifiers, resolves all 49 support/sign descriptors through Endstone before
the first world write, checks the native block registry before
`createBlockData`, and records every mutation phase durably. A committed
36-identifier inventory matches the portable core, test wheel, both executable
identities, and a live scan of the exact Linux executable. The alpha.6 hosted
canary and full matrix remain pending.

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
| Linux portable shared-library build | Configured in GitHub release matrix; pending CI runner |

## Python validation

| Check | Result |
|---|---|
| Package compilation | Passed |
| Unit tests | `65/65` passed, including identifier inventory and descriptor-preflight coverage |
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
| Linux Sign/HangingSign vtable and side layout independently reproduced | Passed |
| libc++ SSO, text-object, filtered-text, owner, readback, and rollback gates | Passed by source review; live probe pending |
| Incomplete Linux manifest reports gate closed | Passed |
| Incomplete Windows manifest reports gate closed | Passed |
| Strict manifest verification rejects incomplete proof | Passed |
| Activation tool rejects incomplete proof | Passed |
| Empty stage-probe template is rejected | Passed |
| Generated C++ manifest remains closed | Passed |
| Verified native bridge source absent | Passed |
| Plugin registration guarded by `completeControl()` | Passed by source guard |
| Structural mutations exact-executable-hash gated in adapter | Passed by source test |
| Canonical sign inventory matches portable/test-wheel generators | Passed, 36/36 identifiers |
| Exact Linux executable identifier scan | Passed, exact hash and 36/36 identifiers |
| Missing native block types rejected before `createBlockData` | Passed by source guard and regression test |
| Tester resolves all support/sign descriptors before mutation | Passed, 49 descriptors in the default plan |
| Default matrix is 12 materials × 4 forms without cell collisions | Passed |
| Advanced fields are capability-gated without native calls | Passed |
| Automated evidence never activates the native manifest | Passed |

## Exact native work still required

The following are intentionally unresolved and are required before a verified
complete-control live plugin may be built:

1. Restore the disposable-world backup, run an alpha.6 dark-oak standing/wall
   canary, then run the full automated matrix against the exact Linux server
   and return `latest-matrix-report.json` plus the server log/world backup.
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
