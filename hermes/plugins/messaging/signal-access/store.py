"""signal-access store: the local mirror of the user's Signal account.

Shared by the sync agent (``sync.py``, the only reader of Signal's message stream) and the
plugin (``sig.py``, Hermes' own Python), so it is standard library only and runs on Python 3.12+.
Everything lives in one private state directory outside every repository (mode 700, excluded
from Time Machine by the launcher): ``signal-cli/`` (signal-cli's data: keys and received
attachments), ``signal-cli.sock`` (the daemon's JSON-RPC socket) and ``mirror.db`` (SQLite, WAL).

Retention, as the user chose it: a message that disappears on a timer stays here, marked
expired when it is read back; a message its sender deleted for everyone is removed with its
files, its earlier versions, its reactions and every quote of it. Contract: docs/signal-access.md.
"""

from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import re
import sqlite3
import time

STATE_ENV = "HERMES_SIGNAL_STATE"
DEFAULT_STATE = Path.home() / ".local" / "state" / "hermes-signal"

UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
GROUP_ID = re.compile(r"^[A-Za-z0-9+/]{42,43}={0,2}$")
GROUP_PREFIX = "group:"

SCHEMA = """
CREATE TABLE IF NOT EXISTS chats (
    id TEXT PRIMARY KEY, kind TEXT NOT NULL, name TEXT, number TEXT, members TEXT,
    member INTEGER NOT NULL DEFAULT 1, expires_in INTEGER, last_ts INTEGER, updated INTEGER);
CREATE TABLE IF NOT EXISTS messages (
    chat TEXT NOT NULL, author TEXT NOT NULL, ts INTEGER NOT NULL,
    from_me INTEGER NOT NULL DEFAULT 0, author_name TEXT, kind TEXT NOT NULL DEFAULT 'message',
    body TEXT, attachments TEXT, quote TEXT, sticker INTEGER NOT NULL DEFAULT 0, other TEXT,
    expires_in INTEGER NOT NULL DEFAULT 0, expire_start INTEGER, read_at INTEGER,
    view_once INTEGER NOT NULL DEFAULT 0, edited INTEGER, received INTEGER, mentions TEXT,
    PRIMARY KEY (author, ts));
CREATE INDEX IF NOT EXISTS messages_chat ON messages (chat, ts);
CREATE TABLE IF NOT EXISTS edits (
    author TEXT NOT NULL, ts INTEGER NOT NULL, rev_ts INTEGER NOT NULL, body TEXT, attachments TEXT,
    mentions TEXT, PRIMARY KEY (author, ts, rev_ts));
CREATE TABLE IF NOT EXISTS reactions (
    author TEXT NOT NULL, ts INTEGER NOT NULL, reactor TEXT NOT NULL, emoji TEXT, at INTEGER,
    PRIMARY KEY (author, ts, reactor));
CREATE TABLE IF NOT EXISTS contacts (
    uuid TEXT PRIMARY KEY, number TEXT, name TEXT, profile_name TEXT, username TEXT,
    blocked INTEGER NOT NULL DEFAULT 0, updated INTEGER);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""
# Columns added after the first mirrors were written: (table, column, type).
ADDED_COLUMNS = (("messages", "mentions", "TEXT"), ("edits", "mentions", "TEXT"))
# Where Signal puts a mention in a message's text; the mention itself travels beside the text.
MENTION = "\ufffc"


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


def data_dir(state: Path | None = None) -> Path:
    return (state or state_dir()) / "signal-cli"


def socket_path(state: Path | None = None) -> Path:
    return (state or state_dir()) / "signal-cli.sock"


def db_path(state: Path | None = None) -> Path:
    return (state or state_dir()) / "mirror.db"


def attachment_file(att_id: str, state: Path | None = None) -> Path | None:
    """signal-cli's local copy of a received attachment, or None for an id that is not a plain name."""
    if not isinstance(att_id, str) or not att_id or "/" in att_id or att_id.startswith("."):
        return None
    return data_dir(state) / "attachments" / att_id


def linked_account(state: Path | None = None) -> dict | None:
    """``{number, uuid, path, registered}`` of the one account in signal-cli's data, or None.

    Read from signal-cli's own files (``data/accounts.json`` and the account file it names), so
    no daemon and no network is needed; ``registered`` is False once Signal unlinked the device."""
    base = data_dir(state) / "data"
    try:
        listing = json.loads((base / "accounts.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    accounts = [a for a in listing.get("accounts") or [] if isinstance(a, dict) and a.get("number")]
    if not accounts:
        return None
    if len(accounts) > 1:
        raise StoreError("signal-cli holds more than one account; signal-access supports exactly one")
    account = accounts[0]
    registered = None
    if account.get("path"):
        try:
            detail = json.loads((base / str(account["path"])).read_text(encoding="utf-8"))
            if isinstance(detail.get("registered"), bool):
                registered = detail["registered"]
        except (OSError, ValueError):
            pass
    return {"number": account["number"], "uuid": (account.get("uuid") or "").lower() or None,
            "path": account.get("path"), "registered": registered}


# --- connection ---------------------------------------------------------------------------------

def connect(path: Path | None = None, *, write: bool = False) -> sqlite3.Connection:
    """The mirror. Writers (the sync agent, a recorded send) create it; a reader of a mirror that
    does not exist yet gets StoreError. Readers are ``query_only`` but open read-write, because a
    WAL database cannot be opened read-only once its ``-shm`` file is gone."""
    path = path or db_path()
    if not write and not path.exists():
        raise StoreError("no Signal mirror yet: the account is not linked or sync never ran")
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
        _add_columns(conn)
    else:
        conn.execute("PRAGMA query_only = ON")
    return conn


def _add_columns(conn: sqlite3.Connection) -> None:
    """Bring an older mirror up to the current schema; existing rows keep NULL there."""
    for table, column, kind in ADDED_COLUMNS:
        if column not in {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}:
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {kind}")
            except sqlite3.OperationalError as exc:  # the other writer added it first
                if "duplicate column" not in str(exc):
                    raise


def column(row: sqlite3.Row, name: str):
    """A column a reader may find missing: a mirror no writer has opened since it was added."""
    return row[name] if name in row.keys() else None


def get_meta(conn: sqlite3.Connection) -> dict:
    return {row["key"]: row["value"] for row in conn.execute("SELECT key, value FROM meta")}


def set_meta(conn: sqlite3.Connection, **values) -> None:
    for key, value in values.items():
        conn.execute("INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT (key) DO UPDATE SET value = "
                     "excluded.value", (key, None if value is None else str(value)))


def now_ms() -> int:
    return int(time.time() * 1000)


# --- identities ---------------------------------------------------------------------------------

def group_chat(group_id: str) -> str:
    return GROUP_PREFIX + group_id


def is_group(chat: str) -> bool:
    return chat.startswith(GROUP_PREFIX)


def valid_chat(chat: str) -> bool:
    if not isinstance(chat, str):
        return False
    if is_group(chat):
        return bool(GROUP_ID.match(chat[len(GROUP_PREFIX):]))
    return bool(UUID.match(chat))


def _uuid(value) -> str | None:
    text = (value or "").lower() if isinstance(value, str) else ""
    return text if UUID.match(text) else None


def _contact_uuid(conn: sqlite3.Connection, number) -> str | None:
    if not isinstance(number, str) or not number:
        return None
    row = conn.execute("SELECT uuid FROM contacts WHERE number = ?", (number,)).fetchone()
    return row["uuid"] if row else None


# --- ingest -------------------------------------------------------------------------------------

def _attachments(items) -> list[dict]:
    out = []
    for a in items or []:
        if not isinstance(a, dict):
            continue
        entry = {"id": a.get("id"), "type": a.get("contentType"), "name": a.get("filename"),
                 "size": a.get("size")}
        if a.get("caption"):
            entry["caption"] = a["caption"]
        if a.get("isVoiceNote"):
            entry["voice"] = True
        out.append({k: v for k, v in entry.items() if v is not None})
    return out


def _mention_list(items) -> list[dict]:
    """signal-cli's mentions (``{number, uuid, start, length}``), in text order, account id or number only."""
    out = []
    for m in items or []:
        if not isinstance(m, dict) or not isinstance(m.get("start"), int):
            continue
        entry = {"start": m["start"], "uuid": _uuid(m.get("uuid")),
                 "number": m.get("number") if isinstance(m.get("number"), str) else None}
        out.append({k: v for k, v in entry.items() if v is not None})
    return sorted(out, key=lambda m: m["start"])


def _mentions(items) -> str | None:
    found = _mention_list(items)
    return json.dumps(found, ensure_ascii=False) if found else None


def _quote(q) -> str | None:
    if not isinstance(q, dict) or not isinstance(q.get("id"), int):
        return None
    quote = {"id": q["id"], "author": _uuid(q.get("authorUuid")), "text": q.get("text")}
    mentions = _mention_list(q.get("mentions"))
    if mentions:
        quote["mentions"] = mentions
    return json.dumps(quote, ensure_ascii=False)


OTHER_KINDS = ("pollCreate", "contacts", "payment", "pollVote", "pollTerminate", "pinMessage")


def _touch_chat(conn, chat: str, ts: int, *, name: str | None = None, number: str | None = None) -> None:
    kind = "group" if is_group(chat) else "person"
    conn.execute(
        "INSERT INTO chats (id, kind, name, number, last_ts, updated) VALUES (?, ?, ?, ?, ?, ?) "
        "ON CONFLICT (id) DO UPDATE SET last_ts = MAX(COALESCE(chats.last_ts, 0), excluded.last_ts), "
        "name = COALESCE(chats.name, excluded.name), number = COALESCE(chats.number, excluded.number)",
        (chat, kind, name, number, ts, now_ms()))


def _store_message(conn, *, chat: str, author: str, from_me: bool, author_name, data: dict,
                   received: int) -> str | None:
    """One data message (incoming or a sent transcript); returns what it was, None when skipped."""
    ts = data.get("timestamp")
    if not isinstance(ts, int):
        return None
    expires = data.get("expiresInSeconds") if isinstance(data.get("expiresInSeconds"), int) else 0
    if data.get("isExpirationUpdate"):
        conn.execute("UPDATE chats SET expires_in = ? WHERE id = ?", (expires, chat))
        _touch_chat(conn, chat, ts)
        conn.execute(
            "INSERT OR IGNORE INTO messages (chat, author, ts, from_me, author_name, kind, expires_in, received) "
            "VALUES (?, ?, ?, ?, ?, 'timer', ?, ?)", (chat, author, ts, int(from_me), author_name, expires, received))
        return "timer"
    body = data.get("message") if isinstance(data.get("message"), str) else None
    attachments = _attachments(data.get("attachments"))
    sticker = isinstance(data.get("sticker"), dict)
    other = next((k for k in OTHER_KINDS if data.get(k)), None)
    if not (body or attachments or sticker or other):
        return None
    _touch_chat(conn, chat, ts)
    conn.execute(
        "INSERT INTO messages (chat, author, ts, from_me, author_name, body, attachments, quote, sticker, other, "
        "expires_in, expire_start, view_once, received, mentions) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT (author, ts) DO NOTHING",
        (chat, author, ts, int(from_me), author_name, body,
         json.dumps(attachments, ensure_ascii=False) if attachments else None, _quote(data.get("quote")),
         int(sticker), other, expires, ts if (from_me and expires) else None, int(bool(data.get("viewOnce"))),
         received, _mentions(data.get("mentions"))))
    return "message"


def _find(conn, author: str, ts: int) -> sqlite3.Row | None:
    """A message by its Signal identity, also when ``ts`` names one of its later revisions."""
    row = conn.execute("SELECT * FROM messages WHERE author = ? AND ts = ?", (author, ts)).fetchone()
    if row:
        return row
    row = conn.execute("SELECT * FROM messages WHERE author = ? AND edited = ?", (author, ts)).fetchone()
    if row:
        return row
    hit = conn.execute("SELECT ts FROM edits WHERE author = ? AND rev_ts = ?", (author, ts)).fetchone()
    if hit:
        return conn.execute("SELECT * FROM messages WHERE author = ? AND ts = ?", (author, hit["ts"])).fetchone()
    return None


def _edit(conn, *, chat: str, author: str, from_me: bool, author_name, edit: dict, received: int) -> str | None:
    target = edit.get("targetSentTimestamp")
    data = edit.get("dataMessage") or {}
    if not isinstance(target, int) or not isinstance(data.get("timestamp"), int):
        return None
    row = _find(conn, author, target)
    if row is None:  # the original never reached the mirror: keep the edited version
        return _store_message(conn, chat=chat, author=author, from_me=from_me, author_name=author_name,
                              data={**data, "timestamp": target}, received=received) and "edit"
    rev = row["edited"] or row["ts"]
    conn.execute("INSERT OR IGNORE INTO edits (author, ts, rev_ts, body, attachments, mentions) "
                 "VALUES (?, ?, ?, ?, ?, ?)",
                 (author, row["ts"], rev, row["body"], row["attachments"], row["mentions"]))
    attachments = _attachments(data.get("attachments"))
    conn.execute("UPDATE messages SET body = ?, attachments = COALESCE(?, attachments), edited = ?, mentions = ? "
                 "WHERE author = ? AND ts = ?",
                 (data.get("message") if isinstance(data.get("message"), str) else None,
                  json.dumps(attachments, ensure_ascii=False) if attachments else None,
                  data["timestamp"], _mentions(data.get("mentions")), author, row["ts"]))
    return "edit"


def _remove_files(attachments_json, state: Path | None) -> None:
    try:
        items = json.loads(attachments_json) if attachments_json else []
    except ValueError:
        return
    for a in items:
        path = attachment_file(a.get("id"), state) if isinstance(a, dict) else None
        if path is not None:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass


def remote_delete(conn, author: str, ts: int, state: Path | None = None) -> bool:
    """A delete for everyone: the message, its files, earlier versions, reactions and quotes of it go.
    Nothing records that it existed."""
    row = _find(conn, author, ts)
    if row is None:
        return False
    _remove_files(row["attachments"], state)
    # Every time this message went by: its own, its current revision's and each earlier revision's.
    identities = {row["ts"], row["edited"]} - {None}
    for edit in conn.execute("SELECT rev_ts, attachments FROM edits WHERE author = ? AND ts = ?",
                             (author, row["ts"])).fetchall():
        identities.add(edit["rev_ts"])
        _remove_files(edit["attachments"], state)
    conn.execute("DELETE FROM edits WHERE author = ? AND ts = ?", (author, row["ts"]))
    conn.execute("DELETE FROM reactions WHERE author = ? AND ts = ?", (author, row["ts"]))
    conn.execute("DELETE FROM messages WHERE author = ? AND ts = ?", (author, row["ts"]))
    # A quote names its message by author and time (of any revision); one without an author only
    # within the chat.
    for ts_ in identities:
        conn.execute("UPDATE messages SET quote = NULL WHERE quote IS NOT NULL AND json_extract(quote, '$.id') = ? "
                     "AND (json_extract(quote, '$.author') = ? "
                     "OR (json_extract(quote, '$.author') IS NULL AND chat = ?))",
                     (ts_, author, row["chat"]))
    return True


def _react(conn, reactor: str, reaction: dict) -> str | None:
    target = _uuid(reaction.get("targetAuthorUuid"))
    ts = reaction.get("targetSentTimestamp")
    if not target or not isinstance(ts, int):
        return None
    row = _find(conn, target, ts)
    ts = row["ts"] if row else ts
    if reaction.get("isRemove"):
        conn.execute("DELETE FROM reactions WHERE author = ? AND ts = ? AND reactor = ?", (target, ts, reactor))
    else:
        conn.execute("INSERT INTO reactions (author, ts, reactor, emoji, at) VALUES (?, ?, ?, ?, ?) "
                     "ON CONFLICT (author, ts, reactor) DO UPDATE SET emoji = excluded.emoji, at = excluded.at",
                     (target, ts, reactor, reaction.get("emoji"), now_ms()))
    return "reaction"


def _handle_data(conn, *, chat, author, from_me, author_name, data, received, state) -> list[str]:
    if isinstance(data.get("remoteDelete"), dict):
        target = data["remoteDelete"].get("timestamp")
        return ["delete"] if isinstance(target, int) and remote_delete(conn, author, target, state) else []
    if isinstance(data.get("reaction"), dict):
        done = _react(conn, author, data["reaction"])
        return [done] if done else []
    if isinstance(data.get("groupInfo"), dict) and data["groupInfo"].get("type") == "UPDATE" \
            and not data.get("message") and not data.get("attachments"):
        set_meta(conn, groups_stale=1)
        return ["group-update"]
    done = _store_message(conn, chat=chat, author=author, from_me=from_me, author_name=author_name, data=data,
                          received=received)
    return [done] if done else []


def ingest(conn: sqlite3.Connection, payload: dict, *, me: str, state: Path | None = None) -> list[str]:
    """Apply one ``receive`` payload (``{account, envelope}``) to the mirror, in the caller's
    transaction. Returns what it did, for the log (never content)."""
    envelope = payload.get("envelope") if isinstance(payload, dict) else None
    if not isinstance(envelope, dict):
        return ["no-envelope"]
    received = now_ms()
    source = _uuid(envelope.get("sourceUuid")) or _contact_uuid(conn, envelope.get("sourceNumber"))
    name = envelope.get("sourceName") or None
    done: list[str] = []
    if source and source != me and name:
        conn.execute("INSERT INTO contacts (uuid, number, profile_name, updated) VALUES (?, ?, ?, ?) "
                     "ON CONFLICT (uuid) DO UPDATE SET profile_name = excluded.profile_name, "
                     "number = COALESCE(excluded.number, contacts.number)",
                     (source, envelope.get("sourceNumber"), name, received))
    data = envelope.get("dataMessage")
    if isinstance(data, dict) and source:
        group = (data.get("groupInfo") or {}).get("groupId")
        chat = group_chat(group) if group else source
        done += _handle_data(conn, chat=chat, author=source, from_me=source == me, author_name=name, data=data,
                             received=received, state=state)
    edit = envelope.get("editMessage")
    if isinstance(edit, dict) and source:
        group = ((edit.get("dataMessage") or {}).get("groupInfo") or {}).get("groupId")
        done.append(_edit(conn, chat=group_chat(group) if group else source, author=source, from_me=source == me,
                          author_name=name, edit=edit, received=received) or "edit-skipped")
    sync = envelope.get("syncMessage")
    if isinstance(sync, dict):
        done += _sync(conn, sync, me=me, received=received, state=state)
    return done or ["ignored"]


def _sync(conn, sync: dict, *, me: str, received: int, state) -> list[str]:
    done = []
    sent = sync.get("sentMessage")
    if isinstance(sent, dict):
        group = (sent.get("groupInfo") or {}).get("groupId")
        if not group and isinstance(sent.get("editMessage"), dict):
            group = ((sent["editMessage"].get("dataMessage") or {}).get("groupInfo") or {}).get("groupId")
        chat = group_chat(group) if group else (_uuid(sent.get("destinationUuid"))
                                               or _contact_uuid(conn, sent.get("destinationNumber")))
        if chat:
            if not group and sent.get("destinationNumber"):
                _touch_chat(conn, chat, sent.get("timestamp") or received, number=sent["destinationNumber"])
            if isinstance(sent.get("editMessage"), dict):
                done.append(_edit(conn, chat=chat, author=me, from_me=True, author_name=None,
                                  edit=sent["editMessage"], received=received) or "edit-skipped")
            else:
                done += _handle_data(conn, chat=chat, author=me, from_me=True, author_name=None, data=sent,
                                     received=received, state=state)
        else:
            done.append("sent-unknown-chat")
    for read in sync.get("readMessages") or []:
        author = _uuid((read or {}).get("senderUuid")) or _contact_uuid(conn, (read or {}).get("senderNumber"))
        ts = (read or {}).get("timestamp")
        if author and isinstance(ts, int):
            # Signal starts a received message's timer when it is read; the read sync is when that was.
            conn.execute("UPDATE messages SET read_at = COALESCE(read_at, ?), expire_start = CASE WHEN "
                         "expires_in > 0 THEN COALESCE(expire_start, ?) END WHERE author = ? AND ts = ?",
                         (received, received, author, ts))
            done.append("read")
    if sync.get("type") in ("CONTACTS_SYNC", "GROUPS_SYNC"):
        set_meta(conn, groups_stale=1)
        done.append(sync["type"].lower())
    return done


# --- contacts and groups (from the daemon's listContacts / listGroups) --------------------------

def _person_name(c: dict) -> str | None:
    for given, family in (("nickGivenName", "nickFamilyName"), ("givenName", "familyName")):
        text = " ".join(p for p in (c.get(given), c.get(family)) if p)
        if text:
            return text
    return c.get("nickName") or c.get("name") or None


def upsert_contacts(conn: sqlite3.Connection, contacts: list) -> int:
    count = 0
    stamp = now_ms()
    for c in contacts or []:
        uuid = _uuid((c or {}).get("uuid"))
        if not uuid:
            continue
        profile = c.get("profile") or {}
        profile_name = " ".join(p for p in (profile.get("givenName"), profile.get("familyName")) if p) or None
        conn.execute(
            "INSERT INTO contacts (uuid, number, name, profile_name, username, blocked, updated) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT (uuid) DO UPDATE SET "
            "number = COALESCE(excluded.number, contacts.number), name = excluded.name, "
            "profile_name = COALESCE(excluded.profile_name, contacts.profile_name), "
            "username = excluded.username, blocked = excluded.blocked, updated = excluded.updated",
            (uuid, c.get("number"), _person_name(c), profile_name, c.get("username"),
             int(bool(c.get("isBlocked"))), stamp))
        if isinstance(c.get("messageExpirationTime"), int):
            conn.execute("UPDATE chats SET expires_in = ? WHERE id = ?", (c["messageExpirationTime"], uuid))
        count += 1
    return count


def upsert_groups(conn: sqlite3.Connection, groups: list) -> int:
    count = 0
    stamp = now_ms()
    for g in groups or []:
        gid = (g or {}).get("id")
        if not isinstance(gid, str) or not GROUP_ID.match(gid):
            continue
        members = [m.get("uuid") for m in g.get("members") or [] if isinstance(m, dict) and _uuid(m.get("uuid"))]
        conn.execute(
            "INSERT INTO chats (id, kind, name, members, member, expires_in, updated) VALUES (?, 'group', ?, ?, ?, ?, ?) "
            "ON CONFLICT (id) DO UPDATE SET name = excluded.name, members = excluded.members, "
            "member = excluded.member, expires_in = excluded.expires_in, updated = excluded.updated",
            (group_chat(gid), g.get("name") or None, json.dumps(members), int(bool(g.get("isMember", True))),
             g.get("messageExpirationTime") if isinstance(g.get("messageExpirationTime"), int) else None, stamp))
        count += 1
    return count


def remember_number(conn: sqlite3.Connection, number: str, uuid: str) -> None:
    """A number → account mapping learned from a check (fresh from Signal, so it wins), so a send
    card can show the number."""
    conn.execute("INSERT INTO contacts (uuid, number, updated) VALUES (?, ?, ?) ON CONFLICT (uuid) DO UPDATE "
                 "SET number = excluded.number, updated = excluded.updated", (uuid, number, now_ms()))


def record_sent(conn: sqlite3.Connection, *, chat: str, me: str, ts: int, body: str | None,
                attachments: list[dict], quote: dict | None) -> None:
    """A message this device sent: signal-cli does not echo its own sends back as events."""
    row = conn.execute("SELECT expires_in FROM chats WHERE id = ?", (chat,)).fetchone()
    expires = (row["expires_in"] if row and row["expires_in"] else 0) or 0
    _touch_chat(conn, chat, ts)
    conn.execute(
        "INSERT OR IGNORE INTO messages (chat, author, ts, from_me, body, attachments, quote, expires_in, "
        "expire_start, received) VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?)",
        (chat, me, ts, body, json.dumps(attachments, ensure_ascii=False) if attachments else None,
         json.dumps(quote, ensure_ascii=False) if quote else None, expires, ts if expires else None, now_ms()))


# --- reading helpers ----------------------------------------------------------------------------

def local_time(ms) -> str | None:
    if not isinstance(ms, int) or ms <= 0:
        return None
    return datetime.fromtimestamp(ms / 1000).astimezone().isoformat(timespec="seconds")


def expiry(row, now: int | None = None) -> dict:
    """The disappearing-message mark of a row: expired (with when), when it will go, or not started."""
    expires = row["expires_in"] or 0
    if row["kind"] != "message" or expires <= 0:
        return {}
    if not row["expire_start"]:
        return {"disappearing": "timer starts when the user reads it"}
    at = row["expire_start"] + expires * 1000
    if at <= (now if now is not None else now_ms()):
        return {"expired": local_time(at)}
    return {"disappears": local_time(at)}
