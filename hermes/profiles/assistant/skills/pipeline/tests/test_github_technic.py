"""The github technic works through the github_* tools: its entry routes every reference, nothing the
Assistant reads in it is a gh command its terminal guard blocks, and history surgery is commissioned
from a build run as outcomes and conditions, never as commands."""

import importlib.util
import re
import unittest

import hermes_yaml as yaml

from _pair import PUBLIC_ROOT


TECHNIC = PUBLIC_ROOT / "hermes/profiles/assistant/skills/technic/github"
TRACKING = PUBLIC_ROOT / "hermes/profiles/assistant/skills/technic/github-tracking"
GUARD = PUBLIC_ROOT / "hermes/plugins/guards/github-tools-guard/gh_terminal.py"
GIT_GUARD = PUBLIC_ROOT / "hermes/plugins/guards/git-tools-guard/git_terminal.py"
SKILL_ROOT = TECHNIC.parents[1]
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

    def test_the_tracking_technic_is_named_after_its_directory_and_routes_its_example(self):
        entry = (TRACKING / "SKILL.md").read_text()
        meta = yaml.safe_load(entry.split("---", 2)[1])
        self.assertEqual(meta["name"], "github-tracking")
        self.assertEqual(meta["metadata"]["hermes"]["category"], "technic")
        for path in sorted((TRACKING / "references").glob("*.md")):
            self.assertIn(f"(references/{path.name})", entry)

    def test_the_entry_routes_every_reference(self):
        self.assertIn(BUILD_BRIEF, self.references)
        for name in self.references:
            self.assertIn(f"(references/{name})", self.entry)

    def test_what_the_assistant_runs_needs_no_blocked_gh_command(self):
        gh_terminal = guard()
        blocked = gh_terminal.blocked
        self.assertTrue(blocked("gh pr merge 1 --squash"))  # the guard this test leans on still blocks
        merge = flat(self.references["merge.md"])
        for name in ('skill_view(name="github-tools:pull-requests")', "`github_pr_merge`", "`github_pr_read` `view`",
                     "`with_lower_layers: true`", "`github_ruleset_read`"):
            self.assertIn(name, merge)
        ci = flat(self.references["ci.md"])
        for name in ("`github_pr_read` `checks`", "`github_run_read`", "`github_run_rerun`"):
            self.assertIn(name, ci)
        for name, text in {"SKILL.md": self.entry, **self.references}.items():
            if name == BUILD_BRIEF:
                continue
            with self.subTest(name):
                commands = re.findall(r"\bgh\s+[a-z][a-z-]*(?:\s+[a-z][a-z-]*)?", text)
                self.assertEqual([c for c in commands if blocked(c)], [])
                self.assertIsNone(re.search(r"\bgh\s+(?:api|stack)\b", text))

    def test_what_the_tools_do_is_blocked_in_the_terminal_with_the_tool_message(self):
        gh_terminal = guard()
        for command in ("gh pr review 1 --approve", "gh run cancel 42", "gh release delete v1.0.0",
                        "gh pr merge 1", "gh issue close 3", "gh project item-edit"):
            with self.subTest(command):
                self.assertEqual(gh_terminal.blocked(command), gh_terminal.MESSAGE)
        for command in ("gh secret set TOKEN", "gh release upload v1.0.0 a.zip", "gh run delete 42"):
            with self.subTest(command):
                self.assertEqual(gh_terminal.blocked(command), gh_terminal.NEVER_MESSAGE)
        for command in ("gh pr view 1", "gh pr checks 1", "gh run view 42", "gh issue list"):
            with self.subTest(command):
                self.assertIsNone(gh_terminal.blocked(command))

    def test_the_assistant_skills_need_no_blocked_terminal_git_command(self):
        spec = importlib.util.spec_from_file_location("github_technic_git_guard", GIT_GUARD)
        git_terminal = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(git_terminal)
        self.assertTrue(git_terminal.blocked("git worktree remove task"))
        for family in ("pipeline", "technic"):
            for path in sorted((SKILL_ROOT / family).rglob("*.md")):
                text = path.read_text()
                for match in re.finditer(r"```[^\n]*\n(.*?)```|`([^`]+)`", text, re.DOTALL):
                    code = match.group(1) if match.group(1) is not None else match.group(2)
                    if not re.search(r"\bgit\s+", code):
                        continue
                    prefix = flat(text[:match.start()])
                    if re.search(r"(?:\bnever|\bdo not|\btell the user to run)$", prefix, re.IGNORECASE):
                        continue
                    with self.subTest(path=path.relative_to(SKILL_ROOT), command=code):
                        self.assertIsNone(git_terminal.blocked(code))

    def test_the_conventions_the_references_carry(self):
        pull_requests = flat(self.references["pull-requests.md"])
        for text in ("**Never review.**", "**Each file with the user's yes.**", "Merge only when the user asks to",
                     "`Refs #N`", "`github_pr_ready`", 'skill_view(name="github-tools:pull-requests")',
                     'skill_view(name="github-tracking")'):
            self.assertIn(text, pull_requests)
        repository = flat(self.references["repository.md"])
        for text in ("**Admin changes each on their own card.**", "Never offer `session` for one",
                     "`github_release_publish`", "`github_workflow_run`", "`Managed protection: <branch>`",
                     'skill_view(name="github-tools:repos")'):
            self.assertIn(text, repository)
        self.assertIn("never ask the user to pick `always`", flat(self.entry))

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
