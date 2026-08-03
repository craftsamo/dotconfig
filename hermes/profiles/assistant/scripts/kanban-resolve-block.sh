#!/bin/sh
# Resolve a decision-backed block and reset its recurrence state as one operation.

set -eu

if [ "$#" -eq 1 ]; then
  OP=apply
  TASK_ID=$1
elif [ "$#" -eq 2 ] && { [ "$1" = inspect ] || [ "$1" = apply ]; }; then
  OP=$1
  TASK_ID=$2
else
  echo "usage: kanban-resolve-block.sh inspect|apply <task-id>" >&2
  exit 2
fi

HERMES=${HERMES_BIN:-}
if [ -z "$HERMES" ]; then
  HERMES=$(command -v hermes 2>/dev/null || :)
fi
if [ -z "$HERMES" ]; then
  HERMES="${HOME:-}/.local/bin/hermes"
fi
if [ ! -x "$HERMES" ]; then
  echo "kanban-resolve-block: hermes CLI not found" >&2
  exit 1
fi

exec /usr/bin/python3 - "$HERMES" "$OP" "$TASK_ID" <<'PY'
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

hermes, operation, task_id = sys.argv[1:]
if not re.fullmatch(r"[A-Za-z0-9._:-]+", task_id):
    print("kanban-resolve-block: invalid task id", file=sys.stderr)
    raise SystemExit(2)

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
conn.row_factory = sqlite3.Row
task = conn.execute(
    "SELECT id, status, block_recurrences, block_kind FROM tasks WHERE id = ?",
    (task_id,),
).fetchone()
if task is None:
    print(f"kanban-resolve-block: task not found: {task_id}", file=sys.stderr)
    raise SystemExit(1)
if task["status"] not in ("blocked", "triage"):
    print(
        f"kanban-resolve-block: {task_id} is {task['status']}; expected blocked or triage",
        file=sys.stderr,
    )
    raise SystemExit(1)

event = conn.execute(
    "SELECT id, created_at, payload FROM task_events WHERE task_id = ? "
    "AND kind IN ('blocked', 'spawn_auto_blocked', 'block_loop_detected') "
    "ORDER BY id DESC LIMIT 1",
    (task_id,),
).fetchone()
if event is None:
    print(f"kanban-resolve-block: {task_id} has no blocking event", file=sys.stderr)
    raise SystemExit(1)

previous_event = conn.execute(
    "SELECT created_at FROM task_events WHERE task_id = ? AND id < ? "
    "AND kind IN ('blocked', 'spawn_auto_blocked', 'block_loop_detected', 'unblocked') "
    "ORDER BY id DESC LIMIT 1",
    (task_id, event["id"]),
).fetchone()
window_start = (previous_event["created_at"] if previous_event else 0) or 0
event_time = event["created_at"] or 0
candidate_rows = conn.execute(
    "SELECT body FROM task_comments WHERE task_id = ? "
    "AND created_at >= ? AND created_at <= ? ORDER BY id ASC",
    (task_id, window_start, event_time),
).fetchall()
question_rows = [
    row
    for row in candidate_rows
    if re.match(
        r"^(?:Q[0-9]+|REVIEW|APPROVAL|FAN_OUT_READY):",
        row["body"] or "",
    )
]
question_ids = {
    match.group(1)
    for row in question_rows
    for match in [re.match(r"^Q([0-9]+):", row["body"] or "")]
    if match
}
decisions = conn.execute(
    "SELECT body, created_at FROM task_comments WHERE task_id = ? "
    "AND author IN ('assistant', 'default') AND body LIKE 'DECISION(%' "
    "ORDER BY id ASC",
    (task_id,),
).fetchall()
decision_re = re.compile(
    r"^DECISION\((?:Q[0-9]+|REVIEW|APPROVAL|FAN_OUT_READY)\):"
)
matching = [
    row["body"]
    for row in decisions
    if (row["created_at"] or 0) >= event_time
    and decision_re.match(row["body"] or "")
]
try:
    event_payload = json.loads(event["payload"] or "{}")
except (TypeError, json.JSONDecodeError):
    event_payload = {}
reason = str(event_payload.get("reason") or event["payload"] or "")
block_contract = {
    "event_id": event["id"],
    "reason": reason,
    "questions": [row["body"] for row in question_rows if row["body"]],
}
block_digest = hashlib.sha256(
    json.dumps(
        block_contract, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
).hexdigest()
binding = f"block_event={event['id']} block_digest={block_digest}"
if operation == "inspect":
    print(binding)
    conn.close()
    raise SystemExit(0)
bound_matching = [body for body in matching if binding in body]
decision_markers = {
    match.group(1)
    for body in bound_matching
    for match in [re.match(r"^DECISION\(([^)]+)\):", body)]
    if match
}
if reason.startswith("REVIEW:"):
    required_markers = {"REVIEW"}
elif reason.startswith("FAN_OUT_READY:"):
    required_markers = {"FAN_OUT_READY"}
elif reason.startswith("APPROVAL:") and not question_ids:
    required_markers = {"APPROVAL"}
else:
    required_markers = {f"Q{question_id}" for question_id in question_ids}
if not required_markers:
    print(
        f"kanban-resolve-block: {task_id} has no typed question or gate to resolve",
        file=sys.stderr,
    )
    raise SystemExit(1)
missing = sorted(required_markers - decision_markers)
if missing:
    print(
        f"kanban-resolve-block: {task_id} is missing DECISION markers: {', '.join(missing)}",
        file=sys.stderr,
    )
    raise SystemExit(1)

original_recurrences = task["block_recurrences"]
original_kind = task["block_kind"]
if task["status"] == "blocked":
    result = subprocess.run(
        [hermes, "kanban", "unblock", "--reason", "decision recorded", task_id],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().replace("\n", " ")
        print(
            "kanban-resolve-block: unblock failed" + (f": {detail}" if detail else ""),
            file=sys.stderr,
        )
        raise SystemExit(1)

conn.execute("BEGIN IMMEDIATE")
latest_event = conn.execute(
    "SELECT id FROM task_events WHERE task_id = ? "
    "AND kind IN ('blocked', 'spawn_auto_blocked', 'block_loop_detected') "
    "ORDER BY id DESC LIMIT 1",
    (task_id,),
).fetchone()
current = conn.execute(
    "SELECT status, block_recurrences, block_kind FROM tasks WHERE id = ?",
    (task_id,),
).fetchone()
if (
    latest_event is None
    or latest_event["id"] != event["id"]
    or current["block_recurrences"] != original_recurrences
    or current["block_kind"] != original_kind
):
    conn.rollback()
    print(
        f"kanban-resolve-block: {task_id} changed while resolving; recurrence state preserved",
        file=sys.stderr,
    )
    raise SystemExit(1)
try:
    if task["status"] == "triage":
        updated = conn.execute(
            "UPDATE tasks SET status = 'todo', block_recurrences = 0, "
            "block_kind = NULL WHERE id = ? AND status = 'triage' "
            "AND block_recurrences IS ? AND block_kind IS ?",
            (task_id, original_recurrences, original_kind),
        )
    else:
        updated = conn.execute(
            "UPDATE tasks SET block_recurrences = 0, block_kind = NULL "
            "WHERE id = ? AND status NOT IN ('blocked', 'triage') "
            "AND block_recurrences IS ? AND block_kind IS ?",
            (task_id, original_recurrences, original_kind),
        )
    if updated.rowcount != 1:
        raise RuntimeError("task state changed before recurrence reset")
    conn.commit()
except Exception as exc:
    conn.rollback()
    print(f"kanban-resolve-block: {exc}", file=sys.stderr)
    raise SystemExit(1)
conn.close()
print(
    f"kanban block resolved: {task_id} decisions={len(bound_matching)} "
    f"recovered_from={task['status']}"
)
PY
