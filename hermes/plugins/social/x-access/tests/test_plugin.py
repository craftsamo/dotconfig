import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


plugin = _load("x_access_plugin_test", ROOT / "__init__.py")
x = plugin.handler_for("assistant")
gate = plugin.gate_for("assistant")


def fake_bridge(op, **fields):
    if op == "check":
        return {"ok": True, "data": None, "fingerprint": "fp", "contacted": False}
    if op == "search":
        return {"ok": True, "data": [], "warnings": [], "fingerprint": "fp", "contacted": True,
                "session": {"active": True, "locks": {}}}
    raise AssertionError(f"unexpected bridge call {op}")


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    (tmp_path / "python").write_text("")
    monkeypatch.setattr(plugin.xa, "STORE", tmp_path)  # never the real ~/.x-access
    monkeypatch.setattr(plugin.xa, "VENV_PYTHON", tmp_path / "python")
    monkeypatch.setattr(plugin.xa, "MIN_GAP", 0)
    monkeypatch.setattr(plugin.xa, "bridge", fake_bridge)
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: False)
    monkeypatch.setattr(plugin, "_home", lambda: tmp_path)


class Ctx:
    def __init__(self, profile):
        self.profile_name = profile
        self.tools = {}
        self.hooks = []
        self.skills = {}

    def register_skill(self, name, path, description="", frontmatter=None):
        assert path.is_file() and frontmatter["name"] == name and description
        self.skills[name] = path

    def register_tool(self, **kwargs):
        self.tools[kwargs["name"]] = kwargs

    def register_hook(self, name, callback):
        self.hooks.append((name, callback))


def test_the_assistant_and_marketer_get_the_tool():
    ctx = Ctx("creator")
    plugin.register(ctx)
    assert ctx.tools == {} and ctx.hooks == []
    for profile in ("assistant", "marketer"):
        ctx = Ctx(profile)
        plugin.register(ctx)
        assert set(ctx.tools) == {"x"}
        tool = ctx.tools["x"]
        assert tool["toolset"] == "x_access" and tool["schema"]["name"] == "x"
        params = tool["schema"]["parameters"]
        assert params["additionalProperties"] is False and params["required"] == ["action"]
        assert params["properties"]["action"]["enum"] == list(plugin.xa.ACTIONS)
        assert params["properties"]["at"]["enum"] == list(plugin.xa.CHECKPOINTS)
        assert [name for name, _ in ctx.hooks] == ["pre_tool_call"]
        assert json.loads(tool["handler"]({"action": "status"}, task_id="t"))["ok"] is True


def test_there_is_no_write_action():
    assert not {"post", "reply", "send", "like", "follow", "dm"} & set(plugin.xa.ACTIONS)


def test_gate_lets_reads_through_and_blocks_ways_around():
    assert gate(tool_name="x", args={"action": "search", "query": "a"}) is None
    directive = gate(tool_name="terminal", args={"command": "twscrape search a"})
    assert directive == {"action": "block", "message": plugin.xa.BYPASS_MESSAGE}
    assert gate(tool_name="terminal", args={"command": "ls"}) is None


def test_inbound_a2a_is_refused_on_the_assistant(monkeypatch, tmp_path):
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    monkeypatch.setattr(plugin, "_home", lambda: tmp_path / "profiles" / "assistant")
    directive = gate(tool_name="x", args={"action": "status"})
    assert directive["action"] == "block" and "A2A" in directive["message"]
    result = json.loads(x({"action": "status"}))
    assert result["ok"] is False and "A2A" in result["error"]


def test_inbound_a2a_reads_on_marketer_only_in_its_own_home(monkeypatch, tmp_path):
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    marketer_x, marketer_gate = plugin.handler_for("marketer"), plugin.gate_for("marketer")
    monkeypatch.setattr(plugin, "_home", lambda: tmp_path / "profiles" / "marketer")
    assert marketer_gate(tool_name="x", args={"action": "status"}) is None
    assert json.loads(marketer_x({"action": "status"}))["ok"] is True
    # an unbound or foreign home fails closed
    for home in (None, tmp_path / ".hermes", tmp_path / "profiles" / "assistant"):
        monkeypatch.setattr(plugin, "_home", lambda home=home: home)
        assert marketer_gate(tool_name="x", args={"action": "status"})["action"] == "block"
        assert json.loads(marketer_x({"action": "status"}))["ok"] is False
    # the bypass guard still applies on Marketer
    assert marketer_gate(tool_name="terminal", args={"command": "twscrape search a"})["action"] == "block"


def test_handler_returns_json():
    result = json.loads(x({"action": "status"}))
    assert result["ok"] is True and result["cookies"] is True
    result = json.loads(x({"action": "search", "query": "a"}))
    assert result["ok"] is True and result["posts"] == []
    result = json.loads(x({"action": "search"}))
    assert result["ok"] is False and "query is required" in result["error"]
    assert json.loads(x("not a dict"))["ok"] is False


def test_oversized_results_are_refused(monkeypatch):
    monkeypatch.setattr(plugin.xa, "execute", lambda args, home=None, profile=None: {"x": "y" * plugin.LIMIT})
    result = json.loads(x({"action": "status"}))
    assert result["ok"] is False and "narrow" in result["error"]


PUBLIC_ACTIONS = ["status", "search", "thread", "verify"]
MAIN_ACCOUNT_ACTIONS = ["posts", "mentions", "snapshot", "insights", "media", "user"]


def test_searcher_gets_only_the_public_reads():
    ctx = Ctx("searcher")
    plugin.register(ctx)
    assert set(ctx.tools) == {"x"} and [name for name, _ in ctx.hooks] == ["pre_tool_call"]
    schema = ctx.tools["x"]["schema"]
    assert schema["parameters"]["properties"]["action"]["enum"] == PUBLIC_ACTIONS
    assert set(schema["parameters"]["properties"]) == {"action", "query", "top", "post", "limit", "posts"}
    assert schema["parameters"]["additionalProperties"] is False
    for action in MAIN_ACCOUNT_ACTIONS:
        assert action not in schema["parameters"]["properties"]["action"]["enum"]
    assert "main account" not in schema["description"] and "x_search" in schema["description"]
    assert "only when x_search is not available" in schema["description"]


def test_the_draft_skill_reaches_only_the_profile_that_saves_drafts():
    expected = {"assistant": {"x-twitter", "x-twitter-drafts"}, "marketer": {"x-twitter"},
                "searcher": {"x-twitter"}, "creator": set()}
    for profile, names in expected.items():
        ctx = Ctx(profile)
        plugin.register(ctx)
        assert set(ctx.skills) == names
    for profile in ("marketer", "searcher"):
        ctx = Ctx(profile)
        plugin.register(ctx)
        for path in ctx.skills.values():
            body = path.read_text().lower()
            assert not any(word in body for word in ("post-draft", "article-draft", "composer", "editor"))
        assert 'x-access:x-twitter"' in ctx.tools["x"]["description"]


def test_a_broken_skill_never_costs_the_tool(monkeypatch):
    monkeypatch.setitem(plugin.SKILLS, "missing", {"assistant"})
    ctx = Ctx("assistant")
    plugin.register(ctx)
    assert set(ctx.tools) == {"x"} and "missing" not in ctx.skills


def test_other_profiles_keep_every_action():
    for profile in ("assistant", "marketer"):
        assert plugin.xa.actions_for(profile) == plugin.xa.ACTIONS
    assert plugin.xa.actions_for("creator") == () and plugin.xa.actions_for(None) == plugin.xa.ACTIONS


@pytest.mark.parametrize("action", MAIN_ACCOUNT_ACTIONS)
def test_searcher_is_refused_the_other_actions_at_every_layer(action):
    searcher_x, searcher_gate = plugin.handler_for("searcher"), plugin.gate_for("searcher")
    args = {"action": action, "handle": "@someone", "query": "a", "post": "https://x.com/a/status/1"}
    directive = searcher_gate(tool_name="x", args=args)
    assert directive["action"] == "block" and "not available to this profile" in directive["message"]
    result = json.loads(searcher_x(args))
    assert result["ok"] is False and "not available to this profile" in result["error"]
    with pytest.raises(plugin.xa.XError, match="action must be one of status, search, thread, verify"):
        plugin.xa.execute(args, profile="searcher")


def count_search_calls(monkeypatch):
    """Route every X read to a fake bridge that answers a search and counts it."""
    seen = []

    def bridge(op, **fields):
        seen.append(op)
        return fake_bridge("search" if op != "check" else op, **fields)
    monkeypatch.setattr(plugin.xa, "bridge", bridge)
    return seen


def test_searcher_search_works_and_is_counted_apart(monkeypatch):
    seen = count_search_calls(monkeypatch)
    searcher_x = plugin.handler_for("searcher")
    result = json.loads(searcher_x({"action": "search", "query": "from:a lang:ja", "top": True}))
    assert result["ok"] is True and result["tab"] == "top" and seen == ["search"]
    state = plugin.xa._read_state()
    assert len(state["calls"]) == 1 and len(state["by_profile"]["searcher"]) == 1
    status = json.loads(searcher_x({"action": "status"}))["usage"]
    assert status["this_profile"] == {"last_hour": 1, "last_day": 1, "hourly_cap": 20, "daily_cap": 120}
    assert "this_profile" not in json.loads(x({"action": "status"}))["usage"]


def test_other_profiles_reads_are_not_counted_against_searcher(monkeypatch):
    count_search_calls(monkeypatch)
    for _ in range(3):
        assert json.loads(x({"action": "search", "query": "a"}))["ok"] is True
    state = plugin.xa._read_state()
    assert len(state["calls"]) == 3 and "by_profile" not in state
    searcher_status = json.loads(plugin.handler_for("searcher")({"action": "status"}))["usage"]
    assert searcher_status["last_hour"] == 3 and searcher_status["this_profile"]["last_hour"] == 0


def test_searcher_share_stops_it_while_the_others_can_still_read(monkeypatch):
    count_search_calls(monkeypatch)
    monkeypatch.setitem(plugin.xa.PROFILE_CAPS, "searcher", (2, 3))
    searcher_x = plugin.handler_for("searcher")
    for _ in range(2):
        assert json.loads(searcher_x({"action": "search", "query": "a"}))["ok"] is True
    blocked = json.loads(searcher_x({"action": "search", "query": "a"}))
    assert blocked["ok"] is False and "this profile's share" in blocked["error"] and "in the last hour" in blocked["error"]
    # the shared caps (30 an hour) are nowhere near used, so the Assistant still reads
    assert json.loads(x({"action": "search", "query": "a"}))["ok"] is True
    assert len(plugin.xa._read_state()["calls"]) == 3


def test_searcher_daily_share(monkeypatch):
    count_search_calls(monkeypatch)
    monkeypatch.setitem(plugin.xa.PROFILE_CAPS, "searcher", (5, 2))
    searcher_x = plugin.handler_for("searcher")
    for _ in range(2):
        assert json.loads(searcher_x({"action": "search", "query": "a"}))["ok"] is True
    blocked = json.loads(searcher_x({"action": "search", "query": "a"}))
    assert blocked["ok"] is False and "in the last 24 hours" in blocked["error"]


def test_searcher_share_ages_out(monkeypatch):
    count_search_calls(monkeypatch)
    monkeypatch.setitem(plugin.xa.PROFILE_CAPS, "searcher", (1, 5))
    searcher_x = plugin.handler_for("searcher")
    assert json.loads(searcher_x({"action": "search", "query": "a"}))["ok"] is True
    state = plugin.xa._read_state()
    old = [t - 4000 for t in state["by_profile"]["searcher"]]   # more than an hour ago
    state["by_profile"]["searcher"], state["calls"] = old, [t - 4000 for t in state["calls"]]
    with plugin.xa._lock():
        plugin.xa._write_state(state)
    assert json.loads(searcher_x({"action": "search", "query": "a"}))["ok"] is True


def test_searcher_verify_costs_no_share(monkeypatch):
    count_search_calls(monkeypatch)
    state_before = plugin.xa._read_state()
    monkeypatch.setattr(plugin.xa, "verify", lambda args, home: {"ok": True, "action": "verify"})
    assert json.loads(plugin.handler_for("searcher")({"action": "verify", "posts": ["1"]}))["ok"] is True
    assert plugin.xa._read_state() == state_before


def test_searcher_status_does_not_ask_for_a_main_handle():
    searcher_x = plugin.handler_for("searcher")
    result = json.loads(searcher_x({"action": "status"}))
    assert result["ok"] is True and "problem" not in result
    assistant_status = json.loads(x({"action": "status"}))
    assert assistant_status["problem"] == plugin.xa.NO_MAIN


def test_searcher_gate_allows_its_reads_and_keeps_the_bypass_guard():
    searcher_gate = plugin.gate_for("searcher")
    for action in PUBLIC_ACTIONS:
        assert searcher_gate(tool_name="x", args={"action": action}) is None
    assert searcher_gate(tool_name="terminal", args={"command": "twscrape search a"})["action"] == "block"


def test_inbound_a2a_is_refused_on_searcher(monkeypatch, tmp_path):
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    monkeypatch.setattr(plugin, "_home", lambda: tmp_path / "profiles" / "searcher")
    directive = plugin.gate_for("searcher")(tool_name="x", args={"action": "verify"})
    assert directive["action"] == "block" and "A2A" in directive["message"]
    assert json.loads(plugin.handler_for("searcher")({"action": "verify"}))["ok"] is False
