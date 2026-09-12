"""Coverage for video-creator's generate/music-video hands leaf.

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
from unittest.mock import patch

from agent import skill_utils
from tools import skills_tool


SCRIPT = Path(__file__).resolve().parents[1] / "validate-profile-skills.py"
SPEC = importlib.util.spec_from_file_location("validate_profile_skills", SCRIPT)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)

PIPELINE_DIR = (
    VALIDATOR.HERMES_ROOT / "profiles" / "video-creator" / "skills" / "video-creator-pipeline"
)
MUSIC_VIDEO_LEAF_DIR = PIPELINE_DIR / "generate" / "music-video"
MUSIC_VIDEO_SKILL = MUSIC_VIDEO_LEAF_DIR / "SKILL.md"
CREATOR_PIPELINE = VALIDATOR.HERMES_ROOT / "profiles" / "creator" / "skills" / "creator-pipeline"


class GenerateMusicVideoLeafTest(unittest.TestCase):
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
        self.assertIn("generate-music-video", by_profile["video-creator"])
        self.assertNotIn("generate-mv", by_profile["video-creator"])
        VALIDATOR.validate_hands_subjects(by_profile, errors)
        self.assertEqual([], errors)

    def test_name_cost_options_note_and_required_fields(self) -> None:
        data = VALIDATOR.frontmatter(MUSIC_VIDEO_SKILL)
        self.assertEqual("generate-music-video", data.get("name"))
        meta = VALIDATOR.hermes_meta(data)
        self.assertEqual("video-creator", meta.get("hands"))
        self.assertEqual("metered", meta.get("cost"))
        self.assertTrue(str(meta.get("output", "")).strip())
        form = meta["form"]
        self.assertEqual({
            "subject", "character_reference", "theme", "theme_detail", "style",
            "performance", "direction", "pace", "transition", "reference_video",
            "reference_focus", "music_mode", "music", "music_file", "music_plan", "words",
            "must_keep", "aspect", "duration", "upload_inputs", "remote_analysis",
            "approved_plan", "approval_sha256", "slug", "note",
        }, set(form))
        self.assertEqual(["generated", "supplied", "silent"], form["music_mode"]["options"])
        self.assertEqual(
            ["16:9", "9:16", "1:1", "4:3", "3:4", "3:2", "2:3"],
            form["aspect"]["options"],
        )
        for field in ("upload_inputs", "remote_analysis"):
            self.assertEqual(["yes", "no"], form[field]["options"])
        self.assertEqual({
            "character_reference": "image", "reference_video": "file",
            "music_file": "file", "music_plan": "text", "duration": "int", "approved_plan": "file",
            "note": "text",
        }, {name: field["type"] for name, field in form.items() if "type" in field})
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
                path = MUSIC_VIDEO_LEAF_DIR / "references" / dirname / f"{option}.md"
                self.assertTrue(path.is_file(), path)
        self.assertIs(False, form["note"]["required"])
        for field in ("pace", "transition"):
            self.assertIs(False, form[field]["required"])
            self.assertEqual(f"references/{field}/*.md", form[field]["references"])
        required = {name for name, field in form.items() if field.get("required")}
        self.assertEqual({"subject", "theme", "style", "music_mode", "remote_analysis"}, required)

    def test_actual_upstream_frontmatter_survives_discovery_window(self) -> None:
        text = MUSIC_VIDEO_SKILL.read_text(encoding="utf-8")
        closing_end = text.index("\n---\n", 3) + len("\n---\n")
        self.assertLessEqual(closing_end, 3800)
        frontmatter, _ = skill_utils.parse_frontmatter(text[:4000])
        self.assertEqual("generate-music-video", frontmatter.get("name"))
        self.assertEqual(VALIDATOR.frontmatter(MUSIC_VIDEO_SKILL), frontmatter)

    def test_actual_upstream_discovery_has_new_name_once_without_alias(self) -> None:
        # Keep real parsing/scanning, but isolate roots/cache from live profiles.
        with (
            patch.object(skills_tool, "SKILLS_DIR", PIPELINE_DIR),
            patch.object(skills_tool, "_SKILLS_CACHE", {}),
            patch.object(skill_utils, "get_external_skills_dirs", return_value=[]),
            patch.object(skill_utils, "get_project_skills_dirs", return_value=[]),
        ):
            skills = skills_tool._find_all_skills(skip_disabled=True)
        names = [skill["name"] for skill in skills]
        self.assertEqual(1, names.count("generate-music-video"), names)
        self.assertNotIn("mv", names)
        self.assertNotIn("generate-mv", names)
        self.assertNotIn("music-video", names)
        self.assertFalse((PIPELINE_DIR / "generate" / "mv").exists())


class ThemeMappingRegressionTest(unittest.TestCase):
    """Pins validate_hands_form's theme/references mapping: a non-style field
    with an explicit `references:` key gets its options checked against
    references/themes/*.md, while an untouched field like `aspect` (no
    references dir, no explicit key) keeps its colon-bearing values unchecked."""

    LEAF = (
        "---\nname: generate-music-video\ndescription: A short generated MV.\n"
        "metadata:\n  hermes:\n    category: hands\n    hands: video-creator\n"
        "    cost: metered\n    output: mv.mp4\n    form:\n{form}"
        "---\n<Procedure>\n</Procedure>\n"
    )

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.leaf_dir = Path(self._tmp.name) / "generate" / "music-video"
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


class MusicVideoRootAndRoutingTest(unittest.TestCase):
    """No generated menu/wrapper in the music-video leaf root, `video_generate` stays
    the generation tool, and Creator's routing surfaces name generate-music-video with
    no video-creator model/provider config drift."""

    def test_music_video_root_has_only_skill_md_no_wrapper_script(self) -> None:
        top_level = {p.name for p in MUSIC_VIDEO_LEAF_DIR.iterdir() if p.is_file()}
        self.assertEqual({"SKILL.md"}, top_level)
        self.assertFalse((MUSIC_VIDEO_LEAF_DIR / "scripts").exists())
        self.assertEqual(21, len(list((MUSIC_VIDEO_LEAF_DIR / "references").rglob("*.md"))))

    def test_generation_tool_is_video_generate(self) -> None:
        text = MUSIC_VIDEO_SKILL.read_text(encoding="utf-8")
        self.assertIn("Uses video_generate, not a new API.", text)

    def test_routed_in_creator_config_capabilities_plan_build(self) -> None:
        root = (CREATOR_PIPELINE / "SKILL.md").read_text(encoding="utf-8")
        capabilities = (CREATOR_PIPELINE / "references" / "capabilities.md").read_text(
            encoding="utf-8"
        )
        plan_index = (CREATOR_PIPELINE / "plan-creator" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        plan = plan_index + (
            CREATOR_PIPELINE / "plan-creator" / "references" / "video-creator" / "music-video.md"
        ).read_text(encoding="utf-8")
        build_index = (CREATOR_PIPELINE / "build-creator" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        build = build_index + (
            CREATOR_PIPELINE / "build-creator" / "references" / "video-creator" / "music-video.md"
        ).read_text(encoding="utf-8")
        self.assertIn("video-creator: generate-music-video", capabilities)
        self.assertIn('music-video-style piece ("MV")', plan)
        self.assertIn("generate-music-video", plan)
        self.assertIn("generate-music-video", build)
        for text in (capabilities, plan, build):
            self.assertNotIn("generate-mv", text)
        # Root (v8) no longer enumerates leaves; it routes to Plan/Build's
        # index, and those indexes link the exact music-video.md reference
        # exercised above.
        for path in ("plan-creator/SKILL.md", "build-creator/SKILL.md"):
            self.assertIn(path, root)
        self.assertIn("(references/video-creator/music-video.md)", plan_index)
        self.assertIn("(references/video-creator/music-video.md)", build_index)
        self.assertNotIn("generate-mv", root)
        for relative in (
            "creator/config.yaml", "creator/profile.yaml",
            "creator/skills/creator-pipeline/qa-creator/references/video-creator/music-video.md",
            "video-creator/config.yaml", "video-creator/profile.yaml",
            "video-creator/skills/video-creator-pipeline/SKILL.md",
        ):
            with self.subTest(path=relative):
                text = (VALIDATOR.HERMES_ROOT / "profiles" / relative).read_text(
                    encoding="utf-8"
                )
                self.assertIn("generate-music-video", text)
                self.assertNotIn("generate-mv", text)

    def test_no_model_or_provider_config_drift(self) -> None:
        """One shared top-level model/provider block for the whole profile;
        no leaf-specific override block was introduced for generate-music-video."""
        config = VALIDATOR.HERMES_ROOT / "profiles" / "video-creator" / "config.yaml"
        lines = config.read_text(encoding="utf-8").splitlines()
        top_level_keys = [l for l in lines if l.startswith(("model:", "providers:", "video_gen:"))]
        self.assertEqual(3, len(top_level_keys))
        self.assertFalse(any(l.strip().startswith("generate-music-video:") for l in lines))


class StaticContractLanguageTest(unittest.TestCase):
    """DOCS-ONLY: confirms SKILL.md still states the safety contract in
    prose. None of these execute the Procedure or prove runtime enforcement."""

    def setUp(self) -> None:
        self.text = MUSIC_VIDEO_SKILL.read_text(encoding="utf-8")

    def test_first_round_is_proposal_only_with_a_stop(self) -> None:
        self.assertIn("STOP", self.text)
        self.assertIn("no video_generate, video_analyze, image", self.text)

    def test_approval_sha256_gates_generation(self) -> None:
        self.assertIn(
            "Round B requires BOTH approved_plan and approval_sha256", self.text
        )

    def test_pending_music_is_a_proposal_not_a_generation_release(self) -> None:
        form = VALIDATOR.hermes_meta(VALIDATOR.frontmatter(MUSIC_VIDEO_SKILL))["form"]
        self.assertIs(False, form["music_plan"]["required"])
        self.assertEqual("text", form["music_plan"]["type"])
        text = " ".join(self.text.split())
        for phrase in (
            "supplied mode accepts either a real music_file or a nonblank music_plan",
            "status: pending-inputs", "can_generate: false",
            "A pending-inputs proposal cannot enter Round B even when its hash matches",
            "return a NEW numbered proposal", "never splice them into the old approved proposal",
            "Do not fabricate a WAV, future file hash or audio measurement",
            "unreadable music_file is an input error, never silently replaced by music_plan",
        ):
            self.assertIn(phrase, text)

    def test_pending_image_consent_allows_only_zero_upload_planning(self) -> None:
        text = " ".join(self.text.split())
        self.assertIn("Round A may retain a local character_reference before upload consent", text)
        self.assertIn("Before Round B, a character_reference without upload_inputs: yes returns Q<n>", text)
        self.assertIn("its hash identifies a preliminary proposal", text.lower())

    def test_creator_preserves_direction_and_resolves_dependencies_separately(self) -> None:
        phase_dirs = {"plan": "plan-creator", "build": "build-creator",
                      "quality-assurance": "qa-creator"}
        for phase, entry_dir in phase_dirs.items():
            text = " ".join(
                (CREATOR_PIPELINE / entry_dir / "references" / "video-creator" / "music-video.md")
                .read_text()
                .split()
            )
            self.assertIn("pending-inputs", text)
            self.assertIn("music_file", text)
        self.assertIn(
            "separate approval",
            (CREATOR_PIPELINE / "build-creator/references/video-creator/music-video.md").read_text(),
        )

    def test_upload_consent_named_explicitly(self) -> None:
        self.assertIn(
            "authorizes the character reference leaving the machine", self.text
        )

    def test_remote_analysis_is_a_separate_audio_boundary(self) -> None:
        self.assertIn(
            "separate consent to upload GENERATED video, including its audio",
            " ".join(self.text.split()),
        )

    def test_reference_duration_and_proposal_versioning_are_explicit(self) -> None:
        self.assertIn("xAI's reference-image path clamps duration to 10s", self.text)
        self.assertIn("proposal-v<N>.md", self.text)
        self.assertIn("never overwrite any previous proposal", self.text)
        self.assertIn("intent: revise <deliver>", self.text)

    def test_continuous_performance_is_not_rejected_for_missing_cuts(self) -> None:
        qa = (
            CREATOR_PIPELINE / "qa-creator" / "references" / "video-creator" / "music-video.md"
        ).read_text(encoding="utf-8")
        self.assertIn("Cuts are allowed, not mandatory", qa)
        self.assertIn("preserve UNVERIFIED", qa)

    def test_tempo_is_in_prompt_and_does_not_mutate_existing_approval(self) -> None:
        self.assertIn(
            "Write these into the actual prompt, not just the form",
            " ".join(self.text.split()),
        )
        self.assertIn("do not inject new defaults or silently reinterpret it", self.text)
        self.assertIn("theme, pace, transition, words policy", self.text)
        self.assertIn("not necessarily cuts; continuous forbids shot breaks", (
            CREATOR_PIPELINE / "qa-creator" / "references" / "video-creator" / "music-video.md"
        ).read_text(encoding="utf-8"))

    def test_prompt_length_is_measured_before_approval_and_submission(self) -> None:
        self.assertIn("1..1800 UTF-8 bytes INCLUDING its final newline before approval", self.text)
        self.assertIn("wc -c <generation-prompt-vN.txt>", self.text)
        self.assertIn("prompt-only file's hash and 1..1800-byte count immediately before calling", self.text)
        self.assertIn("prompt.txt is the ledger, NOT", self.text)

    def test_spatial_actions_keep_crossing_evidence_and_bounded_review(self) -> None:
        reference = MUSIC_VIDEO_LEAF_DIR / "references" / "spatial-direction.md"
        self.assertTrue(reference.is_file())
        self.assertIn("[spatial direction](references/spatial-direction.md)", self.text)
        self.assertIn("START / CROSS / AFTER", self.text)
        self.assertIn("at most TWO critical windows per candidate", self.text)
        self.assertIn("2 seconds and 24 frames per window", self.text)
        self.assertIn("No implicit shot-by-shot generation or assembly", self.text)
        continuous = (MUSIC_VIDEO_LEAF_DIR / "references" / "transition" / "continuous.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("full decode proves file integrity, not an unbroken shot", continuous)

    def test_route_preflight_stays_in_tool_context_and_names_its_gap(self) -> None:
        text = " ".join(self.text.split())
        for phrase in (
            "Route preflight happens inside this session's tool context only",
            "Never probe credentials from a terminal child or a venv script",
            "terminal children do not inherit tool credentials",
            "available when ANY member is",
            "never a blocker, and never consumes an attempt",
            "never only an exception type",
            '"review required" is not an outcome',
            "an unverified route is never reported as a cleared budget check",
            "not a verified bill or a cap: the grant is counted in attempts",
        ):
            self.assertIn(phrase, text)

    def test_rename_keeps_output_paths_and_requires_fresh_legacy_approval(self) -> None:
        text = " ".join(self.text.split())
        self.assertIn("<deliver>/mv_<slug>_v<N>.mp4", text)
        self.assertIn("not an output-filename or runtime-job-path rename", text)
        self.assertIn("There is no generate-mv alias leaf", text)
        self.assertIn(
            "Reissue active legacy jobs under generate-music-video with a new proposal "
            "and new client approval", text,
        )
        self.assertIn("never edit frozen old jobs, prompts or approvals", text)
        self.assertIn("preserve consumed attempts", text)


class ConfiguredChainPreflightTest(unittest.TestCase):
    """The real vid-xai-fal chain plugin: an unavailable or raising secondary
    member leaves the chain available, its surface follows the first available
    member, and one generate call never touches the unavailable member. This is
    the runtime fact the route-preflight rule relies on; no provider is real."""

    CHAIN = VALIDATOR.HERMES_ROOT / "plugins" / "video_gen" / "video-fallback" / "__init__.py"

    def setUp(self) -> None:
        spec = importlib.util.spec_from_file_location("video_fallback_preflight", self.CHAIN)
        assert spec and spec.loader
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.assertEqual(["xai", "fal"], self.module._CHAINS["vid-xai-fal"])

    def member(self, name: str, *, available: bool | Exception, calls: list) -> object:
        module = self.module

        class Member(module.VideoGenProvider):
            @property
            def name(self) -> str:
                return name

            @property
            def display_name(self) -> str:
                return name

            def is_available(self) -> bool:
                if isinstance(available, Exception):
                    raise available
                return available

            def capabilities(self) -> dict:
                return {"member": name, "supports_audio": False}

            def generate(self, prompt: str, **kwargs: object) -> dict:
                calls.append((name, prompt, kwargs.get("reference_image_urls")))
                return {"success": True, "provider": name, "prompt": prompt}

        return Member()

    def test_unavailable_or_raising_fal_never_blocks_or_consumes_xai(self) -> None:
        for fal_state in (False, ValueError("video_gen is configured to use vid-xai-fal but FAL_KEY is not set")):
            with self.subTest(fal=type(fal_state).__name__):
                calls: list = []
                members = {"xai": self.member("xai", available=True, calls=calls),
                           "fal": self.member("fal", available=fal_state, calls=calls)}
                chain = self.module.ChainProvider("vid-xai-fal", self.module._CHAINS["vid-xai-fal"])
                with patch.object(self.module.video_gen_registry, "get_provider", members.get):
                    self.assertTrue(chain.is_available())
                    self.assertEqual("xai", chain.capabilities()["member"])
                    result = chain.generate("approved prompt", duration=10,
                                            reference_image_urls=["file:///reference.png"])
                self.assertTrue(result["success"])
                self.assertEqual([("xai", "approved prompt", ["file:///reference.png"])], calls)

    def test_missing_required_member_is_a_named_gap_not_a_call(self) -> None:
        calls: list = []
        members = {"xai": self.member("xai", available=False, calls=calls),
                   "fal": self.member("fal", available=False, calls=calls)}
        chain = self.module.ChainProvider("vid-xai-fal", self.module._CHAINS["vid-xai-fal"])
        with patch.object(self.module.video_gen_registry, "get_provider", members.get):
            self.assertFalse(chain.is_available())
            result = chain.generate("approved prompt", duration=10)
        self.assertFalse(result["success"])
        self.assertIn("xai: unavailable", result["error"])
        self.assertEqual([], calls)


if __name__ == "__main__":
    unittest.main()
