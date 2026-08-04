#!/bin/sh
# kanban-orphan-watchdog — surface silently-stuck kanban cards.
#
# Six blind spots exist by design (verified against hermes v0.18.x):
#   1. Every card should have a notification subscription. A missing
#      subscription is an invariant violation that needs an out-of-band alert.
#   2. Any card can fall through the block-loop breaker into triage without a
#      notification for that transition, even while a subscription still exists.
#   3. A completed QA card can lose its gateway wake before handling.
#   4. A FAN_OUT_READY notification can advance its subscription cursor before
#      the Assistant wake finishes. The block remains durable but emits no new
#      event, so it must be repeated until a matching decision exists.
#   5. A QA-required producer completion can lose its wake before late-bound QA
#      materialization. Its terminal event remains durable after subscription
#      removal, so it must be repeated until an event-bound marker exists.
#   6. Any other successful completion can lose its Assistant wake after the
#      notifier advances its cursor and removes the subscription.
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
COMPLETION_CONTRACT_CUTOFF = int(
    os.environ.get("HERMES_COMPLETION_CONTRACT_CUTOFF", "1785801600")
)


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


def table_exists(name):
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
    ).fetchone() is not None

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
       AND COALESCE((
             SELECT MAX(e3.id) FROM task_events e3
              WHERE e3.task_id = t.id
                AND e3.kind IN ('gave_up', 'crashed', 'timed_out')
           ), 0) <= COALESCE((
             SELECT MAX(e4.id) FROM task_events e4
              WHERE e4.task_id = t.id
                AND e4.kind IN ('blocked', 'spawn_auto_blocked')
           ), 0)
     GROUP BY t.id
    """
).fetchall()

# 2. Latest terminal event is a failure and nobody is subscribed. Successful
#    completion is excluded because the notifier removes subscriptions after
#    normal delivery.
unsubscribed_failures = conn.execute(
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
       AND e.id > COALESCE((
             SELECT MAX(e3.id) FROM task_events e3
              WHERE e3.task_id = t.id
                AND e3.kind IN ('blocked', 'spawn_auto_blocked')
           ), 0)
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

# 4. QA finished but the handling wake was lost. Archived cards are excluded
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
                  AND c.author IN ('assistant', 'default')
                 AND c.body LIKE 'QA_HANDLED:%'
           )
    """
).fetchall()

# 5. FAN_OUT_READY is an acknowledged handoff. Repeat it regardless of
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

# 6. Push delivery can remove the terminal subscription before Assistant wake
#    injection fails. Reconcile the durable completion until QA materialization
#    is bound to that exact event. An active Researcher child is a legitimate
#    wait; a completed or failed one is not.
qa_candidates_unmaterialized = []
if table_exists("task_runs") and table_exists("task_links"):
    candidate_rows = conn.execute(
        """
        SELECT t.id, t.title, t.assignee, e.id AS ev, e.payload, r.metadata
          FROM tasks t
          JOIN task_events e
            ON e.id = (
                 SELECT MAX(e2.id)
                   FROM task_events e2
                  WHERE e2.task_id = t.id AND e2.kind = 'completed'
               )
          JOIN task_runs r
            ON r.id = (
                 SELECT MAX(r2.id)
                   FROM task_runs r2
                  WHERE r2.task_id = t.id AND r2.outcome = 'completed'
               )
         WHERE t.assignee IN ('creator', 'writer')
           AND t.status = 'done'
           AND t.completed_at <= CAST(strftime('%s', 'now') AS INTEGER) - 300
        """
    ).fetchall()
    materialization_comments = [
        row[0]
        for row in conn.execute(
            "SELECT body FROM task_comments WHERE author IN ('assistant', 'default') "
            "AND body LIKE 'QA_MATERIALIZED:%'"
        ).fetchall()
    ]
    invalid_recovery_comments = [
        row[0]
        for row in conn.execute(
            "SELECT body FROM task_comments "
            "WHERE author IN ('assistant', 'default') "
            "AND body LIKE 'COMPLETION_HANDLED:%' "
            "AND body LIKE '%outcome=invalid-recovery%'"
        ).fetchall()
    ]
    for row in candidate_rows:
        try:
            metadata = json.loads(row["metadata"] or "{}")
        except (TypeError, json.JSONDecodeError):
            continue
        handoff = metadata.get("artifact_handoff")
        qa = handoff.get("qa") if isinstance(handoff, dict) else None
        if not isinstance(qa, dict) or qa.get("status") != "required":
            continue
        producer_token = f"producer={row['id']}"
        task_token = f"task={row['id']}"
        event_token = f"completion_event={row['ev']}"
        if any(
            producer_token in body and event_token in body
            for body in materialization_comments
        ):
            continue
        if any(
            task_token in body and event_token in body
            for body in invalid_recovery_comments
        ):
            continue
        active_research = conn.execute(
            """
            SELECT 1
              FROM task_links l
              JOIN tasks child ON child.id = l.child_id
             WHERE l.parent_id = ?
               AND child.assignee = 'researcher'
               AND child.status IN ('todo', 'ready', 'running', 'blocked', 'triage', 'scheduled')
               AND NOT EXISTS (
                     SELECT 1
                       FROM task_events failure
                      WHERE child.status = 'blocked'
                        AND failure.task_id = child.id
                        AND failure.kind = 'gave_up'
                        AND failure.id > COALESCE((
                              SELECT MAX(blocked.id)
                                FROM task_events blocked
                               WHERE blocked.task_id = child.id
                                 AND blocked.kind IN ('blocked', 'spawn_auto_blocked')
                            ), 0)
                   )
             LIMIT 1
            """,
            (row["id"],),
        ).fetchone()
        if active_research is None:
            qa_candidates_unmaterialized.append(row)

# 7. Reconcile every other successful completion until the Assistant records
#    that admission and all immediate graph transitions finished for the exact
#    terminal event. QA and QA-required candidates use their stronger markers.
general_completions_unhandled = []
if table_exists("task_runs"):
    completed_rows = conn.execute(
        """
        SELECT t.id, t.title, t.assignee, e.id AS ev, e.payload, r.metadata
          FROM tasks t
          JOIN task_events e
            ON e.id = (
                 SELECT MAX(e2.id)
                   FROM task_events e2
                  WHERE e2.task_id = t.id AND e2.kind = 'completed'
               )
          JOIN task_runs r
            ON r.id = (
                 SELECT MAX(r2.id)
                   FROM task_runs r2
                  WHERE r2.task_id = t.id AND r2.outcome = 'completed'
               )
         WHERE t.assignee != 'qa'
           AND t.status = 'done'
           AND t.created_at >= ?
           AND t.completed_at <= CAST(strftime('%s', 'now') AS INTEGER) - 300
        """
        , (COMPLETION_CONTRACT_CUTOFF,)
    ).fetchall()
    handled_comments = [
        row[0]
        for row in conn.execute(
            "SELECT body FROM task_comments WHERE author IN ('assistant', 'default') "
            "AND body LIKE 'COMPLETION_HANDLED:%'"
        ).fetchall()
    ]
    for row in completed_rows:
        try:
            metadata = json.loads(row["metadata"] or "{}")
        except (TypeError, json.JSONDecodeError):
            metadata = {}
        handoff = metadata.get("artifact_handoff")
        qa = handoff.get("qa") if isinstance(handoff, dict) else None
        if isinstance(qa, dict) and qa.get("status") == "required":
            continue
        task_token = f"task={row['id']}"
        event_token = f"completion_event={row['ev']}"
        if any(
            task_token in body and event_token in body for body in handled_comments
        ):
            continue
        general_completions_unhandled.append(row)
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
    ("unsubscribed_failure", unsubscribed_failures,
     "terminal failure, no subscription", False),
    ("loopfall", loopfalls, "block-loop triage fall", False),
    ("completed_qa_unreleased", completed_qa_unreleased,
     "QA finished but not handled", False),
    ("fanout_pending", fanout_pending,
     "FAN_OUT_READY awaiting Assistant decision", True),
    ("qa_candidate_unmaterialized", qa_candidates_unmaterialized,
     "QA-required completion awaiting materialization", True),
    ("general_completion_unhandled", general_completions_unhandled,
     "completion awaiting Assistant handling", True),
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
    print("🚨 kanban watchdog: cards need orchestration recovery")
    print("\n".join(alerts))
    print("→ kanban_show each, then reconcile pending QA handling or apply the BlockedTriage / Failures recipe")

print(
    f"watchdog: {len(orphans)} orphaned blocked, "
    f"{len(unsubscribed_failures)} unsubscribed terminal failures, {len(loopfalls)} loop-falls, "
    f"{len(completed_qa_unreleased)} completed QA unreleased, "
    f"{len(fanout_pending)} FAN_OUT_READY pending, "
    f"{len(qa_candidates_unmaterialized)} QA candidates unmaterialized, "
    f"{len(alerts)} new alerts",
    file=sys.stderr,
)
PY
