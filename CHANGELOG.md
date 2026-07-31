# Changelog

## 0.2.0-alpha.8

- Fixed successful native capability preflight records so they include a
  non-empty evidence reason. This lets the strict qualification validator
  recognize a gate that genuinely passed, with regression coverage for the
  evidence contract.
- Hardened native activation so a manifest's duplicated pass booleans are not
  sufficient. The verifier now requires hash-bound stage and matrix reports,
  validates their 31-probe evidence, and binds their platform, executable,
  artifacts, run, configuration, world, target, and qualification verdict.
- Consolidated the existing full-system workflow as the final qualification
  candidate before an official release. No native capability is enabled by
  this version bump: unresolved advanced, Windows, player-edit, persistence,
  symbol, ABI, and live-stage requirements remain explicit release blockers.

## 0.2.0-alpha.7

- Added `/signprobe accept <x> <y> <z> confirm`, a strict full-system
  qualification mode that forces all 12 materials and four sign forms, starts
  the exact 31-probe stage report, enables every implemented advanced phase,
  continues through case failures, and defers ownership cleanup until after
  reconnect/restart evidence can be collected.
- Added a derived qualification verdict. It passes only with 48/48 cases,
  31/31 evidence-backed probes, every native capability except the final
  stage-pass flag, zero failed/skipped steps, exact stage/matrix identity
  agreement, and completed conflict-free cleanup with no owned blocks left.
- Added `tools/validate_full_system_acceptance.py` and regression tests for a
  complete qualification plus fail-closed rejection of any closed native
  layer. Official evidence now binds and independently re-hashes the exact BDS
  executable, tester wheel, native plugin, final server log, and world backup,
  then validates operation-specific requests, revisions, readbacks, cleanup,
  timestamps, and ownership instead of accepting generic success objects.
- Added live-bridge executors for all 12 server-side run probes: advanced text
  fields, editor lock/unlock, API-event cancellation, replacement, clone,
  move, and a deterministic two-operation rollback check. Clone/move scratch
  cells and the temporary rollback guard are preflighted, ownership tracked,
  revision checked, and included in strict cleanup validation. Sign ownership
  is cleared only after the remove response succeeds and a public block read
  independently proves air.
- Added a versioned auxiliary live-probe service so event-cancellation probes
  execute inside the provider plugin's ABI boundary. Listener state has shared
  lifetime, unique concurrent probe tokens, and no lock held across synchronous
  event callbacks.
- Kept exact executable, native fingerprint/ABI, primary-thread, descriptor,
  revision, ownership, readback, and rollback gates intact. Alpha.7 is a
  downloadable prerelease qualification candidate, not a verified production
  bridge; currently unimplemented advanced and Windows layers remain explicit
  blockers.

## 0.2.0-alpha.6

- Fixed the legacy Bedrock dark-oak standing/wall identifiers to
  `minecraft:darkoak_standing_sign` and `minecraft:darkoak_wall_sign` while
  retaining `minecraft:dark_oak_hanging_sign` for hanging signs. Portable and
  tester classification now reject the invalid separated aliases.
- Added exhaustive 12-material identifier coverage across standing, wall,
  ceiling-hanging, and wall-hanging placement plans.
- Added a pre-mutation tester gate that resolves the support block, cleanup air,
  and every planned sign identifier/state descriptor through Endstone before
  the first arena write. Any missing type, invalid state, or readback mismatch
  stops the run and is recorded in its report.
- Added a cache-only native registry enumeration before the experimental adapter enters
  Endstone's `createBlockData` boundary. An absent block type now returns an
  invalid-patch result without invoking either Endstone's terminating
  `Registry<BlockType>::get` miss path or its throwing descriptor path.
- Added an executable-bound inventory of all 36 canonical sign block IDs and
  a privacy-safe streaming verifier. Exact builds always compare the portable
  API and test-wheel generators; a locally supplied exact server executable
  can additionally be hash-, size-, and identifier-scanned.
- Made every matrix mutation intent a durable checkpoint so an interrupted or
  crashed run records the exact phase that was in flight.
- Supersedes alpha.5, whose hosted Linux run passed the first 20 cases but
  aborted when case 21 generated the invalid dark-oak standing identifier.
  Alpha.6 remains a disposable-world probe candidate; it does not claim that
  the cross-DSO C++ exception-runtime boundary is generally hardened.

## 0.2.0-alpha.5

- Added a one-command, tick-stepped disposable-world matrix:
  `/signprobe run <x> <y> <z> confirm`. The default configuration covers all
  12 sign materials in standing, wall, ceiling-hanging, and wall-hanging forms.
- Added strict editable `matrix-config.toml` settings for materials, forms,
  canonical states, support blocks, spacing, raw formatting-code text, ARGB,
  glow, wax, scheduling, cleanup, and failure behavior.
- Added a package-local blank-placement bridge and automated structural
  capture, exact front/back short-text readback, opposite-side preservation,
  individual-line preservation, cancellation, and ownership-aware cleanup.
- Added untruncated per-run JSON evidence with an explicit disposition for all
  31 activation probes. Unsupported and client/manual probes never count as
  passes and `activation_eligible` remains false.
- Fixed the editor UI probe to request `acquire_lock=false` and
  `bypass_wax=true`, without claiming an editor lock or client acknowledgement.
- Hardened every experimental structural mutation with the exact executable
  SHA-256 gate inside the native adapter. Unverified Windows structural writes
  are now disabled rather than relying only on tester-side preflight.
- Added capability-specific no-mutation gates for ARGB color, glow, and wax;
  the Linux plain-text bridge no longer receives those requests while their
  native NBT boundaries are closed.
- Added expected-revision checks to every tester text write, exact
  placement-revision ownership, structural revalidation on every readback,
  and native rollback when blank placement cannot be verified.
- Removed force-placement from the tester bridge and made cleanup validate the
  run ID, configuration hash, reconstructed plan, world identity, and current
  server/plugin binaries before it can touch a recorded cell.
- Added the complete portable test suites to the tag-release gate and expanded
  tester-wheel smoke checks to validate the packaged alpha.5 plugin and
  48-case default configuration.

## 0.2.0-alpha.4

- Fixed native-plugin discovery when the standalone alpha.3 `.so`/`.dll` was
  installed under its long GitHub release filename.
- Added backward-compatible discovery for canonical and legacy release names,
  with deduplicated searches under both the launch working directory and the
  server executable directory.
- Changed standalone native release assets to the canonical install-ready
  `endstone_sign_bds_1_26_33.so` and `.dll` names while retaining versioned ZIP
  and checksum names.
- Added regression coverage for legacy names, unrelated native plugins,
  ambiguity, and control-panel working-directory differences.

## 0.2.0-alpha.3

- Added a Linux x64 disposable-world plain-text bridge for the exact BDS
  `1.26.33.1` executable. It requires the exact executable SHA-256, exact full
  function hashes, the exact Sign/HangingSign vtable, and the libc++ string ABI
  before it exposes front/back text capabilities.
- Added readback, owner-preservation, and rollback verification around every
  experimental text write. The first probe candidate is deliberately limited
  to 22-byte libc++ small strings and refuses existing text objects.
- Kept the complete native manifest, advanced sign fields, player-edit hook,
  and complete-control capability fail-closed pending disposable-world proof.
- Added explicit native-plugin discovery diagnostics and capability preflight
  so blocked tester commands record that no mutation was attempted.
- Recorded both exact Linux and Windows server executable identities without
  redistributing either server binary.

## 0.2.0-alpha.2

- Fixed `/signprobe` registration on Endstone 0.11.6 by declaring explicit,
  unique `front|back` enum types for every side-taking overload.
- Added command-schema regression tests for unsupported bare types, duplicate
  enum names, empty enum values, and misplaced `message` arguments.

## 0.2.0-alpha.1

- Replaced the narrow text-only prototype with the `endstone:sign:v2` complete lifecycle contract.
- Added capture, place, replace, remove, clone, move, native-editor, and atomic transaction operations.
- Added typed placement helpers for all supported sign materials and all four sign forms.
- Added independent front/back access, four-line edits, filtered text, text objects, owner XUID, ARGB color, glow, hidden glow outline, and formatting persistence.
- Added wax/unwax, editor lock/unlock, profanity-filter state, revision conflicts, cancellable events, and audit actor context.
- Added an atomic in-memory C++ and Python reference adapter with rollback.
- Added canonical sign NBT projections for `FrontText`, `BackText`, wax, and editor lock data.
- Added exact BDS package identity manifests for Windows and Linux, using official package hashes for `1.26.33.1`.
- Added required-symbol, ABI, player-edit-hook, bridge-hash, and disposable-world activation gates.
- Added local BDS archive hashing without redistributing server binaries.
- Made the plugin refuse `endstone:sign:v2` registration unless every complete-control capability is verified.
- Added portable C++ and Python regression coverage and fail-closed CI checks.

## 0.1.0-alpha.1

- Initial sign text contract prototype.
