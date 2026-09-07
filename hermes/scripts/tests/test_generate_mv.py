"""Coverage for video-creator's generate/mv hands leaf.

Structural checks reuse the same validator functions validate-profile-skills.py
runs. The `StaticContractLanguageTest` class at the bottom is DOCS-ONLY: it
confirms SKILL.md still states the safety contract in words, never that any
runtime enforces it. No live API/model/CLI calls are made anywhere here.
"""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "validate-profile-skills.py"
SPEC = importlib.util.spec_from_file_location("validate_profile_skills", SCRIPT)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)

PIPELINE_DIR = (
    VALIDATOR.HERMES_ROOT / "profiles" / "video-creator" / "skills" / "video-creator-pipeline"
)
MV_LEAF_DIR = PIPELINE_DIR / "generate" / "mv"
MV_SKILL = MV_LEAF_DIR / "SKILL.md"
CREATOR_PIPELINE = VALIDATOR.HERMES_ROOT / "profiles" / "creator" / "skills" / "creator-pipeline"


class GenerateMvLeafTest(unittest.TestCase):
    """The real leaf, validated like validate-profile-skills.py does."""

    def test_validate_hands_leaves_passes_and_subject_unique(self) -> None:
        errors: list[str] = []
        by_profile = {
            p: VALIDATOR.validate_hands_leaves(
                VALIDATOR.HERMES_ROOT / "profiles" / p / "skills" / f"{p}-pipeline", p, errors
            )
            for p in VALIDATOR.HANDS_PROFILES
        }
        self.assertEqual([], errors)
        self.assertIn("generate-mv", by_profile["video-creator"])
        VALIDATOR.validate_hands_subjects(by_profile, errors)
        self.assertEqual([], errors)

    def test_name_cost_options_note_and_required_fields(self) -> None:
        data = VALIDATOR.frontmatter(MV_SKILL)
        self.assertEqual("generate-mv", data.get("name"))
        meta = VALIDATOR.hermes_meta(data)
        self.assertEqual("video-creator", meta.get("hands"))
        self.assertEqual("metered", meta.get("cost"))
        self.assertTrue(str(meta.get("output", "")).strip())
        form = meta["form"]
        families = {
            "style": ("styles", ["anime-3d", "anime-2d", "live-action", "mixed-media"]),
            "theme": ("themes", ["theater", "night-city", "dream-garden", "graphic-space"]),
            "direction": ("direction", ["performance", "typographic", "montage"]),
            "pace": ("pace", ["relaxed", "steady", "snappy", "intense"]),
            "transition": ("transition", ["continuous", "cut", "match-cut", "whip", "dissolve"]),
        }
        for field, (dirname, options) in families.items():
            self.assertEqual(options, form[field]["options"])
            self.assertTrue(form[field]["other"])
            for option in options:
                path = MV_LEAF_DIR / "references" / dirname / f"{option}.md"
                self.assertTrue(path.is_file(), path)
        self.assertIs(False, form["note"]["required"])
        for field in ("pace", "transition"):
            self.assertIs(False, form[field]["required"])
            self.assertEqual(f"references/{field}/*.md", form[field]["references"])
        required = {name for name, field in form.items() if field.get("required")}
        self.assertEqual({"subject", "theme", "style", "music_mode", "remote_analysis"}, required)


class ThemeMappingRegressionTest(unittest.TestCase):
    """Pins validate_hands_form's theme/references mapping: a non-style field
    with an explicit `references:` key gets its options checked against
    references/themes/*.md, while an untouched field like `aspect` (no
    references dir, no explicit key) keeps its colon-bearing values unchecked."""

    LEAF = (
        "---\nname: generate-mv\ndescription: A short generated MV.\n"
        "metadata:\n  hermes:\n    category: hands\n    hands: video-creator\n"
        "    cost: metered\n    output: mv.mp4\n    form:\n{form}"
        "---\n<Procedure>\n</Procedure>\n"
    )

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.leaf_dir = Path(self._tmp.name) / "generate" / "mv"
        self.leaf_dir.mkdir(parents=True)

    def validate(self, form: str) -> list[str]:
        path = self.leaf_dir / "SKILL.md"
        path.write_text(self.LEAF.format(form=form), encoding="utf-8")
        data = VALIDATOR.frontmatter(path)
        errors: list[str] = []
        VALIDATOR.validate_hands_form(
            VALIDATOR.hermes_meta(data)["form"], self.leaf_dir, self.leaf_dir, errors
        )
        return errors

    def themed_form(self, options: str, extra: str = "") -> str:
        return (
            f"      theme:\n        required: true\n        options: [{options}]\n"
            "        references: references/themes/*.md\n"
            f"{extra}      note:\n        required: false\n"
        )

    def test_backed_theme_option_passes(self) -> None:
        themes = self.leaf_dir / "references" / "themes"
        themes.mkdir(parents=True)
        (themes / "theater.md").write_text("# t\n")
        self.assertEqual([], self.validate(self.themed_form("theater")))

    def test_missing_backing_file_errors(self) -> None:
        themes = self.leaf_dir / "references" / "themes"
        themes.mkdir(parents=True)
        (themes / "theater.md").write_text("# t\n")
        errors = self.validate(self.themed_form("theater, night-city"))
        self.assertTrue(any("no references/themes/night-city.md" in e for e in errors), errors)

    def test_missing_entire_themes_directory_errors(self) -> None:
        errors = self.validate(self.themed_form("theater"))
        self.assertTrue(any("no references/themes/theater.md" in e for e in errors), errors)

    def test_traversal_option_rejected(self) -> None:
        errors = self.validate(self.themed_form("'../escape'"))
        self.assertTrue(any("reference option must be a slug" in e for e in errors), errors)

    def test_custom_aspect_enum_with_colons_unaffected(self) -> None:
        themes = self.leaf_dir / "references" / "themes"
        themes.mkdir(parents=True)
        (themes / "theater.md").write_text("# t\n")
        extra = "      aspect:\n        required: false\n        options: ['16:9', '9:16']\n"
        self.assertEqual([], self.validate(self.themed_form("theater", extra)))

    def test_tempo_options_require_references_even_when_directory_missing(self) -> None:
        for key, option in (("pace", "snappy"), ("transition", "cut")):
            with self.subTest(field=key):
                form = (
                    f"      {key}:\n        required: false\n        options: [{option}]\n"
                    f"        references: references/{key}/*.md\n"
                    "      note:\n        required: false\n"
                )
                errors = self.validate(form)
                self.assertTrue(any(f"no references/{key}/{option}.md" in e for e in errors))
                reference = self.leaf_dir / "references" / key / f"{option}.md"
                reference.parent.mkdir(parents=True, exist_ok=True)
                reference.write_text("# Example\n", encoding="utf-8")
                self.assertEqual([], self.validate(form))


class MvRootAndRoutingTest(unittest.TestCase):
    """No generated menu/wrapper in the mv leaf root, `video_generate` stays
    the generation tool, and Creator's routing surfaces name generate-mv with
    no video-creator model/provider config drift."""

    def test_mv_root_has_only_skill_md_no_wrapper_script(self) -> None:
        top_level = {p.name for p in MV_LEAF_DIR.iterdir() if p.is_file()}
        self.assertEqual({"SKILL.md"}, top_level)
        self.assertFalse((MV_LEAF_DIR / "scripts").exists())

    def test_generation_tool_is_video_generate(self) -> None:
        text = MV_SKILL.read_text(encoding="utf-8")
        self.assertIn("Uses video_generate, not a new API.", text)

    def test_routed_in_creator_config_capabilities_plan_build(self) -> None:
        root = (CREATOR_PIPELINE / "SKILL.md").read_text(encoding="utf-8")
        capabilities = (CREATOR_PIPELINE / "references" / "capabilities.md").read_text(
            encoding="utf-8"
        )
        plan = (CREATOR_PIPELINE / "references" / "plan.md").read_text(encoding="utf-8")
        build = (CREATOR_PIPELINE / "references" / "build.md").read_text(encoding="utf-8")
        self.assertIn("generate-mv", root)
        self.assertIn("video-creator: generate-mv", capabilities)
        self.assertIn("generate-mv", plan)
        self.assertIn("generate-mv", build)

    def test_no_model_or_provider_config_drift(self) -> None:
        """One shared top-level model/provider block for the whole profile;
        no leaf-specific override block was introduced for generate-mv."""
        config = VALIDATOR.HERMES_ROOT / "profiles" / "video-creator" / "config.yaml"
        lines = config.read_text(encoding="utf-8").splitlines()
        top_level_keys = [l for l in lines if l.startswith(("model:", "providers:", "video_gen:"))]
        self.assertEqual(3, len(top_level_keys))
        self.assertFalse(any(l.strip().startswith("generate-mv:") for l in lines))


class StaticContractLanguageTest(unittest.TestCase):
    """DOCS-ONLY: confirms SKILL.md still states the safety contract in
    prose. None of these execute the Procedure or prove runtime enforcement."""

    def setUp(self) -> None:
        self.text = MV_SKILL.read_text(encoding="utf-8")

    def test_first_round_is_proposal_only_with_a_stop(self) -> None:
        self.assertIn("STOP", self.text)
        self.assertIn("no video_generate, video_analyze, image", self.text)

    def test_approval_sha256_gates_generation(self) -> None:
        self.assertIn(
            "Round B requires BOTH approved_plan and approval_sha256", self.text
        )

    def test_upload_consent_named_explicitly(self) -> None:
        self.assertIn(
            "authorizes the character reference leaving the machine", self.text
        )

    def test_remote_analysis_is_a_separate_audio_boundary(self) -> None:
        self.assertIn(
            "separate consent to upload GENERATED video, including its audio", self.text
        )

    def test_reference_duration_and_proposal_versioning_are_explicit(self) -> None:
        self.assertIn("xAI's reference-image path clamps duration to 10s", self.text)
        self.assertIn("proposal-v<N>.md", self.text)
        self.assertIn("never overwrite any previous proposal", self.text)
        self.assertIn("intent: revise <deliver>", self.text)

    def test_continuous_performance_is_not_rejected_for_missing_cuts(self) -> None:
        qa = (CREATOR_PIPELINE / "references" / "quality-assurance.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Cuts are allowed, not mandatory", qa)
        self.assertIn("preserve UNVERIFIED", qa)

    def test_tempo_is_in_prompt_and_does_not_mutate_existing_approval(self) -> None:
        self.assertIn("Write\n    these into the actual prompt, not just the form", self.text)
        self.assertIn("do not inject new defaults or silently reinterpret it", self.text)
        self.assertIn("theme, pace, transition, words policy", self.text)
        self.assertIn("not necessarily cuts; continuous forbids shot breaks", (
            CREATOR_PIPELINE / "references" / "quality-assurance.md"
        ).read_text(encoding="utf-8"))

    def test_prompt_length_is_measured_before_approval_and_submission(self) -> None:
        self.assertIn("1..1800 UTF-8 bytes INCLUDING its final newline before approval", self.text)
        self.assertIn("wc -c <generation-prompt-vN.txt>", self.text)
        self.assertIn("prompt-only file's hash and 1..1800-byte count immediately before calling", self.text)
        self.assertIn("prompt.txt is the ledger, NOT", self.text)

    def test_spatial_actions_keep_crossing_evidence_and_bounded_review(self) -> None:
        reference = MV_LEAF_DIR / "references" / "spatial-direction.md"
        self.assertTrue(reference.is_file())
        self.assertIn("[spatial direction](references/spatial-direction.md)", self.text)
        self.assertIn("START / CROSS / AFTER", self.text)
        self.assertIn("at most TWO critical windows per candidate", self.text)
        self.assertIn("2 seconds and 24 frames per window", self.text)
        self.assertIn("No implicit shot-by-shot generation or assembly", self.text)
        continuous = (MV_LEAF_DIR / "references" / "transition" / "continuous.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("full decode proves file integrity, not an unbroken shot", continuous)


if __name__ == "__main__":
    unittest.main()
