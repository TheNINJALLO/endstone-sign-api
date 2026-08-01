from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
ADAPTER_SOURCE = ROOT / "src" / "experimental_bds_26_30_adapter.cpp"
RUNTIME_BRIDGE_SOURCE = ROOT / "src" / "sign_native_runtime_bridge.cpp"
LIVE_BINDINGS_SOURCE = ROOT / "src" / "live_python_bindings.cpp"
CMAKE_SOURCE = ROOT / "CMakeLists.txt"


class ExperimentalAdapterRegistryGuardTests(unittest.TestCase):
    def test_direct_descriptor_creation_is_guarded_by_cache_only_enumeration(self) -> None:
        source = ADAPTER_SOURCE.read_text(encoding="utf-8")
        start = source.index("RegisteredBlockData createRegisteredBlockData(")
        end = source.index("\n}\n\nSignStates fromEndstoneStates", start)
        helper = source[start:end]

        registry_lookup = helper.index("server._getRegistry(registry_name)")
        type_enumeration = helper.index("registry->forEach(")
        descriptor_creation = helper.index("server.createBlockData(")

        self.assertLess(registry_lookup, type_enumeration)
        self.assertLess(type_enumeration, descriptor_creation)
        self.assertIn("type.getId() != expected_id", helper)
        self.assertNotIn("registry->get(", helper)
        self.assertIn("Calling get with an absent ID would", helper)
        self.assertEqual(source.count("server.createBlockData("), 1)
        self.assertNotIn("server_.createBlockData(", source)
        self.assertEqual(source.count("createRegisteredBlockData("), 5)

    def test_indirect_air_descriptor_path_is_exact_and_tester_preflighted(self) -> None:
        source = ADAPTER_SOURCE.read_text(encoding="utf-8")
        tester = (
            ROOT
            / "examples"
            / "python"
            / "sign_api_tester_plugin"
            / "src"
            / "endstone_sign_tester"
            / "plugin.py"
        ).read_text(encoding="utf-8")

        self.assertIn('setType("minecraft:air", false)', source)
        self.assertIn('(\"cleanup\", \"minecraft:air\")', tester)

    def test_missing_registry_entry_is_returned_as_an_invalid_patch(self) -> None:
        source = ADAPTER_SOURCE.read_text(encoding="utf-8")

        self.assertEqual(source.count("if (!replacement.type_registered)"), 4)
        self.assertEqual(
            source.count("block type is absent from the Endstone block registry"),
            3,
        )

    def test_transaction_restore_keeps_native_actor_access_mutable(self) -> None:
        source = ADAPTER_SOURCE.read_text(encoding="utf-8")
        start = source.index("auto restore_snapshot =")
        end = source.index("\n\n        auto rollback =", start)
        restore = source[start:end]

        self.assertIn("auto native =", restore)
        self.assertNotIn("const auto native =", restore)
        self.assertIn("signalActorChanged(*native.access);", restore)

    def test_actor_lookup_fallback_yields_to_linked_endstone_definition(self) -> None:
        source = RUNTIME_BRIDGE_SOURCE.read_text(encoding="utf-8")

        self.assertIn('__attribute__((visibility("hidden"), weak))', source)
        self.assertIn(
            "ENDSTONE_SIGN_LOCAL_FALLBACK Actor *\nActor::tryGetFromEntity",
            source,
        )
        self.assertEqual(source.count("ENDSTONE_SIGN_LOCAL_FALLBACK Actor *"), 1)
        self.assertIn(
            "ENDSTONE_SIGN_LOCAL_FALLBACK ActorUniqueID "
            "Actor::getOrCreateUniqueID() const",
            source,
        )
        self.assertIn("level_->getNewUniqueID()", source)

    def test_live_bridge_uses_derived_pep440_release_version(self) -> None:
        cmake = CMAKE_SOURCE.read_text(encoding="utf-8")
        bindings = LIVE_BINDINGS_SOURCE.read_text(encoding="utf-8")

        self.assertIn(
            'set(ENDSTONE_SIGN_PYTHON_VERSION "${CMAKE_MATCH_1}a${CMAKE_MATCH_2}")',
            cmake,
        )
        self.assertIn(
            'ENDSTONE_SIGN_PYTHON_VERSION="${ENDSTONE_SIGN_PYTHON_VERSION}"',
            cmake,
        )
        self.assertNotIn(
            'ENDSTONE_SIGN_VERSION="${ENDSTONE_SIGN_RELEASE_VERSION}")',
            cmake[cmake.index("pybind11_add_module(_endstone_sign_live") :],
        )
        self.assertIn(
            'module.attr("__version__") = ENDSTONE_SIGN_PYTHON_VERSION;',
            bindings,
        )

    def test_supported_linux_mode_exposes_full_native_candidate(self) -> None:
        cmake = CMAKE_SOURCE.read_text(encoding="utf-8")
        adapter = ADAPTER_SOURCE.read_text(encoding="utf-8")
        plugin = (ROOT / "src" / "plugin.cpp").read_text(encoding="utf-8")

        self.assertIn("ENDSTONE_SIGN_SUPPORTED_NATIVE_RELEASE", cmake)
        self.assertIn(
            "if(ENDSTONE_SIGN_EXPERIMENTAL_NATIVE_BRIDGE OR\n"
            "       ENDSTONE_SIGN_SUPPORTED_NATIVE_RELEASE OR\n"
            "       ENDSTONE_SIGN_VERIFIED_NATIVE_BRIDGE)\n"
            "        if(ENDSTONE_SIGN_NATIVE_MANIFEST STREQUAL",
            cmake,
        )
        self.assertIn(
            "-DENDSTONE_SIGN_SUPPORTED_NATIVE_RELEASE=ON",
            (ROOT / "scripts" / "build_exact.py").read_text(encoding="utf-8"),
        )
        for field in (
            "text_objects",
            "text_color",
            "glowing",
            "waxed",
            "editor_lock",
            "open_editor",
            "restart_persistence",
        ):
            self.assertIn(f"result.{field} = complete_native_gate", adapter)
        self.assertIn(
            "result.player_edit_events = complete_native_gate && hook_installed_",
            adapter,
        )
        self.assertNotIn("v0.2.0 does not support", adapter)
        self.assertNotIn("!ENDSTONE_SIGN_SUPPORTED_NATIVE_RELEASE", adapter)
        self.assertIn("installPlayerEditHook();", adapter)
        self.assertIn("TextObjectJsonRva = 0x09DD50D0", adapter)
        self.assertIn("TextObjectJsonSha256", adapter)
        self.assertIn("Json::Value::ArrayIndex", adapter)
        self.assertIn('parsed.find("rawtext")', adapter)
        self.assertIn(
            "'{\"rawtext\":[{\"text\":\"a7\"}]}'",
            (
                ROOT
                / "examples"
                / "python"
                / "sign_api_tester_plugin"
                / "src"
                / "endstone_sign_tester"
                / "plugin.py"
            ).read_text(encoding="utf-8"),
        )
        self.assertIn("caps.supportedRelease()", plugin)


if __name__ == "__main__":
    unittest.main()
