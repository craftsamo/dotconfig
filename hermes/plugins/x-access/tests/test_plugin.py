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

    def register_tool(self, **kwargs):
        self.tools[kwargs["name"]] = kwargs

    def register_hook(self, name, callback):
        self.hooks.append((name, callback))


def test_only_the_assistant_gets_the_tool():
    ctx = Ctx("creator")
    plugin.register(ctx)
    assert ctx.tools == {} and ctx.hooks == []
    ctx = Ctx("assistant")
    plugin.register(ctx)
    assert set(ctx.tools) == {"x"}
    tool = ctx.tools["x"]
    assert tool["toolset"] == "x_access" and tool["schema"]["name"] == "x"
    params = tool["schema"]["parameters"]
    assert params["additionalProperties"] is False and params["required"] == ["action"]
    assert params["properties"]["action"]["enum"] == list(plugin.xa.ACTIONS)
    assert ctx.hooks == [("pre_tool_call", plugin.gate)]


def test_there_is_no_write_action():
    assert not {"post", "reply", "send", "like", "follow", "dm"} & set(plugin.xa.ACTIONS)


def test_gate_lets_reads_through_and_blocks_ways_around():
    assert plugin.gate(tool_name="x", args={"action": "search", "query": "a"}) is None
    directive = plugin.gate(tool_name="terminal", args={"command": "twscrape search a"})
    assert directive == {"action": "block", "message": plugin.xa.BYPASS_MESSAGE}
    assert plugin.gate(tool_name="terminal", args={"command": "ls"}) is None


def test_inbound_a2a_is_refused(monkeypatch):
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    directive = plugin.gate(tool_name="x", args={"action": "status"})
    assert directive["action"] == "block" and "A2A" in directive["message"]
    result = json.loads(plugin.x({"action": "status"}))
    assert result["ok"] is False and "A2A" in result["error"]


def test_handler_returns_json():
    result = json.loads(plugin.x({"action": "status"}))
    assert result["ok"] is True and result["cookies"] is True
    result = json.loads(plugin.x({"action": "search", "query": "a"}))
    assert result["ok"] is True and result["posts"] == []
    result = json.loads(plugin.x({"action": "search"}))
    assert result["ok"] is False and "query is required" in result["error"]
    assert json.loads(plugin.x("not a dict"))["ok"] is False


def test_oversized_results_are_refused(monkeypatch):
    monkeypatch.setattr(plugin.xa, "execute", lambda args, home=None: {"x": "y" * plugin.LIMIT})
    result = json.loads(plugin.x({"action": "status"}))
    assert result["ok"] is False and "narrow" in result["error"]
