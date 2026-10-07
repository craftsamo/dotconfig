"""Tests for validate_hands_routing (Assistant commissioning references <->
installed hands leaves coverage check) plus a real runtime-discovery regression for every
installed hands leaf across all three hands profiles. No generic generated
catalog is built here: expected leaf names always come from an actual
on-disk scan of the candidate under test, never a hardcoded literal list."""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "validate-profile-skills.py"
SPEC = importlib.util.spec_from_file_location("validate_profile_skills_hands_routing", SCRIPT)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


def _leaves(*triples: tuple[str, str, str]) -> dict[str, dict[str, Path]]:
    """Build a hands_leaves mapping (profile -> {name: Path}) from (profile,
    subject, name) triples; the leaf path mirrors <verb>/<subject>/SKILL.md,
    since validate_hands_routing derives the subject from the parent dir."""
    result: dict[str, dict[str, Path]] = {}
    for profile, subject, name in triples:
        verb = name.split("-", 1)[0]
        result.setdefault(profile, {})[name] = Path(f"/fake/{profile}/{verb}/{subject}/SKILL.md")
    return result


class HandsRoutingSandboxTest(unittest.TestCase):
    """Fixture-based unit tests: ASSISTANT_PIPELINE is monkeypatched to a
    temporary tree for the whole test, so no live repo file is ever written."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self._original_root = VALIDATOR.ASSISTANT_PIPELINE
        VALIDATOR.ASSISTANT_PIPELINE = self.root
        self.refs = self.root / "execute-assistant-creative/references"
        self.refs.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        VALIDATOR.ASSISTANT_PIPELINE = self._original_root
        self._tmp.cleanup()

    def ref(self, subject: str, text: str) -> None:
        (self.refs / f"{subject}.md").write_text(text, encoding="utf-8")

    def check(self, leaves) -> list[str]:
        errors: list[str] = []
        VALIDATOR.validate_hands_routing(leaves, errors)
        return errors

    def test_missing_reference_directory_reports_every_subject(self) -> None:
        self.refs.rmdir()
        errors = self.check(_leaves(("audio-creator", "mix", "create-mix")))
        self.assertEqual(["hands subject has no commissioning reference: audio-creator/mix"], errors)

    def test_clean_reference_reports_nothing(self) -> None:
        self.ref("mix", "| a mix | create-mix |\n")
        self.assertEqual([], self.check(_leaves(("audio-creator", "mix", "create-mix"))))

    def test_missing_subject_reference_reported(self) -> None:
        self.ref("mix", "create-mix\n")
        errors = self.check(_leaves(("audio-creator", "mix", "create-mix"), ("audio-creator", "sfx", "generate-sfx")))
        self.assertEqual(["hands subject has no commissioning reference: audio-creator/sfx"], errors)

    def test_orphan_reference_without_hands_subject_reported(self) -> None:
        self.ref("mix", "create-mix\n")
        self.ref("pixel-art", "# nothing serves this\n")
        errors = self.check(_leaves(("audio-creator", "mix", "create-mix")))
        self.assertEqual(["commissioning reference has no hands subject: pixel-art.md"], errors)

    def test_leaf_not_named_in_its_reference_reported(self) -> None:
        self.ref("mix", "create-mix\n")
        errors = self.check(_leaves(("audio-creator", "mix", "create-mix"), ("audio-creator", "mix", "edit-mix")))
        self.assertEqual(["commissioning reference does not name installed leaf: audio-creator: edit-mix"], errors)

    def test_leaf_name_must_match_whole_word(self) -> None:
        self.ref("mix", "create-mix-extra\n")
        errors = self.check(_leaves(("audio-creator", "mix", "create-mix")))
        self.assertEqual(["commissioning reference does not name installed leaf: audio-creator: create-mix"], errors)

    def test_shared_media_ops_reference_is_not_an_orphan(self) -> None:
        self.ref("media-ops", "# shared\n")
        self.ref("mix", "create-mix\n")
        self.assertEqual([], self.check(_leaves(("audio-creator", "mix", "create-mix"))))

    def test_multiple_profiles_report_independently(self) -> None:
        self.ref("card", "create-card\n")
        errors = self.check(_leaves(("image-creator", "card", "create-card"), ("video-creator", "clip", "generate-clip")))
        self.assertEqual(["hands subject has no commissioning reference: video-creator/clip"], errors)


class HandsRoutingLiveCandidateTest(unittest.TestCase):
    """Runs validate_hands + validate_hands_routing against THIS worktree's
    real, unmodified installed leaves and commissioning references -- catches a
    coverage regression (a subject or leaf missing from them) directly."""

    def test_real_commissioning_references_cover_installed_leaves(self) -> None:
        errors: list[str] = []
        hands_leaves: dict[str, dict[str, Path]] = {}
        for profile in VALIDATOR.HANDS_PROFILES:
            leaves, _learned = VALIDATOR.validate_hands(profile, errors)
            hands_leaves[profile] = leaves
        self.assertEqual([], errors, "validate_hands itself must be clean on the live candidate")
        self.assertTrue(all(hands_leaves.values()), "every hands profile must have installed leaves")
        routing_errors: list[str] = []
        VALIDATOR.validate_hands_routing(hands_leaves, routing_errors)
        self.assertEqual([], routing_errors)

    def test_mix_leaves_are_commissioned(self) -> None:
        errors: list[str] = []
        hands_leaves: dict[str, dict[str, Path]] = {}
        for profile in VALIDATOR.HANDS_PROFILES:
            leaves, _learned = VALIDATOR.validate_hands(profile, errors)
            hands_leaves[profile] = leaves
        self.assertEqual([], errors)
        for name in ("create-mix", "edit-mix", "analyze-mix"):
            self.assertIn(name, hands_leaves["audio-creator"])
        routing_errors: list[str] = []
        VALIDATOR.validate_hands_routing(hands_leaves, routing_errors)
        self.assertEqual([], routing_errors)


class HandsRuntimeDiscoveryTest(unittest.TestCase):
    """Real tools.skills_tool discovery, scoped to each hands profile's own
    skill root (never the live default search path/config), plus
    agent.skill_utils.parse_frontmatter against exactly the first 4000
    characters _find_all_skills reads. This is a canonical-name regression
    check, NOT a blanket frontmatter-length cap: a leaf's total file length
    is unconstrained here, only whether its frontmatter fence closes before
    the runtime discovery cutoff."""

    def _installed_leaves(self, profile: str) -> dict[str, Path]:
        pipeline = VALIDATOR.HERMES_ROOT / "profiles" / profile / "skills" / f"{profile}-pipeline"
        leaves: dict[str, Path] = {}
        for path in sorted(pipeline.rglob("SKILL.md")):
            rel = path.relative_to(pipeline)
            if len(rel.parts) != 3:
                continue
            verb, subject, _ = rel.parts
            leaves[f"{verb}-{subject}"] = path
        return leaves

    def test_find_all_skills_discovers_every_leaf_once_with_real_names(self) -> None:
        import tools.skills_tool as skills_tool

        for profile in VALIDATOR.HANDS_PROFILES:
            with self.subTest(profile=profile):
                pipeline = VALIDATOR.HERMES_ROOT / "profiles" / profile / "skills" / f"{profile}-pipeline"
                expected = self._installed_leaves(profile)
                self.assertTrue(expected, f"{profile} must have installed hands leaves to discover")
                with patch.object(skills_tool, "_skill_search_dirs", return_value=([], [pipeline], pipeline)), \
                     patch.object(skills_tool, "_get_disabled_skill_names", return_value=set()), \
                     patch.object(skills_tool, "_SKILLS_CACHE", {}):
                    skills = skills_tool._find_all_skills()
                names = [s["name"] for s in skills]
                self.assertEqual(len(expected) + 1, len(names))  # + the pipeline root itself
                self.assertEqual(len(names), len(set(names)))
                self.assertIn(f"{profile}-pipeline", names)
                for expected_name in expected:
                    self.assertEqual(1, names.count(expected_name))
                # No generic verb/subject-only fallback name leaked through.
                for subject in {name.split("-", 1)[1] for name in expected}:
                    self.assertNotIn(subject, names)

    def test_frontmatter_name_survives_the_4000_char_discovery_cutoff(self) -> None:
        from agent.skill_utils import parse_frontmatter

        for profile in VALIDATOR.HANDS_PROFILES:
            with self.subTest(profile=profile):
                for name, path in self._installed_leaves(profile).items():
                    text = path.read_text(encoding="utf-8")
                    frontmatter, _ = parse_frontmatter(text[:4000])
                    self.assertEqual(
                        name, frontmatter.get("name"),
                        f"{path}: frontmatter must close before the runtime discovery "
                        "cutoff, or the leaf falls back to its parent directory name",
                    )


if __name__ == "__main__":
    unittest.main()
