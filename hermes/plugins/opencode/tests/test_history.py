import importlib.util
import json
from pathlib import Path
import sqlite3
import urllib.parse

import pytest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("opencode_history_test", ROOT / "history.py")
history = importlib.util.module_from_spec(spec)
spec.loader.exec_module(history)

H = 3600 * 1000
FROM = 1_790_000_000_000          # window [FROM, TO)
TO = FROM + 24 * H
SECRET = "SECRET-CONTENT-MARKER"


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



def _session(conn, sid, created, updated, *, parent=None, directory="/w/a", archived=None, agent="build",
             model=("anthropic", "opus")):
    _v2_session(conn, sid, created, updated, parent=parent, archived=archived, agent=agent, model=model)
    conn.execute("update session_v2 set directory = ? where id = ?", (directory, sid))


def _v1_tables(conn):
    """The V1 tables OpenCode 2 keeps beside its own after importing V1 data."""
    conn.execute("create table message (id text primary key, session_id text, time_created integer, "
                 "time_updated integer, data text)")
    conn.execute("create table part (id text primary key, message_id text, session_id text, "
                 "time_created integer, time_updated integer, data text)")


def _v1_step(conn, mid, sid, created, completed):
    data = {"role": "assistant", "providerID": "anthropic", "modelID": "opus", "agent": "build",
            "time": {"created": created, "completed": completed}, "text": SECRET}
    conn.execute("insert into message values (?,?,?,?,?)", (mid, sid, created, completed, json.dumps(data)))


def _v1_wait(conn, pid, sid, start, end, tool="question"):
    data = {"type": "tool", "tool": tool, "state": {"status": "completed", "input": SECRET,
                                                    "output": SECRET, "time": {"start": start, "end": end}}}
    conn.execute("insert into part values (?,?,?,?,?,?)", (pid, "m", sid, start, end, json.dumps(data)))


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "opencode.db"
    conn = sqlite3.connect(path)
    _v2_schema(conn)
    _session(conn, "ses_root", FROM + H, FROM + 10 * H)
    _session(conn, "ses_child", FROM + H, FROM + 2 * H, parent="ses_root", agent="explore",
             model=("openai", "gpt"))
    _session(conn, "ses_archived", FROM + H, FROM + 2 * H, archived=FROM + 3 * H)
    _session(conn, "ses_old", FROM - 5 * H, FROM - 4 * H)
    _session(conn, "ses_sibling_dir", FROM + H, FROM + 2 * H, directory="/w/ab")
    # Root: a 1 h step with a 45 min question wait inside, a 30 min step, a step that
    # began before the window, and one that never completed.
    _v2_step(conn, "m1", "ses_root", FROM + H, FROM + 2 * H,
             waits=[(FROM + H + 10 * 60000, FROM + H + 55 * 60000, "question"),
                    (FROM + H + 5 * 60000, FROM + H + 6 * 60000, "shell")])
    _v2_step(conn, "m2", "ses_root", FROM + 3 * H, FROM + 3 * H + 30 * 60000)
    _v2_step(conn, "m0", "ses_root", FROM - H, FROM + 15 * 60000)
    _v2_step(conn, "m3", "ses_root", FROM + 4 * H, None)
    # Child runs in parallel with the root's first step.
    _v2_step(conn, "c1", "ses_child", FROM + H, FROM + H + 20 * 60000, model=("openai", "gpt"), agent="explore")
    _v2_step(conn, "a1", "ses_archived", FROM + H, FROM + 2 * H)
    conn.execute("insert into session_message values ('u1','ses_root','user',0,?,?,?)",
                 (FROM + H, FROM + H, json.dumps({"text": SECRET})))
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
    assert result["sessions"][0]["version"] == "2.0.23"


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
    # (shell is work, not a wait) = 60 min. Child: 20 min in parallel with the root step.
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


def test_schema_change_fails_closed(tmp_path):
    path = tmp_path / "changed.db"
    conn = sqlite3.connect(path)
    _v2_schema(conn)
    conn.execute("alter table session_v2 drop column tokens_reasoning")
    conn.commit()
    conn.close()
    with pytest.raises(history.Unavailable, match="tokens_reasoning"):
        run_db(path, action="list")


def test_opencode1_only_database_is_unavailable(tmp_path):
    path = tmp_path / "v1.db"
    conn = sqlite3.connect(path)
    _v1_tables(conn)
    conn.commit()
    conn.close()
    with pytest.raises(history.Unavailable, match="no OpenCode 2 tables"):
        run_db(path, action="list")


def test_database_is_opened_read_only(db):
    before = (db.stat().st_mtime_ns, db.read_bytes())
    run_db(db, action="usage", **{"from": history._iso(FROM), "to": history._iso(TO)})
    run_db(db, action="list")
    assert (db.stat().st_mtime_ns, db.read_bytes()) == before
    with history.Snapshot(str(db)) as snap:
        with pytest.raises(sqlite3.Error):
            snap.conn.execute("delete from session_v2")


def test_usage_prefers_the_v1_record_of_imported_messages(tmp_path):
    """OpenCode 2 imports V1 steps with time.completed (and tool times) set to the
    V1 row's last update; while the V1 tables remain, their own times win."""
    path = tmp_path / "imported.db"
    conn = sqlite3.connect(path)
    _v1_tables(conn)
    _v2_schema(conn)
    _v2_session(conn, "ses_root", FROM + H, FROM + 10 * H)
    # Imported step: V1 says 60 min with a 45 min question wait inside.
    _v1_step(conn, "m1", "ses_root", FROM + H, FROM + 2 * H)
    _v1_wait(conn, "p1", "ses_root", FROM + H + 10 * 60000, FROM + H + 55 * 60000)
    # Its V2 copy claims it ran until hour 9, with the wait stretched as well.
    _v2_step(conn, "m1", "ses_root", FROM + H, FROM + 9 * H,
             waits=[(FROM + H + 10 * 60000, FROM + 9 * H, "question")])
    # A step written natively by OpenCode 2 keeps its own times.
    _v2_step(conn, "m2", "ses_root", FROM + 3 * H, FROM + 3 * H + 30 * 60000,
             waits=[(FROM + 3 * H + 5 * 60000, FROM + 3 * H + 10 * 60000, "question")])
    conn.commit()
    conn.close()
    result = run_db(path, action="usage", **{"from": history._iso(FROM), "to": history._iso(TO)})
    totals = result["totals"]
    assert totals["messages"] == 2
    assert totals["question_wait_seconds"] == (45 + 5) * 60
    assert totals["active_seconds"] == (60 - 45 + 30 - 5) * 60


# ---------------------------------------------------------------- API route (shared service)

def _api_session(sid, parent=None, created=FROM + H, updated=FROM + 2 * H):
    return {"id": sid, "parentID": parent, "projectID": "proj", "agent": "build",
            "model": {"providerID": "anthropic", "id": "opus"}, "cost": 1.5,
            "tokens": {"input": 1, "output": 2, "reasoning": 3, "cache": {"read": 4, "write": 5}},
            "time": {"created": created, "updated": updated}, "title": f"TITLE {sid} {SECRET}",
            "location": {"directory": "/w/a"}}


class FakeClient:
    """The shared service's session routes, at the level of history's client."""

    def __init__(self, mode="ok"):
        self.mode, self.routes = mode, []
        self.sessions = [_api_session("ses_new", updated=FROM + 5 * H),
                         _api_session("ses_kid", parent="ses_new", updated=FROM + 4 * H),
                         _api_session("ses_old", created=FROM - 9 * H, updated=FROM - 2 * H),
                         _api_session("ses_older", created=FROM - 9 * H, updated=FROM - 3 * H)]

    def __call__(self, method, route):
        self.routes.append(route)
        if self.mode == "down":
            raise history.Unavailable("service down")
        path, _, query = route.partition("?")
        params = dict(urllib.parse.parse_qsl(query))
        if path == "/api/info":
            return {"version": "2.0.23"}
        if path == "/api/session":
            if self.mode == "badshape":
                return {"data": "nope"}
            items = self.sessions
            if params.get("parentID") == "null":
                items = [s for s in items if not s["parentID"]]
            elif "parentID" in params:
                items = [s for s in items if s["parentID"] == params["parentID"]]
            start = int(params.get("cursor", "0"))
            page = items[start:start + 1]
            more = start + 1 < len(items)
            return {"data": page, "cursor": {"next": str(start + 1) if more else None}}
        sid = path.rsplit("/", 1)[1]
        found = [s for s in self.sessions if s["id"] == sid]
        if not found:
            raise LookupError(route)
        return {"data": found[0]}


def test_api_list_follows_the_cursor_and_stops_before_the_window():
    client = FakeClient()
    result = history.run({"action": "list", "from": history._iso(FROM), "to": history._iso(TO),
                          "include_title": True}, client=client,
                         path_factory=lambda: pytest.fail("database used"))
    assert result["source"] == "api" and result["opencode_version"] == "2.0.23"
    assert ids(result) == ["ses_new"]
    session = result["sessions"][0]
    assert session["directory"] == "/w/a" and session["version"] is None and session["changes"] is None
    assert any("parentID=null" in r and "order=desc" in r for r in client.routes)
    client.routes.clear()
    windowed = history.run({"action": "list", "kind": "all", "from": history._iso(FROM),
                            "to": history._iso(TO)}, client=client)
    assert ids(windowed) == ["ses_new", "ses_kid"]
    # Paging stops at the first session updated before the window.
    assert [r for r in client.routes if r.startswith("/api/session?")][-1].count("cursor=2") == 1
    everything = history.run({"action": "list", "kind": "all"}, client=client)
    assert ids(everything) == ["ses_new", "ses_kid", "ses_old", "ses_older"]


def test_api_get_children_and_missing():
    client = FakeClient()
    assert history.run({"action": "get", "session_id": "ses_new"}, client=client)["session"]["id"] == "ses_new"
    assert ids(history.run({"action": "children", "session_id": "ses_new"}, client=client)) == ["ses_kid"]
    with pytest.raises(ValueError, match="not found"):
        history.run({"action": "get", "session_id": "ses_gone", "source": "api"}, client=client)


def test_api_miss_is_confirmed_against_the_database(db):
    result = history.run({"action": "get", "session_id": "ses_root"}, client=FakeClient(),
                         path_factory=lambda: str(db))
    assert result["source"] == "db" and result["session"]["id"] == "ses_root"


@pytest.mark.parametrize("mode", ["down", "badshape"])
def test_api_failures_fall_back_to_the_database_and_say_so(db, mode):
    result = history.run({"action": "list", "from": history._iso(FROM), "to": history._iso(TO)},
                         client=FakeClient(mode), path_factory=lambda: str(db))
    assert result["source"] == "db" and result["diagnostics"][0]["code"] == "api-unavailable"
    with pytest.raises(history.Unavailable):
        history.run({"action": "list", "source": "api"}, client=FakeClient(mode))


def test_default_client_maps_service_errors(monkeypatch):
    def call(method, route):
        if route.startswith("/api/session/ses_gone"):
            raise history.api.ApiError(404, "SessionNotFoundError", "Session not found")
        if route == "/api/info":
            raise history.api.ApiError(401, "UnauthorizedError", "no")
        raise history.api.Unavailable("down")
    monkeypatch.setattr(history.api, "call", call)
    with pytest.raises(LookupError):
        history._client("get", "/api/session/ses_gone")
    with pytest.raises(history.Unavailable, match="HTTP 401"):
        history._client("get", "/api/info")
    with pytest.raises(history.Unavailable, match="down"):
        history._client("get", "/api/session")


def test_cli_prints_json_and_error_exit(db, monkeypatch, capsys):
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

        def register_hook(self, name, callback):
            pass

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
