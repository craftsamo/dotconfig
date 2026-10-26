"""note work routes to the skills note-access ships; Chat keeps only what is its own."""

from pathlib import Path
import unittest

import hermes_yaml as yaml

from _pair import PUBLIC_ROOT


ROOT = Path(__file__).resolve().parents[1]


def public_root() -> Path:
    return PUBLIC_ROOT


class NoteRouting(unittest.TestCase):
    def test_the_skills_exist_and_take_no_save_packages(self):
        skills = public_root() / "hermes/plugins/social/note-access/skills"
        texts = {}
        for name in ("read", "check-format", "draft"):
            text = (skills / name / "SKILL.md").read_text()
            meta = yaml.safe_load(text.split("---", 2)[1])
            self.assertEqual(meta["name"], name)
            self.assertNotIn("save package", text)
            self.assertFalse((skills / name / "references/save-package.md").exists())
            texts[name] = text
        self.assertIn("no exception", " ".join(texts["read"].split()))
        self.assertIn("`check`", texts["check-format"])
        self.assertIn("preview", texts["draft"])

    def test_chat_loads_the_skills_and_keeps_no_mechanics(self):
        kernel = (ROOT / "chat/SKILL.md").read_text()
        self.assertIn('skill_view(name="note-access:read")', kernel)
        reference = (ROOT / "chat/references/note.md").read_text()
        for name in ("read", "check-format", "draft"):
            self.assertIn(f'skill_view(name="note-access:{name}")', reference)
        for mechanic in ("`base`", "note-block", "UNCERTAIN", "20 MB"):
            self.assertNotIn(mechanic, reference)

    def test_marketing_saves_every_destination_itself(self):
        execute = " ".join((ROOT / "marketing/execute/SKILL.md").read_text().split())
        for route in ('skill_view(name="x-access:draft-post")',
                      'skill_view(name="x-access:draft-article")',
                      'skill_view(name="substack-access:manage")',
                      'skill_view(name="note-access:draft")', 'skill_view(name="zenn-dev")'):
            self.assertIn(route, execute)
        self.assertNotIn("save-package", execute)
        self.assertNotIn("files[].sha256", execute)
        self.assertIn("Never use Marketer's browser or another login profile", execute)
        plan = " ".join((ROOT / "marketing/plan/SKILL.md").read_text().split())
        self.assertIn("Marketer is the strategy advisor", plan)
        self.assertIn("You own the execution plan", plan)
        self.assertNotIn("Marketer operates its existing browser profile", plan)
        self.assertTrue((public_root() / "hermes/plugins/social/x-access/skills/draft-post/SKILL.md").is_file())
        self.assertTrue((public_root() / "hermes/profiles/assistant/skills/technic/zenn-dev/SKILL.md").is_file())


if __name__ == "__main__":
    unittest.main()
