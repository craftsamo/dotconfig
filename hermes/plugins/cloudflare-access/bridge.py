"""cloudflare-access bridge: the only process that holds a Cloudflare API token, for one call.

The engine (``cfa.py``) runs this file with Hermes' own interpreter in isolated mode, a minimal
environment and the state directory as working directory, writes one JSON request to stdin and
reads one JSON reply from stdout.

Tokens live in the Keychain (project ``hermes``, scope ``cloudflare-access``, a scope no Hermes
profile receives), without a stage: Cloudflare has no test mode. An item's name is the user's to
choose and its fields say what it is:

    label=<label>              the name calls use for the account
    account_id=<32 hex>        the Cloudflare account the token acts on

A token is an API token (``cfut_…`` user-owned, ``cfat_…`` account-owned, or an older one without a
prefix); a Global API Key is refused, since it reaches everything the user can. Each item is read
from its exact layer, never a staged one, and a label two items carry is refused rather than
guessed. A token is read when a call needs it and lives only in this short-lived process; it is
masked in every string that leaves. A fingerprint names what a call runs on, the token with the
account id, so a card made for one account never runs on another.

Only the endpoints in ``ROUTES`` exist here and only api.cloudflare.com is contacted, never through
a redirect. A path names the label's own account as ``{account}``, filled in here from the item, so
an account-wide call can reach no other account; a query value of exactly ``{account}`` is filled in
the same way. Cloudflare answers a token it no longer takes and a token without the permission a
call needs alike, so a 401 or 403 is checked against the token's own verify endpoint before it is
reported as a refused token. Contract: docs/cloudflare-access.md.

    {"op": "keys"}     the stored labels, their items, accounts, token kinds and fingerprints, and the
                       scope's items that are no token with why; never a token, never a request
    {"op": "key", "account": label | null}
                       the label a call would run on, its item, account, token kind and fingerprint;
                       no request to Cloudflare
    {"op": "verify", "account": label | null, "paused", "deadline": seconds}
                       the token's status from its verify endpoint (user-owned or account-owned), even
                       for a token remembered as refused
    {"op": "call", "account": label | null, "method": "GET" | "POST" | "PUT" | "PATCH" | "DELETE",
     "path": "/zones/...", "params": [[key, value], ...], "body": JSON | null,
     "refused": {"<label>": fingerprint}, "paused": {"<label>": epoch seconds},
     "expect": fingerprint | null, "deadline": seconds}
    {"op": "reads", "account": label | null, "requests": [{"path", "params"}, ...], "refused", "paused",
     "expect", "deadline"}
                       several GETs under one read of the token, in order; stops at a refused token,
                       a rate limit or a broken connection
    {"op": "graphql", "account": label | null, "query": a name in QUERIES, "variables": {...}, "refused",
     "paused", "deadline"}
                       one fixed analytics query; never a query text of the caller's
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
PROJECT, SCOPE = "hermes", "cloudflare-access"
SECRET_TIMEOUT = 20
BASE = "https://api.cloudflare.com/client/v4"
UA = "hermes-cloudflare-access/1.0"

LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9_]{0,22}[a-z0-9])?$")
# An item name as the secret CLI stores one, so it is never read as a flag or a "scope/NAME@stage" token.
NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
ACCOUNT_ID = re.compile(r"^[0-9a-f]{32}$")
# API tokens: cfut_ (user-owned) and cfat_ (account-owned) with their checksum, or an older token of 40
# characters without a prefix. A Global API Key is cfk_…, or 37 to 45 lowercase hex characters.
TOKEN = re.compile(r"^(?:(cfut|cfat)_[A-Za-z0-9_-]{40,160}|[A-Za-z0-9_-]{40})$")
GLOBAL_KEY = re.compile(r"^(?:cfk_[A-Za-z0-9_-]+|[0-9a-f]{37,45})$")
KINDS_BY_PREFIX = {"cfut": "user", "cfat": "account"}
KEY_SHAPE = re.compile(r"\bcf(?:ut|at|k)_[A-Za-z0-9_*-]+")
PARAM = re.compile(r"^[a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)*(?:\[\])?$")
PARAM_VALUE_MAX = 2000
PARAMS_MAX = 60
BODY_MAX = 256 * 1024
REPLY_MAX = 8 * 1024 * 1024
READS_MAX = 30
METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")
# Path segments: {account} is the label's own account, filled in here; the others are checked by shape.
SEGMENTS = {
    "{id}": r"[0-9a-f]{32}",                        # a zone, a DNS record, a KV namespace
    "{setting}": r"[a-z0-9_]{1,64}",                 # a zone setting
    "{script}": r"[A-Za-z0-9_-]{1,64}",              # a Worker
    "{project}": r"[a-z0-9][a-z0-9-]{0,62}",         # a Pages project
}

# Every endpoint this bridge will call, as (method, path pattern).
ROUTES = (
    ("GET", "/user/tokens/verify"),
    ("GET", "/accounts/{account}/tokens/verify"),
    ("GET", "/accounts/{account}"),
    ("GET", "/zones"),
    ("GET", "/zones/{id}"),
    ("GET", "/zones/{id}/dns_records"),
    ("GET", "/zones/{id}/dns_records/{id}"),
    ("GET", "/zones/{id}/settings/{setting}"),
    # Workers and Pages: what runs and what was deployed, never a script's code
    ("GET", "/accounts/{account}/workers/scripts"),
    ("GET", "/accounts/{account}/workers/scripts/{script}/deployments"),
    ("GET", "/accounts/{account}/workers/scripts/{script}/versions"),
    ("GET", "/accounts/{account}/pages/projects"),
    ("GET", "/accounts/{account}/pages/projects/{project}"),
    ("GET", "/accounts/{account}/pages/projects/{project}/deployments"),
)
VERIFY = {"user": "/user/tokens/verify", "account": "/accounts/{account}/tokens/verify"}

# The GraphQL Analytics API takes any query, so it is not in ROUTES: only these fixed queries are sent, with
# variables checked by kind. accountTag is the label's own account, filled in here; a zone report names a
# zone id the engine has checked belongs to that account.
GRAPHQL = "/graphql"
_TOP = """query($zoneTag: string, $since: Time, $until: Time) {
  viewer { zones(filter: {zoneTag: $zoneTag}) {
    httpRequestsAdaptiveGroups(limit: 25, orderBy: [count_DESC],
        filter: {datetime_geq: $since, datetime_lt: $until, requestSource: "eyeball"}) {
      count
      dimensions { %s }
    }
  } }
}"""
_WORKERS = """query($accountTag: string, $since: Time, $until: Time%s) {
  viewer { accounts(filter: {accountTag: $accountTag}) {
    workersInvocationsAdaptive(limit: 100, orderBy: [sum_requests_DESC],
        filter: {datetime_geq: $since, datetime_lt: $until%s}) {
      sum { requests errors subrequests }
      quantiles { cpuTimeP50 cpuTimeP99 }
      dimensions { scriptName status }
    }
  } }
}"""
QUERIES = {
    "traffic": ({"zoneTag": "zone", "since": "date", "until": "date"}, """query($zoneTag: string, $since: Date, $until: Date) {
  viewer { zones(filter: {zoneTag: $zoneTag}) {
    httpRequests1dGroups(limit: 400, orderBy: [date_ASC], filter: {date_geq: $since, date_leq: $until}) {
      dimensions { date }
      sum { requests bytes cachedRequests cachedBytes threats pageViews }
      uniq { uniques }
    }
  } }
}"""),
    "paths": ({"zoneTag": "zone", "since": "time", "until": "time"}, _TOP % "clientRequestPath"),
    "countries": ({"zoneTag": "zone", "since": "time", "until": "time"}, _TOP % "clientCountryName"),
    "statuses": ({"zoneTag": "zone", "since": "time", "until": "time"}, _TOP % "edgeResponseStatus"),
    "security": ({"zoneTag": "zone", "since": "time", "until": "time"}, """query($zoneTag: string, $since: Time, $until: Time) {
  viewer { zones(filter: {zoneTag: $zoneTag}) {
    firewallEventsAdaptiveGroups(limit: 25, orderBy: [count_DESC],
        filter: {datetime_geq: $since, datetime_lt: $until}) {
      count
      dimensions { action source }
    }
  } }
}"""),
    "security_events": ({"zoneTag": "zone", "since": "time", "until": "time"}, """query($zoneTag: string, $since: Time, $until: Time) {
  viewer { zones(filter: {zoneTag: $zoneTag}) {
    firewallEventsAdaptive(limit: 25, orderBy: [datetime_DESC],
        filter: {datetime_geq: $since, datetime_lt: $until}) {
      datetime action source clientCountryName clientRequestPath
    }
  } }
}"""),
    "workers": ({"accountTag": "account", "since": "time", "until": "time"}, _WORKERS % ("", "")),
    "worker": ({"accountTag": "account", "since": "time", "until": "time", "scriptName": "script"},
               _WORKERS % (", $scriptName: string", ", scriptName: $scriptName")),
}
VARIABLES = {
    "zone": re.compile(r"^[0-9a-f]{32}$"),
    "date": re.compile(r"^\d{4}-\d{2}-\d{2}$"),
    "time": re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"),
    "script": re.compile(r"^[A-Za-z0-9_-]{1,64}$"),
}


def _pattern(path: str) -> re.Pattern:
    text = re.escape(path)
    for segment, shape in SEGMENTS.items():
        text = text.replace(re.escape(segment), shape)
    return re.compile("^" + text + "$")


_ROUTES = tuple((method, _pattern(path)) for method, path in ROUTES)

SECRETS: list[str] = []


class Setup(Exception):
    pass


class Failure(Exception):
    def __init__(self, message: str, kind: str = "error", status: int | None = None, **detail):
        super().__init__(message)
        self.kind, self.status, self.detail = kind, status, detail


def mask(text) -> str:
    """The text without any token this process read, or anything shaped like a Cloudflare credential."""
    text = str(text)
    for value in SECRETS:
        if value:
            text = text.replace(value, "…")
    return KEY_SHAPE.sub("…", text)


def fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:12]


def set_command(label: str) -> str:
    """How the user stores a token for a label; the name is only a suggestion, the fields are what count."""
    return (f"secret set CLOUDFLARE_{label.upper()} -p {PROJECT} --scope {SCOPE} --no-stage -D TOKEN "
            f"--meta label={label} --meta account_id=<account id> --no-env")


def update_command(item: str, change: str = "--value") -> str:
    """How the user changes one stored item in place (a fresh value by default, its fields kept)."""
    return f"secret update {item} -p {PROJECT} --scope {SCOPE} --no-stage {change}"


def _secret(*argv: str) -> subprocess.CompletedProcess:
    if not SECRET.exists():
        raise Setup(f"the secret CLI is missing at {SECRET}")
    try:
        return subprocess.run([str(SECRET), *argv], stdin=subprocess.DEVNULL, capture_output=True, text=True,
                              timeout=SECRET_TIMEOUT)
    except subprocess.TimeoutExpired as exc:
        raise Setup("reading the Keychain timed out") from exc


def _unusable(name: str, stage: str, meta: dict) -> str | None:
    """Why an item of the scope is no token for an account; None when it is one."""
    if not NAME.fullmatch(name):
        return ("its name is not one the secret CLI takes (letters, digits and _, not starting with a digit); "
                "store it again under such a name")
    if stage:
        return (f"it is in stage {stage}; Cloudflare has no test mode, so tokens are stored without a stage "
                f"(`{set_command('<label>')}`)")
    for field in ("label", "account_id"):
        other = next((k for k in meta if k.lower() == field and k != field), None)
        if other and not meta.get(field):   # matched by its exact spelling, so removing it is one exact command
            return (f"its field {other}= is not read: the field is {field}=, in lowercase; rename it with "
                    f"`{update_command(name, f'--meta {other}= --meta {field}=<{field}>')}`")
    label, account_id = meta.get("label", ""), meta.get("account_id", "")
    if not label:
        return f"it has no label= field naming its account; give it one with `{update_command(name, '--meta label=<label>')}`"
    if not LABEL.fullmatch(label.lower()):
        return (f"label={label[:40]} is not a label (lowercase letters, digits and _, at most 24); fix it with "
                f"`{update_command(name, '--meta label=<label>')}`")
    if not account_id:
        return ("it has no account_id= field naming the Cloudflare account the token acts on (the dashboard's "
                f"account home shows it); add it with `{update_command(name, '--meta account_id=<account id>')}`")
    if not ACCOUNT_ID.fullmatch(account_id.lower()):
        return (f"account_id={account_id[:40]} is not a Cloudflare account id (32 hexadecimal characters); fix it "
                f"with `{update_command(name, '--meta account_id=<account id>')}`")
    return None


def inventory() -> tuple[dict, list]:
    """The scope's items, from the Keychain's metadata (no value is read): {label: [{"item", "account_id"}]},
    and what is no token with what is wrong. Fields are spelled exactly; values match without regard to case."""
    proc = _secret("ls", "-p", PROJECT, "--json")
    if proc.returncode != 0:
        raise Setup(f"could not list the Keychain items of project {PROJECT}")
    try:
        items = json.loads(proc.stdout or "[]")
    except ValueError as exc:
        raise Setup("the Keychain listing was not readable") from exc
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
        found.setdefault(meta["label"].lower(), []).append({"item": name, "account_id": meta["account_id"].lower()})
    return {label: sorted(entries, key=lambda e: e["item"]) for label, entries in found.items()}, unused


def _twice(label: str, names: list) -> str:
    listed = ", ".join(names[:4]) + (" …" if len(names) > 4 else "")
    return (f"{len(names)} items carry label={label} ({listed}); nothing was sent. Keep one: take the label off "
            f"the others (`{update_command(names[-1], '--meta label=')}`)")


def pick(label: str, entries: list) -> dict:
    if len(entries) > 1:
        raise Setup(_twice(label, [entry["item"] for entry in entries]))
    return dict(entries[0])


def read_token(label: str, target: dict) -> tuple[str, str]:
    """(token, kind) of a label's item; raises Setup with the fix."""
    item = target["item"]
    where = f"{item} (label={label})"
    proc = _secret("get", item, "-p", PROJECT, "--scope", SCOPE, "--no-stage")
    value = proc.stdout.strip()
    if proc.returncode != 0 or not value:
        raise Setup(f"{where} could not be read from the Keychain (locked, or removed since it was listed); "
                    "nothing was sent")
    SECRETS.append(value)
    if GLOBAL_KEY.fullmatch(value):
        raise Setup(f"{where} holds a Global API Key, which reaches everything the user can; nothing was sent. "
                    f"Create an API token with the permissions Hermes should have and store it there "
                    f"(`{update_command(item)}`)")
    match = TOKEN.fullmatch(value)
    if not match:
        raise Setup(f"{where} is not a Cloudflare API token; store the token there (`{update_command(item)}`)")
    return value, KINDS_BY_PREFIX.get(match.group(1) or "", "token")


def credentials(label: str, target: dict) -> dict:
    """The token, its kind and the fingerprint of what a call runs on: the token with its account."""
    token, kind = read_token(label, target)
    return {"token": token, "kind": kind, "fingerprint": fingerprint(f"{token}|{target['account_id']}")}


def resolve(account) -> tuple[str, dict]:
    """(label, target) a call runs on: the label named, or the only one stored."""
    if account is not None and (not isinstance(account, str) or not LABEL.fullmatch(account)):
        raise Setup("account must be a label like work (lowercase letters, digits and _)")
    found, _ = inventory()
    if account is None:
        labels = sorted(found)
        if not labels:
            raise Setup(f"no Cloudflare token is stored; the user stores one with `{set_command('<label>')}`")
        if len(labels) > 1:
            raise Setup("account is required: tokens are stored for " + ", ".join(labels))
        account = labels[0]
    entries = found.get(account)
    if not entries:
        raise Setup(f"no token for account {account} in the Keychain (project {PROJECT}, scope {SCOPE}, field "
                    f"label={account}); the user stores it with `{set_command(account)}`")
    return account, pick(account, entries)


def keys() -> tuple[list, list]:
    """Each stored label's item, account, token kind and fingerprint, and the scope's items that are none."""
    found, unused = inventory()
    result = []
    for label, entries in sorted(found.items()):
        entry = {"account": label}
        try:
            target = pick(label, entries)
            entry.update(item=target["item"], account_id=target["account_id"])
            creds = credentials(label, target)
            entry.update(kind=creds["kind"], fingerprint=creds["fingerprint"])
        except Setup as exc:
            entry["problem"] = mask(exc)[:300]
        result.append(entry)
    return result, unused


def route(method: str, path: str) -> None:
    if not any(m == method and pattern.fullmatch(path) for m, pattern in _ROUTES):
        raise Failure(f"{method} {path} is not an endpoint this tool calls", "error")


def encode(params, account_id: str) -> str:
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
            raise Failure(f"parameter {key[:80]!r} is not one Cloudflare takes")
        pairs.append((key, account_id if value == "{account}" else value))
    return urllib.parse.urlencode(pairs)


class _CloudflareOnly(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise Failure(f"Cloudflare answered with a redirect ({code}); not followed", "error", code)


_OPENER = urllib.request.build_opener(_CloudflareOnly)


def prepare(token: str, account_id: str, method: str, path: str, params, body=None) -> urllib.request.Request:
    """The request, checked against ROUTES; nothing is sent here."""
    if method not in METHODS or not isinstance(path, str):
        raise Failure("method and path are required")
    route(method, path)
    query = encode(params, account_id)
    headers = {"Authorization": f"Bearer {token}", "User-Agent": UA, "Accept": "application/json"}
    data = None
    if method == "GET":
        if body is not None:
            raise Failure("a read carries no body")
    elif body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        if len(data) > BODY_MAX:
            raise Failure("the request body is too large")
        headers["Content-Type"] = "application/json"
    url = BASE + path.replace("{account}", account_id) + (f"?{query}" if query else "")
    return urllib.request.Request(url, data=data, headers=headers, method=method)


def prepare_graphql(token: str, account_id: str, name, variables) -> urllib.request.Request:
    """One of the fixed QUERIES with its variables checked by kind; nothing is sent here."""
    if name not in QUERIES:
        raise Failure(f"{name!r} is not a query this tool sends")
    kinds, text = QUERIES[name]
    if not isinstance(variables, dict) or set(variables) != {k for k, kind in kinds.items() if kind != "account"}:
        raise Failure(f"the {name} query takes " + ", ".join(sorted(k for k, v in kinds.items() if v != "account")))
    values = {}
    for key, kind in kinds.items():
        if kind == "account":
            values[key] = account_id
        elif not isinstance(variables[key], str) or not VARIABLES[kind].fullmatch(variables[key]):
            raise Failure(f"variable {key} is not a {kind}")
        else:
            values[key] = variables[key]
    data = json.dumps({"query": text, "variables": values}).encode("utf-8")
    headers = {"Authorization": f"Bearer {token}", "User-Agent": UA, "Accept": "application/json",
               "Content-Type": "application/json"}
    return urllib.request.Request(BASE + GRAPHQL, data=data, headers=headers, method="POST")


KINDS = {400: "invalid", 401: "refused", 403: "forbidden", 404: "not_found", 405: "invalid", 409: "conflict",
         413: "invalid", 415: "invalid", 422: "invalid", 429: "limited"}
# Codes Cloudflare gives for a token it cannot read at all (an Authorization header it does not take).
AUTH_CODES = {1000, 6003, 6100, 6111, 9106, 9109, 10000}


def _errors(data) -> tuple[str, list]:
    """(message, codes) of Cloudflare's errors[]: up to three as 'code: message'."""
    errors = data.get("errors") if isinstance(data, dict) else None
    shown, codes = [], []
    for error in errors if isinstance(errors, list) else []:
        if isinstance(error, dict):
            code = error.get("code")
            if isinstance(code, int):
                codes.append(code)
            text = mask(error.get("message") or "")[:200]   # masked whole, so a cut never leaves a token's part
            shown.append(f"{code}: {text}" if code is not None else text)
    return "; ".join(shown[:3]), codes


def _retry_after(head) -> int | None:
    try:
        value = int(float((head.get("Retry-After") if head else None) or ""))
    except ValueError:
        return None
    return max(1, min(value, 3600))


def send(req: urllib.request.Request, deadline: float, graphql: bool = False) -> tuple[int, dict, dict]:
    """(status, parsed reply, response facts) of one request; raises Failure for anything but a 2xx
    Cloudflare marked a success (for GraphQL: data without errors, which come with a 200 as well)."""
    left = deadline - time.monotonic()
    if left <= 1:
        raise Failure("Cloudflare did not answer in time", "timeout")
    try:
        with _OPENER.open(req, timeout=min(left, 60)) as reply:
            status, raw, head = reply.status, reply.read(REPLY_MAX + 1), reply.headers
    except urllib.error.HTTPError as exc:
        status, head = exc.code, exc.headers
        try:
            raw = exc.read(REPLY_MAX + 1)
        except (OSError, http.client.HTTPException):
            raw = b""
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        kind = "timeout" if isinstance(reason, TimeoutError) else "network"
        raise Failure(f"could not reach Cloudflare: {reason}", kind) from exc
    except TimeoutError as exc:
        raise Failure("Cloudflare stopped answering", "timeout") from exc
    except (OSError, http.client.HTTPException) as exc:  # reset, incomplete read: a write may have landed
        raise Failure(f"the connection to Cloudflare broke off ({type(exc).__name__})", "network") from exc
    facts = {"ray": (head.get("cf-ray") if head else None) or None}
    if len(raw or b"") > REPLY_MAX:
        raise Failure("Cloudflare's answer is too large to read", "uncertain" if 200 <= status < 300 else "api",
                      status, **facts)
    try:
        data = json.loads(raw or b"null")
    except ValueError:
        data = None
    message, codes = _errors(data)
    if 200 <= status < 300 and graphql:
        if not isinstance(data, dict) or not isinstance(data.get("data"), dict) or data.get("errors"):
            raise Failure(message or f"Cloudflare answered {status} without readable data", "graphql", status,
                          **facts)
        return status, data, facts
    if 200 <= status < 300:
        if not isinstance(data, dict) or data.get("success") is not True:
            raise Failure(message or f"Cloudflare answered {status} without a readable success", "uncertain",
                          status, codes=codes, **facts)
        return status, data, facts
    kind = KINDS.get(status, "api" if status >= 500 else "http")
    if status == 400 and set(codes) & AUTH_CODES:
        kind = "refused"
    retry = _retry_after(head) if status == 429 else None
    raise Failure(message or f"Cloudflare answered {status}", kind, status, codes=codes, retry_after=retry, **facts)


def verify(creds: dict, account_id: str, deadline: float) -> tuple[dict, int]:
    """({"status": active | disabled | expired | None, ...}, requests): the token's own verify endpoint, the
    user-owned one, the account-owned one, or both in turn for a token without a prefix. A status of None
    means Cloudflare took the token on neither."""
    paths = [VERIFY[creds["kind"]]] if creds["kind"] in VERIFY else [VERIFY["user"], VERIFY["account"]]
    sent, refusal = 0, ""
    for path in paths:
        sent += 1
        try:
            _, data, _ = send(prepare(creds["token"], account_id, "GET", path, None), deadline)
        except Failure as exc:
            if exc.kind in ("refused", "forbidden", "invalid", "not_found"):
                refusal = str(exc)
                continue
            raise
        result = data.get("result") if isinstance(data.get("result"), dict) else {}
        status = result.get("status")
        return ({"status": status if status in ("active", "disabled", "expired") else str(status)[:20],
                 "owner": "account" if path == VERIFY["account"] else "user",
                 **{k: str(result[k])[:40] for k in ("expires_on", "not_before") if result.get(k)}}, sent)
    return {"status": None, "error": refusal}, sent


def _failed(reply: dict, exc: Failure) -> dict:
    detail = {k: mask(v)[:400] if isinstance(v, str) else v for k, v in exc.detail.items() if v not in (None, "", [])}
    return {**reply, "ok": False, "kind": exc.kind, "status": exc.status, "error": mask(exc)[:400], **detail}


def _confirm(failure: dict, creds: dict, account_id: str, deadline: float) -> dict:
    """A 401 or 403 checked against the token's verify endpoint: 'refused' only when Cloudflare no longer
    takes the token, 'forbidden' when it does (a permission is missing) or when the check itself failed,
    'limited' when the check ran into a rate limit."""
    try:
        checked, sent = verify(creds, account_id, deadline)
    except Failure as exc:
        if exc.kind == "limited":
            return {**failure, "kind": "limited", "requests": failure["requests"] + 1,
                    "retry_after": exc.detail.get("retry_after")}
        return {**failure, "kind": "forbidden", "requests": failure["requests"] + 1}
    failure = {**failure, "requests": failure["requests"] + sent}
    if checked["status"] == "active":
        return {**failure, "kind": "forbidden", "token_status": "active"}
    return {**failure, "kind": "refused", "token_status": checked["status"] or "invalid"}


def _open(req: dict, checks: str = "call") -> tuple[dict, dict | None, dict | None]:
    """(reply head, credentials, early answer): the label a call runs on and its token, or why nothing is sent.
    `checks` is "call" (a refused token, a pause and a changed token stop it), "verify" (only a pause: the
    check exists to see a refused token again) or "none" (nothing is sent)."""
    label, target = resolve(req.get("account"))
    reply = {"account": label, "item": target["item"], "account_id": target["account_id"], "requests": 0}
    creds = credentials(label, target)
    reply.update(fingerprint=creds["fingerprint"], token_kind=creds["kind"])
    if checks == "none":
        return reply, creds, None
    until = (req.get("paused") or {}).get(label)
    if isinstance(until, (int, float)) and until > time.time():
        return reply, creds, {**reply, "ok": False, "kind": "limited", "until": until}
    if checks == "verify":
        return reply, creds, None
    if (req.get("refused") or {}).get(label) == reply["fingerprint"]:
        return reply, creds, {**reply, "ok": False, "kind": "refused"}
    if req.get("expect") and req["expect"] != reply["fingerprint"]:
        return reply, creds, {**reply, "ok": False, "kind": "account",
                              "error": "the stored token or the account it acts on changed since the approval card "
                                       "was made; nothing was sent"}
    return reply, creds, None


def _one(reply: dict, creds: dict, method, path, params, body, deadline: float) -> dict:
    return _exchange(reply, creds, lambda: prepare(creds["token"], reply["account_id"], method, path, params, body),
                     deadline)


def _exchange(reply: dict, creds: dict, build, deadline: float, graphql: bool = False) -> dict:
    """One request built by `build`, sent, and a 401 or 403 checked against the token's verify endpoint."""
    try:
        prepared = build()
    except Failure as exc:
        return {**reply, "ok": False, "kind": "error", "error": mask(exc)[:400]}
    reply = {**reply, "requests": reply["requests"] + 1}
    try:
        status, data, facts = send(prepared, deadline, graphql)
    except Failure as exc:
        failure = _failed(reply, exc)
        if exc.status in (401, 403) or exc.kind == "refused":
            return _confirm(failure, creds, reply["account_id"], deadline)
        return failure
    except Exception as exc:  # after the request left: whether it landed is unknown, so it counts as sent
        return {**reply, "ok": False, "kind": "error", "error": mask(f"{type(exc).__name__}: {exc}")[:400]}
    return {**reply, "ok": True, "status": status, "data": data, **{k: v for k, v in facts.items() if v}}


def call(req: dict) -> dict:
    reply, creds, early = _open(req)
    if early:
        return early
    deadline = time.monotonic() + float(req.get("deadline", 60))
    return _one(reply, creds, req.get("method"), req.get("path"), req.get("params"), req.get("body"), deadline)


def graphql(req: dict) -> dict:
    reply, creds, early = _open(req)
    if early:
        return early
    deadline = time.monotonic() + float(req.get("deadline", 60))
    build = lambda: prepare_graphql(creds["token"], reply["account_id"], req.get("query"), req.get("variables"))
    return _exchange(reply, creds, build, deadline, graphql=True)


STOPS = {"refused", "limited", "timeout", "network", "account"}


def reads(req: dict) -> dict:
    requests = req.get("requests")
    if not isinstance(requests, list) or not 0 < len(requests) <= READS_MAX:
        raise Failure(f"requests must be a list of 1 to {READS_MAX} reads")
    reply, creds, early = _open(req)
    if early:
        return early
    deadline = time.monotonic() + float(req.get("deadline", 60))
    results = []
    for entry in requests:
        if not isinstance(entry, dict):
            raise Failure("each read is an object with path and params")
        one = _one({**reply, "requests": 0}, creds, "GET", entry.get("path"), entry.get("params"), None, deadline)
        reply["requests"] += one.pop("requests")
        for key in ("account", "item", "account_id", "fingerprint", "token_kind"):
            one.pop(key, None)
        results.append(one)
        if not one["ok"] and one.get("kind") in STOPS:
            return {**reply, "ok": False, "kind": one["kind"], "error": one.get("error"),
                    "retry_after": one.get("retry_after"), "token_status": one.get("token_status"), "results": results}
    return {**reply, "ok": True, "results": results}


def check(req: dict) -> dict:
    """The verify op: asks Cloudflare even for a token remembered as refused, so the user can see that a
    token re-enabled in the dashboard works again; a rate-limit pause still holds."""
    reply, creds, early = _open(req, checks="verify")
    if early:
        return early
    deadline = time.monotonic() + float(req.get("deadline", 60))
    try:
        checked, sent = verify(creds, reply["account_id"], deadline)
    except Failure as exc:
        return _failed({**reply, "requests": 1}, exc)
    reply["requests"] = sent
    if checked["status"] is None:
        return {**reply, "ok": False, "kind": "refused", "token_status": "invalid",
                "error": mask(checked.get("error") or "Cloudflare does not take this token")[:400]}
    if checked["status"] != "active":
        return {**reply, "ok": False, "kind": "refused", "token_status": checked["status"],
                "error": f"the token is {checked['status']}", **{k: v for k, v in checked.items() if k != "status"}}
    return {**reply, "ok": True, "token_status": "active", "verify": checked}


def key(req: dict) -> dict:
    reply, _, _ = _open(req, checks="none")
    return {**reply, "ok": True}


def main(req: dict) -> dict:
    op = req.get("op")
    try:
        if op == "keys":
            data, unused = keys()
            return {"ok": True, "data": data, "unused": unused, "requests": 0}
        if op == "key":
            return key(req)
        if op == "verify":
            return check(req)
        if op == "call":
            return call(req)
        if op == "reads":
            return reads(req)
        if op == "graphql":
            return graphql(req)
        return {"ok": False, "kind": "error", "error": f"unknown op {op!r}", "requests": 0}
    except Setup as exc:
        return {"ok": False, "kind": "setup", "error": mask(exc)[:500], "requests": 0}
    except Failure as exc:
        return {"ok": False, "kind": exc.kind, "error": mask(exc)[:400], "requests": 0}
    except Exception as exc:  # unexpected: reported without a traceback, the token masked
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
