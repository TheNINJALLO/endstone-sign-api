# Endstone Sign API Tester

This CPython 3.14 Endstone wheel exercises the exact native
`endstone:sign:v2` service and writes both the strict activation-stage report
and an untruncated automated matrix report. It never uses the in-memory
reference adapter.

Install the native plugin and matching tester wheel from the same exact
package ZIP. Use only a backed-up disposable world: the commands place and edit
sign blocks and may remove only cells recorded as runner-owned.

## Alpha.9 full-system qualification

The standalone native download is already named
`endstone_sign_bds_1_26_33.so` (or `.dll`); place it and the matching alpha.9
tester wheel directly in the server's `plugins/` directory. The tester also
recognizes the long standalone filename published in alpha.3 and searches
beside the actual server executable when a hosting panel uses a different
working directory.

Choose an air-filled disposable arena large enough for a 28-by-17-block
default footprint. The command coordinates are the arena anchor and the signs
start one block above its Y coordinate. Start the immutable release
qualification profile with:

```text
/signprobe accept 100 64 100 confirm
```

This starts the full 48-case matrix and a matching 31-probe stage report. It
forces all materials/forms, advanced phases, continue-on-failure behavior, and
deferred cleanup regardless of a reduced diagnostic configuration. It never
turns a false native capability on: unsupported operations remain uncalled and
become explicit qualification blockers.

After the case matrix, acceptance mode calls the live bridge once for each of
the 12 server-side run probes: five advanced text fields, editor lock and
unlock, API edit-event cancellation, structural replacement, clone, move, and
atomic rollback. Advanced fields and replacement are restored after exact
readback. Clone and move use two preflighted scratch sign/support cells. The
rollback probe temporarily puts a diamond block in the vacated clone cell,
then requires a two-operation transaction to fail at the adapter boundary,
roll back its first text mutation, and preserve the guard. Cleanup validates
the recorded revisions/content before removing every runner-owned scratch
block.

The configurable supported-scope diagnostic command remains:

```text
/signprobe run 100 64 100 confirm
```

Each command preflights the exact executable/capabilities, resolves the
support, cleanup air, and all 48 exact sign/state descriptors, and checks every
planned cell before mutation. It then schedules one operation per configured interval. The
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

The acceptance session spans operations that cannot happen in one server
tick. Perform the client UI/player-edit checks, reconnect, and restart checks
against the same retained arena; record concrete evidence and required hash
metadata with the strict stage-report commands.

Those seven guided results are operator-attested. The validator binds them to
this run, world, executable, plugin, tester wheel, final log, and backup, but it
does not independently see the Bedrock client UI. The release reviewer must
inspect the recorded notes and bound artifacts.

After recording the seven guided client/player/reconnect/restart probes, run
ownership-aware matrix cleanup. Do not call `/signprobe remove` on the retained
sign: cleanup supplies and auto-projects the required `remove` evidence. Hash
the final server log and post-cleanup world backup into the stage report, then
finish:

```text
/signprobe cleanup confirm
/signprobe meta log_sha256 <64-lowercase-hex>
/signprobe meta world_backup_sha256 <64-lowercase-hex>
/signprobe finish
/signprobe runstatus
```

On the host, validate the final files:

```bash
python tools/validate_full_system_acceptance.py \
  latest-matrix-report.json linux-x64-1.26.33.1-stage-probe.json \
  --server-executable ./bedrock_server \
  --plugin-binary plugins/endstone_sign_bds_1_26_33.so \
  --tester-wheel plugins/endstone_sign_tester-0.2.0a9-cp314-cp314-linux_x86_64.whl \
  --server-log acceptance-server.log \
  --world-backup post-cleanup-world-backup.zip
```

On Windows, pass the exact `bedrock_server.exe` and the Windows `.dll` and
tester wheel paths instead.

Repeat independently on Windows. An official-release review requires both
platform validators to pass. The validator rejects anything short of 48/48
cases, 31/31 probes, all required capabilities, zero failed/skipped/manual
coverage, exact identity agreement, and conflict-free cleanup.

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
reconnect, and restart persistence cannot be proven by one uninterrupted
server command. They remain guided checkpoints, and `activation_eligible`
stays false pending independent review. In acceptance mode they are hard
blockers, not ignored manual entries; a supported-scope matrix is not a
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
report supplements that evidence; the alpha.9 qualifier additionally requires
truthful native capabilities and zero skipped steps, so hand-recorded evidence
cannot turn the current missing native layers into a passing result.
