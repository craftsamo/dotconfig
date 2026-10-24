import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("cloudflare_access_plugin_test", ROOT / "__init__.py")
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)
cfa = plugin.cfa

ACCOUNT = "0123456789abcdef0123456789abcdef"
ZONE = {"id": "1" * 32, "name": "example.com", "account": {"id": ACCOUNT}}


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(cfa, "STORE", tmp_path)  # never the real ~/.cloudflare-access
    calls = []

    def fake_bridge(op, **fields):
        calls.append({"op": op, **fields})
        if op == "keys":
            return {"ok": True, "data": [], "unused": [], "requests": 0}
        result = [ZONE] if fields.get("path") == "/zones" else ZONE
        return {"ok": True, "account": "work", "account_id": ACCOUNT, "requests": 1, "fingerprint": "f" * 12,
                "data": {"success": True, "result": result, "result_info": {"page": 1, "total_pages": 1}}}
    monkeypatch.setattr(cfa, "bridge", fake_bridge)
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: False)
    monkeypatch.setattr(plugin, "_home", lambda: None)
    monkeypatch.setattr(plugin, "_call_id", lambda: "call-1")
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


def handler_and_gate(profile):
    ctx = registered(profile)
    return ctx.tools["cloudflare"]["handler"], ctx.hooks[0][1]


def test_the_progress_line_shows_the_action_only(monkeypatch):
    display = pytest.importorskip("agent.display")
    monkeypatch.setattr(display, "_PREVIEW_BUILDERS", {})
    registered("researcher")
    line = lambda **args: display.build_tool_preview("cloudflare", args, max_len=0)
    assert line(action="dns_records", zone="secret-project.example", name="staging") == "dns_records"
    assert line(action="analytics", report="paths", zone="secret-project.example") == "analytics paths"
    assert line(action="status") == "status"
    assert line(action="anything", zone="x") is None


def test_assistant_researcher_and_marketer_get_the_tool_others_nothing():
    for profile in ("searcher", "writer", "creator", "default", "engineer"):
        ctx = registered(profile)
        assert ctx.tools == {} and ctx.hooks == [] and ctx.skills == {}
    for profile in ("assistant", "researcher", "marketer"):
        ctx = registered(profile)
        tool = ctx.tools["cloudflare"]
        assert tool["toolset"] == "cloudflare_access" and tool["schema"]["name"] == "cloudflare"
        params = tool["schema"]["parameters"]
        assert params["additionalProperties"] is False and params["required"] == ["action"]
        assert params["properties"]["action"]["enum"] == list(plugin.PROFILES[profile])
        assert 'skill_view(name="cloudflare-access:cloudflare")' in tool["description"]
        assert [name for name, _ in ctx.hooks] == ["pre_tool_call"]
        assert set(ctx.skills) == {"cloudflare"}


def test_the_read_profiles_hold_reads_only():
    for profile in ("researcher", "marketer"):
        assert set(plugin.PROFILES[profile]) == set(cfa.READS)
        assert not set(plugin.PROFILES[profile]) & set(cfa.WRITES)
    assert set(plugin.PROFILES["assistant"]) == set(cfa.READS + cfa.WRITES)
    assert "assistant" not in plugin.A2A
    assert not any(set(actions) & set(cfa.WRITES) for actions in plugin.A2A.values())


def test_a_read_reaches_the_engine(isolated):
    handler, gate = handler_and_gate("researcher")
    args = {"action": "zones", "zone": "example.com"}
    assert gate(tool_name="cloudflare", args=args) is None
    result = json.loads(handler(args))
    assert result["ok"] is True and result["zone"]["name"] == "example.com"
    assert isolated[-1]["path"] == "/zones" and ["name", "example.com"] in isolated[-1]["params"]


def test_an_action_outside_the_schema_is_refused_by_gate_and_handler(isolated):
    handler, gate = handler_and_gate("marketer")
    args = {"action": "purge_everything", "zone": "example.com"}
    assert gate(tool_name="cloudflare", args=args)["action"] == "block"
    assert json.loads(handler(args))["ok"] is False
    assert isolated == []


def test_inbound_a2a_reads_only_on_the_profile_it_is_bound_to(monkeypatch, isolated):
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    args = {"action": "zones"}
    handler, gate = handler_and_gate("assistant")
    directive = gate(tool_name="cloudflare", args=args)
    assert directive["action"] == "block" and "A2A" in directive["message"]
    assert "A2A" in json.loads(handler(args))["error"]
    handler, gate = handler_and_gate("researcher")
    monkeypatch.setattr(plugin, "_home", lambda: Path("/h/profiles/marketer"))
    assert gate(tool_name="cloudflare", args=args)["action"] == "block"
    monkeypatch.setattr(plugin, "_home", lambda: None)
    assert gate(tool_name="cloudflare", args=args)["action"] == "block"
    monkeypatch.setattr(plugin, "_home", lambda: Path("/h/profiles/researcher"))
    assert gate(tool_name="cloudflare", args=args) is None
    assert json.loads(handler(args))["ok"] is True
    assert [c["op"] for c in isolated] == ["call"]


def test_a_result_too_long_asks_to_narrow(monkeypatch):
    monkeypatch.setattr(plugin, "LIMIT", 10)
    handler, _ = handler_and_gate("assistant")
    result = json.loads(handler({"action": "zones"}))
    assert result["ok"] is False and "narrow it" in result["error"]


def test_engine_errors_come_back_as_json():
    handler, _ = handler_and_gate("assistant")
    result = json.loads(handler({"action": "dns_records"}))
    assert result == {"ok": False, "error": "zone is required: its domain (example.com) or its id (zones lists them)"}
    assert json.loads(handler(None))["ok"] is False


def test_the_hook_blocks_ways_around_the_tool():
    _, gate = handler_and_gate("marketer")
    directive = gate(tool_name="terminal", args={"command": "npx wrangler deploy"})
    assert directive == {"action": "block", "message": cfa.BYPASS_MESSAGE}
    assert gate(tool_name="read_file", args={"path": "/Users/x/.cloudflare-access/state.json"})["action"] == "block"
    assert gate(tool_name="terminal", args={"command": "ls"}) is None
