# Changelog

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
