#include "endstone_sign/experimental_bds_26_30_adapter.h"

#include "endstone_sign/placement.h"

#include <endstone/endstone.hpp>

#include "bedrock/world/actor/player/player.h"
#include "bedrock/world/level/block/actor/block_actor.h"
#include "bedrock/world/level/block/actor/vanilla_block_actor.h"
#include "bedrock/world/level/block_source.h"
#include "endstone/core/level/dimension.h"
#include "endstone/core/player.h"

#include <algorithm>
#include <cctype>
#include <cstdint>
#include <exception>
#include <memory>
#include <optional>
#include <stdexcept>
#include <string>
#include <string_view>
#include <type_traits>
#include <utility>

namespace endstone_sign {
namespace {

std::string_view canonicalBdsBuild(std::string_view build) noexcept {
    if (build.starts_with("1."))
        build.remove_prefix(2);
    if (build == "26.33.1")
        return "26.33";
    return build;
}

bool validIdentifierList(std::string_view value) noexcept {
    if (value.empty() || value.front() == '.' || value.back() == '.')
        return false;
    bool previous_dot = false;
    for (const char current : value) {
        if (current == '.') {
            if (previous_dot)
                return false;
            previous_dot = true;
            continue;
        }
        if (!std::isalnum(static_cast<unsigned char>(current)) && current != '-')
            return false;
        previous_dot = false;
    }
    return true;
}

bool expectedEndstoneVersion(std::string_view runtime) noexcept {
    constexpr std::string_view Expected = "0.11.6";
    if (runtime.starts_with('v'))
        runtime.remove_prefix(1);
    if (runtime == Expected)
        return true;
    if (!runtime.starts_with(Expected))
        return false;
    auto suffix = runtime.substr(Expected.size());
    if (suffix.starts_with('+'))
        return validIdentifierList(suffix.substr(1));
    if (!suffix.starts_with(".dev"))
        return false;
    suffix.remove_prefix(4);
    const auto metadata = suffix.find('+');
    const auto serial = suffix.substr(0, metadata);
    if (serial.empty() || !std::ranges::all_of(serial, [](const char current) {
            return current >= '0' && current <= '9';
        })) {
        return false;
    }
    return metadata == std::string_view::npos || validIdentifierList(suffix.substr(metadata + 1));
}

bool exactRuntime(const endstone::Server &server) noexcept {
    try {
        return canonicalBdsBuild(server.getMinecraftVersion()) == "26.33" &&
               expectedEndstoneVersion(server.getVersion());
    } catch (...) {
        return false;
    }
}

endstone::BlockStates toEndstoneStates(const SignStates &states) {
    endstone::BlockStates result;
    result.reserve(states.size());
    for (const auto &[key, value] : states) {
        std::visit(
            [&result, &key](const auto &entry) {
                using T = std::decay_t<decltype(entry)>;
                if constexpr (std::is_same_v<T, std::int32_t>) {
                    result.insert_or_assign(key, static_cast<int>(entry));
                } else {
                    result.insert_or_assign(key, entry);
                }
            },
            value);
    }
    return result;
}

SignStates fromEndstoneStates(const endstone::BlockStates &states) {
    SignStates result;
    for (const auto &[key, value] : states) {
        std::visit(
            [&result, &key](const auto &entry) {
                using T = std::decay_t<decltype(entry)>;
                if constexpr (std::is_same_v<T, int>) {
                    result.insert_or_assign(key, static_cast<std::int32_t>(entry));
                } else {
                    result.insert_or_assign(key, entry);
                }
            },
            value);
    }
    return result;
}

bool defaultText(const SignText &text) noexcept {
    return std::ranges::all_of(text.lines, [](const std::string &line) { return line.empty(); }) &&
           text.filtered_message.empty() && text.text_object.empty() &&
           !text.message_is_text_object && text.argb == 0xFF000000u && !text.glowing &&
           !text.hide_glow_outline && text.persist_formatting && text.owner_xuid.empty();
}

bool requiresSignNbt(const SignPlaceRequest &request) noexcept {
    return !defaultText(request.front) || !defaultText(request.back) || request.waxed ||
           request.locked_for_editing_by != -1 || request.locked_for_editing_xuid.has_value() ||
           request.remote_profanity_filter_enabled || request.local_profanity_filter_enabled;
}

bool requiresSignNbt(const SignPatch &patch) noexcept {
    return patch.front.has_value() || patch.back.has_value() || patch.waxed.has_value() ||
           patch.locked_for_editing_by.has_value() || patch.locked_for_editing_xuid.has_value() ||
           patch.remote_profanity_filter_enabled.has_value() ||
           patch.local_profanity_filter_enabled.has_value();
}

struct PublicBlockAccess {
    endstone::Dimension *dimension{};
    std::unique_ptr<endstone::Block> block;
    std::unique_ptr<endstone::BlockData> data;
};

std::optional<PublicBlockAccess> locatePublicBlock(endstone::Server &server,
                                                   const SignLocation &location) {
    auto *level = server.getLevel();
    auto *dimension = level ? level->getDimension(location.dimension) : nullptr;
    if (!dimension)
        return std::nullopt;
    auto block = dimension->getBlockAt(location.x, location.y, location.z);
    if (!block)
        return std::nullopt;
    auto data = block->getData();
    if (!data)
        return std::nullopt;
    return PublicBlockAccess{dimension, std::move(block), std::move(data)};
}

struct NativeSignActorAccess {
    BlockSource *source{};
    BlockActor *actor{};
    IVanillaMainBlockActorComponent *main{};
};

struct NativeSignActorLookup {
    std::optional<NativeSignActorAccess> access;
    SignActorStatus status{SignActorStatus::AdapterError};
};

NativeSignActorLookup locateNativeSignActor(endstone::Server &server,
                                            const SignLocation &location) {
    auto *level = server.getLevel();
    auto *dimension = level ? level->getDimension(location.dimension) : nullptr;
    if (!dimension)
        return {{}, SignActorStatus::ChunkUnavailable};

    // Endstone v0.11.6 constructs every public Dimension as this exact type.
    // This is the same pinned private boundary used by the BlockData adapter.
    auto *exact_dimension = static_cast<endstone::core::EndstoneDimension *>(dimension);
    auto &native_dimension = exact_dimension->getHandle();
    auto &source = native_dimension.getBlockSourceFromMainChunkSource();
    const ::BlockPos position(location.x, location.y, location.z);
    auto *actor = const_cast<BlockActor *>(source.getBlockEntity(position));
    if (!actor)
        return {{}, SignActorStatus::NoBlockActor};
    if (actor->getType() != BlockActorType::Sign &&
        actor->getType() != BlockActorType::HangingSign) {
        return {{}, SignActorStatus::WrongBlockActorType};
    }

    // Both allowlisted values are VanillaBlockActor implementations in the
    // pinned v0.11.6 ABI. Let C++ perform the multiple-inheritance adjustment.
    auto *vanilla = static_cast<VanillaBlockActor *>(actor);
    auto *main = static_cast<IVanillaMainBlockActorComponent *>(vanilla);
    if (main->getBlockActorType() != actor->getType()) {
        return {{}, SignActorStatus::WrongBlockActorType};
    }
    return {NativeSignActorAccess{&source, actor, main}, SignActorStatus::Captured};
}

void signalActorChanged(NativeSignActorAccess &access) {
    access.main->setChanged();
    access.main->onChanged(*access.source);
    access.source->fireBlockEntityChanged(*access.actor);
}

SignApplyResult runtimeMismatch() {
    return {
        SignApplyStatus::RuntimeMismatch,
        "experimental Sign adapter requires BDS 1.26.33.1/26.33 with Endstone "
        "0.11.6",
        0,
    };
}

SignApplyResult nbtUnsupported(const std::uint64_t revision) {
    return {
        SignApplyStatus::Unsupported,
        "sign text, wax, filtering, and editor-lock mutation require the "
        "unverified "
        "SignBlockActor NBT boundary; this experimental adapter will not guess "
        "it",
        revision,
    };
}

class ExperimentalBds2630SignAdapter final : public ISignAdapter {
  public:
    explicit ExperimentalBds2630SignAdapter(endstone::Server &server)
        : server_(server), exact_runtime_(exactRuntime(server)) {}

    [[nodiscard]] std::string_view name() const noexcept override {
        return exact_runtime_ ? "bds-1.26.33.1-experimental-structural-sign"
                              : "bds-1.26.33.1-experimental-runtime-mismatch";
    }

    [[nodiscard]] SignCapabilities capabilities() const noexcept override {
        SignCapabilities result;
        result.capture = true; // Block identifier/states and actor presence only.
        result.place = true;   // Blank signs only.
        result.remove = true;
        result.replace = true;
        result.open_editor = true; // UI dispatch; editor locking remains false.
        result.api_edit_events = true;
        result.client_updates = true;
        result.exact_build_match = exact_runtime_;

        // Deliberately false until the hosted stage probe and a verified
        // SignBlockActor save/load boundary exist.
        result.read_text = false;
        result.write_text = false;
        result.front_and_back = false;
        result.editor_lock = false;
        result.restart_persistence = false;
        result.exact_binary_hash_match = false;
        result.symbols_validated = false;
        result.stage_probe_passed = false;
        return result;
    }

    [[nodiscard]] std::optional<SignSnapshot> capture(const SignLocation &location) override {
        if (!exact_runtime_ || !server_.isPrimaryThread())
            return std::nullopt;
        try {
            auto access = locatePublicBlock(server_, location);
            if (!access || !isVanillaSignIdentifier(access->data->getType())) {
                return std::nullopt;
            }

            SignSnapshot snapshot;
            snapshot.location = location;
            snapshot.block_identifier = access->data->getType();
            snapshot.states = fromEndstoneStates(access->data->getBlockStates());
            snapshot.kind = classifySign(snapshot.block_identifier, snapshot.states);

            const auto native = locateNativeSignActor(server_, location);
            // The actor itself is verified through the pinned vtable, but its
            // text NBT is intentionally not represented as empty live data.
            snapshot.actor_status =
                native.access ? SignActorStatus::SymbolGateClosed : native.status;
            snapshot.canonical_snbt.clear();
            snapshot.revision = calculateSignRevision(snapshot);
            return snapshot;
        } catch (...) {
            return std::nullopt;
        }
    }

    SignApplyResult apply(const SignPatch &patch, const bool force) override {
        if (!exact_runtime_)
            return runtimeMismatch();
        if (!server_.isPrimaryThread()) {
            return {
                SignApplyStatus::AdapterError,
                "live sign apply must run on the primary thread",
                0,
            };
        }

        auto current = capture(patch.location);
        if (!current)
            return {SignApplyStatus::NotASign, "sign not found", 0};
        if (patch.expected_revision && !force && *patch.expected_revision != current->revision) {
            return {
                SignApplyStatus::Conflict,
                "sign revision changed",
                current->revision,
            };
        }
        if (requiresSignNbt(patch))
            return nbtUnsupported(current->revision);
        if (!patch.send_client_update) {
            return {
                SignApplyStatus::Unsupported,
                "the Endstone public block write always sends a client update",
                current->revision,
            };
        }
        if (!patch.persist) {
            return {
                SignApplyStatus::Unsupported,
                "non-persistent live sign writes are not available",
                current->revision,
            };
        }
        if (!patch.block_identifier && patch.state_updates.empty() &&
            patch.state_removals.empty()) {
            return {
                SignApplyStatus::Applied,
                "structural sign data unchanged",
                current->revision,
            };
        }

        auto identifier = patch.block_identifier.value_or(current->block_identifier);
        auto states = current->states;
        for (const auto &[key, value] : patch.state_updates) {
            states.insert_or_assign(key, value);
        }
        for (const auto &key : patch.state_removals)
            states.erase(key);
        if (const auto error = validateSignBlockStates(identifier, states)) {
            return {
                SignApplyStatus::InvalidPatch,
                *error,
                current->revision,
            };
        }

        try {
            auto access = locatePublicBlock(server_, patch.location);
            if (!access) {
                return {
                    SignApplyStatus::ChunkUnavailable,
                    "dimension, chunk, or block unavailable",
                    current->revision,
                };
            }
            auto replacement = server_.createBlockData(identifier, toEndstoneStates(states));
            if (!replacement) {
                return {
                    SignApplyStatus::InvalidPatch,
                    "Endstone rejected the requested sign block data",
                    current->revision,
                };
            }

            access->block->setData(*replacement, false);
            auto native = locateNativeSignActor(server_, patch.location);
            if (native.access)
                signalActorChanged(*native.access);

            auto updated = capture(patch.location);
            if (!updated) {
                return {
                    SignApplyStatus::AdapterError,
                    "structural sign write completed but readback did not find a sign "
                    "actor",
                    0,
                };
            }
            return {
                SignApplyStatus::Applied,
                "applied sign identifier/states through the Endstone v0.11.6 block "
                "boundary",
                updated->revision,
            };
        } catch (const std::invalid_argument &error) {
            return {
                SignApplyStatus::InvalidPatch,
                error.what(),
                current->revision,
            };
        } catch (const std::exception &error) {
            return {
                SignApplyStatus::AdapterError,
                error.what(),
                current->revision,
            };
        }
    }

    SignApplyResult place(const SignPlaceRequest &request, const bool force) override {
        if (!exact_runtime_)
            return runtimeMismatch();
        if (!server_.isPrimaryThread()) {
            return {
                SignApplyStatus::AdapterError,
                "live sign placement must run on the primary thread",
                0,
            };
        }
        if (requiresSignNbt(request))
            return nbtUnsupported(0);
        if (!request.send_client_update) {
            return {
                SignApplyStatus::Unsupported,
                "the Endstone public block write always sends a client update",
                0,
            };
        }
        if (!request.persist) {
            return {
                SignApplyStatus::Unsupported,
                "non-persistent sign placement is not available",
                0,
            };
        }
        if (const auto error = validateSignBlockStates(request.block_identifier, request.states)) {
            return {SignApplyStatus::InvalidPatch, *error, 0};
        }

        try {
            auto access = locatePublicBlock(server_, request.location);
            if (!access) {
                return {
                    SignApplyStatus::ChunkUnavailable,
                    "dimension, chunk, or block unavailable",
                    0,
                };
            }
            const auto before_sign = capture(request.location);
            const auto before_revision = before_sign ? before_sign->revision : 0;
            if (request.expected_destination_revision && !force &&
                *request.expected_destination_revision != before_revision) {
                return {
                    SignApplyStatus::Conflict,
                    "destination revision changed",
                    before_revision,
                };
            }

            const bool is_air = access->data->getType() == "minecraft:air";
            const bool replaces = force || request.replace_policy == SignReplacePolicy::Force;
            if (!is_air && !replaces) {
                const auto message =
                    request.replace_policy == SignReplacePolicy::ReplaceableOnly
                        ? "destination is not air; this adapter cannot prove that a "
                          "non-air block is replaceable"
                        : "destination block is not air";
                return {SignApplyStatus::BlockOccupied, message, before_revision};
            }

            auto replacement =
                server_.createBlockData(request.block_identifier, toEndstoneStates(request.states));
            if (!replacement) {
                return {
                    SignApplyStatus::InvalidPatch,
                    "Endstone rejected the requested sign block data",
                    before_revision,
                };
            }
            access->block->setData(*replacement, false);

            auto native = locateNativeSignActor(server_, request.location);
            if (!native.access) {
                return {
                    SignApplyStatus::AdapterError,
                    "sign block was placed but its vanilla sign actor was not "
                    "available",
                    0,
                };
            }
            signalActorChanged(*native.access);
            auto updated = capture(request.location);
            if (!updated) {
                return {
                    SignApplyStatus::AdapterError,
                    "sign block was placed but structural readback failed",
                    0,
                };
            }
            return {
                SignApplyStatus::Applied,
                "placed a blank sign through the Endstone v0.11.6 block boundary",
                updated->revision,
            };
        } catch (const std::invalid_argument &error) {
            return {SignApplyStatus::InvalidPatch, error.what(), 0};
        } catch (const std::exception &error) {
            return {SignApplyStatus::AdapterError, error.what(), 0};
        }
    }

    SignApplyResult remove(const SignRemoveRequest &request, const bool force) override {
        if (!exact_runtime_)
            return runtimeMismatch();
        if (!server_.isPrimaryThread()) {
            return {
                SignApplyStatus::AdapterError,
                "live sign removal must run on the primary thread",
                0,
            };
        }
        auto current = capture(request.location);
        if (!current)
            return {SignApplyStatus::NotASign, "sign not found", 0};
        if (request.expected_revision && !force &&
            *request.expected_revision != current->revision) {
            return {
                SignApplyStatus::Conflict,
                "sign revision changed",
                current->revision,
            };
        }
        if (request.drop_item) {
            return {
                SignApplyStatus::Unsupported,
                "verified sign-item drop semantics are not available in the "
                "experimental adapter",
                current->revision,
            };
        }
        if (!request.send_client_update) {
            return {
                SignApplyStatus::Unsupported,
                "the Endstone public block write always sends a client update",
                current->revision,
            };
        }

        try {
            auto access = locatePublicBlock(server_, request.location);
            if (!access) {
                return {
                    SignApplyStatus::ChunkUnavailable,
                    "dimension, chunk, or block unavailable",
                    current->revision,
                };
            }
            access->block->setType("minecraft:air", false);
            auto readback = locatePublicBlock(server_, request.location);
            if (!readback || readback->data->getType() != "minecraft:air") {
                return {
                    SignApplyStatus::AdapterError,
                    "sign removal did not read back as air",
                    current->revision,
                };
            }
            return {
                SignApplyStatus::Applied,
                "removed sign without an item drop",
                0,
            };
        } catch (const std::exception &error) {
            return {
                SignApplyStatus::AdapterError,
                error.what(),
                current->revision,
            };
        }
    }

    SignTransactionResult transact(const SignTransaction &transaction) override {
        if (transaction.operations.empty()) {
            return {
                SignApplyStatus::Applied,
                "empty transaction",
                {},
                false,
            };
        }
        if (transaction.operations.size() != 1) {
            return {
                SignApplyStatus::Unsupported,
                "the experimental structural adapter does not claim atomic "
                "multi-operation transactions",
                {},
                false,
            };
        }

        auto operation_result = std::visit(
            [this, &transaction](const auto &operation) {
                using T = std::decay_t<decltype(operation)>;
                if constexpr (std::is_same_v<T, SignPlaceRequest>) {
                    return place(operation, transaction.force);
                } else if constexpr (std::is_same_v<T, SignPatch>) {
                    return apply(operation, transaction.force);
                } else {
                    return remove(operation, transaction.force);
                }
            },
            transaction.operations.front());
        return {
            operation_result.status,
            operation_result.message,
            {operation_result},
            false,
        };
    }

    SignApplyResult openEditor(endstone::Player &player,
                               const SignOpenEditorRequest &request) override {
        if (!exact_runtime_)
            return runtimeMismatch();
        if (!server_.isPrimaryThread()) {
            return {
                SignApplyStatus::AdapterError,
                "opening a native sign editor must run on the primary thread",
                0,
            };
        }
        auto current = capture(request.location);
        if (!current)
            return {SignApplyStatus::NotASign, "sign not found", 0};
        if (request.expected_revision && *request.expected_revision != current->revision) {
            return {
                SignApplyStatus::Conflict,
                "sign revision changed",
                current->revision,
            };
        }
        if (request.acquire_lock) {
            return {
                SignApplyStatus::Unsupported,
                "Player::openSign is available, but the SignBlockActor editor-lock "
                "setter is not verified; retry with acquire_lock=false for the UI "
                "probe",
                current->revision,
            };
        }
        if (!request.bypass_wax) {
            return {
                SignApplyStatus::Unsupported,
                "the experimental structural capture cannot read IsWaxed; retry "
                "with bypass_wax=true only in the disposable test world",
                current->revision,
            };
        }
        if (player.getDimension().getName() != request.location.dimension) {
            return {
                SignApplyStatus::PermissionDenied,
                "player and sign must be in the same dimension",
                current->revision,
            };
        }
        const auto native_actor = locateNativeSignActor(server_, request.location);
        if (!native_actor.access) {
            return {
                SignApplyStatus::NotASign,
                "the target block has no compatible vanilla sign actor",
                current->revision,
            };
        }

        try {
            auto &native_player = static_cast<endstone::core::EndstonePlayer &>(player).getHandle();
            const ::BlockPos position(request.location.x, request.location.y, request.location.z);
            native_player.openSign(position, request.side == SignSide::Front);
            return {
                SignApplyStatus::Applied,
                "sent the pinned Player::openSign UI request without claiming an "
                "editor lock",
                current->revision,
            };
        } catch (const std::exception &error) {
            return {
                SignApplyStatus::AdapterError,
                error.what(),
                current->revision,
            };
        }
    }

  private:
    endstone::Server &server_;
    bool exact_runtime_{};
};

} // namespace

std::shared_ptr<ISignAdapter> makeExperimentalBds2630SignAdapter(endstone::Server &server) {
    return std::make_shared<ExperimentalBds2630SignAdapter>(server);
}

} // namespace endstone_sign
