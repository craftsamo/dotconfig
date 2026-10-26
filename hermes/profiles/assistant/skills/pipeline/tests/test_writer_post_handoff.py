"""Keep the post-family handoff gated without a generic inspection fallback."""

from pathlib import Path
import re
import unittest

from _public_writer_acceptance import public_raw, public_text

ROOT = Path(__file__).resolve().parents[1]


def text(path):
    return " ".join((ROOT / path).read_text().split())


class WriterPostHandoffTest(unittest.TestCase):
    def test_post_plan_has_existing_qa_contract(self):
        plan = text("plan-assistant-writing/references/post.md")
        self.assertIn("QA `prose`", plan)
        self.assertIn("`references/post.md`", text("plan-assistant-writing/SKILL.md"))
        for verb in ("write", "edit", "analyze"):
            self.assertIn(f"`{verb}-post`", plan)

    def test_analysis_is_not_gated_as_a_new_post(self):
        gate = public_text("index.md")
        self.assertIn("`analyze-post` uses its analysis-report branch", gate)
        self.assertIn("An analysis is not a post", gate)
        self.assertIn("not solely the Writer's reported name", gate)

    def test_served_gate_does_not_run_legacy_inspection(self):
        gate = public_raw("index.md")
        served = gate.split("## Served post gate", 1)[1].split("## Outline gate", 1)[0]
        self.assertNotRegex(served, r"uv run|scripts/lint\.py")
        self.assertIn("only if", served)
        self.assertIn("explicitly asked", served)
        self.assertNotIn("japanese-writing/scripts/", gate)

    def test_campaign_releases_writer_dependency_first(self):
        campaign = text("plan-assistant-marketing/references/campaign.md")
        self.assertIn("You release those as Writer/hands units, independently accept them", campaign)
        execute = text("execute-assistant-marketing/SKILL.md")
        self.assertIn("findings go back to the same Writer", execute)
        self.assertIn("independent writing QA", execute)

    def test_all_writing_plan_qa_mappings_resolve(self):
        for leaf in (ROOT / "plan-assistant-writing/references").glob("*.md"):
            match = re.search(r"QA `([a-z-]+)`", leaf.read_text())
            self.assertIsNotNone(match, leaf)
            self.assertTrue((ROOT / "qa-assistant-writing/references" / f"{match[1]}.md").is_file())


if __name__ == "__main__":
    unittest.main()
