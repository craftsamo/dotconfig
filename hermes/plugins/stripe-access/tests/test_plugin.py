import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("stripe_access_plugin_test", ROOT / "__init__.py")
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)
sta = plugin.sta


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(sta, "STORE", tmp_path)  # never the real ~/.stripe-access
    calls = []

    def fake_bridge(op, **fields):
        calls.append({"op": op, **fields})
        if op == "keys":
            return {"ok": True, "data": [], "requests": 0}
        return {"ok": True, "account": "work", "mode": fields.get("mode"), "requests": 1, "fingerprint": "f" * 12,
                "data": {"object": "list", "data": [], "has_more": False}}
    monkeypatch.setattr(sta, "bridge", fake_bridge)
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: False)
    monkeypatch.setattr(plugin, "_home", lambda: None)
    return calls


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


def registered(profile):
    ctx = Ctx(profile)
    plugin.register(ctx)
    return ctx


def handler_and_gate(profile):
    ctx = registered(profile)
    return ctx.tools["stripe"]["handler"], ctx.hooks[0][1]


def test_the_progress_line_shows_the_action_and_mode_only(monkeypatch):
    display = pytest.importorskip("agent.display")
    monkeypatch.setattr(display, "_PREVIEW_BUILDERS", {})
    registered("researcher")
    line = lambda **args: display.build_tool_preview("stripe", args, max_len=0)
    assert line(action="customers", mode="live", query="email:'someone@example.com'") == "customers live"
    assert line(action="status") == "status"
    assert line(action="anything", mode="prod", query="secret") is None


def test_assistant_researcher_and_marketer_get_the_tool_others_nothing():
    for profile in ("searcher", "writer", "creator", "default", "engineer"):
        ctx = registered(profile)
        assert ctx.tools == {} and ctx.hooks == [] and ctx.skills == {}
    for profile in ("assistant", "researcher", "marketer"):
        ctx = registered(profile)
        tool = ctx.tools["stripe"]
        assert tool["toolset"] == "stripe_access" and tool["schema"]["name"] == "stripe"
        params = tool["schema"]["parameters"]
        assert params["additionalProperties"] is False and params["required"] == ["action"]
        assert params["properties"]["action"]["enum"] == list(plugin.PROFILES[profile])
        assert params["properties"]["mode"]["enum"] == ["live", "test"]
        assert 'skill_view(name="stripe-access:stripe")' in tool["description"]
        assert [name for name, _ in ctx.hooks] == ["pre_tool_call"]
        assert set(ctx.skills) == {"stripe"}


def test_the_read_profiles_hold_reads_only():
    for profile in ("researcher", "marketer"):
        assert set(plugin.PROFILES[profile]) == set(sta.READS)
        assert not set(plugin.PROFILES[profile]) & set(sta.WRITES)
    assert "assistant" not in plugin.A2A


def test_a_read_reaches_the_engine(isolated):
    handler, gate = handler_and_gate("researcher")
    args = {"action": "invoices", "mode": "live", "status": "open"}
    assert gate(tool_name="stripe", args=args) is None
    result = json.loads(handler(args))
    assert result["ok"] is True and result["action"] == "invoices"
    assert isolated[-1]["path"] == "/v1/invoices" and ["status", "open"] in isolated[-1]["params"]


def test_an_action_outside_the_schema_is_refused_by_gate_and_handler(isolated):
    handler, gate = handler_and_gate("marketer")
    args = {"action": "refund_create", "mode": "live"}
    assert gate(tool_name="stripe", args=args)["action"] == "block"
    assert json.loads(handler(args))["ok"] is False
    assert isolated == []


def test_inbound_a2a_reads_only_on_the_profile_it_is_bound_to(monkeypatch, isolated):
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    args = {"action": "balance", "mode": "live"}
    handler, gate = handler_and_gate("assistant")
    directive = gate(tool_name="stripe", args=args)
    assert directive["action"] == "block" and "A2A" in directive["message"]
    assert "A2A" in json.loads(handler(args))["error"]
    handler, gate = handler_and_gate("researcher")
    monkeypatch.setattr(plugin, "_home", lambda: Path("/h/profiles/marketer"))
    assert gate(tool_name="stripe", args=args)["action"] == "block"
    monkeypatch.setattr(plugin, "_home", lambda: None)
    assert gate(tool_name="stripe", args=args)["action"] == "block"
    monkeypatch.setattr(plugin, "_home", lambda: Path("/h/profiles/researcher"))
    assert gate(tool_name="stripe", args=args) is None
    assert json.loads(handler(args))["ok"] is True
    assert [c["op"] for c in isolated] == ["call"]


def test_a_result_too_long_asks_to_narrow(monkeypatch):
    monkeypatch.setattr(plugin, "LIMIT", 10)
    handler, _ = handler_and_gate("assistant")
    result = json.loads(handler({"action": "customers", "mode": "live"}))
    assert result["ok"] is False and "narrow it" in result["error"]


def test_engine_errors_come_back_as_json():
    handler, _ = handler_and_gate("assistant")
    result = json.loads(handler({"action": "customers"}))
    assert result == {"ok": False, "error": "mode is required: live (real money) or test (a test or sandbox key)"}
    assert json.loads(handler(None))["ok"] is False


def test_the_hook_blocks_ways_around_the_tool():
    _, gate = handler_and_gate("marketer")
    directive = gate(tool_name="terminal", args={"command": "stripe invoices list"})
    assert directive == {"action": "block", "message": sta.BYPASS_MESSAGE}
    assert gate(tool_name="read_file", args={"path": "/Users/x/.stripe-access/state.json"})["action"] == "block"
    assert gate(tool_name="terminal", args={"command": "ls"}) is None
