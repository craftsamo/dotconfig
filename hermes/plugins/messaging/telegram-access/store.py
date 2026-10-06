"""telegram-access store: the local mirror of the user's own Telegram account.

Shared by the sync agent (``sync.py``, the only process that talks to Telegram, on the engine
venv) and the plugin (``tg.py``, Hermes' own Python), so it is standard library only and runs on
Python 3.12+. Everything lives in one private state directory outside every repository (mode 700,
excluded from Time Machine by the launcher): ``telethon.session`` (Telethon's entity cache and update
state; the auth key is never written there, it lives in the Keychain), ``mirror.db`` (SQLite,
WAL), ``sync.json`` (the sync list), ``telegram.sock`` (the agent's socket), ``outbox/`` and
``incoming/`` (short-lived file copies).

What the mirror holds: every chat Telegram lists for the account (name, kind, unread count, last
activity), and the messages of the chats it keeps current — private chats, bots and basic groups
always, supergroups and channels only while they are on the sync list. A chat that leaves the
sync list loses its messages here.

Retention, as the user chose it (the signal-access rules): a message that disappears on the
chat's auto-delete timer, and a self-destructing (view-once) photo or video, stays here with its
text and the file the agent kept (``kept/``), marked expired when it is read back; a message
deleted on Telegram is removed with its kept file. Contract: docs/telegram-access.md.
"""

from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import time

STATE_ENV = "HERMES_TELEGRAM_STATE"
DEFAULT_STATE = Path.home() / ".local" / "state" / "hermes-telegram"

# Kinds of chat. Private chats, bots, basic groups and Saved Messages are always mirrored;
# supergroups and channels only while they are on the sync list.
ALWAYS = ("user", "bot", "group", "self")
LISTED = ("supergroup", "channel")
KINDS = ALWAYS + LISTED

CHAT_ID = re.compile(r"^-?[0-9]{1,20}$")
CHANNEL_BASE = 1_000_000_000_000      # Telethon's marked ids: channels are -(10**12 + id)

SYNC_MAX = 30                         # chats on the sync list
DELETE_GRACE = 5 * 60 * 1000          # a delete this close to a message's auto-delete time is the timer's

# Archives and programs: never kept, saved or sent (the signal-access rules, plus animated .tgs
# stickers, which are gzip).
RISKY_MIME = re.compile(r"zip|rar|7z|tar|gzip|bzip|x-xz|compressed|archive|java-archive|android\.package"
                        r"|msdownload|msdos|x-executable|x-mach|x-sh\b|x-shellscript|javascript|vbscript"
                        r"|x-apple-diskimage|x-iso|x-elf|x-sharedlib|x-object|x-python|x-ruby|x-perl|x-php"
                        r"|x-script|x-tcl|x-lua|x-applescript|x-msi|x-bat", re.IGNORECASE)
RISKY_FILES = re.compile(r"\.(?:zip|rar|7z|tar|gz|tgz|bz2|xz|zst|lz|lzma|cab|apk|aab|ipa|exe|msi|msp|dmg|pkg|mpkg"
                         r"|iso|img|jar|war|class|scr|bat|cmd|com|cpl|hta|lnk|reg|inf|msc|wsf|wsh|js|jse|mjs|cjs"
                         r"|vbs|vbe|ps1|psm1|sh|bash|zsh|fish|ksh|csh|command|tool|app|workflow|terminal"
                         r"|applescript|scpt|scptd|py|pyc|pyw|rb|pl|php|lua|tcl|dylib|so|dll|bin|run|deb|rpm"
                         r"|appimage|kext|plugin|prefpane|xpi|crx|tgs)$", re.IGNORECASE)

SCHEMA = """
CREATE TABLE IF NOT EXISTS chats (
    id INTEGER PRIMARY KEY, kind TEXT NOT NULL, name TEXT, username TEXT, phone TEXT,
    unread INTEGER NOT NULL DEFAULT 0, read_max INTEGER, top_id INTEGER, last_ts INTEGER,
    ttl INTEGER, archived INTEGER NOT NULL DEFAULT 0, left_chat INTEGER NOT NULL DEFAULT 0,
    can_send INTEGER, members INTEGER, seeded INTEGER NOT NULL DEFAULT 0, updated INTEGER);
CREATE TABLE IF NOT EXISTS messages (
    chat INTEGER NOT NULL, id INTEGER NOT NULL, ts INTEGER NOT NULL,
    from_me INTEGER NOT NULL DEFAULT 0, sender INTEGER, sender_name TEXT,
    kind TEXT NOT NULL DEFAULT 'message', body TEXT, media TEXT, reply_to INTEGER, fwd_from TEXT,
    edited INTEGER, expires INTEGER, grouped INTEGER, received INTEGER,
    PRIMARY KEY (chat, id));
CREATE INDEX IF NOT EXISTS messages_ts ON messages (chat, ts);
CREATE INDEX IF NOT EXISTS messages_expires ON messages (expires) WHERE expires IS NOT NULL;
CREATE TABLE IF NOT EXISTS deleted (chat INTEGER, id INTEGER NOT NULL, at INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS deleted_id ON deleted (id);
CREATE TABLE IF NOT EXISTS gaps (start INTEGER NOT NULL, until INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""
GAP_TTL = 30 * 86400 * 1000           # how long a gap in watching is remembered
SETTLE = 10 * 60 * 1000               # after a gap, how long the catch-up of what it held may take
TOMBSTONE_TTL = 2 * 86400 * 1000      # how long a delete fences out a history fetch that started before it

MESSAGE_FIELDS = ("chat", "id", "ts", "from_me", "sender", "sender_name", "kind", "body", "media",
                  "reply_to", "fwd_from", "edited", "expires", "grouped")
CHAT_FIELDS = ("kind", "name", "username", "phone", "unread", "read_max", "top_id", "last_ts", "ttl",
               "archived", "left_chat", "can_send", "members")


class StoreError(Exception):
    pass


# --- paths --------------------------------------------------------------------------------------

def state_dir(create: bool = False) -> Path:
    raw = os.environ.get(STATE_ENV)
    path = Path(raw).expanduser() if raw else DEFAULT_STATE
    if create:
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(path, 0o700)
    return path


def db_path(state: Path | None = None) -> Path:
    return (state or state_dir()) / "mirror.db"


def session_path(state: Path | None = None) -> Path:
    return (state or state_dir()) / "telethon.session"  # SQLiteSession insists on the .session suffix


def socket_path(state: Path | None = None) -> Path:
    return (state or state_dir()) / "telegram.sock"


def sync_path(state: Path | None = None) -> Path:
    return (state or state_dir()) / "sync.json"


def outbox_dir(state: Path | None = None) -> Path:
    return (state or state_dir()) / "outbox"


def incoming_dir(state: Path | None = None) -> Path:
    return (state or state_dir()) / "incoming"


def kept_dir(state: Path | None = None) -> Path:
    return (state or state_dir()) / "kept"


def kept_path(chat: int, msg_id: int, state: Path | None = None) -> Path:
    """The folder holding the file the agent kept of one disappearing message."""
    return kept_dir(state) / str(chat) / str(msg_id)


def kept_file(chat: int, msg_id: int, state: Path | None = None) -> Path | None:
    """The one plain file kept for a message; None when absent or when anything on the way is a
    link (the kept tree is the agent's, and nothing in it may lead elsewhere)."""
    base = kept_dir(state)
    folder = kept_path(chat, msg_id, state)
    if any(part.is_symlink() for part in (base, folder.parent, folder)):
        return None
    try:
        files = [f for f in folder.iterdir() if f.is_file() and not f.is_symlink() and not f.name.startswith(".")]
    except OSError:
        return None
    return files[0] if len(files) == 1 else None


def remove_kept(chat: int, msg_id: int | None = None, state: Path | None = None) -> None:
    import shutil
    target = kept_dir(state) / str(chat) if msg_id is None else kept_path(chat, msg_id, state)
    shutil.rmtree(target, ignore_errors=True)


# --- connection ---------------------------------------------------------------------------------

def connect(path: Path | None = None, *, write: bool = False) -> sqlite3.Connection:
    """The mirror. Only the sync agent writes (and creates) it; a reader of a mirror that does not
    exist yet gets StoreError. Readers are ``query_only`` but open read-write, because a WAL
    database cannot be opened read-only once its ``-shm`` file is gone."""
    path = path or db_path()
    if not write and not path.exists():
        raise StoreError("no Telegram mirror yet: the account is not logged in or sync never ran")
    old = os.umask(0o077)
    try:
        conn = sqlite3.connect(str(path), timeout=10, isolation_level=None)
    finally:
        os.umask(old)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 10000")
    if write:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(SCHEMA)
    else:
        conn.execute("PRAGMA query_only = ON")
    return conn


def get_meta(conn: sqlite3.Connection) -> dict:
    return {row["key"]: row["value"] for row in conn.execute("SELECT key, value FROM meta")}


def set_meta(conn: sqlite3.Connection, **values) -> None:
    for key, value in values.items():
        conn.execute("INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT (key) DO UPDATE SET value = "
                     "excluded.value", (key, None if value is None else str(value)))


def now_ms() -> int:
    return int(time.time() * 1000)


def local_time(ms) -> str | None:
    if not isinstance(ms, int) or isinstance(ms, bool) or ms <= 0:
        return None
    return datetime.fromtimestamp(ms / 1000).astimezone().isoformat(timespec="seconds")


# --- identities ---------------------------------------------------------------------------------

def parse_chat(value) -> int | None:
    """A chat id as Telethon marks it (a person or bot > 0, a basic group < 0, a supergroup or
    channel -100…), from an int or its decimal string; None for anything else."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value != 0 else None
    if isinstance(value, str) and CHAT_ID.match(value.strip()):
        number = int(value.strip())
        return number if number != 0 else None
    return None


def is_channel_id(chat: int) -> bool:
    return chat < -CHANNEL_BASE


def marked_id(kind: str, raw_id: int) -> int:
    """Telethon's marked peer id from the bare id of a User, Chat or Channel."""
    if kind in ("user", "bot", "self"):
        return raw_id
    if kind == "group":
        return -raw_id
    return -(CHANNEL_BASE + raw_id)


def mirrored(kind: str | None, chat: int, synced) -> bool:
    return kind in ALWAYS or (kind in LISTED and chat in synced)


# --- sync list ----------------------------------------------------------------------------------

def read_sync_list(state: Path | None = None) -> list[int]:
    """The supergroups and channels to mirror; a missing or unreadable file is an empty list."""
    try:
        data = json.loads(sync_path(state).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    chats = data.get("chats") if isinstance(data, dict) else None
    out = []
    for value in chats if isinstance(chats, list) else []:
        chat = parse_chat(value)
        if chat is not None and chat not in out:
            out.append(chat)
    return out[:SYNC_MAX]


def write_sync_list(chats: list[int], state: Path | None = None) -> None:
    """Atomic replace, so the agent never reads half a file."""
    if len(chats) > SYNC_MAX:
        raise StoreError(f"at most {SYNC_MAX} chats on the sync list")
    base = state_dir(create=True) if state is None else state
    target = sync_path(base)
    fd, tmp = tempfile.mkstemp(dir=str(base), prefix=".sync-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump({"chats": chats}, handle)
        os.chmod(tmp, 0o600)
        os.replace(tmp, target)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


# --- writes (the sync agent) --------------------------------------------------------------------

def upsert_chat(conn: sqlite3.Connection, chat: int, **fields) -> None:
    """Insert or update one chat; only the fields given change (None leaves a field as it is,
    except ``left_chat`` / ``archived`` / ``can_send``, which are taken as given)."""
    values = {k: v for k, v in fields.items() if k in CHAT_FIELDS}
    if "kind" not in values or values["kind"] not in KINDS:
        row = conn.execute("SELECT kind FROM chats WHERE id = ?", (chat,)).fetchone()
        if row is None:
            raise StoreError(f"a new chat needs a kind (got {values.get('kind')!r})")
        values["kind"] = row["kind"]
    columns = ["id", *values, "updated"]
    params = [chat, *values.values(), now_ms()]
    updates = []
    for key in values:
        if key in ("left_chat", "archived", "can_send", "unread", "read_max"):
            updates.append(f"{key} = excluded.{key}")
        elif key in ("top_id", "last_ts"):
            updates.append(f"{key} = MAX(COALESCE(chats.{key}, 0), COALESCE(excluded.{key}, 0))")
        else:
            updates.append(f"{key} = COALESCE(excluded.{key}, chats.{key})")
    updates.append("updated = excluded.updated")
    conn.execute(f"INSERT INTO chats ({', '.join(columns)}) VALUES ({', '.join('?' * len(columns))}) "
                 f"ON CONFLICT (id) DO UPDATE SET {', '.join(updates)}", params)


def touch_chat(conn: sqlite3.Connection, chat: int, msg_id: int, ts: int, *, incoming: bool) -> None:
    """A new message went by in a known chat: its activity and, for an unread incoming one, the
    unread count."""
    row = conn.execute("SELECT top_id, read_max FROM chats WHERE id = ?", (chat,)).fetchone()
    if row is None:
        return
    newer = msg_id > (row["top_id"] or 0)
    bump = incoming and newer and msg_id > (row["read_max"] or 0)
    conn.execute("UPDATE chats SET top_id = MAX(COALESCE(top_id, 0), ?), last_ts = MAX(COALESCE(last_ts, 0), ?), "
                 "unread = unread + ?, updated = ? WHERE id = ?", (msg_id, ts, int(bump), now_ms(), chat))


def set_read(conn: sqlite3.Connection, chat: int, max_id: int, still_unread: int | None) -> None:
    """The user read a chat on one of their devices (Telegram's read sync)."""
    conn.execute("UPDATE chats SET read_max = MAX(COALESCE(read_max, 0), ?), unread = COALESCE(?, unread), "
                 "updated = ? WHERE id = ?", (max_id, still_unread, now_ms(), chat))


def is_deleted(conn: sqlite3.Connection, chat: int, msg_id: int) -> bool:
    """A delete was seen for this message: a history fetch or a late edit never brings it back."""
    if conn.execute("SELECT 1 FROM deleted WHERE id = ? AND chat = ?", (msg_id, chat)).fetchone():
        return True
    return chat >= -CHANNEL_BASE and bool(conn.execute(
        "SELECT 1 FROM deleted WHERE id = ? AND chat IS NULL", (msg_id,)).fetchone())


def upsert_message(conn: sqlite3.Connection, row: dict, now: int | None = None) -> bool:
    """One message as the agent normalised it (``MESSAGE_FIELDS``; ``media`` a dict or None). A
    message seen again (an edit, a refetch) replaces what was stored, except the time it expired
    (an expired message stays expired). A deleted message is not stored; returns whether the row
    was written."""
    values = {k: row.get(k) for k in MESSAGE_FIELDS}
    if not isinstance(values["chat"], int) or not isinstance(values["id"], int) or not isinstance(values["ts"], int):
        raise StoreError("a message needs an integer chat, id and ts")
    if is_deleted(conn, values["chat"], values["id"]):
        return False
    if isinstance(values["media"], (dict, list)):
        values["media"] = json.dumps(values["media"], ensure_ascii=False)
    values["from_me"] = int(bool(values["from_me"]))
    values["kind"] = values["kind"] or "message"
    columns = [*values, "received"]
    params = [*values.values(), now_ms()]
    conn.execute(f"INSERT INTO messages ({', '.join(columns)}) VALUES ({', '.join('?' * len(columns))}) "
                 "ON CONFLICT (chat, id) DO UPDATE SET " +
                 ", ".join(f"{k} = excluded.{k}" for k in MESSAGE_FIELDS
                           if k not in ("chat", "id", "received", "expires")) +
                 ", expires = CASE WHEN messages.expires IS NOT NULL AND messages.expires <= ? THEN messages.expires "
                 "ELSE excluded.expires END",
                 [*params, now if now is not None else now_ms()])
    return True


def record_gap(conn: sqlite3.Connection, start: int, until: int) -> None:
    """A stretch the agent did not watch (down, asleep, stalled, reconnecting): deletes made in it
    may arrive late and out of their time."""
    conn.execute("INSERT INTO gaps (start, until) VALUES (?, ?)", (max(0, int(start)), int(until)))


def gaps(conn: sqlite3.Connection) -> list[tuple[int, int]]:
    return [(r["start"], r["until"]) for r in conn.execute("SELECT start, until FROM gaps")]


def expiry_delete(expires: int | None, now: int, unwatched: list[tuple[int, int]] | None = None) -> bool:
    """Whether a delete of a message on an auto-delete timer is its expiry rather than a delete
    for everyone. Official clients expire such messages by their own timer; whether Telegram also
    sends a delete then is not documented, and its deletes carry no time. So a delete counts as
    the expiry only when it arrives within ``DELETE_GRACE`` of the timer, and the timer did not
    run out inside a gap in watching (``unwatched``; each gap extended by ``SETTLE`` for the
    catch-up after it), where a delete for everyone made earlier could have been held back until
    then. Anything earlier is a delete for everyone; anything later cannot be told apart, and a
    delete for everyone outranks keeping, so it removes too."""
    if expires is None or not expires - DELETE_GRACE <= now <= expires + DELETE_GRACE:
        return False
    edge = expires - DELETE_GRACE
    return not any(start < edge < until + SETTLE for start, until in unwatched or [])


def delete_messages(conn: sqlite3.Connection, ids: list[int], chat: int | None = None,
                    state: Path | None = None, now: int | None = None, *,
                    unwatched: list[tuple[int, int]] | None = None) -> int:
    """Messages deleted on Telegram. Without a chat (private chats and basic groups, whose message
    ids are unique per account) every non-channel chat is matched.

    The delete of a disappearing message at its time is its disappearing, not a delete
    (``expiry_delete``): the message is kept and marked expired from now on. A view-once photo or
    video expires by its media (Telegram serves it without the file afterwards), never by a
    delete, so its delete is a delete — unless it also carries the chat's timer, which then decides. Every other message is removed with its kept file and leaves a tombstone
    for ``TOMBSTONE_TTL``, so a history fetch already in flight cannot bring it back. Returns how
    many were removed."""
    now = now if now is not None else now_ms()
    count = 0
    for msg_id in ids:
        if not isinstance(msg_id, int):
            continue
        if chat is not None:
            rows = conn.execute("SELECT chat, id, expires, media FROM messages WHERE chat = ? AND id = ?",
                                (chat, msg_id)).fetchall()
        else:
            rows = conn.execute("SELECT chat, id, expires, media FROM messages WHERE id = ? AND chat >= ?",
                                (msg_id, -CHANNEL_BASE)).fetchall()
        kept_any = False
        for row in rows:
            if expiry_delete(row["expires"], now, unwatched):
                conn.execute("UPDATE messages SET expires = MIN(COALESCE(expires, ?), ?) WHERE chat = ? AND id = ?",
                             (now, now, row["chat"], row["id"]))
                kept_any = True
                continue
            conn.execute("DELETE FROM messages WHERE chat = ? AND id = ?", (row["chat"], row["id"]))
            remove_kept(row["chat"], row["id"], state)
            count += 1
        if not kept_any:
            conn.execute("INSERT INTO deleted (chat, id, at) VALUES (?, ?, ?)", (chat, msg_id, now))
    return count


def purge_tombstones(conn: sqlite3.Connection, now: int | None = None) -> int:
    """Tombstones past their fence and gaps past ``GAP_TTL``. Expired messages are never purged:
    they stay, marked."""
    now = now if now is not None else now_ms()
    conn.execute("DELETE FROM gaps WHERE until <= ?", (now - GAP_TTL,))
    return conn.execute("DELETE FROM deleted WHERE at <= ?", (now - TOMBSTONE_TTL,)).rowcount


def drop_chat(conn: sqlite3.Connection, chat: int, state: Path | None = None) -> int:
    """A chat the mirror no longer keeps current loses its messages, kept files and seed mark."""
    cur = conn.execute("DELETE FROM messages WHERE chat = ?", (chat,))
    conn.execute("UPDATE chats SET seeded = 0 WHERE id = ?", (chat,))
    remove_kept(chat, None, state)
    return cur.rowcount


def drop_unlisted(conn: sqlite3.Connection, synced, state: Path | None = None) -> int:
    """Supergroups and channels off the sync list lose their messages (the list may have changed
    while the agent was down)."""
    count = 0
    for row in conn.execute(f"SELECT id FROM chats WHERE kind IN ({','.join('?' * len(LISTED))})", LISTED).fetchall():
        if row["id"] not in synced:
            count += drop_chat(conn, row["id"], state)
    return count


# --- reads --------------------------------------------------------------------------------------

def media_of(row) -> dict | None:
    raw = row["media"] if not isinstance(row, dict) else row.get("media")
    if isinstance(raw, dict):
        return raw
    if not raw:
        return None
    try:
        value = json.loads(raw)
    except ValueError:
        return None
    return value if isinstance(value, dict) else None
