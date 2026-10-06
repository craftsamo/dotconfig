import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import struct
import tarfile
import zipfile
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


def _ingest(env, *payloads):
    conn = store.connect(store.db_path(env["state"]), write=True)
    for payload in payloads:
        store.ingest(conn, payload, me=ME, state=env["state"])
    conn.close()


def test_mentions_read_as_names(env, daemon):
    group = {"groupId": GROUP_ID, "type": "DELIVER"}
    _ingest(env,
            fakes.envelope(BOB, name="Bob", number="+819033333333", data={
                "timestamp": 1790000004000, "message": "\ufffc and \ufffc, see this", "groupInfo": group,
                "mentions": [{"uuid": ALICE, "start": 0, "length": 1}, {"uuid": ME, "start": 6, "length": 1}]}),
            fakes.envelope(BOB, name="Bob", number="+819033333333", edit={
                "targetSentTimestamp": 1790000004000, "dataMessage": {
                    "timestamp": 1790000005000, "message": "\ufffc see this", "groupInfo": group,
                    "mentions": [{"uuid": "33333333-3333-4333-8333-333333333333", "number": "+819044444444",
                                  "start": 0, "length": 1}]}}),
            fakes.envelope(data={"timestamp": 1790000006000, "message": "ok", "groupInfo": group,
                                 "quote": {"id": 1790000004000, "authorUuid": BOB, "text": "\ufffc and \ufffc",
                                           "mentions": [{"uuid": ALICE, "start": 0, "length": 1},
                                                        {"uuid": ME, "start": 6, "length": 1}]}}))
    out = sig.execute({"action": "messages", "chat": GROUP, "after": "2026-09-21T14:13:23+00:00"})
    edited, reply = out["messages"]
    assert edited["text"] == "@+819044444444 see this"
    assert edited["earlier_versions"] == ["@Alice and @me, see this"]
    assert reply["reply_to_text"] == "@Alice and @me"
    assert "mention_note" not in out
    card, _ = sig.approval_request({"action": "send", "chat": GROUP, "text": "yes", "reply_to": "1790000006000"})
    assert "Reply to: Alice: ok" in card
    (card, _), sent = approve_and_send({"action": "send", "chat": GROUP, "text": "yes", "reply_to": "1790000004000"})
    assert "Reply to: Bob: @+819044444444 see this" in card and sent["ok"] is True
    mine = sig.execute({"action": "messages", "chat": GROUP})["messages"][-1]
    assert mine["from"] == "me" and mine["reply_to_text"] == "@+819044444444 see this"


def test_mentions_stored_before_they_were_kept(env):
    _ingest(env, fakes.envelope(data={"timestamp": 1790000004000, "message": "hi \ufffc"}))
    conn = store.connect(store.db_path(env["state"]), write=True)
    conn.execute("UPDATE messages SET mentions = NULL")
    conn.close()
    out = sig.execute({"action": "messages", "chat": ALICE})
    assert out["messages"][-1]["text"] == "hi " + sig.UNRECORDED_MENTION
    assert out["mention_note"] == sig.MENTION_NOTE


def test_media_copies_files_and_refuses_programs(env, tmp_path, monkeypatch):
    monkeypatch.setattr(sig, "download_dir", lambda home: env["base"] / "downloads")
    out = sig.execute({"action": "media", "chat": GROUP, "id": "1790000002000"})
    assert out["ok"] is True and Path(out["files"][0]["path"]).read_bytes() == PNG
    conn = store.connect(store.db_path(env["state"]), write=True)
    store.ingest(conn, fakes.envelope(data={"timestamp": 1790000003000, "attachments": [
        {"contentType": "application/x-msdownload", "filename": "invoice.exe", "id": "z.exe"},
        {"contentType": "image/jpeg", "filename": "gone.jpg", "id": "gone.jpg"}]}), me=ME)
    conn.close()
    out = sig.execute({"action": "media", "chat": ALICE, "id": "1790000003000"})
    assert out["ok"] is False and out["refused"] and out["missing"] == ["gone.jpg"]


def _received(env, monkeypatch, attachments, files, **extra):
    """A message with attachments, whose files signal-cli 'downloaded' into its store."""
    monkeypatch.setattr(sig, "download_dir", lambda home: env["base"] / "downloads")
    folder = env["state"] / "signal-cli" / "attachments"
    for file_id, data in files.items():
        (folder / file_id).write_bytes(data)
    conn = store.connect(store.db_path(env["state"]), write=True)
    store.ingest(conn, fakes.envelope(data={"timestamp": 1790000030000, "attachments": attachments}), me=ME)
    conn.close()
    return sig.execute({"action": "media", "chat": ALICE, "id": "1790000030000", **extra})


def _zip_bytes(entries):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in entries.items():
            z.writestr(name, data)
    return buffer.getvalue()


def test_media_saves_an_inspected_archive_and_lists_what_is_inside(env, monkeypatch):
    data = _zip_bytes({"notes.txt": b"hello", ".env": b"A=1", "run.sh": b"#!/bin/sh\necho hi\n"})
    out = _received(env, monkeypatch, [{"contentType": "application/zip", "filename": "photos.zip", "id": "p.zip"}],
                    {"p.zip": data})
    assert out["ok"] is True and "refused" not in out
    saved = out["files"][0]
    assert Path(saved["path"]).read_bytes() == data and saved["archive"]["entries"] == 3
    assert sorted(saved["archive"]["names"]) == [".env", "notes.txt", "run.sh"] and saved["archive"]["more"] == 0
    assert out["archive_note"] == sig.ARCHIVE_NOTE and "unpack" in out["note"]


PHOTOS = [{"contentType": "application/zip", "filename": "photos.zip", "id": "p.zip"}]
PACK = {"notes.txt": b"hello", "data/q1.csv": b"a,b\n1,2\n", "run.sh": b"#!/bin/sh\necho hi\n"}


def test_media_unpacks_an_inspected_archive_only_when_asked(env, monkeypatch):
    out = _received(env, monkeypatch, PHOTOS, {"p.zip": _zip_bytes(PACK)}, unpack=True)
    saved = out["files"][0]
    folder = Path(saved["unpacked"]["folder"])
    assert folder == Path(saved["path"]).parent / "photos.unpacked" and saved["unpacked"]["count"] == 3
    assert (folder / "data" / "q1.csv").read_bytes() == b"a,b\n1,2\n"
    assert not any(p.stat().st_mode & 0o111 for p in folder.rglob("*") if p.is_file())
    assert out["unpacked_note"] == sig.UNPACKED_NOTE and Path(saved["path"]).exists()


def test_media_does_not_unpack_by_itself(env, monkeypatch):
    out = _received(env, monkeypatch, PHOTOS, {"p.zip": _zip_bytes(PACK)})
    assert "unpacked" not in out["files"][0] and "unpacked_note" not in out
    assert not list((env["base"] / "downloads").rglob("*.unpacked"))


def test_media_unpacks_only_the_named_entries(env, monkeypatch):
    out = _received(env, monkeypatch, PHOTOS, {"p.zip": _zip_bytes(PACK)}, unpack=True, entries=["data"])
    unpacked = out["files"][0]["unpacked"]
    assert unpacked["files"] == ["data/q1.csv"] and not (Path(unpacked["folder"]) / "notes.txt").exists()


@pytest.mark.parametrize("entries", [["missing.txt"], [], [1], "notes.txt\n\n"])
def test_a_bad_entries_list_leaves_the_archive_saved_and_says_why(env, monkeypatch, entries):
    out = _received(env, monkeypatch, PHOTOS, {"p.zip": _zip_bytes(PACK)}, unpack=True, entries=entries)
    saved = out["files"][0]
    if entries == "notes.txt\n\n":                      # a single name is accepted, after trimming
        assert saved["unpacked"]["files"] == ["notes.txt"]
        return
    assert out["ok"] is True and Path(saved["path"]).exists() and "unpacked" not in saved
    assert "stays saved" in saved["unpack_error"] or "entries must be" in saved["unpack_error"]
    assert not list((env["base"] / "downloads").rglob("*.unpacked"))


@pytest.mark.parametrize("entries, fragment", [
    ({"a.txt": b"x", "setup.exe": b"x"}, "an archive or a program"),
    ({"a.txt": b"x", "inner.zip": b"x"}, "an archive or a program"),
    ({"a.txt": b"x", "../evil.txt": b"x"}, "not a plain relative path"),
])
def test_media_refuses_an_archive_that_fails_the_inspection_and_keeps_nothing(env, monkeypatch, entries, fragment):
    out = _received(env, monkeypatch, [{"contentType": "application/zip", "filename": "bad.zip", "id": "b.zip"}],
                    {"b.zip": _zip_bytes(entries)})
    assert out["ok"] is False and fragment in out["refused"][0] and "archive_note" not in out
    assert not list((env["base"] / "downloads").rglob("*.zip"))


def test_media_refuses_an_archive_that_does_not_say_so_and_other_formats(env, monkeypatch):
    zipped = _zip_bytes({"a.txt": b"x"})
    out = _received(env, monkeypatch, [
        {"contentType": "image/jpeg", "filename": "photo.jpg", "id": "j.jpg"},        # a ZIP called a photo
        {"contentType": "application/x-rar", "filename": "docs.rar", "id": "d.rar"},
        {"contentType": "application/zip", "filename": "fake.zip", "id": "f.zip"}],   # not a ZIP at all
        {"j.jpg": zipped, "d.rar": b"Rar!\x1a\x07\x00" + b"\x00" * 30, "f.zip": b"not an archive"})
    assert out["ok"] is False and len(out["refused"]) == 3
    assert "really application/zip" in out["refused"][0] and "not a zip archive" in out["refused"][2]
    assert not [p for p in (env["base"] / "downloads").rglob("*") if p.is_file()]


@pytest.mark.skipif(sys.platform != "darwin", reason="the quarantine flag is macOS's")
def test_media_marks_what_it_saves_as_downloaded(env, monkeypatch):
    out = _received(env, monkeypatch, [{"contentType": "image/png", "filename": "pic.png", "id": "pic2.png"}],
                    {"pic2.png": PNG})
    flag = subprocess.run(["/usr/bin/xattr", "-p", "com.apple.quarantine", out["files"][0]["path"]],
                          capture_output=True, text=True).stdout
    assert flag.startswith("0081;")


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


def make_zip(env, relative, entries):
    path = env["workspace"] / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in entries.items():
            z.writestr(name, data)
    return path


def test_zip_is_inspected_shown_on_the_card_and_sent(env, daemon):
    make_zip(env, "Personal/trip/photos.zip", {"a.png": PNG, "notes/b.txt": b"hello"})
    args = {"action": "send", "chat": ALICE, "files": ["Personal/trip/photos.zip"]}
    (card, key), out = approve_and_send(args)
    assert "- photos.zip (application/zip, " in card and ", 2 files inside (" in card and "unpacked)" in card
    assert out["ok"] is True and out["files"] == ["photos.zip"]
    staged = daemon.requests[-1]["params"]["attachment"]
    assert len(staged) == 1 and staged[0].endswith("-photos.zip")


def test_tar_gz_is_sent(env, daemon):
    path = env["workspace"] / "backup.tar.gz"
    with tarfile.open(path, "w:gz") as t:
        info = tarfile.TarInfo("a.png")
        info.size = len(PNG)
        t.addfile(info, io.BytesIO(PNG))
    (card, _), out = approve_and_send({"action": "send", "chat": ALICE, "files": ["backup.tar.gz"]})
    assert "backup.tar.gz (application/gzip" in card and ", 1 files inside (" in card and out["ok"] is True


@pytest.mark.parametrize("entries, message", [
    ({"a.png": PNG, ".env": b"A=1"}, "named like a key or secret"),
    ({"a.png": PNG, "proj/.ssh/id": b"x"}, "keys or settings"),
    ({"a.png": PNG, "setup.exe": b"x"}, "an archive or a program"),
    ({"a.png": PNG, "inner.zip": b"x"}, "an archive or a program"),
    ({"a.png": PNG, "../evil.txt": b"x"}, "not a plain relative path"),
    ({"a.png": PNG, "n.txt": b"-----BEGIN RSA PRIVATE KEY-----\nabc"}, "contains a private key"),
])
def test_zip_with_something_that_would_be_refused_alone_is_refused(env, daemon, entries, message):
    make_zip(env, "bad.zip", entries)
    with pytest.raises(sig.SignalError, match=f"archive 'bad.zip' is not sent: .*{message}"):
        sig.approval_request({"action": "send", "chat": ALICE, "files": ["bad.zip"]})
    assert daemon.requests == []


def test_scripts_are_sent_alone_and_inside_an_archive(env, daemon):
    make_zip(env, "proj.zip", {"a.png": PNG, "run.sh": b"echo hi\n", "src/tool.py": b"print(1)\n"})
    (card, _), out = approve_and_send({"action": "send", "chat": ALICE, "files": ["proj.zip"]})
    assert ", 3 files inside (" in card and out["ok"] is True
    for name, body in (("run.sh", b"#!/bin/sh\necho hi\n"), ("tool.py", b"print('hi')\n"), ("app.js", b"let a = 1;\n"),
                       ("job.rb", b"puts 1\n"), ("notes.txt", b"#!/bin/sh\necho hi\n")):
        put(env, name, body)
        (card, _), out = approve_and_send({"action": "send", "chat": ALICE, "files": [name]})
        assert f"- {name} (" in card and out["ok"] is True, name


@pytest.mark.parametrize("name, data", [
    ("tool.jar", b"PK\x03\x04" + b"\x00" * 64),
    ("app.apk", b"PK\x03\x04" + b"\x00" * 64),
    ("data.rar", b"Rar!\x1a\x07\x00" + b"\x00" * 64),
    ("data.7z", b"7z\xbc\xaf\x27\x1c" + b"\x00" * 64),
    ("data.gz", b"\x1f\x8b\x08\x00" + b"\x00" * 64),
    ("photo.jpg", b"PK\x03\x04" + b"\x00" * 64),
    ("really.zip", b"not an archive at all"),
])
def test_archives_the_inspection_does_not_cover_stay_refused(env, name, data):
    put(env, name, data)
    with pytest.raises(sig.SignalError, match="archive"):
        sig.approval_request({"action": "send", "chat": ALICE, "files": [name]})


def test_zip_changed_after_the_card_is_not_sent(env, daemon):
    path = make_zip(env, "a.zip", {"a.png": PNG})
    args = {"action": "send", "chat": ALICE, "files": ["a.zip"]}
    sig.approval_request(args)
    make_zip(env, "a.zip", {"a.png": PNG, "b.png": PNG})
    out = sig.execute(args)
    assert out["ok"] is False and "changed" in out["error"] and daemon.requests == []
    assert path.exists()


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
    ("proj/run.sh", b"\x00\x01\x02\x03binary" * 20, "archive or program"),   # not a script, whatever the name
    ("proj/photo.jpg", b"PK\x03\x04" + b"\x00" * 64, "archive or program"),
    ("proj/notes.txt", b"-----BEGIN OPENSSH PRIVATE KEY-----\nabc", "private key"),
    ("proj/late.txt", b"a" * 200000 + b"-----BEGIN RSA PRIVATE KEY-----\nabc", "private key"),
    ("proj/.envrc", b"export A=1", "keys or settings"),
    ("proj/credentials-backup.json", b"{}", "keys or settings"),
    ("proj/secrets_backup.txt", b"x", "keys or settings"),
    ("proj/tool.command", b"#!/bin/sh\necho hi\n", "archive or program"),
    ("proj/Tool.app", b"x", "archive or program"),
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
    ("terminal", {"command": "python -c 'import sys; sys.path.append(\"plugins/messaging/signal-access\")'"}),
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
    ("read_file", {"path": "plugins/messaging/signal-access/sig.py"}),
])
def test_ordinary_calls_pass(tool, args):
    assert sig.bypass(tool, args) is None
