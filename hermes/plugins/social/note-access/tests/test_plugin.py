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
        self.skills = {}

    def register_skill(self, name, path, description="", frontmatter=None):
        assert path.is_file() and frontmatter["name"] == name and description
        self.skills[name] = path

    def register_tool(self, **kwargs):
        self.tools[kwargs["name"]] = kwargs

    def register_hook(self, name, callback):
        self.hooks.append((name, callback))


def registered(profile):
    ctx = Ctx(profile)
    plugin.register(ctx)
    return ctx


def test_assistant_writes_marketer_reads_writer_checks_others_get_nothing():
    for profile in ("creator", "engineer", "default", "researcher"):
        ctx = registered(profile)
        assert ctx.tools == {} and ctx.hooks == []
    ctx = registered("assistant")
    tool = ctx.tools["note"]
    assert tool["toolset"] == "note_access" and tool["schema"]["name"] == "note"
    params = tool["schema"]["parameters"]
    assert params["additionalProperties"] is False and params["required"] == ["action"]
    assert params["properties"]["action"]["enum"] == list(na.ACTIONS)
    assert {"title", "body", "eyecatch", "path", "base", "preview"} <= set(params["properties"])
    assert "create_draft" in tool["description"] and "resident session" in tool["description"]
    assert "check (body" in tool["description"]
    assert [name for name, _ in ctx.hooks] == ["pre_tool_call"]
    # Marketer advises: reads and the offline check, no save and no preview.
    ctx = registered("marketer")
    tool = ctx.tools["note"]
    params = tool["schema"]["parameters"]
    assert params["properties"]["action"]["enum"] == list(na.READS + na.OFFLINE)
    assert {"body", "path"} <= set(params["properties"])
    assert not {"base", "preview"} & set(params["properties"])
    assert "create_draft" not in tool["description"] and "check (body" in tool["description"]
    assert [name for name, _ in ctx.hooks] == ["pre_tool_call"]


def test_writer_gets_the_format_check_only():
    tool = registered("writer").tools["note"]
    assert tool["toolset"] == "note_access"
    params = tool["schema"]["parameters"]["properties"]
    assert params["action"]["enum"] == ["check"]
    assert set(params) == {"action", "title", "body", "eyecatch", "path"}
    assert "never contacts note" in tool["description"] and "create_draft" not in tool["description"]
    assert "[[image|embed|table" in tool["description"]


PRIVATE_ACTIONS = ("drafts", "draft", "stats", "create_draft", "update_draft", "check")


def test_searcher_gets_the_public_reads_only():
    ctx = registered("searcher")
    tool = ctx.tools["note"]
    params = tool["schema"]["parameters"]["properties"]
    assert tool["toolset"] == "note_access" and [name for name, _ in ctx.hooks] == ["pre_tool_call"]
    assert params["action"]["enum"] == list(plugin.PUBLIC_READS)
    assert set(params) == {"action", *plugin.PUBLIC_READ_PROPERTIES}
    assert not set(PRIVATE_ACTIONS) & set(params["action"]["enum"])
    for word in ("create_draft", "update_draft", "check (body", "drafts (", "stats ("):
        assert word not in tool["description"]
    assert "not available to this profile" in tool["description"]


def test_searcher_reads_reach_the_engine_and_private_actions_do_not(isolated):
    handler, gate = handler_and_gate("searcher")
    assert json.loads(handler({"action": "status"}))["ok"] is True
    for action in plugin.PUBLIC_READS:
        assert gate(tool_name="note", args={"action": action, "query": "q", "note": "n0000000000a1",
                                            "creator": "@a", "tag": "t"}) is None
    calls_before = list(isolated)
    for action in PRIVATE_ACTIONS:
        args = {"action": action, "draft": "n0000000000a1", "base": "t1", "title": "T", "body": "x"}
        assert gate(tool_name="note", args=args, tool_call_id="s")["action"] == "block"
        assert json.loads(handler(args))["ok"] is False
        with pytest.raises(na.NoteError):
            na.execute(args, can_write=False, allowed=plugin.PUBLIC_READS)
    assert isolated == calls_before


def test_inbound_a2a_never_reaches_searcher(monkeypatch):
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    monkeypatch.setattr(plugin, "_home", lambda: Path("/h/profiles/searcher"))
    handler, gate = handler_and_gate("searcher")
    for args in ({"action": "search", "query": "q"}, {"action": "status"}):
        directive = gate(tool_name="note", args=args)
        assert directive["action"] == "block" and "A2A" in directive["message"]
        assert "A2A" in json.loads(handler(args))["error"]


def test_a_read_only_profile_gets_no_write_schema(monkeypatch):
    monkeypatch.setitem(plugin.PROFILES, "marketer", na.READS)
    tool = registered("marketer").tools["note"]
    assert tool["schema"]["parameters"]["properties"]["action"]["enum"] == list(na.READS)
    assert not {"title", "body", "eyecatch", "base", "preview"} & set(tool["schema"]["parameters"]["properties"])
    assert "create_draft" not in tool["description"]


def handler_and_gate(profile):
    ctx = registered(profile)
    return ctx.tools["note"]["handler"], ctx.hooks[0][1]


def test_a_read_only_profile_cannot_write_through_the_handler_or_the_gate(isolated, monkeypatch):
    monkeypatch.setitem(plugin.PROFILES, "marketer", na.READS)
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


def test_unattended_runs_cannot_write_and_hand_the_save_back(isolated, monkeypatch):
    monkeypatch.setattr(plugin, "_unattended", lambda: True)
    handler, gate = handler_and_gate("assistant")
    args = {"action": "update_draft", "draft": "n0000000000a1", "base": "t1", "body": "new"}
    directive = gate(tool_name="note", args=args)
    assert directive["action"] == "block" and "approve" in directive["message"]
    error = json.loads(handler(args))["error"]
    assert "nothing was saved" in error and "to the caller" in error and "resident session" in error
    assert "save" not in isolated
    assert gate(tool_name="note", args={"action": "drafts"}) is None   # reads still work unattended


def test_marketer_can_neither_save_nor_preview_even_with_a_person(isolated, monkeypatch):
    handler, gate = handler_and_gate("marketer")
    for args in ({"action": "update_draft", "draft": "n0000000000a1", "base": "t1", "body": "new"},
                 {"action": "create_draft", "title": "T", "body": "x", "preview": True}):
        assert gate(tool_name="note", args=args, tool_call_id="m1")["action"] == "block"
        monkeypatch.setattr(plugin, "_call_id", lambda: "m1")
        result = json.loads(handler(dict(args)))
        assert result["ok"] is False and "read note but not write" in result["error"]
    assert json.loads(handler({"action": "check", "body": "## a\n\nb"}))["ready"] is True
    assert "save" not in isolated


def test_inbound_a2a_never_reaches_the_assistant(monkeypatch):
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    monkeypatch.setattr(plugin, "_home", lambda: Path("/h/profiles/assistant"))
    handler, gate = handler_and_gate("assistant")
    for args in ({"action": "drafts"}, {"action": "check", "body": "x"}):
        directive = gate(tool_name="note", args=args)
        assert directive["action"] == "block" and "A2A" in directive["message"]
        result = json.loads(handler(args))
        assert result["ok"] is False and "A2A" in result["error"]


def test_inbound_a2a_lets_marketer_read_and_check_but_never_save(isolated, monkeypatch):
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    monkeypatch.setattr(plugin, "_home", lambda: Path("/h/profiles/marketer"))
    handler, gate = handler_and_gate("marketer")
    assert gate(tool_name="note", args={"action": "status"}) is None
    assert json.loads(handler({"action": "status"}))["ok"] is True
    assert json.loads(handler({"action": "check", "body": "## a\n\nb"}))["ready"] is True
    for args in ({"action": "update_draft", "draft": "n0000000000a1", "base": "t1", "body": "new"},
                 {"action": "create_draft", "title": "T", "body": "x", "preview": True}):
        assert gate(tool_name="note", args=args, tool_call_id="a1")["action"] == "block"
        assert json.loads(handler(args))["ok"] is False
    assert "save" not in isolated


def test_inbound_a2a_fails_closed_unless_bound_to_the_profile(monkeypatch):
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    for home in (None, Path("/h/profiles/assistant")):
        monkeypatch.setattr(plugin, "_home", lambda home=home: home)
        handler, gate = handler_and_gate("marketer")
        assert gate(tool_name="note", args={"action": "drafts"})["action"] == "block"
        assert "here" in json.loads(handler({"action": "drafts"}))["error"]


def test_writer_checks_on_a2a_and_nothing_else(isolated, monkeypatch):
    handler, gate = handler_and_gate("writer")
    for inbound in (False, True):
        monkeypatch.setattr(plugin, "_inbound_peer", lambda inbound=inbound: inbound)
        monkeypatch.setattr(plugin, "_home", lambda: Path("/h/profiles/writer"))
        assert gate(tool_name="note", args={"action": "check", "body": "x"}) is None
        assert json.loads(handler({"action": "check", "body": "x"}))["ok"] is True
        for args in ({"action": "status"}, {"action": "drafts"},
                     {"action": "create_draft", "title": "T", "body": "x", "preview": True}):
            assert gate(tool_name="note", args=args, tool_call_id="w")["action"] == "block"
            assert "only check" in json.loads(handler(args))["error"]
    assert isolated == []   # nothing reached the bridge


def test_the_gate_blocks_ways_around_the_tool():
    for profile in ("assistant", "marketer", "writer", "searcher"):
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
    monkeypatch.setattr(na, "execute", lambda args, home=None, call_id="", can_write=False, allowed=None: {"x": "y" * plugin.LIMIT})
    handler, _ = handler_and_gate("marketer")
    result = json.loads(handler({"action": "drafts"}))
    assert result["ok"] is False and "narrow" in result["error"]


def test_a_preview_runs_without_a_card_even_unattended(isolated, monkeypatch):
    monkeypatch.setattr(plugin, "_unattended", lambda: True)
    handler, gate = handler_and_gate("assistant")
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
    monkeypatch.setitem(plugin.PROFILES, "marketer", na.READS)
    handler, gate = handler_and_gate("marketer")
    args = {"action": "create_draft", "title": "T", "body": "x", "preview": True}
    result = json.loads(handler(args))
    assert result["ok"] is False and "read note but not write" in result["error"]


def test_writer_inbound_a2a_fails_closed_unless_bound_and_names_only_check(monkeypatch):
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    for home in (None, Path("/h/profiles/marketer")):
        monkeypatch.setattr(plugin, "_home", lambda home=home: home)
        handler, gate = handler_and_gate("writer")
        assert gate(tool_name="note", args={"action": "check", "body": "x"})["action"] == "block"
        assert "here" in json.loads(handler({"action": "check", "body": "x"}))["error"]
    monkeypatch.setattr(plugin, "_home", lambda: Path("/h/profiles/writer"))
    handler, gate = handler_and_gate("writer")
    for args in ({"action": "like"}, "not a dict", {"action": ["check"]}):
        assert gate(tool_name="note", args=args)["action"] == "block"
        assert "only check" in json.loads(handler(args))["error"]


def test_each_skill_reaches_only_the_profiles_whose_actions_it_describes():
    expected = {"assistant": {"note-com", "note-com-format", "note-com-drafts"},
                "marketer": {"note-com", "note-com-format"}, "writer": {"note-com-format"},
                "searcher": {"note-com"}}
    for profile, names in expected.items():
        ctx = Ctx(profile)
        plugin.register(ctx)
        assert set(ctx.skills) == names
        first = sorted(names, key=list(plugin.SKILLS).index)[0]
        assert f'note-access:{first}"' in ctx.tools["note"]["description"]
    ctx = Ctx("creator")
    plugin.register(ctx)
    assert ctx.skills == {}
    for profile in ("marketer", "searcher", "writer"):
        ctx = Ctx(profile)
        plugin.register(ctx)
        for path in ctx.skills.values():
            assert "note-com-drafts" not in path.read_text() and "create_draft" not in path.read_text()
