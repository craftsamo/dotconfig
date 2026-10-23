"""stripe-access bridge: the only process that holds a Stripe API key, for one call.

The engine (``sta.py``) runs this file with Hermes' own interpreter in isolated mode, a minimal
environment and the state directory as working directory, writes one JSON request to stdin and
reads one JSON reply from stdout.

Keys live in the Keychain (project ``hermes``, scope ``stripe-access``, a scope no Hermes profile
receives). An item there is a key when it sits in the ``prod`` stage (live) or the ``test`` stage and
carries a ``label=<label>`` field naming its account; its name is the user's to choose. Each is read by
its exact layer, never a stage-less one or another stage, and a label held by two items in one stage is
refused rather than guessed. A key is read when a call needs it and lives only in this short-lived
process; it is masked in every string that leaves. The key's own prefix must agree with the mode asked
for, so a test call never runs on a live key and the other way round. Only the endpoints in ``ROUTES``
exist here, only api.stripe.com is contacted, never through a redirect, and the API version is pinned.
Contract: docs/stripe-access.md.

    {"op": "keys"}   the stored labels, modes, items and key kinds, and the scope's items that are no
                     key with why; never a value, never a request to Stripe
    {"op": "key", "account": label | null, "mode": "live" | "test"}
                     the label a call would run on, its item, and its key's kind and fingerprint; no
                     request to Stripe
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
MODES = ("live", "test")
STAGES = {"live": "prod", "test": "test"}   # the secret CLI's stage for each Stripe mode
SECRET_TIMEOUT = 20
BASE = "https://api.stripe.com"
VERSION = "2026-09-30.endive"
UA = "hermes-stripe-access/1.0"

LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9_]{0,22}[a-z0-9])?$")
# An item name as the secret CLI stores one, so it is never read as a flag or a "scope/NAME@stage" token.
NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
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


def set_command(label: str, mode: str) -> str:
    """How the user stores a key for a label; the name is only a suggestion, the label= field is what counts."""
    return (f"secret set STRIPE_{label.upper()} -p {PROJECT} --scope {SCOPE} --stage {STAGES[mode]} -D TOKEN "
            f"--meta label={label} --no-env")


def update_command(item: str, mode: str, change: str = "--value") -> str:
    """How the user changes one stored item in place (a fresh value by default, its fields kept)."""
    return f"secret update {item} -p {PROJECT} --scope {SCOPE} --stage {STAGES[mode]} {change}"


def _secret(*argv: str) -> subprocess.CompletedProcess:
    if not SECRET.exists():
        raise Setup(f"the secret CLI is missing at {SECRET}")
    try:
        return subprocess.run([str(SECRET), *argv], stdin=subprocess.DEVNULL, capture_output=True, text=True,
                              timeout=SECRET_TIMEOUT)
    except subprocess.TimeoutExpired as exc:
        raise Setup("reading the Keychain timed out") from exc


def _unusable(name: str, stage: str, meta: dict) -> str | None:
    """Why an item of the scope is no key, or None when it is one."""
    if not NAME.fullmatch(name):
        return ("its name is not one the secret CLI takes (letters, digits and _, not starting with a digit); "
                "store it again under such a name")
    modes = {s: m for m, s in STAGES.items()}
    if stage not in modes:
        where = f"stage {stage}" if stage else "no stage"
        return f"it is in {where}; only the prod (live) and test stages hold keys"
    fix = f"`{update_command(name, modes[stage], '--meta label=<label>')}`"
    label = meta.get("label", "")
    if not label:
        other = next((k for k in meta if k.lower() == "label"), None)
        if other:   # the field is matched by its exact spelling, so removing it is one exact command
            return (f"its field {other}= is not read: the field is label=, in lowercase; rename it with "
                    f"`{update_command(name, modes[stage], f'--meta {other}= --meta label=<label>')}`")
        return f"it has no label= field naming its account; give it one with {fix}"
    if not LABEL.fullmatch(label.lower()):
        return (f"label={label[:40]} is not a label (lowercase letters, digits and _, at most 24); fix it with "
                f"{fix}")
    return None


def inventory() -> tuple[dict, list]:
    """The scope's items, from the Keychain's metadata (no value is read): {(label, mode): [item names]} for
    the keys, and the items that are no key with what is wrong with each. The field is label= exactly; its
    value matches without regard to case."""
    proc = _secret("ls", "-p", PROJECT, "--json")
    if proc.returncode != 0:
        raise Setup(f"could not list the Keychain items of project {PROJECT}")
    try:
        items = json.loads(proc.stdout or "[]")
    except ValueError as exc:
        raise Setup("the Keychain listing was not readable") from exc
    modes = {stage: mode for mode, stage in STAGES.items()}
    found, unused = {}, []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict) or item.get("scope") != SCOPE:
            continue
        name, stage = str(item.get("name") or ""), str(item.get("stage") or "")
        raw = item.get("meta") if isinstance(item.get("meta"), dict) else {}
        meta = {str(k): str(v).strip() for k, v in raw.items()}
        problem = _unusable(name, stage, meta)
        if problem:
            unused.append({"item": name[:80], "stage": stage, "problem": mask(problem)[:300]})
            continue
        found.setdefault((meta["label"].lower(), modes[stage]), []).append(name)
    return {slot: sorted(names) for slot, names in found.items()}, unused


def _twice(label: str, mode: str, names: list) -> str:
    listed = ", ".join(names[:4]) + (" …" if len(names) > 4 else "")
    return (f"{len(names)} items in stage {STAGES[mode]} carry label={label} ({listed}); nothing was sent. Keep "
            f"one: take the field off the others (`{update_command(names[-1], mode, '--meta label=')}`)")


def read_key(label: str, mode: str, item: str) -> tuple[str, str]:
    """(key, kind) of one item, read from that stage's exact layer; raises Setup with the fix."""
    where = f"{item}@{STAGES[mode]} (label={label})"
    proc = _secret("get", item, "-p", PROJECT, "--scope", SCOPE, "--stage", STAGES[mode])
    value = proc.stdout.strip()
    if proc.returncode != 0 or not value:
        raise Setup(f"{where} could not be read from the Keychain (locked, or removed since it was listed); "
                    "nothing was sent")
    SECRETS.append(value)
    match = KEY.fullmatch(value)
    if not match:
        raise Setup(f"{where} is not a Stripe secret or restricted key (sk_… / rk_…); a publishable key (pk_…) "
                    f"cannot read or change anything. Store the key there (`{update_command(item, mode)}`)")
    if match.group(2) != mode:
        raise Setup(f"{where} holds a {match.group(2)} key, not a {mode} one; nothing was sent. Store the "
                    f"{mode} key there (`{update_command(item, mode)}`)")
    return value, "restricted" if match.group(1) == "rk" else "secret"


def resolve(account, mode: str) -> tuple[str, str]:
    """(label, item) a call runs on: the label named, or the only one stored for the mode, and its one item."""
    if account is not None and (not isinstance(account, str) or not LABEL.fullmatch(account)):
        raise Setup("account must be a label like work (lowercase letters, digits and _)")
    found, _ = inventory()
    if account is None:
        labels = sorted(label for label, m in found if m == mode)
        if not labels:
            raise Setup(f"no {mode} key is stored; the user stores one with `{set_command('<label>', mode)}`")
        if len(labels) > 1:
            raise Setup(f"account is required: {mode} keys are stored for " + ", ".join(labels))
        account = labels[0]
    names = found.get((account, mode))
    if not names:
        raise Setup(f"no {mode} key for account {account} in the Keychain (project {PROJECT}, scope {SCOPE}, "
                    f"stage {STAGES[mode]}, field label={account}); the user stores it with "
                    f"`{set_command(account, mode)}`")
    if len(names) > 1:
        raise Setup(_twice(account, mode, names))
    return account, names[0]


def keys() -> tuple[list, list]:
    """Each stored key's label, mode, item, kind and fingerprint, read from the Keychain, and the scope's
    items that are no key."""
    found, unused = inventory()
    result = []
    for (label, mode), names in sorted(found.items()):
        entry = {"account": label, "mode": mode}
        if len(names) > 1:
            entry["problem"] = mask(_twice(label, mode, names))[:300]
        else:
            entry["item"] = names[0]
            try:
                value, kind = read_key(label, mode, names[0])
                entry.update(kind=kind, fingerprint=fingerprint(value))
            except Setup as exc:
                entry["problem"] = mask(exc)[:300]
        result.append(entry)
    return result, unused


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
    label, item = resolve(req.get("account"), mode)
    reply = {"account": label, "mode": mode, "item": item, "requests": 0}
    key, kind = read_key(label, mode, item)
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
    label, item = resolve(req.get("account"), mode)
    value, kind = read_key(label, mode, item)
    return {"ok": True, "account": label, "mode": mode, "item": item, "fingerprint": fingerprint(value),
            "key_kind": kind, "requests": 0}


def main(req: dict) -> dict:
    op = req.get("op")
    try:
        if op == "keys":
            data, unused = keys()
            return {"ok": True, "data": data, "unused": unused, "requests": 0}
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
