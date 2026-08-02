# Endstone Sign API validation results

Release: `0.2.1`

Service: `endstone:sign:v2` ABI `2`

Native target: Linux x86-64, BDS `1.26.33.1`, Endstone `0.11.6`

## Full-system result

| Result | Value |
|---|---:|
| Material/form cases | 48/48 passed |
| Capability coverage | 31/31 passed |
| Passed steps | 931 |
| Failed steps | 0 |
| Skipped steps | 0 |
| Attempted mutations | 543 |
| Cleanup conflicts | 0 |

Exact accepted identities:

```text
bedrock_server  61995841f21baf9bfab96e0d9b0cb798501dcc9789dab68e496f3b8e3bc83375
native plugin   c7ebcaaa7101e99d02d95e7e6c2aefa305da9d54e9454f737a30c6ff250f08f5
test artifact   781ac74532d5864ce3f556d3735e9eb304974ec89d8d2b2e0152129e6fab5867
```

The stable production package removes the auxiliary command/diagnostic runtime
surface and publishes only the native API plugin, SDK ZIP, and checksums.

## Verified contract

- Complete lifecycle, structure, transactions, rollback, and revisions.
- Independent front/back text and individual-line edits.
- Filtered text, raw-text objects, owner, color, glow, outline, formatting, wax,
  editor lock/opening, player/API events, client updates, and persistence.
- Exact executable, native boundary, primary-thread, readback, and conflict
  safeguards.
- Production archive integrity, digests, ELF linkage, and diagnostic-payload
  exclusion enforced by the release workflow.
