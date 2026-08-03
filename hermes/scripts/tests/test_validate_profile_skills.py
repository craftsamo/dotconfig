from __future__ import annotations

import copy
import importlib.util
import shutil
import tempfile
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

    def validate(self, contract: dict, hermes_root: Path | None = None) -> list[str]:
        errors: list[str] = []
        VALIDATOR.validate_workflow_contract_data(
            contract,
            errors,
            hermes_root or VALIDATOR.HERMES_ROOT,
        )
        return errors

    def test_repository_contract_is_valid(self) -> None:
        self.assertEqual([], self.validate(self.contract))

    def test_missing_worker_is_rejected(self) -> None:
        contract = copy.deepcopy(self.contract)
        del contract["workers"]["planner"]

        errors = self.validate(contract)

        self.assertTrue(
            any("workers must be exactly" in error for error in errors), errors
        )

    def test_unknown_qa_technic_is_rejected(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["qa_routes"]["creator-generated-image"][0]["technic"] = (
            "qa-missing"
        )

        errors = self.validate(contract)

        self.assertTrue(
            any("names unknown technic qa-missing" in error for error in errors), errors
        )

    def test_schema_field_cannot_be_required_and_optional(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["schemas"]["task_spec"]["optional"].append("goal")

        errors = self.validate(contract)

        self.assertTrue(
            any("repeats fields as required and optional" in error for error in errors),
            errors,
        )

    def test_task_spec_input_attachments_must_be_required(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["schemas"]["task_spec"]["required"].remove("input_attachments")
        contract["schemas"]["task_spec"]["optional"].append("input_attachments")

        errors = self.validate(contract)

        self.assertIn(
            "workflow contract task_spec must require input_attachments",
            errors,
        )

    def test_missing_technic_directory_is_rejected(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["workers"]["engineer"]["technics"]["active"].append(
            "missing-technic"
        )

        errors = self.validate(contract)

        self.assertTrue(
            any("names missing engineer technic" in error for error in errors), errors
        )

    def test_unknown_worker_mode_is_rejected(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["workers"]["searcher"]["modes"].append("execute")

        errors = self.validate(contract)

        self.assertTrue(
            any("searcher modes must be exactly" in error for error in errors), errors
        )

    def test_missing_worker_mode_is_rejected(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["workers"]["creator"]["modes"].remove("plan")

        errors = self.validate(contract)

        self.assertTrue(
            any("creator modes must be exactly" in error for error in errors), errors
        )

    def test_worker_card_creation_must_stay_forbidden(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["orchestration"]["worker_card_creation"] = "allowed"

        errors = self.validate(contract)

        self.assertIn("workflow contract must forbid worker card creation", errors)

    def test_worker_pipelines_are_enforced(self) -> None:
        self.assertEqual(
            "worker_pipelines_enforced", self.contract["migration"]["state"]
        )
        self.assertEqual([], self.contract["migration"]["pending_enforcement"])

    def test_worker_lifecycle_order_is_enforced(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["worker_lifecycle"]["phases"].reverse()

        errors = self.validate(contract)

        self.assertIn(
            "workflow contract worker lifecycle has the wrong phase order", errors
        )

    def test_digest_sentinel_is_limited_to_non_terminal_profiles(self) -> None:
        resolution = self.contract["worker_lifecycle"]["digest_resolution"]

        self.assertEqual("pending-assistant-probe", resolution["sentinel"])
        self.assertEqual(
            {"planner", "writer", "researcher"}, set(resolution["profiles"])
        )

    def test_execution_shapes_are_closed(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["orchestration"]["execution_shapes"].remove("planned")

        errors = self.validate(contract)

        self.assertTrue(
            any("execution shapes must be" in error for error in errors), errors
        )

    def test_planning_flow_order_is_enforced(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["orchestration"]["planning_flow"].reverse()

        errors = self.validate(contract)

        self.assertIn("workflow contract planning flow has the wrong order", errors)

    def test_specialist_and_evidence_profiles_are_disjoint(self) -> None:
        orchestration = self.contract["orchestration"]

        self.assertEqual(
            set(VALIDATOR.PLANNING_SPECIALIST_PROFILES),
            set(orchestration["specialist_planners"]),
        )
        self.assertEqual(
            set(VALIDATOR.PLANNING_EVIDENCE_PROFILES),
            set(orchestration["evidence_workers"]),
        )
        self.assertTrue(
            set(orchestration["specialist_planners"]).isdisjoint(
                orchestration["evidence_workers"]
            )
        )

    def test_evidence_worker_cannot_be_a_specialist_planner(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["orchestration"]["specialist_planners"].append("searcher")

        errors = self.validate(contract)

        self.assertTrue(
            any("specialist planners must be" in error for error in errors), errors
        )

    def test_fan_out_binding_is_enforced(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["bindings"]["fan_out_manifest"]["marker"] = "FAN_OUT:"

        errors = self.validate(contract)

        self.assertTrue(
            any("fan_out_manifest marker" in error for error in errors), errors
        )

    def test_fan_out_policy_requires_purpose(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["schemas"]["fan_out_policy"]["required"].remove("purpose")

        errors = self.validate(contract)

        self.assertIn(
            "workflow contract fan_out_policy has the wrong required fields",
            errors,
        )

    def test_fan_out_manifest_requires_attachments(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["schemas"]["fan_out_manifest"]["required"].remove(
            "attachments"
        )

        errors = self.validate(contract)

        self.assertIn(
            "workflow contract fan_out_manifest has the wrong required fields",
            errors,
        )

    def test_specialist_plan_is_final_and_exclusive(self) -> None:
        binding = self.contract["bindings"]["specialist_plan"]
        self.assertEqual(
            "exactly_one_on_final_plan_completion",
            binding["cardinality"],
        )
        self.assertEqual("FAN_OUT_READY", binding["exclusive_with"])

    def test_completion_and_artifact_bindings_are_enforced(self) -> None:
        self.assertEqual(
            "metadata.completion",
            self.contract["bindings"]["completion_envelope"]["envelope_path"],
        )
        self.assertEqual(
            "metadata.artifact_handoff",
            self.contract["bindings"]["artifact_handoff"]["envelope_path"],
        )
        self.assertEqual(
            "kanban_complete.summary",
            self.contract["bindings"]["completion_envelope"]["summary_match"],
        )

    def test_pending_registration_manifest_is_durable(self) -> None:
        schema = self.contract["schemas"]["pending_registration_manifest"]
        binding = self.contract["bindings"]["pending_registration_manifest"]

        self.assertEqual({"anchor", "digest", "cards"}, set(schema["required"]))
        self.assertEqual("ORCHESTRATION_PENDING:", binding["marker"])
        self.assertEqual(
            "root_body_or_integration_comment", binding["storage"]
        )

    def test_qa_verdict_required_fields_are_closed(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["schemas"]["qa_verdict"]["required"].remove("target_task")

        errors = self.validate(contract)

        self.assertIn("workflow contract qa_verdict has the wrong required fields", errors)

    def test_qa_handoff_is_discriminated(self) -> None:
        schema = self.contract["schemas"]["qa_handoff"]

        self.assertEqual(["status"], schema["required"])
        self.assertEqual(
            {"capability", "routes", "consumer", "ledger", "reason"},
            set(schema["optional"]),
        )

    def test_recovery_lineage_is_closed(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["schemas"]["recovery_lineage"]["required"].remove("spec_digest")

        errors = self.validate(contract)

        self.assertIn(
            "workflow contract recovery_lineage has the wrong required fields",
            errors,
        )

    def test_pending_overlay_required_fields_are_closed(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["schemas"]["pending_registration_overlay"]["required"].remove(
            "lineage"
        )

        errors = self.validate(contract)

        self.assertIn(
            "workflow contract pending_registration_overlay has the wrong required fields",
            errors,
        )

    def test_pending_overlay_binding_is_durable(self) -> None:
        binding = self.contract["bindings"]["pending_registration_overlay"]

        self.assertEqual("ORCHESTRATION_PENDING_OVERLAY:", binding["marker"])
        self.assertEqual("fan_out_origin_comment", binding["storage"])

    def test_completion_envelope_cannot_expose_top_level_fan_out(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["schemas"]["completion_envelope"]["optional"].append("fan_out")

        errors = self.validate(contract)

        self.assertIn(
            "workflow contract completion_envelope must not carry fan-out",
            errors,
        )

    def test_scheduled_until_is_optional(self) -> None:
        scheduled = self.contract["dialogue_events"]["scheduled"]
        self.assertEqual(["reason"], scheduled["required"])
        self.assertEqual(["until"], scheduled["optional"])

    def test_decision_is_bound_to_one_block_generation(self) -> None:
        decision = self.contract["dialogue_events"]["decision"]

        self.assertEqual(
            {"question_id", "choice", "block_event", "block_digest"},
            set(decision["required"]),
        )

    def test_integration_key_carries_revision_digest(self) -> None:
        key = self.contract["registration"]["idempotency_keys"][
            "planner_integration"
        ]
        self.assertIn("<request-run-id>", key)
        self.assertIn("<revision-digest>", key)

    def test_retry_and_replacement_keys_are_distinct(self) -> None:
        registration = self.contract["registration"]

        self.assertEqual(
            "same_key_same_immutable_spec",
            registration["retry_semantics"]["transport_replay"],
        )
        self.assertIn(
            "<spec-digest>", registration["idempotency_keys"]["recovery"]
        )
        self.assertIn(
            "<failed-qa-id>", registration["idempotency_keys"]["revision"]
        )

    def test_version_must_be_an_integer(self) -> None:
        for invalid in (True, 1.0):
            with self.subTest(version=invalid):
                contract = copy.deepcopy(self.contract)
                contract["version"] = invalid

                errors = self.validate(contract)

                self.assertIn("workflow contract version must be 1", errors)

    def test_duplicate_yaml_key_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "contract.yaml"
            path.write_text("version: 1\nversion: 1\n", encoding="utf-8")
            errors: list[str] = []

            contract = VALIDATOR.load_workflow_contract(path, errors)

        self.assertIsNone(contract)
        self.assertTrue(
            any("found duplicate key 'version'" in error for error in errors), errors
        )

    def test_invalid_yaml_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "contract.yaml"
            path.write_text("version: [\n", encoding="utf-8")
            errors: list[str] = []

            contract = VALIDATOR.load_workflow_contract(path, errors)

        self.assertIsNone(contract)
        self.assertTrue(any("invalid workflow contract YAML" in error for error in errors))

    def test_unhashable_yaml_key_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "contract.yaml"
            path.write_text("? [bad]\n: value\n", encoding="utf-8")
            errors: list[str] = []

            contract = VALIDATOR.load_workflow_contract(path, errors)

        self.assertIsNone(contract)
        self.assertTrue(
            any("found an unhashable mapping key" in error for error in errors), errors
        )

    def test_missing_capability_tables_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            errors = self.validate(self.contract, Path(directory))

        self.assertTrue(
            any("Creator capability table not found" in error for error in errors),
            errors,
        )
        self.assertTrue(
            any("QA capability table not found" in error for error in errors), errors
        )

    def test_unknown_qa_condition_is_rejected(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["qa_routes"]["creator-generated-image"][0]["condition"] = (
            "sometimes"
        )

        errors = self.validate(contract)

        self.assertTrue(
            any("names unknown condition sometimes" in error for error in errors), errors
        )


class AssistantOrchestrationContractTest(unittest.TestCase):
    def test_repository_assistant_contract_is_valid(self) -> None:
        errors: list[str] = []

        VALIDATOR.validate_assistant_orchestration_contract(errors)

        self.assertEqual([], errors)

    def test_planning_graph_task_spec_requires_input_attachments(self) -> None:
        plan_reference = (
            VALIDATOR.HERMES_ROOT
            / "skills"
            / "orchestration"
            / "references"
            / "plan.md"
        )
        text = plan_reference.read_text(encoding="utf-8").replace(
            "      input_attachments: []\n", "", 1
        )
        errors: list[str] = []

        VALIDATOR.validate_markdown_contract_examples(
            text, "planned workflow", errors
        )

        self.assertTrue(
            any(
                "TaskSpec example misses required fields: input_attachments" in error
                for error in errors
            ),
            errors,
        )

    def test_fanout_child_task_spec_requires_input_attachments(self) -> None:
        orchestration = VALIDATOR.HERMES_ROOT / "skills" / "orchestration" / "SKILL.md"
        text = orchestration.read_text(encoding="utf-8")
        fanout_start = text.index("<FanOutManifest>")
        child_start = text.index("    task_spec:\n", fanout_start)
        child_end = text.index("continuation:\n", child_start)
        child = text[child_start:child_end]
        broken_child = child.replace("      input_attachments: []\n", "", 1)
        broken_text = text[:child_start] + broken_child + text[child_end:]
        errors: list[str] = []

        VALIDATOR.validate_markdown_contract_examples(
            broken_text, "orchestration", errors
        )

        self.assertTrue(
            any(
                "TaskSpec example misses required fields: input_attachments" in error
                for error in errors
            ),
            errors,
        )

    def test_fanout_continuation_task_spec_requires_input_attachments(self) -> None:
        orchestration = VALIDATOR.HERMES_ROOT / "skills" / "orchestration" / "SKILL.md"
        text = orchestration.read_text(encoding="utf-8")
        fanout_start = text.index("<FanOutManifest>")
        continuation_start = text.index("continuation:\n", fanout_start)
        task_spec_start = text.index("  task_spec:\n", continuation_start)
        task_spec_end = text.index("attachments:\n", task_spec_start)
        task_spec = text[task_spec_start:task_spec_end]
        broken_task_spec = task_spec.replace("    input_attachments: []\n", "", 1)
        broken_text = (
            text[:task_spec_start] + broken_task_spec + text[task_spec_end:]
        )
        errors: list[str] = []

        VALIDATOR.validate_markdown_contract_examples(
            broken_text, "orchestration", errors
        )

        self.assertTrue(
            any(
                "TaskSpec example misses required fields: input_attachments" in error
                for error in errors
            ),
            errors,
        )


class SpecialistPlanningContractTest(unittest.TestCase):
    def copy_specialist_contracts(self, root: Path) -> None:
        for profile in VALIDATOR.PLANNING_SPECIALIST_PROFILES:
            source = VALIDATOR.HERMES_ROOT / "profiles" / profile
            target = root / "profiles" / profile
            target.mkdir(parents=True)
            shutil.copy2(source / "config.yaml", target / "config.yaml")
            shutil.copy2(source / "profile.yaml", target / "profile.yaml")
            shutil.copytree(
                source / "skills" / f"{profile}-pipeline",
                target / "skills" / f"{profile}-pipeline",
            )
        planner = VALIDATOR.HERMES_ROOT / "profiles" / "planner"
        planner_target = root / "profiles" / "planner"
        planner_target.mkdir(parents=True)
        shutil.copy2(planner / "config.yaml", planner_target / "config.yaml")
        shutil.copy2(planner / "profile.yaml", planner_target / "profile.yaml")
        shutil.copytree(
            planner / "skills" / "planner-pipeline",
            planner_target / "skills" / "planner-pipeline",
        )
        plan_reference = root / "skills" / "orchestration" / "references"
        plan_reference.mkdir(parents=True)
        shutil.copy2(
            VALIDATOR.HERMES_ROOT
            / "skills"
            / "orchestration"
            / "references"
            / "plan.md",
            plan_reference / "plan.md",
        )

    def test_repository_specialist_planning_contract_is_valid(self) -> None:
        errors: list[str] = []

        VALIDATOR.validate_specialist_planning_contract(errors)

        self.assertEqual([], errors)

    def test_planner_input_contract_requires_request_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.copy_specialist_contracts(root)
            pipeline = (
                root
                / "profiles"
                / "planner"
                / "skills"
                / "planner-pipeline"
                / "SKILL.md"
            )
            pipeline.write_text(
                pipeline.read_text(encoding="utf-8").replace(
                    "Request run: <RequirementSpec request_id>\n", "", 1
                ),
                encoding="utf-8",
            )
            errors: list[str] = []

            VALIDATOR.validate_specialist_planning_contract(errors, root)

        self.assertTrue(
            any(
                "Planner InputContract missing 'Request run:'" in error
                for error in errors
            ),
            errors,
        )

    def test_planner_integration_requires_input_attachments(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.copy_specialist_contracts(root)
            plan_reference = root / "skills" / "orchestration" / "references" / "plan.md"
            text = plan_reference.read_text(encoding="utf-8")
            integration_start = text.index("## Planner integration")
            integration_end = text.find("\n## ", integration_start + 3)
            integration = text[
                integration_start:
                integration_end if integration_end != -1 else len(text)
            ]
            broken_integration = integration.replace(
                "Input attachments: []\n", "", 1
            )
            plan_reference.write_text(
                text[:integration_start]
                + broken_integration
                + text[integration_end if integration_end != -1 else len(text):],
                encoding="utf-8",
            )
            errors: list[str] = []

            VALIDATOR.validate_specialist_planning_contract(errors, root)

        self.assertTrue(
            any(
                "Planner integration section missing 'Input attachments:'" in error
                for error in errors
            ),
            errors,
        )

    def test_specialist_plan_sibling_call_token_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.copy_specialist_contracts(root)
            reference = (
                root
                / "profiles"
                / "engineer"
                / "skills"
                / "engineer-pipeline"
                / "references"
                / "specialist-plan.md"
            )
            reference.write_text(
                reference.read_text(encoding="utf-8").replace(
                    '"specialist_plan": SPECIALIST_PLAN',
                    '"specialist_plan": SPECIALIST_RESULT',
                ),
                encoding="utf-8",
            )
            errors: list[str] = []

            VALIDATOR.validate_specialist_planning_contract(errors, root)

        self.assertTrue(
            any(
                "engineer specialist planning contract missing "
                "'\"specialist_plan\": SPECIALIST_PLAN'" in error
                for error in errors
            ),
            errors,
        )

    def test_specialist_profiles_match_workflow_contract(self) -> None:
        errors: list[str] = []
        contract = VALIDATOR.load_workflow_contract(
            VALIDATOR.WORKFLOW_CONTRACT,
            errors,
        )

        self.assertEqual([], errors)
        self.assertIsNotNone(contract)
        assert contract is not None
        for profile in VALIDATOR.PLANNING_SPECIALIST_PROFILES:
            self.assertEqual(
                ["plan", "execute"],
                contract["workers"][profile]["modes"],
            )
        self.assertEqual(["integrate"], contract["workers"]["planner"]["modes"])

    def test_markdown_param_keys_detect_domain_fields(self) -> None:
        text = """\
```yaml
params:
  workspace_kind: scratch
  mode: plan
task_spec:
  mode: plan
```
"""

        self.assertEqual(
            {"workspace_kind", "mode"},
            VALIDATOR.markdown_param_keys(text),
        )

    def test_markdown_contract_rejects_domain_params(self) -> None:
        errors: list[str] = []
        text = """\
```yaml
params:
  workspace_kind: scratch
  planning_branch: branch-a
```
"""

        VALIDATOR.validate_markdown_contract_examples(text, "fixture", errors)

        self.assertTrue(any("Kanban params" in error for error in errors), errors)

    def test_markdown_contract_rejects_incomplete_task_spec(self) -> None:
        errors: list[str] = []
        text = """\
```yaml
task_spec:
  mode: plan
  goal: plan it
```
"""

        VALIDATOR.validate_markdown_contract_examples(text, "fixture", errors)

        self.assertTrue(any("TaskSpec example misses" in error for error in errors), errors)

    def test_markdown_contract_rejects_assignee_mode_mismatch(self) -> None:
        errors: list[str] = []
        text = """\
```yaml
assignee: searcher
task_spec:
  mode: execute
  goal: retrieve facts
  inputs: supplied facts
  done_criteria: sources returned
  output: source list
  constraints: read only
```
"""

        VALIDATOR.validate_markdown_contract_examples(text, "fixture", errors)

        self.assertTrue(any("assigns mode execute" in error for error in errors), errors)

    def test_markdown_contract_rejects_incomplete_continuation(self) -> None:
        errors: list[str] = []
        text = """\
```yaml
continuation:
  assignee: writer
  skills: [writer-pipeline]
  params: {workspace_kind: scratch}
  task_spec:
    mode: plan
    goal: finish planning
    inputs: parent results
    done_criteria: plan returned
    output: SpecialistPlan
    constraints: read only
```
"""

        VALIDATOR.validate_markdown_contract_examples(text, "fixture", errors)

        self.assertTrue(
            any("continuation example misses" in error for error in errors), errors
        )


class WorkerPipelineContractTest(unittest.TestCase):
    def copy_worker_contracts(self, root: Path) -> None:
        for profile in VALIDATOR.WORKER_PROFILES:
            source = VALIDATOR.HERMES_ROOT / "profiles" / profile
            target = root / "profiles" / profile
            target.mkdir(parents=True)
            shutil.copy2(source / "config.yaml", target / "config.yaml")
            shutil.copytree(
                source / "skills" / f"{profile}-pipeline",
                target / "skills" / f"{profile}-pipeline",
            )

    def test_repository_worker_pipeline_contract_is_valid(self) -> None:
        errors: list[str] = []

        VALIDATOR.validate_worker_pipeline_contract(errors)

        self.assertEqual([], errors)

    def test_qa_digest_lifecycle_token_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.copy_worker_contracts(root)
            pipeline = (
                root
                / "profiles"
                / "qa"
                / "skills"
                / "qa-pipeline"
                / "SKILL.md"
            )
            pipeline.write_text(
                pipeline.read_text(encoding="utf-8").replace(
                    "The sentinel alone is not a finding.", "", 1
                ),
                encoding="utf-8",
            )
            errors: list[str] = []

            VALIDATOR.validate_worker_pipeline_contract(errors, root)

        self.assertTrue(
            any(
                "missing 'The sentinel alone is not a finding.'" in error
                for error in errors
            ),
            errors,
        )

    def test_worker_owned_card_creation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.copy_worker_contracts(root)
            gather = (
                root
                / "profiles"
                / "researcher"
                / "skills"
                / "researcher-pipeline"
                / "references"
                / "gather.md"
            )
            gather.write_text(
                gather.read_text(encoding="utf-8") + "\nkanban_create\n",
                encoding="utf-8",
            )
            errors: list[str] = []

            VALIDATOR.validate_worker_pipeline_contract(errors, root)

        self.assertTrue(
            any("retains forbidden text 'kanban_create'" in error for error in errors),
            errors,
        )

    def test_missing_completion_binding_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.copy_worker_contracts(root)
            pipeline = (
                root
                / "profiles"
                / "searcher"
                / "skills"
                / "searcher-pipeline"
                / "SKILL.md"
            )
            pipeline.write_text(
                pipeline.read_text(encoding="utf-8").replace(
                    "metadata.completion", "metadata.result"
                ),
                encoding="utf-8",
            )
            errors: list[str] = []

            VALIDATOR.validate_worker_pipeline_contract(errors, root)

        self.assertTrue(
            any("missing 'metadata.completion'" in error for error in errors), errors
        )

    def test_searcher_lifecycle_requires_input_attachments(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.copy_worker_contracts(root)
            pipeline = (
                root
                / "profiles"
                / "searcher"
                / "skills"
                / "searcher-pipeline"
                / "SKILL.md"
            )
            text = pipeline.read_text(encoding="utf-8")
            lifecycle_start = text.index("<LifecycleContract>")
            lifecycle_end = text.index("</LifecycleContract>", lifecycle_start)
            lifecycle = text[lifecycle_start:lifecycle_end]
            broken_lifecycle = lifecycle.replace("input_attachments", "", 1)
            pipeline.write_text(
                text[:lifecycle_start]
                + broken_lifecycle
                + text[lifecycle_end:],
                encoding="utf-8",
            )
            self.assertIn("FINAL_SUMMARY", pipeline.read_text(encoding="utf-8"))
            errors: list[str] = []

            VALIDATOR.validate_worker_pipeline_contract(errors, root)

        self.assertTrue(
            any("searcher worker pipeline lifecycle missing" in error for error in errors),
            errors,
        )

    def test_missing_final_summary_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.copy_worker_contracts(root)
            pipeline = (
                root
                / "profiles"
                / "searcher"
                / "skills"
                / "searcher-pipeline"
                / "SKILL.md"
            )
            pipeline.write_text(
                pipeline.read_text(encoding="utf-8").replace(
                    "FINAL_SUMMARY", "FINAL_RESULT"
                ),
                encoding="utf-8",
            )
            errors: list[str] = []

            VALIDATOR.validate_worker_pipeline_contract(errors, root)

        self.assertTrue(
            any("missing 'FINAL_SUMMARY'" in error for error in errors), errors
        )

    def test_searcher_completion_status_done_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.copy_worker_contracts(root)
            pipeline = (
                root
                / "profiles"
                / "searcher"
                / "skills"
                / "searcher-pipeline"
                / "SKILL.md"
            )
            pipeline.write_text(
                pipeline.read_text(encoding="utf-8").replace(
                    '"status":"completed"', '"status":"done"', 1
                ),
                encoding="utf-8",
            )
            errors: list[str] = []

            VALIDATOR.validate_worker_pipeline_contract(errors, root)

        self.assertTrue(
            any("missing '\"status\":\"completed\"'" in error for error in errors),
            errors,
        )


if __name__ == "__main__":
    unittest.main()
