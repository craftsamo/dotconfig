import importlib.util
import json
from pathlib import Path
import shutil

import pytest

spec = importlib.util.spec_from_file_location("signal_access_fakes", Path(__file__).resolve().parent / "fakes.py")
fakes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fakes)

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("signal_access_plugin_test", ROOT / "__init__.py")
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)
store = plugin.sig.store


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    base = fakes.short_dir()
    monkeypatch.setenv(store.STATE_ENV, str(base))  # never the real state directory
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: False)
    monkeypatch.setattr(plugin.sig, "_agent_running", lambda: True)
    fakes.link_account(base)
    conn = store.connect(store.db_path(base), write=True)
    store.set_meta(conn, uuid=fakes.ME)
    store.upsert_contacts(conn, [{"uuid": fakes.ALICE, "number": "+819011111111", "givenName": "Alice"}])
    conn.close()
    plugin.sig._approved.clear()
    yield base
    shutil.rmtree(base, ignore_errors=True)


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


def test_only_the_assistant_gets_the_tool():
    ctx = Ctx("creator")
    plugin.register(ctx)
    assert ctx.tools == {} and ctx.hooks == []
    ctx = Ctx("assistant")
    plugin.register(ctx)
    assert set(ctx.tools) == {"signal"}
    tool = ctx.tools["signal"]
    assert tool["toolset"] == "signal_access" and tool["schema"]["name"] == "signal"
    params = tool["schema"]["parameters"]
    assert params["additionalProperties"] is False and params["required"] == ["action"]
    assert params["properties"]["action"]["enum"] == list(plugin.sig.ACTIONS)
    assert ctx.hooks == [("pre_tool_call", plugin.gate)]


def test_gate_asks_for_sends_only():
    assert plugin.gate(tool_name="signal", args={"action": "chats"}) is None
    directive = plugin.gate(tool_name="signal", args={"action": "send", "chat": fakes.ALICE, "text": "hi"})
    assert directive["action"] == "approve"
    assert directive["message"] == f"Account: {fakes.NUMBER}\nChat: Alice (+819011111111)\n\nhi"
    assert directive["rule_key"].startswith("signal-access:send:")


@pytest.mark.parametrize("args", [
    {"action": "send", "chat": "Alice", "text": "hi"},
    {"action": "send", "chat": fakes.ALICE, "text": " "},
    {"action": "send", "chat": fakes.ALICE, "files": ["/etc/hosts"]},
    {"action": "forward"},
])
def test_gate_blocks_invalid_calls_without_asking(args):
    assert plugin.gate(tool_name="signal", args=args)["action"] == "block"


def test_gate_blocks_ways_around_the_tool():
    directive = plugin.gate(tool_name="terminal", args={"command": "signal-cli send -m x +81"})
    assert directive == {"action": "block", "message": plugin.sig.BYPASS_MESSAGE}
    assert plugin.gate(tool_name="terminal", args={"command": "ls"}) is None


def test_gate_stops_running_what_was_unpacked_but_not_reading_it():
    folder = "~/Workspaces/.inbox/signal/chat-1/pack.unpacked"
    for command in (f"bash {folder}/run.sh", f"cd {folder} && ./run.sh", f"chmod +x {folder}/run.sh"):
        directive = plugin.gate(tool_name="terminal", args={"command": command})
        assert directive == {"action": "block", "message": plugin.sig.archives.RUN_MESSAGE}, command
    for command in (f"cat {folder}/notes.txt", f"python analyze.py {folder}/data.csv", f"ls {folder}"):
        assert plugin.gate(tool_name="terminal", args={"command": command}) is None, command


def test_inbound_a2a_is_refused(monkeypatch):
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    directive = plugin.gate(tool_name="signal", args={"action": "chats"})
    assert directive["action"] == "block" and "A2A" in directive["message"]
    result = json.loads(plugin.signal_tool({"action": "chats"}))
    assert result["ok"] is False and "A2A" in result["error"]


def test_handler_returns_json():
    result = json.loads(plugin.signal_tool({"action": "chats"}))
    assert result["ok"] is True and result["chats"] == []
    result = json.loads(plugin.signal_tool({"action": "messages"}))
    assert result["ok"] is False and "chat is required" in result["error"]
    assert json.loads(plugin.signal_tool("not a dict"))["ok"] is False


def test_send_without_the_gate_is_refused():
    result = json.loads(plugin.signal_tool({"action": "send", "chat": fakes.ALICE, "text": "hi"}))
    assert result["ok"] is False and "approval" in result["error"]


def test_the_approval_belongs_to_its_tool_call(monkeypatch):
    args = {"action": "send", "chat": fakes.ALICE, "text": "hi"}
    assert plugin.gate(tool_name="signal", args=args, tool_call_id="call-1")["action"] == "approve"
    monkeypatch.setattr(plugin, "_call_id", lambda: "call-2")
    assert "did not pass the approval" in json.loads(plugin.signal_tool(dict(args)))["error"]
    assert plugin.gate(tool_name="signal", args=args, tool_call_id="call-2")["action"] == "approve"
    # the record is found; with no daemon running the send then fails before dispatch
    assert "sync service is not running" in json.loads(plugin.signal_tool(dict(args)))["error"]


def test_call_id_comes_from_hermes_context():
    try:
        from tools.approval_context import set_current_observability_context, reset_current_observability_context
    except ImportError:
        pytest.skip("hermes-agent not importable")
    tokens = set_current_observability_context(tool_call_id="call-9")
    try:
        assert plugin._call_id() == "call-9"
    finally:
        reset_current_observability_context(tokens)


def test_oversized_results_are_refused(monkeypatch):
    monkeypatch.setattr(plugin.sig, "execute", lambda args, home=None, call_id="": {"x": "y" * plugin.LIMIT})
    result = json.loads(plugin.signal_tool({"action": "chats"}))
    assert result["ok"] is False and "narrow" in result["error"]


def test_the_skill_reaches_only_the_assistant():
    for profile, names in (("assistant", {"signal"}), ("marketer", set()), ("creator", set())):
        ctx = Ctx(profile)
        plugin.register(ctx)
        assert set(ctx.skills) == names
