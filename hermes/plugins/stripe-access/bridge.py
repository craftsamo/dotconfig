"""stripe-access bridge: the only process that holds a Stripe API key, for one call.

The engine (``sta.py``) runs this file with Hermes' own interpreter in isolated mode, a minimal
environment and the state directory as working directory, writes one JSON request to stdin and
reads one JSON reply from stdout.

Keys live in the Keychain (project ``hermes``, scope ``stripe-access``, a scope no Hermes profile
receives), one per account label and mode: ``STRIPE_KEY_<LABEL>_LIVE`` and ``STRIPE_KEY_<LABEL>_TEST``.
A key is read when a call needs it and lives only in this short-lived process; it is masked in every
string that leaves. The key's own prefix must agree with the mode asked for, so a test call never
runs on a live key and the other way round. Only the endpoints in ``ROUTES`` exist here, only
api.stripe.com is contacted, never through a redirect, and the API version is pinned.
Contract: docs/stripe-access.md.

    {"op": "keys"}   the stored labels, modes and key kinds; never a value, never a request to Stripe
    {"op": "key", "account": label | null, "mode": "live" | "test"}
                     the label a call would run on and its key's kind and fingerprint; no request to Stripe
    {"op": "call", "account": label | null, "mode": "live" | "test", "method": "GET" | "POST" | "DELETE",
     "path": "/v1/...", "params": [[key, value], ...], "idempotency_key": str | null,
     "refused": {"<label>/<mode>": fingerprint}, "paused": {"<label>/<mode>": epoch seconds},
     "expect": fingerprint | null, "deadline": seconds}
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

SECRET = Path.home() / ".config" / "bin" / "secret"
PROJECT, SCOPE = "hermes", "stripe-access"
PREFIX = "STRIPE_KEY_"
MODES = ("live", "test")
SECRET_TIMEOUT = 20
BASE = "https://api.stripe.com"
VERSION = "2026-09-30.endive"
UA = "hermes-stripe-access/1.0"

LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9_]{0,22}[a-z0-9])?$")
ITEM = re.compile(r"^STRIPE_KEY_([A-Z0-9](?:[A-Z0-9_]{0,22}[A-Z0-9])?)_(LIVE|TEST)$")
KEY = re.compile(r"^(sk|rk)_(live|test)_[A-Za-z0-9]{10,247}$")
KEY_SHAPE = re.compile(r"\b(?:sk|rk|pk)_(?:live|test)_[A-Za-z0-9*]+")
PARAM = re.compile(r"^[a-z_]+(?:\[[^\[\]\x00-\x1f]{0,64}\])*$")
PARAM_VALUE_MAX = 10000
PARAMS_MAX = 400
SEGMENT = r"[A-Za-z0-9_-]{1,255}"

# Every endpoint this bridge will call, as (method, path pattern); {id} is one path segment.
ROUTES = (
    ("GET", "/v1/account"),
    ("GET", "/v1/balance"),
    ("GET", "/v1/balance_transactions"),
    ("GET", "/v1/balance_transactions/{id}"),
    ("GET", "/v1/payment_intents"),
    ("GET", "/v1/payment_intents/search"),
    ("GET", "/v1/payment_intents/{id}"),
    ("GET", "/v1/customers"),
    ("GET", "/v1/customers/search"),
    ("GET", "/v1/customers/{id}"),
    ("GET", "/v1/subscriptions"),
    ("GET", "/v1/subscriptions/search"),
    ("GET", "/v1/subscriptions/{id}"),
    ("GET", "/v1/invoices"),
    ("GET", "/v1/invoices/search"),
    ("GET", "/v1/invoices/{id}"),
    ("GET", "/v1/products"),
    ("GET", "/v1/products/search"),
    ("GET", "/v1/products/{id}"),
    ("GET", "/v1/prices"),
    ("GET", "/v1/prices/search"),
    ("GET", "/v1/prices/{id}"),
    ("GET", "/v1/payment_links"),
    ("GET", "/v1/payment_links/{id}"),
    ("GET", "/v1/payment_links/{id}/line_items"),
    ("GET", "/v1/refunds"),
    ("GET", "/v1/refunds/{id}"),
    ("GET", "/v1/coupons"),
    ("GET", "/v1/coupons/{id}"),
    ("GET", "/v1/promotion_codes"),
    ("GET", "/v1/promotion_codes/{id}"),
    ("GET", "/v1/charges/{id}"),
    # writes: each runs only after its approval card, with an idempotency key
    ("POST", "/v1/customers"),
    ("POST", "/v1/customers/{id}"),
    ("POST", "/v1/products"),
    ("POST", "/v1/products/{id}"),
    ("POST", "/v1/prices"),
    ("POST", "/v1/prices/{id}"),
    ("POST", "/v1/coupons"),
    ("POST", "/v1/coupons/{id}"),
    ("DELETE", "/v1/coupons/{id}"),
    ("POST", "/v1/promotion_codes"),
    ("POST", "/v1/promotion_codes/{id}"),
    ("POST", "/v1/invoices"),
    ("POST", "/v1/invoiceitems"),
    ("POST", "/v1/invoices/{id}/finalize"),
    ("POST", "/v1/invoices/{id}/send"),
    ("POST", "/v1/invoices/{id}/void"),
    ("POST", "/v1/payment_links"),
    ("POST", "/v1/payment_links/{id}"),
    ("POST", "/v1/refunds"),
    ("POST", "/v1/subscriptions/{id}"),
    ("DELETE", "/v1/subscriptions/{id}"),
)
_ROUTES = tuple((method, re.compile("^" + re.escape(path).replace(r"\{id\}", SEGMENT) + "$")) for method, path in ROUTES)

SECRETS: list[str] = []


class Setup(Exception):
    pass


class Failure(Exception):
    def __init__(self, message: str, kind: str = "error", status: int | None = None, **detail):
        super().__init__(message)
        self.kind, self.status, self.detail = kind, status, detail


def mask(text) -> str:
    """The text without any key value this process read, or anything shaped like a Stripe key."""
    text = str(text)
    for value in SECRETS:
        if value:
            text = text.replace(value, "…")
    return KEY_SHAPE.sub("…", text)


def fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:12]


def item_name(label: str, mode: str) -> str:
    return f"{PREFIX}{label.upper()}_{mode.upper()}"


def set_command(label: str, mode: str) -> str:
    return f"secret set {item_name(label, mode)} -p {PROJECT} --scope {SCOPE} -D TOKEN --no-env"


def _secret(*argv: str) -> subprocess.CompletedProcess:
    if not SECRET.exists():
        raise Setup(f"the secret CLI is missing at {SECRET}")
    try:
        return subprocess.run([str(SECRET), *argv], stdin=subprocess.DEVNULL, capture_output=True, text=True,
                              timeout=SECRET_TIMEOUT)
    except subprocess.TimeoutExpired as exc:
        raise Setup("reading the Keychain timed out") from exc


def stored() -> list[tuple[str, str]]:
    """(label, mode) of every key item in the scope, from the Keychain's metadata (no value is read)."""
    proc = _secret("ls", "-p", PROJECT, "--json")
    if proc.returncode != 0:
        raise Setup(f"could not list the Keychain items of project {PROJECT}")
    try:
        items = json.loads(proc.stdout or "[]")
    except ValueError as exc:
        raise Setup("the Keychain listing was not readable") from exc
    found = set()
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict) or item.get("scope") != SCOPE or item.get("stage"):
            continue
        match = ITEM.fullmatch(str(item.get("name") or ""))
        if match:
            found.add((match.group(1).lower(), match.group(2).lower()))
    return sorted(found)


def read_key(label: str, mode: str) -> tuple[str, str]:
    """(key, kind) for one label and mode; raises Setup with the fix."""
    name = item_name(label, mode)
    proc = _secret("get", name, "-p", PROJECT, "--scope", SCOPE)
    value = proc.stdout.strip()
    if proc.returncode != 0 or not value:
        raise Setup(f"no {mode} key for account {label} in the Keychain ({name}, project {PROJECT}, scope "
                    f"{SCOPE}); the user stores it with `{set_command(label, mode)}`")
    SECRETS.append(value)
    match = KEY.fullmatch(value)
    if not match:
        raise Setup(f"{name} is not a Stripe secret or restricted key (sk_… / rk_…); a publishable key (pk_…) "
                    "cannot read or change anything")
    if match.group(2) != mode:
        raise Setup(f"{name} holds a {match.group(2)} key, not a {mode} one; nothing was sent. Store the "
                    f"{mode} key there (`{set_command(label, mode)}`)")
    return value, "restricted" if match.group(1) == "rk" else "secret"


def resolve(account, mode: str) -> str:
    """The account label a call runs on: the one named, or the only one stored for the mode."""
    if account is not None:
        if not isinstance(account, str) or not LABEL.fullmatch(account):
            raise Setup("account must be a label like work (lowercase letters, digits and _)")
        return account
    labels = [label for label, m in stored() if m == mode]
    if len(labels) == 1:
        return labels[0]
    if not labels:
        raise Setup(f"no {mode} key is stored; the user stores one with `{set_command('<label>', mode)}`")
    raise Setup(f"account is required: {mode} keys are stored for " + ", ".join(labels))


def keys() -> list[dict]:
    """Each stored key's label, mode, kind and fingerprint, read from the Keychain."""
    result = []
    for label, mode in stored():
        entry = {"account": label, "mode": mode}
        try:
            value, kind = read_key(label, mode)
            entry.update(kind=kind, fingerprint=fingerprint(value))
        except Setup as exc:
            entry["problem"] = mask(exc)[:300]
        result.append(entry)
    return result


def route(method: str, path: str) -> None:
    if not any(m == method and pattern.fullmatch(path) for m, pattern in _ROUTES):
        raise Failure(f"{method} {path} is not an endpoint this tool calls", "error")


def encode(params) -> str:
    if params is None:
        return ""
    if not isinstance(params, list) or len(params) > PARAMS_MAX:
        raise Failure("params must be a list of [key, value] pairs")
    pairs = []
    for pair in params:
        if not (isinstance(pair, list) and len(pair) == 2 and isinstance(pair[0], str) and isinstance(pair[1], str)):
            raise Failure("params must be a list of [key, value] string pairs")
        key, value = pair
        if not PARAM.fullmatch(key) or len(value) > PARAM_VALUE_MAX:
            raise Failure(f"parameter {key[:80]!r} is not one Stripe takes")
        pairs.append((key, value))
    return urllib.parse.urlencode(pairs)


class _StripeOnly(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise Failure(f"Stripe answered with a redirect ({code}); not followed", "error", code)


_OPENER = urllib.request.build_opener(_StripeOnly)


def _error(data) -> dict:
    error = data.get("error") if isinstance(data, dict) else None
    if not isinstance(error, dict):
        return {}
    return {k: str(error[k])[:400] for k in ("type", "code", "decline_code", "param", "message") if error.get(k)}


KINDS = {400: "invalid", 401: "refused", 402: "invalid", 403: "forbidden", 404: "not_found", 409: "conflict",
         429: "limited"}


def prepare(key: str, method: str, path: str, params, idempotency_key) -> urllib.request.Request:
    """The request, checked against ROUTES and Stripe's parameter shape; nothing is sent here."""
    if not isinstance(method, str) or not isinstance(path, str):
        raise Failure("method and path are required")
    route(method, path)
    query = encode(params)
    headers = {"Authorization": f"Bearer {key}", "Stripe-Version": VERSION, "User-Agent": UA,
               "Accept": "application/json"}
    body = None
    url = BASE + path
    if method == "POST":
        body = query.encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        if not isinstance(idempotency_key, str) or not re.fullmatch(r"[A-Za-z0-9_-]{16,255}", idempotency_key):
            raise Failure("a write needs its idempotency key")
        headers["Idempotency-Key"] = idempotency_key
    elif query:
        url += "?" + query
    return urllib.request.Request(url, data=body, headers=headers, method=method)


def send(req: urllib.request.Request, deadline: float) -> tuple[int, dict, dict]:
    """(status, parsed reply, response facts) of one request; raises Failure for anything but 2xx."""
    left = deadline - time.monotonic()
    if left <= 1:
        raise Failure("Stripe did not answer in time", "timeout")
    try:
        with _OPENER.open(req, timeout=min(left, 60)) as reply:
            status, raw, head = reply.status, reply.read(), reply.headers
    except urllib.error.HTTPError as exc:
        status, head = exc.code, exc.headers
        try:
            raw = exc.read()
        except (OSError, http.client.HTTPException):
            raw = b""
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        kind = "timeout" if isinstance(reason, TimeoutError) else "network"
        raise Failure(f"could not reach Stripe: {reason}", kind) from exc
    except TimeoutError as exc:
        raise Failure("Stripe stopped answering", "timeout") from exc
    except (OSError, http.client.HTTPException) as exc:  # reset, incomplete read: a write may have landed
        raise Failure(f"the connection to Stripe broke off ({type(exc).__name__})", "network") from exc
    facts = {"request_id": (head.get("Request-Id") if head else None) or None,
             "should_retry": (head.get("Stripe-Should-Retry") if head else None) or None,
             "replayed": ((head.get("Idempotent-Replayed") if head else None) or "").lower() == "true"}
    try:
        data = json.loads(raw or b"null")
    except ValueError:
        data = None
    if 200 <= status < 300:
        if not isinstance(data, dict):
            raise Failure(f"Stripe answered {status} without a readable reply", "uncertain", status, **facts)
        return status, data, facts
    detail = _error(data)
    kind = "idempotency" if detail.get("type") == "idempotency_error" else KINDS.get(status, "api" if status >= 500
                                                                                       else "http")
    message = detail.pop("message", None) or f"Stripe answered {status}"
    raise Failure(message, kind, status, **detail, **facts)


def call(req: dict) -> dict:
    mode = req.get("mode")
    if mode not in MODES:
        raise Setup("mode must be live or test")
    label = resolve(req.get("account"), mode)
    reply = {"account": label, "mode": mode, "requests": 0}
    key, kind = read_key(label, mode)
    reply.update(fingerprint=fingerprint(key), key_kind=kind)
    slot = f"{label}/{mode}"
    if (req.get("refused") or {}).get(slot) == reply["fingerprint"]:
        return {**reply, "ok": False, "kind": "refused"}
    until = (req.get("paused") or {}).get(slot)
    if isinstance(until, (int, float)) and until > time.time():
        return {**reply, "ok": False, "kind": "limited", "until": until}
    if req.get("expect") and req["expect"] != reply["fingerprint"]:
        return {**reply, "ok": False, "kind": "account",
                "error": "the stored key changed since the approval card was made; nothing was sent"}
    try:
        prepared = prepare(key, req.get("method"), req.get("path"), req.get("params"), req.get("idempotency_key"))
    except Failure as exc:
        return {**reply, "ok": False, "kind": "error", "error": mask(exc)[:400]}
    deadline = time.monotonic() + float(req.get("deadline", 60))
    reply["requests"] = 1
    try:
        status, data, facts = send(prepared, deadline)
    except Failure as exc:
        return {**reply, "ok": False, "kind": exc.kind, "status": exc.status, "error": mask(exc)[:400],
                **{k: mask(v)[:400] if isinstance(v, str) else v for k, v in exc.detail.items() if v not in (None, "")}}
    except Exception as exc:  # after the request left: whether it landed is unknown, so it counts as sent
        return {**reply, "ok": False, "kind": "error", "error": mask(f"{type(exc).__name__}: {exc}")[:400]}
    return {**reply, "ok": True, "status": status, "data": data,
            **{k: v for k, v in facts.items() if v not in (None, "", False)}}


def key(req: dict) -> dict:
    mode = req.get("mode")
    if mode not in MODES:
        raise Setup("mode must be live or test")
    label = resolve(req.get("account"), mode)
    value, kind = read_key(label, mode)
    return {"ok": True, "account": label, "mode": mode, "fingerprint": fingerprint(value), "key_kind": kind,
            "requests": 0}


def main(req: dict) -> dict:
    op = req.get("op")
    try:
        if op == "keys":
            return {"ok": True, "data": keys(), "requests": 0}
        if op == "key":
            return key(req)
        if op == "call":
            return call(req)
        return {"ok": False, "kind": "error", "error": f"unknown op {op!r}", "requests": 0}
    except Setup as exc:
        return {"ok": False, "kind": "setup", "error": mask(exc)[:500], "requests": 0}
    except Failure as exc:
        return {"ok": False, "kind": exc.kind, "error": mask(exc)[:400], "requests": 0}
    except Exception as exc:  # unexpected: reported without a traceback, the key masked
        return {"ok": False, "kind": "error", "error": mask(f"{type(exc).__name__}: {exc}")[:400], "requests": 0}


if __name__ == "__main__":
    try:
        request_ = json.loads(sys.stdin.read())
        if not isinstance(request_, dict):
            raise ValueError("the request must be a JSON object")
        result = main(request_)
    except Exception as exc:  # reported to the engine, never a traceback on stdout
        result = {"ok": False, "kind": "error", "error": mask(f"{type(exc).__name__}: {exc}")[:500], "requests": 0}
    sys.stdout.write(mask(json.dumps(result, ensure_ascii=False, default=str)))
