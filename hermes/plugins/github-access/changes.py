"""github-access: the write side. One ``github_change`` call carries a list of changes.

plan()      validates every change and reads, fresh from GitHub, the targets it writes to: each
            repository and board with its tier (own / shared / other) and the viewer's right to
            write there. Nothing is written.
card()      the approval card for a plan: one line per target with its tier, one per change.
apply()     runs a plan's changes in order and stops at the first failure, reporting what was
            done and what was not.

Each change has a class: ``routine`` (moving an item's fields, a note on a draft, archiving,
editing an issue's title or body) or ``create`` (anything that makes something new, notifies
someone or closes: a draft, an issue, a comment, a relation, a label, an assignee, a milestone,
a close or reopen). The plugin hook decides from the plan whether a card is needed; mandates
(mandate.py) may cover some classes on some tiers.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import unicodedata
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

MAX_CHANGES = 50
REASONS = ("completed", "not planned", "duplicate")
LINE = 140
CARD_LIMIT = 1500

# op -> (class, target kind, required keys, optional keys)
OPS = {
    "draft_add": ("create", "board", ("title",), ("body", "fields")),
    "draft_note": ("routine", "item", ("item", "text"), ()),
    "draft_edit": ("routine", "item", ("item",), ("title", "body")),
    "item_add": ("create", "board", ("url",), ("fields",)),
    "item_set": ("routine", "item", ("item",), ("fields", "clear")),
    "item_archive": ("routine", "item", ("item",), ("restore",)),
    "draft_promote": ("create", "item+repo", ("item",), ("repo", "kind", "labels", "milestone", "create_milestone")),
    "issue_create": ("create", "repo", ("title",), ("repo", "body", "kind", "labels", "assignees", "milestone",
                                                    "create_milestone", "parent", "blocked_by", "board_fields")),
    "issue_edit": ("routine", "issue", ("issue",), ("title", "body", "append_body", "kind", "add_labels",
                                                    "remove_labels", "add_assignees", "remove_assignees", "milestone",
                                                    "create_milestone")),
    "issue_comment": ("create", "issue", ("issue", "body"), ()),
    "issue_relate": ("create", "issue", ("issue",), ("parent", "remove_parent", "add_sub_issues", "remove_sub_issues",
                                                     "add_blocked_by", "remove_blocked_by")),
    "issue_close": ("create", "issue", ("issue", "reason"), ("comment",)),
    "issue_reopen": ("create", "issue", ("issue",), ()),
}
# An issue edit that touches more than its own words notifies people or changes how it is filed.
EDIT_NOTIFIES = ("kind", "add_labels", "remove_labels", "add_assignees", "remove_assignees", "milestone")


# --- validation -----------------------------------------------------------------------------------

def _str(change: dict, key: str, required: bool = False) -> str:
    value = change.get(key)
    if value is None or value == "":
        if required:
            raise AccessError(f"{change.get('op')}: {key} is required")
        return ""
    if not isinstance(value, str):
        raise AccessError(f"{change.get('op')}: {key} must be text")
    if "\x00" in value:
        raise AccessError(f"{change.get('op')}: {key} must not contain NUL")
    return value


def _list(change: dict, key: str) -> list[str]:
    value = change.get(key) or []
    if not isinstance(value, list) or not all(isinstance(v, str) and v.strip() for v in value):
        raise AccessError(f"{change.get('op')}: {key} must be a list of text")
    return [v.strip() for v in value]


def _fields(change: dict, key: str) -> dict:
    value = change.get(key) or {}
    if not isinstance(value, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in value.items()):
        raise AccessError(f"{change.get('op')}: {key} maps field names to text values")
    return value


def _given(change: dict, key: str) -> bool:
    """Whether a change sets ``key``; an empty milestone is a request to remove it."""
    value = change.get(key)
    return value is not None and value != [] and (value != "" or key == "milestone")


def _check(change) -> dict:
    if not isinstance(change, dict):
        raise AccessError("each change is an object with an op")
    op = change.get("op")
    if op not in OPS:
        raise AccessError(f"op must be one of: {', '.join(OPS)}")
    _, _, required, optional = OPS[op]
    unknown = set(change) - {"op", *required, *optional}
    if unknown:
        raise AccessError(f"{op}: unknown keys {', '.join(sorted(unknown))}")
    for key in required:
        if change.get(key) in (None, "", []):
            raise AccessError(f"{op}: {key} is required")
    if op == "issue_close" and change["reason"] not in REASONS:
        raise AccessError(f"issue_close: reason is one of {', '.join(REASONS)}")
    if op == "issue_edit":
        if change.get("body") is not None and change.get("append_body") is not None:
            raise AccessError("issue_edit: body or append_body, not both")
        if not any(_given(change, k) for k in OPS[op][3] if k != "create_milestone"):
            raise AccessError("issue_edit: nothing to change")
    if op == "issue_relate":
        if change.get("parent") and change.get("remove_parent"):
            raise AccessError("issue_relate: parent or remove_parent, not both")
        if not any(change.get(k) for k in OPS[op][3]):
            raise AccessError("issue_relate: nothing to change")
    if op == "item_set" and not (change.get("fields") or change.get("clear")):
        raise AccessError("item_set: fields or clear is required")
    if op == "draft_edit" and change.get("title") is None and change.get("body") is None:
        raise AccessError("draft_edit: title or body is required")
    for key in ("fields", "board_fields"):
        if key in change:
            _fields(change, key)
    for key in ("labels", "assignees", "blocked_by", "add_labels", "remove_labels", "add_assignees",
                "remove_assignees", "add_sub_issues", "remove_sub_issues", "add_blocked_by", "remove_blocked_by", "clear"):
        if key in change:
            _list(change, key)
    for key in ("create_milestone", "remove_parent", "restore"):
        if key in change and not isinstance(change[key], bool):
            raise AccessError(f"{op}: {key} is true or false")
    for key, value in change.items():
        if isinstance(value, str) and "\x00" in value:
            raise AccessError(f"{op}: {key} must not contain NUL")
    return change


MENTION = re.compile(r"(?<![\w`/.@-])@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:/[A-Za-z0-9_.-]+)?")


def change_class(change: dict) -> str:
    cls = OPS[change["op"]][0]
    if change["op"] == "issue_edit":
        if any(_given(change, k) for k in EDIT_NOTIFIES):
            return "create"
        # A mention in an issue's own words notifies the person or team it names.
        if any(MENTION.search(change.get(k) or "") for k in ("title", "body", "append_body")):
            return "create"
    return cls


# --- plan -----------------------------------------------------------------------------------------

ITEM_QUERY = ("query($id:ID!){node(id:$id){... on ProjectV2Item{id isArchived project{" + access.PROJECT_FIELDS + "} "
              "content{__typename ... on DraftIssue{id title body} ... on Issue{number url repository{nameWithOwner}} "
              "... on PullRequest{number url repository{nameWithOwner}}}}}}")


def _item(item_id: str) -> dict:
    node = access.graphql(ITEM_QUERY, {"id": item_id}).get("node") or {}
    if not node.get("id"):
        raise AccessError(f"board item {item_id} not found")
    content = node.get("content") or {}
    return {"id": node["id"], "archived": bool(node.get("isArchived")), "board": access._board(node["project"], fresh=True),
            "content_type": content.get("__typename"), "draft_id": content.get("id") if content.get("__typename") == "DraftIssue" else None,
            "body": content.get("body") or "", "title": content.get("title") or ""}


# issue_create's parent and blocked_by may name an issue an earlier change of the same list creates.
EARLIER = re.compile(r"^\$(\d+)$")


def _earlier_repo(ref: str, steps: list) -> str | None:
    """The repository of the issue ``$N`` names (change N of this list), or None for an ordinary ref."""
    match = EARLIER.match(ref.strip())
    if not match:
        return None
    n = int(match.group(1))
    if not 1 <= n <= len(steps):
        raise AccessError(f"{ref}: names change {n}, which is not an earlier change of this list")
    if steps[n - 1]["change"]["op"] not in ("issue_create", "draft_promote"):
        raise AccessError(f"{ref}: change {n} is a {steps[n - 1]['change']['op']}, which creates no issue")
    return steps[n - 1]["repo"]["repo"]


def plan(args: dict) -> dict:
    """Validate a github_change call and read its targets. Raises for anything it would refuse."""
    changes = args.get("changes")
    if not isinstance(changes, list) or not changes:
        raise AccessError("changes is a non-empty list")
    if len(changes) > MAX_CHANGES:
        raise AccessError(f"at most {MAX_CHANGES} changes per call; split it")
    changes = [_check(dict(c)) for c in changes]
    default_repo = access.parse_repo(args["repo"]) if args.get("repo") else None
    board = None
    needs_board = any(OPS[c["op"]][1] == "board" or "board_fields" in c for c in changes)
    targets: dict[str, dict] = {}
    touched: list[dict] = []  # the targets of the step being planned

    def note(key, target):
        target = targets.setdefault(key, target)
        if target not in touched:
            touched.append(target)

    repos_read: dict[str, dict] = {}

    def add_repo(name):
        name = access.parse_repo(name)
        if name.lower() not in repos_read:
            repos_read[name.lower()] = access.repo_context(name, fresh=True)
        ctx = repos_read[name.lower()]
        if ctx["archived"]:
            raise AccessError(f"{ctx['repo']} is archived")
        if not ctx["can_write"]:
            raise AccessError(f"no write permission on {ctx['repo']} (viewer permission: {ctx['permission'] or 'none'})")
        note(f"repo:{ctx['repo'].lower()}", {"kind": "repo", "name": ctx["repo"], "tier": ctx["tier"], "id": ctx["id"]})
        return ctx

    def add_board(b):
        if not b["can_update"]:
            raise AccessError(f"board {b['owner']}/{b['number']} {b['title']!r} is read-only for the viewer")
        key = f"board:{b['id']}"
        tier = targets[key]["tier"] if key in targets else access.tier(b["owner"], b["owner_type"], not b["public"], fresh=True)
        note(key, {"kind": "board", "name": f"{b['owner']}/{b['number']} {b['title']}", "tier": tier, "id": b["id"]})
        return {**b, "tier": tier}

    if needs_board:
        resolved = access.resolve_board(args.get("project") or None, args.get("owner") or None, default_repo)
        board = add_board(resolved["board"])
        touched.clear()
    board_fields = {}
    steps = []
    for change in changes:
        op, kind = change["op"], OPS[change["op"]][1]
        step = {"change": change, "class": change_class(change)}
        touched.clear()
        if kind == "board":
            step["board"] = add_board(board)
            if op == "item_add":
                # Putting an issue or PR on a board writes only the board, wherever the issue lives.
                url = change["url"].strip()
                repo, number = access.parse_issue(url, default_repo, allow_pr=True)
                kind_ = "pull" if "/pull/" in url else "issues"
                step["url"] = f"https://github.com/{repo}/{kind_}/{number}"
        elif kind in ("item", "item+repo"):
            it = _item(change["item"])
            step["item"] = it
            step["board"] = add_board(it["board"])
            if op in ("draft_note", "draft_edit", "draft_promote") and it["content_type"] != "DraftIssue":
                raise AccessError(f"{op}: item {change['item']} is not a draft; edit its issue instead")
            if kind == "item+repo":
                if not (change.get("repo") or default_repo):
                    raise AccessError(f"{op}: repo is required (on the change or at the top)")
                step["repo"] = add_repo(change.get("repo") or default_repo)
                # Promoting publishes the draft's words where the repository's readers see them: its
                # title and body as they will be then, after the earlier edits and notes of this list.
                title, body = it["title"], it["body"]
                for prior in steps:
                    p = prior["change"]
                    if p.get("item") != change["item"]:
                        continue
                    if p["op"] == "draft_edit":
                        title = p["title"] if p.get("title") is not None else title
                        body = p["body"] if p.get("body") is not None else body
                    elif p["op"] == "draft_note":
                        body = f"{body.rstrip()}\n\n{p['text'].strip()}\n" if body.strip() else f"{p['text'].strip()}\n"
                step["carried"] = [("draft title", title), ("draft body", body)]
        elif kind == "repo":
            if not (change.get("repo") or default_repo):
                raise AccessError(f"{op}: repo is required (on the change or at the top)")
            step["repo"] = add_repo(change.get("repo") or default_repo)
            for ref in [change.get("parent"), *(change.get("blocked_by") or [])]:
                if ref:
                    add_repo(_earlier_repo(ref, steps) or access.parse_issue(ref, step["repo"]["repo"])[0])
            if "board_fields" in change:
                step["board"] = add_board(board)
        elif kind == "issue":
            repo, number = access.parse_issue(change["issue"], default_repo)
            step["repo"] = add_repo(repo)
            step["number"] = number
            for key in ("parent", "add_sub_issues", "remove_sub_issues", "add_blocked_by", "remove_blocked_by"):
                refs = change.get(key)
                for ref in ([refs] if isinstance(refs, str) else refs or []):
                    add_repo(access.parse_issue(ref, repo)[0])
            if op == "issue_relate" and (change.get("parent") or change.get("remove_parent")):
                # Replacing or removing a parent also changes the old parent's sub-issue list.
                current = access.issue(repo, number, comments=0).get("parent")
                if current:
                    add_repo(current["repo"])
        for key in ("fields", "board_fields"):
            if change.get(key):
                b = step["board"]
                if b["id"] not in board_fields:
                    board_fields[b["id"]] = access.fields(b["id"])
                check_fields(board_fields[b["id"]], change[key], change.get("clear") or [])
        if op == "item_set" and change.get("clear") and not change.get("fields"):
            b = step["board"]
            if b["id"] not in board_fields:
                board_fields[b["id"]] = access.fields(b["id"])
            check_fields(board_fields[b["id"]], {}, change["clear"])
        step["targets"] = list(touched)
        check_text(step)
        steps.append(step)
    tiers = [t["tier"] for t in targets.values()]
    strictest = max(tiers, key=access.TIERS.index) if tiers else "other"
    return {"steps": steps, "targets": list(targets.values()), "tier": strictest,
            "classes": sorted({s["class"] for s in steps})}


# --- what the words carry -------------------------------------------------------------------------
# Every text a change writes is checked before any card: a token anywhere is refused; on a target
# others can read, a path of this machine is refused with how to write it instead (the card then shows
# what will be written, so approving and writing never differ); and the card counts the links each
# change carries, the local paths, and code links that follow a branch.

TEXT_KEYS = ("title", "body", "text", "append_body", "comment")
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
# Single values a change writes besides its words: a kind lands as a label and its description, a
# milestone title may be created, labels and board field values are shown to every reader.
VALUE_KEYS = ("kind", "milestone")
LIST_KEYS = ("labels", "add_labels")
MAP_KEYS = ("fields", "board_fields")


def _texts(step: dict):
    """Every text the step writes: the change's own words and values, and for a promotion the draft's
    title and body it publishes (``carried``, read when the list is planned)."""
    change = step["change"]
    for key in (*TEXT_KEYS, *VALUE_KEYS):
        value = change.get(key)
        if isinstance(value, str) and value:
            yield key, value
    for key in LIST_KEYS:
        for value in change.get(key) or []:
            if isinstance(value, str) and value:
                yield key, value
    for key in MAP_KEYS:
        for name, value in (change.get(key) or {}).items():
            if isinstance(value, str) and value:
                yield f"{key}.{name}", value
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
    for key, text in _texts(step):
        if TOKEN.search(text):
            raise AccessError(f"{change['op']}: {key} holds what looks like a token or a private key; take it out "
                              "(never write a secret anywhere on GitHub)")
        if not shared:
            continue
        for path in local_paths(text):
            if path.startswith("file://"):
                problems.append(f"{key}: {say(path, 80)} → link the file in its repository, or say in words what it is")
                continue
            fix = _rewrite(path)
            if fix is None:
                problems.append(f"{key}: {say(path, 80)} → a private working path: say in words what the file is")
            elif fix:
                problems.append(f"{key}: {say(path, 80)} → {fix}")
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


def binding(planned: dict) -> list:
    """What an approval binds: every target with its tier, in order. A write whose fresh plan differs
    (another board resolved, a repository now public) is a different write and needs its own card."""
    return [[t["kind"], t["id"], t["tier"]] for t in planned["targets"]]


def check_fields(fields: list[dict], values: dict, clear: list[str]) -> None:
    """Refuse, before anything is written, a field the board lacks, a built-in, an unknown option
    or a malformed date."""
    for name in [*values, *clear]:
        f = next((f for f in fields if access.same(f["name"], name)), None)
        if not f:
            raise AccessError(f"no field {name!r} on the board; fields: {', '.join(x['name'] for x in fields)}")
        if f["type"] not in ("SINGLE_SELECT", "TEXT", "NUMBER", "DATE", "ITERATION"):
            raise AccessError(f"{f['name']!r} is a built-in field; change it on the issue")
        if name not in values:
            continue
        value = values[name]
        if f["type"] == "SINGLE_SELECT" and not any(access.same(o["name"], value) for o in f["options"] or []):
            raise AccessError(f"{f['name']!r} has no option {value!r}; options: {', '.join(o['name'] for o in f['options'] or [])}")
        if f["type"] == "ITERATION" and not any(access.same(i["title"], value) for i in f["iterations"] or []):
            raise AccessError(f"{f['name']!r} has no iteration {value!r}")
        if f["type"] == "DATE" and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise AccessError(f"{f['name']!r} takes a date as YYYY-MM-DD")
        if f["type"] == "NUMBER" and not re.fullmatch(r"-?\d+(\.\d+)?", value):
            raise AccessError(f"{f['name']!r} takes a number")


# --- the card -------------------------------------------------------------------------------------

_INVISIBLE = re.compile(r"[\u0000-\u001f\u007f-\u009f\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff]")


def say(value, limit: int = LINE) -> str:
    """One card-safe line: whitespace collapsed, control, bidi and invisible characters spelled out."""
    text = " ".join(str(value or "").split())
    text = _INVISIBLE.sub(lambda m: f"⟨U+{ord(m.group()):04X}⟩", text)
    text = "".join(ch if unicodedata.category(ch) != "Cf" else f"⟨U+{ord(ch):04X}⟩" for ch in text)
    return text if len(text) <= limit else text[:limit - 1] + "…"


def _issue_ref(step: dict) -> str:
    return f"{step['repo']['repo']}#{step['number']}"


def _describe(step: dict) -> str:
    c = step["change"]
    op = c["op"]
    if op == "draft_add":
        fields = ", ".join(f"{k}={v}" for k, v in (c.get("fields") or {}).items())
        return f"Add draft {say(c['title'], 70)!s}" + (f" ({say(fields, 50)})" if fields else "")
    if op == "draft_note":
        return f"Note on draft {say(step['item']['title'], 40)}: {say(c['text'], 80)}"
    if op == "draft_edit":
        parts = [f"title → {say(c['title'], 50)}" if c.get("title") is not None else "",
                 f"body → {say(c['body'], 60)}" if c.get("body") is not None else ""]
        return f"Edit draft {say(step['item']['title'], 40)}: " + "; ".join(p for p in parts if p)
    if op == "item_add":
        return f"Put {c['url'].removeprefix('https://github.com/')} on the board" + (
            f" ({say(', '.join(f'{k}={v}' for k, v in c['fields'].items()), 50)})" if c.get("fields") else "")
    if op == "item_set":
        what = [f"{k}={v}" for k, v in (c.get("fields") or {}).items()] + [f"{k} cleared" for k in c.get("clear") or []]
        return f"Set {say(step['item']['title'] or c['item'], 40)}: {say(', '.join(what), 80)}"
    if op == "item_archive":
        return f"{'Restore' if c.get('restore') else 'Archive'} {say(step['item']['title'] or c['item'], 60)}"
    if op == "draft_promote":
        return f"Turn draft {say(step['item']['title'], 50)} into an issue in {step['repo']['repo']}"
    if op == "issue_create":
        named = lambda ref: EARLIER.sub(r"change \1's issue", ref.strip())  # noqa: E731
        extra = [f"kind {c['kind']}" if c.get("kind") else "", f"parent {named(c['parent'])}" if c.get("parent") else "",
                 f"after {', '.join(map(named, c['blocked_by']))}" if c.get("blocked_by") else "",
                 f"milestone {c['milestone']}" if c.get("milestone") else "",
                 f"assign {', '.join(c['assignees'])}" if c.get("assignees") else ""]
        extra = [e for e in extra if e]
        return f"Create issue in {step['repo']['repo']}: {say(c['title'], 60)}" + (f" ({say('; '.join(extra), 60)})" if extra else "")
    if op == "issue_edit":
        parts = []
        if c.get("title") is not None:
            parts.append(f"title → {say(c['title'], 50)}")
        if c.get("body") is not None:
            parts.append(f"body replaced ({len(c['body'])} chars)")
        if c.get("append_body"):
            parts.append(f"append: {say(c['append_body'], 60)}")
        for key in EDIT_NOTIFIES:
            if _given(c, key):
                value = c[key] if isinstance(c[key], str) else ", ".join(c[key])
                parts.append("milestone removed" if key == "milestone" and value == "" else
                             f"{key.replace('_', ' ')} {say(value, 40)}")
        return f"Edit {_issue_ref(step)}: " + "; ".join(parts)
    if op == "issue_comment":
        return f"Comment on {_issue_ref(step)}: {say(c['body'], 90)}"
    if op == "issue_relate":
        parts = []
        if c.get("parent"):
            parts.append(f"parent → {c['parent']}")
        if c.get("remove_parent"):
            parts.append("remove parent")
        for key in ("add_sub_issues", "remove_sub_issues", "add_blocked_by", "remove_blocked_by"):
            if c.get(key):
                parts.append(f"{key.replace('_', ' ')} {', '.join(c[key])}")
        return f"Relate {_issue_ref(step)}: {say('; '.join(parts), 100)}"
    if op == "issue_close":
        return f"Close {_issue_ref(step)} as {c['reason']}" + (f", saying: {say(c['comment'], 70)}" if c.get("comment") else "")
    if op == "issue_reopen":
        return f"Reopen {_issue_ref(step)}"
    return op


def card(planned: dict) -> str:
    n = len(planned["steps"])
    lines = [f"GitHub · {n} change{'s' if n != 1 else ''}"]
    for t in planned["targets"]:
        mark = {"own": "own, private", "shared": "others can read it", "other": "⚠️ someone else's"}[t["tier"]]
        lines.append(f"{'Repository' if t['kind'] == 'repo' else 'Board'}: {say(t['name'], 80)} ({mark})")
    hosts, paths, branch = _hosts(planned)
    if hosts:
        shown_hosts = [f"{h} ({', '.join(map(str, at))})" for h, at in sorted(hosts.items(), key=lambda kv: kv[1][0])]
        lines.append(say("Links to: " + ", ".join(shown_hosts), LINE))
    if paths:
        lines.append(f"Local paths in the text: {paths}")
    if branch:
        lines.append(f"⚠️ Code links that follow a branch (their content can change): {branch}")
    lines.append("")
    shown = 0
    for i, step in enumerate(planned["steps"], 1):
        line = f"{i}. {say(_describe(step), LINE)}"
        if sum(len(l) + 1 for l in lines) + len(line) > CARD_LIMIT - 40:
            lines.append(f"(+{n - shown} more changes)")
            break
        lines.append(line)
        shown += 1
    return "\n".join(lines)


# --- apply ----------------------------------------------------------------------------------------

def _gh(argv, stdin=None) -> str:
    done = access.run_gh(argv, stdin=stdin)
    if done.returncode != 0:
        detail = (done.stderr or done.stdout or "").strip().splitlines()
        raise AccessError(f"gh {' '.join(argv[:3])} failed: {detail[-1] if detail else f'exit {done.returncode}'}"[:400])
    return done.stdout


def _json(argv) -> dict:
    try:
        return json.loads(_gh(argv) or "{}")
    except json.JSONDecodeError as exc:
        raise AccessError(f"gh {' '.join(argv[:3])} printed no JSON") from exc


def _set_fields(board: dict, item_id: str, values: dict, clear: list[str]) -> list[str]:
    fields = access.fields(board["id"])
    applied = []

    def field(name):
        f = next((f for f in fields if access.same(f["name"], name)), None)
        if not f:
            raise AccessError(f"no field {name!r} on the board; fields: {', '.join(x['name'] for x in fields)}")
        if f["type"] not in ("SINGLE_SELECT", "TEXT", "NUMBER", "DATE", "ITERATION"):
            raise AccessError(f"{f['name']!r} is a built-in field; change it on the issue")
        return f
    base = ["project", "item-edit", "--id", item_id, "--project-id", board["id"]]
    for name, value in values.items():
        f = field(name)
        argv = [*base, "--field-id", f["id"]]
        if f["type"] == "SINGLE_SELECT":
            opt = next((o for o in f["options"] or [] if access.same(o["name"], value)), None)
            if not opt:
                raise AccessError(f"{f['name']!r} has no option {value!r}; options: {', '.join(o['name'] for o in f['options'] or [])}")
            argv += ["--single-select-option-id", opt["id"]]
        elif f["type"] == "ITERATION":
            it = next((i for i in f["iterations"] or [] if access.same(i["title"], value)), None)
            if not it:
                raise AccessError(f"{f['name']!r} has no iteration {value!r}")
            argv += ["--iteration-id", it["id"]]
        elif f["type"] == "NUMBER":
            argv += ["--number", value]
        elif f["type"] == "DATE":
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                raise AccessError(f"{f['name']!r} takes a date as YYYY-MM-DD")
            argv += ["--date", value]
        else:
            argv += ["--text", value]
        _gh(argv)
        applied.append(f["name"])
    for name in clear:
        f = field(name)
        _gh([*base, "--field-id", f["id"], "--clear"])
        applied.append(f"{f['name']} (cleared)")
    return applied


def _milestone(repo: str, title: str, create: bool) -> str:
    pages = _json(["api", "--paginate", "--slurp", f"repos/{repo}/milestones?state=all&per_page=100"])
    found = next((m for page in pages for m in page if access.same(m.get("title"), title)), None)
    if found:
        return found["title"]
    if not create:
        raise AccessError(f"no milestone {title!r} in {repo}; set create_milestone to make it")
    return _json(["api", f"repos/{repo}/milestones", "-f", f"title={title}"])["title"]


def _url(repo: str, number: int) -> str:
    return f"https://github.com/{repo}/issues/{number}"


def _ref_url(ref: str, repo: str, created: dict | None = None) -> str:
    """The URL of an issue reference; ``$N`` is the issue change N of this list created
    (``created``: change number -> (repo, number), filled by ``apply``)."""
    match = EARLIER.match(ref.strip())
    if match:
        if int(match.group(1)) not in (created or {}):
            raise AccessError(f"{ref}: change {match.group(1)} created no issue")
        r, n = created[int(match.group(1))]
    else:
        r, n = access.parse_issue(ref, repo)
    return _url(r, n)


def _short(url: str) -> str:
    r, n = access.parse_issue(url)
    return f"{r}#{n}"


KIND_COLORS = {"feature": "0E8A16", "enhancement": "1D76DB", "bug": "D73A4A", "task": "6F42C1", "chore": "BFD4F2",
               "docs": "0075CA", "test": "FBCA04", "design": "E99695"}


def _apply_kind(repo: str, number: int, kind: str) -> str:
    """The kind lands as the organization's Issue Type when it defines one, else a type:<kind> label;
    the other type:* labels come off."""
    kind = kind.strip()
    match = next((t for t in access.issue_types(repo) if access.same(t, kind)), None)
    current = _json(["issue", "view", str(number), "--repo", repo, "--json", "labels"]).get("labels") or []
    stale = [l["name"] for l in current if l["name"].lower().startswith(access.LABEL_PREFIX)]
    if match:
        _gh(["issue", "edit", str(number), "--repo", repo, "--type", match])
        landed = f"type {match}"
    else:
        label = f"{access.LABEL_PREFIX}{kind.lower()}"
        stale = [l for l in stale if not access.same(l, label)]
        listed = json.loads(_gh(["label", "list", "--repo", repo, "--search", label, "--json", "name", "--limit", "100"]) or "[]")
        names = [l["name"] for l in listed]
        if not any(access.same(n, label) for n in names):
            _gh(["label", "create", label, "--repo", repo, "--color", KIND_COLORS.get(kind.lower(), "EDEDED"),
                 "--description", f"Kind: {kind}"])
        _gh(["issue", "edit", str(number), "--repo", repo, "--add-label", label])
        landed = f"label {label}"
    for label in stale:
        _gh(["issue", "edit", str(number), "--repo", repo, "--remove-label", label])
    return landed


def _relate(repo: str, number: int, change: dict, done: list[str]) -> list[str]:
    current = access.issue(repo, number, comments=0)
    key = lambda b: f"{b['repo'].lower()}#{b['number']}"  # noqa: E731
    target = lambda ref: access.parse_issue(ref, repo)  # noqa: E731
    if change.get("parent"):
        r, n = target(change["parent"])
        if not current["parent"] or key(current["parent"]) != f"{r.lower()}#{n}":
            _gh(["issue", "edit", str(number), "--repo", repo, "--parent", _url(r, n)])
            done.append(f"parent {r}#{n}")
    if change.get("remove_parent") and current["parent"]:
        _gh(["issue", "edit", str(number), "--repo", repo, "--remove-parent"])
        done.append("parent removed")
    needs_deps = any(change.get(k) for k in ("add_blocked_by", "remove_blocked_by"))
    if needs_deps and current["dependencies_error"]:
        raise AccessError(f"the issue's dependencies could not be read: {current['dependencies_error']}")
    for add_key, remove_key, have, flags in (
            ("add_sub_issues", "remove_sub_issues", current["sub_issues"], ("--add-sub-issue", "--remove-sub-issue")),
            ("add_blocked_by", "remove_blocked_by", current["blocked_by"], ("--add-blocked-by", "--remove-blocked-by"))):
        present = {key(b) for b in have}
        for ref in change.get(add_key) or []:
            r, n = target(ref)
            if f"{r.lower()}#{n}" not in present:
                _gh(["issue", "edit", str(number), "--repo", repo, flags[0], _url(r, n)])
                done.append(f"{add_key.replace('_', ' ')} {r}#{n}")
        for ref in change.get(remove_key) or []:
            r, n = target(ref)
            if f"{r.lower()}#{n}" in present:
                _gh(["issue", "edit", str(number), "--repo", repo, flags[1], _url(r, n)])
                done.append(f"{remove_key.replace('_', ' ')} {r}#{n}")
    return done


def _number(url_out: str) -> int:
    match = re.search(r"/issues/(\d+)\s*$", url_out.strip())
    if not match:
        raise AccessError(f"gh printed no issue URL: {url_out.strip()[:200]}")
    return int(match.group(1))


def _run_step(step: dict, out: dict) -> dict:
    """Run one change, recording in ``out`` what exists as soon as it does, so a failure later in the
    same change still reports it."""
    c = step["change"]
    op = c["op"]
    if op == "draft_add":
        b = step["board"]
        argv = ["project", "item-create", str(b["number"]), "--owner", b["owner"], "--title", c["title"], "--format", "json"]
        if c.get("body"):
            argv += ["--body", c["body"]]
        item_id = _json(argv).get("id")
        if not item_id:
            raise AccessError("gh project item-create returned no item")
        out["item"] = item_id
        out["fields"] = _set_fields(b, item_id, c.get("fields") or {}, []) if c.get("fields") else []
        return out
    if op == "draft_note":
        # Read now, not at plan time: an earlier change of this list (or a person) may have changed it.
        current = _item(c["item"])["body"].rstrip()
        body = f"{current}\n\n{c['text'].strip()}\n" if current else f"{c['text'].strip()}\n"
        _gh(["project", "item-edit", "--id", step["item"]["draft_id"], "--body", body])
        out["item"] = c["item"]
        return out
    if op == "draft_edit":
        argv = ["project", "item-edit", "--id", step["item"]["draft_id"]]
        if c.get("title") is not None:
            argv += ["--title", c["title"]]
        if c.get("body") is not None:
            argv += ["--body", c["body"]]
        _gh(argv)
        out["item"] = c["item"]
        return out
    if op == "item_add":
        b = step["board"]
        item_id = _json(["project", "item-add", str(b["number"]), "--owner", b["owner"], "--url", step["url"],
                         "--format", "json"]).get("id")
        if not item_id:
            raise AccessError("gh project item-add returned no item")
        out["item"] = item_id
        out["fields"] = _set_fields(b, item_id, c.get("fields") or {}, [])
        return out
    if op == "item_set":
        out["item"] = c["item"]
        out["fields"] = _set_fields(step["board"], c["item"], c.get("fields") or {}, c.get("clear") or [])
        return out
    if op == "item_archive":
        b = step["board"]
        argv = ["project", "item-archive", str(b["number"]), "--owner", b["owner"], "--id", c["item"]]
        if c.get("restore"):
            argv.append("--undo")
        _gh(argv)
        return {"item": c["item"], "archived": not c.get("restore")}
    if op == "draft_promote":
        repo = step["repo"]
        data = access.graphql("mutation($item:ID!,$repo:ID!){convertProjectV2DraftIssueItemToIssue(input:{itemId:$item,"
                              "repositoryId:$repo}){item{content{... on Issue{number url}}}}}",
                              {"item": c["item"], "repo": repo["id"]})
        content = (((data.get("convertProjectV2DraftIssueItemToIssue") or {}).get("item")) or {}).get("content") or {}
        if not content.get("number"):
            raise AccessError("the draft was not converted")
        number = content["number"]
        out.update({"issue": f"{repo['repo']}#{number}", "url": content.get("url")})
        if c.get("kind"):
            out["kind"] = _apply_kind(repo["repo"], number, c["kind"])
        edit = []
        for label in c.get("labels") or []:
            edit += ["--add-label", label]
        if c.get("milestone"):
            edit += ["--milestone", _milestone(repo["repo"], c["milestone"], bool(c.get("create_milestone")))]
        if edit:
            _gh(["issue", "edit", str(number), "--repo", repo["repo"], *edit])
        return out
    if op == "issue_create":
        repo = step["repo"]["repo"]
        argv = ["issue", "create", "--repo", repo, "--title", c["title"], "--body-file", "-"]
        for label in c.get("labels") or []:
            argv += ["--label", label]
        for who in c.get("assignees") or []:
            argv += ["--assignee", who]
        if c.get("milestone"):
            argv += ["--milestone", _milestone(repo, c["milestone"], bool(c.get("create_milestone")))]
        number = _number(_gh(argv, stdin=c.get("body") or ""))
        out.update({"issue": f"{repo}#{number}", "url": _url(repo, number)})
        if c.get("kind"):
            out["kind"] = _apply_kind(repo, number, c["kind"])
        if c.get("parent"):
            url = _ref_url(c["parent"], repo, step.get("created"))
            _gh(["issue", "edit", str(number), "--repo", repo, "--parent", url])
            out["parent"] = _short(url)
        for ref in c.get("blocked_by") or []:
            url = _ref_url(ref, repo, step.get("created"))
            _gh(["issue", "edit", str(number), "--repo", repo, "--add-blocked-by", url])
            out.setdefault("blocked_by", []).append(_short(url))
        if step.get("board"):
            b = step["board"]
            item_id = _json(["project", "item-add", str(b["number"]), "--owner", b["owner"], "--url", _url(repo, number),
                             "--format", "json"]).get("id")
            out["item"] = item_id
            if c.get("board_fields"):
                out["fields"] = _set_fields(b, item_id, c["board_fields"], [])
        return out
    repo, number = step["repo"]["repo"], step["number"]
    n = str(number)
    if op == "issue_edit":
        argv = ["issue", "edit", n, "--repo", repo]
        stdin = None
        if c.get("title") is not None:
            argv += ["--title", c["title"]]
        if c.get("body") is not None or c.get("append_body"):
            current = access.issue(repo, number, comments=0)["body"].rstrip() if c.get("append_body") else ""
            stdin = c["body"] if c.get("body") is not None else (f"{current}\n\n{c['append_body'].strip()}\n" if current
                                                                  else f"{c['append_body'].strip()}\n")
            argv += ["--body-file", "-"]
        for label in c.get("add_labels") or []:
            argv += ["--add-label", label]
        for label in c.get("remove_labels") or []:
            argv += ["--remove-label", label]
        for who in c.get("add_assignees") or []:
            argv += ["--add-assignee", who]
        for who in c.get("remove_assignees") or []:
            argv += ["--remove-assignee", who]
        if c.get("milestone") is not None:
            argv += ["--remove-milestone"] if c["milestone"] == "" else \
                ["--milestone", _milestone(repo, c["milestone"], bool(c.get("create_milestone")))]
        out["issue"] = f"{repo}#{number}"
        if len(argv) > 5:
            _gh(argv, stdin=stdin)
            out["edited"] = True
        if c.get("kind"):
            out["kind"] = _apply_kind(repo, number, c["kind"])
        return out
    if op == "issue_comment":
        out["issue"] = f"{repo}#{number}"
        out["url"] = _gh(["issue", "comment", n, "--repo", repo, "--body-file", "-"], stdin=c["body"]).strip() or None
        return out
    if op == "issue_relate":
        out["issue"] = f"{repo}#{number}"
        out["done"] = []
        _relate(repo, number, c, out["done"])
        return out
    if op == "issue_close":
        argv = ["issue", "close", n, "--repo", repo, "--reason", c["reason"]]
        if c.get("comment"):
            argv += ["--comment", c["comment"]]
        _gh(argv)
        return {"issue": f"{repo}#{number}", "closed": c["reason"]}
    if op == "issue_reopen":
        _gh(["issue", "reopen", n, "--repo", repo])
        return {"issue": f"{repo}#{number}", "reopened": True}
    raise AccessError(f"unknown op {op}")


UNCERTAIN = re.compile(r"did not answer within|timed out|timeout|connection reset|EOF|502|503|504", re.IGNORECASE)


def apply(planned: dict) -> dict:
    """Run the changes in order; stop at the first failure. A failed change reports what of it already
    exists (``partial``), and one whose failure may have happened after GitHub acted is ``uncertain``:
    read before sending anything again."""
    done, failed = [], None
    created: dict[int, tuple[str, int]] = {}
    for i, step in enumerate(planned["steps"]):
        out: dict = {}
        try:
            done.append({"op": step["change"]["op"], **_run_step({**step, "created": created}, out)})
            if out.get("issue"):
                created[i + 1] = access.parse_issue(out["issue"])
        except Exception as exc:
            failed = {"index": i, "op": step["change"]["op"], "error": str(exc), "partial": out,
                      "uncertain": bool(UNCERTAIN.search(str(exc)))}
            break
    rest = [s["change"]["op"] for s in planned["steps"][len(done) + (1 if failed else 0):]]
    return {"ok": failed is None, "done": done, "failed": failed, "not_done": rest}
