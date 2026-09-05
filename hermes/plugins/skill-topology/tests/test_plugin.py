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
        self.hooks: dict[str, Any] = {}

    def register_middleware(self, kind: str, callback: Any) -> None:
        self.middleware[kind] = callback

    def register_hook(self, kind: str, callback: Any) -> None:
        self.hooks[kind] = callback


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
        self.assertIs(context.hooks["pre_tool_call"], self.plugin._guard_managed_skill_writes)

    def test_learned_category_name_is_the_create_dir_leaf(self) -> None:
        self.assertEqual(self.plugin.LEARNED_CATEGORY, "learned")


class ManagedSkillWriteGuardTest(unittest.TestCase):
    """Maintainer-owned skill files are read-only at runtime."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.plugin = load_plugin()
        cls.managed = str(
            cls.plugin.MANAGED_ROOT
            / "profiles/image-creator/skills/image-creator-pipeline/create/emoji/scripts/text-emoji.sh"
        )
        cls.learned = str(cls.plugin.MANAGED_ROOT / "profiles/image-creator/skills/learned/x/SKILL.md")

    def guard(self, tool_name: str, **args: Any) -> Any:
        return self.plugin._guard_managed_skill_writes(tool_name=tool_name, args=args)

    def test_write_file_into_managed_root_is_blocked(self) -> None:
        result = self.guard("write_file", path=self.managed, content="x")
        self.assertEqual(result["action"], "block")

    def test_patch_into_managed_root_is_blocked(self) -> None:
        result = self.guard("patch", path=self.managed, old_string="a", new_string="b")
        self.assertEqual(result["action"], "block")

    def test_v4a_patch_naming_a_managed_file_is_blocked(self) -> None:
        result = self.guard("patch", mode="v4a", patch=f"*** Begin Patch\n*** Update File: {self.managed}\n")
        self.assertEqual(result["action"], "block")

    def test_learned_stays_writable(self) -> None:
        self.assertIsNone(self.guard("write_file", path=self.learned, content="x"))

    def test_deliverables_stay_writable(self) -> None:
        self.assertIsNone(self.guard("write_file", path="/tmp/emoji/items.tsv", content="x"))

    def test_symlinked_hermes_home_path_resolves_to_managed(self) -> None:
        # ~/.hermes/profiles/<p>/skills is a symlink into the repo on this
        # machine; resolve() follows it. Skip where the link does not exist.
        home = Path.home() / ".hermes/profiles/image-creator/skills/image-creator-pipeline/SKILL.md"
        if not home.exists():
            self.skipTest("no ~/.hermes symlink on this machine")
        self.assertEqual(self.guard("write_file", path=str(home), content="x")["action"], "block")

    def test_terminal_redirect_into_managed_root_is_blocked(self) -> None:
        result = self.guard("terminal", command=f"echo x > {self.managed}")
        self.assertEqual(result["action"], "block")

    def test_terminal_read_of_managed_file_is_allowed(self) -> None:
        self.assertIsNone(self.guard("terminal", command=f"bash {self.managed} items.tsv /tmp/out --platform slack"))

    def test_terminal_write_elsewhere_is_allowed(self) -> None:
        self.assertIsNone(self.guard("terminal", command="echo x > /tmp/out/finish.sh"))

    def test_skill_manage_create_is_left_to_create_dir(self) -> None:
        self.assertIsNone(self.guard("skill_manage", action="create", name="example"))


if __name__ == "__main__":
    unittest.main()
