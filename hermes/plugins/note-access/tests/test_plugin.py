import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("note_access_plugin_test", ROOT / "__init__.py")
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)
na = plugin.na

DRAFT = {"id": 5, "key": "n0000000000a1", "status": "draft", "is_my_note": True, "is_published": False,
         "separator": None, "user": {"urlname": "writer"}, "name": "T",
         "note_draft": {"name": "T", "body": '<p name="u" id="u">old</p>', "updated_at": "t1"}}


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(na, "STORE", tmp_path)  # never the real ~/.note-access
    monkeypatch.setattr(na, "MIN_GAP", 0)
    calls = []

    def fake_bridge(op, **fields):
        calls.append(op)
        if op == "check":
            return {"ok": True, "fingerprint": "f", "requests": 0}
        if op == "draft":
            return {"ok": True, "data": json.loads(json.dumps(DRAFT)), "fingerprint": "f", "requests": 1}
        if op == "save":
            return {"ok": True, "data": {"updated_at": "t2"}, "fingerprint": "f", "requests": 1}
        return {"ok": False, "kind": "error", "error": f"unexpected {op}", "requests": 0}
    monkeypatch.setattr(na, "bridge", fake_bridge)
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: False)
    monkeypatch.setattr(plugin, "_unattended", lambda: False)
    monkeypatch.setattr(plugin, "_home", lambda: None)
    na._approved.clear()
    return calls


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


def test_assistant_and_marketer_read_and_write_others_get_nothing():
    for profile in ("creator", "engineer", "default", "writer"):
        ctx = registered(profile)
        assert ctx.tools == {} and ctx.hooks == []
    for profile in ("assistant", "marketer"):
        ctx = registered(profile)
        tool = ctx.tools["note"]
        assert tool["toolset"] == "note_access" and tool["schema"]["name"] == "note"
        params = tool["schema"]["parameters"]
        assert params["additionalProperties"] is False and params["required"] == ["action"]
        assert params["properties"]["action"]["enum"] == list(na.ACTIONS)
        assert {"title", "body", "eyecatch"} <= set(params["properties"])
        assert "create_draft" in tool["description"] and "resident session" in tool["description"]
        assert [name for name, _ in ctx.hooks] == ["pre_tool_call"]


def test_a_read_only_profile_gets_no_write_schema(monkeypatch):
    monkeypatch.setattr(plugin, "WRITERS", set())
    monkeypatch.setattr(plugin, "READERS", {"marketer"})
    tool = registered("marketer").tools["note"]
    assert tool["schema"]["parameters"]["properties"]["action"]["enum"] == list(na.READS)
    assert not {"title", "body", "eyecatch"} & set(tool["schema"]["parameters"]["properties"])
    assert "create_draft" not in tool["description"]


def handler_and_gate(profile):
    ctx = registered(profile)
    return ctx.tools["note"]["handler"], ctx.hooks[0][1]


def test_a_read_only_profile_cannot_write_through_the_handler_or_the_gate(isolated, monkeypatch):
    monkeypatch.setattr(plugin, "WRITERS", set())
    monkeypatch.setattr(plugin, "READERS", {"marketer"})
    handler, gate = handler_and_gate("marketer")
    args = {"action": "update_draft", "draft": "n0000000000a1", "base": "t1", "body": "x"}
    assert gate(tool_name="note", args=args)["action"] == "block"
    result = json.loads(handler(args))
    assert result["ok"] is False and "read note but not write" in result["error"]
    assert "save" not in isolated


def test_the_gate_asks_for_writes_only():
    _, gate = handler_and_gate("assistant")
    assert gate(tool_name="note", args={"action": "drafts"}) is None
    directive = gate(tool_name="note", args={"action": "update_draft", "draft": "n0000000000a1", "base": "t1", "body": "new"},
                     tool_call_id="c1")
    assert directive["action"] == "approve"
    assert directive["message"].startswith("note: replace draft n0000000000a1 as @writer\nNow: T — old\nTitle: T\n")
    assert directive["rule_key"].startswith("note-access:update_draft:")


@pytest.mark.parametrize("args", [
    {"action": "update_draft", "draft": "nope", "body": "x"},
    {"action": "update_draft", "draft": "n0000000000a1", "base": "t1", "body": "# h1"},
    {"action": "create_draft", "title": "", "body": "x"},
])
def test_the_gate_blocks_invalid_writes_without_asking(args):
    _, gate = handler_and_gate("assistant")
    assert gate(tool_name="note", args=args, tool_call_id="c1")["action"] == "block"


def test_an_approved_update_is_saved_once(isolated, monkeypatch):
    handler, gate = handler_and_gate("assistant")
    args = {"action": "update_draft", "draft": "n0000000000a1", "base": "t1", "body": "new"}
    assert gate(tool_name="note", args=args, tool_call_id="c1")["action"] == "approve"
    monkeypatch.setattr(plugin, "_call_id", lambda: "c1")
    result = json.loads(handler(dict(args)))
    assert result["ok"] is True and result["key"] == "n0000000000a1"
    assert isolated.count("save") == 1
    assert "approval card" in json.loads(handler(dict(args)))["error"]


def test_a_write_without_the_gate_is_refused(isolated):
    handler, _ = handler_and_gate("assistant")
    result = json.loads(handler({"action": "update_draft", "draft": "n0000000000a1", "base": "t1", "body": "new"}))
    assert result["ok"] is False and "approval card" in result["error"] and "save" not in isolated


@pytest.mark.parametrize("profile", ["assistant", "marketer"])
def test_unattended_runs_cannot_write_and_hand_the_save_back(isolated, monkeypatch, profile):
    monkeypatch.setattr(plugin, "_unattended", lambda: True)
    handler, gate = handler_and_gate(profile)
    args = {"action": "update_draft", "draft": "n0000000000a1", "base": "t1", "body": "new"}
    directive = gate(tool_name="note", args=args)
    assert directive["action"] == "block" and "approve" in directive["message"]
    error = json.loads(handler(args))["error"]
    assert "nothing was saved" in error and "to the caller" in error and "resident session" in error
    assert "save" not in isolated
    assert gate(tool_name="note", args={"action": "drafts"}) is None   # reads still work unattended


def test_marketer_saves_through_its_own_card(isolated, monkeypatch):
    handler, gate = handler_and_gate("marketer")
    args = {"action": "update_draft", "draft": "n0000000000a1", "base": "t1", "body": "new"}
    directive = gate(tool_name="note", args=args, tool_call_id="m1")
    assert directive["action"] == "approve" and directive["message"].startswith("note: replace draft")
    monkeypatch.setattr(plugin, "_call_id", lambda: "m1")
    assert json.loads(handler(dict(args)))["ok"] is True and isolated.count("save") == 1


def test_inbound_a2a_is_refused(monkeypatch):
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    for profile in ("assistant", "marketer"):
        handler, gate = handler_and_gate(profile)
        directive = gate(tool_name="note", args={"action": "drafts"})
        assert directive["action"] == "block" and "A2A" in directive["message"]
        result = json.loads(handler({"action": "drafts"}))
        assert result["ok"] is False and "A2A" in result["error"]


def test_the_gate_blocks_ways_around_the_tool():
    for profile in ("assistant", "marketer"):
        _, gate = handler_and_gate(profile)
        directive = gate(tool_name="terminal", args={"command": "curl https://note.com/api/v2/current_user"})
        assert directive == {"action": "block", "message": na.BYPASS_MESSAGE}
        assert gate(tool_name="terminal", args={"command": "ls"}) is None


def test_handler_returns_json():
    handler, _ = handler_and_gate("assistant")
    result = json.loads(handler({"action": "status"}))
    assert result["ok"] is True and result["cookie"] is True
    assert json.loads(handler("not a dict"))["ok"] is False
    assert "action must be" in json.loads(handler({"action": "like"}))["error"]


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


def test_unattended_detection_uses_hermes_when_available():
    try:
        import tools.approval_context  # noqa: F401
    except ImportError:
        pytest.skip("hermes-agent not importable")
    spec2 = importlib.util.spec_from_file_location("note_access_plugin_fresh", ROOT / "__init__.py")
    fresh = importlib.util.module_from_spec(spec2)
    spec2.loader.exec_module(fresh)
    assert fresh._unattended() in (True, False)


def test_oversized_results_are_refused(monkeypatch):
    monkeypatch.setattr(na, "execute", lambda args, home=None, call_id="", can_write=False: {"x": "y" * plugin.LIMIT})
    handler, _ = handler_and_gate("marketer")
    result = json.loads(handler({"action": "drafts"}))
    assert result["ok"] is False and "narrow" in result["error"]


def test_a_preview_runs_without_a_card_even_unattended(isolated, monkeypatch):
    monkeypatch.setattr(plugin, "_unattended", lambda: True)
    handler, gate = handler_and_gate("marketer")
    args = {"action": "update_draft", "draft": "n0000000000a1", "base": "t1", "body": "new", "preview": True}
    assert gate(tool_name="note", args=args, tool_call_id="p1") is None
    result = json.loads(handler(args))
    assert result["ok"] is True and result["preview"] is True and "save" not in isolated
    assert result["card"].startswith("note: replace draft n0000000000a1")


@pytest.mark.parametrize("flag", [1, "true", "yes", 0.5])
def test_a_malformed_preview_flag_is_never_a_preview(isolated, flag):
    handler, gate = handler_and_gate("assistant")
    args = {"action": "update_draft", "draft": "n0000000000a1", "base": "t1", "body": "new", "preview": flag}
    assert gate(tool_name="note", args=args, tool_call_id="m")["action"] == "block"
    assert json.loads(handler(args))["ok"] is False and "save" not in isolated


def test_a_read_only_profile_cannot_preview_either(isolated, monkeypatch):
    monkeypatch.setattr(plugin, "WRITERS", set())
    monkeypatch.setattr(plugin, "READERS", {"marketer"})
    handler, gate = handler_and_gate("marketer")
    args = {"action": "create_draft", "title": "T", "body": "x", "preview": True}
    result = json.loads(handler(args))
    assert result["ok"] is False and "read note but not write" in result["error"]
