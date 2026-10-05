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


plugin = _load("substack_access_plugin_test", ROOT / "__init__.py")


def fake_bridge(op, **fields):
    if op == "check":
        return {"ok": True, "data": None, "fingerprint": "fp", "contacted": False}
    if op == "inbox":
        return {"ok": True, "data": {"posts": [], "publications": {}}, "fingerprint": "fp", "contacted": True,
                "session": {"active": True}}
    raise AssertionError(f"unexpected bridge call {op}")


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    (tmp_path / "python").write_text("")
    monkeypatch.setattr(plugin.sa, "STORE", tmp_path)  # never the real ~/.substack-access
    monkeypatch.setattr(plugin.sa, "VENV_PYTHON", tmp_path / "python")
    monkeypatch.setattr(plugin.sa, "MIN_GAP", 0)
    monkeypatch.setattr(plugin.sa, "bridge", fake_bridge)
    monkeypatch.setattr(plugin.sa, "_config", lambda home: {})
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: False)
    monkeypatch.setattr(plugin, "_home", lambda: tmp_path)


class Ctx:
    def __init__(self, profile):
        self.profile_name = profile
        self.tools = {}
        self.hooks = []

    def register_tool(self, **kwargs):
        self.tools[kwargs["name"]] = kwargs

    def register_hook(self, name, callback):
        self.hooks.append((name, callback))


def registered(profile):
    ctx = Ctx(profile)
    plugin.register(ctx)
    return ctx


def test_only_the_assistant_and_marketer_get_the_tool():
    for profile in ("creator", "engineer", "default"):
        ctx = registered(profile)
        assert ctx.tools == {} and ctx.hooks == []
    for profile in ("assistant", "marketer"):
        ctx = registered(profile)
        tool = ctx.tools["substack"]
        assert tool["toolset"] == "substack_access" and tool["schema"]["name"] == "substack"
        params = tool["schema"]["parameters"]
        assert params["additionalProperties"] is False and params["required"] == ["action"]
        assert [name for name, _ in ctx.hooks] == ["pre_tool_call"]


def test_marketer_sees_only_reads():
    assistant = registered("assistant").tools["substack"]["schema"]
    marketer = registered("marketer").tools["substack"]["schema"]
    assert assistant["parameters"]["properties"]["action"]["enum"] == list(plugin.sa.ACTIONS)
    assert marketer["parameters"]["properties"]["action"]["enum"] == list(plugin.sa.READS)
    assert "never create, change, publish or post" in marketer["description"]


def test_marketer_cannot_call_a_write_even_by_name(monkeypatch):
    monkeypatch.setattr(plugin.sa, "WRITES", ("publish",))
    monkeypatch.setattr(plugin.sa, "ACTIONS", plugin.sa.READS + ("publish",))
    monkeypatch.setattr(plugin.sa, "PROFILE_ACTIONS", {"assistant": plugin.sa.ACTIONS, "marketer": plugin.sa.READS})
    handler = registered("marketer").tools["substack"]["handler"]
    result = json.loads(handler({"action": "publish", "draft": "1"}))
    assert result["ok"] is False and "only read" in result["error"]


def test_handler_returns_json():
    handler = registered("assistant").tools["substack"]["handler"]
    result = json.loads(handler({"action": "status"}))
    assert result["ok"] is True and result["cookies"] is True
    result = json.loads(handler({"action": "inbox"}))
    assert result["ok"] is True and result["posts"] == []
    result = json.loads(handler({"action": "post"}))
    assert result["ok"] is False and "post is required" in result["error"]
    assert json.loads(handler("not a dict"))["ok"] is False


def test_inbound_a2a_reaches_only_marketer_reads(monkeypatch):
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    assistant, marketer = registered("assistant"), registered("marketer")
    gate = assistant.hooks[0][1]
    directive = gate(tool_name="substack", args={"action": "status"})
    assert directive["action"] == "block" and "A2A" in directive["message"]
    result = json.loads(assistant.tools["substack"]["handler"]({"action": "status"}))
    assert result["ok"] is False and "A2A" in result["error"]
    assert marketer.hooks[0][1](tool_name="substack", args={"action": "inbox"}) is None
    assert json.loads(marketer.tools["substack"]["handler"]({"action": "inbox"}))["ok"] is True
    monkeypatch.setattr(plugin.sa, "WRITES", ("publish",))
    directive = marketer.hooks[0][1](tool_name="substack", args={"action": "publish"})
    assert directive["action"] == "block" and "cannot write" in directive["message"]


def test_gate_lets_reads_through_and_blocks_ways_around():
    for profile in ("assistant", "marketer"):
        gate = registered(profile).hooks[0][1]
        assert gate(tool_name="substack", args={"action": "inbox"}) is None
        directive = gate(tool_name="terminal", args={"command": "secret get SUBSTACK_COOKIES"})
        assert directive == {"action": "block", "message": plugin.sa.BYPASS_MESSAGE}
        assert gate(tool_name="terminal", args={"command": "ls"}) is None


def test_oversized_results_are_refused(monkeypatch):
    monkeypatch.setattr(plugin.sa, "execute", lambda args, home=None, profile=None: {"x": "y" * plugin.LIMIT})
    result = json.loads(registered("assistant").tools["substack"]["handler"]({"action": "status"}))
    assert result["ok"] is False and "narrow" in result["error"]
