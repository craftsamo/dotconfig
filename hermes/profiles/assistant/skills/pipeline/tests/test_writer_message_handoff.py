"""Message acceptance preserves intent without sending or expanding private access."""

from pathlib import Path
import unittest

from _public_writer_acceptance import public_raw, public_text

ROOT = Path(__file__).resolve().parents[1]


def text(path):
    return " ".join((ROOT / path).read_text().split())


class WriterMessageHandoffTest(unittest.TestCase):
    def test_plan_routes_three_message_leaves(self):
        plan = text("plan-assistant-writing/references/message.md")
        self.assertIn("QA `prose`", plan)
        for verb in ("write", "edit", "analyze"):
            self.assertIn(f"`{verb}-message`", plan)
        self.assertIn("Message — email, chat reply", text("plan-assistant-writing/SKILL.md"))
        self.assertIn("Promotional mail remains copy", text("plan-assistant-writing/references/copy.md"))

    def test_dispatch_distinguishes_promotional_mail_from_correspondence(self):
        index = (ROOT / "plan-assistant-writing/SKILL.md").read_text()
        copy_row = next(line for line in index.splitlines() if "| Marketing copy —" in line)
        self.assertIn("promotional mail", copy_row)
        self.assertNotIn(", mail text", copy_row)
        message_row = next(line for line in index.splitlines() if "| Message —" in line)
        self.assertIn("email", message_row)
        self.assertIn("Direct correspondence or service notifications", text("plan-assistant-writing/references/copy.md"))

    def test_personal_context_does_not_expand_writer_authority(self):
        plan = text("plan-assistant-writing/references/message.md")
        self.assertIn("does not replace its People/Project permissions", plan)
        self.assertIn("only the necessary sanitized context", plan)
        self.assertIn("Writer does not perform contact lookups", plan)

    def test_message_gate_is_not_legacy_review_or_sending(self):
        gate = public_raw("index.md")
        served = gate.split("## Served message gate", 1)[1].split("## Outline gate", 1)[0]
        self.assertNotIn("scripts/lint.py", served)
        normalized = " ".join(served.split())
        self.assertIn("never legacy lint or four-pass counts", normalized)
        self.assertIn("Analysis is a report, not a new message", normalized)
        self.assertIn("NOT verified", normalized)

    def test_intent_and_unknown_state_survive_acceptance(self):
        prose = public_text("prose.md")
        self.assertIn("preserve accept/decline/defer decisions", prose)
        self.assertIn("available retry is not proof of safe repetition", prose)
        self.assertIn("Text acceptance is not sending approval", prose)
        self.assertIn("reports must not expose secrets", prose)

    def test_analysis_is_not_a_replacement_reply(self):
        prose = public_raw("prose.md")
        analysis = prose.split("## Message analysis (analyze-message)", 1)[1].split("## Unmapped requests", 1)[0]
        self.assertIn("report needs no new greeting", analysis)
        self.assertIn("unsolicited replacement message", analysis)
        execution = text("execute-assistant-writing/SKILL.md")
        self.assertIn("Acceptance never dispatches a message", execution)
        self.assertIn("message-analysis report must not be sent as a reply", execution)


if __name__ == "__main__":
    unittest.main()
