"""The wallet's send ledger and hourly caps (docs/web3.md "Approval").

Pure Python, used by the signer in the engine venv. The cap is code, not a setting: nothing the
model or a file can change lifts it. New Hermes wallets keep a ledger of their own
(``wallets.jsonl``, addresses only) under a cap of their own.
"""

from __future__ import annotations

from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import time

MAX_PER_HOUR = 10       # transfers per hour, every account and recipient together
HOUR = 3600
COUNTED = ("sent", "unknown")  # outcomes that may have moved funds
SENDS = "ledger.jsonl"
WALLETS = "wallets.jsonl"
MAX_WALLETS_PER_HOUR = 3
MADE = ("created", "unknown", "unverified")  # outcomes that may have left a new wallet in the Keychain


class CapReached(Exception):
    pass


@contextmanager
def locked(state: Path):
    """The wallet's state lock: quotes and the ledger change only while it is held."""
    state.mkdir(mode=0o700, parents=True, exist_ok=True)
    with open(state / ".lock", "a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def entries(state: Path, since: float, name: str = SENDS) -> list[dict]:
    """Ledger rows since a time; a send attempt is written before broadcast and again with its
    outcome, so the last row per attempt wins (every attempt counts, a repeated quote included)."""
    path = state / name
    if not path.exists():
        return []
    rows: dict[str, dict] = {}
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("time", 0) >= since:
            rows[str(row.get("attempt") or row.get("quote") or f"line-{n}")] = row
    return list(rows.values())


def attempted(state: Path, quote_id: str) -> bool:
    """Whether the ledger has ever recorded a send of this quote."""
    return any(row.get("quote") == quote_id for row in entries(state, 0))


def append(state: Path, row: dict, name: str = SENDS) -> None:
    path = state / name
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    with os.fdopen(fd, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def check_rate(state: Path, now: float | None = None) -> None:
    """CapReached when MAX_PER_HOUR sends that may have moved funds happened in the last hour."""
    now = now or time.time()
    recent = [r for r in entries(state, now - HOUR) if r.get("outcome") in COUNTED]
    if len(recent) >= MAX_PER_HOUR:
        raise CapReached(f"{MAX_PER_HOUR} transfers in the last hour is the limit; wait and try again")


def check_wallet_rate(state: Path, now: float | None = None) -> None:
    """CapReached when MAX_WALLETS_PER_HOUR new wallets may have been made in the last hour."""
    now = now or time.time()
    recent = [r for r in entries(state, now - HOUR, WALLETS) if r.get("outcome") in MADE]
    if len(recent) >= MAX_WALLETS_PER_HOUR:
        raise CapReached(f"{MAX_WALLETS_PER_HOUR} new wallets in the last hour is the limit; wait and try again")
