#!/bin/sh
# kanban-orphan-watchdog — surface silently-stuck kanban cards.
#
# Two blind spots exist by design (verified against hermes v0.18.x):
#   1. Cards created BY a worker (kanban_create from a dispatcher-spawned
#      run) get no kanban_notify_subs row — when such a card blocks,
#      nobody is notified and it sleeps forever.
#   2. The block-loop breaker (2nd same-kind block) routes a card to
#      `triage` with a `block_loop_detected` event, which is not a
#      notified event kind — silent even WITH a subscription.
#
# This watchdog scans the default board read-only every 30 min and
# reports both, once per new occurrence (dedup keyed on the newest
# relevant event id, state in ~/.hermes/.kanban-watchdog-state.json).
# stdout is delivered verbatim by the no_agent cron job (empty = silent),
# so it speaks ONLY when something needs a human/assistant look.
# It never mutates the board — triage/answering stays with the
# orchestration skill's BlockedTriage / Failures recipes.

set -u
exec /usr/bin/env python3 - <<'PY'
import json
import os
import sqlite3
import sys

HOME = os.path.expanduser("~")
DB = os.path.join(HOME, ".hermes", "kanban.db")
STATE = os.path.join(HOME, ".hermes", ".kanban-watchdog-state.json")

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

conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
conn.row_factory = sqlite3.Row

# 1. Blocked cards nobody is subscribed to.
orphans = conn.execute(
    """
    SELECT t.id, t.title, t.assignee,
           COALESCE(MAX(e.id), 0) AS ev,
           (SELECT e2.payload FROM task_events e2
             WHERE e2.task_id = t.id
               AND e2.kind IN ('blocked', 'spawn_auto_blocked', 'gave_up')
             ORDER BY e2.id DESC LIMIT 1) AS payload
      FROM tasks t
      LEFT JOIN kanban_notify_subs s ON s.task_id = t.id
      LEFT JOIN task_events e
             ON e.task_id = t.id
            AND e.kind IN ('blocked', 'spawn_auto_blocked', 'gave_up')
     WHERE t.status = 'blocked'
       AND s.task_id IS NULL
     GROUP BY t.id
    """
).fetchall()

# 2. Cards the block-loop breaker dropped into triage (silent transition).
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
conn.close()


def reason_of(row):
    try:
        return (json.loads(row["payload"] or "{}").get("reason") or "")[:80]
    except Exception:
        return ""


alerts = []
new_state = {}

for kind, rows, label in (
    ("orphan", orphans, "blocked, no subscription"),
    ("loopfall", loopfalls, "block-loop triage fall"),
):
    for row in rows:
        key = f"{kind}:{row['id']}"
        ev = int(row["ev"] or 0)
        new_state[key] = max(ev, seen(key))
        if ev <= seen(key):
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
    print("🚨 kanban watchdog: cards are stuck where no notification reaches")
    print("\n".join(alerts))
    print("→ kanban_show each, then apply the BlockedTriage / Failures recipe")

print(
    f"watchdog: {len(orphans)} orphaned blocked, {len(loopfalls)} loop-falls, "
    f"{len(alerts)} new alerts",
    file=sys.stderr,
)
PY
