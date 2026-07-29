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
