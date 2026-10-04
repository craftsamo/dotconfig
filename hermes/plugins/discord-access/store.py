"""discord-access store: the local mirror and the sync list.

Shared by the plugin (Hermes' own Python, read side) and the engine (its own venv, the only
writer that talks to Discord), so it is standard library only and runs on Python 3.12+.
Everything lives in one private state directory outside every repository: ``mirror.db`` (SQLite,
WAL) and ``sync.json`` (which servers and channels the sync agent follows besides the DMs).
Contract: docs/discord-access.md.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile

STATE_ENV = "HERMES_DISCORD_STATE"
DEFAULT_STATE = Path.home() / ".local" / "state" / "hermes-discord"

DISCORD_EPOCH_MS = 1420070400000
SNOWFLAKE = re.compile(r"^[0-9]{15,21}$")

# Channel types the mirror knows. Text-like guild channels are synced; threads are read live.
DM, GROUP_DM = 1, 3
GUILD_TEXT, GUILD_ANNOUNCEMENT = 0, 5
THREADS = {10, 11, 12}
TEXT_TYPES = {GUILD_TEXT, GUILD_ANNOUNCEMENT}
PRIVATE_TYPES = {DM, GROUP_DM}
READABLE_TYPES = TEXT_TYPES | PRIVATE_TYPES | THREADS

# Sync list bounds: every channel followed costs requests on every sync run, and the run is what
# Discord sees, so the bound is in code, not in the model's judgement.
MAX_GUILDS = 10
MAX_CHANNELS = 30          # explicit channels plus WHOLE_GUILD_CHANNELS per whole-server entry
WHOLE_GUILD_CHANNELS = 10  # a whole server follows its most recently active text channels

SCHEMA = """
CREATE TABLE IF NOT EXISTS guilds (
    id INTEGER PRIMARY KEY, name TEXT, updated INTEGER);
CREATE TABLE IF NOT EXISTS channels (
    id INTEGER PRIMARY KEY, guild_id INTEGER, type INTEGER, name TEXT, parent_id INTEGER,
    recipients TEXT, last_message_id INTEGER, state TEXT, updated INTEGER);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY, channel_id INTEGER NOT NULL, guild_id INTEGER, author_id INTEGER,
    author_name TEXT, from_me INTEGER NOT NULL DEFAULT 0, content TEXT, reply_to INTEGER,
    attachments TEXT, embeds INTEGER NOT NULL DEFAULT 0, type INTEGER, edited TEXT);
CREATE INDEX IF NOT EXISTS messages_channel ON messages (channel_id, id);
CREATE TABLE IF NOT EXISTS cursors (
    channel_id INTEGER PRIMARY KEY, newest INTEGER, oldest INTEGER, complete INTEGER NOT NULL DEFAULT 0,
    synced_at INTEGER);
CREATE TABLE IF NOT EXISTS sends (
    nonce TEXT PRIMARY KEY, channel_id INTEGER NOT NULL, text_hash TEXT NOT NULL, reply_to INTEGER,
    created INTEGER NOT NULL, status TEXT NOT NULL, message_id INTEGER, detail TEXT);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""


class StoreError(Exception):
    pass


class LimitError(StoreError):
    pass


# --- paths --------------------------------------------------------------------------------------

def state_dir(create: bool = True) -> Path:
    raw = os.environ.get(STATE_ENV)
    path = Path(raw).expanduser() if raw else DEFAULT_STATE
    if create:
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            os.chmod(path, 0o700)
        except OSError:
            pass
    return path


def db_path() -> Path:
    return state_dir(create=False) / "mirror.db"


def sync_path() -> Path:
    return state_dir(create=False) / "sync.json"


# --- snowflakes ---------------------------------------------------------------------------------

def is_snowflake(value) -> bool:
    return isinstance(value, str) and bool(SNOWFLAKE.match(value))


def snowflake_ms(value) -> int:
    return (int(value) >> 22) + DISCORD_EPOCH_MS


def snowflake_time(value) -> datetime:
    return datetime.fromtimestamp(snowflake_ms(value) / 1000, tz=timezone.utc)


def snowflake_at(when: datetime) -> int:
    """The smallest snowflake at ``when``: a time bound for after / before."""
    ms = int(when.timestamp() * 1000) - DISCORD_EPOCH_MS
    return max(ms, 0) << 22


# --- database -----------------------------------------------------------------------------------

def connect(write: bool = False) -> sqlite3.Connection:
    """A connection to the mirror. Readers open it read-only and never create it; the engine
    (the only writer) creates the schema."""
    path = db_path()
    if write:
        state_dir()
        conn = sqlite3.connect(path, timeout=15)
        os.chmod(path, 0o600)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA)
    else:
        if not path.exists():
            raise StoreError("the Discord mirror does not exist yet: the sync has never run")
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=15000")
    return conn


def get_meta(conn: sqlite3.Connection, key: str, default=None):
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    if row is None:
        return default
    try:
        return json.loads(row["value"])
    except ValueError:
        return default


def set_meta(conn: sqlite3.Connection, key: str, value) -> None:
    conn.execute("INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                 (key, json.dumps(value, ensure_ascii=False)))


# --- API objects -> rows ------------------------------------------------------------------------

def display_name(user: dict | None, member: dict | None = None) -> str | None:
    if member and member.get("nick"):
        return member["nick"]
    user = user or {}
    return user.get("global_name") or user.get("username") or None


def channel_row(c: dict, guild_id=None) -> dict:
    recipients = [{"id": str(u.get("id")), "name": display_name(u), "username": u.get("username")}
                  for u in c.get("recipients") or [] if isinstance(u, dict)]
    gid = c.get("guild_id") or guild_id
    return {"id": int(c["id"]), "guild_id": int(gid) if gid else None, "type": c.get("type"),
            "name": c.get("name") or None, "parent_id": int(c["parent_id"]) if c.get("parent_id") else None,
            "recipients": json.dumps(recipients, ensure_ascii=False) if recipients else None,
            "last_message_id": int(c["last_message_id"]) if c.get("last_message_id") else None}


def upsert_channel(conn: sqlite3.Connection, row: dict, now: int) -> None:
    conn.execute(
        "INSERT INTO channels (id, guild_id, type, name, parent_id, recipients, last_message_id, updated) "
        "VALUES (:id, :guild_id, :type, :name, :parent_id, :recipients, :last_message_id, :updated) "
        "ON CONFLICT(id) DO UPDATE SET guild_id = excluded.guild_id, type = excluded.type, "
        "name = excluded.name, parent_id = excluded.parent_id, "
        "recipients = COALESCE(excluded.recipients, channels.recipients), "
        "last_message_id = COALESCE(excluded.last_message_id, channels.last_message_id), "
        "updated = excluded.updated", {**row, "updated": now})


def upsert_guild(conn: sqlite3.Connection, gid, name, now: int) -> None:
    conn.execute("INSERT INTO guilds (id, name, updated) VALUES (?, ?, ?) ON CONFLICT(id) DO UPDATE SET "
                 "name = excluded.name, updated = excluded.updated", (int(gid), name, now))


def message_row(m: dict, me_id, guild_id=None) -> dict:
    author = m.get("author") or {}
    attachments = [{"name": a.get("filename"), "type": a.get("content_type"), "size": a.get("size"),
                    "url": a.get("url")} for a in m.get("attachments") or [] if isinstance(a, dict)]
    ref = m.get("message_reference") or {}
    gid = m.get("guild_id") or guild_id
    return {"id": int(m["id"]), "channel_id": int(m["channel_id"]), "guild_id": int(gid) if gid else None,
            "author_id": int(author["id"]) if author.get("id") else None,
            "author_name": display_name(author, m.get("member")),
            "from_me": int(bool(me_id) and str(author.get("id")) == str(me_id)),
            "content": m.get("content") or "",
            "reply_to": int(ref["message_id"]) if ref.get("message_id") and m.get("type") == 19 else None,
            "attachments": json.dumps(attachments, ensure_ascii=False) if attachments else None,
            "embeds": len(m.get("embeds") or []), "type": m.get("type"),
            "edited": m.get("edited_timestamp") or None}


def upsert_messages(conn: sqlite3.Connection, rows: list[dict]) -> None:
    conn.executemany(
        "INSERT INTO messages (id, channel_id, guild_id, author_id, author_name, from_me, content, reply_to, "
        "attachments, embeds, type, edited) VALUES (:id, :channel_id, :guild_id, :author_id, :author_name, "
        ":from_me, :content, :reply_to, :attachments, :embeds, :type, :edited) ON CONFLICT(id) DO UPDATE SET "
        "author_name = excluded.author_name, content = excluded.content, attachments = excluded.attachments, "
        "embeds = excluded.embeds, edited = excluded.edited", rows)


# --- sync list ----------------------------------------------------------------------------------

@contextmanager
def _sync_lock():
    state_dir()
    with open(state_dir() / "sync.json.lock", "a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def load_sync() -> dict:
    """``{"guilds": {guild_id: {"name", "channels": [ids], "exclude": [ids]}}}``; empty channels
    means the whole server (its WHOLE_GUILD_CHANNELS most recently active text channels)."""
    path = sync_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"guilds": {}}
    except ValueError as exc:
        raise StoreError(f"sync list {path} is not valid JSON; fix or remove it") from exc
    guilds = data.get("guilds") if isinstance(data, dict) else None
    if not isinstance(guilds, dict):
        raise StoreError(f"sync list {path} has no guilds mapping")
    out = {}
    for gid, entry in guilds.items():
        if not is_snowflake(gid) or not isinstance(entry, dict):
            continue
        out[gid] = {"name": entry.get("name") if isinstance(entry.get("name"), str) else None,
                    "channels": [c for c in entry.get("channels") or [] if is_snowflake(c)],
                    "exclude": [c for c in entry.get("exclude") or [] if is_snowflake(c)]}
    return {"guilds": out}


def _save_sync(data: dict) -> None:
    path = sync_path()
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".sync.", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def planned_channels(entry: dict) -> int:
    return len(entry["channels"]) if entry["channels"] else WHOLE_GUILD_CHANNELS


def check_limits(data: dict) -> None:
    guilds = data["guilds"]
    if len(guilds) > MAX_GUILDS:
        raise LimitError(f"at most {MAX_GUILDS} servers can be synced; remove one first")
    total = sum(planned_channels(e) for e in guilds.values())
    if total > MAX_CHANNELS:
        raise LimitError(
            f"that would follow {total} channels; the limit is {MAX_CHANNELS} (a whole server counts as "
            f"{WHOLE_GUILD_CHANNELS}). Name fewer channels or remove a server first")


def _ids(values, key: str) -> list[str]:
    if values in (None, ""):
        return []
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, list) or not all(is_snowflake(v) for v in values):
        raise StoreError(f"{key} must be channel ids (digits) from channels")
    return list(dict.fromkeys(values))


def sync_add(guild_id: str, name: str | None, channels=None, exclude=None) -> dict:
    """Follow a whole server (no channels) or named channels of it; returns the new list."""
    if not is_snowflake(guild_id):
        raise StoreError("guild must be a server id (digits) from guilds")
    channels, exclude = _ids(channels, "channels"), _ids(exclude, "exclude")
    with _sync_lock():
        data = load_sync()
        entry = data["guilds"].get(guild_id)
        if entry is None:
            entry = {"name": name, "channels": channels, "exclude": [] if channels else exclude}
        elif channels:
            if not entry["channels"]:
                raise StoreError("this whole server is already synced; to follow only some of its channels, "
                                 "remove the server first, then add those channels")
            entry = {**entry, "channels": list(dict.fromkeys(entry["channels"] + channels))}
        else:
            if entry["channels"]:
                raise StoreError(f"only {len(entry['channels'])} channel(s) of this server are synced; to follow "
                                 "the whole server, remove it first, then add it without channels")
            entry = {**entry, "exclude": list(dict.fromkeys(entry["exclude"] + exclude))}
        if name:
            entry["name"] = name
        candidate = {"guilds": {**data["guilds"], guild_id: entry}}
        check_limits(candidate)
        _save_sync(candidate)
        return candidate


def sync_remove(guild_id: str, channels=None) -> dict:
    """Stop following a server, or some channels of it (excluded, for a whole-server entry)."""
    if not is_snowflake(guild_id):
        raise StoreError("guild must be a server id (digits) from sync_list")
    channels = _ids(channels, "channels")
    with _sync_lock():
        data = load_sync()
        entry = data["guilds"].get(guild_id)
        if entry is None:
            raise StoreError("that server is not in the sync list")
        guilds = dict(data["guilds"])
        if not channels:
            guilds.pop(guild_id)
        elif entry["channels"]:
            kept = [c for c in entry["channels"] if c not in channels]
            if kept:
                guilds[guild_id] = {**entry, "channels": kept}
            else:
                guilds.pop(guild_id)
        else:
            guilds[guild_id] = {**entry, "exclude": list(dict.fromkeys(entry["exclude"] + channels))}
        candidate = {"guilds": guilds}
        _save_sync(candidate)
        return candidate
