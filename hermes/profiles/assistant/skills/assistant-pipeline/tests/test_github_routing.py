"""GitHub work reaches the github-access tools and skills from every entry that meets it: Chat for the
user's direct requests, engineering for a job's pull requests, CI and merges."""

from pathlib import Path
import re
import unittest

from _pair import PUBLIC_ROOT, private_config


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ("github", "github-tracking", "github-repo", "github-pr")
TECHNIC = PUBLIC_ROOT / "hermes/profiles/assistant/skills/technic/github"
MERGE = 'skill_view(name="github", file_path="references/merge.md")'


def flat(path: Path) -> str:
    return " ".join(path.read_text().split())


class GithubRouting(unittest.TestCase):
    def test_chat_routes_github_requests_to_the_skills(self):
        kernel = flat(ROOT / "chat-assistant/SKILL.md")
        self.assertIn("`references/github.md`", kernel)
        reference = flat(ROOT / "chat-assistant/references/github.md")
        for name in SKILLS:
            self.assertIn(f'skill_view(name="github-access:{name}")', reference)
        self.assertIn('skill_view(name="github")', reference)
        self.assertIn("Code is not Chat's", reference)
        for never in ("approving or requesting changes", "secrets", "cancelling runs"):
            self.assertIn(never, reference)
        self.assertIn("starting a workflow", kernel)
        for op in ("`run_rerun`", "`workflow_dispatch`"):
            self.assertIn(op, reference)
        self.assertIn("the card is the user's go, so do not ask first", reference)

    def test_engineering_reads_ci_and_merges_through_the_tools(self):
        qa = flat(ROOT / "qa-assistant-engineering/SKILL.md")
        self.assertIn("`github_pr` `view`", qa)
        acceptance = flat(ROOT / "qa-assistant-engineering/references/acceptance.md")
        self.assertIn("`github_pr` `view`", acceptance.split("Only when the user separately asks")[0])
        self.assertIn(MERGE, acceptance)
        ops = flat(ROOT / "execute-assistant-engineering/references/github-ops.md")
        for name in ("`pr_create`", "`run_rerun`", "`release_publish`", "`workflow_dispatch`",
                     'skill_view(name="github-access:github-repo")', MERGE,
                     'skill_view(name="github", file_path="references/history-repair.md")'):
            self.assertIn(name, ops)
        self.assertIn("never for a branch a build run made", ops)

    def test_every_technic_reference_the_pipeline_names_exists(self):
        named = set()
        for path in ROOT.rglob("*.md"):
            named.update(re.findall(r'skill_view\(name="github", file_path="([^"]+)"\)', flat(path)))
        self.assertIn("references/merge.md", named)
        for file_path in sorted(named):
            self.assertTrue((TECHNIC / file_path).is_file(), file_path)

    def test_the_operating_contract_names_the_tools_for_every_github_write(self):
        prompt = flat(PUBLIC_ROOT / "hermes/profiles/assistant/config.example.yaml")
        self.assertIn("pull request changes, merges, releases and CI re-runs are yours", prompt)
        self.assertIn("never a gh write in the terminal", prompt)
        opencode = flat(PUBLIC_ROOT / "hermes/plugins/orchestration/opencode/skills/opencode/SKILL.md")
        self.assertIn("never passes `issue_approval`", opencode)

    def test_the_private_contract_says_the_same(self):
        prompt = flat(private_config())  # skipped without the paired private checkout
        self.assertIn("pull request changes, merges, releases and CI re-runs are yours", prompt)
        self.assertIn("never a gh write in the terminal", prompt)


if __name__ == "__main__":
    unittest.main()
