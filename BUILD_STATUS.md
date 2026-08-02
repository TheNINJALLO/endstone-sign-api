# Build status

Version: **0.2.1**

## Production release

- Service: `endstone:sign:v2`, ABI `2`.
- Platform: Linux x86-64.
- Exact BDS package: `1.26.33.1`; runtime: `26.33`.
- Endstone: `0.11.6`.
- Complete native sign lifecycle: enabled.
- Front/back text, line edits, filtered text, and raw-text objects: enabled.
- Owner, color, glow, outline, formatting, and wax state: enabled.
- Editor lock/opening and cancellable player/API edit events: enabled.
- Client updates and restart persistence: enabled.
- Replace, clone, move, atomic transaction, and rollback operations: enabled.
- `completeControl()`: true on the exact accepted Linux release path.

The native adapter remains guarded by the exact executable identity and its
native function, vtable, and representation fingerprints. It refuses service
registration on a mismatched runtime or executable.

## Public package

The stable build publishes exactly three production payloads before the
combined GitHub checksum manifest is generated:

- `endstone_sign_bds_1_26_33.so`;
- `endstone-sign-api-v0.2.1-bds-1.26.33-linux-x64.zip`;
- `endstone-sign-api-v0.2.1-bds-1.26.33-linux-x64.sha256`.

The SDK ZIP contains public headers, Python reference modules, production
documentation, integration examples, compatibility metadata, and the native
plugin. It excludes command harnesses, auxiliary diagnostic services, native
test bridges, command wheels, acceptance utilities, and server/debug artifacts.

## Validation status

- Full Linux material/form matrix: 48/48 passed.
- Complete capability coverage: 31/31 passed.
- Recorded steps: 931 passed, zero failed, zero skipped.
- Mutations: 543 attempted with conflict-free cleanup.
- Portable Python and C++ regression suites: passing.
- Exact Linux build and package verification: enforced by GitHub Actions.
- Release asset set, manifest digests, ELF format/linkage, and archive contents:
  enforced before publication.

## Source-build behavior

A normal source or portable build remains fail-closed for native activation.
Only the exact stable packaging path enables the supported and accepted Linux
release flags. Windows native server artifacts are not built or published.
