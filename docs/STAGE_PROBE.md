# Disposable-world stage probe

The native gate requires every probe in `native/probes/STAGE_PROBE_TEMPLATE.json`.

## Setup

- Use a disposable world copied before every probe run.
- Record the exact server executable SHA-256 and plugin SHA-256.
- Use one operator and at least one Bedrock client.
- Keep server logs and a post-test world backup, then record their SHA-256 values.

## Required probes

The contract covers placement of all four forms; front/back and per-line editing; filtered text; text objects; ownership; color and visual flags; wax/unwax; lock/unlock; both editor sides; observed and cancelled player edits; cancelled API edits; replace/clone/move/remove; atomic rollback; immediate client refresh; reconnect; and full server-restart persistence.

Each result needs concrete evidence, such as coordinates, expected value, observed value, command output, or a bounded log reference.

## Acceptance

1. Fill a copy of the template for the platform.
2. Set a probe to passed only after its expected state is captured from the live server and observed by a client where applicable.
3. Set top-level `passed=true` only when every probe passes.
4. Validate the report:

```bash
python tools/validate_stage_probe_report.py native/probes/<report>.json
```

5. Record the printed report SHA-256 in the platform manifest.

Any crash, stale client display, lost restart state, uncancellable player edit, item duplication, partial move, or rollback failure closes the native gate.
