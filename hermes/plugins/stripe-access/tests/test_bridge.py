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


def item(name: str, stage: str, scope: str = "stripe-access", **meta) -> dict:
    """One entry of `secret ls --json`."""
    return {"name": name, "project": "hermes", "scope": scope, "stage": stage, "kind": "TOKEN", "meta": meta}


def fake_secret(tmp_path: Path, values: dict, listed: list | None = None) -> Path:
    """A `secret` CLI keyed by layer ("NAME@stage", "NAME@" for a stage-less one): it lists `listed`
    (default: every layer in `values`, in the stripe-access scope, labelled with its name after STRIPE_ in
    lowercase), answers `get NAME --stage S` from `values` only when the `--scope stripe-access` and `--stage`
    it is given name that exact layer, and logs its arguments."""
    listed = listed if listed is not None else [
        item(key.split("@")[0], key.split("@")[1], label=key.split("@")[0].removeprefix("STRIPE_").lower())
        for key in values]
    (tmp_path / "ls.json").write_text(json.dumps(listed))
    branches = "".join(f"    '{key}') printf '%s\\n' '{value}' ;;\n" for key, value in values.items())
    script = tmp_path / "secret"
    script.write_text(
        "#!/bin/sh\n"
        f"echo \"$@\" >> '{tmp_path / 'log'}'\n"
        'stage=""; scope=""; prev=""\n'
        'for a in "$@"; do\n'
        '  [ "$prev" = "--stage" ] && stage="$a"\n'
        '  [ "$prev" = "--scope" ] && scope="$a"\n'
        '  prev="$a"\n'
        "done\n"
        'case "$1" in\n'
        f"  ls) cat '{tmp_path / 'ls.json'}' ;;\n"
        '  get) [ "$scope" = "stripe-access" ] || exit 1\n'
        '    case "$2@$stage" in\n'
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
    monkeypatch.setattr(bridge, "SECRET", fake_secret(tmp_path, {"STRIPE_WORK@test": TEST_KEY,
                                                                 "STRIPE_WORK@prod": LIVE_KEY}))
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


def test_keys_are_the_labelled_prod_and_test_items_of_the_scope_whatever_their_name(tmp_path, monkeypatch, net):
    listed = [
        item("STRIPE_WORK", "test", label="work"),
        item("work_live_key", "prod", label="Work"),                 # a free name; the label's case is ignored
        item("shop2_key", "prod", label="shop_2"),                  # stored, unreadable
        item("STRIPE_PLAIN", "", label="plain"),                     # no stage
        item("STRIPE_STAGING", "staging", label="staging"),          # another stage
        item("STRIPE_LOGIN", "prod", account="ops@example.com"),     # a note, no label
        item("STRIPE_BAD", "test", label="Bad Label!"),
        item("STRIPE_UPPER", "test", LABEL="upper"),                 # the field is matched by its spelling
        item("-rf", "test", label="flag"),                           # a name that reads as a flag
        item("stripe-access/STRIPE_X@prod", "test", label="token"),  # a name that reads as a layer token
        item("STRIPE\nX", "test", label="control"),
        item("STRIPE_OTHER", "prod", scope="another-scope", label="other"),
    ]
    monkeypatch.setattr(bridge, "SECRET", fake_secret(tmp_path, {"STRIPE_WORK@test": TEST_KEY,
                                                                 "work_live_key@prod": LIVE_KEY}, listed))
    reply = bridge.main({"op": "keys"})
    _, sent = net
    assert reply["ok"] is True and reply["requests"] == 0 and not sent
    entries = {(e["account"], e["mode"]): e for e in reply["data"]}
    assert set(entries) == {("work", "test"), ("work", "live"), ("shop_2", "live")}
    assert entries[("work", "test")]["item"] == "STRIPE_WORK" and entries[("work", "live")]["item"] == "work_live_key"
    assert entries[("work", "test")]["kind"] == "secret" and len(entries[("work", "test")]["fingerprint"]) == 12
    assert entries[("work", "live")]["kind"] == "restricted"
    assert "shop2_key@prod (label=shop_2) could not be read" in entries[("shop_2", "live")]["problem"]
    unused = {u["item"]: u for u in reply["unused"]}
    assert set(unused) == {"STRIPE_PLAIN", "STRIPE_STAGING", "STRIPE_LOGIN", "STRIPE_BAD", "STRIPE_UPPER", "-rf",
                           "stripe-access/STRIPE_X@prod", "STRIPE\nX"}
    assert "no stage" in unused["STRIPE_PLAIN"]["problem"] and "stage staging" in unused["STRIPE_STAGING"]["problem"]
    assert ("no label= field" in unused["STRIPE_LOGIN"]["problem"] and "secret update STRIPE_LOGIN -p hermes "
            "--scope stripe-access --stage prod --meta label=<label>" in unused["STRIPE_LOGIN"]["problem"])
    assert "label=Bad Label! is not a label" in unused["STRIPE_BAD"]["problem"]
    assert ("field LABEL= is not read" in unused["STRIPE_UPPER"]["problem"] and "secret update STRIPE_UPPER -p hermes "
            "--scope stripe-access --stage test --meta LABEL= --meta label=<label>" in unused["STRIPE_UPPER"]["problem"])
    for name in ("-rf", "stripe-access/STRIPE_X@prod", "STRIPE\nX"):
        assert "name is not one the secret CLI takes" in unused[name]["problem"]
    assert TEST_KEY not in json.dumps(reply) and LIVE_KEY not in json.dumps(reply)


def test_each_mode_reads_its_own_stage_exactly(tmp_path, monkeypatch, net):
    routes, _ = net
    routes["/v1/balance"] = (200, {"object": "balance"}, {})
    reply = call(mode="live", path="/v1/balance")
    assert reply["key_kind"] == "restricted" and reply["item"] == "STRIPE_WORK"
    assert call(mode="test", path="/v1/balance")["key_kind"] == "secret"
    gets = [line.split() for line in (tmp_path / "log").read_text().splitlines() if line.startswith("get ")]
    assert gets == [["get", "STRIPE_WORK", "-p", "hermes", "--scope", "stripe-access", "--stage", "prod"],
                    ["get", "STRIPE_WORK", "-p", "hermes", "--scope", "stripe-access", "--stage", "test"]]


def test_a_stage_less_item_is_never_read_as_a_key(tmp_path, monkeypatch, net):
    monkeypatch.setattr(bridge, "SECRET", fake_secret(tmp_path, {"STRIPE_WORK@": TEST_KEY}))
    reply = call(path="/v1/balance")
    assert reply["kind"] == "setup" and "no test key for account work" in reply["error"] and not net[1]
    listing = bridge.main({"op": "keys"})
    assert listing["data"] == [] and [u["item"] for u in listing["unused"]] == ["STRIPE_WORK"]


def test_a_name_that_reads_as_a_flag_is_never_passed_to_the_cli(tmp_path, monkeypatch, net):
    monkeypatch.setattr(bridge, "SECRET", fake_secret(tmp_path, {}, [item("--copy", "test", label="work")]))
    reply = call(path="/v1/balance")
    assert reply["kind"] == "setup" and "no test key for account work" in reply["error"] and not net[1]
    assert not any(line.startswith("get ") for line in (tmp_path / "log").read_text().splitlines())


def test_a_label_two_items_carry_in_one_stage_is_never_guessed(tmp_path, monkeypatch, net):
    routes, sent = net
    routes["/v1/balance"] = (200, {"object": "balance"}, {})
    listed = [item("STRIPE_A", "test", label="work"), item("STRIPE_B", "test", label="WORK"),
              item("STRIPE_C", "prod", label="work")]
    monkeypatch.setattr(bridge, "SECRET", fake_secret(tmp_path, {"STRIPE_A@test": TEST_KEY,
                                                                 "STRIPE_B@test": "sk_test_" + "f6" * 12,
                                                                 "STRIPE_C@prod": LIVE_KEY}, listed))
    reply = call(path="/v1/balance")
    assert reply["kind"] == "setup" and not sent
    assert "2 items in stage test carry label=work (STRIPE_A, STRIPE_B)" in reply["error"]
    assert "secret update STRIPE_B -p hermes --scope stripe-access --stage test --meta label=" in reply["error"]
    assert call(account=None, path="/v1/balance")["kind"] == "setup" and not sent
    assert call(mode="live", path="/v1/balance")["ok"] is True   # the other stage is not touched
    entries = {(e["account"], e["mode"]): e for e in bridge.main({"op": "keys"})["data"]}
    assert "carry label=work" in entries[("work", "test")]["problem"] and "item" not in entries[("work", "test")]
    assert not any(line.startswith("get STRIPE_A") or line.startswith("get STRIPE_B")
                   for line in (tmp_path / "log").read_text().splitlines())


def test_a_long_name_is_a_key_like_any_other(tmp_path, monkeypatch, net):
    long = "STRIPE_" + "X" * 200
    listed = [item(long, "test", label="work"), item("STRIPE_SHORT", "test", label="work")]
    monkeypatch.setattr(bridge, "SECRET", fake_secret(tmp_path, {f"{long}@test": TEST_KEY,
                                                                 "STRIPE_SHORT@test": TEST_KEY}, listed))
    reply = call(path="/v1/balance")
    assert reply["kind"] == "setup" and "2 items in stage test carry label=work" in reply["error"] and not net[1]


def test_a_label_moved_to_another_item_is_caught_by_the_card_s_fingerprint(tmp_path, monkeypatch, net):
    routes, sent = net
    routes["/v1/balance"] = (200, {"object": "balance"}, {})
    card = bridge.main({"op": "key", "mode": "test", "account": "work"})
    assert card["item"] == "STRIPE_WORK"
    # The label now sits on another item holding another key: the write sends nothing.
    monkeypatch.setattr(bridge, "SECRET", fake_secret(tmp_path, {"STRIPE_NEW@test": "sk_test_" + "a9" * 12}, [
        item("STRIPE_NEW", "test", label="work")]))
    reply = call(path="/v1/balance", expect=card["fingerprint"])
    assert reply["kind"] == "account" and reply["item"] == "STRIPE_NEW" and not sent
    # The same key under a new name is the same account.
    monkeypatch.setattr(bridge, "SECRET", fake_secret(tmp_path, {"STRIPE_RENAMED@test": TEST_KEY}, [
        item("STRIPE_RENAMED", "test", label="work")]))
    assert call(path="/v1/balance", expect=card["fingerprint"])["ok"] is True


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
    monkeypatch.setattr(bridge, "SECRET", fake_secret(tmp_path, {"STRIPE_WORK@test": "sk_live_" + "c3" * 12}))
    reply = call(path="/v1/balance")
    assert reply["ok"] is False and reply["kind"] == "setup"
    assert "STRIPE_WORK@test (label=work) holds a live key, not a test one" in reply["error"]
    assert "secret update STRIPE_WORK -p hermes --scope stripe-access --stage test --value" in reply["error"]
    assert not sent and "c3c3" not in json.dumps(reply)


@pytest.mark.parametrize("value, message", [
    ("pk_test_" + "d4" * 12, "publishable key"),
    ("not a key", "not a Stripe secret or restricted key"),
])
def test_a_key_that_is_not_a_secret_key_is_a_setup_problem(tmp_path, monkeypatch, net, value, message):
    monkeypatch.setattr(bridge, "SECRET", fake_secret(tmp_path, {"STRIPE_WORK@test": value}))
    reply = call(path="/v1/balance")
    assert reply["kind"] == "setup" and message in reply["error"] and not net[1]


def test_a_missing_key_names_the_command_that_stores_it(net):
    reply = call(account="shop", path="/v1/balance")
    assert reply["kind"] == "setup" and reply["requests"] == 0
    assert "stage test, field label=shop" in reply["error"]
    assert ("secret set STRIPE_SHOP -p hermes --scope stripe-access --stage test -D TOKEN --meta label=shop --no-env"
            in reply["error"])
    reply = call(account="shop", mode="live", path="/v1/balance")
    assert ("secret set STRIPE_SHOP -p hermes --scope stripe-access --stage prod -D TOKEN --meta label=shop --no-env"
            in reply["error"])


def test_without_an_account_the_only_label_of_the_mode_is_used(tmp_path, monkeypatch, net):
    routes, _ = net
    routes["/v1/balance"] = (200, {"object": "balance"}, {})
    assert call(account=None, path="/v1/balance")["account"] == "work"
    monkeypatch.setattr(bridge, "SECRET", fake_secret(tmp_path, {"STRIPE_WORK@test": TEST_KEY,
                                                                 "STRIPE_SHOP@test": "sk_test_" + "e5" * 12}))
    reply = call(account=None, path="/v1/balance")
    assert reply["kind"] == "setup" and "account is required" in reply["error"] and "shop, work" in reply["error"]
    reply = call(account=None, mode="live", path="/v1/balance")
    assert reply["kind"] == "setup" and "no live key is stored" in reply["error"]


ORG_KEY = "sk_org_test_" + "c7" * 12
ACCT = "acct_1StudioSandbox"


def org_secret(tmp_path, monkeypatch, values=None, listed=None):
    """An organization main holding a test key, whose item routes the account studio."""
    values = values if values is not None else {"STRIPE_ORG_MAIN@test": ORG_KEY}
    listed = listed if listed is not None else [item("STRIPE_ORG_MAIN", "test", org="main", acct_studio=ACCT)]
    monkeypatch.setattr(bridge, "SECRET", fake_secret(tmp_path, values, listed))


def test_an_account_reached_through_an_organization_sends_its_context(tmp_path, monkeypatch, net):
    routes, sent = net
    routes["/v1/balance"] = (200, {"object": "balance"}, {})
    org_secret(tmp_path, monkeypatch)
    reply = call(account="studio", path="/v1/balance")
    assert reply["ok"] is True and reply["key_kind"] == "organization"
    assert (reply["item"], reply["org"], reply["field"], reply["stripe_account"]) == (
        "STRIPE_ORG_MAIN", "main", "acct_studio", ACCT)
    assert "org_item" not in reply
    assert reply["fingerprint"] == bridge.fingerprint(f"{ORG_KEY}|{ACCT}") != bridge.fingerprint(ORG_KEY)
    assert sent[0].get_header("Authorization") == f"Bearer {ORG_KEY}"
    assert sent[0].get_header("Stripe-context") == ACCT and sent[0].get_header("Stripe-version") == bridge.VERSION
    assert ORG_KEY not in json.dumps(reply)
    # The organization key is no label of its own: left out, account is the one route.
    assert call(account=None, path="/v1/balance")["account"] == "studio"


def test_an_account_s_own_key_wins_over_a_route(tmp_path, monkeypatch, net):
    routes, sent = net
    routes["/v1/balance"] = (200, {"object": "balance"}, {})
    org_secret(tmp_path, monkeypatch, {"STRIPE_ORG_MAIN@test": ORG_KEY, "STRIPE_STUDIO_OWN@test": TEST_KEY},
               [item("STRIPE_ORG_MAIN", "test", org="main", acct_studio=ACCT),
                item("STRIPE_STUDIO_OWN", "test", label="studio")])
    reply = call(account="studio", path="/v1/balance")
    assert reply["key_kind"] == "secret" and reply["item"] == "STRIPE_STUDIO_OWN" and "org" not in reply
    assert sent[0].get_header("Stripe-context") is None
    entry = bridge.main({"op": "keys"})["data"][0]
    assert entry["item"] == "STRIPE_STUDIO_OWN" and "also reached through organization main" in entry["note"]


def test_a_route_lives_on_its_stage_s_organization_key(tmp_path, monkeypatch, net):
    # A route on the live organization key does not serve a test call.
    org_secret(tmp_path, monkeypatch, {"STRIPE_ORG_MAIN@prod": "sk_org_live_" + "c7" * 12},
               [item("STRIPE_ORG_MAIN", "prod", org="main", acct_studio=ACCT)])
    reply = call(account="studio", path="/v1/balance")
    assert reply["kind"] == "setup" and "no test key for account studio" in reply["error"] and not net[1]


def test_an_item_with_both_label_and_org_is_no_key(tmp_path, monkeypatch, net):
    org_secret(tmp_path, monkeypatch, {"STRIPE_STUDIO@test": TEST_KEY},
               [item("STRIPE_STUDIO", "test", label="studio", org="main")])
    reply = call(account="studio", path="/v1/balance")
    assert reply["kind"] == "setup" and not net[1]
    [unused] = bridge.main({"op": "keys"})["unused"]
    assert "carries both label=" in unused["problem"] and "acct_<label>=acct_…" in unused["problem"]
    assert "secret update STRIPE_STUDIO -p hermes --scope stripe-access --stage test --meta org=" in unused["problem"]


def test_an_organization_two_items_carry_is_never_guessed(tmp_path, monkeypatch, net):
    org_secret(tmp_path, monkeypatch, {"STRIPE_ORG_A@test": ORG_KEY, "STRIPE_ORG_B@test": ORG_KEY},
               [item("STRIPE_ORG_A", "test", org="main", acct_studio=ACCT), item("STRIPE_ORG_B", "test", org="Main")])
    reply = call(account="studio", path="/v1/balance")
    assert reply["kind"] == "setup" and "2 items in stage test carry org=main" in reply["error"] and not net[1]
    organizations = bridge.main({"op": "keys"})["organizations"]
    assert organizations == [{"org": "main", "mode": "test", "problem": organizations[0]["problem"]}]


def test_a_label_two_organizations_route_is_never_guessed(tmp_path, monkeypatch, net):
    routes, _ = net
    routes["/v1/balance"] = (200, {"object": "balance"}, {})
    values = {"STRIPE_ORG_MAIN@test": ORG_KEY, "STRIPE_ORG_SIDE@test": "sk_org_test_" + "d8" * 12}
    org_secret(tmp_path, monkeypatch, values, [item("STRIPE_ORG_MAIN", "test", org="main", acct_studio=ACCT),
                                               item("STRIPE_ORG_SIDE", "test", org="side", acct_studio="acct_1Other")])
    reply = call(account="studio", path="/v1/balance")
    fix = "secret update STRIPE_ORG_SIDE -p hermes --scope stripe-access --stage test --meta acct_studio="
    assert reply["kind"] == "setup" and "2 items in stage test carry acct_studio" in reply["error"]
    assert fix in reply["error"] and not net[1]
    # What the fix leaves: the other route works and both organization keys stay.
    org_secret(tmp_path, monkeypatch, values, [item("STRIPE_ORG_MAIN", "test", org="main", acct_studio=ACCT),
                                               item("STRIPE_ORG_SIDE", "test", org="side")])
    assert call(account="studio", path="/v1/balance")["stripe_account"] == ACCT
    assert [o["item"] for o in bridge.main({"op": "keys"})["organizations"]] == ["STRIPE_ORG_MAIN", "STRIPE_ORG_SIDE"]


@pytest.mark.parametrize("org_key, message", [
    ("sk_org_live_" + "c7" * 12, "holds a live organization key, not a test one"),
    ("sk_test_" + "c7" * 12, "is not a Stripe organization key"),
])
def test_a_route_whose_organization_key_is_wrong_sends_nothing(tmp_path, monkeypatch, net, org_key, message):
    org_secret(tmp_path, monkeypatch, {"STRIPE_ORG_MAIN@test": org_key})
    reply = call(account="studio", path="/v1/balance")
    assert reply["kind"] == "setup" and message in reply["error"] and not net[1]
    assert "c7c7" not in json.dumps(reply)


@pytest.mark.parametrize("field, value, message", [
    ("acct_studio", "sk_test_" + "e8" * 12, "its field acct_studio= holds no account id"),
    ("acct_studio", "acct_1../x", "its field acct_studio= holds no account id"),
    ("acct_Studio", ACCT, "its field acct_Studio= routes no label"),
    ("ACCT_studio", ACCT, "its field ACCT_studio= routes no label"),
])
def test_a_route_field_that_routes_nothing_is_listed_and_never_used(tmp_path, monkeypatch, net, field, value,
                                                                    message):
    org_secret(tmp_path, monkeypatch, {"STRIPE_ORG_MAIN@test": ORG_KEY},
               [item("STRIPE_ORG_MAIN", "test", org="main", **{field: value})])
    reply = call(account="studio", path="/v1/balance")
    assert reply["kind"] == "setup" and "no test key for account studio" in reply["error"] and not net[1]
    listing = bridge.main({"op": "keys"})
    assert [o["item"] for o in listing["organizations"]] == ["STRIPE_ORG_MAIN"]   # the key itself stays usable
    [unused] = listing["unused"]
    assert unused["item"] == "STRIPE_ORG_MAIN" and message in unused["problem"]
    assert "e8e8" not in json.dumps(listing)


def test_a_route_moved_to_another_account_is_caught_by_the_card_s_fingerprint(tmp_path, monkeypatch, net):
    routes, sent = net
    routes["/v1/balance"] = (200, {"object": "balance"}, {})
    org_secret(tmp_path, monkeypatch)
    card = bridge.main({"op": "key", "mode": "test", "account": "studio"})
    assert card["stripe_account"] == ACCT and card["org"] == "main"
    org_secret(tmp_path, monkeypatch, None, [item("STRIPE_ORG_MAIN", "test", org="main",
                                                  acct_studio="acct_1SomeoneElse")])
    reply = call(account="studio", path="/v1/balance", expect=card["fingerprint"])
    assert reply["kind"] == "account" and reply["stripe_account"] == "acct_1SomeoneElse" and not sent


def test_keys_lists_routes_and_organization_keys_without_contacting_stripe(tmp_path, monkeypatch, net):
    org_secret(tmp_path, monkeypatch, None,
               [item("STRIPE_ORG_MAIN", "test", org="main", acct_studio=ACCT, url="https://dashboard.stripe.com"),
                item("STRIPE_SHOP", "test", label="shop", ORG="main")])
    reply = bridge.main({"op": "keys"})
    assert reply["ok"] is True and not net[1]
    assert reply["data"] == [{"account": "studio", "mode": "test", "item": "STRIPE_ORG_MAIN", "org": "main",
                              "field": "acct_studio", "stripe_account": ACCT, "kind": "organization",
                              "fingerprint": bridge.fingerprint(f"{ORG_KEY}|{ACCT}")}]
    assert reply["organizations"] == [{"org": "main", "mode": "test", "item": "STRIPE_ORG_MAIN",
                                       "kind": "organization", "fingerprint": bridge.fingerprint(ORG_KEY)}]
    assert "field ORG= is not read" in reply["unused"][0]["problem"]
    assert ORG_KEY not in json.dumps(reply)
    gets = [line for line in (tmp_path / "log").read_text().splitlines() if line.startswith("get STRIPE_ORG_MAIN")]
    assert len(gets) == 1   # read once though it serves the route and its own entry


def test_an_organization_key_never_leaves_even_when_stripe_echoes_it(tmp_path, monkeypatch, net):
    routes, _ = net
    routes["/v1/balance"] = (401, {"error": {"type": "invalid_request_error",
                                             "message": "Invalid API Key provided: sk_org_test_c7c7…"}}, {})
    org_secret(tmp_path, monkeypatch)
    reply = call(account="studio", path="/v1/balance")
    assert reply["kind"] == "refused" and "sk_org_" not in json.dumps(reply)


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
