"""Assert real entry documents and dependencies, not runtime routing behavior."""

from pathlib import Path
import re
import unittest

import hermes_yaml as yaml


ROOT = Path(__file__).resolve().parents[1]
MODES = {"plan": "plan", "execute": "execute", "qa": "quality-assurance"}
CAPABILITIES = ("engineering", "creative", "writing", "research", "search", "marketing")
ENTRIES = {"chat-assistant": ("chat", None)} | {
    f"{prefix}-assistant-{capability}": (mode, capability)
    for prefix, mode in MODES.items()
    for capability in CAPABILITIES
}


class AssistantEntryRoutingTest(unittest.TestCase):
    def document(self, name):
        text = (ROOT / name / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\n"), name)
        _, frontmatter, body = text.split("---\n", 2)
        blocks = re.findall(r"<ReadBeforeWork>(.*?)</ReadBeforeWork>", body, re.S)
        self.assertEqual(len(blocks), 1, name)
        return yaml.safe_load(frontmatter), body, " ".join(blocks[0].split())

    def test_all_19_entries_have_actual_discovery_metadata(self):
        self.assertEqual({p.parent.name for p in ROOT.glob("*/SKILL.md")}, set(ENTRIES))
        prefixes = set()
        for name, (mode, capability) in ENTRIES.items():
            with self.subTest(entry=name):
                metadata, _, _ = self.document(name)
                self.assertEqual(metadata["name"], name)
                self.assertEqual(metadata["version"],
                                 "2.0.0" if name == "execute-assistant-creative" else "1.0.0")
                self.assertEqual(metadata["author"], "CraftSamo")
                self.assertEqual(metadata["license"], "MIT")
                self.assertEqual(metadata["metadata"]["hermes"]["category"], "assistant-pipeline")
                self.assertEqual(metadata["metadata"]["hermes"]["tags"],
                                 [mode] + ([capability] if capability else []))
                description = metadata["description"]
                self.assertIsInstance(description, str)
                phase = "QA" if mode == "quality-assurance" else mode.capitalize()
                expected = phase + (f" {capability}" if capability else "") + ": "
                self.assertTrue(description.startswith(expected), description)
                self.assertGreater(len(description), len(expected))
                self.assertLessEqual(len(description), 1024)
                self.assertNotIn(description[:60], prefixes)
                prefixes.add(description[:60])

    def test_dependency_calls_and_independent_missing_body_conditions(self):
        for name, (mode, _) in ENTRIES.items():
            with self.subTest(entry=name):
                _, _, contract = self.document(name)
                calls = ['skill_view(name="assistant-pipeline")']
                if mode == "chat":
                    self.assertIn("When the kernel body is missing, load:", contract)
                    self.assertNotIn("common mode procedure", contract)
                else:
                    calls.append(f'skill_view(name="assistant-pipeline", '
                                 f'file_path="references/{mode}/index.md")')
                    condition = ("Check the kernel and common mode procedure independently. "
                                 "Load each whose full body is missing:")
                    self.assertIn(condition + " ```text " + " ".join(calls) + " ```", contract)
                    self.assertNotIn("When the kernel body is missing, load:", contract)
                self.assertEqual(re.findall(r"skill_view\([^)]*\)", contract), calls)

    def test_creative_inspiration_is_visible_before_reading_the_body(self):
        metadata, _, _ = self.document("plan-assistant-creative")
        prefix = metadata["description"][:57]
        self.assertIn("media intent", prefix)
        self.assertIn("inspiration comparisons", prefix)

    def test_writing_scripts_are_visible_before_reading_the_body(self):
        metadata, _, _ = self.document("plan-assistant-writing")
        prefix = metadata["description"][:57]
        self.assertIn("scripts", prefix)
        self.assertIn("storyboards", prefix)

    def test_reuse_requires_current_full_body_not_a_summary(self):
        for name in ENTRIES:
            with self.subTest(entry=name):
                _, _, contract = self.document(name)
                self.assertIn("Reuse full-body instructions only while present in the current context, "
                              "not a past load or summary.", contract)
                self.assertIn("Re-evaluate the entry when the request, mode or domain changes, "
                              "including within a turn.", contract)
                self.assertIn("These dependencies also apply to direct entry.", contract)
                self.assertIn("Loading does not restart an approved plan or expand a grant.", contract)

    def test_missing_instructions_recover_or_stop_never_infer_a_pass(self):
        for name, (mode, _) in ENTRIES.items():
            with self.subTest(entry=name):
                _, _, contract = self.document(name)
                fallback = "`${HERMES_SKILL_DIR}/../SKILL.md`"
                if mode != "chat":
                    fallback += f" and `${{HERMES_SKILL_DIR}}/../references/{mode}/index.md`"
                self.assertIn("If a tool returns unchanged while the earlier body is unavailable, "
                              "use read_file on " + fallback + ".", contract)
                self.assertIn("Recover this entry and its own references from ${HERMES_SKILL_DIR} likewise.",
                              contract)
                self.assertIn("Follow next_offset until the whole required document is available; "
                              "do not invent alternate paths or ranges to evade dedup.", contract)
                self.assertIn("If the required instructions remain missing, stop the affected action "
                              "and report it, never infer a pass.", contract)

    def test_entries_reference_shared_bodies_without_copying_them(self):
        shared_paths = [ROOT / "SKILL.md"] + [
            ROOT / "references" / mode / "index.md" for mode in MODES.values()
        ]
        for shared_path in shared_paths:
            shared = shared_path.read_text(encoding="utf-8")
            if shared.startswith("---\n"):
                shared = shared.split("---\n", 2)[2]
            shared = " ".join(shared.split())
            self.assertTrue(shared, shared_path)
            for name in ENTRIES:
                with self.subTest(entry=name, shared=shared_path.relative_to(ROOT)):
                    for path in (ROOT / name).rglob("*.md"):
                        self.assertNotIn(shared, " ".join(path.read_text(encoding="utf-8").split()), path)

    def test_tests_do_not_introduce_discoverable_skills(self):
        self.assertEqual(list((ROOT / "tests").rglob("SKILL.md")), [])


if __name__ == "__main__":
    unittest.main()
