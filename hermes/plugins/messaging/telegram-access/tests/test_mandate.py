"""Send mandates in telegram-access: making, listing and revoking one through the hook and the handler,
and the sends it covers (no card, also where nobody can answer one), over a seeded mirror, a fake sync
agent and a fake Keychain. Never the real agent, state or Keychain."""

import importlib.util
import json
from pathlib import Path
import shutil
import time

import pytest

spec = importlib.util.spec_from_file_location("telegram_access_fakes", Path(__file__).resolve().parent / "fakes.py")
fakes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fakes)

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("telegram_access_plugin_mandate_test", ROOT / "__init__.py")
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)
tg = plugin.tg
store = tg.store
sm = plugin.send_mandate

ACCOUNT = str(fakes.ME)
MAKE = {"action": "create", "chats": [str(fakes.ALICE)], "per_hour": 2, "max_chars": 50, "days": 7,
        "purpose": "The morning report"}
SEND = {"action": "send", "chat": str(fakes.ALICE), "text": "good morning"}
CALL = "call-1"


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    base = fakes.short_dir()
    keychain = fakes.short_dir()
    monkeypatch.setenv(store.STATE_ENV, str(base))  # never the real state directory
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: False)
    monkeypatch.setattr(plugin, "_home", lambda: base)
    monkeypatch.setattr(plugin, "_call_id", lambda: CALL)
    monkeypatch.setattr(tg, "_agent_running", lambda: True)
    monkeypatch.setattr(plugin, "_unattended", lambda: False)
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: None)  # a person is present
    monkeypatch.setattr(sm.mandate_store, "SECRET", fakes.fake_secret(keychain))  # never the Keychain
    fakes.seed(base)
    tg._approved.clear()
    plugin._DECISIONS.clear()
    yield base
    shutil.rmtree(base, ignore_errors=True)
    shutil.rmtree(keychain, ignore_errors=True)


@pytest.fixture()
def agent(isolated):
    handlers = {"send": lambda p: {"ids": [99], "ts": 1, "recorded": True}}
    fake = fakes.FakeAgent(store.socket_path(isolated), handlers)
    fake.handlers_ = handlers
    yield fake
    fake.close()


def sent(agent):
    return [r for r in agent.requests if r["method"] == "send"]


def uses(base):
    """How many counted sends the ledger holds (the opening rows of the mandates are not sends)."""
    path = base / "telegram-access" / "uses.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    return len([row for row in rows if not row.get("open")])


def change_mirror(base, chat, **fields):
    conn = store.connect(store.db_path(base), write=True)
    store.upsert_chat(conn, chat, **fields)
    conn.close()


def hook(tool, args, call_id=CALL):
    return plugin.gate(tool_name=tool, args=dict(args), tool_call_id=call_id)


def make(**over):
    args = {**MAKE, **over}
    assert hook("telegram_mandate", args)["action"] == "approve"
    result = json.loads(plugin.telegram_mandate(dict(args)))
    assert result["ok"] is True, result
    return result["mandate"]["id"]


def run_send(args=SEND):
    """The hook, then (when it lets the call through or after a card) the handler."""
    directive = hook("telegram_account", args)
    return directive, json.loads(plugin.telegram_account(dict(args)))


# --- making, listing and revoking ---------------------------------------------------------------

def test_a_mandate_is_made_on_its_own_card(isolated):
    directive = hook("telegram_mandate", MAKE)
    assert directive["action"] == "approve" and directive["rule_key"].startswith("telegram-access:mandate:")
    lines = directive["message"].splitlines()
    assert lines[0] == "Telegram · Send mandate"
    assert lines[1] == "🚨 Plain text sends to these chats skip the card"
    assert "Chat: Alice (user, @alice)" in lines and "Account: Rui (@rui)" in lines
    assert "Up to: 2 an hour, 50 characters each" in lines and "Purpose: The morning report" in lines
    assert any(line.startswith("Until: ") and line.endswith("(7 days)") for line in lines)
    assert sm.active(isolated, "telegram") == []  # the card alone makes nothing
    made = json.loads(plugin.telegram_mandate(dict(MAKE)))
    assert made["ok"] is True and made["mandate"]["chats"] == ["Alice (@alice)"] and made["mandate"]["per_hour"] == 2
    assert made["mandate"]["service"] == "telegram"
    body, = sm.active(isolated, "telegram")
    assert body["account"] == ACCOUNT and body["account_label"] == "Rui (@rui)"
    assert body["chats"] == [{"id": str(fakes.ALICE), "name": "Alice", "kind": "user", "identity": "@alice"}]
    assert body["expires"] > time.time() + 6 * 86400


def test_every_mandate_card_has_a_fresh_key_and_asks_even_with_a_mandate_in_force():
    keys = {hook("telegram_mandate", MAKE)["rule_key"] for _ in range(3)}
    assert len(keys) == 3
    make()
    again = hook("telegram_mandate", MAKE)
    assert again["action"] == "approve" and again["rule_key"] not in keys


def test_a_mandate_needs_its_own_card_and_its_record_is_used_once(isolated):
    refused = json.loads(plugin.telegram_mandate(dict(MAKE)))
    assert refused["ok"] is False and "only on its own card" in refused["error"]
    hook("telegram_mandate", MAKE)
    assert json.loads(plugin.telegram_mandate(dict(MAKE)))["ok"] is True
    assert "only on its own card" in json.loads(plugin.telegram_mandate(dict(MAKE)))["error"]
    assert len(sm.active(isolated, "telegram")) == 1


def test_the_card_belongs_to_its_tool_call(monkeypatch, isolated):
    hook("telegram_mandate", MAKE, "call-a")
    monkeypatch.setattr(plugin, "_call_id", lambda: "call-b")
    assert "only on its own card" in json.loads(plugin.telegram_mandate(dict(MAKE)))["error"]
    assert sm.active(isolated, "telegram") == []
    monkeypatch.setattr(plugin, "_call_id", lambda: "call-a")
    assert json.loads(plugin.telegram_mandate(dict(MAKE)))["ok"] is True


def test_a_mandate_is_not_made_where_nobody_answers_its_card(monkeypatch, isolated):
    monkeypatch.setattr(plugin, "_unattended", lambda: True)
    directive = hook("telegram_mandate", MAKE)
    assert directive["action"] == "block" and "answers its card" in directive["message"]
    assert "answers its card" in json.loads(plugin.telegram_mandate(dict(MAKE)))["error"]
    monkeypatch.setattr(plugin, "_unattended", lambda: False)
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: "yolo mode is on")
    directive = hook("telegram_mandate", MAKE)
    assert directive["action"] == "block" and "yolo mode is on" in directive["message"]
    assert not plugin._DECISIONS and sm.active(isolated, "telegram") == []


def test_a_card_decided_with_a_person_is_not_enough_where_the_handler_finds_none(monkeypatch, isolated):
    hook("telegram_mandate", MAKE)
    monkeypatch.setattr(plugin, "_unattended", lambda: True)
    assert "answers its card" in json.loads(plugin.telegram_mandate(dict(MAKE)))["error"]
    monkeypatch.setattr(plugin, "_unattended", lambda: False)
    hook("telegram_mandate", MAKE)
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: "nobody is present to answer")
    assert "nobody is present" in json.loads(plugin.telegram_mandate(dict(MAKE)))["error"]
    assert sm.active(isolated, "telegram") == []


def test_inbound_a2a_makes_lists_and_revokes_nothing(monkeypatch, isolated):
    mandate_id = make()
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    for args in (MAKE, {"action": "list"}, {"action": "revoke", "mandate": mandate_id}):
        assert hook("telegram_mandate", args)["action"] == "block"
        result = json.loads(plugin.telegram_mandate(dict(args)))
        assert result["ok"] is False and "A2A" in result["error"]
    assert [m["id"] for m in sm.active(isolated, "telegram")] == [mandate_id]


def test_changed_chat_resolution_between_card_and_handler_makes_nothing(isolated):
    hook("telegram_mandate", MAKE)
    change_mirror(isolated, fakes.ALICE, name="Alicia")
    result = json.loads(plugin.telegram_mandate(dict(MAKE)))
    assert result["ok"] is False and "changed since the card" in result["error"]
    assert sm.active(isolated, "telegram") == []
    hook("telegram_mandate", MAKE)
    conn = store.connect(store.db_path(isolated), write=True)
    store.set_meta(conn, me_id=777)  # another account signed in
    conn.close()
    assert "changed since the card" in json.loads(plugin.telegram_mandate(dict(MAKE)))["error"]


def test_the_handler_makes_the_terms_the_card_showed(isolated):
    hook("telegram_mandate", MAKE)
    changed = {**MAKE, "per_hour": 30, "max_chars": 1000, "days": 30, "purpose": "Something else"}
    # The model cannot widen what the card showed: the same call id with other arguments has no card.
    assert "only on its own card" in json.loads(plugin.telegram_mandate(changed))["error"]
    assert json.loads(plugin.telegram_mandate(dict(MAKE)))["mandate"]["per_hour"] == 2


@pytest.mark.parametrize("over,match", [
    ({"chats": [str(fakes.BOT)]}, "a mandate never covers bots or broadcast channels"),
    ({"chats": [str(fakes.CHANNEL)]}, "a mandate never covers bots or broadcast channels"),
    ({"chats": ["Alice"]}, "not a name"),
    ({"chats": ["@alice"]}, "not a name"),
    ({"chats": ["777"]}, "not in the chat list"),
    ({"chats": []}, "chats is a list"),
    ({"chats": str(fakes.ALICE)}, "chats is a list"),
    ({"chats": [str(fakes.ALICE), str(fakes.ALICE)]}, "named once"),
    ({"per_hour": 0}, "per_hour"), ({"per_hour": 31}, "per_hour"), ({"max_chars": 1001}, "max_chars"),
    ({"days": 31}, "days"), ({"days": "7"}, "days"), ({"purpose": " "}, "purpose"),
])
def test_unacceptable_terms_get_no_card(over, match):
    directive = hook("telegram_mandate", {**MAKE, **over})
    assert directive["action"] == "block" and match in directive["message"] and not plugin._DECISIONS


def test_a_chat_the_user_cannot_post_in_or_has_left_gets_no_card(isolated):
    change_mirror(isolated, fakes.GROUP, left_chat=1)
    assert "no longer in that chat" in hook("telegram_mandate", {**MAKE, "chats": [str(fakes.GROUP)]})["message"]
    change_mirror(isolated, fakes.GROUP, left_chat=0, can_send=0)
    assert "cannot post" in hook("telegram_mandate", {**MAKE, "chats": [str(fakes.GROUP)]})["message"]


def test_an_excluded_chat_gets_no_card(isolated):
    (isolated / "config.yaml").write_text(f"telegram_access:\n  exclude_chats: [{fakes.ALICE}]\n")
    assert tg.EXCLUDED in hook("telegram_mandate", MAKE)["message"]


def test_groups_and_supergroups_are_allowed_up_to_five_chats(isolated):
    args = {**MAKE, "chats": [str(fakes.ALICE), str(fakes.GROUP), str(fakes.SUPER)]}
    directive = hook("telegram_mandate", args)
    assert directive["action"] == "approve"
    assert f"Chat: Family (group, id {fakes.GROUP})" in directive["message"]
    assert f"Chat: Big group (supergroup, @biggroup, id {fakes.SUPER})" in directive["message"]


def test_chats_with_one_name_show_their_own_handles(isolated):
    change_mirror(isolated, fakes.ALICE, name="Mom")
    change_mirror(isolated, fakes.GROUP, name="Mom")
    args = {**MAKE, "chats": [str(fakes.ALICE), str(fakes.GROUP)]}
    lines = hook("telegram_mandate", args)["message"].splitlines()
    assert "Chat: Mom (user, @alice)" in lines and f"Chat: Mom (group, id {fakes.GROUP})" in lines


def test_only_this_accounts_own_saved_messages_can_be_named(isolated):
    own = {**MAKE, "chats": [str(fakes.ME)]}
    directive = hook("telegram_mandate", own)
    assert directive["action"] == "approve" and "Chat: Saved Messages (self, @rui, id 1000)" in directive["message"]
    change_mirror(isolated, 555, kind="self", name="Someone else")
    refused = hook("telegram_mandate", {**MAKE, "chats": ["555"]})
    assert refused["action"] == "block" and "Saved Messages of another account" in refused["message"]


def test_a_mandate_is_listed_and_revoked_without_a_card(isolated):
    assert hook("telegram_mandate", {"action": "list"}) is None
    assert json.loads(plugin.telegram_mandate({"action": "list"})) == {"ok": True, "mandates": []}
    mandate_id = make()
    listed = json.loads(plugin.telegram_mandate({"action": "list"}))["mandates"]
    assert [m["id"] for m in listed] == [mandate_id] and listed[0]["chats"] == ["Alice (@alice)"]
    revoke = {"action": "revoke", "mandate": mandate_id}
    assert hook("telegram_mandate", revoke) is None
    assert json.loads(plugin.telegram_mandate(dict(revoke))) == {"ok": True, "revoked": mandate_id}
    assert json.loads(plugin.telegram_mandate({"action": "list"}))["mandates"] == []
    assert json.loads(plugin.telegram_mandate(dict(revoke)))["note"] == "it was not in force"
    assert json.loads(plugin.telegram_mandate({"action": "revoke", "mandate": "nope"}))["ok"] is False
    assert json.loads(plugin.telegram_mandate({"action": "wipe"}))["ok"] is False
    assert json.loads(plugin.telegram_mandate("not a dict"))["ok"] is False


def test_without_a_profile_home_nothing_is_made_or_covered(monkeypatch):
    monkeypatch.setattr(plugin, "_home", lambda: None)
    assert hook("telegram_mandate", MAKE)["action"] == "block"
    assert json.loads(plugin.telegram_mandate(dict(MAKE)))["ok"] is False
    assert json.loads(plugin.telegram_mandate({"action": "list"})) == {"ok": True, "mandates": []}
    assert json.loads(plugin.telegram_mandate({"action": "revoke", "mandate": "m1a2b3c4d"}))["ok"] is False
    assert hook("telegram_account", SEND)["action"] == "approve"


# --- sends inside a mandate ----------------------------------------------------------------------

def test_a_fitting_text_send_runs_with_no_card_and_is_counted(isolated, agent):
    make()
    directive, result = run_send()
    assert directive is None
    assert result["ok"] is True and result["ids"] == ["99"]
    assert [r["params"] for r in sent(agent)] == [{"chat": fakes.ALICE, "text": "good morning"}]
    assert uses(isolated) == 1 and not tg._approved


@pytest.mark.parametrize("context", ["unattended", "yolo", "nobody present", "both"])
def test_a_fitting_send_also_runs_where_nobody_can_answer_a_card(monkeypatch, isolated, agent, context):
    make()
    if context in ("unattended", "both"):
        monkeypatch.setattr(plugin, "_unattended", lambda: True)
    if context != "unattended":
        monkeypatch.setattr(plugin.human_gate, "no_human",
                            lambda: "yolo mode is on" if context == "yolo" else "nobody is present to answer")
    directive, result = run_send()
    assert directive is None and result["ok"] is True
    assert len(sent(agent)) == 1 and uses(isolated) == 1


def test_a_send_to_a_group_and_to_saved_messages_can_be_covered(isolated, agent):
    make(chats=[str(fakes.GROUP), str(fakes.ME)])
    for chat in (fakes.GROUP, fakes.ME):
        directive, result = run_send({**SEND, "chat": str(chat)})
        assert directive is None and result["ok"] is True, result
    assert len(sent(agent)) == 2 and uses(isolated) == 2


def test_the_hourly_bound_turns_the_next_send_into_an_ordinary_card(isolated, agent):
    make(per_hour=2)
    for _ in range(2):
        assert run_send()[0] is None
    directive = hook("telegram_account", SEND)
    assert directive["action"] == "approve" and directive["rule_key"].startswith("telegram-access:send:")
    assert "Chat: Alice (@alice)" in directive["message"]
    assert len(sent(agent)) == 2 and uses(isolated) == 2


def test_in_cron_the_hourly_bound_is_a_refusal(monkeypatch, isolated, agent):
    make(per_hour=1)
    monkeypatch.setattr(plugin, "_unattended", lambda: True)
    assert run_send()[0] is None
    directive, result = run_send()
    assert directive["action"] == "block" and "approve each one" in directive["message"]
    assert result["ok"] is False and "nothing was sent" in result["error"]
    assert len(sent(agent)) == 1 and uses(isolated) == 1 and not tg._approved
    monkeypatch.setattr(plugin, "_unattended", lambda: False)
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: "this is a cron job")
    directive, result = run_send()
    assert directive["action"] == "block" and "cron job" in directive["message"]
    assert result["ok"] is False and "cron job" in result["error"] and len(sent(agent)) == 1


def change_account(base):
    conn = store.connect(store.db_path(base), write=True)
    store.set_meta(conn, me_id=777, me_name="Other")
    conn.close()


def sign_in_as_another_account(base):
    change_account(base)
    return SEND


MISSES = {
    "another chat": lambda base: {**SEND, "chat": str(fakes.GROUP)},
    "a reply": lambda base: {**SEND, "reply_to": "10"},
    "over max_chars": lambda base: {**SEND, "text": "x" * 51},
    "another account": sign_in_as_another_account,
}


@pytest.mark.parametrize("miss", sorted(MISSES))
def test_a_send_that_does_not_fit_behaves_as_before(monkeypatch, isolated, agent, miss):
    make()
    args = MISSES[miss](isolated)
    directive = hook("telegram_account", args)
    assert directive["action"] == "approve" and directive["rule_key"].startswith("telegram-access:send:")
    assert uses(isolated) == 0
    monkeypatch.setattr(plugin, "_unattended", lambda: True)  # and in cron it is refused
    directive, result = run_send(args)
    assert directive["action"] == "block" and result["ok"] is False and "nothing was sent" in result["error"]
    assert sent(agent) == [] and uses(isolated) == 0


def test_a_send_with_a_file_still_asks_and_is_refused_in_cron(monkeypatch, isolated, agent):
    make()
    workspace = isolated / "Workspaces"
    workspace.mkdir()
    (workspace / "note.txt").write_text("hello")
    monkeypatch.setattr(tg, "SEND_ROOT", workspace)
    args = {**SEND, "files": ["note.txt"]}
    directive = hook("telegram_account", args)
    assert directive["action"] == "approve" and "--- Files (1," in directive["message"]
    monkeypatch.setattr(plugin, "_unattended", lambda: True)
    assert run_send(args)[0]["action"] == "block" and uses(isolated) == 0


def test_after_a_revoke_a_send_asks_again(isolated, agent):
    mandate_id = make()
    assert hook("telegram_account", SEND) is None
    tg._approved.clear()
    sm.revoke(isolated, "telegram", mandate_id)
    assert hook("telegram_account", SEND)["action"] == "approve"


def test_after_the_mandate_ended_a_send_asks_again(monkeypatch, isolated, agent):
    make(days=1)
    assert hook("telegram_account", SEND) is None
    tg._approved.clear()
    real = time.time
    monkeypatch.setattr(time, "time", lambda: real() + 2 * 86400)
    assert hook("telegram_account", SEND)["action"] == "approve"


def test_a_mandate_revoked_between_the_hook_and_the_write_sends_nothing(isolated, agent):
    mandate_id = make()
    assert hook("telegram_account", SEND) is None
    sm.revoke(isolated, "telegram", mandate_id)
    result = json.loads(plugin.telegram_account(dict(SEND)))
    assert result["ok"] is False
    assert result["error"].startswith("not sent: it no longer fits the send mandate (mandate ")
    assert "no longer in force" in result["error"] and "it will ask on a card" in result["error"]
    assert sent(agent) == [] and uses(isolated) == 0


def test_the_last_slot_of_an_hour_goes_to_one_of_two_hooked_sends(monkeypatch, isolated, agent):
    make(per_hour=1)
    assert hook("telegram_account", SEND, "call-a") is None
    assert hook("telegram_account", SEND, "call-b") is None  # both fitted when the hook looked
    results = []
    for call in ("call-a", "call-b"):
        monkeypatch.setattr(plugin, "_call_id", lambda call=call: call)
        results.append(json.loads(plugin.telegram_account(dict(SEND))))
    assert [r["ok"] for r in results] == [True, False]
    assert "allows 1 an hour" in results[1]["error"] and len(sent(agent)) == 1 and uses(isolated) == 1


def test_text_changed_between_the_hook_and_the_write_is_still_refused(monkeypatch, isolated, agent):
    make()
    assert hook("telegram_account", SEND) is None
    real = tg.send_plan
    monkeypatch.setattr(tg, "send_plan", lambda a, h=None: {**real(a, h), "text": "not what was decided"})
    result = json.loads(plugin.telegram_account(dict(SEND)))
    assert "changed after the approval card" in result["error"] and sent(agent) == [] and uses(isolated) == 0


def test_the_count_stands_when_the_send_fails_or_is_uncertain(isolated, agent):
    make(per_hour=3)

    def refuse(p):
        raise fakes.FakeError("not_sent", "UserIsBlockedError: blocked")
    agent.handlers_["send"] = refuse
    assert run_send()[1]["error"].startswith("not sent: UserIsBlockedError")
    assert uses(isolated) == 1

    def unsure(p):
        raise fakes.FakeError("uncertain", "TimeoutError", hint="ids [5]")
    agent.handlers_["send"] = unsure
    assert run_send()[1]["error"].startswith("UNCERTAIN")
    assert uses(isolated) == 2


def test_without_a_readable_key_nothing_is_covered_or_counted(isolated, agent):
    make()
    (Path(sm.mandate_store.SECRET).parent / "keyfile").unlink()
    assert hook("telegram_account", SEND)["action"] == "approve"
    assert sent(agent) == [] and uses(isolated) == 0


def test_a_deleted_ledger_turns_the_send_into_a_card(isolated, agent):
    make()
    assert hook("telegram_account", SEND) is None
    (isolated / "telegram-access" / "uses.jsonl").unlink()
    result = json.loads(plugin.telegram_account(dict(SEND)))
    assert result["ok"] is False and "no longer fits the send mandate" in result["error"]
    tg._approved.clear()
    assert hook("telegram_account", SEND)["action"] == "approve"
    assert sent(agent) == [] and uses(isolated) == 0


def test_a_recorded_mandate_never_takes_the_files_path(monkeypatch, isolated, agent):
    """Even a record carrying a mandate id (the hook never makes one for a file) is refused at the write."""
    mandate_id = make()
    workspace = isolated / "Workspaces"
    workspace.mkdir()
    (workspace / "note.txt").write_text("hello")
    monkeypatch.setattr(tg, "SEND_ROOT", workspace)
    args = {**SEND, "files": ["note.txt"]}
    plan = tg.send_plan(args, isolated)
    tg._approved[tg._call_key(args, CALL)] = (time.monotonic(), tg.request_digest(plan),
                                              [[f["path"], f["sha256"]] for f in plan["files"]], mandate_id)
    result = json.loads(plugin.telegram_account(dict(args)))
    assert result["ok"] is False and "a file always asks on a card" in result["error"]
    assert sent(agent) == [] and uses(isolated) == 0


def test_a_covered_call_without_a_record_is_refused_as_before(monkeypatch, isolated, agent):
    make()
    monkeypatch.setattr(plugin, "_unattended", lambda: True)
    result = json.loads(plugin.telegram_account(dict(SEND)))  # the hook never decided this call
    assert result["ok"] is False and "nothing was sent" in result["error"]
    monkeypatch.setattr(plugin, "_unattended", lambda: False)
    result = json.loads(plugin.telegram_account(dict(SEND)))
    assert "did not pass the approval card" in result["error"] and sent(agent) == []


def test_the_record_of_a_covered_send_belongs_to_its_call(monkeypatch, isolated, agent):
    make()
    assert hook("telegram_account", SEND, "call-a") is None
    monkeypatch.setattr(plugin, "_call_id", lambda: "call-b")
    monkeypatch.setattr(plugin, "_unattended", lambda: True)
    assert json.loads(plugin.telegram_account(dict(SEND)))["ok"] is False
    assert sent(agent) == []
    monkeypatch.setattr(plugin, "_unattended", lambda: False)
    assert "did not pass the approval card" in json.loads(plugin.telegram_account(dict(SEND)))["error"]


def test_reads_are_unaffected_by_a_mandate(monkeypatch, isolated):
    make()
    monkeypatch.setattr(plugin, "_unattended", lambda: True)
    assert hook("telegram_account", {"action": "chats"}) is None
    assert json.loads(plugin.telegram_account({"action": "chats"}))["ok"] is True
    assert hook("telegram_account", {"action": "messages", "chat": str(fakes.ALICE)}) is None
    assert uses(isolated) == 0


def test_a_whatsapp_mandate_covers_nothing_here(isolated, agent):
    chats = [{"id": str(fakes.ALICE), "name": "Alice", "kind": "user", "identity": "+819011111111"}]
    t = sm.terms("whatsapp", ACCOUNT, chats, 5, 100, 7, "Reports")
    sm.create(isolated, t)
    assert hook("telegram_account", SEND)["action"] == "approve"


def test_the_engine_peeks_without_using_up_the_record(isolated):
    make()
    request = tg.approval_request(dict(SEND), home=isolated, call_id=CALL)
    assert isinstance(request, tg.Covered) and sm.mandate_store.valid_id(sm.store("telegram"), request.mandate)
    assert tg.covered(dict(SEND), CALL) == request.mandate and tg.covered(dict(SEND), CALL) == request.mandate
    assert tg.covered(dict(SEND), "other") is None and tg.covered({**SEND, "text": "x"}, CALL) is None
    assert tg.covered({"action": "chats"}, CALL) is None


def test_a_send_outside_every_mandate_raises_when_no_card_can_be_asked(isolated):
    with pytest.raises(tg.TelegramError, match="no card can be answered"):
        tg.approval_request(dict(SEND), home=isolated, call_id=CALL, ask=False)
    assert not tg._approved
    assert tg.approval_request({"action": "chats"}, home=isolated, ask=False) is None
    make()
    assert isinstance(tg.approval_request(dict(SEND), home=isolated, call_id=CALL, ask=False), tg.Covered)
    assert tg.covered(dict(SEND), CALL)


def test_a_card_record_carries_no_mandate(isolated):
    assert tg.approval_request(dict(SEND), home=isolated, call_id=CALL)[1].startswith("telegram-access:send:")
    assert tg.covered(dict(SEND), CALL) is None and len(tg._approved) == 1
