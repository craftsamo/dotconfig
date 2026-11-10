#!/usr/bin/env python3
"""signal-history-import — one-off move of a Signal linked device and its history from the
``signal-access`` plugin's state to the ``signal-tools`` package's state.

The linked device (signal-cli's keys and attachments) and the message mirror are COPIED, never
moved: the old state directory stays untouched as the backup, so a failed or regretted cutover
costs nothing. The signal-cli data is copied as is; the mirror is rebuilt in signal-tools'
schema (user_version 2) from the old ``mirror.db``, with ``meta.account_uuid`` set to the linked
account's uuid so the new sync service accepts it.

Order of the cutover:

  1. stop and unload the old sync agent (``local.hermes.signal-access.sync``); this script
     refuses to run while it is loaded, because a live writer would tear the copy;
  2. run this script (``--dry-run`` first to see the planned row counts);
  3. install the new service, which finds the linked account and the mirror under
     ``<state_root>/<label>/``.

Run it only from the live checkout (``~/.config/hermes``), never from a task worktree, so a
candidate script cannot write live state; it refuses elsewhere. Once the new sync service has
received or sent anything, the old state is out of date: going back means relinking the device,
never starting the old agent on a stale copy beside the new service.

Runs on ``hermes-python``; standard library only. Exit status: 0 done, 1 failed after starting (the new label directory is
removed again), 2 refused before writing anything. It prints table counts and paths only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Mapping, Optional

PROG = "signal-history-import"
OLD_AGENT = "local.hermes.signal-access.sync"
LIVE_ROOT = Path.home() / ".config" / "hermes"
OLD_STATE = Path.home() / ".local" / "state" / "hermes-signal"
NEW_STATE_NAME = "signal-tools"
DEFAULT_LABEL = "default"
LABEL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9_]{0,22}[a-z0-9])?$")
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
USER_VERSION = 2
DIR_MODE = 0o700
DB_MODE = 0o600
CLI_DIR = "signal-cli"
OLD_DB = "mirror.db"
NEW_DB = "mirror.sqlite"
ACCOUNTS_FILE = Path("data") / "accounts.json"
META_ACCOUNT_KEY = "account_uuid"
OLD_META_UUID_KEY = "uuid"
OLD_SCHEMA = "old"

EXIT_FAILED = 1
EXIT_REFUSED = 2

# The signal-tools mirror schema, one statement per entry, exactly as SQLite stores it.
DDL = (
    """CREATE TABLE chats (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL CHECK (kind IN ('person','group')),
  name TEXT, number TEXT, members TEXT,
  member INTEGER NOT NULL DEFAULT 1 CHECK (member IN (0,1)),
  expires_in INTEGER, last_ts INTEGER,
  updated INTEGER NOT NULL)""",
    """CREATE TABLE messages (
  chat TEXT NOT NULL, author TEXT NOT NULL, ts INTEGER NOT NULL,
  from_me INTEGER NOT NULL DEFAULT 0 CHECK (from_me IN (0,1)),
  author_name TEXT,
  kind TEXT NOT NULL DEFAULT 'message' CHECK (kind IN ('message','timer')),
  body TEXT, attachments TEXT, quote TEXT,
  sticker INTEGER NOT NULL DEFAULT 0 CHECK (sticker IN (0,1)),
  other TEXT,
  expires_in INTEGER NOT NULL DEFAULT 0, expire_start INTEGER, read_at INTEGER,
  view_once INTEGER NOT NULL DEFAULT 0 CHECK (view_once IN (0,1)),
  edited INTEGER, received INTEGER NOT NULL, mentions TEXT,
  PRIMARY KEY (author, ts))""",
    "CREATE INDEX messages_chat ON messages (chat, ts)",
    "CREATE INDEX messages_edited ON messages (author, edited) WHERE edited IS NOT NULL",
    """CREATE TABLE edits (
  author TEXT NOT NULL, ts INTEGER NOT NULL, rev_ts INTEGER NOT NULL,
  body TEXT, attachments TEXT, mentions TEXT,
  PRIMARY KEY (author, ts, rev_ts))""",
    "CREATE INDEX edits_rev ON edits (author, rev_ts)",
    """CREATE TABLE reactions (
  author TEXT NOT NULL, ts INTEGER NOT NULL, reactor TEXT NOT NULL,
  emoji TEXT NOT NULL, at INTEGER NOT NULL,
  PRIMARY KEY (author, ts, reactor))""",
    """CREATE TABLE deleted (
  author TEXT NOT NULL, ts INTEGER NOT NULL, at INTEGER NOT NULL,
  PRIMARY KEY (author, ts))""",
    """CREATE TABLE contacts (
  uuid TEXT PRIMARY KEY, number TEXT, name TEXT, profile_name TEXT, username TEXT,
  blocked INTEGER NOT NULL DEFAULT 0 CHECK (blocked IN (0,1)),
  updated INTEGER NOT NULL)""",
    "CREATE INDEX contacts_number ON contacts (number) WHERE number IS NOT NULL",
    "CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)",
    "CREATE INDEX messages_ts ON messages (ts, author)",
)


@dataclass(frozen=True)
class TableSpec:
    """How one old table maps onto the new one.

    ``exprs`` replaces a column's plain copy with a SQL expression over the old row (``:now`` is
    the import time in ms); ``optional`` columns old mirrors may lack and are copied as NULL then;
    ``where`` keeps only some old rows; ``checks`` lists the allowed values of columns the new
    schema constrains, so a violating old row is counted and refused before anything is written."""

    name: str
    columns: tuple[str, ...]
    exprs: Mapping[str, str] = field(default_factory=dict)
    optional: frozenset[str] = frozenset()
    where: str = ""
    checks: Mapping[str, tuple] = field(default_factory=dict)


TABLES = (
    TableSpec(
        "chats",
        ("id", "kind", "name", "number", "members", "member", "expires_in", "last_ts", "updated"),
        exprs={"updated": "COALESCE(updated, last_ts, :now)"},
        checks={"kind": ("person", "group"), "member": (0, 1)},
    ),
    TableSpec(
        "messages",
        ("chat", "author", "ts", "from_me", "author_name", "kind", "body", "attachments", "quote",
         "sticker", "other", "expires_in", "expire_start", "read_at", "view_once", "edited",
         "received", "mentions"),
        exprs={"received": "COALESCE(received, ts)"},
        optional=frozenset({"mentions"}),
        checks={"from_me": (0, 1), "kind": ("message", "timer"), "sticker": (0, 1),
                "view_once": (0, 1)},
    ),
    TableSpec(
        "edits",
        ("author", "ts", "rev_ts", "body", "attachments", "mentions"),
        optional=frozenset({"mentions"}),
    ),
    TableSpec(
        "reactions",
        ("author", "ts", "reactor", "emoji", "at"),
        exprs={"at": "COALESCE(at, :now)"},
        where="emoji IS NOT NULL AND emoji <> ''",
    ),
    TableSpec(
        "contacts",
        ("uuid", "number", "name", "profile_name", "username", "blocked", "updated"),
        exprs={"updated": "COALESCE(updated, :now)"},
        checks={"blocked": (0, 1)},
    ),
)
REPORT_ORDER = ("chats", "messages", "edits", "reactions", "deleted", "contacts", "meta")


class Refusal(Exception):
    """Something is wrong before anything was written; the message carries no personal data."""


@dataclass(frozen=True)
class Plan:
    """What the import will write: rows per new table, and the old reactions it leaves out."""

    account_uuid: str
    counts: Mapping[str, int]
    skipped_reactions: int


# --- preconditions --------------------------------------------------------------------------

def in_live_checkout(script: Path, live_root: Path) -> bool:
    """Whether ``script`` runs from under ``live_root`` (real paths, links resolved)."""
    return Path(os.path.realpath(script)).is_relative_to(Path(os.path.realpath(live_root)))


def agent_is_loaded(label: str = OLD_AGENT) -> bool:
    """Whether launchd has the old sync agent loaded (``launchctl print`` exits 0)."""
    try:
        done = subprocess.run(["launchctl", "print", f"gui/{os.getuid()}/{label}"],
                              capture_output=True, check=False)
    except OSError:
        return False
    return done.returncode == 0


def resolve_state_root(explicit: Optional[str], environ: Mapping[str, str]) -> Path:
    """``--state-dir``, else ``$XDG_STATE_HOME/signal-tools``, else ``~/.local/state/signal-tools``."""
    if explicit:
        return Path(explicit).expanduser()
    base = environ.get("XDG_STATE_HOME")
    return (Path(base).expanduser() if base else Path.home() / ".local" / "state") / NEW_STATE_NAME


def read_account_uuid(source: Path) -> str:
    """The lowercase uuid of the one account in the old signal-cli data."""
    path = source / CLI_DIR / ACCOUNTS_FILE
    try:
        listing = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise Refusal(f"no linked account: {path} is missing") from None
    except (OSError, ValueError):
        raise Refusal(f"{path} is not readable JSON") from None
    accounts = listing.get("accounts") if isinstance(listing, dict) else None
    if not isinstance(accounts, list) or len(accounts) != 1 or not isinstance(accounts[0], dict):
        raise Refusal("accounts.json must hold exactly one account")
    uuid = accounts[0].get("uuid")
    uuid = uuid.lower() if isinstance(uuid, str) else ""
    if not UUID_RE.match(uuid):
        raise Refusal("the account in accounts.json has no valid uuid")
    return uuid


def _where(spec: TableSpec) -> str:
    return f" WHERE {spec.where}" if spec.where else ""


def _violation_condition(spec: TableSpec) -> tuple[str, list]:
    clauses, params = [], []
    for column, allowed in spec.checks.items():
        clauses.append(f"COALESCE({column} IN ({', '.join('?' * len(allowed))}), 0) = 0")
        params.extend(allowed)
    return " OR ".join(clauses), params


def plan_import(old_db: Path, account_uuid: str) -> Plan:
    """Count what would be written from the old mirror (opened read-only); refuse a mismatching
    ``meta.uuid`` or rows that the new schema's CHECKs would reject."""
    try:
        old = sqlite3.connect(f"{old_db.resolve().as_uri()}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        raise Refusal(f"cannot open the old mirror ({type(exc).__name__})") from None
    try:
        tables = {row[0] for row in old.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        missing = [spec.name for spec in TABLES if spec.name not in tables]
        if missing:
            raise Refusal(f"the old mirror lacks table(s): {', '.join(missing)}")
        if "meta" in tables:
            row = old.execute("SELECT value FROM meta WHERE key = ?", (OLD_META_UUID_KEY,)).fetchone()
            if row and row[0] is not None and str(row[0]).lower() != account_uuid:
                raise Refusal("the old mirror belongs to a different account than accounts.json")
        counts, violations = {}, []
        for spec in TABLES:
            counts[spec.name] = old.execute(f"SELECT COUNT(*) FROM {spec.name}{_where(spec)}").fetchone()[0]
            if spec.checks:
                condition, params = _violation_condition(spec)
                bad = old.execute(f"SELECT COUNT(*) FROM {spec.name} WHERE {condition}", params).fetchone()[0]
                if bad:
                    violations.append(f"{spec.name}={bad}")
        if violations:
            raise Refusal("rows the new schema would reject (table=count): " + ", ".join(violations))
        total_reactions = old.execute("SELECT COUNT(*) FROM reactions").fetchone()[0]
    except sqlite3.Error as exc:
        raise Refusal(f"cannot read the old mirror ({type(exc).__name__})") from None
    finally:
        old.close()
    counts["deleted"] = 0
    counts["meta"] = 1
    return Plan(account_uuid, counts, total_reactions - counts["reactions"])


# --- the copy -------------------------------------------------------------------------------

def copy_table(conn: sqlite3.Connection, spec: TableSpec, now: int) -> None:
    """Copy one table from the attached old mirror, applying the spec's defaults."""
    present = {row[1] for row in conn.execute(f"PRAGMA {OLD_SCHEMA}.table_info({spec.name})")}
    selects = [
        "NULL" if column in spec.optional and column not in present else spec.exprs.get(column, column)
        for column in spec.columns
    ]
    conn.execute(
        f"INSERT INTO main.{spec.name} ({', '.join(spec.columns)}) "
        f"SELECT {', '.join(selects)} FROM {OLD_SCHEMA}.{spec.name}{_where(spec)}",
        {"now": now},
    )


def copy_rows(conn: sqlite3.Connection, plan: Plan, now: int) -> None:
    """All rows in one transaction: the tables, then ``meta.account_uuid``."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        for spec in TABLES:
            copy_table(conn, spec, now)
        conn.execute("INSERT INTO main.meta (key, value) VALUES (?, ?)",
                     (META_ACCOUNT_KEY, plan.account_uuid))
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")


def verify(conn: sqlite3.Connection, plan: Plan) -> None:
    """The written mirror holds exactly the planned rows, and only ``account_uuid`` in meta."""
    for name in REPORT_ORDER:
        found = conn.execute(f"SELECT COUNT(*) FROM main.{name}").fetchone()[0]
        if found != plan.counts[name]:
            raise RuntimeError(f"count mismatch in {name}: planned {plan.counts[name]}, wrote {found}")
    meta = dict(conn.execute("SELECT key, value FROM main.meta").fetchall())
    if meta != {META_ACCOUNT_KEY: plan.account_uuid}:
        raise RuntimeError("meta does not hold exactly account_uuid")
    if conn.execute("PRAGMA user_version").fetchone()[0] != USER_VERSION:
        raise RuntimeError("user_version was not set")


def build_mirror(db_path: Path, old_db: Path, plan: Plan, now: int) -> None:
    """Create ``db_path`` (mode 0600 before any write), apply the schema, copy and verify."""
    os.close(os.open(db_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, DB_MODE))
    os.chmod(db_path, DB_MODE)
    conn = sqlite3.connect(db_path.resolve().as_uri(), uri=True, isolation_level=None)
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        for statement in DDL:
            conn.execute(statement)
        conn.execute(f"ATTACH DATABASE ? AS {OLD_SCHEMA}", (f"{old_db.resolve().as_uri()}?mode=ro",))
        copy_rows(conn, plan, now)
        conn.execute(f"PRAGMA user_version = {USER_VERSION}")
        verify(conn, plan)
        conn.execute("PRAGMA main.wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()


def exclude_from_backup(path: Path) -> None:
    """Best effort: keep the state out of Time Machine; a failure only warns."""
    try:
        done = subprocess.run(["tmutil", "addexclusion", str(path)], capture_output=True, check=False)
        failed = done.returncode != 0
    except OSError:
        failed = True
    if failed:
        print(f"{PROG}: warning: could not exclude {path} from Time Machine", file=sys.stderr)


def import_history(source: Path, state_root: Path, label: str, plan: Plan,
                   exclude_backup: Callable[[Path], None]) -> Path:
    """Write the new state; any failure after the label directory exists removes it again."""
    created_root = not state_root.exists()
    state_root.mkdir(mode=DIR_MODE, parents=True, exist_ok=True)
    if created_root:
        os.chmod(state_root, DIR_MODE)
    target = state_root / label
    os.mkdir(target, DIR_MODE)
    os.chmod(target, DIR_MODE)
    try:
        shutil.copytree(source / CLI_DIR, target / CLI_DIR, symlinks=True)
        build_mirror(target / NEW_DB, source / OLD_DB, plan, int(time.time() * 1000))
    except BaseException:
        shutil.rmtree(target, ignore_errors=True)
        raise
    exclude_backup(state_root)
    return target


# --- command line ---------------------------------------------------------------------------

def parse_args(argv: Optional[list[str]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog=PROG, description="Copy the signal-access state into signal-tools.")
    parser.add_argument("--from", dest="source", default=str(OLD_STATE),
                        help="old signal-access state directory (default: %(default)s)")
    parser.add_argument("--state-dir", help="signal-tools state root (default: $XDG_STATE_HOME/signal-tools "
                        "or ~/.local/state/signal-tools)")
    parser.add_argument("--label", default=DEFAULT_LABEL, help="account label (default: %(default)s)")
    parser.add_argument("--dry-run", action="store_true", help="print the plan, write nothing")
    return parser.parse_args(argv)


def report(plan: Plan, source: Path, target: Path, *, dry_run: bool) -> None:
    print(f"{PROG}: {'dry run, nothing written' if dry_run else 'imported'}")
    print(f"from: {source}")
    print(f"to:   {target}")
    for name in REPORT_ORDER:
        print(f"{name}: {plan.counts[name]}")
    print(f"reactions skipped (no emoji): {plan.skipped_reactions}")


def main(argv: Optional[list[str]] = None, *, live_root: Path = LIVE_ROOT,
         agent_loaded: Callable[[], bool] = agent_is_loaded,
         exclude_backup: Callable[[Path], None] = exclude_from_backup,
         environ: Mapping[str, str] = os.environ) -> int:
    args = parse_args(argv)
    source = Path(args.source).expanduser()
    state_root = resolve_state_root(args.state_dir, environ)
    try:
        if not in_live_checkout(Path(__file__), live_root):
            raise Refusal("run this from the live checkout (~/.config/hermes), never a task worktree")
        if not LABEL_RE.match(args.label):
            raise Refusal("the label must match ^[a-z0-9](?:[a-z0-9_]{0,22}[a-z0-9])?$")
        if agent_loaded():
            raise Refusal(f"the old sync agent {OLD_AGENT} is still loaded; stop it first")
        account_uuid = read_account_uuid(source)
        if not (source / OLD_DB).is_file():
            raise Refusal(f"{source / OLD_DB} is missing")
        target = state_root / args.label
        if os.path.lexists(target):
            raise Refusal(f"{target} already exists")
        plan = plan_import(source / OLD_DB, account_uuid)
    except Refusal as exc:
        print(f"{PROG}: refused: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    if args.dry_run:
        report(plan, source, target, dry_run=True)
        return 0
    try:
        import_history(source, state_root, args.label, plan, exclude_backup)
    except Exception as exc:  # the label directory is already gone
        print(f"{PROG}: failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_FAILED
    report(plan, source, target, dry_run=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
