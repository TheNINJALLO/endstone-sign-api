#include "bedrock/entity/components/actor_owner_component.h"
#include "bedrock/entity/components/player_component.h"
#include "bedrock/world/actor/player/player.h"
#include "endstone/core/level/dimension.h"

#include <cstddef>
#include <stdexcept>

#if defined(_WIN32)
#include <Windows.h>
#define ENDSTONE_SIGN_LOCAL
#elif defined(__linux__)
#include <link.h>
#define ENDSTONE_SIGN_LOCAL __attribute__((visibility("hidden")))
#else
#error "The exact Sign adapter supports only Windows and Linux"
#endif

// WeakEntityRef<Player>::tryUnwrap ultimately needs this small lookup. Keeping
// the exact lookup local prevents the linker from importing actor.cpp, whose
// many unrelated actor helpers transitively import the item registry.
ENDSTONE_SIGN_LOCAL Actor *
Actor::tryGetFromEntity(const EntityContext &entity, const bool include_removed) {
  auto *component = entity.tryGetComponent<ActorOwnerComponent>();
  if (!component)
    return nullptr;

  auto &actor = component->getActor();
  return !actor.removed_ || include_removed ? &actor : nullptr;
}

// EndstonePlayer::getHandle() instantiates this one private helper. Supplying
// the matching v0.11.6 implementation here keeps the linker from importing
// Endstone's entire player.cpp archive member, whose unrelated inventory and
// equipment methods depend on runtime-only packet/item factories.
ENDSTONE_SIGN_LOCAL Player *
Player::tryGetFromEntity(EntityContext &entity, const bool include_removed) {
  if (!entity.hasComponent<PlayerComponent>())
    return nullptr;
  return static_cast<Player *>(
      Actor::tryGetFromEntity(entity, include_removed));
}

namespace endstone::runtime {

// Private Bedrock wrappers express executable-relative symbols through this
// helper. The plugin must resolve the host executable at runtime rather than
// importing Endstone's non-exported implementation into a separate DLL/SO.
ENDSTONE_SIGN_LOCAL void *get_executable_base() {
#if defined(_WIN32)
  static void *base = [] {
    auto *module = GetModuleHandleW(nullptr);
    if (!module)
      throw std::runtime_error("Unable to locate the Bedrock server executable");
    return static_cast<void *>(module);
  }();
  return base;
#elif defined(__linux__)
  struct MainExecutable {
    void *base{};
    bool found{};
  };

  static void *base = [] {
    MainExecutable executable;
    dl_iterate_phdr(
        [](dl_phdr_info *info, std::size_t, void *data) {
          auto &result = *static_cast<MainExecutable *>(data);
          if (!info->dlpi_name || info->dlpi_name[0] == '\0') {
            result.base = reinterpret_cast<void *>(info->dlpi_addr);
            result.found = true;
            return 1;
          }
          return 0;
        },
        &executable);
    if (!executable.found)
      throw std::runtime_error("Unable to locate the Bedrock server executable");
    return executable.base;
  }();
  return base;
#endif
}

} // namespace endstone::runtime

namespace endstone::core {

// This is the exact v0.11.6 implementation. It is not exported by the host's
// public plugin ABI, so an exact private-header adapter provides it locally.
ENDSTONE_SIGN_LOCAL ::Dimension &EndstoneDimension::getHandle() const {
  if (!dimension_.isSet())
    throw std::runtime_error(
        "Trying to access a dimension that is no longer valid.");
  return *dimension_.unwrap();
}

} // namespace endstone::core

#undef ENDSTONE_SIGN_LOCAL
