# Changelog

## 0.2.1-alpha.3

- Fixed the strict Linux acceptance scheduler's editor-lock roundtrip. The
  tester now captures the synthetic lock and restores the original unlocked
  state immediately, within the same scheduled tick and revision chain.
- Retained separate `capture_editor_lock` and `capture_editor_unlock` evidence
  steps, so the validator still requires both semantic operations rather than
  treating the combined scheduling boundary as one assertion.
- Added a regression model that clears any synthetic lock left at a tick
  boundary, matching the alpha.2 live report and preventing the unlock plus
  downstream source-revision cascade from returning.
- Preserved alpha.2's successful 48/48 material/form cases, TextObject
  restoration, and all earlier extended-field results without weakening exact
  binary, ownership, readback, cleanup, or evidence gates.

## 0.2.1-alpha.2

- Fixed the strict Linux acceptance harness's TextObject cleanup. When the
  source began as plain text, the probe now disables object mode and then uses
  the returned revision to restore the original four lines explicitly.
- Added a live-behavior regression that renders the probe object as `a7`,
  confirms disabling object mode alone retains that rendering, and requires
  the full 12-operation sequence plus conflict-free cleanup to pass.
- Preserved the successful alpha.1 runtime findings: all 48 material/form cases
  passed and every pre-stage native capability was available. Alpha.2 fixes the
  retained-source revision cascade exposed by that run; it does not weaken an
  activation, readback, ownership, cleanup, or evidence gate.

## 0.2.1-alpha.1

- Removed the stable-build capability overrides and mutation rejections so the
  exact Linux artifact exposes text objects, ARGB color, glow, wax, editor
  lock/open, player-edit interception, and restart-persistence coverage in the
  same strict acceptance run.
- Corrected TextObject input to Bedrock's `rawtext` schema and replaced the
  rendered-message cache read with the exact native TextObject JSON serializer,
  guarded by its executable range and full SHA-256 fingerprint.
- Corrected editor-lock qualification to verify the native runtime ID and only
  derive an XUID when that ID belongs to an online player.
- Re-enabled player-edit hook installation in supported Linux builds while
  retaining exact executable, function, ABI, revision, readback, rollback, and
  stage-evidence gates.
- Versioned the plugin and CPython 3.14 tester as a distinct Linux-only
  qualification candidate so it cannot be confused with stable v0.2.0.

## 0.2.0

- Published the first supported Linux x64 `endstone:sign:v2` ABI 2 service for
  exact BDS `1.26.33.1` and Endstone `0.11.6`.
- Added `SignCapabilities::supportedRelease()` so production consumers can
  require the stable text/structure tier without confusing it with the future
  `completeControl()` contract.
- Fixed the matrix preflight to accept the release adapter's valid `captured`
  actor status in addition to the older experimental status.
- Kept known failed or unaccepted surfaces false: text objects, color, glow,
  wax, editor lock/open, player edit interception, restart persistence, and
  complete control.
- Added practical C++ integration examples for a chest shop, two-way Discord
  sign synchronization, and scheduler-driven moving messages.
- Restricted release artifacts to the Linux `.so`, Linux SDK ZIP and checksum,
  and the matching CPython 3.14 diagnostic wheel.

## 0.2.0-alpha.9

- Enabled the experimental exact-binary-gated adapter capabilities for sign
  replacement, cloning, moving, and multi-operation transactions so the
  strict qualification runner can exercise every implemented structural layer
  in one disposable-world session.
- Added a transaction ledger with reverse-order rollback. Existing signs are
  restored from captured structural and supported text state, while signs
  created by a failed transaction are independently cleared and verified as
  air.
- Fixed the native rollback build failure caused by passing const actor access
  to the mutating block-actor change notifier, and added a regression guard for
  that compile-sensitive path.
- Passed the complete push qualification matrix at commit `77d5c22`: portable
  C++ and Python lanes, exact BDS 1.26.33 Linux and Windows builds, platform
  asset checks, wheel smoke tests, and the combined two-wheel verifier.
- Kept verified complete-control activation fail-closed. The newly exposed
  structural operations still require the exact runtime/executable gate;
  Windows live mutation, advanced SignBlockActor fields, player interception,
  client acknowledgement, reconnect, and restart persistence still require
  their corresponding qualification evidence.

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
