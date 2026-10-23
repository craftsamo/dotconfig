import importlib.util
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import urllib.error
import urllib.parse

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("cloudflare_access_bridge_test", ROOT / "bridge.py")
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)

USER_TOKEN = "cfut_" + "a1B2" * 10 + "c3d4e5"
ACCOUNT_TOKEN = "cfat_" + "Zz9_" * 10 + "f6a7b8"
LEGACY_TOKEN = "Ab3-" * 10
ACCOUNT = "0123456789abcdef0123456789abcdef"
OTHER_ACCOUNT = "fedcba9876543210fedcba9876543210"
ZONE = "1" * 32


def item(name: str, stage: str = "", scope: str = "cloudflare-access", **meta) -> dict:
    """One entry of `secret ls --json`."""
    return {"name": name, "project": "hermes", "scope": scope, "stage": stage, "kind": "TOKEN", "meta": meta}


def fake_secret(tmp_path: Path, values: dict, listed: list | None = None) -> Path:
    """A `secret` CLI: it lists `listed` (default: every name in `values`, stage-less in the cloudflare-access
    scope, labelled with its name after CLOUDFLARE_ in lowercase, on ACCOUNT), answers `get NAME` from
    `values` only when it is given `--scope cloudflare-access` and `--no-stage`, and logs its arguments."""
    listed = listed if listed is not None else [
        item(name, label=name.removeprefix("CLOUDFLARE_").lower(), account_id=ACCOUNT) for name in values]
    (tmp_path / "ls.json").write_text(json.dumps(listed))
    branches = "".join(f"    '{name}') printf '%s\\n' '{value}' ;;\n" for name, value in values.items())
    script = tmp_path / "secret"
    script.write_text(
        "#!/bin/sh\n"
        f"echo \"$@\" >> '{tmp_path / 'log'}'\n"
        'scope=""; nostage=""; prev=""\n'
        'for a in "$@"; do\n'
        '  [ "$prev" = "--scope" ] && scope="$a"\n'
        '  [ "$a" = "--no-stage" ] && nostage=1\n'
        '  prev="$a"\n'
        "done\n"
        'case "$1" in\n'
        f"  ls) cat '{tmp_path / 'ls.json'}' ;;\n"
        '  get) [ "$scope" = "cloudflare-access" ] && [ -n "$nostage" ] || exit 1\n'
        '    case "$2" in\n'
        f"{branches}"
        "    *) exit 1 ;;\n"
        "  esac ;;\n"
        "  *) exit 2 ;;\n"
        "esac\n")
    script.chmod(0o700)
    return script


class Reply(io.BytesIO):
    def __init__(self, status, payload, headers=None):
        super().__init__(json.dumps(payload).encode())
        self.status = status
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def ok(result=None, **extra):
    return {"success": True, "errors": [], "messages": [], "result": result, **extra}


def failed(code, message):
    return {"success": False, "errors": [{"code": code, "message": message}], "messages": [], "result": None}


ACTIVE = (200, ok({"id": "t1", "status": "active", "expires_on": "2027-01-01T00:00:00Z"}), {})


@pytest.fixture
def net(tmp_path, monkeypatch):
    """Cloudflare as a table of path -> (status, JSON, headers); records each request."""
    monkeypatch.setattr(bridge, "SECRET", fake_secret(tmp_path, {"CLOUDFLARE_WORK": USER_TOKEN}))
    bridge.SECRETS.clear()
    routes, sent = {}, []

    def open_(request, timeout):
        sent.append(request)
        path = urllib.parse.urlsplit(request.full_url).path.removeprefix("/client/v4")
        status, payload, headers = routes.get(path, (404, failed(7003, "Could not route"), {}))
        if status >= 400:
            raise urllib.error.HTTPError(request.full_url, status, "x", headers,
                                         io.BytesIO(json.dumps(payload).encode()))
        return Reply(status, payload, headers)
    monkeypatch.setattr(bridge._OPENER, "open", open_)
    return routes, sent


def call(**fields):
    return bridge.main({"op": "call", "account": "work", "method": "GET", "deadline": 30, **fields})


def gets(tmp_path):
    return [line.split() for line in (tmp_path / "log").read_text().splitlines() if line.startswith("get ")]


def test_keys_are_the_labelled_stage_less_items_of_the_scope_with_an_account(tmp_path, monkeypatch, net):
    listed = [
        item("CLOUDFLARE_WORK", label="work", account_id=ACCOUNT),
        item("cf_shop_token", label="Shop", account_id=OTHER_ACCOUNT.upper()),   # case of values is ignored
        item("CLOUDFLARE_LOCKED", label="locked", account_id=ACCOUNT),           # stored, unreadable
        item("CLOUDFLARE_STAGED", "prod", label="staged", account_id=ACCOUNT),
        item("CLOUDFLARE_NOACCOUNT", label="noaccount"),
        item("CLOUDFLARE_BADACCOUNT", label="bad", account_id="acct_123"),
        item("CLOUDFLARE_NOLABEL", account_id=ACCOUNT, url="https://dash.cloudflare.com"),
        item("CLOUDFLARE_UPPER", LABEL="upper", account_id=ACCOUNT),
        item("CLOUDFLARE_BADLABEL", label="Bad Label!", account_id=ACCOUNT),
        item("-rf", label="flag", account_id=ACCOUNT),
        item("CLOUDFLARE_OTHER", scope="another-scope", label="other", account_id=ACCOUNT),
    ]
    monkeypatch.setattr(bridge, "SECRET", fake_secret(tmp_path, {"CLOUDFLARE_WORK": USER_TOKEN,
                                                                 "cf_shop_token": ACCOUNT_TOKEN}, listed))
    reply = bridge.main({"op": "keys"})
    _, sent = net
    assert reply["ok"] is True and reply["requests"] == 0 and not sent
    entries = {e["account"]: e for e in reply["data"]}
    assert set(entries) == {"work", "shop", "locked"}
    assert entries["work"] == {"account": "work", "item": "CLOUDFLARE_WORK", "account_id": ACCOUNT, "kind": "user",
                               "fingerprint": bridge.fingerprint(f"{USER_TOKEN}|{ACCOUNT}")}
    assert entries["shop"]["kind"] == "account" and entries["shop"]["account_id"] == OTHER_ACCOUNT
    assert "CLOUDFLARE_LOCKED (label=locked) could not be read" in entries["locked"]["problem"]
    unused = {u["item"]: u["problem"] for u in reply["unused"]}
    assert set(unused) == {"CLOUDFLARE_STAGED", "CLOUDFLARE_NOACCOUNT", "CLOUDFLARE_BADACCOUNT", "CLOUDFLARE_NOLABEL",
                           "CLOUDFLARE_UPPER", "CLOUDFLARE_BADLABEL", "-rf"}
    assert "stage prod" in unused["CLOUDFLARE_STAGED"] and "--no-stage" in unused["CLOUDFLARE_STAGED"]
    assert ("no account_id= field" in unused["CLOUDFLARE_NOACCOUNT"] and "secret update CLOUDFLARE_NOACCOUNT -p hermes "
            "--scope cloudflare-access --no-stage --meta account_id=<account id>" in unused["CLOUDFLARE_NOACCOUNT"])
    assert "not a Cloudflare account id" in unused["CLOUDFLARE_BADACCOUNT"]
    assert "no label= field" in unused["CLOUDFLARE_NOLABEL"]
    assert "field LABEL= is not read" in unused["CLOUDFLARE_UPPER"]
    assert "label=Bad Label! is not a label" in unused["CLOUDFLARE_BADLABEL"]
    assert "name is not one the secret CLI takes" in unused["-rf"]
    assert USER_TOKEN not in json.dumps(reply) and ACCOUNT_TOKEN not in json.dumps(reply)


def test_a_token_is_read_from_its_exact_stage_less_layer(tmp_path, net):
    routes, _ = net
    routes["/zones"] = (200, ok([]), {})
    assert call(path="/zones")["ok"] is True
    assert gets(tmp_path) == [["get", "CLOUDFLARE_WORK", "-p", "hermes", "--scope", "cloudflare-access", "--no-stage"]]


def test_a_label_two_items_carry_is_never_guessed(tmp_path, monkeypatch, net):
    listed = [item("CLOUDFLARE_A", label="work", account_id=ACCOUNT), item("CLOUDFLARE_B", label="WORK",
                                                                            account_id=OTHER_ACCOUNT)]
    monkeypatch.setattr(bridge, "SECRET", fake_secret(tmp_path, {"CLOUDFLARE_A": USER_TOKEN,
                                                                 "CLOUDFLARE_B": ACCOUNT_TOKEN}, listed))
    reply = call(path="/zones")
    assert reply["kind"] == "setup" and not net[1] and gets(tmp_path) == []
    assert "2 items carry label=work (CLOUDFLARE_A, CLOUDFLARE_B)" in reply["error"]
    assert "secret update CLOUDFLARE_B -p hermes --scope cloudflare-access --no-stage --meta label=" in reply["error"]


def test_without_an_account_the_only_label_is_taken_and_several_are_never_guessed(tmp_path, monkeypatch, net):
    routes, _ = net
    routes["/zones"] = (200, ok([]), {})
    assert bridge.main({"op": "call", "method": "GET", "path": "/zones"})["account"] == "work"
    monkeypatch.setattr(bridge, "SECRET", fake_secret(tmp_path, {"CLOUDFLARE_WORK": USER_TOKEN,
                                                                 "CLOUDFLARE_SHOP": ACCOUNT_TOKEN}))
    reply = bridge.main({"op": "call", "method": "GET", "path": "/zones"})
    assert reply["kind"] == "setup" and "account is required: tokens are stored for shop, work" in reply["error"]
    reply = call(account="other", path="/zones")
    assert reply["kind"] == "setup" and "no token for account other" in reply["error"]
    assert "secret set CLOUDFLARE_OTHER -p hermes --scope cloudflare-access --no-stage" in reply["error"]


@pytest.mark.parametrize("value, problem", [
    ("cfk_" + "a" * 40 + "123456", "Global API Key"),
    ("0123456789abcdef0123456789abcdef01234", "Global API Key"),
    ("not a token", "not a Cloudflare API token"),
    ("cfut_short", "not a Cloudflare API token"),
])
def test_a_global_key_or_anything_but_a_token_sends_nothing(tmp_path, monkeypatch, net, value, problem):
    monkeypatch.setattr(bridge, "SECRET", fake_secret(tmp_path, {"CLOUDFLARE_WORK": value}))
    reply = call(path="/zones")
    assert reply["kind"] == "setup" and problem in reply["error"] and not net[1]
    assert value not in json.dumps(reply)


@pytest.mark.parametrize("value, kind", [(USER_TOKEN, "user"), (ACCOUNT_TOKEN, "account"), (LEGACY_TOKEN, "token")])
def test_the_token_kind_comes_from_its_prefix(tmp_path, monkeypatch, net, value, kind):
    monkeypatch.setattr(bridge, "SECRET", fake_secret(tmp_path, {"CLOUDFLARE_WORK": value}))
    assert bridge.main({"op": "key", "account": "work"})["token_kind"] == kind


def test_a_call_carries_the_token_and_fills_in_the_label_s_own_account(net):
    routes, sent = net
    routes[f"/accounts/{ACCOUNT}"] = (200, ok({"id": ACCOUNT, "name": "Work"}), {"cf-ray": "abc-NRT"})
    routes["/zones"] = (200, ok([], result_info={"page": 1}), {})
    reply = call(path="/accounts/{account}")
    assert reply["ok"] is True and reply["data"]["result"]["name"] == "Work" and reply["ray"] == "abc-NRT"
    assert reply["account_id"] == ACCOUNT and reply["item"] == "CLOUDFLARE_WORK" and reply["requests"] == 1
    assert reply["fingerprint"] == bridge.fingerprint(f"{USER_TOKEN}|{ACCOUNT}") and reply["token_kind"] == "user"
    request = sent[0]
    assert request.full_url == f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT}"
    assert request.get_header("Authorization") == f"Bearer {USER_TOKEN}" and request.data is None
    call(path="/zones", params=[["account.id", "{account}"], ["name", "example.com"], ["per_page", "20"]])
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(sent[1].full_url).query)
    assert query == {"account.id": [ACCOUNT], "name": ["example.com"], "per_page": ["20"]}
    assert USER_TOKEN not in json.dumps(reply)


@pytest.mark.parametrize("method, path", [
    ("GET", f"/accounts/{ACCOUNT}"),               # an account named outright, not the label's own
    ("GET", f"/accounts/{OTHER_ACCOUNT}/tokens/verify"),
    ("GET", "/zones/../accounts"), ("GET", "/zones/not-an-id"), ("GET", f"/zones/{ZONE}/settings/../x"),
    ("DELETE", f"/zones/{ZONE}/dns_records/{ZONE}"), ("DELETE", f"/zones/{ZONE}"), ("POST", "/zones"),
    ("GET", "/user"), ("GET", "https://evil.example/client/v4/zones"), ("TRACE", "/zones"),
])
def test_only_the_routes_in_the_table_are_called(net, method, path):
    reply = call(method=method, path=path)
    assert reply["ok"] is False and reply["requests"] == 0 and not net[1]


def test_a_malformed_parameter_or_a_body_on_a_read_never_goes_out(net):
    for params in ([["name\nInjected", "x"]], [["name", 5]], [["NAME", "x"]], "name=x"):
        reply = call(path="/zones", params=params)
        assert reply["ok"] is False and reply["requests"] == 0
    reply = call(path="/zones", body={"x": 1})
    assert reply["ok"] is False and reply["requests"] == 0 and not net[1]


def test_a_refused_token_a_pause_or_a_changed_token_is_answered_without_cloudflare(net):
    routes, sent = net
    routes["/zones"] = (200, ok([]), {})
    fingerprint = bridge.fingerprint(f"{USER_TOKEN}|{ACCOUNT}")
    reply = call(path="/zones", refused={"work": fingerprint})
    assert reply["kind"] == "refused" and reply["requests"] == 0 and not sent
    reply = call(path="/zones", paused={"work": 4102444800})
    assert reply["kind"] == "limited" and reply["requests"] == 0 and not sent
    reply = call(path="/zones", expect="000000000000")
    assert reply["kind"] == "account" and reply["requests"] == 0 and not sent
    # A refusal remembered for an older token, or a pause that ended, does not stop a call.
    assert call(path="/zones", refused={"work": "000000000000"}, paused={"work": 1})["ok"] is True


def test_the_same_token_on_another_account_is_another_fingerprint(tmp_path, monkeypatch, net):
    before = bridge.main({"op": "key", "account": "work"})["fingerprint"]
    monkeypatch.setattr(bridge, "SECRET", fake_secret(tmp_path, {"CLOUDFLARE_WORK": USER_TOKEN}, [
        item("CLOUDFLARE_WORK", label="work", account_id=OTHER_ACCOUNT)]))
    reply = call(path="/zones", expect=before)
    assert reply["kind"] == "account" and not net[1]


def test_a_forbidden_call_on_a_working_token_is_a_missing_permission(net):
    routes, sent = net
    routes[f"/zones/{ZONE}/dns_records"] = (403, failed(10000, "Authentication error"), {})
    routes["/user/tokens/verify"] = ACTIVE
    reply = call(path=f"/zones/{ZONE}/dns_records")
    assert reply["kind"] == "forbidden" and reply["token_status"] == "active" and reply["requests"] == 2
    assert reply["error"] == "10000: Authentication error" and reply["codes"] == [10000] and reply["status"] == 403


@pytest.mark.parametrize("verified", [(401, failed(1000, "Invalid API Token"), {}),
                                      (200, ok({"id": "t1", "status": "expired"}), {})])
def test_a_token_cloudflare_no_longer_takes_is_refused(net, verified):
    routes, _ = net
    routes["/zones"] = (401, failed(10000, "Authentication error"), {})
    routes["/user/tokens/verify"] = verified
    reply = call(path="/zones")
    assert reply["kind"] == "refused" and reply["token_status"] in ("invalid", "expired") and reply["requests"] == 2


def test_an_unreadable_header_is_checked_like_a_401(net):
    routes, _ = net
    routes["/zones"] = (400, failed(6003, "Invalid request headers"), {})
    routes["/user/tokens/verify"] = (400, failed(6003, "Invalid request headers"), {})
    assert call(path="/zones")["kind"] == "refused"


def test_a_failing_check_never_reads_as_a_refused_token(net):
    routes, _ = net
    routes["/zones"] = (401, failed(10000, "Authentication error"), {})
    routes["/user/tokens/verify"] = (500, failed(10001, "service unavailable"), {})
    assert call(path="/zones")["kind"] == "forbidden"


@pytest.mark.parametrize("status, kind", [(400, "invalid"), (404, "not_found"), (409, "conflict"), (500, "api"),
                                          (418, "http")])
def test_cloudflare_errors_keep_their_kind_and_codes(net, status, kind):
    routes, _ = net
    routes["/zones"] = (status, failed(1234, "explained"), {})
    reply = call(path="/zones")
    assert reply["ok"] is False and reply["kind"] == kind and reply["status"] == status and reply["requests"] == 1
    assert reply["error"] == "1234: explained" and reply["codes"] == [1234]


def test_a_rate_limit_carries_retry_after(net):
    routes, _ = net
    routes["/zones"] = (429, failed(971, "Please wait and consider throttling your request speed"),
                        {"Retry-After": "42"})
    reply = call(path="/zones")
    assert reply["kind"] == "limited" and reply["retry_after"] == 42


def test_a_2xx_without_success_is_uncertain(net):
    routes, _ = net
    routes["/zones"] = (200, {"success": False, "errors": [{"code": 1, "message": "odd"}]}, {})
    assert call(path="/zones")["kind"] == "uncertain"
    routes["/zones"] = (200, ["not", "an", "envelope"], {})
    assert call(path="/zones")["kind"] == "uncertain"


@pytest.mark.parametrize("value, first", [(USER_TOKEN, "/user/tokens/verify"),
                                          (ACCOUNT_TOKEN, f"/accounts/{ACCOUNT}/tokens/verify")])
def test_verify_asks_the_token_s_own_endpoint(tmp_path, monkeypatch, net, value, first):
    routes, sent = net
    monkeypatch.setattr(bridge, "SECRET", fake_secret(tmp_path, {"CLOUDFLARE_WORK": value}))
    routes[first] = ACTIVE
    reply = bridge.main({"op": "verify", "account": "work"})
    assert reply["ok"] is True and reply["verify"]["status"] == "active" and reply["requests"] == 1
    assert reply["verify"]["expires_on"] == "2027-01-01T00:00:00Z"
    assert [urllib.parse.urlsplit(r.full_url).path.removeprefix("/client/v4") for r in sent] == [first]


def test_verify_tries_both_endpoints_for_a_token_without_a_prefix(tmp_path, monkeypatch, net):
    routes, sent = net
    monkeypatch.setattr(bridge, "SECRET", fake_secret(tmp_path, {"CLOUDFLARE_WORK": LEGACY_TOKEN}))
    routes["/user/tokens/verify"] = (401, failed(1000, "Invalid API Token"), {})
    routes[f"/accounts/{ACCOUNT}/tokens/verify"] = ACTIVE
    reply = bridge.main({"op": "verify", "account": "work"})
    assert reply["ok"] is True and reply["verify"]["owner"] == "account" and reply["requests"] == 2


def test_verify_asks_even_for_a_token_remembered_as_refused(net):
    routes, sent = net
    routes["/user/tokens/verify"] = (200, ok({"id": "t1", "status": "disabled"}), {})
    fingerprint = bridge.fingerprint(f"{USER_TOKEN}|{ACCOUNT}")
    reply = bridge.main({"op": "verify", "account": "work", "refused": {"work": fingerprint}})
    assert reply["ok"] is False and reply["kind"] == "refused" and reply["token_status"] == "disabled" and sent


def test_reads_run_in_order_under_one_token_read_and_stop_at_a_rate_limit(tmp_path, net):
    routes, sent = net
    routes[f"/zones/{ZONE}/settings/ssl"] = (200, ok({"id": "ssl", "value": "strict"}), {})
    routes[f"/zones/{ZONE}/settings/http3"] = (404, failed(1003, "Invalid or missing zone setting"), {})
    routes[f"/zones/{ZONE}/settings/ipv6"] = (429, failed(971, "slow down"), {"Retry-After": "5"})
    requests = [{"path": f"/zones/{ZONE}/settings/{name}", "params": []} for name in ("ssl", "http3", "ipv6", "brotli")]
    reply = bridge.main({"op": "reads", "account": "work", "requests": requests, "deadline": 30})
    assert reply["ok"] is False and reply["kind"] == "limited" and reply["retry_after"] == 5
    assert reply["requests"] == 3 and len(sent) == 3 and len(gets(tmp_path)) == 1
    first, second, third = reply["results"]
    assert first["ok"] is True and first["data"]["result"]["value"] == "strict"
    assert second["kind"] == "not_found" and third["kind"] == "limited"
    assert "fingerprint" not in first and reply["fingerprint"]


def test_reads_takes_a_bounded_list_of_reads_only(net):
    assert bridge.main({"op": "reads", "account": "work", "requests": []})["ok"] is False
    too_many = [{"path": "/zones", "params": []}] * (bridge.READS_MAX + 1)
    assert bridge.main({"op": "reads", "account": "work", "requests": too_many})["ok"] is False
    reply = bridge.main({"op": "reads", "account": "work", "requests": [{"path": f"/zones/{ZONE}/purge_cache"}]})
    assert reply["results"][0]["ok"] is False and reply["requests"] == 0 and not net[1]


def graphql(**fields):
    return bridge.main({"op": "graphql", "account": "work", "deadline": 30, **fields})


SPAN = {"since": "2026-10-01T00:00:00Z", "until": "2026-10-02T00:00:00Z"}


def test_an_analytics_query_is_one_of_the_fixed_ones_with_the_label_s_account(net):
    routes, sent = net
    routes["/graphql"] = (200, {"data": {"viewer": {"accounts": [{"workersInvocationsAdaptive": []}]}},
                                "errors": None}, {})
    reply = graphql(query="worker", variables={**SPAN, "scriptName": "api-worker"})
    assert reply["ok"] is True and reply["data"]["data"]["viewer"]["accounts"] == [{"workersInvocationsAdaptive": []}]
    [request] = sent
    body = json.loads(request.data)
    assert request.get_method() == "POST" and request.full_url == "https://api.cloudflare.com/client/v4/graphql"
    assert body == {"query": bridge.QUERIES["worker"][1],
                    "variables": {"accountTag": ACCOUNT, **SPAN, "scriptName": "api-worker"}}


@pytest.mark.parametrize("query, variables", [
    ("mutation", {}),                                                       # not a query of the table
    ("traffic", {"zoneTag": ZONE, "since": "2026-10-01"}),                  # a variable missing
    ("traffic", {"zoneTag": ZONE, "since": "2026-10-01", "until": "2026-10-07", "extra": "x"}),
    ("traffic", {"zoneTag": "example.com", "since": "2026-10-01", "until": "2026-10-07"}),
    ("paths", {"zoneTag": ZONE, "since": "2026-10-01", "until": "2026-10-02"}),   # dates where times go
    ("worker", {**SPAN, "scriptName": "a b"}),
    ("workers", {**SPAN, "accountTag": OTHER_ACCOUNT}),                    # the account is never the caller's
])
def test_an_analytics_query_outside_the_table_or_its_kinds_never_goes_out(net, query, variables):
    reply = graphql(query=query, variables=variables)
    assert reply["ok"] is False and reply["requests"] == 0 and not net[1]


def test_the_analytics_endpoint_is_not_a_route_for_any_body(net):
    reply = call(method="POST", path="/graphql", body={"query": "{ viewer { zones { zoneTag } } }"})
    assert reply["ok"] is False and reply["requests"] == 0 and not net[1]


def test_analytics_errors_on_a_200_are_a_failure(net):
    routes, _ = net
    routes["/graphql"] = (200, {"data": None, "errors": [{"message": "cannot request data older than 31d",
                                                          "path": ["viewer"]}]}, {})
    reply = graphql(query="traffic", variables={"zoneTag": ZONE, "since": "2025-01-01", "until": "2025-01-07"})
    assert reply["kind"] == "graphql" and "older than 31d" in reply["error"]


def test_a_forbidden_analytics_query_is_checked_like_any_call(net):
    routes, _ = net
    routes["/graphql"] = (403, {"errors": [{"message": "not authorized"}]}, {})
    routes["/user/tokens/verify"] = ACTIVE
    reply = graphql(query="traffic", variables={"zoneTag": ZONE, "since": "2026-10-01", "until": "2026-10-07"})
    assert reply["kind"] == "forbidden" and reply["requests"] == 2


DB = "0f0e0d0c-0b0a-4908-8706-050403020100"


def test_the_d1_query_route_sends_only_the_fixed_schema_read(net):
    routes, sent = net
    path = f"/accounts/{{account}}/d1/database/{DB}/query"
    routes[f"/accounts/{ACCOUNT}/d1/database/{DB}/query"] = (200, ok([{"results": [], "success": True}]), {})
    assert call(method="POST", path=path)["ok"] is True
    assert json.loads(sent[0].data) == {"sql": bridge.SCHEMA_SQL} and bridge.SCHEMA_SQL.startswith("SELECT ")
    reply = call(method="POST", path=path, body={"sql": "DROP TABLE users"})
    assert reply["ok"] is False and reply["requests"] == 0 and len(sent) == 1


def test_the_schema_read_leaves_out_only_sqlite_s_and_d1_s_own_objects():
    db = sqlite3.connect(":memory:")
    for table in ("users", "acf_users", "xcf_log", "sqliteish", "_cf_KV"):
        db.execute(f'CREATE TABLE "{table}" (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE)')
    db.execute("CREATE INDEX users_email ON users(email)")
    names = {row[1] for row in db.execute(bridge.SCHEMA_SQL)}
    db.close()
    assert names == {"users", "acf_users", "xcf_log", "sqliteish", "users_email"}


@pytest.mark.parametrize("path", [
    "/accounts/{account}/r2/buckets/media/objects/photo.jpg",          # an object's content
    "/accounts/{account}/storage/kv/namespaces/" + "a" * 32 + "/values/key",
    f"/accounts/{{account}}/d1/database/{DB}/raw",
    f"/accounts/{{account}}/d1/database/{DB}/export",
    "/accounts/{account}/r2/buckets/A_Bucket/objects",
])
def test_storage_contents_are_not_routes(net, path):
    for method in ("GET", "POST"):
        reply = call(method=method, path=path)
        assert reply["ok"] is False and reply["requests"] == 0
    assert not net[1]


def test_a_token_echoed_by_cloudflare_never_leaves(net):
    routes, _ = net
    routes["/zones"] = (400, failed(9999, f"bad header Bearer {USER_TOKEN} and cfat_somethingelse"), {})
    reply = call(path="/zones")
    assert USER_TOKEN not in json.dumps(reply) and "cfat_" not in json.dumps(reply)


@pytest.mark.parametrize("offset", [150, 161, 170, 199])
def test_a_token_without_a_prefix_is_masked_before_a_message_is_cut(tmp_path, monkeypatch, net, offset):
    routes, _ = net
    monkeypatch.setattr(bridge, "SECRET", fake_secret(tmp_path, {"CLOUDFLARE_WORK": LEGACY_TOKEN}))
    routes["/zones"] = (400, failed(9999, "a" * offset + LEGACY_TOKEN + " trailing"), {})
    text = json.dumps(call(path="/zones"))
    assert not any(LEGACY_TOKEN[i:i + 12] in text for i in range(len(LEGACY_TOKEN) - 11))


def test_an_answer_too_large_is_not_read(net, monkeypatch):
    routes, _ = net
    monkeypatch.setattr(bridge, "REPLY_MAX", 64)
    routes["/zones"] = (200, ok(["x" * 100]), {})
    reply = call(path="/zones")
    assert reply["ok"] is False and reply["kind"] == "uncertain" and "too large" in reply["error"]


def test_a_rate_limit_met_by_the_check_is_a_rate_limit(net):
    routes, sent = net
    routes["/zones"] = (403, failed(10000, "Authentication error"), {})
    routes["/user/tokens/verify"] = (429, failed(971, "slow down"), {"Retry-After": "30"})
    reply = call(path="/zones")
    assert reply["kind"] == "limited" and reply["retry_after"] == 30 and reply["requests"] == 2
    requests = [{"path": "/zones", "params": []}, {"path": f"/zones/{ZONE}", "params": []}]
    reply = bridge.main({"op": "reads", "account": "work", "requests": requests})
    assert reply["kind"] == "limited" and len(reply["results"]) == 1


def test_verify_holds_to_a_pause(net):
    reply = bridge.main({"op": "verify", "account": "work", "paused": {"work": 4102444800}})
    assert reply["kind"] == "limited" and reply["requests"] == 0 and not net[1]


def test_a_redirect_is_not_followed(net, monkeypatch):
    def redirect(request, timeout):
        raise bridge.Failure("Cloudflare answered with a redirect (302); not followed", "error", 302)
    monkeypatch.setattr(bridge._OPENER, "open", redirect)
    assert call(path="/zones")["error"].startswith("Cloudflare answered with a redirect")
    with pytest.raises(bridge.Failure):
        bridge._CloudflareOnly().redirect_request(None, None, 302, "Found", {}, "https://elsewhere.example/")


def test_a_network_failure_is_reported_after_the_request_left(net, monkeypatch):
    def broken(request, timeout):
        raise urllib.error.URLError(ConnectionResetError("reset"))
    monkeypatch.setattr(bridge._OPENER, "open", broken)
    reply = call(path="/zones")
    assert reply["kind"] == "network" and reply["requests"] == 1


def test_an_unexpected_failure_after_sending_counts_as_sent(net, monkeypatch):
    def odd(request, timeout):
        raise ValueError(f"odd {USER_TOKEN}")
    monkeypatch.setattr(bridge._OPENER, "open", odd)
    reply = call(path="/zones")
    assert reply["kind"] == "error" and reply["requests"] == 1 and USER_TOKEN not in reply["error"]


@pytest.mark.parametrize("account", ["Work!", "../x", "a" * 30])
def test_a_malformed_account_label_is_refused(net, account):
    assert call(account=account, path="/zones")["kind"] == "setup" and not net[1]


def test_the_bridge_runs_isolated_and_answers_json_only():
    env = {"HOME": "/nonexistent", "PATH": "/usr/bin:/bin"}
    proc = subprocess.run([sys.executable, "-I", str(ROOT / "bridge.py")], input=json.dumps({"op": "nope"}),
                          capture_output=True, text=True, timeout=30, env=env)
    reply = json.loads(proc.stdout)
    assert reply["ok"] is False and "unknown op" in reply["error"] and proc.stderr == ""
    proc = subprocess.run([sys.executable, "-I", str(ROOT / "bridge.py")], input="not json", capture_output=True,
                          text=True, timeout=30, env=env)
    assert json.loads(proc.stdout)["ok"] is False
