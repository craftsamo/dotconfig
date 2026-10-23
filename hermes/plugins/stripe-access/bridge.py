"""stripe-access bridge: the only process that holds a Stripe API key, for one call.

The engine (``sta.py``) runs this file with Hermes' own interpreter in isolated mode, a minimal
environment and the state directory as working directory, writes one JSON request to stdin and
reads one JSON reply from stdout.

Keys live in the Keychain (project ``hermes``, scope ``stripe-access``, a scope no Hermes profile
receives), in the ``prod`` stage (live) or the ``test`` stage; an item's name is the user's to choose and
its fields say what it is:

    label=<label>              the account's own key (sk_… / rk_…)
    org=<org>                  an organization key (sk_org_…); each of its fields acct_<label>=acct_…
                               routes a label to that account, whose id goes out as Stripe-Context with
                               every request the label makes

A label with its own key uses it even when a route names it too. Each item is read by its exact layer,
never a stage-less one or another stage, and a label or organization two items carry in one stage is
refused rather than guessed. A key is read when a call needs it and lives only in this short-lived
process; it is masked in every string that leaves. The key's own prefix must agree with the mode asked
for, so a test call never runs on a live key and the other way round. A fingerprint names what a call
runs on: the key, and for a route the key with the account id, so a card made for one account never
runs on another. Only the endpoints in ``ROUTES`` exist here, only api.stripe.com is contacted, never
through a redirect, and the API version is pinned. Contract: docs/stripe-access.md.

    {"op": "keys"}   the stored labels and organization keys, their modes, items, kinds and routes, and
                     the scope's items that are no key with why; never a key, never a request to Stripe
    {"op": "key", "account": label | null, "mode": "live" | "test"}
                     the label a call would run on, its item and route, and its kind and fingerprint;
                     no request to Stripe
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
ORG_KEY = re.compile(r"^sk_org_(live|test)_[A-Za-z0-9]{10,247}$")
ACCOUNT_ID = re.compile(r"^acct_[A-Za-z0-9]{6,64}$")
ROUTE_FIELD = "acct_"   # acct_<label>=acct_… on an organization key's item
KEY_SHAPE = re.compile(r"\b(?:sk|rk|pk)_(?:live|test|org)_[A-Za-z0-9_*]+")
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
    """Why an item of the scope is none of a key, an organization key or a route; None when it is one."""
    if not NAME.fullmatch(name):
        return ("its name is not one the secret CLI takes (letters, digits and _, not starting with a digit); "
                "store it again under such a name")
    modes = {s: m for m, s in STAGES.items()}
    if stage not in modes:
        where = f"stage {stage}" if stage else "no stage"
        return f"it is in {where}; only the prod (live) and test stages hold keys"
    mode = modes[stage]
    for field in ("label", "org"):
        other = next((k for k in meta if k.lower() == field and k != field), None)
        if other and not meta.get(field):   # matched by its exact spelling, so removing it is one exact command
            return (f"its field {other}= is not read: the field is {field}=, in lowercase; rename it with "
                    f"`{update_command(name, mode, f'--meta {other}= --meta {field}=<{field}>')}`")
    if not meta.get("label") and not meta.get("org"):
        return (f"it has no label= field naming its account, nor org= naming an organization key; give it one "
                f"with `{update_command(name, mode, '--meta label=<label>')}`")
    if meta.get("label") and meta.get("org"):
        return ("it carries both label= (an account's own key) and org= (an organization key); an account reached "
                "through an organization is a field acct_<label>=acct_… on the organization key's item, so keep "
                f"one of the two (`{update_command(name, mode, '--meta org=')}` for an account's own key)")
    for field in ("label", "org"):
        value = meta.get(field, "")
        if value and not LABEL.fullmatch(value.lower()):
            return (f"{field}={value[:40]} is not a {field} name (lowercase letters, digits and _, at most 24); "
                    f"fix it with `{update_command(name, mode, f'--meta {field}=<{field}>')}`")
    return None


def _routes(name: str, mode: str, meta: dict) -> tuple[list, list]:
    """The acct_<label>=acct_… fields of an organization key's item: [(label, account id)], and the fields
    that route nothing with what is wrong with each."""
    routes, problems = [], []
    for field, value in sorted(meta.items()):
        if not field.lower().startswith(ROUTE_FIELD):
            continue
        label = field[len(ROUTE_FIELD):]
        fix = update_command(name, mode, f"--meta {field}= --meta {ROUTE_FIELD}<label>=acct_…")
        if not field.startswith(ROUTE_FIELD) or not LABEL.fullmatch(label):
            problems.append(f"its field {field[:40]}= routes no label: the field is {ROUTE_FIELD}<label>, the label "
                            f"in lowercase letters, digits and _ (`{fix}`)")
        elif not ACCOUNT_ID.fullmatch(value):
            problems.append(f"its field {field}= holds no account id (acct_…); store the "
                            f"{'sandbox ' if mode == 'test' else ''}account's id there (`{fix}`)")
        else:
            routes.append((label, value))
    return routes, problems


def inventory() -> tuple[dict, dict, list]:
    """The scope's items, from the Keychain's metadata (no value is read): {(label, mode): [entries]} for the
    accounts, each {"item"} for its own key or {"item", "org", "account_id"} for a route on an organization
    key's item; {(org, mode): [items]} for the organization keys; and what is no key or routes nothing, with
    what is wrong. Fields are spelled exactly; label and org values match without regard to case."""
    proc = _secret("ls", "-p", PROJECT, "--json")
    if proc.returncode != 0:
        raise Setup(f"could not list the Keychain items of project {PROJECT}")
    try:
        items = json.loads(proc.stdout or "[]")
    except ValueError as exc:
        raise Setup("the Keychain listing was not readable") from exc
    modes = {stage: mode for mode, stage in STAGES.items()}
    found, orgs, unused = {}, {}, []
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
        mode = modes[stage]
        label, org = meta.get("label", "").lower(), meta.get("org", "").lower()
        if label:
            found.setdefault((label, mode), []).append({"item": name})
            continue
        orgs.setdefault((org, mode), []).append(name)
        routes, problems = _routes(name, mode, meta)
        for routed, account_id in routes:
            found.setdefault((routed, mode), []).append({"item": name, "org": org, "account_id": account_id})
        unused += [{"item": name[:80], "stage": stage, "problem": mask(problem)[:300]} for problem in problems]
    return ({slot: sorted(entries, key=lambda e: e["item"]) for slot, entries in found.items()},
            {slot: sorted(names) for slot, names in orgs.items()}, unused)


def _twice(field: str, value: str, mode: str, names: list, clear: str | None = None) -> str:
    """`clear` is what to take off the others (by default the field itself)."""
    listed = ", ".join(names[:4]) + (" …" if len(names) > 4 else "")
    fix = update_command(names[-1], mode, clear or f"--meta {field}=")
    return (f"{len(names)} items in stage {STAGES[mode]} carry {field}={value} ({listed}); nothing was sent. "
            f"Keep one: take the fields off the others (`{fix}`)")


_READ: dict[tuple[str, str], str] = {}   # one read per item in this process: an organization key serves many


def _get(item: str, mode: str, where: str) -> str:
    """One item's value, read from that stage's exact layer; raises Setup with the fix."""
    if (item, mode) in _READ:
        return _READ[(item, mode)]
    proc = _secret("get", item, "-p", PROJECT, "--scope", SCOPE, "--stage", STAGES[mode])
    value = proc.stdout.strip()
    if proc.returncode != 0 or not value:
        raise Setup(f"{where} could not be read from the Keychain (locked, or removed since it was listed); "
                    "nothing was sent")
    _READ[(item, mode)] = value
    return value


def read_key(label: str, mode: str, item: str) -> tuple[str, str]:
    """(key, kind) of an account's own key; raises Setup with the fix."""
    where = f"{item}@{STAGES[mode]} (label={label})"
    value = _get(item, mode, where)
    SECRETS.append(value)
    match = KEY.fullmatch(value)
    if not match:
        raise Setup(f"{where} is not a Stripe secret or restricted key (sk_… / rk_…); a publishable key (pk_…) "
                    f"cannot read or change anything. Store the key there (`{update_command(item, mode)}`)")
    if match.group(2) != mode:
        raise Setup(f"{where} holds a {match.group(2)} key, not a {mode} one; nothing was sent. Store the "
                    f"{mode} key there (`{update_command(item, mode)}`)")
    return value, "restricted" if match.group(1) == "rk" else "secret"


def read_org_key(org: str, mode: str, item: str) -> str:
    """An organization key; its prefix must agree with the mode, as an account key's does."""
    where = f"{item}@{STAGES[mode]} (org={org})"
    value = _get(item, mode, where)
    SECRETS.append(value)
    match = ORG_KEY.fullmatch(value)
    if not match:
        raise Setup(f"{where} is not a Stripe organization key (sk_org_…); store the organization's key there "
                    f"(`{update_command(item, mode)}`)")
    if match.group(1) != mode:
        raise Setup(f"{where} holds a {match.group(1)} organization key, not a {mode} one; nothing was sent. "
                    f"Store the {mode} key there (`{update_command(item, mode)}`)")
    return value


def pick(label: str, mode: str, entries: list, orgs: dict) -> dict:
    """What a label runs on, from the listing: {"item", "org", "account_id", "also"}; its own key when it has
    one, else the one organization key whose item routes it."""
    own = [entry["item"] for entry in entries if not entry.get("org")]
    routed = [entry for entry in entries if entry.get("org")]
    if len(own) > 1:
        raise Setup(_twice("label", label, mode, own))
    if own:
        return {"item": own[0], "org": None, "account_id": None, "also": sorted({e["org"] for e in routed})}
    field = f"{ROUTE_FIELD}{label}"
    if len(routed) > 1:
        raise Setup(_twice(field, "…", mode, [e["item"] for e in routed]))
    route = routed[0]
    holders = orgs.get((route["org"], mode)) or []
    if len(holders) > 1:
        raise Setup(_twice("org", route["org"], mode, holders))
    return {"item": route["item"], "org": route["org"], "account_id": route["account_id"], "field": field,
            "also": []}


def credentials(label: str, mode: str, target: dict) -> dict:
    """The key, its kind, the Stripe-Context and the fingerprint of what a call runs on."""
    if target["org"] is None:
        key, kind = read_key(label, mode, target["item"])
        return {"key": key, "kind": kind, "context": None, "fingerprint": fingerprint(key)}
    key = read_org_key(target["org"], mode, target["item"])
    account_id = target["account_id"]
    return {"key": key, "kind": "organization", "context": account_id,
            "fingerprint": fingerprint(f"{key}|{account_id}")}


def resolve(account, mode: str) -> tuple[str, dict]:
    """(label, target) a call runs on: the label named, or the only one stored for the mode."""
    if account is not None and (not isinstance(account, str) or not LABEL.fullmatch(account)):
        raise Setup("account must be a label like work (lowercase letters, digits and _)")
    found, orgs, _ = inventory()
    if account is None:
        labels = sorted(label for label, m in found if m == mode)
        if not labels:
            raise Setup(f"no {mode} key is stored; the user stores one with `{set_command('<label>', mode)}`")
        if len(labels) > 1:
            raise Setup(f"account is required: {mode} keys are stored for " + ", ".join(labels))
        account = labels[0]
    entries = found.get((account, mode))
    if not entries:
        raise Setup(f"no {mode} key for account {account} in the Keychain (project {PROJECT}, scope {SCOPE}, "
                    f"stage {STAGES[mode]}, field label={account}); the user stores it with "
                    f"`{set_command(account, mode)}`")
    return account, pick(account, mode, entries, orgs)


def _route(target: dict) -> dict:
    """The reply fields that say what a call runs on."""
    fields = {"item": target["item"]}
    if target["org"]:   # item is then the organization key's, field the one on it that routes the label
        fields.update(org=target["org"], field=target["field"], stripe_account=target["account_id"])
    return fields


def keys() -> tuple[list, list, list]:
    """Each stored label's route, item, kind and fingerprint, each organization key's, and the scope's items
    that are none of these; read from the Keychain."""
    found, orgs, unused = inventory()
    result = []
    for (label, mode), entries in sorted(found.items()):
        entry = {"account": label, "mode": mode}
        try:
            target = pick(label, mode, entries, orgs)
            entry.update(_route(target))
            if target["also"]:
                entry["note"] = (f"also reached through organization {', '.join(target['also'])}; its own key is "
                                 "used")
            creds = credentials(label, mode, target)
            entry.update(kind=creds["kind"], fingerprint=creds["fingerprint"])
        except Setup as exc:
            entry["problem"] = mask(exc)[:300]
        result.append(entry)
    organizations = []
    for (org, mode), names in sorted(orgs.items()):
        entry = {"org": org, "mode": mode}
        if len(names) > 1:
            entry["problem"] = mask(_twice("org", org, mode, names))[:300]
        else:
            entry["item"] = names[0]
            try:
                entry.update(kind="organization", fingerprint=fingerprint(read_org_key(org, mode, names[0])))
            except Setup as exc:
                entry["problem"] = mask(exc)[:300]
        organizations.append(entry)
    return result, organizations, unused


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


def prepare(key: str, method: str, path: str, params, idempotency_key,
            context: str | None = None) -> urllib.request.Request:
    """The request, checked against ROUTES and Stripe's parameter shape; nothing is sent here. `context` is
    the account an organization key acts on."""
    if not isinstance(method, str) or not isinstance(path, str):
        raise Failure("method and path are required")
    route(method, path)
    query = encode(params)
    headers = {"Authorization": f"Bearer {key}", "Stripe-Version": VERSION, "User-Agent": UA,
               "Accept": "application/json"}
    if context is not None:
        if not ACCOUNT_ID.fullmatch(context):
            raise Failure("an organization key needs the account it acts on")
        headers["Stripe-Context"] = context
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
    label, target = resolve(req.get("account"), mode)
    reply = {"account": label, "mode": mode, **_route(target), "requests": 0}
    creds = credentials(label, mode, target)
    reply.update(fingerprint=creds["fingerprint"], key_kind=creds["kind"])
    slot = f"{label}/{mode}"
    if (req.get("refused") or {}).get(slot) == reply["fingerprint"]:
        return {**reply, "ok": False, "kind": "refused"}
    until = (req.get("paused") or {}).get(slot)
    if isinstance(until, (int, float)) and until > time.time():
        return {**reply, "ok": False, "kind": "limited", "until": until}
    if req.get("expect") and req["expect"] != reply["fingerprint"]:
        return {**reply, "ok": False, "kind": "account",
                "error": "the stored key or the account it reaches changed since the approval card was made; "
                         "nothing was sent"}
    try:
        prepared = prepare(creds["key"], req.get("method"), req.get("path"), req.get("params"),
                           req.get("idempotency_key"), creds["context"])
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
    label, target = resolve(req.get("account"), mode)
    creds = credentials(label, mode, target)
    return {"ok": True, "account": label, "mode": mode, **_route(target), "fingerprint": creds["fingerprint"],
            "key_kind": creds["kind"], "requests": 0}


def main(req: dict) -> dict:
    op = req.get("op")
    _READ.clear()   # what one request read, never a value an earlier request saw
    try:
        if op == "keys":
            data, organizations, unused = keys()
            return {"ok": True, "data": data, "organizations": organizations, "unused": unused, "requests": 0}
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
