import importlib.util
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
spec = importlib.util.spec_from_file_location("signal_access_fakes", Path(__file__).resolve().parent / "fakes.py")
fakes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fakes)
sys.path.pop(0)

store = fakes.load("store")
ME, ALICE, BOB, GROUP, GROUP_ID = fakes.ME, fakes.ALICE, fakes.BOB, fakes.GROUP, fakes.GROUP_ID


@pytest.fixture
def state(tmp_path, monkeypatch):
    monkeypatch.setenv(store.STATE_ENV, str(tmp_path))
    fakes.link_account(tmp_path)
    return tmp_path


@pytest.fixture
def conn(state):
    c = store.connect(store.db_path(state), write=True)
    yield c
    c.close()


def ingest(conn, payload, state=None):
    return store.ingest(conn, payload, me=ME, state=state)


def rows(conn, sql="SELECT * FROM messages ORDER BY ts", *params):
    return [dict(r) for r in conn.execute(sql, params)]


def test_linked_account_reads_signal_cli_files(state):
    assert store.linked_account(state) == {"number": fakes.NUMBER, "uuid": ME, "path": "123", "registered": True}
    fakes.link_account(state, registered=False)
    assert store.linked_account(state)["registered"] is False


def test_no_account_and_reader_without_mirror(tmp_path):
    assert store.linked_account(tmp_path) is None
    with pytest.raises(store.StoreError):
        store.connect(tmp_path / "mirror.db")


def test_incoming_direct_and_group_messages(conn):
    assert ingest(conn, fakes.envelope(data={"timestamp": 1, "message": "hello"})) == ["message"]
    ingest(conn, fakes.envelope(BOB, name="Bob", data={
        "timestamp": 2, "message": "group hi", "groupInfo": {"groupId": GROUP_ID, "type": "DELIVER"},
        "attachments": [{"contentType": "image/jpeg", "filename": "a.jpg", "id": "x1.jpg", "size": 9}],
        "quote": {"id": 1, "authorUuid": ALICE, "text": "hello"}}))
    found = rows(conn)
    assert [(m["chat"], m["author"], m["body"]) for m in found] == [(ALICE, ALICE, "hello"), (GROUP, BOB, "group hi")]
    assert json.loads(found[1]["attachments"]) == [{"id": "x1.jpg", "type": "image/jpeg", "name": "a.jpg", "size": 9}]
    assert json.loads(found[1]["quote"]) == {"id": 1, "author": ALICE, "text": "hello"}
    chats = {r["id"]: r for r in rows(conn, "SELECT * FROM chats")}
    assert chats[ALICE]["kind"] == "person" and chats[GROUP]["kind"] == "group"
    assert rows(conn, "SELECT profile_name FROM contacts WHERE uuid = ?", BOB) == [{"profile_name": "Bob"}]


def test_mentions_are_kept_beside_the_text(conn):
    ingest(conn, fakes.envelope(data={"timestamp": 3, "message": "hi \ufffc and \ufffc", "mentions": [
        {"name": "+8190", "number": "+8190", "uuid": ME.upper(), "start": 9, "length": 1},
        {"number": None, "uuid": BOB, "start": 3, "length": 1}, "junk"],
        "quote": {"id": 1, "authorUuid": BOB, "text": "\ufffc?", "mentions": [{"uuid": ALICE, "start": 0, "length": 1}]}}))
    m = rows(conn)[0]
    assert json.loads(m["mentions"]) == [{"start": 3, "uuid": BOB}, {"start": 9, "uuid": ME, "number": "+8190"}]
    assert json.loads(m["quote"])["mentions"] == [{"start": 0, "uuid": ALICE}]
    ingest(conn, fakes.envelope(edit={"targetSentTimestamp": 3, "dataMessage": {"timestamp": 4, "message": "hi all"}}))
    m = rows(conn)[0]
    assert m["mentions"] is None
    assert json.loads(rows(conn, "SELECT mentions FROM edits")[0]["mentions"])[0]["uuid"] == BOB


def test_an_older_mirror_gains_the_new_columns(state):
    path = store.db_path(state)
    old = store.sqlite3.connect(str(path))
    old.executescript(store.SCHEMA.replace(", mentions TEXT,", ",").replace("    mentions TEXT, PRIMARY", "    PRIMARY"))
    old.execute("INSERT INTO messages (chat, author, ts, body) VALUES (?, ?, 1, 'x')", (ALICE, ALICE))
    old.commit()
    assert not any(r[1] == "mentions" for t in ("messages", "edits") for r in old.execute(f"PRAGMA table_info({t})"))
    old.close()
    reader = store.connect(path)
    assert store.column(reader.execute("SELECT * FROM messages").fetchone(), "mentions") is None
    reader.close()
    writer = store.connect(path, write=True)
    for table in ("messages", "edits"):
        assert "mentions" in {r["name"] for r in writer.execute(f"PRAGMA table_info({table})")}
    store._add_columns(writer)  # a second writer finding them present changes nothing
    writer.close()


def test_duplicate_delivery_is_ignored(conn):
    payload = fakes.envelope(data={"timestamp": 5, "message": "once"})
    ingest(conn, payload)
    ingest(conn, payload)
    assert len(rows(conn)) == 1


def test_sent_transcript_from_another_device(conn):
    ingest(conn, fakes.envelope(ME, name=None, sync={"sentMessage": {
        "destinationUuid": ALICE, "destinationNumber": "+819011111111", "timestamp": 10, "message": "from phone",
        "expiresInSeconds": 3600, "isExpirationUpdate": False}}))
    m = rows(conn)[0]
    assert (m["chat"], m["author"], m["from_me"], m["expire_start"]) == (ALICE, ME, 1, 10)
    assert rows(conn, "SELECT number FROM chats WHERE id = ?", ALICE) == [{"number": "+819011111111"}]


def test_note_to_self(conn):
    ingest(conn, fakes.envelope(ME, sync={"sentMessage": {"destinationUuid": ME, "timestamp": 11, "message": "memo"}}))
    assert rows(conn)[0]["chat"] == ME


def test_edits_keep_earlier_versions(conn):
    ingest(conn, fakes.envelope(data={"timestamp": 20, "message": "frist"}))
    ingest(conn, fakes.envelope(edit={"targetSentTimestamp": 20, "dataMessage": {"timestamp": 21, "message": "first"}}))
    ingest(conn, fakes.envelope(edit={"targetSentTimestamp": 21, "dataMessage": {"timestamp": 22, "message": "First"}}))
    m = rows(conn)[0]
    assert (m["ts"], m["body"], m["edited"]) == (20, "First", 22)
    assert [e["body"] for e in rows(conn, "SELECT body FROM edits ORDER BY rev_ts")] == ["frist", "first"]


def test_remote_delete_removes_everything(conn, state):
    files = state / "signal-cli" / "attachments"
    files.mkdir(parents=True)
    (files / "p.jpg").write_bytes(b"x")
    (files / "old.jpg").write_bytes(b"y")
    ingest(conn, fakes.envelope(data={"timestamp": 30, "message": "secret",
                                      "attachments": [{"contentType": "image/jpeg", "id": "old.jpg"}]}), state)
    ingest(conn, fakes.envelope(edit={"targetSentTimestamp": 30, "dataMessage": {
        "timestamp": 31, "message": "secret!", "attachments": [{"contentType": "image/jpeg", "id": "p.jpg"}]}}), state)
    ingest(conn, fakes.envelope(BOB, data={"timestamp": 32, "message": "re", "quote": {"id": 30, "authorUuid": ALICE,
                                                                                      "text": "secret"}}), state)
    ingest(conn, fakes.envelope(BOB, data={"timestamp": 33, "reaction": {
        "emoji": "👍", "targetAuthorUuid": ALICE, "targetSentTimestamp": 30, "isRemove": False}}), state)
    assert ingest(conn, fakes.envelope(data={"timestamp": 34, "remoteDelete": {"timestamp": 30}}), state) == ["delete"]
    assert [m["ts"] for m in rows(conn)] == [32]
    assert rows(conn)[0]["quote"] is None
    assert rows(conn, "SELECT * FROM edits") == [] and rows(conn, "SELECT * FROM reactions") == []
    assert not (files / "p.jpg").exists() and not (files / "old.jpg").exists()


def test_delete_clears_quotes_of_every_revision(conn):
    ingest(conn, fakes.envelope(data={"timestamp": 35, "message": "v1"}))
    ingest(conn, fakes.envelope(edit={"targetSentTimestamp": 35, "dataMessage": {"timestamp": 36, "message": "v2"}}))
    ingest(conn, fakes.envelope(edit={"targetSentTimestamp": 36, "dataMessage": {"timestamp": 37, "message": "v3"}}))
    for ts, quoted in ((38, 36), (39, 37)):
        ingest(conn, fakes.envelope(BOB, data={"timestamp": ts, "message": "re",
                                               "quote": {"id": quoted, "authorUuid": ALICE, "text": "v"}}))
    ingest(conn, fakes.envelope(data={"timestamp": 40, "remoteDelete": {"timestamp": 35}}))
    assert [(m["ts"], m["quote"]) for m in rows(conn)] == [(38, None), (39, None)]


def test_only_the_author_can_delete(conn):
    ingest(conn, fakes.envelope(data={"timestamp": 40, "message": "mine"}))
    assert ingest(conn, fakes.envelope(BOB, data={"timestamp": 41, "remoteDelete": {"timestamp": 40}})) == ["ignored"]
    assert len(rows(conn)) == 1


def test_my_own_delete_for_everyone_from_the_phone(conn):
    ingest(conn, fakes.envelope(ME, sync={"sentMessage": {"destinationUuid": ALICE, "timestamp": 50, "message": "oops"}}))
    ingest(conn, fakes.envelope(ME, sync={"sentMessage": {"destinationUuid": ALICE, "timestamp": 51,
                                                          "remoteDelete": {"timestamp": 50}}}))
    assert rows(conn) == []


def test_disappearing_messages_stay_and_are_marked(conn):
    ingest(conn, fakes.envelope(data={"timestamp": 60, "message": "gone soon", "expiresInSeconds": 60}))
    m = conn.execute("SELECT * FROM messages").fetchone()
    assert store.expiry(m) == {"disappearing": "timer starts when the user reads it"}
    ingest(conn, fakes.envelope(ME, sync={"readMessages": [{"senderUuid": ALICE, "timestamp": 60}]}))
    m = conn.execute("SELECT * FROM messages").fetchone()
    assert m["read_at"] and m["expire_start"] == m["read_at"]
    assert "disappears" in store.expiry(m, now=m["expire_start"] + 1000)
    assert "expired" in store.expiry(m, now=m["expire_start"] + 61000)
    assert m["body"] == "gone soon"  # never deleted


def test_timer_updates_are_events(conn):
    assert ingest(conn, fakes.envelope(data={"timestamp": 70, "expiresInSeconds": 86400,
                                             "isExpirationUpdate": True})) == ["timer"]
    m = rows(conn)[0]
    assert m["kind"] == "timer" and m["expires_in"] == 86400


def test_reactions_and_their_removal(conn):
    ingest(conn, fakes.envelope(data={"timestamp": 80, "message": "x"}))
    r = {"emoji": "❤️", "targetAuthorUuid": ALICE, "targetSentTimestamp": 80, "isRemove": False}
    ingest(conn, fakes.envelope(BOB, data={"timestamp": 81, "reaction": r}))
    assert rows(conn, "SELECT reactor, emoji FROM reactions") == [{"reactor": BOB, "emoji": "❤️"}]
    ingest(conn, fakes.envelope(BOB, data={"timestamp": 82, "reaction": {**r, "isRemove": True}}))
    assert rows(conn, "SELECT * FROM reactions") == []


def test_noise_is_ignored(conn):
    assert ingest(conn, fakes.envelope(data={"timestamp": 90, "isProfileKeyUpdate": True})) == ["ignored"]
    assert ingest(conn, {"account": fakes.NUMBER, "envelope": {"sourceUuid": ALICE, "timestamp": 1,
                                                               "receiptMessage": {"isDelivery": True}}}) == ["ignored"]
    assert ingest(conn, {"exception": {"message": "decrypt"}}) == ["no-envelope"]
    assert rows(conn) == []


def test_group_updates_mark_groups_stale(conn):
    ingest(conn, fakes.envelope(data={"timestamp": 95, "groupInfo": {"groupId": GROUP_ID, "type": "UPDATE"}}))
    assert store.get_meta(conn)["groups_stale"] == "1"


def test_contacts_and_groups(conn):
    store.upsert_contacts(conn, [{"uuid": ALICE, "number": "+8190111", "givenName": "Alice", "familyName": "A",
                                  "profile": {"givenName": "Ali"}, "isBlocked": False},
                                 {"uuid": None, "number": "+1"}])
    store.upsert_groups(conn, [{"id": GROUP_ID, "name": "Family", "isMember": True, "messageExpirationTime": 0,
                                "members": [{"uuid": ALICE}, {"uuid": ME}]}, {"id": "bad"}])
    assert rows(conn, "SELECT uuid, name, profile_name FROM contacts") == [
        {"uuid": ALICE, "name": "Alice A", "profile_name": "Ali"}]
    assert rows(conn, "SELECT id, name, member FROM chats") == [{"id": GROUP, "name": "Family", "member": 1}]


def test_record_sent_uses_the_chat_timer(conn):
    store.upsert_groups(conn, [{"id": GROUP_ID, "name": "F", "messageExpirationTime": 300}])
    store.record_sent(conn, chat=GROUP, me=ME, ts=100, body="hi", attachments=[], quote=None)
    m = rows(conn)[0]
    assert (m["from_me"], m["expires_in"], m["expire_start"]) == (1, 300, 100)


def test_attachment_ids_cannot_escape(state):
    assert store.attachment_file("../x", state) is None
    assert store.attachment_file(".hidden", state) is None
    assert store.attachment_file("ok.jpg", state) == state / "signal-cli" / "attachments" / "ok.jpg"
