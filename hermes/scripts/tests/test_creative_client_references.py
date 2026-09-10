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


GUIDE_BODY = (
    "## Use\n\nBody.\n\n"
    "## Client decisions\n\nBody.\n\n"
    "## References\n\nBody.\n\n"
    "## Acceptance\n\nBody.\n"
)


class CreativeClientReferencesTestCase(unittest.TestCase):
    """Creative three-layer alignment after the plain-guide migration:
    plan/creative/legacy/ and quality-assurance/creative/legacy/ keep the
    1:1 creator-technic parity; the new plain-language guides directly
    under plan/creative/ carry no such parity but must carry the four
    client-facing headings; local document references (Markdown links and
    backtick paths) are checked, confined to the pipeline root, and never
    point at a retired shelf. Every fixture here is synthetic, below a
    patched ASSISTANT_PIPELINE / HERMES_ROOT, so nothing leaks from the
    real (private-overlay-backed) repository tree."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.hermes_root = Path(self._tmp.name)
        root_patcher = mock.patch.object(VALIDATOR, "HERMES_ROOT", self.hermes_root)
        root_patcher.start()
        self.addCleanup(root_patcher.stop)

        self.pipeline_dir = (
            self.hermes_root
            / "profiles"
            / "assistant"
            / "skills"
            / "assistant-pipeline"
        )
        self.pipeline_dir.mkdir(parents=True)
        pipeline_patcher = mock.patch.object(
            VALIDATOR, "ASSISTANT_PIPELINE", self.pipeline_dir
        )
        pipeline_patcher.start()
        self.addCleanup(pipeline_patcher.stop)

    def write(self, rel: str, text: str) -> Path:
        path = self.pipeline_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def write_technic(self, name: str) -> Path:
        path = (
            self.hermes_root
            / "profiles"
            / "creator"
            / "skills"
            / "technic"
            / name
            / "SKILL.md"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"---\nname: {name}\n---\n", encoding="utf-8")
        return path

    def build_valid_tree(self) -> None:
        self.write_technic("creator-raster-image")
        self.write_technic("creator-comic")

        self.write(
            "references/plan/creative/index.md",
            "Routes [legacy](legacy/index.md) and "
            "[reference-research](reference-research.md) and "
            "[raster-guide](raster-guide.md).\n",
        )
        self.write(
            "references/plan/creative/reference-research.md", "# reference research\n"
        )
        self.write("references/plan/creative/raster-guide.md", GUIDE_BODY)
        self.write(
            "references/plan/creative/legacy/index.md",
            "asset-set.md composite-media.md raster-image.md comic.md",
        )
        self.write("references/plan/creative/legacy/asset-set.md", "# asset set\n")
        self.write(
            "references/plan/creative/legacy/composite-media.md", "# composite\n"
        )
        self.write("references/plan/creative/legacy/raster-image.md", "# raster\n")
        self.write("references/plan/creative/legacy/comic.md", "# comic\n")

        self.write(
            "references/quality-assurance/creative/index.md",
            "See [legacy](legacy/index.md).\n",
        )
        self.write(
            "references/quality-assurance/creative/legacy/index.md",
            "| # | Contract | Covers |\n"
            "| --- | --- | --- |\n"
            "| 1 | `raster-image.md` | `creator-raster-image` |\n"
            "| 2 | `comic.md` | `creator-comic` |\n",
        )
        self.write(
            "references/quality-assurance/creative/legacy/raster-image.md", "# c\n"
        )
        self.write("references/quality-assurance/creative/legacy/comic.md", "# c\n")

    def validate(self) -> list[str]:
        errors: list[str] = []
        VALIDATOR.validate_creative_alignment(errors)
        return errors

    def test_candidate_isolation_uses_only_patched_roots(self) -> None:
        self.write_technic("creator-nonexistent-synthetic-family")
        self.write(
            "references/plan/creative/index.md",
            "Routes [legacy](legacy/index.md).\n",
        )
        self.write(
            "references/plan/creative/legacy/index.md",
            "nonexistent-synthetic-family.md",
        )
        self.write(
            "references/plan/creative/legacy/nonexistent-synthetic-family.md", "# x\n"
        )
        self.write(
            "references/quality-assurance/creative/index.md",
            "See [legacy](legacy/index.md).\n",
        )
        self.write(
            "references/quality-assurance/creative/legacy/index.md",
            "| # | Contract | Covers |\n"
            "| --- | --- | --- |\n"
            "| 1 | `nonexistent-synthetic-family.md` | "
            "`creator-nonexistent-synthetic-family` |\n",
        )
        self.write(
            "references/quality-assurance/creative/legacy/"
            "nonexistent-synthetic-family.md",
            "# c\n",
        )
        self.assertEqual([], self.validate())

    def test_valid_tree_passes(self) -> None:
        self.build_valid_tree()
        self.assertEqual([], self.validate())

    def test_missing_entire_legacy_shelf_does_not_skip_guides(self) -> None:
        self.write_technic("creator-comic")
        self.write("references/plan/creative/index.md", "bad.md")
        self.write("references/plan/creative/bad.md", "# incomplete guide")
        errors = self.validate()
        self.assertTrue(any("missing creative plan legacy shelf" in e for e in errors))
        self.assertTrue(any("creative guide missing heading" in e for e in errors))

    def test_template_paths_are_not_concrete_links(self) -> None:
        self.build_valid_tree()
        self.write("references/plan/creative/reference-research.md",
                   "Template: `../<deliverable>.md`; actual: `legacy/index.md#units`.")
        self.assertEqual([], self.validate())

    def test_reference_names_can_contain_retired_words(self) -> None:
        self.build_valid_tree()
        self.write("references/plan/creative/legacy/facial-expressions.md", "# example")
        self.write("references/plan/creative/reference-research.md",
                   "See `legacy/facial-expressions.md`.")
        errors: list[str] = []
        VALIDATOR.validate_creative_references(self.pipeline_dir, errors)
        self.assertEqual([], errors)

    def test_missing_legacy_leaf_reported(self) -> None:
        self.build_valid_tree()
        (self.pipeline_dir / "references/plan/creative/legacy/comic.md").unlink()
        self.write(
            "references/plan/creative/legacy/index.md",
            "asset-set.md composite-media.md raster-image.md",
        )
        errors = self.validate()
        self.assertTrue(
            any(
                "creative legacy leaf missing for canonical family: comic.md" in e
                for e in errors
            ),
            errors,
        )

    def test_orphan_legacy_leaf_reported(self) -> None:
        self.build_valid_tree()
        self.write("references/plan/creative/legacy/pixel-art.md", "# pixel\n")
        self.write(
            "references/plan/creative/legacy/index.md",
            "asset-set.md composite-media.md raster-image.md comic.md pixel-art.md",
        )
        errors = self.validate()
        self.assertTrue(
            any(
                "creative legacy leaf has no canonical family: pixel-art.md" in e
                for e in errors
            ),
            errors,
        )

    def test_new_guide_name_need_not_equal_a_hands_family(self) -> None:
        self.build_valid_tree()
        self.assertEqual([], self.validate())

    def test_missing_client_sections_reported(self) -> None:
        self.build_valid_tree()
        self.write(
            "references/plan/creative/raster-guide.md",
            "## Use\n\nBody.\n\n## References\n\nBody.\n\n## Acceptance\n\nBody.\n",
        )
        errors = self.validate()
        self.assertTrue(
            any(
                "creative guide missing heading '## Client decisions'" in e
                for e in errors
            ),
            errors,
        )

    def test_common_roots_excluded_from_guide_heading_check(self) -> None:
        self.build_valid_tree()
        self.assertEqual([], self.validate())

    def test_missing_covers_reported(self) -> None:
        self.build_valid_tree()
        self.write(
            "references/quality-assurance/creative/legacy/index.md",
            "| # | Contract | Covers |\n"
            "| --- | --- | --- |\n"
            "| 1 | `raster-image.md` | `creator-raster-image` |\n",
        )
        errors = self.validate()
        self.assertTrue(
            any(
                "creative QA Covers misses canonical family: creator-comic" in e
                for e in errors
            ),
            errors,
        )

    def test_duplicate_covers_reported(self) -> None:
        self.build_valid_tree()
        self.write(
            "references/quality-assurance/creative/legacy/index.md",
            "| # | Contract | Covers |\n"
            "| --- | --- | --- |\n"
            "| 1 | `raster-image.md` | `creator-raster-image` `creator-raster-image` |\n"
            "| 2 | `comic.md` | `creator-comic` |\n",
        )
        errors = self.validate()
        self.assertTrue(
            any(
                "creative QA Covers lists creator-raster-image 2 times "
                "(must be once)" in e
                for e in errors
            ),
            errors,
        )

    def test_stale_relative_backtick_path_fails(self) -> None:
        self.build_valid_tree()
        self.write(
            "references/plan/creative/legacy/raster-image.md",
            "# raster\n\nSee `../../execute/creative/index.md`.\n",
        )
        errors = self.validate()
        self.assertTrue(
            any("creative reference is broken" in e for e in errors), errors
        )

    def test_escape_path_rejected(self) -> None:
        self.build_valid_tree()
        self.write(
            "references/plan/creative/legacy/raster-image.md",
            "# raster\n\nSee `../../../../../../outside/index.md`.\n",
        )
        errors = self.validate()
        self.assertTrue(
            any("creative reference escapes the pipeline" in e for e in errors),
            errors,
        )

    def test_retired_shelf_reference_rejected(self) -> None:
        self.build_valid_tree()
        self.write(
            "references/plan/creative/raster-guide.md",
            GUIDE_BODY + "\nSee `../expressions/mood.md` for the old palette.\n",
        )
        errors = self.validate()
        self.assertTrue(
            any(
                "creative reference points at a retired shelf" in e for e in errors
            ),
            errors,
        )

    def test_produced_artifact_filenames_are_not_treated_as_references(self) -> None:
        self.build_valid_tree()
        self.write(
            "references/plan/creative/raster-guide.md",
            GUIDE_BODY + "\nThe deliverable is written to `proposal.md`.\n",
        )
        self.assertEqual([], self.validate())

    def test_skill_md_mentions_are_not_treated_as_references(self) -> None:
        self.build_valid_tree()
        self.write(
            "references/plan/creative/raster-guide.md",
            GUIDE_BODY + "\nSee `image-creator-pipeline/generate/icon/SKILL.md`.\n",
        )
        self.assertEqual([], self.validate())

    def test_valid_markdown_link_and_backtick_reference_pass(self) -> None:
        self.build_valid_tree()
        self.write(
            "references/plan/creative/raster-guide.md",
            GUIDE_BODY
            + "\nSee [legacy](legacy/index.md) and `legacy/raster-image.md`.\n",
        )
        self.assertEqual([], self.validate())


class CreativeLegacyShelfStructureTestCase(unittest.TestCase):
    """Structural rules for the flat creative/legacy/ shelf and its
    card_units restriction, verified via validate_assistant_pipeline
    against a synthetic ASSISTANT_PIPELINE."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        patcher = mock.patch.object(VALIDATOR, "ASSISTANT_PIPELINE", self.root)
        patcher.start()
        self.addCleanup(patcher.stop)

    def write(self, rel: str, text: str) -> Path:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def build_minimal_tree(self) -> None:
        self.write(
            "SKILL.md",
            "---\n"
            "name: assistant-pipeline\n"
            "metadata:\n  hermes:\n    category: orchestration\n"
            "---\n# skill\n",
        )
        self.write("references/chat/index.md", "workspace-ops.md cron.md lookups.md")
        self.write("references/chat/workspace-ops.md", "# ops\n")
        self.write("references/chat/cron.md", "# cron\n")
        self.write("references/chat/lookups.md", "# lookups\n")
        self.write("references/plan/index.md", "# plan\n")
        self.write(
            "references/execute/index.md",
            "resident-sessions.md kanban-lite.md scheduled.md",
        )
        self.write("references/execute/resident-sessions.md", "# sessions\n")
        self.write("references/execute/kanban-lite.md", "# kanban\n")
        self.write("references/execute/scheduled.md", "# scheduled\n")
        self.write("references/quality-assurance/index.md", "# qa\n")
        for capability, names in VALIDATOR.REQUIRED_QA_CONTRACTS.items():
            listing = " ".join(sorted(names))
            if capability in VALIDATOR.QA_CONTRACT_LEGACY_CAPABILITIES:
                self.write(
                    f"references/quality-assurance/{capability}/index.md",
                    "legacy/index.md",
                )
                self.write(
                    f"references/quality-assurance/{capability}/legacy/index.md",
                    listing,
                )
                for name in names:
                    self.write(
                        f"references/quality-assurance/{capability}/legacy/{name}",
                        "# c\n",
                    )
                continue
            self.write(f"references/quality-assurance/{capability}/index.md", listing)
            for name in names:
                self.write(f"references/quality-assurance/{capability}/{name}", "# c\n")

    def build_execute_legacy_shelf(self) -> None:
        self.write(
            "references/execute/creative/index.md",
            "---\n"
            "card_units:\n"
            "  - name: anchored-image-batch\n"
            "    assignee: creator\n"
            "    required_inputs: [approved-style-anchor]\n"
            '    unit_cap: "one batch"\n'
            "    runtime_cap: 1800\n"
            "  - name: deterministic-render\n"
            "    assignee: creator\n"
            "    required_inputs: [approved-spec]\n"
            '    unit_cap: "one render"\n'
            "    runtime_cap: 1800\n"
            "---\n"
            "media-ops.md legacy/index.md\n",
        )
        self.write("references/execute/creative/media-ops.md", "# media ops\n")
        self.write("references/execute/creative/legacy/index.md", "raster-image.md")
        self.write("references/execute/creative/legacy/raster-image.md", "# raster\n")

    def validate(self) -> list[str]:
        errors: list[str] = []
        VALIDATOR.validate_assistant_pipeline(errors)
        return errors

    def test_valid_execute_legacy_shelf_passes(self) -> None:
        self.build_minimal_tree()
        self.build_execute_legacy_shelf()
        self.assertEqual([], self.validate())

    def test_unrouted_legacy_directory_rejected(self) -> None:
        self.build_minimal_tree()
        self.build_execute_legacy_shelf()
        self.write(
            "references/execute/creative/index.md",
            "---\n"
            "card_units:\n"
            "  - name: anchored-image-batch\n"
            "    assignee: creator\n"
            "    required_inputs: [approved-style-anchor]\n"
            '    unit_cap: "one batch"\n'
            "    runtime_cap: 1800\n"
            "  - name: deterministic-render\n"
            "    assignee: creator\n"
            "    required_inputs: [approved-spec]\n"
            '    unit_cap: "one render"\n'
            "    runtime_cap: 1800\n"
            "---\n"
            "media-ops.md\n",
        )
        errors = self.validate()
        self.assertTrue(
            any(
                "capability index does not route legacy/index.md" in e
                for e in errors
            ),
            errors,
        )

    def test_nested_deeper_dir_in_legacy_rejected(self) -> None:
        self.build_minimal_tree()
        self.build_execute_legacy_shelf()
        self.write("references/execute/creative/legacy/group/inner.md", "# nested\n")
        self.write(
            "references/execute/creative/legacy/index.md", "raster-image.md group/"
        )
        errors = self.validate()
        self.assertTrue(
            any("no nesting below the creative legacy shelf" in e for e in errors),
            errors,
        )

    def test_non_markdown_file_in_legacy_rejected(self) -> None:
        self.build_minimal_tree()
        self.build_execute_legacy_shelf()
        self.write("references/execute/creative/legacy/notes.txt", "notes\n")
        self.write(
            "references/execute/creative/legacy/index.md",
            "raster-image.md notes.txt",
        )
        errors = self.validate()
        self.assertTrue(any("non-markdown reference" in e for e in errors), errors)

    def test_nested_card_units_in_legacy_rejected(self) -> None:
        self.build_minimal_tree()
        self.build_execute_legacy_shelf()
        self.write(
            "references/execute/creative/legacy/raster-image.md",
            "---\n"
            "card_units:\n"
            "  - name: sneaky-card\n"
            "    assignee: creator\n"
            "    required_inputs: [x]\n"
            '    unit_cap: "one"\n'
            "    runtime_cap: 60\n"
            "---\n# raster\n",
        )
        errors = self.validate()
        self.assertTrue(
            any(
                "card_units are not permitted in the creative legacy shelf" in e
                for e in errors
            ),
            errors,
        )


if __name__ == "__main__":
    unittest.main()
