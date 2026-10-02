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


class Ctx:
    def __init__(self, profile):
        self.profile_name = profile
        self.tools = {}
        self.hooks = []

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
