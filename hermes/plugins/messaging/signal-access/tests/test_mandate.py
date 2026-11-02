"""signal-access send mandates: making, listing and revoking one, and the sends it covers, through the hook
and the handler over a fake Keychain CLI and a fake signal-cli daemon. Nothing outside the temporary folder
is touched."""

import importlib.util
import json
from pathlib import Path
import shutil
import time

import pytest

spec = importlib.util.spec_from_file_location("signal_access_fakes", Path(__file__).resolve().parent / "fakes.py")
fakes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fakes)

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("signal_access_mandate_plugin_test", ROOT / "__init__.py")
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)
store = plugin.sig.store
sm = plugin.send_mandate

ME, ALICE, BOB, GROUP = fakes.ME, fakes.ALICE, fakes.BOB, fakes.GROUP
ALICE_NUMBER, BOB_NUMBER = "+819011111111", "+819022222222"
OTHER_ACCOUNT = "33333333-3333-4333-8333-333333333333"
QUOTED = 1790000000000
MANDATE = {"action": "create", "chats": [ALICE], "per_hour": 2, "max_chars": 50, "days": 7,
           "purpose": "Send the morning report"}
SEND = {"action": "send", "chat": ALICE, "text": "good morning"}
REASONS = ["yolo mode is on", "approvals are off (approvals.mode: off)", "this is a cron job",
           "this is a single-query run", "this platform is unattended", "nobody is present to answer"]
HANDLERS = {"signal": plugin.signal_tool, "signal_mandate": plugin.signal_mandate}
CALL = {"id": ""}
KEY = bytes(range(32))


def fake_cli(path: Path, keyfile: Path) -> Path:
    """A secret CLI over one key file: ``get`` prints it, ``show`` says it exists, ``set --stdin`` stores it."""
    path.write_text(
        "#!/bin/sh\n"
        f"[ \"$1\" = get ] && [ -f {keyfile} ] && cat {keyfile} && exit 0\n"
        f"[ \"$1\" = show ] && [ -f {keyfile} ] && exit 0\n"
        f"[ \"$1\" = set ] && [ ! -f {keyfile} ] && cat > {keyfile} && exit 0\n"
        "exit 1\n")
    path.chmod(0o755)
    return path


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    base = fakes.short_dir()
    monkeypatch.setenv(store.STATE_ENV, str(base))  # never the real state directory
    monkeypatch.setattr(plugin, "_home", lambda: base / "profile")
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: False)
    monkeypatch.setattr(plugin, "_call_id", lambda: CALL["id"])
    monkeypatch.setattr(plugin.sig, "_agent_running", lambda: True)
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: None)   # a person is there to answer cards
    monkeypatch.setattr(sm.mandate_store, "SECRET", fake_cli(base / "secret", base / "keyfile"))
    fakes.link_account(base)
    conn = store.connect(store.db_path(base), write=True)
    store.set_meta(conn, uuid=ME)
    store.upsert_contacts(conn, [{"uuid": ALICE, "number": ALICE_NUMBER, "givenName": "Alice"},
                                 {"uuid": BOB, "number": BOB_NUMBER, "givenName": "Bob"}])
    store.upsert_groups(conn, [{"id": fakes.GROUP_ID, "name": "Family", "isMember": True}])
    store.ingest(conn, fakes.envelope(data={"timestamp": QUOTED, "message": "hello"}), me=ME)
    conn.close()
    plugin.sig._approved.clear()
    plugin._CARDS.clear()
    yield base
    shutil.rmtree(base, ignore_errors=True)


@pytest.fixture
def home(isolated):
    return isolated / "profile"


@pytest.fixture
def daemon(isolated):
    handlers = {"send": lambda p: {"timestamp": 1790000009000, "results": [
        {"recipientAddress": {"uuid": ALICE, "number": "+819011111111"}, "type": "SUCCESS"}]}}
    d = fakes.FakeDaemon(store.socket_path(isolated), handlers)
    yield d
    d.close()


def run(tool, args, call="c1"):
    """The hook, then the handler once the hook lets the call through (a card is answered yes, as in a
    chat): (the hook's directive, the handler's result or None when the hook blocked)."""
    CALL["id"] = call
    directive = plugin.gate(tool_name=tool, args=args, tool_call_id=call)
    if directive and directive["action"] == "block":
        return directive, None
    return directive, json.loads(HANDLERS[tool](dict(args)))


def handle(tool, args, call="c1"):
    CALL["id"] = call
    return json.loads(HANDLERS[tool](dict(args)))


def make(**over) -> str:
    directive, result = run("signal_mandate", {**MANDATE, **over}, call="make")
    assert directive["action"] == "approve" and result["ok"] is True, result
    return result["mandate"]["id"]


def sends(daemon):
    return [r for r in daemon.requests if r["method"] == "send"]


def used(home, mandate_id):
    return sm._used(home, "signal", mandate_id, time.time())


def asks_on_a_card(args, call="s1"):
    directive = plugin.gate(tool_name="signal", args=args, tool_call_id=call)
    return directive["action"] == "approve" and directive["rule_key"].startswith("signal-access:")


# --- making a mandate ---------------------------------------------------------------------------

def test_a_mandate_is_made_on_a_card_of_its_own(home):
    directive, result = run("signal_mandate", MANDATE)
    assert directive["action"] == "approve" and directive["rule_key"].startswith("signal-access:mandate:")
    card = directive["message"]
    assert card.startswith("Signal · Send mandate\n🚨 Plain text sends to these chats skip the card\n")
    for line in (f"Chat: Alice (user, {ALICE_NUMBER})", f"Account: {fakes.NUMBER}",
                 "Up to: 2 an hour, 50 characters each", "(7 days)",
                 "Purpose: Send the morning report", "Never covered: files, quotes, replies"):
        assert line in card
    assert result["ok"] is True and result["mandate"]["chats"] == [f"Alice ({ALICE_NUMBER})"]
    assert result["mandate"]["per_hour"] == 2 and result["mandate"]["max_chars"] == 50
    listed = handle("signal_mandate", {"action": "list"})
    assert listed == {"ok": True, "mandates": [result["mandate"]]}
    assert (home / "signal-access" / "mandates").is_dir() and (home / "signal-access" / "head.json").is_file()


def test_every_mandate_asks_on_a_fresh_key():
    keys = {plugin.gate(tool_name="signal_mandate", args=dict(MANDATE), tool_call_id=f"c{n}")["rule_key"]
            for n in range(3)}
    assert len(keys) == 3 and all(k.startswith("signal-access:mandate:") for k in keys)


def test_a_group_and_the_own_chat_are_named_by_kind():
    directive, result = run("signal_mandate", {**MANDATE, "chats": [GROUP, ME, ALICE.upper()]})
    assert f"Chat: Family (group, {GROUP})" in directive["message"]
    assert f"Chat: Note to Self (self, {fakes.NUMBER})" in directive["message"]
    assert f"Chat: Alice (user, {ALICE_NUMBER})" in directive["message"]
    assert result["ok"] is True
    assert result["mandate"]["chats"] == [f"Family ({GROUP})", f"Note to Self ({fakes.NUMBER})",
                                          f"Alice ({ALICE_NUMBER})"]


def test_chats_with_one_name_show_their_own_numbers(isolated):
    conn = store.connect(store.db_path(isolated), write=True)
    conn.execute("UPDATE contacts SET name = 'Mom' WHERE uuid IN (?, ?)", (ALICE, BOB))
    conn.commit()
    conn.close()
    lines = plugin.gate(tool_name="signal_mandate", args={**MANDATE, "chats": [ALICE, BOB]},
                        tool_call_id="c1")["message"].splitlines()
    assert f"Chat: Mom (user, {ALICE_NUMBER})" in lines and f"Chat: Mom (user, {BOB_NUMBER})" in lines


def test_no_card_no_mandate(home):
    assert "only on its own card" in handle("signal_mandate", dict(MANDATE))["error"]
    assert handle("signal_mandate", {"action": "list"})["mandates"] == []
    assert not (home / "signal-access").exists()


def test_the_card_belongs_to_its_call_and_is_used_once(home):
    plugin.gate(tool_name="signal_mandate", args=dict(MANDATE), tool_call_id="a")
    assert "only on its own card" in handle("signal_mandate", dict(MANDATE), call="b")["error"]
    assert handle("signal_mandate", dict(MANDATE), call="a")["ok"] is True
    assert "only on its own card" in handle("signal_mandate", dict(MANDATE), call="a")["error"]
    assert len(handle("signal_mandate", {"action": "list"})["mandates"]) == 1


@pytest.mark.parametrize("reason", REASONS)
def test_a_mandate_is_not_made_where_nobody_answers_its_card(monkeypatch, reason):
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: reason)
    directive = plugin.gate(tool_name="signal_mandate", args=dict(MANDATE), tool_call_id="c1")
    assert directive["action"] == "block" and reason in directive["message"]
    assert "only on its own card" in handle("signal_mandate", dict(MANDATE))["error"]
    assert handle("signal_mandate", {"action": "list"})["mandates"] == []


def test_the_handler_asks_again_whether_a_person_is_there(monkeypatch):
    plugin.gate(tool_name="signal_mandate", args=dict(MANDATE), tool_call_id="c1")
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: "this is a cron job")
    result = handle("signal_mandate", dict(MANDATE))
    assert result["ok"] is False and "this is a cron job" in result["error"]
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: None)
    assert handle("signal_mandate", {"action": "list"})["mandates"] == []


def test_inbound_a2a_makes_nothing(monkeypatch):
    plugin.gate(tool_name="signal_mandate", args=dict(MANDATE), tool_call_id="c1")
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    for args in (MANDATE, {"action": "list"}):
        directive = plugin.gate(tool_name="signal_mandate", args=dict(args), tool_call_id="c2")
        assert directive["action"] == "block" and "A2A" in directive["message"]
        result = handle("signal_mandate", dict(args), call="c1")
        assert result["ok"] is False and "A2A" in result["error"]
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: False)
    assert handle("signal_mandate", {"action": "list"})["mandates"] == []


def test_a_chat_that_reads_differently_at_the_write_is_refused(isolated):
    plugin.gate(tool_name="signal_mandate", args=dict(MANDATE), tool_call_id="c1")
    conn = store.connect(store.db_path(isolated), write=True)
    conn.execute("UPDATE contacts SET name = 'Mallory' WHERE uuid = ?", (ALICE,))
    conn.commit()
    conn.close()
    result = handle("signal_mandate", dict(MANDATE))
    assert result["ok"] is False and "changed since the card" in result["error"]
    assert handle("signal_mandate", {"action": "list"})["mandates"] == []


def test_the_account_that_changes_at_the_write_is_refused(isolated):
    plugin.gate(tool_name="signal_mandate", args=dict(MANDATE), tool_call_id="c1")
    relink(isolated, OTHER_ACCOUNT)
    assert "changed since the card" in handle("signal_mandate", dict(MANDATE))["error"]


def test_without_a_profile_home_nothing_is_made_or_listed(monkeypatch):
    monkeypatch.setattr(plugin, "_home", lambda: None)
    assert plugin.gate(tool_name="signal_mandate", args=dict(MANDATE), tool_call_id="c1")["action"] == "approve"
    assert "no profile home" in handle("signal_mandate", dict(MANDATE))["error"]
    assert "no profile home" in handle("signal_mandate", {"action": "revoke", "mandate": "m1a2b3c4d"})["error"]
    assert handle("signal_mandate", {"action": "list"}) == {"ok": True, "mandates": []}


@pytest.mark.parametrize("over, message", [
    ({"chats": ["Alice"]}, "chat id"),
    ({"chats": ["+819011111111"]}, "chat id"),
    ({"chats": ALICE}, "chats is a list"),
    ({"chats": [7]}, "chat must be a string"),
    ({"chats": []}, "one to 5 chats"),
    ({"chats": [ALICE, ALICE.upper()]}, "named once"),
    ({"chats": [ALICE, BOB, ME, GROUP, "44444444-4444-4444-8444-444444444444",
                "55555555-5555-4555-8555-555555555555"]}, "one to 5 chats"),
    ({"chats": ["group:" + "Z" * 43 + "="]}, "not in the mirror"),
    ({"per_hour": 31}, "per_hour"),
    ({"per_hour": True}, "per_hour"),
    ({"max_chars": 1001}, "max_chars"),
    ({"days": 31}, "days"),
    ({"days": None}, "days"),
    ({"purpose": " "}, "purpose"),
])
def test_terms_that_are_not_acceptable_are_blocked_without_a_card(over, message):
    directive = plugin.gate(tool_name="signal_mandate", args={**MANDATE, **over}, tool_call_id="c1")
    assert directive["action"] == "block" and message in directive["message"]
    assert plugin._CARDS == {}


def test_a_group_the_user_left_is_refused(isolated):
    conn = store.connect(store.db_path(isolated), write=True)
    conn.execute("UPDATE chats SET member = 0 WHERE id = ?", (GROUP,))
    conn.commit()
    conn.close()
    directive = plugin.gate(tool_name="signal_mandate", args={**MANDATE, "chats": [GROUP]}, tool_call_id="c1")
    assert directive["action"] == "block" and "no longer a member" in directive["message"]


# --- listing and revoking -----------------------------------------------------------------------

def test_list_and_revoke_need_no_card(home):
    mandate_id = make()
    assert plugin.gate(tool_name="signal_mandate", args={"action": "list"}) is None
    revoke = {"action": "revoke", "mandate": mandate_id}
    assert plugin.gate(tool_name="signal_mandate", args=revoke) is None
    assert handle("signal_mandate", revoke) == {"ok": True, "revoked": mandate_id}
    assert handle("signal_mandate", {"action": "list"})["mandates"] == []
    assert handle("signal_mandate", revoke)["note"] == "it was not in force"


@pytest.mark.parametrize("reason", REASONS)
def test_revoking_works_where_nobody_answers_cards(monkeypatch, reason):
    mandate_id = make()
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: reason)
    result = handle("signal_mandate", {"action": "revoke", "mandate": mandate_id})
    assert result == {"ok": True, "revoked": mandate_id}


def test_bad_revokes_and_actions_are_errors_in_json():
    assert "an id like" in handle("signal_mandate", {"action": "revoke", "mandate": "nope"})["error"]
    assert "an id like" in handle("signal_mandate", {"action": "revoke"})["error"]
    assert "create, list or revoke" in handle("signal_mandate", {"action": "forward"})["error"]
    assert json.loads(plugin.signal_mandate("not a dict"))["ok"] is False


# --- a send inside a mandate --------------------------------------------------------------------

def test_a_fitting_text_send_needs_no_card_and_is_counted(home, daemon):
    mandate_id = make()
    directive, result = run("signal", SEND)
    assert directive is None and result["ok"] is True and result["chat"] == ALICE
    assert [r["params"] for r in sends(daemon)] == [{"recipient": [ALICE], "message": "good morning"}]
    assert used(home, mandate_id) == 1
    assert plugin.sig._approved == {}
    # the mirror records it like any send
    last = plugin.sig.execute({"action": "messages", "chat": ALICE})["messages"][-1]
    assert last["from"] == "me" and last["text"] == "good morning"


def test_the_hook_is_a_peek_and_the_write_takes_the_record_once(daemon):
    mandate_id = make()
    assert plugin.gate(tool_name="signal", args=dict(SEND), tool_call_id="c1") is None
    assert plugin.sig.covered(SEND, "c1") == mandate_id == plugin.sig.covered(SEND, "c1")
    assert plugin.sig.covered(SEND, "c2") is None
    assert handle("signal", SEND)["ok"] is True
    assert plugin.sig.covered(SEND, "c1") is None
    assert "did not pass the approval card" in handle("signal", SEND)["error"]
    assert len(sends(daemon)) == 1


@pytest.mark.parametrize("reason", REASONS)
def test_a_fitting_send_runs_where_nobody_can_answer_a_card(monkeypatch, home, daemon, reason):
    mandate_id = make()
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: reason)
    directive, result = run("signal", SEND)
    assert directive is None and result["ok"] is True
    assert len(sends(daemon)) == 1 and used(home, mandate_id) == 1


def test_a_send_outside_the_mandate_keeps_the_rules_where_nobody_answers(monkeypatch, home, daemon):
    make()
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: "this is a cron job")
    for args in ({**SEND, "chat": BOB}, {**SEND, "text": "x" * 51}, {**SEND, "reply_to": str(QUOTED)}):
        directive = plugin.gate(tool_name="signal", args=args, tool_call_id="c1")
        assert directive["action"] == "block" and "this is a cron job" in directive["message"]
        result = handle("signal", args)
        assert result["ok"] is False and "this is a cron job" in result["error"]
    assert plugin.sig._approved == {} and daemon.requests == []


def test_the_hourly_bound_turns_the_next_send_into_a_card(monkeypatch, home, daemon):
    mandate_id = make()
    for n in range(2):
        assert run("signal", SEND, call=f"s{n}")[1]["ok"] is True
    assert used(home, mandate_id) == 2
    directive = plugin.gate(tool_name="signal", args=dict(SEND), tool_call_id="s3")
    assert directive["action"] == "approve" and directive["rule_key"].startswith("signal-access:send:")
    assert directive["message"].startswith("Signal · Send message\n⚠️ They see it at once\n")
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: "this is a cron job")
    directive = plugin.gate(tool_name="signal", args=dict(SEND), tool_call_id="s4")
    assert directive["action"] == "block" and "this is a cron job" in directive["message"]
    assert len(sends(daemon)) == 2 and used(home, mandate_id) == 2


def test_the_hour_rolls_over(monkeypatch, daemon):
    make()
    for n in range(2):
        run("signal", SEND, call=f"s{n}")
    real = time.time
    monkeypatch.setattr(time, "time", lambda: real() + 3601)
    assert plugin.gate(tool_name="signal", args=dict(SEND), tool_call_id="s9") is None
    assert handle("signal", SEND, call="s9")["ok"] is True
    assert len(sends(daemon)) == 3


@pytest.mark.parametrize("name, over", [
    ("another chat", {"chat": BOB}),
    ("a group", {"chat": GROUP}),
    ("the own chat", {"chat": ME}),
    ("a reply", {"reply_to": str(QUOTED)}),
    ("more than max_chars", {"text": "x" * 51}),
])
def test_a_send_that_does_not_fit_asks_on_its_card_as_before(daemon, name, over):
    make()
    assert asks_on_a_card({**SEND, **over}), name


def test_a_send_with_a_file_asks_on_its_card(isolated, monkeypatch):
    make()
    workspace = isolated / "Workspaces"
    workspace.mkdir()
    monkeypatch.setattr(plugin.sig, "SEND_ROOT", workspace)
    (workspace / "a.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16)
    assert asks_on_a_card({**SEND, "files": [str(workspace / "a.png")]})
    plugin.sig._approved.clear()
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: "this is a cron job")
    directive = plugin.gate(tool_name="signal", args={**SEND, "files": ["a.png"]}, tool_call_id="s2")
    assert directive["action"] == "block" and plugin.sig._approved == {}


def test_a_send_from_another_account_asks_on_its_card(isolated):
    make()
    relink(isolated, OTHER_ACCOUNT)
    assert asks_on_a_card(SEND)


def test_a_revoked_mandate_covers_nothing_more(daemon):
    mandate_id = make()
    handle("signal_mandate", {"action": "revoke", "mandate": mandate_id})
    assert asks_on_a_card(SEND)


def test_an_ended_mandate_covers_nothing_more(monkeypatch):
    make(days=1)
    real = time.time
    monkeypatch.setattr(time, "time", lambda: real() + 2 * 86400)
    assert asks_on_a_card(SEND)


def test_a_mandate_without_its_key_covers_nothing(isolated):
    make()
    (isolated / "keyfile").unlink()
    assert asks_on_a_card(SEND)


def test_a_deleted_ledger_turns_the_send_into_a_card(home, daemon):
    mandate_id = make()
    assert plugin.gate(tool_name="signal", args=dict(SEND), tool_call_id="c1") is None
    (home / "signal-access" / "uses.jsonl").unlink()
    assert "no longer fits the send mandate" in handle("signal", SEND)["error"]
    assert asks_on_a_card(SEND) and daemon.requests == [] and used(home, mandate_id) == sm.MAX_PER_HOUR


def test_an_edited_head_covers_nothing(home):
    make()
    head = home / "signal-access" / "head.json"
    body = json.loads(head.read_text())
    body["active"].append("m00000000")
    head.write_text(json.dumps(body))
    assert asks_on_a_card(SEND)


def test_a_mandate_revoked_between_the_hook_and_the_write_sends_nothing(home, daemon):
    mandate_id = make()
    assert plugin.gate(tool_name="signal", args=dict(SEND), tool_call_id="c1") is None
    handle("signal_mandate", {"action": "revoke", "mandate": mandate_id})
    result = handle("signal", SEND)
    assert result["ok"] is False and result["error"].startswith("not sent: it no longer fits the send mandate (")
    assert "is no longer in force" in result["error"] and "it will ask on a card" in result["error"]
    assert daemon.requests == [] and used(home, mandate_id) == 0


def test_the_last_slot_of_the_hour_goes_to_one_send(home, daemon):
    mandate_id = make(per_hour=1)
    assert plugin.gate(tool_name="signal", args=dict(SEND), tool_call_id="a") is None
    assert plugin.gate(tool_name="signal", args=dict(SEND), tool_call_id="b") is None
    assert handle("signal", SEND, call="a")["ok"] is True
    result = handle("signal", SEND, call="b")
    assert result["ok"] is False and "1 sends in the last hour" in result["error"]
    assert len(sends(daemon)) == 1 and used(home, mandate_id) == 1


def test_a_text_changed_after_the_hook_is_not_sent(monkeypatch, home, daemon):
    mandate_id = make()
    assert plugin.gate(tool_name="signal", args=dict(SEND), tool_call_id="c1") is None
    real = plugin.sig.send_plan
    monkeypatch.setattr(plugin.sig, "send_plan", lambda args: {**real(args), "text": "something else"})
    result = handle("signal", SEND)
    assert result["ok"] is False and "changed after the approval card" in result["error"]
    assert daemon.requests == [] and used(home, mandate_id) == 0


def test_a_chat_that_changes_after_the_hook_is_not_sent(monkeypatch, home, daemon):
    mandate_id = make()
    assert plugin.gate(tool_name="signal", args=dict(SEND), tool_call_id="c1") is None
    real = plugin.sig.send_plan
    monkeypatch.setattr(plugin.sig, "send_plan", lambda args: {**real(args), "chat": BOB})
    assert handle("signal", SEND)["ok"] is False
    assert daemon.requests == [] and used(home, mandate_id) == 0


def test_the_count_stands_when_the_send_fails(home):
    mandate_id = make()
    directive, result = run("signal", SEND)      # no daemon is listening
    assert directive is None and result["ok"] is False and result["error"].startswith("not sent")
    assert used(home, mandate_id) == 1


def test_the_count_stands_when_the_send_is_uncertain(monkeypatch, isolated, home):
    mandate_id = make()
    monkeypatch.setattr(plugin.sig, "SEND_TIMEOUT", 0.5)
    d = fakes.FakeDaemon(store.socket_path(isolated), {"send": lambda p: fakes.NO_REPLY})
    try:
        result = run("signal", SEND)[1]
    finally:
        d.close()
    assert result["ok"] is False and result["error"].startswith("UNCERTAIN")
    assert used(home, mandate_id) == 1


def test_a_covered_call_without_a_record_is_refused(monkeypatch, daemon):
    make()
    assert "did not pass the approval card" in handle("signal", SEND)["error"]
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: "this is a cron job")
    assert "this is a cron job" in handle("signal", SEND)["error"]
    assert daemon.requests == []


def test_the_record_of_one_call_does_not_open_another(monkeypatch, daemon):
    make()
    assert plugin.gate(tool_name="signal", args=dict(SEND), tool_call_id="c1") is None
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: "this is a cron job")
    assert "this is a cron job" in handle("signal", SEND, call="c2")["error"]
    assert "this is a cron job" in handle("signal", {**SEND, "text": "other"}, call="c1")["error"]
    assert daemon.requests == []


def test_a_record_made_on_a_card_does_not_open_the_unattended_path(monkeypatch, daemon):
    plugin.gate(tool_name="signal", args=dict(SEND), tool_call_id="c1")     # a card, no mandate
    assert plugin.sig.covered(SEND, "c1") is None
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: "this is a cron job")
    assert "this is a cron job" in handle("signal", SEND)["error"]
    assert daemon.requests == []


def test_reads_are_unaffected(monkeypatch, daemon):
    make()
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: "this is a cron job")
    for args in ({"action": "chats"}, {"action": "status"}, {"action": "messages", "chat": ALICE}):
        assert plugin.gate(tool_name="signal", args=dict(args)) is None
        assert handle("signal", args)["ok"] is True


def test_without_a_profile_home_nothing_is_covered(monkeypatch, daemon):
    make()
    monkeypatch.setattr(plugin, "_home", lambda: None)
    assert asks_on_a_card(SEND)


def test_a_mandate_of_one_service_is_not_read_for_another(home):
    make()
    assert sm.active(home, "telegram") == [] and len(sm.active(home, "signal")) == 1


def relink(base, uuid):
    path = base / "signal-cli" / "data" / "accounts.json"
    listing = json.loads(path.read_text())
    listing["accounts"][0]["uuid"] = uuid
    path.write_text(json.dumps(listing))
