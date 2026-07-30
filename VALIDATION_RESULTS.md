# Endstone Sign API validation results

Release: `0.2.0-alpha.5`
Service ABI: `endstone:sign:v2`  
Validation date: `2026-07-29`

## Result

The portable C++20 and Python API layers pass local validation. The alpha.5
source contains an exact-gated Linux plain-text/structural matrix probe
candidate; the complete native bridge remains disabled because the remaining
symbol/ABI proof, player-edit hook, reviewed bridge, and disposable-world
probes are incomplete.

The returned alpha.4 Linux evidence verified the canonical plugin discovery,
exact executable identity, short unfiltered front/back text, client-visible
text, player reconnect, and server-restart persistence for that narrow text
case. It did not verify the other activation probes.

Alpha.5 adds a strict 48-case default automation plan, capability-specific
no-mutation gates, untruncated per-run evidence, cancellation, and
ownership-aware cleanup. Structural writes are now exact-executable-hash gated
inside the adapter; the Windows candidate cannot mutate.

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
| Unit tests | `51/51` passed, including matrix config/planning/runner/race/cleanup-gate coverage |
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
| Default matrix is 12 materials × 4 forms without cell collisions | Passed |
| Advanced fields are capability-gated without native calls | Passed |
| Automated evidence never activates the native manifest | Passed |

## Exact native work still required

The following are intentionally unresolved and are required before a verified
complete-control live plugin may be built:

1. Run the alpha.5 automated matrix against the exact Linux server and return
   `latest-matrix-report.json` plus the server log/world backup.
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
