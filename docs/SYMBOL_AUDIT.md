# Exact sign symbol audit

## Scope

Audit Windows and Linux independently against the official BDS `1.26.33.1` executables. Never reuse an RVA, vtable offset, class layout, or byte pattern from another Bedrock build.

## Required behavior anchors

The manifest requires proof for:

- full sign save and load;
- message and raw-message reads;
- text color, glow, hidden outline, wax, and edit-lock reads;
- server-side text changes;
- color, glow, hidden outline, wax, lock, and unlock writes;
- native editor opening;
- player text update interception;
- block-actor client update notification.

A capability may be implemented through a behavior-equivalent exact function, but the manifest note must explain that path.

## Per-symbol acceptance

For each entry:

1. Locate the candidate in the exact executable.
2. Confirm its full signature and calling convention.
3. Confirm the candidate's behavior in disassembly or decompilation.
4. Confirm callers, side effects, and relevant constants or data flows.
5. Record its RVA and a short instruction fingerprint.
6. Verify the fingerprint resolves uniquely in that executable.
7. Write a concise public note without copying private source or large disassembly.
8. Set `resolved`, `unique`, `signature_verified`, and `behavior_verified` only after the checks pass.

Function size and a unique byte pattern are not sufficient behavior proof.

## Static candidate ledger

`native/audits/linux-x64-1.26.33.1-text-symbol-candidates.json` records the
three byte ranges used by the alpha.6 experimental Linux text bridge. It has a
candidate-only schema that is deliberately incompatible with the activation
manifests. Validate its structure, blocked-manifest binding, and adapter
constant binding without a BDS executable:

```bash
python tools/verify_native_symbol_candidates.py
```

When the exact official executable is available locally, audit its identity,
ELF executable-range mapping, full range hashes, and unique entry
fingerprints offline:

```bash
python tools/verify_native_symbol_candidates.py /path/to/bedrock_server
```

Even a passing exact-ELF audit is only static candidate byte evidence. The
tool is read-only, does not populate `native/manifests/`, and cannot satisfy
signature, ABI, behavior, hook, or disposable-world gates.

## Linux TextObject serializer boundary

The v0.2.1-alpha.1 and later Linux candidates additionally call the exact BDS
`TextObjectRoot` JSON serializer at RVA `0x09DD50D0`. The complete 122-byte
function fingerprint is
`9b385769e1291cf163e38eea2a0ed7f8527894af81f3201cff2889262486b58a`.
Review confirmed that it creates the Bedrock `rawtext` object and invokes each
native child object's JSON conversion. The adapter validates the executable
segment and full fingerprint before exposing any native capability; it commits
neither the executable nor disassembly.

## ABI acceptance

Record and review:

- the `SignBlockActor` base offset used by the bridge;
- the exact underlying size and values of `SignTextSide`;
- the color argument/return contract;
- platform calling-convention notes;
- any class or helper declaration used across the ABI.

Avoid direct member access when a verified function call can provide the same behavior.

## Player edit hook

The hook must:

- observe front and back edits;
- construct the before and candidate-after snapshots;
- publish a cancellable event before the original mutation;
- skip the original mutation when cancelled;
- preserve the original call exactly when accepted;
- remove lock/listener state when the player disconnects;
- avoid recursion when the API itself performs a write.

## Public-data boundary

Do not commit binaries, PDBs, private generated headers, whole symbol tables, decompiler output, or large disassembly blocks. Commit only the minimal exact manifest and bridge needed by the project.
