"""signal-access sync agent: keeps the local Signal mirror current. Run by launchd
(``local.signal.sync``, ``launchd/signal-sync-launchctl.sh``), never by Hermes.

It owns one ``signal-cli daemon`` child for the linked account, with a JSON-RPC socket in the
state directory and ``--receive-mode manual``: nothing is fetched from Signal until this agent
subscribes, so while it is down messages wait on Signal's server. Each received envelope is
written to ``mirror.db`` in its own transaction. signal-cli has no delivery acknowledgement
towards its clients, so an envelope emitted just before this process dies is lost to the
mirror; the agent therefore never outlives its child or the child it: if either side goes, the
other is stopped and launchd starts both again.

It sends no read receipts or typing indicators (the phone keeps its notifications); signal-cli
sends Signal's normal delivery receipts. Exit codes: 0 when there is nothing to run (no linked
account, or Signal unlinked this device, which needs a new link) or on a stop request; 1 after
any other failure, so launchd restarts it after its throttle. Contract: docs/signal-access.md.
"""

from __future__ import annotations

import collections
import importlib.util
import os
from pathlib import Path
import shutil
import signal
import sqlite3
import subprocess
import sys
import threading
import time

HERE = Path(__file__).resolve().parent


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"hermes_signal_{name}", HERE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


store = _load("store")
rpc = _load("rpc")

CLI_FALLBACKS = ("/opt/homebrew/bin/signal-cli", "/usr/local/bin/signal-cli")
SOCKET_WAIT = 180          # a native signal-cli starts in seconds; the first start migrates data
REFRESH_EVERY = 1800       # contacts and groups
POLL = 5.0
DRAIN = 10.0               # reading what the daemon emitted before it exited
MIN_FREE = 64 * 1024 * 1024
UNLINKED = ("not registered", "authorizationfailed", "authorization failed", "unregistered user",
            "devicelimitexceeded", "account is not registered")

_stop = threading.Event()


class StorageError(Exception):
    """The mirror cannot be written: receiving must stop, or every further envelope is lost."""


def log(message: str) -> None:
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}", file=sys.stderr, flush=True)


def cli_path() -> str:
    found = shutil.which("signal-cli")
    if found:
        return found
    for candidate in CLI_FALLBACKS:
        if os.access(candidate, os.X_OK):
            return candidate
    raise SystemExit("signal-cli is not installed (brew install signal-cli)")


class Child:
    """The signal-cli daemon; its stderr is passed through to this log, and the tail kept."""

    def __init__(self, argv: list[str]):
        self.tail: collections.deque[str] = collections.deque(maxlen=60)
        self.proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.PIPE, text=True, errors="replace")
        self.reader = threading.Thread(target=self._pump, daemon=True)
        self.reader.start()

    def _pump(self) -> None:
        for line in self.proc.stderr:
            line = line.rstrip("\n")
            self.tail.append(line)
            print(f"signal-cli: {line}", file=sys.stderr, flush=True)

    def alive(self) -> bool:
        return self.proc.poll() is None

    def stop(self) -> None:
        if self.proc.poll() is not None:
            return
        self.proc.terminate()
        try:
            self.proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(timeout=5)

    def unlinked(self) -> bool:
        text = "\n".join(self.tail).lower()
        return any(marker in text for marker in UNLINKED)


def daemon_argv(cli: str, state: Path, number: str) -> list[str]:
    return [cli, "--data-dir", str(store.data_dir(state)), "-a", number, "--scrub-log",
            "daemon", "--socket", str(store.socket_path(state)), "--receive-mode", "manual",
            "--no-receive-stdout", "--ignore-stories", "--ignore-avatars", "--ignore-stickers"]


def wait_for_socket(child: Child, path: Path, seconds: float) -> rpc.Connection | None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline and not _stop.is_set():
        if not child.alive():
            return None
        if path.exists():
            try:
                return rpc.Connection(path, timeout=10)
            except rpc.NotConnected:
                pass
        time.sleep(0.5)
    return None


def refresh(conn, sock: Path) -> None:
    """Contacts and groups, on a short connection of their own; a failure only waits for the next round."""
    try:
        contacts = rpc.call(sock, "listContacts", {"allRecipients": True}, timeout=60) or []
        groups = rpc.call(sock, "listGroups", {"detailed": True}, timeout=60) or []
    except Exception as exc:  # noqa: BLE001 - logged, retried next round
        log(f"refresh failed: {type(exc).__name__}: {exc}")
        return
    conn.execute("BEGIN IMMEDIATE")
    try:
        counted = (store.upsert_contacts(conn, contacts), store.upsert_groups(conn, groups))
        store.set_meta(conn, groups_stale=0, refreshed=store.now_ms())
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    log(f"refreshed {counted[0]} contacts, {counted[1]} groups")


def apply(conn, payload: dict, me: str, state: Path) -> None:
    """Store one envelope. A malformed one is logged and skipped; a mirror that cannot be written
    raises StorageError, because receiving on would lose every envelope that follows."""
    if payload.get("exception"):
        log(f"receive error from signal-cli: {str(payload['exception'])[:200]}")
    try:
        conn.execute("BEGIN IMMEDIATE")
    except sqlite3.Error as exc:
        raise StorageError(str(exc)) from exc
    try:
        done = store.ingest(conn, payload, me=me, state=state)
        store.set_meta(conn, last_event=store.now_ms())
        conn.execute("COMMIT")
    except (sqlite3.IntegrityError, sqlite3.ProgrammingError, sqlite3.InterfaceError) as exc:
        # this envelope's data, not the mirror
        _rollback(conn)
        log(f"could not store an event: {exc}")
        return
    except (sqlite3.DatabaseError, OSError) as exc:
        _rollback(conn)
        raise StorageError(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - one malformed envelope must not stop the mirror
        _rollback(conn)
        log(f"could not store an event: {type(exc).__name__}: {exc}")
        return
    log("event: " + ",".join(done))  # what happened, never content


def _rollback(conn) -> None:
    try:
        conn.execute("ROLLBACK")
    except sqlite3.Error:
        pass


def _receive(conn, message: dict, me: str, state: Path) -> None:
    if message.get("method") != "receive":
        return
    params = message.get("params") or {}
    payload = params.get("result") if "subscription" in params else params
    apply(conn, payload or {}, me, state)


def subscribe(conn, sub: rpc.Connection, me: str, state: Path):
    """subscribeReceive on the agent's own connection; anything received before its answer is kept."""
    request = {"jsonrpc": "2.0", "id": 1, "method": "subscribeReceive"}
    sub.write(request)
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        message = sub.readline(max(0.0, deadline - time.monotonic()))
        if message is None:
            break
        if message.get("id") == 1:
            if "error" in message:
                raise rpc.RpcError((message["error"] or {}).get("code"), (message["error"] or {}).get("message"))
            return message.get("result")
        _receive(conn, message, me, state)
    raise rpc.NoAnswer("signal-cli did not answer subscribeReceive")


def drain(conn, sub: rpc.Connection, me: str, state: Path) -> None:
    """The daemon is exiting: store what it emitted before the connection closes."""
    deadline = time.monotonic() + DRAIN
    while time.monotonic() < deadline:
        try:
            message = sub.readline(max(0.0, deadline - time.monotonic()))
        except (EOFError, OSError, ValueError):
            return
        if message is None:
            return
        _receive(conn, message, me, state)


def follow(conn, sub: rpc.Connection, child: Child, me: str, state: Path) -> str:
    """Store every received envelope until a stop request, the child exiting, or the socket closing."""
    sock = store.socket_path(state)
    sub_id = subscribe(conn, sub, me, state)
    log(f"subscribed (subscription {sub_id})")
    store.set_meta(conn, status="running", started=store.now_ms(), error=None)
    refresh(conn, sock)
    next_refresh = time.monotonic() + REFRESH_EVERY
    while not _stop.is_set():
        if not child.alive():
            drain(conn, sub, me, state)
            return "child"
        try:
            message = sub.readline(POLL)
        except EOFError:
            return "socket"
        if message is not None:
            _receive(conn, message, me, state)
        if time.monotonic() >= next_refresh or store.get_meta(conn).get("groups_stale") == "1":
            refresh(conn, sock)
            next_refresh = time.monotonic() + REFRESH_EVERY
    return "stop"


def run() -> int:
    os.umask(0o077)
    state = store.state_dir(create=True)
    account = store.linked_account(state)
    conn = store.connect(store.db_path(state), write=True)
    if not account:
        store.set_meta(conn, status="not linked", error=None)
        log("no linked Signal account; link one with signal-sync-launchctl.sh link")
        return 0
    if account.get("registered") is False:
        store.set_meta(conn, status="unlinked", error="Signal unlinked this device; link it again")
        log("this device is no longer linked; run signal-sync-launchctl.sh link")
        return 0
    me = account.get("uuid") or ""
    if shutil.disk_usage(state).free < MIN_FREE:
        store.set_meta(conn, status="failed", error="the disk is nearly full; not receiving until there is room")
        log("the disk is nearly full; not receiving (messages wait on Signal's server)")
        time.sleep(60)
        return 1
    store.set_meta(conn, account=account["number"], uuid=me, status="starting")
    sock = store.socket_path(state)
    sock.unlink(missing_ok=True)
    child = Child(daemon_argv(cli_path(), state, account["number"]))
    reason = "start"
    try:
        sub = wait_for_socket(child, sock, SOCKET_WAIT)
        if sub is None:
            reason = "stop" if _stop.is_set() else ("child" if not child.alive() else "socket-timeout")
        else:
            with sub:
                reason = follow(conn, sub, child, me, state)
    except StorageError as exc:
        reason = f"the mirror cannot be written ({exc}); receiving stopped"
    except Exception as exc:  # noqa: BLE001 - recorded, then launchd restarts the agent
        reason = f"error: {type(exc).__name__}: {exc}"
    finally:
        if reason == "socket":  # the daemon hung up: usually because it is exiting; see why
            try:
                child.proc.wait(timeout=10)
                reason = "child"
            except subprocess.TimeoutExpired:
                pass
        code = child.proc.poll()
        child.stop()
        child.reader.join(timeout=5)  # the whole stderr tail, for the unlink check below
        sock.unlink(missing_ok=True)
    if reason == "stop":
        store.set_meta(conn, status="stopped", error=None)
        log("stopped")
        return 0
    relinked = store.linked_account(state) or {}
    if child.unlinked() or relinked.get("registered") is False:
        store.set_meta(conn, status="unlinked", error="Signal unlinked this device; link it again")
        log("Signal unlinked this device; staying down until it is linked again")
        return 0
    detail = reason if reason != "child" else f"signal-cli exited ({code})"
    try:
        store.set_meta(conn, status="failed", error=detail)
    except sqlite3.Error:
        pass
    log(f"sync ended: {detail}; launchd restarts it")
    return 1


def main() -> int:
    for name in ("SIGTERM", "SIGINT", "SIGHUP"):
        signal.signal(getattr(signal, name), lambda *_: _stop.set())
    return run()


if __name__ == "__main__":
    sys.exit(main())
