import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("stripe_access_plugin_test", ROOT / "__init__.py")
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)
sta = plugin.sta


CUSTOMER = {"id": "cus_1", "object": "customer", "name": "Ada", "email": "ada@example.com"}


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(sta, "STORE", tmp_path)  # never the real ~/.stripe-access
    calls = []

    def fake_bridge(op, **fields):
        calls.append({"op": op, **fields})
        if op == "keys":
            return {"ok": True, "data": [], "requests": 0}
        if op == "key":
            return {"ok": True, "account": "work", "mode": fields.get("mode"), "fingerprint": "f" * 12,
                    "key_kind": "restricted", "requests": 0}
        data = {"object": "list", "data": [], "has_more": False}
        if fields.get("path", "").startswith("/v1/customers") and fields.get("method") in ("GET", "POST") \
                and fields.get("path") != "/v1/customers":
            data = dict(CUSTOMER)
        if fields.get("method") == "POST" and fields.get("path") == "/v1/customers":
            data = {**CUSTOMER, "id": "cus_new"}
        return {"ok": True, "account": "work", "mode": fields.get("mode"), "requests": 1, "fingerprint": "f" * 12,
                "data": data}
    monkeypatch.setattr(sta, "bridge", fake_bridge)
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: False)
    monkeypatch.setattr(plugin, "_home", lambda: None)
    monkeypatch.setattr(plugin, "_call_id", lambda: "call-1")
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: None)   # a person is there to answer cards
    sta._approved.clear()
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
    return ctx.tools["stripe"]["handler"], ctx.hooks[0][1]


def test_the_progress_line_shows_the_action_and_mode_only(monkeypatch):
    display = pytest.importorskip("agent.display")
    monkeypatch.setattr(display, "_PREVIEW_BUILDERS", {})
    registered("researcher")
    line = lambda **args: display.build_tool_preview("stripe", args, max_len=0)
    assert line(action="customers", mode="live", query="email:'someone@example.com'") == "customers live"
    assert line(action="status") == "status"
    assert line(action="anything", mode="prod", query="secret") is None


def test_assistant_researcher_and_marketer_get_the_tool_others_nothing():
    for profile in ("searcher", "writer", "creator", "default", "engineer"):
        ctx = registered(profile)
        assert ctx.tools == {} and ctx.hooks == [] and ctx.skills == {}
    for profile in ("assistant", "researcher", "marketer"):
        ctx = registered(profile)
        tool = ctx.tools["stripe"]
        assert tool["toolset"] == "stripe_access" and tool["schema"]["name"] == "stripe"
        params = tool["schema"]["parameters"]
        assert params["additionalProperties"] is False and params["required"] == ["action"]
        assert params["properties"]["action"]["enum"] == list(plugin.PROFILES[profile])
        assert params["properties"]["mode"]["enum"] == ["live", "test"]
        assert 'skill_view(name="stripe-access:stripe")' in tool["description"]
        assert [name for name, _ in ctx.hooks] == ["pre_tool_call"]
    assistant = registered("assistant")
    assert set(assistant.skills) == {"stripe", "stripe-manage"}
    tool = assistant.tools["stripe"]
    properties = tool["schema"]["parameters"]["properties"]
    assert {"items", "metadata", "percent_off", "proration", "preview", "reason"} <= set(properties)
    assert "refund_create" in tool["description"] and 'name="stripe-access:stripe-manage"' in tool["description"]
    assert "refund_create" in properties["payment"]["description"]
    for profile in ("researcher", "marketer"):
        ctx = registered(profile)
        tool = ctx.tools["stripe"]
        properties = tool["schema"]["parameters"]["properties"]
        assert set(ctx.skills) == {"stripe"}
        assert not {"items", "metadata", "percent_off", "preview"} & set(properties)
        assert "refund_create" not in tool["description"] and "stripe-manage" not in tool["description"]


def test_the_read_profiles_hold_reads_only():
    for profile in ("researcher", "marketer"):
        assert set(plugin.PROFILES[profile]) == set(sta.READS)
        assert not set(plugin.PROFILES[profile]) & set(sta.WRITES)
    assert set(plugin.PROFILES["assistant"]) == set(sta.READS + sta.WRITES)
    assert "assistant" not in plugin.A2A
    assert not any(set(actions) & set(sta.WRITES) for actions in plugin.A2A.values())


def test_a_read_reaches_the_engine(isolated):
    handler, gate = handler_and_gate("researcher")
    args = {"action": "invoices", "mode": "live", "status": "open"}
    assert gate(tool_name="stripe", args=args) is None
    result = json.loads(handler(args))
    assert result["ok"] is True and result["action"] == "invoices"
    assert isolated[-1]["path"] == "/v1/invoices" and ["status", "open"] in isolated[-1]["params"]


def test_an_action_outside_the_schema_is_refused_by_gate_and_handler(isolated):
    handler, gate = handler_and_gate("marketer")
    args = {"action": "refund_create", "mode": "live"}
    assert gate(tool_name="stripe", args=args)["action"] == "block"
    assert json.loads(handler(args))["ok"] is False
    assert isolated == []


def test_inbound_a2a_reads_only_on_the_profile_it_is_bound_to(monkeypatch, isolated):
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    args = {"action": "balance", "mode": "live"}
    handler, gate = handler_and_gate("assistant")
    directive = gate(tool_name="stripe", args=args)
    assert directive["action"] == "block" and "A2A" in directive["message"]
    assert "A2A" in json.loads(handler(args))["error"]
    handler, gate = handler_and_gate("researcher")
    monkeypatch.setattr(plugin, "_home", lambda: Path("/h/profiles/marketer"))
    assert gate(tool_name="stripe", args=args)["action"] == "block"
    monkeypatch.setattr(plugin, "_home", lambda: None)
    assert gate(tool_name="stripe", args=args)["action"] == "block"
    monkeypatch.setattr(plugin, "_home", lambda: Path("/h/profiles/researcher"))
    assert gate(tool_name="stripe", args=args) is None
    assert json.loads(handler(args))["ok"] is True
    assert [c["op"] for c in isolated] == ["call"]


def test_a_result_too_long_asks_to_narrow(monkeypatch):
    monkeypatch.setattr(plugin, "LIMIT", 10)
    handler, _ = handler_and_gate("assistant")
    result = json.loads(handler({"action": "customers", "mode": "live"}))
    assert result["ok"] is False and "narrow it" in result["error"]


def test_engine_errors_come_back_as_json():
    handler, _ = handler_and_gate("assistant")
    result = json.loads(handler({"action": "customers"}))
    assert result == {"ok": False, "error": "mode is required: live (real money) or test (a test or sandbox key)"}
    assert json.loads(handler(None))["ok"] is False


UPDATE = {"action": "customer_update", "mode": "live", "id": "cus_1", "email": "ada@new.example"}


def sends(calls):
    return [c for c in calls if c["op"] == "call" and c["method"] != "GET"]


def test_a_change_runs_only_after_its_card(isolated):
    handler, gate = handler_and_gate("assistant")
    assert json.loads(handler(dict(UPDATE)))["error"].startswith("not done: this write did not pass its approval card")
    assert sends(isolated) == []
    directive = gate(tool_name="stripe", args=dict(UPDATE), tool_call_id="call-1")
    assert directive["action"] == "approve" and directive["rule_key"].startswith("stripe-access:customer_update:")
    assert directive["message"].startswith("Stripe · Update a customer\n⚠️ Replaces the customer's details\n"
                                           "Account: work\nMode: LIVE, real money\n\n--- Change ---\n")
    assert "Email: ada@example.com → ada@new.example" in directive["message"]
    result = json.loads(handler(dict(UPDATE)))
    assert result["ok"] is True and result["result"]["id"] == "cus_1"
    [sent] = sends(isolated)
    assert sent["path"] == "/v1/customers/cus_1" and sent["params"] == [["email", "ada@new.example"]]
    assert sent["expect"] == "f" * 12 and sent["idempotency_key"].startswith("hermes-")
    # the approval is spent: the same call again is not covered
    assert "did not pass its approval card" in json.loads(handler(dict(UPDATE)))["error"]


def test_an_approval_covers_only_its_own_call(isolated):
    handler, gate = handler_and_gate("assistant")
    gate(tool_name="stripe", args=dict(UPDATE), tool_call_id="another-call")
    assert "did not pass" in json.loads(handler(dict(UPDATE)))["error"]
    gate(tool_name="stripe", args=dict(UPDATE), tool_call_id="call-1")
    assert "did not pass" in json.loads(handler({**UPDATE, "email": "eve@example.com"}))["error"]
    assert sends(isolated) == []


def test_money_moving_cards_are_never_covered_by_always(isolated, monkeypatch):
    _, gate = handler_and_gate("assistant")
    keys = {gate(tool_name="stripe", args=dict(UPDATE), tool_call_id=str(n))["rule_key"] for n in range(2)}
    assert len(keys) == 1   # an identical customer edit may repeat under "always"
    plan = {"action": "refund_create"}
    assert sta.rule_key(plan, "d" * 64) != sta.rule_key(plan, "d" * 64)
    assert sta.ONCE == {"refund_create", "invoice_finalize", "invoice_send", "invoice_void",
                        "subscription_update", "subscription_cancel", "coupon_delete"}


@pytest.mark.parametrize("reason", ["yolo mode is on", "this is a cron job", "nobody is present to answer"])
def test_no_person_no_change_in_the_gate_and_the_handler(isolated, monkeypatch, reason):
    handler, gate = handler_and_gate("assistant")
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: reason)
    directive = gate(tool_name="stripe", args=dict(UPDATE), tool_call_id="call-1")
    assert directive["action"] == "block" and reason in directive["message"] and "Nothing was sent" in directive["message"]
    assert reason in json.loads(handler(dict(UPDATE)))["error"]
    assert sends(isolated) == [] and sta._approved == {}
    # reads and previews still work there
    assert json.loads(handler({"action": "customers", "mode": "live"}))["ok"] is True
    preview = json.loads(handler({**UPDATE, "preview": True}))
    assert preview["preview"] is True and "ada@new.example" in preview["card"]
    assert gate(tool_name="stripe", args={**UPDATE, "preview": True}) is None
    assert sends(isolated) == []


def test_the_genuine_check_refuses_a_change_in_this_headless_test_run(isolated, monkeypatch):
    spec_ = importlib.util.spec_from_file_location("stripe_genuine_human_gate", ROOT.parent / "_shared" / "human_gate.py")
    real = importlib.util.module_from_spec(spec_)
    spec_.loader.exec_module(real)
    monkeypatch.setattr(plugin, "human_gate", real)
    handler, gate = handler_and_gate("assistant")
    assert gate(tool_name="stripe", args=dict(UPDATE), tool_call_id="call-1")["action"] == "block"
    assert json.loads(handler(dict(UPDATE)))["ok"] is False and sends(isolated) == []


def test_a_malformed_preview_counts_as_a_change(isolated):
    handler, gate = handler_and_gate("assistant")
    directive = gate(tool_name="stripe", args={**UPDATE, "preview": "yes"}, tool_call_id="call-1")
    assert directive["action"] == "block" and "preview must be true or false" in directive["message"]


def test_a_change_that_would_fail_is_blocked_before_any_card(isolated):
    _, gate = handler_and_gate("assistant")
    directive = gate(tool_name="stripe", args={"action": "customer_update", "mode": "live", "id": "cus_1"},
                     tool_call_id="call-1")
    assert directive["action"] == "block" and "needs a change" in directive["message"]
    directive = gate(tool_name="stripe", args={**UPDATE, "amount": 5}, tool_call_id="call-1")
    assert directive["action"] == "block" and "does not take amount" in directive["message"]
    assert sta._approved == {}


def test_read_profiles_cannot_change_or_preview(isolated):
    for profile in ("researcher", "marketer"):
        handler, gate = handler_and_gate(profile)
        for args in (dict(UPDATE), {**UPDATE, "preview": True}):
            assert gate(tool_name="stripe", args=args, tool_call_id="call-1")["action"] == "block"
            assert json.loads(handler(args))["ok"] is False
    assert sends(isolated) == [] and sta._approved == {}


def test_the_hook_blocks_ways_around_the_tool():
    _, gate = handler_and_gate("marketer")
    directive = gate(tool_name="terminal", args={"command": "stripe invoices list"})
    assert directive == {"action": "block", "message": sta.BYPASS_MESSAGE}
    assert gate(tool_name="read_file", args={"path": "/Users/x/.stripe-access/state.json"})["action"] == "block"
    assert gate(tool_name="terminal", args={"command": "ls"}) is None
