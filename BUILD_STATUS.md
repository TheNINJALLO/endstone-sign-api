# Build status

Version: **0.2.0-alpha.1**

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
- Executable identities: intentionally empty pending local package inspection.
- Required symbols: manifest skeleton present, unresolved.
- Verified bridge source: absent.
- Stage probe: not passed.
- Live service registration: disabled by design.

This release is safe to use as an API/reference package, not as a working native sign plugin.
