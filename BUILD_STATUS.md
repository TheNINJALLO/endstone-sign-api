# Build status

Version: **0.2.0-alpha.3**

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
- Windows sign text symbols: unresolved; its probe candidate is structural-only.
- Verified bridge source: absent.
- Stage probe: not passed.
- Experimental service registration: enabled with partial capabilities in the
  disposable-server candidate.
- Verified complete-control registration: disabled by design.

Use the native candidate only in a backed-up disposable world. It is intended
to collect the live evidence required for the next boundary, not for production.
