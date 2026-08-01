from __future__ import annotations

import unittest
from dataclasses import replace

from endstone_sign import (
    CardinalDirection,
    InMemorySignAdapter,
    InMemorySignService,
    NativeSignManifest,
    REQUIRED_NATIVE_SIGN_SYMBOLS,
    SignActorContext,
    SignApplyStatus,
    SignCloneRequest,
    SignCapabilities,
    SignEventKind,
    SignKind,
    SignLocation,
    SignMaterial,
    SignMoveRequest,
    SignMutationOrigin,
    SignNbtProjection,
    SignOpenEditorRequest,
    SignPatch,
    SignPlaceRequest,
    SignRemoveRequest,
    SignReplacePolicy,
    SignSide,
    SignSnapshot,
    SignText,
    SignTextPatch,
    SignTransaction,
    SignValidationLimits,
    apply_nbt_projection,
    classify_identifier,
    classify_sign,
    flatten_lines,
    is_vanilla_sign_identifier,
    make_ceiling_hanging_sign_states,
    make_nbt_projection,
    make_standing_sign_states,
    make_wall_hanging_sign_states,
    make_wall_sign_states,
    material_from_sign_identifier,
    sign_block_identifier,
    split_message,
    validate_sign_block_states,
    validate_sign_text,
)


def text(first: str, second: str = "") -> SignText:
    return SignText(lines=(first, second, "", ""))


def standing(location: SignLocation, material: SignMaterial, first: str) -> SignPlaceRequest:
    return SignPlaceRequest(
        location=location,
        block_identifier=sign_block_identifier(material, SignKind.STANDING),
        states=make_standing_sign_states(6),
        front=text(first),
        back=text("back"),
    )


class SignApiTests(unittest.TestCase):
    def test_supported_release_is_a_strict_subset_of_complete_control(self) -> None:
        stable = SignCapabilities(
            capture=True,
            place=True,
            remove=True,
            replace=True,
            clone=True,
            move=True,
            atomic_transactions=True,
            read_text=True,
            write_text=True,
            front_and_back=True,
            per_line_write=True,
            filtered_text=True,
            owner_xuid=True,
            hide_glow_outline=True,
            persist_formatting=True,
            api_edit_events=True,
            client_updates=True,
            exact_build_match=True,
            exact_binary_hash_match=True,
            symbols_validated=True,
        )
        self.assertTrue(stable.supported_release)
        self.assertFalse(stable.complete_control)
        self.assertFalse(replace(stable, write_text=False).supported_release)

    def test_material_and_identifier_mapping(self) -> None:
        identifiers = {
            SignMaterial.OAK: (
                "minecraft:standing_sign",
                "minecraft:wall_sign",
                "minecraft:oak_hanging_sign",
            ),
            SignMaterial.SPRUCE: (
                "minecraft:spruce_standing_sign",
                "minecraft:spruce_wall_sign",
                "minecraft:spruce_hanging_sign",
            ),
            SignMaterial.BIRCH: (
                "minecraft:birch_standing_sign",
                "minecraft:birch_wall_sign",
                "minecraft:birch_hanging_sign",
            ),
            SignMaterial.JUNGLE: (
                "minecraft:jungle_standing_sign",
                "minecraft:jungle_wall_sign",
                "minecraft:jungle_hanging_sign",
            ),
            SignMaterial.ACACIA: (
                "minecraft:acacia_standing_sign",
                "minecraft:acacia_wall_sign",
                "minecraft:acacia_hanging_sign",
            ),
            SignMaterial.DARK_OAK: (
                "minecraft:darkoak_standing_sign",
                "minecraft:darkoak_wall_sign",
                "minecraft:dark_oak_hanging_sign",
            ),
            SignMaterial.MANGROVE: (
                "minecraft:mangrove_standing_sign",
                "minecraft:mangrove_wall_sign",
                "minecraft:mangrove_hanging_sign",
            ),
            SignMaterial.CHERRY: (
                "minecraft:cherry_standing_sign",
                "minecraft:cherry_wall_sign",
                "minecraft:cherry_hanging_sign",
            ),
            SignMaterial.BAMBOO: (
                "minecraft:bamboo_standing_sign",
                "minecraft:bamboo_wall_sign",
                "minecraft:bamboo_hanging_sign",
            ),
            SignMaterial.CRIMSON: (
                "minecraft:crimson_standing_sign",
                "minecraft:crimson_wall_sign",
                "minecraft:crimson_hanging_sign",
            ),
            SignMaterial.WARPED: (
                "minecraft:warped_standing_sign",
                "minecraft:warped_wall_sign",
                "minecraft:warped_hanging_sign",
            ),
            SignMaterial.PALE_OAK: (
                "minecraft:pale_oak_standing_sign",
                "minecraft:pale_oak_wall_sign",
                "minecraft:pale_oak_hanging_sign",
            ),
        }
        self.assertEqual(set(identifiers), set(SignMaterial))
        ceiling_states = make_ceiling_hanging_sign_states(0, False)
        wall_hanging_states = make_wall_hanging_sign_states(CardinalDirection.NORTH)
        for material, (standing_id, wall_id, hanging_id) in identifiers.items():
            with self.subTest(material=material):
                expected_by_kind = {
                    SignKind.STANDING: standing_id,
                    SignKind.WALL: wall_id,
                    SignKind.CEILING_HANGING: hanging_id,
                    SignKind.WALL_HANGING: hanging_id,
                }
                for kind, expected in expected_by_kind.items():
                    self.assertEqual(sign_block_identifier(material, kind), expected)
                self.assertEqual(material_from_sign_identifier(standing_id), material)
                self.assertEqual(material_from_sign_identifier(wall_id), material)
                self.assertEqual(material_from_sign_identifier(hanging_id), material)
                self.assertEqual(classify_identifier(standing_id), SignKind.STANDING)
                self.assertEqual(classify_identifier(wall_id), SignKind.WALL)
                self.assertEqual(
                    classify_sign(hanging_id, ceiling_states),
                    SignKind.CEILING_HANGING,
                )
                self.assertEqual(
                    classify_sign(hanging_id, wall_hanging_states),
                    SignKind.WALL_HANGING,
                )
                self.assertTrue(is_vanilla_sign_identifier(standing_id))
                self.assertTrue(is_vanilla_sign_identifier(wall_id))
                self.assertTrue(is_vanilla_sign_identifier(hanging_id))

        # Regression: this generated descriptor reached the exact BDS
        # createBlockData boundary and stopped the hosted alpha.5 matrix.
        for invalid in (
            "minecraft:dark_oak_standing_sign",
            "minecraft:dark_oak_wall_sign",
            "minecraft:darkoak_hanging_sign",
            "minecraft:oak_standing_sign",
            "minecraft:oak_wall_sign",
            "minecraft:oak_sign",
        ):
            with self.subTest(invalid=invalid):
                self.assertIsNone(material_from_sign_identifier(invalid))
                self.assertEqual(classify_identifier(invalid), SignKind.UNKNOWN)
                self.assertFalse(is_vanilla_sign_identifier(invalid))
        self.assertIsNotNone(
            validate_sign_block_states(
                "minecraft:dark_oak_standing_sign",
                make_standing_sign_states(0),
            )
        )

    def test_block_state_helpers_and_validation(self) -> None:
        standing_states = make_standing_sign_states(15)
        self.assertIsNone(validate_sign_block_states("minecraft:standing_sign", standing_states))
        self.assertIn("between 0 and 15", validate_sign_block_states(
            "minecraft:standing_sign", make_standing_sign_states(16)
        ) or "")

        wall_states = make_wall_sign_states(CardinalDirection.EAST)
        self.assertIsNone(validate_sign_block_states("minecraft:spruce_wall_sign", wall_states))

        ceiling = make_ceiling_hanging_sign_states(8, True)
        self.assertEqual(classify_sign("minecraft:oak_hanging_sign", ceiling), SignKind.CEILING_HANGING)
        self.assertIsNone(validate_sign_block_states("minecraft:oak_hanging_sign", ceiling))

        wall_hanging = make_wall_hanging_sign_states(CardinalDirection.WEST)
        self.assertEqual(classify_sign("minecraft:oak_hanging_sign", wall_hanging), SignKind.WALL_HANGING)
        self.assertIsNone(validate_sign_block_states("minecraft:oak_hanging_sign", wall_hanging))

    def test_message_helpers_and_validation(self) -> None:
        lines = split_message("one\ntwo")
        self.assertEqual(lines, ("one", "two", "", ""))
        self.assertEqual(flatten_lines(lines), "one\ntwo\n\n")
        with self.assertRaises(ValueError):
            split_message("1\n2\n3\n4\n5")
        with self.assertRaises(ValueError):
            split_message("bad\rtext")
        self.assertIsNotNone(validate_sign_text(
            SignText(lines=("x" * 5, "", "", "")),
            SignValidationLimits(max_line_bytes=4),
        ))

    def test_place_capture_and_full_front_back_patch(self) -> None:
        location = SignLocation("overworld", 10, 64, 20)
        service = InMemorySignService()
        request = standing(location, SignMaterial.PALE_OAK, "Kingdom")
        request = replace(
            request,
            front=SignText(lines=("Kingdom", "", "", ""), owner_xuid="123456789"),
            remote_profanity_filter_enabled=True,
            local_profanity_filter_enabled=True,
        )
        placed = service.place(request)
        self.assertTrue(placed.ok)
        before = service.capture(location)
        self.assertIsNotNone(before)
        assert before is not None

        result = service.apply(SignPatch(
            location=location,
            expected_revision=before.revision,
            front=SignTextPatch(
                line_updates={1: "Market"},
                argb=0xFFAA22CC,
                glowing=True,
                hide_glow_outline=True,
                persist_formatting=False,
                text_object='{"rawtext":[{"text":"Kingdom Market"}]}',
                message_is_text_object=True,
            ),
            back=SignTextPatch(
                message="Line A\nLine B",
                filtered_message="Line A\nLine B",
            ),
            waxed=True,
            remote_profanity_filter_enabled=True,
            local_profanity_filter_enabled=True,
        ))
        self.assertTrue(result.ok)
        after = service.capture(location)
        assert after is not None
        self.assertEqual(after.front.lines[1], "Market")
        self.assertEqual(after.front.argb, 0xFFAA22CC)
        self.assertTrue(after.front.glowing)
        self.assertTrue(after.front.hide_glow_outline)
        self.assertFalse(after.front.persist_formatting)
        self.assertTrue(after.front.message_is_text_object)
        self.assertEqual(after.back.lines[1], "Line B")
        self.assertTrue(after.waxed)
        self.assertTrue(after.remote_profanity_filter_enabled)
        self.assertTrue(after.local_profanity_filter_enabled)

    def test_revision_conflict_and_force(self) -> None:
        location = SignLocation("overworld", 1, 64, 2)
        service = InMemorySignService()
        self.assertTrue(service.place(standing(location, SignMaterial.OAK, "Initial")).ok)
        before = service.capture(location)
        assert before is not None
        self.assertTrue(service.apply(SignPatch(
            location=location,
            expected_revision=before.revision,
            front=SignTextPatch(line_updates={0: "Changed"}),
        )).ok)
        stale = service.apply(SignPatch(
            location=location,
            expected_revision=before.revision,
            waxed=True,
        ))
        self.assertEqual(stale.status, SignApplyStatus.CONFLICT)
        forced = service.apply(SignPatch(
            location=location,
            expected_revision=before.revision,
            waxed=True,
        ), force=True)
        self.assertTrue(forced.ok)

    def test_cancellable_events_and_actor_context(self) -> None:
        location = SignLocation("overworld", 2, 64, 2)
        service = InMemorySignService()
        observed: list[tuple[SignEventKind, str, SignMutationOrigin]] = []

        def listener(event) -> None:
            observed.append((event.kind, event.actor.plugin_name, event.actor.origin))
            if event.kind is SignEventKind.BEFORE_CHANGE and event.after and event.after.front.lines[0] == "blocked":
                event.cancelled = True
                event.cancellation_reason = "policy denied"

        listener_id = service.event_bus.add_listener(listener)
        self.assertTrue(service.place(
            standing(location, SignMaterial.BIRCH, "allowed"),
            actor=SignActorContext(plugin_name="test-plugin"),
        ).ok)
        denied = service.apply(SignPatch(
            location=location,
            front=SignTextPatch(line_updates={0: "blocked"}),
        ), actor=SignActorContext(plugin_name="test-plugin"))
        self.assertEqual(denied.status, SignApplyStatus.CANCELLED)
        self.assertEqual(service.capture(location).front.lines[0], "allowed")  # type: ignore[union-attr]
        self.assertTrue(service.event_bus.remove_listener(listener_id))
        self.assertIn((SignEventKind.BEFORE_PLACE, "test-plugin", SignMutationOrigin.API), observed)

    def test_lock_and_unlock_events(self) -> None:
        location = SignLocation("overworld", 3, 64, 3)
        service = InMemorySignService()
        service.place(standing(location, SignMaterial.SPRUCE, "lockable"))
        events: list[SignEventKind] = []
        service.event_bus.add_listener(lambda event: events.append(event.kind))

        self.assertTrue(service.apply(SignPatch(
            location=location,
            locked_for_editing_by=42,
            locked_for_editing_xuid="123",
        )).ok)
        self.assertEqual(events[-1], SignEventKind.AFTER_LOCK)
        self.assertTrue(service.apply(SignPatch(
            location=location,
            locked_for_editing_by=-1,
            locked_for_editing_xuid="",
        )).ok)
        self.assertEqual(events[-1], SignEventKind.AFTER_UNLOCK)

    def test_clone_and_move(self) -> None:
        source = SignLocation("overworld", 4, 64, 4)
        clone = SignLocation("overworld", 5, 64, 4)
        moved = SignLocation("overworld", 6, 64, 4)
        service = InMemorySignService()
        source_request = replace(
            standing(source, SignMaterial.CHERRY, "source"),
            remote_profanity_filter_enabled=True,
            local_profanity_filter_enabled=True,
            locked_for_editing_by=51,
            locked_for_editing_xuid="xuid-51",
        )
        self.assertTrue(service.place(source_request).ok)
        self.assertTrue(service.clone_sign(SignCloneRequest(source, clone, copy_editor_lock=True)).ok)
        cloned = service.capture(clone)
        assert cloned is not None
        self.assertEqual(cloned.front.lines[0], "source")
        self.assertTrue(cloned.remote_profanity_filter_enabled)
        self.assertTrue(cloned.local_profanity_filter_enabled)
        self.assertEqual(cloned.locked_for_editing_by, 51)
        self.assertEqual(cloned.locked_for_editing_xuid, "xuid-51")
        self.assertTrue(service.move_sign(SignMoveRequest(clone, moved)).ok)
        self.assertIsNone(service.capture(clone))
        self.assertEqual(service.capture(moved).front.lines[0], "source")  # type: ignore[union-attr]

    def test_replace_policy(self) -> None:
        location = SignLocation("overworld", 7, 64, 7)
        service = InMemorySignService()
        self.assertTrue(service.place(standing(location, SignMaterial.OAK, "first")).ok)
        blocked = service.place(standing(location, SignMaterial.OAK, "second"))
        self.assertEqual(blocked.status, SignApplyStatus.BLOCK_OCCUPIED)
        replacement = standing(location, SignMaterial.OAK, "second")
        replacement = SignPlaceRequest(
            location=replacement.location,
            block_identifier=replacement.block_identifier,
            states=replacement.states,
            front=replacement.front,
            back=replacement.back,
            replace_policy=SignReplacePolicy.FORCE,
        )
        self.assertTrue(service.place(replacement).ok)
        self.assertEqual(service.capture(location).front.lines[0], "second")  # type: ignore[union-attr]

    def test_atomic_transaction_preflight_and_adapter_rollback(self) -> None:
        first = SignLocation("overworld", 8, 64, 8)
        second = SignLocation("overworld", 9, 64, 8)
        adapter = InMemorySignAdapter()
        service = InMemorySignService()
        # Use the service's adapter for service-level preflight.
        service.place(standing(first, SignMaterial.OAK, "first"))
        service.place(standing(second, SignMaterial.OAK, "second"))
        first_before = service.capture(first)
        second_before = service.capture(second)
        assert first_before is not None and second_before is not None
        tx = SignTransaction((
            SignPatch(first, expected_revision=first_before.revision, front=SignTextPatch(line_updates={0: "tx"})),
            SignPatch(second, expected_revision=second_before.revision + 1, waxed=True),
        ))
        rejected = service.transact(tx)
        self.assertFalse(rejected.ok)
        self.assertEqual(service.capture(first).front.lines[0], "first")  # type: ignore[union-attr]

        # Direct adapter transaction verifies true rollback after the first candidate mutation.
        adapter.upsert(first_before)
        adapter.upsert(second_before)
        direct = adapter.transact(tx)
        self.assertFalse(direct.ok)
        self.assertTrue(direct.rolled_back)
        self.assertEqual(adapter.capture(first).front.lines[0], "first")  # type: ignore[union-attr]

        accepted = service.transact(SignTransaction((
            SignPatch(first, expected_revision=first_before.revision, front=SignTextPatch(line_updates={0: "tx"})),
            SignPatch(second, expected_revision=second_before.revision, waxed=True),
        ), audit_reason="atomic test"))
        self.assertTrue(accepted.ok)
        self.assertEqual(service.capture(first).front.lines[0], "tx")  # type: ignore[union-attr]
        self.assertTrue(service.capture(second).waxed)  # type: ignore[union-attr]

    def test_transaction_event_cancellation_mutates_nothing(self) -> None:
        first = SignLocation("overworld", 10, 64, 10)
        second = SignLocation("overworld", 11, 64, 10)
        service = InMemorySignService()
        service.place(standing(first, SignMaterial.OAK, "first"))
        service.place(standing(second, SignMaterial.OAK, "second"))
        before_first = service.capture(first)
        before_second = service.capture(second)
        assert before_first and before_second

        def cancel_second(event) -> None:
            if event.kind is SignEventKind.BEFORE_CHANGE and event.location == second:
                event.cancelled = True
                event.cancellation_reason = "second denied"

        service.event_bus.add_listener(cancel_second)
        result = service.transact(SignTransaction((
            SignPatch(first, expected_revision=before_first.revision, waxed=True),
            SignPatch(second, expected_revision=before_second.revision, waxed=True),
        )))
        self.assertEqual(result.status, SignApplyStatus.CANCELLED)
        self.assertFalse(service.capture(first).waxed)  # type: ignore[union-attr]
        self.assertFalse(service.capture(second).waxed)  # type: ignore[union-attr]

    def test_nbt_projection_round_trip(self) -> None:
        snapshot = SignSnapshot(
            SignLocation("overworld", 12, 64, 12),
            "minecraft:standing_sign",
            states=make_standing_sign_states(1),
            front=SignText(
                lines=("one", "two", "", ""),
                filtered_message="filtered",
                text_object='{"text":"one"}',
                message_is_text_object=True,
                argb=0xFFAA22CC,
                glowing=True,
                hide_glow_outline=True,
                persist_formatting=False,
                owner_xuid="456",
            ),
            back=text("back"),
            waxed=True,
            locked_for_editing_by=99,
        )
        projection = make_nbt_projection(snapshot)
        self.assertIsInstance(projection, SignNbtProjection)
        restored = apply_nbt_projection(snapshot, projection)
        self.assertEqual(restored.front.lines[1], "two")
        self.assertEqual(restored.front.argb, 0xFFAA22CC)
        self.assertTrue(restored.front.glowing)
        self.assertTrue(restored.waxed)
        self.assertEqual(restored.locked_for_editing_by, 99)

    def test_open_editor_guards_and_reference_limit(self) -> None:
        location = SignLocation("overworld", 13, 64, 13)
        service = InMemorySignService()
        request = standing(location, SignMaterial.OAK, "edit")
        request = SignPlaceRequest(
            location=request.location,
            block_identifier=request.block_identifier,
            states=request.states,
            front=request.front,
            back=request.back,
            waxed=True,
        )
        service.place(request)
        denied = service.open_editor(object(), SignOpenEditorRequest(location, SignSide.FRONT))
        self.assertEqual(denied.status, SignApplyStatus.PERMISSION_DENIED)
        unsupported = service.open_editor(
            object(),
            SignOpenEditorRequest(location, SignSide.BACK, bypass_wax=True),
        )
        self.assertEqual(unsupported.status, SignApplyStatus.UNSUPPORTED)
        self.assertFalse(service.capabilities.complete_control)

    def test_remove(self) -> None:
        location = SignLocation("overworld", 14, 64, 14)
        service = InMemorySignService()
        service.place(standing(location, SignMaterial.WARPED, "remove"))
        before = service.capture(location)
        assert before is not None
        result = service.remove(SignRemoveRequest(location, expected_revision=before.revision, drop_item=True))
        self.assertTrue(result.ok)
        self.assertIsNone(service.capture(location))

    def test_native_manifest_is_fail_closed(self) -> None:
        manifest = NativeSignManifest()
        self.assertFalse(manifest.complete)
        self.assertGreaterEqual(len(REQUIRED_NATIVE_SIGN_SYMBOLS), 15)
        missing = manifest.missing_requirements()
        self.assertIn("binary.executable_sha256", missing)
        self.assertIn("request_open_sign_editor", missing)


if __name__ == "__main__":
    unittest.main()
