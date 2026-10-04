"""Shared test helpers: a private state directory with a seeded mirror, Telethon-shaped objects,
a fake Telethon client and a fake sync agent answering on a UNIX socket. Never the real
Telegram, Keychain or state."""

import asyncio
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import threading
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
ME = 1000
ALICE = 2001
BOT = 3001
HERMES_BOT = 3999
GROUP = -4001
SUPER = -1000000005001
CHANNEL = -1000000006001


def load(name):
    key = f"hermes_telegram_{name}"
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[key] = module
    spec.loader.exec_module(module)
    return module


def short_dir() -> Path:
    """UNIX socket paths are limited to ~104 bytes on macOS; pytest's tmp_path is too long."""
    return Path(tempfile.mkdtemp(prefix="tg-", dir="/tmp"))


def seed(state: Path, *, logged_in=True):
    """A mirror with the account, five chats and a few messages."""
    store = load("store")
    conn = store.connect(store.db_path(state), write=True)
    if logged_in:
        store.set_meta(conn, me_id=ME, me_name="Rui", me_username="rui", me_phone="+819000000000", status="running")
    now = store.now_ms()
    store.upsert_chat(conn, ME, kind="self", name="Rui", username="rui")
    store.upsert_chat(conn, ALICE, kind="user", name="Alice", username="alice", phone="+819011111111",
                      last_ts=now - 1000, unread=2)
    store.upsert_chat(conn, BOT, kind="bot", name="Weather", username="weatherbot", last_ts=now - 2000)
    store.upsert_chat(conn, HERMES_BOT, kind="bot", name="Hermes", username="hermesbot", last_ts=now - 500)
    store.upsert_chat(conn, GROUP, kind="group", name="Family", last_ts=now - 3000, can_send=1)
    store.upsert_chat(conn, SUPER, kind="supergroup", name="Big group", username="biggroup", last_ts=now - 4000,
                      can_send=1)
    store.upsert_chat(conn, CHANNEL, kind="channel", name="News", username="news", last_ts=now - 5000, can_send=0)
    for row in (
        {"chat": ALICE, "id": 10, "ts": now - 60000, "sender": ALICE, "sender_name": "Alice", "body": "明日の打ち合わせは？"},
        {"chat": ALICE, "id": 11, "ts": now - 50000, "from_me": True, "sender": ME, "body": "10時でお願いします",
         "reply_to": 10},
        {"chat": ALICE, "id": 12, "ts": now - 40000, "sender": ALICE, "sender_name": "Alice", "body": None,
         "media": {"type": "photo", "mime": "image/jpeg", "size": 2048}},
        {"chat": ALICE, "id": 13, "ts": now - 30000, "sender": ALICE, "sender_name": "Alice", "body": "gone soon",
         "expires": now - 1},
        {"chat": HERMES_BOT, "id": 20, "ts": now - 20000, "sender": HERMES_BOT, "sender_name": "Hermes",
         "body": "secret topic"},
        {"chat": GROUP, "id": 30, "ts": now - 10000, "sender": ALICE, "sender_name": "Alice", "body": "打ち合わせ 了解"},
    ):
        store.upsert_message(conn, row)
    conn.close()


# --- Telethon-shaped objects --------------------------------------------------------------------

def obj(cls_name: str, **attrs):
    """An instance of a class with Telethon's class name (the normalisers duck-type on it)."""
    return _with(type(cls_name, (), {})(), attrs)


def _with(instance, attrs):
    for key, value in attrs.items():
        setattr(instance, key, value)
    return instance


def user(id_, first="Alice", last=None, username=None, phone=None, bot=False, is_self=False):
    return obj("User", id=id_, first_name=first, last_name=last, username=username, phone=phone, bot=bot,
               is_self=is_self, deleted=False)


def when(seconds_ago=0):
    return datetime.fromtimestamp(datetime.now(tz=timezone.utc).timestamp() - seconds_ago, tz=timezone.utc)


def message(chat, id_, text="hi", *, out=False, sender=None, date=None, media=None, file=None, action=None,
            reply_to=None, ttl_period=None, edit_date=None, **extra):
    attrs = dict(chat_id=chat, id=id_, message=text, out=out, sender_id=getattr(sender, "id", None), sender=sender,
                 date=date or when(), media=media, file=file, action=action, grouped_id=None, post_author=None,
                 reply_to=SimpleNamespace(reply_to_msg_id=reply_to) if reply_to else None, fwd_from=None,
                 edit_date=edit_date, edit_hide=False, ttl_period=ttl_period)
    attrs.update(extra)
    return obj("Message", **attrs)


class RpcFailure(Exception):
    """An RPC error as Telethon raises it: carries the HTTP-like code."""

    def __init__(self, code, message="FAKE_ERROR"):
        super().__init__(message)
        self.code = code


class FakeSender:
    """Telethon's main sender as far as the agent instruments it."""

    def __init__(self):
        self.handed = []

    def send(self, request, ordered=False):
        self.handed.append(type(request).__name__)

    async def _reconnect(self, last_error):
        return None


class FakeClient:
    """The coroutine methods the agent uses, answering from a per-chat list of messages. Sends
    hand their request to the sender (once, or ``deliveries`` times: Telethon's retries)."""

    def __init__(self, history=None, dialogs=None):
        self.history = history or {}
        self.dialogs = dialogs or []
        self.sent = []
        self.uploaded = []
        self.calls = []
        self.send_error = None
        self.next_id = 500
        self.connected = True
        self.deliveries = 1
        self.reconnect_during_send = False
        self._sender = FakeSender()

    async def _deliver(self, request_name):
        for _ in range(self.deliveries):
            self._sender.send(obj(request_name))
        if self.reconnect_during_send:
            await self._sender._reconnect(None)

    def is_connected(self):
        return self.connected

    async def get_me(self):
        return user(ME, "Rui", username="rui", is_self=True)

    async def get_entity(self, chat):
        return user(chat, "Stranger")

    async def get_input_entity(self, chat):
        return ("peer", chat)

    async def iter_dialogs(self):
        for dialog in self.dialogs:
            yield dialog

    async def get_messages(self, chat, limit=None, ids=None, **kwargs):
        self.calls.append(("get_messages", chat, limit, ids, kwargs))
        msgs = sorted(self.history.get(chat, []), key=lambda m: m.id, reverse=True)
        if ids is not None:
            return [next((m for m in msgs if m.id == i), None) for i in ids]
        if "min_id" in kwargs:
            msgs = [m for m in msgs if m.id > kwargs["min_id"]]
        if "max_id" in kwargs:
            msgs = [m for m in msgs if m.id < kwargs["max_id"]]
        if kwargs.get("reverse"):
            offset = kwargs.get("offset_id") or 0
            msgs = sorted([m for m in msgs if m.id > offset], key=lambda m: m.id)
        elif kwargs.get("offset_id"):
            msgs = [m for m in msgs if m.id < kwargs["offset_id"]]
        return msgs[:limit] if limit else msgs

    async def upload_file(self, path):
        self.uploaded.append(path)
        return SimpleNamespace(name=os.path.basename(path))

    async def send_message(self, entity, text, reply_to=None, parse_mode=None):
        await self._deliver("SendMessageRequest")
        if self.send_error:
            raise self.send_error
        self.sent.append(("text", entity, text, reply_to))
        self.next_id += 1
        return message(entity[1], self.next_id, text, out=True)

    async def send_file(self, entity, file, caption=None, reply_to=None, parse_mode=None, force_document=False):
        await self._deliver("SendMultiMediaRequest" if isinstance(file, list) else "SendMediaRequest")
        if self.send_error:
            raise self.send_error
        files = file if isinstance(file, list) else [file]
        self.sent.append(("files", entity, [f.name for f in files], caption, reply_to, force_document))
        out = []
        for index, f in enumerate(files):
            self.next_id += 1
            out.append(message(entity[1], self.next_id, caption if index == 0 else "", out=True,
                               media=obj("MessageMediaDocument"), file=SimpleNamespace(name=f.name, mime_type=None,
                                                                                         size=1, duration=None)))
        return out if isinstance(file, list) else out[0]

    async def download_media(self, msg, file=None):
        path = Path(file) / (getattr(getattr(msg, "file", None), "name", None) or "photo.jpg")
        path.write_bytes(b"\xff\xd8\xff\xe0fake jpeg")
        return str(path)

    async def disconnect(self):
        self.connected = False


def run(coro):
    return asyncio.run(coro)


# --- a fake sync agent on a UNIX socket ---------------------------------------------------------

class FakeAgent:
    """Answers JSON-RPC requests on a UNIX socket with handlers[method](params) -> result, or
    raises FakeError for an error answer. Records every request."""

    def __init__(self, path: Path, handlers: dict):
        self.path = Path(path)
        self.handlers = handlers
        self.requests = []
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(str(self.path))
        self.server.listen(8)
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self):
        while True:
            try:
                conn, _ = self.server.accept()
            except OSError:
                return
            threading.Thread(target=self._client, args=(conn,), daemon=True).start()

    def _client(self, conn):
        buffer = b""
        with conn:
            while True:
                try:
                    chunk = conn.recv(65536)
                except OSError:
                    return
                if not chunk:
                    return
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    request = json.loads(line)
                    self.requests.append(request)
                    handler = self.handlers.get(request["method"])
                    try:
                        if handler is None:
                            raise FakeError("invalid", "unknown method")
                        reply = {"jsonrpc": "2.0", "id": request["id"], "result": handler(request.get("params") or {})}
                    except FakeError as exc:
                        reply = {"jsonrpc": "2.0", "id": request["id"], "error": exc.payload}
                    if reply.get("result") is not NO_REPLY:
                        conn.sendall(json.dumps(reply).encode() + b"\n")

    def close(self):
        self.server.close()
        try:
            os.unlink(self.path)
        except OSError:
            pass


NO_REPLY = object()


class FakeError(Exception):
    def __init__(self, kind, message, **extra):
        super().__init__(message)
        self.payload = {"code": -1, "message": message, "data": {"kind": kind, **extra}}
