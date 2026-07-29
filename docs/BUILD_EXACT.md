# Building the exact native Sign API

A normal source build produces the portable core and the closed plugin boundary. It does not produce a usable native sign plugin.

## Prerequisites

- The official BDS `1.26.33.1` ZIP for the target platform.
- Endstone `v0.11.6` dependencies through Conan 2.
- A private reverse-engineering workspace for exact symbol and ABI analysis.
- A disposable BDS world and test account/client.

Never commit the BDS executable, PDB, reconstructed private headers, full dumps, or decompiler output.

## 1. Verify the official archive

```bash
python tools/hash_bds_package.py /private/path/bedrock-server-1.26.33.1.zip \
  --platform linux-x64 \
  --json-out /private/path/linux-executable-identity.json
```

Copy only the executable SHA-256 and size into the matching public manifest after confirming the archive hash.

## 2. Complete the symbol audit

Follow `docs/SYMBOL_AUDIT.md`. Every symbol entry requires an exact RVA, a short fingerprint, signature confirmation, behavior confirmation, and concise verification notes.

## 3. Implement and review the native bridge

Create `src/verified_bds_26_30_adapter.cpp` using only the reviewed manifest and minimal public declarations. Compute its SHA-256 and record it in the manifest. Set `bridge.reviewed=true` only after code review.

## 4. Run the disposable-world probe

Follow `docs/STAGE_PROBE.md`. Validate the report and record its SHA-256:

```bash
python tools/validate_stage_probe_report.py \
  native/probes/linux-x64-1.26.33.1-stage-probe.json
```

## 5. Open the activation gate

```bash
python tools/verify_native_manifest.py \
  native/manifests/linux-x64-1.26.33.1.json

python tools/activate_verified_manifest.py \
  native/manifests/linux-x64-1.26.33.1.json
```

## 6. Build

Configure through the exact Conan toolchain and enable the verified bridge:

```bash
cmake -S . -B build-exact \
  -DCMAKE_TOOLCHAIN_FILE=/path/to/conan_toolchain.cmake \
  -DENDSTONE_SIGN_BUILD_PLUGIN=ON \
  -DENDSTONE_SIGN_BUILD_TESTS=ON \
  -DENDSTONE_SIGN_VERIFIED_NATIVE_BRIDGE=ON \
  -DENDSTONE_BDS_BUILD=1.26.33 \
  -DENDSTONE_BDS_PACKAGE=1.26.33.1
cmake --build build-exact --parallel
ctest --test-dir build-exact --output-on-failure
```

The configure step fails if the verified bridge source is absent. Runtime registration still fails if the binary hash or generated proof flags do not match.
