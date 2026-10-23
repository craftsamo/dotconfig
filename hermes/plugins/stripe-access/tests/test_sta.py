import importlib.util
from datetime import datetime, timedelta
from pathlib import Path
import re
import time
from zoneinfo import ZoneInfo

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("stripe_access_engine_test", ROOT / "sta.py")
sta = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sta)
bridge_spec = importlib.util.spec_from_file_location("stripe_access_bridge_routes", ROOT / "bridge.py")
bridge_module = importlib.util.module_from_spec(bridge_spec)
bridge_spec.loader.exec_module(bridge_module)


class Bridge:
    """The bridge as a callable: records every request and answers from `answers` (path -> data, or a
    full reply dict when it has "ok")."""

    def __init__(self):
        self.requests = []
        self.answers = {}
        self.keys = {"ok": True, "data": [], "requests": 0}

    def __call__(self, op, **fields):
        self.requests.append({"op": op, **fields})
        if op == "keys":
            return self.keys
        answer = self.answers.get(fields["path"], {"object": "list", "data": [], "has_more": False})
        if isinstance(answer, dict) and "ok" in answer:
            return {"account": fields.get("account") or "work", "mode": fields["mode"], **answer}
        return {"ok": True, "account": fields.get("account") or "work", "mode": fields["mode"], "requests": 1,
                "fingerprint": "f" * 12, "key_kind": "restricted", "data": answer}

    def params(self, n=-1):
        return self.requests[n]["params"]


@pytest.fixture
def fake(monkeypatch, tmp_path):
    monkeypatch.setattr(sta, "STORE", tmp_path / "store")   # never the real ~/.stripe-access
    bridge = Bridge()
    monkeypatch.setattr(sta, "bridge", bridge)
    return bridge


def run(**args):
    return sta.execute(args, allowed=sta.ACTIONS)


@pytest.mark.parametrize("amount, currency, text", [
    (5000, "jpy", "JPY 5,000"), (1050, "usd", "USD 10.50"), (1500, "kwd", "KWD 1.500"), (50000, "isk", "ISK 500.00"),
    (-250, "eur", "EUR -2.50"), (0, "krw", "KRW 0"), (None, "usd", None), (True, "usd", None),
])
def test_money_reads_minor_units_per_currency(amount, currency, text):
    assert sta.money(amount, currency) == text


def test_every_endpoint_the_engine_builds_is_one_the_bridge_allows():
    allowed = [(m, p) for m, p in bridge_module._ROUTES]

    def ok(method, path):
        return any(m == method and p.fullmatch(path) for m, p in allowed)
    assert ok("GET", "/v1/account") and ok("GET", "/v1/balance")
    for spec_ in sta.LISTINGS.values():
        assert ok("GET", spec_.path) and ok("GET", spec_.path + "/obj_1")
        if spec_.search:
            assert ok("GET", spec_.path + "/search")
        if spec_.lines:
            assert ok("GET", f"{spec_.path}/obj_1/{spec_.lines}")


def test_mode_is_required_and_the_account_label_is_checked(fake):
    with pytest.raises(sta.StripeError, match="mode is required"):
        run(action="customers")
    with pytest.raises(sta.StripeError, match="account must be the label"):
        run(action="customers", mode="live", account="my shop")
    run(action="customers", mode="live", account="Work")
    assert fake.requests[-1]["account"] == "work" and fake.requests[-1]["mode"] == "live"
    assert not [r for r in fake.requests if r.get("account") == "my shop"]


def test_a_list_takes_its_filters_dates_and_limit(fake):
    run(action="invoices", mode="live", customer="cus_1", status="open", since="2026-10-01", until="2026-10-31",
        limit=500)
    params = dict(fake.params())
    start = datetime(2026, 10, 1).astimezone()
    end = datetime(2026, 10, 31).astimezone() + timedelta(days=1)
    assert fake.requests[-1]["path"] == "/v1/invoices" and fake.requests[-1]["method"] == "GET"
    assert params == {"customer": "cus_1", "status": "open", "created[gte]": str(int(start.timestamp())),
                      "created[lt]": str(int(end.timestamp())), "limit": "100"}


def test_an_iso_time_or_epoch_bounds_exactly(fake):
    run(action="payments", mode="test", since="2026-10-01T09:00:00+09:00", until=1800000000)
    params = dict(fake.params())
    assert params["created[gte]"] == str(int(datetime.fromisoformat("2026-10-01T09:00:00+09:00").timestamp()))
    assert params["created[lt]"] == "1800000000"
    run(action="payments", mode="test", since="1700000000")   # the schema's string form of epoch seconds
    assert dict(fake.params())["created[gte]"] == "1700000000"


@pytest.fixture
def new_york(monkeypatch):
    monkeypatch.setenv("TZ", "America/New_York")
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


def test_a_whole_day_ends_at_the_next_local_midnight_across_dst(fake, new_york):
    zone = ZoneInfo("America/New_York")
    run(action="invoices", mode="live", since="2026-11-01", until="2026-11-01")   # 25 hours: clocks go back
    params = dict(fake.params())
    assert params["created[gte]"] == str(int(datetime(2026, 11, 1, tzinfo=zone).timestamp()))
    assert params["created[lt]"] == str(int(datetime(2026, 11, 2, tzinfo=zone).timestamp()))
    assert int(params["created[lt]"]) - int(params["created[gte]"]) == 25 * 3600
    run(action="invoices", mode="live", since="2026-03-08", until="2026-03-08")   # 23 hours: clocks go forward
    params = dict(fake.params())
    assert int(params["created[lt]"]) - int(params["created[gte]"]) == 23 * 3600


@pytest.mark.parametrize("args, message", [
    ({"action": "customers", "status": "open"}, "status does not filter customers"),
    ({"action": "invoices", "status": "late"}, "status must be one of"),
    ({"action": "invoices", "customer": "pi_1"}, "starting with cus_"),
    ({"action": "payment_links", "since": "2026-10-01"}, "cannot be filtered by date"),
    ({"action": "refunds", "query": "amount>1"}, "cannot search refunds"),
    ({"action": "customers", "query": "email:'a'", "email": "a"}, "not both"),
    ({"action": "customers", "id": "pi_1"}, "starting with cus_"),
    ({"action": "customers", "since": "next week"}, "since must be a date"),
    ({"action": "customers", "cursor": "a b"}, "cursor must be"),
    ({"action": "products", "active": "yes"}, "active must be true or false"),
    ({"action": "customers", "limit": 0}, "limit must be a positive integer"),
])
def test_bad_arguments_never_reach_the_bridge(fake, args, message):
    with pytest.raises(sta.StripeError, match=message):
        run(mode="live", **args)
    assert not fake.requests


def test_a_list_pages_on_with_the_last_id(fake):
    fake.answers["/v1/customers"] = {"object": "list", "has_more": True, "data": [
        {"id": "cus_1", "name": "A", "email": "a@example.com", "created": 1700000000},
        {"id": "cus_2", "name": "B", "balance": -500, "currency": "jpy"}]}
    result = run(action="customers", mode="live")
    assert result["count"] == 2 and result["next"] == "cus_2" and result["account"] == "work"
    assert result["items"][1]["balance_display"] == "JPY -500" and "Names, e-mails" in result["note"]
    run(action="customers", mode="live", cursor="cus_2")
    assert ["starting_after", "cus_2"] in fake.params()


def test_a_search_pages_on_with_stripes_page_token(fake):
    fake.answers["/v1/invoices/search"] = {"object": "search_result", "has_more": True, "next_page": "tok_+/=",
                                           "data": [{"id": "in_1", "total": 1200, "currency": "usd",
                                                     "status": "paid"}]}
    result = run(action="invoices", mode="live", query="status:'paid'", limit=5)
    assert fake.requests[-1]["path"] == "/v1/invoices/search"
    assert fake.params() == [["query", "status:'paid'"], ["limit", "5"]]
    assert result["next"] == "tok_+/=" and result["items"][0]["total_display"] == "USD 12.00"
    run(action="invoices", mode="live", query="status:'paid'", cursor="tok_+/=")
    assert ["page", "tok_+/="] in fake.params()


def test_an_id_returns_the_object_and_its_summary(fake):
    coupon = {"id": "SUMMER10", "object": "coupon", "percent_off": 10.0, "duration": "repeating",
              "duration_in_months": 3, "valid": True}
    fake.answers["/v1/coupons/SUMMER10"] = coupon
    result = run(action="coupons", mode="live", id="SUMMER10")
    assert result["object"] == coupon and result["summary"]["terms"] == "10% off, for 3 months"
    fake.answers["/v1/coupons/FIXED"] = {"id": "FIXED", "amount_off": 500, "currency": "jpy", "duration": "once"}
    assert run(action="coupons", mode="live", id="FIXED")["summary"]["terms"] == "JPY 500 off, once"


def test_payment_links_come_with_their_line_items(fake):
    fake.answers["/v1/payment_links"] = {"object": "list", "has_more": False, "data": [
        {"id": "plink_1", "url": "https://buy.stripe.com/x", "active": True,
         "line_items": {"has_more": True, "data": [{"quantity": 1, "price": {"id": "price_1"}}]}}]}
    listed = run(action="payment_links", mode="live")
    assert ["expand[]", "data.line_items"] in fake.params()
    assert listed["items"][0]["line_items_more"] is True
    fake.answers["/v1/payment_links/plink_1/line_items"] = {"object": "list", "has_more": False, "data": [
        {"quantity": 1, "price": {"id": "price_1"}}, {"quantity": 2, "price": {"id": "price_2"}}]}
    one = run(action="payment_links", mode="live", id="plink_1")
    assert [r["path"] for r in fake.requests[-2:]] == ["/v1/payment_links/plink_1",
                                                       "/v1/payment_links/plink_1/line_items"]
    assert fake.requests[-2]["params"] == [] and fake.params() == [["limit", "100"]]
    assert fake.requests[-1]["account"] == "work"   # the label the first read resolved
    assert [line["price"] for line in one["summary"]["line_items"]] == ["price_1", "price_2"]
    assert "line_items_more" not in one["summary"]


def test_shapes_read_current_api_fields():
    subscription = sta.shape_subscription({
        "id": "sub_1", "status": "active", "customer": {"id": "cus_1"}, "cancel_at_period_end": False,
        "discounts": [{"id": "di_1", "source": {"type": "coupon", "coupon": "SUMMER10"}}],
        "items": {"data": [{"id": "si_1", "quantity": 2, "current_period_end": 1800000000,
                            "price": {"id": "price_1", "product": "prod_1", "unit_amount": 1000, "currency": "jpy",
                                      "recurring": {"interval": "month", "interval_count": 1}}}]}})
    assert subscription["customer"] == "cus_1" and "cancel_at_period_end" not in subscription
    assert subscription["discounts"] == [{"id": "di_1", "coupon": "SUMMER10"}]
    assert subscription["items"][0]["unit_amount_display"] == "JPY 1,000" and subscription["items"][0]["interval"] == "1 month"
    invoice = sta.shape_invoice({"id": "in_1", "parent": {"subscription_details": {"subscription": "sub_1"}},
                                 "amount_due": 300, "currency": "usd"})
    assert invoice["subscription"] == "sub_1" and invoice["amount_due_display"] == "USD 3.00"
    promo = sta.shape_promotion_code({"id": "promo_1", "code": "WELCOME", "active": True,
                                      "promotion": {"type": "coupon", "coupon": "SUMMER10"}})
    assert promo["coupon"] == "SUMMER10"


def test_balance_formats_each_currency(fake):
    fake.answers["/v1/balance"] = {"available": [{"amount": 120000, "currency": "jpy"}],
                                   "pending": [{"amount": 999, "currency": "usd"}]}
    result = run(action="balance", mode="live")
    assert result["available"] == [{"amount": 120000, "currency": "jpy", "display": "JPY 120,000"}]
    assert result["pending"][0]["display"] == "USD 9.99"


def test_account_is_remembered_for_status(fake):
    fake.answers["/v1/account"] = {"id": "acct_1", "business_profile": {"name": "Shop"}, "country": "JP",
                                   "default_currency": "jpy", "charges_enabled": True}
    result = run(action="account", mode="live")
    assert result["stripe_account"]["name"] == "Shop" and result["key"] == "restricted"
    fake.keys = {"ok": True, "requests": 0, "data": [
        {"account": "work", "mode": "live", "kind": "restricted", "fingerprint": "f" * 12}]}
    status = run(action="status")
    assert status["keys"] == [{"account": "work", "mode": "live", "kind": "restricted",
                               "stripe_account": {"id": "acct_1", "name": "Shop"}}]
    assert fake.requests[-1] == {"op": "keys"}


def test_status_without_keys_says_how_to_store_one(fake):
    status = run(action="status")
    assert status["keys"] == []
    assert "secret set STRIPE_KEY_<LABEL> -p hermes --scope stripe-access --stage <prod|test>" in status["problem"]
    fake.keys = {"ok": False, "kind": "setup", "error": "the secret CLI is missing", "requests": 0}
    assert "not set up" in run(action="status")["problem"]


def test_a_refused_key_is_remembered_until_it_works_again(fake):
    fake.answers["/v1/balance"] = {"ok": False, "kind": "refused", "error": "Invalid API Key", "requests": 1,
                                   "fingerprint": "f" * 12}
    with pytest.raises(sta.StripeError, match="refused the live key of account work"):
        run(action="balance", mode="live")
    with pytest.raises(sta.StripeError):
        run(action="balance", mode="live")
    assert fake.requests[-1]["refused"] == {"work/live": "f" * 12}
    fake.keys = {"ok": True, "requests": 0, "data": [{"account": "work", "mode": "live", "fingerprint": "f" * 12}]}
    assert ("secret set STRIPE_KEY_WORK -p hermes --scope stripe-access --stage prod"
            in run(action="status")["keys"][0]["problem"])
    fake.answers["/v1/balance"] = {"available": [], "pending": []}
    run(action="balance", mode="live")
    run(action="balance", mode="live")
    assert fake.requests[-1]["refused"] == {}


def test_a_rate_limit_pauses_that_key(fake):
    fake.answers["/v1/balance"] = {"ok": False, "kind": "limited", "error": "too many", "requests": 1}
    with pytest.raises(sta.StripeError, match="paused"):
        run(action="balance", mode="test")
    run(action="customers", mode="test")
    assert set(fake.requests[-1]["paused"]) == {"work/test"}


@pytest.mark.parametrize("kind, message", [
    ("setup", "Stripe is not set up"), ("forbidden", "refused this key access"),
    ("not_found", "not found in work/live"), ("invalid", "rejected the request: bad (parameter email)"),
])
def test_failures_explain_themselves(fake, kind, message):
    fake.answers["/v1/customers"] = {"ok": False, "kind": kind, "error": "bad", "param": "email", "requests": 1}
    with pytest.raises(sta.StripeError, match=re.escape(message)):
        run(action="customers", mode="live")


def test_the_state_directory_is_private(fake):
    fake.answers["/v1/balance"] = {"ok": False, "kind": "limited", "error": "x", "requests": 1}
    with pytest.raises(sta.StripeError):
        run(action="balance", mode="live")
    assert (sta.STORE.stat().st_mode & 0o777) == 0o700
    assert "sk_" not in (sta.STORE / "state.json").read_text()


@pytest.mark.parametrize("command", [
    "stripe customers list --limit 3", "stripe login", "stripe config --list", "stripe get /v1/balance",
    "curl https://api.stripe.com/v1/charges -u x:", "secret get STRIPE_KEY_WORK -p hermes --scope stripe-access --stage prod",
    "cat ~/.stripe-access/state.json", "python3 -c 'import stripe; print(stripe.api_key)'",
    "node -e \"require('stripe')\"", "cat ~/.config/stripe/config.toml", "echo sk_live_123 | pbcopy",
    "ls ~/.hermes/plugins/stripe-access", "security dump-keychain", "secret export -p hermes",
    "cd /tmp && stripe listen --forward-to localhost:3000",
    # global flags before the command, the binary by path or behind a wrapper, a shell inside a shell
    "stripe --live customers list", "stripe --live refunds create --charge ch_123",
    "stripe --project-name shop --color off invoices void in_1", "/opt/homebrew/bin/stripe --version",
    "sudo stripe login", "env STRIPE_DEVICE_NAME=x stripe", "bash -c \"stripe --live customers list\"",
    "npx stripe customers list", "echo x; stripe", "(stripe --live customers list)",
    # SDKs in an inline script
    "node -e \"import Stripe from 'stripe'\"", "node --input-type=module -e \"const s = await import('stripe')\"",
    "ruby -e \"require 'stripe'\"", "python3 -c 'from stripe import StripeClient'",
])
def test_the_terminal_cannot_go_around_the_tool(command):
    assert sta.bypass("terminal", {"command": command}) == sta.BYPASS_MESSAGE


@pytest.mark.parametrize("command", [
    "echo stripe", "npm install stripe", "ls node_modules/stripe", "grep -r \"stripe\" src",
    "git commit -m 'note the stripe fee was high'", "open https://dashboard.stripe.com/test/payments",
    "ls ./stripe-cli", "cat notes/stripe.md", "echo 'stripes and dots' | wc -w",
    "npm view stripe version", "grep -En '(stripe |solid )' patterns.txt",
])
def test_ordinary_mentions_of_stripe_are_not_blocked(command):
    assert sta.bypass("terminal", {"command": command}) is None


def test_file_tools_cannot_read_the_state_or_name_a_key():
    assert sta.bypass("read_file", {"path": "~/.stripe-access/state.json"}) == sta.BYPASS_MESSAGE
    assert sta.bypass("search_files", {"pattern": "STRIPE_KEY_", "path": "~"}) == sta.BYPASS_MESSAGE
    assert sta.bypass("read_file", {"path": "~/.config/stripe/config.toml"}) == sta.BYPASS_MESSAGE
    assert sta.bypass("read_file", {"path": "hermes/plugins/stripe-access/sta.py"}) is None
    assert sta.bypass("web_search", {"query": "stripe customers list"}) is None
