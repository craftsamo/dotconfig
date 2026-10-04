"""discord-access engine: the only code that talks to Discord as the user.

Runs on its own hash-locked venv (``engines/discord-user``; ``curl_cffi`` for a Chrome TLS and
HTTP/2 fingerprint), never inside the Hermes gateway, so the user token only ever exists in this
short-lived process: it is read from the Keychain (``secret get DISCORD_USER_TOKEN -p hermes
--scope discord-user``, a scope no Hermes profile receives) at start and never written, printed
or logged.

    engine.py COMMAND  < JSON arguments  > {"ok": true, "data": ...} | {"ok": false, "kind", "error"}

Commands: whoami, guilds, channels, channel, messages, backfill, sync, send. Requests carry the
Discord web client's headers on a Chrome/macOS identity, are paced, and wait out short rate
limits only for reads. ``send`` makes exactly one POST with ``nonce`` + ``enforce_nonce`` and
never retries; its outcome is sent / not_sent / uncertain, recorded in the ``sends`` ledger
before and after dispatch. Contract: docs/discord-access.md.
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import random
import re
import subprocess
import sys
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
import store  # noqa: E402

API = "https://discord.com/api/v9"
WEB = "https://discord.com"
SECRET = Path.home() / ".config" / "bin" / "secret"
TOKEN_NAME, TOKEN_PROJECT, TOKEN_SCOPE = "DISCORD_USER_TOKEN", "hermes", "discord-user"
TOKEN_SET = "secret set DISCORD_USER_TOKEN -p hermes --scope discord-user"
IMPERSONATE = "chrome"

REQUEST_TIMEOUT = 20
SEND_TIMEOUT = 30
TOKEN_TIMEOUT = 30
PACE = (0.6, 1.6)            # seconds between requests in one process
MAX_WAIT = 30                # longest rate-limit wait a read accepts (once)
BUILD_TTL = 12 * 3600
BUILD_STALE_OK = 7 * 86400   # a cached build number this old still serves if the refresh fails
LAUNCH_TTL = 24 * 3600
GUILDS_TTL = 6 * 3600

# Sync run bounds.
MAX_REQUESTS = 60            # per run; the rest continues next run
PAGE = 100
PAGE_CAP = 5                 # pages per channel per run
SEED_COUNT = 50              # newest messages taken when a channel is first followed
SEED_PER_RUN = 15
SEED_DAYS = 30               # older-looking DMs are followed from now on; history via backfill
BACKFILL_PAGES = (2, 5)

# curl error codes raised before a request can have left the machine.
NOT_DISPATCHED_CURL = {5, 6, 7, 35, 58, 60, 77, 83}
PRE_DISPATCH_TIMEOUT = re.compile(r"resolving timed out|connection timed out|connect", re.IGNORECASE)

LOCALES = {"ja": "ja", "ko": "ko", "zh-TW": "zh-TW", "zh": "zh-CN", "en-GB": "en-GB", "fr": "fr",
           "de": "de", "es": "es-ES", "pt": "pt-BR", "it": "it", "ru": "ru"}


class EngineError(Exception):
    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind


class TransportError(Exception):
    """The request failed below HTTP. ``dispatched`` is False only when it cannot have left."""

    def __init__(self, message: str, dispatched: bool):
        super().__init__(message)
        self.dispatched = dispatched


# --- environment --------------------------------------------------------------------------------

def read_token() -> str:
    if not os.access(SECRET, os.X_OK):
        raise EngineError("setup", f"the secret CLI is missing at {SECRET}")
    try:
        proc = subprocess.run([str(SECRET), "get", TOKEN_NAME, "-p", TOKEN_PROJECT, "--scope", TOKEN_SCOPE],
                              stdin=subprocess.DEVNULL, capture_output=True, text=True,
                              timeout=TOKEN_TIMEOUT, cwd=store.state_dir())
    except subprocess.TimeoutExpired as exc:
        raise EngineError("setup", "reading the token from the Keychain timed out") from exc
    token = proc.stdout.strip()
    if proc.returncode != 0 or not token:
        raise EngineError("setup", f"no Discord token in the Keychain ({TOKEN_NAME}, project {TOKEN_PROJECT}, "
                                   f"scope {TOKEN_SCOPE}); the user stores it with `{TOKEN_SET}`")
    if any(ch.isspace() for ch in token) or token.lower().startswith("bot "):
        raise EngineError("setup", f"{TOKEN_NAME} does not look like a user token")
    return token


def system_timezone() -> str | None:
    try:
        target = os.readlink("/etc/localtime")
    except OSError:
        return None
    match = re.search(r"zoneinfo/(.+)$", target)
    return match.group(1) if match else None


def system_locale() -> str:
    try:
        out = subprocess.run(["/usr/bin/defaults", "read", "-g", "AppleLocale"], capture_output=True,
                             text=True, timeout=5).stdout.strip()
    except Exception:  # noqa: BLE001
        out = ""
    tag = out.split("@", 1)[0].replace("_", "-") or "en-US"
    return tag


def discord_locale(tag: str) -> str:
    if tag in LOCALES:
        return LOCALES[tag]
    lang = tag.split("-", 1)[0]
    return LOCALES.get(lang, "en-US")


# --- transport ----------------------------------------------------------------------------------

class Http:
    """curl_cffi with Chrome impersonation; one session (one TLS/HTTP2 connection) per process."""

    def __init__(self):
        from curl_cffi import requests
        from curl_cffi.requests import impersonate
        self.session = requests.Session(impersonate=IMPERSONATE)
        version = re.sub(r"\D", "", getattr(impersonate, "DEFAULT_CHROME", "chrome150")) or "150"
        self.browser_version = f"{version}.0.0.0"
        self.user_agent = (f"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                           f"(KHTML, like Gecko) Chrome/{version}.0.0.0 Safari/537.36")

    def request(self, method: str, url: str, *, headers=None, params=None, body=None, timeout=REQUEST_TIMEOUT):
        """(status, headers, parsed JSON or text). Raises TransportError below HTTP."""
        from curl_cffi import CurlError
        try:
            resp = self.session.request(method, url, headers=headers, params=params,
                                        data=None if body is None else json.dumps(body, separators=(",", ":")),
                                        timeout=timeout, allow_redirects=False)
        except CurlError as exc:
            code = getattr(exc, "code", None)
            text = str(exc)
            early = code in NOT_DISPATCHED_CURL or (code == 28 and bool(PRE_DISPATCH_TIMEOUT.search(text)))
            raise TransportError(f"network error (curl {code}): {mask_tokens(text)[:200]}", dispatched=not early) from exc
        try:
            payload = resp.json()
        except Exception:  # noqa: BLE001
            payload = resp.text
        return resp.status_code, {k.lower(): v for k, v in resp.headers.items()}, payload


# --- client -------------------------------------------------------------------------------------

def _launch_signature() -> str:
    bits = 0b00000000100000000001000000010000000010000001000000001000000000000010000010000001000000000100000000000001000000000000100000000000
    return str(uuid.UUID(int=uuid.uuid4().int & (~bits & ((1 << 128) - 1))))


class Client:
    def __init__(self, conn, http=None, token: str | None = None, clock=None, sleep=None):
        self.conn = conn
        self.http = http or Http()
        self.clock = clock or (lambda: time.time())
        self.sleep = sleep or (lambda seconds: time.sleep(seconds))
        self.token = token if token is not None else read_token()
        self.requests = 0
        self.budget = None          # a sync run sets MAX_REQUESTS; every request counts against it
        self._last = None
        self.me = store.get_meta(conn, "me") or {}
        self.build = self._build_number()
        self.launch = self._launch()

    # identity

    def _build_number(self) -> int:
        cached = store.get_meta(self.conn, "build") or {}
        now = self.clock()
        if cached.get("number") and now - cached.get("fetched", 0) < BUILD_TTL:
            return int(cached["number"])
        try:
            self._pace()
            self.requests += 1
            status, _, page = self.http.request("GET", f"{WEB}/login", headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": self._accept_language()})
            match = re.search(r'"BUILD_NUMBER"\s*:\s*"?(\d+)', page if isinstance(page, str) else "")
            if status == 200 and match:
                number = int(match.group(1))
                store.set_meta(self.conn, "build", {"number": number, "fetched": now})
                self.conn.commit()
                return number
        except TransportError:
            pass
        if cached.get("number") and now - cached.get("fetched", 0) < BUILD_STALE_OK:
            return int(cached["number"])
        raise EngineError("network", "could not read Discord's current client build number from discord.com/login")

    def _launch(self) -> dict:
        launch = store.get_meta(self.conn, "launch") or {}
        if not launch.get("id") or self.clock() - launch.get("started", 0) > LAUNCH_TTL:
            launch = {"id": str(uuid.uuid4()), "heartbeat": str(uuid.uuid4()), "signature": _launch_signature(),
                      "started": self.clock()}
            store.set_meta(self.conn, "launch", launch)
            self.conn.commit()
        return launch

    def _locale_tag(self) -> str:
        return self.me.get("locale") or discord_locale(system_locale())

    def _accept_language(self) -> str:
        tag = self._locale_tag()
        lang = tag.split("-", 1)[0]
        return f"{tag},{lang};q=0.9,en-US;q=0.8,en;q=0.7" if lang != "en" else "en-US,en;q=0.9"

    def super_properties(self) -> str:
        props = {
            "os": "Mac OS X", "browser": "Chrome", "device": "",
            "system_locale": system_locale(),
            "has_client_mods": False,
            "browser_user_agent": self.http.user_agent, "browser_version": self.http.browser_version,
            "os_version": "10.15.7", "referrer": "", "referring_domain": "", "referrer_current": "",
            "referring_domain_current": "", "release_channel": "stable", "client_build_number": self.build,
            "client_event_source": None, "client_launch_id": self.launch["id"],
            "launch_signature": self.launch["signature"],
            "client_heartbeat_session_id": self.launch["heartbeat"], "client_app_state": "focused"}
        return base64.b64encode(json.dumps(props, separators=(",", ":")).encode()).decode()

    def headers(self, *, referer: str = "/channels/@me", json_body: bool = False) -> dict:
        h = {"Accept": "*/*", "Accept-Language": self._accept_language(), "Authorization": self.token,
             "Origin": WEB, "Referer": f"{WEB}{referer}", "Sec-Fetch-Dest": "empty", "Sec-Fetch-Mode": "cors",
             "Sec-Fetch-Site": "same-origin", "User-Agent": self.http.user_agent,
             "X-Debug-Options": "bugReporterEnabled", "X-Discord-Locale": self._locale_tag(),
             "X-Super-Properties": self.super_properties()}
        tz = system_timezone()
        if tz:
            h["X-Discord-Timezone"] = tz
        if json_body:
            h["Content-Type"] = "application/json"
        return h

    # requests

    def _pace(self):
        if self._last is not None:
            wait = random.uniform(*PACE) - (self.clock() - self._last)
            if wait > 0:
                self.sleep(wait)
        self._last = self.clock()

    def _scrub(self, text: str) -> str:
        text = text.replace(self.token, "<token>") if self.token else text
        return mask_tokens(text)

    def _spend(self) -> None:
        """Count one request; past a run's budget, refuse before anything is sent."""
        if self.budget is not None and self.requests >= self.budget:
            raise EngineError("budget", "this run's request budget is spent; the rest continues next run")
        self.requests += 1

    def get(self, path: str, params=None, referer: str = "/channels/@me"):
        """A read: paced; a short rate limit is waited out once; errors become EngineError."""
        for attempt in (0, 1):
            self._spend()
            self._pace()
            try:
                status, headers, payload = self.http.request("GET", f"{API}{path}", params=params,
                                                             headers=self.headers(referer=referer))
            except TransportError as exc:
                raise EngineError("network", self._scrub(str(exc))) from exc
            if status == 429 and attempt == 0:
                wait = retry_after(headers, payload)
                if wait <= MAX_WAIT:
                    self.sleep(wait + random.uniform(0.2, 0.8))
                    continue
            if 200 <= status < 300:
                return payload
            raise self._http_error(status, headers, payload)
        raise EngineError("rate_limited", "Discord rate-limited the request twice")

    def _http_error(self, status, headers, payload) -> EngineError:
        message = payload.get("message") if isinstance(payload, dict) else None
        code = payload.get("code") if isinstance(payload, dict) else None
        detail = self._scrub(f"Discord {status}" + (f" (code {code}): {message}" if message else ""))
        if status == 401:
            store.set_meta(self.conn, "auth", {"state": "rejected", "at": self.clock()})
            self.conn.commit()
            return EngineError("auth", f"Discord rejected the token (401): the user stores a fresh one with `{TOKEN_SET}`")
        if isinstance(payload, dict) and payload.get("captcha_key"):
            return EngineError("captcha", "Discord asked for a captcha; the user does this one in the Discord app")
        if status == 429:
            return EngineError("rate_limited", f"rate-limited by Discord; retry after {retry_after(headers, payload):.0f}s")
        if status == 403:
            return EngineError("forbidden", detail)
        if status == 404:
            return EngineError("not_found", detail)
        return EngineError("http", detail)

    def mark_auth_ok(self):
        store.set_meta(self.conn, "auth", {"state": "ok", "at": self.clock()})


TOKEN_SHAPE = re.compile(r"[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]{20,}")


def mask_tokens(text: str) -> str:
    """Anything shaped like a Discord token, masked: the last line of defence for error text."""
    return TOKEN_SHAPE.sub("<token>", text)


def retry_after(headers: dict, payload) -> float:
    if isinstance(payload, dict) and isinstance(payload.get("retry_after"), (int, float)):
        return float(payload["retry_after"])
    try:
        return float(headers.get("retry-after", 5))
    except (TypeError, ValueError):
        return 5.0


# --- reads --------------------------------------------------------------------------------------

def _now() -> int:
    return int(time.time())


def whoami(client: Client) -> dict:
    me = client.get("/users/@me")
    client.me = {"id": str(me["id"]), "username": me.get("username"), "name": store.display_name(me),
                 "locale": me.get("locale")}
    store.set_meta(client.conn, "me", client.me)
    client.mark_auth_ok()
    client.conn.commit()
    return {k: v for k, v in client.me.items() if k != "locale"}


def guilds(client: Client) -> list[dict]:
    found = client.get("/users/@me/guilds", params={"with_counts": "false"})
    now = _now()
    for g in found:
        store.upsert_guild(client.conn, g["id"], g.get("name"), now)
    store.set_meta(client.conn, "guilds_fetched", now)
    client.conn.commit()
    return [{"id": str(g["id"]), "name": g.get("name")} for g in found]


def channels(client: Client, guild_id: str) -> list[dict]:
    found = client.get(f"/guilds/{guild_id}/channels", referer=f"/channels/{guild_id}")
    now = _now()
    for c in found:
        store.upsert_channel(client.conn, store.channel_row(c, guild_id), now)
    client.conn.commit()
    return found


def channel(client: Client, channel_id: str) -> dict:
    c = client.get(f"/channels/{channel_id}")
    store.upsert_channel(client.conn, store.channel_row(c), _now())
    client.conn.commit()
    return store.channel_row(c)


def _referer(conn, channel_id) -> str:
    row = conn.execute("SELECT guild_id FROM channels WHERE id = ?", (int(channel_id),)).fetchone()
    return f"/channels/{row['guild_id'] or '@me'}/{channel_id}" if row else f"/channels/@me/{channel_id}"


def _store_batch(client: Client, channel_id, batch: list) -> list[dict]:
    me_id = (client.me or {}).get("id")
    row = client.conn.execute("SELECT guild_id FROM channels WHERE id = ?", (int(channel_id),)).fetchone()
    guild_id = row["guild_id"] if row else None
    rows = [store.message_row(m, me_id, guild_id) for m in batch if isinstance(m, dict) and m.get("id")]
    store.upsert_messages(client.conn, rows)
    return rows


def messages(client: Client, channel_id: str, *, before=None, after=None, around=None, limit=50) -> list[dict]:
    """A live window, stored in the mirror too (search and approval cards read it there). It
    never moves a cursor: the mirror's contiguous history is only what sync and backfill made."""
    params = {"limit": str(max(1, min(int(limit), PAGE)))}
    for key, value in (("before", before), ("after", after), ("around", around)):
        if value:
            params[key] = str(value)
    batch = client.get(f"/channels/{channel_id}/messages", params=params, referer=_referer(client.conn, channel_id))
    rows = _store_batch(client, channel_id, batch)
    # Readable again: a channel once marked forbidden or gone rejoins the sync.
    client.conn.execute("UPDATE channels SET state = NULL WHERE id = ? AND state IS NOT NULL", (int(channel_id),))
    client.conn.commit()
    return sorted(rows, key=lambda r: r["id"])


def backfill(client: Client, channel_id: str, pages: int) -> dict:
    """Older history of one followed channel, paging back from the cursor's frontier (the oldest
    message of the contiguous history), so a stray older live window never hides a gap. Each page
    is committed with the frontier before the next request."""
    cid = int(channel_id)
    conn = client.conn
    cursor = conn.execute("SELECT * FROM cursors WHERE channel_id = ?", (cid,)).fetchone()
    if cursor is None:
        raise EngineError("usage", "that channel is not synced")
    before = cursor["oldest"] or (cursor["newest"] + 1 if cursor["newest"] else None)
    added, complete = 0, bool(cursor["complete"])
    for _ in range(0 if complete else pages):
        params = {"limit": str(PAGE)}
        if before:
            params["before"] = str(before)
        batch = client.get(f"/channels/{channel_id}/messages", params=params, referer=_referer(conn, channel_id))
        rows = _store_batch(client, channel_id, batch)
        added += len(rows)
        if rows:
            before = min(r["id"] for r in rows)
        complete = len(batch) < PAGE
        conn.execute("UPDATE cursors SET oldest = ?, complete = ? WHERE channel_id = ?", (before, int(complete), cid))
        conn.commit()
        if complete:
            break
    return {"added": added, "complete": complete,
            "oldest": store.snowflake_time(before).isoformat() if before else None}


# --- sync ---------------------------------------------------------------------------------------

UNREADABLE = ("forbidden", "gone")


def _pick_guild_channels(conn, gid: str, entry: dict) -> tuple[list, list]:
    rows = {r["id"]: r for r in conn.execute("SELECT * FROM channels WHERE guild_id = ?", (int(gid),))}
    missing = []
    if entry["channels"]:
        picked = []
        for cid in entry["channels"]:
            row = rows.get(int(cid))
            if row is None:
                missing.append(cid)
            elif row["state"] not in UNREADABLE:
                picked.append(row)
        return picked, missing
    excluded = {int(c) for c in entry["exclude"]}
    text = [r for r in rows.values() if r["type"] in store.TEXT_TYPES and r["id"] not in excluded
            and r["state"] not in UNREADABLE and r["last_message_id"]]
    text.sort(key=lambda r: r["last_message_id"], reverse=True)
    return text[:store.WHOLE_GUILD_CHANNELS], missing


def _set_cursor(conn, cid: int, newest, oldest=None, complete=None, current: bool = True) -> None:
    """``synced_at`` says the mirror held everything up to ``newest`` at that time; it is cleared
    while a channel lags (the plugin reads such a channel live)."""
    conn.execute(
        "INSERT INTO cursors (channel_id, newest, oldest, complete, synced_at) VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(channel_id) DO UPDATE SET newest = excluded.newest, "
        "oldest = COALESCE(cursors.oldest, excluded.oldest), "
        "complete = MAX(cursors.complete, excluded.complete), synced_at = excluded.synced_at",
        (cid, newest, oldest, int(bool(complete)), _now() if current else None))


def _mark(conn, cid: int, state: str) -> None:
    conn.execute("UPDATE channels SET state = ? WHERE id = ?", (state, cid))


def _follow(conn, client: Client, summary: dict, cid: int, last: int, cursor, seeded: int) -> int:
    """Bring one channel's mirror up to its last message id; returns the seeds used."""
    if cursor is None or not cursor["newest"]:
        if store.snowflake_ms(last) < int(time.time() * 1000) - SEED_DAYS * 86400000:
            # Quiet for a month: followed from now on, history only on request (backfill).
            _set_cursor(conn, cid, last, oldest=last + 1)
            conn.commit()
            return 0
        if seeded >= SEED_PER_RUN:
            summary["deferred"] += 1
            return 0
        batch = client.get(f"/channels/{cid}/messages", params={"limit": str(SEED_COUNT)}, referer=_referer(conn, cid))
        rows = _store_batch(client, cid, batch)
        summary["fetched"] += len(rows)
        _set_cursor(conn, cid, max([r["id"] for r in rows] + [last]),
                    min(r["id"] for r in rows) if rows else last + 1, complete=len(batch) < SEED_COUNT)
        conn.commit()
        summary["channels_updated"] += 1
        return 1
    after = cursor["newest"]
    for _ in range(PAGE_CAP):
        batch = client.get(f"/channels/{cid}/messages", params={"after": str(after), "limit": str(PAGE)},
                           referer=_referer(conn, cid))
        rows = _store_batch(client, cid, batch)
        summary["fetched"] += len(rows)
        if rows:
            after = max(r["id"] for r in rows)
        if len(batch) < PAGE:
            # Caught up: the channel's last message id is the cursor even when that message is gone
            # (deleted), so it is not fetched again every run.
            _set_cursor(conn, cid, max(after, last))
            conn.commit()
            summary["channels_updated"] += 1
            return 0
        _set_cursor(conn, cid, after, current=False)  # each page committed with its progress
        conn.commit()
    summary["deferred"] += 1
    return 0


def sync(client: Client) -> dict:
    """One sync run: the DMs and the sync list's channels, only those whose last message moved."""
    conn = client.conn
    client.budget = MAX_REQUESTS
    summary = {"started": datetime.now(timezone.utc).isoformat(timespec="seconds"), "fetched": 0,
               "channels_updated": 0, "errors": [], "deferred": 0}
    whoami(client)
    if _now() - (store.get_meta(conn, "guilds_fetched") or 0) > GUILDS_TTL:
        guilds(client)
    now = _now()
    plan = []
    for c in client.get("/users/@me/channels"):
        if c.get("type") in store.PRIVATE_TYPES:
            row = store.channel_row(c)
            store.upsert_channel(conn, row, now)
            state = conn.execute("SELECT state FROM channels WHERE id = ?", (row["id"],)).fetchone()["state"]
            if state not in UNREADABLE:
                plan.append(row)
    conn.commit()
    for gid, entry in store.load_sync()["guilds"].items():
        try:
            channels(client, gid)
        except EngineError as exc:
            if exc.kind in ("auth", "captcha"):
                raise
            if exc.kind == "budget":
                summary["deferred"] += 1
                break
            summary["errors"].append(f"server {entry.get('name') or gid}: {exc}")
            continue
        picked, missing = _pick_guild_channels(conn, gid, entry)
        plan += [dict(r) for r in picked]
        if missing:
            summary["errors"].append(f"server {entry.get('name') or gid}: channel(s) not found: {', '.join(missing)}")
    plan.sort(key=lambda r: r.get("last_message_id") or 0, reverse=True)
    changed = []
    for row in plan:
        cid, last = int(row["id"]), row.get("last_message_id")
        if not last:
            continue
        cursor = conn.execute("SELECT * FROM cursors WHERE channel_id = ?", (cid,)).fetchone()
        if cursor and cursor["newest"] and last <= cursor["newest"]:
            conn.execute("UPDATE cursors SET synced_at = ? WHERE channel_id = ?", (_now(), cid))  # still current
        else:
            if cursor:
                # Known to be behind: not current until a fetch catches up (the plugin reads it live).
                conn.execute("UPDATE cursors SET synced_at = NULL WHERE channel_id = ?", (cid,))
            changed.append((cid, last, cursor))
    conn.commit()  # nothing uncommitted while a request is in flight
    seeded = 0
    for cid, last, cursor in changed:
        try:
            seeded += _follow(conn, client, summary, cid, last, cursor, seeded)
        except EngineError as exc:
            conn.commit()
            if exc.kind in ("auth", "captcha"):
                raise
            if exc.kind == "budget":
                summary["deferred"] += 1
                continue
            if exc.kind == "forbidden":
                _mark(conn, cid, "forbidden")
            elif exc.kind == "not_found":
                _mark(conn, cid, "gone")
            conn.commit()
            if exc.kind in ("rate_limited", "network"):
                summary["errors"].append(f"channel {cid}: {exc}; stopped this run")
                break
            summary["errors"].append(f"channel {cid}: {exc}")
    conn.commit()
    summary["requests"] = client.requests
    summary["ok"] = True
    return summary


# --- send ---------------------------------------------------------------------------------------

def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def new_nonce() -> str:
    return str(store.snowflake_at(datetime.now(timezone.utc)) | random.getrandbits(22))


def ledger_status(conn, nonce: str) -> dict | None:
    row = conn.execute("SELECT * FROM sends WHERE nonce = ?", (nonce,)).fetchone()
    return dict(row) if row else None


def _ledger(conn, nonce: str, status: str, message_id=None, detail=None) -> None:
    conn.execute("UPDATE sends SET status = ?, message_id = COALESCE(?, message_id), detail = ? WHERE nonce = ?",
                 (status, message_id, detail, nonce))
    conn.commit()


def send(conn, plan: dict, client_factory) -> dict:
    """Exactly one POST. Outcome: sent (with the message id), not_sent (Discord or the network
    refused before anything was created), or uncertain (it may exist; a read-back looks once)."""
    nonce, cid, text = plan["nonce"], int(plan["channel"]), plan["text"]
    reply_to = int(plan["reply_to"]) if plan.get("reply_to") else None
    if ledger_status(conn, nonce):
        return {"outcome": "not_sent", "detail": "this send was already attempted (same nonce); nothing was sent again"}
    conn.execute("INSERT INTO sends (nonce, channel_id, text_hash, reply_to, created, status) VALUES (?, ?, ?, ?, ?, ?)",
                 (nonce, cid, text_hash(text), reply_to, _now(), "pending"))
    conn.commit()
    try:
        client = client_factory()
    except EngineError as exc:
        _ledger(conn, nonce, "not_sent", detail=str(exc))
        return {"outcome": "not_sent", "detail": str(exc)}
    row = conn.execute("SELECT guild_id FROM channels WHERE id = ?", (cid,)).fetchone()
    guild_id = row["guild_id"] if row else None
    body = {"mobile_network_type": "unknown", "content": text, "nonce": nonce, "tts": False,
            "flags": 0, "enforce_nonce": True}
    if reply_to:
        ref = {"channel_id": str(cid), "message_id": str(reply_to)}
        if guild_id:
            ref["guild_id"] = str(guild_id)
        body["message_reference"] = ref
        body["allowed_mentions"] = {"parse": ["users", "roles", "everyone"], "replied_user": False}
    _ledger(conn, nonce, "dispatching")
    client._pace()
    client.requests += 1
    plan = {**plan, "dispatched_at": client.clock()}
    try:
        status, headers, payload = client.http.request(
            "POST", f"{API}/channels/{cid}/messages", body=body, timeout=SEND_TIMEOUT,
            headers=client.headers(referer=_referer(conn, cid), json_body=True))
    except TransportError as exc:
        detail = client._scrub(str(exc))
        if not exc.dispatched:
            _ledger(conn, nonce, "not_sent", detail=detail)
            return {"outcome": "not_sent", "detail": detail}
        return _read_back(conn, client, plan, detail)
    if 200 <= status < 300 and isinstance(payload, dict) and payload.get("id"):
        _store_batch(client, cid, [payload])
        _ledger(conn, nonce, "sent", message_id=int(payload["id"]))
        return {"outcome": "sent", "message_id": str(payload["id"]), "channel": str(cid)}
    if status >= 500 or 200 <= status < 300:
        return _read_back(conn, client, plan, client._scrub(f"Discord answered {status} without a message"))
    error = client._http_error(status, headers, payload)
    _ledger(conn, nonce, "not_sent", detail=str(error))
    return {"outcome": "not_sent", "detail": str(error), "kind": error.kind}


CLOCK_SKEW = 2  # seconds of local clock error a read-back tolerates


def _looks_like(m: dict, plan: dict, me_id, floor: int) -> bool:
    """The user's message with the exact text and reply target, created after the POST began.
    Discord's history carries no nonce, so this can only ever be a hint, never proof: the user
    may have typed the same words themselves."""
    if str((m.get("author") or {}).get("id")) != str(me_id) or m.get("content") != plan["text"]:
        return False
    if int(m["id"]) < floor:
        return False
    ref = (m.get("message_reference") or {}).get("message_id")
    if plan.get("reply_to"):
        return m.get("type") == 19 and str(ref) == str(plan["reply_to"])
    return m.get("type") == 0 and not ref


def _read_back(conn, client: Client, plan: dict, detail: str) -> dict:
    """An ambiguous send stays ``uncertain``. One look at the channel's newest messages adds what
    was seen, so the Assistant can ask the user with facts; nothing is concluded or resent."""
    nonce, cid = plan["nonce"], int(plan["channel"])
    floor = store.snowflake_at(datetime.fromtimestamp(plan["dispatched_at"] - CLOCK_SKEW, tz=timezone.utc))
    try:
        found = client.get(f"/channels/{cid}/messages", params={"limit": "10"}, referer=_referer(conn, cid))
    except EngineError as exc:
        seen = f"read-back failed: {exc}"
    else:
        me_id = (client.me or {}).get("id") or (store.get_meta(conn, "me") or {}).get("id")
        hits = [m for m in found if isinstance(m, dict) and m.get("id") and _looks_like(m, plan, me_id, floor)]
        if hits:
            _store_batch(client, cid, hits)
            seen = ("a message of yours with exactly this text appeared after the send began (id "
                    + ", ".join(str(m["id"]) for m in hits) + "): probably this send, but not proven")
        else:
            seen = "no message of yours with this text in the channel's newest 10 messages yet"
    _ledger(conn, nonce, "uncertain", detail=f"{detail}; {seen}")
    return {"outcome": "uncertain", "detail": f"{detail}; {seen}"}


# --- entry --------------------------------------------------------------------------------------

def _arg(args: dict, key: str, *, snowflake: bool = True, required: bool = True):
    value = args.get(key)
    if value in (None, ""):
        if required:
            raise EngineError("usage", f"{key} is required")
        return None
    if snowflake and not store.is_snowflake(str(value)):
        raise EngineError("usage", f"{key} must be a Discord id")
    return str(value)


def run(command: str, args: dict, *, http=None, token=None) -> dict:
    conn = store.connect(write=True)
    try:
        def make_client():
            return Client(conn, http=http, token=token)

        if command == "send":
            plan = {"nonce": _arg(args, "nonce", snowflake=False), "channel": _arg(args, "channel"),
                    "text": args.get("text"), "reply_to": _arg(args, "reply_to", required=False)}
            if not isinstance(plan["text"], str) or not plan["text"].strip():
                raise EngineError("usage", "text is required")
            return send(conn, plan, make_client)
        if command == "sync":
            lock = open(store.state_dir() / "sync.lock", "a")
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise EngineError("busy", "another sync run is in progress") from exc
            try:
                client = make_client()
                try:
                    summary = sync(client)
                except EngineError as exc:
                    summary = {"started": datetime.now(timezone.utc).isoformat(timespec="seconds"), "ok": False,
                               "kind": exc.kind, "error": str(exc), "requests": client.requests}
                    store.set_meta(conn, "last_sync", summary)
                    conn.commit()
                    raise
                store.set_meta(conn, "last_sync", summary)
                conn.commit()
                return summary
            finally:
                lock.close()
        client = make_client()
        if command == "whoami":
            return whoami(client)
        if command == "guilds":
            return {"guilds": guilds(client)}
        if command == "channels":
            gid = _arg(args, "guild")
            found = channels(client, gid)
            return {"channels": [store.channel_row(c, gid) for c in found]}
        if command == "channel":
            return channel(client, _arg(args, "channel"))
        if command == "messages":
            if not client.me.get("id"):
                whoami(client)
            return {"messages": messages(client, _arg(args, "channel"), before=_arg(args, "before", required=False),
                                         after=_arg(args, "after", required=False),
                                         around=_arg(args, "around", required=False),
                                         limit=int(args.get("limit") or 50))}
        if command == "backfill":
            pages = max(1, min(int(args.get("pages") or BACKFILL_PAGES[0]), BACKFILL_PAGES[1]))
            if not client.me.get("id"):
                whoami(client)
            return backfill(client, _arg(args, "channel"), pages)
        raise EngineError("usage", f"unknown command {command!r}")
    finally:
        conn.close()


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(json.dumps({"ok": False, "kind": "usage", "error": "usage: engine.py COMMAND < args.json"}))
        return 2
    try:
        raw = sys.stdin.read()
        args = json.loads(raw) if raw.strip() else {}
        if not isinstance(args, dict):
            raise EngineError("usage", "arguments must be a JSON object")
        data = run(argv[1], args)
        print(json.dumps({"ok": True, "data": data}, ensure_ascii=False))
        return 0
    except EngineError as exc:
        print(json.dumps({"ok": False, "kind": exc.kind, "error": mask_tokens(str(exc))}, ensure_ascii=False))
        return 0
    except Exception as exc:  # noqa: BLE001 - never a traceback (it could carry request state)
        print(json.dumps({"ok": False, "kind": "internal",
                          "error": f"{type(exc).__name__}: {mask_tokens(str(exc))[:300]}"}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
