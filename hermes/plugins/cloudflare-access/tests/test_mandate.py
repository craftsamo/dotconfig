"""Zone mandates: the terms, the card, making and ending one, and the writes that run on one instead of a card."""

import importlib.util
import json
import re
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("cloudflare_access_mandate_plugin_test", ROOT / "__init__.py")
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)
cfa = plugin.cfa
mandate = plugin.mandate

ACCOUNT = "0123456789abcdef0123456789abcdef"
OTHER_ACCOUNT = "fedcba9876543210fedcba9876543210"
ACCOUNTS = {"work": ACCOUNT, "other": OTHER_ACCOUNT}
ZONE, ZONE_B, ZONE_X = "1" * 32, "5" * 32, "6" * 32
ZONES = {ZONE: {"id": ZONE, "name": "example.com", "account": {"id": ACCOUNT, "name": "Work"}},
         ZONE_B: {"id": ZONE_B, "name": "example.org", "account": {"id": ACCOUNT, "name": "Work"}},
         ZONE_X: {"id": ZONE_X, "name": "foreign.net", "account": {"id": OTHER_ACCOUNT, "name": "Other"}}}
WWW, PRIVATE, DIRECT, MAIL = "2" * 32, "3" * 32, "7" * 32, "8" * 32
TUNNEL_HOST = "11111111-1111-4111-8111-111111111111.cfargotunnel.com"
ADDRESSES = "/accounts/{account}/email/routing/addresses"
WORKER = "/accounts/{account}/workers/scripts/api/deployments"
BUCKETS = "/accounts/{account}/r2/buckets"
HOUR = 3600


def envelope(result):
    return {"success": True, "errors": [], "messages": [], "result": result}


class Cloudflare:
    """Cloudflare as the bridge answers: zones of two accounts, records, settings, and every request kept."""

    def __init__(self):
        self.requests = []
        self.records = {
            WWW: {"id": WWW, "type": "A", "name": "www.example.com", "content": "192.0.2.1", "proxied": True, "ttl": 1},
            PRIVATE: {"id": PRIVATE, "type": "CNAME", "name": "app.example.com", "content": TUNNEL_HOST,
                      "proxied": True, "ttl": 1},
            DIRECT: {"id": DIRECT, "type": "A", "name": "direct.example.com", "content": "192.0.2.9",
                     "proxied": False, "ttl": 1},
            MAIL: {"id": MAIL, "type": "MX", "name": "example.com", "content": "mx.example.net", "priority": 10,
                   "proxied": False, "ttl": 1}}
        self.settings = {"ssl": "full", "development_mode": "off", "browser_cache_ttl": 14400,
                         "email_obfuscation": "on", "automatic_https_rewrites": "on", "tls_1_3": "on"}
        self.answers = {
            ADDRESSES: envelope([{"email": "owner@example.net", "verified": "2026-01-01T00:00:00Z"}]),
            WORKER: envelope({"deployments": [
                {"id": "d2", "created_on": "2026-10-02T00:00:00Z",
                 "versions": [{"version_id": "2" * 8 + "-2222-4222-8222-222222222222", "percentage": 100}]},
                {"id": "d1", "created_on": "2026-10-01T00:00:00Z",
                 "versions": [{"version_id": "1" * 8 + "-1111-4111-8111-111111111111", "percentage": 100}]}]}),
            BUCKETS: envelope({"buckets": []})}

    def head(self, fields):
        label = fields.get("account") or "work"
        return {"account": label, "item": "CLOUDFLARE_WORK", "account_id": ACCOUNTS[label], "fingerprint": "f" * 12,
                "token_kind": "user"}

    def read(self, path, params=None):
        zone = re.fullmatch(r"/zones/([0-9a-f]{32})", path)
        setting = re.fullmatch(rf"/zones/{ZONE}/settings/(\w+)", path)
        record = re.fullmatch(rf"/zones/{ZONE}/dns_records/([0-9a-f]{{32}})", path)
        if path == "/zones":
            name = dict(params or []).get("name")
            found = [z for z in ZONES.values() if z["name"] == name]
            return {"ok": True, "status": 200, "data": envelope(found)}
        if zone and zone.group(1) in ZONES:
            return {"ok": True, "status": 200, "data": envelope(ZONES[zone.group(1)])}
        if setting and setting.group(1) in self.settings:
            return {"ok": True, "status": 200, "data": envelope(
                {"id": setting.group(1), "value": self.settings[setting.group(1)], "editable": True})}
        if record and record.group(1) in self.records:
            return {"ok": True, "status": 200, "data": envelope(dict(self.records[record.group(1)]))}
        if path in self.answers:
            return {"ok": True, "status": 200, "data": self.answers[path]}
        return {"ok": False, "kind": "not_found", "status": 404, "error": "not found"}

    def __call__(self, op, **fields):
        self.requests.append({"op": op, **fields})
        if op == "reads":
            results = [self.read(r["path"], r.get("params")) for r in fields["requests"]]
            return {**self.head(fields), "ok": True, "requests": len(results), "results": results}
        if fields.get("method") == "GET":
            return {**self.head(fields), "requests": 1, **self.read(fields["path"], fields.get("params"))}
        result = {"posts": [], "patches": [], "deletes": []} if fields["path"].endswith("/batch") else {"id": "new"}
        return {**self.head(fields), "ok": True, "requests": 1, "status": 200, "data": envelope(result)}

    def sends(self):
        return [r for r in self.requests if r["op"] == "call" and r["method"] != "GET"]


def fake_cli(path, keyfile):
    """A secret CLI over one key file: ``get`` prints it, ``show`` says it exists, ``set --stdin`` stores it."""
    path.write_text(f"#!/bin/sh\n[ \"$1\" = get ] && [ -f {keyfile} ] && cat {keyfile} && exit 0\n"
                    f"[ \"$1\" = show ] && [ -f {keyfile} ] && exit 0\n"
                    f"[ \"$1\" = set ] && [ ! -f {keyfile} ] && cat > {keyfile} && exit 0\nexit 1\n")
    path.chmod(0o755)
    return path


class Ctx:
    def __init__(self, profile):
        self.profile_name = profile
        self.tools = {}
        self.hooks = []

    def register_skill(self, *args, **kwargs):
        pass

    def register_tool(self, **kwargs):
        self.tools[kwargs["name"]] = kwargs

    def register_hook(self, name, callback):
        self.hooks.append((name, callback))


class Rig:
    """The Assistant's tools over a fake Cloudflare, a fake Keychain and a profile home of their own."""

    def __init__(self, monkeypatch, tmp_path):
        self.keyfile = tmp_path / "keyfile"
        self.home = tmp_path / "profile"
        self.cloud = Cloudflare()
        self.nobody = None   # why nobody can answer a card, or None
        self.monkeypatch = monkeypatch
        self.calls = 0
        monkeypatch.setattr(mandate.mandate_store, "SECRET", fake_cli(tmp_path / "secret", self.keyfile))
        monkeypatch.setattr(cfa, "STORE", tmp_path / "store")
        monkeypatch.setattr(cfa, "bridge", self.cloud)
        monkeypatch.setattr(cfa.cards, "roomy", lambda: False)
        monkeypatch.setattr(plugin, "_home", lambda: self.home)
        monkeypatch.setattr(plugin, "_inbound_peer", lambda: False)
        monkeypatch.setattr(plugin.human_gate, "no_human", lambda: self.nobody)
        cfa._approved.clear()
        mandate._SHOWN.clear()
        ctx = Ctx("assistant")
        plugin.register(ctx)
        self.handlers = {name: tool["handler"] for name, tool in ctx.tools.items()}
        self.gate = ctx.hooks[0][1]

    def call(self, tool, args, approve=True):
        """The hook, then (unless it blocked or the card was denied) the handler: (directive, result)."""
        self.calls += 1
        call_id = f"call-{self.calls}"
        self.monkeypatch.setattr(plugin, "_call_id", lambda: call_id)
        directive = self.gate(tool_name=tool, args=args, tool_call_id=call_id)
        if directive and (directive["action"] == "block" or not approve):
            return directive, None
        return directive, json.loads(self.handlers[tool](args))

    def write(self, args):
        return self.call("cloudflare", args)

    def make(self, **over):
        directive, result = self.call("cloudflare_mandate", create(**over))
        assert directive["action"] == "approve" and result["ok"] is True, (directive, result)
        return result["mandate"]

    def listed(self):
        return json.loads(self.handlers["cloudflare_mandate"]({"action": "list"}))["mandates"]

    def used(self, mandate_id, now=None):
        secret = mandate.mandate_store.key(mandate.STORE, self.home)
        return mandate.mandate_ledger.count(mandate.STORE, self.home, secret, mandate.LEDGER_KIND, mandate_id,
                                            now or time.time(), HOUR, mandate.USED_UP)


@pytest.fixture
def rig(monkeypatch, tmp_path):
    return Rig(monkeypatch, tmp_path)


def create(**over):
    return {"action": "create", "zones": ["example.com"], "classes": ["dns", "settings", "purge"], "per_hour": 5,
            "days": 3, "purpose": "Point the staging hosts at the new origin", **over}


ADD = {"op": "add", "type": "A", "name": "staging", "content": "192.0.2.5", "proxied": True}
UPDATE = {"op": "update", "id": WWW, "content": "192.0.2.10"}


def dns(*changes, zone="example.com", **extra):
    return {"action": "dns_change", "zone": zone, "changes": list(changes), **extra}


def setting(*pairs, zone="example.com"):
    return {"action": "zone_setting", "zone": zone, "settings": [{"setting": s, "value": v} for s, v in pairs]}


def purge(**extra):
    return {"action": "cache_purge", "zone": "example.com", **extra}


GOOD = dict(account="work", account_id=ACCOUNT, zones=[{"id": ZONE, "name": "example.com"}], classes=["dns"],
            per_hour=5, days=3, purpose="Point the staging hosts at the new origin")


# --- the terms ------------------------------------------------------------------------------------

def test_terms_are_checked_and_fixed_at_the_card():
    t = mandate.terms(**{**GOOD, "classes": ["purge", "dns", "dns"], "purpose": "  Warm\n the   caches "}, now=1000)
    assert t["classes"] == ["dns", "purge"] and t["purpose"] == "Warm the caches"
    assert t["expires"] == 1000 + 3 * mandate.DAY and t["zones"] == GOOD["zones"]
    assert mandate.same_terms(t, {**t, "expires": 1})
    assert not mandate.same_terms(t, {**t, "per_hour": 6})


@pytest.mark.parametrize("over, message", [
    ({"per_hour": 0}, "per_hour is a whole number from 1 to 20"),
    ({"per_hour": 21}, "per_hour is a whole number from 1 to 20"),
    ({"per_hour": True}, "per_hour"),
    ({"per_hour": "5"}, "per_hour"),
    ({"days": 0}, "days is a whole number from 1 to 7"),
    ({"days": 8}, "days is a whole number from 1 to 7"),
    ({"days": True}, "days"),
    ({"days": 1.5}, "days"),
    ({"zones": []}, "one to 3 zones"),
    ({"zones": [{"id": str(n) * 32, "name": f"z{n}.com"} for n in range(1, 5)]}, "one to 3 zones"),
    ({"zones": [{"id": ZONE, "name": "a.com"}, {"id": ZONE, "name": "b.com"}]}, "named once"),
    ({"zones": ["example.com"]}, "each zone is {id, name}"),
    ({"zones": [{"id": "nope", "name": "a.com"}]}, "32 hexadecimal"),
    ({"zones": [{"id": ZONE, "name": ""}]}, "has a name"),
    ({"classes": []}, "classes is a list of: dns, settings, purge"),
    ({"classes": ["delete"]}, "classes is a list of"),
    ({"classes": ["dns", 3]}, "classes is a list of"),
    ({"classes": "dns"}, "classes is a list of"),
    ({"purpose": ""}, "purpose says what"),
    ({"purpose": "x" * 201}, "at most 200"),
    ({"account": " "}, "account is the label"),
    ({"account_id": "abc"}, "32 hexadecimal"),
])
def test_terms_refuse_what_is_out_of_bounds(over, message):
    with pytest.raises(mandate.MandateError, match=re.escape(message)):
        mandate.terms(**{**GOOD, **over})


def test_the_store_holds_every_mandate_to_seven_days():
    assert mandate.STORE.max_days == 7 and mandate.STORE.mac_kind == "cloudflare-mandate"
    assert mandate.STORE.key_prefix == "CLOUDFLARE_MANDATE_KEY_" and mandate.STORE.scope == "cloudflare-access"


def test_the_card_shows_every_bound(monkeypatch):
    t = mandate.terms(**{**GOOD, "zones": [{"id": ZONE, "name": "example.com"}, {"id": ZONE_B, "name": "example.org"}],
                         "classes": ["dns", "settings", "purge"], "per_hour": 12, "days": 1})
    assert "Never covered" not in mandate.card(t)   # the shared rules give way first on a short card
    monkeypatch.setattr(mandate.cards, "budget", lambda where=None: mandate.cards.ROOMY["telegram"])
    card = mandate.card(t)
    assert card.startswith("Cloudflare · Zone mandate\n🚨 Covered changes to these zones skip the card\n")
    assert f"Account: work ({ACCOUNT})" in card
    assert f"Zone: example.com ({ZONE})\nZone: example.org ({ZONE_B})" in card
    assert "Covers: DNS: proxied A, AAAA, CNAME (add, update), settings (none weakened), purges (not everything)" in card
    assert "Up to: 12 changes an hour" in card and "(1 day)" in card
    assert "Purpose: Point the staging hosts at the new origin" in card
    assert "Never covered: deletes, MX/TXT/NS and unproxied records, weaker protection, purging everything" in card


def test_a_card_that_cannot_show_every_bound_is_refused(monkeypatch):
    monkeypatch.setattr(mandate.cards, "budget", lambda where=None: 120)
    with pytest.raises(mandate.MandateError, match="cannot show all its bounds"):
        mandate.card(mandate.terms(**GOOD))


# --- making, listing and ending one ---------------------------------------------------------------

def test_a_mandate_is_made_on_its_own_card_listed_and_revoked(rig):
    directive, result = rig.call("cloudflare_mandate", create())
    assert directive["action"] == "approve" and directive["message"].startswith("Cloudflare · Zone mandate\n🚨 ")
    assert directive["rule_key"].startswith("cloudflare-access:mandate:")
    made = result["mandate"]
    assert result["ok"] is True and made["zones"] == ["example.com"] and made["account"] == "work"
    assert made["classes"] == ["dns", "settings", "purge"] and made["per_hour"] == 5
    assert rig.listed() == [made]
    assert re.fullmatch(r"[0-9a-f]{64}", rig.keyfile.read_text().strip())   # the first mandate made the key
    assert (rig.home / "cloudflare-access" / "uses.jsonl").is_file()
    _, ended = rig.call("cloudflare_mandate", {"action": "revoke", "mandate": made["id"]})
    assert ended == {"ok": True, "revoked": made["id"]} and rig.listed() == []


def test_every_mandate_asks_with_a_fresh_key_even_beside_one_in_force(rig):
    rig.make()
    keys = {rig.call("cloudflare_mandate", create(), approve=False)[0]["rule_key"] for _ in range(3)}
    assert len(keys) == 3


def test_a_mandate_is_made_only_after_its_card(rig):
    result = json.loads(rig.handlers["cloudflare_mandate"](create()))
    assert result["ok"] is False and "only on its own card" in result["error"] and rig.listed() == []
    rig.gate(tool_name="cloudflare_mandate", args=create(days=2), tool_call_id="x")
    other = json.loads(rig.handlers["cloudflare_mandate"](create()))   # a card for different terms is no card
    assert other["ok"] is False and rig.listed() == []


def test_a_denied_card_makes_nothing(rig):
    directive, result = rig.call("cloudflare_mandate", create(), approve=False)
    assert directive["action"] == "approve" and result is None and rig.listed() == []


def test_nobody_to_answer_no_mandate(rig):
    rig.nobody = "this is a cron job"
    directive, _ = rig.call("cloudflare_mandate", create())
    assert directive["action"] == "block" and "this is a cron job" in directive["message"]
    rig.nobody = None
    rig.gate(tool_name="cloudflare_mandate", args=create(), tool_call_id="call-9")
    rig.nobody = "yolo mode is on"
    rig.monkeypatch.setattr(plugin, "_call_id", lambda: "call-9")
    result = json.loads(rig.handlers["cloudflare_mandate"](create()))
    assert result["ok"] is False and "yolo mode is on" in result["error"] and rig.listed() == []
    assert not (rig.home / "cloudflare-access" / "head.json").exists()


def test_inbound_a2a_makes_lists_and_revokes_nothing(rig):
    made = rig.make()
    rig.monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    for args in (create(), {"action": "list"}, {"action": "revoke", "mandate": made["id"]}):
        directive = rig.gate(tool_name="cloudflare_mandate", args=args, tool_call_id="a")
        assert directive["action"] == "block" and "A2A" in directive["message"]
        assert "A2A" in json.loads(rig.handlers["cloudflare_mandate"](args))["error"]
    rig.monkeypatch.setattr(plugin, "_inbound_peer", lambda: False)
    assert [m["id"] for m in rig.listed()] == [made["id"]]


def test_a_zone_that_changed_between_the_card_and_the_handler_makes_nothing(rig):
    rig.gate(tool_name="cloudflare_mandate", args=create(), tool_call_id="call-1")
    rig.monkeypatch.setattr(plugin, "_call_id", lambda: "call-1")
    moved = dict(ZONES[ZONE_B], name="example.com")
    rig.monkeypatch.setitem(ZONES, ZONE_B, moved)
    rig.monkeypatch.setitem(ZONES, ZONE, dict(ZONES[ZONE], name="example.net"))
    result = json.loads(rig.handlers["cloudflare_mandate"](create()))
    assert result["ok"] is False and "zones changed since the card" in result["error"] and rig.listed() == []


@pytest.mark.parametrize("over, message", [
    ({"zones": ["foreign.net"]}, "belongs to another Cloudflare account"),
    ({"zones": ["missing.example"]}, "not in the Cloudflare account"),
    ({"zones": ["example.com", "foreign.net"]}, "belongs to another Cloudflare account"),
    ({"zones": ["example.com", "example.com"]}, "named once"),
    ({"zones": ["a.example", "b.example", "c.example", "d.example"]}, "one to 3 domains"),
    ({"zones": None}, "one to 3 domains"),
    ({"per_hour": 21}, "per_hour"),
    ({"days": 8}, "days"),
    ({"classes": ["dns", "delete"]}, "classes"),
    ({"mandate": "m00000000"}, "does not take mandate"),
])
def test_terms_that_are_refused_never_reach_a_card(rig, over, message):
    directive = rig.gate(tool_name="cloudflare_mandate", args=create(**over), tool_call_id="x")
    assert directive["action"] == "block" and message in directive["message"]
    assert rig.listed() == []


def test_a_zone_of_another_account_is_named_on_that_account_only(rig):
    made = rig.make(account="other", zones=["foreign.net"], classes=["purge"])
    assert made["zones"] == ["foreign.net"] and made["account"] == "other"
    assert rig.call("cloudflare_mandate", create(account="other", zones=["example.com"]))[1] is None


def test_the_mandate_tool_is_the_assistants_and_read_profiles_get_none():
    for profile in ("researcher", "marketer"):
        ctx = Ctx(profile)
        plugin.register(ctx)
        assert "cloudflare_mandate" not in ctx.tools
        gate = ctx.hooks[0][1]
        assert gate(tool_name="cloudflare_mandate", args=create())["action"] == "block"
    ctx = Ctx("assistant")
    plugin.register(ctx)
    schema = ctx.tools["cloudflare_mandate"]["schema"]["parameters"]
    assert schema["additionalProperties"] is False and schema["required"] == ["action"]
    assert schema["properties"]["action"]["enum"] == ["create", "list", "revoke"]
    assert schema["properties"]["classes"]["items"]["enum"] == list(mandate.CLASSES)
    assert ctx.tools["cloudflare_mandate"]["emoji"] and ctx.tools["cloudflare_mandate"]["toolset"] == "cloudflare_access"


def test_the_progress_line_of_the_mandate_tool_shows_the_action_only(monkeypatch):
    display = pytest.importorskip("agent.display")
    monkeypatch.setattr(display, "_PREVIEW_BUILDERS", {})
    plugin.register(Ctx("assistant"))
    line = lambda **args: display.build_tool_preview("cloudflare_mandate", args, max_len=0)
    assert line(action="create", zones=["secret-project.example"], purpose="the merger") == "create"
    assert line(action="revoke", mandate="m1a2b3c4d") == "revoke"
    assert line(action="anything") is None


# --- writes that fit a mandate --------------------------------------------------------------------

COVERED = [   # the call, and how many changes it counts
    pytest.param(dns(ADD, UPDATE), 2, id="dns-add-and-update"),
    pytest.param(dns({"op": "add", "type": "AAAA", "name": "v6", "content": "2001:db8::1", "proxied": True},
                     {"op": "add", "type": "CNAME", "name": "blog", "content": "sites.example.net", "proxied": True},
                     {"op": "update", "id": WWW, "ttl": 300}), 3, id="dns-aaaa-cname-and-a-ttl-update"),
    pytest.param(setting(("development_mode", "on"), ("browser_cache_ttl", "3600")), 2, id="settings"),
    pytest.param(setting(("ssl", "strict")), 1, id="ssl-raised"),
    pytest.param(purge(hosts=["static.example.com"]), 1, id="purge-hosts"),
    pytest.param(purge(prefixes=["www.example.com/a", "www.example.com/b"]), 2, id="purge-prefixes"),
    pytest.param(purge(urls=["https://www.example.com/a"]), 1, id="purge-urls"),
]


@pytest.mark.parametrize("args, changes", COVERED)
@pytest.mark.parametrize("nobody", [None, "this is a cron job"], ids=["attended", "unattended"])
def test_a_covered_write_runs_with_no_card_and_each_change_is_counted(rig, args, changes, nobody):
    made = rig.make()
    rig.nobody = nobody
    directive, result = rig.write(args)
    assert directive is None and result["ok"] is True, result
    assert len(rig.cloud.sends()) == len(cfa.write_plan(args)["steps"])
    assert rig.used(made["id"]) == changes == mandate.weight(cfa.write_plan(args))
    assert cfa._approved == {}   # the record is spent


def test_the_gate_records_the_mandate_and_the_handler_peeks_without_spending_it(rig):
    made = rig.make()
    rig.nobody = "this is a cron job"
    assert rig.gate(tool_name="cloudflare", args=dns(ADD), tool_call_id="c1") is None
    assert cfa.covered_by_mandate(dns(ADD), "c1") and cfa.covered_by_mandate(dns(ADD), "c1")
    assert not cfa.covered_by_mandate(dns(ADD), "c2") and not cfa.covered_by_mandate(dns(UPDATE), "c1")
    [(_, _, recorded)] = cfa._approved.values()
    assert recorded == made["id"]


def test_a_mandate_covers_only_its_class(rig):
    rig.make(classes=["dns"])
    directive, _ = rig.write(purge(hosts=["static.example.com"]))
    assert directive["action"] == "approve" and rig.cloud.sends()[0]["path"].endswith("/purge_cache")
    rig.nobody = "this is a cron job"
    assert rig.write(setting(("ssl", "strict")))[0]["action"] == "block"
    assert rig.write(dns(ADD))[0] is None


def test_the_hours_last_slot_goes_to_one_and_the_next_asks(rig):
    made = rig.make(per_hour=2)
    for n in range(2):
        rig.nobody = "this is a cron job" if n else None
        directive, result = rig.write(dns({**ADD, "name": f"h{n}"}))
        assert directive is None and result["ok"] is True
    assert rig.used(made["id"]) == 2
    rig.nobody = None
    directive, _ = rig.write(dns({**ADD, "name": "h2"}))
    assert directive["action"] == "approve"   # a card, as before
    rig.nobody = "this is a cron job"
    directive, result = rig.write(dns({**ADD, "name": "h3"}))
    assert directive["action"] == "block" and "cron job" in directive["message"] and result is None
    assert len(rig.cloud.sends()) == 3 and rig.used(made["id"]) == 2
    plan = cfa.write_plan(dns({**ADD, "name": "h4"}))
    assert mandate.covering(rig.home, plan)[0] is None
    assert mandate.covering(rig.home, plan, now=time.time() + HOUR + 60)[0] == made["id"]


def test_twenty_an_hour_is_the_ceiling(rig):
    made = rig.make(per_hour=20)
    for n in range(20):
        assert rig.write(dns({**ADD, "name": f"h{n}"}))[1]["ok"] is True
    assert rig.used(made["id"]) == 20
    assert rig.write(dns({**ADD, "name": "h20"}))[0]["action"] == "approve"


def test_two_mandates_the_second_takes_what_the_first_cannot(rig):
    first, second = rig.make(per_hour=1), rig.make(per_hour=1)
    rig.write(dns(ADD))
    rig.write(dns({**ADD, "name": "b"}))
    assert {rig.used(first["id"]), rig.used(second["id"])} == {1}
    rig.nobody = "this is a cron job"
    assert rig.write(dns({**ADD, "name": "c"}))[0]["action"] == "block"


def test_a_failed_or_uncertain_send_still_counts(rig):
    made = rig.make()
    original = rig.cloud.__call__

    def fails(op, **fields):
        if fields.get("method") == "POST":
            raise cfa.Uncertain("Cloudflare did not answer within 90s")
        return original(op, **fields)
    rig.monkeypatch.setattr(cfa, "bridge", fails)
    _, result = rig.write(dns(ADD))
    assert result["ok"] is False and result["error"].startswith("UNCERTAIN: ")
    assert rig.used(made["id"]) == 1


def test_a_preview_never_counts_and_needs_no_mandate(rig):
    rig.nobody = "this is a cron job"
    directive, result = rig.write({**dns(ADD), "preview": True})
    assert directive is None and result["preview"] is True and rig.cloud.sends() == []
    rig.nobody = None
    made = rig.make()
    rig.write({**dns(ADD), "preview": True})
    assert rig.used(made["id"]) == 0


NEVER_COVERED = [
    pytest.param(dns(ADD, {"op": "delete", "id": WWW}), id="dns-delete-in-a-batch"),
    pytest.param(dns({"op": "add", "type": "CNAME", "name": "app2", "content": TUNNEL_HOST, "proxied": True}),
                 id="tunnel-cname-added"),
    pytest.param(dns({"op": "update", "id": PRIVATE, "ttl": 300}), id="tunnel-cname-kept-and-changed"),
    pytest.param(dns({"op": "add", "type": "CNAME", "name": "app3", "content": TUNNEL_HOST.upper() + ".",
                      "proxied": True}), id="tunnel-cname-in-capitals"),
    pytest.param(dns({"op": "add", "type": "MX", "name": "@", "content": "mx2.example.net", "priority": 20}),
                 id="dns-mx-added"),
    pytest.param(dns({"op": "update", "id": MAIL, "priority": 30}), id="dns-mx-updated"),
    pytest.param(dns({"op": "add", "type": "NS", "name": "sub", "content": "ns1.example.net"}), id="dns-ns-added"),
    pytest.param(dns({"op": "add", "type": "TXT", "name": "@", "content": "v=spf1 -all"}), id="dns-txt-added"),
    pytest.param(dns({"op": "add", "type": "CNAME", "name": "_acme-challenge", "content": "validate.example.net",
                      "proxied": True}), id="dns-challenge-cname"),
    pytest.param(dns({"op": "add", "type": "A", "name": "direct", "content": "192.0.2.7"}), id="dns-unproxied-a-added"),
    pytest.param(dns({"op": "add", "type": "A", "name": "direct", "content": "192.0.2.7", "proxied": False}),
                 id="dns-a-added-with-proxied-false"),
    pytest.param(dns({"op": "update", "id": WWW, "proxied": False}), id="dns-proxied-turned-off"),
    pytest.param(dns({"op": "update", "id": DIRECT, "content": "192.0.2.77"}), id="dns-unproxied-stays-unproxied"),
    pytest.param(dns(ADD, {"op": "add", "type": "TXT", "name": "t", "content": "x"}), id="one-txt-in-a-batch"),
    pytest.param(setting(("ssl", "flexible")), id="ssl-weaker"),
    pytest.param(setting(("development_mode", "on"), ("ssl", "flexible")), id="weaker-in-a-batch"),
    pytest.param(setting(("email_obfuscation", "off")), id="email-obfuscation-off"),
    pytest.param(setting(("automatic_https_rewrites", "off")), id="https-rewrites-off"),
    pytest.param(setting(("development_mode", "on"), ("tls_1_3", "off")), id="tls-1-3-off-in-a-batch"),
    pytest.param(purge(everything=True), id="purge-everything"),
    pytest.param({"action": "email_rule", "zone": "example.com", "op": "add", "to": "sales", "drop": True},
                 id="email-rule"),
    pytest.param({"action": "worker_rollback", "script": "api"}, id="worker-rollback"),
    pytest.param({"action": "storage_create", "kind": "r2", "name": "assets"}, id="storage"),
    pytest.param(dns(ADD, zone="example.org"), id="another-zone"),
    pytest.param(dns(ADD, zone="foreign.net", account="other"), id="another-account"),
]


@pytest.mark.parametrize("args", NEVER_COVERED)
def test_what_a_mandate_never_covers_asks_on_its_card_as_before(rig, args):
    made = rig.make(zones=["example.com"])
    directive = rig.gate(tool_name="cloudflare", args=args, tool_call_id="c1")
    assert directive["action"] == "approve" and directive["message"].startswith("Cloudflare · ")
    assert [recorded for _, _, recorded in cfa._approved.values()] == [None]
    rig.nobody = "this is a cron job"
    blocked = rig.gate(tool_name="cloudflare", args=args, tool_call_id="c2")
    assert blocked["action"] == "block" and "cron job" in blocked["message"]
    assert not cfa.covered_by_mandate(args, "c2")
    result = json.loads(rig.handlers["cloudflare"](args))
    assert result["ok"] is False and "cron job" in result["error"]
    assert rig.cloud.sends() == [] and rig.used(made["id"]) == 0


@pytest.mark.parametrize("args, why", [
    (dns(ADD, {"op": "delete", "id": WWW}), "always asks on a card"),
    (dns({"op": "update", "id": PRIVATE, "ttl": 300}), "always asks on a card"),
    (setting(("ssl", "flexible")), "always asks on a card"),
    (purge(everything=True), "always asks on a card"),
    (dns(ADD, zone="example.org"), "example.org is outside the mandate"),
    ({"action": "email_rule", "zone": "example.com", "op": "add", "to": "sales", "drop": True},
     "email_rule always asks on a card"),
    (dns({"op": "add", "type": "MX", "name": "@", "content": "mx2.example.net", "priority": 20}),
     "a MX record always asks on a card"),
    (dns({"op": "add", "type": "TXT", "name": "@", "content": "v=spf1 -all"}), "a TXT record always asks"),
    (dns({"op": "add", "type": "NS", "name": "sub", "content": "ns1.example.net"}), "a NS record always asks"),
    (dns({"op": "add", "type": "CNAME", "name": "_acme-challenge", "content": "v.example.net", "proxied": True}),
     "a name starting with _"),
    (dns({"op": "add", "type": "A", "name": "direct", "content": "192.0.2.7"}), "is not proxied"),
    (dns({"op": "update", "id": WWW, "proxied": False}), "is not proxied"),
    (dns({"op": "update", "id": DIRECT, "content": "192.0.2.77"}), "is not proxied"),
    (setting(("email_obfuscation", "off")), "turning email_obfuscation off always asks"),
    (setting(("automatic_https_rewrites", "off")), "turning automatic_https_rewrites off always asks"),
    (setting(("tls_1_3", "off")), "turning tls_1_3 off always asks"),
])
def test_why_a_mandate_does_not_cover_is_named(rig, args, why):
    rig.make(zones=["example.com"])
    plan = cfa.write_plan(args)
    mid, misses = mandate.covering(rig.home, plan)
    assert mid is None and why in misses[0]


def test_proxied_a_aaaa_and_cname_records_stay_covered(rig):
    made = rig.make(classes=["dns"])
    for args in (dns(UPDATE), dns({"op": "update", "id": DIRECT, "proxied": True}), dns(ADD),
                 dns({"op": "add", "type": "CNAME", "name": "blog", "content": "sites.example.net", "proxied": True}),
                 dns({"op": "add", "type": "AAAA", "name": "v6", "content": "2001:db8::1", "proxied": True})):
        assert mandate.covering(rig.home, cfa.write_plan(args)) == (made["id"], [])


def test_a_setting_that_turns_a_protection_off_is_never_covered(rig):
    rig.make()
    m = mandate.active(rig.home)[0]
    plan = cfa.write_plan(setting(("ssl", "strict")))
    assert mandate.fits(m, plan) is None
    assert {"ssl", "always_use_https", "automatic_https_rewrites", "tls_1_3", "security_level",
            "email_obfuscation"} == set(mandate.PROTECTIVE_OFF)
    for name, values in mandate.PROTECTIVE_OFF.items():
        for value in values:
            tampered = json.loads(json.dumps(plan))
            tampered["steps"][0].update(path=f"/zones/{ZONE}/settings/{name}", body={"value": value})
            assert f"turning {name} {value} always asks" in mandate.fits(m, tampered)
        tampered = json.loads(json.dumps(plan))
        tampered["steps"][0].update(path=f"/zones/{ZONE}/settings/{name}", body={"value": "on"})
        assert mandate.fits(m, tampered) is None


def test_each_change_of_a_call_counts_and_the_fifth_call_of_five_asks(rig):
    made = rig.make(per_hour=20)

    def five(n):
        return dns(*[{**ADD, "name": f"h{n}-{i}"} for i in range(5)])
    for n in range(4):
        rig.nobody = "this is a cron job" if n % 2 else None
        directive, result = rig.write(five(n))
        assert directive is None and result["ok"] is True
        assert rig.used(made["id"]) == 5 * (n + 1)
    plan = cfa.write_plan(five(4))
    mid, misses = mandate.covering(rig.home, plan)
    assert mid is None and "20 changes in the last hour and this makes 5" in misses[0]
    directive, result = rig.write(five(4))
    assert directive["action"] == "block" and "cron job" in directive["message"] and result is None
    assert rig.used(made["id"]) == 20 and len(rig.cloud.sends()) == 4
    rig.nobody = None
    other = rig.make(per_hour=20)   # a mandate with an hour of its own covers it
    assert mandate.covering(rig.home, plan)[0] == other["id"]


def test_the_last_slots_of_an_hour_are_not_split_across_a_call(rig):
    made = rig.make(per_hour=7)
    assert rig.write(dns(*[{**ADD, "name": f"a{i}"} for i in range(5)]))[1]["ok"] is True
    rig.nobody = "this is a cron job"
    directive, _ = rig.write(dns(*[{**ADD, "name": f"b{i}"} for i in range(3)]))
    assert directive["action"] == "block" and rig.used(made["id"]) == 5
    assert rig.write(dns(*[{**ADD, "name": f"c{i}"} for i in range(2)]))[1]["ok"] is True
    assert rig.used(made["id"]) == 7


def test_a_call_with_more_changes_than_the_hour_allows_is_never_covered(rig):
    made = rig.make(per_hour=2)
    args = purge(hosts=["a.example.com", "b.example.com", "c.example.com"])
    mid, misses = mandate.covering(rig.home, cfa.write_plan(args))
    assert mid is None and "it makes 3 changes; the mandate allows 2 an hour" in misses[0]
    assert rig.write(args)[0]["action"] == "approve"   # a card, as before
    rig.nobody = "this is a cron job"
    assert rig.write(args)[0]["action"] == "block"
    assert rig.used(made["id"]) == 0


def test_the_weight_is_what_the_call_sends(rig):
    weight = lambda args: mandate.weight(cfa.write_plan(args))   # noqa: E731
    assert weight(dns(ADD)) == 1 and weight(dns(ADD, UPDATE)) == 2
    assert weight(setting(("development_mode", "on"), ("browser_cache_ttl", "3600"))) == 2
    assert weight(purge(urls=["https://www.example.com/a"])) == 1
    assert weight(purge(hosts=["a.example.com", "b.example.com"])) == 2
    assert weight(purge(prefixes=["www.example.com/a", "www.example.com/b", "www.example.com/c"])) == 3


def test_the_class_is_judged_from_what_would_be_sent(rig):
    rig.make()
    m = mandate.active(rig.home)[0]
    plan = cfa.write_plan(dns(ADD))
    assert mandate.fits(m, plan) is None
    for tamper, why in [(lambda p: p["steps"][0]["body"].update(deletes=[{"id": WWW}]), "delete"),
                        (lambda p: p["steps"][0].update(path="/zones/other/dns_records/batch"), "outside the dns class"),
                        (lambda p: p["steps"].append(dict(p["steps"][0])), None),
                        (lambda p: p.update(steps=[]), "sends nothing"),
                        (lambda p: p.update(zone_id=None), "outside the mandate"),
                        (lambda p: p.update(once=None), "always asks"),
                        (lambda p: p.update(effect=None), "always asks")]:
        copy = json.loads(json.dumps(plan))
        tamper(copy)
        verdict = mandate.fits(m, copy)
        assert (verdict is None) if why is None else (why in verdict)
    purge_plan = cfa.write_plan(purge(hosts=["static.example.com"]))
    purge_plan["steps"][0]["body"] = {"purge_everything": True}
    assert "purging everything" in mandate.fits(m, purge_plan)


def test_a_mandate_asks_nothing_of_the_keychain_until_one_was_made(rig, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("the Keychain was asked")
    monkeypatch.setattr(mandate.mandate_store, "call_secret", forbidden)
    plan = cfa.write_plan(dns(ADD))
    assert mandate.covering(rig.home, plan) == (None, []) and mandate.active(rig.home) == []
    directive, _ = rig.write(dns(ADD))
    assert directive["action"] == "approve"


def test_without_a_readable_key_nothing_is_covered(rig):
    rig.make()
    rig.keyfile.unlink()
    assert rig.write(dns(ADD))[0]["action"] == "approve"
    rig.keyfile.write_text("cd" * 32)   # a replaced key puts nothing in force either
    assert rig.write(dns({**ADD, "name": "b"}))[0]["action"] == "approve"


def test_a_ledger_that_is_gone_reads_as_used_up(rig):
    made = rig.make()
    assert rig.write(dns(ADD))[1]["ok"] is True
    (rig.home / "cloudflare-access" / "uses.jsonl").unlink()
    rig.nobody = "this is a cron job"
    directive, _ = rig.write(dns({**ADD, "name": "b"}))
    assert directive["action"] == "block"
    plan = cfa.write_plan(dns({**ADD, "name": "b"}))
    assert "cannot be read" in mandate.covering(rig.home, plan)[1][0]
    assert made["id"]


def test_a_mandate_that_ended_covers_nothing(rig):
    made = rig.make()
    plan = cfa.write_plan(dns(ADD))
    assert mandate.covering(rig.home, plan)[0] == made["id"]
    assert mandate.covering(rig.home, plan, now=time.time() + 3 * mandate.DAY + 60) == (None, [])


# --- between the hook and the write ---------------------------------------------------------------

def test_a_mandate_revoked_between_the_hook_and_the_write_sends_nothing(rig):
    made = rig.make()
    rig.nobody = "this is a cron job"
    args = dns(ADD)
    assert rig.gate(tool_name="cloudflare", args=args, tool_call_id="call-7") is None
    rig.monkeypatch.setattr(plugin, "_call_id", lambda: "call-7")
    mandate.revoke(rig.home, made["id"])
    result = json.loads(rig.handlers["cloudflare"](args))
    assert result["ok"] is False and "no longer fits the zone mandate" in result["error"]
    assert "no longer in force" in result["error"] and "it will ask on a card" in result["error"]
    assert rig.cloud.sends() == []


def test_a_plan_that_changed_between_the_hook_and_the_write_is_refused_by_its_digest(rig):
    made = rig.make()
    args = dns(UPDATE)
    assert rig.gate(tool_name="cloudflare", args=args, tool_call_id="call-8") is None
    rig.monkeypatch.setattr(plugin, "_call_id", lambda: "call-8")
    rig.cloud.records[WWW]["content"] = "192.0.2.77"
    result = json.loads(rig.handlers["cloudflare"](args))
    assert result["ok"] is False and "changed before the write ran" in result["error"]
    assert rig.cloud.sends() == [] and rig.used(made["id"]) == 0


def test_a_record_that_became_a_tunnel_cname_between_the_hook_and_the_write_is_refused_by_the_fit(rig):
    made = rig.make()
    rig.cloud.records[WWW].update(type="CNAME", content="x.example.net")
    args = dns({"op": "update", "id": WWW, "ttl": 300})
    assert rig.gate(tool_name="cloudflare", args=args, tool_call_id="call-5") is None
    rig.monkeypatch.setattr(plugin, "_call_id", lambda: "call-5")
    before = cfa.digest(cfa.write_plan(args))
    rig.cloud.records[WWW]["content"] = TUNNEL_HOST   # a TTL-only update shows no content: the digest is the same
    assert cfa.digest(cfa.write_plan(args)) == before
    result = json.loads(rig.handlers["cloudflare"](args))
    assert result["ok"] is False and "tunnel" in result["error"] and "no longer fits the zone mandate" in result["error"]
    assert "changed before the write ran" not in result["error"]
    assert rig.cloud.sends() == [] and rig.used(made["id"]) == 0


def test_a_write_the_hook_never_saw_is_refused_even_with_a_mandate(rig):
    rig.make()
    rig.nobody = "this is a cron job"
    result = json.loads(rig.handlers["cloudflare"](dns(ADD)))
    assert result["ok"] is False and "cron job" in result["error"] and rig.cloud.sends() == []
    rig.nobody = None
    result = json.loads(rig.handlers["cloudflare"](dns(ADD)))
    assert "did not pass its approval card" in result["error"] and rig.cloud.sends() == []


def test_a_card_record_is_no_mandate_record(rig):
    rig.gate(tool_name="cloudflare", args=dns(ADD), tool_call_id="call-3")   # no mandate: a card
    rig.monkeypatch.setattr(plugin, "_call_id", lambda: "call-3")
    rig.nobody = "this is a cron job"
    result = json.loads(rig.handlers["cloudflare"](dns(ADD)))
    assert result["ok"] is False and "cron job" in result["error"] and rig.cloud.sends() == []


def test_the_engine_refuses_a_covered_record_without_a_home(rig):
    rig.make()
    cfa.approval_request(dns(ADD), call_id="k", can_write=True, home=rig.home)
    result = cfa.execute(dns(ADD), call_id="k", can_write=True)
    assert result["ok"] is False and "profile home is unknown" in result["error"] and rig.cloud.sends() == []


def test_an_unattended_write_with_no_mandate_in_force_reads_nothing(rig):
    rig.nobody = "this is a cron job"
    before = len(rig.cloud.requests)
    directive = rig.gate(tool_name="cloudflare", args=dns(ADD), tool_call_id="c")
    assert directive["action"] == "block" and "Nothing was sent" in directive["message"]
    assert len(rig.cloud.requests) == before and cfa._approved == {}


# --- ways around the tool -------------------------------------------------------------------------

@pytest.mark.parametrize("tool, args", [
    ("read_file", {"path": "~/.hermes/profiles/assistant/cloudflare-access/head.json"}),
    ("read_file", {"path": "/h/profiles/assistant/cloudflare-access//uses.jsonl"}),
    ("search_files", {"path": "/h/profiles/assistant/cloudflare-access/mandates", "pattern": "id"}),
    ("patch", {"path": "/h/profiles/assistant/cloudflare-access/mandates.jsonl", "old_string": "a"}),
    ("write_file", {"path": "x", "content": "secret get CLOUDFLARE_MANDATE_KEY_ASSISTANT"}),
    ("terminal", {"command": "cat ~/.hermes/profiles/assistant/cloudflare-access/uses.jsonl"}),
    ("terminal", {"command": "security find-generic-password -s CLOUDFLARE_MANDATE_KEY_ASSISTANT"}),
    ("terminal", {"command": "ls /h/profiles/assistant/CLOUDFLARE-ACCESS/Head.json"}),
])
def test_the_mandate_state_and_key_are_off_limits_to_file_and_terminal_calls(tool, args):
    assert cfa.bypass(tool, args) == cfa.BYPASS_MESSAGE


def test_a_link_to_the_mandate_state_does_not_hide_it(tmp_path):
    state = tmp_path / "home" / "cloudflare-access"
    state.mkdir(parents=True)
    (state / "head.json").write_text("{}")
    (tmp_path / "short").symlink_to(state)
    assert cfa.bypass("read_file", {"path": str(tmp_path / "short" / "head.json")}) == cfa.BYPASS_MESSAGE


def test_the_plugin_source_and_its_tests_stay_readable():
    assert cfa.bypass("read_file", {"path": "/repo/hermes/plugins/cloudflare-access/mandate.py"}) is None
    assert cfa.bypass("read_file", {"path": "/repo/hermes/plugins/cloudflare-access/tests/test_mandate.py"}) is None
    assert cfa.bypass("read_file", {"path": "/repo/hermes/docs/decisions/cloudflare-mandates.md"}) is None
