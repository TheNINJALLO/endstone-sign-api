#include "endstone_sign/in_memory_adapter.h"
#include "endstone_sign/placement.h"
#include "endstone_sign/service.h"

#include <cassert>
#include <memory>

using namespace endstone_sign;

int main() {
    auto adapter = std::make_shared<InMemorySignAdapter>();
    SignService service(adapter);

    const SignLocation location{"overworld", 100, 70, 100};
    SignPlaceRequest place;
    place.location = location;
    place.block_identifier = signBlockIdentifier(SignMaterial::Cherry, SignKind::WallHanging);
    place.states = makeWallHangingSignStates(CardinalDirection::North);
    place.front.lines = {"The Kingdom", "Market", "", ""};
    place.back.lines = {"Staff Only", "", "", ""};
    assert(service.place(place).ok());

    const auto snapshot = service.capture(location);
    assert(snapshot);

    SignPatch patch;
    patch.location = location;
    patch.expected_revision = snapshot->revision;
    patch.front.emplace();
    patch.front->line_updates[2] = "Open 24/7";
    patch.front->argb = 0xFFFFAA00u;
    patch.front->glowing = true;
    patch.waxed = true;
    assert(service.apply(patch).ok());
}
