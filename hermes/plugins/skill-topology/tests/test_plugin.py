from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from types import ModuleType
from typing import Any


def load_plugin() -> ModuleType:
    plugin_path = Path(__file__).resolve().parents[1] / "__init__.py"
    spec = importlib.util.spec_from_file_location("skill_topology_plugin", plugin_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load plugin from {plugin_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeContext:
    def __init__(self) -> None:
        self.middleware: dict[str, Any] = {}

    def register_middleware(self, kind: str, callback: Any) -> None:
        self.middleware[kind] = callback


class SkillTopologyPluginTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plugin = load_plugin()

    def test_create_defaults_to_learned(self) -> None:
        result = self.plugin._route_skill_create(
            tool_name="skill_manage",
            args={"action": "create", "name": "example"},
        )

        self.assertEqual(result["args"]["category"], "learned")

    def test_create_overrides_requested_category(self) -> None:
        result = self.plugin._route_skill_create(
            tool_name="skill_manage",
            args={"action": "create", "name": "example", "category": "research"},
        )

        self.assertEqual(result["args"]["category"], "learned")

    def test_other_skill_actions_are_unchanged(self) -> None:
        result = self.plugin._route_skill_create(
            tool_name="skill_manage",
            args={"action": "patch", "name": "example"},
        )

        self.assertIsNone(result)

    def test_other_tools_are_unchanged(self) -> None:
        result = self.plugin._route_skill_create(
            tool_name="write_file",
            args={"action": "create", "name": "example"},
        )

        self.assertIsNone(result)

    def test_registers_tool_request_middleware(self) -> None:
        context = FakeContext()

        self.plugin.register(context)

        self.assertIs(context.middleware["tool_request"], self.plugin._route_skill_create)


if __name__ == "__main__":
    unittest.main()
