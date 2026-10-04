"""telegram-access sync agent: the only process that talks to Telegram as the user.

Run by launchd (``local.telegram-access.sync``, ``launchd/telegram-access-launchctl.sh``) on the
engine venv (``engines/telegram-access``: Telethon), never inside the Hermes gateway:

    sync.py            run the agent (launchd)
    sync.py login      log in interactively in a terminal (phone, code, 2FA password)
    sync.py logout     end this session at Telegram and forget it

The account's credentials live only in the Keychain (project ``hermes``, scope
``telegram-access``, which no Hermes profile receives): ``TELEGRAM_API_ID``, ``TELEGRAM_API_HASH``
and ``TELEGRAM_USER_SESSION`` (Telethon's string session: data centre and auth key). The auth key
is read at start and held in memory; ``telethon.session`` in the state directory keeps Telethon's
entity cache and update state with the key blanked, so updates missed while the agent was down
are caught up on the next start. One connection only: an auth key used from two places at once
can be revoked by Telegram, so nothing else ever uses it.

The agent stores what Telegram pushes into ``mirror.db`` (see ``store.py`` for what is kept),
refreshes the chat list every 30 minutes (filling gaps of up to 200 messages per mirrored
chat), seeds newly mirrored chats with their newest 50 messages, follows ``sync.json``, keeps the
file of every disappearing message (auto-delete timer or view-once) as it arrives, and answers the plugin on ``telegram.sock``: live reads,
backfill, media downloads and sends. It never marks anything read, never sets the online status
and never sends typing actions. Exit codes: 0 when there is nothing to run (not logged in, or
the session was ended) or on a stop request; 1 after any other failure, so launchd restarts it
after its throttle. Contract: docs/telegram-access.md.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import getpass
import importlib.util
import json
import logging
import os
from pathlib import Path
import platform
import random
import secrets
import shutil
import signal
import sqlite3
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent


def _load(name: str):
    key = f"hermes_telegram_{name}"
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, HERE / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        spec.loader.exec_module(module)
    return sys.modules[key]


store = _load("store")

SECRET = Path.home() / ".config" / "bin" / "secret"
PROJECT, SCOPE = "hermes", "telegram-access"
API_ID, API_HASH, SESSION = "TELEGRAM_API_ID", "TELEGRAM_API_HASH", "TELEGRAM_USER_SESSION"
SECRET_TIMEOUT = 30
DEVICE_MODEL = "Hermes telegram-access"
APP_VERSION = "1.0"

REFRESH_EVERY = 1800          # the chat list, with gap filling
PURGE_EVERY = 3600            # delete tombstones past their fence
KEEP_MAX = 100 * 1024 * 1024  # largest file kept of a disappearing message
KEEP_PER_ROUND = 5            # kept-file downloads per housekeeping round
HEARTBEAT = 5                 # seconds between coverage checks
COVERAGE_GAP = 30_000         # ms without a heartbeat that count as a gap in watching (sleep, a stall)
SYNC_LIST_POLL = 5
SEED_COUNT = 50               # newest messages taken when a chat starts being mirrored
SEED_PER_ROUND = 20           # chats seeded per refresh; the rest next round
SEED_DAYS = 30                # quieter private chats are followed from now on (history: backfill)
GAP_MAX = 200                 # newest missing messages fetched per chat and refresh
PAGE = 100
BACKFILL_PAGES = 5
HISTORY_MAX = 100
CONTEXT_MAX = 50
PACE = (0.5, 1.5)             # seconds between history requests in background work
FLOOD_SLEEP = 30              # reads wait out flood waits up to this; sends never wait
SEND_TIMEOUT_TEXT = 45
SEND_TIMEOUT_FILES = 540
DOWNLOAD_TIMEOUT = 540
MIN_FREE = 64 * 1024 * 1024
LINE_MAX = 1 << 20

log_ = logging.getLogger("telegram-access")
_stop: asyncio.Event | None = None


class AgentError(Exception):
    """An answer to the plugin: ``kind`` is not_sent / uncertain / invalid / not_found /
    unauthorized / flood / failed."""

    def __init__(self, kind: str, message: str, **extra):
        super().__init__(message)
        self.kind = kind
        self.extra = extra


class StorageError(Exception):
    """The mirror cannot be written: the agent stops rather than drop what follows."""


def log(message: str) -> None:
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}", file=sys.stderr, flush=True)


# --- Keychain -----------------------------------------------------------------------------------

def secret_get(name: str, *, required: bool = True) -> str | None:
    if not os.access(SECRET, os.X_OK):
        raise SystemExit(f"the secret CLI is missing at {SECRET}")
    try:
        proc = subprocess.run([str(SECRET), "get", name, "-p", PROJECT, "--scope", SCOPE],
                              stdin=subprocess.DEVNULL, capture_output=True, text=True,
                              timeout=SECRET_TIMEOUT, cwd=str(store.state_dir(create=True)))
    except subprocess.TimeoutExpired as exc:
        raise SystemExit(f"reading {name} from the Keychain timed out") from exc
    value = proc.stdout.strip()
    if proc.returncode != 0 or not value:
        if required:
            raise SystemExit(f"{name} is not in the Keychain (project {PROJECT}, scope {SCOPE}); "
                             f"store it with: secret set {name} -p {PROJECT} --scope {SCOPE}")
        return None
    return value


def secret_put(name: str, value: str) -> None:
    """Store or replace a Keychain item; the value goes through stdin, never argv."""
    exists = subprocess.run([str(SECRET), "show", name, "-p", PROJECT, "--scope", SCOPE],
                            stdin=subprocess.DEVNULL, capture_output=True, text=True,
                            timeout=SECRET_TIMEOUT).returncode == 0
    argv = ([str(SECRET), "update", name, "-p", PROJECT, "--scope", SCOPE, "--stdin"] if exists else
            [str(SECRET), "set", name, "-p", PROJECT, "--scope", SCOPE, "-D", "token",
             "-j", "telegram-access session (Telethon string session)", "--stdin"])
    proc = subprocess.run(argv, input=value + "\n", capture_output=True, text=True, timeout=SECRET_TIMEOUT)
    if proc.returncode != 0:
        raise SystemExit(f"could not store {name} in the Keychain: {proc.stderr.strip()[:200]}")


def secret_remove(name: str) -> None:
    subprocess.run([str(SECRET), "rm", name, "-p", PROJECT, "--scope", SCOPE, "-f"],
                   stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=SECRET_TIMEOUT)


def api_credentials() -> tuple[int, str]:
    raw_id = secret_get(API_ID)
    api_hash = secret_get(API_HASH)
    if not raw_id.isdigit():
        raise SystemExit(f"{API_ID} must be the numeric api_id from my.telegram.org")
    if not all(c in "0123456789abcdef" for c in api_hash.lower()) or len(api_hash) != 32:
        raise SystemExit(f"{API_HASH} must be the 32-character api_hash from my.telegram.org")
    return int(raw_id), api_hash


# --- Telethon client ----------------------------------------------------------------------------

def make_session(path: Path, string: str | None):
    """Telethon's SQLite session for the entity cache and update state, with the auth key taken
    from the Keychain string and never written to disk."""
    from telethon.crypto import AuthKey
    from telethon.sessions import MemorySession, SQLiteSession, StringSession

    class KeychainSession(SQLiteSession):
        def set_dc(self, dc_id, server_address, port):
            # SQLiteSession would reload the (blank) key from disk; keep the one in memory for the
            # same data centre. Another one needs a new key, i.e. a new login.
            key = self._auth_key if dc_id == self._dc_id else None
            MemorySession.set_dc(self, dc_id, server_address, port)
            self._update_session_table()
            self._auth_key, self._tmp_auth_key = key, None

        def _update_session_table(self):
            c = self._cursor()
            c.execute("delete from sessions")
            c.execute("insert or replace into sessions values (?,?,?,?,?,?)",
                      (self._dc_id, self._server_address, self._port, b"", self._takeout_id, b""))
            c.close()

    old = os.umask(0o077)
    try:
        session = KeychainSession(str(path))
    finally:
        os.umask(old)
    if string:
        parsed = StringSession(string)
        session._dc_id, session._server_address, session._port = parsed.dc_id, parsed.server_address, parsed.port
        session._auth_key = AuthKey(parsed.auth_key.key) if parsed.auth_key else None
        session._update_session_table()
        session.save()
    return session


def make_client(session, api_id: int, api_hash: str):
    from telethon import TelegramClient
    client = TelegramClient(
        session, api_id, api_hash, device_model=DEVICE_MODEL,
        system_version=f"macOS {platform.mac_ver()[0] or ''}".strip(), app_version=APP_VERSION,
        lang_code="en", system_lang_code="en", flood_sleep_threshold=FLOOD_SLEEP, request_retries=3,
        catch_up=True, receive_updates=True, auto_reconnect=True)
    client.parse_mode = None  # text goes out exactly as written: no Markdown
    return client


# --- normalising Telethon objects (duck-typed, so tests need no Telethon) -----------------------

def _cls(obj) -> str:
    return type(obj).__name__ if obj is not None else ""


def display_name(entity) -> str | None:
    if entity is None:
        return None
    title = getattr(entity, "title", None)
    if title:
        return title
    name = " ".join(p for p in (getattr(entity, "first_name", None), getattr(entity, "last_name", None)) if p)
    return name or getattr(entity, "username", None) or None


def chat_kind(entity, me_id: int | None = None) -> str | None:
    cls = _cls(entity)
    if cls in ("User", "UserEmpty"):
        if getattr(entity, "is_self", False) or (me_id is not None and getattr(entity, "id", None) == me_id):
            return "self"
        return "bot" if getattr(entity, "bot", False) else "user"
    if cls in ("Chat", "ChatForbidden", "ChatEmpty"):
        return "group"
    if cls in ("Channel", "ChannelForbidden"):
        return "supergroup" if getattr(entity, "megagroup", False) else "channel"
    return None


def chat_fields(entity, me_id: int | None = None) -> tuple[int, dict] | None:
    """(marked chat id, chat fields) for a User, Chat or Channel."""
    kind = chat_kind(entity, me_id)
    raw = getattr(entity, "id", None)
    if kind is None or not isinstance(raw, int):
        return None
    chat = store.marked_id(kind, raw)
    fields = {"kind": kind, "name": display_name(entity), "username": getattr(entity, "username", None)}
    if kind in ("user", "bot", "self") and getattr(entity, "phone", None):
        fields["phone"] = "+" + str(entity.phone).lstrip("+")
    cls = _cls(entity)
    fields["left_chat"] = int(bool(getattr(entity, "left", False) or getattr(entity, "deactivated", False)
                                   or getattr(entity, "deleted", False) or cls.endswith("Forbidden")))
    count = getattr(entity, "participants_count", None)
    if isinstance(count, int):
        fields["members"] = count
    if kind == "channel":
        rights = getattr(entity, "admin_rights", None)
        fields["can_send"] = int(bool(getattr(entity, "creator", False) or (rights and getattr(rights, "post_messages", False))))
    elif kind in ("group", "supergroup"):
        banned = getattr(entity, "banned_rights", None) or getattr(entity, "default_banned_rights", None)
        admin = getattr(entity, "creator", False) or getattr(entity, "admin_rights", None)
        fields["can_send"] = 0 if fields["left_chat"] else (
            1 if admin else int(not (banned and getattr(banned, "send_messages", False))))
    elif kind == "bot" or kind == "user":
        fields["can_send"] = 0 if fields["left_chat"] else None
    return chat, fields


def _ms(moment) -> int | None:
    if not isinstance(moment, datetime):
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return int(moment.timestamp() * 1000)


def _duration(seconds) -> str:
    seconds = int(seconds or 0)
    for unit, size in (("week", 604800), ("day", 86400), ("hour", 3600), ("minute", 60)):
        if seconds >= size and seconds % size == 0:
            n = seconds // size
            return f"{n} {unit}{'s' if n != 1 else ''}"
    return f"{seconds} seconds"


SERVICE = {
    "MessageActionChatCreate": "created the group", "MessageActionChannelCreate": "created the channel",
    "MessageActionChatEditPhoto": "changed the photo", "MessageActionChatDeletePhoto": "removed the photo",
    "MessageActionChatAddUser": "added members", "MessageActionChatDeleteUser": "removed a member or left",
    "MessageActionChatJoinedByLink": "joined by invite link", "MessageActionChatJoinedByRequest": "joined",
    "MessageActionPinMessage": "pinned a message", "MessageActionChatMigrateTo": "upgraded to a supergroup",
    "MessageActionChannelMigrateFrom": "upgraded from a basic group", "MessageActionScreenshotTaken": "took a screenshot",
    "MessageActionContactSignUp": "joined Telegram", "MessageActionHistoryClear": "cleared the history",
    "MessageActionGroupCall": "video chat", "MessageActionTopicCreate": "created a topic",
}


def service_text(action) -> tuple[str, int | None]:
    """A service message's event text, and a new auto-delete period when it sets one."""
    cls = _cls(action)
    if cls == "MessageActionChatEditTitle":
        return f"changed the title to “{getattr(action, 'title', '')}”", None
    if cls == "MessageActionSetMessagesTTL":
        period = int(getattr(action, "period", 0) or 0)
        return (f"set auto-delete to {_duration(period)}" if period else "turned auto-delete off"), period
    if cls == "MessageActionPhoneCall":
        video = "video call" if getattr(action, "video", False) else "call"
        duration = getattr(action, "duration", None)
        return (f"{video} ({_duration(duration)})" if duration else f"missed or declined {video}"), None
    return SERVICE.get(cls, f"service event ({cls.replace('MessageAction', '') or 'unknown'})"), None


DOWNLOADABLE = {"photo", "video", "video note", "voice", "audio", "document", "gif", "sticker"}


def media_info(msg) -> dict | None:
    media = getattr(msg, "media", None)
    if media is None:
        return None
    cls = _cls(media)
    file = getattr(msg, "file", None)
    info: dict = {}
    if cls == "MessageMediaPhoto":
        info["type"] = "photo"
    elif cls == "MessageMediaDocument":
        if getattr(msg, "sticker", None) is not None:
            info["type"] = "sticker"
            if file is not None and getattr(file, "emoji", None):
                info["emoji"] = file.emoji
        elif getattr(msg, "voice", None) is not None:
            info["type"] = "voice"
        elif getattr(msg, "video_note", None) is not None:
            info["type"] = "video note"
        elif getattr(msg, "gif", None) is not None:
            info["type"] = "gif"
        elif getattr(msg, "video", None) is not None:
            info["type"] = "video"
        elif getattr(msg, "audio", None) is not None:
            info["type"] = "audio"
        else:
            info["type"] = "document"
    elif cls == "MessageMediaWebPage":
        page = getattr(media, "webpage", None)
        info = {"type": "link preview"}
        if getattr(page, "url", None):
            info["url"] = page.url
        if getattr(page, "title", None):
            info["title"] = page.title
        return info
    elif cls in ("MessageMediaGeo", "MessageMediaGeoLive", "MessageMediaVenue"):
        info = {"type": "location"}
        if getattr(media, "title", None):
            info["title"] = media.title
        return info
    elif cls == "MessageMediaContact":
        name = " ".join(p for p in (getattr(media, "first_name", None), getattr(media, "last_name", None)) if p)
        return {"type": "contact", "name": name or None}
    elif cls == "MessageMediaPoll":
        question = getattr(getattr(media, "poll", None), "question", None)
        text = getattr(question, "text", question)
        return {"type": "poll", "question": text if isinstance(text, str) else None}
    else:
        return {"type": "unsupported", "what": cls.replace("MessageMedia", "") or "unknown"}
    if file is not None:
        for key, attr in (("name", "name"), ("mime", "mime_type"), ("size", "size"), ("duration", "duration")):
            value = getattr(file, attr, None)
            if value not in (None, ""):
                info[key] = value
    if getattr(media, "ttl_seconds", None):
        info["self_destructing"] = True
        if getattr(media, "photo", None) is None and getattr(media, "document", None) is None:
            info["viewed"] = True  # Telegram serves a viewed one without its file
    if getattr(media, "spoiler", False):
        info["spoiler"] = True
    return {k: v for k, v in info.items() if v is not None}


def message_row(msg) -> dict | None:
    """One Telethon Message / MessageService as the mirror stores it; None for anything else."""
    chat, msg_id, ts = getattr(msg, "chat_id", None), getattr(msg, "id", None), _ms(getattr(msg, "date", None))
    if not isinstance(chat, int) or not isinstance(msg_id, int) or ts is None or _cls(msg) == "MessageEmpty":
        return None
    row = {"chat": chat, "id": msg_id, "ts": ts, "from_me": bool(getattr(msg, "out", False)),
           "sender": getattr(msg, "sender_id", None), "kind": "message", "body": None, "media": None,
           "reply_to": None, "fwd_from": None, "edited": None, "expires": None,
           "grouped": getattr(msg, "grouped_id", None)}
    row["sender_name"] = display_name(getattr(msg, "sender", None)) or getattr(msg, "post_author", None)
    action = getattr(msg, "action", None)
    if action is not None:
        row["kind"] = "service"
        row["body"], _ = service_text(action)
    else:
        row["body"] = getattr(msg, "message", None) or None
        row["media"] = media_info(msg)
    reply = getattr(msg, "reply_to", None)
    if reply is not None and isinstance(getattr(reply, "reply_to_msg_id", None), int):
        row["reply_to"] = reply.reply_to_msg_id
    fwd = getattr(msg, "fwd_from", None)
    if fwd is not None:
        forward = getattr(msg, "forward", None)
        row["fwd_from"] = (getattr(fwd, "from_name", None) or display_name(getattr(forward, "sender", None))
                           or display_name(getattr(forward, "chat", None)) or "someone")
    if getattr(msg, "edit_date", None) is not None and not getattr(msg, "edit_hide", False):
        row["edited"] = _ms(msg.edit_date)
    period = getattr(msg, "ttl_period", None)
    if isinstance(period, int) and period > 0:
        row["expires"] = ts + period * 1000
    return row


def classify_send_error(exc: BaseException, *, single_delivery: bool = False) -> str:
    """not_sent only when Telegram answered the call's first and only delivery with a refusal (an
    RPC error in 300-499: rights, a blocked user, a bad peer, flood or slow mode). Telethon
    delivers a call again after a server error or a reconnect, and a refusal may then answer the
    repeat of a call that already went through; RANDOM_ID_DUPLICATE says exactly that.
    Everything else may have gone out."""
    code = getattr(exc, "code", None)
    duplicate = (type(exc).__name__ == "RandomIdDuplicateError"
                 or "RANDOM_ID_DUPLICATE" in str(getattr(exc, "message", None) or exc).upper())
    if not single_delivery or duplicate:
        return "uncertain"
    if isinstance(code, int) and not isinstance(code, bool) and 300 <= code < 500:
        return "not_sent"
    return "uncertain"


SEND_REQUESTS = {"SendMessageRequest", "SendMediaRequest", "SendMultiMediaRequest"}


class Deliveries:
    """Counts what could deliver a send twice on the client's main sender: every send-type request
    handed to it (Telethon's retry after a server error hands the same request over again) and
    every transport reconnect (after which Telethon resends what was pending). Without these
    counts no refusal can be shown to answer a single delivery, so ``single`` stays False."""

    def __init__(self):
        self.sends = 0
        self.reconnects = 0
        self.installed = False

    def install(self, client) -> bool:
        sender = getattr(client, "_sender", None)
        send, reconnect = getattr(sender, "send", None), getattr(sender, "_reconnect", None)
        if not callable(send) or not callable(reconnect):
            return False

        def counted_send(request, *args, **kwargs):
            for item in request if isinstance(request, (list, tuple)) else (request,):
                if type(item).__name__ in SEND_REQUESTS:
                    self.sends += 1
            return send(request, *args, **kwargs)

        async def counted_reconnect(*args, **kwargs):
            self.reconnects += 1
            return await reconnect(*args, **kwargs)

        sender.send = counted_send
        sender._reconnect = counted_reconnect
        self.installed = True
        return True

    def mark(self) -> tuple[int, int]:
        return self.sends, self.reconnects

    def single(self, mark: tuple[int, int]) -> bool:
        return self.installed and self.sends - mark[0] <= 1 and self.reconnects == mark[1]


def _utc(ms) -> datetime | None:
    if not isinstance(ms, int) or isinstance(ms, bool):
        return None
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


# --- the agent ----------------------------------------------------------------------------------

class Agent:
    """Mirror upkeep and the plugin's requests, over one Telethon client (or a test double with
    the same coroutine methods)."""

    def __init__(self, client, conn: sqlite3.Connection, state: Path, me_id: int | None = None,
                 pace: tuple[float, float] = PACE, deliveries: Deliveries | None = None):
        self.client = client
        self.deliveries = deliveries or Deliveries()
        self.conn = conn
        self.state = state
        self.me_id = me_id
        self.pace = pace
        self.synced: set[int] = set(store.read_sync_list(state))
        self._sync_mtime = self._mtime()
        self._seed_queue: list[int] = []
        self._keep_queue: list[tuple[int, int]] = []
        self._refresh_lock = asyncio.Lock()
        # Gaps in watching: deletes carry no time, so every stretch the agent did not watch is
        # remembered (store.record_gap) and decides whether a delete was a timer's
        # (store.expiry_delete). A gap is the time down before this start (from the first start
        # ever, everything before it), a sleep or stall (no heartbeat for COVERAGE_GAP) or a
        # reconnect (note_coverage).
        meta = store.get_meta(conn)
        self.last_beat = store.now_ms()
        alive_at = int(meta["alive_at"]) if str(meta.get("alive_at") or "").isdigit() else 0
        self.write(store.record_gap, self.conn, alive_at, self.last_beat)
        self._seen_reconnects = self.deliveries.reconnects
        # The list may have changed while the agent was down.
        dropped = self.write(store.drop_unlisted, self.conn, self.synced, self.state)
        if dropped:
            log(f"sync list: dropped {dropped} messages of chats no longer listed")

    # transactions; a mirror that cannot be written stops the agent
    def write(self, fn, *args, **kwargs):
        try:
            self.conn.execute("BEGIN IMMEDIATE")
        except sqlite3.Error as exc:
            raise StorageError(str(exc)) from exc
        try:
            result = fn(*args, **kwargs)
            self.conn.execute("COMMIT")
            return result
        except (sqlite3.IntegrityError, sqlite3.ProgrammingError, sqlite3.InterfaceError, store.StoreError) as exc:
            self._rollback()
            log(f"could not store an event: {type(exc).__name__}: {exc}")
            return None
        except (sqlite3.DatabaseError, OSError) as exc:
            self._rollback()
            raise StorageError(str(exc)) from exc
        except Exception:
            self._rollback()
            raise

    def _rollback(self) -> None:
        try:
            self.conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass

    async def _pause(self) -> None:
        low, high = self.pace
        if high > 0:
            await asyncio.sleep(random.uniform(low, high))

    def kind_of(self, chat: int) -> str | None:
        row = self.conn.execute("SELECT kind FROM chats WHERE id = ?", (chat,)).fetchone()
        return row["kind"] if row else None

    def is_mirrored(self, chat: int) -> bool:
        return store.mirrored(self.kind_of(chat), chat, self.synced)

    def remember_entity(self, entity) -> int | None:
        found = chat_fields(entity, self.me_id)
        if not found:
            return None
        chat, fields = found
        self.write(store.upsert_chat, self.conn, chat, **fields)
        return chat

    # --- pushed updates
    async def on_message(self, msg, chat_entity=None) -> str:
        row = message_row(msg)
        if row is None:
            return "ignored"
        chat = row["chat"]
        if self.kind_of(chat) is None:
            entity = chat_entity
            if entity is None:
                try:
                    entity = await self.client.get_entity(chat)
                except Exception as exc:  # noqa: BLE001 - logged; the chat appears at the next refresh
                    log(f"unknown chat for a new message: {type(exc).__name__}")
                    return "unknown-chat"
            self.remember_entity(entity)
        action = getattr(msg, "action", None)
        _, period = service_text(action) if action is not None else (None, None)

        def apply():
            if period is not None:
                self.conn.execute("UPDATE chats SET ttl = ? WHERE id = ?", (period or None, chat))
            store.touch_chat(self.conn, chat, row["id"], row["ts"], incoming=not row["from_me"])
            if store.mirrored(self.kind_of(chat), chat, self.synced):
                if store.upsert_message(self.conn, row):
                    self.queue_keep(row)
                return "message"
            return "activity"

        return self.write(apply) or "skipped"

    async def on_edit(self, msg) -> str:
        row = message_row(msg)
        if row is None or not self.is_mirrored(row["chat"]):
            return "ignored"
        self.write(store.upsert_message, self.conn, row)
        return "edit"

    def note_coverage(self, now: int | None = None) -> bool:
        """Advance the heartbeat; True when a gap in watching was found (and recorded)."""
        now = now if now is not None else store.now_ms()
        gap = now - self.last_beat > COVERAGE_GAP or self.deliveries.reconnects != self._seen_reconnects
        if gap:
            self.write(store.record_gap, self.conn, self.last_beat, now)
            self._seen_reconnects = self.deliveries.reconnects
        self.last_beat = now
        return gap

    def on_delete(self, ids: list[int], chat: int | None) -> str:
        if self.note_coverage():  # a delete caught up after a sleep or reconnect may predate it
            log("a gap in watching (sleep, stall or reconnect)")
        count = self.write(lambda: store.delete_messages(self.conn, list(ids), chat, self.state,
                                                         unwatched=store.gaps(self.conn)))
        return f"delete:{count or 0}"

    def on_read(self, chat: int, max_id: int, still_unread: int | None) -> str:
        self.write(store.set_read, self.conn, chat, max_id, still_unread)
        return "read"

    def on_ttl(self, chat: int, period: int | None) -> str:
        self.write(lambda: self.conn.execute("UPDATE chats SET ttl = ? WHERE id = ?", (period or None, chat)))
        return "ttl"

    # --- the chat list
    async def refresh(self) -> dict:
        """Every dialog into the chats table; gaps in mirrored chats filled; new ones queued for
        seeding. Bounded by Telegram's own paging and the pace between history requests."""
        async with self._refresh_lock:
            seen = 0
            tops: list[tuple[int, int | None, int | None]] = []
            async for dialog in self.client.iter_dialogs():
                entity = getattr(dialog, "entity", None)
                found = chat_fields(entity, self.me_id)
                if not found:
                    continue
                chat, fields = found
                inner = getattr(dialog, "dialog", None)
                top = getattr(getattr(dialog, "message", None), "id", None)
                fields.update(unread=int(getattr(dialog, "unread_count", 0) or 0),
                              read_max=getattr(inner, "read_inbox_max_id", None),
                              top_id=top, last_ts=_ms(getattr(dialog, "date", None)),
                              archived=int(bool(getattr(dialog, "archived", False))),
                              ttl=getattr(inner, "ttl_period", None))
                self.write(store.upsert_chat, self.conn, chat, **fields)
                tops.append((chat, top, fields["last_ts"]))
                seen += 1
            filled = 0
            for chat, top, last_ts in tops:
                if not self.is_mirrored(chat):
                    continue
                row = self.conn.execute("SELECT seeded, (SELECT MAX(id) FROM messages WHERE chat = ?) AS max_id "
                                        "FROM chats WHERE id = ?", (chat, chat)).fetchone()
                if row["max_id"] is None and not row["seeded"]:
                    if chat not in self._seed_queue:
                        recent = last_ts and last_ts > store.now_ms() - SEED_DAYS * 86400 * 1000
                        if recent or self.kind_of(chat) in store.LISTED:
                            self._seed_queue.append(chat)
                        else:
                            self.write(lambda c=chat: self.conn.execute("UPDATE chats SET seeded = 1 WHERE id = ?", (c,)))
                    continue
                if isinstance(top, int) and row["max_id"] is not None and top > row["max_id"]:
                    filled += await self._fill(chat, row["max_id"])
            seeded = await self.seed_some()
            self.write(store.set_meta, self.conn, refreshed=store.now_ms())
            log(f"refreshed {seen} chats, filled {filled}, seeded {seeded}")
            return {"chats": seen, "filled": filled, "seeded": seeded}

    async def _fill(self, chat: int, after_id: int) -> int:
        await self._pause()
        try:
            msgs = await self.client.get_messages(chat, limit=GAP_MAX, min_id=after_id)
        except Exception as exc:  # noqa: BLE001 - retried next round
            log(f"gap fill failed for a chat: {type(exc).__name__}")
            return 0
        return self._store_many(msgs)

    def _store_many(self, msgs) -> int:
        return self._store_many_rows([r for r in (message_row(m) for m in msgs or []) if r is not None])

    def _store_many_rows(self, rows: list[dict]) -> int:
        """Fetched history, checked at commit time: a chat that left the mirror while the fetch was
        in flight stores nothing, and a message deleted meanwhile stays deleted."""
        def apply():
            now = store.now_ms()
            stored = 0
            for r in rows:
                if store.mirrored(self.kind_of(r["chat"]), r["chat"], self.synced) and \
                        store.upsert_message(self.conn, r, now):
                    self.queue_keep(r)
                    stored += 1
            return stored

        return self.write(apply) or 0

    # --- files of disappearing messages
    @staticmethod
    def should_keep(row: dict) -> bool:
        """A disappearing message's file is kept as it arrives, while Telegram still serves it: a
        message on an auto-delete timer or a view-once photo or video, of a downloadable kind, not
        an archive or program, at most KEEP_MAX."""
        media = row.get("media") if isinstance(row.get("media"), dict) else store.media_of(row) or {}
        if not (row.get("expires") or media.get("self_destructing")):
            return False
        if media.get("type") not in DOWNLOADABLE:
            return False
        if store.RISKY_FILES.search(media.get("name") or "") or store.RISKY_MIME.search(media.get("mime") or ""):
            return False
        return not (isinstance(media.get("size"), int) and media["size"] > KEEP_MAX)

    def queue_keep(self, row: dict) -> None:
        key = (row["chat"], row["id"])
        if self.should_keep(row) and key not in self._keep_queue and store.kept_file(*key, self.state) is None:
            self._keep_queue.append(key)

    async def keep_some(self, limit: int = KEEP_PER_ROUND) -> int:
        """At most ``limit`` fetches per round, each paced, whatever their outcome."""
        done = attempts = 0
        while self._keep_queue and attempts < limit:
            chat, msg_id = self._keep_queue.pop(0)
            row = self.conn.execute("SELECT * FROM messages WHERE chat = ? AND id = ?", (chat, msg_id)).fetchone()
            if row is None or not self.is_mirrored(chat) or store.kept_file(chat, msg_id, self.state) is not None:
                continue  # nothing asked of Telegram
            if shutil.disk_usage(self.state).free < MIN_FREE + KEEP_MAX:
                log("the disk is nearly full; not keeping files")
                self._keep_queue.insert(0, (chat, msg_id))
                return done
            attempts += 1
            try:
                found = await self.client.get_messages(chat, ids=[msg_id])
                msg = (found or [None])[0]
                if msg is None or _cls(msg) == "MessageEmpty":
                    continue  # already gone from Telegram: only the text stays
                folder = store.kept_path(chat, msg_id, self.state)
                part = folder.parent / f".part-{msg_id}-{secrets.token_hex(4)}"
                part.mkdir(parents=True, mode=0o700)
                try:
                    path = await asyncio.wait_for(self.client.download_media(msg, file=str(part) + os.sep),
                                                  DOWNLOAD_TIMEOUT)
                    if not path or not Path(path).is_file():
                        continue
                    if self.conn.execute("SELECT 1 FROM messages WHERE chat = ? AND id = ?",
                                         (chat, msg_id)).fetchone() is None:
                        continue  # deleted for everyone while downloading
                    shutil.rmtree(folder, ignore_errors=True)
                    os.replace(part, folder)
                    done += 1
                    log("kept a file")
                finally:
                    shutil.rmtree(part, ignore_errors=True)
            except Exception as exc:  # noqa: BLE001 - the text stays; the file is lost to the mirror
                log(f"could not keep a file: {type(exc).__name__}")
            finally:
                await self._pause()
        return done

    async def seed_some(self) -> int:
        done = 0
        while self._seed_queue and done < SEED_PER_ROUND:
            chat = self._seed_queue.pop(0)
            if not self.is_mirrored(chat):
                continue
            await self._pause()
            try:
                msgs = await self.client.get_messages(chat, limit=SEED_COUNT)
            except Exception as exc:  # noqa: BLE001 - tried again next round
                log(f"seeding failed for a chat: {type(exc).__name__}")
                continue
            self._store_many(msgs)
            self.write(lambda c=chat: self.conn.execute("UPDATE chats SET seeded = 1 WHERE id = ?", (c,)))
            done += 1
        return done

    # --- the sync list
    def _mtime(self) -> float | None:
        try:
            return store.sync_path(self.state).stat().st_mtime
        except OSError:
            return None

    async def follow_sync_list(self) -> tuple[set, set] | None:
        mtime = self._mtime()
        if mtime == self._sync_mtime:
            return None
        self._sync_mtime = mtime
        new = set(store.read_sync_list(self.state))
        added, removed = new - self.synced, self.synced - new
        self.synced = new
        for chat in removed:
            if self.kind_of(chat) in store.LISTED:
                self.write(store.drop_chat, self.conn, chat, self.state)
        for chat in added:
            if self.kind_of(chat) in store.LISTED and chat not in self._seed_queue:
                self._seed_queue.insert(0, chat)
        if added:
            await self.seed_some()
        log(f"sync list: +{len(added)} -{len(removed)}")
        return added, removed

    # --- requests from the plugin
    async def handle(self, method: str, params: dict):
        handler = getattr(self, f"rpc_{method}", None)
        if handler is None:
            raise AgentError("invalid", f"unknown method {method!r}")
        return await handler(params if isinstance(params, dict) else {})

    def _chat(self, params: dict) -> int:
        chat = store.parse_chat(params.get("chat"))
        if chat is None:
            raise AgentError("invalid", "chat must be a chat id")
        if self.kind_of(chat) is None:
            raise AgentError("not_found", "that chat is not in the chat list")
        return chat

    async def rpc_status(self, params: dict):
        out = {"connected": bool(self.client.is_connected()), "me": self.me_id, "synced": sorted(self.synced)}
        if params.get("verify"):
            try:
                me = await self.client.get_me()
                out["authorized"] = me is not None
            except Exception as exc:  # noqa: BLE001 - reported
                out["authorized"] = False
                out["error"] = f"{type(exc).__name__}: {exc}"
        return out

    async def rpc_refresh(self, params: dict):
        return await self.refresh()

    async def _read(self, chat: int, **kwargs) -> list[dict]:
        try:
            msgs = await self.client.get_messages(chat, **kwargs)
        except Exception as exc:  # noqa: BLE001 - a read failure is reported, never retried here
            raise AgentError(_read_kind(exc), f"Telegram did not return the messages: {type(exc).__name__}: {exc}")
        return [r for r in (message_row(m) for m in msgs or []) if r is not None]

    async def rpc_history(self, params: dict):
        chat = self._chat(params)
        limit = max(1, min(int(params.get("limit") or 50), HISTORY_MAX))
        around = params.get("around")
        if isinstance(around, int):
            before = max(0, min(int(params.get("before_count") or 5), CONTEXT_MAX))
            after = max(0, min(int(params.get("after_count") or 5), CONTEXT_MAX))
            older = await self._read(chat, limit=before + 1, offset_id=around + 1)
            newer = await self._read(chat, limit=after, offset_id=around, reverse=True) if after else []
            rows = sorted({r["id"]: r for r in older + newer}.values(), key=lambda r: r["id"])
        elif isinstance(params.get("after_id"), int):
            rows = await self._read(chat, limit=limit, offset_id=params["after_id"], reverse=True)
        elif isinstance(params.get("after_ts"), int):
            rows = await self._read(chat, limit=limit, offset_date=_utc(params["after_ts"]), reverse=True)
        else:
            kwargs = {"limit": limit}
            if isinstance(params.get("before_id"), int):
                kwargs["offset_id"] = params["before_id"]
            elif isinstance(params.get("before_ts"), int):
                kwargs["offset_date"] = _utc(params["before_ts"])
            rows = list(reversed(await self._read(chat, **kwargs)))
        return {"messages": sorted(rows, key=lambda r: r["id"]), "more": len(rows) >= limit}

    async def rpc_message(self, params: dict):
        chat = self._chat(params)
        msg_id = params.get("id")
        if not isinstance(msg_id, int):
            raise AgentError("invalid", "id must be a message id")
        rows = await self._read(chat, ids=[msg_id])
        if not rows:
            raise AgentError("not_found", "no message with that id in that chat")
        return rows[0]

    async def rpc_backfill(self, params: dict):
        chat = self._chat(params)
        if not self.is_mirrored(chat):
            raise AgentError("invalid", "that chat is not mirrored: add it to the sync list, or read it live")
        pages = max(1, min(int(params.get("pages") or 2), BACKFILL_PAGES))
        added, complete = 0, False
        for _ in range(pages):
            oldest = self.conn.execute("SELECT MIN(id) FROM messages WHERE chat = ?", (chat,)).fetchone()[0]
            kwargs = {"limit": PAGE}
            if oldest is not None:
                kwargs["max_id"] = oldest
            rows = await self._read(chat, **kwargs)
            if rows:
                added += self._store_many_rows(rows)
            if len(rows) < PAGE:
                complete = True
                break
            await self._pause()
        oldest = self.conn.execute("SELECT MIN(ts) FROM messages WHERE chat = ?", (chat,)).fetchone()[0]
        return {"added": added, "complete": complete, "oldest": oldest}

    async def _one(self, chat: int, msg_id: int):
        try:
            found = await self.client.get_messages(chat, ids=[msg_id])
        except Exception as exc:  # noqa: BLE001
            raise AgentError(_read_kind(exc), f"Telegram did not return the message: {type(exc).__name__}: {exc}")
        msg = (found or [None])[0]
        if msg is None or _cls(msg) == "MessageEmpty":
            raise AgentError("not_found", "no message with that id in that chat")
        return msg

    async def rpc_download(self, params: dict):
        chat = self._chat(params)
        msg_id = params.get("id")
        if not isinstance(msg_id, int):
            raise AgentError("invalid", "id must be a message id")
        max_bytes = params.get("max_bytes") if isinstance(params.get("max_bytes"), int) else 100 * 1024 * 1024
        msg = await self._one(chat, msg_id)
        info = media_info(msg) or {}
        if info.get("type") not in DOWNLOADABLE:
            raise AgentError("invalid", "that message has no file to save")
        if info.get("self_destructing"):
            raise AgentError("invalid", "a self-destructing photo or video: only viewable on the phone, never saved")
        if isinstance(info.get("size"), int) and info["size"] > max_bytes:
            return {"too_large": True, "media": info}
        if shutil.disk_usage(self.state).free < MIN_FREE + (info.get("size") or 0):
            raise AgentError("failed", "the disk is nearly full")
        target = store.incoming_dir(self.state) / secrets.token_hex(16)
        target.mkdir(parents=True, mode=0o700)
        try:
            path = await asyncio.wait_for(self.client.download_media(msg, file=str(target) + os.sep),
                                          DOWNLOAD_TIMEOUT)
        except Exception as exc:  # noqa: BLE001
            shutil.rmtree(target, ignore_errors=True)
            raise AgentError("failed", f"the download failed: {type(exc).__name__}: {exc}")
        if not path or not Path(path).is_file():
            shutil.rmtree(target, ignore_errors=True)
            raise AgentError("not_found", "Telegram no longer serves that file")
        return {"path": str(path), "media": info}

    def _outbox_file(self, given) -> str:
        root = Path(os.path.realpath(store.outbox_dir(self.state)))
        real = Path(os.path.realpath(str(given))) if isinstance(given, str) else None
        if real is None or root not in real.parents or not real.is_file():
            raise AgentError("not_sent", "files are only sent from the plugin's outbox")
        return str(real)

    async def rpc_send(self, params: dict):
        chat = self._chat(params)
        text = params.get("text") if isinstance(params.get("text"), str) else ""
        reply_to = params.get("reply_to") if isinstance(params.get("reply_to"), int) else None
        files = [self._outbox_file(f) for f in params.get("files") or []]
        if not text and not files:
            raise AgentError("not_sent", "nothing to send")
        try:
            entity = await self.client.get_input_entity(chat)
        except Exception as exc:  # noqa: BLE001 - nothing was sent
            raise AgentError("not_sent", f"the chat could not be resolved: {type(exc).__name__}")
        uploaded = []
        try:
            for path in files:
                uploaded.append(await self.client.upload_file(path))
        except Exception as exc:  # noqa: BLE001 - an upload creates no message
            raise AgentError("not_sent", f"a file upload failed: {type(exc).__name__}: {exc}")
        started = store.now_ms()
        mark = self.deliveries.mark()
        try:
            if uploaded:
                images = all(Path(p).suffix.lower() in (".jpg", ".jpeg", ".png") for p in files)
                result = await asyncio.wait_for(self.client.send_file(
                    entity, uploaded if len(uploaded) > 1 else uploaded[0], caption=text or None,
                    reply_to=reply_to, parse_mode=None, force_document=len(uploaded) > 1 and not images),
                    SEND_TIMEOUT_FILES)
            else:
                result = await asyncio.wait_for(self.client.send_message(
                    entity, text, reply_to=reply_to, parse_mode=None), SEND_TIMEOUT_TEXT)
        except Exception as exc:  # noqa: BLE001 - classified, never retried
            kind = classify_send_error(exc, single_delivery=self.deliveries.single(mark))
            hint = await self._uncertain_hint(chat, text, started) if kind == "uncertain" else None
            raise AgentError(kind, f"{type(exc).__name__}: {exc}", **({"hint": hint} if hint else {}))
        sent = result if isinstance(result, list) else [result]
        rows = [r for r in (message_row(m) for m in sent) if r is not None]
        if not rows:
            raise AgentError("uncertain", "Telegram's answer carried no message")

        def apply():
            for r in rows:
                store.touch_chat(self.conn, chat, r["id"], r["ts"], incoming=False)
                if store.mirrored(self.kind_of(chat), chat, self.synced):
                    store.upsert_message(self.conn, r)

        recorded = True
        try:
            self.write(apply)
        except StorageError:
            recorded = False
        return {"ids": [r["id"] for r in rows], "ts": rows[0]["ts"], "recorded": recorded}

    async def _uncertain_hint(self, chat: int, text: str, started: int) -> str | None:
        """After an uncertain send, one look at the newest messages: the user's own with this text,
        sent after the attempt began. A hint for the user, never a conclusion."""
        try:
            msgs = await asyncio.wait_for(self.client.get_messages(chat, limit=10), 20)
        except Exception:  # noqa: BLE001
            return None
        hits = [r["id"] for r in (message_row(m) for m in msgs or [])
                if r and r["from_me"] and r["ts"] >= started - 2000 and (r["body"] or "") == text]
        return (f"the newest messages include the user's own with this text, ids {hits}" if hits else
                "the newest 10 messages show no message from the user with this text")


def _read_kind(exc: BaseException) -> str:
    name = type(exc).__name__
    if name.startswith("FloodWait") or getattr(exc, "code", None) == 420:
        return "flood"
    if getattr(exc, "code", None) == 401:
        return "unauthorized"
    return "failed"


# --- socket server ------------------------------------------------------------------------------

async def serve_connection(agent: Agent, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while True:
            try:
                line = await reader.readline()
            except (asyncio.LimitOverrunError, ValueError):
                break
            if not line:
                break
            try:
                request = json.loads(line.decode("utf-8"))
                req_id = request.get("id")
                method = request.get("method")
            except (ValueError, AttributeError):
                continue
            try:
                result = await agent.handle(str(method), request.get("params") or {})
                answer = {"jsonrpc": "2.0", "id": req_id, "result": result}
            except AgentError as exc:
                answer = {"jsonrpc": "2.0", "id": req_id,
                          "error": {"code": -1, "message": str(exc), "data": {"kind": exc.kind, **exc.extra}}}
            except StorageError:
                raise
            except Exception as exc:  # noqa: BLE001 - one bad request never stops the agent
                answer = {"jsonrpc": "2.0", "id": req_id,
                          "error": {"code": -2, "message": f"{type(exc).__name__}: {exc}",
                                    "data": {"kind": "uncertain" if method == "send" else "failed"}}}
            writer.write(json.dumps(answer, ensure_ascii=False).encode("utf-8") + b"\n")
            await writer.drain()
    except (ConnectionError, BrokenPipeError):
        pass
    finally:
        try:
            writer.close()
        except Exception:  # noqa: BLE001
            pass


# --- run ----------------------------------------------------------------------------------------

def register_handlers(client, agent: Agent, failures: list) -> None:
    from telethon import events
    from telethon.tl import types

    def guarded(coro_fn):
        async def wrapper(event):
            try:
                done = await coro_fn(event)
                if done:
                    log(f"event: {done}")  # what happened, never content
            except StorageError as exc:
                failures.append(exc)
                await client.disconnect()
            except Exception as exc:  # noqa: BLE001 - one bad update never stops the mirror
                log(f"could not store an event: {type(exc).__name__}: {exc}")
        return wrapper

    async def new(event):
        return await agent.on_message(event.message, getattr(event, "chat", None))

    async def edited(event):
        return await agent.on_edit(event.message)

    async def deleted(event):
        chat = getattr(event, "chat_id", None)
        return agent.on_delete(list(event.deleted_ids or []), chat if isinstance(chat, int) else None)

    async def raw(update):
        if isinstance(update, types.UpdateReadHistoryInbox):
            peer = update.peer
            if isinstance(peer, types.PeerUser):
                chat = peer.user_id
            elif isinstance(peer, types.PeerChat):
                chat = -peer.chat_id
            else:
                return None
            return agent.on_read(chat, update.max_id, update.still_unread_count)
        if isinstance(update, types.UpdateReadChannelInbox):
            return agent.on_read(store.marked_id("channel", update.channel_id), update.max_id,
                                 update.still_unread_count)
        if isinstance(update, types.UpdatePeerHistoryTTL):
            peer = update.peer
            raw_id = getattr(peer, "user_id", None) or getattr(peer, "chat_id", None) or getattr(peer, "channel_id", None)
            kind = "user" if isinstance(peer, types.PeerUser) else "group" if isinstance(peer, types.PeerChat) else "channel"
            if isinstance(raw_id, int):
                return agent.on_ttl(store.marked_id(kind, raw_id), update.ttl_period)
        return None

    client.add_event_handler(guarded(new), events.NewMessage())
    client.add_event_handler(guarded(edited), events.MessageEdited())
    client.add_event_handler(guarded(deleted), events.MessageDeleted())
    client.add_event_handler(guarded(raw), events.Raw(types=[types.UpdateReadHistoryInbox,
                                                             types.UpdateReadChannelInbox,
                                                             types.UpdatePeerHistoryTTL]))


async def heartbeat(agent: Agent, failures: list) -> None:
    """Coverage of the update stream: a beat every few seconds, recorded as alive_at for the next
    run, and a gap noticed after a sleep or a reconnect. Separate from housekeeping, whose rounds
    can take minutes."""
    while _stop is not None and not _stop.is_set():
        if agent.note_coverage():
            log("a gap in watching (sleep, stall or reconnect)")
        try:
            agent.write(store.set_meta, agent.conn, alive_at=agent.last_beat)
        except StorageError as exc:
            failures.append(exc)
            await agent.client.disconnect()
            return
        try:
            await asyncio.wait_for(_stop.wait(), HEARTBEAT)
        except asyncio.TimeoutError:
            pass


async def housekeeping(agent: Agent, failures: list) -> None:
    next_refresh = 0.0
    next_purge = 0.0
    while _stop is not None and not _stop.is_set():
        try:
            now = time.monotonic()
            if now >= next_purge:
                agent.write(store.purge_tombstones, agent.conn)
                next_purge = now + PURGE_EVERY
            if agent._keep_queue:
                await agent.keep_some()
            await agent.follow_sync_list()
            if now >= next_refresh:
                try:
                    await agent.refresh()
                except StorageError:
                    raise
                except Exception as exc:  # noqa: BLE001 - tried again next round
                    log(f"refresh failed: {type(exc).__name__}: {exc}")
                next_refresh = now + REFRESH_EVERY
            elif agent._seed_queue:
                await agent.seed_some()
        except StorageError as exc:
            failures.append(exc)
            await agent.client.disconnect()
            return
        try:
            await asyncio.wait_for(_stop.wait(), SYNC_LIST_POLL)
        except asyncio.TimeoutError:
            pass


def _clean_scratch(state: Path) -> None:
    """Copies older than a day in outbox/, incoming/ and kept/ part folders (a crash or a denied
    card left them)."""
    cutoff = time.time() - 86400
    for base in (store.outbox_dir(state), store.incoming_dir(state)):
        if not base.is_dir():
            continue
        for entry in base.iterdir():
            try:
                if entry.stat().st_mtime < cutoff:
                    shutil.rmtree(entry, ignore_errors=True) if entry.is_dir() else entry.unlink()
            except OSError:
                pass
    for part in store.kept_dir(state).glob("*/.part-*"):
        try:
            if part.stat().st_mtime < cutoff:
                shutil.rmtree(part, ignore_errors=True)
        except OSError:
            pass


async def run() -> int:
    global _stop
    _stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for name in ("SIGTERM", "SIGINT", "SIGHUP"):
        loop.add_signal_handler(getattr(signal, name), _stop.set)
    os.umask(0o077)
    state = store.state_dir(create=True)
    conn = store.connect(store.db_path(state), write=True)
    _clean_scratch(state)
    string = secret_get(SESSION, required=False)
    if not string:
        store.set_meta(conn, status="not logged in", error=None)
        log("no Telegram session in the Keychain; log in with telegram-access-launchctl.sh login")
        return 0
    if shutil.disk_usage(state).free < MIN_FREE:
        store.set_meta(conn, status="failed", error="the disk is nearly full; not receiving until there is room")
        log("the disk is nearly full; not receiving")
        await asyncio.sleep(60)
        return 1
    api_id, api_hash = api_credentials()
    client = make_client(make_session(store.session_path(state), string), api_id, api_hash)
    store.set_meta(conn, status="starting")
    sock = store.socket_path(state)
    server = None
    failures: list = []
    try:
        # Handlers first: connect() starts Telethon's catch-up, which dispatches what was missed
        # (deletes and edits included) right away and advances the stored update state.
        known_me = store.parse_chat(store.get_meta(conn).get("me_id"))
        deliveries = Deliveries()
        if not deliveries.install(client):
            log("cannot count send deliveries on this Telethon; every refused send will read UNCERTAIN")
        agent = Agent(client, conn, state, me_id=known_me, deliveries=deliveries)
        register_handlers(client, agent, failures)
        await client.connect()
        if not await client.is_user_authorized():
            store.set_meta(conn, status="logged out",
                           error="Telegram ended this session; log in again (telegram-access-launchctl.sh login)")
            log("the session is no longer authorised; staying down until the user logs in again")
            return 0
        me = await client.get_me()
        agent.me_id = getattr(me, "id", None)
        agent.remember_entity(me)
        store.set_meta(conn, me_id=me.id, me_name=display_name(me), me_username=getattr(me, "username", None),
                       me_phone=("+" + str(me.phone).lstrip("+")) if getattr(me, "phone", None) else None)
        sock.unlink(missing_ok=True)
        server = await asyncio.start_unix_server(lambda r, w: serve_connection(agent, r, w), path=str(sock),
                                                 limit=LINE_MAX)
        os.chmod(sock, 0o600)
        store.set_meta(conn, status="running", started=store.now_ms(), error=None)
        log("connected")
        keeper = asyncio.create_task(housekeeping(agent, failures))
        beater = asyncio.create_task(heartbeat(agent, failures))
        stopper = asyncio.create_task(_stop.wait())
        runner = asyncio.create_task(client.run_until_disconnected())
        done, _ = await asyncio.wait({stopper, runner}, return_when=asyncio.FIRST_COMPLETED)
        _stop.set()
        keeper.cancel()
        beater.cancel()
        if runner in done and runner.exception() is not None:
            raise runner.exception()
    except Exception as exc:  # noqa: BLE001 - recorded, then launchd restarts the agent
        name = type(exc).__name__
        if name in ("AuthKeyUnregisteredError", "SessionRevokedError", "SessionExpiredError", "UserDeactivatedError",
                    "UserDeactivatedBanError", "AuthKeyDuplicatedError"):
            store.set_meta(conn, status="logged out", error=f"Telegram ended this session ({name}); log in again")
            log(f"session ended by Telegram ({name}); staying down until the user logs in again")
            return 0
        failures.append(exc)
    finally:
        if server is not None:
            server.close()
        sock.unlink(missing_ok=True)
        try:
            await client.disconnect()
        except Exception:  # noqa: BLE001
            pass
        try:
            client.session.close()
        except Exception:  # noqa: BLE001
            pass
    if failures:
        detail = failures[0]
        message = (f"the mirror cannot be written ({detail}); receiving stopped" if isinstance(detail, StorageError)
                   else f"{type(detail).__name__}: {detail}")
        try:
            store.set_meta(conn, status="failed", error=message)
        except sqlite3.Error:
            pass
        log(f"sync ended: {message}; launchd restarts it")
        return 1
    if _stop.is_set():
        store.set_meta(conn, status="stopped", error=None, alive_at=store.now_ms())
        log("stopped")
        return 0
    store.set_meta(conn, status="failed", error="disconnected from Telegram")
    log("disconnected from Telegram; launchd restarts it")
    return 1


# --- login / logout (a terminal, with the agent stopped) ----------------------------------------

async def login() -> int:
    from telethon.sessions import StringSession
    os.umask(0o077)
    state = store.state_dir(create=True)
    api_id, api_hash = api_credentials()
    existing = secret_get(SESSION, required=False)
    if existing:
        client = make_client(StringSession(existing), api_id, api_hash)
        await client.connect()
        try:
            if await client.is_user_authorized():
                print("A Telegram session is still logged in here; run logout first to replace it.", file=sys.stderr)
                return 1
        finally:
            await client.disconnect()
    client = make_client(StringSession(), api_id, api_hash)
    await client.start(phone=lambda: input("Phone number with country code (e.g. +81…): ").strip(),
                       code_callback=lambda: input("Login code (sent to your Telegram app): ").strip(),
                       password=lambda: getpass.getpass("Two-step verification password: "))
    try:
        me = await client.get_me()
        secret_put(SESSION, client.session.save())
    finally:
        await client.disconnect()
    # A fresh login starts a fresh update state and entity cache.
    store.session_path(state).unlink(missing_ok=True)
    print(f"Logged in as {display_name(me)}{' (@' + me.username + ')' if getattr(me, 'username', None) else ''}. "
          "The session is in the Keychain (project hermes, scope telegram-access).")
    return 0


async def logout() -> int:
    state = store.state_dir(create=True)
    string = secret_get(SESSION, required=False)
    if string:
        api_id, api_hash = api_credentials()
        client = make_client(make_session(store.session_path(state), string), api_id, api_hash)
        try:
            await client.connect()
            if await client.is_user_authorized():
                await client.log_out()
                print("Ended the session at Telegram.")
        except Exception as exc:  # noqa: BLE001 - forget it locally anyway
            print(f"Could not reach Telegram ({type(exc).__name__}); end the session on the phone under "
                  "Settings > Devices.", file=sys.stderr)
        finally:
            try:
                await client.disconnect()
            except Exception:  # noqa: BLE001
                pass
        secret_remove(SESSION)
    store.session_path(state).unlink(missing_ok=True)
    print("Forgot the session (the mirror stays; delete the state directory to drop it).")
    return 0


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr, format="%(asctime)s telethon: %(message)s")
    command = argv[1] if len(argv) > 1 else "run"
    if command == "run":
        return asyncio.run(run())
    if command == "login":
        return asyncio.run(login())
    if command == "logout":
        return asyncio.run(logout())
    print("usage: sync.py [run | login | logout]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
