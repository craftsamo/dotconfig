from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "validate-profile-skills.py"
SPEC = importlib.util.spec_from_file_location("validate_profile_skills", SCRIPT)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class CreatorReferencesTestCase(unittest.TestCase):
    """Creator v8 broker tree: references/{plan,build,quality-assurance}/
    index.md plus flat <hands>/<subject>.md leaves, expected subjects
    collected dynamically from a synthetic hands tree below a patched
    HERMES_ROOT."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.hermes_root = Path(self._tmp.name)
        patcher = mock.patch.object(VALIDATOR, "HERMES_ROOT", self.hermes_root)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.pipeline_dir = (
            self.hermes_root / "profiles" / "creator" / "skills" / "creator-pipeline"
        )
        self.pipeline_dir.mkdir(parents=True)

    # ── fixture helpers ───────────────────────────────────────────────

    def write(self, rel: str, text: str) -> Path:
        path = self.pipeline_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def hands_leaf(self, hands: str, verb: str, subject: str) -> Path:
        path = (
            self.hermes_root
            / "profiles"
            / hands
            / "skills"
            / f"{hands}-pipeline"
            / verb
            / subject
            / "SKILL.md"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"---\nname: {verb}-{subject}\n---\n", encoding="utf-8")
        return path

    def write_pipeline_skill(self, version: str) -> None:
        self.write(
            "SKILL.md",
            f"---\nname: creator-pipeline\nversion: {version}\n---\n<Goal>\n</Goal>\n",
        )

    def build_valid_tree(self, version: str = "8.0.0") -> None:
        self.hands_leaf("image-creator", "generate", "icon")
        self.hands_leaf("video-creator", "generate", "clip")
        self.write_pipeline_skill(version)
        for phase in VALIDATOR.CREATOR_REFERENCE_PHASES:
            self.write(f"references/{phase}/image-creator/icon.md", "# icon\n")
            self.write(f"references/{phase}/video-creator/clip.md", "# clip\n")
            self.write(
                f"references/{phase}/index.md",
                "# Phase\n\n"
                "- [icon](image-creator/icon.md)\n"
                "- [clip](video-creator/clip.md)\n",
            )

    def validate(self) -> list[str]:
        errors: list[str] = []
        VALIDATOR.validate_creator_references(self.pipeline_dir, errors)
        return errors

    # ── build-alongside gate ─────────────────────────────────────────

    def test_v7_missing_tree_is_accepted(self) -> None:
        self.hands_leaf("image-creator", "generate", "icon")
        self.write_pipeline_skill("7.0.0")
        self.assertEqual([], self.validate())

    def test_v7_build_alongside_allowed(self) -> None:
        # A full valid v8 tree coexists with the old monolith files while
        # the root pipeline is still declared major version 7.
        self.build_valid_tree(version="7.0.0")
        self.write("references/plan.md", "# old monolith\n")
        self.write("references/build.md", "# old monolith\n")
        self.write("references/quality-assurance.md", "# old monolith\n")
        self.assertEqual([], self.validate())

    def test_partial_new_phase_under_v7_fails(self) -> None:
        self.hands_leaf("image-creator", "generate", "icon")
        self.write_pipeline_skill("7.0.0")
        self.write("references/plan/image-creator/icon.md", "# icon\n")
        self.write(
            "references/plan/index.md", "- [icon](image-creator/icon.md)\n"
        )
        errors = self.validate()
        self.assertTrue(
            any("missing creator reference phase: build" in e for e in errors), errors
        )
        self.assertTrue(
            any(
                "missing creator reference phase: quality-assurance" in e
                for e in errors
            ),
            errors,
        )

    def test_invalid_version_is_rejected(self) -> None:
        self.hands_leaf("image-creator", "generate", "icon")
        self.write_pipeline_skill("v8.0.0")
        errors = self.validate()
        self.assertEqual(["invalid creator pipeline version"], errors)

    def test_missing_version_is_rejected(self) -> None:
        self.write("SKILL.md", "---\nname: creator-pipeline\n---\n")
        errors = self.validate()
        self.assertEqual(["invalid creator pipeline version"], errors)

    def test_strict_numeric_version_is_valid(self) -> None:
        self.build_valid_tree(version="8.0.0")
        self.assertEqual([], self.validate())

    def test_v8_missing_entire_tree_fails(self) -> None:
        self.hands_leaf("image-creator", "generate", "icon")
        self.write_pipeline_skill("8.0.0")
        errors = self.validate()
        for phase in VALIDATOR.CREATOR_REFERENCE_PHASES:
            self.assertTrue(
                any(f"missing creator reference phase: {phase}" in e for e in errors),
                errors,
            )

    def test_valid_v8_tree_passes(self) -> None:
        self.build_valid_tree()
        self.assertEqual([], self.validate())

    def test_stale_old_monolith_on_v8(self) -> None:
        self.build_valid_tree(version="8.0.0")
        self.write("references/plan.md", "# old monolith\n")
        errors = self.validate()
        self.assertTrue(
            any("stale monolith reference file on v8" in e for e in errors), errors
        )

    # ── subject coverage ─────────────────────────────────────────────

    def test_missing_subject_reported(self) -> None:
        self.build_valid_tree()
        (self.pipeline_dir / "references/build/video-creator/clip.md").unlink()
        self.write("references/build/index.md", "- [icon](image-creator/icon.md)\n")
        errors = self.validate()
        self.assertTrue(
            any(
                "creator reference phase build missing hands subject: "
                "video-creator/clip" in e
                for e in errors
            ),
            errors,
        )

    def test_orphan_subject_reported(self) -> None:
        self.build_valid_tree()
        self.write("references/plan/image-creator/mascot.md", "# mascot\n")
        errors = self.validate()
        self.assertTrue(
            any(
                "creator reference phase plan has orphan hands subject: "
                "image-creator/mascot" in e
                for e in errors
            ),
            errors,
        )

    def test_wrong_hands_subject(self) -> None:
        self.build_valid_tree()
        # video-creator's clip file is placed under image-creator instead.
        (self.pipeline_dir / "references/plan/video-creator/clip.md").unlink()
        self.write("references/plan/image-creator/clip.md", "# clip\n")
        errors = self.validate()
        self.assertTrue(
            any(
                "creator reference phase plan has orphan hands subject: "
                "image-creator/clip" in e
                for e in errors
            ),
            errors,
        )
        self.assertTrue(
            any(
                "creator reference phase plan missing hands subject: "
                "video-creator/clip" in e
                for e in errors
            ),
            errors,
        )

    def test_multiple_verbs_one_subject_deduped(self) -> None:
        self.hands_leaf("image-creator", "generate", "icon")
        self.hands_leaf("image-creator", "edit", "icon")
        subjects = VALIDATOR.collect_hands_subjects()
        self.assertEqual({"icon"}, subjects["image-creator"])

    # ── unknown/rejected shapes ──────────────────────────────────────

    def test_unknown_hands_dir_rejected(self) -> None:
        self.build_valid_tree()
        self.write("references/plan/marketer-creator/icon.md", "# icon\n")
        errors = self.validate()
        self.assertTrue(
            any(
                "unknown hands directory in creator reference phase plan: "
                "marketer-creator" in e
                for e in errors
            ),
            errors,
        )

    def test_deep_dir_rejected(self) -> None:
        self.build_valid_tree()
        self.write("references/plan/image-creator/extra/nested.md", "# nested\n")
        errors = self.validate()
        self.assertTrue(
            any(
                "no nesting below a creator reference hands dir: "
                "plan/image-creator/extra" in e
                for e in errors
            ),
            errors,
        )

    def test_non_markdown_file_rejected(self) -> None:
        self.build_valid_tree()
        self.write("references/plan/image-creator/notes.txt", "notes\n")
        errors = self.validate()
        self.assertTrue(
            any(
                "non-markdown file in creator reference tree: "
                "plan/image-creator/notes.txt" in e
                for e in errors
            ),
            errors,
        )

    def test_empty_subject_file_rejected(self) -> None:
        self.build_valid_tree()
        self.write("references/plan/image-creator/icon.md", "   \n")
        errors = self.validate()
        self.assertTrue(
            any(
                "empty creator reference file: plan/image-creator/icon.md" in e
                for e in errors
            ),
            errors,
        )

    def test_extra_skill_md_rejected(self) -> None:
        self.build_valid_tree()
        self.write("references/plan/image-creator/SKILL.md", "---\n---\n")
        errors = self.validate()
        self.assertTrue(
            any(
                "creator reference tree must not contain SKILL.md: "
                "plan/image-creator/SKILL.md" in e
                for e in errors
            ),
            errors,
        )

    # ── index routing and links ───────────────────────────────────────

    def test_unlinked_index_route_rejected(self) -> None:
        self.build_valid_tree()
        self.write("references/plan/index.md", "- [icon](image-creator/icon.md)\n")
        errors = self.validate()
        self.assertTrue(
            any(
                "phase plan index.md does not link video-creator/clip" in e
                for e in errors
            ),
            errors,
        )

    def test_broken_link_rejected(self) -> None:
        self.build_valid_tree()
        self.write(
            "references/plan/image-creator/icon.md",
            "# icon\n\nSee [missing](missing.md).\n",
        )
        errors = self.validate()
        self.assertTrue(
            any("creator reference link is broken" in e for e in errors), errors
        )

    def test_link_escaping_pipeline_rejected(self) -> None:
        self.build_valid_tree()
        self.write(
            "references/plan/image-creator/icon.md",
            "# icon\n\nSee [outside](../../../../outside.md).\n",
        )
        errors = self.validate()
        self.assertTrue(
            any("creator reference link escapes the pipeline" in e for e in errors),
            errors,
        )

    def test_link_titles_and_angle_brackets_are_parsed(self) -> None:
        self.build_valid_tree()
        self.write(
            "references/plan/image-creator/icon.md",
            "# icon\n\n"
            'See [double](../image-creator/icon.md "title") and '
            "[single](../image-creator/icon.md 'title') and "
            "[angle](<../image-creator/icon.md>).\n",
        )
        self.assertEqual([], self.validate())

    def test_link_title_does_not_leak_into_path(self) -> None:
        self.build_valid_tree()
        self.write(
            "references/plan/image-creator/icon.md",
            '# icon\n\nSee [missing](missing.md "a title with (parens)").\n',
        )
        errors = self.validate()
        self.assertTrue(
            any(
                "creator reference link is broken: missing.md in" in e
                for e in errors
            ),
            errors,
        )

    def test_anchor_and_web_links_are_skipped(self) -> None:
        self.build_valid_tree()
        self.write(
            "references/plan/image-creator/icon.md",
            "# icon\n\n"
            "See [top](#top) and [docs](https://example.com/docs).\n",
        )
        self.assertEqual([], self.validate())

    def test_stale_deleted_monolith_link_is_broken(self) -> None:
        self.build_valid_tree()
        self.write(
            "references/plan/image-creator/icon.md",
            "# icon\n\nSee the old [plan](../../plan.md).\n",
        )
        errors = self.validate()
        self.assertTrue(
            any("creator reference link is broken" in e for e in errors), errors
        )


if __name__ == "__main__":
    unittest.main()
