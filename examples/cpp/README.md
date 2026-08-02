# C++ plugin integration examples

Endstone Sign API `v0.2.1` publishes `endstone:sign:v2` with service ABI `2`.
Add the SDK `include/` directory to your plugin, load
`endstone_sign::LiveSignService` through Endstone’s `ServiceManager` during
`onEnable()`, and disable your integration cleanly if the service or required
capabilities are unavailable.

[`plugin_integration_examples.cpp`](plugin_integration_examples.cpp) contains
production-oriented patterns for:

- a chest-shop sign that displays the item, price, and live container stock;
- successful sign API changes queued to a Discord worker;
- inbound Discord posts scheduled onto the server thread and displayed on a
  configured sign;
- scheduler-driven moving announcements with revision-safe frame changes.

Every integration should capture immediately before writing, pass the captured
revision, call the live API only on Endstone’s primary thread, request client
updates and persistence where needed, and inspect every operation result.

Discord HTTP/WebSocket work must stay off the server thread. Event listeners
should copy a small immutable payload into a queue and return. Schedule inbound
Discord changes back onto the primary thread before calling the service.

The stable API plugin registers no commands. Consumer plugins own their command
names, permissions, validation, configuration, and gameplay policy.
