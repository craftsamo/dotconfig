#!/bin/sh
# Validate the canonical completion handoff for one terminal Kanban task.

set -eu

if [ "$#" -ne 1 ]; then
  echo "usage: kanban-completion-probe.sh <task-id>" >&2
  exit 2
fi

exec /usr/bin/python3 - "$1" <<'PY'
import hashlib
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

task_id = sys.argv[1]


def kanban_root():
    override = os.environ.get("HERMES_KANBAN_HOME", "").strip()
    if override:
        return Path(override).expanduser()
    home = Path(os.environ.get("HERMES_HOME", "~/.hermes")).expanduser()
    if home.parent.name == "profiles":
        return home.parent.parent
    return home


def kanban_db_path():
    override = os.environ.get("HERMES_KANBAN_DB", "").strip()
    if override:
        return Path(override).expanduser()
    root = kanban_root()
    board = os.environ.get("HERMES_KANBAN_BOARD", "").strip()
    if not board:
        try:
            board = (root / "kanban" / "current").read_text().strip()
        except OSError:
            board = ""
    if not board or board == "default":
        return root / "kanban.db"
    return root / "kanban" / "boards" / board / "kanban.db"


db = str(kanban_db_path())

conn = sqlite3.connect(db)
conn.execute("PRAGMA query_only = ON")
conn.row_factory = sqlite3.Row
task = conn.execute(
    "SELECT id, assignee, body, status, skills FROM tasks WHERE id = ?", (task_id,)
).fetchone()
if task is None:
    print(f"task not found: {task_id}", file=sys.stderr)
    raise SystemExit(1)

run = conn.execute(
    "SELECT id, started_at, summary, metadata FROM task_runs "
    "WHERE task_id = ? AND outcome = 'completed' ORDER BY id DESC LIMIT 1",
    (task_id,),
).fetchone()
parents = [
    row[0]
    for row in conn.execute(
        "SELECT parent_id FROM task_links WHERE child_id = ? ORDER BY parent_id",
        (task_id,),
    ).fetchall()
]


def attachment_row(source_task_id, name):
    return conn.execute(
        "SELECT filename, stored_path FROM task_attachments "
        "WHERE task_id = ? AND filename = ? ORDER BY id DESC LIMIT 1",
        (source_task_id, name),
    ).fetchone()


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def latest_metadata(source_task_id):
    row = conn.execute(
        "SELECT metadata FROM task_runs WHERE task_id = ? AND outcome = 'completed' "
        "ORDER BY id DESC LIMIT 1",
        (source_task_id,),
    ).fetchone()
    if row is None:
        return None
    try:
        value = json.loads(row[0] or "null")
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None

errors = []
input_match = re.search(
    r"(?m)^Input attachments:\s*(\[[^\n]*\])\s*$", task["body"] or ""
)
input_attachments = []
if input_match is None:
    errors.append("TaskSpec must declare Input attachments as a JSON array")
else:
    try:
        input_attachments = json.loads(input_match.group(1))
    except json.JSONDecodeError as exc:
        errors.append(f"Input attachments is invalid JSON: {exc}")
    if not isinstance(input_attachments, list):
        errors.append("Input attachments must be a JSON list of attachment specs")
        input_attachments = []
for item in input_attachments:
    if not isinstance(item, dict):
        errors.append("Input attachments entries must be attachment spec objects")
        continue
    for field in ("name", "sha256", "purpose", "source_task_id"):
        if not isinstance(item.get(field), str) or not item.get(field):
            errors.append(f"Input attachment {field} is required")
    row = attachment_row(item.get("source_task_id"), item.get("name"))
    if row is None:
        errors.append(
            "declared input attachment is missing from source task: "
            + str(item.get("name"))
        )
    elif isinstance(item.get("sha256"), str):
        try:
            actual_digest = file_sha256(row["stored_path"])
        except OSError as exc:
            errors.append(f"declared input attachment is unreadable: {exc}")
        else:
            if actual_digest != item["sha256"]:
                errors.append(
                    "declared input attachment digest mismatch: " + item["name"]
                )
metadata = None
if task["status"] != "done":
    errors.append(f"task status is {task['status']}, expected done")
if run is None:
    errors.append("completed run not found")
else:
    try:
        metadata = json.loads(run["metadata"] or "null")
    except json.JSONDecodeError as exc:
        errors.append(f"run metadata is invalid JSON: {exc}")

if not isinstance(metadata, dict):
    errors.append("run metadata must be an object")
    metadata = {}

completion = metadata.get("completion")
if not isinstance(completion, dict):
    errors.append("metadata.completion must be exactly one object")
    completion = {}
for field in ("status", "summary", "metadata"):
    if field not in completion:
        errors.append(f"metadata.completion.{field} is required")
if "status" in completion and not isinstance(completion["status"], str):
    errors.append("metadata.completion.status must be a string")
if "summary" in completion and not isinstance(completion["summary"], str):
    errors.append("metadata.completion.summary must be a string")
if "metadata" in completion and not isinstance(completion["metadata"], dict):
    errors.append("metadata.completion.metadata must be an object")
if run is not None and completion.get("summary") != (run["summary"] or ""):
    errors.append("metadata.completion.summary must equal kanban_complete summary")

completion_status = completion.get("status")
allowed_statuses = (
    {"pass", "fail", "can't_verify"}
    if task["assignee"] == "qa"
    else {"completed", "superseded"}
)
if completion_status not in allowed_statuses:
    errors.append(
        "metadata.completion.status must be one of: "
        + ", ".join(sorted(allowed_statuses))
    )

declared_artifacts = completion.get("artifacts", [])
if declared_artifacts is None:
    declared_artifacts = []


def artifact_names(items):
    names = []
    if not isinstance(items, list):
        return names
    for item in items:
        if isinstance(item, str) and item:
            names.append(item)
        elif isinstance(item, dict) and isinstance(item.get("name"), str):
            names.append(item["name"])
    return names
if not isinstance(declared_artifacts, list) or not all(
    isinstance(item, str) and item for item in declared_artifacts
):
    errors.append("metadata.completion.artifacts must be a list of names")
    declared_artifacts = []

handoff = metadata.get("artifact_handoff")
declared_names = artifact_names(declared_artifacts)
has_output_artifact = bool(declared_names or handoff is not None)
output_attachments = []
output_digests = {}
output_paths = {}
qa_handoff = None
if not declared_names and handoff is not None:
    errors.append("metadata.artifact_handoff must be absent without current outputs")
if has_output_artifact:
    if not isinstance(handoff, dict):
        errors.append("metadata.artifact_handoff is required for attached artifacts")
        handoff = {}
    for field in ("artifacts", "verification", "qa"):
        if field not in handoff:
            errors.append(f"metadata.artifact_handoff.{field} is required")
    if not isinstance(handoff.get("verification"), list) or not handoff.get(
        "verification"
    ):
        errors.append("metadata.artifact_handoff.verification must be a non-empty list")
    qa_handoff = handoff.get("qa")
    if not isinstance(qa_handoff, dict):
        errors.append("metadata.artifact_handoff.qa must be an object")
        qa_handoff = {}
    qa_status = qa_handoff.get("status")
    if qa_status not in ("required", "evidence", "exempt"):
        errors.append(
            "metadata.artifact_handoff.qa.status must be required, evidence, or exempt"
        )
    elif qa_status == "required":
        if not isinstance(qa_handoff.get("capability"), str) or not qa_handoff.get(
            "capability"
        ):
            errors.append("required QA handoff must name a producer capability")
        routes = qa_handoff.get("routes")
        if not isinstance(routes, list) or not routes or not all(
            isinstance(route, str) and route.startswith("qa-") for route in routes
        ):
            errors.append("required QA handoff must name non-empty QA routes")
    elif qa_status == "evidence":
        if qa_handoff.get("consumer") != "qa":
            errors.append("QA evidence handoff consumer must be qa")
        if not isinstance(qa_handoff.get("ledger"), str) or not qa_handoff.get(
            "ledger"
        ):
            errors.append("QA evidence handoff must name its ledger attachment")
    elif not isinstance(qa_handoff.get("reason"), str) or not qa_handoff.get(
        "reason"
    ):
        errors.append("exempt QA handoff must state a reason")
    handoff_artifacts = handoff.get("artifacts", [])
    if not isinstance(handoff_artifacts, list):
        errors.append("metadata.artifact_handoff.artifacts must be a list")
    else:
        for item in handoff_artifacts:
            if not isinstance(item, dict):
                errors.append(
                    "metadata.artifact_handoff artifacts must be attachment spec objects"
                )
                continue
            for field in ("name", "sha256", "purpose", "source_task_id"):
                if not isinstance(item.get(field), str) or not item.get(field):
                    errors.append(f"output attachment {field} is required")
            if item.get("source_task_id") != task_id:
                errors.append("output attachment source_task_id must match task id")
            row = attachment_row(task_id, item.get("name"))
            if row is None:
                errors.append(
                    "metadata.artifact_handoff declares nonexistent artifact: "
                    + str(item.get("name"))
                )
                continue
            try:
                actual_digest = file_sha256(row["stored_path"])
            except OSError as exc:
                errors.append(f"output attachment is unreadable: {exc}")
                continue
            declared_digest = item.get("sha256")
            assistant_probe_pending = (
                task["assignee"] in ("planner", "writer", "researcher")
                and declared_digest == "pending-assistant-probe"
            )
            if not assistant_probe_pending and actual_digest != declared_digest:
                errors.append("output attachment digest mismatch: " + item["name"])
            output_attachments.append(item["name"])
            output_digests[item["name"]] = actual_digest
            output_paths[item["name"]] = row["stored_path"]
        if sorted(set(declared_names)) != sorted(set(output_attachments)):
            errors.append(
                "metadata.completion.artifacts must equal artifact handoff inventory"
            )
        if (
            isinstance(qa_handoff, dict)
            and qa_handoff.get("status") == "evidence"
            and qa_handoff.get("ledger") not in output_attachments
        ):
            errors.append("QA evidence ledger must name an output artifact")

body = task["body"] or ""
if "Mode: plan" in body and completion_status != "superseded":
    specialist = metadata.get("specialist_plan")
    if not isinstance(specialist, dict):
        errors.append("final Mode: plan completion requires metadata.specialist_plan")
    else:
        for field in ("origin_task_id", "branch_key", "summary", "proposed_cards"):
            if field not in specialist:
                errors.append(f"metadata.specialist_plan.{field} is required")
        if specialist.get("origin_task_id") != task_id:
            errors.append("metadata.specialist_plan.origin_task_id must match task id")
        branch_match = re.search(r"(?m)^Planning branch:\s*(\S+)\s*$", body)
        if branch_match and specialist.get("branch_key") != branch_match.group(1):
            errors.append("metadata.specialist_plan.branch_key must match TaskSpec")
        if not isinstance(specialist.get("proposed_cards"), list):
            errors.append("metadata.specialist_plan.proposed_cards must be a list")
        else:
            child_fields = {
                "key",
                "title",
                "assignee",
                "skills",
                "parents",
                "params",
                "task_spec",
            }
            task_fields = {"goal", "inputs", "done_criteria", "output", "constraints"}
            for index, card in enumerate(specialist["proposed_cards"]):
                if not isinstance(card, dict):
                    errors.append(
                        f"metadata.specialist_plan.proposed_cards[{index}] must be an object"
                    )
                    continue
                missing = sorted(child_fields - set(card))
                if missing:
                    errors.append(
                        f"metadata.specialist_plan.proposed_cards[{index}] misses: "
                        + ", ".join(missing)
                    )
                spec = card.get("task_spec")
                if not isinstance(spec, dict) or task_fields - set(spec):
                    errors.append(
                        f"metadata.specialist_plan.proposed_cards[{index}] has invalid TaskSpec"
                    )
                for field in ("key", "title", "assignee"):
                    if not isinstance(card.get(field), str) or not card.get(field):
                        errors.append(
                            f"metadata.specialist_plan.proposed_cards[{index}].{field} must be non-empty"
                        )
                for field in ("skills", "parents"):
                    if not isinstance(card.get(field), list) or not all(
                        isinstance(value, str) and value for value in card.get(field, [])
                    ):
                        errors.append(
                            f"metadata.specialist_plan.proposed_cards[{index}].{field} must be a string list"
                        )
                if not isinstance(card.get("params"), dict):
                    errors.append(
                        f"metadata.specialist_plan.proposed_cards[{index}].params must be an object"
                    )
                if isinstance(spec, dict):
                    for field in task_fields:
                        if spec.get(field) in (None, "", [], {}):
                            errors.append(
                                f"metadata.specialist_plan.proposed_cards[{index}].task_spec.{field} must be non-empty"
                            )
if task["assignee"] == "planner":
    outline = metadata.get("execution_outline")
    if not isinstance(outline, dict):
        errors.append("Planner completion requires metadata.execution_outline")
    else:
        for field in (
            "request_id",
            "attachment",
            "sha256",
            "specialist_task_ids",
            "card_count",
        ):
            if field not in outline:
                errors.append(f"metadata.execution_outline.{field} is required")
        if outline.get("attachment") not in output_attachments:
            errors.append("metadata.execution_outline.attachment must name an output artifact")
        if not isinstance(outline.get("specialist_task_ids"), list) or sorted(
            outline.get("specialist_task_ids", [])
        ) != sorted(parents):
            errors.append(
                "metadata.execution_outline.specialist_task_ids must match direct parents"
            )
        if not isinstance(outline.get("request_id"), str) or not outline.get("request_id"):
            errors.append("metadata.execution_outline.request_id must be a string")
        if type(outline.get("card_count")) is not int or outline.get("card_count") < 1:
            errors.append("metadata.execution_outline.card_count must be a positive integer")
        role_metadata = completion.get("metadata")
        if isinstance(role_metadata, dict) and role_metadata.get("request_id") != outline.get(
            "request_id"
        ):
            errors.append("metadata.execution_outline.request_id must match completion metadata")
        request_match = re.search(r"(?m)^Request run:\s*(\S+)\s*$", body)
        if request_match is None or outline.get("request_id") != request_match.group(1):
            errors.append("metadata.execution_outline.request_id must match Request run")
        outline_name = outline.get("attachment")
        actual_outline_digest = output_digests.get(outline_name)
        if outline.get("sha256") != "pending-assistant-probe":
            errors.append("Planner execution outline sha256 must use probe sentinel")
        outline_path = output_paths.get(outline_name)
        if outline_path:
            try:
                outline_text = open(outline_path, encoding="utf-8").read()
            except (OSError, UnicodeError) as exc:
                errors.append(f"execution outline is unreadable: {exc}")
            else:
                request_line = re.search(r"(?m)^request_id:\s*([^\s#]+)", outline_text)
                if request_line is None or request_line.group(1) != outline.get("request_id"):
                    errors.append("execution outline request_id mismatches handoff")
                actual_card_count = len(re.findall(r"(?m)^  - key:\s*", outline_text))
                if actual_card_count != outline.get("card_count"):
                    errors.append("execution outline card_count mismatches attachment")
        if actual_outline_digest:
            output_digests[outline_name] = actual_outline_digest
if task["assignee"] == "qa":
    qa = metadata.get("qa")
    if not isinstance(qa, dict):
        errors.append("QA completion requires metadata.qa")
    else:
        for field in (
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
        ):
            if field not in qa:
                errors.append(f"metadata.qa.{field} is required")
        production_parents = []
        researcher_parents = []
        unknown_parents = []
        for parent in parents:
            parent_task = conn.execute(
                "SELECT assignee FROM tasks WHERE id = ?", (parent,)
            ).fetchone()
            assignee = parent_task[0] if parent_task else None
            if assignee in ("creator", "writer"):
                production_parents.append(parent)
            elif assignee == "researcher":
                researcher_parents.append(parent)
            else:
                unknown_parents.append(parent)
        if len(production_parents) != 1:
            errors.append("QA must have exactly one Creator or Writer production parent")
        if unknown_parents:
            errors.append("QA has unsupported direct parents: " + ", ".join(unknown_parents))
        target_task = qa.get("target_task")
        if production_parents and target_task != production_parents[0]:
            errors.append("metadata.qa.target_task must be the production parent")
        production_assignee = None
        if production_parents:
            production_task = conn.execute(
                "SELECT assignee FROM tasks WHERE id = ?", (production_parents[0],)
            ).fetchone()
            production_assignee = production_task[0] if production_task else None
        capability = qa.get("producer_capability")
        if production_assignee == "creator" and not (
            isinstance(capability, str)
            and (capability.startswith("creator-") or capability == "core:tts")
        ):
            errors.append("metadata.qa.producer_capability mismatches Creator parent")
        if production_assignee == "writer" and not (
            isinstance(capability, str) and capability.startswith("writer:")
        ):
            errors.append("metadata.qa.producer_capability mismatches Writer parent")
        research_parent_values = qa.get("research_parents")
        if not isinstance(research_parent_values, list) or not all(
            isinstance(value, str) and value for value in research_parent_values
        ) or sorted(research_parent_values) != sorted(researcher_parents):
            errors.append("metadata.qa.research_parents must match Researcher parents")
        if qa.get("verdict") not in ("pass", "fail", "can't_verify"):
            errors.append("metadata.qa.verdict is invalid")
        if qa.get("reviewer_scope") != "read-only":
            errors.append("metadata.qa.reviewer_scope must be read-only")
        try:
            pinned_skills = json.loads(task["skills"] or "[]")
        except (json.JSONDecodeError, TypeError):
            pinned_skills = []
        pinned_technics = sorted(
            skill
            for skill in pinned_skills
            if isinstance(skill, str) and skill.startswith("qa-") and skill != "qa-pipeline"
        )
        qa_technics = qa.get("technics")
        if not isinstance(qa_technics, list) or not all(
            isinstance(value, str) and value for value in qa_technics
        ):
            errors.append("metadata.qa.technics must be a string list")
            qa_technics = []
        criteria = qa.get("criteria")
        criterion_verdicts = []
        criterion_ids = set()
        mapping_gap = False
        if not isinstance(criteria, list) or not criteria:
            errors.append("metadata.qa.criteria must be a non-empty list")
        else:
            for criterion in criteria:
                if not isinstance(criterion, dict):
                    errors.append("metadata.qa.criteria entries must be objects")
                    continue
                criterion_shape_valid = True
                for field in (
                    "id",
                    "requirement",
                    "verdict",
                    "method",
                    "evidence",
                    "exclusions",
                ):
                    value = criterion.get(field)
                    if not isinstance(value, str) or not value.strip():
                        errors.append(
                            f"metadata.qa criterion {field} must be a non-empty string"
                        )
                        criterion_shape_valid = False
                criterion_id = criterion.get("id")
                if isinstance(criterion_id, str) and criterion_id.strip():
                    if criterion_id in criterion_ids:
                        errors.append("metadata.qa criterion ids must be unique")
                        criterion_shape_valid = False
                    criterion_ids.add(criterion_id)
                verdict = criterion.get("verdict")
                if verdict not in ("pass", "fail", "can't_verify"):
                    errors.append("metadata.qa criterion verdict is invalid")
                elif criterion_shape_valid:
                    criterion_verdicts.append(verdict)
                    if verdict == "can't_verify":
                        gap_text = " ".join(
                            str(criterion.get(field, ""))
                            for field in ("requirement", "method", "evidence")
                        ).lower()
                        if any(
                            token in gap_text
                            for token in ("mapping", "technic", "pin", "capability")
                        ):
                            mapping_gap = True
        if pinned_technics:
            if sorted(qa_technics) != pinned_technics:
                errors.append("metadata.qa.technics must match pinned QA technics")
        elif qa_technics:
            errors.append("metadata.qa.technics must be empty when no QA leaf is pinned")
        elif qa.get("verdict") != "can't_verify" or not mapping_gap:
            errors.append(
                "missing QA technic is valid only for a mapping-gap can't_verify verdict"
            )
        findings = qa.get("findings")
        finding_severities = []
        if not isinstance(findings, list):
            errors.append("metadata.qa.findings must be a list")
        else:
            for finding in findings:
                if not isinstance(finding, dict):
                    errors.append("metadata.qa.findings entries must be objects")
                    continue
                finding_shape_valid = True
                for field in ("severity", "location", "issue", "required_action"):
                    value = finding.get(field)
                    if not isinstance(value, str) or not value.strip():
                        errors.append(
                            f"metadata.qa finding {field} must be a non-empty string"
                        )
                        finding_shape_valid = False
                severity = finding.get("severity")
                if severity not in ("blocker", "should-fix", "polish"):
                    errors.append("metadata.qa finding severity is invalid")
                elif finding_shape_valid:
                    finding_severities.append(severity)
        expected_verdict = "pass"
        if "fail" in criterion_verdicts or any(
            severity in ("blocker", "should-fix") for severity in finding_severities
        ):
            expected_verdict = "fail"
        elif "can't_verify" in criterion_verdicts:
            expected_verdict = "can't_verify"
        if qa.get("verdict") != expected_verdict:
            errors.append("metadata.qa.verdict does not match criteria/findings roll-up")
        if not isinstance(qa.get("residual_risk"), str) or not qa.get(
            "residual_risk"
        ).strip():
            errors.append("metadata.qa.residual_risk must be a non-empty string")
        if completion_status != qa.get("verdict"):
            errors.append("metadata.completion.status must match metadata.qa.verdict")
        producer_metadata = latest_metadata(target_task) if target_task else None
        producer_handoff = (
            producer_metadata.get("artifact_handoff")
            if isinstance(producer_metadata, dict)
            else None
        )
        producer_specs = (
            producer_handoff.get("artifacts")
            if isinstance(producer_handoff, dict)
            else None
        )
        producer_inventory = {}
        for item in producer_specs or []:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            digest = item.get("sha256")
            if digest == "pending-assistant-probe" and isinstance(name, str):
                row = attachment_row(target_task, name)
                if row is not None:
                    try:
                        digest = file_sha256(row["stored_path"])
                    except OSError:
                        pass
            producer_inventory[name] = digest
        producer_qa = (
            producer_handoff.get("qa") if isinstance(producer_handoff, dict) else None
        )
        if not isinstance(producer_qa, dict) or producer_qa.get("status") != "required":
            errors.append("QA target must have a required QA handoff")
        else:
            if producer_qa.get("capability") != capability:
                errors.append("QA target capability must match producer QA handoff")
            producer_routes = producer_qa.get("routes")
            if not isinstance(producer_routes, list) or sorted(producer_routes) != sorted(
                pinned_technics
            ):
                errors.append("QA pins must match producer QA handoff routes")
        for researcher_parent in researcher_parents:
            researcher_metadata = latest_metadata(researcher_parent)
            researcher_handoff = (
                researcher_metadata.get("artifact_handoff")
                if isinstance(researcher_metadata, dict)
                else None
            )
            researcher_qa = (
                researcher_handoff.get("qa")
                if isinstance(researcher_handoff, dict)
                else None
            )
            if not isinstance(researcher_qa, dict) or researcher_qa.get(
                "status"
            ) != "evidence":
                errors.append(
                    f"Researcher parent {researcher_parent} must expose a QA evidence handoff"
                )
                continue
            if researcher_qa.get("consumer") != "qa":
                errors.append(
                    f"Researcher parent {researcher_parent} QA consumer must be qa"
                )
            ledger = researcher_qa.get("ledger")
            researcher_specs = researcher_handoff.get("artifacts", [])
            researcher_names = {
                item.get("name")
                for item in researcher_specs
                if isinstance(item, dict) and isinstance(item.get("name"), str)
            }
            if not isinstance(ledger, str) or ledger not in researcher_names:
                errors.append(
                    f"Researcher parent {researcher_parent} must name an attached claim ledger"
                )
            elif attachment_row(researcher_parent, ledger) is None:
                errors.append(
                    f"Researcher parent {researcher_parent} claim ledger is not attached"
                )
        targets = qa.get("target_artifacts")
        if not isinstance(targets, list) or not targets:
            errors.append("metadata.qa.target_artifacts must be a non-empty list")
        else:
            target_inventory = {
                target.get("name"): target.get("sha256")
                for target in targets
                if isinstance(target, dict)
            }
            if target_inventory != producer_inventory:
                errors.append(
                    "metadata.qa.target_artifacts must equal production artifact handoff"
                )
            for target in targets:
                if not isinstance(target, dict):
                    errors.append("metadata.qa.target_artifacts entries must be objects")
                    continue
                row = attachment_row(target_task, target.get("name"))
                if row is None:
                    errors.append("metadata.qa target artifact is not attached to target task")
                elif isinstance(target.get("sha256"), str):
                    try:
                        actual_digest = file_sha256(row["stored_path"])
                    except OSError as exc:
                        errors.append(f"metadata.qa target artifact is unreadable: {exc}")
                    else:
                        if actual_digest != target["sha256"]:
                            errors.append("metadata.qa target artifact digest mismatch")
                if not isinstance(target.get("sha256"), str) or not target.get("sha256"):
                    errors.append("metadata.qa target artifact sha256 is required")
    if handoff is not None:
        errors.append("QA completion must not emit metadata.artifact_handoff")

result = {
    "id": task_id,
    "assignee": task["assignee"],
    "status": task["status"],
    "valid": not errors,
    "errors": errors,
    "input_attachments": input_attachments,
    "output_attachments": output_attachments,
    "output_digests": output_digests,
    "completion": completion,
    "artifact_handoff": handoff,
}
conn.close()
print(json.dumps(result, ensure_ascii=True, sort_keys=True))
raise SystemExit(0 if not errors else 1)
PY
