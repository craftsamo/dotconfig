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
        self.account_id = ACCOUNT
        self.answers = {}   # any other GET: path -> Cloudflare's JSON

    def head(self, fields):
        return {"account": fields.get("account") or "work", "item": "CLOUDFLARE_WORK", "account_id": self.account_id,
                "fingerprint": self.fingerprint, "token_kind": "user"}

    def record(self, path, params=None):
        if path in self.answers:
            answer = self.answers[path]
            return {"ok": True, "status": 200,
                    "data": answer(dict(params or [])) if callable(answer) else answer}
        rid = path.rsplit("/", 1)[1]
        if rid in self.records:
            return {"ok": True, "status": 200, "data": envelope(dict(self.records[rid]))}
        return {"ok": False, "kind": "not_found", "status": 404, "error": "81044: Record does not exist."}

    def __call__(self, op, **fields):
        self.requests.append({"op": op, **fields})
        if op == "reads":
            results = [self.record(r["path"], r.get("params")) for r in fields["requests"]]
            return {**self.head(fields), "ok": True, "requests": len(results), "results": results}
        path, method = fields.get("path"), fields.get("method")
        if method == "GET" and path == "/zones":
            return {**self.head(fields), "ok": True, "requests": 1, "data": envelope([ZONE_OBJ])}
        if method == "GET" and path == f"/zones/{ZONE}":
            return {**self.head(fields), "ok": True, "requests": 1, "data": envelope(ZONE_OBJ)}
        if method == "GET" and path in self.answers:
            answer = self.answers[path]
            data = answer(dict(fields.get("params") or [])) if callable(answer) else answer
            return {**self.head(fields), "ok": True, "requests": 1, "data": data}
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


@pytest.fixture(autouse=True)
def stock_card_budgets(monkeypatch):
    # cards.roomy() reads whichever gateway module an earlier test imported
    monkeypatch.setattr(cfa.cards, "roomy", lambda: False)


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


def test_a_dns_change_keeps_its_exact_approval_key(fake):
    # byte identity of the key, pinned: anything that reaches a plan's digest changes every stored "always"
    args = change({"op": "update", "id": WWW, "content": "192.0.2.10", "ttl": 300},
                  {"op": "add", "type": "A", "name": "blog", "content": "192.0.2.20", "proxied": True})
    _, key = cfa.approval_request(args, call_id="k", can_write=True)
    assert key == "cloudflare-access:dns_change:fdf7f7deea8c009a"


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
    at, *record = cfa._approved[key]
    cfa._approved[key] = (at - cfa.APPROVAL_TTL - 1, *record)
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
    assert card.startswith("Cloudflare · Purge the cache\n✅ Visitors get fresh copies")
    assert "2 URLs" in card and "- https://www.example.com/index.html" in card and "- http://example.com/" in card
    [sent] = fake.sends()
    assert sent["path"] == f"/zones/{ZONE}/purge_cache"
    assert sent["body"] == {"files": ["https://www.example.com/index.html", "http://example.com/"]}
    assert result["ok"] is True and key == f"cloudflare-access:purge-urls:{ZONE}"


def test_hosts_and_prefixes_purge_everything_under_them(fake):
    card, key = cfa.approval_request(purge(hosts=["static.example.com"]), call_id="h", can_write=True)
    assert "⚠️" in card and "1 host name, every file under each" in card
    assert key.startswith("cloudflare-access:cache_purge:")
    card, key = cfa.approval_request(purge(prefixes=["www.example.com/blog/"]), call_id="p", can_write=True)
    assert "⚠️" in card and "- www.example.com/blog/" in card
    assert key.startswith("cloudflare-access:cache_purge:")


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


SETTING = f"/zones/{ZONE}/settings"


def test_the_engine_and_the_bridge_name_the_same_settings():
    assert tuple(cfa.SETTING_VALUES) == bridge_module.PATCHABLE
    def ok(path):
        return any(m == "PATCH" and p.fullmatch(path) for m, p in bridge_module._ROUTES)
    assert all(ok(f"{SETTING}/{name}") for name in cfa.SETTING_VALUES)
    assert not ok(f"{SETTING}/waf") and not ok(f"{SETTING}/ssl/../waf")


def test_a_setting_moves_from_what_it_is_to_what_it_becomes(fake):
    fake.answers[f"{SETTING}/ssl"] = envelope({"id": "ssl", "value": "full", "editable": True})
    card, key, result = approve_and_run({"action": "zone_setting", "zone": "example.com", "setting": "ssl",
                                         "value": "Strict"})
    assert "⚠️ How Cloudflare reaches the origin" in card and "ssl: full → strict" in card
    [sent] = fake.sends()
    assert sent["method"] == "PATCH" and sent["path"] == f"{SETTING}/ssl" and sent["body"] == {"value": "strict"}
    assert result["ok"] is True


@pytest.mark.parametrize("setting, now, value", [("ssl", "strict", "flexible"), ("min_tls_version", "1.2", "1.0"),
                                                 ("security_level", "medium", "essentially_off"),
                                                 ("always_use_https", "on", "off")])
def test_weakening_what_protects_visitors_is_marked_and_asked_every_time(fake, setting, now, value):
    fake.answers[f"{SETTING}/{setting}"] = envelope({"id": setting, "value": now, "editable": True})
    args = {"action": "zone_setting", "zone": "example.com", "setting": setting, "value": value}
    card, key = cfa.approval_request(args, call_id="a", can_write=True)
    assert "🚨 Weaker protection for visitors" in card
    assert key != cfa.approval_request(args, call_id="b", can_write=True)[1]


def test_browser_cache_ttl_goes_out_as_a_number(fake):
    fake.answers[f"{SETTING}/browser_cache_ttl"] = envelope({"id": "browser_cache_ttl", "value": 14400})
    approve_and_run({"action": "zone_setting", "zone": "example.com", "setting": "browser_cache_ttl", "value": "3600"})
    assert fake.sends()[0]["body"] == {"value": 3600}


@pytest.mark.parametrize("args, message", [
    ({"setting": "waf", "value": "on"}, "setting must be one of"),
    ({"setting": "ssl", "value": "full_strict"}, "ssl takes off, flexible, full, strict"),
    ({"setting": "browser_cache_ttl", "value": "999"}, "browser_cache_ttl takes"),
    ({"setting": "ssl", "value": "full"}, "already full"),
    ({"setting": "http3", "value": "on"}, "cannot be changed on this zone's plan"),
])
def test_a_setting_change_that_would_fail_is_refused_before_any_card(fake, args, message):
    fake.answers[f"{SETTING}/ssl"] = envelope({"id": "ssl", "value": "full", "editable": True})
    fake.answers[f"{SETTING}/http3"] = envelope({"id": "http3", "value": "off", "editable": False})
    with pytest.raises(cfa.CloudflareError, match=message):
        cfa.approval_request({"action": "zone_setting", "zone": "example.com", **args}, can_write=True)
    assert fake.sends() == []


def test_a_setting_changed_after_the_card_sends_nothing(fake):
    fake.answers[f"{SETTING}/ssl"] = envelope({"id": "ssl", "value": "full", "editable": True})
    args = {"action": "zone_setting", "zone": "example.com", "setting": "ssl", "value": "strict"}
    cfa.approval_request(args, call_id="s", can_write=True)
    fake.answers[f"{SETTING}/ssl"] = envelope({"id": "ssl", "value": "flexible", "editable": True})
    assert "changed before the write ran" in cfa.execute(args, call_id="s", can_write=True)["error"]
    assert fake.sends() == []


RULES = f"/zones/{ZONE}/email/routing/rules"
ADDRESSES = "/accounts/{account}/email/routing/addresses"
RULE = {"id": "a" * 32, "name": "sales", "enabled": True,
        "matchers": [{"type": "literal", "field": "to", "value": "sales@example.com"}],
        "actions": [{"type": "forward", "value": ["owner@example.net"]}]}


@pytest.fixture
def mail(fake):
    fake.answers[ADDRESSES] = envelope([{"email": "owner@example.net", "verified": "2026-01-01T00:00:00Z"},
                                        {"email": "new@example.net", "verified": None}])
    fake.answers[f"{RULES}/{'a' * 32}"] = envelope(dict(RULE))
    fake.answers[f"{RULES}/catch_all"] = envelope({"id": "c", "enabled": False, "matchers": [{"type": "all"}],
                                                   "actions": [{"type": "drop"}]})
    return fake


def rule(**extra):
    return {"action": "email_rule", "zone": "example.com", **extra}


def test_the_rule_routes_never_reach_the_catch_all_through_an_id():
    def ok(method, path):
        return any(m == method and p.fullmatch(path) for m, p in bridge_module._ROUTES)
    assert ok("PUT", f"{RULES}/{'a' * 32}") and ok("PUT", f"{RULES}/catch_all") and ok("DELETE", f"{RULES}/abc")
    assert not ok("DELETE", f"{RULES}/catch_all")


def test_a_rule_forwards_only_to_a_verified_destination(mail):
    card, _, result = approve_and_run(rule(op="add", to="Sales", forward="Owner@Example.net", name="sales desk"))
    assert "Cloudflare · Add an e-mail rule" in card and "+ sales@example.com → forward owner@example.net" in card
    [sent] = mail.sends()
    assert sent["method"] == "POST" and sent["path"] == RULES
    assert sent["body"] == {"matchers": [{"type": "literal", "field": "to", "value": "sales@example.com"}],
                            "actions": [{"type": "forward", "value": ["owner@example.net"]}], "enabled": True,
                            "name": "sales desk"}
    with pytest.raises(cfa.CloudflareError, match="not a verified destination"):
        cfa.approval_request(rule(op="add", to="info", forward="new@example.net"), can_write=True)
    with pytest.raises(cfa.CloudflareError, match="an address at example.com"):
        cfa.approval_request(rule(op="add", to="info@other.example", drop=True), can_write=True)
    with pytest.raises(cfa.CloudflareError, match="exactly one of forward"):
        cfa.approval_request(rule(op="add", to="info", drop=True, forward="owner@example.net"), can_write=True)


def test_a_rule_change_shows_what_moves_and_keeps_the_rest(mail):
    card, _, _ = approve_and_run(rule(op="update", id="a" * 32, drop=True, enabled=False))
    assert "~ sales@example.com: forward owner@example.net → drop; on → off" in card
    [sent] = mail.sends()
    assert sent["method"] == "PUT" and sent["body"] == {"matchers": RULE["matchers"], "actions": [{"type": "drop"}],
                                                        "enabled": False, "name": "sales"}
    with pytest.raises(cfa.CloudflareError, match="moves nothing"):
        cfa.approval_request(rule(op="update", id="a" * 32, forward="owner@example.net"), can_write=True)


def test_deleting_a_rule_or_changing_the_catch_all_asks_every_time(mail):
    args = rule(op="delete", id="a" * 32)
    card, key = cfa.approval_request(args, call_id="d", can_write=True)
    assert "🚨 The rule is gone" in card and "- sales@example.com → forward owner@example.net" in card
    assert key != cfa.approval_request(args, call_id="d2", can_write=True)[1]
    card, key = cfa.approval_request(rule(op="catch_all", forward="owner@example.net", enabled=True),
                                     call_id="c", can_write=True)
    assert "🚨 Changes where all mail no rule matches goes" in card
    assert "~ catch-all: drop → forward owner@example.net; off → on" in card
    cfa.execute(rule(op="catch_all", forward="owner@example.net", enabled=True), call_id="c", can_write=True)
    [sent] = mail.sends()
    assert sent["path"] == f"{RULES}/catch_all" and sent["body"]["matchers"] == [{"type": "all"}]
    with pytest.raises(cfa.CloudflareError, match="delete takes only the rule's id"):
        cfa.approval_request(rule(op="delete", id="a" * 32, drop=True), can_write=True)
    with pytest.raises(cfa.CloudflareError, match="needs id"):
        cfa.approval_request(rule(op="delete"), can_write=True)


def test_a_rule_changed_after_the_card_sends_nothing(mail):
    args = rule(op="update", id="a" * 32, enabled=False)
    cfa.approval_request(args, call_id="call-1", can_write=True)
    mail.answers[f"{RULES}/{'a' * 32}"] = envelope({**RULE, "name": "renamed meanwhile"})
    assert "changed before the write ran" in cfa.execute(args, call_id="call-1", can_write=True)["error"]
    assert mail.sends() == []


def test_a_destination_on_a_later_page_is_found(mail):
    def addresses(params):
        if params.get("page", "1") == "1":
            return {**envelope([{"email": "owner@example.net", "verified": "2026-01-01T00:00:00Z"}]),
                    "result_info": {"page": 1, "total_pages": 2}}
        return {**envelope([{"email": "late@example.net", "verified": "2026-01-02T00:00:00Z"}]),
                "result_info": {"page": 2, "total_pages": 2}}
    mail.answers[ADDRESSES] = addresses
    card, _ = cfa.approval_request(rule(op="add", to="info", forward="late@example.net"), call_id="l",
                                   can_write=True)
    assert "forward late@example.net" in card
    with pytest.raises(cfa.CloudflareError, match="not a verified destination"):
        cfa.approval_request(rule(op="add", to="info", forward="nobody@example.net"), can_write=True)


def test_a_rule_s_name_shows_on_its_card_and_a_change_keeps_its_priority(mail):
    mail.answers[f"{RULES}/{'a' * 32}"] = envelope({**RULE, "priority": 3})
    card, _, _ = approve_and_run(rule(op="update", id="a" * 32, name="front desk\u202e"))
    assert "name sales → front desk⟨U+202E⟩" in card
    assert mail.sends()[0]["body"]["priority"] == 3
    card, _ = cfa.approval_request(rule(op="add", to="info", drop=True, name="spam trap"), call_id="n",
                                   can_write=True)
    assert "name: spam trap" in card


TUNNEL = "5a5a5a5a-1b1b-4c4c-8d8d-9e9e9e9e9e9e"
TUNNEL_BASE = f"/accounts/{{account}}/cfd_tunnel/{TUNNEL}"
CNAME = {"id": "6" * 32, "type": "CNAME", "name": "app.example.com", "content": f"{TUNNEL}.cfargotunnel.com"}


@pytest.fixture
def tunnel(fake):
    fake.answers[TUNNEL_BASE] = envelope({"id": TUNNEL, "name": "home", "config_src": "cloudflare"})
    fake.answers[f"{TUNNEL_BASE}/configurations"] = envelope({"version": 4, "config": {
        "originRequest": {"connectTimeout": 10},
        "ingress": [{"hostname": "wiki.example.com", "service": "http://localhost:3000"},
                    {"service": "http_status:404"}]}})
    fake.answers[f"/zones/{ZONE}/dns_records"] = envelope([])
    return fake


def route(**extra):
    return {"action": "tunnel_route", "tunnel": TUNNEL, **extra}


def test_publishing_a_hostname_adds_its_rule_before_the_catch_all_and_its_dns_record(tunnel):
    card, key, result = approve_and_run(route(op="add", hostname="App.Example.com", service="http://localhost:8080"))
    assert "🚨 Publishes a service of the machine behind the tunnel on the internet" in card
    assert "Tunnel: home" in card and "+ app.example.com → http://localhost:8080" in card
    assert "DNS: + CNAME app → the tunnel, proxied" in card
    config, dns = tunnel.sends()
    assert config["method"] == "PUT" and config["path"] == f"{TUNNEL_BASE}/configurations"
    assert config["body"] == {"config": {"originRequest": {"connectTimeout": 10}, "ingress": [
        {"hostname": "wiki.example.com", "service": "http://localhost:3000"},
        {"hostname": "app.example.com", "service": "http://localhost:8080"}, {"service": "http_status:404"}]}}
    assert dns["path"] == f"/zones/{ZONE}/dns_records/batch"
    assert dns["body"] == {"posts": [{"type": "CNAME", "name": "app.example.com",
                                      "content": f"{TUNNEL}.cfargotunnel.com", "proxied": True, "ttl": 1,
                                      "comment": "Cloudflare Tunnel"}]}
    assert result["ok"] is True and key != cfa.approval_request(
        route(op="add", hostname="other.example.com", service="http://localhost:1"), call_id="x", can_write=True)[1]


def test_a_hostname_with_other_records_or_outside_the_account_is_refused(tunnel):
    tunnel.answers[f"/zones/{ZONE}/dns_records"] = envelope([{"id": "7" * 32, "type": "A", "name": "app.example.com",
                                                              "content": "192.0.2.1"}])
    with pytest.raises(cfa.CloudflareError, match="already has DNS records \\(A\\)"):
        cfa.approval_request(route(op="add", hostname="app.example.com", service="http://localhost:8080"),
                             can_write=True)
    with pytest.raises(cfa.CloudflareError, match="not in a zone of this account"):
        cfa.approval_request(route(op="add", hostname="app.example.org", service="http://localhost:8080"),
                             can_write=True)
    with pytest.raises(cfa.CloudflareError, match="service must be"):
        cfa.approval_request(route(op="add", hostname="app.example.com", service="javascript:alert(1)"),
                             can_write=True)
    assert tunnel.sends() == []


def test_a_tunnel_managed_locally_is_left_alone(tunnel):
    tunnel.answers[TUNNEL_BASE] = envelope({"id": TUNNEL, "name": "home", "config_src": "local"})
    with pytest.raises(cfa.CloudflareError, match="managed in a local config file"):
        cfa.approval_request(route(op="remove", hostname="wiki.example.com"), can_write=True)


def test_changing_or_removing_a_hostname(tunnel):
    card, key = cfa.approval_request(route(op="update", hostname="wiki.example.com", service="http://localhost:3001"),
                                     call_id="u", can_write=True)
    assert "🚨 Changes which service" in card and "~ wiki.example.com: http://localhost:3000 → http://localhost:3001" in card
    tunnel.answers[f"/zones/{ZONE}/dns_records"] = envelope([{**CNAME, "name": "wiki.example.com"}])
    card, _, result = approve_and_run(route(op="remove", hostname="wiki.example.com"))
    assert "🚨 The hostname stops answering" in card and "DNS: - CNAME wiki → the tunnel" in card
    config, dns = tunnel.sends()
    assert config["body"]["config"]["ingress"] == [{"service": "http_status:404"}]
    assert dns["body"] == {"deletes": [{"id": "6" * 32}]}
    with pytest.raises(cfa.CloudflareError, match="does not publish"):
        cfa.approval_request(route(op="remove", hostname="nope.example.com"), can_write=True)


def test_rules_keep_their_order_and_a_path_rule_still_comes_first(tunnel):
    deny = {"path": "^/admin", "service": "http_status:403"}
    tunnel.answers[f"{TUNNEL_BASE}/configurations"] = envelope({"version": 4, "config": {"ingress": [
        deny, {"hostname": "wiki.example.com", "service": "http://localhost:3000"}, {"service": "http_status:404"}]}})
    approve_and_run(route(op="add", hostname="app.example.com", service="http://localhost:8080"))
    assert tunnel.sends()[0]["body"]["config"]["ingress"] == [
        deny, {"hostname": "wiki.example.com", "service": "http://localhost:3000"},
        {"hostname": "app.example.com", "service": "http://localhost:8080"}, {"service": "http_status:404"}]


def test_removing_the_last_rule_of_a_hostname_deletes_its_record_and_asks_every_time(tunnel):
    tunnel.answers[f"/zones/{ZONE}/dns_records"] = envelope([{**CNAME, "name": "wiki.example.com"}])
    args = route(op="remove", hostname="wiki.example.com")
    card, key = cfa.approval_request(args, call_id="r1", can_write=True)
    assert "🚨 The hostname stops answering and its DNS record is deleted" in card
    assert key != cfa.approval_request(args, call_id="r2", can_write=True)[1]


def test_a_tunnel_configuration_changed_after_the_card_sends_nothing(tunnel):
    args = route(op="add", hostname="app.example.com", service="http://localhost:8080")
    cfa.approval_request(args, call_id="call-1", can_write=True)
    tunnel.answers[f"{TUNNEL_BASE}/configurations"] = envelope({"version": 5, "config": {"ingress": [
        {"service": "http_status:404"}]}})
    assert "changed before the write ran" in cfa.execute(args, call_id="call-1", can_write=True)["error"]
    assert tunnel.sends() == []


def test_a_dns_failure_after_the_configuration_is_reported_part_way(tunnel):
    args = route(op="add", hostname="app.example.com", service="http://localhost:8080")
    cfa.approval_request(args, call_id="call-1", can_write=True)
    original = tunnel.__call__

    def dns_fails(op, **fields):
        if fields.get("path", "").endswith("/dns_records/batch"):
            tunnel.requests.append({"op": op, **fields})
            return {**tunnel.head(fields), "ok": False, "requests": 1, "kind": "invalid", "status": 400,
                    "error": "81053: record exists"}
        return original(op, **fields)
    cfa.bridge = dns_fails
    try:
        result = cfa.execute(args, call_id="call-1", can_write=True)
    finally:
        cfa.bridge = tunnel
    assert result["error"].startswith("stopped part way") and "changing the hostnames of tunnel" in result["error"]


DB = "0f0e0d0c-0b0a-4908-8706-050403020100"
NAMESPACE = "4" * 32


def test_the_storage_routes_are_ones_the_bridge_allows():
    def ok(method, path):
        return any(m == method and p.fullmatch(path) for m, p in bridge_module._ROUTES)
    base = "/accounts/{account}"
    assert ok("POST", f"{base}/r2/buckets") and ok("DELETE", f"{base}/r2/buckets/media")
    assert ok("DELETE", f"{base}/storage/kv/namespaces/{NAMESPACE}") and ok("DELETE", f"{base}/d1/database/{DB}")
    assert not ok("DELETE", f"{base}/r2/buckets/media/objects/photo.jpg")
    assert not ok("PUT", f"{base}/storage/kv/namespaces/{NAMESPACE}/values/key")


@pytest.mark.parametrize("kind, name, path, body", [
    ("r2", "media", "/accounts/{account}/r2/buckets", {"name": "media"}),
    ("kv", "SESSIONS", "/accounts/{account}/storage/kv/namespaces", {"title": "SESSIONS"}),
    ("d1", "app_db", "/accounts/{account}/d1/database", {"name": "app_db"}),
])
def test_a_container_is_created_empty_after_its_card(fake, kind, name, path, body):
    fake.answers[path] = envelope([] if kind != "r2" else {"buckets": []})
    card, _, result = approve_and_run({"action": "storage_create", "kind": kind, "name": name})
    assert "✅ A new, empty one" in card and name in card
    [sent] = fake.sends()
    assert sent["method"] == "POST" and sent["path"] == path and sent["body"] == body and result["ok"] is True


def test_a_name_already_taken_or_malformed_is_refused(fake):
    fake.answers["/accounts/{account}/r2/buckets"] = envelope({"buckets": [{"name": "media"}]})
    with pytest.raises(cfa.CloudflareError, match="an R2 bucket named media already exists"):
        cfa.approval_request({"action": "storage_create", "kind": "r2", "name": "media"}, can_write=True)
    with pytest.raises(cfa.CloudflareError, match="lowercase letters"):
        cfa.approval_request({"action": "storage_create", "kind": "r2", "name": "Media!"}, can_write=True)
    with pytest.raises(cfa.CloudflareError, match="kind must be"):
        cfa.approval_request({"action": "storage_create", "kind": "s3", "name": "media"}, can_write=True)


def test_an_empty_bucket_is_deleted_and_one_holding_objects_is_not(fake):
    objects = "/accounts/{account}/r2/buckets/media/objects"
    fake.answers[objects] = envelope([])
    card, key, result = approve_and_run({"action": "storage_delete", "kind": "r2", "bucket": "media"})
    assert "🚨 Deleted for good" in card and "- R2 bucket media, found empty" in card
    assert fake.sends()[0]["path"] == "/accounts/{account}/r2/buckets/media" and fake.sends()[0]["method"] == "DELETE"
    fake.answers[objects] = envelope([{"key": "a.png", "size": 1}])
    with pytest.raises(cfa.CloudflareError, match="still holds objects"):
        cfa.approval_request({"action": "storage_delete", "kind": "r2", "bucket": "media"}, can_write=True)
    fake.answers[objects] = {**envelope([]), "result_info": {"delimited": ["photos/"]}}
    with pytest.raises(cfa.CloudflareError, match="still holds objects"):
        cfa.approval_request({"action": "storage_delete", "kind": "r2", "bucket": "media"}, can_write=True)


def test_an_object_added_after_the_card_stops_the_delete(fake):
    objects = "/accounts/{account}/r2/buckets/media/objects"
    fake.answers[objects] = envelope([])
    args = {"action": "storage_delete", "kind": "r2", "bucket": "media"}
    cfa.approval_request(args, call_id="call-1", can_write=True)
    fake.answers[objects] = envelope([{"key": "late.png", "size": 1}])
    assert "still holds objects" in cfa.execute(args, call_id="call-1", can_write=True)["error"]
    assert fake.sends() == []


def test_an_empty_first_page_of_keys_with_more_behind_it_is_not_empty(fake):
    keys = f"/accounts/{{account}}/storage/kv/namespaces/{NAMESPACE}/keys"
    fake.answers["/accounts/{account}/storage/kv/namespaces"] = envelope([{"id": NAMESPACE, "title": "SESSIONS"}])

    def pages(params):
        if "cursor" not in params:
            return {**envelope([]), "result_info": {"cursor": "next1", "count": 0}}
        return {**envelope([{"name": "live"}]), "result_info": {"cursor": "", "count": 1}}
    fake.answers[keys] = pages
    with pytest.raises(cfa.CloudflareError, match="still holds keys"):
        cfa.approval_request({"action": "storage_delete", "kind": "kv", "namespace": NAMESPACE}, can_write=True)
    fake.answers[keys] = lambda params: {**envelope([]), "result_info": {"cursor": "again", "count": 0}}
    with pytest.raises(cfa.CloudflareError, match="not taken for empty"):
        cfa.approval_request({"action": "storage_delete", "kind": "kv", "namespace": NAMESPACE}, can_write=True)


def test_a_schema_that_could_not_be_read_is_not_empty(fake):
    fake.answers[f"/accounts/{{account}}/d1/database/{DB}"] = envelope({"uuid": DB, "name": "app"})
    fake.write_reply = {"ok": True, "status": 200, "data": envelope([{"success": False, "results": []}])}
    with pytest.raises(cfa.CloudflareError, match="could not be read in full"):
        cfa.approval_request({"action": "storage_delete", "kind": "d1", "database": DB}, can_write=True)
    fake.write_reply = {"ok": True, "status": 200, "data": envelope([])}
    with pytest.raises(cfa.CloudflareError, match="could not be read in full"):
        cfa.approval_request({"action": "storage_delete", "kind": "d1", "database": DB}, can_write=True)


def test_a_bucket_page_that_continues_is_not_empty(fake):
    fake.answers["/accounts/{account}/r2/buckets/media/objects"] = {**envelope([]), "result_info": {
        "cursor": "more", "is_truncated": True}}
    with pytest.raises(cfa.CloudflareError, match="still holds objects"):
        cfa.approval_request({"action": "storage_delete", "kind": "r2", "bucket": "media"}, can_write=True)


def test_namespaces_and_databases_are_deleted_only_when_empty(fake):
    fake.answers["/accounts/{account}/storage/kv/namespaces"] = envelope([{"id": NAMESPACE, "title": "SESSIONS"}])
    fake.answers[f"/accounts/{{account}}/storage/kv/namespaces/{NAMESPACE}/keys"] = envelope([{"name": "k"}])
    with pytest.raises(cfa.CloudflareError, match="still holds keys"):
        cfa.approval_request({"action": "storage_delete", "kind": "kv", "namespace": NAMESPACE}, can_write=True)
    fake.answers[f"/accounts/{{account}}/storage/kv/namespaces/{NAMESPACE}/keys"] = envelope([])
    card, _ = cfa.approval_request({"action": "storage_delete", "kind": "kv", "namespace": NAMESPACE},
                                   call_id="k", can_write=True)
    assert "- KV namespace SESSIONS (44444444), found empty" in card
    fake.answers[f"/accounts/{{account}}/d1/database/{DB}"] = envelope({"uuid": DB, "name": "app"})
    fake.write_reply = {"ok": True, "status": 200, "data": envelope([{"success": True, "results": [
        {"type": "table", "name": "users", "tbl_name": "users", "sql": "CREATE TABLE users (id)"}]}])}
    with pytest.raises(cfa.CloudflareError, match="still holds tables"):
        cfa.approval_request({"action": "storage_delete", "kind": "d1", "database": DB}, can_write=True)
    fake.write_reply = {"ok": True, "status": 200, "data": envelope([{"success": True, "results": []}])}
    card, _ = cfa.approval_request({"action": "storage_delete", "kind": "d1", "database": DB}, call_id="d",
                                   can_write=True)
    assert "- D1 database app (0f0e0d0c), found empty" in card
    with pytest.raises(cfa.CloudflareError, match="named by database, not bucket"):
        cfa.approval_request({"action": "storage_delete", "kind": "d1", "database": DB, "bucket": "x"},
                             can_write=True)


def test_the_card_names_the_account_once_it_was_read(fake):
    cfa.remember_account("work", {"id": ACCOUNT, "name": "Work Co"})
    card, _ = cfa.approval_request(change({"op": "delete", "id": WWW}), can_write=True)
    assert "Account: work (Work Co)" in card


# --- standing keys: one answer covers later calls to the same account or zone --------------------

OTHER_ZONE = "8" * 32
OTHER_ACCOUNT = "fedcba9876543210fedcba9876543210"
KV_LIST = "/accounts/{account}/storage/kv/namespaces"


def zone_now(fake, **now):
    """Cloudflare's current value of each named setting of the zone."""
    for name, value in now.items():
        fake.answers[f"{SETTING}/{name}"] = envelope({"id": name, "value": value, "editable": True})


def setting(name, value, **extra):
    return {"action": "zone_setting", "zone": "example.com", "setting": name, "value": value, **extra}


def settings(*pairs, **extra):
    return {"action": "zone_setting", "zone": "example.com", "settings": [
        {"setting": name, "value": value} for name, value in pairs], **extra}


def other_zone(fake):
    fake.answers[f"/zones/{OTHER_ZONE}"] = envelope({"id": OTHER_ZONE, "name": "example.org",
                                                     "account": {"id": ACCOUNT, "name": "Work"}})
    fake.answers[f"/zones/{OTHER_ZONE}/settings/development_mode"] = envelope(
        {"id": "development_mode", "value": "off", "editable": True})


def test_empty_storage_shares_one_answer_per_account(fake):
    fake.answers[KV_LIST] = envelope([])
    keys = {cfa.approval_request({"action": "storage_create", "kind": "kv", "name": name}, call_id=name,
                                 can_write=True)[1] for name in ("SESSIONS", "CACHE")}
    assert keys == {f"cloudflare-access:empty-storage:{ACCOUNT}"}
    fake.account_id = OTHER_ACCOUNT
    _, other = cfa.approval_request({"action": "storage_create", "kind": "kv", "name": "SESSIONS"}, call_id="o",
                                    can_write=True)
    assert other == f"cloudflare-access:empty-storage:{OTHER_ACCOUNT}"
    fake.account_id = None   # no account to bind: the exact key
    _, exact = cfa.approval_request({"action": "storage_create", "kind": "kv", "name": "SESSIONS"}, call_id="n",
                                    can_write=True)
    assert exact.startswith("cloudflare-access:storage_create:")


def test_a_write_after_a_standing_approval_still_needs_its_own_unchanged_card(fake):
    fake.answers[KV_LIST] = envelope([])
    first = {"action": "storage_create", "kind": "kv", "name": "SESSIONS"}
    second = {"action": "storage_create", "kind": "kv", "name": "CACHE"}
    cfa.approval_request(first, call_id="a", can_write=True)
    # the key is shared, the approval is not: another payload has no card of its own
    assert "did not pass its approval card" in cfa.execute(second, call_id="b", can_write=True)["error"]
    fake.fingerprint = "e" * 12
    assert "changed before the write ran" in cfa.execute(first, call_id="a", can_write=True)["error"]
    assert fake.sends() == []


def test_purging_urls_shares_one_answer_per_zone_and_nothing_wider_does(fake):
    other_zone(fake)
    one = purge(urls=["https://www.example.com/a"])
    card, key = cfa.approval_request(one, call_id="1", can_write=True)
    assert "✅" in card and key == f"cloudflare-access:purge-urls:{ZONE}"
    assert cfa.approval_request(purge(urls=["http://example.com/b", "https://example.com/c"]), call_id="2",
                                can_write=True)[1] == key
    _, elsewhere = cfa.approval_request({"action": "cache_purge", "zone": OTHER_ZONE,
                                         "urls": ["https://example.org/a"]}, call_id="3", can_write=True)
    assert elsewhere == f"cloudflare-access:purge-urls:{OTHER_ZONE}"
    for wider in (purge(hosts=["www.example.com"]), purge(prefixes=["www.example.com/blog"])):
        card, exact = cfa.approval_request(wider, call_id="w", can_write=True)
        assert "⚠️" in card and exact.startswith("cloudflare-access:cache_purge:")
        assert exact == cfa.approval_request(wider, call_id="w2", can_write=True)[1]   # exact: the same payload only
    card, fresh = cfa.approval_request(purge(everything=True), call_id="e", can_write=True)
    assert "⚠️" in card and fresh != cfa.approval_request(purge(everything=True), call_id="e2", can_write=True)[1]
    with pytest.raises(cfa.CloudflareError, match="exactly one of"):
        cfa.approval_request(purge(urls=["https://example.com/a"], hosts=["example.com"]), can_write=True)


def test_development_mode_on_shares_one_answer_per_zone_and_nothing_else_does(fake):
    other_zone(fake)
    zone_now(fake, development_mode="off", ssl="full", http3="off")
    card, key = cfa.approval_request(setting("development_mode", "on"), call_id="1", can_write=True)
    assert card.startswith("Cloudflare · Change a zone setting\n✅ On, the cache is bypassed for three hours, then "
                           "it turns off by itself")
    assert key == f"cloudflare-access:dev-mode-on:{ZONE}"
    assert cfa.approval_request(setting("development_mode", "ON"), call_id="2", can_write=True)[1] == key
    _, elsewhere = cfa.approval_request({"action": "zone_setting", "zone": OTHER_ZONE, "setting": "development_mode",
                                         "value": "on"}, call_id="3", can_write=True)
    assert elsewhere == f"cloudflare-access:dev-mode-on:{OTHER_ZONE}"
    # any other setting keeps its exact key, and switching it off is no standing case
    card, ssl = cfa.approval_request(setting("ssl", "strict"), call_id="4", can_write=True)
    assert "⚠️" in card and ssl.startswith("cloudflare-access:zone_setting:")
    zone_now(fake, development_mode="on")
    card, off = cfa.approval_request(setting("development_mode", "off"), call_id="5", can_write=True)
    assert "⚠️ On, the cache is bypassed for three hours" in card and "turns off by itself" not in card
    assert off.startswith("cloudflare-access:zone_setting:")
    assert off == cfa.approval_request(setting("development_mode", "off"), call_id="6", can_write=True)[1]
    zone_now(fake, ssl="strict")
    card, weaker = cfa.approval_request(setting("ssl", "flexible"), call_id="7", can_write=True)
    assert "🚨" in card and weaker != cfa.approval_request(setting("ssl", "flexible"), call_id="8",
                                                           can_write=True)[1]


def test_a_batch_with_development_mode_on_and_another_setting_gets_no_standing_key(fake):
    zone_now(fake, development_mode="off", ssl="full", min_tls_version="1.2")
    card, key = cfa.approval_request(settings(("development_mode", "on"), ("ssl", "strict")), call_id="1",
                                     can_write=True)
    assert card.startswith("Cloudflare · Change zone settings\n⚠️ ") and key.startswith("cloudflare-access:zone_setting:")
    assert "dev-mode-on" not in key
    card, nonce = cfa.approval_request(settings(("development_mode", "on"), ("min_tls_version", "1.0")), call_id="2",
                                       can_write=True)
    assert card.startswith("Cloudflare · Change zone settings\n🚨 ")
    assert nonce != cfa.approval_request(settings(("development_mode", "on"), ("min_tls_version", "1.0")),
                                         call_id="3", can_write=True)[1]
    # a list of one is the single form: the same plan, so the same standing key
    _, one = cfa.approval_request(settings(("development_mode", "on")), call_id="4", can_write=True)
    assert one == f"cloudflare-access:dev-mode-on:{ZONE}"


# --- zone_setting: several settings, one card ----------------------------------------------------

def test_a_list_of_one_setting_is_the_single_form(fake):
    zone_now(fake, ssl="full")
    plain = cfa.write_plan(setting("ssl", "strict"))
    listed = cfa.write_plan(settings(("ssl", "strict")))
    assert cfa.card(plain) == cfa.card(listed) and cfa.digest(plain) == cfa.digest(listed)


def test_a_single_setting_keeps_its_card_and_a_list_puts_the_note_and_the_warnings_in_lines(fake):
    zone_now(fake, ssl="full", http3="off")
    single = cfa.write_plan(setting("ssl", "strict"))
    assert single["lines"] == ["ssl: full → strict"] and single["details"] == []
    assert single["effect"] == (cfa.cards.CAUTION, cfa.SETTING_EFFECTS["ssl"])
    plan = cfa.write_plan(settings(("ssl", "strict"), ("http3", "on")))
    assert plan["lines"] == [f"ssl: full → strict — {cfa.SETTING_EFFECTS['ssl']}", "http3: off → on", cfa.ONE_BY_ONE]
    assert plan["details"] == []


def test_only_a_lone_development_mode_on_may_take_the_standing_key(fake, monkeypatch):
    zone_now(fake, development_mode="off", http3="off")
    original = cfa._setting_effect
    # a setting that later turns ✅ would otherwise share the development-mode key
    monkeypatch.setattr(cfa, "_setting_effect", lambda name, value, weaker: (
        (cfa.cards.SAFE, "safe now") if name == "http3" else original(name, value, weaker)))
    card, key = cfa.approval_request(setting("http3", "on"), call_id="h", can_write=True)
    assert card.startswith("Cloudflare · Change a zone setting\n✅ safe now")
    assert key.startswith("cloudflare-access:zone_setting:") and "dev-mode-on" not in key
    assert key == cfa.approval_request(setting("http3", "on"), call_id="h2", can_write=True)[1]
    assert (cfa.approval_request(setting("development_mode", "on"), call_id="d", can_write=True)[1] ==
            f"cloudflare-access:dev-mode-on:{ZONE}")


def test_three_settings_go_out_in_order_on_one_card_with_the_highest_level(fake):
    zone_now(fake, ssl="full", development_mode="off", browser_cache_ttl=14400)
    args = settings(("ssl", "strict"), ("development_mode", "on"), ("browser_cache_ttl", "3600"))
    card, key, result = approve_and_run(args)
    assert card.startswith("Cloudflare · Change zone settings\n⚠️ Changes how the zone is served\n")
    # each setting keeps its own warning on its line, and the order note is a line, so no budget cuts it
    assert ("ssl: full → strict — How Cloudflare reaches the origin; a wrong mode breaks the site\n"
            "development_mode: off → on — On, the cache is bypassed for three hours\n"
            "browser_cache_ttl: 14400 → 3600\n" + cfa.ONE_BY_ONE) in card
    assert key.startswith("cloudflare-access:zone_setting:")
    assert key == cfa.approval_request(args, call_id="again", can_write=True)[1]   # exact: this payload only
    assert [(s["method"], s["path"], s["body"]) for s in fake.sends()] == [
        ("PATCH", f"{SETTING}/ssl", {"value": "strict"}), ("PATCH", f"{SETTING}/development_mode", {"value": "on"}),
        ("PATCH", f"{SETTING}/browser_cache_ttl", {"value": 3600})]
    assert result["ok"] is True and len(result["done"]) == 3
    assert [r["value"] for r in result["result"]] == ["strict", "on", 3600]


def test_a_batch_with_one_weakening_asks_every_time(fake):
    zone_now(fake, ssl="strict", http3="off")
    args = settings(("http3", "on"), ("ssl", "flexible"))
    card, key = cfa.approval_request(args, call_id="a", can_write=True)
    assert card.startswith("Cloudflare · Change zone settings\n🚨 Weaker protection for visitors: ssl")
    assert key != cfa.approval_request(args, call_id="b", can_write=True)[1]


@pytest.mark.parametrize("args, message", [
    (settings(), "settings must be a list of 1 to 20"),
    ({**setting("ssl", "full"), "settings": [{"setting": "http3", "value": "on"}]}, "not both"),
    ({"action": "zone_setting", "zone": "example.com", "settings": {"setting": "ssl", "value": "full"}},
     "settings must be a list"),
    (settings(("ssl", "strict"), ("ssl", "full")), "only once in one call"),
    (settings(("ssl", "strict"), ("waf", "on")), "setting 2: setting must be one of"),
    (settings(("ssl", "strict"), ("http3", "maybe")), "setting 2: http3 takes on, off"),
    ({"action": "zone_setting", "zone": "example.com", "settings": [{"setting": "ssl", "value": "strict",
                                                                    "zone": "x"}]}, "setting 1: does not take zone"),
    ({"action": "zone_setting", "zone": "example.com", "settings": ["ssl"]}, "setting 1: needs setting and value"),
])
def test_a_settings_list_that_cannot_be_planned_is_refused_before_any_read(fake, args, message):
    with pytest.raises(cfa.CloudflareError, match=message):
        cfa.approval_request(args, can_write=True)
    assert fake.requests == []


def test_too_many_settings_are_refused(fake):
    names = list(cfa.SETTING_VALUES)
    pairs = [(names[n % len(names)], "on") for n in range(cfa.CHANGES_MAX + 1)]
    with pytest.raises(cfa.CloudflareError, match="1 to 20 changes"):
        cfa.approval_request(settings(*pairs), can_write=True)
    assert fake.requests == []


def test_one_setting_that_would_fail_refuses_the_whole_batch_before_its_card(fake):
    zone_now(fake, ssl="full")
    fake.answers[f"{SETTING}/http3"] = envelope({"id": "http3", "value": "off", "editable": False})
    with pytest.raises(cfa.CloudflareError, match="setting 2: http3 of example.com cannot be changed"):
        cfa.approval_request(settings(("ssl", "strict"), ("http3", "on")), can_write=True)
    with pytest.raises(cfa.CloudflareError, match="setting 1: ssl of example.com is already full"):
        cfa.approval_request(settings(("ssl", "full"), ("http3", "on")), can_write=True)
    assert fake.sends() == [] and cfa._approved == {}


def test_a_batch_of_settings_is_previewed_without_sending(fake):
    zone_now(fake, ssl="full", http3="off")
    args = settings(("ssl", "strict"), ("http3", "on"), preview=True)
    assert cfa.approval_request(args, can_write=True) is None
    result = cfa.execute(args, can_write=True)
    assert result["preview"] is True and result["requests"] == 2 and fake.sends() == []
    assert ("ssl: full → strict — How Cloudflare reaches the origin; a wrong mode breaks the site\nhttp3: off → on"
            in result["card"])


def failing(fake, monkeypatch, path_end, reply):
    """The bridge, but the write whose path ends so gets `reply`."""
    original = fake.__call__

    def bridge(op, **fields):
        if fields.get("method") in ("POST", "PUT", "PATCH", "DELETE") and fields.get("path", "").endswith(path_end):
            fake.requests.append({"op": op, **fields})
            return {**fake.head(fields), "requests": 1, **reply}
        return original(op, **fields)
    monkeypatch.setattr(cfa, "bridge", bridge)


def test_a_setting_refused_part_way_stops_the_rest_and_reports_what_was_done(fake, monkeypatch):
    zone_now(fake, ssl="full", http3="off", ipv6="off")
    args = settings(("ssl", "strict"), ("http3", "on"), ("ipv6", "on"))
    failing(fake, monkeypatch, "/settings/http3", {"ok": False, "kind": "invalid", "status": 400,
                                                   "error": "1007: Invalid value"})
    _, _, result = approve_and_run(args)
    assert result["ok"] is False and result["error"].startswith("stopped part way: ")
    assert result["done"] == ["setting ssl of example.com to strict"]
    assert [s["path"] for s in fake.sends()] == [f"{SETTING}/ssl", f"{SETTING}/http3"]   # ipv6 never sent


def test_the_first_setting_refused_changes_nothing_and_an_unknown_outcome_is_never_repeated(fake, monkeypatch):
    zone_now(fake, ssl="full", http3="off")
    args = settings(("ssl", "strict"), ("http3", "on"))
    failing(fake, monkeypatch, "/settings/ssl", {"ok": False, "kind": "forbidden", "status": 403,
                                                 "error": "10000: Authentication error"})
    _, _, result = approve_and_run(args)
    assert result["error"].startswith("not done: ") and "nothing was changed" in result["error"]
    assert len(fake.sends()) == 1
    fake.requests.clear()
    failing(fake, monkeypatch, "/settings/http3", {"ok": False, "kind": "api", "status": 502, "error": "bad gateway"})
    _, _, result = approve_and_run(args, call_id="call-2")
    assert result["uncertain"] is True and result["done"] == ["setting ssl of example.com to strict"]
    assert len(fake.sends()) == 2


def test_a_setting_changed_after_the_batch_card_sends_nothing(fake):
    zone_now(fake, ssl="full", http3="off")
    args = settings(("ssl", "strict"), ("http3", "on"))
    cfa.approval_request(args, call_id="call-1", can_write=True)
    zone_now(fake, http3="on")
    assert "not done" in cfa.execute(args, call_id="call-1", can_write=True)["error"]
    zone_now(fake, http3="off")
    cfa.approval_request(args, call_id="call-2", can_write=True)
    fake.fingerprint = "e" * 12
    assert "changed before the write ran" in cfa.execute(args, call_id="call-2", can_write=True)["error"]
    assert fake.sends() == []


def test_settings_that_cannot_all_be_shown_are_refused(fake, monkeypatch):
    zone_now(fake, **{name: values[0] for name, values in cfa.SETTING_VALUES.items()})
    pairs = [(name, values[-1]) for name, values in cfa.SETTING_VALUES.items()]
    monkeypatch.setattr(cfa.cards, "platform", lambda: "discord")
    with pytest.raises(cfa.CloudflareError, match="send fewer changes"):
        cfa.approval_request(settings(*pairs), can_write=True)


# --- email_rule: several rules, one card ---------------------------------------------------------

def test_a_list_of_one_rule_is_the_single_form(mail):
    plain = cfa.write_plan(rule(op="update", id="a" * 32, enabled=False))
    listed = cfa.write_plan({"action": "email_rule", "zone": "example.com",
                             "rules": [{"op": "update", "id": "a" * 32, "enabled": False}]})
    assert cfa.card(plain) == cfa.card(listed) and cfa.digest(plain) == cfa.digest(listed)
    assert listed["each"] is False and listed["effect"] == plain["effect"]


def rules(*items, **extra):
    return {"action": "email_rule", "zone": "example.com", "rules": list(items), **extra}


def test_rules_go_out_in_order_on_one_card_and_a_standing_key_never_covers_them(mail):
    second = "b" * 32
    mail.answers[f"{RULES}/{second}"] = envelope({**RULE, "id": second, "name": "info", "matchers": [
        {"type": "literal", "field": "to", "value": "info@example.com"}]})
    args = rules({"op": "add", "to": "jobs", "forward": "owner@example.net"},
                 {"op": "update", "id": second, "drop": True},
                 {"op": "add", "to": "press", "drop": True, "name": "press desk"})
    card, key, result = approve_and_run(args)
    assert card.startswith("Cloudflare · Change e-mail rules\n⚠️ Mail to the addresses goes where the rules say\n")
    assert ("+ jobs@example.com → forward owner@example.net\n~ info@example.com: forward owner@example.net → drop\n"
            "+ press@example.com → drop") in card
    assert "+ press@example.com → drop, name press desk\n" + cfa.ONE_BY_ONE in card and "name: press desk" not in card
    assert key.startswith("cloudflare-access:email_rule:") and key == cfa.approval_request(
        args, call_id="again", can_write=True)[1]
    assert [(s["method"], s["path"]) for s in mail.sends()] == [("POST", RULES), ("PUT", f"{RULES}/{second}"),
                                                                ("POST", RULES)]
    assert result["ok"] is True and len(result["done"]) == 3 and len(result["result"]) == 3


@pytest.mark.parametrize("last, marker", [
    ({"op": "delete", "id": "a" * 32}, "- sales@example.com → forward owner@example.net"),
    ({"op": "catch_all", "forward": "owner@example.net", "enabled": True}, "~ catch-all: drop → forward"),
])
def test_one_deleted_rule_or_changed_catch_all_in_a_batch_asks_every_time(mail, last, marker):
    args = rules({"op": "add", "to": "jobs", "drop": True}, last)
    card, key = cfa.approval_request(args, call_id="a", can_write=True)
    assert card.startswith("Cloudflare · Change e-mail rules\n🚨 A rule is deleted or the catch-all changes")
    assert marker in card
    assert key != cfa.approval_request(args, call_id="b", can_write=True)[1]


@pytest.mark.parametrize("args, message", [
    (rules(), "rules must be a list of 1 to 20"),
    ({**rules({"op": "delete", "id": "a" * 32}), "op": "add"}, "not both"),
    ({"action": "email_rule", "zone": "example.com", "rules": {"op": "add"}}, "rules must be a list"),
    (rules({"op": "update", "id": "a" * 32, "drop": True}, {"op": "delete", "id": "a" * 32}), "only once in one call"),
    (rules({"op": "catch_all", "drop": True}, {"op": "catch_all", "enabled": False}), "only once in one call"),
    (rules({"op": "add", "to": "jobs", "drop": True}, {"op": "rename"}), "rule 2: op must be one of"),
    (rules({"op": "add", "to": "jobs", "drop": True, "zone": "x"}), "rule 1: does not take zone"),
    (rules("add"), "rule 1: needs op"),
    (rules({"op": "add", "to": "jobs", "drop": True}, {"op": "delete"}), "rule 2: delete needs id"),
])
def test_a_rules_list_that_cannot_be_planned_is_refused_before_any_read(mail, args, message):
    with pytest.raises(cfa.CloudflareError, match=message):
        cfa.approval_request(args, can_write=True)
    assert mail.requests == []


def test_too_many_rules_are_refused(mail):
    many = [{"op": "add", "to": f"box{n}", "drop": True} for n in range(cfa.CHANGES_MAX + 1)]
    with pytest.raises(cfa.CloudflareError, match="1 to 20 rules"):
        cfa.approval_request(rules(*many), can_write=True)
    assert mail.requests == []


def test_a_rule_that_would_fail_refuses_the_whole_batch(mail):
    with pytest.raises(cfa.CloudflareError, match="rule 2: .*not a verified destination"):
        cfa.approval_request(rules({"op": "add", "to": "jobs", "drop": True},
                                   {"op": "add", "to": "info", "forward": "new@example.net"}), can_write=True)
    with pytest.raises(cfa.CloudflareError, match="rule 2: the change moves nothing"):
        cfa.approval_request(rules({"op": "add", "to": "jobs", "drop": True},
                                   {"op": "update", "id": "a" * 32, "enabled": True}), can_write=True)
    assert mail.sends() == []


@pytest.fixture
def second_rule(mail):
    mail.answers[f"{RULES}/{'b' * 32}"] = envelope({**RULE, "id": "b" * 32, "name": "info", "matchers": [
        {"type": "literal", "field": "to", "value": "info@example.com"}]})
    return mail


@pytest.mark.parametrize("items", [
    [{"op": "add", "to": "jobs", "drop": True}, {"op": "add", "to": "jobs", "forward": "owner@example.net"}],
    [{"op": "add", "to": "jobs", "drop": True}, {"op": "add", "to": "JOBS@example.com", "drop": True}],
    [{"op": "add", "to": "jobs", "drop": True}, {"op": "update", "id": "b" * 32, "to": "jobs", "drop": True}],
    [{"op": "update", "id": "b" * 32, "to": "jobs", "drop": True}, {"op": "add", "to": "jobs", "drop": True}],
    [{"op": "update", "id": "a" * 32, "to": "jobs", "enabled": False},
     {"op": "update", "id": "b" * 32, "to": "jobs", "drop": True}],
])
def test_two_rules_for_one_address_in_a_list_are_refused_before_any_send(second_rule, items):
    with pytest.raises(cfa.CloudflareError, match="rule 2: jobs@example.com already gets a rule in this call"):
        cfa.approval_request(rules(*items), can_write=True)
    assert second_rule.sends() == [] and cfa._approved == {}


def test_deleting_a_rule_and_adding_one_for_its_address_is_a_replace_not_a_repeat(second_rule):
    args = rules({"op": "delete", "id": "a" * 32}, {"op": "add", "to": "sales", "drop": True})
    card, _ = cfa.approval_request(args, call_id="r", can_write=True)
    assert "- sales@example.com → forward owner@example.net\n+ sales@example.com → drop" in card


@pytest.mark.parametrize("items", [
    [{"op": "delete", "id": "a" * 32}, {"op": "delete", "id": "b" * 32}],
    [{"op": "update", "id": "a" * 32, "enabled": False}, {"op": "update", "id": "b" * 32, "enabled": False}],
])
def test_rules_that_name_no_new_address_are_not_repeats(second_rule, items):
    card, _ = cfa.approval_request(rules(*items), call_id="r", can_write=True)
    assert "sales@example.com" in card and "info@example.com" in card


def test_the_order_note_is_a_line_of_a_list_and_a_single_rule_keeps_its_details(mail):
    plan = cfa.write_plan(rules({"op": "add", "to": "jobs", "drop": True, "name": "jobs desk"},
                                {"op": "add", "to": "press", "drop": True}))
    assert plan["lines"][-1] == cfa.ONE_BY_ONE and cfa.ONE_BY_ONE not in plan["details"] and plan["details"] == []
    assert plan["lines"][0] == "+ jobs@example.com → drop, name jobs desk"
    single = cfa.write_plan(rule(op="add", to="jobs", drop=True, name="jobs desk"))
    assert single["lines"] == ["+ jobs@example.com → drop"] and single["details"] == ["name: jobs desk"]


def test_a_card_that_cannot_show_every_rule_is_refused(mail):
    many = [{"op": "add", "to": f"mailbox-number-{n}", "drop": True} for n in range(12)]
    with pytest.raises(cfa.CloudflareError, match="send fewer changes"):
        cfa.approval_request(rules(*many), can_write=True)


def test_rules_are_previewed_without_sending(mail):
    args = rules({"op": "add", "to": "jobs", "drop": True}, {"op": "delete", "id": "a" * 32}, preview=True)
    assert cfa.approval_request(args, can_write=True) is None
    result = cfa.execute(args, can_write=True)
    assert result["preview"] is True and result["requests"] == 2 and mail.sends() == []
    assert "+ jobs@example.com → drop\n- sales@example.com" in result["card"]


def test_a_rule_refused_part_way_stops_the_rest_and_reports_what_was_done(mail, monkeypatch):
    args = rules({"op": "add", "to": "jobs", "drop": True}, {"op": "update", "id": "a" * 32, "enabled": False},
                 {"op": "add", "to": "press", "drop": True})
    failing(mail, monkeypatch, f"{RULES}/{'a' * 32}", {"ok": False, "kind": "invalid", "status": 400,
                                                       "error": "2002: bad rule"})
    _, _, result = approve_and_run(args)
    assert result["ok"] is False and result["error"].startswith("stopped part way: ")
    assert result["done"] == ["adding a rule for jobs@example.com"]
    assert len(mail.sends()) == 2   # the third never went out
    mail.requests.clear()
    failing(mail, monkeypatch, RULES, {"ok": False, "kind": "network", "error": "the connection broke off"})
    _, _, result = approve_and_run(args, call_id="call-2")
    assert result["uncertain"] is True and result["done"] == [] and len(mail.sends()) == 1


def test_a_rule_changed_after_the_batch_card_sends_nothing(mail):
    args = rules({"op": "add", "to": "jobs", "drop": True}, {"op": "update", "id": "a" * 32, "enabled": False})
    cfa.approval_request(args, call_id="call-1", can_write=True)
    mail.answers[f"{RULES}/{'a' * 32}"] = envelope({**RULE, "name": "renamed meanwhile"})
    assert "changed before the write ran" in cfa.execute(args, call_id="call-1", can_write=True)["error"]
    assert mail.sends() == []
