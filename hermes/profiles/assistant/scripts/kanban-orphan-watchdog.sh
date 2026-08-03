#!/bin/sh
# kanban-orphan-watchdog — surface silently-stuck kanban cards.
#
# Seven blind spots exist by design (verified against hermes v0.18.x):
#   1. Assistant-registered hidden/manifest cards may intentionally have no
#      subscription while an internal gate owns their lifecycle.
#   2. Any card can fall through the block-loop breaker into triage without a
#      notification for that transition, even while a subscription still exists.
#   3. QA-protected production/Researcher cards deliberately remove their
#      chat subscription so candidate completion stays hidden. Their blocked
#      and failed terminal events therefore need this out-of-band route.
#   4. A failed QA setup can leave an internal card parked in scheduled with
#      no later release marker.
#   5. A completed QA card can lose its gateway wake before release.
#   6. A killed create-hidden wrapper can leave its deliberately unassigned,
#      blocked card before the QA_SETUP marker is written.
#   7. A FAN_OUT_READY notification can advance its subscription cursor before
#      the Assistant wake finishes. The block remains durable but emits no new
#      event, so it must be repeated until a matching decision exists.
#
# This watchdog scans the default board read-only every 5 min and
# reports them once per new occurrence (dedup keyed on the newest
# relevant event id, state in ~/.hermes/.kanban-watchdog-state.json).
# stdout is delivered verbatim by the no_agent cron job (empty = silent),
# so it speaks ONLY when something needs a human/assistant look.
# It never mutates the board — triage/answering stays with the
# orchestration skill's BlockedTriage / Failures recipes.

set -u
exec /usr/bin/python3 - <<'PY'
import json
import os
import sqlite3
import sys
from pathlib import Path

HOME = os.path.expanduser("~")


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


DB = str(kanban_db_path())
STATE = os.environ.get("HERMES_WATCHDOG_STATE") or os.path.join(
    HOME, ".hermes", ".kanban-watchdog-state.json"
)

if not os.path.exists(DB):
    sys.exit(0)

try:
    with open(STATE) as fh:
        raw = json.load(fh)
    state = {
        str(k): int(v) for k, v in raw.items()
    } if isinstance(raw, dict) else {}
except Exception:
    state = {}


def seen(key):
    try:
        return int(state.get(key, -1))
    except (TypeError, ValueError):
        return -1

conn = sqlite3.connect(DB)
conn.execute("PRAGMA query_only = ON")
conn.row_factory = sqlite3.Row

# 1. Blocked cards nobody is subscribed to.
orphans = conn.execute(
    """
    SELECT t.id, t.title, t.assignee,
           COALESCE(MAX(e.id), 0) AS ev,
           (SELECT e2.payload FROM task_events e2
             WHERE e2.task_id = t.id
                AND e2.kind IN ('blocked', 'spawn_auto_blocked')
             ORDER BY e2.id DESC LIMIT 1) AS payload
      FROM tasks t
      LEFT JOIN kanban_notify_subs s ON s.task_id = t.id
      LEFT JOIN task_events e
             ON e.task_id = t.id
             AND e.kind IN ('blocked', 'spawn_auto_blocked')
     WHERE t.status = 'blocked'
       AND s.task_id IS NULL
     GROUP BY t.id
    """
).fetchall()

# 2. Latest hidden terminal event is a failure rather than completion.
hidden_failures = conn.execute(
    """
    SELECT t.id, t.title, t.assignee, e.id AS ev, e.payload
      FROM tasks t
      JOIN task_events e
        ON e.id = (
             SELECT MAX(e2.id)
               FROM task_events e2
              WHERE e2.task_id = t.id
                AND e2.kind IN ('completed', 'gave_up', 'crashed', 'timed_out')
           )
      LEFT JOIN kanban_notify_subs s ON s.task_id = t.id
      WHERE s.task_id IS NULL
       AND e.kind IN ('gave_up', 'crashed', 'timed_out')
       AND t.status NOT IN ('ready', 'running', 'todo')
       AND t.status != 'archived'
    """
).fetchall()

# 3. Cards the block-loop breaker dropped into triage (silent transition).
loopfalls = conn.execute(
    """
    SELECT t.id, t.title, t.assignee, MAX(e.id) AS ev,
           (SELECT e2.payload FROM task_events e2
             WHERE e2.task_id = t.id AND e2.kind = 'block_loop_detected'
             ORDER BY e2.id DESC LIMIT 1) AS payload
      FROM tasks t
      JOIN task_events e
        ON e.task_id = t.id AND e.kind = 'block_loop_detected'
       WHERE t.status = 'triage'
       GROUP BY t.id
    """
).fetchall()

# 4. A create-hidden card that never reached its durable setup marker.
qa_setup_missing = conn.execute(
    """
    SELECT t.id, t.title, t.assignee, e.id AS ev, e.payload
      FROM tasks t
      JOIN task_events e
        ON e.id = (
             SELECT MIN(e2.id)
               FROM task_events e2
              WHERE e2.task_id = t.id
                AND e2.kind = 'created'
           )
     WHERE t.created_by = 'assistant:qa-gate'
       AND t.status IN ('blocked', 'todo', 'ready', 'scheduled')
       AND t.created_at <= CAST(strftime('%s', 'now') AS INTEGER) - 300
       AND NOT EXISTS (
             SELECT 1
               FROM task_comments c
              WHERE c.task_id = t.id
                AND c.body LIKE '%QA_SETUP%'
           )
    """
).fetchall()

# 5. A manual QA setup hold that has not been released.
stale_qa_setup = conn.execute(
    """
    SELECT t.id, t.title, t.assignee, c.id AS ev, c.body AS payload
      FROM tasks t
      JOIN task_comments c
        ON c.id = (
             SELECT MAX(c2.id)
               FROM task_comments c2
              WHERE c2.task_id = t.id
                AND c2.body LIKE '%QA_SETUP%'
           )
     WHERE t.status = 'scheduled'
       AND c.created_at <= CAST(strftime('%s', 'now') AS INTEGER) - 300
       AND NOT EXISTS (
             SELECT 1
               FROM task_comments c3
              WHERE c3.task_id = t.id
                AND c3.id > c.id
                 AND c3.author = 'assistant'
                 AND c3.body LIKE 'QA_RELEASE:%'
           )
    """
).fetchall()

# 6. QA finished but the handling wake was lost. Archived cards are excluded
#    by the status predicate.
completed_qa_unreleased = conn.execute(
    """
    SELECT t.id, t.title, t.assignee, e.id AS ev, e.payload
      FROM tasks t
      JOIN task_events e
        ON e.id = (
             SELECT MAX(e2.id)
               FROM task_events e2
              WHERE e2.task_id = t.id
                AND e2.kind = 'completed'
           )
     WHERE t.assignee = 'qa'
       AND t.status = 'done'
       AND t.completed_at <= CAST(strftime('%s', 'now') AS INTEGER) - 300
       AND NOT EXISTS (
             SELECT 1
               FROM task_comments c
              WHERE c.task_id = t.id
                 AND c.author = 'assistant'
                 AND c.body LIKE 'QA_HANDLED:%'
           )
    """
).fetchall()

# 7. FAN_OUT_READY is an acknowledged handoff. Repeat it regardless of
#    subscription while the task remains blocked. A DECISION(FAN_OUT_READY):
#    comment is not enough: the Assistant may stop before kanban_unblock.
#    Deterministic keys make partial-registration replay safe.
fanout_pending = conn.execute(
    """
    SELECT t.id, t.title, t.assignee, e.id AS ev, e.payload
      FROM tasks t
      JOIN task_events e
        ON e.id = (
             SELECT MAX(e2.id)
               FROM task_events e2
              WHERE e2.task_id = t.id
                AND e2.kind IN ('blocked', 'spawn_auto_blocked')
           )
     WHERE t.status = 'blocked'
       AND e.created_at <= CAST(strftime('%s', 'now') AS INTEGER) - 300
       AND e.payload LIKE '%FAN_OUT_READY%'
    """
).fetchall()
conn.close()


def reason_of(row):
    raw = row["payload"] or ""
    try:
        payload = json.loads(raw or "{}")
        return (
            payload.get("reason")
            or payload.get("error")
            or payload.get("outcome")
            or ""
        )[:80]
    except Exception:
        return str(raw)[:80]


alerts = []
new_state = {}

for kind, rows, label, repeat_until_handled in (
    ("orphan", orphans, "blocked, no subscription", False),
    ("hidden_failure", hidden_failures, "failed, no subscription", False),
    ("loopfall", loopfalls, "block-loop triage fall", False),
    ("qa_setup_missing", qa_setup_missing, "QA hidden-create missing setup", False),
    ("stale_qa_setup", stale_qa_setup, "stale QA setup hold", False),
    ("completed_qa_unreleased", completed_qa_unreleased,
     "QA finished but not handled", False),
    ("fanout_pending", fanout_pending,
     "FAN_OUT_READY awaiting Assistant decision", True),
):
    for row in rows:
        key = f"{kind}:{row['id']}"
        ev = int(row["ev"] or 0)
        new_state[key] = max(ev, seen(key))
        if not repeat_until_handled and ev <= seen(key):
            continue  # already alerted for this occurrence
        reason = reason_of(row)
        alerts.append(
            f"  - {row['id']} [{row['assignee'] or 'unassigned'}] "
            f"{(row['title'] or '')[:60]}"
            + (f" — {reason}" if reason else "")
            + f" ({label})"
        )

os.makedirs(os.path.dirname(STATE), exist_ok=True)
tmp = STATE + ".tmp"
with open(tmp, "w") as fh:
    json.dump(new_state, fh)
os.replace(tmp, STATE)

if alerts:
    print("🚨 kanban watchdog: cards need notification or QA recovery")
    print("\n".join(alerts))
    print("→ kanban_show each, then reconcile the QA release or apply the BlockedTriage / Failures recipe")

print(
    f"watchdog: {len(orphans)} orphaned blocked, "
    f"{len(hidden_failures)} hidden failures, {len(loopfalls)} loop-falls, "
    f"{len(qa_setup_missing)} QA setups missing, "
    f"{len(stale_qa_setup)} stale QA setup holds, "
    f"{len(completed_qa_unreleased)} completed QA unreleased, "
    f"{len(fanout_pending)} FAN_OUT_READY pending, "
    f"{len(alerts)} new alerts",
    file=sys.stderr,
)
PY
