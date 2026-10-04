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


plugin = _load("discord_access_plugin_test", ROOT / "__init__.py")
store = plugin.access.store
DM = "200000000000000001"


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv(store.STATE_ENV, str(tmp_path / "state"))
    monkeypatch.setattr(plugin.access, "call_engine", lambda *a, **k: pytest.fail("engine called"))
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: False)
    conn = store.connect(write=True)
    store.set_meta(conn, "me", {"id": "100000000000000001", "username": "me", "name": "Me"})
    store.upsert_channel(conn, store.channel_row({"id": DM, "type": 1, "recipients": [
        {"id": "100000000000000002", "username": "taro", "global_name": "Taro"}]}), 0)
    conn.commit()
    conn.close()


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
    assert set(ctx.tools) == {"discord_account"}
    tool = ctx.tools["discord_account"]
    assert tool["toolset"] == "discord_access" and tool["schema"]["name"] == "discord_account"
    params = tool["schema"]["parameters"]
    assert params["additionalProperties"] is False and params["required"] == ["action"]
    assert params["properties"]["action"]["enum"] == list(plugin.access.ACTIONS)
    assert ctx.hooks == [("pre_tool_call", plugin.gate), ("pre_tool_call", plugin.bind)]


def test_gate_asks_for_sends_only():
    assert plugin.gate(tool_name="discord_account", args={"action": "dms"}) is None
    directive = plugin.gate(tool_name="discord_account", args={"action": "send", "channel": DM, "text": "hi"})
    assert directive["action"] == "approve"
    assert directive["message"] == f"Discord: Me (@me)\nTo: DM with Taro (@taro)\nChannel id: {DM}\n\nhi"
    assert directive["rule_key"].startswith("discord-access:send:")


@pytest.mark.parametrize("args", [
    {"action": "send", "channel": "Taro", "text": "hi"},
    {"action": "send", "channel": "200000000000000099", "text": "hi"},
    {"action": "send", "channel": DM, "text": " "},
    {"action": "react"},
])
def test_gate_blocks_invalid_calls_without_asking(args):
    assert plugin.gate(tool_name="discord_account", args=args)["action"] == "block"


def test_gate_blocks_ways_around_the_tool():
    directive = plugin.gate(tool_name="terminal", args={"command": "secret get DISCORD_USER_TOKEN -p discord-user"})
    assert directive == {"action": "block", "message": plugin.access.BYPASS_MESSAGE}
    assert plugin.gate(tool_name="terminal", args={"command": "ls"}) is None


def test_the_bots_discord_tool_is_not_gated():
    assert plugin.gate(tool_name="discord", args={"action": "fetch_messages", "channel_id": DM}) is None


def test_inbound_a2a_is_refused(monkeypatch):
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    directive = plugin.gate(tool_name="discord_account", args={"action": "dms"})
    assert directive["action"] == "block" and "A2A" in directive["message"]
    result = json.loads(plugin.discord_account({"action": "dms"}))
    assert result["ok"] is False and "A2A" in result["error"]


def test_handler_returns_json():
    result = json.loads(plugin.discord_account({"action": "dms"}))
    assert result["ok"] is True and result["dms"][0]["channel"] == DM
    result = json.loads(plugin.discord_account({"action": "messages"}))
    assert result["ok"] is False and "channel is required" in result["error"]
    assert json.loads(plugin.discord_account("not a dict"))["ok"] is False


def test_oversized_results_are_refused(monkeypatch):
    monkeypatch.setattr(plugin.access, "execute", lambda args, home=None: {"x": "y" * plugin.LIMIT})
    result = json.loads(plugin.discord_account({"action": "dms"}))
    assert result["ok"] is False and "narrow" in result["error"]


def test_file_sends_are_staged_and_bound_to_the_call(tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "a.txt").write_text("hello")
    monkeypatch.setattr(plugin.access, "DEFAULT_ATTACH_ROOT", ws)
    monkeypatch.setattr(plugin, "_home", lambda: None)
    args = {"action": "send", "channel": DM, "files": [str(ws / "a.txt")]}
    payload = {"tool_name": "discord_account", "args": args, "tool_call_id": "call-1", "session_id": "s"}
    directive = plugin.gate(**payload)
    assert directive["action"] == "approve" and "Files (1): a.txt (5 B)" in directive["message"]
    modify = plugin.bind(**payload)
    assert modify["action"] == "modify" and len(modify["args"]["_outbox"]) == 32
    assert (plugin.access._outbox() / modify["args"]["_outbox"]).is_dir()
    assert plugin.gate(tool_name="discord_account", args=args)["action"] == "block"          # no call id
    forged = {**args, "_outbox": modify["args"]["_outbox"]}
    assert plugin.gate(tool_name="discord_account", args=forged, tool_call_id="call-2")["action"] == "block"
    assert plugin.bind(tool_name="discord_account", args={"action": "dms"}, tool_call_id="c") is None
    assert plugin.bind(tool_name="terminal", args=args, tool_call_id="c") is None
