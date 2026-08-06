#!/bin/sh
# kanban-scheduled-sweeper — release due `scheduled` kanban tasks.
#
# The `scheduled` status is a parking state with no built-in timer (no
# scheduled_at column as of hermes v0.18.x): something external must
# unblock the card. This sweeper is that something for TIME-deferred
# cards. Runs as an assistant-profile cron script (no_agent — zero LLM
# cost), every 15 min.
#
# Contract (see assistant-pipeline references/execute/scheduled.md):
#   - The assistant parks a card via
#       hermes kanban schedule <id> "until=<ISO8601> — <reason>"
#     which stores a `SCHEDULED: until=… — <reason>` comment.
#   - This sweeper unblocks cards whose NEWEST `SCHEDULED:` comment has an
#     `until=` at or before now (→ ready, or todo while parents are open;
#     chat subscriptions survive scheduling, so completion notifications
#     still reach the requester).
#   - A newest SCHEDULED: comment with NO `until=` is a manual hold — the
#     sweeper never touches it.
#   - It never unblocks `blocked` cards (that is the assistant's DECISION
#     round-trip; blind cron unblocks are exactly what the board's
#     block-loop breaker exists to stop).
#
# Sweeps the current/default board only (board resolution: env >
# ~/.hermes/kanban/current > default).

set -u

HERMES="$(command -v hermes || echo "$HOME/.local/bin/hermes")"
export HERMES_BIN="$HERMES"

exec /usr/bin/env python3 - <<'PY'
import json
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERMES = os.environ["HERMES_BIN"]
UNTIL_RE = re.compile(r"until=([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}(?::[0-9]{2})?(?:[+-][0-9]{2}:?[0-9]{2}|Z)?)")


def run(*args):
    return subprocess.run(
        [HERMES, "kanban", *args],
        capture_output=True, text=True, timeout=120,
    )


def parse_until(body):
    m = UNTIL_RE.search(body)
    if not m:
        return None
    raw = m.group(1).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def is_due(dt):
    now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
    return dt <= now


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


listing = run("list", "--status", "scheduled", "--json")
if listing.returncode != 0:
    print(f"sweeper: kanban list failed: {listing.stderr.strip()}", file=sys.stderr)
    sys.exit(0)  # transient board error — never mark the cron job failed

try:
    tasks = json.loads(listing.stdout or "[]")
except json.JSONDecodeError as exc:
    print(f"sweeper: bad list JSON: {exc}", file=sys.stderr)
    sys.exit(0)

released = held = 0
try:
    conn = sqlite3.connect(str(kanban_db_path()))
    conn.execute("PRAGMA query_only = ON")
except sqlite3.Error as exc:
    print(f"sweeper: cannot open active board: {exc}", file=sys.stderr)
    sys.exit(0)
for task in tasks:
    tid = task.get("id")
    if not tid:
        continue
    latest = conn.execute(
        "SELECT body FROM task_comments WHERE task_id = ? "
        "AND body LIKE 'SCHEDULED:%' ORDER BY id DESC LIMIT 1",
        (tid,),
    ).fetchone()
    if latest is None:
        held += 1
        continue  # parked without a SCHEDULED: comment — manual hold
    until = parse_until(str(latest[0] or ""))
    if until is None:
        held += 1
        continue  # newest SCHEDULED: has no parseable until= — manual hold
    if not is_due(until):
        held += 1
        continue
    unblock = run("unblock", "--reason", f"scheduled until={until.isoformat()} reached", tid)
    if unblock.returncode == 0:
        released += 1
        # stdout is delivered verbatim by the no_agent cron job (empty
        # stdout = silent) — speak ONLY when a card was actually released.
        title = task.get("title") or ""
        print(f"⏰ scheduled task released: {tid} {title}".rstrip())
    else:
        print(f"sweeper: unblock {tid} failed: {unblock.stderr.strip()}", file=sys.stderr)

conn.close()

print(f"sweeper: {len(tasks)} scheduled, {released} released, {held} held",
      file=sys.stderr)
PY
