#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6,<7"]
# ///
"""Validate Hermes skill topology, metadata, routing, and Git ownership."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import yaml


HERMES_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = HERMES_ROOT.parent
WORKFLOW_CONTRACT = (
    HERMES_ROOT
    / "skills"
    / "orchestration"
    / "references"
    / "workflow-contract.yaml"
)
WORKER_PROFILES = (
    "planner",
    "engineer",
    "researcher",
    "searcher",
    "creator",
    "writer",
    "qa",
    "marketer",
)
PLANNING_SPECIALIST_PROFILES = (
    "engineer",
    "creator",
    "writer",
    "marketer",
)
PLANNING_EVIDENCE_PROFILES = ("searcher", "researcher")
WORKER_MODE_SETS = {
    "planner": {"integrate"},
    "engineer": {"plan", "execute"},
    "creator": {"plan", "execute"},
    "writer": {"plan", "execute"},
    "marketer": {"plan", "execute"},
    "searcher": {"retrieve"},
    "researcher": {"analyze"},
    "qa": {"verify"},
}
REQUIRED_TASK_SPEC_FIELDS = {
    "goal",
    "inputs",
    "done_criteria",
    "output",
    "constraints",
    "input_attachments",
}
REQUIRED_CONTINUATION_FIELDS = {
    "title",
    "assignee",
    "skills",
    "parents",
    "params",
    "task_spec",
}
ALL_PROFILES = ("assistant", *WORKER_PROFILES)
COMPLETION_PATH_GUARD_PLUGIN = "kanban-completion-path-guard"
COMPLETION_PATH_GUARD_PROFILES = {"creator", "writer"}
WORKER_MUTATION_GUARD_PLUGIN = "kanban-worker-mutation-guard"
QA_REQUIRED_NON_CREATOR_ROUTES = {
    "core:tts",
    "writer:marketing-copy",
    "writer:technical-prose",
    "writer:documentation",
    "writer:script",
}
REQUIRED_WORKFLOW_SCHEMAS = {
    "requirement_spec",
    "task_spec",
    "planning_graph",
    "planning_branch",
    "specialist_plan",
    "execution_outline",
    "fan_out_manifest",
    "attachment_spec",
    "fan_out_policy",
    "child_spec",
    "continuation_spec",
    "completion_envelope",
    "artifact_handoff",
    "qa_handoff",
    "producer_qa_requirement",
    "execution_outline_handoff",
    "qa_verdict",
    "recovery_lineage",
    "pending_registration_manifest",
    "pending_registration_overlay",
}
REQUIRED_DIALOGUE_EVENTS = {
    "state",
    "question",
    "decision",
    "progress",
    "authority_expansion",
    "review",
    "approval",
    "scheduled",
}
REQUIRED_GRANTS = {"authority", "budget", "publish"}
PENDING_CONTRACT_ENFORCEMENT: set[str] = set()
WORKER_LIFECYCLE_PHASES = [
    "admit",
    "route",
    "act_or_plan",
    "verify",
    "handoff",
    "terminal",
]
WORKER_TERMINAL_ACTIONS = {"complete", "block"}
WORKER_FORBIDDEN_TEXT = {
    "kanban_create",
    "QA_DAG_CHANGE",
    "metadata.child_specs",
    "metadata.production_specs",
}
QA_ROUTE_CONDITIONS = {
    "always",
    "sourced_template",
    "exported_video",
    "exported_time_based_media",
}
PLANNING_FLOW = [
    "normalize_requirement",
    "approve_planning_graph",
    "collect_specialist_plans",
    "integrate_execution_outline",
    "approve_execution_outline",
    "register_execution_graph",
]
ASSISTANT_FORBIDDEN_TEXT = {
    "triage=true",
    "QA_DAG_CHANGE",
    "Approach=",
    "Plan Loop",
    "Planner tree",
    "metadata.child_specs",
    "metadata.production_specs",
    "metadata.fan_out",
    "Workers can fan out themselves",
}
QA_SUPPRESSION_FORBIDDEN_TEXT = {
    "create-" + "hidden",
    "QA_" + "SETUP",
    "kanban-" + "qa-gate.sh",
    "zero-" + "subscription",
}
REGISTRATION_KEY_TEMPLATES = {
    "planning_branch": (
        "<request-run-id>:planning:<planning-graph-digest>:branch:<branch-key>"
    ),
    "planner_integration": (
        "<request-run-id>:integration:<specialist-id-set-digest>:<revision-digest>"
    ),
    "execution_card": "<integration-task-id>:execution:<card-key>",
    "fan_out_child": (
        "<origin-task-id>:fanout:<checkpoint-key>:child:<child-key>"
    ),
    "fan_out_continuation": (
        "<origin-task-id>:fanout:<checkpoint-key>:continuation"
    ),
    "qa": "<target-task-id>:qa:<qa-contract-digest>",
    "revision": "<failed-qa-id>:revision:<spec-digest>",
    "recovery": "<source-task-id>:recovery:<kind>:<spec-digest>",
    "replacement_qa": "<recovery-task-id>:qa:<qa-contract-digest>",
}


class UniqueKeyLoader(yaml.SafeLoader):
    pass


def construct_unique_mapping(
    loader: UniqueKeyLoader, node: yaml.MappingNode, deep: bool = False
) -> dict[Any, Any]:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            hash(key)
        except TypeError as error:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "found an unhashable mapping key",
                key_node.start_mark,
            ) from error
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    construct_unique_mapping,
)


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def load_workflow_contract(path: Path, errors: list[str]) -> dict[str, Any] | None:
    try:
        data = yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueKeyLoader)
    except (OSError, yaml.YAMLError) as error:
        errors.append(f"invalid workflow contract YAML: {path}: {error}")
        return None
    if not isinstance(data, dict):
        errors.append(f"workflow contract must be a mapping: {path}")
        return None
    return data


def frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8").lstrip("\ufeff")
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}
    data = yaml.safe_load(text[4:end])
    return data if isinstance(data, dict) else {}


def hermes_category(data: dict[str, Any]) -> str | None:
    metadata = data.get("metadata")
    if not isinstance(metadata, dict):
        return None
    hermes = metadata.get("hermes")
    if not isinstance(hermes, dict):
        return None
    category = hermes.get("category")
    return str(category) if category is not None else None


def capability_names(path: Path) -> set[str]:
    names: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or line.startswith("| ---"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        cell = cells[1]
        if len(cell) > 2 and cell.startswith("`") and cell.endswith("`"):
            names.add(cell[1:-1])
    return names


def capability_routes(path: Path) -> list[tuple[str, str]]:
    routes: list[tuple[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or line.startswith("| ---"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        source, target = cells[:2]
        if all(
            len(cell) > 2 and cell.startswith("`") and cell.endswith("`")
            for cell in (source, target)
        ):
            routes.append((source[1:-1], target[1:-1]))
    return routes


def string_list(value: Any, location: str, errors: list[str]) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        errors.append(f"{location} must be a list of strings")
        return []
    if len(value) != len(set(value)):
        errors.append(f"{location} contains duplicate values")
    return value


def markdown_param_keys(text: str) -> set[str]:
    keys: set[str] = set()
    lines = text.splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("params: {") and stripped.endswith("}"):
            body = stripped[len("params: {") : -1]
            for item in body.split(","):
                key = item.strip().split(":", 1)[0].strip()
                if key:
                    keys.add(key)
            continue
        if stripped != "params:":
            continue
        base_indent = len(line) - len(line.lstrip())
        for child in lines[index + 1 :]:
            if not child.strip():
                continue
            indent = len(child) - len(child.lstrip())
            if indent <= base_indent:
                break
            if indent == base_indent + 2 and ":" in child:
                keys.add(child.strip().split(":", 1)[0])
    return keys


def markdown_task_specs(text: str) -> list[tuple[int, set[str]]]:
    specs: list[tuple[int, set[str]]] = []
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.strip() != "task_spec:":
            continue
        base_indent = len(line) - len(line.lstrip())
        fields: set[str] = set()
        for child in lines[index + 1 :]:
            if not child.strip():
                continue
            indent = len(child) - len(child.lstrip())
            if indent <= base_indent:
                break
            if indent == base_indent + 2 and ":" in child:
                fields.add(child.strip().split(":", 1)[0])
        specs.append((index + 1, fields))
    return specs


def section_body(
    text: str,
    opening: str,
    closing: str,
    location: str,
    errors: list[str],
) -> str | None:
    start = text.find(opening)
    if start == -1:
        errors.append(f"{location} missing section {opening!r}")
        return None
    body_start = start + len(opening)
    end = text.find(closing, body_start)
    if end == -1:
        errors.append(f"{location} missing section {closing!r}")
        return None
    return text[body_start:end]


def first_fenced_block(
    text: str, location: str, errors: list[str]
) -> str | None:
    start = text.find("```")
    if start == -1:
        errors.append(f"{location} missing fenced example")
        return None
    body_start = text.find("\n", start)
    if body_start == -1:
        errors.append(f"{location} missing fenced example body")
        return None
    end = text.find("```", body_start + 1)
    if end == -1:
        errors.append(f"{location} missing fenced example closing")
        return None
    return text[body_start + 1 : end]


def markdown_mapping_fields(
    text: str, mapping_name: str
) -> list[tuple[int, set[str]]]:
    mappings: list[tuple[int, set[str]]] = []
    lines = text.splitlines()
    marker = f"{mapping_name}:"
    for index, line in enumerate(lines):
        if line.strip() != marker:
            continue
        base_indent = len(line) - len(line.lstrip())
        fields: set[str] = set()
        for child in lines[index + 1 :]:
            if not child.strip():
                continue
            indent = len(child) - len(child.lstrip())
            if indent <= base_indent:
                break
            if indent == base_indent + 2 and ":" in child:
                fields.add(child.strip().split(":", 1)[0])
        mappings.append((index + 1, fields))
    return mappings


def markdown_assignee_modes(text: str) -> list[tuple[int, str, str | None]]:
    results: list[tuple[int, str, str | None]] = []
    lines = text.splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("assignee:"):
            continue
        assignee = stripped.split(":", 1)[1].strip()
        if assignee not in WORKER_MODE_SETS:
            continue
        mode: str | None = None
        for candidate in lines[index + 1 :]:
            candidate_stripped = candidate.strip()
            if candidate_stripped.startswith("assignee:"):
                break
            if candidate_stripped.startswith("mode:"):
                value = candidate_stripped.split(":", 1)[1].strip()
                if value and "<" not in value and "|" not in value:
                    mode = value
                break
            if candidate_stripped == "```":
                break
        results.append((index + 1, assignee, mode))
    return results


def validate_markdown_contract_examples(
    text: str, location: str, errors: list[str]
) -> None:
    forbidden_param_keys = {
        "mode",
        "planning_graph",
        "request_run",
        "planning_branch",
        "branch_key",
        "MarketingBrief",
        "publish_grant_proposal",
        "qa_dependencies",
        "release_dependencies",
        "fan_out_policy",
    }
    invalid_param_keys = markdown_param_keys(text) & forbidden_param_keys
    if invalid_param_keys:
        errors.append(
            f"{location} puts workflow/domain fields in Kanban params: "
            + ", ".join(sorted(invalid_param_keys))
        )

    for line, fields in markdown_task_specs(text):
        missing = REQUIRED_TASK_SPEC_FIELDS - fields
        if missing:
            errors.append(
                f"{location}:{line} TaskSpec example misses required fields: "
                + ", ".join(sorted(missing))
            )

    for line, fields in markdown_mapping_fields(text, "continuation"):
        missing = REQUIRED_CONTINUATION_FIELDS - fields
        if missing:
            errors.append(
                f"{location}:{line} continuation example misses required fields: "
                + ", ".join(sorted(missing))
            )

    for line, assignee, mode in markdown_assignee_modes(text):
        if mode is not None and mode not in WORKER_MODE_SETS[assignee]:
            errors.append(
                f"{location}:{line} assigns mode {mode} to {assignee}; allowed: "
                + ", ".join(sorted(WORKER_MODE_SETS[assignee]))
            )


def validate_workflow_contract_data(
    data: dict[str, Any], errors: list[str], hermes_root: Path = HERMES_ROOT
) -> None:
    version = data.get("version")
    if type(version) is not int or version != 1:
        errors.append("workflow contract version must be 1")

    migration = data.get("migration")
    if not isinstance(migration, dict):
        errors.append("workflow contract migration must be a mapping")
    else:
        if migration.get("state") != "worker_pipelines_enforced":
            errors.append(
                "workflow contract migration state must be worker_pipelines_enforced"
            )
        pending = set(
            string_list(
                migration.get("pending_enforcement"),
                "workflow contract migration.pending_enforcement",
                errors,
            )
        )
        if pending != PENDING_CONTRACT_ENFORCEMENT:
            errors.append("workflow contract pending enforcement must be empty")

    orchestration = data.get("orchestration")
    if not isinstance(orchestration, dict):
        errors.append("workflow contract orchestration must be a mapping")
    else:
        if orchestration.get("card_registration_owner") != "assistant":
            errors.append("workflow contract card registration owner must be assistant")
        if orchestration.get("worker_card_creation") != "forbidden":
            errors.append("workflow contract must forbid worker card creation")
        if orchestration.get("requirement_interview") != "risk_and_ambiguity_only":
            errors.append(
                "workflow contract requirement interview must be risk_and_ambiguity_only"
            )
        shapes = set(
            string_list(
                orchestration.get("execution_shapes"),
                "workflow contract orchestration.execution_shapes",
                errors,
            )
        )
        if shapes != {"inline", "single", "chain", "planned"}:
            errors.append(
                "workflow contract execution shapes must be inline, single, chain, and planned"
            )
        gates = set(
            string_list(
                orchestration.get("approval_gates"),
                "workflow contract orchestration.approval_gates",
                errors,
            )
        )
        if gates != {"planning_graph", "execution_outline"}:
            errors.append(
                "workflow contract approval gates must be planning_graph and execution_outline"
            )
        planning_flow = string_list(
            orchestration.get("planning_flow"),
            "workflow contract orchestration.planning_flow",
            errors,
        )
        if planning_flow != PLANNING_FLOW:
            errors.append("workflow contract planning flow has the wrong order")
        specialists = set(
            string_list(
                orchestration.get("specialist_planners"),
                "workflow contract orchestration.specialist_planners",
                errors,
            )
        )
        if specialists != set(PLANNING_SPECIALIST_PROFILES):
            errors.append(
                "workflow contract specialist planners must be engineer, creator, "
                "writer, and marketer"
            )
        evidence_workers = set(
            string_list(
                orchestration.get("evidence_workers"),
                "workflow contract orchestration.evidence_workers",
                errors,
            )
        )
        if evidence_workers != set(PLANNING_EVIDENCE_PROFILES):
            errors.append(
                "workflow contract planning evidence workers must be searcher and "
                "researcher"
            )

    lifecycle = data.get("worker_lifecycle")
    if not isinstance(lifecycle, dict):
        errors.append("workflow contract worker_lifecycle must be a mapping")
    else:
        phases = string_list(
            lifecycle.get("phases"),
            "workflow contract worker_lifecycle.phases",
            errors,
        )
        if phases != WORKER_LIFECYCLE_PHASES:
            errors.append("workflow contract worker lifecycle has the wrong phase order")
        terminal_actions = set(
            string_list(
                lifecycle.get("terminal_actions"),
                "workflow contract worker_lifecycle.terminal_actions",
                errors,
            )
        )
        if terminal_actions != WORKER_TERMINAL_ACTIONS:
            errors.append(
                "workflow contract worker terminal actions must be complete and block"
            )
        expected_lifecycle = {
            "completion_binding": "metadata.completion",
            "artifact_binding": "metadata.artifact_handoff",
            "completion_probe": "assistant/scripts/kanban-completion-probe.sh",
            "fan_out_terminal": "block",
            "registration_owner": "assistant",
        }
        for field, expected in expected_lifecycle.items():
            if lifecycle.get(field) != expected:
                errors.append(
                    f"workflow contract worker_lifecycle.{field} must be {expected}"
                )
        if lifecycle.get("digest_resolution") != {
            "sentinel": "pending-assistant-probe",
            "profiles": ["planner", "writer", "researcher"],
        }:
            errors.append(
                "workflow contract digest resolution must be limited to planner, writer, and researcher"
            )

    schemas = data.get("schemas")
    if not isinstance(schemas, dict):
        errors.append("workflow contract schemas must be a mapping")
    else:
        schema_names = set(schemas)
        if schema_names != REQUIRED_WORKFLOW_SCHEMAS:
            errors.append(
                "workflow contract schemas must be exactly: "
                + ", ".join(sorted(REQUIRED_WORKFLOW_SCHEMAS))
            )
        for name, schema in schemas.items():
            if not isinstance(schema, dict):
                errors.append(f"workflow contract schema {name} must be a mapping")
                continue
            required = string_list(
                schema.get("required"),
                f"workflow contract schemas.{name}.required",
                errors,
            )
            optional = string_list(
                schema.get("optional"),
                f"workflow contract schemas.{name}.optional",
                errors,
            )
            overlap = set(required) & set(optional)
            if overlap:
                errors.append(
                    f"workflow contract schema {name} repeats fields as required and optional: "
                    + ", ".join(sorted(overlap))
                )
        for name in ("requirement_spec", "planning_graph", "execution_outline"):
            schema = schemas.get(name)
            if isinstance(schema, dict) and "request_id" not in schema.get("required", []):
                errors.append(f"workflow contract schema {name} must require request_id")
        task_spec = schemas.get("task_spec")
        if isinstance(task_spec, dict) and "input_attachments" not in task_spec.get(
            "required", []
        ):
            errors.append(
                "workflow contract task_spec must require input_attachments"
            )
        completion = schemas.get("completion_envelope")
        if isinstance(completion, dict):
            completion_fields = set(completion.get("required", [])) | set(
                completion.get("optional", [])
            )
            if "fan_out" in completion_fields:
                errors.append(
                    "workflow contract completion_envelope must not carry fan-out"
                )
        fan_out_policy = schemas.get("fan_out_policy")
        if isinstance(fan_out_policy, dict):
            if set(fan_out_policy.get("required", [])) != {
                "allowed_assignees",
                "max_children",
                "purpose",
            }:
                errors.append(
                    "workflow contract fan_out_policy has the wrong required fields"
                )
        fan_out_manifest = schemas.get("fan_out_manifest")
        if isinstance(fan_out_manifest, dict):
            if set(fan_out_manifest.get("required", [])) != {
                "origin_task_id",
                "checkpoint_key",
                "children",
                "continuation",
                "attachments",
            }:
                errors.append(
                    "workflow contract fan_out_manifest has the wrong required fields"
                )
        exact_schema_fields = {
            "execution_outline_handoff": {
                "request_id",
                "attachment",
                "sha256",
                "specialist_task_ids",
                "card_count",
            },
            "qa_verdict": {
                "target_task",
                "producer_capability",
                "target_artifacts",
                "research_parents",
                "technics",
                "verdict",
                "criteria",
                "findings",
                "residual_risk",
                "reviewer_scope",
            },
            "qa_handoff": {"status"},
            "recovery_lineage": {
                "kind",
                "source_task_id",
                "reason",
                "spec_digest",
            },
            "pending_registration_manifest": {"anchor", "digest", "cards"},
            "pending_registration_overlay": {
                "overlay_task_id",
                "overlay_key",
                "digest",
                "cards",
                "lineage",
            },
            "producer_qa_requirement": {
                "candidate_key",
                "evidence_keys",
                "capability",
                "routes",
                "criteria",
                "done_criteria",
                "output_inventory",
            },
        }
        for name, expected in exact_schema_fields.items():
            schema = schemas.get(name)
            if isinstance(schema, dict) and set(schema.get("required", [])) != expected:
                errors.append(
                    f"workflow contract {name} has the wrong required fields"
                )

    bindings = data.get("bindings")
    if not isinstance(bindings, dict):
        errors.append("workflow contract bindings must be a mapping")
    else:
        expected_bindings = {
            "specialist_plan": {
                "envelope_path": "metadata.specialist_plan",
                "cardinality": "exactly_one_on_final_plan_completion",
                "exclusive_with": "FAN_OUT_READY",
            },
            "fan_out_manifest": {
                "marker": "FAN_OUT_READY:",
                "attachment": "fan-out.yaml",
                "probe": "kanban-fanout-manifest-probe.sh",
                "scope": "all_origins_before_completion",
                "cardinality": "zero_or_one",
            },
            "completion_envelope": {
                "envelope_path": "metadata.completion",
                "cardinality": "exactly_one_on_every_completion",
                "absent_during": "FAN_OUT_READY",
                "summary_match": "kanban_complete.summary",
                "statuses": {
                    "workers": ["completed", "superseded"],
                    "qa": ["pass", "fail", "can't_verify"],
                },
            },
            "artifact_handoff": {
                "envelope_path": "metadata.artifact_handoff",
                "cardinality": "exactly_one_when_current_outputs_declared",
                "absent_when": "no_current_output_inventory",
            },
            "pending_registration_manifest": {
                "marker": "ORCHESTRATION_PENDING:",
                "storage": "root_body_or_integration_comment",
                "cardinality": "exactly_one_per_multistage_graph",
            },
            "pending_registration_overlay": {
                "marker": "ORCHESTRATION_PENDING_OVERLAY:",
                "storage": "fan_out_origin_comment",
                "cardinality": "one_per_fan_out_checkpoint",
            },
            "qa_pending_materialization": {
                "marker": "QA_PENDING_MATERIALIZATION:",
                "storage": "origin_or_integration_comment",
                "cardinality": "exactly_one_per_qa_contract_before_create",
            },
            "completion_handled": {
                "marker": "COMPLETION_HANDLED:",
                "storage": "completed_task_comment",
                "event_binding": "task_and_completion_event",
                "scope": "non_qa_success_or_invalid_recovery",
            },
        }
        if set(bindings) != set(expected_bindings):
            errors.append(
                "workflow contract bindings must define fan-out, specialist, completion, artifact, handling, and pending-registration handoffs"
            )
        for name, expected in expected_bindings.items():
            binding = bindings.get(name)
            if not isinstance(binding, dict):
                errors.append(f"workflow contract binding {name} must be a mapping")
                continue
            if set(binding) != set(expected):
                errors.append(
                    f"workflow contract binding {name} has the wrong fields"
                )
            for field, value in expected.items():
                if binding.get(field) != value:
                    errors.append(
                        f"workflow contract binding {name} {field} must be {value}"
                    )

    registration = data.get("registration")
    if not isinstance(registration, dict):
        errors.append("workflow contract registration must be a mapping")
    else:
        if registration.get("subscription") != "required":
            errors.append("workflow contract registration subscription must be required")
        if registration.get("classic_cli_dispatch") != "forbidden":
            errors.append(
                "workflow contract classic CLI dispatch must be forbidden"
            )
        if registration.get("completion_watchdog_cutoff") != 1785801600:
            errors.append(
                "workflow contract completion watchdog cutoff is invalid"
            )
        if registration.get("qa_policy") != {
            "all_cards_subscription_required": True,
            "qa_registration": (
                "late_bound_after_candidate_and_evidence_completion_admission"
            ),
            "qa_task_input_digests": "resolved",
            "pending_form": "producer_qa_requirement",
            "pending_schema": "producer_qa_requirement",
            "pending_materialization_marker": "QA_PENDING_MATERIALIZATION:",
            "materialization_marker": "QA_MATERIALIZED:",
            "materialization_event_binding": "producer_and_completion_event",
            "candidate_completion": "progress",
            "formal_delivery": "digest_checked_pass",
        }:
            errors.append(
                "workflow contract registration QA policy must require subscriptions,"
                " late-bind QA after candidate/evidence CompletionAdmission, require"
                " resolved QA input digests, materialize from producer QA requirements, treat"
                " candidate completion as progress, and require a digest-checked pass"
            )
        if registration.get("retry_semantics") != {
            "transport_replay": "same_key_same_immutable_spec",
            "replacement": "fresh_key_changed_spec",
        }:
            errors.append(
                "workflow contract registration retry semantics must separate replay and replacement"
            )
        keys = registration.get("idempotency_keys")
        if not isinstance(keys, dict) or set(keys) != set(REGISTRATION_KEY_TEMPLATES):
            errors.append(
                "workflow contract registration must define all idempotency key templates"
            )
        else:
            for name, template in REGISTRATION_KEY_TEMPLATES.items():
                if keys.get(name) != template:
                    errors.append(
                        f"workflow contract registration key {name} must be {template}"
                    )

    dialogue_events = data.get("dialogue_events")
    if not isinstance(dialogue_events, dict):
        errors.append("workflow contract dialogue_events must be a mapping")
    else:
        if set(dialogue_events) != REQUIRED_DIALOGUE_EVENTS:
            errors.append(
                "workflow contract dialogue events must be exactly: "
                + ", ".join(sorted(REQUIRED_DIALOGUE_EVENTS))
            )
        markers: list[str] = []
        for name, event in dialogue_events.items():
            if not isinstance(event, dict):
                errors.append(f"workflow contract dialogue event {name} must be a mapping")
                continue
            marker = event.get("marker")
            if not isinstance(marker, str) or not marker:
                errors.append(f"workflow contract dialogue event {name} needs a marker")
            else:
                markers.append(marker)
            required = string_list(
                event.get("required"),
                f"workflow contract dialogue_events.{name}.required",
                errors,
            )
            if not required:
                errors.append(
                    f"workflow contract dialogue event {name} needs required fields"
                )
            optional = string_list(
                event.get("optional", []),
                f"workflow contract dialogue_events.{name}.optional",
                errors,
            )
            overlap = set(required) & set(optional)
            if overlap:
                errors.append(
                    f"workflow contract dialogue event {name} repeats fields as "
                    "required and optional: " + ", ".join(sorted(overlap))
                )
        if len(markers) != len(set(markers)):
            errors.append("workflow contract dialogue event markers must be unique")
        scheduled = dialogue_events.get("scheduled")
        if isinstance(scheduled, dict):
            if set(scheduled.get("required", [])) != {"reason"} or set(
                scheduled.get("optional", [])
            ) != {"until"}:
                errors.append(
                    "workflow contract scheduled event must require reason and make until optional"
                )
        decision = dialogue_events.get("decision")
        if isinstance(decision, dict) and set(decision.get("required", [])) != {
            "question_id",
            "choice",
            "block_event",
            "block_digest",
        }:
            errors.append(
                "workflow contract decision event must bind question, choice, block event, and digest"
            )

    grants = data.get("grants")
    grant_owners: dict[str, str] = {}
    if not isinstance(grants, dict):
        errors.append("workflow contract grants must be a mapping")
    else:
        if set(grants) != REQUIRED_GRANTS:
            errors.append(
                "workflow contract grants must be exactly: "
                + ", ".join(sorted(REQUIRED_GRANTS))
            )
        for name, grant in grants.items():
            if not isinstance(grant, dict):
                errors.append(f"workflow contract grant {name} must be a mapping")
                continue
            owner = grant.get("owner")
            if not isinstance(owner, str):
                errors.append(f"workflow contract grant {name} needs an owner")
            else:
                grant_owners[name] = owner
            if not isinstance(grant.get("task_field"), str):
                errors.append(f"workflow contract grant {name} needs a task_field")
            string_list(
                grant.get("presets"),
                f"workflow contract grants.{name}.presets",
                errors,
            )

    workers = data.get("workers")
    worker_technics: dict[str, set[str]] = {}
    if not isinstance(workers, dict):
        errors.append("workflow contract workers must be a mapping")
        workers = {}
    if set(workers) != set(WORKER_PROFILES):
        errors.append(
            "workflow contract workers must be exactly: "
            + ", ".join(WORKER_PROFILES)
        )

    for profile, worker in workers.items():
        if not isinstance(worker, dict):
            errors.append(f"workflow contract worker {profile} must be a mapping")
            continue
        expected_pipeline = f"{profile}-pipeline"
        if worker.get("pipeline") != expected_pipeline:
            errors.append(
                f"workflow contract worker {profile} pipeline must be {expected_pipeline}"
            )
        pipeline = (
            hermes_root
            / "profiles"
            / profile
            / "skills"
            / expected_pipeline
            / "SKILL.md"
        )
        if not pipeline.is_file():
            errors.append(f"workflow contract pipeline not found: {pipeline}")
        modes = string_list(
            worker.get("modes"),
            f"workflow contract workers.{profile}.modes",
            errors,
        )
        if not modes:
            errors.append(f"workflow contract worker {profile} needs at least one mode")
        expected_modes = WORKER_MODE_SETS.get(profile)
        if expected_modes is not None and set(modes) != expected_modes:
            errors.append(
                f"workflow contract worker {profile} modes must be exactly: "
                + ", ".join(sorted(expected_modes))
            )

        grant = worker.get("grant")
        if grant is not None and grant not in REQUIRED_GRANTS:
            errors.append(f"workflow contract worker {profile} names unknown grant {grant}")

        technics = worker.get("technics")
        if not isinstance(technics, dict):
            errors.append(f"workflow contract worker {profile} technics must be a mapping")
            continue
        active = string_list(
            technics.get("active"),
            f"workflow contract workers.{profile}.technics.active",
            errors,
        )
        deprecated = string_list(
            technics.get("deprecated"),
            f"workflow contract workers.{profile}.technics.deprecated",
            errors,
        )
        overlap = set(active) & set(deprecated)
        if overlap:
            errors.append(
                f"workflow contract worker {profile} marks technics active and deprecated: "
                + ", ".join(sorted(overlap))
            )
        declared = set(active) | set(deprecated)
        worker_technics[profile] = declared
        technic_dir = hermes_root / "profiles" / profile / "skills" / "technic"
        actual = {
            path.parent.name for path in technic_dir.glob("*/SKILL.md")
        } if technic_dir.is_dir() else set()
        for name in sorted(declared - actual):
            errors.append(f"workflow contract names missing {profile} technic: {name}")
        for name in sorted(actual - declared):
            errors.append(f"{profile} technic missing from workflow contract: {name}")

    for grant, owner in grant_owners.items():
        worker = workers.get(owner)
        if not isinstance(worker, dict) or worker.get("grant") != grant:
            errors.append(
                f"workflow contract grant {grant} owner {owner} must select that grant"
            )
    for profile, worker in workers.items():
        if not isinstance(worker, dict) or worker.get("grant") is None:
            continue
        grant = worker["grant"]
        if grant_owners.get(grant) != profile:
            errors.append(
                f"workflow contract worker {profile} grant {grant} has a different owner"
            )

    creator_capabilities_path = (
        hermes_root
        / "profiles"
        / "creator"
        / "skills"
        / "creator-pipeline"
        / "references"
        / "capabilities.md"
    )
    qa_capabilities_path = (
        hermes_root
        / "profiles"
        / "qa"
        / "skills"
        / "qa-pipeline"
        / "references"
        / "capabilities.md"
    )
    creator_capabilities: set[str] = set()
    if creator_capabilities_path.is_file():
        creator_capabilities = capability_names(creator_capabilities_path)
    else:
        errors.append(
            f"Creator capability table not found: {creator_capabilities_path}"
        )
    if creator_capabilities != worker_technics.get("creator", set()):
        errors.append("Creator capability table must match workflow contract technics")
    qa_technics: set[str] = set()
    if qa_capabilities_path.is_file():
        qa_technics = capability_names(qa_capabilities_path)
    else:
        errors.append(f"QA capability table not found: {qa_capabilities_path}")
    if qa_technics != worker_technics.get("qa", set()):
        errors.append("QA capability table must match workflow contract technics")

    qa_routes = data.get("qa_routes")
    contract_routes: set[tuple[str, str]] = set()
    if not isinstance(qa_routes, dict):
        errors.append("workflow contract qa_routes must be a mapping")
        qa_routes = {}
    for source, routes in qa_routes.items():
        if not isinstance(source, str) or not isinstance(routes, list) or not routes:
            errors.append(f"workflow contract QA route {source} must be a non-empty list")
            continue
        for index, route in enumerate(routes):
            if not isinstance(route, dict):
                errors.append(
                    f"workflow contract QA route {source}[{index}] must be a mapping"
                )
                continue
            target = route.get("technic")
            condition = route.get("condition")
            if not isinstance(target, str):
                errors.append(
                    f"workflow contract QA route {source}[{index}] needs a technic"
                )
                continue
            if target not in worker_technics.get("qa", set()):
                errors.append(
                    f"workflow contract QA route {source} names unknown technic {target}"
                )
            if not isinstance(condition, str) or not condition:
                errors.append(
                    f"workflow contract QA route {source}[{index}] needs a condition"
                )
            elif condition not in QA_ROUTE_CONDITIONS:
                errors.append(
                    f"workflow contract QA route {source}[{index}] names unknown "
                    f"condition {condition}"
                )
            pair = (source, target)
            if pair in contract_routes:
                errors.append(
                    f"workflow contract repeats QA route {source} -> {target}"
                )
            contract_routes.add(pair)

    expected_sources = worker_technics.get("creator", set()) | QA_REQUIRED_NON_CREATOR_ROUTES
    if set(qa_routes) != expected_sources:
        errors.append(
            "workflow contract QA route sources must match Creator and non-Creator capabilities"
        )
    if qa_capabilities_path.is_file():
        markdown_routes = set(capability_routes(qa_capabilities_path))
        if contract_routes != markdown_routes:
            errors.append("QA capability table routes must match workflow contract qa_routes")


def validate_workflow_contract(errors: list[str]) -> int | None:
    if not WORKFLOW_CONTRACT.is_file():
        errors.append(f"workflow contract not found: {WORKFLOW_CONTRACT}")
        return None
    data = load_workflow_contract(WORKFLOW_CONTRACT, errors)
    if data is None:
        return None
    validate_workflow_contract_data(data, errors)
    version = data.get("version")
    return version if type(version) is int else None


def validate_managed_qa_suppression_text(
    errors: list[str], hermes_root: Path = HERMES_ROOT
) -> None:
    managed_text_extensions = {".json", ".md", ".yaml", ".yml", ".sh", ".txt"}
    runtime_parts = {
        ".archive",
        ".hub",
        ".restore-backups",
        "__pycache__",
        "hermes-achievements",
        "index-cache",
        "learned",
        "output",
    }

    paths = set(
        path
        for path in hermes_root.iterdir()
        if path.is_file()
        and path.suffix in managed_text_extensions
        and path.name != "SOUL.md"
    )
    for relative_root in (
        "skills/orchestration",
        "skills/workspaces",
        "plugins",
        "scripts",
        "launchd",
    ):
        root = hermes_root / relative_root
        if root.is_dir():
            paths.update(root.rglob("*"))
    for relative_file in ("cron/jobs.json",):
        path = hermes_root / relative_file
        if path.is_file():
            paths.add(path)
    profiles = hermes_root / "profiles"
    if profiles.is_dir():
        for profile in profiles.iterdir():
            if not profile.is_dir():
                continue
            for name in ("profile.yaml", "config.example.yaml"):
                path = profile / name
                if path.is_file():
                    paths.add(path)
            if profile.name != "assistant" and (profile / "config.yaml").is_file():
                paths.add(profile / "config.yaml")
            for relative_root in ("skills", "scripts"):
                root = profile / relative_root
                if root.is_dir():
                    paths.update(root.rglob("*"))
            jobs = profile / "cron" / "jobs.json"
            if jobs.is_file():
                paths.add(jobs)

    for path in sorted(paths):
        if not path.is_file() or path.suffix not in managed_text_extensions:
            continue
        if runtime_parts.intersection(path.parts):
            continue
        text = path.read_text(encoding="utf-8")
        for token in sorted(QA_SUPPRESSION_FORBIDDEN_TEXT):
            if token in text:
                errors.append(
                    f"Managed Hermes text retains forbidden QA suppression {token!r}: {path}"
                )


def validate_fanout_write_ahead(text: str, errors: list[str]) -> None:
    match = re.search(
        r"(?ms)^<FanOutManifest>\s*$\n(.*?)^</FanOutManifest>\s*$",
        text,
    )
    if match is None:
        errors.append("Assistant FanOutManifest section is missing")
        return
    fanout = match.group(1)
    overlay = fanout.find("ORCHESTRATION_PENDING_OVERLAY:")
    create = fanout.find("Create only child roots")
    if overlay == -1 or create == -1 or overlay > create:
        errors.append(
            "Assistant FanOutManifest must persist ORCHESTRATION_PENDING_OVERLAY before creating child roots"
        )


def validate_qa_write_ahead(text: str, errors: list[str]) -> None:
    match = re.search(
        r"(?ms)^<QualityGate>\s*$\n(.*?)^</QualityGate>\s*$",
        text,
    )
    if match is None:
        errors.append("Assistant QualityGate section is missing")
        return
    quality_gate = match.group(1)
    pending = quality_gate.find("QA_PENDING_MATERIALIZATION:")
    create = quality_gate.find("Create\nQA exactly from it")
    if pending == -1 or create == -1 or pending > create:
        errors.append(
            "Assistant QualityGate must persist QA_PENDING_MATERIALIZATION before creating QA"
        )


def validate_assistant_orchestration_contract(errors: list[str]) -> None:
    orchestration_skill = HERMES_ROOT / "skills" / "orchestration" / "SKILL.md"
    plan_reference = (
        HERMES_ROOT / "skills" / "orchestration" / "references" / "plan.md"
    )
    default_config = HERMES_ROOT / "config.yaml"
    assistant_example = HERMES_ROOT / "profiles" / "assistant" / "config.example.yaml"
    assistant_scripts = HERMES_ROOT / "profiles" / "assistant" / "scripts"
    task_probe = assistant_scripts / "kanban-task-spec-probe.sh"
    completion_probe = assistant_scripts / "kanban-completion-probe.sh"
    fanout_probe = assistant_scripts / "kanban-fanout-manifest-probe.sh"
    watchdog = assistant_scripts / "kanban-orphan-watchdog.sh"
    sweeper = assistant_scripts / "kanban-scheduled-sweeper.sh"
    block_resolver = assistant_scripts / "kanban-resolve-block.sh"
    assistant_jobs = HERMES_ROOT / "profiles" / "assistant" / "cron" / "jobs.json"
    profiles_doc = HERMES_ROOT / "PROFILES.md"
    agents_doc = HERMES_ROOT / "AGENTS.md"
    reference_dir = HERMES_ROOT / "skills" / "orchestration" / "references"

    required_by_file = {
        orchestration_skill: {
            "RequirementSpec",
            "FanOutManifest",
            "PlanningGraph",
            "ExecutionOutline",
            "Only the Assistant registers cards",
            "`inline`",
            "`single`",
            "`chain`",
            "`planned`",
            "FAN_OUT_READY:",
            "CompletionAdmission",
            "ORCHESTRATION_PENDING:",
            "ORCHESTRATION_PENDING_OVERLAY:",
            "Input attachments:",
            "Before QA registration",
            "must replace that sentinel with the measured digest",
            "completion_event=<producer-completed-event-id>",
            "QA_PENDING_MATERIALIZATION:",
            "hermes kanban link",
            "hermes kanban unlink",
        },
        plan_reference: {
            "Approval gate 1: PlanningGraph",
            "Approval gate 2: ExecutionOutline",
            "SpecialistPlan",
            "metadata.specialist_plan",
            "FAN_OUT_READY:",
            "fan-out.yaml",
            "planning-graph.yaml",
            "fan_out_policy",
            "register only branches with no local parents",
            "ORCHESTRATION_PENDING:",
            "Input attachments:",
        },
        default_config: {
            "RequirementSpec",
            "PlanningGraph",
            "ExecutionOutline",
            "FanOutManifest",
        },
        assistant_example: {
            "RequirementSpec",
            "PlanningGraph",
            "ExecutionOutline",
            "FanOutManifest",
            "Never create child or",
        },
        task_probe: {
            "PRAGMA query_only = ON",
            "kanban_db_path",
            "max_runtime_seconds",
            "goal_max_turns",
            "task_links",
            '"skills": skills',
            "Producer QA requirement",
        },
        completion_probe: {
            "PRAGMA query_only = ON",
            "kanban_db_path",
            "metadata.completion",
            "metadata.artifact_handoff",
            "metadata.specialist_plan",
            "metadata.execution_outline",
            "metadata.qa",
            "producer_qa_requirement",
        },
        fanout_probe: {
            "PRAGMA query_only = ON",
            "kanban_db_path",
            "fan-out.yaml",
            "cannot assign qa",
            "manifest_digest",
            "producer_qa_requirement",
        },
        profiles_doc: {"FAN_OUT_READY:", "Workers never register cards"},
        agents_doc: {"FAN_OUT_READY:", "Assistant alone registers"},
        watchdog: {
            "kanban_db_path",
            "fanout_pending",
            "repeat_until_handled",
            "DECISION(FAN_OUT_READY):",
            "qa_candidates_unmaterialized",
            "completion_event=",
        },
        sweeper: {"ORDER BY id DESC LIMIT 1", "kanban_db_path"},
        block_resolver: {
            "DECISION",
            "block_digest",
            "block_recurrences = 0",
            "block_loop_detected",
        },
    }

    texts: dict[Path, str] = {}
    for path, required in required_by_file.items():
        if not path.is_file():
            errors.append(f"Assistant orchestration contract file not found: {path}")
            continue
        text = path.read_text(encoding="utf-8")
        texts[path] = text
        for token in sorted(required):
            if token not in text:
                errors.append(
                    f"Assistant orchestration contract missing {token!r}: {path}"
                )

    for path, location in (
        (orchestration_skill, "orchestration"),
        (plan_reference, "planned workflow"),
    ):
        text = texts.get(path)
        if text is not None:
            validate_markdown_contract_examples(text, location, errors)
    orchestration_text = texts.get(orchestration_skill)
    if orchestration_text is not None:
        validate_fanout_write_ahead(orchestration_text, errors)
        validate_qa_write_ahead(orchestration_text, errors)

    all_orchestration_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [orchestration_skill, *sorted(reference_dir.glob("*.md"))]
        if path.is_file()
    )
    for token in sorted(ASSISTANT_FORBIDDEN_TEXT):
        if token in all_orchestration_text:
            errors.append(f"Assistant orchestration retains forbidden text {token!r}")
    validate_managed_qa_suppression_text(errors)
    for path in (profiles_doc, agents_doc):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for token in ("QA_DAG_CHANGE", "workers fan out sub-tasks via kanban_create"):
            if token in text:
                errors.append(f"Hermes design doc retains forbidden text {token!r}: {path}")

    for path in (default_config, assistant_example):
        if not path.is_file():
            continue
        data = load_yaml(path)
        auto_decompose = data.get("kanban", {}).get("auto_decompose")
        if auto_decompose is not False:
            errors.append(f"auto_decompose must stay false: {path}")

    if assistant_jobs.is_file():
        jobs = load_yaml(assistant_jobs).get("jobs", [])
        watchdog_jobs = [
            job
            for job in jobs if isinstance(job, dict)
            and job.get("name") == "kanban-orphan-watchdog"
        ]
        if len(watchdog_jobs) != 1:
            errors.append("Assistant cron must define one kanban-orphan-watchdog job")
        else:
            schedule = watchdog_jobs[0].get("schedule", {})
            if not isinstance(schedule, dict) or schedule.get("expr") != "*/5 * * * *":
                errors.append("kanban-orphan-watchdog must run every 5 minutes")
        sweeper_jobs = [
            job
            for job in jobs if isinstance(job, dict)
            and job.get("name") == "kanban-scheduled-sweeper"
        ]
        if len(sweeper_jobs) != 1:
            errors.append("Assistant cron must define one kanban-scheduled-sweeper job")
        else:
            schedule = sweeper_jobs[0].get("schedule", {})
            if not isinstance(schedule, dict) or schedule.get("expr") != "*/15 * * * *":
                errors.append("kanban-scheduled-sweeper must run every 15 minutes")
    else:
        errors.append(f"Assistant cron jobs not found: {assistant_jobs}")

    if task_probe.is_file() and not os.access(task_probe, os.X_OK):
        errors.append(f"Kanban task probe must be executable: {task_probe}")
    if completion_probe.is_file() and not os.access(completion_probe, os.X_OK):
        errors.append(f"Kanban completion probe must be executable: {completion_probe}")
    for script in (watchdog, sweeper, block_resolver):
        if script.is_file() and not os.access(script, os.X_OK):
            errors.append(f"Assistant Kanban script must be executable: {script}")

    contract = load_workflow_contract(WORKFLOW_CONTRACT, errors)
    if contract is None:
        return
    keys = contract.get("registration", {}).get("idempotency_keys", {})
    if isinstance(keys, dict):
        registration_text = texts.get(orchestration_skill, "") + texts.get(
            plan_reference, ""
        )
        for name, template in keys.items():
            if isinstance(template, str) and template not in registration_text:
                errors.append(
                    f"Assistant orchestration does not document {name} key {template}"
                )


def validate_specialist_planning_contract(
    errors: list[str], hermes_root: Path = HERMES_ROOT
) -> None:
    common_pipeline_tokens = {
        "Mode: plan",
        "Mode: execute",
        "metadata.specialist_plan",
        "fan-out.yaml",
        "FAN_OUT_READY:",
        "Fan-out policy",
        "Assistant",
        "obsolete origin",
    }
    common_reference_tokens = {
        "Planning graph:",
        "Request run:",
        "Planning branch:",
        "Mode: plan",
        "Fan-out policy:",
        "origin_task_id",
        "branch_key",
        "summary",
        "proposed_cards",
        "FAN_OUT_READY:",
        "fan-out.yaml",
        "retrieve|analyze",
        "kanban_complete(",
        "FINAL_SUMMARY",
        '"specialist_plan": SPECIALIST_PLAN',
        "Do not pass an outer `metadata:` wrapper.",
    }
    forbidden_tokens = {
        "kanban_create",
        "QA_DAG_CHANGE",
        "metadata.child_specs",
        "metadata.production_specs",
    }

    for profile in PLANNING_SPECIALIST_PROFILES:
        profile_root = hermes_root / "profiles" / profile
        pipeline_dir = profile_root / "skills" / f"{profile}-pipeline"
        pipeline = pipeline_dir / "SKILL.md"
        specialist_reference = pipeline_dir / "references" / "specialist-plan.md"
        config = profile_root / "config.yaml"
        description = profile_root / "profile.yaml"

        required_by_file = {
            pipeline: common_pipeline_tokens,
            specialist_reference: common_reference_tokens,
            config: {
                "Mode",
                "plan",
                "execute",
                "SpecialistPlan",
                "fan-out.yaml",
                "FAN_OUT_READY",
            },
            description: {"plan", "execute", "SpecialistPlan"},
        }
        if profile in {"creator", "writer", "marketer"}:
            required_by_file[specialist_reference] = (
                required_by_file[specialist_reference]
                | {"producer_qa_requirement"}
            )
        texts: dict[Path, str] = {}
        for path, required in required_by_file.items():
            if not path.is_file():
                errors.append(f"specialist planning contract file not found: {path}")
                continue
            text = path.read_text(encoding="utf-8")
            texts[path] = text
            for token in sorted(required):
                if token not in text:
                    errors.append(
                        f"{profile} specialist planning contract missing "
                        f"{token!r}: {path}"
                    )

        pipeline_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted(pipeline_dir.rglob("*.md"))
            if path.is_file()
        )
        specialist_text = texts.get(specialist_reference, "")
        if re.search(r"(?m)^\s*assignee:\s*[^\n]*\bqa\b", specialist_text):
            errors.append(
                f"{profile} SpecialistPlan must not propose a QA card before digest resolution"
            )
        for token in sorted(forbidden_tokens):
            if token in pipeline_text:
                errors.append(
                    f"{profile} specialist planning retains forbidden text {token!r}"
                )

        validate_markdown_contract_examples(pipeline_text, profile, errors)

    planner_root = hermes_root / "profiles" / "planner"
    planner_pipeline = planner_root / "skills" / "planner-pipeline" / "SKILL.md"
    planner_config = planner_root / "config.yaml"
    planner_description = planner_root / "profile.yaml"
    planner_required = {
        planner_pipeline: {
            "Mode: integrate",
            "RequirementSpec",
            "PlanningGraph",
            "SpecialistPlan",
            "ExecutionOutline",
            "execution-outline.yaml",
            "workflow-contract.yaml",
            "metadata.specialist_plan",
            "never creates",
            "Request run:",
            "producer_qa_requirement",
            "local-to-outline key map",
        },
        planner_config: {
            "Mode: integrate",
            "SpecialistPlan",
            "ExecutionOutline",
            "Never create any card",
        },
        planner_description: {
            "Mode: integrate",
            "SpecialistPlan",
            "ExecutionOutline",
        },
    }
    for path, required in planner_required.items():
        if not path.is_file():
            errors.append(f"Planner integration contract file not found: {path}")
            continue
        text = path.read_text(encoding="utf-8")
        for token in sorted(required):
            if token not in text:
                errors.append(
                    f"Planner integration contract missing {token!r}: {path}"
                )
        if path == planner_pipeline and "Request ID:" in text:
            errors.append(
                f"Planner integration contract must not use 'Request ID:': {path}"
            )
        if path == planner_pipeline:
            input_contract = section_body(
                text,
                "<InputContract>",
                "</InputContract>",
                "Planner pipeline",
                errors,
            )
            if input_contract is not None:
                input_example = first_fenced_block(
                    input_contract, "Planner InputContract", errors
                )
                if input_example is not None and "Request run:" not in input_example:
                    errors.append(
                        f"Planner InputContract missing 'Request run:': {path}"
                    )

    planner_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (planner_pipeline, planner_config, planner_description)
        if path.is_file()
    )
    for token in (
        "kanban_create",
        "QA_DAG_CHANGE",
        "InvestigationTiers",
        "advisory fan-out",
    ):
        if token in planner_text:
            errors.append(f"Planner integration retains forbidden text {token!r}")
    validate_markdown_contract_examples(planner_text, "planner", errors)

    plan_reference = hermes_root / "skills" / "orchestration" / "references" / "plan.md"
    if not plan_reference.is_file():
        errors.append(f"planned workflow reference not found: {plan_reference}")
    else:
        plan_text = plan_reference.read_text(encoding="utf-8")
        for token in (
            "assignee: engineer|creator|writer|marketer",
            "not direct PlanningGraph branches",
        ):
            if token not in plan_text:
                errors.append(
                    f"planned workflow does not separate specialists/evidence: "
                    f"missing {token!r}"
                )
        integration_start = plan_text.find("## Planner integration")
        if integration_start == -1:
            errors.append("planned workflow missing section '## Planner integration'")
        else:
            integration_end = plan_text.find("\n## ", integration_start + 3)
            integration_text = plan_text[
                integration_start:
                integration_end if integration_end != -1 else len(plan_text)
            ]
            for token in ("Request run:", "Input attachments:"):
                if token not in integration_text:
                    errors.append(
                        f"Planner integration section missing {token!r}: "
                        f"{plan_reference}"
                    )


def validate_worker_pipeline_contract(
    errors: list[str], hermes_root: Path = HERMES_ROOT
) -> None:
    mode_tokens = {
        "planner": "Mode: integrate",
        "engineer": "Mode: execute",
        "researcher": "Mode: analyze",
        "searcher": "Mode: retrieve",
        "creator": "Mode: execute",
        "writer": "Mode: execute",
        "qa": "Mode: verify",
        "marketer": "Mode: execute",
    }
    config_mode_tokens = {
        "planner": "Mode: integrate",
        "engineer": "Mode: execute",
        "researcher": "Mode: analyze",
        "searcher": "Mode: retrieve",
        "creator": "Mode: execute",
        "writer": "Mode execute",
        "qa": "Mode: verify",
        "marketer": "Mode execute",
    }
    profile_tokens = {
        "planner": {
            "metadata.artifact_handoff",
            "metadata.execution_outline",
            "sibling of `completion`",
            '"status":"completed"',
        },
        "engineer": {
            "Mode: plan",
            "metadata.artifact_handoff",
            "metadata.specialist_plan",
            "FAN_OUT_READY:",
            "sibling of `completion`",
            '"status":"completed"',
        },
        "researcher": {
            "metadata.artifact_handoff",
            "FAN_OUT_READY:",
            "claim-ledger.md",
            "status: superseded",
            '"status":"completed"',
            '"status":"superseded"',
        },
        "searcher": {
            "terminal evidence worker",
            "never decomposes work",
            '"status":"completed"',
        },
        "creator": {
            "Mode: plan",
            "metadata.artifact_handoff",
            "metadata.specialist_plan",
            "FAN_OUT_READY:",
            "sibling of `completion`",
            '"status":"completed"',
        },
        "writer": {
            "Mode: plan",
            "metadata.artifact_handoff",
            "metadata.specialist_plan",
            "FAN_OUT_READY:",
            "sibling of `completion`",
            '"status":"completed"',
        },
        "qa": {
            "metadata.qa",
            "does not emit `metadata.artifact_handoff`",
            '"status":FINAL_VERDICT',
            "FINAL_VERDICT",
            "QA TaskSpec never carries `pending-assistant-probe`",
            "Match every candidate and evidence attachment",
        },
        "marketer": {
            "Mode: plan",
            "metadata.artifact_handoff",
            "metadata.specialist_plan",
            "FAN_OUT_READY:",
            "APPROVAL:",
            "sibling of `completion`",
            '"status":"completed"',
        },
    }
    lifecycle_token = "admit -> route -> act_or_plan -> verify -> handoff -> terminal"

    for profile in WORKER_PROFILES:
        profile_root = hermes_root / "profiles" / profile
        pipeline_dir = profile_root / "skills" / f"{profile}-pipeline"
        pipeline = pipeline_dir / "SKILL.md"
        config = profile_root / "config.yaml"

        if not pipeline.is_file():
            errors.append(f"worker pipeline contract file not found: {pipeline}")
            continue
        pipeline_text = pipeline.read_text(encoding="utf-8")
        required_pipeline = {
            lifecycle_token,
            mode_tokens[profile],
            "metadata.completion",
            "Input attachments:",
            "FINAL_SUMMARY",
            "byte-for-byte",
            "done` is a Kanban task state",
            *profile_tokens[profile],
        }
        for token in sorted(required_pipeline):
            if token not in pipeline_text:
                errors.append(
                    f"{profile} worker pipeline contract missing {token!r}: {pipeline}"
                )

        lifecycle_markers = {
            "searcher": ("<LifecycleContract>", "</LifecycleContract>"),
            "researcher": ("<LifecycleContract>", "</LifecycleContract>"),
            "qa": ("<Lifecycle>", "</Lifecycle>"),
        }
        markers = lifecycle_markers.get(profile)
        if markers is not None:
            lifecycle = section_body(
                pipeline_text,
                *markers,
                f"{profile} worker pipeline",
                errors,
            )
            if lifecycle is not None and "input_attachments" not in lifecycle:
                errors.append(
                    f"{profile} worker pipeline lifecycle missing "
                    f"'input_attachments': {pipeline}"
                )

        managed_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted(pipeline_dir.rglob("*.md"))
            if path.is_file()
        )
        for token in sorted(WORKER_FORBIDDEN_TEXT):
            if token in managed_text:
                errors.append(
                    f"{profile} worker pipeline retains forbidden text {token!r}"
                )

        if not config.is_file():
            errors.append(f"worker config not found: {config}")
            continue
        config_text = config.read_text(encoding="utf-8")
        for token in (
            "kanban_show",
            config_mode_tokens[profile],
            "metadata.completion",
        ):
            if token not in config_text:
                errors.append(
                    f"{profile} worker config contract missing {token!r}: {config}"
                )
        for token in sorted(WORKER_FORBIDDEN_TEXT):
            if token in config_text:
                errors.append(
                    f"{profile} worker config retains forbidden text {token!r}"
                )


def relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def is_ignored(path: Path) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "-q", "--", relative(path)],
        cwd=REPO_ROOT,
        check=False,
    )
    return result.returncode == 0


def tracked_learned_files() -> list[str]:
    result = subprocess.run(
        [
            "git",
            "ls-files",
            "--",
            "hermes/skills/learned/**",
            "hermes/profiles/*/skills/learned/**",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def untracked_managed_files() -> list[str]:
    result = subprocess.run(
        [
            "git",
            "ls-files",
            "--others",
            "--exclude-standard",
            "--",
            "hermes/skills/orchestration/**",
            "hermes/skills/workspaces/**",
            "hermes/profiles/*/skills/*-pipeline/**",
            "hermes/profiles/*/skills/technic/**",
            "hermes/profiles/assistant/skills/desks/**",
            "hermes/plugins/skill-topology/**",
            "hermes/plugins/kanban-completion-path-guard/**",
            "hermes/plugins/kanban-worker-mutation-guard/**",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def validate_skill(
    path: Path,
    expected_name: str,
    errors: list[str],
    expected_category: str | None = None,
) -> None:
    data = frontmatter(path)
    if not data:
        errors.append(f"missing or invalid frontmatter: {path}")
        return
    if data.get("name") != expected_name:
        errors.append(f"frontmatter name must be {expected_name}: {path}")
    if expected_category and hermes_category(data) != expected_category:
        errors.append(
            f"metadata.hermes.category must be {expected_category}: {path}"
        )


def validate_allowed_skill_roots(
    skills: Path,
    allowed: set[tuple[str, ...]],
    errors: list[str],
) -> None:
    for entry in skills.iterdir():
        if entry.is_symlink():
            errors.append(f"local skill root must not contain symlinks: {entry}")

    for path in sorted(skills.rglob("SKILL.md")):
        rel = path.relative_to(skills)
        if any(part.startswith(".") for part in rel.parts):
            continue
        if rel.parts not in allowed:
            errors.append(f"unexpected skill root: {path}")


def validate_git_boundary(
    managed: list[Path], learned: Path, errors: list[str]
) -> None:
    for path in managed:
        if path.exists() and is_ignored(path):
            errors.append(f"managed skill path is gitignored: {path}")
    if not is_ignored(learned / ".gitignore-probe"):
        errors.append(f"learned skill path must be gitignored: {learned}")


def validate_plugin_source(errors: list[str]) -> None:
    for name in (
        "skill-topology",
        COMPLETION_PATH_GUARD_PLUGIN,
        WORKER_MUTATION_GUARD_PLUGIN,
    ):
        plugin = HERMES_ROOT / "plugins" / name
        manifest = plugin / "plugin.yaml"
        implementation = plugin / "__init__.py"
        if not manifest.is_file():
            errors.append(f"{name} manifest not found: {manifest}")
        elif load_yaml(manifest).get("name") != name:
            errors.append(f"{name} manifest has the wrong name: {manifest}")
        if not implementation.is_file():
            errors.append(f"{name} implementation not found: {implementation}")


def validate_plugin_enabled(profile: str, config: Path, errors: list[str]) -> None:
    if not config.is_file():
        errors.append(f"profile config not found: {config}")
        return
    enabled = load_yaml(config).get("plugins", {}).get("enabled", [])
    if not isinstance(enabled, list) or "skill-topology" not in enabled:
        errors.append(f"skill-topology plugin is not enabled: {config}")
    if profile in COMPLETION_PATH_GUARD_PROFILES and (
        not isinstance(enabled, list) or COMPLETION_PATH_GUARD_PLUGIN not in enabled
    ):
        errors.append(
            f"{COMPLETION_PATH_GUARD_PLUGIN} plugin is not enabled: {config}"
        )
    if profile in WORKER_PROFILES and (
        not isinstance(enabled, list) or WORKER_MUTATION_GUARD_PLUGIN not in enabled
    ):
        errors.append(
            f"{WORKER_MUTATION_GUARD_PLUGIN} plugin is not enabled: {config}"
        )


def validate_worker(
    profile: str,
    errors: list[str],
    dispatch: Path | None = None,
) -> tuple[int, int]:
    profile_root = HERMES_ROOT / "profiles" / profile
    skills = profile_root / "skills"
    pipeline_name = f"{profile}-pipeline"
    pipeline_dir = skills / pipeline_name
    pipeline = pipeline_dir / "SKILL.md"
    technic_dir = skills / "technic"
    learned_dir = skills / "learned"

    if not pipeline.is_file():
        errors.append(f"missing root pipeline: {pipeline}")
    else:
        validate_skill(pipeline, pipeline_name, errors)

    if not technic_dir.is_dir():
        errors.append(f"missing technic directory: {technic_dir}")

    leaves: dict[str, Path] = {}
    if technic_dir.is_dir():
        for path in sorted(technic_dir.glob("*/SKILL.md")):
            name = path.parent.name
            validate_skill(path, name, errors, expected_category="technic")
            if name in leaves:
                errors.append(f"duplicate technic name {name}: {leaves[name]} and {path}")
            leaves[name] = path

    learned: dict[str, Path] = {}
    if learned_dir.is_dir():
        for path in sorted(learned_dir.glob("*/SKILL.md")):
            name = path.parent.name
            validate_skill(path, name, errors)
            learned[name] = path

    allowed = {(pipeline_name, "SKILL.md")}
    allowed.update(("technic", name, "SKILL.md") for name in leaves)
    allowed.update(("learned", name, "SKILL.md") for name in learned)
    validate_allowed_skill_roots(skills, allowed, errors)

    capabilities = pipeline_dir / "references" / "capabilities.md"
    if capabilities.is_file():
        routed = capability_names(capabilities)
        for name in sorted(routed - leaves.keys()):
            errors.append(f"capability has no technic directory: {name}")
        for name in sorted(leaves.keys() - routed):
            errors.append(f"technic missing from capability table: {name}")

        if profile == "qa":
            creator_capabilities = (
                HERMES_ROOT
                / "profiles"
                / "creator"
                / "skills"
                / "creator-pipeline"
                / "references"
                / "capabilities.md"
            )
            creator_leaves = capability_names(creator_capabilities)
            qa_sources = {source for source, _ in capability_routes(capabilities)}
            for name in sorted(creator_leaves - qa_sources):
                errors.append(f"creator capability missing QA route: {name}")
            for name in sorted(
                source
                for source in qa_sources
                if source.startswith("creator-") and source not in creator_leaves
            ):
                errors.append(f"QA route names unknown creator capability: {name}")
            for name in sorted(QA_REQUIRED_NON_CREATOR_ROUTES - qa_sources):
                errors.append(f"non-Creator capability missing QA route: {name}")
            for name in sorted(
                source
                for source in qa_sources
                if (source.startswith("writer:") or source.startswith("core:"))
                and source not in QA_REQUIRED_NON_CREATOR_ROUTES
            ):
                errors.append(f"QA route names unknown non-Creator capability: {name}")

    if dispatch:
        resolved = dispatch if dispatch.is_absolute() else HERMES_ROOT / dispatch
        if not resolved.is_file():
            errors.append(f"dispatch reference not found: {resolved}")
        else:
            dispatch_text = resolved.read_text(encoding="utf-8")
            for name in sorted(leaves):
                if f"`{name}`" not in dispatch_text:
                    errors.append(f"dispatch reference does not name {name}")

    validate_git_boundary([pipeline_dir, technic_dir], learned_dir, errors)
    validate_plugin_enabled(profile, profile_root / "config.yaml", errors)
    return len(leaves), len(learned)


def validate_assistant(errors: list[str]) -> tuple[int, int, int]:
    profile_root = HERMES_ROOT / "profiles" / "assistant"
    skills = profile_root / "skills"
    desks_dir = skills / "desks"
    technic_dir = skills / "technic"
    learned_dir = skills / "learned"

    if not (HERMES_ROOT / "skills" / "orchestration" / "SKILL.md").is_file():
        errors.append("assistant pipeline equivalent is missing: shared orchestration")
    if not desks_dir.is_dir():
        errors.append(f"missing assistant desks directory: {desks_dir}")
    if not technic_dir.is_dir():
        errors.append(f"missing assistant technic directory: {technic_dir}")

    groups: dict[str, dict[str, Path]] = {"desks": {}, "technic": {}, "learned": {}}
    for category, directory in (
        ("desks", desks_dir),
        ("technic", technic_dir),
        ("learned", learned_dir),
    ):
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*/SKILL.md")):
            name = path.parent.name
            validate_skill(
                path,
                name,
                errors,
                expected_category=category if category != "learned" else None,
            )
            groups[category][name] = path

    allowed: set[tuple[str, ...]] = set()
    for category, skills_by_name in groups.items():
        allowed.update((category, name, "SKILL.md") for name in skills_by_name)
    validate_allowed_skill_roots(skills, allowed, errors)

    config = profile_root / "config.yaml"
    if config.is_file():
        data = load_yaml(config)
        dm_topics = (
            data.get("platforms", {})
            .get("telegram", {})
            .get("extra", {})
            .get("dm_topics", [])
        )
        for chat in dm_topics if isinstance(dm_topics, list) else []:
            for topic in chat.get("topics", []) if isinstance(chat, dict) else []:
                skill = topic.get("skill") if isinstance(topic, dict) else None
                if skill and skill not in groups["desks"]:
                    errors.append(f"Telegram topic binds a non-desk skill: {skill}")

    validate_git_boundary([desks_dir, technic_dir], learned_dir, errors)
    if config.is_file():
        validate_plugin_enabled("assistant", config, errors)
    validate_plugin_enabled("assistant", profile_root / "config.example.yaml", errors)
    return len(groups["desks"]), len(groups["technic"]), len(groups["learned"])


def validate_shared(errors: list[str]) -> tuple[int, int]:
    skills = HERMES_ROOT / "skills"
    orchestration = skills / "orchestration"
    workspaces = skills / "workspaces"
    learned_dir = skills / "learned"

    managed: dict[str, Path] = {}
    orchestration_skill = orchestration / "SKILL.md"
    if orchestration_skill.is_file():
        validate_skill(orchestration_skill, "orchestration", errors)
        managed["orchestration"] = orchestration_skill
    else:
        errors.append(f"missing shared orchestration skill: {orchestration_skill}")

    for path in sorted(workspaces.glob("*/SKILL.md")):
        name = path.parent.name
        validate_skill(path, name, errors)
        managed[name] = path

    learned: dict[str, Path] = {}
    if learned_dir.is_dir():
        for path in sorted(learned_dir.glob("*/SKILL.md")):
            name = path.parent.name
            validate_skill(path, name, errors)
            learned[name] = path

    allowed = {("orchestration", "SKILL.md")}
    allowed.update(("workspaces", name, "SKILL.md") for name in managed if name != "orchestration")
    allowed.update(("learned", name, "SKILL.md") for name in learned)
    validate_allowed_skill_roots(skills, allowed, errors)
    validate_git_boundary([orchestration, workspaces], learned_dir, errors)
    validate_plugin_enabled("default", HERMES_ROOT / "config.yaml", errors)
    return len(managed), len(learned)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile", nargs="?", choices=ALL_PROFILES)
    parser.add_argument("--all", action="store_true", help="validate shared and all profiles")
    parser.add_argument(
        "--strict-git",
        action="store_true",
        help="fail instead of warn when managed skill files are untracked",
    )
    parser.add_argument(
        "--dispatch",
        type=Path,
        help="optional dispatch reference that must name every profile technic",
    )
    args = parser.parse_args()

    if args.all == bool(args.profile):
        parser.error("choose exactly one profile or --all")
    if args.all and args.dispatch:
        parser.error("--dispatch requires one worker profile")
    if args.strict_git and not args.all:
        parser.error("--strict-git requires --all")
    if args.profile == "assistant" and args.dispatch:
        parser.error("--dispatch is only valid for worker profiles")

    errors: list[str] = []
    warnings: list[str] = []
    summaries: list[str] = []

    if args.all:
        workflow_version = validate_workflow_contract(errors)
        if workflow_version is not None:
            summaries.append(f"workflow-contract=v{workflow_version}")
        validate_assistant_orchestration_contract(errors)
        validate_specialist_planning_contract(errors)
        validate_worker_pipeline_contract(errors)
        validate_plugin_source(errors)
        managed, learned = validate_shared(errors)
        summaries.append(f"shared={managed} managed/{learned} learned")
        desks, technics, learned = validate_assistant(errors)
        summaries.append(
            f"assistant={desks} desks/{technics} technics/{learned} learned"
        )
        for profile in WORKER_PROFILES:
            technics, learned = validate_worker(profile, errors)
            summaries.append(f"{profile}={technics} technics/{learned} learned")
        for path in tracked_learned_files():
            errors.append(f"learned skill file must not be tracked: {path}")
        for path in untracked_managed_files():
            message = f"managed skill file is untracked: {path}"
            (errors if args.strict_git else warnings).append(message)
    elif args.profile == "assistant":
        desks, technics, learned = validate_assistant(errors)
        summaries.append(
            f"assistant={desks} desks/{technics} technics/{learned} learned"
        )
    else:
        technics, learned = validate_worker(args.profile, errors, args.dispatch)
        summaries.append(f"{args.profile}={technics} technics/{learned} learned")

    for warning in warnings:
        print(f"WARN: {warning}")

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1

    print(f"PASS: {'; '.join(summaries)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
