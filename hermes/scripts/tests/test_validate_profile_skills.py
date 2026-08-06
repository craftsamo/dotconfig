from __future__ import annotations

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "validate-profile-skills.py"
SPEC = importlib.util.spec_from_file_location("validate_profile_skills", SCRIPT)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class AssistantPipelineTreeTest(unittest.TestCase):
    def test_repository_tree_is_valid(self) -> None:
        errors: list[str] = []
        refs, units = VALIDATOR.validate_assistant_pipeline(errors)
        self.assertEqual([], errors)
        self.assertGreater(refs, 0)
        self.assertGreater(units, 0)


class SandboxTreeTest(unittest.TestCase):
    """Structural rules verified against a synthetic tree."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self._original = VALIDATOR.ASSISTANT_PIPELINE
        VALIDATOR.ASSISTANT_PIPELINE = self.root

    def tearDown(self) -> None:
        VALIDATOR.ASSISTANT_PIPELINE = self._original
        self._tmp.cleanup()

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
            self.write(
                f"references/quality-assurance/{capability}/index.md", listing
            )
            for name in names:
                self.write(
                    f"references/quality-assurance/{capability}/{name}", "# c\n"
                )

    def validate(self) -> list[str]:
        errors: list[str] = []
        VALIDATOR.validate_assistant_pipeline(errors)
        return errors

    def test_minimal_tree_passes(self) -> None:
        self.build_minimal_tree()
        self.assertEqual([], self.validate())

    def test_rejects_unknown_mode_dir(self) -> None:
        self.build_minimal_tree()
        self.write("references/deploy/index.md", "# nope\n")
        errors = self.validate()
        self.assertTrue(any("unexpected mode" in e for e in errors), errors)

    def test_rejects_capability_dir_in_chat(self) -> None:
        self.build_minimal_tree()
        self.write("references/chat/creative/index.md", "# nope\n")
        errors = self.validate()
        self.assertTrue(any("must stay flat" in e for e in errors), errors)

    def test_rejects_unrouted_leaf(self) -> None:
        self.build_minimal_tree()
        self.write(
            "references/execute/creative/index.md", "# creative\n"
        )
        self.write("references/execute/creative/pixel-art.md", "# pixel\n")
        errors = self.validate()
        self.assertTrue(any("does not route pixel-art.md" in e for e in errors), errors)

    def test_accepts_valid_card_units(self) -> None:
        self.build_minimal_tree()
        self.write(
            "references/execute/creative/index.md",
            "---\n"
            "card_units:\n"
            "  - name: anchored-image-batch\n"
            "    required_inputs: [approved-style-anchor]\n"
            "    unit_cap: \"one batch\"\n"
            "    runtime_cap: 1800\n"
            "---\n# creative\n",
        )
        self.assertEqual([], self.validate())
        errors: list[str] = []
        _, units = VALIDATOR.validate_assistant_pipeline(errors)
        self.assertEqual(1, units)

    def test_rejects_card_unit_without_runtime_cap(self) -> None:
        self.build_minimal_tree()
        self.write(
            "references/execute/creative/index.md",
            "---\n"
            "card_units:\n"
            "  - name: anchored-image-batch\n"
            "    required_inputs: [anchor]\n"
            "    unit_cap: \"one batch\"\n"
            "---\n# creative\n",
        )
        errors = self.validate()
        self.assertTrue(any("runtime_cap" in e for e in errors), errors)

    def test_rejects_duplicate_card_unit_names(self) -> None:
        self.build_minimal_tree()
        unit = (
            "card_units:\n"
            "  - name: same-unit\n"
            "    required_inputs: [spec]\n"
            "    unit_cap: \"one\"\n"
            "    runtime_cap: 900\n"
        )
        self.write(
            "references/execute/creative/index.md", f"---\n{unit}---\n# a\n"
        )
        self.write(
            "references/execute/research/index.md", f"---\n{unit}---\n# b\n"
        )
        errors = self.validate()
        self.assertTrue(any("duplicate card unit" in e for e in errors), errors)

    def test_rejects_card_units_outside_execute(self) -> None:
        self.build_minimal_tree()
        self.write(
            "references/plan/creative/index.md",
            "---\n"
            "card_units:\n"
            "  - name: sneaky-unit\n"
            "    required_inputs: [spec]\n"
            "    unit_cap: \"one\"\n"
            "    runtime_cap: 900\n"
            "---\n# plan\n",
        )
        errors = self.validate()
        self.assertTrue(any("only legal under execute/" in e for e in errors), errors)

    def test_rejects_missing_qa_contract(self) -> None:
        self.build_minimal_tree()
        (self.root / "references/quality-assurance/writing/prose.md").unlink()
        errors = self.validate()
        self.assertTrue(
            any("quality-assurance/writing/prose.md" in e for e in errors), errors
        )


class EndToEndTest(unittest.TestCase):
    def test_all_profiles_pass(self) -> None:
        result = subprocess.run(
            [str(SCRIPT), "--all"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("PASS:", result.stdout)
        self.assertIn("assistant-pipeline=", result.stdout)


if __name__ == "__main__":
    unittest.main()
