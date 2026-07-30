# Endstone Sign API Tester

This CPython 3.14 Endstone wheel exercises the exact native
`endstone:sign:v2` service and writes both the strict activation-stage report
and an untruncated automated matrix report. It never uses the in-memory
reference adapter.

Install the native plugin and matching tester wheel from the same exact
package ZIP. Use only a backed-up disposable world: the commands place and edit
sign blocks and may remove only cells recorded as runner-owned.

## Alpha.5 one-command matrix

The standalone native download is already named
`endstone_sign_bds_1_26_33.so` (or `.dll`); place it and the matching alpha.5
tester wheel directly in the server's `plugins/` directory. The tester also
recognizes the long standalone filename published in alpha.3 and searches
beside the actual server executable when a hosting panel uses a different
working directory.

Choose an air-filled disposable arena large enough for a 22-by-17-block
default footprint. The command coordinates are the arena anchor and the signs
start one block above its Y coordinate:

```text
/signprobe run 100 64 100 confirm
```

That single command preflights the exact executable/capabilities and every
planned cell before mutation, then schedules one operation per configured interval. The
default `matrix-config.toml` covers all 12 materials in all four forms (48
cases). For each case it creates a solid support fixture, places a blank sign
through the Sign API, captures canonical identifier/kind/states, writes and
reads both sides, checks opposite-side preservation, and changes one line while
preserving the others.

Default front/back text includes raw `§a`, `§c`, and `§e` formatting codes.
This proves their exact UTF-8 round trip through the server; a Bedrock client's
rendered color remains a manual checkpoint. Every rendered four-line message
is validated against the current exact bridge's 22-byte limit, including three
newline separators.

Useful commands:

```text
/signprobe config
/signprobe runstatus
/signprobe cancel
/signprobe cleanup confirm
/signprobe path
```

`/signprobe config` prints the generated editable configuration path. You can
select materials/forms, canonical orientation states, support block, spacing,
front/back text, line edit, ARGB, glow, wax, delay, cleanup, and stop-on-failure
behavior. Invalid, oversized, colliding, or out-of-bounds plans fail before any
world mutation.

The latest evidence is `latest-matrix-report.json` in the tester data folder;
the same per-run checkpoint journal is kept under `runs/<run_id>.json`. Reports record
every request, response, capability requirement, mutation-attempt flag,
readback, revision, owned resource, cleanup conflict, and an explicit
disposition for all 31 activation probes. The runner never truncates this case
evidence.

Cleanup removes a sign only when its identifier and revision still match the
runner's last verified state. A changed cell is preserved and reported as a
conflict. Fixture supports are removed only after the owned sign is gone and
the support still matches the configured block.

## Capability boundaries

On the exact Linux server, status must show adapter
`bds-1.26.33.1-experimental-linux-plain-text`, with `exact_build_match`,
`exact_binary_hash_match`, `capture`, `client_updates`, `place`, `read_text`,
`write_text`, `front_and_back`, and `per_line_write` true before the matrix can
start. A captured actor must report `experimental_text_captured` before text
mutation.

ARGB color, glow, wax, filtered text, text objects, owner XUID, hide-outline,
formatting flags, profanity state, and editor locks remain behind the
unverified SignBlockActor NBT boundary. The runner records them as unsupported
with `mutation_attempted=false` when their individual capability is closed.
Clone, move, and multi-operation atomic transactions are likewise not assumed.

The Windows candidate cannot pass the new exact executable-hash structural
gate and has no text bridge. It remains useful for build/packaging diagnostics,
not live mutation.

Client refresh, editor UI acknowledgement, player edit interception,
reconnect, and restart persistence cannot be proven by one server command.
They remain manual checkpoints, so an automated report always keeps
`activation_eligible=false`; a successful supported-scope matrix is not a
verified complete-control release.

## Targeted commands and activation report

The earlier explicit-coordinate workflow remains available:

```text
/signprobe status
/signprobe begin 47 22 68
/signprobe capture
/signprobe text back test|||
/signprobe text front test|||
/signprobe editor front
/signprobe path
```

Use `/signprobe record`, `/signprobe meta`, and `/signprobe finish` only for the
strict schema-1 activation report. Finish passes only when all 31 probes have
non-empty passing evidence and all required SHA-256 fields are valid. A matrix
report supplements that evidence; it never fabricates passes for unsupported
or manual probes.
