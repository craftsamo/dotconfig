import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("cloudflare_access_writes_test", ROOT / "cfa.py")
cfa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cfa)
bridge_spec = importlib.util.spec_from_file_location("cloudflare_access_bridge_writes", ROOT / "bridge.py")
bridge_module = importlib.util.module_from_spec(bridge_spec)
bridge_spec.loader.exec_module(bridge_module)

ACCOUNT = "0123456789abcdef0123456789abcdef"
ZONE = "1" * 32
WWW = "2" * 32
MAIL = "3" * 32
SPF = "4" * 32
ZONE_OBJ = {"id": ZONE, "name": "example.com", "account": {"id": ACCOUNT, "name": "Work"}}


def envelope(result):
    return {"success": True, "errors": [], "messages": [], "result": result}


class Bridge:
    """Cloudflare as the bridge answers: a zone, its records by id, and the batch endpoint; records every
    request."""

    def __init__(self):
        self.requests = []
        self.records = {
            WWW: {"id": WWW, "type": "A", "name": "www.example.com", "content": "192.0.2.1", "proxied": True, "ttl": 1},
            MAIL: {"id": MAIL, "type": "MX", "name": "example.com", "content": "mx.example.net", "priority": 10,
                   "ttl": 3600, "proxied": False},
            SPF: {"id": SPF, "type": "TXT", "name": "example.com", "content": "v=spf1 include:mail.example.net ~all",
                  "ttl": 1, "proxied": False},
        }
        self.write_reply = None
        self.fingerprint = "f" * 12
        self.answers = {}   # any other GET: path -> Cloudflare's JSON

    def head(self, fields):
        return {"account": fields.get("account") or "work", "item": "CLOUDFLARE_WORK", "account_id": ACCOUNT,
                "fingerprint": self.fingerprint, "token_kind": "user"}

    def record(self, path):
        if path in self.answers:
            return {"ok": True, "status": 200, "data": self.answers[path]}
        rid = path.rsplit("/", 1)[1]
        if rid in self.records:
            return {"ok": True, "status": 200, "data": envelope(dict(self.records[rid]))}
        return {"ok": False, "kind": "not_found", "status": 404, "error": "81044: Record does not exist."}

    def __call__(self, op, **fields):
        self.requests.append({"op": op, **fields})
        if op == "reads":
            results = [self.record(r["path"]) for r in fields["requests"]]
            return {**self.head(fields), "ok": True, "requests": len(results), "results": results}
        path, method = fields.get("path"), fields.get("method")
        if method == "GET" and path == "/zones":
            return {**self.head(fields), "ok": True, "requests": 1, "data": envelope([ZONE_OBJ])}
        if method == "GET" and path == f"/zones/{ZONE}":
            return {**self.head(fields), "ok": True, "requests": 1, "data": envelope(ZONE_OBJ)}
        if method == "GET" and path in self.answers:
            return {**self.head(fields), "ok": True, "requests": 1, "data": self.answers[path]}
        if method == "GET":
            return {**self.head(fields), "ok": False, "requests": 1, "kind": "not_found", "status": 404,
                    "error": "not found"}
        if method in ("POST", "PUT", "PATCH", "DELETE"):
            if self.write_reply is not None:
                return {**self.head(fields), "requests": 1, **self.write_reply}
            if not path.endswith("/dns_records/batch"):
                return {**self.head(fields), "ok": True, "requests": 1, "status": 200,
                        "data": envelope({"id": "new", **(fields.get("body") or {})})}
            body = fields.get("body") or {}
            result = {"posts": [{"id": "9" * 32, **post} for post in body.get("posts", [])],
                      "patches": [{**self.records[p["id"]], **p} for p in body.get("patches", [])],
                      "deletes": [{"id": d["id"]} for d in body.get("deletes", [])]}
            return {**self.head(fields), "ok": True, "requests": 1, "status": 200, "data": envelope(result)}
        raise AssertionError(f"unexpected {op} {method} {path}")

    def sends(self):
        return [r for r in self.requests if r["op"] == "call" and r["method"] != "GET"]


@pytest.fixture
def fake(monkeypatch, tmp_path):
    monkeypatch.setattr(cfa, "STORE", tmp_path / "store")
    bridge = Bridge()
    monkeypatch.setattr(cfa, "bridge", bridge)
    cfa._approved.clear()
    return bridge


def change(*changes, **extra):
    return {"action": "dns_change", "zone": "example.com", "changes": list(changes), **extra}


def approve_and_run(args, call_id="call-1"):
    card, key = cfa.approval_request(args, call_id=call_id, can_write=True)
    return card, key, cfa.execute(args, call_id=call_id, can_write=True, allowed=cfa.ACTIONS)


def test_the_batch_route_is_one_the_bridge_allows():
    assert any(m == "POST" and p.fullmatch(f"/zones/{ZONE}/dns_records/batch") for m, p in bridge_module._ROUTES)


def test_adds_and_updates_go_out_as_one_batch_after_their_card(fake):
    args = change({"op": "add", "type": "cname", "name": "blog", "content": "Sites.Example.NET.", "proxied": True},
                  {"op": "update", "id": WWW, "content": "192.0.2.10", "ttl": 300},
                  {"op": "add", "type": "TXT", "name": "_dmarc", "content": "v=DMARC1; p=none",
                   "comment": "added for the report"})
    card, key, result = approve_and_run(args)
    assert card.startswith("Cloudflare · Change DNS records\n⚠️ Changes where the domain points")
    assert "Account: work\nZone: example.com\n\n--- Change ---\n" in card
    assert "+ CNAME blog → sites.example.net, proxied, TTL auto" in card
    assert "~ A www: 192.0.2.1 → 192.0.2.10; TTL auto → 300s" in card
    assert '+ TXT _dmarc → "v=DMARC1; p=none", TTL auto' in card
    assert "All of them apply at once, or none does." in card and "comment: added for the report" in card
    assert key.startswith("cloudflare-access:dns_change:")
    [sent] = fake.sends()
    assert sent["path"] == f"/zones/{ZONE}/dns_records/batch" and sent["expect"] == "f" * 12
    assert sent["body"] == {
        "patches": [{"id": WWW, "content": "192.0.2.10", "ttl": 300}],
        "posts": [{"type": "CNAME", "name": "blog.example.com", "content": "sites.example.net", "ttl": 1,
                   "proxied": True},
                  {"type": "TXT", "name": "_dmarc.example.com", "content": "v=DMARC1; p=none", "ttl": 1,
                   "proxied": False, "comment": "added for the report"}]}
    assert result["ok"] is True and [r["name"] for r in result["result"]["posts"]] == ["blog.example.com",
                                                                                     "_dmarc.example.com"]
    # the approval is spent
    assert "did not pass its approval card" in cfa.execute(args, call_id="call-1", can_write=True)["error"]


def test_a_delete_is_marked_final_and_never_covered_by_always(fake):
    args = change({"op": "delete", "id": MAIL}, {"op": "add", "type": "MX", "name": "@", "content": "mx2.example.net",
                                                 "priority": 20})
    card, key, result = approve_and_run(args)
    assert "🚨 A deleted record is gone: a site or its mail can stop" in card
    assert "- MX @ mx.example.net (priority 10)" in card and "+ MX @ → mx2.example.net (priority 20), TTL auto" in card
    keys = {cfa.approval_request(args, call_id=str(n), can_write=True)[1] for n in range(3)}
    assert len(keys) == 3
    plain = change({"op": "update", "id": WWW, "proxied": False})
    assert len({cfa.approval_request(plain, call_id=str(n), can_write=True)[1] for n in range(3)}) == 1
    assert fake.sends()[0]["body"]["deletes"] == [{"id": MAIL}]


def test_a_txt_record_on_the_card_is_quoted_cut_and_spelled_out(fake):
    args = change({"op": "update", "id": SPF, "content": "v=spf1 include:new.example.net\u202e ~all " + "x" * 80})
    with pytest.raises(cfa.CloudflareError, match="one line"):
        cfa.approval_request(change({"op": "update", "id": SPF, "content": "a\nb"}), can_write=True)
    card, _ = cfa.approval_request(args, call_id="c", can_write=True)
    assert "⟨U+202E⟩" in card and '~ TXT @: "v=spf1 include:mail.example.net ~all" → "v=spf1' in card


@pytest.mark.parametrize("bad, message", [
    ({"op": "add", "type": "SRV", "name": "_sip._tcp", "content": "x"}, "type must be one of A, AAAA"),
    ({"op": "add", "type": "A", "name": "www", "content": "999.1.1.1"}, "not an IPv4 address"),
    ({"op": "add", "type": "AAAA", "name": "www", "content": "192.0.2.1"}, "not an IPv6 address"),
    ({"op": "add", "type": "CNAME", "name": "www", "content": "localhost"}, "points to another host name"),
    ({"op": "add", "type": "MX", "name": "@", "content": "mx.example.net"}, "needs priority"),
    ({"op": "add", "type": "TXT", "name": "@", "content": "x", "proxied": True}, "cannot be proxied"),
    ({"op": "add", "type": "A", "name": "www", "content": "192.0.2.1", "ttl": 30}, "ttl must be 1"),
    ({"op": "add", "type": "A", "name": "www", "content": "192.0.2.1", "priority": 1}, "priority is for MX"),
    ({"op": "add", "type": "A", "name": "www", "content": "192.0.2.1", "id": WWW}, "does not take id"),
    ({"op": "update", "id": WWW, "content": "192.0.2.1"}, "changes nothing"),
    ({"op": "update", "id": WWW, "type": "CNAME", "content": "x.example.net"}, "keeps the record's type"),
    ({"op": "update", "id": "5" * 32, "content": "192.0.2.9"}, "not found"),
    ({"op": "delete", "id": "nope"}, "Cloudflare id"),
    ({"op": "rename", "id": WWW}, "needs op"),
])
def test_a_change_that_would_fail_is_refused_before_any_card(fake, bad, message):
    with pytest.raises(cfa.CloudflareError, match=message):
        cfa.approval_request(change(bad), can_write=True)
    assert fake.sends() == [] and cfa._approved == {}


def test_a_record_changed_twice_or_too_many_changes_are_refused(fake):
    with pytest.raises(cfa.CloudflareError, match="only once"):
        cfa.approval_request(change({"op": "update", "id": WWW, "ttl": 300}, {"op": "delete", "id": WWW}),
                             can_write=True)
    many = [{"op": "add", "type": "A", "name": f"h{n}", "content": "192.0.2.1"} for n in range(cfa.CHANGES_MAX + 1)]
    with pytest.raises(cfa.CloudflareError, match="1 to 20 changes"):
        cfa.approval_request(change(*many), can_write=True)
    with pytest.raises(cfa.CloudflareError, match="does not take records"):
        cfa.approval_request({**change({"op": "delete", "id": WWW}), "records": []}, can_write=True)
    assert fake.requests == []


def test_a_card_that_cannot_show_every_change_is_refused(fake):
    many = [{"op": "add", "type": "A", "name": f"host-number-{n}", "content": f"192.0.2.{n}"} for n in range(12)]
    with pytest.raises(cfa.CloudflareError, match="send fewer changes"):
        cfa.approval_request(change(*many), can_write=True)


def test_a_record_changed_after_the_card_sends_nothing(fake):
    args = change({"op": "update", "id": WWW, "content": "192.0.2.10"})
    cfa.approval_request(args, call_id="call-1", can_write=True)
    fake.records[WWW]["content"] = "192.0.2.77"
    result = cfa.execute(args, call_id="call-1", can_write=True)
    assert result["ok"] is False and "changed before the write ran" in result["error"] and fake.sends() == []


def test_a_token_stored_anew_after_the_card_sends_nothing(fake):
    args = change({"op": "update", "id": WWW, "content": "192.0.2.10"})
    cfa.approval_request(args, call_id="call-1", can_write=True)
    fake.fingerprint = "e" * 12
    assert "changed before the write ran" in cfa.execute(args, call_id="call-1", can_write=True)["error"]
    assert fake.sends() == []


@pytest.mark.parametrize("reply, start", [
    ({"ok": False, "kind": "invalid", "status": 400, "error": "81058: An identical record already exists."},
     "not done: "),
    ({"ok": False, "kind": "forbidden", "status": 403, "error": "10000: Authentication error"}, "not done: "),
    ({"ok": False, "kind": "api", "status": 502, "error": "bad gateway"}, "UNCERTAIN: "),
    ({"ok": False, "kind": "network", "error": "the connection to Cloudflare broke off"}, "UNCERTAIN: "),
    ({"ok": False, "kind": "uncertain", "status": 200, "error": "odd"}, "UNCERTAIN: "),
])
def test_outcomes_are_never_guessed(fake, reply, start):
    fake.write_reply = reply
    _, _, result = approve_and_run(change({"op": "update", "id": WWW, "ttl": 300}))
    assert result["ok"] is False and result["error"].startswith(start)
    assert len(fake.sends()) == 1   # never retried
    if start == "not done: ":
        assert "nothing was changed" in result["error"]
    else:
        assert result["uncertain"] is True and "never repeat the write" in result["error"]


def test_no_answer_from_the_bridge_is_uncertain(fake, monkeypatch):
    args = change({"op": "update", "id": WWW, "ttl": 300})
    cfa.approval_request(args, call_id="call-1", can_write=True)
    original = fake.__call__

    def silent(op, **fields):
        if fields.get("method") == "POST":
            raise cfa.Uncertain("Cloudflare did not answer within 90s")
        return original(op, **fields)
    monkeypatch.setattr(cfa, "bridge", silent)
    result = cfa.execute(args, call_id="call-1", can_write=True)
    assert result["error"].startswith("UNCERTAIN: ")


def test_a_preview_shows_the_card_and_sends_nothing(fake):
    args = change({"op": "delete", "id": WWW}, preview=True)
    assert cfa.approval_request(args, can_write=True) is None
    result = cfa.execute(args, can_write=True)
    assert result["preview"] is True and "- A www 192.0.2.1" in result["card"] and fake.sends() == []
    with pytest.raises(cfa.CloudflareError, match="preview must be true or false"):
        cfa.execute({**args, "preview": "yes"}, can_write=True)


def test_a_read_profile_cannot_change_or_preview(fake):
    for args in (change({"op": "delete", "id": WWW}), change({"op": "delete", "id": WWW}, preview=True)):
        with pytest.raises(cfa.CloudflareError, match="can read Cloudflare but not change"):
            cfa.execute(args, can_write=False)
        with pytest.raises(cfa.CloudflareError, match="can read Cloudflare but not change"):
            cfa.approval_request({**args, "preview": None}, can_write=False)
    assert fake.sends() == []


def test_a_comment_change_shows_the_old_and_the_new_words(fake):
    fake.records[WWW]["comment"] = "old box\u200b"
    card, _ = cfa.approval_request(change({"op": "update", "id": WWW, "comment": "new box"}), call_id="a",
                                   can_write=True)
    assert "~ A www: comment" in card and "comment: old box⟨U+200B⟩ → new box" in card
    card, _ = cfa.approval_request(change({"op": "update", "id": WWW, "comment": ""}), call_id="b", can_write=True)
    assert "→ (removed)" in card


def test_state_that_cannot_be_written_never_hides_the_outcome(fake, monkeypatch):
    plan = cfa.write_plan(change({"op": "update", "id": WWW, "ttl": 300}))

    def broken(reply):
        raise cfa.CloudflareError("another cloudflare call is still updating the tool's state")
    monkeypatch.setattr(cfa, "_record", broken)
    result = cfa.run(plan)
    assert result["ok"] is True and "state could not be updated" in result["notes"][0]
    fake.write_reply = {"ok": False, "kind": "api", "status": 502, "error": "bad gateway"}
    result = cfa.run(plan)
    assert result["error"].startswith("UNCERTAIN: ") and result["notes"]


def test_an_approval_expires(fake):
    args = change({"op": "update", "id": WWW, "ttl": 300})
    cfa.approval_request(args, call_id="call-1", can_write=True)
    [key] = cfa._approved
    at, value = cfa._approved[key]
    cfa._approved[key] = (at - cfa.APPROVAL_TTL - 1, value)
    assert "did not pass its approval card" in cfa.execute(args, call_id="call-1", can_write=True)["error"]
    assert fake.sends() == []


def test_discord_s_shorter_card_drops_details_first_and_refuses_what_it_cannot_show(fake, monkeypatch):
    monkeypatch.setattr(cfa.cards, "platform", lambda: "discord")
    args = change({"op": "update", "id": WWW, "ttl": 300}, {"op": "delete", "id": SPF})
    card, _ = cfa.approval_request(args, call_id="d", can_write=True)
    assert cfa.cards.units(card) <= cfa.cards.COMPACT_BUDGET
    assert "~ A www: TTL auto → 300s" in card and "- TXT @" in card
    many = [{"op": "add", "type": "A", "name": f"host-{n}", "content": f"192.0.2.{n}"} for n in range(5)]
    with pytest.raises(cfa.CloudflareError, match="send fewer changes"):
        cfa.approval_request(change(*many), call_id="m", can_write=True)
    monkeypatch.setattr(cfa.cards, "platform", lambda: "telegram")
    assert cfa.approval_request(change(*many), call_id="t", can_write=True)


def purge(**extra):
    return {"action": "cache_purge", "zone": "example.com", **extra}


def test_the_purge_route_is_one_the_bridge_allows():
    assert any(m == "POST" and p.fullmatch(f"/zones/{ZONE}/purge_cache") for m, p in bridge_module._ROUTES)


def test_urls_inside_the_zone_are_purged_after_their_card(fake):
    fake.write_reply = {"ok": True, "status": 200, "data": envelope({"id": ZONE})}
    args = purge(urls=["https://WWW.Example.com/index.html", "http://example.com"])
    card, key, result = approve_and_run(args)
    assert card.startswith("Cloudflare · Purge the cache\n⚠️ Visitors get fresh copies")
    assert "2 URLs" in card and "- https://www.example.com/index.html" in card and "- http://example.com/" in card
    [sent] = fake.sends()
    assert sent["path"] == f"/zones/{ZONE}/purge_cache"
    assert sent["body"] == {"files": ["https://www.example.com/index.html", "http://example.com/"]}
    assert result["ok"] is True and key.startswith("cloudflare-access:cache_purge:")


def test_hosts_and_prefixes_purge_everything_under_them(fake):
    card, _ = cfa.approval_request(purge(hosts=["static.example.com"]), call_id="h", can_write=True)
    assert "1 host name, every file under each" in card
    card, _ = cfa.approval_request(purge(prefixes=["www.example.com/blog/"]), call_id="p", can_write=True)
    assert "- www.example.com/blog/" in card


def test_purging_everything_asks_every_time(fake):
    args = purge(everything=True)
    card, key = cfa.approval_request(args, call_id="e", can_write=True)
    assert "Everything cached for example.com and its subdomains" in card and "burst of traffic" in card
    assert key != cfa.approval_request(args, call_id="e2", can_write=True)[1]
    cfa.execute(args, call_id="e", can_write=True)
    assert fake.sends()[0]["body"] == {"purge_everything": True}


@pytest.mark.parametrize("extra, message", [
    ({}, "exactly one of"),
    ({"urls": ["https://example.com/"], "everything": True}, "exactly one of"),
    ({"everything": "yes"}, "everything must be true"),
    ({"urls": ["https://other.example.org/"]}, "not in the zone example.com"),
    ({"urls": ["https://notexample.com/"]}, "not in the zone"),
    ({"urls": ["ftp://example.com/"]}, "is not a URL"),
    ({"urls": ["https://example.com/a b"]}, "without spaces"),
    ({"hosts": ["example.com", "EXAMPLE.com"]}, "twice"),
    ({"prefixes": ["https://example.com/blog"]}, "without the scheme"),
    ({"urls": [f"https://example.com/{n}" for n in range(31)]}, "1 to 30"),
])
def test_a_purge_outside_the_zone_or_malformed_is_refused_before_any_card(fake, extra, message):
    with pytest.raises(cfa.CloudflareError, match=message):
        cfa.approval_request(purge(**extra), can_write=True)
    assert fake.sends() == []


V1, V2, V3 = ("11111111-1111-4111-8111-111111111111", "22222222-2222-4222-8222-222222222222",
              "33333333-3333-4333-8333-333333333333")
WORKER = "/accounts/{account}/workers/scripts/api/deployments"


def deployment(n, *versions, message=None):
    return {"id": f"d{n}", "created_on": f"2026-10-0{n}T00:00:00Z", "author_email": "dev@example.com",
            "versions": [{"version_id": v, "percentage": p} for v, p in versions],
            **({"annotations": {"workers/message": message}} if message else {})}


def test_the_rollback_routes_are_ones_the_bridge_allows():
    def ok(method, path):
        return any(m == method and p.fullmatch(path) for m, p in bridge_module._ROUTES)
    assert ok("POST", WORKER) and ok("POST", "/accounts/{account}/pages/projects/site/deployments/abc-1/rollback")
    assert not ok("PUT", "/accounts/{account}/workers/scripts/api")   # uploading code is no route


def test_a_worker_goes_back_to_its_previous_deployment_exactly(fake):
    fake.answers[WORKER] = envelope({"deployments": [deployment(1, (V1, 100)), deployment(3, (V3, 100)),
                                                      deployment(2, (V1, 40), (V2, 60), message="canary")]})
    card, _, result = approve_and_run({"action": "worker_rollback", "script": "api"})
    assert card.startswith("Cloudflare · Roll back a Worker\n⚠️ Visitors get the earlier code at once")
    assert "Worker: api" in card and "Serve 11111111 40% + 22222222 60%" in card and "instead of 33333333 100%" in card
    assert "then: canary" in card and "message: Rolled back through Hermes" in card
    [sent] = fake.sends()
    assert sent["method"] == "POST" and sent["path"] == WORKER
    assert sent["body"] == {"strategy": "percentage", "versions": [{"version_id": V1, "percentage": 40},
                                                                   {"version_id": V2, "percentage": 60}],
                            "annotations": {"workers/message": "Rolled back through Hermes"}}
    assert result["ok"] is True


def test_a_worker_goes_back_only_to_a_version_that_ran_before(fake):
    fake.answers[WORKER] = envelope({"deployments": [deployment(2, (V2, 100)), deployment(1, (V1, 100))]})
    args = {"action": "worker_rollback", "script": "api", "version": V1, "message": "back to stable"}
    card, _ = cfa.approval_request(args, call_id="v", can_write=True)
    assert "Serve 11111111 100%" in card and "message: back to stable" in card
    with pytest.raises(cfa.CloudflareError, match="only goes back to versions that ran before"):
        cfa.approval_request({**args, "version": V3}, can_write=True)
    with pytest.raises(cfa.CloudflareError, match="only goes back to versions that ran before"):
        cfa.approval_request({**args, "version": V2}, can_write=True)   # served now, never before
    fake.answers[WORKER] = envelope({"deployments": [deployment(3, (V1, 100)), deployment(2, (V2, 100)),
                                                      deployment(1, (V1, 100))]})
    with pytest.raises(cfa.CloudflareError, match="already serves 11111111 100%"):
        cfa.approval_request(args, can_write=True)
    fake.answers[WORKER] = envelope({"deployments": [deployment(1, (V1, 100))]})
    with pytest.raises(cfa.CloudflareError, match="no earlier deployment"):
        cfa.approval_request({"action": "worker_rollback", "script": "api"}, can_write=True)


def test_a_deployment_after_the_card_sends_nothing(fake):
    fake.answers[WORKER] = envelope({"deployments": [deployment(2, (V2, 100)), deployment(1, (V1, 100))]})
    args = {"action": "worker_rollback", "script": "api"}
    cfa.approval_request(args, call_id="call-1", can_write=True)
    fake.answers[WORKER] = envelope({"deployments": [deployment(3, (V3, 100)), deployment(2, (V2, 100)),
                                                      deployment(1, (V1, 100))]})
    result = cfa.execute(args, call_id="call-1", can_write=True)
    assert "changed before the write ran" in result["error"] and fake.sends() == []


PAGES = "/accounts/{account}/pages/projects/site"


def pages_deploy(n, status="success", environment="production"):
    return {"id": f"dep-{n}", "short_id": f"short{n}00", "environment": environment,
            "created_on": f"2026-10-0{n}T00:00:00Z", "latest_stage": {"name": "deploy", "status": status},
            "deployment_trigger": {"metadata": {"branch": "main", "commit_hash": f"{n}" * 40}}}


def test_a_pages_site_goes_back_to_its_previous_successful_production_deployment(fake):
    fake.answers[PAGES] = envelope({"name": "site", "domains": ["example.com"], "canonical_deployment": pages_deploy(4)})
    fake.answers[f"{PAGES}/deployments"] = envelope([pages_deploy(4), pages_deploy(3, status="failure"),
                                                     pages_deploy(2), pages_deploy(1)])
    card, _, result = approve_and_run({"action": "pages_rollback", "project": "site"})
    assert "Cloudflare · Roll back a Pages site" in card and "Project: site" in card
    assert "Make live again: short200 main 22222222 2026-10-02" in card and "instead of short400" in card
    [sent] = fake.sends()
    assert sent["path"] == f"{PAGES}/deployments/dep-2/rollback" and sent["body"] is None
    assert result["ok"] is True


def test_a_pages_rollback_refuses_a_preview_a_failure_or_the_live_one(fake):
    fake.answers[PAGES] = envelope({"name": "site", "canonical_deployment": pages_deploy(4)})
    fake.answers[f"{PAGES}/deployments"] = envelope([pages_deploy(4), pages_deploy(3, status="failure")])
    fake.answers[f"{PAGES}/deployments/dep-5"] = envelope(pages_deploy(5, environment="preview"))
    for wanted in ("dep-3", "dep-4", "dep-5"):
        with pytest.raises(cfa.CloudflareError, match="not a successful production deployment older than the live"):
            cfa.approval_request({"action": "pages_rollback", "project": "site", "deployment": wanted},
                                 can_write=True)
    with pytest.raises(cfa.CloudflareError, match="no earlier successful production deployment"):
        cfa.approval_request({"action": "pages_rollback", "project": "site"}, can_write=True)
    assert fake.sends() == []


def test_a_version_that_never_served_traffic_or_shares_that_do_not_add_up_are_refused(fake):
    fake.answers[WORKER] = envelope({"deployments": [deployment(3, (V3, 100)), deployment(2, (V1, 100), (V2, 0)),
                                                      deployment(1, (V1, 100))]})
    with pytest.raises(cfa.CloudflareError, match="did not serve traffic"):
        cfa.approval_request({"action": "worker_rollback", "script": "api", "version": V2}, can_write=True)
    with pytest.raises(cfa.CloudflareError, match="add up to 100%"):
        cfa.approval_request({"action": "worker_rollback", "script": "api"}, can_write=True)
    assert fake.sends() == []


def test_a_named_pages_deployment_newer_than_the_live_one_is_refused(fake):
    fake.answers[PAGES] = envelope({"name": "site", "canonical_deployment": pages_deploy(2)})
    fake.answers[f"{PAGES}/deployments"] = envelope([pages_deploy(3), pages_deploy(2), pages_deploy(1)])
    with pytest.raises(cfa.CloudflareError, match="older than the live one"):
        cfa.approval_request({"action": "pages_rollback", "project": "site", "deployment": "dep-3"}, can_write=True)
    assert cfa.approval_request({"action": "pages_rollback", "project": "site", "deployment": "short100"},
                                can_write=True)


def test_a_pages_deploy_after_the_card_sends_nothing(fake):
    fake.answers[PAGES] = envelope({"name": "site", "canonical_deployment": pages_deploy(3)})
    fake.answers[f"{PAGES}/deployments"] = envelope([pages_deploy(3), pages_deploy(2)])
    args = {"action": "pages_rollback", "project": "site"}
    cfa.approval_request(args, call_id="p", can_write=True)
    fake.answers[PAGES] = envelope({"name": "site", "canonical_deployment": pages_deploy(4)})
    fake.answers[f"{PAGES}/deployments"] = envelope([pages_deploy(4), pages_deploy(3), pages_deploy(2)])
    assert "changed before the write ran" in cfa.execute(args, call_id="p", can_write=True)["error"]
    assert fake.sends() == []


def test_the_card_names_the_account_once_it_was_read(fake):
    cfa.remember_account("work", {"id": ACCOUNT, "name": "Work Co"})
    card, _ = cfa.approval_request(change({"op": "delete", "id": WWW}), can_write=True)
    assert "Account: work (Work Co)" in card
