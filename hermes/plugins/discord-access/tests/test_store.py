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
