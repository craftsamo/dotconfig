"""Behaviour tests for profiles/assistant/scripts/resident-session.sh.

The wrapper is exercised end to end against a fake `hermes` CLI.
"""

from __future__ import annotations

import glob
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


HERMES_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = HERMES_ROOT / "profiles" / "assistant" / "scripts" / "resident-session.sh"

# Replies on stdout, reports a session id on stderr — the shape the wrapper
# scrapes. `--resume <id>` echoes that id back, like a resumed conversation.
FAKE_OK = """#!/usr/bin/env python3
import sys
args = sys.argv[1:]
sid = "20260824_000000_aaaaaa"
for i, a in enumerate(args):
    if a == "--resume":
        sid = args[i + 1]
print("REPLY-OK")
print("session_id: %s" % sid, file=sys.stderr)
"""

# Replies, but slowly enough that a second invocation overlaps it.
FAKE_SLOW = """#!/usr/bin/env python3
import sys, time
time.sleep(3)
print("REPLY-OK")
print("session_id: 20260824_000000_aaaaaa", file=sys.stderr)
"""


class ResidentSessionTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.reg = self.root / "reg"
        self.reg.mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.addCleanup(self._tmp.cleanup)

    def fake(self, name: str, body: str) -> Path:
        path = self.bin / name
        path.write_text(body, encoding="utf-8")
        path.chmod(0o755)
        return path

    def environment(self, hermes: str = "ok", **env: str) -> dict:
        binary = {
            "ok": lambda: self.fake("hermes-ok", FAKE_OK),
            "slow": lambda: self.fake("hermes-slow", FAKE_SLOW),
        }[hermes]()
        return {
            **os.environ,
            "RESIDENT_SESSION_DIR": str(self.reg),
            "HERMES": str(binary),
            "POLL_INTERVAL": "1",
            "KILL_GRACE": "1",
            "LOCK_STALE_AFTER": "2",
            **env,
        }

    def run_script(self, *args: str, hermes: str = "ok", **env: str):
        return subprocess.run(
            [str(SCRIPT), *args],
            env=self.environment(hermes, **env),
            capture_output=True,
            text=True,
        )

    def registry(self, key: str) -> dict:
        return json.loads((self.reg / f"{key}.json").read_text(encoding="utf-8"))

    def log(self, key: str) -> str:
        return (self.reg / f"{key}.log").read_text(encoding="utf-8")

    # --- happy path -----------------------------------------------------

    def test_start_then_send_records_session_and_counts_turns(self) -> None:
        started = self.run_script("start", "k", "--profile", "creator",
                                  "--topic", "t", "-q", "brief")
        self.assertEqual(0, started.returncode, started.stderr)
        self.assertIn("REPLY-OK", started.stdout)

        sent = self.run_script("send", "k", "-q", "next")
        self.assertEqual(0, sent.returncode, sent.stderr)

        entry = self.registry("k")
        self.assertEqual("20260824_000000_aaaaaa", entry["session_id"])
        self.assertEqual("idle", entry["status"])
        self.assertEqual(2, entry["turns"])
        self.assertEqual("creator", entry["profile"])

    def test_prompt_can_come_from_a_file(self) -> None:
        brief = self.root / "brief.txt"
        brief.write_text("goal: ship it\n", encoding="utf-8")
        result = self.run_script("start", "k", "--profile", "writer", "-f", str(brief))
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("goal: ship it", self.log("k"))

    # --- locking --------------------------------------------------------

    def test_busy_lock_exits_75(self) -> None:
        self.run_script("start", "k", "--profile", "creator", "-q", "brief")
        lock = self.reg / "k.lock"
        lock.mkdir()
        (lock / "pid").write_text(f"{os.getpid()}\n", encoding="utf-8")

        result = self.run_script("send", "k", "-q", "x")
        self.assertEqual(75, result.returncode)
        self.assertIn("in flight", result.stderr)

    def test_stale_lock_from_a_dead_holder_is_reclaimed(self) -> None:
        self.run_script("start", "k", "--profile", "creator", "-q", "brief")
        lock = self.reg / "k.lock"
        lock.mkdir()
        (lock / "pid").write_text("999999\n", encoding="utf-8")
        os.utime(lock, (0, 0))  # far older than LOCK_STALE_AFTER

        result = self.run_script("send", "k", "-q", "x")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("reclaiming stale lock", result.stderr)
        self.assertFalse(lock.exists(), "the reclaimed lock is released again")

    def test_lock_older_than_the_turn_timeout_is_reclaimed_despite_a_live_pid(self) -> None:
        # Guards pid reuse: no legitimate holder outlives TURN_TIMEOUT, since
        # it hard-kills itself and drops the lock in its trap.
        self.run_script("start", "k", "--profile", "creator", "-q", "brief")
        lock = self.reg / "k.lock"
        lock.mkdir()
        (lock / "pid").write_text(f"{os.getpid()}\n", encoding="utf-8")
        os.utime(lock, (0, 0))

        result = self.run_script("send", "k", "-q", "x", TURN_TIMEOUT="1")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("reclaiming stale lock", result.stderr)

    def test_two_reclaimers_racing_one_stale_lock_produce_a_single_holder(self) -> None:
        # The reclaim path is rm-then-mkdir shaped, so a concurrent pair must
        # not both conclude they own the key.
        self.run_script("start", "k", "--profile", "creator", "-q", "brief")
        lock = self.reg / "k.lock"
        lock.mkdir()
        (lock / "pid").write_text("999999\n", encoding="utf-8")
        os.utime(lock, (0, 0))

        env = self.environment("slow")
        racers = [
            subprocess.Popen([str(SCRIPT), "send", "k", "-q", "x"], env=env,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            for _ in range(2)
        ]
        results = [(p.wait(timeout=60), *p.communicate()) for p in racers]
        codes = sorted(code for code, _, _ in results)
        self.assertEqual([0, 75], codes,
                         "exactly one reclaimer may run the turn; the other waits")
        winner = [out for code, out, _ in results if code == 0][0]
        self.assertIn("REPLY-OK", winner)
        self.assertFalse(lock.exists(), "the winner releases the lock it took")

    # --- list -----------------------------------------------------------

    def test_list_hides_closed_by_default_and_sorts_newest_first(self) -> None:
        for key in ("old", "new", "gone"):
            self.run_script("start", key, "--profile", "creator", "-q", "brief")
        self.run_script("close", "gone")
        for key, stamp in (("old", "2026-01-01T00:00:00"), ("new", "2026-08-01T00:00:00")):
            entry = self.registry(key)
            entry["last_turn_at"] = stamp
            (self.reg / f"{key}.json").write_text(json.dumps(entry), encoding="utf-8")

        default = self.run_script("list")
        self.assertEqual(0, default.returncode, default.stderr)
        lines = [line for line in default.stdout.splitlines() if line.strip()]
        self.assertNotIn("gone", default.stdout)
        self.assertLess(lines.index([l for l in lines if l.startswith("new")][0]),
                        lines.index([l for l in lines if l.startswith("old")][0]))
        self.assertIn("1 closed hidden", default.stdout)

        everything = self.run_script("list", "--all")
        self.assertIn("gone", everything.stdout)
        self.assertNotIn("closed hidden", everything.stdout)

    def test_list_reports_an_empty_registry(self) -> None:
        result = self.run_script("list")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("no open resident sessions", result.stdout)

    def test_list_walks_the_registry_in_one_python_process(self) -> None:
        # The per-key loop cost 23s at 101 keys; guard the shape, not the clock.
        source = SCRIPT.read_text(encoding="utf-8")
        list_block = source.split("  list)", 1)[1].split("    ;;", 1)[0]
        code = [line for line in list_block.splitlines()
                if not line.lstrip().startswith("#")]
        self.assertEqual(1, sum(line.count("python3 ") for line in code))
        self.assertNotIn("for f in", list_block)

    def test_invalid_key_is_rejected(self) -> None:
        result = self.run_script("start", "bad key", "--profile", "creator", "-q", "x")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("invalid key", result.stderr)

    def test_unknown_command_is_rejected(self) -> None:
        result = self.run_script("resume", "k")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("unknown command", result.stderr)



if __name__ == "__main__":
    unittest.main()
