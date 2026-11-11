"""mandate_store: the persistence half of a mandate, shared by the plugins that keep one.

A mandate is the user's standing approval for a bounded kind of change, made on a card of its own.
What its terms are, and whether a change fits them, is the plugin's; what is kept, authenticated and
in force is the same everywhere, so it lives here. State, in the profile home (never the repository;
the plugin's guard blocks file and terminal access):

  <HERMES_HOME>/<state>/mandates/<id>.json   the terms, MAC'd
  <HERMES_HOME>/<state>/head.json            the ids in force, MAC'd: only the head decides
  <HERMES_HOME>/<state>/mandates.jsonl       made / revoked history, for the record only

The MAC key is a random key in the Keychain (``<key_prefix><PROFILE>``, project hermes, the store's
scope, a scope no profile receives), made with the first mandate and read afresh every time. Without
a readable key no mandate is in force. Each plugin describes itself with a ``Store``; the functions
take it first. A mandate and the head are MAC'd under the store's ``mac_kind`` (the head under
``<mac_kind>-head``), so one store's files never verify as another's.

Shared by the plugins that keep mandates (each loads this file by path as ``hermes_mandate_store``;
it is not a plugin and has no manifest). Contract: docs/access-common.md (mandates).
"""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import threading
import time
from typing import Callable, NamedTuple, Optional

SECRET = Path.home() / ".config" / "bin" / "secret"
VAULT_PROJECT = "hermes"
SECRET_TIMEOUT = 20
DAY = 86400         # seconds
KEY_HEX = re.compile(r"[0-9a-f]{64}")
ID_DIGITS = 8   # hex digits after the prefix

# One thread lock per state directory name; the file lock beside the state serializes processes.
_LOCKS: dict[str, threading.Lock] = {}


# NamedTuple, not dataclass: a dataclass looks its module up in sys.modules, which a module loaded
# by path need not be in.
class Store(NamedTuple):
    """How one plugin keeps its mandates."""

    state: str          # directory name under the profile home, e.g. "cloudflare-access"
    key_prefix: str     # Keychain item name prefix, e.g. "CLOUDFLARE_MANDATE_KEY_"
    scope: str          # Keychain scope, e.g. "cloudflare-access"
    mac_kind: str       # what a mandate is MAC'd as, e.g. "cloudflare-mandate"; the head adds "-head"
    key_note: str       # the description stored with the key
    error: type         # raised for storage problems
    max_days: int = 30  # the longest a mandate may run; the plugin's terms are held to it
    id_prefix: str = "m"   # ids are id_prefix + 8 hex digits


KeyOf = Callable[..., Optional[bytes]]                     # (home, create=False) -> the MAC key or None
RunCli = Callable[..., subprocess.CompletedProcess]        # (home, command, extra=(), value=None)


def thread_lock(store: Store) -> threading.Lock:
    """The in-process lock of the store's state directory."""
    return _LOCKS.setdefault(store.state, threading.Lock())


def state_dir(store: Store, home) -> Path:
    return Path(home) / store.state


def vault_name(store: Store, home) -> str:
    """The Keychain item of the profile at ``home``: the prefix and the profile's name, upper-cased."""
    home = Path(os.path.expanduser(str(home)))
    name = "default" if home == Path.home() / ".hermes" else home.name
    return store.key_prefix + (re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_") or "DEFAULT")


def valid_id(store: Store, text) -> bool:
    """Whether ``text`` has the shape of one of the store's mandate ids."""
    return isinstance(text, str) and bool(
        re.match(rf"^{re.escape(store.id_prefix)}[0-9a-f]{{{ID_DIGITS}}}$", text))


@contextlib.contextmanager
def locked(store: Store, home):
    """The state directory (made if absent) held exclusively by this thread and process."""
    folder = state_dir(store, home)
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    with thread_lock(store), open(folder / ".lock", "a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield folder
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


# --- the key --------------------------------------------------------------------------------------

def call_secret(store: Store, home, command: str, extra: tuple = (), value: Optional[str] = None,
                cli: Optional[Path] = None, timeout: Optional[int] = None) -> subprocess.CompletedProcess:
    """One call of the secret CLI on the profile's key (``cli`` and ``timeout`` default to the
    module's ``SECRET`` and ``SECRET_TIMEOUT``, read now)."""
    cli = SECRET if cli is None else cli
    timeout = SECRET_TIMEOUT if timeout is None else timeout
    if not os.access(cli, os.X_OK):
        raise store.error(f"the secret CLI is missing at {cli}")
    argv = [str(cli), command, vault_name(store, home), "-p", VAULT_PROJECT, "--scope", store.scope, *extra]
    feed = {"input": value + "\n"} if value is not None else {"stdin": subprocess.DEVNULL}
    if value is not None:
        argv.append("--stdin")
    folder = state_dir(store, home)
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=timeout,
                              cwd=str(folder) if folder.is_dir() else None, **feed)
    except subprocess.TimeoutExpired as exc:
        raise store.error("the Keychain did not answer in time") from exc


def key(store: Store, home, create: bool = False, run: Optional[RunCli] = None) -> Optional[bytes]:
    """The MAC key, read from the Keychain every time (never cached: a removed or replaced key takes
    effect at once); None when there is none (and ``create`` is off) or it cannot be read. ``run``
    makes the CLI calls as ``run(home, command, extra, value=)`` (default: ``call_secret`` on the store)."""
    run = run or (lambda h, command, extra=(), value=None: call_secret(store, h, command, extra, value))
    try:
        proc = run(home, "get")
    except store.error:
        return None
    value = proc.stdout.strip()
    if proc.returncode == 0 and KEY_HEX.fullmatch(value):
        return bytes.fromhex(value)
    if not create or run(home, "show").returncode == 0:
        return None  # absent, or present but unreadable: never written over
    made = secrets.token_hex(32)
    proc = run(home, "set", ("-D", "key", "-j", store.key_note), value=made)
    if proc.returncode != 0:
        raise store.error(f"could not store {vault_name(store, home)} in the Keychain: {proc.stderr.strip()[:200]}")
    return key(store, home, run=run)


def mac(secret: bytes, kind: str, body: dict) -> str:
    """The HMAC-SHA256 of ``body`` (its own ``mac`` left out) under ``kind``."""
    text = json.dumps({"kind": kind, **{k: v for k, v in body.items() if k != "mac"}}, sort_keys=True,
                      separators=(",", ":"), ensure_ascii=False)
    return hmac.new(secret, text.encode("utf-8"), hashlib.sha256).hexdigest()


# --- the files ------------------------------------------------------------------------------------

def write(path: Path, body: dict) -> None:
    """``body`` as JSON at ``path``, 0600 in a 0700 directory, replaced whole."""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(body, ensure_ascii=False, indent=1), encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def read(path: Path) -> Optional[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def log(store: Store, home, event: str, mandate_id: str) -> None:
    with open(state_dir(store, home) / "mandates.jsonl", "a", encoding="utf-8") as handle:
        handle.write(json.dumps({"event": event, "mandate": mandate_id, "time": int(time.time())}) + "\n")


# --- what is in force -----------------------------------------------------------------------------

def active_ids(store: Store, home, secret: bytes) -> list[str]:
    """The ids in the authenticated head; none when the head is missing, edited or unreadable."""
    head = read(state_dir(store, home) / "head.json")
    if not head or not isinstance(head.get("active"), list):
        return []
    if not hmac.compare_digest(str(head.get("mac", "")), mac(secret, f"{store.mac_kind}-head", head)):
        return []
    return [i for i in head["active"] if valid_id(store, i)]


def set_head(store: Store, home, secret: bytes, ids: list[str]) -> None:
    head = {"active": sorted(set(ids)), "time": int(time.time())}
    head["mac"] = mac(secret, f"{store.mac_kind}-head", head)
    write(state_dir(store, home) / "head.json", head)


def load(store: Store, home, secret: bytes, mandate_id: str) -> Optional[dict]:
    """One mandate's stored body, if its file is its own and authentic."""
    body = read(state_dir(store, home) / "mandates" / f"{mandate_id}.json")
    if not body or body.get("id") != mandate_id:
        return None
    if not hmac.compare_digest(str(body.get("mac", "")), mac(secret, store.mac_kind, body)):
        return None
    return body


def active(store: Store, home, now: Optional[float] = None, key_of: Optional[KeyOf] = None) -> list[dict]:
    """The mandates in force: in the authenticated head, authenticated themselves, not ended.
    ``key_of(home)`` reads the key (default: ``key`` on the store)."""
    secret = key_of(home) if key_of else key(store, home)
    if secret is None:
        return []
    now = time.time() if now is None else now
    out = []
    for mandate_id in active_ids(store, home, secret):
        body = load(store, home, secret, mandate_id)
        if body and isinstance(body.get("expires"), (int, float)) and now < body["expires"]:
            out.append(body)
    return out


def create(store: Store, home, fields: dict, expires: int, key_of: Optional[KeyOf] = None) -> dict:
    """Make a mandate with the plugin's ``fields`` ending at ``expires``: stored, put in the head and
    logged. Returns the stored body. ``key_of(home, create=)`` reads or makes the key (default: ``key``
    on the store)."""
    with locked(store, home):
        secret = key_of(home, create=True) if key_of else key(store, home, create=True)
        if secret is None:
            raise store.error(
                f"{vault_name(store, home)} is in the Keychain but could not be read; nothing was made")
        now = int(time.time())
        if expires <= now:
            raise store.error("the mandate's end on its card has already passed; nothing was made")
        # The terms are held to the ceiling when they are made; the store holds every consumer to it
        # again, so a forgotten mandate lapses on its own whichever plugin made it.
        if expires > now + store.max_days * DAY:
            raise store.error(f"a mandate runs at most {store.max_days} days; nothing was made")
        body = {"id": store.id_prefix + secrets.token_hex(ID_DIGITS // 2), "created": now, "expires": expires,
                **fields}
        body["mac"] = mac(secret, store.mac_kind, body)
        write(state_dir(store, home) / "mandates" / f"{body['id']}.json", body)
        set_head(store, home, secret, active_ids(store, home, secret) + [body["id"]])
        log(store, home, "made", body["id"])
    return body


def revoke(store: Store, home, mandate_id: str, key_of: Optional[KeyOf] = None) -> dict:
    """Take a mandate out of the head (its file stays, as the record)."""
    if not valid_id(store, mandate_id):
        raise store.error(f"mandate is an id like {store.id_prefix}1a2b3c4d")
    with locked(store, home):
        secret = key_of(home) if key_of else key(store, home)
        if secret is None:
            return {"revoked": mandate_id, "note": "no mandate key: none was in force"}
        ids = active_ids(store, home, secret)
        if mandate_id not in ids:
            return {"revoked": mandate_id, "note": "it was not in force"}
        set_head(store, home, secret, [i for i in ids if i != mandate_id])
        log(store, home, "revoked", mandate_id)
    return {"revoked": mandate_id}
