# Build status

Version: **0.2.0-alpha.6**

## Portable core

- C++20 library: implemented.
- Portable Windows DLL and Linux shared-library targets: implemented.
- Warnings as errors: enabled.
- Linux portable build: validated locally.
- C++ tests: passing.
- Pure Python package: implemented.
- Tag-driven GitHub SDK and wheel release workflow: implemented.
- Python tests: passing.
- Source ZIP, pure-Python wheel, and portable Linux SDK package: validated.
- Service ABI: `endstone:sign:v2`.

## Exact native bridge

- Target package: BDS `1.26.33.1`.
- Runtime string: `26.33`.
- Endstone: `0.11.6`.
- Windows archive identity: pinned.
- Linux archive identity: pinned.
- Linux executable identity: pinned and matched by the off-site report.
- Windows executable identity: pinned from the exact official archive.
- Linux plain-text candidates: independently mapped and protected by exact
  executable, full-function, vtable, representation, readback, and rollback gates.
- Windows runtime executable-identity verification and sign text symbols: unresolved; its probe candidate is build/packaging diagnostics only, with live capture and mutation disabled.
- Verified bridge source: absent.
- Stage probe: not passed.
- Experimental service registration: enabled with partial capabilities in the
  disposable-server candidate.
- Linux structural mutation: executable-hash gated; blank placement,
  suite-owned no-drop removal, and UI-only editor dispatch are exposed to the
  disposable-world tester but remain live-unverified.
- Canonical sign identifier inventory: all 36 IDs are pinned to both exact
  executable identities; the exact Linux binary scan passed 36/36.
- Descriptor safety: the tester resolves its support plus all 48 sign/state
  descriptors before mutation, and native placement rejects absent registry
  types before calling `createBlockData`.
- Automated tester: strict 48-case default matrix, one operation per scheduled
  interval, atomic JSON checkpoints, cancellation, and ownership-aware cleanup.
- Raw Linux formatting-code text: transported and read back as ordinary UTF-8
  within the 22-byte boundary; client rendering is not inferred.
- Advanced SignBlockActor NBT: color, glow, outline, wax, filtered text,
  TextObject, owner, formatting flags, profanity state, and editor locking stay
  capability-gated and are never auto-marked passed.
- Standalone native assets: published under the canonical install-ready
  `endstone_sign_bds_1_26_33` filename; tester discovery also recognizes the
  legacy alpha.3 release filename and the server executable directory.
- Verified complete-control registration: disabled by design.

Use the native candidate only in a backed-up disposable world. It is intended
to collect the live evidence required for the next boundary, not for production.
Alpha.5 is superseded after its Linux matrix aborted on the invalid
`dark_oak_standing_sign` alias; alpha.6 corrects and preflights that path.
