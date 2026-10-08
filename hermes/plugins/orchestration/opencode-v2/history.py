"""Read-only OpenCode 2 session inventory: list, get, children and usage.

The official HTTP API of the person's shared background service comes first,
reached through `opencode api` (see api.py). The guarded read-only SQLite route
is used only where the API has no equivalent — message-level usage and
activity, whose API form carries message content — or as a disclosed fallback
when the service is unavailable. Message content is never returned. Titles and
costs are withheld unless the caller asks for them.

The database is OpenCode 2's (`session_v2` / `session_message`). Data imported
from OpenCode 1 keeps its V1 tables beside them, and their step times win for
the imported messages (see Snapshot).

Stdlib only: cron scripts run this file as a CLI, the Hermes tool imports it.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import urllib.parse


def _load(name, path):
    # Load siblings by path so this file stays runnable as a plain CLI (no package, no Hermes).
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


HERE = Path(__file__).resolve().parent
common = _load("hermes_session_history_common", HERE.parent / "session-history" / "common.py")
api = _load("hermes_opencode2_api", HERE / "api.py")
Unavailable = common.Unavailable


ACTIONS = ("list", "get", "children", "usage")
KINDS = ("root", "child", "all")
GROUPS = ("model", "agent", "directory", "kind", "day")
SOURCES = ("auto", "api", "db")
FIELDS = {"action", "session_id", "from", "to", "days", "timezone", "directory", "kind", "agent", "model",
          "archived", "search", "include_title", "include_cost", "limit", "offset", "group_by", "source"}
SESSION_ID = re.compile(r"ses_[A-Za-z0-9_-]{1,64}\Z")
DEFAULT_LIMIT = 50
MAX_LIMIT = 200
TOKEN_KEYS = ("input", "output", "reasoning", "cache_read", "cache_write")
SESSION_COLUMNS = {"id", "project_id", "parent_id", "directory", "title", "version", "time_created",
                   "time_updated", "time_archived", "agent", "model", "cost", "tokens_input",
                   "tokens_output", "tokens_reasoning", "tokens_cache_read", "tokens_cache_write"}
MESSAGE_COLUMNS = {"id", "session_id", "time_created", "data"}
PART_COLUMNS = {"session_id", "time_created", "data"}
V2_MESSAGE_COLUMNS = {"id", "session_id", "type", "time_created", "data"}
# Sessions come newest-updated first in cursor pages; stop well before any real
# store could loop forever on a broken cursor.
API_PAGE = 200
API_MAX_PAGES = 1000
# Tools whose run time is the model waiting on a person, not working. A step
# (assistant message) spans its tool calls, so without this a question left
# unanswered overnight would count as hours of activity.
WAIT_TOOLS = ("question",)


class ApiNotFound(Unavailable):
    """The API has no such session. Auto mode confirms against the database."""


def child_env(extra=None):
    return api.child_env(extra)


def _client(method, route):
    try:
        return api.call(method, route)
    except api.ApiError as exc:
        if exc.status == 404:
            raise LookupError(route) from None
        raise Unavailable(f"API {route.split('?')[0]} returned HTTP {exc.status}") from None
    except api.Unavailable as exc:
        raise Unavailable(str(exc)) from None


# --------------------------------------------------------------------------
# Request parsing


def parse(args):
    """Validate a request dict and return the normalized query."""
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
         "source": args.get("source", "auto")}
    if q["source"] not in SOURCES:
        raise ValueError("source must be one of " + ", ".join(SOURCES))
    if action in ("get", "children"):
        sid = args.get("session_id")
        if not isinstance(sid, str) or not SESSION_ID.fullmatch(sid):
            raise ValueError(f"{action} requires a session_id like ses_…")
        extra = set(args) - {"action", "session_id", "timezone", "include_title", "include_cost", "source"}
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
    q["agent"] = common.text(args, "agent")
    q["model"] = common.text(args, "model")
    # Archiving hides a session in the UI; it does not undo the work, so usage
    # counts archived sessions unless told otherwise.
    q["archived"] = args.get("archived", action == "usage")
    if type(q["archived"]) is not bool:
        raise ValueError("archived must be boolean")
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
        q["group_by"] = common.group_by(args, GROUPS, ["model"])
        if q["source"] == "api":
            raise ValueError("usage needs message-level timing and tokens, which the API only returns "
                             "with message content; use source auto or db")
    return q


# --------------------------------------------------------------------------
# Normalized session records


def _num(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else 0


def _model_name(provider, model):
    return f"{provider}/{model}" if isinstance(provider, str) and isinstance(model, str) else None


def _record(sid, parent, project, directory, title, version, created, updated, archived,
            agent, model, cost, tokens, changes):
    if not isinstance(sid, str) or not sid.startswith("ses") or type(created) is not int \
            or type(updated) is not int:
        raise Unavailable("unexpected session shape")
    model = model if isinstance(model, dict) else {}
    return {"id": sid, "parent_id": parent, "project_id": project, "directory": directory,
            "title": title, "version": version, "created_ms": created, "updated_ms": updated,
            "archived_ms": archived if isinstance(archived, (int, float)) else None,
            "agent": agent if isinstance(agent, str) else None,
            "model": _model_name(model.get("providerID"), model.get("id")),
            "variant": model.get("variant") if isinstance(model.get("variant"), str) else None,
            "cost": _num(cost), "tokens": {k: _num(tokens.get(k)) for k in TOKEN_KEYS},
            "changes": changes}


def _from_api(item):
    if not isinstance(item, dict) or not isinstance(item.get("time"), dict):
        raise Unavailable("unexpected API session shape")
    t, tokens = item["time"], item.get("tokens") or {}
    cache = tokens.get("cache") or {}
    location = item.get("location") if isinstance(item.get("location"), dict) else {}
    return _record(item.get("id"), item.get("parentID"), item.get("projectID"), location.get("directory"),
                   item.get("title"), item.get("version"), t.get("created"), t.get("updated"),
                   t.get("archived"), item.get("agent"), item.get("model"), item.get("cost"),
                   {"input": tokens.get("input"), "output": tokens.get("output"),
                    "reasoning": tokens.get("reasoning"), "cache_read": cache.get("read"),
                    "cache_write": cache.get("write")}, None)


_iso = common.iso


def _present(rec, q):
    out = {"id": rec["id"], "parent_id": rec["parent_id"], "project_id": rec["project_id"],
           "directory": rec["directory"], "agent": rec["agent"], "model": rec["model"],
           "variant": rec["variant"], "version": rec["version"], "created": _iso(rec["created_ms"]),
           "updated": _iso(rec["updated_ms"]), "archived": _iso(rec["archived_ms"]),
           "tokens": rec["tokens"], "changes": rec["changes"]}
    if q["include_title"]:
        out["title"] = rec["title"]
    if q["include_cost"]:
        out["cost"] = rec["cost"]
    return out


_under = common.under


def _model_matches(name, wanted):
    return isinstance(name, str) and (name == wanted or name.split("/", 1)[-1] == wanted)


def _kind_matches(parent, kind):
    return kind == "all" or (kind == "root") == (parent is None)


def _select(records, q):
    out = []
    for rec in records:
        if q["from"] is not None and rec["updated_ms"] < q["from"]:
            continue
        if q["to"] is not None and rec["created_ms"] >= q["to"]:
            continue
        if not _kind_matches(rec["parent_id"], q["kind"]):
            continue
        if not q["archived"] and rec["archived_ms"] is not None:
            continue
        if q["directory"] and not _under(rec["directory"], q["directory"]):
            continue
        if q["agent"] and rec["agent"] != q["agent"]:
            continue
        if q["model"] and not _model_matches(rec["model"], q["model"]):
            continue
        if q.get("search") and q["search"].casefold() not in (rec["title"] or "").casefold():
            continue
        out.append(rec)
    out.sort(key=lambda r: (-r["updated_ms"], r["id"]))
    return out


# --------------------------------------------------------------------------
# Official API on the shared service


def _api_pages(client, params, stop_before=None):
    """`/api/session` pages, newest-updated first, until the cursor ends or a
    session was last updated before `stop_before` (later pages only get older)."""
    out, cursor = [], None
    for _ in range(API_MAX_PAGES):
        query = {**params, "limit": API_PAGE, "order": "desc", **({"cursor": cursor} if cursor else {})}
        page = client("get", "/api/session?" + urllib.parse.urlencode(query))
        if not isinstance(page, dict) or not isinstance(page.get("data"), list) \
                or not isinstance(page.get("cursor"), dict):
            raise Unavailable("unexpected API list shape")
        for item in page["data"]:
            rec = _from_api(item)
            if stop_before is not None and rec["updated_ms"] < stop_before:
                return out
            out.append(rec)
        cursor = page["cursor"].get("next")
        if not cursor or not page["data"]:
            return out
    raise Unavailable("API list did not end; it may be truncated")


def _api_list(client, q):
    try:
        return _api_pages(client, {**({"parentID": "null"} if q["kind"] == "root" else {}),
                                   **({"search": q["search"]} if q.get("search") else {})},
                          stop_before=q["from"])
    except LookupError:
        raise Unavailable("API has no session list") from None


def _api_get(client, sid):
    try:
        body = client("get", f"/api/session/{sid}")
    except LookupError:
        raise ApiNotFound(f"session {sid} not found via API") from None
    return _from_api(body.get("data") if isinstance(body, dict) else None)


def _api_children(client, sid):
    _api_get(client, sid)
    try:
        return _api_pages(client, {"parentID": sid})
    except LookupError:
        raise Unavailable("API has no session list") from None


def _api_version(client):
    try:
        info = client("get", "/api/info")
    except LookupError:
        return None
    return info.get("version") if isinstance(info, dict) and isinstance(info.get("version"), str) else None


# --------------------------------------------------------------------------
# Guarded read-only SQLite: one snapshot, explicit scalar columns only


def db_path():
    command = ["opencode", "debug", "paths", "db"]
    label = " ".join(command)
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=30,
                              stdin=subprocess.DEVNULL, env=child_env())
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise Unavailable(f"{label} failed: {exc.__class__.__name__}") from None
    lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    if proc.returncode or not lines or not os.path.isabs(lines[-1]) or not os.path.isfile(lines[-1]):
        raise Unavailable(f"{label} did not name an existing database")
    return lines[-1]


class Snapshot:
    """One read-only snapshot of the OpenCode 2 database."""

    def __init__(self, path):
        self.path = path

    def _columns(self, table):
        return {row[1] for row in self.conn.execute(f"PRAGMA table_info({table})")}

    def __enter__(self):
        try:
            uri = "file:" + urllib.parse.quote(self.path) + "?mode=ro"
            self.conn = sqlite3.connect(uri, uri=True, timeout=5, isolation_level=None)
            self.conn.execute("PRAGMA query_only = ON")
            self.conn.execute("BEGIN")
            self.tables = {row[0] for row in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'")}
            if "session_v2" not in self.tables:
                raise Unavailable("database has no OpenCode 2 tables")
            for table, required in (("session_v2", SESSION_COLUMNS), ("session_message", V2_MESSAGE_COLUMNS)):
                missing = sorted(required - self._columns(table)) if table in self.tables else ["(table)"]
                if missing:
                    raise Unavailable(f"unsupported database schema: {table} lacks {', '.join(missing)}")
            # OpenCode 2 imports V1 messages with time.completed set to the V1
            # row's last update (a later revert, fork or compaction), and their
            # tool times likewise, so a V1 message's own record wins while the
            # V1 tables remain (measured on 2.0.23: ~11% of imported steps).
            self.legacy = ("message" in self.tables and "part" in self.tables
                           and MESSAGE_COLUMNS <= self._columns("message")
                           and PART_COLUMNS <= self._columns("part"))
        except sqlite3.Error as exc:
            self.__exit__()
            raise Unavailable(f"database not readable: {exc.__class__.__name__}") from None
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

    def sessions(self, where="1", params=()):
        rows = self.conn.execute(
            "SELECT id, parent_id, project_id, directory, title, version, time_created, time_updated, "
            "time_archived, agent, model, cost, tokens_input, tokens_output, tokens_reasoning, "
            f"tokens_cache_read, tokens_cache_write FROM session_v2 WHERE {where}", params)
        out = []
        for row in rows:
            try:
                model = json.loads(row[10]) if isinstance(row[10], str) else None
            except ValueError:
                model = None
            out.append(_record(row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8],
                               row[9], model, row[11], dict(zip(TOKEN_KEYS, row[12:17])), None))
        return out

    def messages(self, session_ids, to_ms):
        """Assistant-message scalars only; never content, parts or raw JSON."""
        out = []
        ids = list(session_ids)
        completed = ("coalesce(json_extract(o.data, '$.time.completed'), json_extract(m.data, '$.time.completed'))"
                     if self.legacy else "json_extract(m.data, '$.time.completed')")
        join = "LEFT JOIN message AS o ON o.id = m.id " if self.legacy else ""
        for start in range(0, len(ids), 500):
            chunk = ids[start:start + 500]
            marks = ",".join("?" * len(chunk))
            out.extend(self.conn.execute(
                "SELECT m.session_id, json_extract(m.data, '$.model.providerID'), "
                "json_extract(m.data, '$.model.id'), json_extract(m.data, '$.agent'), "
                f"json_extract(m.data, '$.time.created'), {completed}, "
                "json_extract(m.data, '$.tokens.input'), json_extract(m.data, '$.tokens.output'), "
                "json_extract(m.data, '$.tokens.reasoning'), json_extract(m.data, '$.tokens.cache.read'), "
                "json_extract(m.data, '$.tokens.cache.write'), json_extract(m.data, '$.cost') "
                f"FROM session_message AS m {join}WHERE m.session_id IN ({marks}) AND m.time_created < ? "
                "AND m.type = 'assistant'", (*chunk, to_ms)))
        return out

    def waits(self, session_ids, to_ms):
        """Start/end of wait-tool calls per session; never their input or output."""
        out = {}
        ids = list(session_ids)
        tools = ",".join("?" * len(WAIT_TOOLS))
        # Tool calls are entries of the assistant message's content array; only
        # their type, name and times are extracted. Imported V1 messages take
        # their waits from the V1 parts instead.
        queries = [("SELECT m.session_id, coalesce(json_extract(c.value, '$.time.ran'), "
                    "json_extract(c.value, '$.time.created')), json_extract(c.value, '$.time.completed') "
                    "FROM session_message AS m, json_each(m.data, '$.content') AS c "
                    "WHERE m.session_id IN ({marks}) AND m.time_created < ? AND m.type = 'assistant' "
                    "AND json_extract(c.value, '$.type') = 'tool' "
                    f"AND json_extract(c.value, '$.name') IN ({tools})"
                    + (" AND NOT EXISTS (SELECT 1 FROM message AS o WHERE o.id = m.id)" if self.legacy else ""))]
        if self.legacy:
            queries.append("SELECT session_id, json_extract(data, '$.state.time.start'), "
                           "json_extract(data, '$.state.time.end') FROM part "
                           "WHERE session_id IN ({marks}) AND time_created < ? "
                           "AND json_extract(data, '$.type') = 'tool' "
                           f"AND json_extract(data, '$.tool') IN ({tools})")
        for start in range(0, len(ids), 500):
            chunk = ids[start:start + 500]
            marks = ",".join("?" * len(chunk))
            for query in queries:
                for sid, begin, end in self.conn.execute(query.format(marks=marks), (*chunk, to_ms, *WAIT_TOOLS)):
                    if type(begin) is int and type(end) is int and end > begin:
                        out.setdefault(sid, []).append((begin, end))
        for spans in out.values():
            spans.sort()
        return out


def _db_window_sessions(snap, q):
    where, params = ["1"], []
    if q["from"] is not None:
        where.append("time_updated >= ?")
        params.append(q["from"])
    if q["to"] is not None:
        where.append("time_created < ?")
        params.append(q["to"])
    return snap.sessions(" AND ".join(where), params)


# --------------------------------------------------------------------------
# Usage: message-level tokens and activity intervals


_union_ms = common.union_ms
_subtract = common.subtract


def _usage(snap, q):
    lo, hi = q["from"], q["to"]
    sessions = {}
    for rec in _db_window_sessions(snap, q):
        if not _kind_matches(rec["parent_id"], q["kind"]):
            continue
        if not q["archived"] and rec["archived_ms"] is not None:
            continue
        if q["directory"] and not _under(rec["directory"], q["directory"]):
            continue
        sessions[rec["id"]] = rec
    waits = snap.waits(sessions, hi)
    groups = {}
    incomplete = malformed = 0

    def bucket(key):
        return {"key": key, "sessions": set(), "messages": 0, "active_ms": 0, "wait_ms": 0,
                "intervals": [], "tokens": dict.fromkeys(TOKEN_KEYS, 0), "cost": 0.0}

    totals = bucket({})
    for row in snap.messages(sessions, hi):
        sid, provider, model_id, agent, created, completed = row[:6]
        if type(created) is not int or (completed is not None and type(completed) is not int):
            malformed += 1
            continue
        model = _model_name(provider, model_id)
        if q["agent"] and agent != q["agent"]:
            continue
        if q["model"] and not _model_matches(model, q["model"]):
            continue
        counted = lo <= created < hi
        interval = None
        if completed is None:
            if created >= lo:
                incomplete += 1
        elif completed > lo and created < hi:
            interval = (max(created, lo), min(completed, hi))
        if not counted and interval is None:
            continue
        pieces, waited = _subtract(interval, waits.get(sid, ())) if interval else ([], 0)
        rec = sessions[sid]
        anchor = max(created, lo)
        key = {"model": model, "agent": agent if isinstance(agent, str) else None,
               "directory": rec["directory"], "kind": "child" if rec["parent_id"] else "root",
               "day": common.local_day(anchor, q["tz"])}
        key = {g: key[g] for g in q["group_by"]}
        name = json.dumps(key, sort_keys=True)
        for b in (groups.setdefault(name, bucket(key)), totals):
            b["sessions"].add(sid)
            if counted:
                b["messages"] += 1
                for k, v in zip(TOKEN_KEYS, row[6:11]):
                    b["tokens"][k] += _num(v)
                b["cost"] += _num(row[11])
            b["active_ms"] += sum(stop - begin for begin, stop in pieces)
            b["wait_ms"] += waited
            b["intervals"].extend(pieces)

    def finish(b):
        out = {"key": b["key"], "sessions": len(b["sessions"]), "messages": b["messages"],
               "active_seconds": round(b["active_ms"] / 1000, 1),
               "active_union_seconds": round(_union_ms(b["intervals"]) / 1000, 1),
               "question_wait_seconds": round(b["wait_ms"] / 1000, 1),
               "tokens": b["tokens"]}
        if q["include_cost"]:
            out["cost"] = round(b["cost"], 6)
        if not b["key"]:
            del out["key"]
            if q.get("keep_intervals"):
                out["intervals_ms"] = common.merged(b["intervals"])
        return out

    ordered = sorted(groups.values(), key=lambda b: (-b["active_ms"], json.dumps(b["key"], sort_keys=True)))
    diagnostics = []
    if incomplete:
        diagnostics.append({"code": "messages-without-completion", "count": incomplete,
                            "effect": "their activity is not counted", "partial": True})
    if malformed:
        diagnostics.append({"code": "messages-malformed-time", "count": malformed,
                            "effect": "skipped", "partial": True})
    return {"totals": finish(totals), "groups": [finish(b) for b in ordered]}, diagnostics


# --------------------------------------------------------------------------
# Dispatch


def _page(records, q):
    selected = _select(records, q)
    page = selected[q["offset"]:q["offset"] + q["limit"]]
    after = q["offset"] + len(page)
    return {"total": len(selected), "offset": q["offset"],
            "next_offset": after if after < len(selected) else None,
            "sessions": [_present(r, q) for r in page]}


def _via_api(q, client):
    if q["action"] == "list":
        body = _page(_api_list(client, q), q)
    elif q["action"] == "get":
        body = {"session": _present(_api_get(client, q["session_id"]), q)}
    else:
        children = sorted(_api_children(client, q["session_id"]), key=lambda r: (r["created_ms"], r["id"]))
        body = {"sessions": [_present(r, q) for r in children]}
    return body, _api_version(client)


def _via_db(q, path_factory):
    try:
        with Snapshot(path_factory()) as snap:
            if q["action"] == "usage":
                return _usage(snap, q)
            if q["action"] == "list":
                return _page(_db_window_sessions(snap, q), q), []
            found = snap.sessions("id = ?", (q["session_id"],))
            if not found:
                raise ValueError(f"Session {q['session_id']} not found")
            if q["action"] == "get":
                return {"session": _present(found[0], q)}, []
            children = sorted(snap.sessions("parent_id = ?", (q["session_id"],)),
                              key=lambda r: (r["created_ms"], r["id"]))
            return {"sessions": [_present(r, q) for r in children]}, []
    except sqlite3.Error as exc:
        raise Unavailable(f"database read failed: {exc.__class__.__name__}") from None


def run(args, *, client=_client, path_factory=db_path, keep_intervals=False):
    """Answer one request. Raises ValueError for caller mistakes, Unavailable for sources.

    keep_intervals (callers in code only) adds the merged activity intervals to
    usage totals, so a cross-tool summary can remove overlap between tools."""
    q = parse(args)
    q["keep_intervals"] = keep_intervals
    diagnostics = []
    window = common.window_view(q.get("from"), q.get("to"), q["timezone"])
    if q["action"] != "usage" and q["source"] in ("auto", "api"):
        try:
            body, version = _via_api(q, client)
            return common.envelope(q["action"], window, "api", diagnostics, body, opencode_version=version)
        except Unavailable as exc:
            if q["source"] == "api":
                if isinstance(exc, ApiNotFound):
                    raise ValueError(f"Session {q['session_id']} not found") from None
                raise
            diagnostics.append({"code": "api-unavailable", "detail": str(exc),
                                "effect": "answered from the local database"})
    body, notes = _via_db(q, path_factory)
    diagnostics.extend(notes)
    return common.envelope(q["action"], window, "db", diagnostics, body, opencode_version=None)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="opencode-history", description=__doc__.splitlines()[0])
    parser.add_argument("action", choices=ACTIONS)
    parser.add_argument("session_id", nargs="?")
    for flag in ("from", "to", "timezone", "directory", "kind", "agent", "model", "search"):
        parser.add_argument(f"--{flag}")
    parser.add_argument("--days", type=int, help="last N local days ending today")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--offset", type=int)
    parser.add_argument("--group-by", help="comma-separated: " + ",".join(GROUPS))
    parser.add_argument("--source", choices=SOURCES)
    for flag in ("archived", "include-title", "include-cost"):
        parser.add_argument(f"--{flag}", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    ns = parser.parse_args(argv)
    args = {"action": ns.action}
    if ns.session_id is not None:
        args["session_id"] = ns.session_id
    for key in ("from", "to", "days", "timezone", "directory", "kind", "agent", "model", "search", "limit",
                "offset", "source"):
        if getattr(ns, key) is not None:
            args[key] = getattr(ns, key)
    for key in ("archived", "include_title", "include_cost"):
        if getattr(ns, key):
            args[key] = True
    if ns.group_by:
        args["group_by"] = [g.strip() for g in ns.group_by.split(",") if g.strip()]
    try:
        result, code = run(args), 0
    except (ValueError, Unavailable) as exc:
        result, code = {"error": str(exc)}, 1
    except Exception as exc:  # a cron caller gets JSON, never a traceback
        result, code = {"error": f"unexpected failure: {exc.__class__.__name__}"}, 1
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if ns.pretty else None)
    sys.stdout.write("\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
