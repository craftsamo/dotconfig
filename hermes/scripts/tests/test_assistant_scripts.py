from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import tempfile
import time
import unittest
from pathlib import Path


HERMES_ROOT = Path(__file__).resolve().parents[2]
ASSISTANT_SCRIPTS = HERMES_ROOT / "profiles" / "assistant" / "scripts"


class AssistantScriptTest(unittest.TestCase):
    def test_watchdog_repeats_unhandled_fan_out(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            board = root / "kanban" / "boards" / "named"
            board.mkdir(parents=True)
            db = board / "kanban.db"
            state = root / "watchdog.json"
            conn = sqlite3.connect(db)
            conn.executescript(
                """
                CREATE TABLE tasks (
                    id TEXT PRIMARY KEY, title TEXT, assignee TEXT, status TEXT,
                    created_by TEXT, created_at INTEGER, completed_at INTEGER
                );
                CREATE TABLE task_events (
                    id INTEGER PRIMARY KEY, task_id TEXT, kind TEXT,
                    payload TEXT, created_at INTEGER
                );
                CREATE TABLE kanban_notify_subs (task_id TEXT);
                CREATE TABLE task_comments (
                    id INTEGER PRIMARY KEY, task_id TEXT, body TEXT,
                    created_at INTEGER, author TEXT
                );
                """
            )
            now = int(time.time())
            conn.execute(
                "INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("fan-1", "fan out", "engineer", "blocked", "assistant", now - 900, None),
            )
            conn.execute(
                "INSERT INTO task_events VALUES (?, ?, ?, ?, ?)",
                (
                    1,
                    "fan-1",
                    "blocked",
                    json.dumps({"reason": "FAN_OUT_READY: needs search"}),
                    now - 600,
                ),
            )
            conn.execute("INSERT INTO kanban_notify_subs VALUES (?)", ("fan-1",))
            conn.commit()
            conn.close()

            env = {
                **os.environ,
                "HERMES_KANBAN_DB": str(db),
                "HERMES_WATCHDOG_STATE": str(state),
            }
            script = ASSISTANT_SCRIPTS / "kanban-orphan-watchdog.sh"
            first = subprocess.run(
                [str(script)], env=env, check=True, capture_output=True, text=True
            )
            second = subprocess.run(
                [str(script)], env=env, check=True, capture_output=True, text=True
            )

            self.assertIn("fan-1", first.stdout)
            self.assertIn("fan-1", second.stdout)

            conn = sqlite3.connect(db)
            conn.execute(
                "INSERT INTO task_comments VALUES (?, ?, ?, ?, ?)",
                (
                    1,
                    "fan-1",
                    "DECISION(FAN_OUT_READY): registered",
                    now - 300,
                    "assistant",
                ),
            )
            conn.commit()
            conn.close()
            decided_but_blocked = subprocess.run(
                [str(script)], env=env, check=True, capture_output=True, text=True
            )

            self.assertIn("fan-1", decided_but_blocked.stdout)

            conn = sqlite3.connect(db)
            conn.execute("UPDATE tasks SET status = 'ready' WHERE id = ?", ("fan-1",))
            conn.commit()
            conn.close()
            handled = subprocess.run(
                [str(script)], env=env, check=True, capture_output=True, text=True
            )

            self.assertNotIn("fan-1", handled.stdout)

    def test_watchdog_reports_subscribed_loopfall_and_scheduled_qa_gap(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            board = root / "kanban" / "boards" / "named"
            board.mkdir(parents=True)
            db = board / "kanban.db"
            state = root / "watchdog.json"
            now = int(time.time())
            conn = sqlite3.connect(db)
            conn.executescript(
                """
                CREATE TABLE tasks (
                    id TEXT PRIMARY KEY, title TEXT, assignee TEXT, status TEXT,
                    created_by TEXT, created_at INTEGER, completed_at INTEGER
                );
                CREATE TABLE task_events (
                    id INTEGER PRIMARY KEY, task_id TEXT, kind TEXT,
                    payload TEXT, created_at INTEGER
                );
                CREATE TABLE kanban_notify_subs (task_id TEXT);
                CREATE TABLE task_comments (
                    id INTEGER PRIMARY KEY, task_id TEXT, body TEXT,
                    created_at INTEGER, author TEXT
                );
                """
            )
            conn.executemany(
                "INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    ("loop-1", "loop", "engineer", "triage", "assistant", now - 900, None),
                    (
                        "qa-gap",
                        "hidden",
                        None,
                        "scheduled",
                        "assistant:qa-gate",
                        now - 900,
                        None,
                    ),
                ],
            )
            conn.executemany(
                "INSERT INTO task_events VALUES (?, ?, ?, ?, ?)",
                [
                    (1, "loop-1", "block_loop_detected", "{}", now - 600),
                    (2, "qa-gap", "created", "{}", now - 900),
                ],
            )
            conn.execute("INSERT INTO kanban_notify_subs VALUES (?)", ("loop-1",))
            conn.commit()
            conn.close()

            result = subprocess.run(
                [str(ASSISTANT_SCRIPTS / "kanban-orphan-watchdog.sh")],
                env={
                    **os.environ,
                    "HERMES_KANBAN_DB": "",
                    "HERMES_KANBAN_HOME": str(root),
                    "HERMES_KANBAN_BOARD": "named",
                    "HERMES_WATCHDOG_STATE": str(state),
                },
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertIn("loop-1", result.stdout)
            self.assertIn("qa-gap", result.stdout)

    def test_block_resolver_requires_decision_and_resets_counter(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            db = root / "kanban.db"
            fake = root / "hermes"
            fake.write_text(
                """#!/usr/bin/env python3
import os, sqlite3, sys
db = os.environ["HERMES_KANBAN_DB"]
task_id = sys.argv[-1]
conn = sqlite3.connect(db)
conn.execute("UPDATE tasks SET status = 'todo' WHERE id = ?", (task_id,))
conn.commit()
conn.close()
""",
                encoding="utf-8",
            )
            fake.chmod(0o755)
            conn = sqlite3.connect(db)
            conn.executescript(
                """
                CREATE TABLE tasks (
                    id TEXT PRIMARY KEY, status TEXT, block_recurrences INTEGER,
                    block_kind TEXT
                );
                CREATE TABLE task_events (
                    id INTEGER PRIMARY KEY, task_id TEXT, kind TEXT,
                    created_at INTEGER, payload TEXT
                );
                CREATE TABLE task_comments (
                    id INTEGER PRIMARY KEY, task_id TEXT, body TEXT,
                    created_at INTEGER, author TEXT
                );
                """
            )
            conn.execute(
                "INSERT INTO tasks VALUES (?, ?, ?, ?)",
                ("blocked-1", "blocked", 1, "needs_input"),
            )
            conn.execute(
                "INSERT INTO task_events VALUES (?, ?, ?, ?, ?)",
                (1, "blocked-1", "blocked", 100, json.dumps({"reason": "Q1/Q2"})),
            )
            conn.execute(
                "INSERT INTO task_comments VALUES (?, ?, ?, ?, ?)",
                (1, "blocked-1", "Q1: choose an option", 99, "engineer"),
            )
            conn.execute(
                "INSERT INTO task_comments VALUES (?, ?, ?, ?, ?)",
                (2, "blocked-1", "Q2: confirm scope", 99, "engineer"),
            )
            conn.commit()
            conn.close()
            env = {
                **os.environ,
                "HERMES_KANBAN_DB": str(db),
                "HERMES_BIN": str(fake),
            }
            script = ASSISTANT_SCRIPTS / "kanban-resolve-block.sh"
            inspected = subprocess.run(
                [str(script), "inspect", "blocked-1"],
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            binding = inspected.stdout.strip()
            self.assertIn("block_event=1", binding)
            self.assertIn("block_digest=", binding)

            missing = subprocess.run(
                [str(script), "apply", "blocked-1"],
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(1, missing.returncode)
            self.assertIn("missing DECISION markers: Q1, Q2", missing.stderr)

            conn = sqlite3.connect(db)
            conn.execute(
                "INSERT INTO task_comments VALUES (?, ?, ?, ?, ?)",
                (
                    3,
                    "blocked-1",
                    "DECISION(Q1): stale answer block_event=0 block_digest=stale",
                    100,
                    "assistant",
                ),
            )
            conn.commit()
            conn.close()
            stale = subprocess.run(
                [str(script), "apply", "blocked-1"],
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(1, stale.returncode)
            self.assertIn("missing DECISION markers: Q1, Q2", stale.stderr)

            conn = sqlite3.connect(db)
            conn.execute(
                "INSERT INTO task_comments VALUES (?, ?, ?, ?, ?)",
                (
                    4,
                    "blocked-1",
                    f"DECISION(Q1): use the recommended option {binding}",
                    100,
                    "assistant",
                ),
            )
            conn.commit()
            conn.close()
            partial = subprocess.run(
                [str(script), "apply", "blocked-1"],
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(1, partial.returncode)
            self.assertIn("missing DECISION markers: Q2", partial.stderr)

            conn = sqlite3.connect(db)
            conn.execute(
                "INSERT INTO task_comments VALUES (?, ?, ?, ?, ?)",
                (
                    5,
                    "blocked-1",
                    f"DECISION(Q2): keep the current scope {binding}",
                    100,
                    "default",
                ),
            )
            conn.commit()
            conn.close()
            resolved = subprocess.run(
                [str(script), "apply", "blocked-1"],
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertIn("kanban block resolved", resolved.stdout)
            conn = sqlite3.connect(db)
            task = conn.execute(
                "SELECT status, block_recurrences, block_kind FROM tasks WHERE id = ?",
                ("blocked-1",),
            ).fetchone()
            conn.close()
            self.assertEqual(("todo", 0, None), task)

    def test_block_resolver_preserves_a_new_block_generation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            db = root / "kanban.db"
            fake = root / "hermes"
            conn = sqlite3.connect(db)
            conn.executescript(
                """
                CREATE TABLE tasks (
                    id TEXT PRIMARY KEY, status TEXT, block_recurrences INTEGER,
                    block_kind TEXT
                );
                CREATE TABLE task_events (
                    id INTEGER PRIMARY KEY, task_id TEXT, kind TEXT,
                    created_at INTEGER, payload TEXT
                );
                CREATE TABLE task_comments (
                    id INTEGER PRIMARY KEY, task_id TEXT, body TEXT,
                    created_at INTEGER, author TEXT
                );
                """
            )
            conn.execute(
                "INSERT INTO tasks VALUES (?, ?, ?, ?)",
                ("race-1", "blocked", 1, "needs_input"),
            )
            conn.execute(
                "INSERT INTO task_events VALUES (?, ?, ?, ?, ?)",
                (1, "race-1", "blocked", 100, json.dumps({"reason": "Q1"})),
            )
            conn.execute(
                "INSERT INTO task_comments VALUES (?, ?, ?, ?, ?)",
                (1, "race-1", "Q1: choose", 99, "engineer"),
            )
            conn.commit()
            conn.close()
            fake.write_text(
                """#!/usr/bin/env python3
import json, os, sqlite3, sys
db = os.environ["HERMES_KANBAN_DB"]
task_id = sys.argv[-1]
conn = sqlite3.connect(db)
conn.execute("UPDATE tasks SET status='blocked', block_recurrences=2, block_kind='needs_input' WHERE id=?", (task_id,))
conn.execute("INSERT INTO task_events VALUES (2, ?, 'blocked', 101, ?)", (task_id, json.dumps({"reason": "Q1 newer"})))
conn.commit()
conn.close()
""",
                encoding="utf-8",
            )
            fake.chmod(0o755)
            env = {
                **os.environ,
                "HERMES_KANBAN_DB": str(db),
                "HERMES_BIN": str(fake),
            }
            script = ASSISTANT_SCRIPTS / "kanban-resolve-block.sh"
            inspected = subprocess.run(
                [str(script), "inspect", "race-1"],
                env=env,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            conn = sqlite3.connect(db)
            conn.execute(
                "INSERT INTO task_comments VALUES (?, ?, ?, ?, ?)",
                (2, "race-1", f"DECISION(Q1): choose {inspected}", 100, "assistant"),
            )
            conn.commit()
            conn.close()

            result = subprocess.run(
                [str(script), "apply", "race-1"],
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(1, result.returncode)
            self.assertIn("changed while resolving", result.stderr)
            conn = sqlite3.connect(db)
            task = conn.execute(
                "SELECT status, block_recurrences, block_kind FROM tasks WHERE id='race-1'"
            ).fetchone()
            conn.close()
            self.assertEqual(("blocked", 2, "needs_input"), task)

    def test_sweeper_uses_newest_scheduled_comment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = root / "hermes"
            calls = root / "calls.jsonl"
            db = root / "kanban.db"
            conn = sqlite3.connect(db)
            conn.execute(
                "CREATE TABLE task_comments (id INTEGER PRIMARY KEY, task_id TEXT, body TEXT)"
            )
            conn.executemany(
                "INSERT INTO task_comments VALUES (?, ?, ?)",
                [
                    (1, "scheduled-1", "SCHEDULED: until=2000-01-01T00:00 — old"),
                    (2, "scheduled-1", "SCHEDULED: manual hold"),
                ],
            )
            conn.commit()
            conn.close()
            fake.write_text(
                """#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
with open(os.environ["FAKE_CALLS"], "a", encoding="utf-8") as handle:
    handle.write(json.dumps(args) + "\\n")
if args[0:2] == ["kanban", "list"]:
    print(json.dumps([{"id": "scheduled-1", "title": "held"}]))
""",
                encoding="utf-8",
            )
            fake.chmod(0o755)
            result = subprocess.run(
                [str(ASSISTANT_SCRIPTS / "kanban-scheduled-sweeper.sh")],
                env={
                    **os.environ,
                    "PATH": f"{root}:{os.environ.get('PATH', '')}",
                    "FAKE_CALLS": str(calls),
                    "HERMES_KANBAN_DB": str(db),
                },
                check=True,
                capture_output=True,
                text=True,
            )

            invoked = [json.loads(line) for line in calls.read_text().splitlines()]
            self.assertEqual("", result.stdout)
            self.assertFalse(any(call[1:2] == ["unblock"] for call in invoked))

    def test_qa_gate_rejects_idempotency_collision_in_runtime_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = root / "hermes"
            spec = root / "spec.json"
            db = root / "kanban.db"
            conn = sqlite3.connect(db)
            conn.execute(
                """CREATE TABLE tasks (
                    id TEXT PRIMARY KEY, status TEXT, assignee TEXT, created_by TEXT,
                    title TEXT, body TEXT, idempotency_key TEXT, skills TEXT,
                    workspace_kind TEXT, workspace_path TEXT, max_runtime_seconds INTEGER,
                    priority INTEGER, project_id TEXT, tenant TEXT
                )"""
            )
            conn.execute(
                "INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "hidden-1",
                    "blocked",
                    None,
                    "assistant:qa-gate",
                    "Hidden",
                    "Mode: execute",
                    "hidden:key",
                    json.dumps(["creator-pipeline"]),
                    "dir",
                    "/wrong",
                    None,
                    0,
                    None,
                    None,
                ),
            )
            conn.commit()
            conn.close()
            fake.write_text(
                """#!/usr/bin/env python3
import json, sys
args = sys.argv[1:]
if args[0:2] == ["kanban", "create"]:
    print(json.dumps({"id": "hidden-1"}))
elif args[0:2] == ["kanban", "show"]:
    print(json.dumps({"task": {
        "id": "hidden-1", "status": "blocked", "assignee": None,
        "created_by": "assistant:qa-gate", "title": "Hidden", "body": "Mode: execute",
        "idempotency_key": "hidden:key", "parents": [],
        "skills": ["creator-pipeline"], "workspace_path": "/wrong"
    }, "comments": []}))
""",
                encoding="utf-8",
            )
            fake.chmod(0o755)
            spec.write_text(
                json.dumps(
                    {
                        "title": "Hidden",
                        "body": "Mode: execute",
                        "assignee": "creator",
                        "parents": [],
                        "skills": ["creator-pipeline"],
                        "idempotency_key": "hidden:key",
                    }
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    str(ASSISTANT_SCRIPTS / "kanban-qa-gate.sh"),
                    "create-hidden",
                    str(spec),
                ],
                env={
                    **os.environ,
                    "HERMES_BIN": str(fake),
                    "HERMES_KANBAN_DB": str(db),
                },
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(1, result.returncode)
            self.assertIn("different workspace", result.stderr)

            conn = sqlite3.connect(db)
            conn.execute(
                "UPDATE tasks SET workspace_kind='scratch', workspace_path=NULL, priority=5 "
                "WHERE id='hidden-1'"
            )
            conn.commit()
            conn.close()
            runtime_collision = subprocess.run(
                [
                    str(ASSISTANT_SCRIPTS / "kanban-qa-gate.sh"),
                    "create-hidden",
                    str(spec),
                ],
                env={
                    **os.environ,
                    "HERMES_BIN": str(fake),
                    "HERMES_KANBAN_DB": str(db),
                },
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(1, runtime_collision.returncode)
            self.assertIn("different priority", runtime_collision.stderr)

    def test_qa_gate_accepts_project_linked_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            hermes_home = root / "assistant-home"
            hermes_home.mkdir()
            projects = sqlite3.connect(hermes_home / "projects.db")
            projects.execute(
                "CREATE TABLE projects (id TEXT PRIMARY KEY, slug TEXT, primary_path TEXT)"
            )
            projects.execute(
                "INSERT INTO projects VALUES (?, ?, ?)",
                ("p_123", "proj", "/repo"),
            )
            projects.commit()
            projects.close()
            fake = root / "hermes"
            spec = root / "spec.json"
            db = root / "kanban.db"
            conn = sqlite3.connect(db)
            conn.execute(
                """CREATE TABLE tasks (
                    id TEXT PRIMARY KEY, status TEXT, assignee TEXT, created_by TEXT,
                    title TEXT, body TEXT, idempotency_key TEXT, skills TEXT,
                    workspace_kind TEXT, workspace_path TEXT, max_runtime_seconds INTEGER,
                    priority INTEGER, project_id TEXT, tenant TEXT
                )"""
            )
            conn.execute(
                "INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "hidden-1",
                    "scheduled",
                    "creator",
                    "assistant:qa-gate",
                    "Hidden",
                    "Mode: execute",
                    "hidden:key",
                    json.dumps(["creator-pipeline"]),
                    "worktree",
                    "/repo/.worktrees/hidden-1",
                    900,
                    3,
                    "p_123",
                    None,
                ),
            )
            conn.commit()
            conn.close()
            fake.write_text(
                """#!/usr/bin/env python3
import json, sys
args = sys.argv[1:]
if args[0:2] == ["kanban", "create"]:
    print(json.dumps({"id": "hidden-1"}))
elif args[0:2] == ["kanban", "show"]:
    print(json.dumps({"task": {
        "id": "hidden-1", "status": "scheduled", "assignee": "creator",
        "started_at": None, "parents": []
    }, "comments": [{"body": "QA_SETUP: protected candidate notifications"}]}))
elif args[0:2] == ["kanban", "notify-list"]:
    print("[]")
""",
                encoding="utf-8",
            )
            fake.chmod(0o755)
            spec.write_text(
                json.dumps(
                    {
                        "title": "Hidden",
                        "body": "Mode: execute",
                        "assignee": "creator",
                        "parents": [],
                        "skills": ["creator-pipeline"],
                        "project": "proj",
                        "max_runtime": 900,
                        "priority": 3,
                        "idempotency_key": "hidden:key",
                    }
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    str(ASSISTANT_SCRIPTS / "kanban-qa-gate.sh"),
                    "create-hidden",
                    str(spec),
                ],
                env={
                    **os.environ,
                    "HERMES_BIN": str(fake),
                    "HERMES_KANBAN_DB": str(db),
                    "HERMES_HOME": str(hermes_home),
                },
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertIn("hidden task_id=hidden-1", result.stdout)
            self.assertFalse(spec.exists())

    def test_completion_probe_resolves_named_board(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            board = root / "kanban" / "boards" / "named"
            board.mkdir(parents=True)
            db = board / "kanban.db"
            conn = sqlite3.connect(db)
            conn.executescript(
                """
                CREATE TABLE tasks (
                    id TEXT PRIMARY KEY, assignee TEXT, body TEXT, status TEXT,
                    skills TEXT
                );
                CREATE TABLE task_runs (
                    id INTEGER PRIMARY KEY, task_id TEXT, outcome TEXT,
                    started_at INTEGER, summary TEXT, metadata TEXT
                );
                CREATE TABLE task_attachments (
                    id INTEGER PRIMARY KEY, task_id TEXT, filename TEXT,
                    stored_path TEXT, created_at INTEGER
                );
                CREATE TABLE task_links (parent_id TEXT, child_id TEXT);
                """
            )
            summary = "Retrieved one source."
            metadata = {
                "completion": {
                    "status": "completed",
                    "summary": summary,
                    "metadata": {"mode": "retrieve"},
                }
            }
            conn.execute(
                "INSERT INTO tasks VALUES (?, ?, ?, ?, ?)",
                (
                    "named-1",
                    "searcher",
                    "Mode: retrieve\nInput attachments: []",
                    "done",
                    json.dumps(["searcher-pipeline"]),
                ),
            )
            conn.execute(
                "INSERT INTO task_runs VALUES (?, ?, ?, ?, ?, ?)",
                (1, "named-1", "completed", 1, summary, json.dumps(metadata)),
            )
            conn.commit()
            conn.close()

            result = subprocess.run(
                [str(ASSISTANT_SCRIPTS / "kanban-completion-probe.sh"), "named-1"],
                env={
                    **os.environ,
                    "HERMES_KANBAN_HOME": str(root),
                    "HERMES_KANBAN_BOARD": "named",
                    "HERMES_KANBAN_DB": "",
                },
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertTrue(json.loads(result.stdout)["valid"])

    def test_task_probe_includes_runtime_registration_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            board = root / "kanban" / "boards" / "named"
            board.mkdir(parents=True)
            db = board / "kanban.db"
            conn = sqlite3.connect(db)
            conn.executescript(
                """
                CREATE TABLE tasks (
                    id TEXT PRIMARY KEY, idempotency_key TEXT, title TEXT,
                    body TEXT, assignee TEXT, status TEXT, priority INTEGER,
                    workspace_kind TEXT, workspace_path TEXT, tenant TEXT,
                    branch_name TEXT, project_id TEXT, workflow_template_id TEXT,
                    max_runtime_seconds INTEGER, max_retries INTEGER,
                    goal_mode INTEGER, goal_max_turns INTEGER, skills TEXT,
                    model_override TEXT, provider_override TEXT, session_id TEXT
                );
                CREATE TABLE task_links (parent_id TEXT, child_id TEXT);
                CREATE TABLE task_events (
                    id INTEGER PRIMARY KEY, task_id TEXT, kind TEXT, payload TEXT
                );
                """
            )
            body = "Goal: verify"
            conn.execute(
                "INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    "task-1",
                    "run:key",
                    "Verify",
                    body,
                    "searcher",
                    "todo",
                    7,
                    "scratch",
                    None,
                    "tenant-a",
                    None,
                    "project-a",
                    None,
                    900,
                    2,
                    1,
                    8,
                    json.dumps(["searcher-pipeline"]),
                    "model-a",
                    "provider-a",
                    "session-a",
                ),
            )
            conn.execute("INSERT INTO task_links VALUES (?, ?)", ("parent-1", "task-1"))
            conn.execute(
                "INSERT INTO task_events VALUES (?, ?, ?, ?)",
                (1, "task-1", "created", json.dumps({"initial_status": "todo"})),
            )
            conn.commit()
            conn.close()

            script = ASSISTANT_SCRIPTS / "kanban-task-spec-probe.sh"
            result = subprocess.run(
                [str(script), "task-1"],
                env={
                    **os.environ,
                    "HERMES_KANBAN_DB": "",
                    "HERMES_KANBAN_HOME": str(root),
                    "HERMES_KANBAN_BOARD": "named",
                },
                check=True,
                capture_output=True,
                text=True,
            )
            data = json.loads(result.stdout)

            self.assertEqual(900, data["max_runtime_seconds"])
            self.assertEqual(8, data["goal_max_turns"])
            self.assertEqual(["searcher-pipeline"], data["skills"])
            self.assertEqual(["parent-1"], data["parents"])
            self.assertEqual(
                hashlib.sha256(body.encode()).hexdigest(), data["body_sha256"]
            )

    def test_completion_probe_accepts_canonical_envelope(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "kanban.db"
            conn = sqlite3.connect(db)
            conn.executescript(
                """
                CREATE TABLE tasks (
                    id TEXT PRIMARY KEY, assignee TEXT, body TEXT, status TEXT, skills TEXT
                );
                CREATE TABLE task_runs (
                    id INTEGER PRIMARY KEY, task_id TEXT, outcome TEXT,
                    started_at INTEGER, summary TEXT, metadata TEXT
                );
                CREATE TABLE task_attachments (
                    id INTEGER PRIMARY KEY, task_id TEXT, filename TEXT,
                    stored_path TEXT, created_at INTEGER
                );
                CREATE TABLE task_links (parent_id TEXT, child_id TEXT);
                """
            )
            summary = "Retrieved three sources."
            metadata = {
                "completion": {
                    "status": "completed",
                    "summary": summary,
                    "metadata": {
                        "mode": "lookup",
                        "sources": 3,
                        "coverage": "targeted",
                        "open_gaps": [],
                    },
                }
            }
            conn.execute(
                "INSERT INTO tasks VALUES (?, ?, ?, ?, ?)",
                (
                    "task-1",
                    "searcher",
                    "Mode: retrieve\nInput attachments: []",
                    "done",
                    json.dumps(["searcher-pipeline"]),
                ),
            )
            conn.execute(
                "INSERT INTO task_runs VALUES (?, ?, ?, ?, ?, ?)",
                (1, "task-1", "completed", 100, summary, json.dumps(metadata)),
            )
            conn.commit()
            conn.close()

            script = ASSISTANT_SCRIPTS / "kanban-completion-probe.sh"
            result = subprocess.run(
                [str(script), "task-1"],
                env={**os.environ, "HERMES_KANBAN_DB": str(db)},
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertTrue(json.loads(result.stdout)["valid"])

            metadata["artifact_handoff"] = {
                "artifacts": [],
                "verification": [],
                "qa": None,
            }
            conn = sqlite3.connect(db)
            conn.execute(
                "UPDATE task_runs SET metadata = ? WHERE id = ?",
                (json.dumps(metadata), 1),
            )
            conn.commit()
            conn.close()
            empty_handoff = subprocess.run(
                [str(script), "task-1"],
                env={**os.environ, "HERMES_KANBAN_DB": str(db)},
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(1, empty_handoff.returncode)
            self.assertIn(
                "metadata.artifact_handoff must be absent without current outputs",
                json.loads(empty_handoff.stdout)["errors"],
            )

    def test_completion_probe_rejects_missing_artifact_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "kanban.db"
            conn = sqlite3.connect(db)
            conn.executescript(
                """
                CREATE TABLE tasks (
                    id TEXT PRIMARY KEY, assignee TEXT, body TEXT, status TEXT, skills TEXT
                );
                CREATE TABLE task_runs (
                    id INTEGER PRIMARY KEY, task_id TEXT, outcome TEXT,
                    started_at INTEGER, summary TEXT, metadata TEXT
                );
                CREATE TABLE task_attachments (
                    id INTEGER PRIMARY KEY, task_id TEXT, filename TEXT,
                    stored_path TEXT, created_at INTEGER
                );
                CREATE TABLE task_links (parent_id TEXT, child_id TEXT);
                """
            )
            summary = "Created the final image."
            artifact = Path(directory) / "final.png"
            artifact.write_bytes(b"image")
            metadata = {
                "completion": {
                    "status": "completed",
                    "summary": summary,
                    "metadata": {"mode": "execute"},
                    "artifacts": ["final.png"],
                }
            }
            conn.execute(
                "INSERT INTO tasks VALUES (?, ?, ?, ?, ?)",
                (
                    "task-2",
                    "creator",
                    "Mode: execute\nInput attachments: []",
                    "done",
                    json.dumps(["creator-pipeline"]),
                ),
            )
            conn.execute(
                "INSERT INTO task_runs VALUES (?, ?, ?, ?, ?, ?)",
                (2, "task-2", "completed", 100, summary, json.dumps(metadata)),
            )
            conn.execute(
                "INSERT INTO task_attachments VALUES (?, ?, ?, ?, ?)",
                (1, "task-2", "final.png", str(artifact), 50),
            )
            conn.commit()
            conn.close()

            script = ASSISTANT_SCRIPTS / "kanban-completion-probe.sh"
            result = subprocess.run(
                [str(script), "task-2"],
                env={**os.environ, "HERMES_KANBAN_DB": str(db)},
                check=False,
                capture_output=True,
                text=True,
            )
            data = json.loads(result.stdout)

            self.assertEqual(1, result.returncode)
            self.assertFalse(data["valid"])
            self.assertIn(
                "metadata.artifact_handoff is required for attached artifacts",
                data["errors"],
            )

    def test_completion_probe_excludes_declared_input_attachment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "kanban.db"
            conn = sqlite3.connect(db)
            conn.executescript(
                """
                CREATE TABLE tasks (
                    id TEXT PRIMARY KEY, assignee TEXT, body TEXT, status TEXT, skills TEXT
                );
                CREATE TABLE task_runs (
                    id INTEGER PRIMARY KEY, task_id TEXT, outcome TEXT,
                    started_at INTEGER, summary TEXT, metadata TEXT
                );
                CREATE TABLE task_attachments (
                    id INTEGER PRIMARY KEY, task_id TEXT, filename TEXT,
                    stored_path TEXT, created_at INTEGER
                );
                CREATE TABLE task_links (parent_id TEXT, child_id TEXT);
                """
            )
            summary = "Prepared the specialist plan."
            graph = Path(directory) / "planning-graph.yaml"
            graph.write_text("branches: []\n", encoding="utf-8")
            graph_digest = hashlib.sha256(graph.read_bytes()).hexdigest()
            metadata = {
                "completion": {
                    "status": "completed",
                    "summary": summary,
                    "metadata": {"mode": "plan"},
                },
                "specialist_plan": {
                    "origin_task_id": "task-3",
                    "branch_key": "creator-plan",
                    "summary": "Use one image production card.",
                    "proposed_cards": [],
                },
            }
            body = "\n".join(
                [
                    "Mode: plan",
                    "Planning branch: creator-plan",
                    "Input attachments: "
                    + json.dumps(
                        [
                            {
                                "name": "planning-graph.yaml",
                                "sha256": graph_digest,
                                "purpose": "approved planning evidence",
                                "source_task_id": "origin-1",
                            }
                        ],
                        separators=(",", ":"),
                    ),
                ]
            )
            conn.execute(
                "INSERT INTO tasks VALUES (?, ?, ?, ?, ?)",
                ("origin-1", "engineer", "Mode: execute", "done", json.dumps(["engineer-pipeline"])),
            )
            conn.execute(
                "INSERT INTO tasks VALUES (?, ?, ?, ?, ?)",
                ("task-3", "creator", body, "done", json.dumps(["creator-pipeline"])),
            )
            conn.execute(
                "INSERT INTO task_runs VALUES (?, ?, ?, ?, ?, ?)",
                (3, "task-3", "completed", 100, summary, json.dumps(metadata)),
            )
            conn.execute(
                "INSERT INTO task_attachments VALUES (?, ?, ?, ?, ?)",
                (2, "origin-1", "planning-graph.yaml", str(graph), 110),
            )
            conn.execute("INSERT INTO task_links VALUES (?, ?)", ("origin-1", "task-3"))
            conn.commit()
            conn.close()

            script = ASSISTANT_SCRIPTS / "kanban-completion-probe.sh"
            result = subprocess.run(
                [str(script), "task-3"],
                env={**os.environ, "HERMES_KANBAN_DB": str(db)},
                check=True,
                capture_output=True,
                text=True,
            )
            data = json.loads(result.stdout)

            self.assertEqual("planning-graph.yaml", data["input_attachments"][0]["name"])
            self.assertEqual([], data["output_attachments"])

            metadata["specialist_plan"] = {}
            conn = sqlite3.connect(db)
            conn.execute(
                "UPDATE task_runs SET metadata = ? WHERE id = ?",
                (json.dumps(metadata), 3),
            )
            conn.commit()
            conn.close()
            malformed = subprocess.run(
                [str(script), "task-3"],
                env={**os.environ, "HERMES_KANBAN_DB": str(db)},
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(1, malformed.returncode)
            self.assertIn(
                "metadata.specialist_plan.origin_task_id is required",
                json.loads(malformed.stdout)["errors"],
            )

    def test_completion_probe_rejects_nonexistent_declared_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "kanban.db"
            conn = sqlite3.connect(db)
            conn.executescript(
                """
                CREATE TABLE tasks (
                    id TEXT PRIMARY KEY, assignee TEXT, body TEXT, status TEXT, skills TEXT
                );
                CREATE TABLE task_runs (
                    id INTEGER PRIMARY KEY, task_id TEXT, outcome TEXT,
                    started_at INTEGER, summary TEXT, metadata TEXT
                );
                CREATE TABLE task_attachments (
                    id INTEGER PRIMARY KEY, task_id TEXT, filename TEXT,
                    stored_path TEXT, created_at INTEGER
                );
                CREATE TABLE task_links (parent_id TEXT, child_id TEXT);
                """
            )
            summary = "Claimed an output that does not exist."
            metadata = {
                "completion": {
                    "status": "completed",
                    "summary": summary,
                    "metadata": {"mode": "execute"},
                    "artifacts": ["missing.png"],
                },
                "artifact_handoff": {
                    "artifacts": [
                        {
                            "name": "missing.png",
                            "sha256": "0" * 64,
                            "purpose": "final image",
                            "source_task_id": "task-4",
                        }
                    ],
                    "verification": ["claimed"],
                    "qa": {
                        "status": "required",
                        "capability": "creator-generated-image",
                        "routes": ["qa-raster-image"],
                    },
                },
            }
            conn.execute(
                "INSERT INTO tasks VALUES (?, ?, ?, ?, ?)",
                (
                    "task-4",
                    "creator",
                    "Mode: execute\nInput attachments: []",
                    "done",
                    json.dumps(["creator-pipeline"]),
                ),
            )
            conn.execute(
                "INSERT INTO task_runs VALUES (?, ?, ?, ?, ?, ?)",
                (4, "task-4", "completed", 100, summary, json.dumps(metadata)),
            )
            conn.commit()
            conn.close()

            script = ASSISTANT_SCRIPTS / "kanban-completion-probe.sh"
            result = subprocess.run(
                [str(script), "task-4"],
                env={**os.environ, "HERMES_KANBAN_DB": str(db)},
                check=False,
                capture_output=True,
                text=True,
            )
            data = json.loads(result.stdout)

            self.assertEqual(1, result.returncode)
            self.assertTrue(
                any("declares nonexistent artifact" in error for error in data["errors"])
            )

    def test_completion_probe_accepts_only_current_review_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            db = root / "kanban.db"
            old = root / "draft-v1.md"
            current = root / "draft-v2.md"
            old.write_text("old", encoding="utf-8")
            current.write_text("current", encoding="utf-8")
            digest = hashlib.sha256(current.read_bytes()).hexdigest()
            summary = "Approved the current draft."
            metadata = {
                "completion": {
                    "status": "completed",
                    "summary": summary,
                    "metadata": {"mode": "execute"},
                    "artifacts": ["draft-v2.md"],
                },
                "artifact_handoff": {
                    "artifacts": [
                        {
                            "name": "draft-v2.md",
                            "sha256": "pending-assistant-probe",
                            "purpose": "current approved draft",
                            "source_task_id": "writer-1",
                        }
                    ],
                    "verification": ["review approved"],
                    "qa": {
                        "status": "required",
                        "capability": "writer:documentation",
                        "routes": ["qa-prose"],
                    },
                },
            }
            conn = sqlite3.connect(db)
            conn.executescript(
                """
                CREATE TABLE tasks (id TEXT PRIMARY KEY, assignee TEXT, body TEXT, status TEXT, skills TEXT);
                CREATE TABLE task_runs (id INTEGER PRIMARY KEY, task_id TEXT, outcome TEXT,
                    started_at INTEGER, summary TEXT, metadata TEXT);
                CREATE TABLE task_attachments (id INTEGER PRIMARY KEY, task_id TEXT,
                    filename TEXT, stored_path TEXT, created_at INTEGER);
                CREATE TABLE task_links (parent_id TEXT, child_id TEXT);
                """
            )
            conn.execute(
                "INSERT INTO tasks VALUES (?, ?, ?, ?, ?)",
                ("writer-1", "writer", "Mode: execute\nInput attachments: []", "done", json.dumps(["writer-pipeline"])),
            )
            conn.execute(
                "INSERT INTO task_runs VALUES (?, ?, ?, ?, ?, ?)",
                (1, "writer-1", "completed", 200, summary, json.dumps(metadata)),
            )
            conn.executemany(
                "INSERT INTO task_attachments VALUES (?, ?, ?, ?, ?)",
                [
                    (1, "writer-1", "draft-v1.md", str(old), 100),
                    (2, "writer-1", "draft-v2.md", str(current), 180),
                ],
            )
            conn.commit()
            conn.close()

            result = subprocess.run(
                [str(ASSISTANT_SCRIPTS / "kanban-completion-probe.sh"), "writer-1"],
                env={**os.environ, "HERMES_KANBAN_DB": str(db)},
                check=True,
                capture_output=True,
                text=True,
            )

            probe = json.loads(result.stdout)
            self.assertEqual(["draft-v2.md"], probe["output_attachments"])
            self.assertEqual(digest, probe["output_digests"]["draft-v2.md"])

    def test_completion_probe_rejects_wrong_qa_parent_and_verdict(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            db = root / "kanban.db"
            artifact = root / "final.png"
            artifact.write_bytes(b"final")
            digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
            producer_metadata = {
                "completion": {
                    "status": "completed",
                    "summary": "Produced final image.",
                    "metadata": {"mode": "execute"},
                    "artifacts": ["final.png"],
                },
                "artifact_handoff": {
                    "artifacts": [
                        {
                            "name": "final.png",
                            "sha256": digest,
                            "purpose": "final image",
                            "source_task_id": "producer-1",
                        }
                    ],
                    "verification": ["opened"],
                    "qa": {
                        "status": "required",
                        "capability": "creator-generated-image",
                        "routes": ["qa-raster-image"],
                    },
                },
            }
            qa_summary = "QA fail for final image."
            qa_metadata = {
                "completion": {
                    "status": "fail",
                    "summary": qa_summary,
                    "metadata": {"mode": "verify"},
                },
                "qa": {
                    "target_task": "research-1",
                    "producer_capability": "creator-generated-image",
                    "target_artifacts": [
                        {"name": "final.png", "sha256": "0" * 64}
                    ],
                    "research_parents": [],
                    "technics": ["qa-raster-image"],
                    "verdict": "pass",
                    "criteria": [
                        {
                            "id": [],
                            "requirement": [],
                            "verdict": "pass",
                            "method": [],
                            "evidence": [],
                            "exclusions": [],
                        }
                    ],
                    "findings": [],
                    "residual_risk": "none",
                    "reviewer_scope": "read-only",
                },
            }
            conn = sqlite3.connect(db)
            conn.executescript(
                """
                CREATE TABLE tasks (id TEXT PRIMARY KEY, assignee TEXT, body TEXT, status TEXT, skills TEXT);
                CREATE TABLE task_runs (id INTEGER PRIMARY KEY, task_id TEXT, outcome TEXT,
                    started_at INTEGER, summary TEXT, metadata TEXT);
                CREATE TABLE task_attachments (id INTEGER PRIMARY KEY, task_id TEXT,
                    filename TEXT, stored_path TEXT, created_at INTEGER);
                CREATE TABLE task_links (parent_id TEXT, child_id TEXT);
                """
            )
            conn.executemany(
                "INSERT INTO tasks VALUES (?, ?, ?, ?, ?)",
                [
                    ("producer-1", "creator", "Mode: execute", "done", json.dumps(["creator-pipeline"])),
                    ("research-1", "researcher", "Mode: analyze", "done", json.dumps(["researcher-pipeline"])),
                    ("qa-1", "qa", "Mode: verify\nInput attachments: []", "done", json.dumps(["qa-pipeline", "qa-raster-image"])),
                ],
            )
            conn.executemany(
                "INSERT INTO task_runs VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (
                        1,
                        "producer-1",
                        "completed",
                        100,
                        "Produced final image.",
                        json.dumps(producer_metadata),
                    ),
                    (2, "qa-1", "completed", 200, qa_summary, json.dumps(qa_metadata)),
                ],
            )
            conn.execute(
                "INSERT INTO task_attachments VALUES (?, ?, ?, ?, ?)",
                (1, "producer-1", "final.png", str(artifact), 150),
            )
            conn.executemany(
                "INSERT INTO task_links VALUES (?, ?)",
                [("producer-1", "qa-1"), ("research-1", "qa-1")],
            )
            conn.commit()
            conn.close()

            result = subprocess.run(
                [str(ASSISTANT_SCRIPTS / "kanban-completion-probe.sh"), "qa-1"],
                env={**os.environ, "HERMES_KANBAN_DB": str(db)},
                check=False,
                capture_output=True,
                text=True,
            )
            errors = json.loads(result.stdout)["errors"]

            self.assertEqual(1, result.returncode)
            self.assertIn("metadata.qa.target_task must be the production parent", errors)
            self.assertIn("metadata.qa.research_parents must match Researcher parents", errors)
            self.assertIn("metadata.completion.status must match metadata.qa.verdict", errors)
            self.assertIn(
                "metadata.qa criterion id must be a non-empty string", errors
            )

            unsupported_summary = "QA can't_verify: direct inspection was unavailable."
            unsupported_metadata = {
                "completion": {
                    "status": "can't_verify",
                    "summary": unsupported_summary,
                    "metadata": {"mode": "verify"},
                },
                "qa": {
                    "target_task": "producer-1",
                    "producer_capability": "creator-generated-image",
                    "target_artifacts": [
                        {"name": "final.png", "sha256": digest}
                    ],
                    "research_parents": [],
                    "technics": ["qa-raster-image"],
                    "verdict": "can't_verify",
                    "criteria": [
                        {
                            "id": "direct-inspection",
                            "requirement": "The final artifact can be inspected directly",
                            "verdict": "can't_verify",
                            "method": "qa-raster-image direct inspection",
                            "evidence": "the inspection backend was unavailable",
                            "exclusions": "artifact inspection not run",
                        }
                    ],
                    "findings": [],
                    "residual_risk": "The artifact was not inspected",
                    "reviewer_scope": "read-only",
                },
            }
            conn = sqlite3.connect(db)
            conn.execute(
                "INSERT INTO tasks VALUES (?, ?, ?, ?, ?)",
                (
                    "qa-2",
                    "qa",
                    "Mode: verify\nInput attachments: []",
                    "done",
                    json.dumps(["qa-pipeline", "qa-raster-image"]),
                ),
            )
            conn.execute(
                "INSERT INTO task_runs VALUES (?, ?, ?, ?, ?, ?)",
                (
                    3,
                    "qa-2",
                    "completed",
                    300,
                    unsupported_summary,
                    json.dumps(unsupported_metadata),
                ),
            )
            conn.execute(
                "INSERT INTO task_links VALUES (?, ?)", ("producer-1", "qa-2")
            )
            conn.commit()
            conn.close()
            unsupported = subprocess.run(
                [str(ASSISTANT_SCRIPTS / "kanban-completion-probe.sh"), "qa-2"],
                env={**os.environ, "HERMES_KANBAN_DB": str(db)},
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertTrue(json.loads(unsupported.stdout)["valid"])


if __name__ == "__main__":
    unittest.main()
