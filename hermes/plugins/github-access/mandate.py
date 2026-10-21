"""github-access: mandates — the user's standing approval for a bounded kind of GitHub change.

A mandate is made only on its own approval card and names: the boards and repositories it covers
(and optionally one parent issue whose direct sub-issues alone it covers), the classes of change
(routine, create), a purpose, and an end at most MAX_DAYS out. A change list runs without a card
only when every change fits one mandate, each target is in its scope, and each target's tier,
read at the moment of the write, allows the change's class (TIER_CAP): a shared target never takes
more than routine changes and someone else's never takes any, whatever the mandate says.

State, in the profile home (never the repository; the guard blocks file and terminal access):

  <HERMES_HOME>/github-access/mandates/<id>.json   the terms, MAC'd
  <HERMES_HOME>/github-access/head.json            the ids in force, MAC'd: only the head decides
  <HERMES_HOME>/github-access/mandates.jsonl       made / revoked history, for the record only

The MAC key is a random key in the Keychain (``GITHUB_MANDATE_KEY_<PROFILE>``, project hermes,
scope github-access, a scope no profile receives), made with the first mandate. Without a readable
key no mandate is in force and every change list asks on its card.
"""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import hmac
import importlib.util
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import time
from pathlib import Path


def _load(name, path):
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


access = _load("hermes_github_access_engine", Path(__file__).resolve().parent / "access.py")
AccessError = access.AccessError

STATE = "github-access"
MAX_DAYS = 30
DAY = 86400
CLASSES = ("routine", "create")
TIER_CAP = {"own": {"routine", "create"}, "shared": {"routine"}, "other": set()}
ID = re.compile(r"^m[0-9a-f]{8}$")
PURPOSE_LIMIT = 200
SECRET = Path.home() / ".config" / "bin" / "secret"
VAULT_PROJECT, VAULT_SCOPE = "hermes", "github-access"
SECRET_TIMEOUT = 20
_LOCK = threading.Lock()


def state_dir(home) -> Path:
    return Path(home) / STATE


def vault_name(home) -> str:
    home = Path(os.path.expanduser(str(home)))
    name = "default" if home == Path.home() / ".hermes" else home.name
    return "GITHUB_MANDATE_KEY_" + (re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_") or "DEFAULT")


@contextlib.contextmanager
def _locked(home):
    folder = state_dir(home)
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    with _LOCK, open(folder / ".lock", "a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield folder
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


# --- the key --------------------------------------------------------------------------------------

def _secret(home, command: str, extra: tuple = (), value: str | None = None) -> subprocess.CompletedProcess:
    if not os.access(SECRET, os.X_OK):
        raise AccessError(f"the secret CLI is missing at {SECRET}")
    argv = [str(SECRET), command, vault_name(home), "-p", VAULT_PROJECT, "--scope", VAULT_SCOPE, *extra]
    feed = {"input": value + "\n"} if value is not None else {"stdin": subprocess.DEVNULL}
    if value is not None:
        argv.append("--stdin")
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=SECRET_TIMEOUT,
                              cwd=str(state_dir(home)) if state_dir(home).is_dir() else None, **feed)
    except subprocess.TimeoutExpired as exc:
        raise AccessError("the Keychain did not answer in time") from exc


def key(home, create: bool = False) -> bytes | None:
    """The MAC key, read from the Keychain every time (never cached: a removed or replaced key takes
    effect at once); None when there is none (and ``create`` is off) or it cannot be read."""
    try:
        proc = _secret(home, "get")
    except AccessError:
        return None
    value = proc.stdout.strip()
    if proc.returncode == 0 and re.fullmatch(r"[0-9a-f]{64}", value):
        return bytes.fromhex(value)
    if not create or _secret(home, "show").returncode == 0:
        return None  # absent, or present but unreadable: never written over
    made = secrets.token_hex(32)
    proc = _secret(home, "set", ("-D", "key", "-j", "github-access mandate MAC key"), value=made)
    if proc.returncode != 0:
        raise AccessError(f"could not store {vault_name(home)} in the Keychain: {proc.stderr.strip()[:200]}")
    return key(home)


def _mac(secret: bytes, kind: str, body: dict) -> str:
    text = json.dumps({"kind": kind, **{k: v for k, v in body.items() if k != "mac"}}, sort_keys=True,
                      separators=(",", ":"), ensure_ascii=False)
    return hmac.new(secret, text.encode("utf-8"), hashlib.sha256).hexdigest()


def _write(path: Path, body: dict) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(body, ensure_ascii=False, indent=1), encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def _read(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _log(home, event: str, mandate_id: str) -> None:
    with open(state_dir(home) / "mandates.jsonl", "a", encoding="utf-8") as handle:
        handle.write(json.dumps({"event": event, "mandate": mandate_id, "time": int(time.time())}) + "\n")


# --- terms ----------------------------------------------------------------------------------------

def terms(args: dict) -> dict:
    """The terms of a new mandate from a ``github_mandate`` create call, targets read now."""
    boards, repos = [], []
    for ref in args.get("boards") or []:
        if not isinstance(ref, str) or not ref.strip():
            raise AccessError("boards is a list of board references (URL or owner/N)")
        b = access.resolve_board(project=ref.strip())["board"]
        if not b["can_update"]:
            raise AccessError(f"board {b['owner']}/{b['number']} is read-only for the viewer")
        tier = access.tier(b["owner"], b["owner_type"], not b["public"], fresh=True)
        boards.append({"id": b["id"], "name": f"{b['owner']}/{b['number']} {b['title']}", "tier": tier})
    for ref in args.get("repos") or []:
        if not isinstance(ref, str) or not ref.strip():
            raise AccessError("repos is a list of owner/repo")
        ctx = access.repo_context(ref, fresh=True)
        if not ctx["can_write"]:
            raise AccessError(f"no write permission on {ctx['repo']}")
        # The node id, not the name, is what a mandate covers: a repository renamed away and another
        # made under the old name is not the one the user approved.
        repos.append({"id": ctx["id"], "name": ctx["repo"], "tier": ctx["tier"]})
    if not boards and not repos:
        raise AccessError("a mandate names at least one board or repository")
    parent = None
    if args.get("parent"):
        if not repos:
            raise AccessError("a parent issue needs its repository in repos")
        repo, number = access.parse_issue(args["parent"], repos[0]["name"])
        if not any(access.same(repo, r["name"]) for r in repos):
            raise AccessError(f"the parent's repository {repo} is not in repos")
        parent = f"{repo}#{number}"
    classes = args.get("classes") or ["routine"]
    if not isinstance(classes, list) or not classes or any(c not in CLASSES for c in classes):
        raise AccessError(f"classes is a list of: {', '.join(CLASSES)}")
    days = args.get("days")
    if not isinstance(days, int) or isinstance(days, bool) or not 1 <= days <= MAX_DAYS:
        raise AccessError(f"days is a whole number from 1 to {MAX_DAYS}")
    purpose = " ".join(str(args.get("purpose") or "").split())
    if not purpose:
        raise AccessError("purpose says what the mandate is for (one line)")
    if len(purpose) > PURPOSE_LIMIT:
        raise AccessError(f"purpose is at most {PURPOSE_LIMIT} characters")
    # The end is fixed now, when the card is drawn, so what is stored ends when the card said.
    return {"boards": boards, "repos": repos, "parent": parent, "classes": sorted(set(classes)),
            "days": days, "expires": int(time.time()) + days * DAY, "purpose": purpose}


def same_terms(a: dict, b: dict) -> bool:
    """Whether two readings of a create call agree on everything but the end (fixed at the card)."""
    strip = lambda t: {k: v for k, v in t.items() if k != "expires"}  # noqa: E731
    return strip(a) == strip(b)


def _what(classes) -> str:
    return " and ".join({"routine": "routine updates (fields, notes, archiving, issue text)",
                         "create": "new items, issues, comments, relations, labels, assignees, closing"}[c]
                        for c in classes)


def card(t: dict, say) -> str:
    end = time.strftime("%Y-%m-%d %H:%M", time.localtime(t["expires"]))
    lines = ["GitHub · Mandate", "⚠️ Changes inside it skip the card"]
    for b in t["boards"]:
        lines.append(f"Board: {say(b['name'], 80)} ({b['tier']})")
    for r in t["repos"]:
        lines.append(f"Repository: {r['name']} ({r['tier']})")
    if t["parent"]:
        lines.append(f"Only issue {t['parent']} and its direct sub-issues")
    lines.append(f"Covers: {_what(t['classes'])}")
    lines.append("Never covered: a target someone else owns; on a shared one, routine updates only")
    lines.append(f"Until: {end} ({t['days']} day{'s' if t['days'] != 1 else ''})")
    lines.append(f"Purpose: {say(t['purpose'], 120)}")
    return "\n".join(lines)


# --- what is in force -----------------------------------------------------------------------------

def _head(home, secret: bytes) -> list[str]:
    head = _read(state_dir(home) / "head.json")
    if not head or not isinstance(head.get("active"), list):
        return []
    if not hmac.compare_digest(str(head.get("mac", "")), _mac(secret, "github-mandate-head", head)):
        return []
    return [i for i in head["active"] if isinstance(i, str) and ID.match(i)]


def _set_head(home, secret: bytes, ids: list[str]) -> None:
    head = {"active": sorted(set(ids)), "time": int(time.time())}
    head["mac"] = _mac(secret, "github-mandate-head", head)
    _write(state_dir(home) / "head.json", head)


def _mandate(home, secret: bytes, mandate_id: str) -> dict | None:
    body = _read(state_dir(home) / "mandates" / f"{mandate_id}.json")
    if not body or body.get("id") != mandate_id:
        return None
    if not hmac.compare_digest(str(body.get("mac", "")), _mac(secret, "github-mandate", body)):
        return None
    return body


def active(home, now: float | None = None) -> list[dict]:
    """The mandates in force: in the authenticated head, authenticated themselves, not ended."""
    secret = key(home)
    if secret is None:
        return []
    now = time.time() if now is None else now
    out = []
    for mandate_id in _head(home, secret):
        body = _mandate(home, secret, mandate_id)
        if body and isinstance(body.get("expires"), (int, float)) and now < body["expires"]:
            out.append(body)
    return out


def create(home, t: dict) -> dict:
    with _locked(home):
        secret = key(home, create=True)
        if secret is None:
            raise AccessError(f"{vault_name(home)} is in the Keychain but could not be read; nothing was made")
        now = int(time.time())
        if t["expires"] <= now:
            raise AccessError("the mandate's end on its card has already passed; nothing was made")
        body = {"id": "m" + secrets.token_hex(4), "created": now, "expires": t["expires"],
                **{k: t[k] for k in ("boards", "repos", "parent", "classes", "purpose")}}
        body["mac"] = _mac(secret, "github-mandate", body)
        _write(state_dir(home) / "mandates" / f"{body['id']}.json", body)
        _set_head(home, secret, _head(home, secret) + [body["id"]])
        _log(home, "made", body["id"])
    return summary(body)


def revoke(home, mandate_id: str) -> dict:
    if not isinstance(mandate_id, str) or not ID.match(mandate_id):
        raise AccessError("mandate is an id like m1a2b3c4d")
    with _locked(home):
        secret = key(home)
        if secret is None:
            return {"revoked": mandate_id, "note": "no mandate key: none was in force"}
        ids = _head(home, secret)
        if mandate_id not in ids:
            return {"revoked": mandate_id, "note": "it was not in force"}
        _set_head(home, secret, [i for i in ids if i != mandate_id])
        _log(home, "revoked", mandate_id)
    return {"revoked": mandate_id}


def summary(body: dict) -> dict:
    return {"id": body["id"], "until": time.strftime("%Y-%m-%d %H:%M", time.localtime(body["expires"])),
            "boards": [b["name"] for b in body["boards"]], "repos": [r["name"] for r in body["repos"]],
            "parent": body.get("parent"), "classes": body["classes"], "purpose": body["purpose"]}


# --- does a change list fit -----------------------------------------------------------------------

def _in_scope(m: dict, target: dict) -> bool:
    if target["kind"] == "board":
        return any(b["id"] == target["id"] for b in m["boards"])
    return any(r.get("id") == target["id"] for r in m["repos"])


EARLIER = re.compile(r"^\$(\d+)$")


def _under_parent(m: dict, step: dict, steps: list | None = None) -> bool:
    """With a parent in the terms, every issue a change touches or relates is that issue or one of its
    direct sub-issues, and nothing leaves that tree or joins it from outside. ``$N`` (an issue change
    N of the same list creates) is inside only when change N creates a direct sub-issue of the parent."""
    if not m.get("parent"):
        return True
    root = access.parse_issue(m["parent"])
    change = step["change"]
    op = change["op"]
    steps = steps or []

    def ref(text):
        return access.parse_issue(text, step["repo"]["repo"])

    def is_root(r):
        return access.same(r[0], root[0]) and r[1] == root[1]

    def in_tree(r):
        if is_root(r):
            return True
        current = access.issue(r[0], r[1], comments=0).get("parent")
        return bool(current and is_root((current["repo"], current["number"])))

    def earlier_child(text) -> bool:
        n = int(EARLIER.match(text.strip()).group(1))
        if not 1 <= n <= len(steps):
            return False
        prior = steps[n - 1]
        parent = prior["change"].get("parent")
        return (prior["change"]["op"] == "issue_create" and isinstance(parent, str) and not EARLIER.match(parent.strip())
                and is_root(access.parse_issue(parent, prior["repo"]["repo"])))

    def in_tree_ref(text) -> bool:
        return earlier_child(text) if EARLIER.match(text.strip()) else in_tree(ref(text))

    if op == "issue_create":
        parent = change.get("parent")
        # A "$N" parent makes a grandchild of the mandate's parent: outside its direct sub-issues.
        return bool(parent) and not EARLIER.match(parent.strip()) and is_root(ref(parent)) and \
            all(in_tree_ref(x) for x in change.get("blocked_by") or [])
    if step.get("number") is None:
        return step.get("repo") is None  # board-only changes are bounded by the boards
    this = (step["repo"]["repo"], step["number"])
    if not in_tree(this):
        return False
    if op != "issue_relate":
        return True
    if change.get("remove_parent") or (change.get("parent") and not is_root(ref(change["parent"]))):
        return False  # it would leave the tree, or move under another issue
    if (change.get("add_sub_issues") or change.get("remove_sub_issues")) and not is_root(this):
        return False  # a sub-issue's own sub-issues are outside the tree
    if any(not in_tree(ref(x)) for x in change.get("add_sub_issues") or []):
        return False  # pulling an issue in from outside changes that issue
    return all(in_tree(ref(x)) for key in ("remove_sub_issues", "add_blocked_by", "remove_blocked_by")
               for x in change.get(key) or [])


def fits(m: dict, planned: dict) -> str | None:
    """Why the change list does not fit mandate ``m``, or None when it does."""
    for step in planned["steps"]:
        cls = step["class"]
        if cls not in m["classes"]:
            return f"{step['change']['op']} is a {cls} change; the mandate covers {', '.join(m['classes'])}"
        for target in step["targets"]:
            if not _in_scope(m, target):
                return f"{target['name']} is outside the mandate"
            if cls not in TIER_CAP[target["tier"]]:
                return f"{target['name']} is {target['tier']}: a mandate never covers {cls} changes there"
        try:
            if not _under_parent(m, step, planned["steps"]):
                return f"{step['change']['op']} is outside issue {m['parent']} and its sub-issues"
        except AccessError as exc:
            return f"could not check the parent: {exc}"
    return None


def covering(home, planned: dict) -> tuple[str | None, list[str]]:
    """(the id of a mandate the whole list fits, or None; why each mandate in force did not)."""
    misses = []
    for m in active(home):
        why = fits(m, planned)
        if why is None:
            return m["id"], misses
        misses.append(f"{m['id']}: {why}")
    return None, misses


def still_fits(home, mandate_id: str, planned: dict) -> str | None:
    """At write time: why the list no longer fits ``mandate_id``, or None."""
    m = next((m for m in active(home) if m["id"] == mandate_id), None)
    if m is None:
        return f"mandate {mandate_id} is no longer in force"
    return fits(m, planned)
