"""Send mandates in whatsapp-access: making, listing and revoking one through the hook and the handler, and
the sends it covers (no card, also where nobody can answer one), over a fake wacli and a fake Keychain.
Never the real wacli, profile home or Keychain."""

import importlib.util
import json
from pathlib import Path
import shutil
import time

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("whatsapp_access_plugin_mandate_test", ROOT / "__init__.py")
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)
wa = plugin.wa
sm = plugin.send_mandate

ALICE = "819011111111@s.whatsapp.net"
BOB = "819022222222@s.whatsapp.net"
FAMILY = "120363001234567890@g.us"
HIDDEN = "123456789012345@lid"
NEWSLETTER = "120363999999999999@newsletter"
BROADCAST = "status@broadcast"
CALL = "call-1"
MAKE = {"action": "create", "account": "work", "chats": [ALICE], "per_hour": 2, "max_chars": 50, "days": 7,
        "purpose": "The morning report"}
SEND = {"action": "send", "account": "work", "chat": ALICE, "text": "good morning"}


def fake_secret(folder: Path) -> Path:
    """A fake Keychain CLI over one key file in ``folder`` (``get`` prints it, ``show`` says it exists,
    ``set --stdin`` stores it): a send mandate's MAC key, never the real Keychain."""
    keyfile = folder / "keyfile"
    cli = folder / "secret"
    cli.write_text(
        "#!/bin/sh\n"
        f"[ \"$1\" = get ] && [ -f {keyfile} ] && cat {keyfile} && exit 0\n"
        f"[ \"$1\" = show ] && [ -f {keyfile} ] && exit 0\n"
        f"[ \"$1\" = set ] && [ ! -f {keyfile} ] && cat > {keyfile} && exit 0\n"
        "exit 1\n")
    cli.chmod(0o755)
    return cli


class Wacli:
    """Stands in for wa.run: two accounts, three named chats, every call recorded."""

    def __init__(self):
        self.calls = []
        self.accounts = ["work", "play"]
        self.names = {ALICE: "Alice", BOB: "Bob", FAMILY: "Family"}
        self.unknown = set()    # chats the mirror has never seen
        self.send_text = lambda args: {"sent": True, "to": args[args.index("--to") + 1], "id": "3EB0XYZ"}

    def __call__(self, args, *, account=None, write=False, timeout=None, media_roots=None):
        self.calls.append({"args": list(args), "account": account, "write": write})
        key = " ".join(args[:2])
        if key == "accounts list":
            return {"accounts": [{"name": n} for n in self.accounts]}
        if key == "chats show":
            jid = args[args.index("--jid") + 1]
            if jid in self.unknown:
                raise wa.WhatsAppError("not found in local store", reported=True)
            return {"jid": jid, "name": self.names.get(jid)}
        if key == "messages show":
            return {}
        if key == "send text":
            return self.send_text(args)
        raise AssertionError(f"unexpected wacli call {args}")

    def sent(self):
        return [c for c in self.calls if c["args"][:2] == ["send", "text"]]

    def writes(self):
        return [c for c in self.calls if c["write"]]


@pytest.fixture()
def wacli():
    return Wacli()


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path, wacli):
    base = tmp_path / "home"
    base.mkdir()
    keychain = tmp_path / "keychain"
    keychain.mkdir()
    monkeypatch.setattr(wa, "run", wacli)  # never the real wacli or ~/.wacli
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: False)
    monkeypatch.setattr(plugin, "_home", lambda: base)
    monkeypatch.setattr(plugin, "_call_id", lambda: CALL)
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: None)  # a person is present
    monkeypatch.setattr(sm.mandate_store, "SECRET", fake_secret(keychain))  # never the Keychain
    monkeypatch.setattr(wa, "SEND_ROOT", tmp_path / "Workspaces")
    monkeypatch.setenv(wa.STATE_ENV, str(tmp_path / "state"))
    wa._approved.clear()
    wa._PENDING.clear()
    plugin._DECISIONS.clear()
    return base


def uses(base):
    """How many counted sends the ledger holds (the opening rows of the mandates are not sends)."""
    path = base / "whatsapp-access" / "uses.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    return len([row for row in rows if not row.get("open")])


def hook(tool, args, call_id=CALL):
    return plugin.gate(tool_name=tool, args=dict(args), tool_call_id=call_id, session_id="s")


def make(**over):
    args = {**MAKE, **over}
    assert hook("whatsapp_mandate", args)["action"] == "approve"
    result = json.loads(plugin.whatsapp_mandate(dict(args)))
    assert result["ok"] is True, result
    return result["mandate"]["id"]


def run_send(args=SEND):
    """The hook, then (when it lets the call through or after a card) the handler."""
    directive = hook("whatsapp", args)
    return directive, json.loads(plugin.whatsapp(dict(args)))


def block_text(directive):
    assert directive["action"] == "block"
    return directive["message"]


# --- making, listing and revoking ---------------------------------------------------------------

def test_a_mandate_is_made_on_its_own_card(isolated):
    directive = hook("whatsapp_mandate", MAKE)
    assert directive["action"] == "approve" and directive["rule_key"].startswith("whatsapp-access:mandate:")
    lines = directive["message"].splitlines()
    assert lines[0] == "WhatsApp · Send mandate"
    assert lines[1] == "🚨 Plain text sends to these chats skip the card"
    assert "Chat: Alice (user, +819011111111)" in lines and "Account: work" in lines
    assert "Up to: 2 an hour, 50 characters each" in lines and "Purpose: The morning report" in lines
    assert any(line.startswith("Until: ") and line.endswith("(7 days)") for line in lines)
    assert sm.active(isolated, "whatsapp") == []  # the card alone makes nothing
    made = json.loads(plugin.whatsapp_mandate(dict(MAKE)))
    assert made["ok"] is True and made["mandate"]["chats"] == ["Alice (+819011111111)"]
    assert made["mandate"]["per_hour"] == 2 and made["mandate"]["service"] == "whatsapp"
    body, = sm.active(isolated, "whatsapp")
    assert body["account"] == "work" and body["account_label"] == "work"
    assert body["chats"] == [{"id": ALICE, "name": "Alice", "kind": "user", "identity": "+819011111111"}]
    assert body["expires"] > time.time() + 6 * 86400
    assert (isolated / "whatsapp-access" / "head.json").is_file()


def test_every_mandate_card_has_a_fresh_key_and_asks_even_with_a_mandate_in_force():
    keys = {hook("whatsapp_mandate", MAKE)["rule_key"] for _ in range(3)}
    assert len(keys) == 3
    make()
    again = hook("whatsapp_mandate", MAKE)
    assert again["action"] == "approve" and again["rule_key"] not in keys


def test_a_mandate_needs_its_own_card_and_its_record_is_used_once(isolated):
    refused = json.loads(plugin.whatsapp_mandate(dict(MAKE)))
    assert refused["ok"] is False and "only on its own card" in refused["error"]
    hook("whatsapp_mandate", MAKE)
    assert json.loads(plugin.whatsapp_mandate(dict(MAKE)))["ok"] is True
    assert "only on its own card" in json.loads(plugin.whatsapp_mandate(dict(MAKE)))["error"]
    assert len(sm.active(isolated, "whatsapp")) == 1


def test_the_card_belongs_to_its_tool_call(monkeypatch, isolated):
    hook("whatsapp_mandate", MAKE, "call-a")
    monkeypatch.setattr(plugin, "_call_id", lambda: "call-b")
    assert "only on its own card" in json.loads(plugin.whatsapp_mandate(dict(MAKE)))["error"]
    assert sm.active(isolated, "whatsapp") == []
    monkeypatch.setattr(plugin, "_call_id", lambda: "call-a")
    assert json.loads(plugin.whatsapp_mandate(dict(MAKE)))["ok"] is True


@pytest.mark.parametrize("reason", ["yolo mode is on", "this is a cron job", "nobody is present to answer"])
def test_a_mandate_is_not_made_where_nobody_answers_its_card(monkeypatch, isolated, reason):
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: reason)
    assert reason in block_text(hook("whatsapp_mandate", MAKE))
    assert reason in json.loads(plugin.whatsapp_mandate(dict(MAKE)))["error"]
    assert not plugin._DECISIONS and sm.active(isolated, "whatsapp") == []


def test_a_card_decided_with_a_person_is_not_enough_where_the_handler_finds_none(monkeypatch, isolated):
    hook("whatsapp_mandate", MAKE)
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: "nobody is present to answer")
    assert "nobody is present" in json.loads(plugin.whatsapp_mandate(dict(MAKE)))["error"]
    assert sm.active(isolated, "whatsapp") == []


def test_inbound_a2a_makes_lists_and_revokes_nothing(monkeypatch, isolated):
    mandate_id = make()
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    for args in (MAKE, {"action": "list"}, {"action": "revoke", "mandate": mandate_id}):
        assert "A2A" in block_text(hook("whatsapp_mandate", args))
        result = json.loads(plugin.whatsapp_mandate(dict(args)))
        assert result["ok"] is False and "A2A" in result["error"]
    assert [m["id"] for m in sm.active(isolated, "whatsapp")] == [mandate_id]


def test_changed_chat_resolution_between_card_and_handler_makes_nothing(isolated, wacli):
    hook("whatsapp_mandate", MAKE)
    wacli.names[ALICE] = "Alicia"
    result = json.loads(plugin.whatsapp_mandate(dict(MAKE)))
    assert result["ok"] is False and "changed since the card" in result["error"]
    assert sm.active(isolated, "whatsapp") == []


def test_the_handler_makes_the_terms_the_card_showed(isolated):
    hook("whatsapp_mandate", MAKE)
    changed = {**MAKE, "per_hour": 5, "max_chars": 1000, "days": 30, "purpose": "Something else"}
    # The model cannot widen what the card showed: the same call id with other arguments has no card.
    assert "only on its own card" in json.loads(plugin.whatsapp_mandate(changed))["error"]
    assert json.loads(plugin.whatsapp_mandate(dict(MAKE)))["mandate"]["per_hour"] == 2


def test_the_hourly_ceiling_is_five_and_refused_above_it():
    assert make(per_hour=5)
    message = block_text(hook("whatsapp_mandate", {**MAKE, "per_hour": 6}))
    assert "WhatsApp allows at most 5 sends an hour" in message
    assert "at most 5" in block_text(hook("whatsapp_mandate", {**MAKE, "per_hour": 30}))
    assert not plugin._DECISIONS


def test_the_hourly_ceiling_is_the_accounts_total_across_its_mandates(isolated):
    first = make(per_hour=3)
    message = block_text(hook("whatsapp_mandate", {**MAKE, "chats": [BOB], "per_hour": 3}))
    assert ("WhatsApp allows at most 5 sends an hour per account; mandates in force for work already take 3"
            in message)
    assert not plugin._DECISIONS and [m["id"] for m in sm.active(isolated, "whatsapp")] == [first]
    second = make(chats=[BOB], per_hour=2)                  # 3 + 2 fits exactly
    assert "already take 5" in block_text(hook("whatsapp_mandate", {**MAKE, "per_hour": 1}))
    sm.revoke(isolated, "whatsapp", first)                  # its share is free again
    third = make(per_hour=3)
    assert {m["id"] for m in sm.active(isolated, "whatsapp")} == {second, third}
    # Another account has a ceiling of its own.
    assert hook("whatsapp_mandate", {**MAKE, "account": "play", "per_hour": 5})["action"] == "approve"


def test_a_mandate_that_passed_the_look_before_the_card_is_still_refused_by_create(monkeypatch, isolated):
    """Two cards drawn while nothing was in force: the second to be answered breaks the ceiling at create."""
    assert hook("whatsapp_mandate", {**MAKE, "per_hour": 3}, "call-a")["action"] == "approve"
    assert hook("whatsapp_mandate", {**MAKE, "chats": [BOB], "per_hour": 3}, "call-b")["action"] == "approve"
    monkeypatch.setattr(plugin, "_call_id", lambda: "call-a")
    first = json.loads(plugin.whatsapp_mandate({**MAKE, "per_hour": 3}))
    assert first["ok"] is True
    monkeypatch.setattr(plugin, "_call_id", lambda: "call-b")
    second = json.loads(plugin.whatsapp_mandate({**MAKE, "chats": [BOB], "per_hour": 3}))
    assert second["ok"] is False and second["error"].endswith("already take 3; nothing was made")
    assert [m["id"] for m in sm.active(isolated, "whatsapp")] == [first["mandate"]["id"]]
    assert hook("whatsapp", {**SEND, "chat": BOB}, "call-c")["action"] == "approve"   # and BOB is not covered


@pytest.mark.parametrize("chats", [
    [f"81900000000{n}@s.whatsapp.net" for n in range(6)],        # too many
    [],                                                           # none
    [ALICE, f"  {ALICE}\n"],                                      # one twice, after trimming
    [ALICE, BOB, HIDDEN],                                         # a good start, then a refused kind
    [ALICE, "Alice"],                                             # a good start, then a name
])
def test_a_list_of_chats_that_cannot_hold_asks_wacli_nothing(wacli, chats):
    assert hook("whatsapp_mandate", {**MAKE, "chats": chats})["action"] == "block"
    assert wacli.calls == []


@pytest.mark.parametrize("over,match", [
    ({"chats": [HIDDEN]}, "hidden"),
    ({"chats": [NEWSLETTER]}, "newsletter"),
    ({"chats": [BROADCAST]}, "broadcast list"),
    ({"chats": [ALICE, HIDDEN]}, "@lid"),
    ({"chats": ["Alice"]}, "not a name or phone number"),
    ({"chats": ["+819011111111"]}, "not a name or phone number"),
    ({"chats": ["123@g.us"]}, "not a name or phone number"),
    ({"chats": []}, "chats is a list"),
    ({"chats": [5]}, "chats is a list"),
    ({"chats": ALICE}, "chats is a list"),
    ({"chats": [ALICE, ALICE]}, "named once"),
    ({"chats": [f"81900000000{n}@s.whatsapp.net" for n in range(6)]}, "one to 5 chats"),
    ({"per_hour": 0}, "per_hour"), ({"per_hour": 6}, "per_hour"), ({"max_chars": 1001}, "max_chars"),
    ({"days": 31}, "days"), ({"days": "7"}, "days"), ({"purpose": " "}, "purpose"),
    ({"account": "nope"}, "no WhatsApp account named"),
    ({"account": None}, "several WhatsApp accounts"),
])
def test_unacceptable_terms_get_no_card(over, match):
    message = block_text(hook("whatsapp_mandate", {**MAKE, **over}))
    assert match in message and not plugin._DECISIONS


def test_a_hidden_number_contact_is_refused_in_words():
    message = block_text(hook("whatsapp_mandate", {**MAKE, "chats": [HIDDEN]}))
    assert f"{HIDDEN} is a contact whose number is hidden" in message and "who it is" in message


def test_five_chats_a_person_and_a_group_show_their_number_and_group_id(isolated):
    others = [f"81900000000{n}@s.whatsapp.net" for n in range(3)]
    directive = hook("whatsapp_mandate", {**MAKE, "chats": [ALICE, FAMILY, *others]})
    assert directive["action"] == "approve"
    lines = directive["message"].splitlines()
    assert "Chat: Alice (user, +819011111111)" in lines
    assert f"Chat: Family (group, {FAMILY})" in lines
    assert "Chat: 819000000000@s.whatsapp.net (user, +819000000000)" in lines


def test_chats_with_one_name_show_their_own_handles(wacli):
    wacli.names[ALICE] = wacli.names[FAMILY] = "Mom"
    lines = hook("whatsapp_mandate", {**MAKE, "chats": [ALICE, FAMILY]})["message"].splitlines()
    assert "Chat: Mom (user, +819011111111)" in lines and f"Chat: Mom (group, {FAMILY})" in lines


def test_a_chat_unknown_to_the_mirror_is_shown_by_its_number(wacli):
    wacli.unknown.add(BOB)
    lines = hook("whatsapp_mandate", {**MAKE, "chats": [BOB]})["message"].splitlines()
    assert f"Chat: {BOB} (user, +819022222222)" in lines


def test_the_account_is_the_one_named_or_the_only_one(wacli):
    wacli.accounts = ["work"]
    no_account = {k: v for k, v in MAKE.items() if k != "account"}
    assert "Account: work" in hook("whatsapp_mandate", no_account)["message"].splitlines()
    wacli.accounts = ["work", "play"]
    assert "Account: play" in hook("whatsapp_mandate", {**MAKE, "account": "play"})["message"].splitlines()
    assert "several WhatsApp accounts" in block_text(hook("whatsapp_mandate", no_account))


def test_a_mandate_is_listed_and_revoked_without_a_card(isolated):
    assert hook("whatsapp_mandate", {"action": "list"}) is None
    assert json.loads(plugin.whatsapp_mandate({"action": "list"})) == {"ok": True, "mandates": []}
    mandate_id = make()
    listed = json.loads(plugin.whatsapp_mandate({"action": "list"}))["mandates"]
    assert [m["id"] for m in listed] == [mandate_id] and listed[0]["chats"] == ["Alice (+819011111111)"]
    revoke = {"action": "revoke", "mandate": mandate_id}
    assert hook("whatsapp_mandate", revoke) is None
    assert json.loads(plugin.whatsapp_mandate(dict(revoke))) == {"ok": True, "revoked": mandate_id}
    assert json.loads(plugin.whatsapp_mandate({"action": "list"}))["mandates"] == []
    assert json.loads(plugin.whatsapp_mandate(dict(revoke)))["note"] == "it was not in force"
    assert json.loads(plugin.whatsapp_mandate({"action": "revoke", "mandate": "nope"}))["ok"] is False
    assert json.loads(plugin.whatsapp_mandate({"action": "wipe"}))["ok"] is False
    assert json.loads(plugin.whatsapp_mandate("not a dict"))["ok"] is False


def test_without_a_profile_home_nothing_is_made_or_covered(monkeypatch):
    monkeypatch.setattr(plugin, "_home", lambda: None)
    assert hook("whatsapp_mandate", MAKE)["action"] == "block"
    assert json.loads(plugin.whatsapp_mandate(dict(MAKE)))["ok"] is False
    assert json.loads(plugin.whatsapp_mandate({"action": "list"})) == {"ok": True, "mandates": []}
    assert json.loads(plugin.whatsapp_mandate({"action": "revoke", "mandate": "m1a2b3c4d"}))["ok"] is False
    assert hook("whatsapp", SEND)["action"] == "approve"


# --- sends inside a mandate ----------------------------------------------------------------------

def test_a_fitting_text_send_runs_with_no_card_and_is_counted(isolated, wacli):
    make()
    directive, result = run_send()
    assert directive is None
    assert result["ok"] is True and result["id"] == "3EB0XYZ"
    assert [c["args"] for c in wacli.sent()] == [["send", "text", "--to", ALICE, "--message", "good morning"]]
    assert wacli.sent()[0]["account"] == "work" and wacli.sent()[0]["write"] is True
    assert uses(isolated) == 1 and not wa._approved


@pytest.mark.parametrize("reason", ["yolo mode is on", "this is a cron job", "nobody is present to answer",
                                    "approvals are off (approvals.mode: off)"])
def test_a_fitting_send_also_runs_where_nobody_can_answer_a_card(monkeypatch, isolated, wacli, reason):
    make()
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: reason)
    directive, result = run_send()
    assert directive is None and result["ok"] is True
    assert len(wacli.sent()) == 1 and uses(isolated) == 1


def test_a_send_to_a_group_can_be_covered(isolated, wacli):
    make(chats=[FAMILY, ALICE])
    directive, result = run_send({**SEND, "chat": FAMILY})
    assert directive is None and result["ok"] is True, result
    assert wacli.sent()[0]["args"][3] == FAMILY and uses(isolated) == 1


def test_the_hourly_bound_turns_the_next_send_into_an_ordinary_card(isolated, wacli):
    make(per_hour=2)
    for _ in range(2):
        assert run_send()[0] is None
    directive = hook("whatsapp", SEND)
    assert directive["action"] == "approve" and directive["rule_key"].startswith("whatsapp-access:send:")
    assert "Chat: Alice (+819011111111)" in directive["message"]
    assert len(wacli.sent()) == 2 and uses(isolated) == 2


def test_the_sixth_send_in_an_hour_asks_and_in_cron_is_refused(monkeypatch, isolated, wacli):
    make(per_hour=5)
    for n in range(5):
        directive, result = run_send({**SEND, "text": f"report {n}"})
        assert directive is None and result["ok"] is True
    sixth = {**SEND, "text": "report 5"}
    directive = hook("whatsapp", sixth)
    assert directive["action"] == "approve" and directive["rule_key"].startswith("whatsapp-access:send:")
    wa._approved.clear()    # the card was never answered
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: "this is a cron job")
    directive, result = run_send(sixth)
    assert "cron job" in block_text(directive)
    assert result["ok"] is False and "cron job" in result["error"] and "Nothing was sent" in result["error"]
    assert len(wacli.sent()) == 5 and uses(isolated) == 5 and not wa._approved


def test_in_cron_the_hourly_bound_is_a_refusal(monkeypatch, isolated, wacli):
    make(per_hour=1)
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: "this is a cron job")
    assert run_send()[0] is None
    directive, result = run_send()
    assert "cron job" in block_text(directive)
    assert result["ok"] is False and "cron job" in result["error"]
    assert len(wacli.sent()) == 1 and uses(isolated) == 1 and not wa._approved


def write_file(tmp_path):
    workspace = tmp_path / "Workspaces"
    workspace.mkdir(exist_ok=True)
    (workspace / "note.txt").write_text("hello")


MISSES = {
    "another chat": lambda: {**SEND, "chat": BOB},
    "a group the mandate does not name": lambda: {**SEND, "chat": FAMILY},
    "a reply": lambda: {**SEND, "reply_to": "3EB0ABCDEF"},
    "over max_chars": lambda: {**SEND, "text": "x" * 51},
    "another account": lambda: {**SEND, "account": "play"},
    "a file": lambda: {**SEND, "files": ["note.txt"]},
}


@pytest.mark.parametrize("miss", sorted(MISSES))
def test_a_send_that_does_not_fit_behaves_as_before(monkeypatch, tmp_path, isolated, wacli, miss):
    make()
    write_file(tmp_path)
    args = MISSES[miss]()
    directive = hook("whatsapp", args)
    assert directive["action"] == "approve" and directive["rule_key"].startswith("whatsapp-access:send:")
    assert uses(isolated) == 0
    wa._approved.clear()
    wa._PENDING.clear()
    shutil.rmtree(tmp_path / "state", ignore_errors=True)   # the copies the card froze
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: "this is a cron job")  # and in cron it is refused
    directive, result = run_send(args)
    assert "cron job" in block_text(directive) and result["ok"] is False and "Nothing was sent" in result["error"]
    assert wacli.writes() == [] and uses(isolated) == 0 and wa._PENDING == {}
    assert not (tmp_path / "state" / "outbox").exists() or list((tmp_path / "state" / "outbox").iterdir()) == []


def test_after_a_revoke_a_send_asks_again(isolated):
    mandate_id = make()
    assert hook("whatsapp", SEND) is None
    wa._approved.clear()
    sm.revoke(isolated, "whatsapp", mandate_id)
    assert hook("whatsapp", SEND)["action"] == "approve"


def test_after_the_mandate_ended_a_send_asks_again(monkeypatch, isolated):
    make(days=1)
    assert hook("whatsapp", SEND) is None
    wa._approved.clear()
    real = time.time
    monkeypatch.setattr(time, "time", lambda: real() + 2 * 86400)
    assert hook("whatsapp", SEND)["action"] == "approve"


def test_a_mandate_revoked_between_the_hook_and_the_write_sends_nothing(isolated, wacli):
    mandate_id = make()
    assert hook("whatsapp", SEND) is None
    sm.revoke(isolated, "whatsapp", mandate_id)
    result = json.loads(plugin.whatsapp(dict(SEND)))
    assert result["ok"] is False
    assert result["error"].startswith("not sent: it no longer fits the send mandate (mandate ")
    assert "no longer in force" in result["error"] and "it will ask on a card" in result["error"]
    assert wacli.writes() == [] and uses(isolated) == 0


def test_the_last_slot_of_an_hour_goes_to_one_of_two_hooked_sends(monkeypatch, isolated, wacli):
    make(per_hour=1)
    assert hook("whatsapp", SEND, "call-a") is None
    assert hook("whatsapp", SEND, "call-b") is None  # both fitted when the hook looked
    results = []
    for call in ("call-a", "call-b"):
        monkeypatch.setattr(plugin, "_call_id", lambda call=call: call)
        results.append(json.loads(plugin.whatsapp(dict(SEND))))
    assert [r["ok"] for r in results] == [True, False]
    assert "allows 1 an hour" in results[1]["error"] and len(wacli.sent()) == 1 and uses(isolated) == 1


def test_text_changed_between_the_hook_and_the_write_is_still_refused(isolated, wacli):
    make()
    assert hook("whatsapp", SEND) is None
    result = json.loads(plugin.whatsapp({**SEND, "text": "not what was decided"}))
    assert "changed after the approval card" in result["error"] and wacli.writes() == [] and uses(isolated) == 0


def test_the_count_stands_when_the_send_fails_or_is_uncertain(isolated, wacli):
    make(per_hour=3)

    def refuse(args):
        raise wa.WhatsAppError("store is locked by another wacli process", reported=True)
    wacli.send_text = refuse
    assert run_send()[1]["error"].startswith("not sent: store is locked")
    assert uses(isolated) == 1

    def unsure(args):
        raise TimeoutError("wacli did not answer within 60s")
    wacli.send_text = unsure
    assert run_send({**SEND, "text": "again"})[1]["error"].startswith("UNCERTAIN")
    assert uses(isolated) == 2


def test_without_a_readable_key_nothing_is_covered_or_counted(isolated, wacli):
    make()
    (Path(sm.mandate_store.SECRET).parent / "keyfile").unlink()
    assert hook("whatsapp", SEND)["action"] == "approve"
    assert wacli.writes() == [] and uses(isolated) == 0


def test_a_deleted_ledger_turns_the_send_into_a_card_and_says_why(isolated, wacli):
    make()
    assert hook("whatsapp", SEND) is None
    (isolated / "whatsapp-access" / "uses.jsonl").unlink()
    result = json.loads(plugin.whatsapp(dict(SEND)))
    assert result["ok"] is False and "no longer fits the send mandate" in result["error"]
    assert sm.LEDGER_USED_UP in result["error"] and "30 sends" not in result["error"]
    wa._approved.clear()
    assert hook("whatsapp", SEND)["action"] == "approve"
    assert wacli.writes() == [] and uses(isolated) == 0


def test_a_recorded_mandate_never_takes_the_files_path(tmp_path, isolated, wacli):
    """Even a record carrying a mandate id (the hook never makes one for a file) is refused at the write."""
    mandate_id = make()
    write_file(tmp_path)
    args = {**SEND, "files": ["note.txt"]}
    plan = wa.send_plan(args)
    wa._remember(args, CALL, wa.request_digest(plan, wa._requested(args)), mandate_id)
    result = json.loads(plugin.whatsapp(dict(args)))
    assert result["ok"] is False and "a file always asks on a card" in result["error"]
    assert wacli.writes() == [] and uses(isolated) == 0 and wa._PENDING == {}


def test_a_recorded_mandate_never_takes_a_reply(isolated, wacli):
    mandate_id = make()
    args = {**SEND, "reply_to": "3EB0ABCDEF"}
    plan = wa.send_plan(args)
    wa._remember(args, CALL, wa.request_digest(plan, wa._requested(args)), mandate_id)
    result = json.loads(plugin.whatsapp(dict(args)))
    assert result["ok"] is False and "a quote or a reply always asks on a card" in result["error"]
    assert wacli.writes() == [] and uses(isolated) == 0


def test_a_covered_call_without_a_record_is_refused_as_before(monkeypatch, isolated, wacli):
    make()
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: "this is a cron job")
    result = json.loads(plugin.whatsapp(dict(SEND)))  # the hook never decided this call
    assert result["ok"] is False and "Nothing was sent" in result["error"]
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: None)
    result = json.loads(plugin.whatsapp(dict(SEND)))
    assert "did not pass its approval card" in result["error"] and wacli.writes() == []


def test_the_record_of_a_covered_send_belongs_to_its_call(monkeypatch, isolated, wacli):
    make()
    assert hook("whatsapp", SEND, "call-a") is None
    monkeypatch.setattr(plugin, "_call_id", lambda: "call-b")
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: "this is a cron job")
    assert json.loads(plugin.whatsapp(dict(SEND)))["ok"] is False
    assert wacli.writes() == []
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: None)
    assert "did not pass its approval card" in json.loads(plugin.whatsapp(dict(SEND)))["error"]


def test_a_card_record_does_not_skip_the_missing_person_check(monkeypatch, isolated, wacli):
    """A send that asked on a card (no mandate) is still refused where the handler finds nobody."""
    assert hook("whatsapp", SEND)["action"] == "approve"
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: "this is a cron job")
    result = json.loads(plugin.whatsapp(dict(SEND)))
    assert result["ok"] is False and "cron job" in result["error"] and wacli.writes() == []


def test_reads_are_unaffected_by_a_mandate(monkeypatch, isolated):
    make()
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: "this is a cron job")
    assert hook("whatsapp", {"action": "contacts", "query": "ali"}) is None
    assert uses(isolated) == 0


def test_the_engine_peeks_without_using_up_the_record(isolated):
    make()
    request = wa.approval_request(dict(SEND), home=isolated, call_id=CALL)
    assert isinstance(request, wa.Covered) and sm.mandate_store.valid_id(sm.store("whatsapp"), request.mandate)
    assert wa.covered(dict(SEND), CALL) == request.mandate and wa.covered(dict(SEND), CALL) == request.mandate
    assert wa.covered(dict(SEND), "other") is None
    # The call id alone names the record; the digest at the write is what binds the content.
    assert wa.covered({**SEND, "text": "x"}, CALL) == request.mandate
    digest = wa.request_digest(wa.send_plan(SEND), [])
    assert wa._approved_record({**SEND, "text": "x"}, CALL) == (digest, request.mandate)
    assert wa.covered(dict(SEND), CALL) is None


def test_a_send_outside_every_mandate_raises_when_no_card_can_be_asked(tmp_path, isolated):
    with pytest.raises(wa.WhatsAppError, match="no card can be answered"):
        wa.approval_request(dict(SEND), home=isolated, call_id=CALL, ask=False)
    assert not wa._approved
    write_file(tmp_path)
    with pytest.raises(wa.WhatsAppError, match="no card can be answered"):
        wa.approval_request({**SEND, "files": ["note.txt"]}, ids={"tool_call_id": CALL}, home=isolated,
                            call_id=CALL, ask=False)
    assert not wa._approved and wa._PENDING == {}
    assert wa.approval_request({"action": "chats"}, home=isolated, ask=False) is None
    make()
    assert isinstance(wa.approval_request(dict(SEND), home=isolated, call_id=CALL, ask=False), wa.Covered)
    assert wa.covered(dict(SEND), CALL)


def test_a_card_record_carries_no_mandate(isolated):
    assert wa.approval_request(dict(SEND), home=isolated, call_id=CALL)[1].startswith("whatsapp-access:send:")
    assert wa.covered(dict(SEND), CALL) is None and len(wa._approved) == 1


def test_a_send_without_a_home_is_never_counted_or_covered(monkeypatch, isolated, wacli):
    make()
    assert hook("whatsapp", SEND) is None
    monkeypatch.setattr(plugin, "_home", lambda: None)
    result = json.loads(plugin.whatsapp(dict(SEND)))
    assert result["ok"] is False and "profile home is unknown" in result["error"] and wacli.writes() == []


# --- ways around the tool ------------------------------------------------------------------------

STATE = "~/.hermes/profiles/assistant/whatsapp-access"


@pytest.mark.parametrize("tool,args", [
    ("read_file", {"path": f"{STATE}/head.json"}),
    ("read_file", {"path": f"{STATE}/mandates/m1a2b3c4d.json"}),
    ("search_files", {"path": f"{STATE}/mandates", "pattern": "x"}),
    ("write_file", {"path": f"{STATE}/uses.jsonl", "content": ""}),
    ("patch", {"path": f"{STATE}/mandates.jsonl"}),
    ("read_file", {"path": "/Users/x/.hermes/profiles/assistant/WhatsApp-Access/HEAD.json"}),
    ("read_file", {"path": "/x/whatsapp-access/downloads/../mandates/m.json"}),
    ("terminal", {"command": f"cat {STATE}/uses.jsonl"}),
    ("terminal", {"command": "ls", "workdir": f"{STATE}/mandates"}),
    ("terminal", {"command": "secret get WHATSAPP_MANDATE_KEY_ASSISTANT"}),
    ("terminal", {"command": "secret rm whatsapp_mandate_key_assistant"}),
    ("terminal", {"command": "security find-generic-password -s WHATSAPP_MANDATE_KEY_ASSISTANT"}),
    ("read_file", {"path": "WHATSAPP_MANDATE_KEY_ASSISTANT"}),
])
def test_the_mandate_state_and_key_are_off_limits_to_file_and_terminal_calls(tool, args):
    assert wa.bypass(tool, args) == wa.BYPASS_MESSAGE
    assert plugin.gate(tool_name=tool, args=args) == {"action": "block", "message": wa.BYPASS_MESSAGE}


def test_a_link_into_the_state_does_not_hide_it(tmp_path):
    real = tmp_path / "profile" / "whatsapp-access"
    real.mkdir(parents=True)
    (tmp_path / "innocent").symlink_to(real)
    assert wa.bypass("read_file", {"path": str(tmp_path / "innocent" / "head.json")}) == wa.BYPASS_MESSAGE
    assert wa.bypass("terminal", {"command": "ls", "workdir": str(tmp_path / "innocent" / "mandates")}) == (
        wa.BYPASS_MESSAGE)


@pytest.mark.parametrize("tool,args", [
    ("read_file", {"path": "hermes/plugins/messaging/whatsapp-access/wa.py"}),
    ("read_file", {"path": "hermes/docs/whatsapp-access.md"}),
    ("read_file", {"path": f"{STATE}-notes/head.json"}),
    ("read_file", {"path": "/x/mywhatsapp-access/mandates/m.json"}),
    ("read_file", {"path": "~/.hermes/profiles/assistant/whatsapp-downloads/a.png"}),
    ("web_search", {"query": "whatsapp-access/mandates"}),
])
def test_the_plugins_source_and_unrelated_names_stay_readable(tool, args):
    assert wa.bypass(tool, args) is None
