import importlib.util
import json
from pathlib import Path
import shutil

import pytest

spec = importlib.util.spec_from_file_location("telegram_access_fakes", Path(__file__).resolve().parent / "fakes.py")
fakes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fakes)

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("telegram_access_plugin_test", ROOT / "__init__.py")
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)
store = plugin.tg.store


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    base = fakes.short_dir()
    monkeypatch.setenv(store.STATE_ENV, str(base))  # never the real state directory
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: False)
    monkeypatch.setattr(plugin, "_home", lambda: base)
    monkeypatch.setattr(plugin.tg, "_agent_running", lambda: True)
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: None)  # a person is present
    fakes.seed(base)
    plugin.tg._approved.clear()
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
    assert set(ctx.tools) == {"telegram_account"}
    tool = ctx.tools["telegram_account"]
    assert tool["toolset"] == "telegram_access" and tool["schema"]["name"] == "telegram_account"
    params = tool["schema"]["parameters"]
    assert params["additionalProperties"] is False and params["required"] == ["action"]
    assert params["properties"]["action"]["enum"] == list(plugin.tg.ACTIONS)
    assert ctx.hooks == [("pre_tool_call", plugin.gate)]


def test_gate_asks_for_sends_only():
    assert plugin.gate(tool_name="telegram_account", args={"action": "chats"}) is None
    directive = plugin.gate(tool_name="telegram_account",
                            args={"action": "send", "chat": str(fakes.ALICE), "text": "hi"})
    assert directive["action"] == "approve"
    assert directive["message"] == "Telegram: Rui (@rui)\nChat: Alice (@alice)\n\nhi"
    assert directive["rule_key"].startswith("telegram-access:send:")


@pytest.mark.parametrize("args", [
    {"action": "send", "chat": "Alice", "text": "hi"},
    {"action": "send", "chat": str(fakes.ALICE), "text": " "},
    {"action": "send", "chat": str(fakes.ALICE), "files": ["/etc/hosts"]},
    {"action": "forward"},
])
def test_gate_blocks_invalid_calls_without_asking(args):
    assert plugin.gate(tool_name="telegram_account", args=args)["action"] == "block"


def test_gate_blocks_ways_around_the_tool():
    directive = plugin.gate(tool_name="terminal", args={"command": "python3 -m telethon"})
    assert directive == {"action": "block", "message": plugin.tg.BYPASS_MESSAGE}
    assert plugin.gate(tool_name="terminal", args={"command": "ls"}) is None


def test_gate_stops_running_what_was_unpacked_but_not_reading_it():
    folder = "~/Workspaces/.inbox/telegram/9-1/pack.unpacked"
    for command in (f"bash {folder}/run.sh", f"cd {folder} && ./run.sh", f"chmod +x {folder}/run.sh"):
        directive = plugin.gate(tool_name="terminal", args={"command": command})
        assert directive == {"action": "block", "message": plugin.tg.archives.RUN_MESSAGE}, command
    for command in (f"cat {folder}/notes.txt", f"python analyze.py {folder}/data.csv", f"ls {folder}"):
        assert plugin.gate(tool_name="terminal", args={"command": command}) is None, command


def test_inbound_a2a_is_refused(monkeypatch):
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    directive = plugin.gate(tool_name="telegram_account", args={"action": "chats"})
    assert directive["action"] == "block" and "A2A" in directive["message"]
    result = json.loads(plugin.telegram_account({"action": "chats"}))
    assert result["ok"] is False and "A2A" in result["error"]


def test_sends_are_refused_without_a_person(monkeypatch):
    monkeypatch.setattr(plugin, "_unattended", lambda: True)
    args = {"action": "send", "chat": str(fakes.ALICE), "text": "hi"}
    directive = plugin.gate(tool_name="telegram_account", args=args, tool_call_id="call-1")
    assert directive["action"] == "block" and "approve" in directive["message"]
    assert "nothing was sent" in json.loads(plugin.telegram_account(dict(args)))["error"]
    assert plugin.gate(tool_name="telegram_account", args={"action": "chats"}) is None
    assert json.loads(plugin.telegram_account({"action": "chats"}))["ok"] is True


NO_HUMAN = ["yolo mode is on", "approvals are off (approvals.mode: off)", "nobody is present to answer"]
SENDS = [{"action": "send", "chat": str(fakes.ALICE), "text": "hi"},
         {"action": "send", "chat": str(fakes.ALICE), "text": "hi", "files": ["~/Workspaces/a.txt"]}]


@pytest.mark.parametrize("reason", NO_HUMAN)
@pytest.mark.parametrize("args", SENDS)
def test_a_send_never_runs_where_no_person_can_answer_its_card(monkeypatch, isolated, reason, args):
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: reason)
    before = sorted(str(p) for p in isolated.rglob("*"))
    directive = plugin.gate(tool_name="telegram_account", args=dict(args), tool_call_id="call-1")
    assert directive["action"] == "block"
    assert reason in directive["message"] and "Nothing was sent or changed" in directive["message"]
    error = json.loads(plugin.telegram_account(dict(args)))
    assert error["ok"] is False and reason in error["error"] and "Nothing was sent or changed" in error["error"]
    assert not plugin.tg._approved
    assert sorted(str(p) for p in isolated.rglob("*")) == before


def test_reads_are_unaffected_where_no_person_is_present(monkeypatch):
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: "yolo mode is on")
    assert plugin.gate(tool_name="telegram_account", args={"action": "chats"}) is None
    assert json.loads(plugin.telegram_account({"action": "chats"}))["ok"] is True


def test_with_a_person_present_a_send_still_gets_a_card():
    directive = plugin.gate(tool_name="telegram_account", args=dict(SENDS[0]))
    assert directive["action"] == "approve"


def test_the_genuine_check_refuses_in_this_headless_run(monkeypatch):
    path = ROOT.parents[1] / "_shared" / "human_gate.py"
    gate_spec = importlib.util.spec_from_file_location("human_gate_genuine_test", path)
    genuine = importlib.util.module_from_spec(gate_spec)
    gate_spec.loader.exec_module(genuine)
    monkeypatch.setattr(plugin.human_gate, "no_human", genuine.no_human)
    assert genuine.no_human()
    assert plugin.gate(tool_name="telegram_account", args=dict(SENDS[0]))["action"] == "block"
    assert json.loads(plugin.telegram_account(dict(SENDS[0])))["ok"] is False


def test_cron_is_unattended():
    pytest.importorskip("tools.approval_context")
    import os
    os.environ["HERMES_CRON_SESSION"] = "1"
    try:
        assert plugin._unattended() is True
    finally:
        del os.environ["HERMES_CRON_SESSION"]
    assert plugin._unattended() is False


def test_handler_returns_json():
    result = json.loads(plugin.telegram_account({"action": "chats"}))
    assert result["ok"] is True and len(result["chats"]) == 7
    result = json.loads(plugin.telegram_account({"action": "messages"}))
    assert result["ok"] is False and "chat is required" in result["error"]
    assert json.loads(plugin.telegram_account("not a dict"))["ok"] is False


def test_the_approval_belongs_to_its_tool_call(monkeypatch):
    args = {"action": "send", "chat": str(fakes.ALICE), "text": "hi"}
    assert plugin.gate(tool_name="telegram_account", args=args, tool_call_id="call-1")["action"] == "approve"
    monkeypatch.setattr(plugin, "_call_id", lambda: "call-2")
    assert "did not pass the approval" in json.loads(plugin.telegram_account(dict(args)))["error"]
    assert plugin.gate(tool_name="telegram_account", args=args, tool_call_id="call-2")["action"] == "approve"
    # the record is found; with no agent running the send then fails before dispatch
    assert "not running" in json.loads(plugin.telegram_account(dict(args)))["error"]


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
    monkeypatch.setattr(plugin.tg, "execute", lambda args, home=None, call_id="": {"x": "y" * plugin.LIMIT})
    result = json.loads(plugin.telegram_account({"action": "chats"}))
    assert result["ok"] is False and "narrow" in result["error"]


def test_the_skill_reaches_only_the_assistant():
    for profile, names in (("assistant", {"telegram-account"}), ("marketer", set()), ("creator", set())):
        ctx = Ctx(profile)
        plugin.register(ctx)
        assert set(ctx.skills) == names
