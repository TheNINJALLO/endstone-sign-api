from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
ADAPTER_SOURCE = ROOT / "src" / "experimental_bds_26_30_adapter.cpp"


class ExperimentalAdapterRegistryGuardTests(unittest.TestCase):
    def test_create_block_data_is_centralized_behind_non_throwing_lookup(self) -> None:
        source = ADAPTER_SOURCE.read_text(encoding="utf-8")
        start = source.index("RegisteredBlockData createRegisteredBlockData(")
        end = source.index("\n}\n\nSignStates fromEndstoneStates", start)
        helper = source[start:end]

        registry_lookup = helper.index("server._getRegistry(registry_name)")
        type_lookup = helper.index("registry->get(endstone::BlockTypeId(identifier))")
        descriptor_creation = helper.index("server.createBlockData(")

        self.assertLess(registry_lookup, type_lookup)
        self.assertLess(type_lookup, descriptor_creation)
        self.assertEqual(source.count("server.createBlockData("), 1)
        self.assertNotIn("server_.createBlockData(", source)
        self.assertEqual(source.count("createRegisteredBlockData("), 3)

    def test_missing_registry_entry_is_returned_as_an_invalid_patch(self) -> None:
        source = ADAPTER_SOURCE.read_text(encoding="utf-8")

        self.assertEqual(source.count("if (!replacement.type_registered)"), 2)
        self.assertEqual(
            source.count("block type is absent from the Endstone block registry"),
            2,
        )


if __name__ == "__main__":
    unittest.main()
