"""The github technic works through the GitHub tools: its entry routes every reference, nothing the
Assistant reads in it is a gh command its terminal guard blocks, and history surgery is commissioned
from a build run as outcomes and conditions, never as commands."""

import importlib.util
import re
import unittest

import hermes_yaml as yaml

from _pair import PUBLIC_ROOT


TECHNIC = PUBLIC_ROOT / "hermes/profiles/assistant/skills/technic/github"
GUARD = PUBLIC_ROOT / "hermes/plugins/github-access/guard.py"
BUILD_BRIEF = "history-repair.md"


def guard():
    spec = importlib.util.spec_from_file_location("github_technic_guard", GUARD)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def flat(text: str) -> str:
    return " ".join(text.split())


class GithubTechnic(unittest.TestCase):
    def setUp(self):
        self.entry = (TECHNIC / "SKILL.md").read_text()
        self.references = {p.name: p.read_text() for p in sorted((TECHNIC / "references").glob("*.md"))}

    def test_it_is_a_technic_named_after_its_directory(self):
        meta = yaml.safe_load(self.entry.split("---", 2)[1])
        self.assertEqual(meta["name"], "github")
        self.assertEqual(meta["metadata"]["hermes"]["category"], "technic")

    def test_the_entry_routes_every_reference(self):
        self.assertIn(BUILD_BRIEF, self.references)
        for name in self.references:
            self.assertIn(f"(references/{name})", self.entry)

    def test_what_the_assistant_runs_needs_no_blocked_gh_command(self):
        blocked = guard().blocked
        self.assertTrue(blocked("gh pr merge 1 --squash"))  # the guard this test leans on still blocks
        merge = flat(self.references["merge.md"])
        for name in ('skill_view(name="github-access:manage-pr")', "`pr_merge`", "`github_pr` `view`"):
            self.assertIn(name, merge)
        for name, text in {"SKILL.md": self.entry, **self.references}.items():
            if name == BUILD_BRIEF:
                continue
            with self.subTest(name):
                commands = re.findall(r"\bgh\s+[a-z][a-z-]*(?:\s+[a-z][a-z-]*)?", text)
                self.assertEqual([c for c in commands if blocked(c)], [])
                self.assertIsNone(re.search(r"\bgh\s+(?:api|stack)\b", text))

    def test_history_surgery_is_commissioned_as_outcomes_never_as_commands(self):
        brief = flat(self.references[BUILD_BRIEF])
        self.assertIn("none of it is the Assistant's to run", brief)
        self.assertIn("explicit go", brief)
        self.assertIn("How it gets there, which commands and in what order, is the run's", brief)
        self.assertIn("never main or any other branch", brief)
        self.assertIn("ends with a verified result the user pushes, never a push of the run's", brief)
        self.assertIn("checked before anything is pushed and again after", brief)
        for name, text in {"SKILL.md": self.entry, **self.references}.items():
            for surgery in ("--force-with-lease", "filter-repo", "git push", "git rebase", "cherry-pick",
                            "gh stack"):
                self.assertNotIn(surgery, text, (name, surgery))
        ops = flat(self.references["merge.md"])
        self.assertNotIn("brief it with", ops)


if __name__ == "__main__":
    unittest.main()
