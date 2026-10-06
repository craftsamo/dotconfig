"""note-access bridge: the only process that holds the note session, for one signed-in call.

The engine (``na.py``) runs this file with Hermes' own interpreter in isolated mode, a minimal
environment and the state directory as working directory, writes one JSON request to stdin and
reads one JSON reply from stdout. Public reads never come here: they go out from the engine
without any cookie.

The session cookie (``_note_session_v5`` of the user's main account) is read from the Keychain at
start (``secret get NOTE_SESSION -p hermes --scope note-session``, a scope no Hermes profile
receives) and lives only in this short-lived process; it is masked in every string that leaves,
and the account's e-mail address is removed from every reply. Only a fixed set of operations on
note.com exists here — reads of the user's own drafts and stats, creating and saving a draft,
asking for an image upload slot and setting a cover image. Nothing publishes, deletes, likes,
follows or comments. Contract: docs/note-access.md.

    {"op": "check" | "me" | "drafts" | "draft" | "stats" | "create" | "save" | "presign" | "eyecatch",
     "deadline": seconds, "refused": <fingerprint the engine saw refused, or null>, ...op arguments}
"""

from __future__ import annotations

import hashlib
import http.client
import json
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

SECRET = Path.home() / ".config" / "bin" / "secret"
COOKIE_NAME, COOKIE_PROJECT, COOKIE_SCOPE = "NOTE_SESSION", "hermes", "note-session"
COOKIE_SET = f"secret set {COOKIE_NAME} -p {COOKIE_PROJECT} --scope {COOKIE_SCOPE} -D COOKIE"
SESSION = "_note_session_v5"
SECRET_TIMEOUT = 20
BASE = "https://note.com"
EDITOR = "https://editor.note.com"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/129.0.0.0 Safari/537.36")
OUTBOX = Path.home() / ".note-access" / "outbox"
EYECATCH_MAX = 10 * 1024 * 1024
COVER_BOX = (1280, 670)
IMAGE_MIME = {"image/jpeg", "image/png", "image/gif", "image/webp"}

KEY = re.compile(r"^n[0-9a-f]{6,20}$")
SECRETS: list[str] = []


class Setup(Exception):
    pass


class Refused(Exception):
    pass


class Failure(Exception):
    def __init__(self, message: str, kind: str = "error", status: int | None = None):
        super().__init__(message)
        self.kind, self.status = kind, status


EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def mask(text) -> str:
    """The text without the session value (applied to everything that leaves, content included)."""
    text = str(text)
    for value in SECRETS:
        if value:
            text = text.replace(value, "…")
    return text


def redact(text) -> str:
    """A diagnostic string without the session value or any e-mail address, before it is clipped.
    Never applied to note content: a draft that mentions an address must round-trip unchanged."""
    return EMAIL.sub("[e-mail]", mask(text))


def scrub(value):
    """The reply without the account's e-mail address (or any other e-mail field)."""
    if isinstance(value, dict):
        return {k: scrub(v) for k, v in value.items() if "email" not in k.lower()}
    if isinstance(value, list):
        return [scrub(v) for v in value]
    return value


def read_cookie() -> tuple[str, str]:
    """(Cookie header value, fingerprint); raises Setup with the fix."""
    if not SECRET.exists():
        raise Setup(f"the secret CLI is missing at {SECRET}")
    try:
        proc = subprocess.run([str(SECRET), "get", COOKIE_NAME, "-p", COOKIE_PROJECT, "--scope", COOKIE_SCOPE],
                              stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=SECRET_TIMEOUT)
    except subprocess.TimeoutExpired as exc:
        raise Setup("reading the note session from the Keychain timed out") from exc
    raw = proc.stdout.strip()
    if proc.returncode != 0 or not raw:
        raise Setup(f"no note session in the Keychain ({COOKIE_NAME}, project {COOKIE_PROJECT}, scope "
                    f"{COOKIE_SCOPE}); the user stores it with `{COOKIE_SET}`")
    value = raw.split("=", 1)[1].strip() if raw.startswith(SESSION + "=") else raw
    value = value.split(";", 1)[0].strip()
    if not re.fullmatch(r"[A-Za-z0-9%._~+/=-]{16,512}", value):
        raise Setup(f"{COOKIE_NAME} is not a {SESSION} value; store it as '{SESSION}=…'")
    SECRETS.extend([raw, value])
    return f"{SESSION}={value}", hashlib.sha256(value.encode()).hexdigest()[:12]


class Session:
    def __init__(self, cookie: str, deadline: float, gap: float = 0):
        self.cookie, self.deadline, self.requests, self.gap, self.last = cookie, deadline, 0, gap, None

    def _timeout(self) -> float:
        left = self.deadline - time.monotonic()
        if left <= 1:
            raise Failure("note did not answer in time", "timeout")
        return min(left, 60)

    def call(self, method: str, path: str, *, payload=None, form=None, body: bytes | None = None,
             content_type: str | None = None, write: bool = False):
        """(status, parsed JSON or None). Only note.com, never a redirect elsewhere."""
        headers = {"User-Agent": UA, "Accept": "application/json", "Cookie": self.cookie,
                   "X-Requested-With": "XMLHttpRequest"}
        if write:
            headers.update({"Origin": EDITOR, "Referer": EDITOR + "/"})
        if payload is not None:
            body, content_type = json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json"
        elif form is not None:
            body, content_type = urllib.parse.urlencode(form).encode(), "application/x-www-form-urlencoded"
        if content_type:
            headers["Content-Type"] = content_type
        request = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
        if self.last is not None and self.gap:  # the engine's pacing gap holds inside one operation too
            wait = self.gap - (time.monotonic() - self.last)
            if wait > 0:
                time.sleep(wait)
        self.requests += 1
        self.last = time.monotonic()
        try:
            with _OPENER.open(request, timeout=self._timeout()) as reply:
                status, raw = reply.status, reply.read()
        except urllib.error.HTTPError as exc:
            status = exc.code
            try:
                raw = exc.read()
            except (OSError, http.client.HTTPException):
                raw = b""
        except urllib.error.URLError as exc:
            raise Failure(f"could not reach note.com: {getattr(exc, 'reason', exc)}", "network") from exc
        except TimeoutError as exc:
            raise Failure("note stopped answering", "timeout") from exc
        except (OSError, http.client.HTTPException) as exc:  # reset, incomplete read: the request may have landed
            raise Failure(f"the connection to note broke off ({type(exc).__name__})", "network") from exc
        try:
            data = json.loads(raw or b"null")
        except ValueError:
            data = None
        if status == 401:
            raise Refused(_message(data) or "authentication failed")
        if isinstance(data, dict) and isinstance(data.get("error"), dict) and data["error"].get("code") == "auth":
            raise Refused(str(data["error"].get("message") or "not logged in"))
        return status, data


class _NoteOnly(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise Failure(f"note answered with a redirect ({code}); nothing more was sent", "error", code)


_OPENER = urllib.request.build_opener(_NoteOnly)


def _message(data) -> str:
    if isinstance(data, dict):
        for key in ("message", "error", "data"):
            value = data.get(key)
            if isinstance(value, str):
                return value
            if isinstance(value, dict) and isinstance(value.get("message"), str):
                return value["message"]
    return ""


def _ok(status: int, data, what: str):
    if 200 <= status < 300 and isinstance(data, dict) and isinstance(data.get("error"), dict):
        raise Failure(f"{what}: note refused it ({_message(data) or data['error'].get('code') or 'no reason'})",
                      "rejected", status)
    if 200 <= status < 300 and isinstance(data, dict):
        return data.get("data")
    if 200 <= status < 300:
        raise Failure(f"{what}: note answered {status} without a readable reply", "uncertain", status)
    if status == 404:
        raise Failure(f"{what}: not found", "not_found", status)
    if status == 403:
        raise Failure(f"{what}: note refused access (403)", "forbidden", status)
    if status == 429:
        raise Failure(f"{what}: note is rate-limiting this account (429)", "limited", status)
    detail = _message(data)
    raise Failure(f"{what}: note answered {status}" + (f" ({detail})" if detail else ""), "http", status)


def _key(value) -> str:
    if not isinstance(value, str) or not KEY.match(value):
        raise Failure("a note key looks like n0123456789ab")
    return value


def _int(value, name: str, low: int = 1, high: int = 10 ** 12) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise Failure(f"{name} must be an integer between {low} and {high}")
    return value


def _me(session: Session) -> dict:
    status, data = session.call("GET", "/api/v2/current_user")
    me = _ok(status, data, "current user")
    if not isinstance(me, dict) or not me.get("urlname"):
        raise Refused("note did not say who is signed in")
    return {"id": me.get("id"), "urlname": me.get("urlname"), "nickname": me.get("nickname")}


def _multipart(fields: list[tuple[str, str]], file_field: str, filename: str, data: bytes, mime: str):
    boundary = uuid.uuid4().hex
    parts = [f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode() for k, v in fields]
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'
                 f"Content-Type: {mime}\r\n\r\n".encode() + data + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def run(session: Session, req: dict):
    op = req["op"]
    if op == "me":
        return _me(session)
    if op == "drafts":
        page, limit = _int(req.get("page", 1), "page", 1, 1000), _int(req.get("limit", 20), "limit", 1, 50)
        me = _me(session)  # a stale session lists nothing rather than failing: ask who is signed in first
        status, data = session.call("GET", f"/api/v2/note_list/contents?limit={limit}&page={page}"
                                           "&status=draft&without_magazines=true")
        return {"me": me, "list": _ok(status, data, "drafts")}
    if op == "draft":
        key = _key(req.get("key"))
        status, data = session.call("GET", f"/api/v3/notes/{key}?draft=true&draft_reedit=false")
        return _ok(status, data, f"draft {key}")
    if op == "stats":
        period = req.get("period", "all")
        sort = req.get("sort", "pv")
        if period not in ("all", "daily", "weekly", "monthly", "yearly") or sort not in ("pv", "like", "comment"):
            raise Failure("period / sort is not one note offers")
        page = _int(req.get("page", 1), "page", 1, 1000)
        status, data = session.call("GET", f"/api/v1/stats/pv?filter={period}&page={page}&sort={sort}")
        return _ok(status, data, "stats")
    if op == "create":
        title = req.get("title")
        if not isinstance(title, str) or not title.strip():
            raise Failure("title is required")
        status, data = session.call("POST", "/api/v1/text_notes", write=True, payload={
            "body": "", "body_length": 0, "name": title, "index": False, "is_lead_form": False})
        created = _ok(status, data, "creating the draft")
        if not isinstance(created, dict) or not created.get("id") or not created.get("key"):
            raise Failure("note did not return the new draft's id", "uncertain")
        return {"id": created["id"], "key": created["key"]}
    if op == "save":
        note_id = _int(req.get("id"), "id")
        title, body = req.get("title"), req.get("body")
        if not isinstance(title, str) or not isinstance(body, str):
            raise Failure("title and body are required")
        status, data = session.call("POST", f"/api/v1/text_notes/draft_save?id={note_id}&is_temp_saved=true",
                                    write=True, payload={"name": title, "body": body,
                                                         "body_length": _int(req.get("length", 0), "length", 0),
                                                         "index": False, "is_lead_form": False})
        saved = _ok(status, data, "saving the draft")
        if not isinstance(saved, dict) or saved.get("result") is not True:
            raise Failure("note did not confirm the save", "uncertain")
        return {"updated_at": saved.get("updated_at")}
    if op == "presign":
        filename = req.get("filename")
        if not isinstance(filename, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,40}\.(?:jpg|png|gif|webp)", filename):
            raise Failure("filename must be a plain image file name")
        status, data = session.call("POST", "/api/v3/images/upload/presigned_post", write=True,
                                    form={"filename": filename})
        slot = _ok(status, data, "an image upload slot")
        if not isinstance(slot, dict) or not all(k in slot for k in ("action", "url", "post")):
            raise Failure("note's upload slot is missing fields")
        return {"action": slot["action"], "url": slot["url"], "post": slot["post"]}
    if op == "eyecatch":
        note_id = _int(req.get("id"), "id")
        path = Path(str(req.get("path") or ""))
        mime = req.get("mime")
        try:
            real = path.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise Failure("the staged cover image is gone") from exc
        if OUTBOX.resolve() not in real.parents or not real.is_file() or mime not in IMAGE_MIME:
            raise Failure("the cover image must be a staged copy in the tool's outbox")
        data = real.read_bytes()
        if not data or len(data) > EYECATCH_MAX:
            raise Failure("the cover image is empty or over 10 MB")
        ext = {"image/jpeg": "jpg", "image/png": "png", "image/gif": "gif", "image/webp": "webp"}[mime]
        # note's cover box is 1280:670 and it refuses any other ratio here; it fits the image to it
        fields = [("note_id", str(note_id)), ("width", str(COVER_BOX[0])), ("height", str(COVER_BOX[1]))]
        body, content_type = _multipart(fields, "file", f"cover.{ext}", data, mime)
        status, reply = session.call("POST", "/api/v1/image_upload/note_eyecatch", write=True, body=body,
                                     content_type=content_type)
        done = _ok(status, reply, "setting the cover image")
        if not isinstance(done, dict) or not done.get("url"):
            raise Failure("note did not confirm the cover image", "uncertain")
        return {"url": done["url"]}
    raise Failure(f"unknown op {op!r}")


def main(req: dict) -> dict:
    try:
        cookie, fingerprint = read_cookie()
    except Setup as exc:
        return {"ok": False, "kind": "setup", "error": str(exc), "requests": 0}
    if req.get("op") == "check":
        return {"ok": True, "data": None, "fingerprint": fingerprint, "requests": 0}
    if req.get("refused") and req["refused"] == fingerprint:
        return {"ok": False, "kind": "refused", "fingerprint": fingerprint, "requests": 0}
    if req.get("expect") and req["expect"] != fingerprint:
        return {"ok": False, "kind": "account", "fingerprint": fingerprint, "requests": 0,
                "error": "the stored note session changed since the approval card was made; nothing was sent"}
    session = Session(cookie, time.monotonic() + float(req.get("deadline", 60)), float(req.get("gap", 0)))
    reply = {"fingerprint": fingerprint}
    try:
        reply.update(ok=True, data=scrub(run(session, req)))
    except Refused as exc:
        reply.update(ok=False, kind="refused", error=redact(exc)[:200])
    except Failure as exc:
        reply.update(ok=False, kind=exc.kind, error=redact(exc)[:300], status=exc.status)
    except Exception as exc:  # unexpected: reported with the requests already made, never a traceback
        reply.update(ok=False, kind="error", error=redact(f"{type(exc).__name__}: {exc}")[:300])
    reply["requests"] = session.requests
    return reply


if __name__ == "__main__":
    try:
        request = json.loads(sys.stdin.read())
        if not isinstance(request, dict):
            raise ValueError("the request must be a JSON object")
        reply = main(request)
    except Exception as exc:  # reported to the engine, never a traceback on stdout
        reply = {"ok": False, "kind": "error", "error": redact(f"{type(exc).__name__}: {exc}")[:500], "requests": 1}
    sys.stdout.write(mask(json.dumps(reply, ensure_ascii=False, default=str)))
