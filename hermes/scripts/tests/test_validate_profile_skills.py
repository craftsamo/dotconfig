from __future__ import annotations

import copy
import importlib.util
import subprocess
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "validate-profile-skills.py"
SPEC = importlib.util.spec_from_file_location("validate_profile_skills", SCRIPT)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class WorkflowContractTest(unittest.TestCase):
    def setUp(self) -> None:
        errors: list[str] = []
        contract = VALIDATOR.load_workflow_contract(
            VALIDATOR.WORKFLOW_CONTRACT,
            errors,
        )
        self.assertEqual([], errors)
        self.assertIsNotNone(contract)
        self.contract = contract

    def validate(self, contract: dict) -> list[str]:
        errors: list[str] = []
        VALIDATOR.validate_workflow_contract_data(contract, errors)
        return errors

    def test_repository_contract_is_valid(self) -> None:
        self.assertEqual([], self.validate(self.contract))

    def test_rejects_wrong_version(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["version"] = 1
        errors = self.validate(contract)
        self.assertTrue(any("version" in error for error in errors), errors)

    def test_rejects_extra_specialist(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["specialists"]["planner"] = {
            "capability": "research",
            "pipeline": "planner-pipeline",
            "grant": None,
        }
        errors = self.validate(contract)
        self.assertTrue(any("specialists" in error for error in errors), errors)

    def test_rejects_wrong_mode_set(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["orchestration"]["modes"] = ["chat", "plan", "execute"]
        errors = self.validate(contract)
        self.assertTrue(any("modes" in error for error in errors), errors)

    def test_rejects_double_approval(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["orchestration"]["approval_gates"] = [
            "planning_graph",
            "execution_outline",
        ]
        errors = self.validate(contract)
        self.assertTrue(any("approval gates" in error for error in errors), errors)

    def test_rejects_missing_wrapper(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["resident_session"]["wrapper"] = "assistant/scripts/nonexistent.sh"
        errors = self.validate(contract)
        self.assertTrue(any("wrapper" in error for error in errors), errors)

    def test_rejects_unknown_capability(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["specialists"]["creator"]["capability"] = "media"
        errors = self.validate(contract)
        self.assertTrue(any("capability" in error for error in errors), errors)

    def test_rejects_empty_retired_markers(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["kanban"]["retired_markers"] = []
        errors = self.validate(contract)
        self.assertTrue(any("retired_markers" in error for error in errors), errors)


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
        self.assertIn("workflow-contract=v2", result.stdout)


if __name__ == "__main__":
    unittest.main()
