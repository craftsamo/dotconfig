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
    """Creative alignment: the plain-language guides directly under
    plan-assistant-creative/references/ must carry the four client-facing
    headings; local document references (Markdown links and backtick paths)
    are checked, confined to the pipeline root, and never point at a retired
    shelf (including the removed legacy shelf). Every fixture is synthetic,
    below a patched ASSISTANT_PIPELINE / HERMES_ROOT."""

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

    def build_valid_tree(self) -> None:
        self.write(
            "plan-assistant-creative/SKILL.md",
            "Routes [reference-research](references/reference-research.md) and "
            "[raster-guide](references/raster-guide.md).\n",
        )
        self.write(
            "plan-assistant-creative/references/reference-research.md",
            "# reference research\n",
        )
        self.write("plan-assistant-creative/references/raster-guide.md", GUIDE_BODY)
        self.write(
            "execute-assistant-creative/SKILL.md",
            "See [media-ops](references/media-ops.md).\n",
        )
        self.write("execute-assistant-creative/references/media-ops.md", "# media ops\n")
        self.write("execute-assistant-creative/references/card.md", "# card\n")

    def validate(self) -> list[str]:
        errors: list[str] = []
        VALIDATOR.validate_creative_alignment(errors)
        return errors

    def test_valid_tree_passes(self) -> None:
        self.build_valid_tree()
        self.assertEqual([], self.validate())

    def test_guide_name_need_not_equal_a_hands_subject(self) -> None:
        self.build_valid_tree()
        self.write("plan-assistant-creative/references/free-name.md", GUIDE_BODY)
        self.assertEqual([], self.validate())

    def test_reference_research_excluded_from_guide_heading_check(self) -> None:
        self.build_valid_tree()
        self.write(
            "plan-assistant-creative/references/reference-research.md", "# no headings\n"
        )
        self.assertEqual([], self.validate())

    def test_incomplete_guide_reported(self) -> None:
        self.write("plan-assistant-creative/SKILL.md", "bad.md")
        self.write("plan-assistant-creative/references/bad.md", "# incomplete guide")
        errors = self.validate()
        self.assertTrue(any("creative guide missing heading" in e for e in errors))

    def test_missing_client_sections_reported(self) -> None:
        self.build_valid_tree()
        self.write(
            "plan-assistant-creative/references/raster-guide.md",
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

    def test_template_paths_are_not_concrete_links(self) -> None:
        self.build_valid_tree()
        self.write(
            "plan-assistant-creative/references/reference-research.md",
            "Template: `../<deliverable>.md`; actual: `raster-guide.md#units`.",
        )
        self.assertEqual([], self.validate())

    def test_reference_names_can_contain_retired_words(self) -> None:
        self.build_valid_tree()
        self.write("plan-assistant-creative/references/facial-expressions.md", "# example")
        self.write(
            "plan-assistant-creative/references/reference-research.md",
            "See `facial-expressions.md`.",
        )
        errors: list[str] = []
        VALIDATOR.validate_creative_references(self.pipeline_dir, errors)
        self.assertEqual([], errors)

    def test_stale_relative_backtick_path_fails(self) -> None:
        self.build_valid_tree()
        self.write(
            "plan-assistant-creative/references/reference-research.md",
            "# r\n\nSee `../../execute/creative/index.md`.\n",
        )
        errors = self.validate()
        self.assertTrue(
            any("creative reference is broken" in e for e in errors), errors
        )

    def test_escape_path_rejected(self) -> None:
        self.build_valid_tree()
        self.write(
            "plan-assistant-creative/references/reference-research.md",
            "# r\n\nSee `../../../../../../outside/index.md`.\n",
        )
        errors = self.validate()
        self.assertTrue(
            any("creative reference escapes the pipeline" in e for e in errors),
            errors,
        )

    def test_retired_shelf_reference_rejected(self) -> None:
        self.build_valid_tree()
        self.write(
            "plan-assistant-creative/references/raster-guide.md",
            GUIDE_BODY + "\nSee `../expressions/mood.md` for the old palette.\n",
        )
        errors = self.validate()
        self.assertTrue(
            any(
                "creative reference points at a retired shelf" in e for e in errors
            ),
            errors,
        )

    def test_legacy_shelf_reference_rejected(self) -> None:
        self.build_valid_tree()
        self.write("plan-assistant-creative/references/legacy/raster-image.md", "# r\n")
        self.write(
            "plan-assistant-creative/references/raster-guide.md",
            GUIDE_BODY + "\nSee `legacy/raster-image.md`.\n",
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
            "plan-assistant-creative/references/raster-guide.md",
            GUIDE_BODY + "\nThe deliverable is written to `proposal.md`.\n",
        )
        self.assertEqual([], self.validate())

    def test_code_output_paths_are_not_document_references(self) -> None:
        self.build_valid_tree()
        self.write(
            "plan-assistant-creative/references/raster-guide.md",
            GUIDE_BODY + "\n```sh\ncommand --out `OUTPUT/report.md`\n```\n",
        )
        self.assertEqual([], self.validate())

    def test_runtime_fallback_paths_are_not_relative_document_links(self) -> None:
        self.build_valid_tree()
        path = self.pipeline_dir / "plan-assistant-creative/SKILL.md"
        path.write_text(path.read_text() + '\nUse read_file on '
                        '`${HERMES_SKILL_DIR}/../references/plan/index.md`.\n')
        self.assertEqual([], self.validate())

    def test_skill_md_mentions_are_not_treated_as_references(self) -> None:
        self.build_valid_tree()
        self.write(
            "plan-assistant-creative/references/raster-guide.md",
            GUIDE_BODY + "\nSee `image-creator-pipeline/generate/icon/SKILL.md`.\n",
        )
        self.assertEqual([], self.validate())

    def test_valid_markdown_link_and_backtick_reference_pass(self) -> None:
        self.build_valid_tree()
        self.write(
            "plan-assistant-creative/references/raster-guide.md",
            GUIDE_BODY
            + "\nSee [research](reference-research.md) and `reference-research.md`.\n",
        )
        self.assertEqual([], self.validate())


if __name__ == "__main__":
    unittest.main()
