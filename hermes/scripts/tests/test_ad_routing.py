"""Static contract tests for the video-creator `ad` hands family and its
routing through Creator (create-ad / analyze-ad). These are contract tests
against tracked config/skill text, not a claim that any runtime path was
actually exercised end to end (no LLM/gateway calls are made)."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

import yaml

HERMES_ROOT = Path(__file__).resolve().parents[2]

VALIDATOR_SCRIPT = HERMES_ROOT / "scripts" / "validate-profile-skills.py"
VALIDATOR_SPEC = importlib.util.spec_from_file_location("validate_profile_skills_ad", VALIDATOR_SCRIPT)
assert VALIDATOR_SPEC and VALIDATOR_SPEC.loader
VALIDATOR = importlib.util.module_from_spec(VALIDATOR_SPEC)
VALIDATOR_SPEC.loader.exec_module(VALIDATOR)

VIDEO_PIPELINE = HERMES_ROOT / "profiles" / "video-creator" / "skills" / "video-creator-pipeline"
CREATE_AD = VIDEO_PIPELINE / "create" / "ad" / "SKILL.md"
ANALYZE_AD = VIDEO_PIPELINE / "analyze" / "ad" / "SKILL.md"


# ── leaf validator: names, verbs, shared "ad" subject within one hands ──────

class LeafValidatorTest(unittest.TestCase):
    def test_create_and_analyze_ad_are_valid_leaves(self) -> None:
        errors: list[str] = []
        leaves = VALIDATOR.validate_hands_leaves(VIDEO_PIPELINE, "video-creator", errors)
        self.assertEqual([], errors)
        self.assertEqual(CREATE_AD, leaves["create-ad"])
        self.assertEqual(ANALYZE_AD, leaves["analyze-ad"])

    def test_ad_verbs_are_in_the_closed_set(self) -> None:
        self.assertIn("create", VALIDATOR.HANDS_VERBS)
        self.assertIn("analyze", VALIDATOR.HANDS_VERBS)

    def test_shared_ad_subject_within_video_creator_is_not_a_conflict(self) -> None:
        """create-ad and analyze-ad both name the subject `ad`; the subject
        uniqueness check is per-hands-profile, so two leaves of the SAME
        profile sharing a subject must not be flagged."""
        errors: list[str] = []
        VALIDATOR.validate_hands_subjects(
            {"video-creator": {"create-ad": CREATE_AD, "analyze-ad": ANALYZE_AD}}, errors)
        self.assertEqual([], errors)

    def test_ad_subject_owned_by_a_second_hands_profile_is_a_conflict(self) -> None:
        """The cross-hands uniqueness rule still fires when a DIFFERENT
        hands profile claims the same subject."""
        errors: list[str] = []
        VALIDATOR.validate_hands_subjects(
            {"video-creator": {"create-ad": CREATE_AD},
             "image-creator": {"generate-ad": Path("/fake/image-creator/generate/ad/SKILL.md")}},
            errors)
        self.assertEqual(1, len(errors))
        self.assertIn("ad", errors[0])

    def test_no_other_hands_profile_actually_claims_the_ad_subject(self) -> None:
        """Regression guard against a real cross-hands collision: run the
        subject check across every hands profile currently in the repo."""
        errors: list[str] = []
        leaves_by_profile: dict[str, dict[str, Path]] = {}
        for profile_dir in (HERMES_ROOT / "profiles").iterdir():
            pipeline = profile_dir / "skills" / f"{profile_dir.name}-pipeline"
            if not pipeline.is_dir():
                continue
            sub_errors: list[str] = []
            leaves = VALIDATOR.validate_hands_leaves(pipeline, profile_dir.name, sub_errors)
            if leaves:
                leaves_by_profile[profile_dir.name] = leaves
        VALIDATOR.validate_hands_subjects(leaves_by_profile, errors)
        self.assertEqual([], errors)


# ── creator + video-creator config/pipeline describe create-ad / analyze-ad ─

class CreatorAndVideoConfigTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.creator_config = yaml.safe_load((HERMES_ROOT / "profiles/creator/config.yaml").read_text())
        cls.video_config = yaml.safe_load((HERMES_ROOT / "profiles/video-creator/config.yaml").read_text())
        cls.video_profile = (HERMES_ROOT / "profiles/video-creator/profile.yaml").read_text()
        cls.creator_prompt = cls.creator_config["agent"]["system_prompt"]
        cls.video_prompt = cls.video_config["agent"]["system_prompt"]
        cls.pipeline_skill = (HERMES_ROOT / "profiles/creator/skills/creator-pipeline/SKILL.md").read_text()
        refs = HERMES_ROOT / "profiles/creator/skills/creator-pipeline/references"
        cls.plan_index_md = (refs / "plan/index.md").read_text()
        cls.plan_ad_md = (refs / "plan/video-creator/ad.md").read_text()
        cls.plan_md = cls.plan_index_md + cls.plan_ad_md
        cls.build_index_md = (refs / "build/index.md").read_text()
        cls.build_ad_md = (refs / "build/video-creator/ad.md").read_text()
        cls.build_md = cls.build_index_md + cls.build_ad_md
        cls.qa_index_md = (refs / "quality-assurance/index.md").read_text()
        cls.qa_ad_md = (refs / "quality-assurance/video-creator/ad.md").read_text()
        cls.qa_md = cls.qa_index_md + cls.qa_ad_md
        cls.capabilities_md = (refs / "capabilities.md").read_text()

    def test_creator_config_and_pipeline_name_both_leaves(self) -> None:
        for text in (self.creator_prompt, self.plan_md,
                     self.build_md, self.qa_md, self.capabilities_md):
            self.assertIn("create-ad", text)
            self.assertIn("analyze-ad", text)

    def test_root_routes_to_phase_indexes_which_link_the_ad_subject(self) -> None:
        """Root SKILL.md (v8) no longer enumerates every leaf; it routes to
        each phase's index, and those indexes link the exact ad.md subject
        reference exercised by the other assertions in this class."""
        for path in ("references/plan/index.md", "references/build/index.md",
                     "references/quality-assurance/index.md"):
            self.assertIn(path, self.pipeline_skill)
        for index_text in (self.plan_index_md, self.build_index_md, self.qa_index_md):
            self.assertIn("(video-creator/ad.md)", index_text)

    def test_video_root_and_profile_describe_both_leaves(self) -> None:
        for text in (self.video_prompt, self.video_profile):
            self.assertIn("create-ad", text)
            self.assertIn("analyze-ad", text)

    def test_ad_leaves_always_use_specialist_kind_work(self) -> None:
        self.assertIn('always specialist kind="work"', self.creator_prompt)
        self.assertIn("video-creator's `create-ad` / `analyze-ad`", self.build_md)
        self.assertIn('kind="work")`; approval turns or bounded multi-pass evidence extraction, not an inquiry',
                       self.build_md)
        # Root (v8) states no per-leaf kind="work" rule itself; it routes to
        # Build's index, which carries the general specialist_call
        # kind="work" contract that ad's own transport row (asserted above)
        # follows.
        self.assertIn("references/build/index.md", self.pipeline_skill)
        self.assertIn('kind="work")`; the tool starts the resident session you supervise',
                       self.build_index_md)

    def test_no_raw_a2a_path_for_ad_specialist_calls(self) -> None:
        """create-ad / analyze-ad are only ever reached via specialist_call,
        never a raw a2a_call / direct URL / resident script."""
        self.assertIn("Specialist requests use specialist_call, never raw a2a_call, a direct\n"
                       "resident script, or a peer URL.", self.creator_prompt)
        self.assertIn("never an arbitrary profile,\n"
                       "URL, raw `a2a_call`, or direct resident script for new work.", self.build_md)
        self.assertNotIn("a2a_call(", self.build_md)
        self.assertNotIn("a2a_call(", self.plan_md)

    def test_generate_ad_and_pv_are_unimplemented(self) -> None:
        self.assertIn("Generate-ad and PV are not served; never substitute MV.", self.creator_prompt)
        self.assertIn("generate-ad/PV are not served\nyet; do not quietly replace them with MV or clip "
                       "production.", self.plan_md)
        self.assertIn("Only create-ad and analyze-ad are served; generate-ad and a PV leaf are not yet\n"
                       "implemented.", self.capabilities_md)
        profiles_md = (HERMES_ROOT / "PROFILES.md").read_text()
        self.assertIn("`generate-ad` and PV are planned, not advertised capabilities.", profiles_md)
        # Root (v8) no longer states served/unserved status per family; it
        # points Plan at capabilities.md, which carries that status (asserted
        # above).
        self.assertIn("[capabilities](references/capabilities.md)", self.pipeline_skill)


# ── human vs assistant brief: contract text only, not a live-runtime claim ──

class ClientOriginContractTest(unittest.TestCase):
    """Runtime caller context precedes presentation when Creator fills a form.
    These assertions only check the documented contract text; they make no
    claim about live routing behavior, LLM output, or gateway state."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.pipeline_skill = (HERMES_ROOT / "profiles/creator/skills/creator-pipeline/SKILL.md").read_text()
        cls.creator_prompt = yaml.safe_load(
            (HERMES_ROOT / "profiles/creator/config.yaml").read_text())["agent"]["system_prompt"]

    def test_assistant_brief_maps_to_a_batched_q_block(self) -> None:
        for text in (self.pipeline_skill, self.creator_prompt):
            self.assertIn("Q<n>:", text)
        self.assertIn(
            "Its\n  brief (`Goal:` / `Context:` / `Inputs:` / `Deliverable:` /\n"
            "  `Constraints:` / `Budget:`) is parsed into the form; what it leaves\n"
            "  unsettled returns as ONE `Q<n>:` text block (2-4 options +\n"
            "  recommendation).",
            self.pipeline_skill,
        )

    def test_human_client_uses_clarify_never_a_typed_q_block(self) -> None:
        self.assertIn("clarify", self.pipeline_skill)
        self.assertIn(
            "Questions go through the\n  `clarify` tool (native buttons), one call per round, one entry per\n"
            "  open form field, the field's options as choices with your\n"
            "  recommendation first. Never a typed `Q<n>:` list at a human.",
            self.pipeline_skill,
        )

    def test_conversational_agent_input_does_not_become_human_approval(self) -> None:
        body = " ".join(self.pipeline_skill.split())
        prompt = " ".join(self.creator_prompt.split())
        self.assertIn("never establish human origin or approval", body)
        self.assertIn("even when its current message is conversational", body)
        self.assertIn("Use runtime caller context before message shape", prompt)
        self.assertIn("conversational prose does not prove human origin", prompt)
        for text in (body, prompt):
            self.assertNotIn("conversational = a human", text)


if __name__ == "__main__":
    unittest.main()
