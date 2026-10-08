"""Client reference contracts, not live LLM, rendering or gateway evidence.

Run: HERMES_PRIVATE_ROOT=<paired-private-checkout> python3 -m unittest discover -s
hermes/profiles/assistant/skills/assistant-pipeline/tests
"""

import importlib.util
from pathlib import Path
import re
import tempfile
import unittest

from _pair import PUBLIC_ROOT

ROOT = Path(__file__).resolve().parents[1]
PLAN_ENTRY = ROOT / "plan-assistant-creative/SKILL.md"
PLAN = PLAN_ENTRY.parent / "references"
EXECUTE_ENTRY = ROOT / "execute-assistant-creative/SKILL.md"
EXECUTE = EXECUTE_ENTRY.parent / "references"
QA_ENTRY = ROOT / "qa-assistant-creative/SKILL.md"
QA = QA_ENTRY.parent / "references"
GUIDES = {
    "icon", "emoji", "mascot", "reimagine", "kit", "card", "clip",
    "music-video", "ad", "tour", "explainer-video", "speech", "sfx",
    "music", "mix", "ui-design",
}


def text(path):
    return " ".join(path.read_text(encoding="utf-8").split())


class CreativeHandoffTest(unittest.TestCase):
    def test_initial_client_guides_are_substantive_and_routed(self):
        index = text(PLAN_ENTRY)
        for guide in sorted(GUIDES):
            with self.subTest(guide=guide):
                path = PLAN / f"{guide}.md"
                body = path.read_text(encoding="utf-8")
                self.assertIn(f"(references/{guide}.md)", index)
                for heading in ("Use", "Client decisions", "References", "Acceptance"):
                    section = body.split(f"## {heading}\n", 1)[1].split("\n## ", 1)[0]
                    self.assertGreater(len(section.split()), 20, (guide, heading))
                self.assertNotRegex(
                    body,
                    r"metadata\.hermes|approval_sha256|max_calls|image_generate|"
                    r"video_generate|\bengine:|\d{3,4}[x\u00d7]\d{3,4}",
                )

    def test_guides_are_not_a_capability_catalog(self):
        plan = text(PLAN_ENTRY)
        self.assertIn("A missing guide is NOT evidence", plan)
        self.assertIn("the installed hands leaves confirm the actual scope", plan)
        self.assertIn("not a live capability catalog", plan)
        self.assertFalse((PLAN / "character-music-video.md").exists())
        self.assertFalse(QA.exists() and any((QA / f"{name}.md").exists() for name in GUIDES))
        for subject in GUIDES - {"ui-design"}:
            self.assertTrue((EXECUTE / f"{subject}.md").is_file(), subject)

    def test_questions_are_not_a_mandatory_production_form(self):
        plan = text(PLAN_ENTRY)
        self.assertIn("Ask only unresolved questions", plan)
        self.assertIn("not forms to make the user complete", plan)
        self.assertIn("An incomplete creative direction is a valid brief for Creator", plan)
        self.assertIn("Commission directly when the user's own words settle every required field",
                      text(EXECUTE_ENTRY))

    def test_reference_search_is_conditional_and_research_can_finish(self):
        research = text(PLAN / "reference-research.md")
        self.assertIn("Skip extra searching", research)
        self.assertIn("2-4 candidates overall", research)
        self.assertIn("A research-only request ends with the comparison", research)
        self.assertIn("A search snippet is only a lead", research)
        self.assertIn("mark it uninspected", research)
        self.assertIn("suggested:", research)
        self.assertIn("user-decided:", research)
        self.assertIn("open:", research)

    def test_reference_evidence_does_not_authorize_upload(self):
        research = text(PLAN / "reference-research.md")
        self.assertIn("inspiration only; production reuse/upload not authorized", research)
        self.assertIn("Neither Assistant's brief shape nor a capture path conveys consent", research)
        execute = text(EXECUTE_ENTRY)
        self.assertIn("explicit consent for that asset and operation", execute)
        self.assertIn('A path, a public URL, a direction choice or "use this" is not consent', execute)
        self.assertIn("an omitted permission is unknown, not yes", execute)
        self.assertIn("Missing permission blocks the affected operation", execute)
        self.assertIn("Research examples are inspiration, never production inputs", execute)

    def test_handoff_and_transport_keep_client_boundary(self):
        execute = text(EXECUTE_ENTRY)
        self.assertIn("You are the only client of the media hands", execute)
        for line in ("skill: <verb>-<subject>", "intent: new | revise", "deliver: <absolute durable directory>",
                     "budget: <grant>", "form:"):
            self.assertIn(line, execute)
        self.assertIn('specialist_call(target="creator", kind="inquiry")', execute)
        self.assertIn("Never send a design of your own for it to fill in", execute)
        for hand in ("image-creator", "video-creator", "audio-creator"):
            self.assertIn(f"`{hand}`", execute)
        self.assertIn('specialist_call(target="<hands>", message=<the text>, kind="work")', execute)
        self.assertIn("Transport grants nothing", execute)
        self.assertIn("never retry an unknown result or switch backends", execute)
        self.assertIn("never add form keys", execute)

    def test_approval_relay_preserves_authority_and_identity(self):
        execute = text(EXECUTE_ENTRY)
        for phrase in (
            "relay the user's decision in the same conversation",
            "Never compute, refresh or invent a hash",
            "A Budget line is not proposal approval, and proposal approval is not more spend",
            "An approved study is not an approved final",
            "Never invent an approval",
        ):
            self.assertIn(phrase, execute)

    def test_analysis_preview_and_final_are_distinct(self):
        qa = text(QA_ENTRY)
        self.assertIn("Analysis findings can be the final deliverable", qa)
        self.assertIn("A proposal/preview is an approval stop", qa)
        self.assertIn("Never present an input or reference example", qa)
        self.assertIn("rather than mandating duplicate measurements", qa)
        self.assertIn("Required failures block acceptance", qa)
        self.assertIn("not a listening verdict", qa)

    def test_hands_reference_catalog_routes_to_engineering(self):
        plan = text(PLAN_ENTRY)
        self.assertIn("(../plan-assistant-engineering/references/existing-change.md)", plan)
        self.assertIn("Producing media stays with the hands", plan)
        self.assertIn("Assessing, adding to, or improving managed hands reference catalogs", plan)
        self.assertIn("whether the user wants an asset or a managed reference change", plan)
        self.assertIn("not by words such as card, icon, style or reference alone", plan)
        target = (ROOT / "plan-assistant-engineering/references/existing-change.md").resolve()
        self.assertTrue(target.is_file(), target)

    def test_dependencies_and_publish_are_not_duplicated(self):
        plan = text(PLAN_ENTRY)
        self.assertIn("never opens a duplicate job for the same unit", plan)
        self.assertIn("passed unchanged", plan)
        self.assertIn("Keep service-side drafts with marketing Execute", plan)
        explainer = text(PLAN / "explainer-video.md")
        self.assertIn("does not mean \"no character\"", explainer)
        self.assertIn("do not duplicate their requests", explainer)
        self.assertIn("not a completed musical deliverable", text(PLAN / "music-video.md"))

    def test_legacy_shelves_are_gone_and_never_a_fallback(self):
        for entry in (PLAN_ENTRY, EXECUTE_ENTRY, QA_ENTRY):
            self.assertFalse((entry.parent / "references/legacy").exists(), entry)
            self.assertNotIn("references/legacy", text(entry))
        self.assertIn("never a fallback after a failed current Card job", text(PLAN / "card.md"))
        self.assertIn("fall back to an archived method", text(EXECUTE_ENTRY))
        for name in ("generated-video", "html-motion", "composite-media", "pixel-art", "pixel-video"):
            self.assertFalse((PLAN / f"{name}.md").exists())

    def test_retired_house_rules_have_no_active_references(self):
        for entry in (PLAN_ENTRY, EXECUTE_ENTRY, QA_ENTRY):
            for path in entry.parent.rglob("*.md"):
                self.assertNotRegex(
                    path.read_text(encoding="utf-8"),
                    r"house-formats/|expressions/|production-facts\.md",
                    path,
                )

    def test_creative_has_no_card_units(self):
        execute = EXECUTE_ENTRY.read_text(encoding="utf-8")
        frontmatter = execute.split("---", 2)[1]
        self.assertNotIn("card_units", frontmatter)
        self.assertNotIn("assignee:", frontmatter)
        self.assertNotIn("runtime_cap", frontmatter)

    def test_retention_does_not_delete_frozen_work(self):
        ops = text(EXECUTE / "media-ops.md")
        self.assertIn("Acceptance is not blanket permission", ops)
        self.assertIn("frozen bundle, proposal, receipt or original input", ops)

    def test_common_modes_preserve_creative_approval_and_evidence_rules(self):
        plan = text(ROOT / "references/plan/index.md")
        self.assertNotIn("There is no second approval gate", plan)
        self.assertIn("does not waive a capability's later exact-proposal", plan)
        self.assertIn("consultation and reference research alone authorize no production", plan)
        qa = text(ROOT / "references/quality-assurance/index.md")
        self.assertIn("do not apply this inspection floor or feedback loop to ordinary completions", qa)
        self.assertIn("does not authorize deletion of original inputs", qa)

    def test_normal_creative_completion_delivers_without_broker_inspection(self):
        # Static routing contract, not a real-model selection test.
        root = text(ROOT / "SKILL.md")
        execute = text(EXECUTE_ENTRY)
        qa = text(QA_ENTRY)
        self.assertIn("Plan -> Execute -> Deliver", root)
        self.assertIn("Other domains' QA is unchanged", root)
        self.assertIn("Stay in Execute on normal completion", execute)
        self.assertIn("do not load `qa-assistant-creative`", execute)
        self.assertIn("A required failure still blocks final readiness and dependent use", execute)
        self.assertIn("attach the actual file when supported", execute)
        self.assertIn("composition and progression", execute)
        ops = text(EXECUTE / "media-ops.md")
        self.assertIn("No separate QA acceptance is required before showing a candidate", ops)
        self.assertNotIn("qa-assistant-creative/SKILL.md", ops)
        self.assertIn("only for an explicit user inspection request", qa)
        self.assertIn("Do not dispatch repairs from this inspection", qa)

    def test_resident_handoff_distinguishes_outcome_from_authority_source(self):
        # Static contract check only, not live model behavior: the doc must
        # require separating WHO decided (with its source/scope) from the
        # agent's own outcome/choice, key meaning only, not an exact sentence.
        resident = text(ROOT / "references/execute/resident-sessions.md")
        self.assertIn("distinguishes your message from direct human input", resident)
        self.assertIn("does not authenticate a human approval", resident)
        self.assertIn("separate the user's actual decision (source, affected proposal and scope), "
                       "your implementation choice and an unapproved suggestion", resident)
        self.assertIn("or renew an old grant on resume", resident)

    def test_creative_continuation_preserves_human_authority(self):
        execute = text(EXECUTE_ENTRY)
        self.assertIn("The user's pick is a human decision; record it separately from "
                      "Creator's recommendation", execute)
        self.assertIn("Creator's output is advice: it approves nothing, releases no spend", execute)
        self.assertIn("Keep the original purpose, audience and must-keep conditions in every dependent form",
                      execute)
        resident = text(ROOT / "references/execute/resident-sessions.md")
        self.assertIn("separate the user's actual decision (source, affected proposal and scope), "
                      "your implementation choice and an unapproved suggestion", resident)

    def test_qa_version_binding_prevents_latest_saved_assumption(self):
        qa = text(ROOT / "references/quality-assurance/index.md")
        self.assertIn("Reconcile assembled versions", qa)
        self.assertIn("A local file, approved preview, completed transport and reopened remote "
                       "draft are distinct states", qa)
        self.assertIn("Do not claim the latest version was saved because an earlier one was", qa)

    def test_resident_reconcile_semantics_never_confirms_completion_or_resume(self):
        resident = text(ROOT / "references/execute/resident-sessions.md")
        self.assertIn("requires a recorded dead process group and no live, foreign or "
                       "unverifiable shell lock", resident)
        self.assertIn("stays as evidence, never removed", resident)
        self.assertIn("records `interrupted`, keeps effects `unknown`", resident)
        self.assertIn("never permits continuation of WORK in that conversation", resident)
        self.assertIn("Closing it is bookkeeping, not acceptance", resident)
        self.assertIn("A2A has no local liveness proof and remains blocked", resident)
        self.assertIn("Do not signal stored PIDs or steal locks", resident)

    def test_user_listening_is_attributed_criterion_evidence(self):
        speech = text(PLAN / "speech.md")
        self.assertIn("file/version, criterion and user's actual observation", speech)
        self.assertIn("not your own listening verdict", speech)
        self.assertIn("A general \"accepted\" is not a listening observation", text(QA_ENTRY))

    def test_card_revision_pairs_with_real_public_authored_path(self):
        # The Client remains outcome-led; execute the paired producer's validator
        # rather than only checking that two documents claim the feature exists.
        guide = text(PLAN / "card.md")
        self.assertIn("existing editable source", guide)
        self.assertIn("Your implementation choice is not the user's scope change", guide)
        self.assertNotIn("layout_html", guide)
        self.assertNotIn("copy_blocks", guide)
        root = PUBLIC_ROOT / "hermes"
        helper = root / "profiles/image-creator/skills/image-creator-pipeline/scripts/card.py"
        loader = importlib.util.spec_from_file_location("paired_card", helper)
        card = importlib.util.module_from_spec(loader)
        loader.loader.exec_module(card)
        with tempfile.TemporaryDirectory(prefix="paired-card-") as work:
            source = Path(work) / "layout.html"
            source.write_text('<style>h1{text-align:center;font-size:108px}</style>'
                              '<section data-card-tile="1"><h1 data-card-copy="title">Exact title</h1></section>')
            spec = {"title": "Exact title", "destination": "1500x600", "style": "Existing centered design",
                    "layout_html": str(source)}
            self.assertEqual(card.validate(spec, "create")["width"], 1500)
            source.write_text(source.read_text().replace("Exact title", "Changed title"))
            with self.assertRaisesRegex(ValueError, "copy differs"):
                card.validate(spec, "create")
        build = text(EXECUTE / "card.md")
        self.assertIn('authored-layout/custom-style Card', build)
        self.assertIn('kind="work"', build)


if __name__ == "__main__":
    unittest.main()
