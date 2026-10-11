"""Locally installed plugin skills are discovered generically; breakage stays visible."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "validate-profile-skills.py"
spec = importlib.util.spec_from_file_location("optional_plugin_skills_validator", SCRIPT)
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)

CALL = 'skill_view(name="sample-local:sample-action")'


class LocalPluginSkillsTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.root = self.base / "hermes"
        self.root.mkdir()
        patch = mock.patch.object(validator, "HERMES_ROOT", self.root)
        patch.start()
        self.addCleanup(patch.stop)
        self.profile = self.root / "profiles/assistant/skills/assistant-pipeline"
        self.profile.mkdir(parents=True)
        self.reference = self.profile / "SKILL.md"
        self.reference.write_text(f"Load {CALL} first.\n", encoding="utf-8")
        self.group = self.root / "plugins/sample-group"
        self.group.mkdir(parents=True)
        self.installed = self.base / "installed/sample-local"

    def build(self, *, name="sample-local", skills=("sample-action",), table=("sample-action",)):
        self.installed.mkdir(parents=True)
        (self.installed / "plugin.yaml").write_text(f"name: {name}\n", encoding="utf-8")
        entries = ", ".join(f'"{skill}": {{"assistant"}}' for skill in table)
        (self.installed / "__init__.py").write_text(f"SKILLS = {{{entries}}}\n", encoding="utf-8")
        for skill in skills:
            directory = self.installed / "skills" / skill
            directory.mkdir(parents=True)
            (directory / "SKILL.md").write_text(
                f"---\nname: {skill}\ndescription: Sample.\n---\n# Sample\n", encoding="utf-8"
            )

    def link(self, parent=None):
        (parent or self.group / "sample-local").symlink_to(self.installed)

    def validate(self):
        errors = []
        count = validator.validate_plugin_skills(errors)
        return count, errors

    def test_checkout_without_local_plugins_has_no_requirement(self):
        self.reference.write_text("No qualified calls here.\n", encoding="utf-8")
        self.assertEqual(self.validate(), (0, []))

    def test_linked_plugin_in_a_group_slot_is_discovered(self):
        self.build()
        self.link()
        self.assertEqual(self.validate(), (1, []))

    def test_linked_plugin_in_a_root_slot_is_discovered(self):
        self.build()
        self.link(self.root / "plugins/sample-local")
        self.assertEqual(self.validate(), (1, []))

    def test_missing_namespace_is_an_error(self):
        count, errors = self.validate()
        self.assertEqual(count, 0)
        self.assertEqual(len(errors), 1)
        self.assertIn("does not exist", errors[0])

    def test_typo_in_the_call_is_an_error(self):
        self.build()
        self.link()
        self.reference.write_text('skill_view(name="sample-local:sample-actoin")\n', encoding="utf-8")
        _, errors = self.validate()
        self.assertEqual(len(errors), 1)
        self.assertIn("does not exist", errors[0])

    def test_manifest_name_mismatch_is_an_error(self):
        self.build(name="other-name")
        self.link()
        _, errors = self.validate()
        self.assertTrue(any("plugin.yaml name must be" in error for error in errors))

    def test_linked_plugin_with_skills_but_no_manifest_is_an_error(self):
        self.build()
        (self.installed / "plugin.yaml").unlink()
        self.link()
        self.reference.write_text("No qualified calls here.\n", encoding="utf-8")
        _, errors = self.validate()
        self.assertTrue(any("without a plugin.yaml" in error for error in errors))

    def test_skills_table_mismatch_is_an_error(self):
        self.build(table=())
        self.link()
        _, errors = self.validate()
        self.assertTrue(any("SKILLS table" in error for error in errors))

    def test_table_entry_without_a_skill_file_is_an_error(self):
        self.build(table=("sample-action", "sample-extra"))
        self.link()
        _, errors = self.validate()
        self.assertTrue(any("is missing" in error for error in errors))

    def test_dangling_installed_link_is_an_error(self):
        self.reference.write_text("No qualified calls here.\n", encoding="utf-8")
        self.link()
        _, errors = self.validate()
        self.assertEqual(len(errors), 1)
        self.assertIn("dangling plugin directory link", errors[0])

    def test_symlink_inside_a_skill_is_an_error(self):
        self.build()
        (self.installed / "skills/sample-action/extra").symlink_to(self.installed / "plugin.yaml")
        self.link()
        _, errors = self.validate()
        self.assertTrue(any("must not contain symlinks" in error for error in errors))

    def test_discovery_does_not_descend_past_one_group_level(self):
        self.build()
        deep = self.group / "nested"
        deep.mkdir()
        self.link(deep / "sample-local")
        self.reference.write_text("No qualified calls here.\n", encoding="utf-8")
        self.assertEqual(self.validate(), (0, []))


if __name__ == "__main__":
    unittest.main()
