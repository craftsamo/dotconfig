import importlib.util
from datetime import datetime, timezone
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


store = _load("discord_access_store_test", ROOT / "store.py")

G1, G2 = "300000000000000001", "300000000000000002"
C = [str(400000000000000000 + i) for i in range(1, 40)]


@pytest.fixture(autouse=True)
def state(tmp_path, monkeypatch):
    monkeypatch.setenv(store.STATE_ENV, str(tmp_path / "state"))
    return tmp_path / "state"


def test_snowflake_round_trip():
    when = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)
    flake = store.snowflake_at(when)
    assert store.snowflake_time(flake) == when
    assert store.is_snowflake(str(flake)) and not store.is_snowflake("general") and not store.is_snowflake(123)


def test_state_dir_is_private(state):
    store.connect(write=True).close()
    assert state.stat().st_mode & 0o777 == 0o700
    assert (state / "mirror.db").stat().st_mode & 0o777 == 0o600


def test_reader_never_creates_the_mirror():
    with pytest.raises(store.StoreError, match="never run"):
        store.connect(write=False)


def test_message_row_marks_me_replies_and_attachments():
    m = {"id": "500000000000000001", "channel_id": C[0], "type": 19, "content": "hi",
         "author": {"id": "100000000000000001", "username": "me", "global_name": "Me"},
         "message_reference": {"message_id": "500000000000000000"},
         "attachments": [{"filename": "a.png", "content_type": "image/png", "size": 3, "url": "https://cdn/x"}],
         "embeds": [{}], "member": {"nick": "Nick"}}
    row = store.message_row(m, "100000000000000001", guild_id=G1)
    assert row["from_me"] == 1 and row["author_name"] == "Nick" and row["reply_to"] == 500000000000000000
    assert row["guild_id"] == int(G1) and row["embeds"] == 1
    assert json.loads(row["attachments"])[0]["name"] == "a.png"
    forwarded = {**m, "type": 0}
    assert store.message_row(forwarded, None)["reply_to"] is None


def test_sync_add_whole_server_and_channels():
    data = store.sync_add(G1, "One", None, [C[0]])
    assert data["guilds"][G1] == {"name": "One", "channels": [], "exclude": [C[0]]}
    data = store.sync_add(G2, "Two", [C[1], C[2]])
    assert data["guilds"][G2]["channels"] == [C[1], C[2]]
    data = store.sync_add(G2, None, [C[2], C[3]])
    assert data["guilds"][G2]["channels"] == [C[1], C[2], C[3]] and data["guilds"][G2]["name"] == "Two"
    assert store.load_sync() == data


def test_sync_add_refuses_mode_switches():
    store.sync_add(G1, "One")
    with pytest.raises(store.StoreError, match="whole server is already synced"):
        store.sync_add(G1, "One", [C[0]])
    store.sync_add(G2, "Two", [C[1]])
    with pytest.raises(store.StoreError, match="remove it first"):
        store.sync_add(G2, "Two")


def test_limits_are_enforced_in_code():
    with pytest.raises(store.LimitError, match="limit is 30"):
        store.sync_add(G1, "One", C[:31])
    for i in range(3):
        store.sync_add(str(300000000000000010 + i), f"S{i}")
    with pytest.raises(store.LimitError):
        store.sync_add(G1, "One", [C[0]])  # 3 whole servers = 30 channels already
    assert G1 not in store.load_sync()["guilds"]


def test_sync_remove():
    store.sync_add(G1, "One")
    store.sync_add(G2, "Two", [C[1], C[2]])
    assert store.sync_remove(G1, [C[5]])["guilds"][G1]["exclude"] == [C[5]]
    assert store.sync_remove(G2, [C[1]])["guilds"][G2]["channels"] == [C[2]]
    assert G2 not in store.sync_remove(G2, [C[2]])["guilds"]
    assert store.sync_remove(G1)["guilds"] == {}
    with pytest.raises(store.StoreError, match="not in the sync list"):
        store.sync_remove(G1)


@pytest.mark.parametrize("bad", ["general", ["general"], [123], "12"])
def test_sync_ids_must_be_snowflakes(bad):
    with pytest.raises(store.StoreError):
        store.sync_add(G1, "One", bad)


def test_corrupt_sync_list_is_reported(state):
    state.mkdir(parents=True, exist_ok=True)
    (state / "sync.json").write_text("{nope")
    with pytest.raises(store.StoreError, match="not valid JSON"):
        store.load_sync()


# --- reactions, embeds, deletions, roles ----------------------------------------------------------

ME = "100000000000000001"


def _msg(mid, **extra):
    return {"id": str(mid), "channel_id": C[0], "type": 0, "content": "x",
            "author": {"id": "100000000000000002", "username": "taro"}, **extra}


def test_an_old_mirror_gains_every_new_column():
    import sqlite3
    path = store.state_dir() / "mirror.db"
    old = sqlite3.connect(path)
    old.executescript("""
        CREATE TABLE guilds (id INTEGER PRIMARY KEY, name TEXT, updated INTEGER);
        CREATE TABLE channels (id INTEGER PRIMARY KEY, guild_id INTEGER, type INTEGER, name TEXT, parent_id INTEGER,
            recipients TEXT, last_message_id INTEGER, state TEXT, updated INTEGER);
        CREATE TABLE messages (id INTEGER PRIMARY KEY, channel_id INTEGER NOT NULL, guild_id INTEGER,
            author_id INTEGER, author_name TEXT, from_me INTEGER NOT NULL DEFAULT 0, content TEXT, reply_to INTEGER,
            attachments TEXT, embeds INTEGER NOT NULL DEFAULT 0, type INTEGER, edited TEXT);
        CREATE TABLE cursors (channel_id INTEGER PRIMARY KEY, newest INTEGER, oldest INTEGER,
            complete INTEGER NOT NULL DEFAULT 0, synced_at INTEGER);""")
    old.close()
    conn = store.connect(write=True)
    for table, columns in store.MIGRATIONS.items():
        have = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        assert set(columns) <= have
    assert conn.execute("SELECT COUNT(*) FROM roles").fetchone()[0] == 0


def test_reactions_and_embeds_are_stored_and_kept_by_partial_payloads():
    conn = store.connect(write=True)
    full = _msg(1 << 40, reactions=[{"emoji": {"name": "\U0001F44D"}, "count": 2, "me": True},
                                    {"emoji": {"name": "party", "id": "700000000000000001"}, "count": 1}],
                embeds=[{"title": "News", "description": "d" * 900, "provider": {"name": "Site"},
                         "fields": [{"name": "k", "value": "v"}] * 7}, {"type": "image"}])
    store.upsert_messages(conn, [store.message_row(full, ME)])
    stored = conn.execute("SELECT reactions, embed_data FROM messages").fetchone()
    assert json.loads(stored[0]) == [{"emoji": "\U0001F44D", "count": 2, "me": True},
                                     {"emoji": "party:700000000000000001", "count": 1, "me": False}]
    embed = json.loads(stored[1])
    assert len(embed) == 1 and embed[0]["site"] == "Site" and len(embed[0]["description"]) == 500
    assert len(embed[0]["fields"]) == 5
    # A search result omits reactions: the stored ones stay.
    store.upsert_messages(conn, [store.message_row({**full, "reactions": None}, ME, reactions=False)])
    assert json.loads(conn.execute("SELECT reactions FROM messages").fetchone()[0])[0]["count"] == 2
    # An ordinary read without reactions means there are none now.
    store.upsert_messages(conn, [store.message_row({**full, "reactions": None}, ME)])
    assert conn.execute("SELECT reactions FROM messages").fetchone()[0] is None


def test_adjust_reaction_counts_only_the_users_own():
    conn = store.connect(write=True)
    mid = 1 << 40
    store.upsert_messages(conn, [store.message_row(_msg(mid, reactions=[
        {"emoji": {"name": "a"}, "count": 2, "me": False}]), ME)])
    store.adjust_reaction(conn, mid, "a", True)
    store.adjust_reaction(conn, mid, "a", True)          # already mine: no double count
    store.adjust_reaction(conn, mid, "b", True)
    items = {r["emoji"]: r for r in json.loads(conn.execute("SELECT reactions FROM messages").fetchone()[0])}
    assert items["a"] == {"emoji": "a", "count": 3, "me": True} and items["b"]["count"] == 1
    store.adjust_reaction(conn, mid, "b", False)
    assert "b" not in {r["emoji"] for r in json.loads(conn.execute("SELECT reactions FROM messages").fetchone()[0])}


def test_drop_missing_deletes_only_inside_the_range():
    conn = store.connect(write=True)
    ids = [(1 << 40) + i for i in range(5)]
    store.upsert_messages(conn, [store.message_row(_msg(i), ME) for i in ids])
    assert store.drop_missing(conn, C[0], [ids[1], ids[3]], ids[1], ids[3]) == 1   # ids[2] gone
    left = [r[0] for r in conn.execute("SELECT id FROM messages ORDER BY id")]
    assert left == [ids[0], ids[1], ids[3], ids[4]]


def test_threads_keep_their_metadata():
    conn = store.connect(write=True)
    row = store.channel_row({"id": C[5], "type": 11, "name": "help", "parent_id": C[0], "guild_id": G1,
                             "message_count": 4, "thread_metadata": {"archived": True, "locked": False}})
    store.upsert_channel(conn, row, 0)
    store.upsert_channel(conn, store.channel_row({"id": C[5], "type": 11, "name": "help", "guild_id": G1}), 1)
    meta = json.loads(conn.execute("SELECT thread FROM channels").fetchone()[0])
    assert meta["archived"] is True and meta["messages"] == 4


def test_roles_and_members():
    conn = store.connect(write=True)
    store.upsert_guild(conn, G1, "One", 0, owner=False)
    store.upsert_guild(conn, G1, "One", 1)                      # owner unknown: kept
    assert conn.execute("SELECT owner FROM guilds").fetchone()[0] == 0
    roles = [{"id": G1, "name": "@everyone", "position": 0, "permissions": "1024"},
             {"id": "600000000000000001", "name": "Mod", "position": 2, "permissions": "8192",
              "colors": {"primary_color": 255}}]
    store.replace_roles(conn, G1, roles, {"600000000000000001": 3}, 100)
    rows = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM roles")}
    assert rows[600000000000000001]["members"] == 3 and rows[600000000000000001]["color"] == 255
    assert conn.execute("SELECT roles_at FROM guilds").fetchone()[0] == 100
    member = store.member_row({"user": {"id": ME, "username": "me"}, "roles": ["600000000000000001"]}, G1)
    store.upsert_member(conn, member, 1)
    store.member_role(conn, G1, ME, "600000000000000002", True, 2)
    assert json.loads(conn.execute("SELECT roles FROM members").fetchone()[0]) == [
        "600000000000000001", "600000000000000002"]
    store.delete_role(conn, G1, "600000000000000001")
    assert json.loads(conn.execute("SELECT roles FROM members").fetchone()[0]) == ["600000000000000002"]
    assert 600000000000000001 not in {r[0] for r in conn.execute("SELECT id FROM roles")}


perms = _load("discord_access_perms_test", ROOT / "perms.py")


def test_permission_names_round_trip_and_strong_ones():
    bits = perms.parse(["Send Messages", "manage-messages", "bit47"])
    assert perms.names(bits) == ["send_messages", "manage_messages", "bit47"]
    assert perms.strong(bits) == ["manage_messages"]
    with pytest.raises(perms.UnknownPermission, match="fly"):
        perms.parse(["fly"])


def test_base_permissions():
    assert perms.base(True, 0, []) == perms.ALL
    assert perms.base(False, 1 << 10, [1 << 3]) == perms.ALL
    assert perms.base(False, 1 << 10, [1 << 11, 1 << 13]) == (1 << 10) | (1 << 11) | (1 << 13)
