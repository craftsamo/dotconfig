"""audit-searcher-sessions.py: failure-signature detectors over a synthetic state.db.

Fixtures are neutral and synthetic: no real transcript, brief or path is used.
"""

from __future__ import annotations

import importlib.util
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "audit-searcher-sessions.py"
SPEC = importlib.util.spec_from_file_location("audit_searcher_sessions", SCRIPT)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)

BUDGET_89 = ("Turn budget: this turn is killed at 2026-10-05 12:52 +08 (~89 min from now); "
             "the whole process group dies with it.")


class Transcript:
    """Append-only builder for one synthetic database."""

    def __init__(self, tmp_path: Path):
        self.path = tmp_path / "state.db"
        self.db = sqlite3.connect(self.path)
        self.db.execute(
            "CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, role TEXT, "
            "content TEXT, tool_calls TEXT, tool_name TEXT, timestamp REAL)"
        )
        self.clock = 1_000_000.0

    def add(self, session, role, content="", *, calls=None, tool=None, after=1.0):
        self.clock += after
        self.db.execute(
            "INSERT INTO messages (session_id, role, content, tool_calls, tool_name, timestamp) VALUES (?,?,?,?,?,?)",
            (session, role, content, json.dumps(calls) if calls else None, tool, self.clock),
        )
        self.db.commit()

    def call(self, session, tool, **arguments):
        self.add(session, "assistant", calls=[{"function": {"name": tool, "arguments": json.dumps(arguments)}}])
        self.add(session, "tool", "{}", tool=tool)


@pytest.fixture
def transcript(tmp_path):
    return Transcript(tmp_path)


def detectors(transcript, **kwargs):
    return [f["detector"] for f in AUDIT.audit(transcript.path, **kwargs)["findings"]]


def test_premature_stop_when_budget_is_cited_within_a_tenth_of_it(transcript):
    transcript.add("s1", "user", BUDGET_89)
    transcript.call("s1", "skill_view", name="build-searcher")
    transcript.call("s1", "web_search")
    transcript.add("s1", "assistant", "Stopping here: the turn budget does not allow more.", after=30)
    assert detectors(transcript) == ["premature_stop"]
    finding = AUDIT.audit(transcript.path)["findings"][0]
    assert finding["detail"]["budget_min"] == 89 and finding["detail"]["elapsed_s"] < 8 * 60


def test_stop_after_using_the_budget_is_not_premature(transcript):
    transcript.add("s1", "user", BUDGET_89)
    transcript.add("s1", "assistant", "Budget exhausted; checkpoint written.", after=80 * 60)
    assert "premature_stop" not in detectors(transcript)


def test_short_budgets_are_a_real_constraint(transcript):
    transcript.add("s1", "user", BUDGET_89.replace("~89 min", "~5 min"))
    transcript.add("s1", "assistant", "Out of budget, stopping.", after=20)
    assert "premature_stop" not in detectors(transcript)


def test_early_finish_without_a_budget_reason_is_not_flagged(transcript):
    transcript.add("s1", "user", BUDGET_89)
    transcript.add("s1", "assistant", "Here are the three links you asked for.", after=20)
    assert detectors(transcript) == []


def test_commit_claim_needs_a_terminal_call_in_the_same_turn(transcript):
    transcript.add("s1", "user", "collect sources")
    transcript.call("s1", "web_search")
    transcript.add("s1", "assistant", "コミット済みチェックポイントとして停止します。")
    assert "commit_claim_without_terminal" in detectors(transcript)

    transcript.add("s2", "user", "collect sources")
    transcript.call("s2", "terminal")
    transcript.add("s2", "assistant", "Work is committed.")
    assert "commit_claim_without_terminal" not in [
        f["detector"] for f in AUDIT.audit(transcript.path)["findings"] if f["session"] == "s2"
    ]


def test_save_claim_needs_some_write_in_the_session(transcript):
    transcript.add("s1", "user", "collect sources")
    transcript.add("s1", "assistant", "結果はファイルに保存しました。")
    assert "save_claim_without_write" in detectors(transcript)

    transcript.add("s2", "user", "collect sources")
    transcript.call("s2", "write_file", path="out.md")
    transcript.add("s2", "assistant", "結果はファイルに保存しました。")
    assert not [f for f in AUDIT.audit(transcript.path)["findings"]
                if f["session"] == "s2" and f["detector"] == "save_claim_without_write"]


@pytest.mark.parametrize("text", [
    "Not searched: X検索（read-only制約）",
    "read-only のため x_search は使っていません",
])
def test_x_search_excluded_as_read_only(transcript, text):
    transcript.add("s1", "user", "survey")
    transcript.add("s1", "assistant", text)
    assert "x_search_excluded_as_read_only" in detectors(transcript)


def test_x_search_mention_is_fine_when_the_tool_ran(transcript):
    transcript.add("s1", "user", "survey")
    transcript.call("s1", "x_search", query="topic")
    transcript.add("s1", "assistant", "X検索は read-only 制約の範囲で実施済みです。")
    assert "x_search_excluded_as_read_only" not in detectors(transcript)


def test_phase_entry_missing_and_qa_entry_missing(transcript):
    transcript.add("s1", "user", "survey")
    transcript.call("s1", "web_search")
    transcript.call("s1", "write_file", path="out.md")
    assert sorted(detectors(transcript)) == ["phase_entry_missing", "qa_entry_missing"]

    transcript.add("s2", "user", "survey")
    transcript.call("s2", "skill_view", name="build-searcher")
    transcript.call("s2", "skill_view", name="qa-searcher")
    transcript.call("s2", "web_search")
    transcript.call("s2", "write_file", path="out.md")
    assert not [f for f in AUDIT.audit(transcript.path)["findings"] if f["session"] == "s2"]


def test_session_without_retrieval_needs_no_entries(transcript):
    transcript.add("s1", "user", "plan only")
    transcript.add("s1", "assistant", "Proposal: three units.")
    assert detectors(transcript) == []


def test_runtime_refusals_are_counted(transcript):
    transcript.add("s1", "user", "card")
    transcript.add("s1", "tool", "goal_mode tasks can only block with kind in ['dependency']", tool="kanban_block")
    transcript.add("s1", "tool", "Goal completion rejected by judge: floor unmet", tool="kanban_complete")
    assert sorted(detectors(transcript)) == ["goal_block_rejected", "goal_completion_rejected"]


def test_since_skips_older_turns(transcript):
    transcript.add("s1", "user", BUDGET_89)
    transcript.add("s1", "assistant", "The turn budget ends here.", after=10)
    assert detectors(transcript, since=transcript.clock + 1) == []


def test_findings_never_carry_message_text(transcript):
    marker = "BRIEF-TEXT-MARKER"
    transcript.add("s1", "user", f"{BUDGET_89} {marker}")
    transcript.add("s1", "assistant", f"{marker} budget exhausted. コミット済み", after=10)
    assert marker not in json.dumps(AUDIT.audit(transcript.path))


def test_database_is_opened_read_only(transcript):
    transcript.add("s1", "user", "x")
    transcript.db.close()
    snapshot = transcript.path.read_bytes()
    transcript.path.chmod(0o444)
    try:
        assert AUDIT.audit(transcript.path)["sessions"] == 1
    finally:
        transcript.path.chmod(0o644)
    assert transcript.path.read_bytes() == snapshot
    assert sorted(p.name for p in transcript.path.parent.iterdir()) == ["state.db"]


def run_cli(*args):
    return subprocess.run([sys.executable, "-B", str(SCRIPT), *map(str, args)], capture_output=True, text=True)


def test_cli_strict_exit_codes_and_invalid_invocation(transcript, tmp_path):
    transcript.add("s1", "user", BUDGET_89)
    transcript.add("s1", "assistant", "The turn budget ends here.", after=10)
    transcript.db.close()
    assert run_cli("--db", transcript.path).returncode == 0
    strict = run_cli("--db", transcript.path, "--strict", "--json")
    assert strict.returncode == 1 and json.loads(strict.stdout)["counts"] == {"premature_stop": 1}
    assert run_cli("--db", tmp_path / "missing.db").returncode == 2
    assert run_cli("--db", transcript.path, "--since", "yesterday").returncode == 2
