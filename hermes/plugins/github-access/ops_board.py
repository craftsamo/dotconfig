"""github-access: board changes — drafts and the items of a Projects (v2) board.

Registered into ``changes.py``. Also the board helpers the issue ops share: reading an item, and
checking and setting its field values.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path


def _load(name, path):
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


changes = _load("hermes_github_access_changes", Path(__file__).resolve().parent / "changes.py")
access = changes.access
AccessError = changes.AccessError
Op, say = changes.Op, changes.say

changes.key("item", "str", description="a board item id (PVTI_…)")
changes.key("url", "str")
changes.key("text", "str", text=True)
changes.key("fields", "map", text=True)
changes.key("clear", "list")
changes.key("restore", "bool")

ITEM_QUERY = ("query($id:ID!){node(id:$id){... on ProjectV2Item{id isArchived project{" + access.PROJECT_FIELDS + "} "
              "content{__typename ... on DraftIssue{id title body} ... on Issue{number url repository{nameWithOwner}} "
              "... on PullRequest{number url repository{nameWithOwner}}}}}}")
EDITABLE = ("SINGLE_SELECT", "TEXT", "NUMBER", "DATE", "ITERATION")


def read_item(item_id: str) -> dict:
    node = access.graphql(ITEM_QUERY, {"id": item_id}).get("node") or {}
    if not node.get("id"):
        raise AccessError(f"board item {item_id} not found")
    content = node.get("content") or {}
    return {"id": node["id"], "archived": bool(node.get("isArchived")), "board": access._board(node["project"], fresh=True),
            "content_type": content.get("__typename"), "draft_id": content.get("id") if content.get("__typename") == "DraftIssue" else None,
            "body": content.get("body") or "", "title": content.get("title") or ""}


def check_fields(fields: list[dict], values: dict, clear: list[str]) -> None:
    """Refuse, before anything is written, a field the board lacks, a built-in, an unknown option
    or a malformed date."""
    for name in [*values, *clear]:
        f = next((f for f in fields if access.same(f["name"], name)), None)
        if not f:
            raise AccessError(f"no field {name!r} on the board; fields: {', '.join(x['name'] for x in fields)}")
        if f["type"] not in EDITABLE:
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


def plan_fields(step: dict, planned, values: dict, clear: list | None = None) -> None:
    """Check field values against the step's board (read once per list)."""
    if values or clear:
        check_fields(planned.fields(step["board"]["id"]), values or {}, list(clear or []))


def set_fields(board: dict, item_id: str, values: dict, clear: list[str]) -> list[str]:
    fields = access.fields(board["id"])
    applied = []

    def field(name):
        f = next((f for f in fields if access.same(f["name"], name)), None)
        if not f:
            raise AccessError(f"no field {name!r} on the board; fields: {', '.join(x['name'] for x in fields)}")
        if f["type"] not in EDITABLE:
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
        changes.gh(argv)
        applied.append(f["name"])
    for name in clear:
        f = field(name)
        changes.gh([*base, "--field-id", f["id"], "--clear"])
        applied.append(f"{f['name']} (cleared)")
    return applied


def add_to_board(board: dict, url: str) -> str:
    item_id = changes.gh_json(["project", "item-add", str(board["number"]), "--owner", board["owner"], "--url", url,
                               "--format", "json"]).get("id")
    if not item_id:
        raise AccessError("gh project item-add returned no item")
    return item_id


def plan_item(step: dict, planned, draft: bool = False) -> dict:
    """The item a change names, read now, and its board as a target."""
    change = step["change"]
    it = read_item(change["item"])
    step["item"] = it
    step["board"] = planned.add_board(it["board"])
    if draft and it["content_type"] != "DraftIssue":
        raise AccessError(f"{change['op']}: item {change['item']} is not a draft; edit its issue instead")
    return it


def _named(step: dict, limit: int) -> str:
    return say(step["item"]["title"] or step["change"]["item"], limit)


# --- draft_add ------------------------------------------------------------------------------------

def _draft_add_plan(step, planned):
    step["board"] = planned.list_board()
    plan_fields(step, planned, step["change"].get("fields"))


def _draft_add_describe(step):
    c = step["change"]
    fields = ", ".join(f"{k}={v}" for k, v in (c.get("fields") or {}).items())
    return f"Add draft {say(c['title'], 70)!s}" + (f" ({say(fields, 50)})" if fields else "")


def _draft_add_run(step, out):
    c, b = step["change"], step["board"]
    argv = ["project", "item-create", str(b["number"]), "--owner", b["owner"], "--title", c["title"], "--format", "json"]
    if c.get("body"):
        argv += ["--body", c["body"]]
    item_id = changes.gh_json(argv).get("id")
    if not item_id:
        raise AccessError("gh project item-create returned no item")
    out["item"] = item_id
    out["fields"] = set_fields(b, item_id, c.get("fields") or {}, []) if c.get("fields") else []
    return out


# --- draft_note, draft_edit -----------------------------------------------------------------------

def _draft_note_run(step, out):
    c = step["change"]
    # Read now, not at plan time: an earlier change of this list (or a person) may have changed it.
    current = read_item(c["item"])["body"].rstrip()
    body = f"{current}\n\n{c['text'].strip()}\n" if current else f"{c['text'].strip()}\n"
    changes.gh(["project", "item-edit", "--id", step["item"]["draft_id"], "--body", body])
    out["item"] = c["item"]
    return out


def _draft_edit_check(change):
    if change.get("title") is None and change.get("body") is None:
        raise AccessError("draft_edit: title or body is required")


def _draft_edit_describe(step):
    c = step["change"]
    parts = [f"title → {say(c['title'], 50)}" if c.get("title") is not None else "",
             f"body → {say(c['body'], 60)}" if c.get("body") is not None else ""]
    return f"Edit draft {say(step['item']['title'], 40)}: " + "; ".join(p for p in parts if p)


def _draft_edit_run(step, out):
    c = step["change"]
    argv = ["project", "item-edit", "--id", step["item"]["draft_id"]]
    if c.get("title") is not None:
        argv += ["--title", c["title"]]
    if c.get("body") is not None:
        argv += ["--body", c["body"]]
    changes.gh(argv)
    out["item"] = c["item"]
    return out


# --- item_add, item_set, item_archive -------------------------------------------------------------

def _item_add_plan(step, planned):
    change = step["change"]
    step["board"] = planned.list_board()
    # Putting an issue or PR on a board writes only the board, wherever the issue lives.
    url = change["url"].strip()
    repo, number = access.parse_issue(url, planned.default_repo, allow_pr=True)
    step["url"] = f"https://github.com/{repo}/{'pull' if '/pull/' in url else 'issues'}/{number}"
    plan_fields(step, planned, change.get("fields"))


def _item_add_describe(step):
    c = step["change"]
    return f"Put {c['url'].removeprefix('https://github.com/')} on the board" + (
        f" ({say(', '.join(f'{k}={v}' for k, v in c['fields'].items()), 50)})" if c.get("fields") else "")


def _item_add_run(step, out):
    out["item"] = add_to_board(step["board"], step["url"])
    out["fields"] = set_fields(step["board"], out["item"], step["change"].get("fields") or {}, [])
    return out


def _item_set_check(change):
    if not (change.get("fields") or change.get("clear")):
        raise AccessError("item_set: fields or clear is required")


def _item_set_plan(step, planned):
    plan_item(step, planned)
    plan_fields(step, planned, step["change"].get("fields"), step["change"].get("clear"))


def _item_set_describe(step):
    c = step["change"]
    what = [f"{k}={v}" for k, v in (c.get("fields") or {}).items()] + [f"{k} cleared" for k in c.get("clear") or []]
    return f"Set {_named(step, 40)}: {say(', '.join(what), 80)}"


def _item_set_run(step, out):
    c = step["change"]
    out["item"] = c["item"]
    out["fields"] = set_fields(step["board"], c["item"], c.get("fields") or {}, c.get("clear") or [])
    return out


def _item_archive_run(step, out):
    c, b = step["change"], step["board"]
    argv = ["project", "item-archive", str(b["number"]), "--owner", b["owner"], "--id", c["item"]]
    if c.get("restore"):
        argv.append("--undo")
    changes.gh(argv)
    return {"item": c["item"], "archived": not c.get("restore")}


for _op in (
        Op("draft_add", "create", "title, body, fields: a draft on the board", _draft_add_plan, _draft_add_describe,
           _draft_add_run, required=("title",), optional=("body", "fields"), needs_board=lambda c: True),
        Op("draft_note", "routine", "item, text: appended to a draft", lambda s, p: plan_item(s, p, draft=True),
           lambda s: f"Note on draft {say(s['item']['title'], 40)}: {say(s['change']['text'], 80)}", _draft_note_run,
           required=("item", "text")),
        Op("draft_edit", "routine", "item, title / body", lambda s, p: plan_item(s, p, draft=True), _draft_edit_describe,
           _draft_edit_run, required=("item",), optional=("title", "body"), check=_draft_edit_check),
        Op("item_add", "create", "url of an issue or PR, fields", _item_add_plan, _item_add_describe, _item_add_run,
           required=("url",), optional=("fields",), needs_board=lambda c: True),
        Op("item_set", "routine", "item, fields {name: value}, clear [names]", _item_set_plan, _item_set_describe,
           _item_set_run, required=("item",), optional=("fields", "clear"), check=_item_set_check),
        Op("item_archive", "routine", "item, restore", plan_item,
           lambda s: f"{'Restore' if s['change'].get('restore') else 'Archive'} {_named(s, 60)}", _item_archive_run,
           required=("item",), optional=("restore",))):
    changes.register(_op)
