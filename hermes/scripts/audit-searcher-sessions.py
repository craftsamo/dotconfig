#!/usr/bin/env python3
"""Read-only audit of Searcher session transcripts for known failure signatures.

Opens a profile's ``state.db`` read-only and scans its ``messages`` table. It
never prints message text: findings carry only the detector, a truncated session
id, the turn index and numeric facts, so the output is safe to paste into an
issue. It never touches the network, a subprocess or the live gateway.

Detectors (each one is a failure seen in real Searcher transcripts):

- ``premature_stop`` (warn): the handoff announced a turn budget of N minutes,
  yet the turn ended within 10% of it and the final reply cites the budget or a
  checkpoint as the reason to stop.
- ``commit_claim_without_terminal`` (warn): the final reply says it committed,
  but the turn made no ``terminal`` call.
- ``save_claim_without_write`` (warn): the final reply says it saved or wrote a
  file, but the session holds no ``write_file`` / ``patch`` call at all.
- ``x_search_excluded_as_read_only`` (warn): the reply lists X search as not
  searched because of a read-only constraint, and the session never called
  ``x_search``. The constraint only forbids writing to social platforms.
- ``phase_entry_missing`` (warn): the session searched without ever loading
  ``build-searcher``.
- ``qa_entry_missing`` (info): the session searched and wrote output without
  ever loading ``qa-searcher``; a preliminary Build may legitimately end there.
- ``goal_block_rejected`` / ``goal_completion_rejected`` (warn): the runtime
  refused a ``kanban_block`` kind, or the completion judge refused the handoff.

Sessions older than the v7 entry cutover (2026-09-13) ran the retired per-unit
skills, so ``phase_entry_missing`` there is expected: audit with
``--since 2026-09-13``.

Usage:
    audit-searcher-sessions.py [--db PATH] [--since YYYY-MM-DD] [--json] [--strict]

Exit codes: 0 audit ran (findings are reported, not failed), 1 with ``--strict``
and at least one ``warn`` finding, 2 invalid invocation (missing or unreadable
database).
"""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse
import json
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_DB = Path.home() / ".hermes" / "profiles" / "searcher" / "state.db"

BUDGET = re.compile(r"Turn budget: this turn is killed at .*?\(~(\d+) min from now\)")
STOP_REASON = re.compile(r"予算|budget|checkpoint|チェックポイント", re.IGNORECASE)
COMMIT_CLAIM = re.compile(r"コミット(?:済|し)|\bcommitted\b", re.IGNORECASE)
SAVE_CLAIM = re.compile(r"保存(?:済|し)|\bsaved\b|\bwritten to\b", re.IGNORECASE)
X_EXCLUDED = re.compile(
    r"(?:X\s*検索|x_search)[^\n]{0,40}(?:read-only|読み取り専用|制約)"
    r"|(?:read-only|読み取り専用|制約)[^\n]{0,40}(?:X\s*検索|x_search)",
    re.IGNORECASE,
)
RETRIEVAL_TOOLS = {"web_search", "web_extract", "x_search"}
WRITE_TOOLS = {"write_file", "patch"}
# A turn that ends this fast against its announced budget stopped early.
PREMATURE_FRACTION = 0.10
# Below this a short budget is a real constraint, not a mis-stop.
MIN_BUDGET_MINUTES = 30
SESSION_ID_CHARS = 12


def _tool_calls(raw: str | None) -> list[tuple[str, dict[str, Any]]]:
    try:
        calls = json.loads(raw or "[]")
    except (TypeError, ValueError):
        return []
    found = []
    for call in calls if isinstance(calls, list) else []:
        function = call.get("function", {}) if isinstance(call, dict) else {}
        arguments = function.get("arguments", {})
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except ValueError:
                arguments = {}
        found.append((str(function.get("name") or ""), arguments if isinstance(arguments, dict) else {}))
    return found


def _split_turns(rows: list[sqlite3.Row]) -> list[list[sqlite3.Row]]:
    turns: list[list[sqlite3.Row]] = []
    for row in rows:
        if row["role"] == "user" or not turns:
            turns.append([])
        turns[-1].append(row)
    return turns


def _finding(detector: str, severity: str, session: str, turn: int | None, **detail: Any) -> dict[str, Any]:
    return {"detector": detector, "severity": severity, "session": session[:SESSION_ID_CHARS],
            "turn": turn, "detail": detail}


def audit_session(session: str, rows: list[sqlite3.Row], since: float | None) -> tuple[int, list[dict[str, Any]]]:
    """Return (turn count, findings) for one session's ordered messages."""
    findings: list[dict[str, Any]] = []
    tool_names = Counter(r["tool_name"] for r in rows if r["role"] == "tool" and r["tool_name"])
    viewed: set[str] = set()
    for row in rows:
        if row["role"] == "assistant":
            for name, args in _tool_calls(row["tool_calls"]):
                if name == "skill_view" and args.get("name"):
                    viewed.add(str(args["name"]))
    wrote = any(tool_names[t] for t in WRITE_TOOLS)

    turns = _split_turns(rows)
    for index, turn in enumerate(turns):
        first = turn[0]
        if since is not None and first["timestamp"] < since:
            continue
        final = next((r for r in reversed(turn) if r["role"] == "assistant" and not r["tool_calls"]
                      and (r["content"] or "").strip()), None)
        text = (final["content"] or "") if final else ""
        terminal_calls = sum(1 for r in turn if r["role"] == "tool" and r["tool_name"] == "terminal")

        budget = BUDGET.search(first["content"] or "") if first["role"] == "user" else None
        if budget and final and int(budget.group(1)) >= MIN_BUDGET_MINUTES:
            minutes = int(budget.group(1))
            elapsed = final["timestamp"] - first["timestamp"]
            if elapsed < minutes * 60 * PREMATURE_FRACTION and STOP_REASON.search(text):
                findings.append(_finding("premature_stop", "warn", session, index,
                                         budget_min=minutes, elapsed_s=round(elapsed)))
        if final and COMMIT_CLAIM.search(text) and not terminal_calls:
            findings.append(_finding("commit_claim_without_terminal", "warn", session, index))
        if final and SAVE_CLAIM.search(text) and not wrote:
            findings.append(_finding("save_claim_without_write", "warn", session, index))
        if final and X_EXCLUDED.search(text) and not tool_names["x_search"]:
            findings.append(_finding("x_search_excluded_as_read_only", "warn", session, index))
        for row in turn:
            if row["role"] != "tool":
                continue
            content = row["content"] or ""
            if "goal_mode tasks can only block" in content:
                findings.append(_finding("goal_block_rejected", "warn", session, index))
            elif "Goal completion rejected by judge" in content:
                findings.append(_finding("goal_completion_rejected", "warn", session, index))

    if any(tool_names[t] for t in RETRIEVAL_TOOLS):
        if "build-searcher" not in viewed:
            findings.append(_finding("phase_entry_missing", "warn", session, None, entry="build-searcher"))
        if wrote and "qa-searcher" not in viewed:
            findings.append(_finding("qa_entry_missing", "info", session, None))
    return len(turns), findings


def audit(db: Path, since: float | None = None) -> dict[str, Any]:
    connection = sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            "SELECT session_id, role, content, tool_calls, tool_name, timestamp "
            "FROM messages ORDER BY session_id, timestamp, id"
        ).fetchall()
    finally:
        connection.close()
    by_session: dict[str, list[sqlite3.Row]] = defaultdict(list)
    for row in rows:
        by_session[row["session_id"]].append(row)
    turn_count = 0
    findings: list[dict[str, Any]] = []
    for session, session_rows in by_session.items():
        turns, found = audit_session(session, session_rows, since)
        turn_count += turns
        findings += found
    counts = Counter(f["detector"] for f in findings)
    return {"sessions": len(by_session), "turns": turn_count, "counts": dict(sorted(counts.items())),
            "findings": findings}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="Searcher state.db (default: live profile)")
    parser.add_argument("--since", help="only audit turns that start on or after YYYY-MM-DD (local time)")
    parser.add_argument("--json", action="store_true", help="print the full report as JSON")
    parser.add_argument("--strict", action="store_true", help="exit 1 when any warn finding exists")
    args = parser.parse_args(argv)
    since = None
    if args.since:
        try:
            since = datetime.strptime(args.since, "%Y-%m-%d").timestamp()
        except ValueError:
            print(f"audit-searcher-sessions: --since must be YYYY-MM-DD (got {args.since!r})", file=sys.stderr)
            return 2
    if not args.db.is_file():
        print(f"audit-searcher-sessions: no such database: {args.db}", file=sys.stderr)
        return 2
    try:
        report = audit(args.db, since)
    except sqlite3.Error as exc:
        print(f"audit-searcher-sessions: cannot read {args.db}: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"sessions={report['sessions']} turns={report['turns']}")
        for name, count in report["counts"].items():
            print(f"{name}: {count}")
        if not report["counts"]:
            print("no findings")
    warned = any(f["severity"] == "warn" for f in report["findings"])
    return 1 if args.strict and warned else 0


if __name__ == "__main__":
    raise SystemExit(main())
