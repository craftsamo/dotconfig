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

    def test_no_tool_request_middleware_rewrites_creates(self) -> None:
        """Placement is skills.create_dir's job; a category rewrite would nest learned/learned/."""
        context = FakeContext()

        self.plugin.register(context)

        self.assertNotIn("tool_request", context.middleware)
        self.assertFalse(hasattr(self.plugin, "_route_skill_create"))

    def test_learned_category_name_is_the_create_dir_leaf(self) -> None:
        self.assertEqual(self.plugin.LEARNED_CATEGORY, "learned")


if __name__ == "__main__":
    unittest.main()
