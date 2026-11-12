"""GitHub work reaches the github-tools tools and skills from every entry that meets it: Chat for the
user's direct requests, engineering for a job's pull requests, CI and merges."""

from pathlib import Path
import re
import unittest

from _pair import PUBLIC_ROOT, private_config


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ("issues", "projects", "pull-requests", "repos", "releases", "actions")
TECHNIC = PUBLIC_ROOT / "hermes/profiles/assistant/skills/technic/github"
MERGE = 'skill_view(name="github", file_path="references/merge.md")'
# The retired plugin's change-list tool, its grant tool and its skill prefix, and any sentence that ties a
# GitHub write to a standing grant, spelled in pieces so this file is not itself a hit for them.
RETIRED = ("github_" + "change", "github_" + "man" + "date", "github-" + "access" + ":")
GRANT = "man" + "date"
STANDING_GRANT = rf"github[^.]{{0,80}}{GRANT}|{GRANT}[^.]{{0,80}}github"


def flat(path: Path) -> str:
    return " ".join(path.read_text().split())


class GithubRouting(unittest.TestCase):
    def test_chat_routes_github_requests_to_the_skills(self):
        kernel = flat(ROOT / "chat/SKILL.md")
        self.assertIn("`references/github.md`", kernel)
        reference = flat(ROOT / "chat/references/github.md")
        for name in SKILLS:
            self.assertIn(f'skill_view(name="github-tools:{name}")', reference)
        self.assertIn('skill_view(name="github-tracking")', reference)
        self.assertIn('skill_view(name="github")', reference)
        self.assertIn("Code is not Chat's", reference)
        for never in ("approving or requesting changes", "secrets", "cancelling runs"):
            self.assertIn(never, reference)
        self.assertIn("starting a workflow", kernel)
        for op in ("`github_run_rerun`", "`github_workflow_run`"):
            self.assertIn(op, reference)
        self.assertIn("the card is the user's go, so do not ask first", reference)

    def test_engineering_reads_ci_and_merges_through_the_tools(self):
        qa = flat(ROOT / "engineering/qa/SKILL.md")
        self.assertIn("`github_pr_read` `view`", qa)
        acceptance = flat(ROOT / "engineering/qa/references/acceptance.md")
        self.assertIn("`github_pr_read` `view`", acceptance.split("Only when the user separately asks")[0])
        self.assertIn("`github_pr_merge`", acceptance)
        self.assertIn(MERGE, acceptance)
        ops = flat(ROOT / "engineering/execute/references/github-ops.md")
        for name in ("`github_pr_create`", "`github_run_rerun`", "`github_release_publish`",
                     "`github_workflow_run`", 'skill_view(name="github-tools:repos")',
                     'skill_view(name="github", file_path="references/pull-requests.md")',
                     'skill_view(name="github", file_path="references/repository.md")', MERGE,
                     'skill_view(name="github", file_path="references/history-repair.md")'):
            self.assertIn(name, ops)
        self.assertIn("never for a branch a build run made", ops)

    def test_chat_routes_git_requests_to_the_skills(self):
        kernel = flat(ROOT / "chat/SKILL.md")
        self.assertIn("`references/git.md`", kernel)
        reference = flat(ROOT / "chat/references/git.md")
        for name in ("repo", "worktree"):
            self.assertIn(f'skill_view(name="git-tools:{name}")', reference)
        for name in ("`git_repo_read`", "`git_worktree_read`", "`git_worktree_remove`",
                     "`opencode_session cleanup`", "`git pull --ff-only`"):
            self.assertIn(name, reference)
        self.assertIn("Commits, rebases and pushes on target repositories are OpenCode's", reference)

    def test_every_technic_reference_the_pipeline_names_exists(self):
        named = set()
        for path in ROOT.rglob("*.md"):
            named.update(re.findall(r'skill_view\(name="github", file_path="([^"]+)"\)', flat(path)))
        self.assertIn("references/merge.md", named)
        for file_path in sorted(named):
            self.assertTrue((TECHNIC / file_path).is_file(), file_path)

    def test_no_entry_names_the_retired_plugin_or_its_standing_grants(self):
        for path in sorted([*ROOT.rglob("*.md"), *TECHNIC.parent.rglob("*.md")]):
            text = flat(path)
            with self.subTest(path.name):
                for word in RETIRED:
                    self.assertNotIn(word, text)
                self.assertIsNone(re.search(STANDING_GRANT, text, re.IGNORECASE))

    def test_the_operating_contract_names_the_tools_for_every_github_write(self):
        prompt = flat(PUBLIC_ROOT / "hermes/profiles/assistant/config.example.yaml")
        self.assertIn("pull request changes, merges, releases and CI re-runs are yours", prompt)
        self.assertIn("never a gh write in the terminal", prompt)
        opencode = flat(PUBLIC_ROOT / "hermes/plugins/orchestration/opencode/skills/drive/SKILL.md")
        self.assertIn("never passes `issue_approval`", opencode)

    def test_the_private_contract_says_the_same(self):
        prompt = flat(private_config())  # skipped without the paired private checkout
        self.assertIn("pull request changes, merges, releases and CI re-runs are yours", prompt)
        self.assertIn("never a gh write in the terminal", prompt)


if __name__ == "__main__":
    unittest.main()
