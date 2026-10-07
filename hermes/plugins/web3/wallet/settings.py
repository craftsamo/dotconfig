"""The wallet's settings and send ledger (docs/web3.md "Accounts" and "Approval").

Pure Python, used by the plugin in Hermes' interpreter (which reads ``<profile home>/web3-wallet.yaml``
on every call) and by the signer in the engine venv (which re-checks what it is given). The settings
name seeds and accounts and open mainnets; nothing in them can lift the approval rule or the hourly
cap, which are code.

    mainnet: false          # true lets mainnet chains sign; testnets always may
    seeds: [main, work]     # Keychain items WEB3_SEED_MAIN, WEB3_SEED_WORK (project hermes, scope web3-wallet)
    accounts:               # role: <seed>/<index>
      ops: main/0
      lab: main/1
      work: work/0
"""

from __future__ import annotations

from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import re
import time

NAME = re.compile(r"^[a-z][a-z0-9-]{0,31}$")
ACCOUNT = re.compile(r"^([a-z][a-z0-9-]{0,31})/(\d{1,10})$")
MAX_INDEX = 2 ** 31 - 1
MAX_PER_HOUR = 10       # transfers per hour, every account and recipient together
HOUR = 3600
COUNTED = ("sent", "unknown")  # ledger outcomes that may have moved funds
FILE = "web3-wallet.yaml"


class SettingsError(Exception):
    pass


def seed_item(name: str) -> str:
    """The Keychain item of a seed: 'work-x' → WEB3_SEED_WORK_X."""
    return "WEB3_SEED_" + name.upper().replace("-", "_")


def parse(raw) -> dict:
    """The normalized settings, or SettingsError naming the first problem."""
    if not isinstance(raw, dict):
        raise SettingsError(f"{FILE} is missing or empty in this profile")
    mainnet = raw.get("mainnet", False)
    if not isinstance(mainnet, bool):
        raise SettingsError("mainnet must be true or false")
    seeds = raw.get("seeds") or []
    if not isinstance(seeds, list) or not seeds:
        raise SettingsError("seeds must list at least one seed name, like [main]")
    for name in seeds:
        if not isinstance(name, str) or not NAME.match(name):
            raise SettingsError(f"seed name {name!r}: lowercase letters, digits and dashes")
    if len(set(seeds)) != len(seeds):
        raise SettingsError("a seed is listed twice")
    accounts_raw = raw.get("accounts") or {}
    if not isinstance(accounts_raw, dict) or not accounts_raw:
        raise SettingsError("accounts must name at least one account, like ops: main/0")
    accounts = {}
    for role, spec in accounts_raw.items():
        if not isinstance(role, str) or not NAME.match(role):
            raise SettingsError(f"account name {role!r}: lowercase letters, digits and dashes")
        if isinstance(spec, dict):  # the normalized form, as the plugin passes it on
            spec = f"{spec.get('seed')}/{spec.get('index')}"
        found = ACCOUNT.match(str(spec))
        if not found:
            raise SettingsError(f"account {role}: write <seed>/<index>, like main/0")
        seed, index = found.group(1), int(found.group(2))
        if seed not in seeds:
            raise SettingsError(f"account {role}: seed {seed!r} is not in seeds")
        if index > MAX_INDEX:
            raise SettingsError(f"account {role}: index is too large")
        accounts[role] = {"seed": seed, "index": index}
    pairs = [(a["seed"], a["index"]) for a in accounts.values()]
    if len(set(pairs)) != len(pairs):
        raise SettingsError("two accounts name the same seed and index")
    return {"mainnet": mainnet, "seeds": list(seeds), "accounts": accounts}


def chain_allowed(settings: dict, testnet: bool) -> bool:
    return testnet or settings["mainnet"]


# --- ledger -------------------------------------------------------------------------------------

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


def entries(state: Path, since: float) -> list[dict]:
    """Ledger rows since a time; a send is written before broadcast and again with its outcome, so
    the last row per quote wins."""
    path = state / "ledger.jsonl"
    if not path.exists():
        return []
    rows: dict[str, dict] = {}
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("time", 0) >= since:
            rows[str(row.get("quote") or f"line-{n}")] = row
    return list(rows.values())


def append(state: Path, row: dict) -> None:
    path = state / "ledger.jsonl"
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    with os.fdopen(fd, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def check_rate(state: Path, now: float | None = None) -> None:
    """SettingsError when MAX_PER_HOUR sends that may have moved funds happened in the last hour."""
    now = now or time.time()
    recent = [r for r in entries(state, now - HOUR) if r.get("outcome") in COUNTED]
    if len(recent) >= MAX_PER_HOUR:
        raise SettingsError(f"{MAX_PER_HOUR} transfers in the last hour is the limit; wait and try again")
