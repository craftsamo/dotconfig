"""Copy gates preserve claims and terms without accepting analysis as a draft."""

from pathlib import Path
import unittest

from _public_writer_acceptance import public_raw, public_text

ROOT = Path(__file__).resolve().parents[1]


def text(path):
    return " ".join((ROOT / path).read_text().split())


class WriterCopyHandoffTest(unittest.TestCase):
    def test_plan_routes_three_copy_leaves(self):
        plan = text("plan-assistant-writing/references/copy.md")
        index = text("plan-assistant-writing/SKILL.md")
        self.assertIn("QA `prose`", plan)
        for verb in ("write", "edit", "analyze"):
            self.assertIn(f"`{verb}-copy`", plan)
            self.assertIn(f"`{verb}-copy`", index)
        self.assertIn("existing `marketing-copy` briefs", plan)
        self.assertIn("custom destination", plan)

    def test_adjacent_families_and_conditional_action(self):
        plan = text("plan-assistant-writing/references/copy.md")
        for reference in ("post.md", "message.md", "documentation.md"):
            self.assertIn(f"`{reference}`", plan)
        self.assertIn("An awareness announcement need not have a CTA", plan)
        self.assertIn("offer corrections require supporting evidence", plan)
        self.assertIn("other social platforms keep marketing Execute's existing drafting contract", plan)

    def test_marketing_controller_releases_accepted_copy_parts(self):
        execution = text("execute-assistant-marketing/SKILL.md")
        for verb in ("write", "edit", "analyze"):
            self.assertIn(f"{verb}-copy", execution)
        self.assertIn("independent writing QA", execution)
        self.assertIn("consumes accepted text unchanged", execution)
        self.assertIn("findings go back to the same Writer", execution)
        self.assertIn("No Publish/P1 grant", execution)

    def test_copy_gate_uses_operation_and_evidence(self):
        gate = public_raw("index.md")
        served = gate.split("## Served copy gate", 1)[1].split("## Outline gate", 1)[0]
        self.assertNotIn("scripts/lint.py", served)
        for verb in ("write", "edit", "analyze"):
            self.assertIn(f"`{verb}-copy`", served)
        self.assertIn("NOT verified", served)
        self.assertIn("Humanizer is explicit-request only", served)
        self.assertIn("not a new sales page requiring a CTA", served)
        self.assertNotIn("japanese-writing/scripts/", gate)

    def test_copy_draft_protects_terms_and_does_not_certify_performance(self):
        prose = public_text("prose.md")
        self.assertIn("Protected conditions must remain associated", prose)
        self.assertIn("authorized edit scope and untouched fields", prose)
        self.assertIn("not fail an awareness announcement solely for lacking a CTA", prose)
        self.assertIn("legal compliance or conversion lift", prose)
        self.assertIn("independent QA never rewrites the copy", prose)

    def test_analysis_needs_no_new_copy_and_script_remains_legacy(self):
        prose = public_text("prose.md")
        self.assertIn("report needs no new headline, offer, testimonial, CTA", prose)
        self.assertIn("unsolicited replacement draft", prose)
        self.assertIn("scripts still use `script.md`", prose)

    def test_part_handoff_is_verbatim_after_independent_acceptance(self):
        execution = text("execute-assistant-writing/SKILL.md")
        for verb in ("write", "edit", "analyze"):
            self.assertIn(f"`{verb}-copy`", execution)
        self.assertIn("consumer after independent writing QA", execution)
        self.assertIn("no local shortening or humanizer rewrite", execution)
        self.assertIn("changed approved text needs renewed approval", execution)
        self.assertIn("analyze-copy report is decision input, not publishable copy", execution)


if __name__ == "__main__":
    unittest.main()
