"""Tests for validate_hands_routing (capabilities.md <-> installed hands
leaves cross-check) plus a real runtime-discovery regression for every
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


def _leaves(*pairs: tuple[str, str]) -> dict[str, dict[str, Path]]:
    """Build a hands_leaves mapping (profile -> {name: Path}) from (profile,
    name) pairs; the Path value's content is irrelevant to validate_hands_routing,
    only the mapping shape matters."""
    result: dict[str, dict[str, Path]] = {}
    for profile, name in pairs:
        result.setdefault(profile, {})[name] = Path(f"/fake/{profile}/{name}/SKILL.md")
    return result


def _row(profile: str, name: str, note: str = "some engine/variant detail") -> str:
    return f"| a deliverable | {profile}: {name} | {note} |\n"


class HandsRoutingSandboxTest(unittest.TestCase):
    """Fixture-based unit tests: HERMES_ROOT is monkeypatched to a temporary
    tree for the whole test, so no live repo file is ever written."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self._original_root = VALIDATOR.HERMES_ROOT
        VALIDATOR.HERMES_ROOT = self.root
        self.table = self.root / "profiles/creator/skills/creator-pipeline/references/capabilities.md"
        self.table.parent.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        VALIDATOR.HERMES_ROOT = self._original_root
        self._tmp.cleanup()

    def test_missing_table_reports_and_stops(self) -> None:
        errors: list[str] = []
        VALIDATOR.validate_hands_routing(_leaves(("audio-creator", "create-mix")), errors)
        self.assertEqual(1, len(errors))
        self.assertIn("missing creator capabilities routing table", errors[0])

    def test_clean_table_reports_nothing(self) -> None:
        self.table.write_text(_row("audio-creator", "create-mix"), encoding="utf-8")
        errors: list[str] = []
        VALIDATOR.validate_hands_routing(_leaves(("audio-creator", "create-mix")), errors)
        self.assertEqual([], errors)

    def test_orphan_route_to_uninstalled_leaf_reported(self) -> None:
        self.table.write_text(
            _row("audio-creator", "create-mix") + _row("audio-creator", "generate-mix"),
            encoding="utf-8",
        )
        errors: list[str] = []
        VALIDATOR.validate_hands_routing(_leaves(("audio-creator", "create-mix")), errors)
        self.assertEqual(1, len(errors))
        self.assertIn("not installed", errors[0])
        self.assertIn("generate-mix", errors[0])

    def test_missing_installed_route_reported(self) -> None:
        self.table.write_text(_row("audio-creator", "create-mix"), encoding="utf-8")
        errors: list[str] = []
        VALIDATOR.validate_hands_routing(
            _leaves(("audio-creator", "create-mix"), ("audio-creator", "edit-mix")), errors
        )
        self.assertEqual(1, len(errors))
        self.assertIn("has no capabilities.md route", errors[0])
        self.assertIn("edit-mix", errors[0])

    def test_wrong_hands_assignment_reported(self) -> None:
        # The table claims video-creator serves create-mix; it is actually
        # installed under audio-creator -- a wrong-hands-assignment error,
        # plus (separately true) audio-creator's real leaf still has no
        # documented route of its own, since the only row for that name
        # named the wrong profile.
        self.table.write_text(_row("video-creator", "create-mix"), encoding="utf-8")
        errors: list[str] = []
        VALIDATOR.validate_hands_routing(_leaves(("audio-creator", "create-mix")), errors)
        self.assertEqual(2, len(errors))
        joined = "\n".join(errors)
        self.assertIn("assigns create-mix to video-creator", joined)
        self.assertIn("installed under audio-creator", joined)
        self.assertIn("audio-creator: create-mix", joined)

    def test_duplicate_engine_variant_rows_are_allowed(self) -> None:
        self.table.write_text(
            _row("audio-creator", "generate-sfx", "(local Stable Audio 3 Medium, engine omitted)")
            + _row("audio-creator", "generate-sfx", "(`engine: fal:elevenlabs-sfx-v2`)"),
            encoding="utf-8",
        )
        errors: list[str] = []
        VALIDATOR.validate_hands_routing(_leaves(("audio-creator", "generate-sfx")), errors)
        self.assertEqual([], errors)

    def test_multiple_profiles_and_missing_leaves_report_independently(self) -> None:
        self.table.write_text(_row("image-creator", "create-card"), encoding="utf-8")
        errors: list[str] = []
        VALIDATOR.validate_hands_routing(
            _leaves(("image-creator", "create-card"), ("video-creator", "generate-clip")), errors
        )
        self.assertEqual(1, len(errors))
        self.assertIn("generate-clip", errors[0])


class HandsRoutingLiveCandidateTest(unittest.TestCase):
    """Runs validate_hands + validate_hands_routing against THIS worktree's
    real, unmodified installed leaves and capabilities.md -- catches a
    routing-table regression (like the Mix omission this fixes) directly."""

    def test_real_capabilities_table_matches_installed_leaves(self) -> None:
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

    def test_mix_leaves_are_now_routed(self) -> None:
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
