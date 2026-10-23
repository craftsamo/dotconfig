import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import urllib.error
import urllib.parse

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("stripe_access_bridge_test", ROOT / "bridge.py")
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)

TEST_KEY = "sk_test_" + "a1" * 12
LIVE_KEY = "rk_live_" + "b2" * 12


def fake_secret(tmp_path: Path, values: dict, listed: list | None = None) -> Path:
    """A `secret` CLI that lists `listed` (default: every name in `values`, in the stripe-access scope),
    answers `get` from `values` and logs its arguments."""
    listed = listed if listed is not None else [
        {"name": name, "project": "hermes", "scope": "stripe-access", "stage": "", "kind": "TOKEN"} for name in values]
    (tmp_path / "ls.json").write_text(json.dumps(listed))
    branches = "".join(f"    {name}) printf '%s\\n' '{value}' ;;\n" for name, value in values.items())
    script = tmp_path / "secret"
    script.write_text(
        "#!/bin/sh\n"
        f"echo \"$@\" >> '{tmp_path / 'log'}'\n"
        'case "$1" in\n'
        f"  ls) cat '{tmp_path / 'ls.json'}' ;;\n"
        '  get) case "$2" in\n'
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


@pytest.fixture
def net(tmp_path, monkeypatch):
    """Stripe as a table of path -> (status, JSON, headers); records each request."""
    monkeypatch.setattr(bridge, "SECRET", fake_secret(tmp_path, {"STRIPE_KEY_WORK_TEST": TEST_KEY,
                                                                 "STRIPE_KEY_WORK_LIVE": LIVE_KEY}))
    bridge.SECRETS.clear()
    routes, sent = {}, []

    def open_(request, timeout):
        sent.append(request)
        path = urllib.parse.urlsplit(request.full_url).path
        status, payload, headers = routes.get(path, (404, {"error": {"type": "invalid_request_error",
                                                                     "message": "No such thing"}}, {}))
        if status >= 400:
            raise urllib.error.HTTPError(request.full_url, status, "x", headers,
                                         io.BytesIO(json.dumps(payload).encode()))
        return Reply(status, payload, headers)
    monkeypatch.setattr(bridge._OPENER, "open", open_)
    return routes, sent


def call(**fields):
    return bridge.main({"op": "call", "mode": "test", "account": "work", "method": "GET", "deadline": 30, **fields})


def test_keys_lists_the_scope_and_reads_kinds_without_contacting_stripe(tmp_path, monkeypatch, net):
    listed = [
        {"name": "STRIPE_KEY_WORK_TEST", "scope": "stripe-access", "stage": ""},
        {"name": "STRIPE_KEY_WORK_LIVE", "scope": "stripe-access", "stage": ""},
        {"name": "STRIPE_KEY_SHOP_2_LIVE", "scope": "stripe-access", "stage": ""},   # stored, unreadable
        {"name": "STRIPE_KEY_OTHER_LIVE", "scope": "another-scope", "stage": ""},
        {"name": "STRIPE_KEY_STAGED_LIVE", "scope": "stripe-access", "stage": "prod"},
        {"name": "UNRELATED", "scope": "stripe-access", "stage": ""},
    ]
    monkeypatch.setattr(bridge, "SECRET", fake_secret(tmp_path, {"STRIPE_KEY_WORK_TEST": TEST_KEY,
                                                                 "STRIPE_KEY_WORK_LIVE": LIVE_KEY}, listed))
    reply = bridge.main({"op": "keys"})
    _, sent = net
    assert reply["ok"] is True and reply["requests"] == 0 and not sent
    entries = {(e["account"], e["mode"]): e for e in reply["data"]}
    assert set(entries) == {("work", "test"), ("work", "live"), ("shop_2", "live")}
    assert entries[("work", "test")]["kind"] == "secret" and len(entries[("work", "test")]["fingerprint"]) == 12
    assert entries[("work", "live")]["kind"] == "restricted"
    assert "secret set STRIPE_KEY_SHOP_2_LIVE -p hermes --scope stripe-access" in entries[("shop_2", "live")]["problem"]
    assert TEST_KEY not in json.dumps(reply) and LIVE_KEY not in json.dumps(reply)


def test_a_get_is_pinned_authorized_and_encoded(net):
    routes, sent = net
    routes["/v1/customers"] = (200, {"object": "list", "data": [], "has_more": False}, {"Request-Id": "req_1"})
    reply = call(path="/v1/customers", params=[["email", "a+b@example.com"], ["created[gte]", "1700000000"],
                                               ["expand[]", "data.x"]])
    assert reply["ok"] is True and reply["requests"] == 1 and reply["account"] == "work"
    assert reply["request_id"] == "req_1" and reply["key_kind"] == "secret"
    request = sent[0]
    assert request.get_method() == "GET" and urllib.parse.urlsplit(request.full_url).hostname == "api.stripe.com"
    assert request.get_header("Authorization") == f"Bearer {TEST_KEY}"
    assert request.get_header("Stripe-version") == bridge.VERSION == "2026-09-30.endive"
    query = urllib.parse.parse_qsl(urllib.parse.urlsplit(request.full_url).query)
    assert query == [("email", "a+b@example.com"), ("created[gte]", "1700000000"), ("expand[]", "data.x")]
    assert request.data is None


def test_the_key_never_leaves_even_when_stripe_echoes_it(net):
    routes, _ = net
    routes["/v1/balance"] = (401, {"error": {"type": "invalid_request_error",
                                             "message": f"Invalid API Key provided: {TEST_KEY}"}}, {})
    reply = call(path="/v1/balance")
    assert reply["ok"] is False and reply["kind"] == "refused" and reply["requests"] == 1
    assert TEST_KEY not in json.dumps(reply) and "sk_test_" not in reply["error"]


def test_a_key_of_the_other_mode_is_never_used(tmp_path, monkeypatch, net):
    _, sent = net
    monkeypatch.setattr(bridge, "SECRET", fake_secret(tmp_path, {"STRIPE_KEY_WORK_TEST": "sk_live_" + "c3" * 12}))
    reply = call(path="/v1/balance")
    assert reply["ok"] is False and reply["kind"] == "setup" and "holds a live key, not a test one" in reply["error"]
    assert not sent and "c3c3" not in json.dumps(reply)


@pytest.mark.parametrize("value, message", [
    ("pk_test_" + "d4" * 12, "publishable key"),
    ("not a key", "not a Stripe secret or restricted key"),
])
def test_a_key_that_is_not_a_secret_key_is_a_setup_problem(tmp_path, monkeypatch, net, value, message):
    monkeypatch.setattr(bridge, "SECRET", fake_secret(tmp_path, {"STRIPE_KEY_WORK_TEST": value}))
    reply = call(path="/v1/balance")
    assert reply["kind"] == "setup" and message in reply["error"] and not net[1]


def test_a_missing_key_names_the_command_that_stores_it(net):
    reply = call(account="shop", path="/v1/balance")
    assert reply["kind"] == "setup" and reply["requests"] == 0
    assert "secret set STRIPE_KEY_SHOP_TEST -p hermes --scope stripe-access -D TOKEN --no-env" in reply["error"]


def test_without_an_account_the_only_label_of_the_mode_is_used(tmp_path, monkeypatch, net):
    routes, _ = net
    routes["/v1/balance"] = (200, {"object": "balance"}, {})
    assert call(account=None, path="/v1/balance")["account"] == "work"
    monkeypatch.setattr(bridge, "SECRET", fake_secret(tmp_path, {"STRIPE_KEY_WORK_TEST": TEST_KEY,
                                                                 "STRIPE_KEY_SHOP_TEST": "sk_test_" + "e5" * 12}))
    reply = call(account=None, path="/v1/balance")
    assert reply["kind"] == "setup" and "account is required" in reply["error"] and "shop, work" in reply["error"]
    reply = call(account=None, mode="live", path="/v1/balance")
    assert reply["kind"] == "setup" and "no live key is stored" in reply["error"]


@pytest.mark.parametrize("account", ["Work!", "../x", "a" * 30])
def test_a_malformed_account_label_is_refused(net, account):
    assert call(account=account, path="/v1/balance")["kind"] == "setup" and not net[1]


@pytest.mark.parametrize("method, path", [
    ("GET", "/v1/charges/../account"), ("GET", "/v2/core/accounts"), ("POST", "/v1/customers"),
    ("DELETE", "/v1/customers/cus_1"), ("GET", "/v1/files"), ("GET", "https://evil.example/v1/account"),
])
def test_only_the_routes_in_the_table_are_called(net, method, path):
    reply = call(method=method, path=path)
    assert reply["ok"] is False and reply["requests"] == 0 and not net[1]


def test_a_malformed_parameter_never_goes_out(net):
    reply = call(path="/v1/customers", params=[["email\nInjected", "x"]])
    assert reply["ok"] is False and reply["requests"] == 0 and not net[1]
    reply = call(path="/v1/customers", params=[["email", 5]])
    assert reply["ok"] is False and reply["requests"] == 0 and not net[1]


def test_a_refused_key_or_a_pause_is_answered_without_stripe(net):
    routes, sent = net
    routes["/v1/balance"] = (200, {"object": "balance"}, {})
    fingerprint = bridge.fingerprint(TEST_KEY)
    reply = call(path="/v1/balance", refused={"work/test": fingerprint})
    assert reply["kind"] == "refused" and reply["requests"] == 0 and not sent
    reply = call(path="/v1/balance", paused={"work/test": 4102444800})
    assert reply["kind"] == "limited" and reply["requests"] == 0 and not sent
    # A refusal remembered for an older key, or a pause that ended, does not stop a call.
    assert call(path="/v1/balance", refused={"work/test": "000000000000"}, paused={"work/test": 1})["ok"] is True


def test_a_key_changed_since_the_card_sends_nothing(net):
    reply = call(path="/v1/balance", expect="000000000000")
    assert reply["kind"] == "account" and reply["requests"] == 0 and not net[1]


@pytest.mark.parametrize("status, kind", [(400, "invalid"), (401, "refused"), (402, "invalid"), (403, "forbidden"),
                                          (404, "not_found"), (409, "conflict"), (429, "limited"), (500, "api"),
                                          (418, "http")])
def test_stripe_errors_keep_their_kind_and_detail(net, status, kind):
    routes, _ = net
    routes["/v1/invoices"] = (status, {"error": {"type": "invalid_request_error", "code": "c", "param": "status",
                                                 "message": "explained"}}, {"Stripe-Should-Retry": "false"})
    reply = call(path="/v1/invoices")
    assert reply["ok"] is False and reply["kind"] == kind and reply["status"] == status and reply["requests"] == 1
    assert reply["error"] == "explained" and reply["param"] == "status" and reply["code"] == "c"
    assert reply["should_retry"] == "false"


def test_an_idempotency_error_is_its_own_kind(net):
    routes, _ = net
    routes["/v1/invoices"] = (400, {"error": {"type": "idempotency_error", "message": "reused"}}, {})
    assert call(path="/v1/invoices")["kind"] == "idempotency"


def test_a_redirect_is_not_followed(net, monkeypatch):
    def redirect(request, timeout):
        raise bridge.Failure("Stripe answered with a redirect (302); not followed", "error", 302)
    monkeypatch.setattr(bridge._OPENER, "open", redirect)
    assert call(path="/v1/balance")["error"].startswith("Stripe answered with a redirect")
    handler = bridge._StripeOnly()
    with pytest.raises(bridge.Failure):
        handler.redirect_request(None, None, 302, "Found", {}, "https://elsewhere.example/")


def test_a_network_failure_is_reported_after_the_request_left(net, monkeypatch):
    def broken(request, timeout):
        raise urllib.error.URLError(ConnectionResetError("reset"))
    monkeypatch.setattr(bridge._OPENER, "open", broken)
    reply = call(path="/v1/balance")
    assert reply["kind"] == "network" and reply["requests"] == 1


def test_an_unexpected_failure_after_sending_counts_as_sent(net, monkeypatch):
    def odd(request, timeout):
        raise ValueError(f"odd {TEST_KEY}")
    monkeypatch.setattr(bridge._OPENER, "open", odd)
    reply = call(path="/v1/balance")
    assert reply["kind"] == "error" and reply["requests"] == 1 and TEST_KEY not in reply["error"]


def test_the_bridge_runs_isolated_and_answers_json_only():
    proc = subprocess.run([sys.executable, "-I", str(ROOT / "bridge.py")], input=json.dumps({"op": "nope"}),
                          capture_output=True, text=True, timeout=30, env={"HOME": "/nonexistent", "PATH": "/usr/bin:/bin"})
    reply = json.loads(proc.stdout)
    assert reply["ok"] is False and "unknown op" in reply["error"] and proc.stderr == ""
    proc = subprocess.run([sys.executable, "-I", str(ROOT / "bridge.py")], input="not json", capture_output=True,
                          text=True, timeout=30, env={"HOME": "/nonexistent", "PATH": "/usr/bin:/bin"})
    assert json.loads(proc.stdout)["ok"] is False
