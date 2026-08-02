# C++ plugin integration examples

Endstone Sign API v0.2.1-alpha.2 publishes the typed service `endstone:sign:v2` with
service ABI `2`. Add the release `include/` directory to your plugin build,
link/load after the Endstone plugin named `sign_api`, and load
`endstone_sign::LiveSignService` during `onEnable()`.

[`plugin_integration_examples.cpp`](plugin_integration_examples.cpp) contains
three reusable patterns:

- a chest-shop display that renders item, unit price, and current stock;
- a two-way Discord bridge: API change events enqueue outbound posts, while an
  inbound Discord callback schedules a sign write on the server thread;
- a scheduler-driven moving-message sign with revision-safe frame updates.

Every consumer must require `capabilities().supportedRelease()` and then check
each optional capability it uses. Capture immediately before writing, pass the
captured revision, run calls on Endstone's primary thread, and handle every
non-`applied` result.

Discord HTTP/WebSocket work must stay off the server thread. The event listener
should only enqueue a small immutable payload; schedule inbound Discord changes
back onto the primary thread before calling the API. Direct player sign edits
may be mirrored when `player_edit_events` is true and a listener is registered.

The v0.2.1-alpha.2 candidate advertises text objects, color, glow, wax, editor
locking/opening, player edit interception, and restart-persistence coverage for
the one full-system Linux qualification. Production consumers must still check
each capability and wait for the accepted stable release before relying on it.
