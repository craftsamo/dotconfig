"""The plugin engine over a seeded mirror and a fake sync agent: reads, exclusions, the card,
approval binding, send outcomes, media and the guard. Never the real agent or state."""

import importlib.util
from pathlib import Path
import shutil

import pytest

spec = importlib.util.spec_from_file_location("telegram_access_fakes", Path(__file__).resolve().parent / "fakes.py")
fakes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fakes)
store = fakes.load("store")
tg = fakes.load("tg")


@pytest.fixture(autouse=True)
def state(monkeypatch):
    base = fakes.short_dir()
    monkeypatch.setenv(store.STATE_ENV, str(base))  # never the real state directory
    monkeypatch.setattr(tg, "_agent_running", lambda: True)
    workspace = base / "Workspaces"
    workspace.mkdir()
    monkeypatch.setattr(tg, "SEND_ROOT", workspace)
    fakes.seed(base)
    tg._approved.clear()
    yield base
    shutil.rmtree(base, ignore_errors=True)


@pytest.fixture()
def home(state):
    path = state / "home"
    path.mkdir()
    (path / "config.yaml").write_text(
        f"telegram_access:\n  exclude_chats: [{fakes.HERMES_BOT}, '-55']\n  download_dir: {state}/inbox\n")
    return path


@pytest.fixture()
def agent(state):
    handlers = {}
    fake = fakes.FakeAgent(store.socket_path(state), handlers)
    fake.handlers_ = handlers
    yield fake
    fake.close()


def approve_and_send(args, home, call_id="call-1"):
    request = tg.approval_request(args, home=home, call_id=call_id)
    assert request is not None
    return request, tg.execute(args, home=home, call_id=call_id)


# --- reads ---------------------------------------------------------------------------------------

def test_not_logged_in(state):
    shutil.rmtree(state)
    state.mkdir()
    out = tg.execute({"action": "status"})
    assert out["logged_in"] is False and "login" in out["action_needed"]
    with pytest.raises(tg.TelegramError, match="not set up"):
        tg.execute({"action": "chats"})


def test_status(home):
    out = tg.execute({"action": "status"}, home=home)
    assert out["logged_in"] and out["account"] == "Rui" and out["username"] == "@rui" and out["chats"] == 7
    assert "action_needed" not in out


def test_chats_hide_excluded_and_say_what_is_mirrored(home):
    out = tg.execute({"action": "chats", "last": True}, home=home)
    chats = {c["chat"]: c for c in out["chats"]}
    assert str(fakes.HERMES_BOT) not in chats and out["complete"]
    alice = chats[str(fakes.ALICE)]
    assert alice["kind"] == "person" and alice["unread"] == 2 and alice["mirrored"] and alice["username"] == "@alice"
    assert alice["last"]["id"] == "13" and alice["last"]["text"] == "gone soon" and alice["last"]["expired"]
    assert "expired_note" in out
    big = chats[str(fakes.SUPER)]
    assert big["mirrored"] is False and big["on_sync_list"] is False and "live" in big["last"]
    found = tg.execute({"action": "chats", "query": "@ALI"}, home=home)["chats"]
    assert [c["chat"] for c in found] == [str(fakes.ALICE)]
    assert [c["chat"] for c in tg.execute({"action": "chats", "unread": True}, home=home)["chats"]] == [str(fakes.ALICE)]
    page = tg.execute({"action": "chats", "limit": 2}, home=home)
    assert page["next_offset"] == 2


def test_messages_from_the_mirror(home):
    out = tg.execute({"action": "messages", "chat": str(fakes.ALICE)}, home=home)
    assert out["source"] == "mirror" and [m["id"] for m in out["messages"]] == ["10", "11", "12", "13"]
    reply = out["messages"][1]
    assert reply["from"] == "me" and reply["reply_to"] == "10" and reply["reply_to_text"] == "明日の打ち合わせは？"
    assert out["messages"][2]["file"]["type"] == "photo"
    assert out["messages"][3]["text"] == "gone soon" and out["messages"][3]["expired"]
    assert "history_note" in out and "data" in out["note"] and "only for the user" in out["expired_note"]
    after = tg.execute({"action": "messages", "chat": str(fakes.ALICE), "after": "10", "before": "13"}, home=home)
    assert [m["id"] for m in after["messages"]] == ["11", "12"] and "expired_note" not in after
    with pytest.raises(tg.TelegramError, match="not available"):
        tg.execute({"action": "messages", "chat": str(fakes.HERMES_BOT)}, home=home)
    with pytest.raises(tg.TelegramError, match="not a name"):
        tg.execute({"action": "messages", "chat": "@alice"}, home=home)


def test_disappearing_messages_are_kept_and_marked(state, home):
    conn = store.connect(store.db_path(state), write=True)
    now = store.now_ms()
    store.upsert_message(conn, {"chat": fakes.ALICE, "id": 50, "ts": now, "body": "timed", "expires": now + 60000})
    store.upsert_message(conn, {"chat": fakes.ALICE, "id": 51, "ts": now, "body": "about that", "reply_to": 50})
    store.upsert_message(conn, {"chat": fakes.ALICE, "id": 52, "ts": now, "body": "later", "expires": now + 10 ** 8})
    store.upsert_message(conn, {"chat": fakes.ALICE, "id": 53, "ts": now,
                                "media": {"type": "photo", "self_destructing": True}})
    conn.execute("UPDATE messages SET expires = ? WHERE id = 50", (now - 1,))
    conn.close()
    out = tg.execute({"action": "messages", "chat": str(fakes.ALICE), "after": "49"}, home=home)
    entries = {m["id"]: m for m in out["messages"]}
    assert entries["50"]["text"] == "timed" and "expired" in entries["50"]
    assert entries["51"]["reply_to_text"] == "timed" and entries["51"]["reply_to_expired"] is True
    assert "disappears" in entries["52"] and entries["53"]["file"]["view_once"] is True
    assert "expired_note" in out
    found = tg.execute({"action": "search", "query": "timed"}, home=home)
    assert [m["id"] for m in found["messages"]] == ["50"] and "expired_note" in found


def test_a_kept_file_is_saved_without_asking_telegram(state, home):
    conn = store.connect(store.db_path(state), write=True)
    store.upsert_message(conn, {"chat": fakes.ALICE, "id": 60, "ts": 1, "expires": 2,
                                "media": {"type": "photo", "self_destructing": True, "mime": "image/jpeg"}})
    store.upsert_message(conn, {"chat": fakes.ALICE, "id": 61, "ts": 1,
                                "media": {"type": "photo", "self_destructing": True}})
    conn.close()
    kept = store.kept_path(fakes.ALICE, 60, state)
    kept.mkdir(parents=True)
    (kept / "photo.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 64)
    out = tg.execute({"action": "media", "chat": str(fakes.ALICE), "id": "60"}, home=home)
    saved = Path(out["files"][0]["path"])
    assert out["ok"] and saved.read_bytes()[:3] == b"\xff\xd8\xff" and "kept_note" in out
    assert (kept / "photo.jpg").is_file()  # the kept copy stays
    with pytest.raises(tg.TelegramError, match="not kept"):
        tg.execute({"action": "media", "chat": str(fakes.ALICE), "id": "61"}, home=home)


def test_unmirrored_chats_are_read_live(home, agent):
    agent.handlers["history"] = lambda p: {"messages": [
        {"chat": fakes.SUPER, "id": 5, "ts": store.now_ms(), "sender": 9, "sender_name": "Zed", "body": "yo",
         "media": None, "kind": "message", "from_me": False, "reply_to": None, "fwd_from": None, "edited": None,
         "expires": None, "grouped": None}], "more": False}
    out = tg.execute({"action": "messages", "chat": str(fakes.SUPER), "before": "2026-10-01"}, home=home)
    assert out["source"] == "live" and out["messages"][0]["from"] == "Zed" and "sync list" in out["source_note"]
    params = agent.requests[0]["params"]
    assert params["chat"] == fakes.SUPER and "before_ts" in params and params["limit"] == 50


def test_live_reads_need_the_agent(home):
    with pytest.raises(tg.TelegramError, match="not running"):
        tg.execute({"action": "messages", "chat": str(fakes.SUPER)}, home=home)


def test_search_covers_the_mirror_without_excluded(home):
    out = tg.execute({"action": "search", "query": "打ち合わせ"}, home=home)
    assert [(m["chat"], m["id"]) for m in out["messages"]] == [(str(fakes.GROUP), "30"), (str(fakes.ALICE), "10")]
    assert out["messages"][0]["chat_name"] == "Family" and "mirror only" in out["scope"]
    assert tg.execute({"action": "search", "query": "secret"}, home=home)["messages"] == []
    gone = tg.execute({"action": "search", "query": "gone"}, home=home)
    assert [m["id"] for m in gone["messages"]] == ["13"] and "expired_note" in gone


def test_context_in_the_mirror(home):
    out = tg.execute({"action": "context", "chat": str(fakes.ALICE), "id": "11", "before_count": 1,
                      "after_count": 1}, home=home)
    assert out["source"] == "mirror" and [m["id"] for m in out["messages"]] == ["10", "11", "12"]


def test_sync_list_edits(home):
    with pytest.raises(tg.TelegramError, match="always mirrored"):
        tg.execute({"action": "sync_add", "chats": [str(fakes.GROUP)]}, home=home)
    with pytest.raises(tg.TelegramError, match="not in the chat list"):
        tg.execute({"action": "sync_add", "chats": ["-1000000999999"]}, home=home)
    out = tg.execute({"action": "sync_add", "chats": [str(fakes.SUPER), str(fakes.CHANNEL)]}, home=home)
    assert [e["chat"] for e in out["sync_list"]] == [str(fakes.SUPER), str(fakes.CHANNEL)]
    assert store.read_sync_list() == [fakes.SUPER, fakes.CHANNEL]
    out = tg.execute({"action": "sync_remove", "chat": str(fakes.CHANNEL)}, home=home)
    assert store.read_sync_list() == [fakes.SUPER] and "lose" in out["note"]
    chats = {c["chat"]: c for c in tg.execute({"action": "chats"}, home=home)["chats"]}
    assert chats[str(fakes.SUPER)]["mirrored"] and chats[str(fakes.SUPER)]["on_sync_list"]


# --- the card and approval -----------------------------------------------------------------------

def test_card_for_a_reply(home):
    reason, key = tg.approval_request({"action": "send", "chat": str(fakes.ALICE), "text": " 了解です \n",
                                       "reply_to": "10"}, home=home)
    assert reason == ("Telegram: Rui (@rui)\nChat: Alice (@alice)\nReply to: Alice: 明日の打ち合わせは？\n\n了解です")
    assert key.startswith("telegram-access:send:")
    reason, _ = tg.approval_request({"action": "send", "chat": str(fakes.GROUP), "text": "x"}, home=home)
    assert "Chat: Family (group, id -4001)" in reason
    reason, _ = tg.approval_request({"action": "send", "chat": str(fakes.ME), "text": "note"}, home=home)
    assert "Chat: Saved Messages" in reason


def test_card_spells_out_hidden_characters_and_cuts_long_text(home):
    reason, _ = tg.approval_request({"action": "send", "chat": str(fakes.ALICE), "text": "a\u202eb"}, home=home)
    assert reason.endswith("a⟨U+202E⟩b")
    reason, _ = tg.approval_request({"action": "send", "chat": str(fakes.ALICE), "text": "あ" * 1000}, home=home)
    assert "more characters)" in reason and tg._units(reason) <= tg.CARD_LIMIT


def test_rule_key_binds_the_exact_message(home):
    one = tg.approval_request({"action": "send", "chat": str(fakes.ALICE), "text": "hi"}, home=home)[1]
    assert one == tg.approval_request({"action": "send", "chat": str(fakes.ALICE), "text": "hi "}, home=home)[1]
    assert one != tg.approval_request({"action": "send", "chat": str(fakes.ALICE), "text": "hi!"}, home=home)[1]
    assert one != tg.approval_request({"action": "send", "chat": str(fakes.GROUP), "text": "hi"}, home=home)[1]


@pytest.mark.parametrize("args, match", [
    ({"chat": str(fakes.HERMES_BOT), "text": "hi"}, "not available"),
    ({"chat": str(fakes.CHANNEL), "text": "hi"}, "cannot post"),
    ({"chat": "+819011111111", "text": "hi"}, "not a name"),
    ({"chat": str(fakes.ALICE), "text": "   "}, "nothing to send"),
    ({"chat": str(fakes.ALICE), "text": "x" * 4097}, "at most"),
    ({"chat": "777", "text": "hi"}, "not in the chat list"),
    ({"chat": str(fakes.ALICE), "text": "hi", "reply_to": "abc"}, "message id"),
    ({"chat": str(fakes.ALICE), "files": ["/etc/hosts"]}, "outside"),
])
def test_invalid_sends_are_refused_before_the_card(home, args, match):
    with pytest.raises(tg.TelegramError, match=match):
        tg.approval_request({"action": "send", **args}, home=home)


def test_files_on_the_card_and_their_checks(state, home):
    ws = tg.SEND_ROOT
    (ws / "trip").mkdir()
    (ws / "trip" / "photo.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 100)
    reason, _ = tg.approval_request({"action": "send", "chat": str(fakes.ALICE), "text": "旅行の写真",
                                     "files": ["trip/photo.png"]}, home=home)
    assert "Files: 1 (108 B)\n- photo.png (" in reason and ", 108 B) in trip, sha256 " in reason
    for name, body in ((".env", b"A=1"), ("run.sh", b"#!/bin/sh\n"), ("key.txt", b"-----BEGIN PRIVATE KEY-----"),
                       ("empty.txt", b""), ("mirror.db", b"x")):
        (ws / name).write_bytes(body)
        with pytest.raises(tg.TelegramError):
            tg.approval_request({"action": "send", "chat": str(fakes.ALICE), "files": [name]}, home=home)
    (ws / ".git").mkdir()
    (ws / ".git" / "notes.txt").write_text("x")
    with pytest.raises(tg.TelegramError, match="keys or settings"):
        tg.approval_request({"action": "send", "chat": str(fakes.ALICE), "files": [".git/notes.txt"]}, home=home)
    with pytest.raises(tg.TelegramError, match="caption"):
        tg.approval_request({"action": "send", "chat": str(fakes.ALICE), "text": "x" * 1025,
                             "files": ["trip/photo.png"]}, home=home)


# --- send ----------------------------------------------------------------------------------------

def test_send_needs_its_own_approval(home, agent):
    agent.handlers["send"] = lambda p: {"ids": [99], "ts": 1, "recorded": True}
    args = {"action": "send", "chat": str(fakes.ALICE), "text": "hi"}
    assert "did not pass the approval" in tg.execute(args, home=home, call_id="x")["error"]
    tg.approval_request(args, home=home, call_id="call-1")
    assert "did not pass the approval" in tg.execute(args, home=home, call_id="call-2")["error"]
    assert agent.requests == []


def test_send_success(home, agent):
    agent.handlers["send"] = lambda p: {"ids": [99], "ts": 1, "recorded": True}
    _, out = approve_and_send({"action": "send", "chat": str(fakes.ALICE), "text": " hi ", "reply_to": "10"}, home)
    assert out == {"ok": True, "chat": str(fakes.ALICE), "ids": ["99"],
                   "note": "accepted by Telegram; delivery and reading are not confirmed"}
    assert agent.requests[0]["params"] == {"chat": fakes.ALICE, "text": "hi", "reply_to": 10}
    # the approval is used up
    assert "did not pass the approval" in tg.execute({"action": "send", "chat": str(fakes.ALICE), "text": " hi ",
                                                      "reply_to": "10"}, home=home, call_id="call-1")["error"]


def test_send_outcomes(home, agent):
    args = {"action": "send", "chat": str(fakes.ALICE), "text": "hi"}

    def refuse(p):
        raise fakes.FakeError("not_sent", "UserIsBlockedError: blocked")
    agent.handlers["send"] = refuse
    assert approve_and_send(args, home)[1]["error"].startswith("not sent: UserIsBlockedError")

    def unsure(p):
        raise fakes.FakeError("uncertain", "TimeoutError", hint="ids [5]")
    agent.handlers["send"] = unsure
    error = approve_and_send(args, home, "call-2")[1]["error"]
    assert error.startswith("UNCERTAIN: TimeoutError; ids [5]") and "never resend" in error

    agent.handlers["send"] = lambda p: fakes.NO_REPLY
    tg.SEND_TIMEOUT_TEXT, saved = 1, tg.SEND_TIMEOUT_TEXT
    try:
        assert approve_and_send(args, home, "call-3")[1]["error"].startswith("UNCERTAIN")
    finally:
        tg.SEND_TIMEOUT_TEXT = saved

    agent.handlers["send"] = lambda p: {"ids": []}
    assert approve_and_send(args, home, "call-4")[1]["error"].startswith("UNCERTAIN")


def test_send_without_the_agent_is_not_sent(home):
    _, out = approve_and_send({"action": "send", "chat": str(fakes.ALICE), "text": "hi"}, home)
    assert out["error"].startswith("not sent:") and "not running" in out["error"]


def test_files_are_staged_and_must_match_the_card(state, home, agent):
    seen = {}

    def send(p):
        seen["files"] = [Path(f).read_bytes() for f in p["files"]]
        seen["paths"] = p["files"]
        return {"ids": [7], "ts": 1, "recorded": True}
    agent.handlers["send"] = send
    doc = tg.SEND_ROOT / "doc.txt"
    doc.write_text("version 1")
    args = {"action": "send", "chat": str(fakes.ALICE), "files": ["doc.txt"]}
    _, out = approve_and_send(args, home)
    assert out["ok"] and out["files"] == ["doc.txt"] and seen["files"] == [b"version 1"]
    outbox = store.outbox_dir(state)
    assert all(outbox in Path(p).parents for p in seen["paths"]) and not any(outbox.iterdir())
    tg.approval_request(args, home=home, call_id="call-2")
    doc.write_text("version 2")
    out = tg.execute(args, home=home, call_id="call-2")
    assert "changed after the approval card" in out["error"] and len(agent.requests) == 1


# --- media ---------------------------------------------------------------------------------------

def test_media_is_saved_into_the_download_folder(state, home, agent):
    def download(p):
        folder = store.incoming_dir(state) / ("f" * 32)
        folder.mkdir(parents=True)
        path = folder / "photo.jpg"
        path.write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 64)
        return {"path": str(path), "media": {"type": "photo"}}
    agent.handlers["download"] = download
    out = tg.execute({"action": "media", "chat": str(fakes.ALICE), "id": "12"}, home=home)
    saved = Path(out["files"][0]["path"])
    assert out["ok"] and saved.parent == state / "inbox" / f"{fakes.ALICE}-12" and saved.read_bytes()[:3] == b"\xff\xd8\xff"
    assert not any(store.incoming_dir(state).iterdir())
    assert agent.requests[0]["params"]["max_bytes"] == 100 * 1024 * 1024


def test_media_refusals(state, home, agent):
    conn = store.connect(store.db_path(state), write=True)
    store.upsert_message(conn, {"chat": fakes.ALICE, "id": 40, "ts": 1, "media": {"type": "document", "name": "tool.zip",
                                                                                  "mime": "application/zip"}})
    store.upsert_message(conn, {"chat": fakes.ALICE, "id": 41, "ts": 1, "media": {"type": "photo",
                                                                                  "self_destructing": True}})
    store.upsert_message(conn, {"chat": fakes.ALICE, "id": 42, "ts": 1, "body": "just text"})
    store.upsert_message(conn, {"chat": fakes.ALICE, "id": 43, "ts": 1, "media": {"type": "document", "name": "a.pdf"}})
    conn.close()
    out = tg.execute({"action": "media", "chat": str(fakes.ALICE), "id": "40"}, home=home)
    assert out["ok"] is False and out["refused"] and agent.requests == []
    with pytest.raises(tg.TelegramError, match="self-destructing"):
        tg.execute({"action": "media", "chat": str(fakes.ALICE), "id": "41"}, home=home)
    with pytest.raises(tg.TelegramError, match="no file"):
        tg.execute({"action": "media", "chat": str(fakes.ALICE), "id": "42"}, home=home)

    def disguised(p):
        folder = store.incoming_dir(state) / ("e" * 32)
        folder.mkdir(parents=True)
        path = folder / "a.pdf"
        path.write_bytes(b"#!/bin/sh\necho hi\n")
        return {"path": str(path), "media": {}}
    agent.handlers["download"] = disguised
    out = tg.execute({"action": "media", "chat": str(fakes.ALICE), "id": "43"}, home=home)
    assert out["ok"] is False and "really" in out["refused"][0] and not (state / "inbox").exists()

    agent.handlers["download"] = lambda p: {"path": "/etc/hosts"}
    with pytest.raises(tg.TelegramError, match="outside"):
        tg.execute({"action": "media", "chat": str(fakes.ALICE), "id": "43"}, home=home)

    agent.handlers["download"] = lambda p: {"too_large": True, "media": {"size": 300 * 1024 * 1024}}
    out = tg.execute({"action": "media", "chat": str(fakes.ALICE), "id": "43"}, home=home)
    assert out["ok"] is False and "300.0 MB" in out["error"]


def test_config_defaults(state):
    home = state / "bare"
    home.mkdir()
    assert tg.download_dir(home) == home / "telegram-downloads"
    assert tg.download_limit(home) == 100 * 1024 * 1024 and tg.excluded(home) == set()
    (home / "config.yaml").write_text("telegram_access:\n  download_max_mb: 9000\n  download_dir: ~/Inbox/t\n")
    assert tg.download_limit(home) == 500 * 1024 * 1024 and tg.download_dir(home) == Path.home() / "Inbox" / "t"


# --- guard ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("tool, args", [
    ("terminal", {"command": "sqlite3 ~/.local/state/hermes-telegram/mirror.db .dump"}),
    ("terminal", {"command": "secret get TELEGRAM_USER_SESSION -p hermes --scope telegram-access"}),
    ("terminal", {"command": "python -c 'import telethon'"}),
    ("terminal", {"command": "pip install pyrogram"}),
    ("terminal", {"command": "open https://my.telegram.org"}),
    ("terminal", {"command": "ls ~/Library/Group\\ Containers/6N38VWS5BX.ru.keepcoder.Telegram"}),
    ("terminal", {"command": "cat plugins/telegram-access/tg.py"}),
    ("terminal", {"command": "launchctl kickstart gui/501/local.telegram-access.sync"}),
    ("terminal", {"command": "ls", "workdir": "/Users/x/.local/state/hermes-telegram"}),
    ("read_file", {"path": "~/.local/state/hermes-telegram/telethon.session"}),
    ("read_file", {"path": "~/Library/LaunchAgents/local.telegram-access.sync.plist"}),
    ("read_file", {"path": "~/Library/Logs/telegram-access-sync.log"}),
    ("search_files", {"path": "~/.config/hermes/local/telegram-access/venv"}),
    ("search_files", {"path": "~/Library/Application Support/Telegram Desktop"}),
])
def test_bypass_is_blocked(tool, args):
    assert tg.bypass(tool, args) == tg.BYPASS_MESSAGE


@pytest.mark.parametrize("tool, args", [
    ("terminal", {"command": "ls ~/Workspaces/.inbox/telegram"}),
    ("terminal", {"command": "echo telegram is nice"}),
    ("read_file", {"path": "plugins/telegram-access/tg.py"}),
    ("read_file", {"path": "~/.config/hermes/launchd/telegram-access-launchctl.sh"}),
    ("read_file", {"path": "~/Workspaces/.inbox/telegram/2001-12/photo.jpg"}),
    ("web_search", {"query": "telethon"}),
])
def test_ordinary_calls_pass(tool, args):
    assert tg.bypass(tool, args) is None
