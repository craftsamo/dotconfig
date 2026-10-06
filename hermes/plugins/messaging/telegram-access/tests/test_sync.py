"""The sync agent against a fake Telethon client: normalising Telegram's objects, keeping the
mirror, the sync list, and the plugin's requests over a real UNIX socket. Never Telethon,
Telegram or the Keychain."""

import asyncio
import importlib.util
import os
from pathlib import Path
import shutil
import threading
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location("telegram_access_fakes", Path(__file__).resolve().parent / "fakes.py")
fakes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fakes)
store = fakes.load("store")
sync = fakes.load("sync")
rpc = fakes.load("rpc")
obj, message, user = fakes.obj, fakes.message, fakes.user


@pytest.fixture()
def state(monkeypatch):
    base = fakes.short_dir()
    monkeypatch.setenv(store.STATE_ENV, str(base))
    yield base
    shutil.rmtree(base, ignore_errors=True)


@pytest.fixture()
def conn(state):
    fakes.seed(state)
    c = store.connect(store.db_path(state), write=True)
    yield c
    c.close()


def agent_for(conn, state, client=None):
    client = client or fakes.FakeClient()
    deliveries = sync.Deliveries()
    deliveries.install(client)
    return sync.Agent(client, conn, state, me_id=fakes.ME, pace=(0, 0), deliveries=deliveries)


# --- normalising ----------------------------------------------------------------------------------

def test_chat_fields_by_kind():
    assert sync.chat_fields(user(5, "Alice", "B", username="ab", phone="8190"), fakes.ME) == \
        (5, {"kind": "user", "name": "Alice B", "username": "ab", "phone": "+8190", "left_chat": 0, "can_send": None})
    assert sync.chat_fields(user(fakes.ME, "Rui", is_self=True), fakes.ME)[1]["kind"] == "self"
    assert sync.chat_fields(user(6, "Bot", bot=True))[1]["kind"] == "bot"
    chat, fields = sync.chat_fields(obj("Chat", id=7, title="Family", left=False, deactivated=False,
                                        participants_count=4, default_banned_rights=None, creator=False,
                                        admin_rights=None))
    assert chat == -7 and fields["kind"] == "group" and fields["members"] == 4 and fields["can_send"] == 1
    chat, fields = sync.chat_fields(obj("Channel", id=8, title="News", megagroup=False, left=False, creator=False,
                                        admin_rights=None, username="news"))
    assert chat == -1000000000008 and fields["kind"] == "channel" and fields["can_send"] == 0
    chat, fields = sync.chat_fields(obj("Channel", id=9, title="Big", megagroup=True, left=False, creator=False,
                                        admin_rights=None, banned_rights=None,
                                        default_banned_rights=SimpleNamespace(send_messages=True)))
    assert fields["kind"] == "supergroup" and fields["can_send"] == 0
    assert sync.chat_fields(obj("ChannelForbidden", id=9, title="Gone", megagroup=True))[1]["left_chat"] == 1
    assert sync.chat_fields(obj("Something", id=1)) is None


def test_message_row_text_reply_edit_and_auto_delete():
    msg = message(fakes.ALICE, 10, "hello", sender=user(fakes.ALICE, "Alice"), reply_to=9, ttl_period=86400,
                  edit_date=fakes.when(0))
    row = sync.message_row(msg)
    assert row["chat"] == fakes.ALICE and row["id"] == 10 and row["body"] == "hello" and row["reply_to"] == 9
    assert row["sender"] == fakes.ALICE and row["sender_name"] == "Alice" and not row["from_me"]
    assert row["expires"] == row["ts"] + 86400 * 1000 and row["edited"]
    assert sync.message_row(obj("MessageEmpty", chat_id=1, id=1, date=fakes.when())) is None
    assert sync.message_row(obj("Message", chat_id=None, id=1, date=fakes.when())) is None


def test_message_row_media_and_service():
    file = SimpleNamespace(name="report.pdf", mime_type="application/pdf", size=1234, duration=None, emoji=None)
    doc = message(1, 1, "", media=obj("MessageMediaDocument", ttl_seconds=None, spoiler=False), file=file)
    assert sync.message_row(doc)["media"] == {"type": "document", "name": "report.pdf", "mime": "application/pdf",
                                              "size": 1234}
    voice = message(1, 2, "", media=obj("MessageMediaDocument"), file=SimpleNamespace(name=None, mime_type="audio/ogg",
                                                                                         size=9, duration=3), voice=1)
    assert sync.message_row(voice)["media"]["type"] == "voice"
    photo = message(1, 3, "look", media=obj("MessageMediaPhoto", ttl_seconds=10, spoiler=True),
                    file=SimpleNamespace(name=None, mime_type="image/jpeg", size=10, duration=None))
    media = sync.message_row(photo)["media"]
    assert media["type"] == "photo" and media["self_destructing"] and media["spoiler"]
    page = message(1, 4, "see", media=obj("MessageMediaWebPage", webpage=SimpleNamespace(url="https://x", title="X")))
    assert sync.message_row(page)["media"] == {"type": "link preview", "url": "https://x", "title": "X"}
    assert sync.message_row(message(1, 5, "", media=obj("MessageMediaDice")))["media"]["type"] == "unsupported"
    service = message(1, 6, None, action=obj("MessageActionSetMessagesTTL", period=86400))
    row = sync.message_row(service)
    assert row["kind"] == "service" and row["body"] == "set auto-delete to 1 day"
    assert sync.service_text(obj("MessageActionChatEditTitle", title="New"))[0] == "changed the title to “New”"
    assert sync.service_text(obj("MessageActionPhoneCall", video=False, duration=None))[0] == "missed or declined call"
    assert sync.service_text(obj("MessageActionWhatever"))[0] == "service event (Whatever)"


def test_send_errors_are_classified():
    one = {"single_delivery": True}
    assert sync.classify_send_error(fakes.RpcFailure(400, "CHAT_WRITE_FORBIDDEN"), **one) == "not_sent"
    assert sync.classify_send_error(fakes.RpcFailure(420, "FLOOD_WAIT_30"), **one) == "not_sent"
    assert sync.classify_send_error(fakes.RpcFailure(500, "INTERNAL"), **one) == "uncertain"
    assert sync.classify_send_error(fakes.RpcFailure(-503, "Timeout"), **one) == "uncertain"
    assert sync.classify_send_error(asyncio.TimeoutError(), **one) == "uncertain"
    assert sync.classify_send_error(ConnectionError(), **one) == "uncertain"
    # a refusal that may answer a repeated delivery, or a duplicate random id, may follow a delivery
    assert sync.classify_send_error(fakes.RpcFailure(403, "CHAT_WRITE_FORBIDDEN")) == "uncertain"
    duplicate = fakes.RpcFailure(400, "RANDOM_ID_DUPLICATE")
    duplicate.message = "RANDOM_ID_DUPLICATE"
    assert sync.classify_send_error(duplicate, **one) == "uncertain"


def test_deliveries_count_send_requests_and_reconnects():
    client = fakes.FakeClient()
    deliveries = sync.Deliveries()
    assert deliveries.install(client) and deliveries.installed
    mark = deliveries.mark()
    client._sender.send(fakes.obj("GetHistoryRequest"))
    client._sender.send([fakes.obj("SendMessageRequest")])
    assert deliveries.single(mark) and client._sender.handed == ["GetHistoryRequest", "list"]  # still sent
    fakes.run(client._sender._reconnect(None))
    assert not deliveries.single(mark)
    assert not sync.Deliveries().single((0, 0))  # not installed: never single
    assert not sync.Deliveries().install(object())


@pytest.mark.parametrize("how", ["retried", "reconnected", "uninstrumented"])
def test_a_refusal_after_a_repeated_delivery_is_uncertain(conn, state, how):
    client = fakes.FakeClient()
    client.send_error = fakes.RpcFailure(403, "CHAT_WRITE_FORBIDDEN")
    if how == "retried":
        client.deliveries = 2           # Telethon retried after a server error
    elif how == "reconnected":
        client.reconnect_during_send = True
    agent = agent_for(conn, state, client) if how != "uninstrumented" else \
        sync.Agent(client, conn, state, me_id=fakes.ME, pace=(0, 0))
    with pytest.raises(sync.AgentError) as err:
        fakes.run(agent.handle("send", {"chat": fakes.ALICE, "text": "hi"}))
    assert err.value.kind == "uncertain"


def test_history_never_resurrects_a_deleted_message(conn, state):
    client = fakes.FakeClient(history={fakes.ALICE: [message(fakes.ALICE, i, f"m{i}") for i in range(10, 20)]})
    agent = agent_for(conn, state, client)
    agent.on_delete([15], None)
    fakes.run(agent._fill(fakes.ALICE, 13))
    ids = [r[0] for r in conn.execute("SELECT id FROM messages WHERE chat = ? ORDER BY id", (fakes.ALICE,))]
    assert 15 not in ids and 19 in ids
    fakes.run(agent.on_edit(message(fakes.ALICE, 15, "late edit", edit_date=fakes.when())))
    assert not conn.execute("SELECT 1 FROM messages WHERE chat = ? AND id = 15", (fakes.ALICE,)).fetchone()


def test_history_for_a_chat_that_left_the_mirror_is_dropped(conn, state):
    agent = agent_for(conn, state)
    rows = [sync.message_row(message(fakes.SUPER, 1, "x"))]
    assert agent._store_many_rows(rows) == 0
    agent.synced.add(fakes.SUPER)
    assert agent._store_many_rows(rows) == 1


def test_a_list_changed_while_down_is_applied_at_start(conn, state):
    store.upsert_message(conn, {"chat": fakes.SUPER, "id": 1, "ts": 1, "body": "stale"})
    agent_for(conn, state)
    assert conn.execute("SELECT COUNT(*) FROM messages WHERE chat = ?", (fakes.SUPER,)).fetchone()[0] == 0


# --- pushed updates -------------------------------------------------------------------------------

def test_new_messages_are_stored_for_mirrored_chats_only(conn, state):
    agent = agent_for(conn, state)
    assert fakes.run(agent.on_message(message(fakes.ALICE, 50, "new", sender=user(fakes.ALICE)))) == "message"
    assert conn.execute("SELECT body FROM messages WHERE chat = ? AND id = 50", (fakes.ALICE,)).fetchone()[0] == "new"
    assert fakes.run(agent.on_message(message(fakes.SUPER, 7, "busy"))) == "activity"
    assert conn.execute("SELECT COUNT(*) FROM messages WHERE chat = ?", (fakes.SUPER,)).fetchone()[0] == 0
    row = conn.execute("SELECT unread, top_id FROM chats WHERE id = ?", (fakes.SUPER,)).fetchone()
    assert row[:] == (1, 7)


def test_a_message_from_an_unknown_chat_adds_the_chat(conn, state):
    agent = agent_for(conn, state)
    assert fakes.run(agent.on_message(message(7777, 1, "hello"))) == "message"
    assert conn.execute("SELECT kind, name FROM chats WHERE id = 7777").fetchone()[:] == ("user", "Stranger")


def test_edits_deletes_reads_and_auto_delete_timer(conn, state):
    agent = agent_for(conn, state)
    fakes.run(agent.on_edit(message(fakes.ALICE, 10, "changed", sender=user(fakes.ALICE), edit_date=fakes.when())))
    assert conn.execute("SELECT body FROM messages WHERE chat = ? AND id = 10", (fakes.ALICE,)).fetchone()[0] == "changed"
    assert fakes.run(agent.on_edit(message(fakes.SUPER, 1, "x"))) == "ignored"
    assert agent.on_delete([10, 11], None) == "delete:2"
    agent.on_read(fakes.ALICE, 12, 0)
    assert conn.execute("SELECT unread FROM chats WHERE id = ?", (fakes.ALICE,)).fetchone()[0] == 0
    fakes.run(agent.on_message(message(fakes.ALICE, 60, None, action=obj("MessageActionSetMessagesTTL", period=3600))))
    assert conn.execute("SELECT ttl FROM chats WHERE id = ?", (fakes.ALICE,)).fetchone()[0] == 3600


def test_files_of_disappearing_messages_are_kept(conn, state):
    photo = SimpleNamespace(name="p.jpg", mime_type="image/jpeg", size=10, duration=None)
    timed = message(fakes.ALICE, 70, "", media=obj("MessageMediaPhoto", ttl_seconds=None), file=photo,
                    ttl_period=86400)
    once = message(fakes.ALICE, 71, "", media=obj("MessageMediaPhoto", ttl_seconds=10), file=photo)
    plain = message(fakes.ALICE, 72, "", media=obj("MessageMediaPhoto", ttl_seconds=None), file=photo)
    risky = message(fakes.ALICE, 73, "", media=obj("MessageMediaDocument"), ttl_period=86400,
                    file=SimpleNamespace(name="x.zip", mime_type="application/zip", size=10, duration=None))
    client = fakes.FakeClient(history={fakes.ALICE: [timed, once, plain, risky]})
    agent = agent_for(conn, state, client)
    for msg in (timed, once, plain, risky):
        fakes.run(agent.on_message(msg))
    assert agent._keep_queue == [(fakes.ALICE, 70), (fakes.ALICE, 71)]
    assert fakes.run(agent.keep_some()) == 2
    assert store.kept_file(fakes.ALICE, 70, state).name == "p.jpg" and store.kept_file(fakes.ALICE, 71, state)
    assert store.kept_file(fakes.ALICE, 72, state) is None
    # the view-once photo is viewed: Telegram serves it without its file; the kept copy stays
    viewed = message(fakes.ALICE, 71, "", media=obj("MessageMediaPhoto", ttl_seconds=10, photo=None), file=None,
                     edit_date=fakes.when())
    fakes.run(agent.on_edit(viewed))
    media = store.media_of(conn.execute("SELECT media FROM messages WHERE id = 71").fetchone())
    assert media["viewed"] and store.kept_file(fakes.ALICE, 71, state)
    # deleted for everyone long before its timer: gone, file too
    agent.on_delete([70], None)
    assert store.kept_file(fakes.ALICE, 70, state) is None


def test_a_file_is_not_kept_for_a_message_deleted_meanwhile(conn, state):
    photo = SimpleNamespace(name="p.jpg", mime_type="image/jpeg", size=10, duration=None)
    timed = message(fakes.ALICE, 80, "", media=obj("MessageMediaPhoto", ttl_seconds=None), file=photo,
                    ttl_period=86400)
    agent = agent_for(conn, state, fakes.FakeClient(history={fakes.ALICE: [timed]}))
    fakes.run(agent.on_message(timed))
    agent.on_delete([80], None)
    assert fakes.run(agent.keep_some()) == 0 and store.kept_file(fakes.ALICE, 80, state) is None


def test_gaps_in_watching_are_all_remembered(conn, state):
    hour = 3_600_000
    store.set_meta(conn, alive_at=8 * hour)
    agent = agent_for(conn, state)
    assert store.gaps(conn)[-1][0] == 8 * hour             # down since the previous run's last beat
    agent.last_beat = 9 * hour + 600_000
    assert agent.note_coverage(9 * hour + 605_000) is False
    assert agent.note_coverage(10 * hour + 600_000) is True     # slept 09:10 → 10:10
    fakes.run(agent.client._sender._reconnect(None))
    assert agent.note_coverage(10 * hour + 602_000) is True     # and a reconnect right after
    recorded = store.gaps(conn)
    assert (9 * hour + 605_000, 10 * hour + 600_000) in recorded and (10 * hour + 600_000, 10 * hour + 602_000) in recorded
    # a message timed for 10:15 whose delete arrives at its time may have been deleted at 09:15
    assert not store.expiry_delete(10 * hour + 900_000, 10 * hour + 900_000, recorded)


def test_a_delete_after_a_sleep_removes_a_message_timed_within_it(conn, state):
    agent = agent_for(conn, state)
    now = store.now_ms()
    store.upsert_message(conn, {"chat": fakes.ALICE, "id": 90, "ts": 1, "body": "x", "expires": now})
    agent.last_beat = now - 3_600_000   # the last beat was an hour ago: asleep since
    agent.on_delete([90], None)
    assert not conn.execute("SELECT 1 FROM messages WHERE chat = ? AND id = 90", (fakes.ALICE,)).fetchone()


def test_keeping_is_bounded_by_attempts(conn, state):
    client = fakes.FakeClient()  # Telegram no longer has any of them
    agent = agent_for(conn, state, client)
    for msg_id in range(100, 120):
        store.upsert_message(conn, {"chat": fakes.ALICE, "id": msg_id, "ts": 1, "expires": 2,
                                    "media": {"type": "photo"}})
        agent._keep_queue.append((fakes.ALICE, msg_id))
    assert fakes.run(agent.keep_some()) == 0
    assert len([c for c in client.calls if c[0] == "get_messages"]) == sync.KEEP_PER_ROUND
    assert len(agent._keep_queue) == 20 - sync.KEEP_PER_ROUND


def test_a_mirror_that_cannot_be_written_stops_the_agent(conn, state):
    agent = agent_for(conn, state)
    conn.close()
    with pytest.raises(sync.StorageError):
        agent.on_delete([1], None)


# --- the chat list and the sync list --------------------------------------------------------------

def dialog(entity, top, *, unread=0, seconds_ago=0):
    return SimpleNamespace(entity=entity, message=SimpleNamespace(id=top), unread_count=unread,
                           dialog=SimpleNamespace(read_inbox_max_id=top - unread, ttl_period=None),
                           date=fakes.when(seconds_ago), archived=False)


def test_refresh_lists_fills_gaps_and_seeds(conn, state):
    newcomer = user(8888, "Bob")
    old = user(8889, "Quiet")
    history = {fakes.ALICE: [message(fakes.ALICE, i, f"m{i}") for i in range(10, 16)],
               8888: [message(8888, i, f"b{i}") for i in range(1, 4)]}
    client = fakes.FakeClient(history=history, dialogs=[
        dialog(user(fakes.ALICE, "Alice"), 15, unread=1), dialog(newcomer, 3), dialog(old, 1, seconds_ago=90 * 86400),
        dialog(obj("Channel", id=5001, title="Big group", megagroup=True, left=False, creator=False, admin_rights=None,
                   banned_rights=None, default_banned_rights=None), 900)])
    agent = agent_for(conn, state, client)
    result = fakes.run(agent.refresh())
    assert result["chats"] == 4 and result["filled"] == 2 and result["seeded"] == 1
    ids = [r[0] for r in conn.execute("SELECT id FROM messages WHERE chat = ? ORDER BY id", (fakes.ALICE,))]
    assert ids == [10, 11, 12, 13, 14, 15]
    assert conn.execute("SELECT COUNT(*) FROM messages WHERE chat = 8888").fetchone()[0] == 3
    # a private chat quiet for months is followed from now on, not seeded
    assert conn.execute("SELECT seeded FROM chats WHERE id = 8889").fetchone()[0] == 1
    assert not any(c[1] == 8889 for c in client.calls)
    # a supergroup off the sync list is listed, never fetched
    assert not any(c[1] == fakes.SUPER for c in client.calls)
    assert conn.execute("SELECT unread FROM chats WHERE id = ?", (fakes.ALICE,)).fetchone()[0] == 1


def test_sync_list_changes_seed_and_drop(conn, state):
    client = fakes.FakeClient(history={fakes.SUPER: [message(fakes.SUPER, i, "x") for i in range(1, 80)]})
    agent = agent_for(conn, state, client)
    assert fakes.run(agent.follow_sync_list()) is None
    store.write_sync_list([fakes.SUPER])
    os.utime(store.sync_path(state), (1, 1))
    added, removed = fakes.run(agent.follow_sync_list())
    assert added == {fakes.SUPER} and not removed
    assert conn.execute("SELECT COUNT(*) FROM messages WHERE chat = ?", (fakes.SUPER,)).fetchone()[0] == sync.SEED_COUNT
    store.write_sync_list([])
    os.utime(store.sync_path(state), (2, 2))
    fakes.run(agent.follow_sync_list())
    assert conn.execute("SELECT COUNT(*) FROM messages WHERE chat = ?", (fakes.SUPER,)).fetchone()[0] == 0


# --- requests ------------------------------------------------------------------------------------

def test_history_reads_live_without_storing(conn, state):
    client = fakes.FakeClient(history={fakes.SUPER: [message(fakes.SUPER, i, f"m{i}") for i in range(1, 30)]})
    agent = agent_for(conn, state, client)
    out = fakes.run(agent.handle("history", {"chat": fakes.SUPER, "limit": 5}))
    assert [m["id"] for m in out["messages"]] == [25, 26, 27, 28, 29] and out["more"]
    out = fakes.run(agent.handle("history", {"chat": fakes.SUPER, "limit": 3, "after_id": 10}))
    assert [m["id"] for m in out["messages"]] == [11, 12, 13]
    out = fakes.run(agent.handle("history", {"chat": fakes.SUPER, "around": 15, "before_count": 2, "after_count": 2}))
    assert [m["id"] for m in out["messages"]] == [13, 14, 15, 16, 17]
    assert conn.execute("SELECT COUNT(*) FROM messages WHERE chat = ?", (fakes.SUPER,)).fetchone()[0] == 0
    with pytest.raises(sync.AgentError) as err:
        fakes.run(agent.handle("history", {"chat": 424242}))
    assert err.value.kind == "not_found"


def test_backfill_pages_back_from_the_oldest(conn, state):
    client = fakes.FakeClient(history={fakes.GROUP: [message(fakes.GROUP, i, "x") for i in range(1, 160)]})
    agent = agent_for(conn, state, client)
    conn.execute("DELETE FROM messages WHERE chat = ?", (fakes.GROUP,))
    store.upsert_message(conn, {"chat": fakes.GROUP, "id": 150, "ts": 1, "body": "x"})
    out = fakes.run(agent.handle("backfill", {"chat": fakes.GROUP, "pages": 3}))
    assert out["added"] == 149 and out["complete"]
    with pytest.raises(sync.AgentError):
        fakes.run(agent.handle("backfill", {"chat": fakes.SUPER}))


def test_send_text_records_and_never_retries(conn, state):
    client = fakes.FakeClient()
    agent = agent_for(conn, state, client)
    out = fakes.run(agent.handle("send", {"chat": fakes.ALICE, "text": "hi", "reply_to": 10}))
    assert out["ids"] == [501] and out["recorded"]
    assert client.sent == [("text", ("peer", fakes.ALICE), "hi", 10)]
    assert conn.execute("SELECT from_me, body FROM messages WHERE chat = ? AND id = 501",
                        (fakes.ALICE,)).fetchone()[:] == (1, "hi")
    client.send_error = fakes.RpcFailure(403, "CHAT_WRITE_FORBIDDEN")
    with pytest.raises(sync.AgentError) as err:
        fakes.run(agent.handle("send", {"chat": fakes.ALICE, "text": "again"}))
    assert err.value.kind == "not_sent" and len(client.sent) == 1


def test_an_uncertain_send_looks_once_for_a_hint(conn, state):
    client = fakes.FakeClient(history={fakes.ALICE: [message(fakes.ALICE, 77, "hi", out=True)]})
    client.send_error = asyncio.TimeoutError()
    agent = agent_for(conn, state, client)
    with pytest.raises(sync.AgentError) as err:
        fakes.run(agent.handle("send", {"chat": fakes.ALICE, "text": "hi"}))
    assert err.value.kind == "uncertain" and "[77]" in err.value.extra["hint"]


def test_files_come_only_from_the_outbox(conn, state):
    client = fakes.FakeClient()
    agent = agent_for(conn, state, client)
    outbox = store.outbox_dir(state) / "abc"
    outbox.mkdir(parents=True)
    (outbox / "0-a.png").write_bytes(b"png")
    (outbox / "1-b.png").write_bytes(b"png")
    out = fakes.run(agent.handle("send", {"chat": fakes.GROUP, "text": "pics",
                                          "files": [str(outbox / "0-a.png"), str(outbox / "1-b.png")]}))
    assert len(out["ids"]) == 2
    assert client.sent[0][2:] == (["0-a.png", "1-b.png"], "pics", None, False)
    elsewhere = state / "x.png"
    elsewhere.write_bytes(b"png")
    with pytest.raises(sync.AgentError) as err:
        fakes.run(agent.handle("send", {"chat": fakes.GROUP, "files": [str(elsewhere)]}))
    assert err.value.kind == "not_sent" and len(client.sent) == 1


def test_download_refuses_self_destructing_media(conn, state):
    secret = message(fakes.ALICE, 90, "", media=obj("MessageMediaPhoto", ttl_seconds=10),
                     file=SimpleNamespace(name=None, mime_type="image/jpeg", size=10, duration=None))
    plain = message(fakes.ALICE, 91, "", media=obj("MessageMediaPhoto", ttl_seconds=None),
                    file=SimpleNamespace(name="p.jpg", mime_type="image/jpeg", size=10, duration=None))
    big = message(fakes.ALICE, 92, "", media=obj("MessageMediaDocument"),
                  file=SimpleNamespace(name="big.pdf", mime_type="application/pdf", size=10 ** 9, duration=None))
    agent = agent_for(conn, state, fakes.FakeClient(history={fakes.ALICE: [secret, plain, big]}))
    with pytest.raises(sync.AgentError):
        fakes.run(agent.handle("download", {"chat": fakes.ALICE, "id": 90}))
    out = fakes.run(agent.handle("download", {"chat": fakes.ALICE, "id": 91}))
    path = Path(out["path"])
    assert path.is_file() and store.incoming_dir(state) in path.parents
    assert fakes.run(agent.handle("download", {"chat": fakes.ALICE, "id": 92, "max_bytes": 100}))["too_large"]


# --- the socket ----------------------------------------------------------------------------------

def test_requests_over_the_socket(conn, state):
    sock = store.socket_path(state)
    ready = threading.Event()
    holder = {}

    def serve():
        own = store.connect(store.db_path(state), write=True)  # sqlite connections stay in their thread
        agent = agent_for(own, state, fakes.FakeClient())

        async def main():
            server = await asyncio.start_unix_server(lambda r, w: sync.serve_connection(agent, r, w), path=str(sock))
            holder["loop"], holder["server"] = asyncio.get_running_loop(), server
            ready.set()
            holder["stop"] = asyncio.Event()
            await holder["stop"].wait()
            server.close()
        asyncio.run(main())

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    assert ready.wait(5)
    try:
        assert rpc.call(sock, "status", {})["me"] == fakes.ME
        with pytest.raises(rpc.RpcError) as err:
            rpc.call(sock, "send", {"chat": fakes.ALICE})
        assert err.value.kind == "not_sent"
        with pytest.raises(rpc.RpcError) as err:
            rpc.call(sock, "nope", {})
        assert err.value.kind == "invalid"
    finally:
        holder["loop"].call_soon_threadsafe(holder["stop"].set)
        thread.join(5)
    with pytest.raises(rpc.NotConnected):
        rpc.call(sock, "status", {})
