"""x-access bridge: one twscrape read, run by the engine venv's interpreter (not Hermes').

The engine (``xa.py``) writes one JSON request to stdin and reads one JSON reply from
stdout. Only reads exist here; there is no posting, liking, following or DM code path.

The sub-account's session cookies are read from the Keychain at start (``secret get
X_READER_COOKIES -p hermes --scope x-reader``, a scope no Hermes profile receives) and live only
in this short-lived process: twscrape's account pool is an in-memory SQLite database, so nothing
of the session is written to disk, printed or logged (both cookie values are masked in every
string that leaves). The reply reports what became of the session (refused, rate-limited) so the
engine can remember it between calls. Contract: docs/x-access.md.

    {"op": "check" | "user" | "posts" | "search" | "details" | "thread", "deadline": seconds,
     "refused": <fingerprint the engine saw refused, or null>, ...op arguments}
"""

from __future__ import annotations

import asyncio
from contextlib import aclosing
from datetime import datetime, timezone
import functools
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

SECRET = Path.home() / ".config" / "bin" / "secret"
COOKIES_NAME, COOKIES_PROJECT, COOKIES_SCOPE = "X_READER_COOKIES", "hermes", "x-reader"
COOKIES_SET = f"secret set {COOKIES_NAME} -p {COOKIES_PROJECT} --scope {COOKIES_SCOPE}"
SECRET_TIMEOUT = 20
POOL = "file:x-access-pool?mode=memory&cache=shared"
ACCOUNT = "reader"

WARNINGS: list[str] = []
SECRETS: list[str] = []


class Setup(Exception):
    pass


def mask(text) -> str:
    text = str(text)
    for value in SECRETS:
        if value:
            text = text.replace(value, "…")
    return text


def _capture_logs():
    import twscrape  # noqa: F401  (its import installs a stderr sink; replace it after)
    from loguru import logger
    logger.remove()
    logger.add(lambda message: WARNINGS.append(mask(str(message).strip())[:300]), level="WARNING",
               format="{message}")


def _plain(value):
    return json.loads(json.dumps(value, default=str))


def read_cookies() -> tuple[str, str]:
    """(cookie string, fingerprint) from the Keychain; raises Setup with the fix."""
    from twscrape.utils import parse_cookies
    if not SECRET.exists():
        raise Setup(f"the secret CLI is missing at {SECRET}")
    try:
        proc = subprocess.run([str(SECRET), "get", COOKIES_NAME, "-p", COOKIES_PROJECT, "--scope", COOKIES_SCOPE],
                              stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=SECRET_TIMEOUT)
    except subprocess.TimeoutExpired as exc:
        raise Setup("reading the sub-account's cookies from the Keychain timed out") from exc
    value = proc.stdout.strip()
    if proc.returncode != 0 or not value:
        raise Setup(f"no sub-account cookies in the Keychain ({COOKIES_NAME}, project {COOKIES_PROJECT}, "
                    f"scope {COOKIES_SCOPE}); the user stores them with `{COOKIES_SET}`")
    try:
        parsed = parse_cookies(value)
    except Exception as exc:
        raise Setup(f"{COOKIES_NAME} is not a cookie string; store it as 'auth_token=…; ct0=…'") from exc
    if not parsed.get("auth_token") or not parsed.get("ct0"):
        raise Setup(f"{COOKIES_NAME} must hold both auth_token and ct0 ('auth_token=…; ct0=…')")
    SECRETS.extend([value, str(parsed["auth_token"]), str(parsed["ct0"])])
    fingerprint = hashlib.sha256(str(parsed["auth_token"]).encode()).hexdigest()[:12]
    return value, fingerprint


def _memory_pool():
    """twscrape keeps its account pool in SQLite; hold it in memory so the session never touches disk.

    A shared-cache in-memory database lives while one connection is open (the anchor), and
    twscrape's own connections reach it through URI filenames."""
    import twscrape.db as tdb
    anchor = sqlite3.connect(POOL, uri=True)
    tdb.aiosqlite.connect = functools.partial(tdb.aiosqlite.connect, uri=True)
    return anchor


async def _collect(gen, limit: int) -> list[dict]:
    items = []
    async with aclosing(gen) as stream:
        async for item in stream:
            items.append(item.dict())
            if len(items) >= limit:
                break
    return items


async def _session(api) -> dict:
    """What X made of the session: refused (twscrape marked it inactive) and future endpoint locks."""
    accounts = await api.pool.get_all()
    if not accounts:
        return {"active": False, "error": "no account"}
    acc = accounts[0]
    now = datetime.now(timezone.utc)
    locks = {queue: until.isoformat() for queue, until in (acc.locks or {}).items() if until > now}
    error = None if acc.error_msg in (None, "None", "") else mask(acc.error_msg)[:200]
    return {"active": bool(acc.active), "error": error, "locks": locks}


async def _run(api, req: dict):
    op = req["op"]
    if op == "user":
        user = await api.user_by_login(req["handle"])
        return user.dict() if user else None
    if op == "posts":
        uid = int(req["user_id"])
        gen = api.user_tweets_and_replies(uid, limit=req["limit"]) if req.get("replies") else \
            api.user_tweets(uid, limit=req["limit"])
        return await _collect(gen, req["limit"])
    if op == "search":
        kv = {"product": "Top"} if req.get("top") else None
        return await _collect(api.search(req["query"], limit=req["limit"], kv=kv), req["limit"])
    if op == "details":
        post = await api.tweet_details(int(req["id"]))
        return post.dict() if post else None
    if op == "thread":
        return await _collect(api.tweet_thread(int(req["root"]), limit=req["limit"]), req["limit"])
    raise ValueError(f"unknown op {op!r}")


async def main(req: dict) -> dict:
    try:
        cookies, fingerprint = read_cookies()
    except Setup as exc:
        return {"ok": False, "kind": "setup", "error": str(exc), "contacted": False}
    if req["op"] == "check":
        return {"ok": True, "data": None, "fingerprint": fingerprint, "contacted": False}
    if req.get("refused") and req["refused"] == fingerprint:
        return {"ok": False, "kind": "refused", "fingerprint": fingerprint, "contacted": False}
    from twscrape import API, NoAccountError
    anchor = _memory_pool()
    try:
        api = API(POOL, raise_when_no_account=True, wait_timeout=10, wait_interval=2)
        await api.pool.add_account_cookies(ACCOUNT, cookies)
        reply = {"fingerprint": fingerprint, "contacted": True}
        try:
            data = await asyncio.wait_for(_run(api, req), timeout=float(req.get("deadline", 60)))
            reply.update(ok=True, data=data)
        except NoAccountError:
            reply.update(ok=False, kind="no_account")
        except asyncio.TimeoutError:
            reply.update(ok=False, kind="timeout", error=f"X did not answer within {req.get('deadline')}s")
        reply["session"] = await _session(api)
        return reply
    finally:
        anchor.close()


if __name__ == "__main__":
    try:
        _capture_logs()
        request = json.loads(sys.stdin.read())
        reply = asyncio.run(main(request))
    except Exception as exc:  # reported to the engine, never a traceback on stdout
        reply = {"ok": False, "kind": "error", "error": mask(f"{type(exc).__name__}: {exc}")[:500], "contacted": True}
    reply["warnings"] = WARNINGS[-10:]
    sys.stdout.write(mask(json.dumps(_plain(reply), ensure_ascii=False)))
