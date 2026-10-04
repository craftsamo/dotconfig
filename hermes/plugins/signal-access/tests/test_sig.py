import importlib.util
import json
import os
from pathlib import Path
import shutil
import struct
import zlib

import pytest

spec = importlib.util.spec_from_file_location("signal_access_fakes", Path(__file__).resolve().parent / "fakes.py")
fakes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fakes)

store = fakes.load("store")
sig = fakes.load("sig")
ME, ALICE, BOB, GROUP, GROUP_ID = fakes.ME, fakes.ALICE, fakes.BOB, fakes.GROUP, fakes.GROUP_ID


def _png() -> bytes:
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 0, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\x00\x00")) + chunk(b"IEND", b""))


PNG = _png()


@pytest.fixture
def env(monkeypatch):
    base = fakes.short_dir()
    state = base / "s"
    state.mkdir()
    workspace = base / "Workspaces"
    workspace.mkdir()
    monkeypatch.setenv(store.STATE_ENV, str(state))
    monkeypatch.setattr(sig, "SEND_ROOT", workspace)
    monkeypatch.setattr(sig, "_agent_running", lambda: True)
    fakes.link_account(state)
    conn = store.connect(store.db_path(state), write=True)
    store.set_meta(conn, uuid=ME, account=fakes.NUMBER, status="running")
    store.upsert_contacts(conn, [{"uuid": ALICE, "number": "+819011111111", "givenName": "Alice"}])
    store.upsert_groups(conn, [{"id": GROUP_ID, "name": "Family", "isMember": True}])
    for payload in (
        fakes.envelope(data={"timestamp": 1790000000000, "message": "hello there"}),
        fakes.envelope(data={"timestamp": 1790000001000, "message": "vanishing", "expiresInSeconds": 60}),
        fakes.envelope(ME, sync={"readMessages": [{"senderUuid": ALICE, "timestamp": 1790000001000}]}),
        fakes.envelope(BOB, name="Bob", number="+819033333333", data={"timestamp": 1790000002000, "message": "group news",
                                              "groupInfo": {"groupId": GROUP_ID, "type": "DELIVER"},
                                              "attachments": [{"contentType": "image/png", "filename": "pic.png",
                                                               "id": "pic.png", "size": len(PNG)}]}),
    ):
        store.ingest(conn, payload, me=ME, state=state)
    # The read sync came "now": move the timer start back so the message reads as expired.
    conn.execute("UPDATE messages SET expire_start = 1790000001000 WHERE ts = 1790000001000")
    conn.close()
    (state / "signal-cli" / "attachments").mkdir(parents=True)
    (state / "signal-cli" / "attachments" / "pic.png").write_bytes(PNG)
    sig._approved.clear()
    yield {"state": state, "workspace": workspace, "base": base}
    shutil.rmtree(base, ignore_errors=True)


@pytest.fixture
def daemon(env):
    handlers = {
        "send": lambda p: {"timestamp": 1790000009000, "results": [
            {"recipientAddress": {"uuid": ALICE, "number": "+819011111111"}, "type": "SUCCESS"}]},
        "getUserStatus": lambda p: [{"recipient": n, "number": n, "uuid": BOB.upper(), "isRegistered": True}
                                    for n in p["recipient"]],
    }
    d = fakes.FakeDaemon(store.socket_path(env["state"]), handlers)
    yield d
    d.close()


def approve_and_send(args):
    request = sig.approval_request(args)
    assert request is not None
    return request, sig.execute(args)


# --- reads --------------------------------------------------------------------------------------

def test_status(env):
    out = sig.status()
    assert out["linked"] is True and out["account"] == fakes.NUMBER and out["sync"] == "running"
    assert out["messages"] == 3 and "action_needed" not in out


def test_status_unlinked_and_not_set_up(env, monkeypatch):
    fakes.link_account(env["state"], registered=False)
    assert sig.status()["linked"] is False and "link" in sig.status()["action_needed"]
    shutil.rmtree(env["state"] / "signal-cli" / "data")
    assert sig.status() == {"ok": True, "linked": False, "action_needed": sig.NOT_SET_UP}
    with pytest.raises(sig.SignalError, match="not set up"):
        sig.execute({"action": "chats"})


def test_chats(env):
    out = sig.execute({"action": "chats", "last": True})
    chats = {c["chat"]: c for c in out["chats"]}
    assert out["complete"] is True and list(chats) == [GROUP, ALICE]
    assert chats[ALICE]["name"] == "Alice" and chats[ALICE]["number"] == "+819011111111"
    assert chats[ALICE]["unread"] == 1 and chats[GROUP]["name"] == "Family"
    assert chats[GROUP]["last"]["text"] == "group news"
    page = sig.execute({"action": "chats", "limit": 1})
    assert len(page["chats"]) == 1 and page["next_offset"] == 1
    assert [c["chat"] for c in sig.execute({"action": "chats", "query": "fam"})["chats"]] == [GROUP]
    assert [c["chat"] for c in sig.execute({"action": "chats", "unread": True})["chats"]] == [GROUP, ALICE]
    conn = store.connect(store.db_path(env["state"]), write=True)
    store.ingest(conn, fakes.envelope(ME, sync={"readMessages": [{"senderUuid": BOB, "timestamp": 1790000002000}]}),
                 me=ME)
    conn.close()
    assert [c["chat"] for c in sig.execute({"action": "chats", "unread": True})["chats"]] == [ALICE]


def test_messages_mark_expired_and_warn(env):
    out = sig.execute({"action": "messages", "chat": ALICE})
    assert [m["text"] for m in out["messages"]] == ["hello there", "vanishing"]
    assert "expired" in out["messages"][1] and out["messages"][1]["from"] == "Alice"
    assert out["expired_note"] == sig.EXPIRED_NOTE and out["note"] == sig.UNTRUSTED
    assert "expired_note" not in sig.execute({"action": "messages", "chat": GROUP})


def test_messages_bounds_and_bad_chats(env):
    out = sig.execute({"action": "messages", "chat": ALICE, "after": "2026-09-21T14:13:20+00:00"})
    assert [m["text"] for m in out["messages"]] == ["vanishing"]
    for chat in ("Alice", "+819011111111", "group:short"):
        with pytest.raises(sig.SignalError, match="chat id"):
            sig.execute({"action": "messages", "chat": chat})


def test_search_context_contacts(env):
    found = sig.execute({"action": "search", "query": "news"})["messages"]
    assert [(m["chat"], m["chat_name"], m["from"]) for m in found] == [(GROUP, "Family", "Bob")]
    assert found[0]["files"] == [{"name": "pic.png", "type": "image/png", "size": len(PNG)}]
    assert sig.execute({"action": "search", "query": "pic.png"})["messages"][0]["id"] == "1790000002000"
    assert sig.execute({"action": "search", "query": "100%"})["messages"] == []
    ctx = sig.execute({"action": "context", "chat": ALICE, "id": "1790000001000", "before_count": 1})
    assert [m["id"] for m in ctx["messages"]] == ["1790000000000", "1790000001000"]
    contacts = sig.execute({"action": "contacts", "query": "ali"})["contacts"]
    assert contacts == [{"chat": ALICE, "name": "Alice", "number": "+819011111111"}]


def test_media_copies_files_and_refuses_programs(env, tmp_path, monkeypatch):
    monkeypatch.setattr(sig, "download_dir", lambda home: env["base"] / "downloads")
    out = sig.execute({"action": "media", "chat": GROUP, "id": "1790000002000"})
    assert out["ok"] is True and Path(out["files"][0]["path"]).read_bytes() == PNG
    conn = store.connect(store.db_path(env["state"]), write=True)
    store.ingest(conn, fakes.envelope(data={"timestamp": 1790000003000, "attachments": [
        {"contentType": "application/zip", "filename": "invoice.zip", "id": "z.zip"},
        {"contentType": "image/jpeg", "filename": "gone.jpg", "id": "gone.jpg"}]}), me=ME)
    conn.close()
    out = sig.execute({"action": "media", "chat": ALICE, "id": "1790000003000"})
    assert out["ok"] is False and out["refused"] and out["missing"] == ["gone.jpg"]


def test_check_learns_numbers(env, daemon):
    out = sig.execute({"action": "check", "numbers": ["+81 90-2222-2222"]})
    assert out["numbers"] == [{"number": "+819022222222", "on_signal": True, "chat": BOB}]
    conn = store.connect(store.db_path(env["state"]))
    assert conn.execute("SELECT number FROM contacts WHERE uuid = ?", (BOB,)).fetchone()[0] == "+819022222222"
    with pytest.raises(sig.SignalError, match="country code"):
        sig.execute({"action": "check", "numbers": ["090-1234-5678"]})


def test_check_without_sync(env):
    with pytest.raises(sig.SignalError, match="not running"):
        sig.execute({"action": "check", "numbers": ["+819022222222"]})


# --- sends --------------------------------------------------------------------------------------

def test_text_send_card_and_record(env, daemon):
    args = {"action": "send", "chat": ALICE, "text": "  see you\n", "reply_to": "1790000000000"}
    (card, key), out = approve_and_send(args)
    assert card == (f"Account: {fakes.NUMBER}\nChat: Alice (+819011111111)\nReply to: Alice: hello there\n\nsee you")
    assert key.startswith("signal-access:send:")
    assert out["ok"] is True and out["id"] == "1790000009000"
    sent = daemon.requests[-1]["params"]
    assert sent == {"recipient": [ALICE], "message": "see you", "quoteTimestamp": 1790000000000,
                    "quoteAuthor": ALICE, "quoteMessage": "hello there"}
    last = sig.execute({"action": "messages", "chat": ALICE})["messages"][-1]
    assert last["from"] == "me" and last["text"] == "see you" and last["reply_to"] == "1790000000000"


def test_send_needs_the_gate_first(env, daemon):
    out = sig.execute({"action": "send", "chat": ALICE, "text": "hi"})
    assert out["ok"] is False and "approval" in out["error"] and daemon.requests == []
    args = {"action": "send", "chat": ALICE, "text": "hi"}
    sig.approval_request(args)
    assert sig.execute(args)["ok"] is True
    assert sig.execute(args)["ok"] is False  # one approval, one send


def test_group_send_and_note_to_self(env, daemon):
    (card, _), out = approve_and_send({"action": "send", "chat": GROUP, "text": "hi all"})
    assert "Chat: Family (group AbCdEfGhIjKl…)" in card and out["ok"] is True
    assert daemon.requests[-1]["params"]["groupId"] == GROUP_ID
    (card, _), _ = approve_and_send({"action": "send", "chat": ME, "text": "memo"})
    assert "Chat: Note to Self" in card


@pytest.mark.parametrize("args, message", [
    ({"action": "send", "chat": ALICE}, "nothing to send"),
    ({"action": "send", "chat": "Alice", "text": "x"}, "chat id"),
    ({"action": "send", "chat": "group:" + "Z" * 43 + "=", "text": "x"}, "not in the mirror"),
    ({"action": "send", "chat": ALICE, "text": "x", "reply_to": "1790000002000"}, "reply_to"),
    ({"action": "send", "chat": ALICE, "text": "x" * 4001}, "at most"),
])
def test_invalid_sends_raise_before_asking(env, args, message):
    with pytest.raises(sig.SignalError, match=message):
        sig.approval_request(args)


def test_unknown_person_from_check_is_sendable(env, daemon):
    sig.execute({"action": "check", "numbers": ["+819022222222"]})
    (card, _), out = approve_and_send({"action": "send", "chat": BOB, "text": "first hello"})
    assert "Chat: Bob (+819022222222)" in card and out["ok"] is True


def test_long_text_is_cut_on_the_card(env):
    card, _ = sig.approval_request({"action": "send", "chat": ALICE, "text": "あ" * 1000})
    assert card.endswith("more characters)") and sig._units(card) <= sig.CARD_LIMIT


def test_suspicious_characters_are_spelled_out(env):
    card, _ = sig.approval_request({"action": "send", "chat": ALICE, "text": "pay\u202eyou"})
    assert "⟨U+202E⟩" in card


# --- outcomes -----------------------------------------------------------------------------------

def outcome(env, handler):
    d = fakes.FakeDaemon(store.socket_path(env["state"]), {"send": handler})
    try:
        args = {"action": "send", "chat": ALICE, "text": "x"}
        sig.approval_request(args)
        return sig.execute(args)
    finally:
        d.close()


def test_failures_before_dispatch_read_not_sent(env):
    def identity(p):
        raise fakes.FakeError(-4, "Untrusted identity", {"response": {"timestamp": 1, "results": [
            {"recipientAddress": {"uuid": ALICE}, "type": "IDENTITY_FAILURE"}]}})
    assert outcome(env, identity)["error"].startswith("not sent: their safety number changed")

    def invalid(p):
        raise fakes.FakeError(-32602, "Invalid params")
    assert outcome(env, invalid)["error"].startswith("not sent")


def test_unclear_failures_are_uncertain(env, monkeypatch):
    def network(p):
        raise fakes.FakeError(-1, "Failed to send message", {"response": {"timestamp": 1, "results": [
            {"recipientAddress": {"uuid": ALICE}, "type": "NETWORK_FAILURE"}]}})
    assert outcome(env, network)["error"].startswith("UNCERTAIN")
    assert "phone" in outcome(env, network)["error"]
    monkeypatch.setattr(sig, "SEND_TIMEOUT", 0.5)
    assert outcome(env, lambda p: fakes.NO_REPLY)["error"].startswith("UNCERTAIN")
    assert outcome(env, lambda p: {"results": []})["error"].startswith("UNCERTAIN")


def test_no_daemon_is_not_sent(env):
    args = {"action": "send", "chat": ALICE, "text": "x"}
    sig.approval_request(args)
    assert sig.execute(args)["error"].startswith("not sent: the Signal sync service is not running")


def test_partial_group_delivery(env):
    out = outcome(env, lambda p: {"timestamp": 5, "results": [
        {"recipientAddress": {"uuid": ALICE}, "type": "SUCCESS"},
        {"recipientAddress": {"uuid": BOB, "number": "+8190"}, "type": "UNREGISTERED_FAILURE"}]})
    assert out["ok"] is True and out["not_delivered_to"] == [{"member": "+8190", "reason": "UNREGISTERED_FAILURE"}]


# --- files --------------------------------------------------------------------------------------

def put(env, relative, data=PNG):
    path = env["workspace"] / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def test_file_send_card_staging_and_cleanup(env, daemon):
    put(env, "Personal/trip/photo.png")
    args = {"action": "send", "chat": ALICE, "text": "photo", "files": ["Personal/trip/photo.png"]}
    (card, key), out = approve_and_send(args)
    digest = sig._sha256(env["workspace"] / "Personal/trip/photo.png")
    assert f"- photo.png (image/png, {len(PNG)} B) in Personal/trip, sha256 {digest[:12]}" in card
    assert "Files: 1" in card and out["ok"] is True and out["files"] == ["photo.png"]
    staged = daemon.requests[-1]["params"]["attachment"]
    assert len(staged) == 1 and "/outbox/" in staged[0] and not Path(staged[0]).exists()
    assert list((env["state"] / "outbox").iterdir()) == []


def test_changed_file_after_approval_is_not_sent(env, daemon):
    path = put(env, "a.png")
    args = {"action": "send", "chat": ALICE, "files": [str(path)]}
    sig.approval_request(args)
    path.write_bytes(PNG + b"changed")
    out = sig.execute(args)
    assert out["ok"] is False and "changed" in out["error"] and daemon.requests == []


def test_concurrent_identical_calls_keep_their_own_approval(env, daemon):
    path = put(env, "a.png")
    args = {"action": "send", "chat": ALICE, "files": ["a.png"]}
    sig.approval_request(args, call_id="call-A")          # card A shows the original
    path.write_bytes(PNG + b"v2")
    sig.approval_request(args, call_id="call-B")          # card B (say, denied) shows v2
    out = sig.execute(args, call_id="call-A")             # A was approved: v2 must not go out
    assert out["ok"] is False and "changed" in out["error"] and daemon.requests == []
    assert sig.execute(args, call_id="call-C")["error"].startswith("not sent: this send did not pass")


def test_quote_changed_after_the_card_is_not_sent(env, daemon):
    args = {"action": "send", "chat": ALICE, "text": "yes", "reply_to": "1790000000000"}
    sig.approval_request(args)
    conn = store.connect(store.db_path(env["state"]), write=True)
    store.ingest(conn, fakes.envelope(edit={"targetSentTimestamp": 1790000000000,
                                            "dataMessage": {"timestamp": 1790000005000, "message": "pay me"}}), me=ME)
    conn.close()
    out = sig.execute(args)
    assert out["ok"] is False and "quoted message changed" in out["error"] and daemon.requests == []


def test_rule_key_binds_file_content(env):
    path = put(env, "a.png")
    args = {"action": "send", "chat": ALICE, "files": ["a.png"]}
    _, first = sig.approval_request(args)
    path.write_bytes(PNG + b"v2")
    _, second = sig.approval_request(args)
    assert first != second


def test_files_outside_the_workspace_are_refused(env):
    outside = env["base"] / "secret.png"
    outside.write_bytes(PNG)
    os.symlink(outside, env["workspace"] / "link.png")
    for given in (str(outside), "link.png", "../secret.png"):
        with pytest.raises(sig.SignalError, match="outside"):
            sig.approval_request({"action": "send", "chat": ALICE, "files": [given]})


@pytest.mark.parametrize("relative, data, message", [
    (".ssh/notes.png", PNG, "keys or settings"),
    ("proj/.env", b"A=1", "keys or settings"),
    ("proj/server.pem", b"x", "keys or settings"),
    ("proj/tool.sh", b"#!/bin/sh\necho hi\n", "archive or program"),
    ("proj/photo.jpg", b"PK\x03\x04" + b"\x00" * 64, "archive or program"),
    ("proj/notes.txt", b"-----BEGIN OPENSSH PRIVATE KEY-----\nabc", "private key"),
    ("proj/late.txt", b"a" * 200000 + b"-----BEGIN RSA PRIVATE KEY-----\nabc", "private key"),
    ("proj/.envrc", b"export A=1", "keys or settings"),
    ("proj/credentials-backup.json", b"{}", "keys or settings"),
    ("proj/secrets_backup.txt", b"x", "keys or settings"),
    ("proj/tool.py", b"print('hi')\n", "archive or program"),
    ("proj/run.rb", b"puts 1\n", "archive or program"),
    ("proj/empty.png", b"", "empty"),
])
def test_dangerous_files_are_refused(env, relative, data, message):
    put(env, relative, data)
    with pytest.raises(sig.SignalError, match=message):
        sig.approval_request({"action": "send", "chat": ALICE, "files": [relative]})


def test_file_limits(env, monkeypatch):
    names = [f"f{i}.png" for i in range(11)]
    for name in names:
        put(env, name)
    with pytest.raises(sig.SignalError, match="at most 10"):
        sig.approval_request({"action": "send", "chat": ALICE, "files": names})
    monkeypatch.setattr(sig, "FILES_BYTES_MAX", len(PNG) + 1)
    with pytest.raises(sig.SignalError, match="per send"):
        sig.approval_request({"action": "send", "chat": ALICE, "files": names[:2]})
    with pytest.raises(sig.SignalError, match="twice"):
        sig.approval_request({"action": "send", "chat": ALICE, "files": ["f0.png", "./f0.png"]})


def test_too_many_files_for_one_card(env):
    names = [f"a-rather-long-file-name-number-{i}.png" for i in range(9)]
    for name in names:
        put(env, f"some/deeper/folder/{name}")
    with pytest.raises(sig.SignalError, match="fewer files"):
        sig.approval_request({"action": "send", "chat": ALICE, "files": [f"some/deeper/folder/{n}" for n in names]})


# --- guard --------------------------------------------------------------------------------------

@pytest.mark.parametrize("tool, args", [
    ("terminal", {"command": "signal-cli -a +81 send -m hi"}),
    ("terminal", {"command": "/opt/homebrew/bin/signal-cli listContacts"}),
    ("terminal", {"command": "sqlite3 ~/.local/state/hermes-signal/mirror.db"}),
    ("terminal", {"command": "python -c 'import sys; sys.path.append(\"plugins/signal-access\")'"}),
    ("terminal", {"command": "ls", "workdir": "/Users/x/.local/state/hermes-signal"}),
    ("terminal", {"command": "cp ~/Library/Application Support/Signal/sql/db.sqlite ."}),
    ("terminal", {"command": "cp ~/Library/Application\\ Support/Signal/config.json ."}),
    ("read_file", {"path": "~/.local/state/hermes-signal/signal-cli/data/123"}),
    ("search_files", {"path": "/Users/x/Library/Application Support/Signal"}),
    ("read_file", {"path": "~/Library/LaunchAgents/local.hermes.signal-access.sync.plist"}),
    ("read_file", {"path": "~/Library/Logs/signal-access-sync.log"}),
    ("read_file", {"path": "~/Library/Logs/signal-sync.log"}),
])
def test_bypass_is_blocked(tool, args):
    assert sig.bypass(tool, args) == sig.BYPASS_MESSAGE


@pytest.mark.parametrize("tool, args", [
    ("terminal", {"command": "ls ~/Workspaces"}),
    ("terminal", {"command": "echo signal processing"}),
    ("read_file", {"path": "plugins/signal-access/sig.py"}),
])
def test_ordinary_calls_pass(tool, args):
    assert sig.bypass(tool, args) is None
