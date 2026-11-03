"""mandate_ledger: the use ledger of a mandate, shared by the plugins that count how often one is used.

A mandate that allows so many uses in a window (an hour) needs a count that cannot be reset by whoever
can write files. What the count is of, the window, the bound and what a use must fit are the plugin's;
how the uses are recorded and read back is the same everywhere, so it lives here. State, in the profile
home next to the mandate store's (``plugins/_shared/mandate_store.py``):

  <HERMES_HOME>/<state>/uses.jsonl   one MAC'd opening row per mandate, then one per counted use

Each row is MAC'd under the consumer's ``mac_kind`` (a use is ``{mandate, time, mac}``, the opening row
``{mandate, time, open, mac}``), so one consumer's rows never verify as another's. ``anchor`` writes the
opening row when the mandate is made; a mandate without one counts as used up. The ledger fails closed:
no readable key, and any ledger that is not a plain file of this user (opened without following links),
or cannot be read, count as used up, so a deleted, emptied or replaced ledger blocks instead of resetting
the count. ``take`` is the check and the count in one step; it must run under ``mandate_store.locked``,
which the caller holds because it reads the mandate there too.

Shared by the plugins that keep a mandate with an hourly bound (each loads this file by path as
``hermes_mandate_ledger``; it is not a plugin and has no manifest). The row format and the file stay as
they are, or every ledger in use stops verifying.
"""

from __future__ import annotations

import hmac
import importlib.util
import json
import os
import stat
import sys
from pathlib import Path
from typing import Callable, Optional


def _load(name, path):
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


mandate_store = _load("hermes_mandate_store", Path(__file__).resolve().parent / "mandate_store.py")

USES_FILE = "uses.jsonl"
USE, OPENING = "use", "opening"   # the two kinds of ledger row
USE_KEYS = {"mandate", "time", "mac"}
OPENING_KEYS = USE_KEYS | {"open"}

Fits = Callable[[int], Optional[str]]   # (the window's count) -> why the use does not fit, or None
Write = Callable[[dict], None]          # (a ledger row) -> None; how a row reaches the file


class UsedUp(int):
    """The count of a ledger that cannot be vouched for. A consumer makes one instance, equal to the count
    at which every mandate of it reads as used up, so ``fits`` can still tell it from a real count that
    reached the same number (``isinstance(used, UsedUp)``)."""


def uses_path(store: mandate_store.Store, home) -> Path:
    return mandate_store.state_dir(store, home) / USES_FILE


def row(secret: bytes, mac_kind: str, mandate_id: str, at: int, opening: bool = False) -> dict:
    """A MAC'd ledger row: one counted use, or (``opening``) the anchor ``anchor`` writes for the mandate."""
    body = {"mandate": mandate_id, "time": at, **({"open": True} if opening else {})}
    return {**body, "mac": mandate_store.mac(secret, mac_kind, body)}


def _row_kind(secret: bytes, mac_kind: str, entry, mandate_id: str) -> str | None:
    """OPENING or USE for a row that is the mandate's own and authentic, else None."""
    if not isinstance(entry, dict) or entry.get("mandate") != mandate_id:
        return None
    if set(entry) == USE_KEYS:
        opening = False
    elif set(entry) == OPENING_KEYS and entry["open"] is True:
        opening = True
    else:
        return None
    if not isinstance(entry["time"], int) or isinstance(entry["time"], bool):
        return None
    good = row(secret, mac_kind, mandate_id, entry["time"], opening)["mac"]
    if not hmac.compare_digest(str(entry["mac"]), good):
        return None
    return OPENING if opening else USE


def _own_file(info: os.stat_result) -> bool:
    """Whether ``info`` is a regular file owned by the current user."""
    return stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid()


def _lines(store: mandate_store.Store, home) -> list[str] | None:
    """The ledger's lines: none yet when the file does not exist; None when it cannot be trusted (a
    link, a device, a directory, another owner, unreadable). Opened without following links."""
    try:
        fd = os.open(uses_path(store, home), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return []
    except OSError:
        return None
    try:
        if not _own_file(os.fstat(fd)):
            return None
        with os.fdopen(fd, encoding="utf-8", errors="replace", closefd=False) as handle:
            return handle.read().splitlines()
    except OSError:
        return None
    finally:
        os.close(fd)


def count(store: mandate_store.Store, home, secret: bytes | None, mac_kind: str, mandate_id: str, now: float,
          window: int, used_up: UsedUp) -> int:
    """How many counted uses of the mandate lie in the ``window`` seconds before ``now``: rows with a valid
    MAC only, so a bad or foreign row counts for nothing. Everything that cannot be vouched for counts as
    ``used_up``: no readable key (``secret`` is None), a ledger that is not a plain file of this user or
    cannot be read, and a mandate whose opening row is missing."""
    if secret is None:
        return used_up
    lines = _lines(store, home)
    if lines is None:
        return used_up
    used, anchored = 0, False
    for text in lines:
        try:
            entry = json.loads(text)
        except ValueError:
            continue
        kind = _row_kind(secret, mac_kind, entry, mandate_id)
        if kind == OPENING:
            anchored = True
        elif kind == USE and now - entry["time"] < window:
            used += 1
    return used if anchored else used_up


def append_rows(store: mandate_store.Store, home, entries: list[dict]) -> None:
    """The rows at the end of the ledger in one write, which must be (or become) a plain file of this user: a
    link is never followed, so nothing is written through one."""
    fd = os.open(uses_path(store, home), os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK,
                 0o600)
    try:
        if not _own_file(os.fstat(fd)):
            raise OSError("the ledger is not a plain file of this user")
        data = memoryview("".join(json.dumps(entry) + "\n" for entry in entries).encode("utf-8"))
        while data:
            data = data[os.write(fd, data):]
        os.fsync(fd)
    finally:
        os.close(fd)


def append(store: mandate_store.Store, home, entry: dict) -> None:
    """One row at the end of the ledger (see ``append_rows``)."""
    append_rows(store, home, [entry])


def _put(store: mandate_store.Store, home, entry: dict, write: Write | None) -> None:
    (write or (lambda made: append(store, home, made)))(entry)


def anchor(store: mandate_store.Store, home, secret: bytes, mac_kind: str, mandate_id: str, created: int,
           write: Write | None = None) -> None:
    """The mandate's opening row, written at ``created``; without it the mandate counts as used up. Raises
    OSError when the ledger cannot be written. ``write`` replaces ``append`` as the way a row is written."""
    _put(store, home, row(secret, mac_kind, mandate_id, created, opening=True), write)


def take(store: mandate_store.Store, home, secret: bytes, mac_kind: str, mandate_id: str, now: float,
         window: int, used_up: UsedUp, fits: Fits, write: Write | None = None, weight: int = 1) -> str | None:
    """Count ``weight`` uses at ``now`` if they fit: the window's count is read afresh, ``fits(used)`` says
    why the uses do not fit (returned, nothing written; it knows the weight, the caller's closure) or None,
    and only then are ``weight`` identical use rows written, in one write by default. Run under
    ``mandate_store.locked(store, home)``, so the last slots of a window go to one caller. Raises OSError
    when the rows cannot be written. ``write`` replaces the file write: it is handed each row in turn."""
    if not isinstance(weight, int) or isinstance(weight, bool) or weight < 1:
        raise ValueError("weight is a whole number of at least 1")
    used = count(store, home, secret, mac_kind, mandate_id, now, window, used_up)
    why = fits(used)
    if why is None:
        made = row(secret, mac_kind, mandate_id, int(now))
        if write is None:
            append_rows(store, home, [made] * weight)
        else:
            for _ in range(weight):
                write(made)
    return why
