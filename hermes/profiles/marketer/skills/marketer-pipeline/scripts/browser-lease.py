#!/usr/bin/env python3
"""A persistent advisory lease for cooperating Marketer browser jobs.

An owner spans tool calls; process exit never releases its lease. This is not
identity verification, content approval or a browser sandbox. No expiry/stealing.
Exit: 0 success, 2 usage, 3 busy, 4 wrong owner, 5 unsafe/corrupt state.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path


LEASE_NAME = "marketing-browser-lease.json"
GUARD_NAME = "marketing-browser-lease.guard"


def emit(code, **result):
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return code


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise SystemExit(emit(2, state="error", error=message))


def valid_owner(owner):
    return (isinstance(owner, str) and 1 <= len(owner.encode("utf-8")) <= 256
            and not any(c in owner for c in "\r\n\0"))


def open_regular(path, flags):
    fd = os.open(path, flags | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    if not stat.S_ISREG(os.fstat(fd).st_mode):
        os.close(fd)
        raise ValueError(f"not a regular file: {path.name}")
    return fd


def read_lease(path):
    try:
        fd = open_regular(path, os.O_RDONLY)
    except FileNotFoundError:
        return None
    try:
        raw = os.read(fd, 4097)
    finally:
        os.close(fd)
    if len(raw) > 4096:
        raise ValueError("lease is too large")
    data = json.loads(raw.decode("utf-8"))
    if (not isinstance(data, dict) or not valid_owner(data.get("owner"))
            or not isinstance(data.get("created_at"), str) or not data["created_at"]):
        raise ValueError("malformed lease")
    return {"owner": data["owner"], "created_at": data["created_at"]}


def main():
    parser = Parser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("acquire", "status", "release"):
        command = commands.add_parser(name)
        command.add_argument("--home", required=True)
        if name != "status":
            command.add_argument("--owner", required=True)
    args = parser.parse_args()
    try:
        if not args.home:
            raise ValueError("empty home")
        home = Path(args.home).resolve(strict=True)
        if not home.is_dir():
            raise ValueError("home is not a directory")
        if home.name != "marketer" or home.parent.name != "profiles":
            raise ValueError("home must be the resolved profiles/marketer directory")
        if args.command != "status" and not valid_owner(args.owner):
            raise ValueError("owner must be 1..256 UTF-8 bytes without CR/LF/NUL")
    except (OSError, ValueError, RuntimeError) as exc:
        return emit(2, command=args.command, state="error", error=str(exc))

    guard = None
    try:
        # Never unlink the guard: every caller must lock the same inode.
        guard = open_regular(home / GUARD_NAME, os.O_CREAT | os.O_RDWR)
        fcntl.flock(guard, fcntl.LOCK_EX)
        path = home / LEASE_NAME
        existing = read_lease(path)
        if args.command == "status":
            return emit(0, command="status", state="held" if existing else "free",
                        **(existing or {}))
        if args.command == "release":
            if existing is None:
                return emit(0, command="release", state="absent")
            if existing["owner"] != args.owner:
                return emit(4, command="release", state="held", owner=existing["owner"])
            path.unlink()
            return emit(0, command="release", state="released")
        if existing:
            if existing["owner"] != args.owner:
                return emit(3, command="acquire", state="blocked", owner=existing["owner"])
            return emit(0, command="acquire", state="held", resumed=True, **existing)
        payload = {"owner": args.owner,
                   "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        fd = open_regular(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream)
            stream.flush()
            os.fsync(stream.fileno())
        # Partial writes remain untrusted, never automatically removed/reclaimed.
        return emit(0, command="acquire", state="held", resumed=False, **payload)
    except (OSError, ValueError, UnicodeError) as exc:
        return emit(5, command=args.command, state="error", error=str(exc))
    finally:
        if guard is not None:
            os.close(guard)


if __name__ == "__main__":
    raise SystemExit(main())
