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
    monkeypatch.setattr(plugin.xa, "execute", lambda args, home=None: {"x": "y" * plugin.LIMIT})
    result = json.loads(x({"action": "status"}))
    assert result["ok"] is False and "narrow" in result["error"]
