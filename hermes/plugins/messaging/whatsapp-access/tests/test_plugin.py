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
        return {"accounts": [{"name": "work"}]}
    if args[:2] == ["chats", "show"]:
        return {"jid": DM, "name": "Yamada Taro", "kind": "dm"}
    if args[:2] == ["chats", "list"]:
        return []
    raise AssertionError(f"unexpected wacli call {args}")


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(plugin.wa, "run", fake_run)  # never the real wacli or ~/.wacli
    monkeypatch.setattr(plugin, "_home", lambda: tmp_path)  # never the real profile home or its send mandates
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: False)
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: None)   # a person is there to answer cards
    plugin.wa._approved.clear()
    plugin._DECISIONS.clear()


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


def test_the_progress_line_shows_the_action_only(monkeypatch):
    display = pytest.importorskip("agent.display")
    monkeypatch.setattr(display, "_PREVIEW_BUILDERS", {})
    plugin.register(Ctx("assistant"))
    line = lambda **args: display.build_tool_preview("whatsapp", args, max_len=0)
    assert line(action="search", query="someone's name", text="the private message") == "search"
    assert line(action="chats") == "chats"
    assert line(action="anything else", text="the private message") is None
    mandate_line = lambda **args: display.build_tool_preview("whatsapp_mandate", args, max_len=0)
    assert mandate_line(action="create", purpose="the private reason", chats=["x"]) == "create"
    assert mandate_line(action="list") == "list"
    assert mandate_line(action="anything else", purpose="the private reason") is None


def test_only_the_assistant_gets_the_tool():
    ctx = Ctx("creator")
    plugin.register(ctx)
    assert ctx.tools == {} and ctx.hooks == []
    ctx = Ctx("assistant")
    plugin.register(ctx)
    assert set(ctx.tools) == {"whatsapp", "whatsapp_mandate"}
    tool = ctx.tools["whatsapp"]
    assert tool["toolset"] == "whatsapp_access" and tool["schema"]["name"] == "whatsapp"
    params = tool["schema"]["parameters"]
    assert params["additionalProperties"] is False and params["required"] == ["action"]
    assert params["properties"]["action"]["enum"] == list(plugin.wa.ACTIONS)
    mandate = ctx.tools["whatsapp_mandate"]
    assert mandate["toolset"] == "whatsapp_access" and mandate["schema"]["name"] == "whatsapp_mandate"
    params = mandate["schema"]["parameters"]
    assert params["additionalProperties"] is False and params["required"] == ["action"]
    assert params["properties"]["action"]["enum"] == ["create", "list", "revoke"]
    assert set(params["properties"]) == {"action", "account", "chats", "per_hour", "max_chars", "days", "purpose",
                                         "mandate"}
    assert ctx.hooks == [("pre_tool_call", plugin.gate), ("pre_tool_call", plugin.bind)]


def test_gate_asks_for_sends_only():
    assert plugin.gate(tool_name="whatsapp", args={"action": "chats"}) is None
    directive = plugin.gate(tool_name="whatsapp", args={
        "action": "send", "account": "work", "chat": DM, "text": "hi"})
    assert directive["action"] == "approve"
    assert directive["message"] == ("WhatsApp · Send message\n⚠️ They see it at once\nAccount: work\n"
                                    "Chat: Yamada Taro (+819012345678)\n\n--- Text ---\nhi")
    assert directive["rule_key"].startswith("whatsapp-access:send:")


@pytest.mark.parametrize("args", [
    {"action": "send", "chat": DM, "text": "hi"},                               # no account
    {"action": "send", "account": "work", "chat": "Yamada", "text": "hi"},  # a name
    {"action": "send", "account": "work", "chat": DM, "text": " "},
    {"action": "forward"},
])
def test_gate_blocks_invalid_calls_without_asking(args):
    assert plugin.gate(tool_name="whatsapp", args=args)["action"] == "block"


def test_bind_only_touches_sends_with_files():
    assert plugin.bind(tool_name="whatsapp", args={"action": "chats"}) is None
    assert plugin.bind(tool_name="whatsapp", args={"action": "send", "account": "work", "chat": DM,
                                                  "text": "hi"}) is None
    assert plugin.bind(tool_name="terminal", args={"command": "ls"}) is None


def test_gate_stops_running_what_was_unpacked_but_not_reading_it():
    folder = "~/Workspaces/.inbox/whatsapp/chat-1/pack.unpacked"
    for command in (f"bash {folder}/run.sh", f"cd {folder} && ./run.sh", f"chmod +x {folder}/run.sh"):
        directive = plugin.gate(tool_name="terminal", args={"command": command})
        assert directive == {"action": "block", "message": plugin.wa.archives.RUN_MESSAGE}, command
    for command in (f"cat {folder}/notes.txt", f"python analyze.py {folder}/data.csv", f"ls {folder}"):
        assert plugin.gate(tool_name="terminal", args={"command": command}) is None, command


def test_gate_blocks_a_caller_supplied_outbox():
    directive = plugin.gate(tool_name="whatsapp", args={"action": "send", "account": "work", "chat": DM,
                                                       "text": "hi", "_outbox": "0" * 32})
    assert directive["action"] == "block" and "_outbox" in directive["message"]


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
    assert result["ok"] is True and result["chats"] == [] and result["account"] == "work"
    result = json.loads(plugin.whatsapp({"action": "messages"}))
    assert result["ok"] is False and "chat is required" in result["error"]
    assert json.loads(plugin.whatsapp("not a dict"))["ok"] is False


def test_oversized_results_are_refused(monkeypatch):
    monkeypatch.setattr(plugin.wa, "execute", lambda args, home=None, call_id="": {"x": "y" * plugin.LIMIT})
    result = json.loads(plugin.whatsapp({"action": "chats"}))
    assert result["ok"] is False and "narrow" in result["error"]


SEND = {"action": "send", "account": "work", "chat": DM, "text": "hi"}


def test_the_handler_sends_only_what_its_own_hook_recorded(monkeypatch):
    sent = []

    def run(args, **kwargs):
        if args[:2] == ["send", "text"]:
            sent.append(args)
            return {"sent": True, "to": DM, "id": "3EB0XYZ"}
        return fake_run(args, **kwargs)
    monkeypatch.setattr(plugin.wa, "run", run)
    call = {"id": "call-1"}
    monkeypatch.setattr(plugin, "_call_id", lambda: call["id"])

    result = json.loads(plugin.whatsapp(SEND))                                    # the hook never ran
    assert result["ok"] is False and "approval card" in result["error"]
    assert plugin.gate(tool_name="whatsapp", args=SEND, tool_call_id="call-1")["action"] == "approve"
    call["id"] = "call-2"                                                        # another call, same arguments
    assert "approval card" in json.loads(plugin.whatsapp(SEND))["error"]
    call["id"] = "call-1"
    assert json.loads(plugin.whatsapp(SEND))["ok"] is True and len(sent) == 1
    assert "approval card" in json.loads(plugin.whatsapp(SEND))["error"] and len(sent) == 1


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


def test_a_send_survives_hermes_coercing_its_arguments(monkeypatch, staging):
    """The hook sees the arguments as the model wrote them, the handler after coerce_tool_args."""
    sent = []

    def run(args, **kwargs):
        if args[:2] == ["send", "file"]:
            sent.append(args)
            return {"sent": True, "id": "3EBF1", "file": {"media": "document"}}
        return fake_run(args, **kwargs)
    monkeypatch.setattr(plugin.wa, "run", run)
    call = {"id": "c1"}
    monkeypatch.setattr(plugin, "_call_id", lambda: call["id"])

    def handler_args(raw, call_id, **changes):
        ids = {"tool_call_id": call_id, "session_id": "s"}
        assert plugin.gate(tool_name="whatsapp", args=raw, **ids)["action"] == "approve"
        bound = plugin.bind(tool_name="whatsapp", args=raw, **ids)["args"]
        call["id"] = call_id
        return {**raw, "files": ["a.txt"], **changes, **bound}      # files: "a.txt" became ["a.txt"]

    raw = {**SEND, "files": "a.txt"}
    result = json.loads(plugin.whatsapp(handler_args(raw, "c1")))
    assert result["ok"] is True and len(sent) == 1

    result = json.loads(plugin.whatsapp(handler_args(raw, "c2", text="something else")))
    assert result["ok"] is False and "changed after the approval card was made" in result["error"]
    assert len(sent) == 1


READS = ({"action": "chats"}, {"action": "status"}, {"action": "messages", "chat": DM},
         {"action": "search", "query": "hi"})


@pytest.fixture
def staging(tmp_path, monkeypatch):
    workspace = tmp_path / "Workspaces"
    workspace.mkdir()
    (workspace / "a.txt").write_text("notes")
    monkeypatch.setattr(plugin.wa, "SEND_ROOT", workspace)
    monkeypatch.setenv(plugin.wa.STATE_ENV, str(tmp_path / "state"))
    plugin.wa._PENDING.clear()


@pytest.mark.parametrize("reason", ["yolo mode is on", "this is a cron job", "nobody is present to answer"])
@pytest.mark.parametrize("extra", [{}, {"files": ["a.txt"]}, {"reply_to": "3EB0ABCDEF"},
                                   {"files": ["a.txt"], "reply_to": "3EB0ABCDEF"}])
def test_a_send_never_runs_where_no_person_can_answer_its_card(monkeypatch, staging, reason, extra):
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: reason)
    args = {**SEND, **extra}
    ids = {"tool_call_id": "call-1", "session_id": "s"}
    directive = plugin.gate(tool_name="whatsapp", args=args, **ids)
    assert directive["action"] == "block" and reason in directive["message"]
    assert "Nothing was sent or changed" in directive["message"]
    for forged in ({}, {"_outbox": "0" * 32}):
        result = json.loads(plugin.whatsapp({**args, **forged}))
        assert result["ok"] is False and reason in result["error"]
        assert "Nothing was sent or changed" in result["error"]
    assert plugin.bind(tool_name="whatsapp", args=args, **ids) is None
    assert plugin.wa._PENDING == {}                                        # no snapshot was staged
    assert not plugin.wa.outbox().exists() or list(plugin.wa.outbox().iterdir()) == []


def test_reads_are_not_affected_by_the_missing_person(monkeypatch):
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: "yolo mode is on")
    for args in READS:
        assert plugin.gate(tool_name="whatsapp", args=args) is None
        assert "Nothing was sent" not in plugin.whatsapp(args)


def test_with_a_person_present_a_send_still_asks_for_its_card(staging):
    directive = plugin.gate(tool_name="whatsapp", args={**SEND, "files": ["a.txt"]}, tool_call_id="c", session_id="s")
    assert directive["action"] == "approve" and directive["rule_key"].startswith("whatsapp-access:send:")


def test_the_genuine_check_refuses_a_send_in_this_headless_test_run(monkeypatch):
    """Without the stub, the real check runs against Hermes' own approval code. A test run is
    headless (nobody present, not a gateway), so the send is refused: the situation of `hermes -z`."""
    genuine = _load("whatsapp_access_human_gate_genuine", ROOT.parents[1] / "_shared" / "human_gate.py")
    monkeypatch.setattr(plugin.human_gate, "no_human", genuine.no_human)
    assert genuine.no_human() is not None
    result = json.loads(plugin.whatsapp(SEND))
    assert result["ok"] is False and "not done" in result["error"]
    assert plugin.gate(tool_name="whatsapp", args=SEND)["action"] == "block"


def test_the_skill_reaches_only_the_assistant():
    for profile, names in (("assistant", {"account", "count-activity"}), ("marketer", set()), ("creator", set())):
        ctx = Ctx(profile)
        plugin.register(ctx)
        assert set(ctx.skills) == names
