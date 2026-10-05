import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import stat
import sys
import time

import pytest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("opencode_history_test", ROOT / "history.py")
history = importlib.util.module_from_spec(spec)
spec.loader.exec_module(history)

H = 3600 * 1000
FROM = 1_790_000_000_000          # window [FROM, TO)
TO = FROM + 24 * H
SECRET = "SECRET-CONTENT-MARKER"


def _schema(conn, *, parts=True, drop_session_column=None):
    session_cols = ["id text primary key", "project_id text", "parent_id text", "slug text", "directory text",
                    "title text", "version text", "time_created integer", "time_updated integer",
                    "time_archived integer", "agent text", "model text", "cost real",
                    "tokens_input integer", "tokens_output integer", "tokens_reasoning integer",
                    "tokens_cache_read integer", "tokens_cache_write integer"]
    if drop_session_column:
        session_cols = [c for c in session_cols if not c.startswith(drop_session_column + " ")]
    conn.execute(f"create table session ({', '.join(session_cols)})")
    conn.execute("create table message (id text primary key, session_id text, time_created integer, "
                 "time_updated integer, data text)")
    if parts:
        conn.execute("create table part (id text primary key, message_id text, session_id text, "
                     "time_created integer, time_updated integer, data text)")


def _session(conn, sid, created, updated, *, parent=None, directory="/w/a", archived=None, agent="build",
             model=("anthropic", "opus")):
    conn.execute("insert into session (id, project_id, parent_id, slug, directory, title, version, time_created, "
                 "time_updated, time_archived, agent, model, cost, tokens_input, tokens_output, tokens_reasoning, "
                 "tokens_cache_read, tokens_cache_write) values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                 (sid, "proj", parent, "slug", directory, f"TITLE {sid} {SECRET}", "1.0", created, updated,
                  archived, agent, json.dumps({"id": model[1], "providerID": model[0]}), 1.5, 1, 2, 3, 4, 5))


def _step(conn, mid, sid, created, completed, *, model=("anthropic", "opus"), agent="build", output=10):
    data = {"role": "assistant", "providerID": model[0], "modelID": model[1], "agent": agent,
            "time": {"created": created, **({"completed": completed} if completed is not None else {})},
            "tokens": {"input": 1, "output": output, "reasoning": 2, "cache": {"read": 3, "write": 4}},
            "cost": 0.25, "text": SECRET}
    conn.execute("insert into message values (?,?,?,?,?)", (mid, sid, created, completed or created, json.dumps(data)))


def _wait(conn, pid, sid, start, end, tool="question"):
    data = {"type": "tool", "tool": tool, "state": {"status": "completed", "input": SECRET,
                                                    "output": SECRET, "time": {"start": start, "end": end}}}
    conn.execute("insert into part values (?,?,?,?,?,?)", (pid, "m", sid, start, end, json.dumps(data)))


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "opencode.db"
    conn = sqlite3.connect(path)
    _schema(conn)
    _session(conn, "ses_root", FROM + H, FROM + 10 * H)
    _session(conn, "ses_child", FROM + H, FROM + 2 * H, parent="ses_root", agent="explore",
             model=("openai", "gpt"))
    _session(conn, "ses_archived", FROM + H, FROM + 2 * H, archived=FROM + 3 * H)
    _session(conn, "ses_old", FROM - 5 * H, FROM - 4 * H)
    _session(conn, "ses_sibling_dir", FROM + H, FROM + 2 * H, directory="/w/ab")
    # Root: a 1 h step with a 45 min question wait inside, a 30 min step, a step that
    # began before the window, and one that never completed.
    _step(conn, "m1", "ses_root", FROM + H, FROM + 2 * H)
    _wait(conn, "p1", "ses_root", FROM + H + 10 * 60000, FROM + H + 55 * 60000)
    _wait(conn, "p2", "ses_root", FROM + H + 5 * 60000, FROM + H + 6 * 60000, tool="bash")
    _step(conn, "m2", "ses_root", FROM + 3 * H, FROM + 3 * H + 30 * 60000)
    _step(conn, "m0", "ses_root", FROM - H, FROM + 15 * 60000)
    _step(conn, "m3", "ses_root", FROM + 4 * H, None)
    # Child runs in parallel with the root's first step.
    _step(conn, "c1", "ses_child", FROM + H, FROM + H + 20 * 60000, model=("openai", "gpt"), agent="explore")
    _step(conn, "a1", "ses_archived", FROM + H, FROM + 2 * H)
    conn.commit()
    conn.close()
    return path


def run_db(db, **args):
    return history.run({"source": "db", **args}, path_factory=lambda: str(db))


def ids(result):
    return [s["id"] for s in result["sessions"]]


# ---------------------------------------------------------------- parsing

@pytest.mark.parametrize("args, message", [
    ({"action": "list", "surprise": 1}, "Unexpected"),
    ({"action": "remove"}, "action"),
    ({"action": "usage", "from": "2026-09-21"}, "requires days, or both"),
    ({"action": "usage", "days": 7, "from": "2026-09-21"}, "cannot be combined"),
    ({"action": "usage", "days": 0}, "days"),
    ({"action": "usage", "from": "2026-09-22", "to": "2026-09-21"}, "earlier"),
    ({"action": "usage", "from": "2026-09-21", "to": "2026-09-22", "source": "api"}, "message content"),
    ({"action": "get", "session_id": "ses_x", "kind": "all"}, "no filters"),
    ({"action": "get", "session_id": "../x"}, "session_id"),
    ({"action": "list", "limit": 500}, "limit"),
    ({"action": "list", "group_by": ["model"]}, "only accepted for usage"),
    ({"action": "usage", "from": "2026-09-21", "to": "2026-09-22", "group_by": ["title"]}, "group_by"),
    ({"action": "list", "include_title": "yes"}, "boolean"),
    ({"action": "list", "directory": "relative/path"}, "absolute"),
    ({"action": "list", "timezone": "Mars/Base"}, "timezone"),
])
def test_rejects_bad_requests(args, message):
    with pytest.raises(ValueError, match=message):
        history.parse(args)


def test_dates_are_local_midnight_and_end_is_exclusive():
    q = history.parse({"action": "usage", "from": "2026-09-21", "to": "2026-09-28",
                        "timezone": "Asia/Kuala_Lumpur"})
    assert history._iso(q["from"]) == "2026-09-20T16:00:00Z"
    assert history._iso(q["to"]) == "2026-09-27T16:00:00Z"
    explicit = history.parse({"action": "list", "from": "2026-09-21T00:00:00Z"})
    assert history._iso(explicit["from"]) == "2026-09-21T00:00:00Z"


def test_default_timezone_follows_local_daylight_saving(monkeypatch):
    monkeypatch.setenv("TZ", "America/New_York")
    q = history.parse({"action": "usage", "from": "2026-03-07", "to": "2026-03-09"})
    assert q["timezone"] == "America/New_York"
    assert history._iso(q["from"]) == "2026-03-07T05:00:00Z"   # EST
    assert history._iso(q["to"]) == "2026-03-09T04:00:00Z"     # EDT


# ---------------------------------------------------------------- database route

def test_list_defaults_to_roots_in_window_without_titles_or_costs(db):
    result = run_db(db, action="list", **{"from": history._iso(FROM), "to": history._iso(TO)})
    assert result["source"] == "db" and result["status"] == "complete"
    assert set(ids(result)) == {"ses_root", "ses_sibling_dir"}
    assert SECRET not in json.dumps(result)
    assert all("title" not in s and "cost" not in s for s in result["sessions"])


def test_list_filters_and_opt_ins(db):
    window = {"from": history._iso(FROM), "to": history._iso(TO)}
    assert ids(run_db(db, action="list", directory="/w/a", **window)) == ["ses_root"]
    assert set(ids(run_db(db, action="list", kind="all", archived=True, **window))) == {
        "ses_root", "ses_child", "ses_archived", "ses_sibling_dir"}
    assert ids(run_db(db, action="list", kind="child", model="gpt", **window)) == ["ses_child"]
    shown = run_db(db, action="list", directory="/w/a", include_title=True, include_cost=True, **window)
    assert shown["sessions"][0]["title"].startswith("TITLE ses_root")
    assert shown["sessions"][0]["cost"] == 1.5


def test_list_pages(db):
    first = run_db(db, action="list", kind="all", archived=True, limit=2)
    assert first["total"] == 5 and len(first["sessions"]) == 2 and first["next_offset"] == 2
    last = run_db(db, action="list", kind="all", archived=True, limit=2, offset=4)
    assert len(last["sessions"]) == 1 and last["next_offset"] is None


def test_get_and_children(db):
    assert run_db(db, action="get", session_id="ses_root")["session"]["id"] == "ses_root"
    assert ids(run_db(db, action="children", session_id="ses_root")) == ["ses_child"]
    with pytest.raises(ValueError, match="not found"):
        run_db(db, action="get", session_id="ses_missing")


def test_usage_subtracts_question_waits_and_removes_parallel_overlap(db):
    result = run_db(db, action="usage", group_by=["kind"], archived=False,
                    **{"from": history._iso(FROM), "to": history._iso(TO)})
    totals = result["totals"]
    # Root: 60 min step - 45 min question wait + 30 min step + 15 min clipped from m0
    # (bash is work, not a wait) = 60 min. Child: 20 min in parallel with the root step.
    assert totals["active_seconds"] == (60 + 20) * 60
    assert totals["question_wait_seconds"] == 45 * 60
    # Parallel minutes: child 0-20 overlaps root 0-10 only (10-55 is the wait).
    assert totals["active_union_seconds"] == (60 + 10) * 60
    # Tokens: only steps started in the window (m1, m2, m3, c1), never m0.
    assert totals["messages"] == 4 and totals["tokens"]["output"] == 40
    assert totals["sessions"] == 2  # archived excluded on request
    groups = {g["key"]["kind"]: g for g in result["groups"]}
    assert groups["child"]["active_seconds"] == 20 * 60
    # The unfinished step is disclosed and makes the totals partial.
    assert result["status"] == "partial"
    assert [d["code"] for d in result["diagnostics"]] == ["messages-without-completion"]
    assert SECRET not in json.dumps(result) and "cost" not in totals


def test_usage_groups_and_filters(db):
    window = {"from": history._iso(FROM), "to": history._iso(TO)}
    # Archiving does not undo work: usage counts archived sessions by default.
    assert run_db(db, action="usage", **window)["totals"]["sessions"] == 3
    by_model = run_db(db, action="usage", group_by=["model", "agent"], **window)
    keys = [g["key"] for g in by_model["groups"]]
    assert {"model": "anthropic/opus", "agent": "build"} in keys
    assert {"model": "openai/gpt", "agent": "explore"} in keys
    only_child = run_db(db, action="usage", kind="child", include_cost=True, **window)
    assert only_child["totals"]["sessions"] == 1 and only_child["totals"]["cost"] == 0.25
    day = run_db(db, action="usage", group_by=["day"], timezone="UTC", **window)
    assert {g["key"]["day"] for g in day["groups"]} <= {history._iso(FROM)[:10], history._iso(TO)[:10]}


def test_usage_without_part_table_is_partial(tmp_path):
    path = tmp_path / "noparts.db"
    conn = sqlite3.connect(path)
    _schema(conn, parts=False)
    _session(conn, "ses_root", FROM + H, FROM + 2 * H)
    _step(conn, "m1", "ses_root", FROM + H, FROM + 2 * H)
    conn.commit()
    conn.close()
    result = run_db(path, action="usage", **{"from": history._iso(FROM), "to": history._iso(TO)})
    assert result["status"] == "partial"
    assert result["diagnostics"][0]["code"] == "waits-unavailable"
    assert result["totals"]["active_seconds"] == 3600


def test_schema_change_fails_closed(tmp_path):
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    _schema(conn, drop_session_column="tokens_reasoning")
    conn.commit()
    conn.close()
    with pytest.raises(history.Unavailable, match="tokens_reasoning"):
        run_db(path, action="list")


def test_database_is_opened_read_only(db):
    before = (db.stat().st_mtime_ns, db.read_bytes())
    run_db(db, action="usage", **{"from": history._iso(FROM), "to": history._iso(TO)})
    run_db(db, action="list")
    assert (db.stat().st_mtime_ns, db.read_bytes()) == before
    with history.Snapshot(str(db)) as snap:
        with pytest.raises(sqlite3.Error):
            snap.conn.execute("delete from session")


# ---------------------------------------------------------------- API route

FAKE_SERVE = r'''#!{python}
import base64, json, os, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
version = os.environ.get("FAKE_VERSION", "1.18.34")
if sys.argv[1:] == ["--version"]:
    print(version)
    sys.exit(0)
v2 = "v2." in version
record = os.environ["FAKE_RECORD"]
mode = os.environ.get("FAKE_MODE", "ok")
json.dump({{"argv": sys.argv[1:], "cwd": os.getcwd(), "pid": os.getpid(),
           "hermes_env": sorted(k for k in os.environ if k.startswith(("HERMES_", "RESIDENT_")))}},
          open(record, "w"))
if mode == "crash":
    sys.exit(3)
expected = "Basic " + base64.b64encode(("opencode:" + os.environ["OPENCODE_SERVER_PASSWORD"]).encode()).decode()
H = 3600 * 1000
FROM = {start}
def session(sid, parent=None, created=FROM + H, updated=FROM + 2 * H):
    return {{"id": sid, "slug": "s", "projectID": "p", "directory": "/w/a", "title": "T " + sid,
            "version": "9.9", "parentID": parent, "agent": "build",
            "model": {{"id": "opus", "providerID": "anthropic"}}, "cost": 2.0,
            "tokens": {{"input": 1, "output": 2, "reasoning": 0, "cache": {{"read": 0, "write": 0}}}},
            "summary": {{"additions": 1, "deletions": 0, "files": 1}},
            "time": {{"created": created, "updated": updated}}}}
def session_v2(sid, parent=None, created=FROM + H, updated=FROM + 2 * H):
    item = session(sid, parent, created, updated)
    for key in ("directory", "version", "summary", "slug"):
        item.pop(key)
    return {{**item, "location": {{"directory": "/w/a"}}}}
def v2_get(url, query):
    if url.path == "/api/info":
        return {{"version": "2.0.23", "pid": os.getpid()}}
    if url.path == "/api/session/ses_new":
        return {{"data": session_v2("ses_new")}}
    if url.path != "/api/session" or mode == "noroute":
        return None
    if mode == "badshape":
        return {{"not": "a page"}}
    seen = json.load(open(record))
    json.dump({{**seen, "query": query, "cursors": seen.get("cursors", []) + query.get("cursor", ["0"])}},
              open(record, "w"))
    rows = [session_v2("ses_new", updated=FROM + 3 * H), session_v2("ses_kid", parent="ses_new"),
            session_v2("ses_old", created=FROM - 5 * H, updated=FROM - 4 * H),
            session_v2("ses_older", created=FROM - 9 * H, updated=FROM - 8 * H)]
    parent = query.get("parentID", [None])[0]
    if parent == "null":
        rows = [r for r in rows if not r["parentID"]]
    elif parent:
        rows = [r for r in rows if r["parentID"] == parent]
    start = int(query.get("cursor", ["0"])[0])
    # One session per page, so callers must follow the cursor.
    page = rows[start:start + 1]
    return {{"data": page, "cursor": {{"next": str(start + 1) if start + 1 < len(rows) else None}}}}
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass
    def do_GET(self):
        if self.headers.get("Authorization") != expected:
            self.send_response(401); self.end_headers(); return
        url = urlparse(self.path); query = parse_qs(url.query)
        if v2:
            body = v2_get(url, query)
            if body is None:
                self.send_response(404); self.end_headers(); return
        elif url.path == "/global/health":
            body = {{"healthy": True, "version": "9.9"}}
        elif url.path == "/experimental/session":
            if mode == "noroute":
                self.send_response(404); self.end_headers(); return
            if mode == "badshape":
                body = {{"not": "a list"}}
            else:
                body = [session("ses_new"), session("ses_kid", parent="ses_new"),
                        session("ses_old", created=FROM - 5 * H, updated=FROM - 4 * H)]
                json.dump({{**json.load(open(record)), "query": query}}, open(record, "w"))
                if query.get("roots") == ["true"]:
                    body = [s for s in body if not s["parentID"]]
                if "start" in query:
                    body = [s for s in body if s["time"]["updated"] >= int(query["start"][0])]
        elif url.path == "/session/ses_new":
            body = session("ses_new")
        elif url.path == "/session/ses_new/children":
            body = [session("ses_kid", parent="ses_new")]
        else:
            self.send_response(404); self.end_headers(); return
        data = json.dumps(body).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(data)
server = HTTPServer(("127.0.0.1", 0), Handler)
print("opencode server listening on http://127.0.0.1:%d" % server.server_port, flush=True)
server.serve_forever()
'''


@pytest.fixture
def fake(tmp_path, monkeypatch):
    exe = tmp_path / "opencode"
    exe.write_text(FAKE_SERVE.format(python=sys.executable, start=FROM))
    exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
    record = tmp_path / "record.json"
    monkeypatch.setenv("FAKE_RECORD", str(record))
    monkeypatch.setenv("HERMES_SESSION_ID", "must-not-leak")
    return lambda: history.ApiServer(executable=str(exe)), record


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def test_api_list_is_preferred_private_and_stopped(fake, db):
    factory, record = fake
    result = history.run({"action": "list", "from": history._iso(FROM), "to": history._iso(TO)},
                          server_factory=factory, path_factory=lambda: pytest.fail("database used"))
    assert result["source"] == "api" and result["opencode_version"] == "9.9"
    assert ids(result) == ["ses_new"]
    assert "title" not in result["sessions"][0] and "cost" not in result["sessions"][0]
    seen = json.loads(record.read_text())
    assert seen["argv"] == ["serve", "--pure", "--hostname", "127.0.0.1", "--port", "0"]
    assert seen["hermes_env"] == []
    assert seen["query"]["start"] == [str(FROM)] and seen["query"]["roots"] == ["true"]
    assert not Path(seen["cwd"]).exists(), "private working directory is removed"
    deadline = time.time() + 5
    while alive(seen["pid"]) and time.time() < deadline:
        time.sleep(0.05)
    assert not alive(seen["pid"]), "server is stopped after the call"


def test_api_get_children_and_missing(fake):
    factory, _ = fake
    got = history.run({"action": "get", "session_id": "ses_new", "include_title": True}, server_factory=factory)
    assert got["session"]["title"] == "T ses_new" and got["session"]["changes"]["files"] == 1
    kids = history.run({"action": "children", "session_id": "ses_new"}, server_factory=factory)
    assert ids(kids) == ["ses_kid"]
    with pytest.raises(ValueError, match="not found"):
        history.run({"action": "get", "session_id": "ses_gone", "source": "api"}, server_factory=factory)


def test_api_miss_is_confirmed_against_the_database(fake, db):
    factory, _ = fake
    # The fake API does not know ses_root; the database does (a project-scoped miss).
    found = history.run({"action": "get", "session_id": "ses_root"}, server_factory=factory,
                        path_factory=lambda: str(db))
    assert found["source"] == "db" and found["session"]["id"] == "ses_root"
    assert found["diagnostics"][0]["code"] == "api-unavailable"
    with pytest.raises(ValueError, match="not found"):
        history.run({"action": "get", "session_id": "ses_gone"}, server_factory=factory,
                    path_factory=lambda: str(db))


@pytest.mark.parametrize("mode", ["crash", "badshape", "noroute"])
def test_auto_falls_back_to_database_and_says_so(fake, db, monkeypatch, mode):
    factory, _ = fake
    monkeypatch.setenv("FAKE_MODE", mode)
    result = history.run({"action": "list", "from": history._iso(FROM), "to": history._iso(TO)},
                          server_factory=factory, path_factory=lambda: str(db))
    assert result["source"] == "db"
    assert result["diagnostics"][0]["code"] == "api-unavailable"
    with pytest.raises(history.Unavailable):
        history.run({"action": "list", "source": "api"}, server_factory=factory)


def test_cli_prints_json_and_error_exit(db, monkeypatch, capsys):
    monkeypatch.setattr(history, "db_path", lambda: str(db))
    monkeypatch.setattr(history.run, "__kwdefaults__", {**history.run.__kwdefaults__,
                                                         "path_factory": lambda: str(db)})
    assert history.main(["list", "--source", "db", "--kind", "all", "--archived"]) == 0
    assert json.loads(capsys.readouterr().out)["total"] == 5
    assert history.main(["usage", "--from", "2026-09-21"]) == 1
    assert "requires days, or both" in json.loads(capsys.readouterr().out)["error"]


# ---------------------------------------------------------------- Hermes tool

def _plugin():
    pytest.importorskip("hermes_constants")
    source = ROOT / "__init__.py"
    plugin_spec = importlib.util.spec_from_file_location("opencode_plugin_history_test", source)
    plugin = importlib.util.module_from_spec(plugin_spec)
    plugin_spec.loader.exec_module(plugin)
    return plugin


def test_tool_is_registered_strict_and_gated(db, monkeypatch):
    plugin = _plugin()
    tools = {}

    class Context:
        profile_name = "engineer"

        def register_tool(self, **kwargs):
            tools[kwargs["name"]] = kwargs

    plugin.register(Context())
    tool = tools["opencode_history"]
    assert tool["toolset"] == "opencode"
    assert tool["schema"]["parameters"]["additionalProperties"] is False
    assert set(tool["schema"]["parameters"]["properties"]) == history.FIELDS

    monkeypatch.setattr(plugin, "_scope", lambda: (_ for _ in ()).throw(ValueError("inbound refused")))
    assert json.loads(plugin.opencode_history({"action": "list"}))["error"] == "inbound refused"

    monkeypatch.setattr(plugin, "_scope", lambda: None)
    monkeypatch.setattr(plugin.inventory.run, "__kwdefaults__", {**plugin.inventory.run.__kwdefaults__,
                                                                  "path_factory": lambda: str(db)})
    result = json.loads(plugin.opencode_history({"action": "list", "source": "db"}))
    assert result["source"] == "db" and "ses_root" in ids(result)


# ---------------------------------------------------------------- OpenCode 2

def test_v2_api_routes_follow_the_cursor_without_pure(fake, monkeypatch):
    factory, record = fake
    monkeypatch.setenv("FAKE_VERSION", "opencode v2.0.23")
    result = history.run({"action": "list", "from": history._iso(FROM), "to": history._iso(TO),
                          "include_title": True}, server_factory=factory,
                         path_factory=lambda: pytest.fail("database used"))
    assert result["source"] == "api" and result["opencode_version"] == "2.0.23"
    # Roots only, newest first; ses_old (updated before the window) ends the paging.
    assert ids(result) == ["ses_new"]
    session = result["sessions"][0]
    assert session["directory"] == "/w/a" and session["version"] is None and session["changes"] is None
    seen = json.loads(record.read_text())
    assert seen["argv"] == ["serve", "--hostname", "127.0.0.1", "--port", "0"]
    assert seen["query"]["parentID"] == ["null"] and seen["query"]["order"] == ["desc"]
    windowed = history.run({"action": "list", "kind": "all", "from": history._iso(FROM),
                            "to": history._iso(TO)}, server_factory=factory)
    assert ids(windowed) == ["ses_new", "ses_kid"]
    # Paging stops at the first session updated before the window.
    assert json.loads(record.read_text())["cursors"] == ["0", "1", "2"]
    everything = history.run({"action": "list", "kind": "all"}, server_factory=factory)
    assert ids(everything) == ["ses_new", "ses_kid", "ses_old", "ses_older"]
    got = history.run({"action": "get", "session_id": "ses_new"}, server_factory=factory)
    assert got["session"]["id"] == "ses_new"
    kids = history.run({"action": "children", "session_id": "ses_new"}, server_factory=factory)
    assert ids(kids) == ["ses_kid"]
    with pytest.raises(ValueError, match="not found"):
        history.run({"action": "get", "session_id": "ses_gone", "source": "api"}, server_factory=factory)


@pytest.mark.parametrize("mode", ["badshape", "noroute"])
def test_v2_api_failures_fall_back_to_the_database(fake, db, monkeypatch, mode):
    factory, _ = fake
    monkeypatch.setenv("FAKE_VERSION", "opencode v2.0.23")
    monkeypatch.setenv("FAKE_MODE", mode)
    result = history.run({"action": "list", "from": history._iso(FROM), "to": history._iso(TO)},
                         server_factory=factory, path_factory=lambda: str(db),
                         version_factory=lambda: pytest.fail("single-schema database needs no version"))
    assert result["source"] == "db" and result["diagnostics"][0]["code"] == "api-unavailable"


def test_unknown_major_version_is_unavailable(fake, monkeypatch):
    factory, _ = fake
    monkeypatch.setenv("FAKE_VERSION", "3.0.0")
    with pytest.raises(history.Unavailable, match="major version 3"):
        history.run({"action": "list", "source": "api"}, server_factory=factory)


def _v2_schema(conn):
    conn.execute("create table session_v2 (id text primary key, project_id text, workspace_id text, "
                 "parent_id text, directory text, path text, title text, version text, cost real, "
                 "tokens_input integer, tokens_output integer, tokens_reasoning integer, "
                 "tokens_cache_read integer, tokens_cache_write integer, agent text, model text, "
                 "time_created integer, time_updated integer, time_archived integer)")
    conn.execute("create table session_message (id text primary key, session_id text, type text, "
                 "seq integer, time_created integer, time_updated integer, data text)")


def _v2_session(conn, sid, created, updated, *, parent=None, archived=None, agent="build",
                model=("anthropic", "opus")):
    conn.execute("insert into session_v2 (id, project_id, parent_id, directory, title, version, cost, "
                 "tokens_input, tokens_output, tokens_reasoning, tokens_cache_read, tokens_cache_write, "
                 "agent, model, time_created, time_updated, time_archived) "
                 "values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                 (sid, "proj", parent, "/w/a", f"TITLE {sid} {SECRET}", "2.0.23", 1.5, 1, 2, 3, 4, 5,
                  agent, json.dumps({"id": model[1], "providerID": model[0]}), created, updated, archived))


def _v2_step(conn, mid, sid, created, completed, *, waits=(), model=("anthropic", "opus"), agent="build"):
    content = [{"type": "text", "text": SECRET}]
    for start, end, name in waits:
        content.append({"type": "tool", "name": name, "input": SECRET, "state": {"status": "completed"},
                        "time": {"created": start - 1, "ran": start, "completed": end}})
    data = {"agent": agent, "model": {"id": model[1], "providerID": model[0]},
            "time": {"created": created, **({"completed": completed} if completed is not None else {})},
            "tokens": {"input": 1, "output": 10, "reasoning": 2, "cache": {"read": 3, "write": 4}},
            "cost": 0.25, "content": content}
    conn.execute("insert into session_message values (?,?,?,?,?,?,?)",
                 (mid, sid, "assistant", 0, created, completed or created, json.dumps(data)))


@pytest.fixture
def db_v2(tmp_path):
    path = tmp_path / "opencode-v2.db"
    conn = sqlite3.connect(path)
    _v2_schema(conn)
    _v2_session(conn, "ses_root", FROM + H, FROM + 10 * H)
    _v2_session(conn, "ses_child", FROM + H, FROM + 2 * H, parent="ses_root", agent="explore",
                model=("openai", "gpt"))
    _v2_step(conn, "m1", "ses_root", FROM + H, FROM + 2 * H,
             waits=[(FROM + H + 10 * 60000, FROM + H + 55 * 60000, "question"),
                    (FROM + H + 5 * 60000, FROM + H + 6 * 60000, "shell")])
    _v2_step(conn, "m2", "ses_root", FROM + 3 * H, FROM + 3 * H + 30 * 60000)
    _v2_step(conn, "c1", "ses_child", FROM + H, FROM + H + 20 * 60000, model=("openai", "gpt"),
             agent="explore")
    conn.execute("insert into session_message values ('u1','ses_root','user',0,?,?,?)",
                 (FROM + H, FROM + H, json.dumps({"text": SECRET})))
    conn.commit()
    conn.close()
    return path


def test_v2_database_lists_and_measures_usage(db_v2):
    listed = run_db(db_v2, action="list", kind="all")
    assert ids(listed) == ["ses_root", "ses_child"]
    assert listed["sessions"][0]["version"] == "2.0.23"
    kids = run_db(db_v2, action="children", session_id="ses_root")
    assert ids(kids) == ["ses_child"]
    result = run_db(db_v2, action="usage", group_by=["model"],
                    **{"from": history._iso(FROM), "to": history._iso(TO)})
    totals = result["totals"]
    # Root: 60 min step - 45 min question wait (shell is work) + 30 min step; child 20 min.
    assert totals["active_seconds"] == (45 + 20) * 60
    assert totals["question_wait_seconds"] == 45 * 60
    assert totals["messages"] == 3 and totals["tokens"]["output"] == 30
    assert {g["key"]["model"] for g in result["groups"]} == {"anthropic/opus", "openai/gpt"}
    assert result["status"] == "complete" and SECRET not in json.dumps(result)


def test_database_with_both_schemas_follows_the_installed_version(tmp_path):
    path = tmp_path / "both.db"
    conn = sqlite3.connect(path)
    _schema(conn)
    _v2_schema(conn)
    _session(conn, "ses_v1", FROM + H, FROM + 2 * H)
    _v2_session(conn, "ses_v2", FROM + H, FROM + 2 * H)
    conn.commit()
    conn.close()
    for major, expected in ((1, "ses_v1"), (2, "ses_v2")):
        result = history.run({"action": "list", "source": "db"}, path_factory=lambda: str(path),
                             version_factory=lambda major=major: major)
        assert ids(result) == [expected]
    with pytest.raises(history.Unavailable, match="1 and 2"):
        with history.Snapshot(str(path)):
            pass
