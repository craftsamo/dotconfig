import importlib.util
import json
from pathlib import Path
import shutil

import pytest

spec = importlib.util.spec_from_file_location("telegram_access_fakes", Path(__file__).resolve().parent / "fakes.py")
fakes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fakes)
store = fakes.load("store")


@pytest.fixture()
def state(monkeypatch):
    base = fakes.short_dir()
    monkeypatch.setenv(store.STATE_ENV, str(base))  # never the real state directory
    yield base
    shutil.rmtree(base, ignore_errors=True)


@pytest.fixture()
def conn(state):
    c = store.connect(store.db_path(state), write=True)
    yield c
    c.close()


def test_chat_ids():
    assert store.parse_chat("123") == 123 and store.parse_chat(" -1001234 ") == -1001234
    assert store.parse_chat(-5) == -5
    for bad in ("alice", "@alice", "+819011111111", "0", 0, True, None, "1e3", ""):
        assert store.parse_chat(bad) is None
    assert store.marked_id("user", 7) == 7 and store.marked_id("group", 7) == -7
    assert store.marked_id("channel", 7) == -1000000000007 and store.is_channel_id(-1000000000007)
    assert not store.is_channel_id(-7)


def test_what_is_mirrored():
    for kind in ("user", "bot", "group", "self"):
        assert store.mirrored(kind, 1, set())
    assert not store.mirrored("supergroup", -1000000000001, set())
    assert store.mirrored("channel", -1000000000001, {-1000000000001})
    assert not store.mirrored(None, 1, {1})


def test_reader_needs_an_existing_mirror(state):
    with pytest.raises(store.StoreError):
        store.connect()
    store.connect(write=True).close()
    reader = store.connect()
    with pytest.raises(Exception):
        reader.execute("INSERT INTO meta (key, value) VALUES ('a', 'b')")


def test_state_and_files_are_private(state):
    store.state_dir(create=True)
    store.connect(write=True).close()
    assert oct(state.stat().st_mode & 0o777) == "0o700"
    assert oct(store.db_path(state).stat().st_mode & 0o777) == "0o600"


def test_upsert_chat_keeps_what_is_not_given(conn):
    store.upsert_chat(conn, 5, kind="user", name="Alice", username="alice", phone="+81")
    store.upsert_chat(conn, 5, name="Alice B", top_id=9, last_ts=100)
    store.upsert_chat(conn, 5, top_id=3, last_ts=50)  # older activity never wins
    row = conn.execute("SELECT * FROM chats WHERE id = 5").fetchone()
    assert (row["kind"], row["name"], row["username"], row["phone"], row["top_id"], row["last_ts"]) == \
        ("user", "Alice B", "alice", "+81", 9, 100)
    with pytest.raises(store.StoreError):
        store.upsert_chat(conn, 6, name="no kind")


def test_unread_follows_messages_and_read_syncs(conn):
    store.upsert_chat(conn, 5, kind="user", read_max=10, top_id=10, unread=0)
    store.touch_chat(conn, 5, 11, 1000, incoming=True)
    store.touch_chat(conn, 5, 12, 1001, incoming=False)  # the user's own message
    store.touch_chat(conn, 5, 11, 1000, incoming=True)   # seen again
    assert conn.execute("SELECT unread, top_id FROM chats WHERE id = 5").fetchone()[:] == (1, 12)
    store.set_read(conn, 5, 12, 0)
    assert conn.execute("SELECT unread, read_max FROM chats WHERE id = 5").fetchone()[:] == (0, 12)
    store.touch_chat(conn, 99, 1, 1, incoming=True)  # an unknown chat is ignored


def test_messages_replace_delete_and_expire(conn):
    store.upsert_message(conn, {"chat": 5, "id": 1, "ts": 10, "body": "a", "media": {"type": "photo"}})
    store.upsert_message(conn, {"chat": 5, "id": 1, "ts": 10, "body": "a (edited)", "edited": 20})
    row = conn.execute("SELECT * FROM messages").fetchone()
    assert row["body"] == "a (edited)" and row["edited"] == 20 and row["media"] is None
    assert store.media_of({"media": json.dumps({"type": "photo"})}) == {"type": "photo"}
    store.upsert_message(conn, {"chat": -1000000000001, "id": 1, "ts": 10, "body": "channel"})
    store.upsert_message(conn, {"chat": -7, "id": 2, "ts": 10, "body": "group"})
    # without a chat (private chats and basic groups) channels are never touched
    assert store.delete_messages(conn, [1, 2]) == 2
    assert [r[0] for r in conn.execute("SELECT body FROM messages")] == ["channel"]
    assert store.delete_messages(conn, [1], chat=-1000000000001) == 1
    with pytest.raises(store.StoreError):
        store.upsert_message(conn, {"chat": "5", "id": 1, "ts": 1})


def test_a_delete_fences_out_later_copies(conn):
    store.upsert_message(conn, {"chat": 5, "id": 1, "ts": 1, "body": "private"})
    store.upsert_message(conn, {"chat": -1000000000001, "id": 1, "ts": 1, "body": "channel"})
    store.delete_messages(conn, [1])  # a private chat or basic group: no chat given
    assert store.upsert_message(conn, {"chat": 5, "id": 1, "ts": 1, "body": "refetched"}) is False
    assert store.upsert_message(conn, {"chat": -7, "id": 1, "ts": 1, "body": "same id, group"}) is False
    # channel ids are per channel: a non-channel delete never fences a channel's message
    assert store.upsert_message(conn, {"chat": -1000000000001, "id": 1, "ts": 1, "body": "edit"}) is True
    store.delete_messages(conn, [1], chat=-1000000000001)
    assert store.upsert_message(conn, {"chat": -1000000000001, "id": 1, "ts": 1, "body": "again"}) is False
    assert store.upsert_message(conn, {"chat": -1000000000002, "id": 1, "ts": 1, "body": "other"}) is True
    # the fence lifts after its time
    store.purge_tombstones(conn, now=store.now_ms() + store.TOMBSTONE_TTL + 1)
    assert store.upsert_message(conn, {"chat": 5, "id": 1, "ts": 1, "body": "much later"}) is True


def test_disappearing_messages_stay_like_signal(conn, state):
    now = 10_000_000
    store.upsert_message(conn, {"chat": 5, "id": 3, "ts": 10, "body": "timer", "expires": now - 1}, now=now)
    store.upsert_message(conn, {"chat": 5, "id": 4, "ts": 10, "body": "timer soon", "expires": now + 60_000}, now=now)
    store.upsert_message(conn, {"chat": 5, "id": 5, "ts": 10, "body": "timer later", "expires": now + 86_400_000},
                         now=now)
    store.upsert_message(conn, {"chat": 5, "id": 6, "ts": 10, "media": {"type": "photo", "self_destructing": True}},
                         now=now)
    for msg_id in (3, 4, 5, 6):
        folder = store.kept_path(5, msg_id, state)
        folder.mkdir(parents=True)
        (folder / "f.jpg").write_bytes(b"x")
    assert store.purge_tombstones(conn, now=now + 10 ** 9) == 0
    # deletes at the timer's time are its disappearing: kept, marked expired, files kept
    assert store.delete_messages(conn, [3, 4], state=state, now=now) == 0
    rows = {r["id"]: r["expires"] for r in conn.execute("SELECT id, expires FROM messages")}
    assert rows == {3: now - 1, 4: now, 5: now + 86_400_000, 6: None}
    assert all(store.kept_file(5, i, state) for i in (3, 4))
    # a view-once expires by its media, never by a delete: its delete is a delete
    assert store.delete_messages(conn, [6], state=state, now=now) == 1 and store.kept_file(5, 6, state) is None
    # a refetch or an edit never revives an expired message's timer
    store.upsert_message(conn, {"chat": 5, "id": 4, "ts": 10, "body": "edited", "expires": now + 60_000}, now=now + 1)
    assert conn.execute("SELECT expires FROM messages WHERE id = 4").fetchone()[0] == now
    # a delete for everyone well before the timer removes the message and its file
    assert store.delete_messages(conn, [5], state=state, now=now) == 1
    assert store.kept_file(5, 5, state) is None and not store.kept_path(5, 5, state).exists()
    assert store.kept_file(5, 99, state) is None
    # a delete arriving long after the timer cannot be told from a delete for everyone: it removes
    store.upsert_message(conn, {"chat": 5, "id": 7, "ts": 10, "body": "old", "expires": now - 10 ** 8}, now=now)
    assert store.delete_messages(conn, [7], state=state, now=now) == 1
    # nothing on the way to a kept file may be a link
    outside = state / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("x")
    store.kept_path(5, 8, state).parent.mkdir(parents=True, exist_ok=True)
    store.kept_path(5, 8, state).symlink_to(outside)
    assert store.kept_file(5, 8, state) is None


def test_whose_delete_it_was():
    grace, hour = store.DELETE_GRACE, 3_600_000
    now = 100 * hour
    f = store.expiry_delete
    assert not f(None, now)
    assert not f(now + grace + 1, now)              # before the timer: a delete for everyone
    assert f(now + grace, now) and f(now - grace, now) and f(now, now)
    assert not f(now - grace - 1, now)              # late: cannot be told apart, removes
    gaps = [(0, 20 * hour), (90 * hour, int(99.9 * hour))]
    assert not f(now, now, gaps)                    # the timer ran out within the catch-up after a gap
    assert f(now, now, [(0, 20 * hour), (80 * hour, 90 * hour)])
    assert not f(now, now, [(80 * hour, 90 * hour), (95 * hour, 99.95 * hour)])  # an older gap never hides a newer


def test_a_delete_from_a_gap_removes(conn, state):
    hour = 3_600_000
    now = 100 * hour
    store.upsert_message(conn, {"chat": 5, "id": 1, "ts": 1, "body": "x", "expires": now}, now=now)
    store.upsert_message(conn, {"chat": 5, "id": 2, "ts": 1, "body": "y", "expires": now + 60_000}, now=now)
    store.record_gap(conn, 80 * hour, now - 400_000)    # the agent woke 6m40s ago; edge of 1 is 5 min ago
    assert store.gaps(conn) == [(80 * hour, now - 400_000)]
    assert store.delete_messages(conn, [1, 2], state=state, now=now, unwatched=store.gaps(conn)) == 2
    assert [r[0] for r in conn.execute("SELECT id FROM messages")] == []
    store.purge_tombstones(conn, now=now + store.GAP_TTL + 1)
    assert store.gaps(conn) == []


def test_unlisted_chats_lose_their_messages(conn):
    store.upsert_chat(conn, -1000000000001, kind="supergroup")
    store.upsert_chat(conn, -1000000000002, kind="channel")
    store.upsert_chat(conn, -7, kind="group")
    for chat in (-1000000000001, -1000000000002, -7):
        store.upsert_message(conn, {"chat": chat, "id": 1, "ts": 1, "body": "x"})
    assert store.drop_unlisted(conn, {-1000000000002}) == 1
    assert sorted(r[0] for r in conn.execute("SELECT chat FROM messages")) == [-1000000000002, -7]


def test_drop_chat(conn):
    store.upsert_chat(conn, -1000000000001, kind="supergroup")
    conn.execute("UPDATE chats SET seeded = 1")
    store.upsert_message(conn, {"chat": -1000000000001, "id": 1, "ts": 1, "body": "x"})
    assert store.drop_chat(conn, -1000000000001) == 1
    assert conn.execute("SELECT seeded FROM chats").fetchone()[0] == 0


def test_sync_list_round_trip(state):
    assert store.read_sync_list() == []
    store.write_sync_list([-1000000000001, -1000000000002])
    assert store.read_sync_list() == [-1000000000001, -1000000000002]
    assert oct(store.sync_path(state).stat().st_mode & 0o777) == "0o600"
    store.sync_path(state).write_text('{"chats": ["-1000000000003", "x", -1000000000003, 0]}')
    assert store.read_sync_list() == [-1000000000003]
    store.sync_path(state).write_text("not json")
    assert store.read_sync_list() == []
    with pytest.raises(store.StoreError):
        store.write_sync_list(list(range(1, store.SYNC_MAX + 2)))


def test_local_time():
    assert store.local_time(None) is None and store.local_time(True) is None
    assert store.local_time(1790000000000).startswith("2026-")
