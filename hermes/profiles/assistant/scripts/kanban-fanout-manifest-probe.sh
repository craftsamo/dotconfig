#!/bin/sh
# Validate the identity and pre-materialization QA boundary of fan-out.yaml.

set -eu

if [ "$#" -ne 1 ]; then
  echo "usage: kanban-fanout-manifest-probe.sh <origin-task-id>" >&2
  exit 2
fi

PYTHON=${HERMES_PYTHON:-}
if [ -z "$PYTHON" ]; then
  HERMES_ENTRY=${HERMES_BIN:-"${HOME:-}/.local/bin/hermes"}
  HERMES_TARGET=$(readlink "$HERMES_ENTRY" 2>/dev/null || :)
  if [ -z "$HERMES_TARGET" ]; then
    HERMES_TARGET=$HERMES_ENTRY
  elif [ "${HERMES_TARGET#/}" = "$HERMES_TARGET" ]; then
    HERMES_TARGET=$(dirname "$HERMES_ENTRY")/$HERMES_TARGET
  fi
  PYTHON=$(dirname "$HERMES_TARGET")/python
fi
if [ ! -x "$PYTHON" ]; then
  echo "kanban-fanout-manifest-probe: Hermes Python not found; set HERMES_PYTHON" >&2
  exit 1
fi

exec "$PYTHON" - "$1" <<'PY'
import hashlib
import json
import os
import sqlite3
import sys
from pathlib import Path

import yaml

task_id = sys.argv[1]


def kanban_root():
    override = os.environ.get("HERMES_KANBAN_HOME", "").strip()
    if override:
        return Path(override).expanduser()
    home = Path(os.environ.get("HERMES_HOME", "~/.hermes")).expanduser()
    return home.parent.parent if home.parent.name == "profiles" else home


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


conn = sqlite3.connect(str(kanban_db_path()))
conn.execute("PRAGMA query_only = ON")
conn.row_factory = sqlite3.Row
task = conn.execute(
    "SELECT id, assignee, status FROM tasks WHERE id = ?", (task_id,)
).fetchone()
errors = []
if task is None:
    errors.append(f"task not found: {task_id}")
elif task["status"] not in ("blocked", "triage"):
    errors.append("fan-out origin must be blocked or triage")

attachments = conn.execute(
    "SELECT stored_path FROM task_attachments "
    "WHERE task_id = ? AND filename = 'fan-out.yaml' ORDER BY id",
    (task_id,),
).fetchall()
if len(attachments) != 1:
    errors.append("fan-out origin must have exactly one fan-out.yaml attachment")

manifest = None
if len(attachments) == 1:
    try:
        manifest = yaml.safe_load(Path(attachments[0]["stored_path"]).read_text())
    except (OSError, UnicodeError, yaml.YAMLError):
        errors.append("fan-out.yaml is unreadable or invalid YAML")

if not isinstance(manifest, dict):
    if manifest is not None:
        errors.append("fan-out.yaml must be a mapping")
else:
    task_spec_fields = {
        "goal",
        "inputs",
        "input_attachments",
        "done_criteria",
        "output",
        "constraints",
    }

    def validate_card(card, location, required_fields, expected_key):
        if not isinstance(card, dict):
            errors.append(f"{location} must be a mapping")
            return
        missing = sorted(required_fields - set(card))
        if missing:
            errors.append(f"{location} misses: {', '.join(missing)}")
        assignee = card.get("assignee")
        if not isinstance(assignee, str) or not assignee.strip():
            errors.append(f"{location} must have a non-empty string assignee")
        elif assignee == "qa":
            errors.append(
                f"{location} cannot assign qa: "
                "QA must be late-bound after CompletionAdmission/digest resolution"
            )
        spec = card.get("task_spec")
        if not isinstance(spec, dict):
            errors.append(f"{location}.task_spec must be a mapping")
        else:
            missing_spec = sorted(task_spec_fields - set(spec))
            if missing_spec:
                errors.append(
                    f"{location}.task_spec misses: {', '.join(missing_spec)}"
                )
            if assignee in ("creator", "writer") and spec.get("qa") == "required":
                requirement = spec.get("producer_qa_requirement")
                requirement_fields = {
                    "candidate_key",
                    "evidence_keys",
                    "capability",
                    "routes",
                    "criteria",
                    "done_criteria",
                    "output_inventory",
                }
                if not isinstance(requirement, dict) or set(requirement) != requirement_fields:
                    errors.append(
                        f"{location}.task_spec.producer_qa_requirement must be the closed canonical object"
                    )
                else:
                    if not all(
                        isinstance(requirement[field], str) and requirement[field]
                        for field in ("candidate_key", "capability")
                    ):
                        errors.append(
                            f"{location}.task_spec.producer_qa_requirement identity is invalid"
                        )
                    elif requirement["candidate_key"] != expected_key:
                        errors.append(
                            f"{location}.task_spec.producer_qa_requirement.candidate_key must match the card key"
                        )
                    if not isinstance(requirement["evidence_keys"], list) or not all(
                        isinstance(key, str) and key
                        for key in requirement["evidence_keys"]
                    ):
                        errors.append(
                            f"{location}.task_spec.producer_qa_requirement evidence_keys are invalid"
                        )
                    if not isinstance(requirement["routes"], list) or not all(
                        isinstance(route, str) and route.startswith("qa-")
                        for route in requirement["routes"]
                    ):
                        errors.append(
                            f"{location}.task_spec.producer_qa_requirement routes are invalid"
                        )
                    if any(
                        requirement[field] in (None, "", [], {})
                        for field in ("routes", "criteria", "done_criteria", "output_inventory")
                    ):
                        errors.append(
                            f"{location}.task_spec.producer_qa_requirement is incomplete"
                        )
                    for field in ("criteria", "output_inventory"):
                        value = requirement[field]
                        if not isinstance(value, list) or not all(
                            isinstance(item, (str, dict)) and bool(item)
                            for item in value
                        ):
                            errors.append(
                                f"{location}.task_spec.producer_qa_requirement {field} is invalid"
                            )

    if manifest.get("origin_task_id") != task_id:
        errors.append("fan-out.yaml origin_task_id must match the origin task")
    checkpoint = manifest.get("checkpoint_key")
    if not isinstance(checkpoint, str) or not checkpoint.strip():
        errors.append("fan-out.yaml checkpoint_key must be a non-empty string")

    children = manifest.get("children")
    if not isinstance(children, list) or not children:
        errors.append("fan-out.yaml children must be a non-empty list")
    else:
        for index, child in enumerate(children):
            validate_card(
                child,
                f"fan-out.yaml children[{index}]",
                {"key", "title", "assignee", "skills", "parents", "params", "task_spec"},
                child.get("key") if isinstance(child, dict) else None,
            )

    continuation = manifest.get("continuation")
    validate_card(
        continuation,
        "fan-out.yaml continuation",
        {"title", "assignee", "skills", "parents", "params", "task_spec"},
        f"{task_id}:fanout:{checkpoint}:continuation",
    )
    if isinstance(continuation, dict):
        assignee = continuation.get("assignee")
        if (
            isinstance(assignee, str)
            and assignee != "qa"
            and task is not None
            and assignee != task["assignee"]
        ):
            errors.append("fan-out.yaml continuation assignee must match the origin")

    attachment_specs = manifest.get("attachments")
    if not isinstance(attachment_specs, list):
        errors.append("fan-out.yaml attachments must be a list")
    else:
        for index, attachment in enumerate(attachment_specs):
            location = f"fan-out.yaml attachments[{index}]"
            if not isinstance(attachment, dict):
                errors.append(f"{location} must be a mapping")
                continue
            missing = sorted(
                {"name", "sha256", "purpose", "source_task_id"} - set(attachment)
            )
            if missing:
                errors.append(f"{location} misses: {', '.join(missing)}")

normalized = None
if isinstance(manifest, dict):
    try:
        normalized = json.dumps(
            manifest, ensure_ascii=True, sort_keys=True, separators=(",", ":")
        )
    except (TypeError, ValueError):
        errors.append("fan-out.yaml must contain only JSON-compatible values")

conn.close()
if errors:
    print(json.dumps({"valid": False, "errors": errors}, ensure_ascii=True))
    raise SystemExit(1)

print(
    json.dumps(
        {
            "valid": True,
            "origin_task_id": task_id,
            "checkpoint_key": manifest["checkpoint_key"],
            "manifest_digest": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
            "manifest": manifest,
        },
        ensure_ascii=True,
        sort_keys=True,
    )
)
PY
