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
        self.assertIn("Creator confirms the actual scope", plan)
        self.assertIn("not a live capability catalog", plan)
        self.assertFalse((PLAN / "character-music-video.md").exists())
        for directory in (EXECUTE, QA):
            self.assertFalse(any((directory / f"{name}.md").exists() for name in GUIDES))

    def test_questions_are_not_a_mandatory_production_form(self):
        plan = text(PLAN_ENTRY)
        self.assertIn("Ask only unresolved questions", plan)
        self.assertIn("not forms to make the user complete", plan)
        self.assertIn("valid consultation brief", plan)
        self.assertIn("needs no mandatory prior inquiry", plan)

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
        self.assertIn("An omitted permission is unknown, not yes", execute)
        self.assertIn("Missing permission blocks the affected operation", execute)

    def test_brief_and_transport_keep_client_boundary(self):
        execute = text(EXECUTE_ENTRY)
        for field in ("Goal:", "Context:", "Inputs:", "Deliverable:", "Constraints:", "Budget:"):
            self.assertIn(field, execute)
        self.assertIn('specialist_call(target="creator", ...)', execute)
        self.assertIn("never fill in Creator's hands forms yourself", execute)
        for hand in ("image-creator", "video-creator", "audio-creator"):
            self.assertIn(f"`{hand}`", execute)
        self.assertIn("never upgrade the pinned route in place", execute)
        self.assertIn("No repeating the first call", execute)

    def test_approval_relay_preserves_authority_and_identity(self):
        execute = text(EXECUTE_ENTRY)
        for phrase in (
            "SAME `target` and `conversation_id`", "Never self-compute",
            "A Budget line is not proposal approval",
            "new approval, not a silent continuation",
            "do not add a mandatory taste vote",
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
        self.assertIn("Producing media stays with Creator", plan)
        self.assertIn("Assessing, adding to, or improving managed hands reference catalogs", plan)
        self.assertIn("whether the user wants an asset or a managed reference change", plan)
        self.assertIn("not by words such as card, icon, style or reference alone", plan)
        target = (ROOT / "plan-assistant-engineering/references/existing-change.md").resolve()
        self.assertTrue(target.is_file(), target)

    def test_dependencies_and_publish_are_not_duplicated(self):
        plan = text(PLAN_ENTRY)
        self.assertIn("do not open a duplicate Writer or hands job", plan)
        self.assertIn("passed unchanged", plan)
        self.assertIn("Keep service-side drafts with marketing Execute", plan)
        explainer = text(PLAN / "explainer-video.md")
        self.assertIn("does not mean \"no character\"", explainer)
        self.assertIn("do not duplicate their requests", explainer)
        self.assertIn("not a completed musical deliverable", text(PLAN / "music-video.md"))

    def test_legacy_is_separate_and_never_a_failure_fallback(self):
        for entry in (PLAN_ENTRY, EXECUTE_ENTRY, QA_ENTRY):
            directory = entry.parent / "references"
            self.assertIn("(references/legacy/index.md)", text(entry))
            self.assertTrue((directory / "legacy/index.md").is_file())
        self.assertIn("not a fallback after a served failure", text(PLAN_ENTRY))
        for name in ("generated-video", "html-motion", "composite-media", "pixel-art", "pixel-video"):
            self.assertFalse((PLAN / f"{name}.md").exists())
            self.assertIn("legacy", text(PLAN / f"legacy/{name}.md").lower())
        qa = (QA / "legacy/index.md").read_text(encoding="utf-8")
        for name in re.findall(r"^\| .*?\| `([^`]+\.md)` \|", qa, re.M):
            self.assertTrue((QA / "legacy" / name).is_file(), name)

    def test_retired_house_rules_have_no_active_references(self):
        for entry in (PLAN_ENTRY, EXECUTE_ENTRY, QA_ENTRY):
            for path in entry.parent.rglob("*.md"):
                self.assertNotRegex(
                    path.read_text(encoding="utf-8"),
                    r"house-formats/|expressions/|production-facts\.md",
                    path,
                )
        self.assertNotIn("voice-line sets", text(PLAN / "legacy/asset-set.md"))

    def test_cards_stay_closed_and_unchanged(self):
        execute = EXECUTE_ENTRY.read_text(encoding="utf-8")
        frontmatter = execute.split("---", 2)[1]
        self.assertEqual(re.findall(r"^  - name: (\S+)$", frontmatter, re.M),
                         ["anchored-image-batch", "deterministic-render"])
        self.assertEqual(re.findall(r"assignee: (\S+)", frontmatter), ["creator", "creator"])
        self.assertEqual(re.findall(r"runtime_cap: (\d+)", frontmatter), ["1800", "900"])
        for path in (EXECUTE / "legacy").rglob("*.md"):
            self.assertFalse(path.read_text(encoding="utf-8").startswith("---\n"))

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
        self.assertIn("Stay in Execute on normal Creator completion", execute)
        self.assertIn("do not load `qa-assistant-creative`", execute)
        self.assertIn("Required failures still block final readiness and dependent use", execute)
        self.assertIn("attach the actual viewable file", execute)
        self.assertIn("composition AND progression", execute)
        ops = text(EXECUTE / "media-ops.md")
        self.assertIn("No separate QA acceptance is required before showing a candidate", ops)
        self.assertNotIn("qa-assistant-creative/SKILL.md", ops)
        self.assertIn("only for an explicit user inspection request", qa)
        self.assertIn("Do not dispatch repairs from this inspection", qa)
        self.assertIn("Legacy is not an exception that restores routine Assistant QA",
                      text(EXECUTE / "legacy/index.md"))
        self.assertIn("ONLY for explicitly user-requested inspection", text(QA / "legacy/index.md"))
        cards = text(ROOT / "references/execute/kanban-lite.md")
        self.assertIn("Creative: use `../../execute-assistant-creative/SKILL.md` direct delivery", cards)

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
        self.assertIn("human decision with source and exact affected proposal/preview, "
                      "your implementation choice within the grant, or an unapproved suggestion", execute)
        self.assertIn("attributes messages to an agent; this helps inspection, not authorization", execute)
        self.assertIn("An agent DECISION or a source label cannot turn a weakened requirement "
                      "into human approval", execute)
        self.assertIn("Compare any proposed compromise with the original purpose, audience "
                      "and must-keep conditions before responding to Creator", execute)

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
        # The one continuation is a reconcile-only turn on the owning session.
        self.assertIn('kind="reconcile"', resident)
        self.assertIn("`opencode_call` is refused", resident)
        self.assertIn("nothing is edited or committed", resident)
        self.assertIn("not with the interrupted transcript", resident)
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
        build = text(root / "profiles/creator/skills/creator-pipeline/build-creator/references/image-creator/card.md")
        self.assertIn('authored-layout/custom-style Card', build)
        self.assertIn('kind="work"', build)


if __name__ == "__main__":
    unittest.main()
