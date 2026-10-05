import importlib.util
import json
from pathlib import Path
import sys

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
    monkeypatch.setattr(plugin, "_unattended", lambda: False)
    monkeypatch.setattr(plugin, "_approvals_bypassed", lambda: False)
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
    for profile, hooks in (("assistant", 2), ("marketer", 1)):
        ctx = registered(profile)
        tool = ctx.tools["substack"]
        assert tool["toolset"] == "substack_access" and tool["schema"]["name"] == "substack"
        params = tool["schema"]["parameters"]
        assert params["additionalProperties"] is False and params["required"] == ["action"]
        assert [name for name, _ in ctx.hooks] == ["pre_tool_call"] * hooks


def test_marketer_sees_only_reads():
    assistant = registered("assistant").tools["substack"]["schema"]
    marketer = registered("marketer").tools["substack"]["schema"]
    assert assistant["parameters"]["properties"]["action"]["enum"] == list(plugin.sa.ACTIONS)
    assert marketer["parameters"]["properties"]["action"]["enum"] == list(plugin.sa.READS)
    assert "never create, change, publish or post" in marketer["description"]
    assert {"markdown", "send_email", "text"} <= set(assistant["parameters"]["properties"])
    assert not {"markdown", "send_email", "text", "title"} & set(marketer["parameters"]["properties"])
    assert "approval" in assistant["description"]


def test_marketer_cannot_call_a_write_even_by_name():
    ctx = registered("marketer")
    result = json.loads(ctx.tools["substack"]["handler"]({"action": "publish", "draft": "1", "send_email": False}))
    assert result["ok"] is False and "only read" in result["error"]
    directive = ctx.hooks[0][1](tool_name="substack", args={"action": "note", "text": "hi"}, tool_call_id="c1")
    assert directive["action"] == "block" and "only read" in directive["message"]


# --- writes ---------------------------------------------------------------------------------------

PREPARED = {"publication": {"name": "CraftSamo", "url": "https://craftsamo.substack.com", "subdomain": "craftsamo"},
            "account": {"handle": "craftsamo"}, "images": []}


@pytest.fixture
def writes(monkeypatch):
    """A fake bridge that prepares cards and records writes."""
    calls = []

    def bridge(op, **fields):
        calls.append({"op": op, **fields})
        if op == "prepare":
            data = dict(PREPARED)
        elif op == "write":
            data = {"note": {"id": 9, "url": "https://substack.com/@craftsamo/note/c-9"}}
        else:
            return fake_bridge(op, **fields)
        return {"ok": True, "data": data, "fingerprint": "fp", "contacted": True, "session": {"active": True}}

    monkeypatch.setattr(plugin.sa, "bridge", bridge)
    monkeypatch.setattr(plugin, "_unattended", lambda: False)
    return calls


def hooks(profile="assistant"):
    ctx = registered(profile)
    return ctx, ctx.hooks[0][1], ctx.hooks[1][1]


def test_a_write_is_approved_bound_and_carried_out_once(writes):
    ctx, gate, bind = hooks()
    args = {"action": "note", "text": "Hello from Hermes"}
    ids = {"session_id": "s", "task_id": "t", "tool_call_id": "c1"}
    directive = gate(tool_name="substack", args=args, **ids)
    assert directive["action"] == "approve" and directive["rule_key"].startswith("substack-access:note:")
    assert "post a public Note as @craftsamo" in directive["message"] and "Hello from Hermes" in directive["message"]
    modify = bind(tool_name="substack", args=args, **ids)
    assert modify["action"] == "modify" and len(modify["args"]["_prepared"]) == 32
    assert [c["op"] for c in writes] == ["prepare"]  # one read for both hooks
    handler = ctx.tools["substack"]["handler"]
    result = json.loads(handler({**args, **modify["args"]}))
    assert result["ok"] is True and result["note_posted"]["id"] == 9
    assert writes[-1]["op"] == "write" and writes[-1]["plan"] == {"action": "note", "text": "Hello from Hermes"}
    again = json.loads(handler({**args, **modify["args"]}))
    assert again["ok"] is False and "already carried out" in again["error"]


def test_a_write_without_its_card_never_runs(writes):
    ctx, gate, bind = hooks()
    handler = ctx.tools["substack"]["handler"]
    result = json.loads(handler({"action": "note", "text": "hi"}))
    assert result["ok"] is False and "not prepared on an approval card" in result["error"]
    forged = {"action": "note", "text": "hi", "_prepared": "0" * 32}
    directive = gate(tool_name="substack", args=forged, tool_call_id="c2")
    assert directive["action"] == "block" and "set by the plugin" in directive["message"]
    assert bind(tool_name="substack", args=forged, tool_call_id="c2") is None
    assert json.loads(handler(forged))["ok"] is False
    assert not [c for c in writes if c["op"] == "write"]


def test_a_changed_request_does_not_use_the_approved_snapshot(writes):
    ctx, gate, bind = hooks()
    args = {"action": "note", "text": "approved text"}
    gate(tool_name="substack", args=args, tool_call_id="c3")
    token = bind(tool_name="substack", args=args, tool_call_id="c3")["args"]["_prepared"]
    result = json.loads(ctx.tools["substack"]["handler"]({"action": "note", "text": "other text", "_prepared": token}))
    assert result["ok"] is False and "differs from what was approved" in result["error"]


def test_writes_need_a_call_id_and_valid_arguments(writes):
    _, gate, bind = hooks()
    directive = gate(tool_name="substack", args={"action": "note", "text": "hi"})
    assert directive["action"] == "block" and "tool call id" in directive["message"]
    directive = gate(tool_name="substack", args={"action": "publish", "draft": "1"}, tool_call_id="c4")
    assert directive["action"] == "block" and "send_email" in directive["message"]
    assert bind(tool_name="substack", args={"action": "publish", "draft": "1"}, tool_call_id="c4") is None
    assert writes == []  # invalid calls never reach Substack


def test_reads_ask_nothing(writes):
    _, gate, bind = hooks()
    assert gate(tool_name="substack", args={"action": "inbox"}, tool_call_id="c5") is None
    assert bind(tool_name="substack", args={"action": "inbox"}, tool_call_id="c5") is None


def test_unattended_runs_never_write(writes, monkeypatch):
    monkeypatch.setattr(plugin, "_unattended", lambda: True)
    ctx, gate, bind = hooks()
    args = {"action": "note", "text": "hi"}
    directive = gate(tool_name="substack", args=args, tool_call_id="c6")
    assert directive["action"] == "block" and "need a person to approve" in directive["message"]
    assert bind(tool_name="substack", args=args, tool_call_id="c6") is None
    result = json.loads(ctx.tools["substack"]["handler"]({**args, "_prepared": "0" * 32}))
    assert result["ok"] is False and "need a person to approve" in result["error"]
    assert gate(tool_name="substack", args={"action": "inbox"}, tool_call_id="c7") is None  # reads still work
    assert writes == []


def test_writes_stay_approval_only_under_yolo(writes, monkeypatch):
    monkeypatch.setattr(plugin, "_approvals_bypassed", lambda: True)
    ctx, gate, bind = hooks()
    args = {"action": "note", "text": "hi"}
    directive = gate(tool_name="substack", args=args, tool_call_id="y1")
    assert directive["action"] == "block" and "approvals are switched off" in directive["message"]
    assert bind(tool_name="substack", args=args, tool_call_id="y1") is None
    assert "switched off" in json.loads(ctx.tools["substack"]["handler"]({**args, "_prepared": "0" * 32}))["error"]
    assert gate(tool_name="substack", args={"action": "inbox"}, tool_call_id="y2") is None
    assert writes == []


def test_the_bypass_check_fails_closed_when_hermes_changes(monkeypatch):
    import types
    real = _load("substack_access_plugin_bypass", ROOT / "__init__.py")
    fake = types.ModuleType("tools.approval")
    monkeypatch.setitem(sys.modules, "tools", types.ModuleType("tools"))
    monkeypatch.setitem(sys.modules, "tools.approval", fake)
    sys.modules["tools"].approval = fake
    assert real._approvals_bypassed() is True  # helper missing: cannot tell
    fake.is_approval_bypass_active = lambda: False
    assert real._approvals_bypassed() is False
    fake.is_approval_bypass_active = lambda: True
    assert real._approvals_bypassed() is True


def test_bind_without_a_card_gets_nothing(writes):
    _, gate, bind = hooks()
    args = {"action": "note", "text": "hi"}
    assert bind(tool_name="substack", args=args, tool_call_id="b1") is None
    assert writes == []  # bind never prepares on its own


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
    directive = marketer.hooks[0][1](tool_name="substack", args={"action": "publish"})
    assert directive["action"] == "block" and "cannot write" in directive["message"]
    assert assistant.hooks[1][1](tool_name="substack", args={"action": "note", "text": "x"}, tool_call_id="c") is None


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
