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
        for name in ("note-com", "note-com-format", "note-com-drafts"):
            text = (skills / name / "SKILL.md").read_text()
            meta = yaml.safe_load(text.split("---", 2)[1])
            self.assertEqual(meta["name"], name)
            self.assertNotIn("save package", text)
            self.assertFalse((skills / name / "references/save-package.md").exists())
            texts[name] = text
        self.assertIn("no exception", " ".join(texts["note-com"].split()))
        self.assertIn("`check`", texts["note-com-format"])
        self.assertIn("preview", texts["note-com-drafts"])

    def test_chat_loads_the_skills_and_keeps_no_mechanics(self):
        kernel = (ROOT / "chat-assistant/SKILL.md").read_text()
        self.assertIn('skill_view(name="note-access:note-com")', kernel)
        reference = (ROOT / "chat-assistant/references/note.md").read_text()
        for name in ("note-com", "note-com-format", "note-com-drafts"):
            self.assertIn(f'skill_view(name="note-access:{name}")', reference)
        for mechanic in ("`base`", "note-block", "UNCERTAIN", "20 MB"):
            self.assertNotIn(mechanic, reference)

    def test_marketing_saves_every_destination_itself(self):
        execute = " ".join((ROOT / "execute-assistant-marketing/SKILL.md").read_text().split())
        for route in ('skill_view(name="x-access:x-twitter-drafts", file_path="references/post-draft.md")',
                      'skill_view(name="x-access:x-twitter-drafts", file_path="references/article-draft.md")',
                      'skill_view(name="substack-access:substack-drafts")',
                      'skill_view(name="note-access:note-com-drafts")', 'skill_view(name="zenn-dev")'):
            self.assertIn(route, execute)
        self.assertNotIn("save-package", execute)
        self.assertNotIn("files[].sha256", execute)
        self.assertIn("Never use Marketer's browser or another login profile", execute)
        plan = " ".join((ROOT / "plan-assistant-marketing/SKILL.md").read_text().split())
        self.assertIn("Marketer is the strategy advisor", plan)
        self.assertIn("You own the execution plan", plan)
        self.assertNotIn("Marketer operates its existing browser profile", plan)
        self.assertTrue((public_root() / "hermes/plugins/social/x-access/skills/x-twitter-drafts/references/post-draft.md").is_file())
        self.assertTrue((public_root() / "hermes/profiles/assistant/skills/technic/zenn-dev/SKILL.md").is_file())


if __name__ == "__main__":
    unittest.main()
