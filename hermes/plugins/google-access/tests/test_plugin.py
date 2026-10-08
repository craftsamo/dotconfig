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


plugin = _load("google_access_plugin_test", ROOT / "__init__.py")
LEAF = {"commands": {}, "flags": {}}
TREE = {"commands": {"projects": {"commands": {"list": LEAF}}, "run": {"commands": {"deploy": LEAF}}}}


@pytest.fixture(autouse=True)
def fake_tree(monkeypatch):
    monkeypatch.setattr(plugin.access, "_command_tree", lambda: TREE)
    monkeypatch.setattr(plugin, "_card_home", lambda: None)  # cards never reach a real account

@pytest.fixture(autouse=True)
def empty_keychain(tmp_path_factory, monkeypatch):
    """A ``secret`` CLI that holds nothing, so no test reaches the real Keychain."""
    script = tmp_path_factory.mktemp("keychain") / "secret"
    script.write_text("#!/bin/sh\nexit 1\n")
    script.chmod(0o755)
    monkeypatch.setattr(plugin.access, "SECRET", script)
    plugin.access._CREDS.clear()


@pytest.fixture(autouse=True)
def person_present(monkeypatch):
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: None)  # a person is there to answer cards


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


def test_only_the_assistant_gets_the_tools():
    ctx = Ctx("creator")
    plugin.register(ctx)
    assert ctx.tools == {} and ctx.hooks == []
    ctx = Ctx("assistant")
    plugin.register(ctx)
    assert set(ctx.tools) == {"google_sheets", "google_gmail", "google_drive", "gcloud"}
    assert {t["toolset"] for t in ctx.tools.values()} == {"google_access"}
    assert ctx.hooks == [("pre_tool_call", plugin.gate)]
    for name, tool in ctx.tools.items():
        params = tool["schema"]["parameters"]
        assert params["additionalProperties"] is False and params["required"] == plugin.REQUIRED[name]
        assert tool["schema"]["name"] == name


def test_action_enums_match_the_engine():
    ctx = Ctx("assistant")
    plugin.register(ctx)
    props = {name: tool["schema"]["parameters"]["properties"] for name, tool in ctx.tools.items()}
    assert props["google_sheets"]["action"]["enum"] == list(plugin.access.SHEETS_ACTIONS)
    assert props["google_gmail"]["action"]["enum"] == list(plugin.access.GMAIL_ACTIONS)
    assert props["google_drive"]["action"]["enum"] == list(plugin.access.DRIVE_ACTIONS)


def test_the_layout_op_schema_matches_the_engine():
    ctx = Ctx("assistant")
    plugin.register(ctx)
    op = ctx.tools["google_sheets"]["schema"]["parameters"]["properties"]["ops"]["items"]
    vocabularies = [vocabulary for vocabulary, *_ in plugin.access.OP_SETS.values()]
    assert op["properties"]["op"]["enum"] == [name for vocabulary in vocabularies for name in vocabulary]
    fields = {key for vocabulary in vocabularies for required, optional in vocabulary.values()
              for key in required + optional}
    assert set(op["properties"]) == fields | {"op"}
    assert op["additionalProperties"] is False


def test_gate_asks_per_call_for_a_layout_that_deletes():
    sid = "1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789_-abcd"
    safe = plugin.gate(tool_name="google_sheets", args={"action": "layout", "spreadsheet_id": sid, "ops": [
        {"op": "format", "range": "A1:C1", "bold": True}]})
    assert safe["rule_key"] == f"google-access:sheets-edit:{sid}" and "Format A1:C1: bold" in safe["message"]
    drop = plugin.gate(tool_name="google_sheets", args={"action": "layout", "spreadsheet_id": sid, "ops": [
        {"op": "delete", "range": "Sheet1!3:4"}]})
    assert drop["action"] == "approve" and "sheets-edit" not in drop["rule_key"]
    assert "Delete rows 3-4" in drop["message"]


def test_gate_asks_for_writes_only():
    sid = "1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789_-abcd"
    assert plugin.gate(tool_name="google_sheets", args={"action": "get", "spreadsheet_id": sid}) is None
    directive = plugin.gate(tool_name="google_sheets", args={
        "action": "append", "spreadsheet_id": sid, "range": "A1", "values": [["x"]]})
    assert directive["action"] == "approve" and "A(+1) > x" in directive["message"]
    assert directive["rule_key"] == f"google-access:sheets-edit:{sid}"
    assert plugin.gate(tool_name="gcloud", args={"command": ["projects", "list"]}) is None
    assert plugin.gate(tool_name="gcloud", args={"command": ["run", "deploy"]})["action"] == "approve"


def test_gate_blocks_invalid_calls_without_asking():
    directive = plugin.gate(tool_name="gcloud", args={"command": ["auth", "login"]})
    assert directive["action"] == "block" and "gaccess" in directive["message"]
    directive = plugin.gate(tool_name="google_gmail", args={"action": "send", "body": "x"})
    assert directive["action"] == "block"


def test_gate_blocks_ways_around_the_tools():
    directive = plugin.gate(tool_name="terminal", args={"command": "gcloud run deploy x"})
    assert directive == {"action": "block", "message": plugin.access.BYPASS_MESSAGE}
    assert plugin.gate(tool_name="terminal", args={"command": "ls"}) is None
    assert plugin.gate(tool_name="read_file", args={"path": "~/.config/gcloud/credentials.db"})["action"] == "block"


def test_inbound_a2a_is_refused(monkeypatch):
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    directive = plugin.gate(tool_name="google_gmail", args={"action": "search"})
    assert directive["action"] == "block"
    result = json.loads(plugin.google_gmail({"action": "search"}))
    assert result["ok"] is False and "A2A" in result["error"]


def test_handlers_return_json_errors(tmp_path, monkeypatch):
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: False)
    monkeypatch.setattr(plugin, "_home", lambda: tmp_path)
    result = json.loads(plugin.google_sheets({"action": "get", "spreadsheet_id": "1AbCdEfGhIjKlMnOp",
                                              "range": "A1"}))
    assert result["ok"] is False and "gaccess auth" in result["error"]
    result = json.loads(plugin.gcloud({"command": ["projects", "list"]}))
    assert result["ok"] is False and "gcloud-login" in result["error"]


def test_oversized_results_are_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: False)
    monkeypatch.setattr(plugin, "_home", lambda: tmp_path)
    monkeypatch.setitem(plugin.ENGINES, "google_drive", lambda home, args: {"x": "y" * plugin.LIMIT})
    result = json.loads(plugin.google_drive({"action": "search"}))
    assert result["ok"] is False and "narrow" in result["error"]


SID = "1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789_-abcd"
SHEET_WRITES = {
    "update": {"range": "A1", "values": [["x"]]},
    "batch_update": {"data": [{"range": "B2", "values": [["w"]]}]},
    "append": {"range": "Log!A:C", "values": [["z"]]},
    "add_sheet": {"title": "New"},
    "clear": {"range": "A1:B9"},
    "layout": {"ops": [{"op": "format", "range": "A1:C1", "bold": True}]},
}
REASONS = ["yolo mode is on", "this is a cron job", "nobody is present to answer"]


def _write_calls(tmp_path):
    report = tmp_path / "report.pdf"
    report.write_bytes(b"%PDF")
    calls = [("google_sheets", {"action": action, "spreadsheet_id": SID, **extra})
             for action, extra in SHEET_WRITES.items()]
    calls.append(("google_sheets", {"action": "create", "title": "Budget"}))
    calls.append(("google_gmail", {"action": "send", "to": "a@example.com", "subject": "s", "body": "b"}))
    calls.append(("google_drive", {"action": "upload", "path": str(report)}))
    calls.append(("gcloud", {"command": ["run", "deploy"]}))
    return calls


@pytest.mark.parametrize("reason", REASONS)
def test_a_write_is_refused_where_nobody_can_answer_its_card(tmp_path, monkeypatch, reason):
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: reason)
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: False)
    monkeypatch.setattr(plugin, "_home", lambda: tmp_path)
    calls = _write_calls(tmp_path)
    assert len(calls) == len(SHEET_WRITES) + 4
    for tool, args in calls:
        directive = plugin.gate(tool_name=tool, args=args)
        assert directive["action"] == "block" and reason in directive["message"], (tool, args)
        assert "Nothing was sent or changed" in directive["message"]
        result = json.loads(getattr(plugin, tool)(args))
        assert result["ok"] is False and reason in result["error"], (tool, args)
        assert "Nothing was sent or changed" in result["error"]


def test_reads_are_not_affected_by_the_missing_person(monkeypatch):
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: "yolo mode is on")
    for tool, args in (("google_sheets", {"action": "get", "spreadsheet_id": SID}),
                       ("google_gmail", {"action": "search"}),
                       ("google_drive", {"action": "search"}),
                       ("gcloud", {"command": ["projects", "list"]})):
        assert plugin.gate(tool_name=tool, args=args) is None
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: False)
    monkeypatch.setitem(plugin.ENGINES, "gcloud", lambda home, args: {"ok": True})
    monkeypatch.setattr(plugin, "_home", lambda: Path("."))
    assert json.loads(plugin.gcloud({"command": ["projects", "list"]})) == {"ok": True}


def test_with_a_person_present_a_write_still_gets_its_card(tmp_path):
    for tool, args in _write_calls(tmp_path):
        assert plugin.gate(tool_name=tool, args=args)["action"] == "approve", (tool, args)


def test_the_genuine_check_refuses_a_write_in_this_headless_test_run(tmp_path, monkeypatch):
    genuine = _load("google_access_human_gate_genuine", ROOT.parent / "_shared" / "human_gate.py")
    monkeypatch.setattr(plugin.human_gate, "no_human", genuine.no_human)
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: False)
    assert genuine.no_human() is not None
    args = {"action": "update", "spreadsheet_id": SID, "range": "A1", "values": [["x"]]}
    assert plugin.gate(tool_name="google_sheets", args=args)["action"] == "block"
    result = json.loads(plugin.google_sheets(args))
    assert result["ok"] is False and "not done" in result["error"]


def test_the_skill_reaches_only_the_assistant():
    for profile, names in (("assistant", {"google-sheets"}), ("marketer", set()), ("creator", set())):
        ctx = Ctx(profile)
        plugin.register(ctx)
        assert set(ctx.skills) == names
