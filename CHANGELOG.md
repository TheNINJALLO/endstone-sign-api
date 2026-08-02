# Changelog

## 0.2.1

- Promoted the exact Linux `endstone:sign:v2` ABI 2 implementation to the
  stable production release for BDS `1.26.33.1` and Endstone `0.11.6` after the
  full matrix completed 48/48 cases, 31/31 capability coverage, 931 passing
  steps, zero failures/skips, 543 mutations, and conflict-free cleanup.
- Added complete native support for Bedrock raw-text objects, ARGB color, glow,
  hidden glow outline, formatting persistence, wax, editor lock/opening,
  cancellable player edits, client updates, and restart persistence.
- Completed native structural replacement, clone, move, atomic transactions,
  cancellation, reverse-order rollback, and revision/readback protection.
- Corrected raw-text object restoration so returning to plain text restores the
  original four lines and revision chain.
- Corrected transient editor-lock restoration so Bedrock cannot clear a
  non-session lock between apply and restore and invalidate later operations.
- Enabled the accepted stable capability contract on the exact supported Linux
  build so `completeControl()` is true only when the pinned runtime, executable,
  native fingerprints, event hook, and complete capability surface are ready.
- Removed the auxiliary diagnostic service from the production plugin and
  removed command wheels, native diagnostic bridges, acceptance utilities, and
  test-oriented examples from the repository and public release assets.
- Reduced the public build payload to the native `.so`, production SDK ZIP, and
  package checksum file, with a combined `SHA256SUMS.txt` generated at release.
- Replaced development instructions with stable installation, upgrade,
  service-loading, capability, threading, revision, error-handling, chest-shop,
  Discord bridge, and moving-message documentation.

## 0.2.0

- Published the first supported Linux x86-64 `endstone:sign:v2` ABI 2 service
  for exact BDS `1.26.33.1` and Endstone `0.11.6`.
- Added capture, placement, removal, front/back and individual-line text,
  filtered text, owner data, outline/formatting flags, API edit events,
  replacement, clone, move, atomic rollback, exact runtime identity, native
  readback, client updates, and optimistic revision handling.
- Added canonical typed identifiers and block states for 12 material families
  across standing, wall, ceiling-hanging, and wall-hanging signs.
- Added the C++ chest-shop, Discord synchronization, and moving-message
  integration patterns.
- Restricted supported server artifacts to exact Linux x86-64 builds.
