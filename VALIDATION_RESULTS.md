# Endstone Sign API validation results

Release: `0.2.1`

Service: `endstone:sign:v2` ABI `2`

Native target: Linux x86-64, BDS `1.26.33.1`, Endstone `0.11.6`

## Full-system result

The completed Linux acceptance cycle exercised every sign material/form and
native capability layer together:

| Result | Value |
|---|---:|
| Material/form cases | 48/48 passed |
| Capability coverage | 31/31 passed |
| Passed steps | 931 |
| Failed steps | 0 |
| Skipped steps | 0 |
| Attempted mutations | 543 |
| Cleanup conflicts | 0 |

The completed run used the exact BDS executable and native implementation that
were promoted into the stable source line:

```text
bedrock_server  61995841f21baf9bfab96e0d9b0cb798501dcc9789dab68e496f3b8e3bc83375
native plugin   c7ebcaaa7101e99d02d95e7e6c2aefa305da9d54e9454f737a30c6ff250f08f5
```

The stable code removes the former command/diagnostic runtime surface while
leaving the accepted `endstone:sign:v2` implementation unchanged apart from
stable version metadata and production packaging.

## Portable validation

| Check | Result |
|---|---|
| Python compilation and unit/regression suite | Passed |
| C++20 configure, build, and CTest | Passed |
| Warnings as errors | Enabled |
| Pure-Python reference wheel | Built and inspected in CI |
| Linux and Windows portable lanes | Passed in CI |

## Exact Linux release validation

| Check | Result |
|---|---|
| Official BDS archive and executable identity pinned | Passed |
| Canonical sign identifiers | 36/36 matched |
| Native function and representation guards | Passed |
| TextObject plain-line restoration regression | Passed |
| Editor-lock same-tick restoration regression | Passed |
| Player/API event cancellation and original-call preservation | Passed |
| Atomic rollback and conflict handling | Passed |
| ELF x86-64 format and runtime linkage | Enforced |
| SDK archive safety and package-manifest digests | Enforced |
| Production-only three-file payload set | Enforced |
| Diagnostic command/service/wheel exclusion | Enforced |

## Supported contract

The stable release provides capture, placement, replacement, removal, clone,
move, atomic transactions, independent front/back text, individual lines,
filtered and raw-text object data, ownership, ARGB color, glow, outline,
formatting, wax, editor lock/opening, player/API edit events, client updates,
restart persistence, revisions, readback, cancellation, and rollback.

The production plugin is Linux-only and registers no command namespace. Other
plugins consume the typed service and define their own commands and gameplay.
