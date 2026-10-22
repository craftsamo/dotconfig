"""github-access: board changes — drafts and the items of a Projects (v2) board, and the board
itself: making one in the standard shape, linking it to a repository, its fields and views.

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


# --- the board itself -----------------------------------------------------------------------------
# The standard shape is small on purpose: Milestone, Repository, Parent issue, Sub-issues progress
# and Type are built-in fields GitHub fills from the issues.

COLORS = ("GRAY", "BLUE", "GREEN", "YELLOW", "ORANGE", "RED", "PINK", "PURPLE")
DATA_TYPES = ("TEXT", "SINGLE_SELECT", "DATE", "NUMBER")
LAYOUTS = {"table": "TABLE_LAYOUT", "board": "BOARD_LAYOUT", "roadmap": "ROADMAP_LAYOUT"}
STANDARD_FIELDS = (
    ("Status", "SINGLE_SELECT", (("Todo", "GRAY"), ("In Progress", "YELLOW"), ("Done", "GREEN"), ("Cancelled", "RED"))),
    ("Start", "DATE", ()),
    ("Target", "DATE", ()),
)
STANDARD_VIEWS = (
    ("Kanban", "board", "-status:Done -status:Cancelled", ("Title", "Assignees", "Repository", "Parent issue", "Target")),
    ("Backlog", "table", "-status:Done -status:Cancelled",
     ("Title", "Status", "Repository", "Milestone", "Parent issue", "Sub-issues progress", "Target")),
    ("Roadmap", "roadmap", "-status:Cancelled", ()),
)
# Names GitHub keeps for its own fields: a custom field cannot take one.
BUILT_IN_NAMES = {"title", "assignees", "labels", "milestone", "repository", "reviewers", "linked pull requests",
                  "parent issue", "sub-issues progress", "type", "status", "tracks", "tracked by"}

changes.key("owner", "str", description="board_create: the owner's login, or \"@me\"")
changes.key("template", "str")
changes.key("link_repo", "str")
changes.key("views", "bool")
changes.key("unlink", "bool")
changes.key("name", "str", text=True)
changes.key("data_type", "str", enum=list(DATA_TYPES))
changes.key("options", "list", text=True)
changes.key("layout", "str", enum=list(LAYOUTS))
changes.key("filter", "str", text=True)
changes.key("visible_fields", "list")

OWNER_QUERY = "query($login:String!){repositoryOwner(login:$login){__typename id login}}"
FIELD_DETAIL_QUERY = ("query($id:ID!){node(id:$id){... on ProjectV2{fields(first:50){nodes{"
                      "... on ProjectV2FieldCommon{id name dataType} "
                      "... on ProjectV2SingleSelectField{options{id name color description}}}}}}}")
VIEWS_QUERY = "query($id:ID!){node(id:$id){... on ProjectV2{views(first:50){nodes{id name}}}}}"
CREATE_BOARD = ("mutation($owner:ID!,$title:String!){createProjectV2(input:{ownerId:$owner,title:$title})"
                "{projectV2{id}}}")
COPY_BOARD = ("mutation($project:ID!,$owner:ID!,$title:String!){copyProjectV2(input:{projectId:$project,ownerId:$owner,"
              "title:$title,includeDraftIssues:false}){projectV2{id}}}")
LINK = ("mutation($project:ID!,$repo:ID!){%s(input:{projectId:$project,repositoryId:$repo}){repository{id}}}")
CREATE_FIELD = ("mutation($project:ID!,$type:ProjectV2CustomFieldType!,$name:String!,"
                "$options:[ProjectV2SingleSelectFieldOptionInput!]){createProjectV2Field(input:{projectId:$project,"
                "dataType:$type,name:$name,singleSelectOptions:$options}){projectV2Field{... on ProjectV2FieldCommon{id}}}}")
UPDATE_OPTIONS = ("mutation($field:ID!,$options:[ProjectV2SingleSelectFieldOptionInput!]){updateProjectV2Field("
                  "input:{fieldId:$field,singleSelectOptions:$options}){projectV2Field{... on ProjectV2FieldCommon{id}}}}")
CREATE_VIEW = ("mutation($project:ID!,$name:String!,$layout:ProjectV2ViewLayout!,$fields:[ID!]){createProjectV2View("
               "input:{projectId:$project,name:$name,layout:$layout,configuration:{visibleFieldIds:$fields}})"
               "{projectV2View{id}}}")
FILTER_VIEW = ("mutation($view:ID!,$filter:String!){updateProjectV2View(input:{viewId:$view,filter:$filter})"
               "{projectV2View{id}}}")


def _options(change: dict) -> list[tuple[str, str]]:
    """``Name`` or ``Name:COLOR`` options as (name, color), GRAY when no color is given. Only one of
    GitHub's colors counts as a suffix, in any case, so ``Release:V2`` stays a name."""
    out = []
    for text in change.get("options") or []:
        name, color = text.strip(), "GRAY"
        head, sep, tail = name.rpartition(":")
        if sep and tail.strip().upper() in COLORS:
            name, color = head.strip(), tail.strip().upper()
        if not name:
            raise AccessError(f"{change['op']}: an option needs a name")
        if any(access.same(name, n) for n, _ in out):
            raise AccessError(f"{change['op']}: option {name!r} is named twice")
        out.append((name, color))
    return out


def field_details(board_id: str) -> list[dict]:
    data = access.graphql(FIELD_DETAIL_QUERY, {"id": board_id})
    return [f for f in ((data.get("node") or {}).get("fields") or {}).get("nodes") or [] if f and f.get("id")]


def view_names(board_id: str) -> dict[str, str]:
    data = access.graphql(VIEWS_QUERY, {"id": board_id})
    return {v["name"]: v["id"] for v in ((data.get("node") or {}).get("views") or {}).get("nodes") or [] if v}


def ensure_field(board: dict, name: str, data_type: str, options: list[tuple[str, str]]) -> dict:
    """Create the field when the board lacks it, else append the options it lacks. Existing options
    keep their ids, colors and descriptions, so no item's value moves."""
    found = next((f for f in field_details(board["id"]) if access.same(f["name"], name)), None)
    if found is None:
        made = access.graphql(CREATE_FIELD, {
            "project": board["id"], "type": data_type, "name": name,
            "options": [{"name": n, "color": c, "description": ""} for n, c in options] if data_type == "SINGLE_SELECT"
            else None})
        if not ((made.get("createProjectV2Field") or {}).get("projectV2Field") or {}).get("id"):
            raise AccessError(f"field {name!r} was not created")
        return {"field": name, "created": True, "added": [n for n, _ in options]}
    if found["dataType"] != data_type:
        raise AccessError(f"field {found['name']!r} is a {found['dataType']} field, not {data_type}")
    have = found.get("options") or []
    missing = [(n, c) for n, c in options if not any(access.same(o["name"], n) for o in have)]
    if missing:
        access.graphql(UPDATE_OPTIONS, {"field": found["id"], "options": [
            *({"id": o["id"], "name": o["name"], "color": o["color"], "description": o.get("description") or ""}
              for o in have),
            *({"name": n, "color": c, "description": ""} for n, c in missing)]})
    return {"field": found["name"], "created": False, "added": [n for n, _ in missing]}


def ensure_view(board: dict, name: str, layout: str, filter_: str, columns) -> dict:
    """Make the view when the board has none of that name. Grouping, sort and a roadmap's date fields
    are set once in GitHub's own page: the API does not take them."""
    if any(access.same(v, name) for v in view_names(board["id"])):
        return {"view": name, "created": False}
    fields = {f["name"].lower(): f["id"] for f in field_details(board["id"])}
    ids = [fields[c.lower()] for c in columns if c.lower() in fields] if layout != "roadmap" else []
    skipped = [c for c in columns if c.lower() not in fields] if layout != "roadmap" else []
    made = access.graphql(CREATE_VIEW, {"project": board["id"], "name": name, "layout": LAYOUTS[layout],
                                        "fields": ids or None})
    view_id = ((made.get("createProjectV2View") or {}).get("projectV2View") or {}).get("id")
    if not view_id:
        raise AccessError(f"view {name!r} was not created")
    if filter_:
        access.graphql(FILTER_VIEW, {"view": view_id, "filter": filter_})
    return {"view": name, "created": True, **({"columns_missing": skipped} if skipped else {})}


def _linked(board_id: str, repo: str) -> bool:
    return any(b["id"] == board_id for b in access.linked_boards(repo))


def _owner(login: str, what: str = "board") -> dict:
    """Who a new board (or repository) would belong to: the viewer, or an organization the viewer
    belongs to."""
    login = access.viewer(fresh=True) if login.strip() in ("", "@me") else login.strip()
    found = access.graphql(OWNER_QUERY, {"login": login}).get("repositoryOwner")
    if not found:
        raise AccessError(f"no user or organization named {login!r}")
    if found["__typename"] == "User":
        if not access.same(found["login"], access.viewer(fresh=True)):
            raise AccessError(f"a {what} is made for yourself (@me) or an organization you belong to, not for {login}")
        tier = "own"  # a new board is private
    else:
        if access.tier(found["login"], "Organization", True, fresh=True) == "other":
            raise AccessError(f"you are not a member of {found['login']}; a {what} is made only where you work")
        tier = "shared"
    return {"id": found["id"], "login": found["login"], "type": found["__typename"], "tier": tier}


def _board_create_check(change):
    if change.get("title") is not None and not change["title"].strip():
        raise AccessError("board_create: title, when given, is not empty")


def _board_create_plan(step, planned):
    c = step["change"]
    owner = _owner(c.get("owner") or "@me")
    title = (c.get("title") or access.DEFAULT_BOARD).strip()
    found = access.boards_titled(owner["login"], title)
    if len(found) > 1:
        raise AccessError(f"{owner['login']} has {len(found)} open boards titled {title!r}; close or rename the extra ones")
    step["owner"], step["title"] = owner, title
    if found:
        step["existing"] = planned.add_board(found[0])  # reused, brought to the standard shape
        have = planned.fields(found[0]["id"])
        for name, kind, _ in STANDARD_FIELDS:
            f = next((f for f in have if access.same(f["name"], name)), None)
            if f and f["type"] != kind:
                raise AccessError(f"board_create: {f['name']!r} on {found[0]['owner']}/{found[0]['number']} is a "
                                  f"{f['type']} field, not {kind}; rename it on the board first")
    else:
        planned.note(f"owner:{owner['id']}", {"kind": "owner", "name": owner["login"], "tier": owner["tier"],
                                               "id": owner["id"]})
        if c.get("template"):
            # Read, never written: shown with its tier, and bound like a target, so another board
            # resolving at the write is a different change.
            t = access.resolve_board(project=c["template"])["board"]
            planned.note(f"template:{t['id']}", {"kind": "template", "name": f"{t['owner']}/{t['number']} {t['title']}",
                                                 "tier": access.tier(t["owner"], t["owner_type"], not t["public"], fresh=True),
                                                 "id": t["id"]})
            step["template"] = t
    if c.get("link_repo"):
        step["repo"] = planned.repo(c["link_repo"])


def _board_create_describe(step):
    c = step["change"]
    shape = "Status, Start, Target" + ("" if c.get("views") is False else "; Kanban, Backlog, Roadmap views")
    extra = [f"copied from {step['template']['owner']}/{step['template']['number']}" if step.get("template") else "",
             f"linked to {step['repo']['repo']}" if step.get("repo") else ""]
    extra = "; ".join(e for e in extra if e)
    if step.get("existing"):
        b = step["existing"]
        return f"Bring board {b['owner']}/{b['number']} {say(b['title'], 40)} to the standard shape ({shape}" + (
            f"; {extra})" if extra else ")")
    return f"Create board {say(step['title'], 40)} for {step['owner']['login']} ({shape}" + (f"; {extra})" if extra else ")")


def _board_create_run(step, out):
    c = step["change"]
    if step.get("existing"):
        b = step["existing"]
        out.update({"board": f"{b['owner']}/{b['number']}", "url": b["url"], "created": False})
    else:
        if step.get("template"):
            made = access.graphql(COPY_BOARD, {"project": step["template"]["id"], "owner": step["owner"]["id"],
                                               "title": step["title"]})
            made = (made.get("copyProjectV2") or {}).get("projectV2") or {}
        else:
            made = (access.graphql(CREATE_BOARD, {"owner": step["owner"]["id"], "title": step["title"]})
                    .get("createProjectV2") or {}).get("projectV2") or {}
        if not made.get("id"):
            raise AccessError("the board was not created")
        out.update({"board_id": made["id"], "created": True})
        b = access.board_context(made["id"], fresh=True)
        out.update({"board": f"{b['owner']}/{b['number']}", "url": b["url"]})
    # Each piece is recorded as it lands, so a failure part-way says what the board already has.
    out["fields"] = []
    for name, kind, options in STANDARD_FIELDS:
        out["fields"].append(ensure_field(b, name, kind, list(options)))
    if c.get("views") is not False:
        out["views"] = []
        for view in STANDARD_VIEWS:
            out["views"].append(ensure_view(b, *view))
    if step.get("repo"):
        out["linked"] = _link(b, step["repo"], link=True)
    return out


def _link(board: dict, repo: dict, link: bool) -> str:
    if _linked(board["id"], repo["repo"]) == link:
        return f"{repo['repo']} (already {'linked' if link else 'unlinked'})"
    access.graphql(LINK % ("linkProjectV2ToRepository" if link else "unlinkProjectV2FromRepository"),
                   {"project": board["id"], "repo": repo["id"]})
    return repo["repo"]


def _board_link_plan(step, planned):
    step["board"] = planned.list_board()
    step["repo"] = planned.repo_of(step["change"])


def _board_link_describe(step):
    b = step["board"]
    verb = "Unlink" if step["change"].get("unlink") else "Link"
    return f"{verb} board {b['owner']}/{b['number']} {say(b['title'], 40)} {'from' if verb == 'Unlink' else 'to'} {step['repo']['repo']}"


def _board_link_run(step, out):
    out["board"] = f"{step['board']['owner']}/{step['board']['number']}"
    out["linked" if not step["change"].get("unlink") else "unlinked"] = _link(step["board"], step["repo"],
                                                                              link=not step["change"].get("unlink"))
    return out


def _field_ensure_check(change):
    _options(change)
    if change["data_type"] != "SINGLE_SELECT" and change.get("options"):
        raise AccessError("field_ensure: options are for a SINGLE_SELECT field")


def _field_ensure_plan(step, planned):
    c = step["change"]
    step["board"] = planned.list_board()
    name, options = c["name"].strip(), _options(c)
    found = next((f for f in planned.fields(step["board"]["id"]) if access.same(f["name"], name)), None)
    if found is None:
        if name.lower() in BUILT_IN_NAMES:
            raise AccessError(f"field_ensure: {name!r} is a name GitHub keeps for its own field; pick another")
        if c["data_type"] == "SINGLE_SELECT" and not options:
            raise AccessError("field_ensure: a new SINGLE_SELECT field needs its options")
        step["adds"] = [n for n, _ in options]
    else:
        if found["type"] != c["data_type"]:
            raise AccessError(f"field_ensure: {found['name']!r} is a {found['type']} field, not {c['data_type']}")
        step["field"] = found["name"]
        step["adds"] = [n for n, _ in options if not any(access.same(o["name"], n) for o in found["options"] or [])]


def _field_ensure_describe(step):
    c = step["change"]
    if step.get("field"):
        if not step["adds"]:
            return f"Field {say(step['field'], 40)}: already in place"
        return f"Field {say(step['field'], 40)}: add options {say(', '.join(step['adds']), 80)}"
    kind = c["data_type"] + (f": {', '.join(step['adds'])}" if step["adds"] else "")
    return f"Create field {say(c['name'], 40)} ({say(kind, 80)})"


def _field_ensure_run(step, out):
    c = step["change"]
    return {**out, **ensure_field(step["board"], c["name"].strip(), c["data_type"], _options(c))}


def _view_ensure_check(change):
    if change["layout"] == "roadmap" and change.get("visible_fields"):
        raise AccessError("view_ensure: visible_fields are for a table or board view; a roadmap takes none")


def _view_ensure_plan(step, planned):
    c = step["change"]
    step["board"] = planned.list_board()
    if c.get("visible_fields") and c["layout"] != "roadmap":
        names = {f["name"].lower() for f in planned.fields(step["board"]["id"])}
        unknown = [n for n in c["visible_fields"] if n.lower() not in names]
        if unknown:
            raise AccessError(f"view_ensure: the board has no field {', '.join(map(repr, unknown))}")
    step["exists"] = any(access.same(v, c["name"]) for v in view_names(step["board"]["id"]))


def _view_ensure_describe(step):
    c = step["change"]
    if step["exists"]:
        return f"View {say(c['name'], 40)}: already in place"
    filt = f", filter {say(c['filter'], 50)}" if c.get("filter") else ""
    return f"Add view {say(c['name'], 40)} ({c['layout']}{filt})"


def _view_ensure_run(step, out):
    c = step["change"]
    return {**out, **ensure_view(step["board"], c["name"].strip(), c["layout"], c.get("filter") or "",
                                 c.get("visible_fields") or [])}


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
           required=("item",), optional=("restore",)),
        Op("board_create", "create",
           "owner (a login or \"@me\", default @me), title (default Roadmap), template (a board to copy), link_repo, "
           "views (default true): a board with Status Todo / In Progress / Done / Cancelled, Start and Target dates "
           "and the Kanban, Backlog and Roadmap views; an open board of that title is reused and brought to that shape",
           _board_create_plan, _board_create_describe, _board_create_run,
           optional=("owner", "title", "template", "link_repo", "views"), check=_board_create_check),
        Op("board_link", "create", "repo, unlink: the board linked to (or unlinked from) a repository, so it resolves "
           "first for that repository", _board_link_plan, _board_link_describe, _board_link_run,
           optional=("repo", "unlink"), needs_board=lambda c: True),
        Op("field_ensure", "create", "name, data_type TEXT|SINGLE_SELECT|DATE|NUMBER, options [\"Name\" or "
           "\"Name:COLOR\"]: a field made, or the options it lacks appended (e.g. Status + Waiting)",
           _field_ensure_plan, _field_ensure_describe, _field_ensure_run, required=("name", "data_type"),
           optional=("options",), check=_field_ensure_check, needs_board=lambda c: True),
        Op("view_ensure", "create", "name, layout table|board|roadmap, filter, visible_fields [names]: a saved view "
           "made when the board has none of that name", _view_ensure_plan, _view_ensure_describe, _view_ensure_run,
           required=("name", "layout"), optional=("filter", "visible_fields"), check=_view_ensure_check,
           needs_board=lambda c: True)):
    changes.register(_op)
