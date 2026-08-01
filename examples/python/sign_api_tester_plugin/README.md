# Endstone Sign API Tester

This CPython 3.14 Endstone wheel exercises the exact native
`endstone:sign:v2` service and writes both the strict activation-stage report
and an untruncated automated matrix report. It never uses the in-memory
reference adapter.

Install the native plugin and matching tester wheel from the same exact
package ZIP. Use only a backed-up disposable world: the commands place and edit
sign blocks and may remove only cells recorded as runner-owned.

## v0.2.0 Linux diagnostics

The Linux-only standalone native download is named
`endstone_sign_bds_1_26_33.so`; place it and the matching v0.2.0 Linux tester
wheel directly in the server's `plugins/` directory. The tester also
recognizes the long standalone filename published in alpha.3 and searches
beside the actual server executable when a hosting panel uses a different
working directory.

Verify the downloaded release before installation. `SHA256SUMS.txt` covers all
four Linux package assets; the platform manifest covers the native library,
ZIP, and matching tester wheel. The GitHub release therefore contains those
four package assets plus `SHA256SUMS.txt`:

```bash
gh release download v0.2.0 \
  --repo TheNINJALLO/endstone-sign-api \
  --dir sign-api-0.2.0
cd sign-api-0.2.0
sha256sum --check SHA256SUMS.txt
sha256sum --check endstone-sign-api-v0.2.0-bds-1.26.33-linux-x64.sha256
```

Choose an air-filled disposable arena large enough for a 28-by-17-block
default footprint. The command coordinates are the arena anchor and the signs
start one block above its Y coordinate. Test the stable supported scope with:

```text
/signprobe run 100 64 100 confirm
```

Maintainers developing the known unavailable capabilities can start the strict
optional complete-control profile with:

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

The acceptance session spans actions that cannot happen in one server tick.
When the automated runner says guided evidence remains, perform each real
client action and then record it. Do not paste these examples unchanged:

```text
/signprobe editor front
/signprobe record open_editor_front true Front editor opened at <coordinates>; observed <time/log reference>
/signprobe editor back
/signprobe record open_editor_back true Back editor opened at <coordinates>; observed <time/log reference>
/signprobe record player_edit_event_observed true Client edit emitted the expected event; log <reference>
/signprobe record player_edit_event_cancelled true Cancelled client edit left the captured content and revision unchanged; log <reference>
/signprobe record client_refresh true Connected client immediately showed the captured front and back state at <coordinates>
/signprobe record player_reconnect true Reconnected client and API capture retained the expected state and revision
/signprobe record server_restart_persistence true Full stop/start retained the expected state and revision in the client and API capture
```

These seven results are operator-attested. The validator binds them to this
run, world, executable, plugin, tester wheel, final log, and backup, but it does
not independently see the Bedrock client UI. A release reviewer must inspect
the recorded notes and bound artifacts.

After those checks, run ownership-aware cleanup. Do not call
`/signprobe remove` on the retained sign: cleanup supplies and auto-projects the
required `remove` evidence.

```text
/signprobe cleanup confirm
/signprobe runstatus
/signprobe path
```

Stop the server cleanly, preserve an immutable final-log copy, and create a
post-cleanup world backup. Hash those exact files, restart only to record the
hashes and finish, and pass the same immutable files to the offline validator:

```bash
sha256sum acceptance-server.evidence.log post-cleanup-world-backup.zip
```

```text
/signprobe meta log_sha256 <acceptance-server.evidence.log-sha256>
/signprobe meta world_backup_sha256 <post-cleanup-world-backup.zip-sha256>
/signprobe finish
/signprobe runstatus
/signprobe path
```

On the host, validate the final files:

```bash
python tools/validate_full_system_acceptance.py \
  latest-matrix-report.json linux-x64-1.26.33.1-stage-probe.json \
  --server-executable ./bedrock_server \
  --plugin-binary plugins/endstone_sign_bds_1_26_33.so \
  --tester-wheel plugins/endstone_sign_tester-0.2.0-cp314-cp314-linux_x86_64.whl \
  --server-log acceptance-server.evidence.log \
  --world-backup post-cleanup-world-backup.zip
```

The final command must print `full-system acceptance VALID`. This result
qualifies only the exact Linux artifacts supplied to the validator; v0.2.0
does not publish or claim support for a Windows native DLL or tester wheel. The
validator rejects anything short of 48/48 cases, 31/31 probes, all required
capabilities, zero failed/skipped/manual coverage, exact identity agreement,
and conflict-free cleanup.

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
`bds-1.26.33.1-linux-release` and `supported_release: true` before the stable
matrix starts. Version 0.2.0 covers both-side plain and filtered text, owner
XUID, outline/formatting flags, placement/removal/replacement/clone/move,
atomic transactions, client updates, and API edit events. TextObjects, color,
glow, wax, editor locking/opening, player edit interception, restart-persistence
certification, and `complete_control` remain false. Those closed capabilities
block only the optional complete-control profile, not the supported v0.2.0
matrix.

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
report supplements that evidence; the optional complete-control qualifier requires
truthful native capabilities and zero skipped steps, so hand-recorded evidence
cannot turn the current missing native layers into a passing result.

## Third-party plugin boundary

This tester wheel is a qualification harness, not a runtime SDK. Its
`_endstone_sign_live` extension is private and version-locked to the tester;
third-party Python plugins must not import it. Live C++ consumers should load
the typed `LiveSignService` named `endstone:sign:v2`, require ABI 2, require
`completeControl()` for production use, capture a fresh revision before every
mutation, and handle every non-applied result. See the repository root README
for service-lookup and patch examples. The pure Python
`endstone_sign` package remains suitable for typed plugin logic and in-memory
unit tests until a public live Python binding is released.
