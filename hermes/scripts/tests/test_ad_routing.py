"""Static contract tests for the video-creator `ad` hands family and its
routing through Creator (create-ad / analyze-ad). These are contract tests
against tracked config/skill text, not a claim that any runtime path was
actually exercised end to end (no LLM/gateway calls are made)."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

import hermes_yaml as yaml

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


# ── commissioning + video-creator config/pipeline describe create-ad / analyze-ad ─

ASSISTANT_CREATIVE = (HERMES_ROOT / "profiles/assistant/skills/assistant-pipeline/"
                      "execute-assistant-creative")
CREATOR_PIPELINE = HERMES_ROOT / "profiles/creator/skills/creator-pipeline"


class CommissioningAndVideoConfigTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.creator_config = yaml.safe_load((HERMES_ROOT / "profiles/creator/config.yaml").read_text())
        cls.assistant_config = yaml.safe_load(
            (HERMES_ROOT / "profiles/assistant/config.example.yaml").read_text())
        cls.video_config = yaml.safe_load((HERMES_ROOT / "profiles/video-creator/config.yaml").read_text())
        cls.video_profile = (HERMES_ROOT / "profiles/video-creator/profile.yaml").read_text()
        cls.video_prompt = cls.video_config["agent"]["system_prompt"]
        cls.commission_md = (ASSISTANT_CREATIVE / "references/ad.md").read_text()
        cls.commission_skill = (ASSISTANT_CREATIVE / "SKILL.md").read_text()
        cls.advisor_md = (CREATOR_PIPELINE / "references/video-creator/ad.md").read_text()
        cls.advisor_kernel = (CREATOR_PIPELINE / "SKILL.md").read_text()

    def test_commissioning_and_advisor_name_both_leaves(self) -> None:
        for text in (self.commission_md, self.advisor_md):
            self.assertIn("create-ad", text)
            self.assertIn("analyze-ad", text)

    def test_commissioning_leaves_table_and_kernel_link_the_ad_subject(self) -> None:
        self.assertIn("## Leaves", self.commission_md)
        self.assertIn("| `create-ad` |", self.commission_md)
        self.assertIn("| `analyze-ad` |", self.commission_md)
        self.assertIn("(references/video-creator/ad.md)", self.advisor_kernel)

    def test_video_root_and_profile_describe_both_leaves(self) -> None:
        for text in (self.video_prompt, self.video_profile):
            self.assertIn("create-ad", text)
            self.assertIn("analyze-ad", text)

    def test_ad_leaves_always_use_specialist_kind_work(self) -> None:
        self.assertIn("video-creator's `create-ad` / `analyze-ad`", self.commission_md)
        self.assertIn('kind="work")`; approval turns or bounded multi-pass evidence extraction, not an inquiry',
                      self.commission_md)
        self.assertIn('kind="work"', self.commission_md.split("## Transport", 1)[1])
        self.assertIn('target="<hands>", message=<the text>, kind="work"', self.commission_skill)

    def test_no_raw_a2a_path_for_ad_specialist_calls(self) -> None:
        """create-ad / analyze-ad are only ever reached via specialist_call,
        never a raw a2a_call / direct URL / resident script."""
        self.assertIn("specialist_call(target=\"video-creator\"", self.commission_md)
        self.assertNotIn("a2a_call(", self.commission_md)
        self.assertNotIn("a2a_call(", self.commission_skill)
        self.assertNotIn("a2a_call(", self.advisor_md)

    def test_assistant_commissions_video_creator_and_creator_cannot(self) -> None:
        targets = self.assistant_config["specialist_call"]["resident_targets"]
        self.assertIn("video-creator", targets)
        self.assertEqual(["researcher"], self.creator_config["specialist_call"]["resident_targets"])
        self.assertEqual(["researcher"], list(self.creator_config["a2a_agents"]))
        self.assertNotIn("video-creator", self.creator_config["a2a_agents"])
        self.assertNotIn("image_gen", self.creator_config["toolsets"])
        self.assertNotIn("video_gen", self.creator_config["toolsets"])

    def test_generated_ad_is_a_clip_to_ad_chain_and_pv_is_promotion(self) -> None:
        commission = " ".join(self.commission_md.split())
        self.assertIn("A generated ad is not a leaf of its own", commission)
        self.assertIn("text-free generate-clip shots", commission)
        self.assertIn("A PV authored from supplied material is create-promotion", commission)
        self.assertIn("Never silently route a requested generated ad or PV to MV.", commission)
        self.assertIn("A generated ad (its picture drawn by a video model) is a chain of existing units, not one leaf.",
                      commission)
        self.assertIn("they never stand in for the real product", commission)
        advisor = " ".join(self.advisor_md.split())
        self.assertIn("never stand in for the real product", advisor)
        self.assertIn("Introducing a brand, world or qualities without one action: [promotion]", advisor)
        profiles_md = " ".join((HERMES_ROOT / "docs" / "hands" / "video.md").read_text().split())
        self.assertIn("A generated ad is not a leaf", profiles_md)
        self.assertNotIn("generate-ad` is planned", profiles_md)
        leaves = {p.parent.name for p in (HERMES_ROOT / "profiles/video-creator/skills/video-creator-pipeline")
                  .glob("generate/*/SKILL.md")}
        self.assertNotIn("ad", leaves)


# ── agent-authored handoff vs human decision: contract text only ───────────

class ClientOriginContractTest(unittest.TestCase):
    """The Assistant is the only client of the hands and of Creator; a
    specialist handoff is agent-authored and never a human approval. These
    assertions only check the documented contract text; they make no claim
    about live routing behavior, LLM output, or gateway state."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.kernel = (CREATOR_PIPELINE / "SKILL.md").read_text()
        cls.commission_skill = (ASSISTANT_CREATIVE / "SKILL.md").read_text()

    def test_creator_returns_one_q_block_to_the_assistant(self) -> None:
        body = " ".join(self.kernel.split())
        self.assertIn("a question back is one `Q<n>:` text block with 2-4 options and a recommendation", body)

    def test_creator_never_uses_clarify(self) -> None:
        self.assertIn("`clarify`", self.kernel.split("<Boundaries>", 1)[1])
        self.assertIn("no generation, TTS, hands calls, `clarify`", " ".join(self.kernel.split()))

    def test_agent_authored_handoff_does_not_become_human_approval(self) -> None:
        body = " ".join(self.kernel.split())
        self.assertIn("A runtime specialist handoff is agent-authored, even when conversational", body)
        self.assertIn("a choice is the user's only when the Assistant relays it as such", body)
        commission = " ".join(self.commission_skill.split())
        self.assertIn("The user's pick is a human decision; record it separately from Creator's recommendation",
                      commission)
        self.assertIn("Creator's output is advice: it approves nothing", commission)


if __name__ == "__main__":
    unittest.main()
