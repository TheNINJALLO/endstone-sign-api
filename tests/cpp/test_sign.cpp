#include "endstone_sign/sign_api.h"
#include "endstone_sign/in_memory_adapter.h"
#include "endstone_sign/native_binary_identity.h"
#include "endstone_sign/native_manifest.h"
#include "endstone_sign/placement.h"
#include "endstone_sign/schema.h"
#include "endstone_sign/service.h"

#include <array>
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <iostream>
#include <memory>
#include <string>
#include <string_view>
#include <vector>

using namespace endstone_sign;

namespace {

struct CanonicalMaterialIdentifiers {
    SignMaterial material;
    std::string_view standing;
    std::string_view wall;
    std::string_view hanging;
};

constexpr std::array CanonicalIdentifiers{
    CanonicalMaterialIdentifiers{SignMaterial::Oak, "minecraft:standing_sign",
                                 "minecraft:wall_sign",
                                 "minecraft:oak_hanging_sign"},
    CanonicalMaterialIdentifiers{SignMaterial::Spruce,
                                 "minecraft:spruce_standing_sign",
                                 "minecraft:spruce_wall_sign",
                                 "minecraft:spruce_hanging_sign"},
    CanonicalMaterialIdentifiers{SignMaterial::Birch,
                                 "minecraft:birch_standing_sign",
                                 "minecraft:birch_wall_sign",
                                 "minecraft:birch_hanging_sign"},
    CanonicalMaterialIdentifiers{SignMaterial::Jungle,
                                 "minecraft:jungle_standing_sign",
                                 "minecraft:jungle_wall_sign",
                                 "minecraft:jungle_hanging_sign"},
    CanonicalMaterialIdentifiers{SignMaterial::Acacia,
                                 "minecraft:acacia_standing_sign",
                                 "minecraft:acacia_wall_sign",
                                 "minecraft:acacia_hanging_sign"},
    CanonicalMaterialIdentifiers{SignMaterial::DarkOak,
                                 "minecraft:darkoak_standing_sign",
                                 "minecraft:darkoak_wall_sign",
                                 "minecraft:dark_oak_hanging_sign"},
    CanonicalMaterialIdentifiers{SignMaterial::Mangrove,
                                 "minecraft:mangrove_standing_sign",
                                 "minecraft:mangrove_wall_sign",
                                 "minecraft:mangrove_hanging_sign"},
    CanonicalMaterialIdentifiers{SignMaterial::Cherry,
                                 "minecraft:cherry_standing_sign",
                                 "minecraft:cherry_wall_sign",
                                 "minecraft:cherry_hanging_sign"},
    CanonicalMaterialIdentifiers{SignMaterial::Bamboo,
                                 "minecraft:bamboo_standing_sign",
                                 "minecraft:bamboo_wall_sign",
                                 "minecraft:bamboo_hanging_sign"},
    CanonicalMaterialIdentifiers{SignMaterial::Crimson,
                                 "minecraft:crimson_standing_sign",
                                 "minecraft:crimson_wall_sign",
                                 "minecraft:crimson_hanging_sign"},
    CanonicalMaterialIdentifiers{SignMaterial::Warped,
                                 "minecraft:warped_standing_sign",
                                 "minecraft:warped_wall_sign",
                                 "minecraft:warped_hanging_sign"},
    CanonicalMaterialIdentifiers{SignMaterial::PaleOak,
                                 "minecraft:pale_oak_standing_sign",
                                 "minecraft:pale_oak_wall_sign",
                                 "minecraft:pale_oak_hanging_sign"},
};

SignText text(std::string first, std::string second = {}) {
    SignText value;
    value.lines[0] = std::move(first);
    value.lines[1] = std::move(second);
    return value;
}

SignPlaceRequest standing(
    SignLocation location,
    SignMaterial material,
    std::string first_line) {
    SignPlaceRequest request;
    request.location = std::move(location);
    request.block_identifier = signBlockIdentifier(material, SignKind::Standing);
    request.states = makeStandingSignStates(6);
    request.front = text(std::move(first_line));
    request.back = text("back");
    return request;
}

} // namespace

int main() {
    assert(signActorStatusName(SignActorStatus::Captured) == "captured");
    assert(signActorStatusName(SignActorStatus::ExperimentalTextCaptured) ==
           "experimental_text_captured");
    assert(signActorStatusName(SignActorStatus::ChunkUnavailable) ==
           "chunk_unavailable");
    assert(signActorStatusName(SignActorStatus::NoBlockActor) == "no_block_actor");
    assert(signActorStatusName(SignActorStatus::WrongBlockActorType) ==
           "wrong_block_actor_type");
    assert(signActorStatusName(SignActorStatus::SymbolGateClosed) ==
           "symbol_gate_closed");
    assert(signActorStatusName(SignActorStatus::AdapterError) == "adapter_error");

    const std::string abc = "abc";
    const auto abc_bytes = std::span<const std::byte>(
        reinterpret_cast<const std::byte *>(abc.data()), abc.size());
    assert(sha256Bytes(abc_bytes) ==
           "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");

    const auto ceiling_states = makeCeilingHangingSignStates(8, true);
    const auto wall_hanging_states = makeWallHangingSignStates(CardinalDirection::East);
    assert(allSignMaterials().size() == CanonicalIdentifiers.size());
    for (std::size_t index = 0; index < CanonicalIdentifiers.size(); ++index) {
        const auto &expected = CanonicalIdentifiers[index];
        assert(allSignMaterials()[index] == expected.material);
        const auto standing_identifier =
            signBlockIdentifier(expected.material, SignKind::Standing);
        const auto wall_identifier =
            signBlockIdentifier(expected.material, SignKind::Wall);
        const auto ceiling_identifier =
            signBlockIdentifier(expected.material, SignKind::CeilingHanging);
        const auto wall_hanging_identifier =
            signBlockIdentifier(expected.material, SignKind::WallHanging);
        assert(standing_identifier == expected.standing);
        assert(wall_identifier == expected.wall);
        assert(ceiling_identifier == expected.hanging);
        assert(wall_hanging_identifier == expected.hanging);
        assert(materialFromSignIdentifier(standing_identifier) == expected.material);
        assert(materialFromSignIdentifier(wall_identifier) == expected.material);
        assert(materialFromSignIdentifier(ceiling_identifier) == expected.material);
        assert(classifySignIdentifier(standing_identifier) == SignKind::Standing);
        assert(classifySignIdentifier(wall_identifier) == SignKind::Wall);
        assert(classifySign(ceiling_identifier, ceiling_states) ==
               SignKind::CeilingHanging);
        assert(classifySign(wall_hanging_identifier, wall_hanging_states) ==
               SignKind::WallHanging);
        assert(isVanillaSignIdentifier(standing_identifier));
        assert(isVanillaSignIdentifier(wall_identifier));
        assert(isVanillaSignIdentifier(ceiling_identifier));
    }

    // Regression: passing this non-existent descriptor to the exact BDS
    // createBlockData boundary stopped the hosted alpha.5 matrix.
    assert(signBlockIdentifier(SignMaterial::DarkOak, SignKind::Standing) ==
           "minecraft:darkoak_standing_sign");
    assert(signBlockIdentifier(SignMaterial::DarkOak, SignKind::Wall) ==
           "minecraft:darkoak_wall_sign");
    assert(signBlockIdentifier(SignMaterial::DarkOak, SignKind::CeilingHanging) ==
           "minecraft:dark_oak_hanging_sign");
    for (const auto invalid : {
             "minecraft:dark_oak_standing_sign",
             "minecraft:dark_oak_wall_sign",
             "minecraft:darkoak_hanging_sign",
             "minecraft:oak_standing_sign",
             "minecraft:oak_wall_sign"}) {
        assert(!materialFromSignIdentifier(invalid));
        assert(classifySignIdentifier(invalid) == SignKind::Unknown);
        assert(!isVanillaSignIdentifier(invalid));
    }
    assert(validateSignBlockStates(
        "minecraft:dark_oak_standing_sign", makeStandingSignStates(0)));
    assert(!materialFromSignIdentifier("minecraft:oak_sign"));

    assert(!validateSignBlockStates("minecraft:oak_hanging_sign", ceiling_states));
    auto invalid_states = makeStandingSignStates(16);
    assert(validateSignBlockStates("minecraft:standing_sign", invalid_states));

    std::string split_error;
    const auto lines = splitSignMessage("one\ntwo\nthree\nfour", &split_error);
    assert(lines && (*lines)[3] == "four");
    assert(!splitSignMessage("1\n2\n3\n4\n5", &split_error));
    assert(!isValidUtf8(std::string("\xC0\xAF", 2)));

    auto adapter = std::make_shared<InMemorySignAdapter>();
    SignService service(adapter);
    const auto caps = service.capabilities();
    assert(caps.capture && caps.place && caps.atomic_transactions);
    assert(!caps.completeControl());

    const SignLocation origin{"overworld", 10, 64, 20};
    auto place_request = standing(origin, SignMaterial::PaleOak, "Kingdom");
    place_request.front.owner_xuid = "123456789";
    place_request.remote_profanity_filter_enabled = true;
    place_request.local_profanity_filter_enabled = true;
    assert(service.place(place_request).ok());

    auto captured = service.capture(origin);
    assert(captured);
    assert(captured->kind == SignKind::Standing);
    assert(captured->front.lines[0] == "Kingdom");
    assert(captured->remote_profanity_filter_enabled);
    assert(captured->local_profanity_filter_enabled);
    const auto initial_revision = captured->revision;

    SignPatch patch;
    patch.location = origin;
    patch.expected_revision = initial_revision;
    SignTextPatch front_patch;
    front_patch.line_updates[1] = "Market";
    front_patch.argb = 0xFFAA22CCu;
    front_patch.glowing = true;
    front_patch.hide_glow_outline = true;
    front_patch.persist_formatting = false;
    front_patch.text_object = R"({"rawtext":[{"text":"Kingdom Market"}]})";
    front_patch.message_is_text_object = true;
    patch.front = front_patch;
    SignTextPatch back_patch;
    back_patch.message = "Line A\nLine B";
    back_patch.filtered_message = "Line A\nLine B";
    patch.back = back_patch;
    patch.waxed = true;
    const auto patched = service.apply(patch);
    assert(patched.ok());

    captured = service.capture(origin);
    assert(captured);
    assert(captured->front.lines[1] == "Market");
    assert(captured->front.argb == 0xFFAA22CCu);
    assert(captured->front.glowing);
    assert(captured->front.hide_glow_outline);
    assert(!captured->front.persist_formatting);
    assert(captured->front.message_is_text_object);
    assert(captured->back.lines[1] == "Line B");
    assert(captured->waxed);

    SignPatch stale = patch;
    stale.expected_revision = initial_revision;
    assert(service.apply(stale).status == SignApplyStatus::Conflict);

    std::vector<SignEventKind> observed_events;
    const auto listener_id = service.eventBus()->addListener(
        [&](SignEvent &event) {
            observed_events.push_back(event.kind);
            if (event.kind == SignEventKind::BeforeChange && event.after &&
                event.after->front.lines[0] == "blocked") {
                event.cancelled = true;
                event.cancellation_reason = "test policy";
            }
        });

    SignPatch blocked;
    blocked.location = origin;
    SignTextPatch blocked_text;
    blocked_text.line_updates[0] = "blocked";
    blocked.front = blocked_text;
    const auto blocked_result = service.apply(blocked);
    assert(blocked_result.status == SignApplyStatus::Cancelled);
    assert(service.capture(origin)->front.lines[0] == "Kingdom");

    SignPatch lock;
    lock.location = origin;
    lock.locked_for_editing_by = 42;
    lock.locked_for_editing_xuid = "123456789";
    assert(service.apply(lock).ok());
    assert(observed_events.back() == SignEventKind::AfterLock);

    SignPatch unlock;
    unlock.location = origin;
    unlock.locked_for_editing_by = -1;
    unlock.locked_for_editing_xuid = "";
    assert(service.apply(unlock).ok());
    assert(observed_events.back() == SignEventKind::AfterUnlock);
    assert(service.eventBus()->removeListener(listener_id));

    const SignLocation clone_location{"overworld", 11, 64, 20};
    SignCloneRequest clone;
    clone.source = origin;
    clone.destination = clone_location;
    assert(service.cloneSign(clone).ok());
    assert(service.capture(clone_location));
    assert(service.capture(clone_location)->front.lines[1] == "Market");
    assert(service.capture(clone_location)->remote_profanity_filter_enabled);
    assert(service.capture(clone_location)->local_profanity_filter_enabled);

    const SignLocation moved_location{"overworld", 12, 64, 20};
    SignMoveRequest move;
    move.source = clone_location;
    move.destination = moved_location;
    assert(service.moveSign(move).ok());
    assert(!service.capture(clone_location));
    assert(service.capture(moved_location));

    const SignLocation initially_locked_location{"overworld", 13, 64, 20};
    auto initially_locked = standing(initially_locked_location, SignMaterial::Oak, "locked");
    initially_locked.locked_for_editing_by = 77;
    initially_locked.locked_for_editing_xuid = "987654321";
    initially_locked.remote_profanity_filter_enabled = true;
    assert(service.place(initially_locked).ok());
    const auto initially_locked_snapshot = service.capture(initially_locked_location);
    assert(initially_locked_snapshot);
    assert(initially_locked_snapshot->locked_for_editing_by == 77);
    assert(initially_locked_snapshot->locked_for_editing_xuid == "987654321");
    assert(initially_locked_snapshot->remote_profanity_filter_enabled);

    const SignLocation second{"overworld", 20, 64, 20};
    assert(service.place(standing(second, SignMaterial::Spruce, "second")).ok());
    const auto origin_before_transaction = service.capture(origin);
    const auto second_before_transaction = service.capture(second);
    assert(origin_before_transaction && second_before_transaction);

    SignPatch transaction_patch_one;
    transaction_patch_one.location = origin;
    transaction_patch_one.expected_revision = origin_before_transaction->revision;
    SignTextPatch tx_text;
    tx_text.line_updates[0] = "transaction";
    transaction_patch_one.front = tx_text;

    SignPatch transaction_patch_two;
    transaction_patch_two.location = second;
    transaction_patch_two.expected_revision = second_before_transaction->revision + 1;
    transaction_patch_two.waxed = true;

    SignTransaction rejected_transaction;
    rejected_transaction.operations.emplace_back(transaction_patch_one);
    rejected_transaction.operations.emplace_back(transaction_patch_two);
    const auto rejected = service.transact(rejected_transaction);
    assert(!rejected.ok());
    assert(service.capture(origin)->front.lines[0] == origin_before_transaction->front.lines[0]);

    SignTransaction direct_rollback;
    direct_rollback.operations.emplace_back(transaction_patch_one);
    direct_rollback.operations.emplace_back(transaction_patch_two);
    const auto direct_result = adapter->transact(direct_rollback);
    assert(!direct_result.ok());
    assert(direct_result.rolled_back);
    assert(service.capture(origin)->front.lines[0] == origin_before_transaction->front.lines[0]);

    transaction_patch_two.expected_revision = second_before_transaction->revision;
    SignTransaction accepted_transaction;
    accepted_transaction.audit_reason = "test atomic edit";
    accepted_transaction.operations.emplace_back(transaction_patch_one);
    accepted_transaction.operations.emplace_back(transaction_patch_two);
    const auto accepted = service.transact(accepted_transaction);
    assert(accepted.ok());
    assert(service.capture(origin)->front.lines[0] == "transaction");
    assert(service.capture(second)->waxed);

    const auto projection = makeNbtProjection(*service.capture(origin));
    SignSnapshot restored;
    applyNbtProjection(restored, projection);
    assert(restored.front.lines[0] == "transaction");
    assert(restored.front.argb == 0xFFAA22CCu);

    NativeSignManifest incomplete_manifest;
    assert(!incomplete_manifest.complete());
    assert(!incomplete_manifest.missingRequirements().empty());
    assert(requiredNativeSignSymbols().size() >= 15);

    SignRemoveRequest remove;
    remove.location = moved_location;
    remove.expected_revision = service.capture(moved_location)->revision;
    assert(service.remove(remove).ok());
    assert(!service.capture(moved_location));

    std::cout << "sign API portable tests passed\n";
    return 0;
}
