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
    def test_gateway_launcher_keeps_discord_credentials(self) -> None:
        launcher = HERMES_ROOT / "launchd" / "hermes-gateway-assistant"
        text = launcher.read_text(encoding="utf-8")
        self.assertNotIn("unset DISCORD_", text)
        self.assertIn("gateway run --replace --accept-hooks", text)

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
            self.assertEqual(("ready", 0, None), task)

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
            env = {
                **os.environ,
                "HERMES_KANBAN_DB": str(db),
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
            conn.execute("UPDATE tasks SET block_recurrences=2 WHERE id='race-1'")
            conn.execute(
                "INSERT INTO task_events VALUES (?, ?, ?, ?, ?)",
                (2, "race-1", "blocked", 101, json.dumps({"reason": "Q1 newer"})),
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
            self.assertIn("no typed question or gate", result.stderr)
            conn = sqlite3.connect(db)
            task = conn.execute(
                "SELECT status, block_recurrences, block_kind FROM tasks WHERE id='race-1'"
            ).fetchone()
            conn.close()
            self.assertEqual(("blocked", 2, "needs_input"), task)

    def test_block_resolver_rolls_back_unblock_when_reset_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "kanban.db"
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
                ("rollback-1", "blocked", 1, "needs_input"),
            )
            conn.execute(
                "INSERT INTO task_events VALUES (?, ?, ?, ?, ?)",
                (1, "rollback-1", "blocked", 100, json.dumps({"reason": "Q1"})),
            )
            conn.execute(
                "INSERT INTO task_comments VALUES (?, ?, ?, ?, ?)",
                (1, "rollback-1", "Q1: choose", 99, "engineer"),
            )
            conn.commit()
            conn.close()
            env = {**os.environ, "HERMES_KANBAN_DB": str(db)}
            script = ASSISTANT_SCRIPTS / "kanban-resolve-block.sh"
            binding = subprocess.run(
                [str(script), "inspect", "rollback-1"],
                env=env,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            conn = sqlite3.connect(db)
            conn.execute(
                "INSERT INTO task_comments VALUES (?, ?, ?, ?, ?)",
                (2, "rollback-1", f"DECISION(Q1): choose {binding}", 100, "assistant"),
            )
            conn.execute(
                "CREATE TRIGGER reject_unblock BEFORE UPDATE ON tasks "
                "BEGIN SELECT RAISE(ABORT, 'reset failed'); END"
            )
            conn.commit()
            conn.close()

            result = subprocess.run(
                [str(script), "apply", "rollback-1"],
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(1, result.returncode)
            conn = sqlite3.connect(db)
            task = conn.execute(
                "SELECT status, block_recurrences, block_kind FROM tasks"
            ).fetchone()
            unblocked = conn.execute(
                "SELECT COUNT(*) FROM task_events WHERE kind='unblocked'"
            ).fetchone()[0]
            conn.close()
            self.assertEqual(("blocked", 1, "needs_input"), task)
            self.assertEqual(0, unblocked)

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



if __name__ == "__main__":
    unittest.main()
