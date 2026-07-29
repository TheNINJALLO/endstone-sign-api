#pragma once

#include "endstone_sign/adapter.h"

#include <memory>

namespace endstone {
class Server;
}

namespace endstone_sign {

// First-test adapter for the public Endstone block surface plus the pinned
// Endstone v0.11.6 native Player::openSign and VanillaBlockActor interfaces.
//
// This factory is deliberately separate from makeBds2630SignAdapter: using it
// does not imply that the SignBlockActor NBT ABI, executable symbol manifest,
// or disposable-world stage probe has been verified.
std::shared_ptr<ISignAdapter> makeExperimentalBds2630SignAdapter(endstone::Server &server);

} // namespace endstone_sign
