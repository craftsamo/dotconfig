"""Receiver wording regressions, not proof of runtime consent enforcement."""

from pathlib import Path
import unittest


PIPELINE = (
    Path(__file__).resolve().parents[2]
    / "profiles/creator/skills/creator-pipeline"
)


def read(relative):
    return " ".join((PIPELINE / relative).read_text(encoding="utf-8").split())


class CreatorClientBriefTest(unittest.TestCase):
    def test_inspiration_is_not_a_production_input(self):
        plan = read("plan-creator/SKILL.md")
        self.assertIn("A research example is inspiration only", plan)
        self.assertIn("not automatically a production asset", plan)
        self.assertIn("research-only examples are not required production inputs", plan)

    def test_suggestions_and_user_decisions_are_distinct(self):
        plan = read("plan-creator/SKILL.md")
        self.assertIn("observed evidence, suggested direction, user-decided constraints", plan)
        self.assertIn("You still own creative proposals, forms and production sequencing", plan)
        self.assertIn("Do not require a new taste vote for every minor suggestion", plan)
        self.assertIn("exact-plan/preview approval", plan)

    def test_assistant_shape_does_not_imply_upload_consent(self):
        plan = read("plan-creator/SKILL.md")
        self.assertNotIn("brief is taken as consent", plan)
        self.assertIn("explicit relay of the user's authorization", plan)
        self.assertIn("named asset and upload operation", plan)
        self.assertIn('"use this" alone is not external-upload consent', plan)
        self.assertIn("return `Q<n>:` before the affected upload", plan)
        self.assertIn("does not block harmless local planning", plan)

    def test_human_and_stricter_leaf_gates_survive(self):
        plan = read("plan-creator/SKILL.md")
        self.assertIn("a human client is told so in the SAME clarify round", plan)
        self.assertIn("Preserve stricter leaf-specific consent requirements", plan)
        self.assertIn("remote video analysis", plan)

    def test_reimagine_uses_explicit_relay_for_every_photo(self):
        reimagine = read("plan-creator/references/image-creator/reimagine.md")
        self.assertNotIn("assistant-brief-consent", reimagine)
        self.assertIn("explicit assistant relay of the user's asset-and-upload authorization", reimagine)
        self.assertIn("not only a person", reimagine)


if __name__ == "__main__":
    unittest.main()
