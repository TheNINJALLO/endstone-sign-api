<p align="center">
  <img src="docs/assets/banner.svg" width="100%" alt="Endstone Sign API — revision-safe, two-sided sign control for Bedrock server plugins">
</p>

<p align="center">
  <a href="https://github.com/TheNINJALLO/endstone-sign-api/actions/workflows/ci.yml"><img alt="Build" src="https://img.shields.io/github/actions/workflow/status/TheNINJALLO/endstone-sign-api/ci.yml?branch=main&amp;style=for-the-badge&amp;logo=githubactions&amp;logoColor=white&amp;label=Build"></a>
  <a href="https://github.com/TheNINJALLO/endstone-sign-api/releases/latest"><img alt="Latest release" src="https://img.shields.io/github/v/release/TheNINJALLO/endstone-sign-api?display_name=tag&amp;style=for-the-badge&amp;label=Release"></a>
  <a href="LICENSE"><img alt="Apache 2.0 license" src="https://img.shields.io/badge/license-Apache--2.0-52b7a8?style=for-the-badge"></a>
</p>

<p align="center">
  <img alt="C++20" src="https://img.shields.io/badge/C%2B%2B-20-00599C?style=flat-square&amp;logo=cplusplus">
  <img alt="Endstone 0.11.6" src="https://img.shields.io/badge/Endstone-0.11.6-52b7a8?style=flat-square">
  <img alt="BDS 1.26.33.1" src="https://img.shields.io/badge/BDS-1.26.33.1-8b7dff?style=flat-square">
  <img alt="Linux x86-64" src="https://img.shields.io/badge/Linux-x86--64-FCC624?style=flat-square&amp;logo=linux&amp;logoColor=black">
  <img alt="Service ABI v2" src="https://img.shields.io/badge/service%20ABI-v2-63b8ff?style=flat-square">
</p>

<p align="center">
  <strong>One production service for every Bedrock sign.</strong><br>
  Capture, place, edit, mirror, move, lock, and persist standing, wall, and
  hanging signs through a revision-safe native API.
</p>

<p align="center">
  <a href="#install">Install</a> •
  <a href="#use-the-service">Use the service</a> •
  <a href="#production-integration-patterns">Integration patterns</a> •
  <a href="docs/API.md">API reference</a> •
  <a href="examples/cpp/plugin_integration_examples.cpp">Complete examples</a>
</p>

## Stable release

Endstone Sign API `v0.2.1` publishes the production `endstone:sign:v2` service
for Linux x86-64, exact BDS package `1.26.33.1` (runtime `26.33`), and Endstone
`0.11.6`.

The API covers the full native sign surface:

| Area | Capabilities |
|---|---|
| Lifecycle | Capture, place, replace, remove, clone, and move |
| Sign forms | 12 material families across standing, wall, ceiling-hanging, and wall-hanging signs |
| Text | Four lines per side, individual-line changes, filtered text, and Bedrock `rawtext` objects |
| Presentation | ARGB color, glow, hidden glow outline, formatting persistence, and wax state |
| Editing | Native editor lock/unlock, front/back editor requests, and player-edit interception |
| Events | Cancellable before-events and observational after-events for API and player changes |
| Safety | Exact executable identity, optimistic revisions, readback, client updates, atomic transactions, and rollback |
| Persistence | Server-save and restart-safe sign state |

The native plugin registers only the typed API service. The API plugin
registers no player or console commands and does not ship the former qualification command wheel or
its auxiliary diagnostic service. Consumer plugins define their own commands,
permissions, storage, Discord integration, and gameplay behavior.

## Documentation

| Guide | Purpose |
|---|---|
| [API reference](docs/API.md) | Public types, operations, results, capabilities, and events |
| [Architecture](docs/ARCHITECTURE.md) | Service boundary, exact native adapter, revisions, and transactions |
| [Placement](docs/PLACEMENT.md) | Canonical sign identifiers and typed block states |
| [Exact production build](docs/BUILD_EXACT.md) | Reproducible Linux plugin and SDK packaging |
| [Native boundary audit](docs/SYMBOL_AUDIT.md) | Exact executable and native representation safeguards |
| [C++ integrations](examples/cpp/plugin_integration_examples.cpp) | Chest shop, Discord bridge, and moving-message patterns |

## Install

Download the stable release and verify the public checksum manifest:

```bash
mkdir -p sign-api-0.2.1
gh release download v0.2.1 \
  --repo TheNINJALLO/endstone-sign-api \
  --dir sign-api-0.2.1
cd sign-api-0.2.1
sha256sum --check SHA256SUMS.txt
```

Published files:

| Deliverable | Filename |
|---|---|
| Native Endstone plugin | `endstone_sign_bds_1_26_33.so` |
| Headers, reference modules, docs, and examples | `endstone-sign-api-v0.2.1-bds-1.26.33-linux-x64.zip` |
| Package checksum file | `endstone-sign-api-v0.2.1-bds-1.26.33-linux-x64.sha256` |
| Combined public checksums | `SHA256SUMS.txt` |

Stop the server, install the native plugin, and remove old qualification wheels
from the active plugin directory:

```bash
SERVER_ROOT=/srv/endstone
mkdir -p "$SERVER_ROOT/plugins-disabled"
find "$SERVER_ROOT/plugins" -maxdepth 1 -type f \
  -name 'endstone_sign_tester-*.whl' \
  -exec mv -t "$SERVER_ROOT/plugins-disabled" -- {} +
install -D -m 0644 endstone_sign_bds_1_26_33.so \
  "$SERVER_ROOT/plugins/endstone_sign_bds_1_26_33.so"
cd "$SERVER_ROOT"
endstone
```

The plugin refuses to register on a different platform, BDS executable, or
Endstone version. A successful startup includes:

```text
Sign API 0.2.1 registered complete service endstone:sign:v2 using bds-1.26.33.1-linux-release
```

You can verify that line without installing any command plugin:

```bash
grep -F "registered complete service endstone:sign:v2" logs/latest.log
```

## Use the service

Add the SDK `include/` directory to the consuming plugin and load the service
during `onEnable()`:

```cpp
#include "endstone_sign/live_service.h"

#include <endstone/plugin/service_manager.h>
#include <endstone/server.h>

#include <memory>
#include <string>

std::shared_ptr<endstone_sign::LiveSignService>
loadSignApi(endstone::Server &server) {
    auto signs = server.getServiceManager().load<endstone_sign::LiveSignService>(
        std::string(endstone_sign::SignServiceName));
    if (!signs || !signs->capabilities().completeControl()) {
        return {};
    }
    return signs;
}
```

Capture immediately before a mutation and pass the returned revision:

```cpp
using namespace endstone_sign;

bool setShopText(
    const std::shared_ptr<LiveSignService> &signs,
    const SignLocation &location,
    SignLines lines) {
    const auto current = signs->capture(location);
    if (!current) return false;

    SignPatch patch;
    patch.location = location;
    patch.expected_revision = current->revision;
    patch.front.emplace();
    patch.front->lines = std::move(lines);
    patch.send_client_update = true;
    patch.persist = true;

    const auto result = signs->apply(patch);
    return result.status == SignApplyStatus::Applied;
}
```

Every consumer should:

- load `endstone:sign:v2` only after the Sign API plugin is enabled;
- require `completeControl()` or explicitly check every capability it uses;
- call native API methods on Endstone’s primary server thread;
- capture a fresh revision before each write;
- handle `Conflict`, `Cancelled`, `Unsupported`, `Invalid`, and `NotASign` results;
- keep network, database, and Discord work off the server thread;
- use `send_client_update=true` and `persist=true` for visible durable changes.

## Production integration patterns

### Sign-backed chest shop

Read the container inventory and shop configuration in your plugin, then render
the current item, unit price, and stock:

```cpp
setShopText(signs, sign_location, {
    "[CHEST SHOP]",
    item_name,
    "$" + std::to_string(price_each) + " each",
    "Stock: " + std::to_string(stock),
});
```

Update the sign after inventory, purchase, sale, or price-change events. Keep a
location-to-shop mapping in the consumer plugin; the API intentionally does not
own economy data.

### Sign changes sent to Discord

Register a Sign API event listener. For `AfterChange` and `AfterPlace`, copy the
small immutable event payload into a thread-safe queue and return immediately.
A separate Discord worker may then post the sign location, text, and source
plugin without blocking the server thread.

### Discord posts displayed in game

Receive the Discord message off-thread, sanitize and split it into four bounded
lines, then schedule the Sign API write back onto Endstone’s primary thread.
Never call the native service directly from the Discord HTTP/WebSocket thread.

### Moving announcements

Use an Endstone scheduler task. Each frame captures the current sign first and
writes with that revision, so player or plugin edits become explicit conflicts
instead of being silently overwritten.

See [plugin_integration_examples.cpp](examples/cpp/plugin_integration_examples.cpp)
for complete reusable implementations of all four patterns.

## Compatibility

| Component | Supported value |
|---|---|
| API release | `0.2.1` |
| Service | `endstone:sign:v2` |
| Service ABI | `2` |
| Operating system | Linux x86-64 |
| BDS package | `1.26.33.1` |
| Runtime BDS | `26.33` |
| Endstone | `0.11.6` |
| Python reference package | CPython 3.11+ |

Windows native DLLs and Windows server wheels are not part of this release.
The native adapter fails closed if the running executable does not match the
pinned Linux identity.

## Build and verify from source

Portable API and regression suites:

```bash
python -m pip install -e .
python -m compileall -q python
python -m unittest discover -s tests/python -p 'test_*.py' -v

cmake -S . -B build \
  -DENDSTONE_SIGN_BUILD_TESTS=ON \
  -DENDSTONE_SIGN_BUILD_SHARED=ON \
  -DENDSTONE_SIGN_BUILD_PLUGIN=OFF
cmake --build build --parallel
ctest --test-dir build --output-on-failure
```

Exact production package on supported Linux with CPython 3.11 or newer:

```bash
python scripts/build_exact.py \
  --bds 1.26.33 \
  --platform linux-x64 \
  --parallel 2

python scripts/verify_release_assets.py \
  --slug endstone-sign-api \
  --version 0.2.1 \
  --bds 1.26.33 \
  --platform linux-x64 \
  --release-dir dist/release
```

## Safety model

- Exact BDS package, executable SHA-256, and byte-size checks are mandatory.
- Native function, vtable, and representation fingerprints are checked before
  the advanced adapter reports readiness.
- Mutations require the primary server thread and use optimistic revisions.
- Native writes are read back before success is returned.
- Transactions preflight the full operation set and roll back in reverse order.
- Events identify their source plugin and support cancellation before mutation.
- A normal source build remains closed; only the exact stable packaging path
  enables the accepted production contract.

## License

Apache License 2.0. BDS executables, debug databases, private generated headers,
and decompiler output are never redistributed.
