"""send_mandate: the terms, the card, the fit checks and the hourly ledger of a WhatsApp
send mandate, over a fake Keychain CLI; nothing outside the temporary folder is touched."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import threading
import time

import pytest

spec = importlib.util.spec_from_file_location(
    "hermes_send_mandate",
    Path(__file__).resolve().parents[1] / "send_mandate.py",
)
sm = importlib.util.module_from_spec(spec)
sys.modules["hermes_send_mandate"] = sm
spec.loader.exec_module(sm)
mandate_store, cards = sm.mandate_store, sm.cards

KEY = bytes(range(32))
ALICE = {"id": "1001", "name": "Alice", "kind": "user", "identity": "@alice"}
TEAM = {"id": "-2002", "name": "Team", "kind": "group", "identity": "id -2002"}
SAY = lambda text, limit: cards.clip(" ".join(str(text).split()), limit)  # noqa: E731


def chat(n, name="N", kind="user", **over):
    return {"id": str(n), "name": name, "kind": kind, "identity": f"id {n}", **over}


def fake_cli(path: Path, keyfile: Path, calls: Path | None = None) -> Path:
    """A secret CLI over one key file: ``get`` prints it, ``show`` says it exists, ``set --stdin`` stores it.
    With ``calls`` every call appends its command word to that file."""
    log = f"echo \"$1\" >> {calls}\n" if calls else ""
    path.write_text(
        "#!/bin/sh\n"
        + log +
        f"[ \"$1\" = get ] && [ -f {keyfile} ] && cat {keyfile} && exit 0\n"
        f"[ \"$1\" = show ] && [ -f {keyfile} ] && exit 0\n"
        f"[ \"$1\" = set ] && [ ! -f {keyfile} ] && cat > {keyfile} && exit 0\n"
        "exit 1\n")
    path.chmod(0o755)
    return path


@pytest.fixture
def keyfile(tmp_path, monkeypatch):
    keyfile = tmp_path / "keyfile"
    monkeypatch.setattr(mandate_store, "SECRET", fake_cli(tmp_path / "secret", keyfile))
    keyfile.write_text(KEY.hex() + "\n")
    return keyfile


@pytest.fixture
def home(tmp_path):
    return tmp_path / "profile"


def terms(service="whatsapp", **over):
    args = {"account": "acct", "chats": [ALICE], "per_hour": 3, "max_chars": 100, "days": 7,
            "purpose": "Send the morning report"}
    args.update(over)
    return sm.terms(service, args.pop("account"), args.pop("chats"), args.pop("per_hour"),
                    args.pop("max_chars"), args.pop("days"), args.pop("purpose"), **args)


def make(home, service="whatsapp", **over) -> str:
    return sm.create(home, terms(service, **over))["id"]


def view(**over):
    return {"service": "whatsapp", "account": "acct", "chat": "1001", "text": "good morning",
            "files": 0, "reply": False, **over}


# --- terms ----------------------------------------------------------------------------------------

def test_terms_are_read_and_the_end_is_fixed_now():
    t = terms(chats=[ALICE, TEAM], purpose="  Send the\n morning   report ", now=1_000_000)
    assert t == {"service": "whatsapp", "account": "acct", "account_label": None, "chats": [ALICE, TEAM],
                 "per_hour": 3, "max_chars": 100, "days": 7, "expires": 1_000_000 + 7 * 86400,
                 "purpose": "Send the morning report"}


def test_an_account_label_is_kept_as_one_line():
    assert terms(account_label=" Rui\n (@rui) ")["account_label"] == "Rui (@rui)"
    assert terms(account_label="x" * 120)["account_label"] == "x" * 120


@pytest.mark.parametrize("label", ["", "  ", 7, True, ["Rui"], "x" * 121])
def test_an_account_label_is_held(label):
    with pytest.raises(sm.MandateError, match="account_label"):
        terms(account_label=label)


def test_terms_of_an_unknown_service_are_refused():
    with pytest.raises(sm.MandateError, match="service is one of"):
        terms("discord")
    with pytest.raises(sm.MandateError, match="service is one of"):
        sm.store("discord")


def test_telegram_is_not_a_service_any_more():
    assert list(sm.SERVICES) == ["whatsapp"]
    with pytest.raises(sm.MandateError, match="service is one of: whatsapp"):
        terms("telegram")
    with pytest.raises(sm.MandateError, match="service is one of: whatsapp"):
        sm.store("telegram")


def test_signal_is_not_a_service_any_more():
    assert "signal" not in sm.SERVICES
    with pytest.raises(sm.MandateError, match="service is one of"):
        terms("signal")
    with pytest.raises(sm.MandateError, match="service is one of"):
        sm.store("signal")


@pytest.mark.parametrize("field,bad,message", [
    ("per_hour", 0, "per_hour is a whole number from 1 to 5"),
    ("per_hour", 6, "per_hour is a whole number from 1 to 5"),
    ("per_hour", True, "per_hour is a whole number"),
    ("per_hour", 2.0, "per_hour is a whole number"),
    ("per_hour", "3", "per_hour is a whole number"),
    ("max_chars", 0, "max_chars is a whole number from 1 to 1000"),
    ("max_chars", 1001, "max_chars is a whole number from 1 to 1000"),
    ("max_chars", True, "max_chars is a whole number"),
    ("days", 0, "days is a whole number from 1 to 30"),
    ("days", 31, "days is a whole number from 1 to 30"),
    ("days", True, "days is a whole number"),
    ("days", None, "days is a whole number"),
    ("account", "", "account names"),
    ("account", "  ", "account names"),
    ("account", 7, "account names"),
    ("purpose", "", "purpose says what"),
    ("purpose", " \n\t ", "purpose says what"),
    ("purpose", "x" * 201, "purpose is at most 200"),
    ("chats", [], "one to 5 chats"),
    ("chats", "1001", "one to 5 chats"),
    ("chats", [ALICE] * 1 + [chat(n) for n in range(5)], "one to 5 chats"),
])
def test_each_bound_of_the_terms_is_held(field, bad, message):
    with pytest.raises(sm.MandateError, match=message):
        terms(**{field: bad})


@pytest.mark.parametrize("per_hour,days", [(1, 1), (5, 30)])
def test_the_bounds_themselves_are_allowed(per_hour, days):
    t = terms(per_hour=per_hour, days=days, max_chars=days * 33)
    assert (t["per_hour"], t["days"]) == (per_hour, days)
    assert terms(max_chars=1000)["max_chars"] == 1000


def test_the_hourly_ceiling_is_the_services_own():
    assert sm.SERVICES["whatsapp"]["max_per_hour"] == 5 <= sm.MAX_PER_HOUR
    assert terms("whatsapp", per_hour=5)["per_hour"] == 5
    with pytest.raises(sm.MandateError, match="per_hour is a whole number from 1 to 5"):
        terms("whatsapp", per_hour=6)


def test_a_service_below_the_absolute_ceiling_names_its_own_in_the_refusal():
    with pytest.raises(sm.MandateError, match=r"from 1 to 5 \(WhatsApp allows at most 5 sends an hour\)"):
        terms("whatsapp", per_hour=6)
    with pytest.raises(sm.MandateError, match="WhatsApp allows at most 5"):
        terms("whatsapp", per_hour=30)
    with pytest.raises(sm.MandateError, match="per_hour is a whole number from 1 to 5"):
        terms("whatsapp", per_hour=0)


def test_whatsapp_terms_are_read_like_the_others():
    chats = [{"id": "819011111111@s.whatsapp.net", "name": "Alice", "kind": "user", "identity": "+819011111111"},
             {"id": "120363001234567890@g.us", "name": "Team", "kind": "group",
              "identity": "120363001234567890@g.us"}]
    t = terms("whatsapp", chats=chats, per_hour=5, account="work", account_label="work", now=1_000_000)
    assert t["service"] == "whatsapp" and t["chats"] == chats and t["per_hour"] == 5
    lines = sm.card(t, SAY).splitlines()
    assert lines[0] == "WhatsApp · Send mandate"
    assert "Chat: Alice (user, +819011111111)" in lines
    assert "Chat: Team (group, 120363001234567890@g.us)" in lines
    assert "Up to: 5 an hour, 100 characters each" in lines


def test_five_chats_are_allowed_and_six_are_not():
    five = [chat(n, f"Chat {n}", "group") for n in range(5)]
    assert len(terms(chats=five)["chats"]) == 5
    with pytest.raises(sm.MandateError, match="one to 5 chats"):
        terms(chats=five + [ALICE])


def test_a_purpose_longer_than_the_limit_only_before_collapse_is_allowed():
    assert terms(purpose="a    " * 40)["purpose"] == " ".join(["a"] * 40)
    assert len(terms(purpose="x" * 200)["purpose"]) == 200


@pytest.mark.parametrize("kind,allowed", [
    ("user", True), ("group", True), ("self", False), ("supergroup", False), ("bot", False),
    ("channel", False), ("broadcast", False), ("lid", False), ("newsletter", False), ("", False),
    (None, False), ("forum", False),
])
def test_chat_kinds_are_held(kind, allowed):
    chats = [chat(1, "X", kind)]
    if allowed:
        assert terms(chats=chats)["chats"][0]["kind"] == kind
    else:
        with pytest.raises(sm.MandateError):
            terms(chats=chats)


def test_a_bot_or_a_channel_is_refused_in_words():
    with pytest.raises(sm.MandateError, match="Newsroom is a channel: a mandate never covers bots or broadcast"):
        terms(chats=[chat(9, "Newsroom", "channel")])
    with pytest.raises(sm.MandateError, match="Helper is a bot"):
        terms(chats=[chat(9, "Helper", "bot")])


@pytest.mark.parametrize("bad", [
    "1001", None, {"name": "Alice", "kind": "user", "identity": "@alice"},
    {"id": "", "name": "Alice", "kind": "user", "identity": "@alice"},
    {"id": "  ", "name": "Alice", "kind": "user", "identity": "@alice"},
    {"id": 1001, "name": "Alice", "kind": "user", "identity": "@alice"},
    {"id": True, "name": "Alice", "kind": "user", "identity": "@alice"},
])
def test_a_chat_needs_an_id(bad):
    with pytest.raises(sm.MandateError, match="each chat"):
        terms(chats=[bad])


@pytest.mark.parametrize("identity", [None, "", "  \n ", 1001, True, ["@alice"], "x" * 81])
def test_a_chat_needs_an_identity(identity):
    with pytest.raises(sm.MandateError, match="each chat has an identity"):
        terms(chats=[{**ALICE, "identity": identity}])
    without = {k: v for k, v in ALICE.items() if k != "identity"}
    with pytest.raises(sm.MandateError, match="each chat has an identity"):
        terms(chats=[without])


def test_an_identity_is_one_line_and_may_fill_its_limit():
    t = terms(chats=[{**ALICE, "identity": " @al\n ice "}, {**TEAM, "identity": "x" * 80}])
    assert [c["identity"] for c in t["chats"]] == ["@al ice", "x" * 80]


def test_chat_ids_are_unique():
    with pytest.raises(sm.MandateError, match="each chat is named once"):
        terms(chats=[ALICE, {**TEAM, "id": " 1001 "}])


def test_a_chat_name_is_one_line_and_falls_back_to_its_id():
    t = terms(chats=[{**ALICE, "name": " Alice\n  A. "}, {"id": "7", "kind": "user", "identity": "id 7"}])
    assert [c["name"] for c in t["chats"]] == ["Alice A.", "7"]


def test_same_terms_ignore_only_the_end():
    a, b = terms(now=1_000), terms(now=2_000)
    assert a["expires"] != b["expires"] and sm.same_terms(a, b)
    for field, other in (("per_hour", 4), ("max_chars", 99), ("days", 8), ("purpose", "Other"), ("account", "x"),
                         ("account_label", "Rui (@rui)"), ("chats", [TEAM]), ("chats", [ALICE, TEAM]),
                         ("chats", [{**ALICE, "identity": "@mallory"}]), ("chats", [{**ALICE, "name": "Mom"}])):
        assert not sm.same_terms(a, terms(**{field: other, "now": 1_000})), field


# --- the card -------------------------------------------------------------------------------------

def test_the_card_shows_every_bound():
    t = terms(chats=[ALICE, TEAM], now=time.time())
    lines = sm.card(t, SAY).splitlines()
    assert lines[0] == "WhatsApp · Send mandate"
    assert lines[1] == "🚨 Plain text sends to these chats skip the card"
    assert "Chat: Alice (user, @alice)" in lines and "Chat: Team (group, id -2002)" in lines
    assert "Account: acct" in lines
    assert "Up to: 3 an hour, 100 characters each" in lines
    assert "Purpose: Send the morning report" in lines
    until = next(line for line in lines if line.startswith("Until: "))
    assert until.endswith("(7 days)") and time.strftime("%Y-%m-%d %H:%M", time.localtime(t["expires"])) in until
    assert lines[-1] == "Never covered: files, quotes, replies, other chats or accounts, and channels"


def test_the_card_names_its_service_and_a_single_day():
    card = sm.card(terms("whatsapp", days=1), SAY)
    assert card.splitlines()[0] == "WhatsApp · Send mandate"
    assert "(1 day)" in card


def test_long_names_and_purposes_shrink_until_the_card_fits():
    chats = [chat(n, f"{n} " + "Name " * 40, "group") for n in range(5)]
    t = terms(chats=chats, purpose="Reason " * 28)
    text = sm.card(t, SAY)
    assert cards.units(text) <= cards.budget()
    assert text.count("Chat: ") == 5 and "…" in text
    assert all(f"(group, id {n})" in text for n in range(5))
    assert "Up to: 3 an hour, 100 characters each" in text


def test_a_card_that_cannot_show_all_its_bounds_is_refused():
    t = terms(account="a" * 600)
    with pytest.raises(sm.MandateError, match="name fewer chats"):
        sm.card(t, SAY)
    t = terms(account_label="a" * 120, chats=[chat(n, "N", "group", identity="i" * 80) for n in range(5)])
    with pytest.raises(sm.MandateError, match="name fewer chats"):
        sm.card(t, SAY)


def test_the_card_shows_the_account_label_in_place_of_the_account_id():
    lines = sm.card(terms(account="1000", account_label="Rui (@rui)"), SAY).splitlines()
    assert "Account: Rui (@rui)" in lines and "Account: 1000" not in lines


def test_two_chats_with_one_name_render_different_lines():
    lines = sm.card(terms(chats=[{**ALICE, "name": "Mom"}, {**TEAM, "name": "Mom", "kind": "user"}]), SAY).splitlines()
    chat_lines = [line for line in lines if line.startswith("Chat: ")]
    assert chat_lines == ["Chat: Mom (user, @alice)", "Chat: Mom (user, id -2002)"]


def test_an_identity_is_never_clipped_only_the_name_and_purpose_shrink():
    chats = [chat(n, "Name " * 40, "group", identity=f"{n}" + "h" * 49) for n in range(2)]
    text = sm.card(terms(chats=chats, purpose="Reason " * 28), SAY)
    assert all(f"({c['kind']}, {c['identity']})" in text for c in chats)
    assert text.count("Chat: ") == 2 and "…" in text


def test_a_stranger_named_chat_shows_its_own_handle():
    mom = {**ALICE, "name": "Mom", "identity": "@mallory"}
    assert "Chat: Mom (user, @mallory)" in sm.card(terms(chats=[mom]), SAY).splitlines()


def test_control_and_bidi_characters_in_an_identity_are_spelled_out():
    spoof = {**ALICE, "identity": "@al\u202eice\x07"}
    text = sm.card(terms(chats=[spoof]), SAY)
    assert "\u202e" not in text and "\x07" not in text
    assert "Chat: Alice (user, @al⟨U+202E⟩ice⟨U+0007⟩)" in text.splitlines()


# --- creating, listing and ending ------------------------------------------------------------------

def test_a_mandate_is_made_listed_and_revoked(keyfile, home):
    made = sm.create(home, terms(chats=[ALICE, TEAM], account_label="Rui (@rui)"))
    assert made["chats"] == ["Alice (@alice)", "Team (id -2002)"] and made["service"] == "whatsapp"
    assert (made["per_hour"], made["max_chars"], made["purpose"]) == (3, 100, "Send the morning report")
    assert set(made) == {"id", "until", "chats", "per_hour", "max_chars", "purpose", "service"}
    body, = sm.active(home, "whatsapp")
    assert body["id"] == made["id"] and body["account"] == "acct" and body["chats"] == [ALICE, TEAM]
    assert body["account_label"] == "Rui (@rui)"
    assert sm.summary(body) == made
    assert sm.revoke(home, "whatsapp", made["id"]) == {"revoked": made["id"]}
    assert sm.active(home, "whatsapp") == []
    assert sm.revoke(home, "whatsapp", made["id"]) == {"revoked": made["id"], "note": "it was not in force"}


def test_a_mandate_lives_in_its_services_state(keyfile, home):
    make(home)
    assert (home / "whatsapp-access" / "head.json").is_file()
    assert sm.store("whatsapp").max_days == 30
    assert (sm.store("whatsapp").mac_kind, sm.store("whatsapp").key_prefix, sm.store("whatsapp").scope) == (
        "whatsapp-send-mandate", "WHATSAPP_MANDATE_KEY_", "whatsapp-access")


def test_whatsapps_ceiling_is_the_accounts_total_across_its_mandates_in_force(keyfile, home):
    first = make(home, "whatsapp", per_hour=3)
    with pytest.raises(sm.MandateError) as refused:
        make(home, "whatsapp", per_hour=3)
    assert str(refused.value) == ("WhatsApp allows at most 5 sends an hour per account; mandates in force for "
                                  "acct already take 3; nothing was made")
    assert [m["id"] for m in sm.active(home, "whatsapp")] == [first]   # the refused one is not left in force
    second = make(home, "whatsapp", per_hour=2)                         # 3 + 2 fits exactly
    assert {m["id"] for m in sm.active(home, "whatsapp")} == {first, second}
    with pytest.raises(sm.MandateError, match="already take 5"):
        make(home, "whatsapp", per_hour=1)
    sm.revoke(home, "whatsapp", first)                                  # the first one's share is free again
    third = make(home, "whatsapp", per_hour=3)
    assert {m["id"] for m in sm.active(home, "whatsapp")} == {second, third}


def test_the_ceiling_counts_one_account_only(keyfile, home):
    make(home, "whatsapp", per_hour=5)
    other = make(home, "whatsapp", account="other", per_hour=5)
    assert other in {m["id"] for m in sm.active(home, "whatsapp")}
    with pytest.raises(sm.MandateError, match="mandates in force for other already take 5"):
        make(home, "whatsapp", account="other", per_hour=1)


def test_a_refused_mandate_is_never_anchored_and_ends_revoked(keyfile, home):
    first = make(home, "whatsapp", per_hour=4)
    with pytest.raises(sm.MandateError):
        make(home, "whatsapp", per_hour=2)
    rows = (home / "whatsapp-access" / "uses.jsonl").read_text().splitlines()
    assert [json.loads(row)["mandate"] for row in rows] == [first]      # only the first was ever anchored
    events = [json.loads(line) for line in (home / "whatsapp-access" / "mandates.jsonl").read_text().splitlines()]
    assert [e["event"] for e in events] == ["made", "made", "revoked"] and events[1]["mandate"] == events[2]["mandate"]


def test_check_account_ceiling_looks_before_the_card(keyfile, home):
    sm.check_account_ceiling(home, terms("whatsapp", per_hour=5))      # nothing in force yet
    make(home, "whatsapp", per_hour=3)
    sm.check_account_ceiling(home, terms("whatsapp", per_hour=2))
    with pytest.raises(sm.AccountCeilingError, match="already take 3"):
        sm.check_account_ceiling(home, terms("whatsapp", per_hour=3))
    assert sm.account_ceiling_refusal(terms("whatsapp", per_hour=3), []) is None


def test_a_mandate_ends_when_its_card_said(keyfile, home):
    t = terms()
    sm.create(home, t)
    assert sm.active(home, "whatsapp", now=t["expires"] - 1)
    assert sm.active(home, "whatsapp", now=t["expires"]) == []


def test_the_history_file_does_not_decide(keyfile, home):
    mandate_id = make(home)
    sm.revoke(home, "whatsapp", mandate_id)
    with open(home / "whatsapp-access" / "mandates.jsonl", "a") as handle:
        handle.write(json.dumps({"event": "made", "mandate": mandate_id, "time": int(time.time())}) + "\n")
    assert sm.active(home, "whatsapp") == []
    assert sm.use(home, "whatsapp", mandate_id, view()) == f"mandate {mandate_id} is no longer in force"


def test_without_a_key_nothing_is_in_force(keyfile, home):
    mandate_id = make(home)
    keyfile.unlink()
    assert sm.active(home, "whatsapp") == []
    assert sm.covering(home, "whatsapp", view()) == (None, [])
    assert sm.use(home, "whatsapp", mandate_id, view()) == sm.NO_KEY
    assert uses(home) == []


def test_a_service_that_never_made_a_mandate_does_not_ask_the_keychain(tmp_path, monkeypatch, home):
    calls = tmp_path / "calls"
    keyfile = tmp_path / "keyfile"
    keyfile.write_text(KEY.hex() + "\n")
    monkeypatch.setattr(mandate_store, "SECRET", fake_cli(tmp_path / "secret", keyfile, calls))
    assert sm.covering(home, "whatsapp", view()) == (None, [])
    assert not calls.exists()
    make(home)
    calls.unlink()
    assert sm.covering(home, "whatsapp", view())[0] is not None and calls.exists()


# --- does a send fit --------------------------------------------------------------------------------

@pytest.fixture
def mandate():
    t = terms(chats=[ALICE, TEAM], per_hour=2, max_chars=20)
    return {**{k: t[k] for k in ("service", "account", "chats", "per_hour", "max_chars", "purpose")},
            "id": "m1a2b3c4d"}


def test_a_plain_send_to_a_named_chat_fits(mandate):
    assert sm.fits(mandate, view()) is None
    assert sm.fits(mandate, view(chat="-2002", text="x" * 20, files=[], reply=None), used=1) is None


@pytest.mark.parametrize("over,used,reason", [
    ({"service": "discord"}, 0, "the mandate is for whatsapp, not discord"),
    ({"service": None}, 0, "the mandate is for whatsapp"),
    ({"account": "other"}, 0, "another account"),
    ({"account": None}, 0, "another account"),
    ({"chat": "3003"}, 0, "not one the mandate names"),
    ({"chat": None}, 0, "not one the mandate names"),
    ({"files": 1}, 0, "a file"),
    ({"files": ["a.png"]}, 0, "a file"),
    ({"reply": True}, 0, "a quote or a reply"),
    ({"reply": "5"}, 0, "a quote or a reply"),
    ({"text": ""}, 0, "the text is empty"),
    ({"text": "  \n"}, 0, "the text is empty"),
    ({"text": None}, 0, "the text is empty"),
    ({"text": "x" * 21}, 0, "21 characters; the mandate allows 20"),
    ({}, 2, "2 sends in the last hour; the mandate allows 2 an hour"),
    ({}, 9, "the mandate allows 2 an hour"),
])
def test_a_send_that_does_not_fit_says_why(mandate, over, used, reason):
    assert reason in sm.fits(mandate, view(**over), used=used)


def test_accounts_and_chats_compare_as_text(mandate):
    mandate = {**mandate, "account": "42"}
    assert sm.fits(mandate, view(account=42, chat=1001)) is None
    assert sm.fits(mandate, view(account=43)) is not None


def test_the_first_reason_wins(mandate):
    assert "another account" in sm.fits(mandate, view(account="x", chat="9", files=1, text=""), used=5)


def test_covering_picks_the_first_fitting_mandate_and_reports_the_misses(keyfile, home):
    make(home, per_hour=1, max_chars=5)   # whatsapp bounds the account's total: 4 × 1 stays within its 5
    make(home, per_hour=1, chats=[TEAM])
    make(home, per_hour=1, max_chars=500)
    make(home, per_hour=1, max_chars=600)
    # The head lists the ids sorted, so the order of the mandates in force is what ``active`` returns.
    order = [m["id"] for m in sm.active(home, "whatsapp")]
    by_id = {m["id"]: m for m in sm.active(home, "whatsapp")}
    found, misses = sm.covering(home, "whatsapp", view(text="x" * 50))
    fitting = [i for i in order if sm.fits(by_id[i], view(text="x" * 50)) is None]
    assert found == fitting[0] and len(fitting) == 2
    assert [m.split(": ", 1)[0] for m in misses] == order[:order.index(found)]
    assert all(m.split(": ", 1)[1] == sm.fits(by_id[m.split(": ", 1)[0]], view(text="x" * 50)) for m in misses)
    none, all_misses = sm.covering(home, "whatsapp", view(text="x" * 5000))
    assert none is None and [m.split(": ", 1)[0] for m in all_misses] == order


def test_covering_counts_the_hour_per_mandate(keyfile, home):
    ids = [make(home, per_hour=1), make(home, per_hour=1)]
    now = time.time()
    first, misses = sm.covering(home, "whatsapp", view(), now=now)
    assert first in ids and misses == []
    assert sm.use(home, "whatsapp", first, view(), now=now) is None
    second, misses = sm.covering(home, "whatsapp", view(), now=now)
    assert second == next(i for i in ids if i != first)
    assert sm.use(home, "whatsapp", second, view(), now=now) is None
    none, misses = sm.covering(home, "whatsapp", view(), now=now)
    assert none is None and len(misses) == 2
    assert all(m.endswith("1 sends in the last hour; the mandate allows 1 an hour") for m in misses)


# --- the hourly ledger ------------------------------------------------------------------------------

def ledger(home):
    return home / "whatsapp-access" / "uses.jsonl"


def rows(home):
    return [json.loads(line) for line in ledger(home).read_text().splitlines()]


def uses(home):
    """The counted sends in the ledger: its rows but the mandates' opening rows."""
    return [row for row in rows(home) if not row.get("open")]


def test_the_hours_count_is_held_and_the_slot_frees_after_an_hour(keyfile, home):
    mandate_id = make(home, per_hour=2)
    now = time.time()
    assert sm.use(home, "whatsapp", mandate_id, view(), now=now) is None
    assert sm.use(home, "whatsapp", mandate_id, view(), now=now + 10) is None
    refused = sm.use(home, "whatsapp", mandate_id, view(), now=now + 20)
    assert refused == "2 sends in the last hour; the mandate allows 2 an hour"
    assert len(uses(home)) == 2
    assert sm.covering(home, "whatsapp", view(), now=now + 20)[0] is None
    # The first row leaves the window at now + 3600, the second ten seconds later.
    assert sm.use(home, "whatsapp", mandate_id, view(), now=now + 3599) is not None
    assert sm.use(home, "whatsapp", mandate_id, view(), now=now + 3601) is None
    assert sm.use(home, "whatsapp", mandate_id, view(), now=now + 3602) is not None
    assert len(uses(home)) == 3


def test_a_send_that_does_not_fit_is_not_counted(keyfile, home):
    mandate_id = make(home, per_hour=2, max_chars=10)
    assert "allows 10" in sm.use(home, "whatsapp", mandate_id, view(text="x" * 11))
    assert sm.use(home, "whatsapp", mandate_id, view(chat="3003")) is not None
    assert sm.use(home, "whatsapp", mandate_id, view(files=1)) is not None
    assert uses(home) == []


def test_a_use_row_is_authenticated_and_private(keyfile, home):
    mandate_id = make(home)
    now = time.time()
    assert sm.use(home, "whatsapp", mandate_id, view(), now=now) is None
    row, = uses(home)
    assert set(row) == {"mandate", "time", "mac"} and row["mandate"] == mandate_id and row["time"] == int(now)
    assert row["mac"] == mandate_store.mac(KEY, "whatsapp-send-use", row)

    def mode(path):
        return stat.S_IMODE(os.stat(path).st_mode)

    assert mode(home / "whatsapp-access" / "uses.jsonl") == 0o600
    assert mode(home / "whatsapp-access") == 0o700


def test_the_ledger_is_appended_not_rewritten(keyfile, home):
    mandate_id = make(home)
    sm.use(home, "whatsapp", mandate_id, view())
    path = home / "whatsapp-access" / "uses.jsonl"
    first = path.read_text()
    sm.use(home, "whatsapp", mandate_id, view())
    assert path.read_text().startswith(first) and len(uses(home)) == 2


def append_raw(home, text):
    with open(home / "whatsapp-access" / "uses.jsonl", "a") as handle:
        handle.write(text + "\n")


def test_rows_that_are_not_this_mandates_own_count_for_nothing(keyfile, home):
    mandate_id, other_id = make(home, per_hour=1), make(home, per_hour=1)
    now = int(time.time())
    # A bad MAC, another mandate's valid row, a row MAC'd as another kind, a changed time, a wrong key,
    # a row with extras, a bool time, junk and a blank line.
    good = {"mandate": other_id, "time": now}
    append_raw(home, json.dumps({"mandate": mandate_id, "time": now, "mac": "0" * 64}))
    append_raw(home, json.dumps({**good, "mac": mandate_store.mac(KEY, "whatsapp-send-use", good)}))
    other_kind_row = {"mandate": mandate_id, "time": now}
    append_raw(home, json.dumps({**other_kind_row,
                                 "mac": mandate_store.mac(KEY, "whatsapp-send-mandate", other_kind_row)}))
    older = {"mandate": mandate_id, "time": now - 5}
    append_raw(home, json.dumps({**older, "time": now, "mac": mandate_store.mac(KEY, "whatsapp-send-use", older)}))
    wrong_key = {"mandate": mandate_id, "time": now}
    append_raw(home, json.dumps({**wrong_key, "mac": mandate_store.mac(b"\x01" * 32, "whatsapp-send-use", wrong_key)}))
    extra = {"mandate": mandate_id, "time": now, "note": "x"}
    append_raw(home, json.dumps({**extra, "mac": mandate_store.mac(KEY, "whatsapp-send-use", extra)}))
    flag = {"mandate": mandate_id, "time": True}
    append_raw(home, json.dumps({**flag, "mac": mandate_store.mac(KEY, "whatsapp-send-use", flag)}))
    append_raw(home, "not json")
    append_raw(home, "[1, 2]")
    append_raw(home, "")
    assert sm._used(home, "whatsapp", mandate_id, now) == 0
    assert sm._used(home, "whatsapp", other_id, now) == 1
    assert sm.use(home, "whatsapp", mandate_id, view(), now=now) is None
    assert sm._used(home, "whatsapp", mandate_id, now) == 1
    assert sm.use(home, "whatsapp", mandate_id, view(), now=now) is not None


def test_a_torn_last_line_is_skipped_and_the_valid_rows_still_count(keyfile, home):
    mandate_id = make(home, per_hour=1)
    now = time.time()
    assert sm.use(home, "whatsapp", mandate_id, view(), now=now) is None
    with open(home / "whatsapp-access" / "uses.jsonl", "a") as handle:
        handle.write('{"mandate": "' + mandate_id)
    assert sm.use(home, "whatsapp", mandate_id, view(), now=now) is not None


def test_a_replaced_key_forgets_the_old_rows_with_the_mandates(keyfile, home):
    mandate_id = make(home, per_hour=1)
    sm.use(home, "whatsapp", mandate_id, view())
    new_key = bytes(reversed(range(32)))
    assert sm._used(home, "whatsapp", mandate_id, time.time(), new_key) == sm.MAX_PER_HOUR
    keyfile.write_text(new_key.hex())
    assert sm.active(home, "whatsapp") == []


def test_use_refuses_a_mandate_that_is_gone(keyfile, home):
    make(home, per_hour=2)
    assert sm.use(home, "whatsapp", "m00000000", view()) == "mandate m00000000 is no longer in force"
    t = terms(per_hour=2)
    ended = sm.create(home, t)["id"]
    assert sm.use(home, "whatsapp", ended, view(), now=t["expires"]) == f"mandate {ended} is no longer in force"


def test_a_mandate_revoked_between_covering_and_use_is_refused(keyfile, home):
    mandate_id = make(home)
    assert sm.covering(home, "whatsapp", view()) == (mandate_id, [])
    sm.revoke(home, "whatsapp", mandate_id)
    assert sm.use(home, "whatsapp", mandate_id, view()) == f"mandate {mandate_id} is no longer in force"
    assert uses(home) == []


def test_use_checks_the_send_again_against_the_mandate(keyfile, home):
    mandate_id = make(home, max_chars=10)
    assert sm.covering(home, "whatsapp", view(text="short"))[0] == mandate_id
    assert "allows 10" in sm.use(home, "whatsapp", mandate_id, view(text="a longer text than the mandate allows"))
    assert "another account" in sm.use(home, "whatsapp", mandate_id, view(account="other"))


def test_use_refuses_when_the_key_cannot_be_read(keyfile, home):
    mandate_id = make(home)
    keyfile.write_text("garbled")
    assert sm.use(home, "whatsapp", mandate_id, view()) == sm.NO_KEY
    keyfile.unlink()
    assert sm.use(home, "whatsapp", mandate_id, view()) == sm.NO_KEY
    assert uses(home) == []


def test_use_refuses_when_the_row_cannot_be_written(keyfile, home, monkeypatch):
    mandate_id = make(home)

    def fail(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(sm, "_append", fail)
    assert sm.use(home, "whatsapp", mandate_id, view()) == "the send could not be counted: disk full"


def test_use_of_an_unknown_service_refuses(home):
    assert "service is one of" in sm.use(home, "discord", "m1a2b3c4d", view())
    assert "service is one of" in sm.use(home, "telegram", "m1a2b3c4d", view())


def test_threads_racing_the_last_slots_win_exactly_per_hour_times(keyfile, home):
    mandate_id = make(home, per_hour=3)
    now = time.time()
    gate = threading.Barrier(10)
    results = []

    def send():
        gate.wait()
        results.append(sm.use(home, "whatsapp", mandate_id, view(), now=now))

    threads = [threading.Thread(target=send) for _ in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(results) == 10 and results.count(None) == 3
    assert len(uses(home)) == 3
    assert all("allows 3 an hour" in r for r in results if r is not None)


# --- the ledger fails closed ----------------------------------------------------------------------

def opening(mandate_id, at, key=KEY, **over):
    row = {"mandate": mandate_id, "time": at, "open": True, **over}
    return {**row, "mac": mandate_store.mac(key, "whatsapp-send-use", row)}


def test_a_mandate_is_anchored_by_one_authenticated_opening_row(keyfile, home):
    before = int(time.time())
    mandate_id = make(home, per_hour=1)
    row, = rows(home)
    assert set(row) == {"mandate", "time", "open", "mac"} and row["open"] is True and row["mandate"] == mandate_id
    assert before <= row["time"] <= int(time.time()) and row == opening(mandate_id, row["time"])
    assert sm._used(home, "whatsapp", mandate_id, time.time()) == 0   # an opening row is not a use
    assert sm.use(home, "whatsapp", mandate_id, view()) is None
    assert sm.use(home, "whatsapp", mandate_id, view()) is not None   # per_hour 1: the opening row took no slot
    assert len(rows(home)) == 2 and len(uses(home)) == 1


def test_a_deleted_ledger_blocks_every_mandate_it_anchored(keyfile, home):
    old = make(home, per_hour=2)
    ledger(home).unlink()
    assert sm.covering(home, "whatsapp", view()) == (None, [f"{old}: {sm.LEDGER_USED_UP}"])
    assert sm.use(home, "whatsapp", old, view()) is not None
    assert not ledger(home).exists()
    new = make(home, per_hour=2)   # a new mandate is anchored afresh
    assert sm.use(home, "whatsapp", new, view()) is None
    assert sm.use(home, "whatsapp", old, view()) is not None


def test_an_emptied_ledger_blocks(keyfile, home):
    mandate_id = make(home)
    assert sm.use(home, "whatsapp", mandate_id, view()) is None
    ledger(home).write_text("")
    assert sm._used(home, "whatsapp", mandate_id, time.time()) == sm.MAX_PER_HOUR
    assert sm.use(home, "whatsapp", mandate_id, view()) is not None
    assert ledger(home).read_text() == ""


def test_a_ledger_that_cannot_be_vouched_for_says_so_instead_of_naming_a_count(keyfile, home):
    mandate_id = make(home, per_hour=3)
    assert sm.use(home, "whatsapp", mandate_id, view()) is None
    for damage, reason in ((lambda: ledger(home).write_text(""), sm.LEDGER_USED_UP),     # emptied
                           (lambda: ledger(home).unlink(), sm.LEDGER_USED_UP),           # gone
                           (lambda: keyfile.write_text("garbled"), sm.NO_KEY)):          # no key to vouch with
        damage()
        assert sm.use(home, "whatsapp", mandate_id, view()) == reason
    assert "cannot be read" in sm.LEDGER_USED_UP and "counts as used up" in sm.LEDGER_USED_UP
    assert "sends in the last hour" not in sm.LEDGER_USED_UP


def test_a_missing_opening_row_says_so(keyfile, home):
    mandate_id = make(home, per_hour=2)
    ledger(home).write_text("")
    assert sm.use(home, "whatsapp", mandate_id, view()) == sm.LEDGER_USED_UP
    assert sm.covering(home, "whatsapp", view()) == (None, [f"{mandate_id}: {sm.LEDGER_USED_UP}"])


def test_a_real_count_equal_to_the_absolute_ceiling_still_names_a_count(mandate):
    assert sm.USED_UP == sm.MAX_PER_HOUR
    assert sm.fits(mandate, view(), used=sm.USED_UP) == sm.LEDGER_USED_UP
    assert sm.fits(mandate, view(), used=sm.MAX_PER_HOUR) == (
        f"{sm.MAX_PER_HOUR} sends in the last hour; the mandate allows 2 an hour")


def test_a_whatsapp_hour_is_used_up_at_five(keyfile, home):
    mandate_id = make(home, "whatsapp", per_hour=5)
    now = time.time()
    seen = view(service="whatsapp")
    assert [sm.use(home, "whatsapp", mandate_id, seen, now=now + n) for n in range(5)] == [None] * 5
    assert sm.use(home, "whatsapp", mandate_id, seen, now=now + 6) == (
        "5 sends in the last hour; the mandate allows 5 an hour")
    rows = (home / "whatsapp-access" / "uses.jsonl").read_text().splitlines()
    assert len([row for row in rows if not json.loads(row).get("open")]) == 5


def test_a_ledger_replaced_by_a_link_to_a_device_blocks_and_nothing_is_written_through_it(keyfile, home):
    mandate_id = make(home)
    ledger(home).unlink()
    ledger(home).symlink_to("/dev/null")
    assert sm.use(home, "whatsapp", mandate_id, view()) is not None
    assert sm.covering(home, "whatsapp", view())[0] is None
    assert ledger(home).is_symlink() and os.stat("/dev/null").st_size == 0


def test_a_ledger_replaced_by_a_link_to_a_copy_blocks_even_when_the_copy_is_intact(keyfile, home, tmp_path):
    mandate_id = make(home)
    copy = tmp_path / "copy.jsonl"
    copy.write_text(ledger(home).read_text())
    ledger(home).unlink()
    ledger(home).symlink_to(copy)
    assert sm.use(home, "whatsapp", mandate_id, view()) is not None
    assert copy.read_text().count("\n") == 1 and ledger(home).is_symlink()


def test_a_dangling_link_in_place_of_the_ledger_is_not_followed_to_create_a_file(keyfile, home, tmp_path):
    mandate_id = make(home)
    ledger(home).unlink()
    ledger(home).symlink_to(tmp_path / "elsewhere.jsonl")
    assert sm.use(home, "whatsapp", mandate_id, view()) is not None
    assert not (tmp_path / "elsewhere.jsonl").exists()


def test_a_ledger_that_is_not_a_plain_file_of_this_user_blocks(keyfile, home, monkeypatch):
    mandate_id = make(home)
    original = ledger(home).read_text()
    real_getuid = os.getuid
    monkeypatch.setattr(os, "getuid", lambda: real_getuid() + 1)   # the file is now another user's
    assert sm._used(home, "whatsapp", mandate_id, time.time()) == sm.MAX_PER_HOUR
    assert sm.use(home, "whatsapp", mandate_id, view()) is not None
    monkeypatch.setattr(os, "getuid", real_getuid)
    assert ledger(home).read_text() == original
    ledger(home).unlink()
    ledger(home).mkdir()   # a directory
    assert sm._used(home, "whatsapp", mandate_id, time.time()) == sm.MAX_PER_HOUR
    assert sm.use(home, "whatsapp", mandate_id, view()) is not None
    ledger(home).rmdir()
    os.mkfifo(ledger(home))   # a pipe: never opened for reading to block on
    assert sm._used(home, "whatsapp", mandate_id, time.time()) == sm.MAX_PER_HOUR
    assert sm.use(home, "whatsapp", mandate_id, view()) is not None


def test_an_unreadable_ledger_blocks(keyfile, home):
    mandate_id = make(home)
    ledger(home).chmod(0)
    try:
        assert sm._used(home, "whatsapp", mandate_id, time.time()) == sm.MAX_PER_HOUR
        assert sm.use(home, "whatsapp", mandate_id, view()) is not None
    finally:
        ledger(home).chmod(0o600)


def test_a_forged_opening_row_does_not_anchor(keyfile, home):
    mandate_id = make(home, per_hour=2)
    now = int(time.time())
    other_id = make(home, per_hour=2)
    forgeries = [
        {"mandate": mandate_id, "time": now, "open": True, "mac": "0" * 64},
        opening(mandate_id, now, key=b"\x01" * 32),
        opening(other_id, now),                                    # another mandate's own
        opening(mandate_id, now, extra="x"),                       # a key too many
        {**opening(mandate_id, now), "open": False},               # a flag the MAC does not cover
        {**opening(mandate_id, now), "time": now + 1},             # a time the MAC does not cover
    ]
    bare = {"mandate": mandate_id, "time": now}                    # a use row is not an opening
    forgeries.append({**bare, "mac": mandate_store.mac(KEY, "whatsapp-send-use", bare)})
    forgeries.append({"mandate": mandate_id, "time": now, "open": 1, "mac": opening(mandate_id, now)["mac"]})
    ledger(home).write_text("".join(json.dumps(row) + "\n" for row in forgeries))
    assert sm._used(home, "whatsapp", mandate_id, now) == sm.MAX_PER_HOUR
    assert sm.use(home, "whatsapp", mandate_id, view()) is not None
    found, misses = sm.covering(home, "whatsapp", view())
    assert found == other_id and all(m.startswith(mandate_id) for m in misses)   # only its own row anchors
    assert len(ledger(home).read_text().splitlines()) == len(forgeries)


def test_an_opening_row_of_another_kind_does_not_anchor(keyfile, home):
    mandate_id = make(home)
    row = {"mandate": mandate_id, "time": int(time.time()), "open": True}
    ledger(home).write_text(json.dumps({**row, "mac": mandate_store.mac(KEY, "whatsapp-send-mandate", row)}) + "\n")
    assert sm._used(home, "whatsapp", mandate_id, time.time()) == sm.MAX_PER_HOUR


def test_documented_limit_removing_use_rows_from_an_intact_ledger_is_not_detected(keyfile, home):
    """A ledger that keeps its opening row but loses its use rows reads as unused: the file guard and the
    30-day ceiling bound that edit, not the MACs (docs/decisions/send-mandates.md)."""
    mandate_id = make(home, per_hour=1)
    assert sm.use(home, "whatsapp", mandate_id, view()) is None
    assert sm.use(home, "whatsapp", mandate_id, view()) is not None
    first = ledger(home).read_text().splitlines()[0]
    ledger(home).write_text(first + "\n")
    assert sm.use(home, "whatsapp", mandate_id, view()) is None


def test_a_mandate_that_cannot_be_anchored_is_revoked_and_nothing_is_made(keyfile, home, tmp_path):
    ledger(home).parent.mkdir(parents=True)
    ledger(home).symlink_to(tmp_path / "elsewhere.jsonl")
    with pytest.raises(sm.MandateError, match="could not be recorded in its ledger.*nothing was made, it was revoked"):
        sm.create(home, terms())
    assert sm.active(home, "whatsapp") == [] and not (tmp_path / "elsewhere.jsonl").exists()


def test_a_mandate_whose_anchor_and_revoke_both_fail_says_which_to_revoke(keyfile, home, monkeypatch):
    def fail(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(sm, "_append", fail)
    monkeypatch.setattr(mandate_store, "revoke", fail)
    said = r"disk full\); nothing was made, it could not be revoked \(disk full\); revoke m"
    with pytest.raises(sm.MandateError, match=said):
        sm.create(home, terms())
    # Not anchored, so it is used up whatever the head says.
    mandate_id, = [m["id"] for m in sm.active(home, "whatsapp")]
    assert sm.use(home, "whatsapp", mandate_id, view()) is not None

