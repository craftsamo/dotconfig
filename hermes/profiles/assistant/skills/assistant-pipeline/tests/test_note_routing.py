"""note work routes to the public note-com technic; Chat keeps only what is its own."""

from pathlib import Path
import unittest

import hermes_yaml as yaml

from _pair import PUBLIC_ROOT


ROOT = Path(__file__).resolve().parents[1]


def public_root() -> Path:
    return PUBLIC_ROOT


class NoteRouting(unittest.TestCase):
    def test_the_technic_exists_and_takes_no_save_packages(self):
        technic = public_root() / "hermes/profiles/assistant/skills/technic/note-com"
        text = (technic / "SKILL.md").read_text()
        meta = yaml.safe_load(text.split("---", 2)[1])
        self.assertEqual(meta["name"], "note-com")
        self.assertEqual(meta["metadata"]["hermes"]["category"], "technic")
        self.assertIn("no exception", text)
        self.assertIn("`check`", text)
        self.assertFalse((technic / "references/save-package.md").exists())
        self.assertNotIn("save package", text)

    def test_chat_loads_the_technic_and_keeps_no_mechanics(self):
        kernel = (ROOT / "chat-assistant/SKILL.md").read_text()
        self.assertIn('skill_view(name="note-com")', kernel)
        reference = (ROOT / "chat-assistant/references/note.md").read_text()
        self.assertIn('skill_view(name="note-com")', reference)
        for mechanic in ("`base`", "note-block", "UNCERTAIN", "20 MB"):
            self.assertNotIn(mechanic, reference)

    def test_marketing_saves_every_destination_itself(self):
        execute = " ".join((ROOT / "execute-assistant-marketing/SKILL.md").read_text().split())
        for route in ('skill_view(name="x-twitter", file_path="references/post-draft.md")',
                      'skill_view(name="x-twitter", file_path="references/article-draft.md")',
                      'skill_view(name="chat-assistant", file_path="references/substack.md")',
                      'skill_view(name="note-com")', 'skill_view(name="zenn-dev")'):
            self.assertIn(route, execute)
        self.assertNotIn("save-package", execute)
        self.assertNotIn("files[].sha256", execute)
        self.assertIn("Never use Marketer's browser or another login profile", execute)
        plan = " ".join((ROOT / "plan-assistant-marketing/SKILL.md").read_text().split())
        self.assertIn("Marketer is the strategy advisor", plan)
        self.assertIn("You own the execution plan", plan)
        self.assertNotIn("Marketer operates its existing browser profile", plan)
        for name in ("x-twitter/references/post-draft.md", "zenn-dev/SKILL.md"):
            self.assertTrue((public_root() / "hermes/profiles/assistant/skills/technic" / name).is_file())


if __name__ == "__main__":
    unittest.main()
