# Endstone Sign API validation results

Release: `0.2.0-alpha.1`  
Service ABI: `endstone:sign:v2`  
Validation date: `2026-07-29`

## Result

The portable C++20 and Python API layers passed all available local validation. The exact native BDS bridge remains deliberately disabled because its executable identities, symbol RVAs, ABI proof, reviewed bridge source, and disposable-world probe have not yet been supplied.

No native `.dll` or `.so` is claimed or packaged by this release.

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
| CTest | `1/1` passed |
| C++ example compile/run | Passed |
| CMake install layout | Passed |
| Windows portable shared library (`endstone_sign_api.dll`) | Passed |
| Linux portable shared-library build | Configured in GitHub release matrix; pending CI runner |

## Python validation

| Check | Result |
|---|---|
| Package compilation | Passed |
| Unit tests | `18/18` passed |
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
| Incomplete Linux manifest reports gate closed | Passed |
| Incomplete Windows manifest reports gate closed | Passed |
| Strict manifest verification rejects incomplete proof | Passed |
| Activation tool rejects incomplete proof | Passed |
| Empty stage-probe template is rejected | Passed |
| Generated C++ manifest remains closed | Passed |
| Verified native bridge source absent | Passed |
| Plugin registration guarded by `completeControl()` | Passed by source guard |

## Exact native work still required

The following are intentionally unresolved and are required before a working live plugin may be built:

1. Hash the exact `bedrock_server` or `bedrock_server.exe` extracted from the verified official `1.26.33.1` ZIP.
2. Locate and behavior-confirm all 19 required sign/native update symbols independently on Windows and Linux.
3. Review ABI signatures and calling contracts.
4. Implement and review `src/verified_bds_26_30_adapter.cpp`.
5. Install and validate the cancellable player-edit hook.
6. Pass all 31 disposable-world probes, including client refresh, reconnect, restart persistence, and rollback.
7. Generate the activated platform manifest and compile the exact plugin against Endstone `0.11.6`.

Until those steps pass, the plugin refuses to register `endstone:sign:v2`.
