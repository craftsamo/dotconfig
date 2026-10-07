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


class CreatorReferenceFixture(unittest.TestCase):
    """Creator v10 advisor tree: a kernel SKILL.md, the propose-creator and
    revise-creator entries, and flat references/<hands>/<subject>.md
    capability references, with expected subjects collected dynamically from a
    synthetic hands tree below a patched HERMES_ROOT."""

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

    def write(self, rel: str, text: str) -> Path:
        path = self.pipeline_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def hands_leaf(self, hands: str, verb: str, subject: str) -> Path:
        path = (
            self.hermes_root / "profiles" / hands / "skills"
            / f"{hands}-pipeline" / verb / subject / "SKILL.md"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"---\nname: {verb}-{subject}\n---\n", encoding="utf-8")
        return path

    def write_kernel(self, version: str = "10.0.0", links: str | None = None) -> None:
        if links is None:
            links = "\n".join(
                [f"[{n}]({n}/SKILL.md)" for n in VALIDATOR.CREATOR_ENTRIES.values()]
                + [
                    "[icon](references/image-creator/icon.md)",
                    "[clip](references/video-creator/clip.md)",
                ]
            )
        self.write(
            "SKILL.md",
            f"---\nname: creator-pipeline\nversion: {version}\n---\n"
            f"<Goal>\n</Goal>\n{links}\n",
        )

    def write_entry(self, name: str) -> None:
        self.write(
            f"{name}/SKILL.md",
            f"---\nname: {name}\ndescription: Fixture entry\nversion: 1.0.0\n"
            "metadata:\n  hermes:\n    category: creator-pipeline\n---\n"
            '<ReadBeforeWork>\nskill_view(name="creator-pipeline")\n'
            "Reuse the full body, not a summary. If unchanged, read_file\n"
            "${HERMES_SKILL_DIR}/../SKILL.md or ${HERMES_SKILL_DIR}/SKILL.md;\n"
            "follow next_offset on truncation; stop if unavailable.\n</ReadBeforeWork>\n",
        )

    def build_valid_tree(self) -> None:
        self.hands_leaf("image-creator", "generate", "icon")
        self.hands_leaf("video-creator", "generate", "clip")
        self.write_kernel()
        for name in VALIDATOR.CREATOR_ENTRIES.values():
            self.write_entry(name)
        self.write("references/image-creator/icon.md", "# icon\n")
        self.write("references/video-creator/clip.md", "# clip\n")

    def validate(self) -> list[str]:
        errors: list[str] = []
        VALIDATOR.validate_creator_references(self.pipeline_dir, errors)
        return errors


class CreatorReferencesTestCase(CreatorReferenceFixture):
    def test_entries_are_propose_and_revise(self) -> None:
        self.assertEqual(
            {"propose": "propose-creator", "revise": "revise-creator"},
            VALIDATOR.CREATOR_ENTRIES,
        )
        self.assertEqual(10, VALIDATOR.CREATOR_PIPELINE_MAJOR)

    def test_valid_v10_tree_passes(self) -> None:
        self.build_valid_tree()
        self.assertEqual([], self.validate())

    def test_old_versions_rejected(self) -> None:
        for version in ("7.0.0", "8.0.0", "9.0.0"):
            with self.subTest(version=version):
                self.build_valid_tree()
                self.write_kernel(version=version)
                errors = self.validate()
                self.assertTrue(
                    any("creator pipeline must be version 10" in e for e in errors),
                    errors,
                )

    def test_invalid_or_missing_version_is_rejected(self) -> None:
        self.build_valid_tree()
        self.write_kernel(version="v10.0.0")
        self.assertTrue(
            any("creator pipeline must be version 10" in e for e in self.validate())
        )
        self.write("SKILL.md", "---\nname: creator-pipeline\n---\n")
        self.assertTrue(
            any("creator pipeline must be version 10" in e for e in self.validate())
        )

    def test_missing_entry(self) -> None:
        self.build_valid_tree()
        (self.pipeline_dir / "revise-creator/SKILL.md").unlink()
        self.assertIn(
            "missing creator entry skill: revise-creator/SKILL.md", self.validate()
        )

    def test_retired_entries_rejected(self) -> None:
        self.build_valid_tree()
        for name in ("plan-creator", "build-creator", "qa-creator"):
            self.write(f"{name}/SKILL.md", f"---\nname: {name}\n---\n")
        errors = self.validate()
        for name in ("plan-creator", "build-creator", "qa-creator"):
            self.assertIn(f"unexpected creator pipeline child: {name}", errors)

    def test_kernel_must_link_entry(self) -> None:
        self.build_valid_tree()
        kernel = self.pipeline_dir / "SKILL.md"
        kernel.write_text(
            kernel.read_text().replace("[revise-creator](revise-creator/SKILL.md)", "")
        )
        self.assertIn("creator kernel does not link entry: revise-creator", self.validate())

    def test_kernel_must_link_every_reference(self) -> None:
        self.build_valid_tree()
        kernel = self.pipeline_dir / "SKILL.md"
        kernel.write_text(
            kernel.read_text().replace("[clip](references/video-creator/clip.md)", "")
        )
        self.assertIn("creator kernel does not link video-creator/clip", self.validate())

    def test_missing_kernel_dependency(self) -> None:
        self.build_valid_tree()
        entry = self.pipeline_dir / "propose-creator/SKILL.md"
        entry.write_text(
            entry.read_text().replace('skill_view(name="creator-pipeline")', "")
        )
        self.assertTrue(
            any("ReadBeforeWork missing skill_view" in e for e in self.validate())
        )

    def test_missing_recovery_contract(self) -> None:
        self.build_valid_tree()
        entry = self.pipeline_dir / "revise-creator/SKILL.md"
        entry.write_text(entry.read_text().replace("read_file", "remember"))
        self.assertIn(
            "creator entry ReadBeforeWork missing read_file: revise-creator",
            self.validate(),
        )

    def test_entry_with_children_rejected(self) -> None:
        self.build_valid_tree()
        self.write("propose-creator/references/icon.md", "# icon\n")
        self.assertIn(
            "unexpected creator entry child: propose-creator/references", self.validate()
        )

    # ── subject coverage ─────────────────────────────────────────────

    def test_missing_subject_reported(self) -> None:
        self.build_valid_tree()
        (self.pipeline_dir / "references/video-creator/clip.md").unlink()
        self.assertIn(
            "creator references missing hands subject: video-creator/clip",
            self.validate(),
        )

    def test_orphan_subject_reported(self) -> None:
        self.build_valid_tree()
        self.write("references/image-creator/mascot.md", "# mascot\n")
        self.assertIn(
            "creator references have orphan hands subject: image-creator/mascot",
            self.validate(),
        )

    def test_wrong_hands_subject(self) -> None:
        self.build_valid_tree()
        (self.pipeline_dir / "references/video-creator/clip.md").unlink()
        self.write("references/image-creator/clip.md", "# clip\n")
        errors = self.validate()
        self.assertIn(
            "creator references have orphan hands subject: image-creator/clip", errors
        )
        self.assertIn(
            "creator references missing hands subject: video-creator/clip", errors
        )

    def test_multiple_verbs_one_subject_deduped(self) -> None:
        self.hands_leaf("image-creator", "generate", "icon")
        self.hands_leaf("image-creator", "edit", "icon")
        subjects = VALIDATOR.collect_hands_subjects()
        self.assertEqual({"icon"}, subjects["image-creator"])

    # ── unexpected shapes ────────────────────────────────────────────

    def test_unknown_reference_dir_rejected(self) -> None:
        self.build_valid_tree()
        self.write("references/marketer-creator/icon.md", "# icon\n")
        self.assertIn(
            "unexpected creator reference: marketer-creator", self.validate()
        )

    def test_old_phase_tree_rejected(self) -> None:
        self.build_valid_tree()
        self.write("references/plan/index.md", "# Retired\n")
        self.assertIn("unexpected creator reference: plan", self.validate())

    def test_deep_dir_rejected(self) -> None:
        self.build_valid_tree()
        self.write("references/image-creator/extra/nested.md", "# nested\n")
        self.assertIn(
            "no nesting below a creator reference hands dir: image-creator/extra",
            self.validate(),
        )

    def test_non_markdown_file_rejected(self) -> None:
        self.build_valid_tree()
        self.write("references/image-creator/notes.txt", "notes\n")
        self.assertIn(
            "unexpected file in creator references: image-creator/notes.txt",
            self.validate(),
        )

    def test_extra_skill_md_rejected(self) -> None:
        self.build_valid_tree()
        self.write("references/image-creator/SKILL.md", "---\n---\n")
        self.assertIn(
            "unexpected file in creator references: image-creator/SKILL.md",
            self.validate(),
        )

    def test_empty_subject_file_rejected(self) -> None:
        self.build_valid_tree()
        self.write("references/image-creator/icon.md", "   \n")
        self.assertIn(
            "empty creator reference file: image-creator/icon.md", self.validate()
        )

    # ── links ────────────────────────────────────────────────────────

    def test_broken_link_rejected(self) -> None:
        self.build_valid_tree()
        self.write(
            "references/image-creator/icon.md", "# icon\n\nSee [missing](missing.md).\n"
        )
        self.assertTrue(
            any("creator reference link is broken" in e for e in self.validate())
        )

    def test_link_escaping_pipeline_rejected(self) -> None:
        self.build_valid_tree()
        self.write(
            "references/image-creator/icon.md",
            "# icon\n\nSee [outside](../../../../outside.md).\n",
        )
        self.assertTrue(
            any(
                "creator reference link escapes the pipeline" in e
                for e in self.validate()
            )
        )

    def test_link_titles_and_angle_brackets_are_parsed(self) -> None:
        self.build_valid_tree()
        self.write(
            "references/image-creator/icon.md",
            "# icon\n\n"
            'See [double](../image-creator/icon.md "title") and '
            "[single](../image-creator/icon.md 'title') and "
            "[angle](<../image-creator/icon.md>).\n",
        )
        self.assertEqual([], self.validate())

    def test_link_title_does_not_leak_into_path(self) -> None:
        self.build_valid_tree()
        self.write(
            "references/image-creator/icon.md",
            '# icon\n\nSee [missing](missing.md "a title with (parens)").\n',
        )
        self.assertTrue(
            any(
                "creator reference link is broken: missing.md in" in e
                for e in self.validate()
            )
        )

    def test_anchor_and_web_links_are_skipped(self) -> None:
        self.build_valid_tree()
        self.write(
            "references/image-creator/icon.md",
            "# icon\n\nSee [top](#top) and [docs](https://example.com/docs).\n",
        )
        self.assertEqual([], self.validate())

    def test_entry_link_cannot_escape(self) -> None:
        self.build_valid_tree()
        entry = self.pipeline_dir / "propose-creator/SKILL.md"
        entry.write_text(entry.read_text() + "[escape](../../../outside.md)\n")
        self.assertTrue(any("link escapes the pipeline" in e for e in self.validate()))


class CreatorWorkerRootsTestCase(CreatorReferenceFixture):
    def test_worker_allows_only_named_entries(self) -> None:
        self.build_valid_tree()
        skills = self.pipeline_dir.parent
        (skills / "technic").mkdir()
        (skills / "learned").mkdir()
        with mock.patch.object(VALIDATOR, "validate_git_boundary"), mock.patch.object(
            VALIDATOR, "validate_plugin_enabled"
        ):
            errors: list[str] = []
            count, _ = VALIDATOR.validate_worker("creator", errors)
            self.assertEqual([], errors)
            self.assertEqual(2, count)
            self.write("rogue-creator/SKILL.md", "---\nname: rogue-creator\n---\n")
            VALIDATOR.validate_worker("creator", errors)
            self.assertTrue(any("unexpected skill root" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
