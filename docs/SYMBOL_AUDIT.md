# Exact native boundary audit

## Supported identity

The production native adapter supports only Linux x86-64, official BDS package
`1.26.33.1`, runtime `26.33`, and Endstone `0.11.6`. Addresses, layouts, vtable
positions, and byte fingerprints are never reused for another Bedrock build.

The running `bedrock_server` must match:

```text
SHA-256  61995841f21baf9bfab96e0d9b0cb798501dcc9789dab68e496f3b8e3bc83375
Size     232842872 bytes
```

## Reviewed behavior anchors

The adapter guards the native boundaries used for:

- complete sign save/load and actor capture;
- front/back message and raw-message access;
- filtered text and TextObject JSON conversion;
- color, glow, hidden outline, formatting, owner, wax, and editor-lock state;
- server-side text and presentation changes;
- editor request dispatch;
- player text-update interception;
- block-actor dirty marking and client notification;
- structural replacement, removal, clone, move, and rollback.

Each boundary is tied to the exact executable range and the calling or
representation contract used by the adapter. A version string by itself is not
accepted.

## Representation safeguards

The Linux implementation validates its `SignBlockActor` and text-side
assumptions before reporting readiness. Short native strings stay within the
accepted representation boundary, and TextObject data uses Bedrock’s native
`rawtext` JSON serializer rather than treating rendered text as canonical JSON.

The serializer boundary is additionally protected by its executable range and
complete function fingerprint.

## Player-edit interception

The stable hook:

- observes front and back player edits;
- builds before and proposed-after snapshots;
- publishes a cancellable event before native mutation;
- skips the original mutation when cancelled;
- preserves the original native call exactly when accepted;
- avoids recursion for API-originated writes;
- removes hook/listener state during shutdown.

## Runtime failure behavior

If executable identity, a required fingerprint, native actor access, the player
hook, or another required capability is unavailable, `completeControl()` is
false. The production plugin then refuses to present a complete service for
that environment.

## Public-data boundary

The repository and release artifacts never redistribute BDS executables,
PDB/debug databases, private generated headers, full symbol tables, decompiler
output, or large disassembly blocks. Public materials contain only the minimum
identity and behavioral descriptions required to document the supported API.
