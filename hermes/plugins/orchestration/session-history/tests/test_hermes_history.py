import asyncio
import importlib.util
import json
import os
from pathlib import Path
import sqlite3

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


hermes = _load("session_history_hermes_test", ROOT / "hermes.py")
common = hermes.common

S = 1_790_000_000            # seconds; window [FROM, TO) below
FROM, TO = S * 1000, (S + 86400) * 1000
SECRET = "SECRET-CONTENT-MARKER"


def _hermes_store():
    return pytest.importorskip("hermes_state")


def _db(path):
    """A real Hermes schema, created by Hermes itself, then filled with raw rows."""
    _hermes_store().SessionDB(db_path=path).close()
    return sqlite3.connect(path)


def _session(conn, sid, start, *, parent=None, end_reason=None, source="cli", cwd="/w/a", archived=0,
             last=None, model="opus", provider="anthropic", config=None):
    conn.execute(
        "INSERT INTO sessions (id, source, user_id, model, model_config, system_prompt, parent_session_id, "
        "started_at, ended_at, end_reason, message_count, cwd, title, archived, chat_id, billing_provider, "
        "last_activity_at, output_tokens, actual_cost_usd) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (sid, source, "user-" + SECRET, model, json.dumps(config) if config else None, "PROMPT " + SECRET,
         parent, start, None, end_reason, 3, cwd, f"TITLE {sid} {SECRET}", archived, "chat-" + SECRET,
         provider, last, 7, 0.5))


def _msg(conn, sid, t, role, tool=None, summary=0):
    conn.execute("INSERT INTO messages (session_id, role, content, tool_name, timestamp, _compressed_summary) "
                 "VALUES (?,?,?,?,?,?)", (sid, role, SECRET, tool, t, summary))


def _usage(conn, sid, first, last, out, *, model="opus", task=""):
    conn.execute("INSERT INTO session_model_usage (session_id, model, billing_provider, task, api_call_count, "
                 "input_tokens, output_tokens, first_seen, last_seen, actual_cost_usd) VALUES (?,?,?,?,?,?,?,?,?,?)",
                 (sid, model, "anthropic", task, 2, 1, out, first, last, 0.25))


@pytest.fixture
def root(tmp_path):
    base = tmp_path / "hermes"
    (base / "profiles" / "engineer").mkdir(parents=True)
    (base / "profiles" / "assistant").mkdir(parents=True)
    (base / "profiles" / "empty").mkdir(parents=True)          # no state.db: not a profile
    eng = _db(base / "profiles" / "engineer" / "state.db")
    # Root: user at +1h, model at +1h05, a clarify answered at +1h35 (30 min wait),
    # opencode_call returning at +1h55, model at +2h. Then idle until the next user turn.
    _session(eng, "e1", S + 3600, last=S + 7200)
    for t, role, tool in ((3600, "user", None), (3900, "assistant", None), (5700, "tool", "clarify"),
                          (6000, "assistant", None), (6900, "tool", "opencode_call"), (7200, "assistant", None),
                          (7200, "assistant", None),                          # duplicate row: counted once
                          (7300, "assistant", None)):
        _msg(eng, "e1", S + t, role, tool)
    _msg(eng, "e1", S + 7250, "assistant", summary=1)                     # synthetic compression summary
    # Compression continues e1 as e2, copying the kept tail with its original timestamps;
    # the person's next turn (after an idle gap) lands in e2.
    eng.execute("UPDATE sessions SET end_reason='compression' WHERE id='e1'")
    _session(eng, "e2", S + 7400, parent="e1", last=S + 50100)
    for t, role in ((7200, "assistant"), (7300, "assistant"), (50000, "user"), (50100, "assistant")):
        _msg(eng, "e2", S + t, role)
    # A delegate child starts first; as in Hermes it is marked, so it is not the continuation.
    _session(eng, "e1-sub", S + 3600, parent="e1", source="subagent", model="gpt", provider="openai",
             config={"_delegate_from": "e1"})
    _msg(eng, "e1-sub", S + 3600, "user")
    _msg(eng, "e1-sub", S + 3900, "assistant")                           # 5 min, parallel to e1
    _session(eng, "old", S - 90000, last=S - 80000)
    _usage(eng, "e1", S + 3600, S + 7300, 100)                          # inside the window
    _usage(eng, "e1", S + 3600, S + 7300, 5, task="title_generation")
    _usage(eng, "old", S - 90000, S + 100, 999)                         # crosses the window start
    eng.commit()
    eng.close()
    asst = _db(base / "profiles" / "assistant" / "state.db")
    _session(asst, "a1", S + 3000, source="telegram", archived=1, last=S + 4200)
    _msg(asst, "a1", S + 3000, "user")
    _msg(asst, "a1", S + 4200, "assistant")                              # 20 min, overlaps e1's
    asst.commit()
    asst.close()
    return base


def run(root, **args):
    return hermes.run(args, root=root)


def iso(seconds):
    return common.iso(seconds * 1000)


def window():
    return {"from": iso(S), "to": iso(S + 86400)}


# ------------------------------------------------------------------ parsing and discovery

def test_profiles_are_discovered_from_the_root(root):
    assert list(hermes.profiles(root)) == ["assistant", "engineer"]
    with pytest.raises(hermes.Unavailable):
        hermes.profiles(root / "nowhere")


@pytest.mark.parametrize("args, message", [
    ({"action": "list", "profile": "ghost"}, "Unknown profile"),
    ({"action": "list", "surprise": 1}, "Unexpected"),
    ({"action": "usage"}, "requires days"),
    ({"action": "usage", "days": 3, "from": "2026-09-01"}, "cannot be combined"),
    ({"action": "usage", "days": 1, "source": "api"}, "no windowed usage API"),
    ({"action": "get", "session_id": "e1", "kind": "all"}, "no filters"),
    ({"action": "list", "group_by": ["profile"]}, "only accepted for usage"),
    ({"action": "usage", "days": 1, "group_by": ["title"]}, "group_by"),
])
def test_rejects_bad_requests(root, args, message):
    with pytest.raises(ValueError, match=message):
        run(root, **args)


def test_days_is_the_last_local_calendar_days():
    q = hermes.parse({"action": "usage", "days": 7, "timezone": "Asia/Tokyo"}, ["engineer"])
    assert (q["to"] - q["from"]) == 7 * 86400 * 1000
    assert common.iso(q["to"]).endswith("T15:00:00Z")          # local midnight in Tokyo


# ------------------------------------------------------------------ list / get / children

@pytest.mark.parametrize("source", ["api", "db"])
def test_list_defaults_and_privacy(root, source):
    result = run(root, action="list", source=source, **window())
    assert result["source"] == source and result["status"] == "complete"
    # Roots (a compression continuation is the same conversation, so root-kind),
    # archived and out-of-window sessions excluded.
    assert [s["id"] for s in result["sessions"]] == ["e2", "e1"]
    assert result["sessions"][0]["continuation"] is True and result["sessions"][0]["kind"] == "root"
    text = json.dumps(result)
    assert SECRET not in text and "title" not in result["sessions"][0] and "cost" not in result["sessions"][0]
    assert result["sessions"][0]["model"] == "anthropic/opus"


@pytest.mark.parametrize("source", ["api", "db"])
def test_list_filters_and_opt_ins(root, source):
    everything = run(root, action="list", source=source, kind="all", archived=True, **window())
    assert {s["id"] for s in everything["sessions"]} == {"e1", "e2", "e1-sub", "a1"}
    assert [s["id"] for s in run(root, action="list", source=source, platform="subagent", kind="all",
                                 **window())["sessions"]] == ["e1-sub"]
    assert [s["id"] for s in run(root, action="list", source=source, profile="assistant", archived=True,
                                 **window())["sessions"]] == ["a1"]
    shown = run(root, action="list", source=source, include_title=True, include_cost=True, **window())
    assert shown["sessions"][1]["title"].startswith("TITLE e1") and shown["sessions"][1]["cost"] == 0.5
    assert [s["id"] for s in run(root, action="list", source=source, kind="child", **window())["sessions"]] \
        == ["e1-sub"]


@pytest.mark.parametrize("source", ["api", "db"])
def test_get_carries_lineage_and_children(root, source):
    got = run(root, action="get", session_id="e2", source=source)["session"]
    assert got["profile"] == "engineer" and got["lineage"] == ["e1", "e2"]
    kids = run(root, action="children", session_id="e1", source=source)["sessions"]
    assert [k["id"] for k in kids] == ["e1-sub", "e2"]
    with pytest.raises(ValueError, match="not found"):
        run(root, action="get", session_id="missing", source=source)


def test_store_failure_falls_back_and_says_so(root):
    class Broken:
        def __init__(self, paths):
            pass

        def __enter__(self):
            raise hermes.Unavailable("store moved")

        def __exit__(self, *exc):
            return False

    result = hermes.run({"action": "list", **window()}, root=root, store_factory=Broken)
    assert result["source"] == "db" and result["diagnostics"][0]["code"] == "api-unavailable"
    assert result["status"] == "complete"
    with pytest.raises(hermes.Unavailable):
        hermes.run({"action": "list", "source": "api"}, root=root, store_factory=Broken)


def test_databases_are_not_modified(root):
    paths = hermes.profiles(root)
    before = {n: p.read_bytes() for n, p in paths.items()}
    for source in ("api", "db"):
        run(root, action="list", source=source, kind="all", archived=True)
        run(root, action="get", session_id="e2", source=source)
    run(root, action="usage", **window())
    assert {n: p.read_bytes() for n, p in paths.items()} == before


# ------------------------------------------------------------------ usage

def test_usage_counts_agent_work_not_waits_or_idle(root):
    result = run(root, action="usage", group_by=["profile"], **window())
    by = {g["key"]["profile"]: g for g in result["groups"]}
    eng = by["engineer"]
    # e1: 5 min + (clarify 30 min wait) + 5 min + opencode 15 min + 5 min + 100 s; the tail copied
    # into e2 counts once; e2's new turn 100 s; sub: 5 min.
    assert eng["active_seconds"] == 5 * 60 + 5 * 60 + 15 * 60 + 5 * 60 + 100 + 100 + 5 * 60
    assert eng["sessions"] == 3
    assert eng["question_wait_seconds"] == 30 * 60
    assert eng["opencode_wait_seconds"] == 15 * 60
    # The subagent's 5 min lie inside e1's first 5 min: union removes them.
    assert eng["active_union_seconds"] == eng["active_seconds"] - 5 * 60
    # Archived sessions count in usage; the assistant's 20 min contain engineer's first 5.
    assert by["assistant"]["active_seconds"] == 20 * 60
    totals = result["totals"]
    assert totals["active_union_seconds"] == 20 * 60 + (eng["active_union_seconds"] - 5 * 60)
    assert SECRET not in json.dumps(result) and "cost" not in totals
    assert result["status"] == "partial"             # only because of the crossing usage row
    assert [d["code"] for d in result["diagnostics"]] == ["usage-crosses-window"]


def test_usage_closes_gaps_open_at_the_window_end(root):
    eng = sqlite3.connect(root / "profiles" / "engineer" / "state.db")
    _session(eng, "late", S + 86000)
    for t, role, tool in ((86000, "user", None), (86100, "assistant", None), (87000, "tool", "opencode_call")):
        _msg(eng, "late", S + t, role, tool)
    eng.commit()
    eng.close()
    result = run(root, action="usage", platform="cli", kind="root", profile="engineer",
                 **{"from": iso(S + 80000), "to": iso(S + 86400)})
    assert result["totals"]["active_seconds"] == 100 + 300
    assert result["totals"]["opencode_wait_seconds"] == 300


@pytest.mark.parametrize("tool, counted", [
    ("opencode_call", True),            # the retired plugin: past sessions still carry it
    ("opencode_run_plan", True),        # opencode: one run tool per configured role
    ("opencode_run_any_role", True),
    ("opencode_request", True),         # a reply blocks until the run's next hand-back
    ("opencode_session", False),        # status/diff/steer: ordinary work, not a wait on a run
    ("opencode_catalog", False),
])
def test_waits_on_opencode_runs_are_reported_separately(root, tool, counted):
    eng = sqlite3.connect(root / "profiles" / "engineer" / "state.db")
    _session(eng, "waiting", S + 86000)
    for t, role, name in ((86000, "user", None), (86100, "assistant", None), (87000, "tool", tool)):
        _msg(eng, "waiting", S + t, role, name)
    eng.commit()
    eng.close()
    result = run(root, action="usage", platform="cli", kind="root", profile="engineer",
                 **{"from": iso(S + 80000), "to": iso(S + 86400)})
    assert result["totals"]["active_seconds"] == 100 + 300
    assert result["totals"]["opencode_wait_seconds"] == (300 if counted else 0)


def test_one_unreadable_profile_is_disclosed_not_fatal(root):
    (root / "profiles" / "broken").mkdir()
    conn = sqlite3.connect(root / "profiles" / "broken" / "state.db")
    conn.execute("CREATE TABLE sessions (id TEXT)")
    conn.close()
    for action in ("usage", "list"):
        result = run(root, action=action, **window())
        assert result["status"] == "partial"
        assert {"code": "profile-unreadable", "profile": "broken"}.items() <= next(
            d for d in result["diagnostics"] if d["code"] == "profile-unreadable").items()
    assert run(root, action="usage", **window())["totals"]["sessions"] > 0


def test_usage_tokens_and_window_edges(root):
    result = run(root, action="usage", group_by=["task"], include_cost=True, **window())
    by = {g["key"]["task"]: g for g in result["groups"]}
    assert by["title_generation"]["tokens"]["output"] == 5
    assert result["totals"]["tokens"]["output"] == 105 and result["totals"]["api_calls"] == 4
    assert result["totals"]["cost"] == 0.5
    crossing = [d for d in result["diagnostics"] if d["code"] == "usage-crosses-window"]
    assert crossing and crossing[0]["output_tokens"] == 999 and result["status"] == "partial"


def test_usage_filters(root):
    only_sub = run(root, action="usage", platform="subagent", **window())
    assert only_sub["totals"]["active_seconds"] == 300 and only_sub["totals"]["sessions"] == 1
    for source in ("api", "db"):
        assert run(root, action="get", session_id="e1-sub", source=source)["session"]["lineage"] == ["e1-sub"]
    no_archived = run(root, action="usage", archived=False, profile="assistant", **window())
    assert no_archived["totals"]["sessions"] == 0
    gpt = run(root, action="usage", model="gpt", **window())
    assert gpt["totals"]["active_seconds"] == 300 and gpt["totals"]["tokens"]["output"] == 0


def test_intervals_for_cross_tool_union(root):
    result = hermes.run({"action": "usage", **window()}, root=root, keep_intervals=True)
    spans = result["totals"]["intervals_ms"]
    assert spans == common.merged(spans)
    assert sum(b - a for a, b in spans) == result["totals"]["active_union_seconds"] * 1000
    assert "intervals_ms" not in run(root, action="usage", **window())["totals"]


# ------------------------------------------------------------------ plugin

def _plugin():
    pytest.importorskip("hermes_constants")
    return _load("session_history_plugin_test", ROOT / "__init__.py")


@pytest.mark.parametrize("profile", ["writer", "creator", "marketer", "default", "engineer"])
def test_registration_is_assistant_only(profile):
    plugin = _plugin()

    class Context:
        profile_name = profile

        def register_tool(self, **kwargs):
            raise AssertionError("foreign profile gained hermes_history")

        def register_command(self, *args, **kwargs):
            raise AssertionError("foreign profile gained /activity")

    plugin.register(Context())


def test_tool_and_command(root, monkeypatch):
    plugin = _plugin()
    tools, commands = {}, {}

    class Context:
        profile_name = "assistant"

        def register_tool(self, **kwargs):
            tools[kwargs["name"]] = kwargs

        def register_command(self, name, handler, **kwargs):
            commands[name] = handler

    plugin.register(Context())
    tool = tools["hermes_history"]
    assert tool["toolset"] == "session_history"
    assert tool["schema"]["parameters"]["additionalProperties"] is False
    assert set(tool["schema"]["parameters"]["properties"]) == hermes.FIELDS
    monkeypatch.setenv("HERMES_ROOT", str(root))
    result = json.loads(tool["handler"]({"action": "list", **window()}))
    assert [s["id"] for s in result["sessions"]] == ["e2", "e1"]
    assert "error" in json.loads(tool["handler"]({"action": "nope"}))

    assert "Usage: /activity" in asyncio.run(commands["activity"]("yesterday"))
    seen = {}

    def fake_summary(args):
        seen.update(args)
        return {"action": "summary", "window": None, "status": "complete", "active_union_seconds": 60,
                "tools": {}}

    monkeypatch.setattr(plugin.cli, "summary", fake_summary)
    text = asyncio.run(commands["activity"]("week"))
    assert seen == {"days": 7} and text.startswith("## AI activity") and "**1m**" in text
