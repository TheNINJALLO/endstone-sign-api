from __future__ import annotations

import ast
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
PLUGIN = (
    ROOT
    / "examples"
    / "python"
    / "sign_api_tester_plugin"
    / "src"
    / "endstone_sign_tester"
    / "plugin.py"
)

# Endstone v0.11.6's EndstoneCommandMap::TYPE_SYMBOLS plus the three
# special-cased types checked before that map.
SUPPORTED_BASIC_TYPES = {
    "actor",
    "block",
    "block_pos",
    "block_states",
    "bool",
    "entity",
    "entity_type",
    "float",
    "int",
    "json",
    "message",
    "player",
    "pos",
    "str",
    "string",
    "target",
    "vec3",
    "vec3f",
    "vec3i",
}

PARAMETER = re.compile(
    r"(?P<values>\([^()]*\))?"
    r"(?P<open><|\[)\s*(?P<name>[^:\]>]+)\s*:\s*"
    r"(?P<type>[A-Za-z_][A-Za-z0-9_]*)\s*(?P<close>>|\])"
)


def load_usages() -> list[str]:
    tree = ast.parse(PLUGIN.read_text(encoding="utf-8"), filename=str(PLUGIN))
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != "SignApiTesterPlugin":
            continue
        for statement in node.body:
            if not isinstance(statement, ast.Assign):
                continue
            if not any(isinstance(target, ast.Name) and target.id == "commands" for target in statement.targets):
                continue
            commands = ast.literal_eval(statement.value)
            return list(commands["signprobe"]["usages"])
    raise AssertionError("SignApiTesterPlugin.commands was not found")


class SignTesterCommandSchemaTests(unittest.TestCase):
    def test_every_custom_type_declares_a_unique_nonempty_enum(self) -> None:
        enum_types: dict[str, str] = {}
        for usage in load_usages():
            matches = list(PARAMETER.finditer(usage))
            self.assertGreater(len(matches), 0, usage)
            for match in matches:
                parameter_type = match.group("type")
                values = match.group("values")
                if values is None:
                    self.assertIn(
                        parameter_type,
                        SUPPORTED_BASIC_TYPES,
                        f"unsupported bare type {parameter_type!r} in {usage!r}",
                    )
                else:
                    entries = [entry.strip() for entry in values[1:-1].split("|")]
                    self.assertTrue(all(entries), f"empty enum value in {usage!r}")
                    self.assertNotIn(
                        parameter_type,
                        enum_types,
                        f"enum type {parameter_type!r} is reused by Endstone usages",
                    )
                    enum_types[parameter_type] = usage

                if parameter_type == "message":
                    self.assertEqual(
                        match.end(),
                        len(usage),
                        f"message must be the final argument in {usage!r}",
                    )

    def test_side_choices_are_declared_for_each_overload(self) -> None:
        usages = load_usages()
        expected = {
            "text": "(front|back)<side: SignProbeTextSide>",
            "glow": "(front|back)<side: SignProbeGlowSide>",
            "color": "(front|back)<side: SignProbeColorSide>",
            "editor": "(front|back)<side: SignProbeEditorSide>",
        }
        for action, declaration in expected.items():
            matching = [usage for usage in usages if f"({action})<action:" in usage]
            self.assertEqual(len(matching), 1, action)
            self.assertIn(declaration, matching[0])

    def test_automation_commands_use_distinct_confirmation_enums(self) -> None:
        usages = load_usages()
        run = next(usage for usage in usages if "(run)<action:" in usage)
        accept = next(usage for usage in usages if "(accept)<action:" in usage)
        cleanup = next(usage for usage in usages if "(cleanup)<action:" in usage)
        self.assertIn("(confirm)<confirmation: SignProbeRunConfirm>", run)
        self.assertIn("(confirm)<confirmation: SignProbeAcceptConfirm>", accept)
        self.assertIn("(confirm)<confirmation: SignProbeCleanupConfirm>", cleanup)
        self.assertIn("<x: int> <y: int> <z: int>", run)
        self.assertIn("<x: int> <y: int> <z: int>", accept)


if __name__ == "__main__":
    unittest.main()
