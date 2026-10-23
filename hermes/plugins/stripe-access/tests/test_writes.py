import importlib.util
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("stripe_access_writes_test", ROOT / "sta.py")
sta = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sta)
bridge_spec = importlib.util.spec_from_file_location("stripe_access_bridge_write_routes", ROOT / "bridge.py")
bridge_module = importlib.util.module_from_spec(bridge_spec)
bridge_spec.loader.exec_module(bridge_module)

CUSTOMER = {"id": "cus_1", "name": "Ada", "email": "ada@example.com"}
ONE_TIME = {"id": "price_a", "type": "one_time", "active": True, "unit_amount": 5000, "currency": "jpy",
            "nickname": "Setup"}
MONTHLY = {"id": "price_m", "type": "recurring", "active": True, "unit_amount": 1000, "currency": "jpy",
           "recurring": {"interval": "month", "interval_count": 1}}
YEARLY = {"id": "price_y", "type": "recurring", "active": True, "unit_amount": 10000, "currency": "jpy",
          "recurring": {"interval": "year", "interval_count": 1}}
COUPON = {"id": "SUMMER10", "percent_off": 10.0, "duration": "repeating", "duration_in_months": 3, "valid": True,
          "times_redeemed": 4}
CHARGE = {"id": "ch_1", "status": "succeeded", "currency": "usd", "amount": 5000, "amount_captured": 5000,
          "amount_refunded": 1000, "billing_details": {"name": "Ada", "email": "ada@example.com"}, "customer": "cus_1"}
SUBSCRIPTION = {"id": "sub_1", "status": "active", "customer": CUSTOMER, "discounts": [],
                "items": {"data": [{"id": "si_1", "quantity": 1, "price": MONTHLY, "current_period_end": 1800000000}]}}


class Stripe:
    """The bridge as a callable: GETs answer from `objects` (path -> data), writes from `writes`
    ((method, path) -> data or a full reply dict); records every request."""

    def __init__(self):
        self.requests = []
        self.objects = {
            "/v1/customers/cus_1": CUSTOMER, "/v1/prices/price_a": ONE_TIME, "/v1/prices/price_m": MONTHLY,
            "/v1/prices/price_y": YEARLY, "/v1/coupons/SUMMER10": COUPON, "/v1/charges/ch_1": CHARGE,
            "/v1/payment_intents/pi_1": {"id": "pi_1", "latest_charge": CHARGE},
            "/v1/subscriptions/sub_1": SUBSCRIPTION, "/v1/products/prod_1": {"id": "prod_1", "name": "Plan",
                                                                             "active": True},
            "/v1/invoices/in_1": {"id": "in_1", "status": "draft", "total": 12000, "currency": "jpy",
                                  "customer": "cus_1", "customer_name": "Ada", "customer_email": "ada@example.com",
                                  "collection_method": "send_invoice"},
            "/v1/promotion_codes/promo_1": {"id": "promo_1", "code": "WELCOME", "active": True,
                                            "promotion": {"type": "coupon", "coupon": "SUMMER10"}},
            "/v1/payment_links/plink_1": {"id": "plink_1", "url": "https://buy.stripe.com/x", "active": True},
        }
        self.writes = {}

    def __call__(self, op, **fields):
        self.requests.append({"op": op, **fields})
        base = {"account": fields.get("account") or "work", "mode": fields.get("mode"), "fingerprint": "f" * 12}
        if op == "key":
            return {**base, "ok": True, "key_kind": "restricted", "requests": 0}
        method, path = fields["method"], fields["path"]
        if method == "GET":
            if path not in self.objects:
                return {**base, "ok": False, "kind": "not_found", "status": 404, "error": "No such object",
                        "requests": 1}
            return {**base, "ok": True, "requests": 1, "data": self.objects[path]}
        answer = self.writes.get((method, path), {"id": "obj_new"})
        if isinstance(answer, dict) and "ok" in answer:
            return {**base, **answer}
        return {**base, "ok": True, "requests": 1, "data": answer}

    def sent(self):
        return [r for r in self.requests if r["op"] == "call" and r["method"] != "GET"]


@pytest.fixture
def stripe(monkeypatch, tmp_path):
    monkeypatch.setattr(sta, "STORE", tmp_path / "store")
    fake = Stripe()
    monkeypatch.setattr(sta, "bridge", fake)
    sta._approved.clear()
    return fake


def approve_and_run(args, call_id="c1"):
    card, key = sta.approval_request(args, call_id=call_id, can_write=True)
    return card, key, sta.execute(args, call_id=call_id, can_write=True, allowed=sta.ACTIONS)


def test_every_write_has_a_plan_its_routes_and_its_arguments():
    assert set(sta.PLANS) == set(sta.WRITES) == set(sta.WRITE_ARGS)
    assert sta.ONCE <= set(sta.WRITES)
    routes = [(m, p) for m, p in bridge_module._ROUTES]
    for method, path in [("POST", "/v1/customers"), ("POST", "/v1/customers/cus_1"), ("DELETE", "/v1/coupons/X"),
                         ("POST", "/v1/invoiceitems"), ("POST", "/v1/invoices/in_1/send"),
                         ("DELETE", "/v1/subscriptions/sub_1"), ("POST", "/v1/refunds"), ("GET", "/v1/charges/ch_1")]:
        assert any(m == method and p.fullmatch(path) for m, p in routes), (method, path)
    # nothing that moves money out of the account, or deletes a customer, is reachable
    for method, path in [("POST", "/v1/payouts"), ("POST", "/v1/transfers"), ("DELETE", "/v1/customers/cus_1"),
                         ("POST", "/v1/invoices/in_1/pay"), ("POST", "/v1/charges"), ("POST", "/v1/payment_intents")]:
        assert not any(m == method and p.fullmatch(path) for m, p in routes), (method, path)


def test_customer_create_card_and_request(stripe):
    card, key, result = approve_and_run({"action": "customer_create", "mode": "test", "name": "Bob",
                                         "email": "bob@example.com", "metadata": {"plan": "pro", "old": ""}})
    assert card.splitlines()[:8] == ["Stripe · Create a customer", "✅ Test mode: no real money or customers",
                                     "Account: work", "Mode: test", "", "--- Change ---", "Name: Bob",
                                     "Email: bob@example.com"]
    assert "Metadata: plan=pro, old removed" in card and key.startswith("stripe-access:customer_create:")
    [sent] = stripe.sent()
    assert sent["method"] == "POST" and sent["path"] == "/v1/customers"
    assert sent["params"] == [["name", "Bob"], ["email", "bob@example.com"], ["metadata[plan]", "pro"],
                              ["metadata[old]", ""]]
    assert result["ok"] is True and result["done"] == ["creating the customer (obj_new)"]


def test_the_account_name_is_on_the_card_once_known(stripe):
    sta.remember_account("work", "live", {"id": "acct_1", "name": "Shop"})
    card = sta.preview({"action": "customer_create", "mode": "live", "name": "Bob"})["card"]
    assert card.splitlines()[:4] == ["Stripe · Create a customer", "✅ A record only: nothing is charged or sent",
                                     "Account: work (Shop)", "Mode: LIVE, real money"]


@pytest.mark.parametrize("action", sorted(sta.WRITES))
def test_every_change_has_a_title_and_its_stakes_in_live_mode(action):
    assert action in sta.TITLES and action in sta.EFFECTS
    once = action in sta.ONCE and action not in ("invoice_send", "subscription_update")
    # what cannot be undone is marked so; a card asked every time is never marked as staying the user's
    assert (sta.EFFECTS[action][0] == sta.cards.DANGER) == once
    assert action not in sta.ONCE or sta.EFFECTS[action][0] != sta.cards.SAFE


def test_someone_elses_text_cannot_forge_card_lines(stripe):
    stripe.objects["/v1/customers/cus_1"] = {**CUSTOMER, "name": "Ada\nRefund USD 1.00\u202e"}
    card = sta.preview({"action": "customer_update", "mode": "live", "id": "cus_1", "phone": "123"})["card"]
    assert "\nRefund USD 1.00" not in card and "⟨U+202E⟩" in card


def test_a_long_card_counts_what_does_not_fit(stripe):
    metadata = {f"k{n}": "v" * 400 for n in range(3)}
    items = [{"price": "price_a", "quantity": n} for n in range(1, 11)]
    card = sta.preview({"action": "invoice_create", "mode": "live", "customer": "cus_1", "items": items,
                        "metadata": metadata})["card"]
    assert sta.cards.units(card) <= sta.cards.BUDGET
    assert "A draft only" in card and re.search(r"\(\+\d+ more lines\)$", card)


def test_a_card_fits_discord_or_is_refused(stripe, monkeypatch):
    monkeypatch.setattr(sta.cards, "platform", lambda: "discord")
    card = sta.preview({"action": "refund_create", "mode": "live", "payment": "pi_1", "amount": 1500})["card"]
    assert sta.cards.units(card) <= sta.cards.COMPACT_BUDGET and card.split("\n")[1].startswith("🚨 ")
    with pytest.raises(sta.StripeError, match="cannot show this change in full"):
        sta.preview({"action": "customer_create", "mode": "live", "name": "x" * 256, "email": "a@example.com",
                     "description": "d" * 350, "phone": "1" * 20})


def test_invoice_create_builds_a_draft_then_its_lines(stripe):
    stripe.writes[("POST", "/v1/invoices")] = {"id": "in_new", "status": "draft"}
    stripe.objects["/v1/invoices/in_new"] = {"id": "in_new", "status": "draft", "total": 11000, "currency": "jpy"}
    args = {"action": "invoice_create", "mode": "live", "customer": "cus_1", "coupon": "SUMMER10",
            "items": [{"price": "price_a", "quantity": 2}, {"amount": 1000, "currency": "jpy", "description": "Fee"}]}
    card, key, result = approve_and_run(args)
    assert "Draft invoice for Ada <ada@example.com> (cus_1)" in card
    assert "2 lines: JPY 11,000 before discounts and tax" in card
    assert "Paid by: an e-mailed invoice due 30 days after it is finalized" in card
    assert "Discount: coupon SUMMER10 (10% off, for 3 months)" in card
    assert "- 2 × price_a 'Setup' JPY 5,000" in card and "- Fee: JPY 1,000" in card
    invoice, first, second = stripe.sent()
    assert invoice["path"] == "/v1/invoices" and ["auto_advance", "false"] in invoice["params"]
    assert ["currency", "jpy"] in invoice["params"]
    assert ["collection_method", "send_invoice"] in invoice["params"] and ["days_until_due", "30"] in invoice["params"]
    assert ["discounts[0][coupon]", "SUMMER10"] in invoice["params"]
    assert first["path"] == "/v1/invoiceitems" and ["invoice", "in_new"] in first["params"]
    assert ["pricing[price]", "price_a"] in first["params"] and ["quantity", "2"] in first["params"]
    assert ["amount", "1000"] in second["params"] and ["description", "Fee"] in second["params"]
    assert len({invoice["idempotency_key"], first["idempotency_key"], second["idempotency_key"]}) == 3
    assert result["ok"] is True and result["result"]["total_display"] == "JPY 11,000" and "invoice_finalize" in result["next"]


def test_a_line_that_reads_like_a_placeholder_is_sent_as_typed(stripe):
    stripe.writes[("POST", "/v1/invoices")] = {"id": "in_new"}
    approve_and_run({"action": "invoice_create", "mode": "live", "customer": "cus_1",
                     "items": [{"amount": 100, "currency": "jpy", "description": "{0}"}]})
    line = stripe.sent()[1]
    assert ["description", "{0}"] in line["params"] and ["invoice", "in_new"] in line["params"]


def test_without_the_drafts_id_no_line_is_sent(stripe):
    stripe.writes[("POST", "/v1/invoices")] = {"object": "invoice"}   # an answer without an id
    approve_and_run({"action": "invoice_create", "mode": "live", "customer": "cus_1",
                     "items": [{"price": "price_a"}]})
    params = stripe.sent()[1]["params"]
    assert ["invoice", None] in params
    with pytest.raises(bridge_module.Failure):   # the real bridge refuses it before anything is sent
        bridge_module.encode(params)


@pytest.mark.parametrize("items, message", [
    ([{"price": "price_m"}], "must be an active one-time price"),
    ([{"price": "price_a"}, {"amount": 100, "currency": "usd", "description": "x"}], "one currency"),
    ([{"amount": 100, "currency": "jpy"}], "needs a description"),
    ([{"amount": 100, "currency": "jpy", "description": "x", "quantity": 2}], "has no quantity"),
    ([{"price": "price_a", "amount": 5}], "a line is a price"),
    ([], "items must be a list of 1 to 10"),
    ([{"price": "price_a", "tax": 1}], "does not take tax"),
])
def test_invoice_lines_are_checked_before_any_card(stripe, items, message):
    with pytest.raises(sta.StripeError, match=message):
        sta.approval_request({"action": "invoice_create", "mode": "live", "customer": "cus_1", "items": items},
                             can_write=True)
    assert stripe.sent() == [] and sta._approved == {}


def test_a_failed_later_step_stops_part_way(stripe):
    stripe.writes[("POST", "/v1/invoices")] = {"id": "in_new"}
    stripe.writes[("POST", "/v1/invoiceitems")] = {"ok": False, "kind": "invalid", "status": 400, "requests": 1,
                                                   "error": "No such price"}
    _, _, result = approve_and_run({"action": "invoice_create", "mode": "live", "customer": "cus_1",
                                    "items": [{"price": "price_a"}]})
    assert result["ok"] is False and result["error"].startswith("stopped part way:")
    assert result["done"] == ["creating the draft invoice (in_new)"]


@pytest.mark.parametrize("reply, outcome", [
    ({"ok": False, "kind": "invalid", "status": 400, "requests": 1, "error": "bad"}, "not done"),
    ({"ok": False, "kind": "limited", "status": 429, "requests": 1, "error": "slow down"}, "not done"),
    ({"ok": False, "kind": "account", "requests": 0, "error": "key changed"}, "not done"),
    ({"ok": False, "kind": "conflict", "status": 409, "requests": 1, "error": "in progress"}, "UNCERTAIN"),
    ({"ok": False, "kind": "api", "status": 500, "requests": 1, "error": "oops"}, "UNCERTAIN"),
    ({"ok": False, "kind": "network", "requests": 1, "error": "reset"}, "UNCERTAIN"),
])
def test_outcomes_are_never_guessed(stripe, reply, outcome):
    stripe.writes[("POST", "/v1/refunds")] = reply
    _, _, result = approve_and_run({"action": "refund_create", "mode": "live", "charge": "ch_1"})
    assert result["ok"] is False and result["error"].startswith(outcome)
    assert result.get("uncertain", False) == (outcome == "UNCERTAIN")
    assert len(stripe.sent()) == 1   # never retried


def test_a_bridge_without_an_answer_is_uncertain(stripe, monkeypatch):
    sta.approval_request({"action": "refund_create", "mode": "live", "charge": "ch_1"}, call_id="c1", can_write=True)
    original = sta.bridge

    def silent(op, **fields):
        if op == "call" and fields["method"] == "POST":
            raise sta.Uncertain("Stripe did not answer within 90s")
        return original(op, **fields)
    monkeypatch.setattr(sta, "bridge", silent)
    result = sta.execute({"action": "refund_create", "mode": "live", "charge": "ch_1"}, call_id="c1", can_write=True)
    assert result["uncertain"] is True and "refunding charge ch_1 was sent" in result["error"]


def test_a_refund_names_what_was_paid_and_refunded(stripe):
    card, key, result = approve_and_run({"action": "refund_create", "mode": "live", "payment": "pi_1",
                                         "amount": 1500, "reason": "requested_by_customer"})
    assert "Refund USD 15.00 (part) of payment pi_1" in card
    assert "Paid USD 50.00, refunded before USD 10.00, by Ada <ada@example.com> (cus_1)" in card
    assert "Reason: requested_by_customer" in card
    [get_pi] = [r for r in stripe.requests if r.get("path") == "/v1/payment_intents/pi_1"][:1]
    assert get_pi["params"] == [["expand[]", "latest_charge"]]
    [sent] = stripe.sent()
    assert sent["params"] == [["payment_intent", "pi_1"], ["amount", "1500"], ["reason", "requested_by_customer"]]


def test_a_refund_defaults_to_what_is_left_and_never_more(stripe):
    card = sta.preview({"action": "refund_create", "mode": "live", "charge": "ch_1"})["card"]
    assert "Refund USD 40.00 (all that is left) of charge ch_1" in card
    with pytest.raises(sta.StripeError, match="more than the USD 40.00 left"):
        sta.preview({"action": "refund_create", "mode": "live", "charge": "ch_1", "amount": 4001})
    stripe.objects["/v1/charges/ch_1"] = {**CHARGE, "amount_refunded": 5000}
    with pytest.raises(sta.StripeError, match="already refunded in full"):
        sta.preview({"action": "refund_create", "mode": "live", "charge": "ch_1"})
    with pytest.raises(sta.StripeError, match="one of them"):
        sta.preview({"action": "refund_create", "mode": "live", "charge": "ch_1", "payment": "pi_1"})


def test_a_card_that_changed_before_the_write_sends_nothing(stripe):
    args = {"action": "refund_create", "mode": "live", "charge": "ch_1", "amount": 100}
    sta.approval_request(args, call_id="c1", can_write=True)
    stripe.objects["/v1/charges/ch_1"] = {**CHARGE, "amount_refunded": 2000}   # someone refunded meanwhile
    result = sta.execute(args, call_id="c1", can_write=True)
    assert result["ok"] is False and "changed before the write ran" in result["error"] and stripe.sent() == []


def test_subscription_update_changes_the_one_item(stripe):
    card, key, _ = approve_and_run({"action": "subscription_update", "mode": "live", "id": "sub_1",
                                    "price": "price_y", "quantity": 3, "proration": "always_invoice"})
    assert "Change subscription sub_1 of Ada <ada@example.com> (cus_1) (active)" in card
    assert "Item si_1: 1 × price_m JPY 1,000 / 1 month" in card and "Becomes: 3 × price_y JPY 10,000 / 1 year" in card
    assert "Prorations: always_invoice (invoice the difference now)" in card
    [sent] = stripe.sent()
    assert sent["params"] == [["items[0][id]", "si_1"], ["items[0][price]", "price_y"], ["items[0][quantity]", "3"],
                              ["proration_behavior", "always_invoice"]]
    assert re.fullmatch(r"stripe-access:subscription_update:[0-9a-f]{16}", key)


@pytest.mark.parametrize("quantity", [5, 0])
def test_a_price_change_keeps_the_quantity(stripe, quantity):
    stripe.objects["/v1/subscriptions/sub_1"] = {**SUBSCRIPTION, "items": {"data": [
        {"id": "si_1", "quantity": quantity, "price": MONTHLY}]}}
    card, _, _ = approve_and_run({"action": "subscription_update", "mode": "live", "id": "sub_1", "price": "price_y"})
    assert f"Item si_1: {quantity} × price_m" in card and f"Becomes: {quantity} × price_y JPY 10,000 / 1 year" in card
    assert ["items[0][quantity]", str(quantity)] in stripe.sent()[0]["params"]


def test_a_quantity_change_is_bound_to_the_price_it_was_approved_on(stripe):
    args = {"action": "subscription_update", "mode": "live", "id": "sub_1", "quantity": 2}
    card, _ = sta.approval_request(args, call_id="c1", can_write=True)
    assert "Becomes: 2 × price_m JPY 1,000 / 1 month" in card
    stripe.objects["/v1/subscriptions/sub_1"] = {**SUBSCRIPTION, "items": {"data": [
        {"id": "si_1", "quantity": 1, "price": YEARLY}]}}   # the price changed in the Dashboard meanwhile
    result = sta.execute(args, call_id="c1", can_write=True)
    assert "changed before the write ran" in result["error"] and stripe.sent() == []


def test_subscription_update_with_several_items_needs_the_item(stripe):
    stripe.objects["/v1/subscriptions/sub_1"] = {**SUBSCRIPTION, "items": {"data": [
        {"id": "si_1", "quantity": 1, "price": MONTHLY}, {"id": "si_2", "quantity": 1, "price": MONTHLY}]}}
    with pytest.raises(sta.StripeError, match=r"has 2 items \(si_1, si_2\)"):
        sta.preview({"action": "subscription_update", "mode": "live", "id": "sub_1", "quantity": 2})
    card = sta.preview({"action": "subscription_update", "mode": "live", "id": "sub_1", "item": "si_2",
                        "quantity": 2})["card"]
    assert "Item si_2: 1 × price_m" in card and "Becomes: 2 × price_m" in card
    with pytest.raises(sta.StripeError, match="must be an active recurring price"):
        sta.preview({"action": "subscription_update", "mode": "live", "id": "sub_1", "item": "si_2",
                     "price": "price_a"})


def test_ending_at_the_period_end_and_a_discount(stripe):
    card, _, _ = approve_and_run({"action": "subscription_update", "mode": "live", "id": "sub_1",
                                  "cancel_at_period_end": True, "promotion_code": "promo_1"})
    assert "Ends when the current period ends" in card
    assert "Discount: promotion code WELCOME (10% off, for 3 months)" in card
    [sent] = stripe.sent()
    assert sent["params"] == [["cancel_at_period_end", "true"], ["discounts[0][promotion_code]", "promo_1"]]


def test_subscription_cancel_is_a_delete_with_its_options(stripe):
    card, _, _ = approve_and_run({"action": "subscription_cancel", "mode": "live", "id": "sub_1", "prorate": True})
    assert "Cancel subscription sub_1 of Ada <ada@example.com> (cus_1) now" in card
    assert "cannot be resumed" in card and "Final invoice now: no; prorated credit: yes" in card
    [sent] = stripe.sent()
    assert sent["method"] == "DELETE" and sent["params"] == [["prorate", "true"]] and sent["idempotency_key"] is None
    stripe.objects["/v1/subscriptions/sub_1"] = {**SUBSCRIPTION, "status": "canceled"}
    with pytest.raises(sta.StripeError, match="is canceled"):
        sta.preview({"action": "subscription_cancel", "mode": "live", "id": "sub_1"})


def test_coupon_create_terms_and_limits(stripe):
    card, _, _ = approve_and_run({"action": "coupon_create", "mode": "live", "id": "LAUNCH", "amount": 500,
                                  "currency": "JPY", "duration": "once", "max_redemptions": 100,
                                  "redeem_by": 1900000000})
    assert "Create coupon LAUNCH: JPY 500 off, once" in card and "Redeemable 100 times at most" in card
    [sent] = stripe.sent()
    assert sent["params"] == [["amount_off", "500"], ["currency", "jpy"], ["duration", "once"], ["id", "LAUNCH"],
                              ["max_redemptions", "100"], ["redeem_by", "1900000000"]]


@pytest.mark.parametrize("args, message", [
    ({"percent_off": 10, "amount": 100, "currency": "jpy", "duration": "once"}, "one of them"),
    ({"percent_off": 0, "duration": "once"}, "above 0"),
    ({"percent_off": 10}, "duration is required"),
    ({"percent_off": 10, "duration": "repeating"}, "duration_in_months goes with"),
    ({"percent_off": 10, "duration": "once", "duration_in_months": 3}, "duration_in_months goes with"),
    ({"percent_off": 10, "duration": "once", "redeem_by": "2001-01-01"}, "must be in the future"),
    ({"percent_off": 10, "duration": "once", "id": "a b"}, "id \\(the coupon's own id\\)"),
])
def test_coupon_create_is_checked(stripe, args, message):
    with pytest.raises(sta.StripeError, match=message):
        sta.preview({"action": "coupon_create", "mode": "live", **args})


def test_coupon_delete_says_what_stays(stripe):
    card, key, result = approve_and_run({"action": "coupon_delete", "mode": "live", "id": "SUMMER10"})
    assert "Delete coupon SUMMER10: 10% off, for 3 months, redeemed 4 times" in card
    assert "discounts already applied stay" in card
    assert stripe.sent()[0]["method"] == "DELETE"
    with pytest.raises(sta.StripeError, match="only name and metadata"):
        sta.preview({"action": "coupon_update", "mode": "live", "id": "SUMMER10"})


def test_promotion_code_create_uses_the_current_api_shape(stripe):
    card, _, _ = approve_and_run({"action": "promotion_code_create", "mode": "live", "coupon": "SUMMER10",
                                  "code": "WELCOME10", "customer": "cus_1", "first_time": True,
                                  "minimum_amount": 3000, "currency": "jpy"})
    assert "Create promotion code WELCOME10 for coupon SUMMER10: 10% off, for 3 months" in card
    assert "Only for Ada <ada@example.com> (cus_1)" in card and "Minimum order: JPY 3,000" in card
    [sent] = stripe.sent()
    assert sent["params"][:3] == [["promotion[type]", "coupon"], ["promotion[coupon]", "SUMMER10"],
                                  ["code", "WELCOME10"]]
    assert ["restrictions[first_time_transaction]", "true"] in sent["params"]
    assert ["restrictions[minimum_amount_currency]", "jpy"] in sent["params"]


def test_invoice_lifecycle_cards(stripe):
    card = sta.preview({"action": "invoice_finalize", "mode": "live", "id": "in_1"})["card"]
    assert "Finalize invoice in_1 for Ada <ada@example.com> (cus_1): JPY 12,000" in card
    assert "Nothing is e-mailed before invoice_send." in card
    with pytest.raises(sta.StripeError, match="is draft; this needs it open or paid"):
        sta.preview({"action": "invoice_send", "mode": "live", "id": "in_1"})
    stripe.objects["/v1/invoices/in_1"] = {**stripe.objects["/v1/invoices/in_1"], "status": "open",
                                           "number": "ABC-0001", "due_date": 1800000000}
    card = sta.preview({"action": "invoice_send", "mode": "test", "id": "in_1"})["card"]
    assert "E-mail invoice ABC-0001 for Ada" in card and "To: ada@example.com; open, due" in card
    assert "Test mode: Stripe sends no e-mail." in card
    card = sta.preview({"action": "invoice_void", "mode": "live", "id": "in_1"})["card"]
    assert "Void invoice ABC-0001" in card and "cannot be undone" in card


def test_payment_link_create_and_deactivate(stripe):
    card, _, _ = approve_and_run({"action": "payment_link_create", "mode": "live", "allow_promotion_codes": True,
                                  "items": [{"price": "price_m", "quantity": 2}]})
    assert "Create a payment link: 1 item, JPY 2,000 at checkout" in card
    assert card.split("\n")[1] == "⚠️ Anyone with the link can pay"
    assert "Checkout starts a subscription that bills again:\n- 2 × price_m JPY 1,000 / 1 month" in card
    assert stripe.sent()[0]["params"] == [["line_items[0][price]", "price_m"], ["line_items[0][quantity]", "2"],
                                          ["allow_promotion_codes", "true"]]
    card = sta.preview({"action": "payment_link_update", "mode": "live", "id": "plink_1", "active": False})["card"]
    assert "Deactivate payment link plink_1 (https://buy.stripe.com/x)" in card and "Accepts payments: true → false" in card


def test_recurring_billing_is_never_cut_from_a_payment_link_card(stripe):
    for n in range(1, 16):
        stripe.objects[f"/v1/prices/price_o{n}"] = {**ONE_TIME, "id": f"price_o{n}", "nickname": "x" * 20}
    items = [{"price": f"price_o{n}"} for n in range(1, 16)] + [{"price": "price_m"}]
    card = sta.preview({"action": "payment_link_create", "mode": "live", "items": items})["card"]
    assert "more lines)" in card and "- 1 × price_m JPY 1,000 / 1 month" in card
    assert sta.cards.units(card) <= sta.cards.BUDGET


def test_price_and_product_changes(stripe):
    card = sta.preview({"action": "price_create", "mode": "live", "product": "prod_1", "amount": 1200,
                        "currency": "usd", "interval": "month"})["card"]
    assert "Create price for product Plan (prod_1): USD 12.00 / 1 month" in card
    with pytest.raises(sta.StripeError, match="does not take amount"):
        sta.preview({"action": "price_update", "mode": "live", "id": "price_m", "amount": 2000})
    card = sta.preview({"action": "price_update", "mode": "live", "id": "price_m", "active": False})["card"]
    assert "Active (can be bought): true → false" in card
    card = sta.preview({"action": "product_create", "mode": "live", "name": "Pro", "amount": 3000,
                        "currency": "jpy", "interval": "year", "interval_count": 1})["card"]
    assert "Default price: JPY 3,000 / 1 year" in card
    with pytest.raises(sta.StripeError, match="needs amount"):
        sta.preview({"action": "product_create", "mode": "live", "name": "Pro", "currency": "jpy"})


def test_a_preview_reads_only(stripe):
    result = sta.execute({"action": "coupon_delete", "mode": "live", "id": "SUMMER10", "preview": True},
                         can_write=True)
    assert result["preview"] is True and result["requests"] == 1 and stripe.sent() == []
    with pytest.raises(sta.StripeError, match="can read Stripe but not change"):
        sta.execute({"action": "coupon_delete", "mode": "live", "id": "SUMMER10", "preview": True}, can_write=False)


def test_idempotency_keys_are_per_approval_and_step(stripe):
    assert sta._idempotency_key("n1", 0) == sta._idempotency_key("n1", 0)
    assert len({sta._idempotency_key("n1", 0), sta._idempotency_key("n1", 1), sta._idempotency_key("n2", 0)}) == 3
    assert re.fullmatch(r"hermes-[0-9a-f]{40}", sta._idempotency_key("n1", 0))
    # the same change approved twice, even under a provider's reused call id, gets new keys
    args = {"action": "customer_create", "mode": "live", "name": "Bob"}
    approve_and_run(args, call_id="call_0")
    approve_and_run(args, call_id="call_0")
    first, second = stripe.sent()
    assert first["idempotency_key"] != second["idempotency_key"]


def test_an_approval_expires(stripe, monkeypatch):
    args = {"action": "customer_create", "mode": "live", "name": "Bob"}
    sta.approval_request(args, call_id="c1", can_write=True)
    clock = [sta.time.monotonic() + sta.APPROVAL_TTL + 1]
    monkeypatch.setattr(sta.time, "monotonic", lambda: clock[0])
    assert "did not pass its approval card" in sta.execute(args, call_id="c1", can_write=True)["error"]
    assert stripe.sent() == []
