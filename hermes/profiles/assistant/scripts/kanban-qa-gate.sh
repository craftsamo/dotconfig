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
import subprocess
import sys


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
    current_assignee = task.get("assignee")
    if current_assignee not in (None, "", spec["assignee"]):
        fail(f"{task_id} idempotency collision has assignee {current_assignee}")
    if task.get("created_by") != "assistant:qa-gate":
        fail(f"{task_id} was not created by assistant:qa-gate")
    if task.get("title") != spec["title"] or task.get("body") != spec["body"]:
        fail(f"{task_id} idempotency collision has different title/body")
    actual_parents = set(parent_ids(task, detail))
    expected_parents = {str(parent) for parent in spec.get("parents", [])}
    if actual_parents != expected_parents:
        fail(f"{task_id} idempotency collision has different parents")
    actual_skills = set(task.get("skills") or [])
    expected_skills = {str(skill) for skill in spec.get("skills", [])}
    if actual_skills != expected_skills:
        fail(f"{task_id} idempotency collision has different skills")

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
