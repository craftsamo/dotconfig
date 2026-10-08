"""Read-only Hermes session inventory across every profile: list, get, children, usage.

Hermes' own session store comes first: each profile's state.db is opened through
``SessionDB(read_only=True)``, the attach Hermes provides for cross-profile
aggregation (no schema init, no write lock). It owns compression lineage and
row shaping. When Hermes is not importable (a plain python3), a guarded
read-only SQLite route answers instead and says so. ``usage`` always reads
scalar columns directly, because Hermes has no windowed usage API.

Only metadata leaves this module. Titles and costs are opt-in; message
content, previews, prompts and messaging identities (user, chat, thread,
session key, origin) are never selected.
"""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import urllib.parse


def _load_common():
    name = "hermes_session_history_common"
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parent / "common.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


common = _load_common()
Unavailable = common.Unavailable

ACTIONS = ("list", "get", "children", "usage")
KINDS = ("root", "child", "all")
GROUPS = ("profile", "platform", "model", "task", "directory", "kind", "day")
SOURCES = ("auto", "api", "db")
FIELDS = {"action", "session_id", "profile", "from", "to", "days", "timezone", "directory", "kind", "platform",
          "model", "archived", "search", "include_title", "include_cost", "limit", "offset", "group_by",
          "source"}
SESSION_ID = re.compile(r"[A-Za-z0-9_.:-]{1,128}\Z")
PROFILE = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}\Z")
DEFAULT_LIMIT = 50
MAX_LIMIT = 200
TOKEN_KEYS = ("input", "output", "reasoning", "cache_read", "cache_write")
# The agent loop's events: a user turn, model output, tool results. A gap that
# ends at model output or a tool result is the agent working (thinking, or a
# tool running); a gap that ends at a user message is the person away.
EVENT_ROLES = ("user", "assistant", "tool")
# Tool results whose wait is a person answering, not work.
WAIT_TOOLS = ("clarify",)
# Tool results whose wait is another agent's session, already counted there.
# They stay in activity (the caller did wait) and are reported separately so a
# cross-tool total can remove the overlap.
# `opencode_call` is the retired plugin's run tool and past sessions still carry it; the
# opencode run tools are one per configured role (`opencode_run_<role>`), and a reply to a
# paused run blocks until its next hand-back.
HANDOFF_TOOLS = {"opencode_call": "opencode_wait_ms", "opencode_request": "opencode_wait_ms",
                 "specialist_call": "specialist_wait_ms"}
HANDOFF_PREFIXES = {"opencode_run_": "opencode_wait_ms"}


def handoff_bucket(tool):
    """The wait bucket of a tool result that blocked on another agent's session, or None."""
    if tool in HANDOFF_TOOLS:
        return HANDOFF_TOOLS[tool]
    return next((bucket for prefix, bucket in HANDOFF_PREFIXES.items()
                 if isinstance(tool, str) and tool.startswith(prefix)), None)


# How far before the window to look for the event that opens a gap.
LOOKBACK_MS = 24 * 3600 * 1000
SESSION_COLUMNS = {"id", "source", "parent_session_id", "started_at", "ended_at", "end_reason", "model",
                   "cwd", "archived", "title", "message_count", "tool_call_count", "api_call_count",
                   "input_tokens", "output_tokens", "reasoning_tokens", "cache_read_tokens",
                   "cache_write_tokens", "estimated_cost_usd", "actual_cost_usd", "billing_provider"}
MESSAGE_COLUMNS = {"session_id", "role", "timestamp", "tool_name"}
USAGE_COLUMNS = {"session_id", "model", "billing_provider", "task", "api_call_count", "input_tokens",
                 "output_tokens", "reasoning_tokens", "cache_read_tokens", "cache_write_tokens",
                 "estimated_cost_usd", "actual_cost_usd", "first_seen", "last_seen"}
OPTIONAL_SESSION_COLUMNS = ("last_activity_at", "hidden", "git_repo_root", "git_branch", "model_config")


# --------------------------------------------------------------------------
# Profiles


def default_root():
    """The Hermes root (``~/.hermes``), also when running inside a named profile."""
    explicit = os.environ.get("HERMES_ROOT")
    if explicit:
        return Path(explicit).expanduser()
    home = os.environ.get("HERMES_HOME")
    if home:
        home = Path(home).expanduser()
        return home.parent.parent if home.parent.name == "profiles" else home
    return Path.home() / ".hermes"


def profiles(root):
    """{name: state.db path} for the default profile and every named profile."""
    root = Path(root)
    found = {}
    if (root / "state.db").is_file():
        found["default"] = root / "state.db"
    base = root / "profiles"
    if base.is_dir():
        for child in sorted(base.iterdir()):
            if PROFILE.fullmatch(child.name) and child.is_dir() and not child.is_symlink() \
                    and (child / "state.db").is_file():
                found[child.name] = child / "state.db"
    if not found:
        raise Unavailable(f"no Hermes state.db under {root}")
    return found


# --------------------------------------------------------------------------
# Request parsing


def _profiles_arg(args, available):
    value = args.get("profile")
    if value is None:
        return list(available)
    names = [value] if isinstance(value, str) else value
    if not isinstance(names, list) or not names or not all(isinstance(n, str) for n in names):
        raise ValueError("profile must be a profile name or a list of names")
    unknown = sorted(set(names) - set(available))
    if unknown:
        raise ValueError("Unknown profile: " + ", ".join(unknown) + " (have: " + ", ".join(available) + ")")
    return [n for n in available if n in names]


def parse(args, available):
    if not isinstance(args, dict):
        raise ValueError("Request must be an object")
    if set(args) - FIELDS:
        raise ValueError("Unexpected arguments: " + ", ".join(sorted(set(args) - FIELDS)))
    action = args.get("action")
    if action not in ACTIONS:
        raise ValueError("action must be one of " + ", ".join(ACTIONS))
    tz, label = common.zone(args.get("timezone"))
    q = {"action": action, "tz": tz, "timezone": label,
         "include_title": common.flag(args, "include_title"),
         "include_cost": common.flag(args, "include_cost"),
         "source": args.get("source", "auto"), "profiles": _profiles_arg(args, available)}
    if q["source"] not in SOURCES:
        raise ValueError("source must be one of " + ", ".join(SOURCES))
    if action in ("get", "children"):
        sid = args.get("session_id")
        if not isinstance(sid, str) or not SESSION_ID.fullmatch(sid):
            raise ValueError(f"{action} requires a session_id")
        extra = set(args) - {"action", "session_id", "profile", "timezone", "include_title", "include_cost",
                             "source"}
        if extra:
            raise ValueError(f"{action} takes no filters: " + ", ".join(sorted(extra)))
        q["session_id"] = sid
        return q
    if "session_id" in args:
        raise ValueError(f"{action} does not take session_id")
    q["from"], q["to"] = common.window(args, tz, required="usage" if action == "usage" else None)
    q["directory"] = common.directory(args)
    q["kind"] = args.get("kind", "root" if action == "list" else "all")
    if q["kind"] not in KINDS:
        raise ValueError("kind must be one of " + ", ".join(KINDS))
    q["platform"] = common.text(args, "platform")
    q["model"] = common.text(args, "model")
    # Archiving hides a session; it does not undo the work.
    q["archived"] = common.flag(args, "archived", action == "usage")
    if action == "list":
        q["search"] = common.text(args, "search")
        q["limit"] = common.integer(args, "limit", DEFAULT_LIMIT, 1, MAX_LIMIT)
        q["offset"] = common.integer(args, "offset", 0, 0, 10**9)
        if "group_by" in args:
            raise ValueError("group_by is only accepted for usage")
    else:
        for key in ("search", "limit", "offset"):
            if key in args:
                raise ValueError(f"{key} is only accepted for list")
        q["group_by"] = common.group_by(args, GROUPS, ["profile"])
        if q["source"] == "api":
            raise ValueError("Hermes has no windowed usage API; use source auto or db")
    return q


# --------------------------------------------------------------------------
# Normalized session records


def _num(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else 0


def _ms(seconds):
    return int(round(seconds * 1000)) if isinstance(seconds, (int, float)) and not isinstance(seconds, bool) \
        else None


def _model_name(provider, model):
    if not isinstance(model, str) or not model:
        return None
    if isinstance(provider, str) and provider and "/" not in model:
        return f"{provider}/{model}"
    return model


def _fork_markers(source, config, parent):
    """Hermes' explicit-fork test: branch, delegate and tool children are not continuations."""
    if source == "tool":
        return True
    if isinstance(config, str):
        try:
            config = json.loads(config)
        except ValueError:
            return False
    return isinstance(config, dict) and parent is not None \
        and parent in (config.get("_branched_from"), config.get("_delegate_from"))


def _record(profile, row):
    get = row.get if isinstance(row, dict) else (lambda k, d=None: row[k] if k in row.keys() else d)
    sid, started = get("id"), _ms(get("started_at"))
    if not isinstance(sid, str) or started is None:
        raise Unavailable("unexpected Hermes session shape")
    ended = _ms(get("ended_at"))
    candidates = [v for v in (_ms(get("last_active")), _ms(get("last_activity_at")), ended, started)
                  if v is not None]
    actual, estimated = get("actual_cost_usd"), get("estimated_cost_usd")
    parent = get("parent_session_id")
    return {"profile": profile, "id": sid, "platform": get("source"), "parent_id": parent,
            "end_reason": get("end_reason"), "directory": get("cwd"),
            "git_repo_root": get("git_repo_root"), "git_branch": get("git_branch"),
            "model": _model_name(get("billing_provider"), get("model")),
            "started_ms": started, "ended_ms": ended, "last_active_ms": max(candidates),
            "archived": bool(get("archived")), "hidden": bool(get("hidden")),
            "messages": _num(get("message_count")), "tool_calls": _num(get("tool_call_count")),
            "api_calls": _num(get("api_call_count")),
            "tokens": {"input": _num(get("input_tokens")), "output": _num(get("output_tokens")),
                       "reasoning": _num(get("reasoning_tokens")), "cache_read": _num(get("cache_read_tokens")),
                       "cache_write": _num(get("cache_write_tokens"))},
            "title": get("title"), "fork": _fork_markers(get("source"), get("model_config"), parent),
            "cost": _num(actual) if _num(actual) else _num(estimated)}


def _link(records):
    """Mark compression continuations and each record's conversation root, in place.

    A continuation is the same conversation after compression, so it is kind
    root; only branch, delegate and tool children (and orphans) are kind child."""
    by_id = {r["id"]: r for r in records}
    for rec in records:
        parent = by_id.get(rec["parent_id"])
        rec["continuation"] = bool(parent and parent["end_reason"] == "compression" and not rec["fork"])
    for rec in records:
        root, seen = rec, {rec["id"]}
        while root["continuation"] and root["parent_id"] not in seen:
            root = by_id[root["parent_id"]]
            seen.add(root["id"])
        rec["conversation"] = root["id"]
    return by_id


def _kind(rec):
    return "child" if rec["parent_id"] and not rec.get("continuation") else "root"


def _lineage(by_id, sid):
    """Compression chain root..tip, mirroring Hermes' get_compression_lineage."""
    rec = by_id.get(sid)
    if rec is None:
        return [sid]
    if rec["parent_id"] and rec["fork"]:
        return [sid]
    root, seen = rec, {sid}
    while root["continuation"] and root["parent_id"] not in seen:
        root = by_id[root["parent_id"]]
        seen.add(root["id"])
    chain = [root["id"]]
    while by_id[chain[-1]]["end_reason"] == "compression":
        kids = sorted((r["started_ms"], r["id"]) for r in by_id.values()
                      if r["parent_id"] == chain[-1] and r["continuation"])
        if not kids or kids[0][1] in chain:
            break
        chain.append(kids[0][1])
    return chain if sid in chain else [sid]


def _present(rec, q):
    out = {k: rec[k] for k in ("profile", "id", "platform", "parent_id", "end_reason", "directory",
                               "git_repo_root", "git_branch", "model", "archived", "messages", "tool_calls",
                               "api_calls", "tokens")}
    out.update(kind=_kind(rec), continuation=bool(rec.get("continuation")),
               started=common.iso(rec["started_ms"]), ended=common.iso(rec["ended_ms"]),
               last_active=common.iso(rec["last_active_ms"]))
    if rec.get("lineage") is not None:
        out["lineage"] = rec["lineage"]
    if q["include_title"]:
        out["title"] = rec["title"]
    if q["include_cost"]:
        out["cost"] = round(rec["cost"], 6)
    return out


def _model_matches(name, wanted):
    return isinstance(name, str) and (name == wanted or name.split("/", 1)[-1] == wanted)


def _admits(rec, q):
    """Session-level filters shared by list and usage (not the window)."""
    if q["kind"] != "all" and _kind(rec) != q["kind"]:
        return False
    if not q["archived"] and (rec["archived"] or rec["hidden"]):
        return False
    if q["platform"] and rec["platform"] != q["platform"]:
        return False
    return not (q["directory"] and not common.under(rec["directory"], q["directory"]))


def _select(records, q):
    out = []
    for rec in records:
        if q["from"] is not None and rec["last_active_ms"] < q["from"]:
            continue
        if q["to"] is not None and rec["started_ms"] >= q["to"]:
            continue
        if not _admits(rec, q):
            continue
        if q["model"] and not _model_matches(rec["model"], q["model"]):
            continue
        if q.get("search") and q["search"].casefold() not in (rec["title"] or "").casefold():
            continue
        out.append(rec)
    out.sort(key=lambda r: (-r["last_active_ms"], r["profile"], r["id"]))
    return out


# --------------------------------------------------------------------------
# Hermes' own store: SessionDB(read_only=True), one profile at a time


class StoreMissing(Unavailable):
    """Hermes is not importable here; no profile can use the store."""


class HermesStore:
    def __init__(self, path):
        self.path = Path(path)
        self.db = None

    def __enter__(self):
        try:
            from hermes_state import SessionDB
        except Exception as exc:  # plain python3, or a Hermes that moved the class
            raise StoreMissing(f"Hermes session store not importable: {exc.__class__.__name__}") from None
        try:
            self.db = SessionDB(db_path=self.path, read_only=True)
        except Exception as exc:
            raise Unavailable(f"Hermes session store could not open: {exc.__class__.__name__}") from None
        return self

    def __exit__(self, *exc):
        if self.db is not None:
            try:
                self.db.close()
            except Exception:
                pass
            self.db = None
        return False

    def records(self, profile):
        try:
            rows = self.db.list_sessions_rich(
                limit=10**7, include_children=True, include_archived=True, include_hidden=True,
                compact_rows=True, project_compression_tips=False)
        except Exception as exc:
            raise Unavailable(f"Hermes session list failed: {exc.__class__.__name__}") from None
        return [_record(profile, row) for row in rows]

    def lineage(self, sid, by_id):
        try:
            return self.db.get_compression_lineage(sid)
        except Exception:
            return _lineage(by_id, sid)


# --------------------------------------------------------------------------
# Guarded read-only SQLite: explicit scalar columns only


class Snapshot:
    """One profile database, mode=ro, query_only, one read transaction."""

    def __init__(self, path):
        self.path = str(path)

    def __enter__(self):
        try:
            uri = "file:" + urllib.parse.quote(self.path) + "?mode=ro"
            self.conn = sqlite3.connect(uri, uri=True, timeout=5, isolation_level=None)
            self.conn.execute("PRAGMA query_only = ON")
            self.conn.execute("BEGIN")
            self.columns = {}
            for table, required in (("sessions", SESSION_COLUMNS), ("messages", MESSAGE_COLUMNS),
                                    ("session_model_usage", USAGE_COLUMNS)):
                have = {row[1] for row in self.conn.execute(f"PRAGMA table_info({table})")}
                missing = sorted(required - have)
                if missing:
                    raise Unavailable(f"unsupported Hermes schema: {table} lacks {', '.join(missing)}")
                self.columns[table] = have
        except sqlite3.Error as exc:
            self.__exit__()
            raise Unavailable(f"Hermes database not readable: {exc.__class__.__name__}") from None
        except Unavailable:
            self.__exit__()
            raise
        return self

    def __exit__(self, *exc):
        conn = getattr(self, "conn", None)
        if conn is not None:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            conn.close()
            self.conn = None
        return False

    def records(self, profile):
        optional = [c for c in OPTIONAL_SESSION_COLUMNS if c in self.columns["sessions"]]
        self.conn.row_factory = sqlite3.Row
        try:
            rows = list(self.conn.execute(
                f"SELECT {', '.join(sorted(SESSION_COLUMNS) + optional)} FROM sessions"))
        finally:
            self.conn.row_factory = None
        return [_record(profile, row) for row in rows]

    def lineage(self, sid, by_id):
        return _lineage(by_id, sid)

    def events(self, lo_ms, hi_ms):
        """(session_id, timestamp, role, tool_name) per agent-loop event; never content.

        Reads a day either side of the window: before, for the event that opens a
        gap ending inside it; after, for the event that closes a gap still open at
        its end."""
        synthetic = " AND _compressed_summary = 0" if "_compressed_summary" in self.columns["messages"] else ""
        roles = ",".join("?" * len(EVENT_ROLES))
        return self.conn.execute(
            "SELECT DISTINCT session_id, timestamp, role, tool_name FROM messages "
            f"WHERE timestamp >= ? AND timestamp < ? AND role IN ({roles}){synthetic}",
            ((lo_ms - LOOKBACK_MS) / 1000, (hi_ms + LOOKBACK_MS) / 1000, *EVENT_ROLES))

    def usage(self, lo_ms, hi_ms):
        return self.conn.execute(
            "SELECT session_id, model, billing_provider, task, api_call_count, input_tokens, output_tokens, "
            "reasoning_tokens, cache_read_tokens, cache_write_tokens, actual_cost_usd, estimated_cost_usd, "
            "first_seen, last_seen FROM session_model_usage "
            "WHERE last_seen IS NULL OR first_seen IS NULL OR (last_seen >= ? AND first_seen < ?)",
            (lo_ms / 1000, hi_ms / 1000))


# --------------------------------------------------------------------------
# Reading profiles, one failure at a time


def _unreadable(name, exc):
    return {"code": "profile-unreadable", "profile": name, "detail": str(exc),
            "effect": "this profile is missing from the answer", "partial": True}


def _inventory(q, paths, store_factory):
    """{profile: (by_id, reader_lineage)} for list/get/children, the routes used, and diagnostics."""
    out, routes, diagnostics = {}, set(), []
    use_store = q["source"] in ("auto", "api")
    for name in q["profiles"]:
        if use_store:
            try:
                with store_factory(paths[name]) as store:
                    records = store.records(name)
                    by_id = _link(records)
                    lineage = store.lineage(q["session_id"], by_id) \
                        if q.get("session_id") in by_id else None
                out[name] = (by_id, lineage)
                routes.add("api")
                continue
            except Unavailable as exc:
                if q["source"] == "api":
                    raise
                if isinstance(exc, StoreMissing):
                    use_store = False
                    diagnostics.append({"code": "api-unavailable", "detail": str(exc),
                                        "effect": "answered from the profile databases"})
                else:
                    diagnostics.append({"code": "api-unavailable", "profile": name, "detail": str(exc),
                                        "effect": "answered from the profile database"})
        try:
            with Snapshot(paths[name]) as snap:
                by_id = _link(snap.records(name))
            lineage = _lineage(by_id, q["session_id"]) if q.get("session_id") in by_id else None
            out[name] = (by_id, lineage)
            routes.add("db")
        except (Unavailable, sqlite3.Error) as exc:
            diagnostics.append(_unreadable(name, exc))
    if not out:
        raise Unavailable("no Hermes profile database was readable")
    return out, routes, diagnostics


# --------------------------------------------------------------------------
# Usage


def _usage(paths, q):
    lo, hi = q["from"], q["to"]
    groups, diagnostics, read = {}, [], 0
    lookback_misses = crossing = crossing_output = untimed = 0

    def bucket(key):
        return {"key": key, "sessions": set(), "api_calls": 0, "active_ms": 0, "wait_ms": 0,
                "opencode_wait_ms": 0, "specialist_wait_ms": 0, "intervals": [],
                "tokens": dict.fromkeys(TOKEN_KEYS, 0), "cost": 0.0}

    totals = bucket({})

    def add(key, sid, **values):
        key = {g: key[g] for g in q["group_by"]}
        name = json.dumps(key, sort_keys=True)
        for b in (groups.setdefault(name, bucket(key)), totals):
            b["sessions"].add(sid)
            for field, value in values.items():
                if field == "intervals":
                    b["intervals"].extend(value)
                elif field == "tokens":
                    for k, v in value.items():
                        b["tokens"][k] += v
                else:
                    b[field] += value

    for profile in q["profiles"]:
        try:
            with Snapshot(paths[profile]) as snap:
                by_id = _link(snap.records(profile))
                events = list(snap.events(lo, hi))
                usage_rows = list(snap.usage(lo, hi))
        except (Unavailable, sqlite3.Error) as exc:
            diagnostics.append(_unreadable(profile, exc))
            continue
        read += 1

        def key_for(rec, model, task, anchor):
            return {"profile": profile, "platform": rec["platform"], "model": model, "task": task,
                    "directory": rec["directory"], "kind": _kind(rec),
                    "day": common.local_day(anchor, q["tz"])}

        # Activity: gaps between consecutive agent-loop events of one conversation.
        # Compression copies the kept tail into the continuation with its original
        # timestamps, so events are merged per conversation and each counted once,
        # on the earliest session that holds it.
        timeline = []
        for sid, ts, role, tool in events:
            rec, at = by_id.get(sid), _ms(ts)
            if rec is None or at is None:
                continue
            timeline.append((rec["conversation"], at, role, tool or "", rec["started_ms"], sid))
        timeline.sort()
        previous, seen = {}, set()
        for conversation, at, role, tool, _, sid in timeline:
            if (conversation, at, role, tool) in seen:
                continue
            seen.add((conversation, at, role, tool))
            prev = previous.get(conversation)
            previous[conversation] = at
            rec = by_id[sid]
            if role == "user" or not _admits(rec, q):
                continue
            if q["model"] and not _model_matches(rec["model"], q["model"]):
                continue
            if prev is None:
                if lo <= at < hi:
                    lookback_misses += 1
                continue
            span = common.clip(prev, at, lo, hi)
            if span is None:
                continue
            key = key_for(rec, rec["model"], "main", span[0])
            length = span[1] - span[0]
            if tool in WAIT_TOOLS:
                add(key, sid, wait_ms=length)
                continue
            values = {"active_ms": length, "intervals": [span]}
            wait_field = handoff_bucket(tool)
            if wait_field:
                values[wait_field] = length
            add(key, sid, **values)

        # Tokens: model-usage rows that lie wholly inside the window.
        for row in usage_rows:
            (sid, model, provider, task, calls, t_in, t_out, t_reason, t_read, t_write,
             actual, estimated, first, last) = row
            rec = by_id.get(sid)
            if rec is None or not _admits(rec, q):
                continue
            name = _model_name(provider, model)
            if q["model"] and not _model_matches(name, q["model"]):
                continue
            first_ms, last_ms = _ms(first), _ms(last)
            if first_ms is None or last_ms is None:
                untimed += 1
                continue
            if not (lo <= first_ms and last_ms < hi):
                crossing += 1
                crossing_output += _num(t_out)
                continue
            add(key_for(rec, name, task or "main", first_ms), sid, api_calls=_num(calls),
                tokens={"input": _num(t_in), "output": _num(t_out), "reasoning": _num(t_reason),
                        "cache_read": _num(t_read), "cache_write": _num(t_write)},
                cost=_num(actual) if _num(actual) else _num(estimated))

    if not read:
        raise Unavailable("no Hermes profile database was readable")

    def finish(b):
        out = {"key": b["key"], "sessions": len(b["sessions"]), "api_calls": b["api_calls"],
               "active_seconds": round(b["active_ms"] / 1000, 1),
               "active_union_seconds": round(common.union_ms(b["intervals"]) / 1000, 1),
               "question_wait_seconds": round(b["wait_ms"] / 1000, 1),
               "opencode_wait_seconds": round(b["opencode_wait_ms"] / 1000, 1),
               "specialist_wait_seconds": round(b["specialist_wait_ms"] / 1000, 1),
               "tokens": b["tokens"]}
        if q["include_cost"]:
            out["cost"] = round(b["cost"], 6)
        if not b["key"]:
            del out["key"]
            if q.get("keep_intervals"):
                out["intervals_ms"] = common.merged(b["intervals"])
        return out

    if crossing:
        diagnostics.append({"code": "usage-crosses-window", "count": crossing, "output_tokens": crossing_output,
                            "effect": "model usage recorded across a window edge is not split; excluded "
                                      "from tokens and api_calls", "partial": True})
    if untimed:
        diagnostics.append({"code": "usage-without-time", "count": untimed, "effect": "excluded", "partial": True})
    if lookback_misses:
        diagnostics.append({"code": "gap-before-lookback", "count": lookback_misses,
                            "effect": "activity whose previous event is over a day old is not counted",
                            "partial": True})
    ordered = sorted(groups.values(), key=lambda b: (-b["active_ms"], json.dumps(b["key"], sort_keys=True)))
    return {"profiles": q["profiles"], "totals": finish(totals), "groups": [finish(b) for b in ordered]}, \
        diagnostics


# --------------------------------------------------------------------------
# Dispatch


def _answer(q, paths, store_factory):
    inventory, routes, diagnostics = _inventory(q, paths, store_factory)
    source = "api" if routes == {"api"} else "db" if routes == {"db"} else "api+db"
    if q["action"] == "list":
        records = [rec for by_id, _ in inventory.values() for rec in by_id.values()]
        selected = _select(records, q)
        page = selected[q["offset"]:q["offset"] + q["limit"]]
        after = q["offset"] + len(page)
        return {"profiles": q["profiles"], "total": len(selected), "offset": q["offset"],
                "next_offset": after if after < len(selected) else None,
                "sessions": [_present(r, q) for r in page]}, source, diagnostics
    for by_id, lineage in inventory.values():
        rec = by_id.get(q["session_id"])
        if rec is None:
            continue
        if q["action"] == "get":
            return {"session": _present({**rec, "lineage": lineage}, q)}, source, diagnostics
        children = sorted((r for r in by_id.values() if r["parent_id"] == q["session_id"]),
                          key=lambda r: (r["started_ms"], r["id"]))
        return {"sessions": [_present(r, q) for r in children]}, source, diagnostics
    raise ValueError(f"Session {q['session_id']} not found")


def run(args, *, root=None, store_factory=HermesStore, keep_intervals=False):
    """Answer one request. Raises ValueError for caller mistakes, Unavailable for sources.

    keep_intervals (callers in code only) adds the merged activity intervals to
    usage totals, so a cross-tool summary can remove overlap between tools."""
    paths = profiles(root or default_root())
    q = parse(args, list(paths))
    q["keep_intervals"] = keep_intervals
    window = common.window_view(q.get("from"), q.get("to"), q["timezone"])
    if q["action"] == "usage":
        body, diagnostics = _usage(paths, q)
        return common.envelope(q["action"], window, "db", diagnostics, body)
    body, source, diagnostics = _answer(q, paths, store_factory)
    return common.envelope(q["action"], window, source, diagnostics, body)
