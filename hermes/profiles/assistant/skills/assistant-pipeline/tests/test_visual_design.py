"""Paired planning contracts and actual helper output, not model-quality proof."""

import importlib.util
import hashlib
import json
from pathlib import Path
import unittest

from _pair import PUBLIC_ROOT


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "plan-assistant-creative"


def text(path):
    return " ".join(path.read_text().split())


class VisualDesignTest(unittest.TestCase):
    def test_compact_review_retains_complete_pre_authored_design(self):
        guide = text(PLAN / "references/video-design.md")
        for phrase in ("concise viewing overview", "Every change retains a visible intermediate preview",
                       "every open item a visible concise summary", "Multiple panels may stay open",
                       "Opening a panel never invokes a model", "Detailed design lives in `spec.html`, never omitted",
                       "The user reads boards, not prose",
                       "--review <absolute-review.json>", "Review ID", "schema version 2",
                       "never draw or describe them by hand", "one stable `key` per on-screen object",
                       "Open items are design questions that need the user's judgment",
                       "never written into `open_items` or the document",
                       "procedural status the document omits"):
            self.assertIn(phrase, guide)
        execute = text(ROOT / "execute-assistant-creative/SKILL.md")
        self.assertIn("short viewing layer never replaces full design data", execute)
        self.assertIn("orange motion marks are derived reading aids, not part of the film", execute)

    def test_new_video_passes_intent_and_timeline_is_opt_in(self):
        entry = text(PLAN / "SKILL.md")
        guide = text(PLAN / "references/video-design.md")
        execute = text(ROOT / "execute-assistant-creative/SKILL.md")
        self.assertIn("do NOT author a visual design, timeline or storyboard yourself", entry)
        self.assertIn("the producer owns the visual story, which the user approves as its storyboard", entry)
        self.assertIn("only when the user explicitly asks you for a designed timeline", entry)
        self.assertIn("applies only when the user explicitly asks for an Assistant-designed timeline", guide)
        self.assertIn("send intent, not a design", execute)
        self.assertIn("Only when the user explicitly asked for a designed timeline and agreed it", execute)
        self.assertIn("Do not ask the user to supply artistic vocabulary", guide)
        self.assertIn("without waiting for the user to ask", guide)
        self.assertIn("planning-only HTML timeline", text(ROOT / "references/plan/index.md"))
        self.assertIn("only when the user explicitly asks for one", text(ROOT / "references/plan/index.md"))
        self.assertIn("the producer designs the storyboard the user approves", text(ROOT / "SKILL.md"))

    def test_detail_and_exceptions_remain_explicit(self):
        guide = text(PLAN / "references/video-design.md")
        for phrase in ("before/during/after", "deliberate", "typography", "occlusion",
                       "not the final media", "standalone written script/storyboard still belongs to Writer",
                       "do not invent a duration", "frozen render resumes", "unsettled feasibility is reported in the message"):
            self.assertIn(phrase, guide)
        self.assertIn("Every event", (PUBLIC_ROOT /
                      "hermes/profiles/assistant/scripts/creative-timeline.md").read_text())

    def test_sources_become_applied_decisions_not_just_names(self):
        research = text(PLAN / "references/reference-research.md")
        for phrase in ("Ordinary Folk", "BUCK", "Linear's redesign", "Raycast's UI update",
                       "Art of the Title", "scene/event/component", "not a design decision",
                       "not automatically", "not a stored recipe"):
            self.assertIn(phrase, research)
        self.assertIn("reference-interpretation", text(PLAN / "references/video-design.md"))

    def test_delivery_and_handoff_do_not_grant_production(self):
        guide = text(PLAN / "references/video-design.md")
        execute = text(ROOT / "execute-assistant-creative/SKILL.md")
        for phrase in ("Attach `timeline.html` in Telegram as a document", "client-dependent",
                       "not spend, upload", "actual user message", "Each revision gets a new directory"):
            self.assertIn(phrase, guide)
        for phrase in ("JSON, HTML timeline and identity receipt", "not an invented hands form field",
                       "marked unapproved/discussion-only", "never silently accept a flat zoom"):
            self.assertIn(phrase, execute)

    def test_paired_helper_implements_the_documented_contract(self):
        helper = PUBLIC_ROOT / "hermes/profiles/assistant/scripts/creative-timeline.py"
        loader = importlib.util.spec_from_file_location("paired_timeline", helper)
        module = importlib.util.module_from_spec(loader)
        loader.loader.exec_module(module)
        document = helper.with_suffix(".md").read_text()
        raw = document.split("```json\n", 1)[1].split("\n```", 1)[0].encode()
        spec = json.loads(raw)
        output = module.render(module.validate(spec), hashlib.sha256(raw).hexdigest())
        self.assertIn("Intermediate reveal", output)
        self.assertIn("Component designs", output)
        self.assertIn("Discussion only", output)
        spec["scenes"][0]["keyframes"].pop(1)
        with self.assertRaisesRegex(ValueError, "intermediate"):
            module.validate(spec)


if __name__ == "__main__":
    unittest.main()
