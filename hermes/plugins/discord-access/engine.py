"""discord-access engine: the only code that talks to Discord as the user.

Runs on its own hash-locked venv (``engines/discord-user``; ``curl_cffi`` for a Chrome TLS and
HTTP/2 fingerprint), never inside the Hermes gateway, so the user token only ever exists in this
short-lived process: it is read from the Keychain (``secret get DISCORD_USER_TOKEN -p hermes
--scope discord-user``, a scope no Hermes profile receives) at start and never written, printed
or logged.

    engine.py COMMAND  < JSON arguments  > {"ok": true, "data": ...} | {"ok": false, "kind", "error"}

Commands: whoami, guilds, channels, channel, messages, backfill, sync, send, media, threads, pins,
mentions, friends, search, roles, member, role_members, members. Requests carry the Discord web
client's headers on a Chrome/macOS identity, are paced, and wait out short
rate limits only for reads. ``send`` makes exactly one message POST with ``nonce`` +
``enforce_nonce`` and never retries it; attachments are uploaded first (Discord's cloud upload, as
the web client does), which creates no message. Its outcome is sent / not_sent / uncertain,
recorded in the ``sends`` ledger before and after dispatch.
Contract: docs/discord-access.md.
"""

from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
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
import urllib.parse
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
# Edits and deletions: each run reads the newest page of a few recently active channels again.
RECHECK_PER_RUN = 2
RECHECK_DAYS = 7
RECHECK_INTERVAL = 30 * 60   # a channel is read again at most this often
RECHECK_COUNT = 50

# Discord JSON error codes the engine tells apart.
INDEXING = 110000            # search: the index is not ready (HTTP 202)

# Attachments: Discord's cloud upload. The upload URL is a signed Google Cloud Storage URL; the
# token never goes there, and files are only ever read from the plugin's approved outbox.
UPLOAD_TIMEOUT = 120
UPLOAD_BUDGET = 600          # all uploads of one send; the plugin waits 840 s for the whole send
# Media: one message's attachments, proxied link-preview media and stickers, fetched from Discord's
# media hosts without the token into a private incoming folder that the plugin then sorts.
MEDIA_BUDGET = 540           # all downloads of one call; the plugin waits 660 s for the whole call
MEDIA_TIMEOUT = 180          # one download
MEDIA_LIMIT_MAX = 500 * 1024 * 1024
INCOMING_TOKEN = re.compile(r"^[0-9a-f]{32}$")
UPLOAD_HOST = re.compile(r"^[a-z0-9-]+\.storage\.googleapis\.com$")

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

    def request(self, method: str, url: str, *, headers=None, params=None, body=None, data=None,
                timeout=REQUEST_TIMEOUT):
        """(status, headers, parsed JSON or text). ``body`` is sent as JSON, ``data`` as raw bytes.
        Raises TransportError below HTTP."""
        from curl_cffi import CurlError
        if body is not None:
            data = json.dumps(body, separators=(",", ":"))
        try:
            resp = self.session.request(method, url, headers=headers, params=params, data=data,
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


    def download(self, url: str, dest: Path, *, headers: dict, limit: int, timeout: float) -> dict:
        """Stream one file into ``dest`` (created exclusively), stopping past ``limit`` bytes.
        ``{"status", "type", "size", "too_large"}``; raises TransportError below HTTP."""
        from curl_cffi import CurlError
        try:
            resp = self.session.get(url, headers=headers, timeout=timeout, stream=True, allow_redirects=False)
        except CurlError as exc:
            raise TransportError(f"network error (curl {getattr(exc, 'code', None)})", dispatched=True) from exc
        try:
            kind = (resp.headers.get("content-type") or "").split(";", 1)[0].strip()
            out = {"status": resp.status_code, "type": kind, "size": 0, "too_large": False}
            if not 200 <= resp.status_code < 300:
                return out
            declared = resp.headers.get("content-length")
            if declared and declared.isdigit() and int(declared) > limit:
                return {**out, "size": int(declared), "too_large": True}
            with open(dest, "xb") as handle:
                os.fchmod(handle.fileno(), 0o600)
                for chunk in resp.iter_content():
                    out["size"] += len(chunk)
                    if out["size"] > limit:
                        out["too_large"] = True
                        break
                    handle.write(chunk)
            if out["too_large"]:
                dest.unlink(missing_ok=True)
            return out
        except CurlError as exc:
            dest.unlink(missing_ok=True)
            raise TransportError(f"network error (curl {getattr(exc, 'code', None)})", dispatched=True) from exc
        finally:
            resp.close()


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
        return self.read("GET", path, params=params, referer=referer)

    def read(self, method: str, path: str, *, params=None, body=None, referer: str = "/channels/@me"):
        """A read (searches POST a body): a short rate limit or a search index still being built
        (HTTP 202) is waited out once; errors become EngineError."""
        for attempt in (0, 1):
            self._spend()
            self._pace()
            try:
                status, headers, payload = self.http.request(
                    method, f"{API}{path}", params=params, body=body,
                    headers=self.headers(referer=referer, json_body=body is not None))
            except TransportError as exc:
                raise EngineError("network", self._scrub(str(exc))) from exc
            if status == 429 and attempt == 0:
                wait = retry_after(headers, payload)
                if wait <= MAX_WAIT:
                    self.sleep(wait + random.uniform(0.2, 0.8))
                    continue
            if status == 202 and isinstance(payload, dict) and payload.get("code") == INDEXING:
                wait = retry_after(headers, payload) or 5.0
                if attempt == 0 and wait <= MAX_WAIT:
                    self.sleep(wait + random.uniform(0.2, 0.8))
                    continue
                raise EngineError("indexing", "Discord is still indexing this search; try again in a minute")
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
        store.upsert_guild(client.conn, g["id"], g.get("name"), now, owner=g.get("owner"))
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


def _store_batch(client: Client, channel_id, batch: list, reactions: bool = True) -> list[dict]:
    """Store messages of one channel. ``reactions=False`` for search, pin and mention results,
    which leave reactions out (stored ones are kept)."""
    me_id = (client.me or {}).get("id")
    row = client.conn.execute("SELECT guild_id FROM channels WHERE id = ?", (int(channel_id),)).fetchone()
    guild_id = row["guild_id"] if row else None
    rows = [store.message_row(m, me_id, guild_id, reactions=reactions)
            for m in batch if isinstance(m, dict) and m.get("id")]
    store.upsert_messages(client.conn, rows)
    return rows


def _store_found(client: Client, found: list) -> list[dict]:
    """Messages from several channels (search, mentions), none authoritative for reactions."""
    rows = []
    for m in found:
        if isinstance(m, dict) and m.get("id") and m.get("channel_id"):
            rows += _store_batch(client, m["channel_id"], [m], reactions=False)
    return rows


def _fetch(client: Client, channel_id, params: dict) -> tuple[list, list[dict]]:
    """One page of a channel's history (raw messages, mirror rows). A page is contiguous, so a
    mirrored message inside the range it covers that it did not return was deleted on Discord:
    the mirror drops it. The range is the page itself; a short page also vouches for its open ends:
    back to the channel's start unless ``after`` bounded it (anything older than its oldest message
    existed when it was read), and past its newest message unless ``before`` bounded it — there
    only for messages already mirrored before the request began, since one stored meanwhile (by a
    sync or a send in another process) may be newer than what Discord answered."""
    cid = int(channel_id)
    open_top = "before" not in params and "around" not in params
    recent = store.snowflake_at(datetime.now(timezone.utc) - timedelta(days=RECHECK_DAYS))
    known = {r[0] for r in client.conn.execute("SELECT id FROM messages WHERE channel_id = ? AND id >= ?",
                                               (cid, recent))} if open_top else set()
    batch = client.get(f"/channels/{cid}/messages", params=params, referer=_referer(client.conn, cid))
    batch = [m for m in batch if isinstance(m, dict) and m.get("id")]
    rows = _store_batch(client, cid, batch)
    if rows:
        ids = [r["id"] for r in rows]
        lo, hi = min(ids), max(ids)
        short = len(batch) < int(params.get("limit") or 50)
        if short and "around" not in params and "after" not in params:
            lo = 0
        store.drop_missing(client.conn, cid, ids, lo, hi)
        if short and open_top:
            gone = [i for i in known if i > hi and i not in set(ids)]
            for i in gone:
                store.delete_message(client.conn, i)
    return batch, rows


def fetch_message(client: Client, channel_id, message_id) -> dict | None:
    """One message as Discord has it now, or None when it is gone (the mirror follows)."""
    batch, _ = _fetch(client, channel_id, {"around": str(message_id), "limit": "5"})
    client.conn.commit()
    return next((m for m in batch if str(m.get("id")) == str(message_id)), None)


def messages(client: Client, channel_id: str, *, before=None, after=None, around=None, limit=50) -> list[dict]:
    """A live window, stored in the mirror too (search and approval cards read it there), with
    edits and deletions inside it applied. It never moves a cursor: the mirror's contiguous
    history is only what sync and backfill made."""
    params = {"limit": str(max(1, min(int(limit), PAGE)))}
    for key, value in (("before", before), ("after", after), ("around", around)):
        if value:
            params[key] = str(value)
    _, rows = _fetch(client, channel_id, params)
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
        batch, rows = _fetch(client, channel_id, params)
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
        batch, rows = _fetch(client, cid, {"limit": str(SEED_COUNT)})
        summary["fetched"] += len(rows)
        _set_cursor(conn, cid, max([r["id"] for r in rows] + [last]),
                    min(r["id"] for r in rows) if rows else last + 1, complete=len(batch) < SEED_COUNT)
        conn.execute("UPDATE cursors SET rechecked_at = ? WHERE channel_id = ?", (_now(), cid))  # a fresh newest page
        conn.commit()
        summary["channels_updated"] += 1
        return 1
    after = cursor["newest"]
    for _ in range(PAGE_CAP):
        batch, rows = _fetch(client, cid, {"after": str(after), "limit": str(PAGE)})
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
    seeded, stopped = 0, False
    for cid, last, cursor in changed:
        try:
            seeded += _follow(conn, client, summary, cid, last, cursor, seeded)
        except EngineError as exc:
            if _channel_failed(conn, summary, cid, exc):
                stopped = True
                break
    if not stopped:
        _recheck(conn, client, summary, plan)
    conn.commit()
    summary["requests"] = client.requests
    summary["ok"] = True
    return summary


def _channel_failed(conn, summary: dict, cid: int, exc: EngineError) -> bool:
    """Record one channel's failure in a sync run; True when the run should stop here."""
    conn.commit()
    if exc.kind in ("auth", "captcha"):
        raise exc
    if exc.kind == "budget":
        summary["deferred"] += 1
        return False
    if exc.kind == "forbidden":
        _mark(conn, cid, "forbidden")
    elif exc.kind == "not_found":
        _mark(conn, cid, "gone")
    conn.commit()
    if exc.kind in ("rate_limited", "network"):
        summary["errors"].append(f"channel {cid}: {exc}; stopped this run")
        return True
    summary["errors"].append(f"channel {cid}: {exc}")
    return False


def _recheck(conn, client: Client, summary: dict, plan: list) -> None:
    """Edits and deletions: read the newest page of up to RECHECK_PER_RUN channels again — those
    active in the last RECHECK_DAYS whose newest page was not read for RECHECK_INTERVAL (a seed
    counts; following new messages does not), least recently first. What is left of the run's
    budget bounds it all."""
    since = store.snowflake_at(datetime.now(timezone.utc) - timedelta(days=RECHECK_DAYS))
    ids = [int(r["id"]) for r in plan if (r.get("last_message_id") or 0) >= since]
    if not ids:
        return
    due = _now() - RECHECK_INTERVAL
    rows = conn.execute(
        f"SELECT c.channel_id FROM cursors c JOIN channels ch ON ch.id = c.channel_id "
        f"WHERE c.channel_id IN ({','.join('?' * len(ids))}) AND c.newest IS NOT NULL "
        f"AND COALESCE(c.rechecked_at, 0) <= ? AND (ch.state IS NULL OR ch.state NOT IN ('forbidden', 'gone')) "
        f"ORDER BY COALESCE(c.rechecked_at, 0) ASC LIMIT ?", ids + [due, RECHECK_PER_RUN]).fetchall()
    summary.setdefault("rechecked", 0)
    for (cid,) in rows:
        try:
            _fetch(client, cid, {"limit": str(RECHECK_COUNT)})
        except EngineError as exc:
            if exc.kind == "budget":
                conn.commit()
                return
            if _channel_failed(conn, summary, cid, exc):
                return
            continue
        conn.execute("UPDATE cursors SET rechecked_at = ? WHERE channel_id = ?", (_now(), cid))
        conn.commit()
        summary["rechecked"] += 1


# --- media --------------------------------------------------------------------------------------

def _url_name(url: str) -> str:
    return Path(urllib.parse.urlparse(url).path).name


def media_items(m: dict) -> list[dict]:
    """Everything savable in one message, in order: attachments, link-preview media (Discord's
    proxied copies only) and stickers, without duplicates."""
    items, seen = [], set()

    def add(item):
        if item["url"] and item["url"] not in seen:
            seen.add(item["url"])
            items.append(item)

    for i, a in enumerate(m.get("attachments") or []):
        if isinstance(a, dict):
            add({"kind": "attachment", "name": a.get("filename") or f"file-{i + 1}",
                 "type": a.get("content_type") or "", "size": a.get("size"), "url": a.get("url")})
    for e in m.get("embeds") or []:
        if not isinstance(e, dict):
            continue
        for part in ("image", "thumbnail", "video"):
            proxy = (e.get(part) or {}).get("proxy_url")
            if proxy:
                add({"kind": "preview", "name": f"preview-{_url_name(proxy) or part}", "type": "", "size": None,
                     "url": proxy, "source": e.get("url")})
    for st in m.get("sticker_items") or []:
        if not isinstance(st, dict) or not store.is_snowflake(str(st.get("id"))):
            continue
        ext = store.STICKER_FORMATS.get(st.get("format_type"), "png")
        host = "media.discordapp.net" if ext == "gif" else "cdn.discordapp.com"
        add({"kind": "sticker", "name": f"{st.get('name') or st['id']}.{ext}", "type": "", "size": None,
             "url": f"https://{host}/stickers/{st['id']}.{ext}"})
    return items


def media(client: Client, channel_id: str, message_id: str, folder: Path, limit: int) -> dict:
    """Fetch the message again (attachment URLs are signed and expire), then download each item
    into ``folder``. Each item reports saved / refused / too_large / missing / failed."""
    cid = int(channel_id)
    m = fetch_message(client, cid, message_id)
    if m is None:
        raise EngineError("not_found", "that message is gone or not visible to this account")
    deadline = time.monotonic() + MEDIA_BUDGET
    out = []
    for i, item in enumerate(media_items(m)):
        entry = {k: v for k, v in item.items() if k != "url"}
        url = urllib.parse.urlparse(item["url"] or "")
        if url.scheme != "https" or not store.MEDIA_HOST.match(url.hostname or ""):
            out.append({**entry, "status": "refused", "why": "not on Discord's media hosts"})
            continue
        if store.risky(item["name"], item["type"]):
            out.append({**entry, "status": "refused", "why": "an archive or program"})
            continue
        if isinstance(item["size"], int) and item["size"] > limit:
            out.append({**entry, "status": "too_large"})
            continue
        remaining = deadline - time.monotonic()
        if remaining < 5:
            out.append({**entry, "status": "failed", "why": "out of time for this call"})
            continue
        dest = folder / f"{i:02d}"
        client._pace()
        client.requests += 1
        headers = {"Accept": "*/*", "Accept-Language": client._accept_language(), "Referer": f"{WEB}/",
                   "User-Agent": client.http.user_agent, "Sec-Fetch-Dest": "image", "Sec-Fetch-Mode": "no-cors",
                   "Sec-Fetch-Site": "cross-site"}
        try:
            got = client.http.download(item["url"], dest, headers=headers, limit=limit,
                                       timeout=min(MEDIA_TIMEOUT, remaining))
        except TransportError as exc:
            out.append({**entry, "status": "failed", "why": client._scrub(str(exc))})
            continue
        if got["too_large"]:
            out.append({**entry, "status": "too_large", "size": got["size"]})
        elif 200 <= got["status"] < 300:
            out.append({**entry, "status": "saved", "file": dest.name, "size": got["size"],
                        "type": item["type"] or got["type"]})
        else:
            out.append({**entry, "status": "missing", "why": f"Discord's media host answered {got['status']}"})
    return {"items": out}


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


def outbox_files(files) -> list[dict]:
    """The approved snapshots to attach: regular files inside the state's outbox, nothing else."""
    if not files:
        return []
    if not isinstance(files, list) or len(files) > 10:
        raise EngineError("usage", "files must be a list of at most 10 outbox files")
    outbox = (store.state_dir() / "outbox").resolve()
    out = []
    for f in files:
        if not isinstance(f, dict) or not isinstance(f.get("path"), str) or not isinstance(f.get("name"), str):
            raise EngineError("usage", "each file needs path and name")
        path = Path(f["path"]).resolve()
        if outbox not in path.parents or not path.is_file():
            raise EngineError("usage", "attachments are read only from the approved outbox")
        out.append({"path": path, "name": f["name"], "size": path.stat().st_size})
    return out


def _upload(conn, client: Client, cid: int, files: list[dict]) -> list[dict]:
    """Reserve upload URLs and PUT each file there; the attachments entry for the message.
    Nothing here creates a message, so any failure means not sent."""
    referer = _referer(conn, cid)
    client._pace()
    client.requests += 1
    status, headers, payload = client.http.request(
        "POST", f"{API}/channels/{cid}/attachments", timeout=REQUEST_TIMEOUT,
        headers=client.headers(referer=referer, json_body=True),
        body={"files": [{"id": str(i), "filename": f["name"], "file_size": f["size"]} for i, f in enumerate(files)]})
    if not (200 <= status < 300 and isinstance(payload, dict) and isinstance(payload.get("attachments"), list)):
        raise client._http_error(status, headers, payload)
    slots = {str(a.get("id")): a for a in payload["attachments"] if isinstance(a, dict)}
    deadline = time.monotonic() + UPLOAD_BUDGET
    attachments = []
    for i, f in enumerate(files):
        slot = slots.get(str(i)) or {}
        url, uploaded = slot.get("upload_url"), slot.get("upload_filename")
        host = re.match(r"^https://([^/]+)/", url or "")
        if not uploaded or not host or not UPLOAD_HOST.match(host.group(1)):
            raise EngineError("http", "Discord returned no usable upload URL")
        data = f["path"].read_bytes()
        if len(data) != f["size"]:
            raise EngineError("usage", f"{f['name']} changed while it was being sent")
        put_headers = {"Accept": "*/*", "Content-Type": "", "Origin": WEB, "Referer": f"{WEB}{referer}",
                       "User-Agent": client.http.user_agent, "Sec-Fetch-Dest": "empty", "Sec-Fetch-Mode": "cors",
                       "Sec-Fetch-Site": "cross-site"}
        remaining = deadline - time.monotonic()
        if remaining < 10:
            raise EngineError("upload", "the uploads took too long; nothing was sent")
        client._pace()
        client.requests += 1
        try:
            status, _, answer = client.http.request("PUT", url, data=data, headers=put_headers,
                                                    timeout=min(UPLOAD_TIMEOUT, remaining))
        except TransportError as exc:
            raise EngineError("network", f"uploading {f['name']} failed: {client._scrub(str(exc))}") from exc
        if not 200 <= status < 300:
            raise EngineError("http", f"uploading {f['name']} failed: storage answered {status}")
        attachments.append({"id": str(i), "filename": f["name"], "uploaded_filename": uploaded})
    return attachments


def send(conn, plan: dict, client_factory) -> dict:
    """Exactly one message POST. Outcome: sent (with the message id), not_sent (Discord or the
    network refused before anything was created), or uncertain (it may exist; a read-back looks
    once)."""
    nonce, cid, text = plan["nonce"], int(plan["channel"]), plan["text"]
    reply_to = int(plan["reply_to"]) if plan.get("reply_to") else None
    if ledger_status(conn, nonce):
        return {"outcome": "not_sent", "detail": "this send was already attempted (same nonce); nothing was sent again"}
    conn.execute("INSERT INTO sends (nonce, channel_id, text_hash, reply_to, created, status) VALUES (?, ?, ?, ?, ?, ?)",
                 (nonce, cid, text_hash(text), reply_to, _now(), "pending"))
    conn.commit()
    try:
        files = outbox_files(plan.get("files"))
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
    if files:
        try:
            body["attachments"] = _upload(conn, client, cid, files)
        except (EngineError, TransportError, OSError) as exc:
            detail = client._scrub(str(exc))
            _ledger(conn, nonce, "not_sent", detail=detail)
            return {"outcome": "not_sent", "detail": detail, "kind": getattr(exc, "kind", "upload")}
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
    if len(m.get("attachments") or []) != len(plan.get("files") or []):
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


# --- threads, pins, mentions, friends, server-side search ----------------------------------------

def threads(client: Client, channel_id: str, *, archived=None, offset: int = 0, limit: int = 25) -> dict:
    """Threads (or forum posts) under one parent channel, newest activity first. Each thread is
    stored as a channel, so it can be read and sent to afterwards."""
    conn = client.conn
    params = {"sort_by": "last_message_time", "sort_order": "desc", "limit": str(limit), "offset": str(offset)}
    if archived is not None:
        params["archived"] = "true" if archived else "false"
    found = client.get(f"/channels/{channel_id}/threads/search", params=params, referer=_referer(conn, channel_id))
    now, rows = _now(), []
    for t in found.get("threads") or []:
        if isinstance(t, dict) and t.get("id"):
            row = store.channel_row(t)
            store.upsert_channel(conn, row, now)
            rows.append(row)
    first = {}
    for m in found.get("first_messages") or []:
        if isinstance(m, dict) and m.get("id") and m.get("channel_id"):
            _store_batch(client, m["channel_id"], [m], reactions=False)
            first[str(m["channel_id"])] = (m.get("content") or "")[:300]
    conn.commit()
    return {"threads": rows, "first": first, "has_more": bool(found.get("has_more")),
            "total": found.get("total_results")}


def pins(client: Client, channel_id: str, *, before=None, limit: int = 50) -> dict:
    params = {"limit": str(limit)}
    if before:
        params["before"] = before
    found = client.get(f"/channels/{channel_id}/messages/pins", params=params,
                       referer=_referer(client.conn, channel_id))
    items = [i for i in found.get("items") or [] if isinstance(i, dict) and isinstance(i.get("message"), dict)]
    rows = _store_batch(client, channel_id, [i["message"] for i in items], reactions=False)
    pinned = {str(i["message"].get("id")): i.get("pinned_at") for i in items}
    client.conn.commit()
    return {"messages": [{**r, "pinned_at": pinned.get(str(r["id"]))} for r in rows],
            "has_more": bool(found.get("has_more"))}


def mentions(client: Client, *, guild=None, before=None, limit: int = 25) -> dict:
    params = {"limit": str(limit), "roles": "true", "everyone": "true"}
    if guild:
        params["guild_id"] = guild
    if before:
        params["before"] = before
    found = client.get("/users/@me/mentions", params=params)
    rows = _store_found(client, found if isinstance(found, list) else [])
    client.conn.commit()
    return {"messages": rows}


def friends(client: Client) -> dict:
    """Friends (pending requests and blocks only counted), cached in the mirror's meta."""
    found = client.get("/users/@me/relationships")
    out = {"friends": [], "incoming": 0, "outgoing": 0}
    for r in found if isinstance(found, list) else []:
        if not isinstance(r, dict):
            continue
        user = r.get("user") or {}
        if r.get("type") == 1:
            out["friends"].append({"id": str(r.get("id") or user.get("id")), "name": store.display_name(user),
                                   "username": user.get("username"), "nickname": r.get("nickname")})
        elif r.get("type") == 3:
            out["incoming"] += 1
        elif r.get("type") == 4:
            out["outgoing"] += 1
    store.set_meta(client.conn, "friends", {**out, "fetched": _now()})
    client.conn.commit()
    return out


def _hits(groups) -> list[dict]:
    """Search results come as groups of messages; the hits are flagged when context rides along."""
    out = []
    for group in groups or []:
        group = group if isinstance(group, list) else [group]
        group = [m for m in group if isinstance(m, dict) and m.get("id")]
        flagged = [m for m in group if m.get("hit")]
        out += flagged or group
    return out


def search(client: Client, *, query: str, guild=None, channel=None, offset: int = 0, limit: int = 25,
           min_id=None, max_id=None) -> dict:
    """Discord's own search: one server (optionally one of its channels), one DM or group DM, or
    every DM at once (no guild or channel)."""
    terms = {"content": query, "offset": offset, "limit": limit, "sort_by": "timestamp", "sort_order": "desc"}
    if min_id:
        terms["min_id"] = str(min_id)
    if max_id:
        terms["max_id"] = str(max_id)
    params = {k: str(v) for k, v in terms.items()}
    if guild:
        if channel:
            params["channel_id"] = str(channel)
        found = client.get(f"/guilds/{guild}/messages/search", params=params, referer=f"/channels/{guild}")
        groups, total = found.get("messages"), found.get("total_results")
        now = _now()
        for t in found.get("threads") or []:
            if isinstance(t, dict) and t.get("id"):
                store.upsert_channel(client.conn, store.channel_row(t), now)
    elif channel:
        found = client.get(f"/channels/{channel}/messages/search", params=params, referer=f"/channels/@me/{channel}")
        groups, total = found.get("messages"), found.get("total_results")
    else:
        found = client.read("POST", "/users/@me/messages/search/tabs",
                            body={"tabs": {"messages": terms}, "track_exact_total_hits": False})
        tab = (found.get("tabs") or {}).get("messages") or {}
        groups, total = tab.get("messages"), tab.get("total_results")
    rows = _store_found(client, _hits(groups))
    client.conn.commit()
    return {"messages": rows, "total": total}


# --- roles and members --------------------------------------------------------------------------

def roles(client: Client, guild_id: str) -> dict:
    """The server's roles (with member counts) and the user's own member, into the mirror."""
    conn = client.conn
    if not client.me.get("id"):
        whoami(client)  # the user's own member carries no user
    referer = f"/channels/{guild_id}"
    found = client.get(f"/guilds/{guild_id}/roles", referer=referer)
    try:
        counts = client.get(f"/guilds/{guild_id}/roles/member-counts", referer=referer)
    except EngineError as exc:
        if exc.kind in ("auth", "captcha"):
            raise
        counts = {}
    mine = client.get(f"/users/@me/guilds/{guild_id}/member", referer=referer)
    row = conn.execute("SELECT owner FROM guilds WHERE id = ?", (int(guild_id),)).fetchone()
    if row is None or row["owner"] is None:
        guilds(client)  # who owns the server comes with the server list
    now = _now()
    store.replace_roles(conn, guild_id, found if isinstance(found, list) else [], counts, now)
    store.upsert_member(conn, store.member_row(mine, guild_id, client.me), now)
    conn.commit()
    return {"roles": len(found) if isinstance(found, list) else 0}


def member(client: Client, guild_id: str, user_id: str) -> dict:
    m = client.get(f"/guilds/{guild_id}/members/{user_id}", referer=f"/channels/{guild_id}")
    row = store.member_row(m, guild_id)
    store.upsert_member(client.conn, row, _now())
    client.conn.commit()
    return row


def role_members(client: Client, guild_id: str, role_id: str) -> dict:
    found = client.get(f"/guilds/{guild_id}/roles/{role_id}/member-ids", referer=f"/channels/{guild_id}")
    return {"ids": [str(i) for i in found] if isinstance(found, list) else []}


def members(client: Client, guild_id: str, query: str, limit: int = 25) -> dict:
    """Members by name (display name, username or nickname): Discord's member search, which needs
    the Manage Server permission."""
    body = {"limit": limit, "or_query": {"usernames": {"or_query": [query]}}}
    found = client.read("POST", f"/guilds/{guild_id}/members-search", body=body, referer=f"/channels/{guild_id}")
    now, rows = _now(), []
    for item in found.get("members") or []:
        m = item.get("member") if isinstance(item, dict) and isinstance(item.get("member"), dict) else item
        if isinstance(m, dict) and isinstance(m.get("user"), dict) and m["user"].get("id"):
            row = store.member_row(m, guild_id)
            store.upsert_member(client.conn, row, now)
            rows.append(row)
    client.conn.commit()
    return {"members": rows, "total": found.get("total_result_count")}


# --- entry --------------------------------------------------------------------------------------

def _int(args: dict, key: str, default: int, top: int) -> int:
    value = args.get(key)
    if value in (None, ""):
        return default
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise EngineError("usage", f"{key} must be a non-negative integer")
    return min(value, top)


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
                    "text": args.get("text") or "", "reply_to": _arg(args, "reply_to", required=False),
                    "files": args.get("files") or []}
            if not isinstance(plan["text"], str) or not (plan["text"].strip() or plan["files"]):
                raise EngineError("usage", "text or files are required")
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
        if command == "media":
            token = args.get("token")
            if not isinstance(token, str) or not INCOMING_TOKEN.match(token):
                raise EngineError("usage", "token must be 32 hex characters")
            limit = args.get("limit")
            if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MEDIA_LIMIT_MAX:
                raise EngineError("usage", f"limit must be 1 to {MEDIA_LIMIT_MAX} bytes")
            folder = store.state_dir() / "incoming"
            folder.mkdir(mode=0o700, exist_ok=True)
            folder = folder / token
            folder.mkdir(mode=0o700)
            return media(client, _arg(args, "channel"), _arg(args, "id"), folder, limit)
        if command == "backfill":
            pages = max(1, min(int(args.get("pages") or BACKFILL_PAGES[0]), BACKFILL_PAGES[1]))
            if not client.me.get("id"):
                whoami(client)
            return backfill(client, _arg(args, "channel"), pages)
        if command in ("mentions", "search") and not client.me.get("id"):
            whoami(client)  # from_me needs the account id
        if command == "threads":
            archived = args.get("archived")
            return threads(client, _arg(args, "channel"), archived=archived if isinstance(archived, bool) else None,
                           offset=_int(args, "offset", 0, 9975), limit=_int(args, "limit", 25, 25) or 25)
        if command == "pins":
            before = args.get("before")
            return pins(client, _arg(args, "channel"), before=before if isinstance(before, str) and before else None,
                        limit=_int(args, "limit", 50, 50) or 50)
        if command == "mentions":
            return mentions(client, guild=_arg(args, "guild", required=False),
                            before=_arg(args, "before", required=False), limit=_int(args, "limit", 25, 25) or 25)
        if command == "friends":
            return friends(client)
        if command == "search":
            query = args.get("query")
            if not isinstance(query, str) or not query.strip():
                raise EngineError("usage", "query is required")
            return search(client, query=query.strip()[:1024], guild=_arg(args, "guild", required=False),
                          channel=_arg(args, "channel", required=False), offset=_int(args, "offset", 0, 9975),
                          limit=_int(args, "limit", 25, 25) or 25, min_id=_arg(args, "min_id", required=False),
                          max_id=_arg(args, "max_id", required=False))
        if command == "roles":
            return roles(client, _arg(args, "guild"))
        if command == "member":
            return member(client, _arg(args, "guild"), _arg(args, "user"))
        if command == "role_members":
            return role_members(client, _arg(args, "guild"), _arg(args, "role"))
        if command == "members":
            query = args.get("query")
            if not isinstance(query, str) or not query.strip():
                raise EngineError("usage", "query is required")
            return members(client, _arg(args, "guild"), query.strip()[:100], _int(args, "limit", 25, 100) or 25)
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
