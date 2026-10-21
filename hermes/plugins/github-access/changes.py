"""github-access: the write side. One ``github_change`` call carries a list of changes.

Every change names an op. The ops live in the module of their domain (``ops_board.py``: drafts and
board items; ``ops_issue.py``: issues), each registered here with its keys, its plan (the targets
it reads), its card line and how it runs. This module owns what every change shares:

plan()      validates every change and reads, fresh from GitHub, the targets it writes to: each
            repository and board with its tier (own / shared / other) and the viewer's right to
            write there. Nothing is written.
card()      the approval card for a plan: one line per target with its tier, one per change.
apply()     runs a plan's changes in order and stops at the first failure, reporting what was
            done and what was not.

Each change has a class: ``routine`` (moving an item's fields, a note on a draft, archiving,
editing an issue's title or body), ``create`` (anything that makes something new, notifies
someone or closes: a draft, an issue, a comment, a relation, a label, an assignee, a milestone,
a close or reopen) or ``admin`` (what changes how a repository works or what reaches others at
once: settings, visibility, a merge, a published release, a workflow run). The plugin hook decides
from the plan whether a card is needed; mandates (mandate.py) may cover routine and create
changes on some tiers, and never an admin one.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


def _load(name, path):
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


HERE = Path(__file__).resolve().parent
access = _load("hermes_github_access_engine", HERE / "access.py")
AccessError = access.AccessError

MAX_CHANGES = 50
LINE = 140
CARD_LIMIT = 1500
CLASSES = ("routine", "create", "admin")
ADMIN = "admin"  # always asks on a card: no mandate covers it


# --- the registry ---------------------------------------------------------------------------------
# A key is one field a change may carry, with its JSON type; ``text`` marks what a change writes
# where others read it (checked for tokens and paths, its links counted on the card). An op names
# the keys it requires and takes, and the four things only it knows.

@dataclass(frozen=True)
class Key:
    type: str  # str | bool | list | map
    text: bool = False
    schema: dict = field(default_factory=dict)  # more JSON schema: an enum, a description


@dataclass(frozen=True)
class Op:
    name: str
    cls: str
    doc: str  # the tool description's words for it: its keys and what it does
    plan: Callable  # (step, Plan): read the targets into the step; nothing is written
    describe: Callable  # (step) -> the card's line
    run: Callable  # (step, out) -> the result; ``out`` holds what exists as soon as it does
    required: tuple = ()
    optional: tuple = ()
    check: Callable | None = None  # (change): more validation, before anything is read
    classify: Callable | None = None  # (change) -> a class other than ``cls``
    needs_board: Callable = lambda change: False  # whether the list's board must be resolved
    creates_issue: bool = False  # a later change may name the issue it creates as "$N"


KEYS: dict[str, Key] = {}
OPS: dict[str, Op] = {}
_TYPES = {"str": {"type": "string"}, "bool": {"type": "boolean"},
          "list": {"type": "array", "items": {"type": "string"}},
          "map": {"type": "object", "additionalProperties": {"type": "string"}}}


def key(name: str, type_: str, text: bool = False, **schema) -> None:
    """Declare a key; the same key declared again by another domain must say the same."""
    made = Key(type_, text, schema)
    if KEYS.setdefault(name, made) != made:
        raise ValueError(f"key {name} is declared twice, differently")


def register(op: Op) -> None:
    unknown = [k for k in (*op.required, *op.optional) if k not in KEYS]
    if op.name in OPS:
        raise ValueError(f"op {op.name} is registered twice")
    if op.cls not in CLASSES:
        raise ValueError(f"op {op.name} has a bad class {op.cls!r}")
    if unknown:
        raise ValueError(f"op {op.name} takes undeclared keys {', '.join(unknown)}")
    OPS[op.name] = op


def schema() -> dict:
    """The JSON schema of one change, from the declared keys and the registered ops."""
    return {"type": "object", "required": ["op"], "additionalProperties": False,
            "properties": {"op": {"type": "string", "enum": list(OPS)},
                           **{name: {**_TYPES[k.type], **k.schema} for name, k in KEYS.items()}}}


def doc() -> str:
    return ", ".join(f"{op.name} ({op.doc})" for op in OPS.values())


key("repo", "str")
key("title", "str", text=True)
key("body", "str", text=True)


# --- validation -----------------------------------------------------------------------------------

def _check_value(op: str, name: str, value) -> None:
    if value is None:
        return
    kind = KEYS[name].type
    if kind == "str":
        if not isinstance(value, str):
            raise AccessError(f"{op}: {name} must be text")
        if "\x00" in value:
            raise AccessError(f"{op}: {name} must not contain NUL")
        enum = KEYS[name].schema.get("enum")
        if enum and value not in enum:
            raise AccessError(f"{op}: {name} is one of {', '.join(enum)}")
    elif kind == "bool":
        if not isinstance(value, bool):
            raise AccessError(f"{op}: {name} is true or false")
    elif kind == "list":
        if not isinstance(value, list) or not all(isinstance(v, str) and v.strip() and "\x00" not in v for v in value):
            raise AccessError(f"{op}: {name} must be a list of text")
    elif kind == "map":
        if not isinstance(value, dict) or not all(isinstance(k, str) and isinstance(v, str) and "\x00" not in v
                                                  for k, v in value.items()):
            raise AccessError(f"{op}: {name} maps field names to text values")


def _check(change) -> dict:
    if not isinstance(change, dict):
        raise AccessError("each change is an object with an op")
    op = change.get("op")
    if op not in OPS:
        raise AccessError(f"op must be one of: {', '.join(OPS)}")
    spec = OPS[op]
    unknown = set(change) - {"op", *spec.required, *spec.optional}
    if unknown:
        raise AccessError(f"{op}: unknown keys {', '.join(sorted(unknown))}")
    for name in spec.required:
        if change.get(name) in (None, "", []):
            raise AccessError(f"{op}: {name} is required")
    for name, value in change.items():
        if name != "op":
            _check_value(op, name, value)
    if spec.check:
        spec.check(change)
    return change


def given(change: dict, name: str) -> bool:
    """Whether a change sets ``name``; an empty milestone is a request to remove it."""
    value = change.get(name)
    return value is not None and value != [] and (value != "" or name == "milestone")


def change_class(change: dict) -> str:
    spec = OPS[change["op"]]
    return spec.classify(change) if spec.classify else spec.cls


# --- plan -----------------------------------------------------------------------------------------

# A change may name the issue an earlier change of the same list creates.
EARLIER = re.compile(r"^\$(\d+)$")


class Plan:
    """The targets of one change list, each read fresh: ``targets`` across the list, ``touched``
    those of the change being planned."""

    def __init__(self, args: dict, changes: list):
        self.default_repo = access.parse_repo(args["repo"]) if args.get("repo") else None
        self.targets: dict[str, dict] = {}
        self.touched: list[dict] = []
        self.steps: list[dict] = []
        self._repos: dict[str, dict] = {}
        self._fields: dict[str, list] = {}
        self.board = None
        if any(OPS[c["op"]].needs_board(c) for c in changes):
            resolved = access.resolve_board(args.get("project") or None, args.get("owner") or None, self.default_repo)
            self.board = self.add_board(resolved["board"])
            self.touched.clear()

    def note(self, name: str, target: dict) -> None:
        target = self.targets.setdefault(name, target)
        if target not in self.touched:
            self.touched.append(target)

    def repo(self, name: str) -> dict:
        """A repository the change writes to, read fresh once per list; refused when the viewer
        cannot write there."""
        name = access.parse_repo(name)
        if name.lower() not in self._repos:
            self._repos[name.lower()] = access.repo_context(name, fresh=True)
        ctx = self._repos[name.lower()]
        if ctx["archived"]:
            raise AccessError(f"{ctx['repo']} is archived")
        if not ctx["can_write"]:
            raise AccessError(f"no write permission on {ctx['repo']} (viewer permission: {ctx['permission'] or 'none'})")
        self.note(f"repo:{ctx['repo'].lower()}", {"kind": "repo", "name": ctx["repo"], "tier": ctx["tier"], "id": ctx["id"]})
        return ctx

    def repo_of(self, change: dict) -> dict:
        """The repository a change names, else the list's."""
        if not (change.get("repo") or self.default_repo):
            raise AccessError(f"{change['op']}: repo is required (on the change or at the top)")
        return self.repo(change.get("repo") or self.default_repo)

    def add_board(self, b: dict) -> dict:
        if not b["can_update"]:
            raise AccessError(f"board {b['owner']}/{b['number']} {b['title']!r} is read-only for the viewer")
        name = f"board:{b['id']}"
        tier = self.targets[name]["tier"] if name in self.targets else access.tier(b["owner"], b["owner_type"],
                                                                                   not b["public"], fresh=True)
        self.note(name, {"kind": "board", "name": f"{b['owner']}/{b['number']} {b['title']}", "tier": tier, "id": b["id"]})
        return {**b, "tier": tier}

    def list_board(self) -> dict:
        """The board the list resolved (project / owner / repo at the top)."""
        return self.add_board(self.board)

    def fields(self, board_id: str) -> list[dict]:
        if board_id not in self._fields:
            self._fields[board_id] = access.fields(board_id)
        return self._fields[board_id]

    def earlier_repo(self, ref: str) -> str | None:
        """The repository of the issue ``$N`` names (change N of this list), or None for an ordinary ref."""
        match = EARLIER.match(ref.strip())
        if not match:
            return None
        n = int(match.group(1))
        if not 1 <= n <= len(self.steps):
            raise AccessError(f"{ref}: names change {n}, which is not an earlier change of this list")
        op = self.steps[n - 1]["change"]["op"]
        if not OPS[op].creates_issue:
            raise AccessError(f"{ref}: change {n} is a {op}, which creates no issue")
        return self.steps[n - 1]["repo"]["repo"]


def plan(args: dict) -> dict:
    """Validate a github_change call and read its targets. Raises for anything it would refuse."""
    changes = args.get("changes")
    if not isinstance(changes, list) or not changes:
        raise AccessError("changes is a non-empty list")
    if len(changes) > MAX_CHANGES:
        raise AccessError(f"at most {MAX_CHANGES} changes per call; split it")
    changes = [_check(dict(c)) if isinstance(c, dict) else _check(c) for c in changes]
    planned = Plan(args, changes)
    for change in changes:
        step = {"change": change, "class": change_class(change)}
        planned.touched.clear()
        OPS[change["op"]].plan(step, planned)
        step["targets"] = list(planned.touched)
        check_text(step)
        planned.steps.append(step)
    tiers = [t["tier"] for t in planned.targets.values()]
    strictest = max(tiers, key=access.TIERS.index) if tiers else "other"
    return {"steps": planned.steps, "targets": list(planned.targets.values()), "tier": strictest,
            "classes": sorted({s["class"] for s in planned.steps})}


def binding(planned: dict) -> list:
    """What an approval binds: every target with its tier, in order. A write whose fresh plan differs
    (another board resolved, a repository now public) is a different write and needs its own card."""
    return [[t["kind"], t["id"], t["tier"]] for t in planned["targets"]]


# --- what the words carry -------------------------------------------------------------------------
# Every text a change writes is checked before any card: a token anywhere is refused; on a target
# others can read, a path of this machine is refused with how to write it instead (the card then shows
# what will be written, so approving and writing never differ); and the card counts the links each
# change carries, the local paths, and code links that follow a branch.

TOKEN = re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|sk-[A-Za-z0-9_-]{32,}|"
                   r"xox[abprs]-[A-Za-z0-9-]{20,}|AKIA[0-9A-Z]{16})\b|-----BEGIN [A-Z ]*PRIVATE KEY-----")
_TAIL = r"[^\s`'\"()<>\[\]]*"
HOME_PATH = re.compile(rf"(?<![\w./:~-])(?:/Users|/home)/[A-Za-z0-9._-]+(?:/{_TAIL})?")
TILDE_PATH = re.compile(rf"(?<![\w/])~/{_TAIL}")
FILE_URL = re.compile(r"\bfile://\S+")
URL = re.compile(r"https?://[^\s<>()\[\]`'\"]+")
BRANCH_BLOB = re.compile(r"^https?://(?:www\.)?github\.com/[^/]+/[^/]+/blob/(?![0-9a-f]{7,40}/)[^/]+/")
HOME_VAR_PATH = re.compile(rf"\$(?:HOME\b|\{{HOME\}})/{_TAIL}")
AGENT_PATH = re.compile(rf"(?<![\w/.~-])\.agent/{_TAIL}")
_CHECKOUT = re.compile(r"^(?:ghq/[^/]+/[^/]+/[^/]+|Worktrees/[^/]+/[^/]+)/(.+)$")
_PRIVATE = re.compile(r"^(?:Workspaces(?:/|$)|(?:.*/)?\.agent(?:/|$)|.*private-dotconfig)")


def _texts(step: dict):
    """Every text the step writes: the change's own words and values, and what an op carries from
    elsewhere (``carried``: a promoted draft's title and body, read when the list is planned)."""
    change = step["change"]
    texts = [(name, k) for name, k in KEYS.items() if k.text]
    for name, _ in (t for t in texts if t[1].type == "str"):
        value = change.get(name)
        if isinstance(value, str) and value:
            yield name, value
    for name, _ in (t for t in texts if t[1].type == "list"):
        value = change.get(name)
        for item in value if isinstance(value, list) else []:
            if isinstance(item, str) and item:
                yield name, item
    for name, _ in (t for t in texts if t[1].type == "map"):
        value = change.get(name)
        for field_name, item in (value if isinstance(value, dict) else {}).items():
            if isinstance(item, str) and item:
                yield f"{name}.{field_name}", item
    yield from step.get("carried") or []


def _rewrite(path: str) -> str | None:
    """How a local path may appear where others read, or None when it may not appear at all."""
    if path.startswith(".agent/"):
        return None
    rest = re.sub(r"^(?:/Users/[^/]+|/home/[^/]+|~|\$HOME|\$\{HOME\})/?", "", path)
    if _PRIVATE.match(rest):
        return None  # private first: a checkout inside the workspace is still the workspace
    checkout = _CHECKOUT.match(rest)
    if checkout:
        return f"`{checkout.group(1)}` (the repository-relative path) or a commit permalink"
    return "" if path.startswith("~/") else f"`~/{rest}`"


def local_paths(text: str) -> list[str]:
    return [m.group() for pattern in (HOME_PATH, TILDE_PATH, HOME_VAR_PATH, AGENT_PATH, FILE_URL)
            for m in pattern.finditer(text)]


def check_text(step: dict) -> None:
    """Refuse a token anywhere, and on a target others read a path of this machine, naming the fix."""
    change = step["change"]
    shared = any(t["tier"] != "own" for t in step.get("targets") or [])
    problems = []
    for name, text in _texts(step):
        if TOKEN.search(text):
            raise AccessError(f"{change['op']}: {name} holds what looks like a token or a private key; take it out "
                              "(never write a secret anywhere on GitHub)")
        if not shared:
            continue
        for path in local_paths(text):
            if path.startswith("file://"):
                problems.append(f"{name}: {say(path, 80)} → link the file in its repository, or say in words what it is")
                continue
            fix = _rewrite(path)
            if fix is None:
                problems.append(f"{name}: {say(path, 80)} → a private working path: say in words what the file is")
            elif fix:
                problems.append(f"{name}: {say(path, 80)} → {fix}")
    if problems:
        raise AccessError(f"{change['op']}: others can read this target, so its text cannot carry this machine's "
                          "paths. Rewrite: " + "; ".join(problems[:6]) + (f" (+{len(problems) - 6} more)"
                                                                          if len(problems) > 6 else ""))


def _hosts(planned: dict) -> tuple[dict, int, int]:
    """{host: [change numbers]}, local paths and branch-following code links across the list."""
    hosts: dict[str, list[int]] = {}
    paths = branch = 0
    for i, step in enumerate(planned["steps"], 1):
        for _, text in _texts(step):
            for url in URL.findall(text):
                host = re.sub(r"^www\.", "", url.split("/")[2].split("@")[-1].split(":")[0].lower())
                if i not in hosts.setdefault(host, []):
                    hosts[host].append(i)
                branch += bool(BRANCH_BLOB.match(url))
            paths += len(local_paths(text))
    return hosts, paths, branch


# --- the card -------------------------------------------------------------------------------------

_INVISIBLE = re.compile(r"[\u0000-\u001f\u007f-\u009f\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff]")


def say(value, limit: int = LINE) -> str:
    """One card-safe line: whitespace collapsed, control, bidi and invisible characters spelled out."""
    text = " ".join(str(value or "").split())
    text = _INVISIBLE.sub(lambda m: f"⟨U+{ord(m.group()):04X}⟩", text)
    text = "".join(ch if unicodedata.category(ch) != "Cf" else f"⟨U+{ord(ch):04X}⟩" for ch in text)
    return text if len(text) <= limit else text[:limit - 1] + "…"


def card(planned: dict) -> str:
    n = len(planned["steps"])
    lines = [f"GitHub · {n} change{'s' if n != 1 else ''}"]
    for t in planned["targets"]:
        mark = {"own": "own, private", "shared": "others can read it", "other": "⚠️ someone else's"}[t["tier"]]
        kind = {"repo": "Repository", "owner": "New board for", "template": "Copied from"}.get(t["kind"], "Board")
        lines.append(f"{kind}: {say(t['name'], 80)} ({mark})")
    hosts, paths, branch = _hosts(planned)
    if hosts:
        shown_hosts = [f"{h} ({', '.join(map(str, at))})" for h, at in sorted(hosts.items(), key=lambda kv: kv[1][0])]
        lines.append(say("Links to: " + ", ".join(shown_hosts), LINE))
    if paths:
        lines.append(f"Local paths in the text: {paths}")
    if branch:
        lines.append(f"⚠️ Code links that follow a branch (their content can change): {branch}")
    admin = [i for i, step in enumerate(planned["steps"], 1) if step["class"] == ADMIN]
    if admin:
        lines.append(say(f"⚠️ Admin changes, never covered by a mandate: {', '.join(map(str, admin))}", LINE))
    lines.append("")
    shown = 0
    for i, step in enumerate(planned["steps"], 1):
        mark = "⚠️ " if step["class"] == ADMIN else ""
        line = f"{i}. {mark}{say(OPS[step['change']['op']].describe(step), LINE)}"
        if sum(len(l) + 1 for l in lines) + len(line) > CARD_LIMIT - 40:
            lines.append(f"(+{n - shown} more changes)")
            break
        lines.append(line)
        shown += 1
    return "\n".join(lines)


# --- apply ----------------------------------------------------------------------------------------

def gh(argv, stdin=None) -> str:
    done = access.run_gh(argv, stdin=stdin)
    if done.returncode != 0:
        detail = (done.stderr or done.stdout or "").strip().splitlines()
        raise AccessError(f"gh {' '.join(argv[:3])} failed: {detail[-1] if detail else f'exit {done.returncode}'}"[:400])
    return done.stdout


def gh_json(argv) -> dict:
    try:
        return json.loads(gh(argv) or "{}")
    except json.JSONDecodeError as exc:
        raise AccessError(f"gh {' '.join(argv[:3])} printed no JSON") from exc


UNCERTAIN = re.compile(r"did not answer within|timed out|timeout|connection reset|EOF|502|503|504", re.IGNORECASE)


def apply(planned: dict) -> dict:
    """Run the changes in order; stop at the first failure. A failed change reports what of it already
    exists (``partial``), and one whose failure may have happened after GitHub acted is ``uncertain``:
    read before sending anything again. ``created`` maps a change's number to the issue it made, for
    the ``$N`` of a later change."""
    done, failed = [], None
    created: dict[int, tuple[str, int]] = {}
    for i, step in enumerate(planned["steps"]):
        out: dict = {}
        try:
            done.append({"op": step["change"]["op"], **OPS[step["change"]["op"]].run({**step, "created": created}, out)})
            if out.get("issue"):
                created[i + 1] = access.parse_issue(out["issue"])
        except Exception as exc:
            failed = {"index": i, "op": step["change"]["op"], "error": str(exc), "partial": out,
                      "uncertain": bool(UNCERTAIN.search(str(exc)))}
            break
    rest = [s["change"]["op"] for s in planned["steps"][len(done) + (1 if failed else 0):]]
    return {"ok": failed is None, "done": done, "failed": failed, "not_done": rest}


# --- the domains ----------------------------------------------------------------------------------
# Loaded last: each registers its keys and ops here. The order is the order of the op enum. A domain
# reaches this module by its one name, so a copy loaded under another name would stay empty.

NAME = "hermes_github_access_changes"
if __name__ != NAME:
    raise ImportError(f"load changes.py as {NAME}: the op modules register into that module")
for _domain in ("board", "issue"):
    _load(f"hermes_github_access_ops_{_domain}", HERE / f"ops_{_domain}.py")
