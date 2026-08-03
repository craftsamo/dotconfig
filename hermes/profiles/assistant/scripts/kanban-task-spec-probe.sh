#!/bin/sh
# Emit the complete immutable registration fingerprint for one Kanban task.

set -eu

if [ "$#" -ne 1 ]; then
  echo "usage: kanban-task-spec-probe.sh <task-id>" >&2
  exit 2
fi

exec /usr/bin/python3 - "$1" <<'PY'
import hashlib
import json
import os
import sqlite3
import sys
from pathlib import Path

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


db = str(kanban_db_path())

conn = sqlite3.connect(db)
conn.execute("PRAGMA query_only = ON")
conn.row_factory = sqlite3.Row
row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
if row is None:
    print(f"task not found: {task_id}", file=sys.stderr)
    raise SystemExit(1)

keys = set(row.keys())


def value(name):
    return row[name] if name in keys else None


skills = value("skills")
if isinstance(skills, str):
    try:
        skills = json.loads(skills)
    except json.JSONDecodeError:
        skills = None

body = value("body") or ""
parents = [
    item[0]
    for item in conn.execute(
        "SELECT parent_id FROM task_links WHERE child_id = ? ORDER BY parent_id",
        (task_id,),
    ).fetchall()
]
created = conn.execute(
    "SELECT payload FROM task_events WHERE task_id = ? AND kind = 'created' "
    "ORDER BY id ASC LIMIT 1",
    (task_id,),
).fetchone()
conn.close()

fingerprint = {
    "id": task_id,
    "idempotency_key": value("idempotency_key"),
    "title": value("title"),
    "body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
    "assignee": value("assignee"),
    "parents": parents,
    "skills": skills,
    "priority": value("priority"),
    "workspace_kind": value("workspace_kind"),
    "workspace_path": value("workspace_path"),
    "tenant": value("tenant"),
    "branch_name": value("branch_name"),
    "project_id": value("project_id"),
    "workflow_template_id": value("workflow_template_id"),
    "max_runtime_seconds": value("max_runtime_seconds"),
    "max_retries": value("max_retries"),
    "goal_mode": bool(value("goal_mode")),
    "goal_max_turns": value("goal_max_turns"),
    "model_override": value("model_override"),
    "provider_override": value("provider_override"),
    "session_id": value("session_id"),
    "status": value("status"),
    "created_event": created[0] if created else None,
}
print(json.dumps(fingerprint, ensure_ascii=True, sort_keys=True))
PY
