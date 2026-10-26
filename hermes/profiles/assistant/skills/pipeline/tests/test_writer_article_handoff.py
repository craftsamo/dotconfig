"""Article-source acceptance must not imply editor/media completion."""

from pathlib import Path
import unittest

from _public_writer_acceptance import public_raw, public_text

ROOT = Path(__file__).resolve().parents[1]


def text(path):
    return " ".join((ROOT / path).read_text().split())


class WriterArticleHandoffTest(unittest.TestCase):
    def test_plan_names_article_leaves_and_existing_qa(self):
        plan = text("plan-assistant-writing/references/article.md")
        self.assertIn("QA `prose`", plan)
        for verb in ("write", "edit", "analyze"):
            self.assertIn(f"`{verb}-article`", plan)
        self.assertIn("not generation or capture", plan)

    def test_served_article_gate_is_not_legacy_review(self):
        gate = public_raw("index.md")
        served = gate.split("## Served article gate", 1)[1].split("## Outline gate", 1)[0]
        self.assertIn("do not require four legacy passes", " ".join(served.split()))
        self.assertNotIn("scripts/lint.py", served)
        self.assertIn("Analysis is judged as a report", served)

    def test_source_acceptance_does_not_certify_finishing(self):
        prose = public_text("prose.md")
        self.assertIn("text-only scope actually released", prose)
        self.assertIn("not call it publication-ready", prose)
        self.assertIn("Never delete a marker", prose)
        self.assertIn("Article analysis (analyze-article)", prose)
        execution = text("execute-assistant-writing/SKILL.md")
        self.assertIn("unresolved asset/editor dependencies intact", execution)

    def test_article_client_guide_separates_decisions_and_reference_evidence(self):
        plan = text("plan-assistant-writing/references/article.md")
        for heading in ("Use", "Client decisions", "References", "Acceptance"):
            self.assertIn(f"## {heading}", plan)
        self.assertIn("Keep editorial decisions here", plan)
        self.assertIn("Writer interprets its form", plan)
        self.assertIn("factual sources separate from examples", plan)
        self.assertIn("observed evidence, suggested direction, user decisions and open choices", plan)
        self.assertIn("research is not mandatory", plan)
        self.assertNotIn("asset_policy", plan)

    def test_bounded_article_work_does_not_restart_new_writing(self):
        plan = text("plan-assistant-writing/references/article.md")
        self.assertIn("`scope: proofread`", plan)
        self.assertIn("`scope: wording`", plan)
        self.assertIn("no new outline, tone samples, reader research", plan)
        self.assertIn("scope that conflicts with the request needs clarification", plan)
        index = text("plan-assistant-writing/SKILL.md")
        self.assertIn("does not require every new-writing decision", index)
        execution = text("execute-assistant-writing/SKILL.md")
        self.assertIn("existing text as its unit", execution)
        self.assertIn("Accept a checked no-change result", execution)

    def test_proofreading_acceptance_preserves_scope_and_report_only_work(self):
        gate = public_text("index.md")
        self.assertIn("generic new-writing outline/full gate below does not add", gate)
        self.assertIn("edits within a proofread or wording scope", gate)
        self.assertIn("Structure/rewrite units retain their applicable full gate", gate)
        self.assertIn("Explicitly requested factual checks still require evidence", gate)
        prose = public_text("prose.md")
        self.assertIn("For `scope: proofread`", prose)
        self.assertIn("A no-change result is valid", prose)
        self.assertIn("not permission to guess a replacement", prose)
        self.assertIn("do not commission external fact-checking", prose)
        self.assertIn("For proofreading-focused analysis", prose)
        self.assertIn("report is not replacement text", prose)


if __name__ == "__main__":
    unittest.main()
