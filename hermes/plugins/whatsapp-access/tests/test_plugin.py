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


plugin = _load("whatsapp_access_plugin_test", ROOT / "__init__.py")
DM = "819012345678@s.whatsapp.net"


def fake_run(args, *, account=None, write=False, timeout=None):
    if args[:2] == ["accounts", "list"]:
        return {"accounts": [{"name": "technicity"}]}
    if args[:2] == ["chats", "show"]:
        return {"jid": DM, "name": "Yamada Taro", "kind": "dm"}
    if args[:2] == ["chats", "list"]:
        return []
    raise AssertionError(f"unexpected wacli call {args}")


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    monkeypatch.setattr(plugin.wa, "run", fake_run)  # never the real wacli or ~/.wacli
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: False)


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
    assert set(ctx.tools) == {"whatsapp"}
    tool = ctx.tools["whatsapp"]
    assert tool["toolset"] == "whatsapp_access" and tool["schema"]["name"] == "whatsapp"
    params = tool["schema"]["parameters"]
    assert params["additionalProperties"] is False and params["required"] == ["action"]
    assert params["properties"]["action"]["enum"] == list(plugin.wa.ACTIONS)
    assert ctx.hooks == [("pre_tool_call", plugin.gate)]


def test_gate_asks_for_sends_only():
    assert plugin.gate(tool_name="whatsapp", args={"action": "chats"}) is None
    directive = plugin.gate(tool_name="whatsapp", args={
        "action": "send", "account": "technicity", "chat": DM, "text": "hi"})
    assert directive["action"] == "approve"
    assert directive["message"] == "Account: technicity\nChat: Yamada Taro (+819012345678)\n\nhi"
    assert directive["rule_key"].startswith("whatsapp-access:send:")


@pytest.mark.parametrize("args", [
    {"action": "send", "chat": DM, "text": "hi"},                               # no account
    {"action": "send", "account": "technicity", "chat": "Yamada", "text": "hi"},  # a name
    {"action": "send", "account": "technicity", "chat": DM, "text": " "},
    {"action": "forward"},
])
def test_gate_blocks_invalid_calls_without_asking(args):
    assert plugin.gate(tool_name="whatsapp", args=args)["action"] == "block"


def test_gate_blocks_ways_around_the_tool():
    directive = plugin.gate(tool_name="terminal", args={"command": "wacli send text --to x"})
    assert directive == {"action": "block", "message": plugin.wa.BYPASS_MESSAGE}
    assert plugin.gate(tool_name="terminal", args={"command": "ls"}) is None


def test_inbound_a2a_is_refused(monkeypatch):
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    directive = plugin.gate(tool_name="whatsapp", args={"action": "chats"})
    assert directive["action"] == "block" and "A2A" in directive["message"]
    result = json.loads(plugin.whatsapp({"action": "chats"}))
    assert result["ok"] is False and "A2A" in result["error"]


def test_handler_returns_json():
    result = json.loads(plugin.whatsapp({"action": "chats"}))
    assert result["ok"] is True and result["chats"] == [] and result["account"] == "technicity"
    result = json.loads(plugin.whatsapp({"action": "messages"}))
    assert result["ok"] is False and "chat is required" in result["error"]
    assert json.loads(plugin.whatsapp("not a dict"))["ok"] is False


def test_oversized_results_are_refused(monkeypatch):
    monkeypatch.setattr(plugin.wa, "execute", lambda args: {"x": "y" * plugin.LIMIT})
    result = json.loads(plugin.whatsapp({"action": "chats"}))
    assert result["ok"] is False and "narrow" in result["error"]
