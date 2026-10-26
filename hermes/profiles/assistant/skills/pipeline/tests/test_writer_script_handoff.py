"""Script acceptance verifies text boundaries, not an imagined media result."""

from pathlib import Path
import unittest

from _public_writer_acceptance import public_raw, public_text

ROOT = Path(__file__).resolve().parents[1]


def text(path):
    return " ".join((ROOT / path).read_text().split())


class WriterScriptHandoffTest(unittest.TestCase):
    def test_plan_routes_script_operations_and_actual_consumer(self):
        plan = text("plan-assistant-writing/references/script.md")
        index = text("plan-assistant-writing/SKILL.md")
        self.assertIn("QA `script`", plan)
        for verb in ("write", "edit", "analyze"):
            self.assertIn(f"`{verb}-script`", plan)
            self.assertIn(f"`{verb}-script`", index)
        self.assertIn("Plain narration needs no scene table", plan)
        self.assertIn("not a rendered or synthesized artifact", plan)

    def test_gate_routes_analysis_before_draft_requirements(self):
        index = public_raw("index.md")
        served = index.split("## Served script gate", 1)[1].split("## Outline gate", 1)[0]
        self.assertNotIn("scripts/lint.py", served)
        self.assertIn("`analyze-script` uses its analysis-report branch", served)
        self.assertIn("never require the analysis report".lower(), served.lower())
        self.assertIn("Humanizer is explicit-request only", served)
        self.assertIn("NOT verified", served)

    def test_draft_gate_inspects_raw_exports_and_ids(self):
        gate = public_text("script.md")
        self.assertIn("raw speech file contains words only", gate)
        self.assertIn("retired IDs outside verbatim text", gate)
        self.assertIn("requester and consumer", gate)
        self.assertIn("a stale export is not the revised script", gate)
        self.assertIn("Old timing/media evidence may not cover revised words", gate)
        self.assertIn("Do not research new facts, render, synthesize or publish in QA", gate)

    def test_analysis_report_is_not_a_script_part(self):
        gate = public_raw("script.md")
        analysis = " ".join(gate.split("## Script analysis", 1)[1].split("## Evidence", 1)[0].split())
        self.assertIn("no new scenes, dialogue, speaker roster, narration export", analysis)
        self.assertIn("not a production part", analysis)
        self.assertIn("descriptions need not invent faults", analysis)

    def test_execution_preserves_approved_payload_and_timing_limits(self):
        execution = text("execute-assistant-writing/SKILL.md")
        for verb in ("write", "edit", "analyze"):
            self.assertIn(f"`{verb}-script`", execution)
        self.assertIn("approved raw spoken file, never a structured master", execution)
        self.assertIn("Text edits require renewed approval", execution)
        self.assertIn("analyze-script report is decision input, never a production part", execution)
        self.assertIn("sectioning or new takes need their own release", execution)


if __name__ == "__main__":
    unittest.main()
