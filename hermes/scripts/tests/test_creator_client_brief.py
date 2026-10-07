"""Wording regressions for briefs, consent and decisions, not proof of runtime enforcement.

The Assistant is the only client of the hands: consent, inspiration vs production
input and suggestion vs decision live in its commissioning procedure; Creator's
propose/revise entries keep observed, suggested and decided apart.
"""

from pathlib import Path
import unittest


PROFILES = Path(__file__).resolve().parents[2] / "profiles"
ASSISTANT = PROFILES / "assistant/skills/assistant-pipeline"
CREATOR = PROFILES / "creator/skills/creator-pipeline"


def read(root, relative):
    return " ".join((root / relative).read_text(encoding="utf-8").split())


class CreativeBriefTest(unittest.TestCase):
    def test_inspiration_is_not_a_production_input(self):
        execute = read(ASSISTANT, "execute-assistant-creative/SKILL.md")
        self.assertIn("Research examples are inspiration, never production inputs", execute)
        propose = read(CREATOR, "propose-creator/SKILL.md")
        self.assertIn("A research example is inspiration, never a production input", propose)
        research = read(ASSISTANT, "plan-assistant-creative/references/reference-research.md")
        self.assertIn("role: inspiration only; production reuse/upload not authorized", research)

    def test_suggestions_and_user_decisions_are_distinct(self):
        execute = read(ASSISTANT, "execute-assistant-creative/SKILL.md")
        self.assertIn("The user's pick is a human decision; record it separately from Creator's recommendation", execute)
        self.assertIn("Creator's output is advice: it approves nothing, releases no spend", execute)
        self.assertIn("Never send a design of your own for it to fill in", execute)
        plan = read(ASSISTANT, "plan-assistant-creative/SKILL.md")
        self.assertIn("Record what is decided, what is merely suggested and what Creator should propose", plan)
        propose = read(CREATOR, "propose-creator/SKILL.md")
        self.assertIn("Keep observed evidence, the user's decisions, your suggestions and open questions apart", propose)
        self.assertIn("A direction is a suggestion; nothing is approved or released until the Assistant relays the user's choice", propose)
        revise = read(CREATOR, "revise-creator/SKILL.md")
        self.assertIn("do not reopen decisions the user did not question", revise)
        kernel = read(CREATOR, "SKILL.md")
        self.assertIn("a choice is the user's only when the Assistant relays it as such", kernel)

    def test_agent_shape_does_not_imply_upload_consent(self):
        execute = read(ASSISTANT, "execute-assistant-creative/SKILL.md")
        self.assertNotIn("brief is taken as consent", execute)
        self.assertIn("needs the user's explicit consent for that asset and operation", execute)
        self.assertIn('A path, a public URL, a direction choice or "use this" is not consent', execute)
        self.assertIn("asked in the same round as the related choice", execute)

    def test_creator_never_holds_or_grants_consent(self):
        kernel = read(CREATOR, "SKILL.md")
        self.assertIn("The Assistant owns the user's decisions, filling and sending hands forms, approvals, budgets, consent and delivery", kernel)
        self.assertIn("A recommendation never approves a proposal, preview or spend", kernel)

    def test_reimagine_requires_upload_authorization_for_every_photo(self):
        reimagine = read(ASSISTANT, "execute-assistant-creative/references/reimagine.md")
        self.assertNotIn("assistant-brief-consent", reimagine)
        self.assertIn("the user's asset-and-upload authorization apply to any of those subjects, not only a person", reimagine)
        self.assertIn("never incidental context", reimagine)


if __name__ == "__main__":
    unittest.main()
