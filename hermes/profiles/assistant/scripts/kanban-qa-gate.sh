#!/bin/sh
# kanban-qa-gate — harden the notification gate around a QA chain.

set -u

usage() {
    printf '%s\n' \
        "usage: $0 create-hidden <task-spec.json>" \
        "usage: $0 protect <internal-task-id>" \
        "       $0 release <qa-task-id> <internal-task-id>..." >&2
    exit 2
}

[ "$#" -ge 1 ] || usage
case $1 in
    create-hidden) [ "$#" -eq 2 ] || usage ;;
    protect) [ "$#" -eq 2 ] || usage ;;
    release) [ "$#" -ge 3 ] || usage ;;
    *) usage ;;
esac

HERMES=${HERMES_BIN:-}
if [ -z "$HERMES" ]; then
    HERMES=$(command -v hermes 2>/dev/null || :)
fi
if [ -z "$HERMES" ]; then
    HERMES="${HOME:-}/.local/bin/hermes"
fi
if [ ! -x "$HERMES" ]; then
    printf '%s\n' "kanban-qa-gate: hermes CLI not found" >&2
    exit 1
fi

exec /usr/bin/python3 - "$HERMES" "$@" <<'PY'
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path


HERMES = sys.argv[1]
OP = sys.argv[2]
ARGS = sys.argv[3:]


def run(*args):
    return subprocess.run(
        [HERMES, "kanban", *args],
        capture_output=True,
        text=True,
        timeout=120,
    )


def fail(message):
    print(f"kanban-qa-gate: {message}", file=sys.stderr)
    sys.exit(1)


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


def db_task(task_id):
    try:
        conn = sqlite3.connect(str(kanban_db_path()))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        conn.close()
    except sqlite3.Error as exc:
        fail(f"cannot inspect active board for {task_id}: {exc}")
    if row is None:
        fail(f"task not found in active board: {task_id}")
    return dict(row)


def expected_project(project):
    if not project:
        return None, None
    home = Path(os.environ.get("HERMES_HOME", "~/.hermes")).expanduser()
    project_db = home / "projects.db"
    if not project_db.is_file():
        return str(project), None
    try:
        conn = sqlite3.connect(str(project_db))
        row = conn.execute(
            "SELECT id, primary_path FROM projects WHERE id = ? OR slug = ? LIMIT 1",
            (str(project), str(project).lower()),
        ).fetchone()
        conn.close()
    except sqlite3.Error:
        return str(project), None
    return (str(row[0]), row[1]) if row else (str(project), None)


def expected_workspace(workspace):
    if workspace in (None, "", "scratch"):
        return "scratch", None
    if workspace == "worktree":
        return "worktree", None
    for prefix in ("dir:", "worktree:"):
        if str(workspace).startswith(prefix):
            path = os.path.expanduser(str(workspace)[len(prefix):].strip())
            return prefix[:-1], path
    fail(f"invalid workspace value: {workspace}")


def board_default_workdir():
    root = kanban_root()
    board = os.environ.get("HERMES_KANBAN_BOARD", "").strip()
    if not board:
        try:
            board = (root / "kanban" / "current").read_text().strip()
        except OSError:
            board = ""
    board = board or "default"
    metadata = root / "kanban" / "boards" / board / "board.json"
    try:
        value = json.loads(metadata.read_text()).get("default_workdir")
    except (OSError, AttributeError, json.JSONDecodeError):
        return None
    return os.path.expanduser(str(value)) if value else None


def cli_error(action, result):
    detail = (result.stderr or result.stdout).strip().replace("\n", " ")
    fail(f"{action} failed" + (f": {detail}" if detail else ""))


def show(task_id):
    result = run("show", "--json", task_id)
    if result.returncode != 0:
        cli_error(f"show {task_id}", result)
    try:
        detail = json.loads(result.stdout)
    except (TypeError, json.JSONDecodeError) as exc:
        fail(f"show {task_id} returned invalid JSON: {exc}")
    if not isinstance(detail, dict):
        fail(f"show {task_id} returned an invalid task")
    task = detail.get("task")
    if not isinstance(task, dict):
        task = detail
    comments = detail.get("comments")
    if not isinstance(comments, list):
        comments = task.get("comments", [])
    if not isinstance(comments, list):
        comments = []
    return task, comments, detail


def comment_body(comment):
    if not isinstance(comment, dict):
        return str(comment)
    return str(comment.get("body", comment.get("text", comment.get("comment", ""))))


def has_marker(comments, marker):
    return any(marker in comment_body(comment) for comment in comments)


def has_prefix(comments, marker):
    return any(comment_body(comment).startswith(marker) for comment in comments)


def subscriptions(task_id):
    result = run("notify-list", "--json", task_id)
    if result.returncode != 0:
        cli_error(f"notify-list {task_id}", result)
    try:
        data = json.loads(result.stdout or "[]")
    except (TypeError, json.JSONDecodeError) as exc:
        fail(f"notify-list {task_id} returned invalid JSON: {exc}")
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        fail(f"notify-list {task_id} returned an invalid subscription list")
    for key in ("subscriptions", "items", "results", "data", "rows"):
        value = data.get(key)
        if isinstance(value, list):
            return value
    if any(key in data for key in ("platform", "chat_id", "chatId")):
        return [data]
    return []


def value(row, *keys):
    for key in keys:
        if key in row and row[key] is not None:
            return row[key]
    return None


def is_chat_subscription(row):
    if not isinstance(row, dict):
        return False
    return (
        value(row, "platform") not in (None, "")
        and value(row, "chat_id", "chatId", "chat") not in (None, "")
    )


def unsubscribe_all(task_id, rows):
    for row in rows:
        if not isinstance(row, dict):
            fail(f"subscription list for {task_id} contains an invalid row")
        platform = value(row, "platform")
        chat_id = value(row, "chat_id", "chatId", "chat")
        thread_id = value(row, "thread_id", "threadId", "thread")
        if platform is None or chat_id is None:
            fail(f"subscription list for {task_id} contains an incomplete row")
        args = [
            "notify-unsubscribe", task_id,
            "--platform", str(platform),
            "--chat-id", str(chat_id),
        ]
        if thread_id not in (None, ""):
            args.extend(["--thread-id", str(thread_id)])
        result = run(*args)
        if result.returncode != 0:
            cli_error(f"unsubscribe {task_id}", result)


def protect(task_id):
    task, comments, _ = show(task_id)
    status = str(task.get("status", ""))
    setup = has_marker(comments, "QA_SETUP")
    started = task.get("started_at") not in (None, "")

    if status == "scheduled":
        if not setup:
            fail(f"{task_id} is scheduled without QA_SETUP")
        if started:
            fail(f"{task_id} has started_at set; refusing scheduled retry")
    elif status in ("blocked", "todo", "ready"):
        if started:
            fail(f"{task_id} has started_at set; refusing to schedule")
        if status == "ready" and task.get("assignee") not in (None, ""):
            fail(f"{task_id} is assigned+ready; refusing claim race")
        result = run("schedule", task_id, "QA_SETUP: notification gate")
        if result.returncode != 0:
            cli_error(f"schedule {task_id}", result)
    else:
        fail(f"{task_id} is {status or 'missing a status'}; refusing protection")

    rows = subscriptions(task_id)
    unsubscribe_all(task_id, rows)
    if subscriptions(task_id):
        fail(f"{task_id} still has subscriptions after unsubscribe")

    if not has_marker(comments, "QA_SETUP: protected candidate notifications"):
        result = run(
            "comment", task_id,
            "QA_SETUP: protected candidate notifications",
        )
        if result.returncode != 0:
            cli_error(f"comment {task_id}", result)
    print(f"qa gate: protected {task_id}")


def create_hidden(spec_path):
    try:
        with open(spec_path, encoding="utf-8") as handle:
            spec = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read hidden-task spec {spec_path}: {exc}")
    if not isinstance(spec, dict):
        fail("hidden-task spec must be a JSON object")

    allowed = {
        "title", "body", "assignee", "parents", "skills", "workspace",
        "idempotency_key", "max_runtime", "priority", "project", "tenant",
    }
    unknown = sorted(set(spec) - allowed)
    if unknown:
        fail(f"hidden-task spec has unknown keys: {', '.join(unknown)}")
    for required in ("title", "body", "assignee", "idempotency_key"):
        if not isinstance(spec.get(required), str) or not spec[required]:
            fail(f"hidden-task spec requires non-empty {required}")
    for field in ("parents", "skills"):
        values = spec.get(field, [])
        if not isinstance(values, list) or not all(
            isinstance(item, str) and item for item in values
        ):
            fail(f"hidden-task spec {field} must be a string list")
    for field in ("max_runtime", "priority"):
        if field in spec and type(spec[field]) is not int:
            fail(f"hidden-task spec {field} must be an integer")

    args = [
        "create", "--json", "--initial-status", "blocked",
        "--created-by", "assistant:qa-gate",
        "--body", spec["body"],
        "--idempotency-key", spec["idempotency_key"],
    ]
    if spec.get("workspace"):
        args.extend(["--workspace", str(spec["workspace"])])
    if spec.get("max_runtime") is not None:
        args.extend(["--max-runtime", str(spec["max_runtime"])])
    if spec.get("priority") is not None:
        args.extend(["--priority", str(spec["priority"])])
    if spec.get("project"):
        args.extend(["--project", str(spec["project"])])
    if spec.get("tenant"):
        args.extend(["--tenant", str(spec["tenant"])])
    for parent in spec.get("parents", []):
        args.extend(["--parent", str(parent)])
    for skill in spec.get("skills", []):
        args.extend(["--skill", str(skill)])
    args.append(spec["title"])

    result = run(*args)
    if result.returncode != 0:
        cli_error("create hidden task", result)
    try:
        created = json.loads(result.stdout)
    except (TypeError, json.JSONDecodeError) as exc:
        fail(f"create hidden task returned invalid JSON: {exc}")
    task_data = created.get("task", {}) if isinstance(created, dict) else {}
    task_id = (
        created.get("id") if isinstance(created, dict) else None
    ) or (
        created.get("task_id") if isinstance(created, dict) else None
    ) or (
        task_data.get("id") if isinstance(task_data, dict) else None
    )
    if not task_id:
        fail("create hidden task returned no task id")
    task_id = str(task_id)

    # The card is deliberately created unassigned. Even a process crash before
    # protection cannot dispatch it. Assignment happens only after the durable
    # QA_SETUP hold and zero-subscription check succeed.
    task, _, detail = show(task_id)
    stored = db_task(task_id)
    current_assignee = stored.get("assignee")
    if current_assignee not in (None, "", spec["assignee"]):
        fail(f"{task_id} idempotency collision has assignee {current_assignee}")
    if stored.get("created_by") != "assistant:qa-gate":
        fail(f"{task_id} was not created by assistant:qa-gate")
    if stored.get("title") != spec["title"] or stored.get("body") != spec["body"]:
        fail(f"{task_id} idempotency collision has different title/body")
    if stored.get("idempotency_key") != spec["idempotency_key"]:
        fail(f"{task_id} idempotency collision has a different key")
    actual_parents = set(parent_ids(task, detail))
    expected_parents = {str(parent) for parent in spec.get("parents", [])}
    if actual_parents != expected_parents:
        fail(f"{task_id} idempotency collision has different parents")
    actual_skill_values = stored.get("skills") or []
    if isinstance(actual_skill_values, str):
        try:
            actual_skill_values = json.loads(actual_skill_values)
        except json.JSONDecodeError:
            fail(f"{task_id} has unreadable skills")
    if not isinstance(actual_skill_values, list):
        fail(f"{task_id} has invalid skills")
    actual_skills = set(actual_skill_values)
    expected_skills = {str(skill) for skill in spec.get("skills", [])}
    if actual_skills != expected_skills:
        fail(f"{task_id} idempotency collision has different skills")
    project_id, project_primary = expected_project(spec.get("project"))
    expected_kind, expected_path = expected_workspace(spec.get("workspace", "scratch"))
    if project_id and project_primary and expected_kind == "scratch":
        expected_kind = "worktree"
        expected_path = os.path.join(str(project_primary), ".worktrees", task_id)
    elif (
        project_id
        and project_primary
        and expected_kind == "worktree"
        and expected_path is None
    ):
        expected_path = os.path.join(str(project_primary), ".worktrees", task_id)
    elif expected_kind in ("dir", "worktree") and expected_path is None:
        expected_path = board_default_workdir()
    if stored.get("workspace_kind") != expected_kind:
        fail(f"{task_id} idempotency collision has different workspace kind")
    actual_path = stored.get("workspace_path")
    if (actual_path is None) != (expected_path is None) or (
        actual_path is not None
        and expected_path is not None
        and os.path.normpath(str(actual_path)) != os.path.normpath(expected_path)
    ):
        fail(f"{task_id} idempotency collision has different workspace path")
    immutable_fields = {
        "max_runtime": ("max_runtime_seconds", spec.get("max_runtime")),
        "priority": ("priority", spec.get("priority", 0)),
        "project": ("project_id", project_id),
        "tenant": ("tenant", spec.get("tenant")),
    }
    for spec_field, (column, expected) in immutable_fields.items():
        if str(stored.get(column)) != str(expected):
            fail(f"{task_id} idempotency collision has different {spec_field}")

    protect(task_id)
    task, _, _ = show(task_id)
    current_assignee = task.get("assignee")
    if current_assignee != spec["assignee"]:
        result = run("assign", task_id, spec["assignee"])
        if result.returncode != 0:
            cli_error(f"assign {task_id}", result)
    try:
        os.unlink(spec_path)
    except OSError:
        pass
    print(f"qa gate: hidden task_id={task_id} assignee={spec['assignee']}")
    return task_id


def parent_ids(task, detail):
    raw = task.get("parents")
    if raw is None:
        raw = detail.get("parents")
    if raw is None:
        raw = task.get("parent_ids", detail.get("parent_ids", []))
    if not isinstance(raw, list):
        return []
    result = []
    for parent in raw:
        if isinstance(parent, dict):
            parent = value(parent, "id", "task_id", "taskId")
        if parent is not None:
            result.append(str(parent))
    return result


def release(qa_id, internal_ids):
    qa_task, qa_comments, qa_detail = show(qa_id)
    qa_status = str(qa_task.get("status", ""))
    if qa_task.get("assignee") != "qa":
        fail(f"{qa_id} is not assigned to qa")
    if qa_status != "todo":
        fail(f"{qa_id} is {qa_status or 'missing a status'}; expected todo")

    parents = set(parent_ids(qa_task, qa_detail))
    supplied = set(internal_ids)
    if supplied != parents:
        missing = sorted(parents - supplied)
        extra = sorted(supplied - parents)
        detail = []
        if missing:
            detail.append(f"missing {', '.join(missing)}")
        if extra:
            detail.append(f"not parents {', '.join(extra)}")
        fail(f"{qa_id} release parent set mismatch: {'; '.join(detail)}")
    if not any(is_chat_subscription(row) for row in subscriptions(qa_id)):
        fail(f"{qa_id} has no chat subscription")

    to_unblock = []
    for task_id in internal_ids:
        task, comments, _ = show(task_id)
        if not has_marker(comments, "QA_SETUP"):
            fail(f"{task_id} has no QA_SETUP comment")
        if subscriptions(task_id):
            fail(f"{task_id} still has subscriptions")
        if task.get("status") == "scheduled":
            to_unblock.append(task_id)
        elif not has_marker(comments, "QA_RELEASE:"):
            fail(f"{task_id} is neither scheduled nor previously QA_RELEASEd")

    if to_unblock:
        result = run(
            "unblock",
            "--reason", "QA_RELEASE: protected QA chain ready",
            *to_unblock,
        )
        if result.returncode != 0:
            cli_error("release protected QA chain", result)
    for task_id in internal_ids:
        _, comments, _ = show(task_id)
        if has_prefix(comments, "QA_RELEASE:"):
            continue
        result = run(
            "comment", task_id,
            "QA_RELEASE: protected QA chain ready",
        )
        if result.returncode != 0:
            cli_error(f"record release marker {task_id}", result)
    print(
        f"qa gate: released protected chain for {qa_id} "
        f"({len(to_unblock)} newly released, {len(internal_ids)} internal)"
    )


if OP == "create-hidden":
    create_hidden(ARGS[0])
elif OP == "protect":
    protect(ARGS[0])
else:
    release(ARGS[0], ARGS[1:])
PY
