"""Editorial scores supplement evidence; they never replace scope or approval.

The rubric itself moved to the public writer-pipeline (see
`_public_writer_acceptance.py`); this file also guards that this repo's own
adapter stays thin instead of re-accumulating a second copy.
"""

from pathlib import Path
import unittest

from _public_writer_acceptance import public_text

ROOT = Path(__file__).resolve().parents[1]


def text(path):
    return " ".join((ROOT / path).read_text().split())


class WriterScoringTest(unittest.TestCase):
    def test_scoring_has_one_definition_inside_existing_gate(self):
        directory = ROOT / "qa-assistant-writing"
        self.assertEqual({p.relative_to(directory).as_posix()
                          for p in directory.rglob("*.md")},
                         {"SKILL.md", "references/prose.md", "references/script.md"})
        rubric = public_text("index.md")
        for axis in ("Naturalness", "Density and concision", "Function and navigation",
                     "Logical clarity", "Integrity", "Demonstration"):
            self.assertIn(f"| {axis} |", rubric)
        for anchor in ("95-100", "90-94", "80-89", "below 80", "unverified"):
            self.assertIn(f"| {anchor} |", rubric)
        self.assertIn("every applicable axis is at least 90", rubric)
        self.assertIn("the mean of the scored axes is at least 92", rubric)
        self.assertIn("Purpose and fidelity are hard gates", rubric)
        self.assertIn("Never average away", rubric)
        self.assertIn("v1.5.0", rubric)

    def test_scores_cannot_hide_missing_evidence_or_invent_scope(self):
        rubric = public_text("index.md")
        self.assertIn("unverified with no numeric score", rubric)
        self.assertIn("not applicable with a reason", rubric)
        self.assertIn("A valid unchanged edit can score 95 or above", rubric)
        self.assertIn("Never demand invented findings", rubric)
        self.assertIn("Scores describe reader cost, never authorship", rubric)
        self.assertIn("neither user approval nor publication authorization", rubric)
        self.assertIn("do not assume Writer's profile-local references are loaded", rubric)

    def test_scoring_uses_released_scope_and_format_anchors(self):
        rubric = public_text("index.md")
        self.assertIn("from the released request, not the output name", rubric)
        prose = public_text("prose.md")
        self.assertIn("30 satisfied respondents", prose)
        self.assertIn("not the target report's quality", prose)
        self.assertIn("An accurate existing sentence may pass unchanged", prose)
        for name in ("README", "Guide", "Reference", "Minutes", "Proposal",
                     "Slides", "Release notes", "Issue", "Explanation",
                     "Tutorial", "Experience", "Comparison", "Destination",
                     "Assets and notes"):
            self.assertIn(f"| {name} |", prose)

    def test_revision_budget_and_latest_candidate_are_explicit(self):
        execution = text("execute-assistant-writing/SKILL.md")
        rubric = public_text("index.md")
        self.assertIn("at most two corrective returns per released unit", rubric)
        self.assertIn("does not reset the budget", rubric)
        self.assertIn("Re-read the complete latest candidate", execution)
        self.assertIn("never a substitute for it", execution)
        self.assertIn("Escalation is not acceptance", rubric)
        self.assertIn("Before releasing the unit, communicate", execution)
        self.assertIn("Optional improvements on a passing score of 90-94", execution)
        self.assertIn("#correction-ceiling", execution)
        self.assertIn("before acceptance", rubric)
        self.assertIn("explicit corrective release", rubric)
        self.assertIn("do not re-score the settled structure or tone", rubric)

    def test_all_families_are_scored_without_extending_production_authority(self):
        rubric = public_text("index.md")
        self.assertIn("Post, Article, Document, Message, Copy and Script", rubric)
        self.assertIn("across write/edit/analyze", rubric)
        self.assertIn("not planning consultation", rubric)
        prose = public_text("prose.md")
        script = public_text("script.md")
        for family in ("Post", "Article", "Document", "Message", "Copy"):
            self.assertIn(f"### {family} scoring anchors", prose)
        for name in ("X", "Instagram", "Email", "Chat", "Notification", "UI",
                     "Error", "Landing page", "Promotional email", "Announcement"):
            self.assertIn(f"| {name} |", prose)
        for name in ("Narration", "Comic", "Storyboard", "Screenplay", "Slide-script"):
            self.assertIn(f"| {name} |", script)
        self.assertIn("never a claim of measured duration", script)
        self.assertIn("not a defect in the analysis itself", script)

    def test_private_adapter_points_at_public_source_and_blocks_on_failure(self):
        for name in ("index.md", "prose.md", "script.md"):
            adapter_path = ("qa-assistant-writing/SKILL.md" if name == "index.md"
                            else f"qa-assistant-writing/references/{name}")
            adapter = text(adapter_path)
            self.assertIn(
                'skill_view(name="writer-pipeline", '
                f'file_path="references/acceptance/{name}")', adapter)
            self.assertIn("BLOCKED", adapter)
            self.assertIn("do not copy", adapter.lower())
        # None of the moved rubric text is duplicated locally anymore.
        index_adapter = text("qa-assistant-writing/SKILL.md")
        self.assertNotIn("| Naturalness |", index_adapter)
        self.assertNotIn("at most two corrective returns", index_adapter)
        prose_adapter = text("qa-assistant-writing/references/prose.md")
        self.assertNotIn("30 satisfied respondents", prose_adapter)
        script_adapter = text("qa-assistant-writing/references/script.md")
        self.assertNotIn("Narration | Spoken order", script_adapter)


if __name__ == "__main__":
    unittest.main()
