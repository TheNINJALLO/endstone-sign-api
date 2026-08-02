# Building the exact production plugin

The stable native artifact targets Linux x86-64, BDS package `1.26.33.1`
(runtime `26.33`), Endstone `0.11.6`, and CPython `3.11` or newer for the
build environment.

Normal source builds create the portable API and remain native-fail-closed. Use
the exact packaging script for the installable server plugin.

## Requirements

- Ubuntu 22.04-compatible Linux x86-64 environment;
- CPython 3.11 or newer;
- CMake 3.20+ and Ninja;
- Clang/LLVM 18 with libc++ and lld;
- Conan 2.31.1;
- Endstone 0.11.6 dependencies;
- network access to the configured Endstone and Conan repositories.

## Portable validation

```bash
python -m pip install -e .
python -m compileall -q python
python -m unittest discover -s tests/python -p 'test_*.py' -v

cmake -S . -B build \
  -DENDSTONE_SIGN_BUILD_TESTS=ON \
  -DENDSTONE_SIGN_BUILD_SHARED=ON \
  -DENDSTONE_SIGN_BUILD_PLUGIN=OFF
cmake --build build --parallel
ctest --test-dir build --output-on-failure
```

## Exact Linux package

```bash
python scripts/build_exact.py \
  --bds 1.26.33 \
  --platform linux-x64 \
  --parallel 2
```

The script pins the exact package/runtime metadata, configures the supported
native bridge, enables the accepted stable capability contract, disables the
obsolete diagnostic runtime entirely, builds the plugin, installs a production
SDK stage, packages it, and runs the platform asset verifier.

Expected outputs:

```text
dist/release/endstone_sign_bds_1_26_33.so
dist/release/endstone-sign-api-v0.2.1-bds-1.26.33-linux-x64.zip
dist/release/endstone-sign-api-v0.2.1-bds-1.26.33-linux-x64.sha256
```

Verify them explicitly:

```bash
python scripts/verify_release_assets.py \
  --slug endstone-sign-api \
  --version 0.2.1 \
  --bds 1.26.33 \
  --platform linux-x64 \
  --release-dir dist/release

cd dist/release
sha256sum --check endstone-sign-api-v0.2.1-bds-1.26.33-linux-x64.sha256
```

The verifier checks the ELF architecture, runtime linkage, relocation paths,
archive integrity, manifest digests, plugin identity, required SDK files, and
the absence of command wheels, diagnostic bridges/services, and test payloads.

## Release tags

The GitHub release workflow requires tag `v0.2.1` to point to a commit already
contained in `main`. It repeats portable tests, metadata validation, the exact
Linux build, package verification, combined checksum generation, and stable
GitHub release publication.

## Redistributable boundary

Never commit or package BDS executables, PDB/debug databases, private generated
headers, complete symbol dumps, or decompiler output. Public artifacts contain
only the API plugin, SDK materials, and the minimum compatibility metadata.
