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
    def test_watchdog_repeats_qa_candidate_until_materialized(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            db = root / "kanban.db"
            state = root / "watchdog.json"
            now = int(time.time())
            metadata = {
                "artifact_handoff": {
                    "artifacts": [{"name": "draft.md"}],
                    "verification": [],
                    "qa": {
                        "status": "required",
                        "capability": "writer:technical-prose",
                        "routes": ["qa-prose"],
                    },
                }
            }
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
                CREATE TABLE task_runs (
                    id INTEGER PRIMARY KEY, task_id TEXT, outcome TEXT, metadata TEXT
                );
                CREATE TABLE task_links (parent_id TEXT, child_id TEXT);
                CREATE TABLE kanban_notify_subs (task_id TEXT);
                CREATE TABLE task_comments (
                    id INTEGER PRIMARY KEY, task_id TEXT, body TEXT,
                    created_at INTEGER, author TEXT
                );
                """
            )
            conn.execute(
                "INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    "writer-1",
                    "write",
                    "writer",
                    "done",
                    "assistant",
                    now - 900,
                    now - 600,
                ),
            )
            conn.execute(
                "INSERT INTO task_events VALUES (?, ?, ?, ?, ?)",
                (41, "writer-1", "completed", "{}", now - 600),
            )
            conn.execute(
                "INSERT INTO task_runs VALUES (?, ?, ?, ?)",
                (7, "writer-1", "completed", json.dumps(metadata)),
            )
            conn.execute(
                "INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    "research-1",
                    "verify claims",
                    "researcher",
                    "blocked",
                    "assistant",
                    now - 800,
                    None,
                ),
            )
            conn.execute(
                "INSERT INTO task_links VALUES (?, ?)",
                ("writer-1", "research-1"),
            )
            conn.executemany(
                "INSERT INTO task_events VALUES (?, ?, ?, ?, ?)",
                [
                    (42, "research-1", "blocked", "{}", now - 500),
                    (43, "research-1", "gave_up", "{}", now - 400),
                ],
            )
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
            self.assertIn("writer-1", first.stdout)
            self.assertIn("writer-1", second.stdout)

            conn = sqlite3.connect(db)
            conn.execute(
                "UPDATE tasks SET status = 'ready' WHERE id = ?", ("research-1",)
            )
            conn.execute(
                "UPDATE task_events SET kind = 'timed_out' WHERE id = ?", (43,)
            )
            conn.commit()
            conn.close()
            retrying = subprocess.run(
                [str(script)], env=env, check=True, capture_output=True, text=True
            )
            self.assertNotIn("writer-1", retrying.stdout)

            conn = sqlite3.connect(db)
            conn.execute(
                "INSERT INTO task_comments VALUES (?, ?, ?, ?, ?)",
                (
                    1,
                    "writer-1",
                    "QA_MATERIALIZED: requirement=draft task=qa-1 producer=writer-1 "
                    "completion_event=41 contract_digest=abc inputs_digest=def",
                    now - 300,
                    "assistant",
                ),
            )
            conn.commit()
            conn.close()
            handled = subprocess.run(
                [str(script)], env=env, check=True, capture_output=True, text=True
            )
            self.assertNotIn("writer-1", handled.stdout)

    def test_fanout_probe_rejects_predeclared_qa(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            db = root / "kanban.db"
            manifest = root / "fan-out.yaml"
            manifest.write_text(
                """origin_task_id: origin-1
checkpoint_key: expand-1
children:
  - key: draft
    title: Draft the report
    assignee: writer
    skills: [writer-pipeline]
    parents: []
    params: {}
    task_spec:
      goal: Draft the report
      inputs: approved facts
      input_attachments: []
      done_criteria: complete report
      output: report.md
      constraints: no publishing
      qa: required
      producer_qa_requirement:
        candidate_key: draft
        evidence_keys: []
        capability: writer:technical-prose
        routes: [qa-prose]
        criteria: [complete and accurate]
        done_criteria: complete report
        output_inventory: [report.md]
continuation:
  title: Resume engineering
  assignee: engineer
  skills: [engineer-pipeline]
  parents: [draft]
  params: {}
  task_spec:
    goal: Integrate the report
    inputs: completed draft
    input_attachments: []
    done_criteria: integration complete
    output: summary
    constraints: no scope expansion
attachments: []
""",
                encoding="utf-8",
            )
            conn = sqlite3.connect(db)
            conn.executescript(
                """
                CREATE TABLE tasks (id TEXT PRIMARY KEY, assignee TEXT, status TEXT);
                CREATE TABLE task_attachments (id INTEGER PRIMARY KEY, task_id TEXT,
                    filename TEXT, stored_path TEXT);
                """
            )
            conn.execute(
                "INSERT INTO tasks VALUES (?, ?, ?)",
                ("origin-1", "engineer", "blocked"),
            )
            conn.execute(
                "INSERT INTO task_attachments VALUES (?, ?, ?, ?)",
                (1, "origin-1", "fan-out.yaml", str(manifest)),
            )
            conn.commit()
            conn.close()

            script = ASSISTANT_SCRIPTS / "kanban-fanout-manifest-probe.sh"
            valid = subprocess.run(
                [str(script), "origin-1"],
                env={**os.environ, "HERMES_KANBAN_DB": str(db)},
                check=True,
                capture_output=True,
                text=True,
            )
            valid_payload = json.loads(valid.stdout)
            self.assertTrue(valid_payload["valid"])
            self.assertRegex(valid_payload["manifest_digest"], r"^[0-9a-f]{64}$")
            replay = subprocess.run(
                [str(script), "origin-1"],
                env={**os.environ, "HERMES_KANBAN_DB": str(db)},
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                valid_payload["manifest_digest"],
                json.loads(replay.stdout)["manifest_digest"],
            )

            for original, replacement, expected in (
                ("assignee: writer", "assignee: qa", "children[0] cannot assign qa"),
                ("assignee: engineer", "assignee: qa", "continuation cannot assign qa"),
            ):
                with self.subTest(expected=expected):
                    text = manifest.read_text(encoding="utf-8")
                    manifest.write_text(
                        text.replace(original, replacement, 1), encoding="utf-8"
                    )
                    rejected = subprocess.run(
                        [str(script), "origin-1"],
                        env={**os.environ, "HERMES_KANBAN_DB": str(db)},
                        check=False,
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(1, rejected.returncode)
                    self.assertTrue(
                        any(
                            expected in error
                            for error in json.loads(rejected.stdout)["errors"]
                        )
                    )
                    manifest.write_text(text, encoding="utf-8")

            text = manifest.read_text(encoding="utf-8")
            manifest.write_text(
                text.replace(
                    "      producer_qa_requirement:",
                    "      missing_qa_requirement:",
                    1,
                ),
                encoding="utf-8",
            )
            missing_requirement = subprocess.run(
                [str(script), "origin-1"],
                env={**os.environ, "HERMES_KANBAN_DB": str(db)},
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(1, missing_requirement.returncode)
            self.assertTrue(
                any(
                    "producer_qa_requirement must be the closed canonical object"
                    in error
                    for error in json.loads(missing_requirement.stdout)["errors"]
                )
            )

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

    def test_watchdog_reports_loopfall_and_generic_no_subscription(self) -> None:
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
                        "unsubscribed",
                        "creator",
                        "blocked",
                        "assistant",
                        now - 900,
                        None,
                    ),
                    (
                        "failed-1",
                        "terminal failure",
                        "writer",
                        "blocked",
                        "assistant",
                        now - 900,
                        now - 600,
                    ),
                    (
                        "done-1",
                        "normally completed",
                        "researcher",
                        "done",
                        "assistant",
                        now - 900,
                        now - 600,
                    ),
                    (
                        "reblocked-1",
                        "blocked after retry",
                        "engineer",
                        "blocked",
                        "assistant",
                        now - 900,
                        None,
                    ),
                ],
            )
            conn.executemany(
                "INSERT INTO task_events VALUES (?, ?, ?, ?, ?)",
                [
                    (1, "loop-1", "block_loop_detected", "{}", now - 600),
                    (2, "qa-gap", "blocked", json.dumps({"reason": "missing subscription"}), now - 600),
                    (3, "failed-1", "gave_up", json.dumps({"reason": "failed"}), now - 600),
                    (4, "done-1", "completed", json.dumps({"outcome": "done"}), now - 600),
                    (5, "reblocked-1", "gave_up", json.dumps({"reason": "old failure"}), now - 500),
                    (6, "reblocked-1", "blocked", json.dumps({"reason": "Q1: retry input"}), now - 400),
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
            self.assertIn("failed-1", result.stdout)
            self.assertEqual(1, result.stdout.count("failed-1"))
            self.assertNotIn("done-1", result.stdout)
            self.assertEqual(1, result.stdout.count("reblocked-1"))

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

            conn = sqlite3.connect(db)
            conn.execute(
                "UPDATE tasks SET assignee = ?, body = ? WHERE id = ?",
                (
                    "writer",
                    "Mode: execute\nQA: required\nCandidate key: write",
                    "task-1",
                ),
            )
            conn.commit()
            conn.close()
            missing_requirement = subprocess.run(
                [str(script), "task-1"],
                env={
                    **os.environ,
                    "HERMES_KANBAN_DB": "",
                    "HERMES_KANBAN_HOME": str(root),
                    "HERMES_KANBAN_BOARD": "named",
                },
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(1, missing_requirement.returncode)
            self.assertIn("Producer QA requirement", missing_requirement.stderr)

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

            conn = sqlite3.connect(db)
            conn.execute(
                "UPDATE tasks SET body = ? WHERE id = ?",
                (
                    "Mode: retrieve\nInput attachments: []\n"
                    "Input attachments: []",
                    "task-1",
                ),
            )
            conn.commit()
            conn.close()
            duplicate_inputs = subprocess.run(
                [str(script), "task-1"],
                env={**os.environ, "HERMES_KANBAN_DB": str(db)},
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(1, duplicate_inputs.returncode)
            self.assertIn(
                "TaskSpec must declare Input attachments exactly once",
                json.loads(duplicate_inputs.stdout)["errors"],
            )

            metadata["artifact_handoff"] = {
                "artifacts": [],
                "verification": [],
                "qa": None,
            }
            conn = sqlite3.connect(db)
            conn.execute(
                "UPDATE tasks SET body = ? WHERE id = ?",
                ("Mode: retrieve\nInput attachments: []", "task-1"),
            )
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

    def test_completion_probe_rejects_qa_in_specialist_plan(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "kanban.db"
            summary = "Prepared the specialist plan."
            metadata = {
                "completion": {
                    "status": "completed",
                    "summary": summary,
                    "metadata": {"mode": "plan"},
                },
                "specialist_plan": {
                    "origin_task_id": "plan-1",
                    "branch_key": "writer-plan",
                    "summary": "Use one writing card.",
                    "proposed_cards": [
                        {
                            "key": "qa-card",
                            "title": "Review the output",
                            "assignee": "qa",
                            "skills": [],
                            "parents": [],
                            "params": {},
                            "task_spec": {
                                "goal": "Review the output",
                                "inputs": "the output",
                                "input_attachments": [],
                                "done_criteria": "review complete",
                                "output": "review result",
                                "constraints": "read-only",
                            },
                        }
                    ],
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
                (
                    "plan-1",
                    "writer",
                    "Mode: plan\nPlanning branch: writer-plan\nInput attachments: []",
                    "done",
                    json.dumps(["writer-pipeline"]),
                ),
            )
            conn.execute(
                "INSERT INTO task_runs VALUES (?, ?, ?, ?, ?, ?)",
                (1, "plan-1", "completed", 100, summary, json.dumps(metadata)),
            )
            conn.commit()
            conn.close()

            result = subprocess.run(
                [str(ASSISTANT_SCRIPTS / "kanban-completion-probe.sh"), "plan-1"],
                env={**os.environ, "HERMES_KANBAN_DB": str(db)},
                check=False,
                capture_output=True,
                text=True,
            )

            errors = json.loads(result.stdout)["errors"]
            self.assertEqual(1, result.returncode)
            self.assertIn(
                "metadata.specialist_plan.proposed_cards[0] cannot assign qa: "
                "QA must be late-bound after CompletionAdmission/digest resolution",
                errors,
            )

            metadata["specialist_plan"]["proposed_cards"][0].update(
                {"key": "write", "title": "Write the output", "assignee": "writer"}
            )
            metadata["specialist_plan"]["proposed_cards"][0]["task_spec"][
                "qa"
            ] = "required"
            conn = sqlite3.connect(db)
            conn.execute(
                "UPDATE task_runs SET metadata = ? WHERE id = ?",
                (json.dumps(metadata), 1),
            )
            conn.commit()
            conn.close()
            missing_requirement = subprocess.run(
                [str(ASSISTANT_SCRIPTS / "kanban-completion-probe.sh"), "plan-1"],
                env={**os.environ, "HERMES_KANBAN_DB": str(db)},
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(1, missing_requirement.returncode)
            self.assertTrue(
                any(
                    "producer_qa_requirement must be the closed canonical object"
                    in error
                    for error in json.loads(missing_requirement.stdout)["errors"]
                )
            )

    def test_completion_probe_parses_outline_and_rejects_qa_cards(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            db = root / "kanban.db"
            outline = root / "execution-outline.yaml"
            outline.write_text(
                """request_id: request-1
goal: Integrate the approved plans.
cards:
  - key: write
    title: Write the result
    assignee: writer
    skills:
      - writer-pipeline
    parents: []
    params: {}
    task_spec:
      goal: Write the result
      inputs: approved plan
      done_criteria: result is written
      output: result.md
      constraints: no extra research
""",
                encoding="utf-8",
            )
            summary = "Prepared the execution outline."
            metadata = {
                "completion": {
                    "status": "completed",
                    "summary": summary,
                    "metadata": {"mode": "integrate", "request_id": "request-1"},
                    "artifacts": ["execution-outline.yaml"],
                },
                "artifact_handoff": {
                    "artifacts": [
                        {
                            "name": "execution-outline.yaml",
                            "sha256": "pending-assistant-probe",
                            "purpose": "approval gate 2",
                            "source_task_id": "planner-1",
                        }
                    ],
                    "verification": ["schema"],
                    "qa": {"status": "exempt", "reason": "planning artifact"},
                },
                "execution_outline": {
                    "request_id": "request-1",
                    "attachment": "execution-outline.yaml",
                    "sha256": "pending-assistant-probe",
                    "specialist_task_ids": ["specialist-1"],
                    "card_count": 1,
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
                (
                    "specialist-1",
                    "writer",
                    "Mode: plan\nInput attachments: []",
                    "done",
                    json.dumps(["writer-pipeline"]),
                ),
            )
            conn.execute(
                "INSERT INTO tasks VALUES (?, ?, ?, ?, ?)",
                (
                    "planner-1",
                    "planner",
                    "Mode: integrate\nRequest run: request-1\nInput attachments: []",
                    "done",
                    json.dumps(["planner-pipeline"]),
                ),
            )
            conn.execute(
                "INSERT INTO task_runs VALUES (?, ?, ?, ?, ?, ?)",
                (1, "planner-1", "completed", 100, summary, json.dumps(metadata)),
            )
            conn.execute(
                "INSERT INTO task_attachments VALUES (?, ?, ?, ?, ?)",
                (1, "planner-1", "execution-outline.yaml", str(outline), 110),
            )
            conn.execute(
                "INSERT INTO task_links VALUES (?, ?)", ("specialist-1", "planner-1")
            )
            conn.commit()
            conn.close()

            script = ASSISTANT_SCRIPTS / "kanban-completion-probe.sh"
            valid = subprocess.run(
                [str(script), "planner-1"],
                env={**os.environ, "HERMES_KANBAN_DB": str(db)},
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertTrue(json.loads(valid.stdout)["valid"])

            outline.write_text(
                outline.read_text(encoding="utf-8").replace(
                    "assignee: writer", "assignee: qa", 1
                ),
                encoding="utf-8",
            )
            rejected = subprocess.run(
                [str(script), "planner-1"],
                env={**os.environ, "HERMES_KANBAN_DB": str(db)},
                check=False,
                capture_output=True,
                text=True,
            )

            errors = json.loads(rejected.stdout)["errors"]
            self.assertEqual(1, rejected.returncode)
            self.assertIn(
                "execution outline cards[0] cannot assign qa: "
                "QA must be late-bound after CompletionAdmission/digest resolution",
                errors,
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
            qa_inputs = json.dumps(
                [
                    {
                        "name": "final.png",
                        "sha256": digest,
                        "purpose": "QA candidate",
                        "source_task_id": "producer-1",
                    }
                ],
                separators=(",", ":"),
            )
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
                    ("qa-1", "qa", f"Mode: verify\nInput attachments: {qa_inputs}", "done", json.dumps(["qa-pipeline", "qa-raster-image"])),
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
                    f"Mode: verify\nInput attachments: {qa_inputs}",
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
