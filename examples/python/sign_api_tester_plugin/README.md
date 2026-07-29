# Endstone Sign API Tester

This CPython 3.14 Endstone wheel exercises the exact native
`endstone:sign:v2` service and writes the JSON report required by the Sign API
activation gate. It never uses the in-memory reference adapter.

Install the native plugin and the matching tester wheel from the same exact
package ZIP. Use only a backed-up disposable world: the commands can edit or
remove the sign at the explicit coordinates selected with `/signprobe begin`.

## Alpha.3 Linux short-text probe

Start with a normal, unwaxed sign that has no filtered text or text object. The
first probe deliberately accepts only messages and owner XUIDs of at most 22
UTF-8 bytes; the message limit includes the three `|` line separators.

```text
/signprobe status
/signprobe begin 47 22 68
/signprobe capture
/signprobe text back test|||
/signprobe capture
/signprobe text front test|||
/signprobe capture
/signprobe path
```

Before either text command, `status` must show adapter
`bds-1.26.33.1-experimental-linux-plain-text`, with `exact_build_match`,
`exact_binary_hash_match`, `read_text`, `write_text`, `front_and_back`, and
`per_line_write` all true. A captured actor should report
`experimental_text_captured`. If any gate differs, stop and return the JSON;
the tester records that mutation was not attempted.

Glow, wax, color, filtered text, text objects, editor locking, and complete
control remain expected-unsupported in alpha.3.

## Suggested run

1. Place the four sign variants in a disposable test area.
2. Stand in the target dimension and run `/signprobe begin <x> <y> <z>` for the
   sign under test.
3. Run `/signprobe status` and `/signprobe capture`.
4. Exercise text, glow, wax, color, editor, and remove operations. Four text
   lines are separated with `|`.
5. Record observed results with
   `/signprobe record <probe> <true|false> <evidence>`.
6. Set the world seed and SHA-256 fields with `/signprobe meta` after creating
   the log and world-backup evidence.
7. Run `/signprobe finish`, then `/signprobe path`. Return that JSON report,
   the referenced server log, and the matching world backup.

`/signprobe finish` sets `passed` only when every required probe has non-empty
passing evidence and all four required SHA-256 values are valid. Failed or
incomplete reports remain useful diagnostic evidence but cannot activate a
production manifest.
