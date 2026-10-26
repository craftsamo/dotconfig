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
RECORD = {"id": "2" * 32, "type": "A", "name": "www.example.com", "content": "192.0.2.1", "proxied": False, "ttl": 1}


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(cfa, "STORE", tmp_path)  # never the real ~/.cloudflare-access
    calls = []
    head = {"account": "work", "account_id": ACCOUNT, "fingerprint": "f" * 12}

    def fake_bridge(op, **fields):
        calls.append({"op": op, **fields})
        if op == "keys":
            return {"ok": True, "data": [], "unused": [], "requests": 0}
        if op == "reads":
            results = [{"ok": True, "data": {"success": True, "result": dict(RECORD)}} for _ in fields["requests"]]
            return {**head, "ok": True, "requests": len(results), "results": results}
        if fields.get("method") == "POST":
            return {**head, "ok": True, "requests": 1, "status": 200,
                    "data": {"success": True, "result": {"patches": [dict(RECORD)]}}}
        result = [ZONE] if fields.get("path") == "/zones" else ZONE
        return {**head, "ok": True, "requests": 1,
                "data": {"success": True, "result": result, "result_info": {"page": 1, "total_pages": 1}}}
    monkeypatch.setattr(cfa, "bridge", fake_bridge)
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: False)
    monkeypatch.setattr(plugin, "_home", lambda: None)
    monkeypatch.setattr(plugin, "_call_id", lambda: "call-1")
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: None)   # a person is there to answer cards
    cfa._approved.clear()
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
        assert 'skill_view(name="cloudflare-access:read")' in tool["description"]
        assert [name for name, _ in ctx.hooks] == ["pre_tool_call"]
    assistant = registered("assistant")
    assert set(assistant.skills) == {"read", "manage"}
    tool = assistant.tools["cloudflare"]
    assert {"changes", "preview"} <= set(tool["schema"]["parameters"]["properties"])
    assert "dns_change" in tool["description"] and 'name="cloudflare-access:manage"' in tool["description"]
    for profile in ("researcher", "marketer"):
        ctx = registered(profile)
        tool = ctx.tools["cloudflare"]
        assert set(ctx.skills) == {"read"}
        assert not {"changes", "preview"} & set(tool["schema"]["parameters"]["properties"])
        assert "dns_change" not in tool["description"] and "manage" not in tool["description"]


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


UPDATE = {"action": "dns_change", "zone": "example.com", "changes": [{"op": "update", "id": "2" * 32,
                                                                      "content": "192.0.2.10"}]}


def sends(calls):
    return [c for c in calls if c["op"] == "call" and c["method"] != "GET"]


def fresh():
    return json.loads(json.dumps(UPDATE))


def test_a_change_runs_only_after_its_card(isolated):
    handler, gate = handler_and_gate("assistant")
    assert json.loads(handler(fresh()))["error"].startswith("not done: this write did not pass its approval card")
    assert sends(isolated) == []
    directive = gate(tool_name="cloudflare", args=fresh(), tool_call_id="call-1")
    assert directive["action"] == "approve" and directive["rule_key"].startswith("cloudflare-access:dns_change:")
    assert directive["message"].startswith("Cloudflare · Change DNS records\n⚠️ ")
    assert "~ A www: 192.0.2.1 → 192.0.2.10" in directive["message"]
    result = json.loads(handler(fresh()))
    assert result["ok"] is True
    [sent] = sends(isolated)
    assert sent["path"] == f"/zones/{'1' * 32}/dns_records/batch" and sent["expect"] == "f" * 12
    assert "did not pass its approval card" in json.loads(handler(fresh()))["error"]


def test_an_approval_covers_only_its_own_call(isolated):
    handler, gate = handler_and_gate("assistant")
    gate(tool_name="cloudflare", args=fresh(), tool_call_id="another-call")
    assert "did not pass" in json.loads(handler(fresh()))["error"]
    gate(tool_name="cloudflare", args=fresh(), tool_call_id="call-1")
    other = fresh()
    other["changes"][0]["content"] = "192.0.2.99"
    assert "did not pass" in json.loads(handler(other))["error"]
    assert sends(isolated) == []


@pytest.mark.parametrize("reason", ["yolo mode is on", "this is a cron job", "nobody is present to answer"])
def test_no_person_no_change_in_the_gate_and_the_handler(isolated, monkeypatch, reason):
    handler, gate = handler_and_gate("assistant")
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: reason)
    directive = gate(tool_name="cloudflare", args=fresh(), tool_call_id="call-1")
    assert directive["action"] == "block" and reason in directive["message"]
    assert "Nothing was sent" in directive["message"]
    assert reason in json.loads(handler(fresh()))["error"]
    assert sends(isolated) == [] and cfa._approved == {}
    # reads and previews still work there
    assert json.loads(handler({"action": "zones"}))["ok"] is True
    preview = json.loads(handler({**fresh(), "preview": True}))
    assert preview["preview"] is True and "192.0.2.10" in preview["card"]
    assert gate(tool_name="cloudflare", args={**fresh(), "preview": True}) is None
    assert sends(isolated) == []


def test_the_genuine_check_refuses_a_change_in_this_headless_test_run(isolated, monkeypatch):
    spec_ = importlib.util.spec_from_file_location("cloudflare_genuine_human_gate",
                                                   ROOT.parent / "_shared" / "human_gate.py")
    real = importlib.util.module_from_spec(spec_)
    spec_.loader.exec_module(real)
    monkeypatch.setattr(plugin, "human_gate", real)
    handler, gate = handler_and_gate("assistant")
    assert gate(tool_name="cloudflare", args=fresh(), tool_call_id="call-1")["action"] == "block"
    assert json.loads(handler(fresh()))["ok"] is False and sends(isolated) == []


def test_a_malformed_preview_counts_as_a_change(isolated):
    _, gate = handler_and_gate("assistant")
    directive = gate(tool_name="cloudflare", args={**fresh(), "preview": "yes"}, tool_call_id="call-1")
    assert directive["action"] == "block" and "preview must be true or false" in directive["message"]


def test_a_change_that_would_fail_is_blocked_before_any_card(isolated):
    _, gate = handler_and_gate("assistant")
    directive = gate(tool_name="cloudflare", args={**fresh(), "changes": []}, tool_call_id="call-1")
    assert directive["action"] == "block" and "1 to 20 changes" in directive["message"]
    directive = gate(tool_name="cloudflare", args={**fresh(), "setting": "ssl"}, tool_call_id="call-1")
    assert directive["action"] == "block" and "does not take setting" in directive["message"]
    assert cfa._approved == {}


def test_read_profiles_cannot_change_or_preview(isolated):
    for profile in ("researcher", "marketer"):
        handler, gate = handler_and_gate(profile)
        for args in (fresh(), {**fresh(), "preview": True}):
            assert gate(tool_name="cloudflare", args=args, tool_call_id="call-1")["action"] == "block"
            assert json.loads(handler(args))["ok"] is False
    assert sends(isolated) == [] and cfa._approved == {}


def test_the_hook_blocks_ways_around_the_tool():
    _, gate = handler_and_gate("marketer")
    directive = gate(tool_name="terminal", args={"command": "npx wrangler deploy"})
    assert directive == {"action": "block", "message": cfa.BYPASS_MESSAGE}
    assert gate(tool_name="read_file", args={"path": "/Users/x/.cloudflare-access/state.json"})["action"] == "block"
    assert gate(tool_name="terminal", args={"command": "ls"}) is None
