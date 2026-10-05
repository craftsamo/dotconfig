"""substack-access bridge: one Substack call, run by the engine venv's interpreter (not Hermes').

The engine (``sa.py``) writes one JSON request to stdin and reads one JSON reply from stdout.

The session cookies of the user's own Substack account are read from the Keychain at start
(``secret get SUBSTACK_COOKIES -p hermes --scope substack-session``, a scope no Hermes profile
receives) and live only in this short-lived process. They are bound to ``.substack.com``, so the
cookie jar never sends them to another host (a publication on a custom domain is read without
them); every string that leaves is masked. The reply says what became of the session (refused,
rate-limited, blocked) so the engine can remember it between calls. Contract:
docs/substack-access.md.

    {"op": "check" | "archive" | "post" | "inbox" | "published" | "drafts" | "draft" | "stats",
     "deadline": seconds, "refused": <fingerprint the engine saw refused, or null>,
     "publication": <configured own publication host, or null>, ...op arguments}
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.parse import quote, unquote, urljoin, urlsplit

SECRET = Path.home() / ".config" / "bin" / "secret"
COOKIES_NAME, COOKIES_PROJECT, COOKIES_SCOPE = "SUBSTACK_COOKIES", "hermes", "substack-session"
COOKIES_SET = f"secret set {COOKIES_NAME} -p {COOKIES_PROJECT} --scope {COOKIES_SCOPE}"
SECRET_TIMEOUT = 20
SESSION_COOKIE = "substack.sid"
COOKIE_DOMAIN = ".substack.com"
ROOT = "https://substack.com/api/v1"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/129.0.0.0 Safari/537.36")
REQUEST_TIMEOUT = 30
MAX_REDIRECTS = 3
DEFAULT_RETRY_AFTER = 900

# Keys that only cost size in a reply; the engine never shows them.
HEAVY = {"body_json", "draft_body", "podcastFields", "podcastUpload", "podcastPreviewUpload", "videoUpload",
         "voiceoverUpload", "audio_items", "coverImagePalette", "reactions", "inboxItem", "top_exclusions",
         "pins", "postCountryBlocks", "headlineTest", "theme", "logoPalette", "site_config"}

SECRETS: list[str] = []


class Setup(Exception):
    pass


class Failure(Exception):
    """A request that did not give data: kind is setup / refused / blocked / limited / not_found /
    forbidden / no_publication / timeout / error."""

    def __init__(self, kind: str, error: str, *, retry_after: int | None = None):
        super().__init__(error)
        self.kind = kind
        self.error = error
        self.retry_after = retry_after


def mask(text) -> str:
    text = str(text)
    for value in SECRETS:
        if value and len(value) > 3:
            text = text.replace(value, "…")
    return text


def _plain(value):
    return json.loads(json.dumps(value, default=str))


def parse_cookies(value: str) -> dict[str, str]:
    cookies = {}
    for part in value.split(";"):
        if "=" in part:
            name, val = part.split("=", 1)
            if name.strip() and val.strip():
                cookies[name.strip()] = val.strip()
    return cookies


def read_cookies() -> tuple[dict[str, str], str]:
    """(cookies, fingerprint) from the Keychain; raises Setup with the fix."""
    if not SECRET.exists():
        raise Setup(f"the secret CLI is missing at {SECRET}")
    try:
        proc = subprocess.run([str(SECRET), "get", COOKIES_NAME, "-p", COOKIES_PROJECT, "--scope", COOKIES_SCOPE],
                              stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=SECRET_TIMEOUT)
    except subprocess.TimeoutExpired as exc:
        raise Setup("reading the Substack cookies from the Keychain timed out") from exc
    value = proc.stdout.strip()
    if proc.returncode != 0 or not value:
        raise Setup(f"no Substack cookies in the Keychain ({COOKIES_NAME}, project {COOKIES_PROJECT}, "
                    f"scope {COOKIES_SCOPE}); the user stores them with `{COOKIES_SET}`")
    cookies = parse_cookies(value)
    if not cookies.get(SESSION_COOKIE):
        raise Setup(f"{COOKIES_NAME} must hold {SESSION_COOKIE} ('{SESSION_COOKIE}=…; substack.lli=…')")
    SECRETS.append(value)
    for val in cookies.values():
        SECRETS.extend([val, unquote(val)])
    fingerprint = hashlib.sha256(cookies[SESSION_COOKIE].encode()).hexdigest()[:12]
    return cookies, fingerprint


# --- HTTP ---------------------------------------------------------------------------------------

class Client:
    """Two sessions: ``auth`` carries the cookies, bound to .substack.com; ``anon`` carries none and
    is the only one that talks to other hosts (custom domains), after a public-address check."""

    def __init__(self, cookies: dict[str, str], deadline: float):
        import requests
        self.requests = requests
        self.auth = requests.Session()
        self.anon = requests.Session()
        for session in (self.auth, self.anon):
            session.headers.update({"User-Agent": UA, "Accept": "application/json"})
            session.trust_env = False
        for name, value in cookies.items():
            self.auth.cookies.set(name, value, domain=COOKIE_DOMAIN, path="/", secure=True)
        self.ends = time.monotonic() + deadline
        self.contacted = False

    def _timeout(self) -> float:
        left = self.ends - time.monotonic()
        if left <= 1:
            raise Failure("timeout", "Substack did not answer within the deadline")
        return min(REQUEST_TIMEOUT, left)

    def get(self, url: str, params: dict | None = None):
        """A GET that follows redirects one hop at a time: a Substack host gets the cookie session,
        any other host the cookieless one, and only after it resolves to public addresses."""
        for _ in range(MAX_REDIRECTS + 1):
            parts = urlsplit(url)
            if parts.scheme != "https":
                raise Failure("error", f"refused: {parts.scheme or 'no'} scheme for {parts.hostname}")
            host = parts.hostname or ""
            if is_substack(host):
                session = self.auth
            else:
                check_public(host)
                session = self.anon
            response = self._send(session, url, params)
            if response.status_code in (301, 302, 303, 307, 308) and response.headers.get("Location"):
                url, params = urljoin(url, response.headers["Location"]), None
                continue
            return self._json(response, url)
        raise Failure("error", "too many redirects")

    def _send(self, session, url, params=None):
        try:
            self.contacted = True
            return session.get(url, params=params, timeout=self._timeout(), allow_redirects=False)
        except self.requests.Timeout as exc:
            raise Failure("timeout", "Substack did not answer in time") from exc
        except self.requests.RequestException as exc:
            raise Failure("error", f"could not reach {urlsplit(url).hostname}: {type(exc).__name__}") from exc

    def _json(self, response, url):
        status = response.status_code
        ctype = (response.headers.get("Content-Type") or "").lower()
        if status == 429:
            raise Failure("limited", "Substack is rate-limiting this account",
                          retry_after=_retry_after(response.headers.get("Retry-After")))
        if response.headers.get("cf-mitigated") or ("text/html" in ctype and "Just a moment" in response.text[:4000]):
            raise Failure("blocked", "Cloudflare challenged the request (bot protection)")
        if status in (401, 403):
            raise Failure("forbidden", f"Substack answered {status} for {_path(url)}")
        if status == 404:
            raise Failure("not_found", f"nothing at {_path(url)}")
        if not 200 <= status < 300:
            raise Failure("error", f"Substack answered {status} for {_path(url)}")
        try:
            return response.json()
        except ValueError as exc:
            raise Failure("error", f"Substack sent no JSON for {_path(url)}") from exc


def _retry_after(value) -> int:
    try:
        return max(60, min(int(value), 86400))
    except (TypeError, ValueError):
        return DEFAULT_RETRY_AFTER


def _path(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.hostname}{parts.path}"


def is_substack(host: str) -> bool:
    host = host.lower().rstrip(".")
    return host == "substack.com" or host.endswith(".substack.com")


def check_public(host: str) -> None:
    """Only a DNS name whose every address is public may be fetched (no internal hosts)."""
    host = host.lower().rstrip(".")
    try:
        ipaddress.ip_address(host)
        raise Failure("error", f"refused: {host} is an address, not a publication host")
    except ValueError:
        pass
    if "." not in host or host.endswith((".local", ".internal", ".lan", ".home", ".localhost")):
        raise Failure("error", f"refused: {host} is not a public host")
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except OSError as exc:
        raise Failure("not_found", f"{host} does not resolve") from exc
    for info in infos:
        if not ipaddress.ip_address(info[4][0]).is_global:
            raise Failure("error", f"refused: {host} resolves to a non-public address")


# --- the account and its publication -----------------------------------------------------------

def profile(client: Client) -> dict:
    """GET profile/self; a 401/403 here means the session itself is refused."""
    try:
        data = client.get(f"{ROOT}/user/profile/self")
    except Failure as exc:
        if exc.kind == "forbidden":
            raise Failure("refused", exc.error) from exc
        raise
    if not isinstance(data, dict) or not data.get("id"):
        raise Failure("refused", "Substack did not recognise the session (no signed-in user)")
    return data


def _host(value: str) -> str:
    value = (value or "").strip().lower()
    host = urlsplit(value).hostname if "//" in value else value.split("/")[0]
    host = (host or "").rstrip(".")
    return host[4:] if host.startswith("www.") else host


def own_publication(client: Client, configured: str | None) -> dict:
    me = profile(client)
    pubs = [u.get("publication") or {} for u in me.get("publicationUsers") or [] if u.get("publication")]
    roles = {(u.get("publication") or {}).get("id"): u.get("role") for u in me.get("publicationUsers") or []}
    chosen = None
    if configured:
        want = _host(configured)
        for pub in pubs:
            hosts = {f"{pub.get('subdomain')}.substack.com", _host(pub.get("custom_domain") or ""),
                     str(pub.get("subdomain") or "")}
            if want in hosts:
                chosen = pub
                break
        if chosen is None:
            raise Failure("no_publication", f"the account has no publication {configured!r} "
                                            "(substack_access.publication in the profile's config.yaml)")
    else:
        primary = (me.get("primaryPublication") or {}).get("id")
        chosen = next((p for p in pubs if p.get("id") == primary), None) or (pubs[0] if pubs else None)
    if not chosen or not chosen.get("subdomain"):
        raise Failure("no_publication", "the Substack account has no publication of its own yet; the user "
                                        "creates one on substack.com")
    sub = chosen["subdomain"]
    return {"id": chosen.get("id"), "name": chosen.get("name"), "subdomain": sub,
            "custom_domain": chosen.get("custom_domain"), "role": roles.get(chosen.get("id")),
            "url": f"https://{chosen.get('custom_domain') or sub + '.substack.com'}",
            "api": f"https://{sub}.substack.com/api/v1", "user_id": me.get("id"), "handle": me.get("handle")}


# --- shapes --------------------------------------------------------------------------------------

def slim(item, keep_body: bool = False):
    if not isinstance(item, dict):
        return item
    out = {k: v for k, v in item.items() if k not in HEAVY and (keep_body or k != "body_html")}
    bylines = out.get("publishedBylines") or out.get("published_bylines")
    if isinstance(bylines, list):
        out["publishedBylines"] = [{"name": b.get("name"), "handle": b.get("handle")} for b in bylines
                                   if isinstance(b, dict)]
        out.pop("published_bylines", None)
    return out


def _pub_brief(pub) -> dict | None:
    if not isinstance(pub, dict):
        return None
    return {"id": pub.get("id"), "name": pub.get("name"), "subdomain": pub.get("subdomain"),
            "custom_domain": pub.get("custom_domain")}


# --- reads ---------------------------------------------------------------------------------------

def op_archive(client: Client, req: dict):
    if req.get("host"):
        base, pub = f"https://{req['host']}/api/v1", None
    else:
        pub = own_publication(client, req.get("publication"))
        base = pub["api"]
    params = {"sort": "new", "offset": int(req.get("offset") or 0), "limit": int(req["limit"])}
    if req.get("query"):
        params["search"] = req["query"]
    items = client.get(f"{base}/archive", params)
    if not isinstance(items, list):
        raise Failure("error", "the archive did not come back as a list")
    return {"publication": pub, "posts": [slim(p) for p in items]}


def op_post(client: Client, req: dict):
    if req.get("id"):
        wrapper = client.get(f"{ROOT}/posts/by-id/{int(req['id'])}")
    else:
        host, slug = req["host"], quote(req["slug"], safe="")
        if is_substack(host):
            post = client.get(f"https://{host}/api/v1/posts/{slug}")
            wrapper = {"post": post}
        else:  # a custom domain: find the id without cookies, then read it on substack.com with them
            post = client.get(f"https://{host}/api/v1/posts/{slug}")
            wrapper = client.get(f"{ROOT}/posts/by-id/{int(post['id'])}") if post.get("id") else {"post": post}
    post = wrapper.get("post") if isinstance(wrapper, dict) else None
    if not isinstance(post, dict):
        raise Failure("error", "the post did not come back as an object")
    sub = wrapper.get("subscription") if isinstance(wrapper.get("subscription"), dict) else {}
    return {"post": slim(post, keep_body=True), "publication": _pub_brief(wrapper.get("publication")),
            "membership": sub.get("membership_state")}


def op_inbox(client: Client, req: dict):
    data = client.get(f"{ROOT}/inbox/top", {"inboxType": "inbox", "surface": "inbox_all", "limit": int(req["limit"])})
    if not isinstance(data, dict):
        raise Failure("error", "the inbox did not come back as an object")
    pubs = {str(p.get("id")): p.get("name") for p in data.get("publications") or [] if isinstance(p, dict)}
    return {"posts": [slim(p) for p in data.get("posts") or []], "publications": pubs, "more": bool(data.get("more"))}


def op_published(client: Client, req: dict):
    pub = own_publication(client, req.get("publication"))
    data = client.get(f"{pub['api']}/post_management/published",
                      {"offset": int(req.get("offset") or 0), "limit": int(req["limit"]), "order_by": "post_date",
                       "order_direction": "desc"})
    return {"publication": pub, "posts": [slim(p) for p in (data or {}).get("posts") or []],
            "total": (data or {}).get("total")}


def op_drafts(client: Client, req: dict):
    pub = own_publication(client, req.get("publication"))
    data = client.get(f"{pub['api']}/drafts",
                      {"filter": "draft", "offset": int(req.get("offset") or 0), "limit": int(req["limit"])})
    posts = data.get("posts") if isinstance(data, dict) else data
    return {"publication": pub, "posts": [slim(p) for p in posts or []],
            "more": bool(data.get("hasMore")) if isinstance(data, dict) else None}


def op_draft(client: Client, req: dict):
    pub = own_publication(client, req.get("publication"))
    draft = client.get(f"{pub['api']}/drafts/{int(req['id'])}")
    if not isinstance(draft, dict):
        raise Failure("error", "the draft did not come back as an object")
    body = draft.get("draft_body")
    markdown, unsupported = "", []
    if body:
        from substack.mdexport import document_to_markdown
        try:
            markdown, unsupported = document_to_markdown(json.loads(body) if isinstance(body, str) else body)
        except Exception as exc:  # a body the converter cannot read is reported, not fatal
            markdown = f"(the body could not be converted to Markdown: {type(exc).__name__})"
    return {"publication": pub, "draft": slim(draft), "markdown": markdown, "unsupported": len(unsupported or [])}


def op_stats(client: Client, req: dict):
    pub = own_publication(client, req.get("publication"))
    summary = client.get(f"{pub['api']}/publish-dashboard/summary")
    checklist = client.get(f"{pub['api']}/publication_launch_checklist")
    count = None
    if isinstance(checklist, dict):
        count = checklist.get("subscriberCount")
        if count is None and isinstance(checklist.get("subscribers"), list):
            count = len(checklist["subscribers"])
    return {"publication": pub, "summary": summary if isinstance(summary, dict) else {}, "subscriber_count": count}


OPS = {"archive": op_archive, "post": op_post, "inbox": op_inbox, "published": op_published,
       "drafts": op_drafts, "draft": op_draft, "stats": op_stats}


def _forbidden_or_refused(client: Client, exc: Failure) -> Failure:
    """A 401/403 from an op is a refused session only if profile/self says so too."""
    try:
        profile(client)
    except Failure as again:
        return again
    return exc


def main(req: dict) -> dict:
    try:
        cookies, fingerprint = read_cookies()
    except Setup as exc:
        return {"ok": False, "kind": "setup", "error": str(exc), "contacted": False}
    if req["op"] == "check":
        return {"ok": True, "data": None, "fingerprint": fingerprint, "contacted": False}
    if req.get("refused") and req["refused"] == fingerprint:
        return {"ok": False, "kind": "refused", "fingerprint": fingerprint, "contacted": False}
    handler = OPS.get(req["op"])
    if handler is None:
        raise ValueError(f"unknown op {req['op']!r}")
    client = Client(cookies, float(req.get("deadline", 60)))
    reply = {"fingerprint": fingerprint}
    try:
        reply.update(ok=True, data=handler(client, req), session={"active": True})
    except Failure as exc:
        if exc.kind == "forbidden":
            exc = _forbidden_or_refused(client, exc)
        reply.update(ok=False, kind=exc.kind, error=exc.error)
        if exc.kind == "refused":
            reply["session"] = {"active": False, "error": exc.error}
        if exc.retry_after:
            reply["retry_after"] = exc.retry_after
    reply["contacted"] = client.contacted
    return reply


if __name__ == "__main__":
    try:
        request = json.loads(sys.stdin.read())
        reply = main(request)
    except Exception as exc:  # reported to the engine, never a traceback on stdout
        reply = {"ok": False, "kind": "error", "error": mask(f"{type(exc).__name__}: {exc}")[:500], "contacted": True}
    sys.stdout.write(mask(json.dumps(_plain(reply), ensure_ascii=False)))
