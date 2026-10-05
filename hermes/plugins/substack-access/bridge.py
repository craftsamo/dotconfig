"""substack-access bridge: one Substack call, run by the engine venv's interpreter (not Hermes').

The engine (``sa.py``) writes one JSON request to stdin and reads one JSON reply from stdout.

The session cookies of the user's own Substack account are read from the Keychain at start
(``secret get SUBSTACK_COOKIES -p hermes --scope substack-session``, a scope no Hermes profile
receives) and live only in this short-lived process. They are bound to ``.substack.com``, so the
cookie jar never sends them to another host (a publication on a custom domain is read without
them); every string that leaves is masked. The reply says what became of the session (refused,
rate-limited, blocked) so the engine can remember it between calls. Contract:
docs/substack-access.md.

    {"op": "check" | "archive" | "post" | "inbox" | "published" | "drafts" | "draft" | "stats"
           | "prepublish" | "prepare" | "write",
     "deadline": seconds, "refused": <fingerprint the engine saw refused, or null>,
     "publication": <configured own publication host, or null>, ...op arguments}
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
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
        self._guard_auth()

    def _guard_auth(self) -> None:
        """Every request on the cookie session, including python-substack's own: https to a Substack
        host only, within the deadline, and a write never follows a redirect."""
        send = self.auth.request

        def request(method, url, **kwargs):
            parts = urlsplit(url)
            if parts.scheme != "https" or not is_substack(parts.hostname or ""):
                raise Failure("error", f"refused: the signed-in session only talks to Substack, not {parts.hostname}")
            if kwargs.get("timeout") is None:
                kwargs["timeout"] = self._timeout()
            if method.upper() != "GET":
                kwargs["allow_redirects"] = False
            self.contacted = True
            return send(method, url, **kwargs)

        self.auth.request = request

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


def op_prepublish(client: Client, req: dict):
    pub = own_publication(client, req.get("publication"))
    checks = client.get(f"{pub['api']}/drafts/{int(req['id'])}/prepublish")
    return {"publication": pub, "checks": checks}


# --- writes --------------------------------------------------------------------------------------
#
# Every write was approved on a card the engine built from a ``prepare`` reply. ``prepare`` reads
# what the card shows (the draft, the email audience) and lists the Markdown's local images with
# python-substack's own parser; ``write`` re-reads a draft and refuses when it is no longer the one
# the card showed, uploads only the copies the engine froze at approval, and marks a ledger file
# right before each step that changes the account, so a killed process still says how far it got.

DRAFT_BOUND = {"update_draft", "publish", "schedule", "unschedule"}
PLACEHOLDER = "https://substackcdn.com/image/fetch/placeholder.png"
NOTE_URL = re.compile(r"https?://[^\s<>()\"']+[^\s<>()\"'.,;:!?]")


class Uncertain(Exception):
    """A step that changes the account was sent, and its outcome is unknown."""


class _Recorder:
    """Stands in for the Api while Markdown is rendered: records each local image instead of uploading."""

    def __init__(self):
        self.paths: list[str] = []

    def get_image(self, path):
        self.paths.append(str(path))
        return {"url": PLACEHOLDER}


def scan_images(markdown: str) -> list[str]:
    """The local images of a Markdown body, as python-substack resolves them (no network)."""
    from substack import mdrender
    recorder = _Recorder()
    try:
        mdrender.markdown_to_doc(markdown, api=recorder)
    except FileNotFoundError as exc:
        raise Failure("invalid", f"{exc}; give images as absolute paths (or ~/…) to files that exist") from exc
    except ValueError as exc:
        raise Failure("invalid", f"the Markdown cannot be converted: {exc}") from exc
    return list(dict.fromkeys(recorder.paths))


def _schedules(draft: dict) -> list[str]:
    return sorted(str(s.get("trigger_at")) for s in draft.get("postSchedules") or []
                  if isinstance(s, dict) and s.get("trigger_at"))


def draft_digest(draft: dict) -> str:
    """What a card shows of a draft and a write acts on: title, subtitle, body, audience, email and
    scheduled releases (not the edit timestamp)."""
    body = draft.get("draft_body")
    if not isinstance(body, str):
        body = json.dumps(body, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(json.dumps([draft.get("draft_title") or "", draft.get("draft_subtitle") or "", body or "",
                                      draft.get("audience"), bool(draft.get("should_send_email")),
                                      bool(draft.get("is_published")), _schedules(draft)],
                                     ensure_ascii=False).encode("utf-8")).hexdigest()


def _doc_words(body) -> int:
    try:
        doc = json.loads(body) if isinstance(body, str) else body
    except ValueError:
        return 0
    words, stack = 0, [doc]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            if node.get("type") == "text":
                words += len(str(node.get("text") or "").split())
            stack.extend(node.get("content") or [])
        elif isinstance(node, list):
            stack.extend(node)
    return words


def draft_brief(draft: dict) -> dict:
    return {"id": draft.get("id"), "title": draft.get("draft_title") or "", "subtitle": draft.get("draft_subtitle") or "",
            "audience": draft.get("audience"), "updated": draft.get("draft_updated_at"),
            "published": bool(draft.get("is_published")), "should_send_email": draft.get("should_send_email"),
            "scheduled": _schedules(draft), "words": _doc_words(draft.get("draft_body"))}


def api_for(client: Client, pub: dict):
    """python-substack's Api on the guarded cookie session, without its eager sign-in."""
    from substack import Api
    api = object.__new__(Api)
    api.base_url, api.timeout, api._session, api.publication_url = ROOT, None, client.auth, pub["api"]
    return api


def _get_draft(client: Client, pub: dict, draft_id) -> dict:
    draft = client.get(f"{pub['api']}/drafts/{int(draft_id)}")
    if not isinstance(draft, dict) or not draft.get("id"):
        raise Failure("not_found", f"no draft {draft_id} in {pub['subdomain']}")
    return draft


def _check_state(action: str, brief: dict) -> None:
    if action in ("update_draft", "publish", "schedule") and brief["published"]:
        raise Failure("invalid", f"draft {brief['id']} is already published")
    if action in ("publish", "schedule") and (not brief["title"].strip() or not brief["words"]):
        raise Failure("invalid", f"draft {brief['id']} has no title or no text; finish it before releasing it")
    if action == "publish" and brief["scheduled"]:
        raise Failure("invalid", f"draft {brief['id']} is scheduled; unschedule it before publishing it now")
    if action == "unschedule" and not brief["scheduled"]:
        raise Failure("invalid", f"draft {brief['id']} is not scheduled")


def op_prepare(client: Client, req: dict):
    """What an approval card needs: the account or publication, the draft as it is now (and its
    digest), the email audience of a release, and the Markdown's local images."""
    action = req["action"]
    out = {}
    if req.get("markdown") is not None:
        out["images"] = scan_images(req["markdown"])
    if action == "note":
        me = profile(client)
        out["account"] = {"id": me.get("id"), "handle": me.get("handle"), "name": me.get("name")}
        return out
    pub = own_publication(client, req.get("publication"))
    out["publication"] = pub
    if action in DRAFT_BOUND:
        draft = _get_draft(client, pub, req["draft"])
        brief = draft_brief(draft)
        _check_state(action, brief)
        out["draft"], out["digest"] = brief, draft_digest(draft)
        if action == "update_draft" and req.get("markdown") is not None:
            api = api_for(client, pub)
            api.get_image = _Recorder().get_image
            try:
                result = api.update_draft_from_markdown(
                    int(req["draft"]), req["markdown"], dry_run=True, allow_image_replacement=True,
                    allow_unsupported_change=bool(req.get("replace_unsupported")))
            except ValueError as exc:
                raise Failure("invalid", f"{exc} (replace_unsupported=true drops those blocks)") from exc
            out["unsupported"] = len(result.get("unsupported_nodes") or [])
    if action in ("publish", "schedule"):
        summary = client.get(f"{pub['api']}/publish-dashboard/summary")
        out["email_subscribers"] = summary.get("totalEmail") if isinstance(summary, dict) else None
    return out


class Ledger:
    """A file the engine reads when this process dies: how far a write got."""

    def __init__(self, path: str | None):
        self.path = Path(path) if path else None
        self.done: list[str] = []

    def mark(self, status: str, step: str) -> None:
        if status == "done":
            self.done.append(step)
        if not self.path:
            return
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text(json.dumps({"status": status, "step": step, "done": self.done}), encoding="utf-8")
        os.replace(tmp, self.path)


def _api_error(exc) -> tuple[int | None, str]:
    code = getattr(exc, "status_code", None)
    return code, mask(getattr(exc, "message", None) or str(exc))[:300]


def dispatch(client: Client, ledger: Ledger, step: str, call):
    """One step that changes the account: refused by Substack (nothing changed), done, or uncertain."""
    from substack.exceptions import SubstackAPIException, SubstackRequestException
    ledger.mark("dispatching", step)
    try:
        result = call()
    except SubstackAPIException as exc:
        code, message = _api_error(exc)
        if code == 429:
            ledger.mark("rejected", step)
            raise Failure("limited", f"Substack is rate-limiting this account ({step})",
                          retry_after=DEFAULT_RETRY_AFTER) from exc
        if code is not None and 400 <= code < 500:
            ledger.mark("rejected", step)
            raise Failure("rejected", f"Substack refused to {step} ({code}: {message})") from exc
        raise Uncertain(f"Substack answered {code} to '{step}'") from exc
    except SubstackRequestException as exc:  # a 2xx without JSON: it was accepted
        ledger.mark("done", step)
        return {}
    except Failure:  # raised by the guarded session before sending (a refused host or the deadline)
        ledger.mark("rejected", step)
        raise
    except client.requests.RequestException as exc:
        raise Uncertain(f"the connection broke during '{step}' ({type(exc).__name__})") from exc
    except Exception as exc:  # an answer the library could not read: it may have been applied
        raise Uncertain(f"Substack's answer to '{step}' could not be read ({type(exc).__name__})") from exc
    ledger.mark("done", step)
    return result


def _guard_uploads(client: Client, api, images: dict[str, str], ledger: Ledger) -> list[str]:
    """Let python-substack upload only the frozen copy of each image the card listed, each upload
    in the ledger as a step of its own."""
    from substack import Api
    uploaded: list[str] = []

    def get_image(path):
        staged = images.get(str(path))
        if not staged:
            raise Failure("invalid", f"the image {Path(str(path)).name} was not on the approval card")
        result = dispatch(client, ledger, f"upload image {Path(str(path)).name}", lambda: Api.get_image(api, staged))
        uploaded.append(str(path))
        return result

    api.get_image = get_image
    return uploaded


def _cause(exc: BaseException) -> str:
    parts = []
    while exc is not None and len(parts) < 3:
        parts.append(str(exc))
        exc = exc.__cause__
    return mask("; ".join(p for p in parts if p))[:400]


def note_body(text: str) -> dict:
    """Plain text -> the ProseMirror document of a Note: one paragraph per line, links marked."""
    paragraphs = []
    for line in text.splitlines():
        if not line.strip():
            continue
        nodes, last = [], 0
        for match in NOTE_URL.finditer(line):
            if match.start() > last:
                nodes.append({"type": "text", "text": line[last:match.start()]})
            nodes.append({"type": "text", "text": match.group(),
                          "marks": [{"type": "link", "attrs": {"href": match.group()}}]})
            last = match.end()
        if last < len(line):
            nodes.append({"type": "text", "text": line[last:]})
        paragraphs.append({"type": "paragraph", "content": nodes})
    return {"type": "doc", "attrs": {"schemaVersion": "v1"}, "content": paragraphs}


def _json_or_empty(response) -> dict:
    try:
        data = response.json()
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _post_note(client: Client, text: str) -> dict:
    from substack.exceptions import SubstackAPIException
    payload = {"bodyJson": note_body(text), "tabId": "for-you", "surface": "feed", "replyMinimumRole": "everyone"}
    response = client.auth.post(f"{ROOT}/comment/feed/", json=payload)
    if not 200 <= response.status_code < 300:
        raise SubstackAPIException(response.status_code, response.text[:2000])
    return _json_or_empty(response)


def _read_back(client: Client, pub: dict | None, action: str, plan: dict, started: str) -> str:
    """One look after an uncertain step, as a hint; never a conclusion."""
    try:
        if action == "create_draft" and pub:
            data = client.get(f"{pub['api']}/drafts", {"filter": "draft", "offset": 0, "limit": 10})
            posts = data.get("posts") if isinstance(data, dict) else data
            for d in posts or []:
                if (d.get("draft_title") or "") == plan["title"] and str(d.get("draft_created_at") or "") >= started:
                    return f"a draft with this title now exists (id {d.get('id')}): it was probably created"
            return "no new draft with this title is listed yet"
        if action in ("publish", "schedule", "unschedule") and pub:
            brief = draft_brief(_get_draft(client, pub, plan["draft"]))
            if action == "publish":
                return "the draft now shows as published" if brief["published"] else "the draft still shows as unpublished"
            return f"the draft's scheduled releases now: {brief['scheduled'] or 'none'}"
    except Exception:  # noqa: BLE001 - a hint only
        return "a look afterwards failed too"
    return "there is no way to look it up from here"


def op_write(client: Client, req: dict):
    """The approved write, on the account and publication the card named (both checked again)."""
    action, plan = req["action"], req["plan"]
    ledger = Ledger(req.get("ledger"))
    started = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
    pub = None
    try:
        if action == "note":
            me = profile(client)
            if str(me.get("id")) != str(req.get("expect_user")):
                raise Failure("changed", "the signed-in account is not the one the approval card named")
            note = dispatch(client, ledger, "post the Note", lambda: _post_note(client, plan["text"]))
            nid = note.get("id")
            return {"note": {"id": nid, "url": f"https://substack.com/@{me.get('handle')}/note/c-{nid}" if nid else None}}
        pub = own_publication(client, req.get("publication"))
        if str(pub.get("id")) != str(req.get("expect_publication")) or str(pub.get("user_id")) != str(req.get("expect_user")):
            raise Failure("changed", "the account or publication is not the one the approval card named")
        api = api_for(client, pub)
        draft = None
        if action in DRAFT_BOUND:
            draft = _get_draft(client, pub, plan["draft"])
            if draft_digest(draft) != req.get("expect"):
                raise Failure("changed", f"draft {plan['draft']} changed after the approval card was shown")
            _check_state(action, draft_brief(draft))
        uploaded = _guard_uploads(client, api, req.get("images") or {}, ledger)
        try:
            return _write_steps(client, api, pub, action, plan, draft, ledger, uploaded)
        except (ValueError, OSError) as exc:  # the library refused, or an upload failed (the ledger says which)
            raise Failure("invalid", _cause(exc)) from exc
    except Uncertain as exc:
        return {"uncertain": str(exc), "hint": _read_back(client, pub, action, plan, started), "done": ledger.done}


def _write_steps(client, api, pub, action, plan, draft, ledger, uploaded):
    from substack.post import Post
    draft_id = int(plan["draft"]) if plan.get("draft") else None
    if action == "create_draft":
        post = Post(title=plan["title"], subtitle=plan.get("subtitle") or "", user_id=pub["user_id"],
                    audience=plan["audience"], write_comment_permissions="everyone")
        post.from_markdown(plan["markdown"], api=api)
        body = post.get_draft()
        created = dispatch(client, ledger, "create the draft", lambda: api.post_draft(body))
        return {"draft": draft_brief(created) | {"id": created.get("id")}, "images": len(uploaded)}
    if action == "update_draft":
        payload = {}
        if plan.get("markdown") is not None:
            result = api.update_draft_from_markdown(
                draft_id, plan["markdown"], dry_run=True, allow_image_replacement=True,
                allow_unsupported_change=bool(plan.get("replace_unsupported")))
            payload = dict(result.get("payload") or {})
            payload.pop("subtitle", None)
        for key, field in (("title", "draft_title"), ("subtitle", "draft_subtitle"), ("audience", "audience")):
            if plan.get(key) is not None:
                payload[field] = plan[key]
        updated = dispatch(client, ledger, "save the draft", lambda: api.put_draft(draft_id, **payload))
        return {"draft": draft_brief(updated if updated.get("id") else draft), "images": len(uploaded)}
    if action == "publish":
        try:
            checks = api.prepublish_draft(draft_id)
        except Exception as exc:  # noqa: BLE001 - nothing was published
            raise Failure("rejected", f"the pre-publish check failed: {_cause(exc)}") from exc
        published = dispatch(client, ledger, "publish the draft",
                             lambda: api.publish_draft(draft_id, send=plan["send_email"], share_automatically=False))
        slug = published.get("slug")
        return {"post": {"id": published.get("id") or draft_id, "slug": slug,
                         "url": published.get("canonical_url") or (f"{pub['url']}/p/{slug}" if slug else None)},
                "emailed": plan["send_email"], "checks": checks}
    if action == "schedule":
        from datetime import datetime
        if bool(draft.get("should_send_email")) != plan["send_email"]:
            dispatch(client, ledger, "set whether the release is emailed",
                     lambda: api.put_draft(draft_id, should_send_email=plan["send_email"]))
        when = datetime.fromisoformat(plan["at"])
        dispatch(client, ledger, "schedule the release", lambda: api.schedule_draft(draft_id, when))
        try:  # a look afterwards, for the reply only: the release is scheduled either way
            after = draft_brief(_get_draft(client, pub, draft_id))
        except Exception:  # noqa: BLE001
            after = {"id": draft_id, "title": draft.get("draft_title") or ""}
        return {"draft": after, "emailed": plan["send_email"]}
    if action == "unschedule":
        dispatch(client, ledger, "cancel the scheduled release", lambda: api.unschedule_draft(draft_id))
        return {"draft": {"id": draft_id, "title": draft.get("draft_title") or ""}}
    raise Failure("invalid", f"unknown write {action!r}")


OPS = {"archive": op_archive, "post": op_post, "inbox": op_inbox, "published": op_published,
       "drafts": op_drafts, "draft": op_draft, "stats": op_stats, "prepublish": op_prepublish,
       "prepare": op_prepare, "write": op_write}


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
