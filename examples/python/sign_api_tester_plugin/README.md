# Endstone Sign API Tester

This CPython 3.14 Endstone wheel exercises the exact native
`endstone:sign:v2` service and writes the JSON report required by the Sign API
activation gate. It never uses the in-memory reference adapter.

Install the native plugin and the matching tester wheel from the same exact
package ZIP. Use only a backed-up disposable world: the commands can edit or
remove the sign at the explicit coordinates selected with `/signprobe begin`.

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
