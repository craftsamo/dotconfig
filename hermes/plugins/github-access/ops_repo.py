"""github-access: repository changes — making a repository, its settings, visibility and archiving
(``admin``: they change how a repository works for everyone at once), and its labels and
milestones (``create``).

Registered into ``changes.py``. Each reads the repository's settings, labels or milestones before
the card (``access_repo.py``), so the card says what a change moves from.
"""

from __future__ import annotations

import importlib.util
import json
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


HERE = Path(__file__).resolve().parent
changes = _load("hermes_github_access_changes", HERE / "changes.py")
board = _load("hermes_github_access_ops_board", HERE / "ops_board.py")
reads = _load("hermes_github_access_repo_reads", HERE / "access_repo.py")
access = changes.access
AccessError = changes.AccessError
Op, say, gh = changes.Op, changes.say, changes.gh

VISIBILITIES = ("private", "public", "internal")
FEATURES = ("has_issues", "has_wiki", "has_projects", "has_discussions")
MERGE = ("allow_merge_commit", "allow_squash_merge", "allow_rebase_merge", "allow_auto_merge",
         "delete_branch_on_merge", "allow_update_branch")
# setting -> the gh repo edit flag that sets it
FLAGS = {"has_issues": "--enable-issues", "has_wiki": "--enable-wiki", "has_projects": "--enable-projects",
         "has_discussions": "--enable-discussions", "allow_merge_commit": "--enable-merge-commit",
         "allow_squash_merge": "--enable-squash-merge", "allow_rebase_merge": "--enable-rebase-merge",
         "allow_auto_merge": "--enable-auto-merge", "delete_branch_on_merge": "--delete-branch-on-merge",
         "allow_update_branch": "--allow-update-branch", "is_template": "--template"}
WORDS = {"has_issues": "issues", "has_wiki": "wiki", "has_projects": "projects", "has_discussions": "discussions",
         "allow_merge_commit": "merge commits", "allow_squash_merge": "squash merges", "allow_rebase_merge": "rebase merges",
         "allow_auto_merge": "auto-merge", "delete_branch_on_merge": "deleting the branch on merge",
         "allow_update_branch": "updating a PR's branch", "is_template": "template"}
TOPIC = re.compile(r"^[a-z0-9][a-z0-9-]{0,49}$")
COLOR = re.compile(r"^#?[0-9a-fA-F]{6}$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
EDIT_KEYS = ("description", "homepage", "add_topics", "remove_topics", "default_branch", *FEATURES, *MERGE, "is_template")

changes.key("visibility", "str", enum=list(VISIBILITIES))
changes.key("description", "str", text=True)
changes.key("homepage", "str", text=True)
changes.key("add_topics", "list", text=True)
changes.key("remove_topics", "list")
changes.key("default_branch", "str")
changes.key("license", "str")
changes.key("gitignore", "str")
changes.key("add_readme", "bool")
changes.key("unarchive", "bool")
changes.key("color", "str")
changes.key("new_name", "str", text=True)
changes.key("new_title", "str", text=True)
changes.key("due", "str")
changes.key("state", "str", enum=["open", "closed"])
for _name in (*FEATURES, *MERGE, "is_template"):
    changes.key(_name, "bool")

BRANCH_QUERY = "query($owner:String!,$name:String!,$ref:String!){repository(owner:$owner,name:$name){ref(qualifiedName:$ref){name}}}"


def _admin(ctx: dict, op: str) -> None:
    if ctx["permission"] != "ADMIN":
        raise AccessError(f"{op}: needs admin on {ctx['repo']} (viewer permission: {ctx['permission'] or 'none'})")


def _onoff(value: bool) -> str:
    return "on" if value else "off"


# --- repo_create ----------------------------------------------------------------------------------

def _repo_create_check(change):
    if change.get("license") and not re.fullmatch(r"[A-Za-z0-9.-]{2,40}", change["license"]):
        raise AccessError("repo_create: license is an SPDX-style key such as mit or apache-2.0")
    if change.get("gitignore") and not re.fullmatch(r"[A-Za-z0-9.+_-]{1,40}", change["gitignore"]):
        raise AccessError("repo_create: gitignore is a template name such as Python or Node")
    if change.get("template") and (change.get("license") or change.get("gitignore") or change.get("add_readme")):
        raise AccessError("repo_create: a template brings its own files; license, gitignore and add_readme are for an "
                          "empty repository")


def _repo_create_plan(step, planned):
    c = step["change"]
    name = access.parse_repo(c["repo"])
    if any(s["change"]["op"] == "repo_create" and access.same(s.get("name"), name) for s in planned.steps):
        raise AccessError(f"repo_create: {name} is made by an earlier change of this list")
    try:
        access.repo_context(name, fresh=True)
    except AccessError as exc:
        if "not found" not in str(exc):
            raise
    else:
        raise AccessError(f"repo_create: {name} already exists")
    owner = board._owner(name.split("/", 1)[0], what="repository")
    visibility = c.get("visibility") or "private"
    if visibility == "internal" and owner["type"] != "Organization":
        raise AccessError("repo_create: internal visibility is for an organization's repository")
    tier = "own" if owner["type"] == "User" and visibility == "private" else "shared"
    step["owner"], step["name"], step["visibility"] = owner, name, visibility
    planned.note(f"new_repo:{owner['id']}:{name.lower()}",
                 {"kind": "new_repo", "name": f"{name} ({visibility})", "tier": tier, "id": f"{owner['id']}/{name.lower()}"})
    if c.get("template"):
        t = reads.settings(c["template"])
        if not t["is_template"]:
            raise AccessError(f"repo_create: {t['repo']} is not a template repository")
        planned.note(f"template:{t['id']}", {"kind": "template", "name": t["repo"], "tier": t["tier"], "id": t["id"]})
        step["template"] = t


def _repo_create_describe(step):
    c = step["change"]
    extra = [f"from template {step['template']['repo']}" if step.get("template") else "",
             f"license {c['license']}" if c.get("license") else "", f"gitignore {c['gitignore']}" if c.get("gitignore") else "",
             "with a README" if c.get("add_readme") else "",
             f"description: {say(c['description'], 50)}" if c.get("description") else ""]
    extra = "; ".join(e for e in extra if e)
    warn = " (anyone can read it)" if step["visibility"] == "public" else ""
    return f"Create {step['visibility']} repository {step['name']}{warn}" + (f" ({extra})" if extra else "")


def _repo_create_run(step, out):
    c = step["change"]
    argv = ["repo", "create", step["name"], f"--{step['visibility']}"]
    for key, flag in (("description", "--description"), ("homepage", "--homepage"), ("license", "--license"),
                      ("gitignore", "--gitignore")):
        if c.get(key):
            argv += [flag, c[key]]
    if c.get("add_readme"):
        argv.append("--add-readme")
    if step.get("template"):
        argv += ["--template", step["template"]["repo"]]
    printed = gh(argv).strip()
    out.update({"repo": step["name"], "url": printed.splitlines()[-1] if printed else f"https://github.com/{step['name']}"})
    return out


# --- repo_edit, repo_visibility, repo_archive -----------------------------------------------------

def _repo_edit_check(change):
    if not any(change.get(k) is not None and change.get(k) != [] for k in EDIT_KEYS):
        raise AccessError("repo_edit: nothing to change")
    for topic in [*(change.get("add_topics") or []), *(change.get("remove_topics") or [])]:
        if not TOPIC.match(topic):
            raise AccessError(f"repo_edit: topic {topic!r} is lowercase letters, digits and hyphens, at most 50")


def _repo_edit_plan(step, planned):
    c = step["change"]
    ctx = planned.repo_of(c)
    _admin(ctx, "repo_edit")
    current = reads.settings(ctx["repo"])
    step["repo"], step["current"] = ctx, current
    after = {**current["merge"], **{k: c[k] for k in MERGE if c.get(k) is not None}}
    if not any(after[k] for k in ("allow_merge_commit", "allow_squash_merge", "allow_rebase_merge")):
        raise AccessError("repo_edit: at least one merge method stays allowed")
    if c.get("default_branch") and c["default_branch"] != current["default_branch"]:
        owner, name = ctx["repo"].split("/", 1)
        found = access.graphql(BRANCH_QUERY, {"owner": owner, "name": name, "ref": f"refs/heads/{c['default_branch']}"})
        if not ((found.get("repository") or {}).get("ref")):
            raise AccessError(f"repo_edit: {ctx['repo']} has no branch {c['default_branch']!r}")


def _repo_edit_parts(step) -> list[str]:
    c, cur = step["change"], step["current"]
    flat = {**cur["features"], **cur["merge"], "is_template": cur["is_template"]}
    parts = []
    for key, label in (("description", "description"), ("homepage", "homepage")):
        if c.get(key) is not None and c[key] != cur[key]:
            parts.append(f"{label} → {say(c[key], 50) or '(none)'}")
    if c.get("default_branch") and c["default_branch"] != cur["default_branch"]:
        parts.append(f"default branch {cur['default_branch']} → {c['default_branch']}")
    if c.get("add_topics"):
        parts.append(f"topics + {', '.join(c['add_topics'])}")
    if c.get("remove_topics"):
        parts.append(f"topics − {', '.join(c['remove_topics'])}")
    for key in (*FEATURES, *MERGE, "is_template"):
        if c.get(key) is not None and c[key] != flat[key]:
            parts.append(f"{WORDS[key]} {_onoff(c[key])}")
    return parts


def _repo_edit_describe(step):
    parts = _repo_edit_parts(step)
    return f"Settings of {step['repo']['repo']}: " + ("; ".join(parts) if parts else "already as asked")


def _repo_edit_run(step, out):
    c = step["change"]
    argv = ["repo", "edit", step["repo"]["repo"]]
    for key, flag in (("description", "--description"), ("homepage", "--homepage"), ("default_branch", "--default-branch")):
        if c.get(key) is not None:
            argv += [flag, c[key]]
    for topic in c.get("add_topics") or []:
        argv += ["--add-topic", topic]
    for topic in c.get("remove_topics") or []:
        argv += ["--remove-topic", topic]
    for key in (*FEATURES, *MERGE, "is_template"):
        if c.get(key) is not None:
            argv.append(f"{FLAGS[key]}={'true' if c[key] else 'false'}")
    gh(argv)
    out.update({"repo": step["repo"]["repo"], "changed": _repo_edit_parts(step)})
    return out


def _repo_visibility_plan(step, planned):
    c = step["change"]
    ctx = planned.repo_of(c)
    _admin(ctx, "repo_visibility")
    current = reads.settings(ctx["repo"])
    if current["visibility"] == c["visibility"]:
        raise AccessError(f"repo_visibility: {ctx['repo']} is already {c['visibility']}")
    if c["visibility"] == "internal" and ctx["owner_type"] != "Organization":
        raise AccessError("repo_visibility: internal is for an organization's repository")
    step["repo"], step["from"] = ctx, current["visibility"]


def _repo_visibility_describe(step):
    to = step["change"]["visibility"]
    why = {"public": "anyone can read its code, issues and history",
           "private": "only people given access can read it; stars and forks of others go",
           "internal": "everyone in the enterprise can read it"}[to]
    return f"Make {step['repo']['repo']} {to} (was {step['from']}): {why}"


def _repo_visibility_run(step, out):
    gh(["repo", "edit", step["repo"]["repo"], "--visibility", step["change"]["visibility"],
        "--accept-visibility-change-consequences"])
    return {**out, "repo": step["repo"]["repo"], "visibility": step["change"]["visibility"]}


def _repo_archive_plan(step, planned):
    c = step["change"]
    ctx = planned.repo_of(c, archived_ok=True)
    _admin(ctx, "repo_archive")
    if bool(ctx["archived"]) != bool(c.get("unarchive")):
        raise AccessError(f"repo_archive: {ctx['repo']} is {'already archived' if ctx['archived'] else 'not archived'}")
    step["repo"] = ctx


def _repo_archive_describe(step):
    if step["change"].get("unarchive"):
        return f"Unarchive {step['repo']['repo']}: it takes changes again"
    return f"Archive {step['repo']['repo']}: read-only for everyone, issues and PRs included"


def _repo_archive_run(step, out):
    verb = "unarchive" if step["change"].get("unarchive") else "archive"
    gh(["repo", verb, step["repo"]["repo"], "--yes"])
    return {**out, "repo": step["repo"]["repo"], "archived": verb == "archive"}


# --- labels ---------------------------------------------------------------------------------------

def _color(change) -> str | None:
    if change.get("color") in (None, ""):
        return None
    if not COLOR.match(change["color"]):
        raise AccessError(f"{change['op']}: color is six hex digits, such as d73a4a")
    return change["color"].lstrip("#").lower()


def _label_plan(step, planned):
    c = step["change"]
    _color(c)
    step["repo"] = planned.repo_of(c)
    found = reads.labels(step["repo"]["repo"])
    existing = next((l for l in found if access.same(l["name"], c["name"])), None)
    if c["op"] == "label_create" and existing:
        raise AccessError(f"label_create: {step['repo']['repo']} already has {existing['name']!r}; change it with label_edit")
    if c["op"] == "label_edit":
        if not existing:
            raise AccessError(f"label_edit: {step['repo']['repo']} has no label {c['name']!r}")
        if not any(c.get(k) is not None for k in ("new_name", "color", "description")):
            raise AccessError("label_edit: new_name, color or description is required")
        taken = c.get("new_name") and next((l for l in found if access.same(l["name"], c["new_name"])
                                            and l is not existing), None)
        if taken:
            raise AccessError(f"label_edit: {step['repo']['repo']} already has {taken['name']!r}")
    step["label"] = existing


def _label_describe(step):
    c = step["change"]
    if c["op"] == "label_create":
        extra = ", ".join(x for x in (f"#{_color(c)}" if _color(c) else "",
                                      say(c.get("description"), 50) if c.get("description") else "") if x)
        return f"Create label {say(c['name'], 40)} in {step['repo']['repo']}" + (f" ({extra})" if extra else "")
    parts = [f"name → {say(c['new_name'], 40)}" if c.get("new_name") else "", f"color → #{_color(c)}" if _color(c) else "",
             f"description → {say(c['description'], 50)}" if c.get("description") is not None else ""]
    return f"Edit label {say(step['label']['name'], 40)} in {step['repo']['repo']}: " + "; ".join(p for p in parts if p)


def _label_run(step, out):
    c = step["change"]
    repo = step["repo"]["repo"]
    argv = ["label", "create" if c["op"] == "label_create" else "edit", "--repo", repo]
    if c.get("new_name"):
        argv += ["--name", c["new_name"]]
    if _color(c):
        argv += ["--color", _color(c)]
    if c.get("description") is not None:
        argv += ["--description", c["description"]]
    # The name last, after "--": a label named "-x" is a name, never a flag.
    gh([*argv, "--", c["name"] if c["op"] == "label_create" else step["label"]["name"]])
    return {**out, "repo": repo, "label": c.get("new_name") or c["name"]}


# --- milestones -----------------------------------------------------------------------------------

def _due(change) -> str | None:
    due = change.get("due")
    if due is None:
        return None
    if due != "" and not DATE.match(due):
        raise AccessError(f"{change['op']}: due is a date as YYYY-MM-DD (\"\" removes it)")
    return due


def _milestone_plan(step, planned):
    c = step["change"]
    _due(c)
    step["repo"] = planned.repo_of(c)
    title = c["title"] if c["op"] == "milestone_create" else c["milestone"]
    existing = next((m for m in reads.milestones(step["repo"]["repo"], "all") if access.same(m["title"], title)), None)
    if c["op"] == "milestone_create" and existing:
        raise AccessError(f"milestone_create: {step['repo']['repo']} already has milestone {existing['title']!r}")
    if c["op"] == "milestone_edit":
        if not existing:
            raise AccessError(f"milestone_edit: {step['repo']['repo']} has no milestone {title!r}")
        if not any(c.get(k) is not None for k in ("new_title", "due", "description", "state")):
            raise AccessError("milestone_edit: new_title, due, description or state is required")
        if c.get("new_title") and any(access.same(m["title"], c["new_title"]) and m["number"] != existing["number"]
                                      for m in reads.milestones(step["repo"]["repo"], "all")):
            raise AccessError(f"milestone_edit: {step['repo']['repo']} already has milestone {c['new_title']!r}")
    step["milestone"] = existing


def _milestone_describe(step):
    c = step["change"]
    repo = step["repo"]["repo"]
    if c["op"] == "milestone_create":
        extra = ", ".join(x for x in (f"due {c['due']}" if c.get("due") else "",
                                      say(c.get("description"), 50) if c.get("description") else "") if x)
        return f"Create milestone {say(c['title'], 40)} in {repo}" + (f" ({extra})" if extra else "")
    m = step["milestone"]
    parts = [f"title → {say(c['new_title'], 40)}" if c.get("new_title") else "",
             ("due removed" if c["due"] == "" else f"due {m['due'] or 'none'} → {c['due']}") if c.get("due") is not None else "",
             f"description → {say(c['description'], 50)}" if c.get("description") is not None else "",
             f"{'close' if c['state'] == 'closed' else 'reopen'}" if c.get("state") and c["state"] != m["state"] else ""]
    return f"Edit milestone {say(m['title'], 40)} in {repo}: " + ("; ".join(p for p in parts if p) or "already as asked")


def _milestone_run(step, out):
    c = step["change"]
    repo = step["repo"]["repo"]
    body: dict = {}
    if c["op"] == "milestone_create":
        body["title"] = c["title"]
    elif c.get("new_title"):
        body["title"] = c["new_title"]
    if c.get("due") is not None:
        # Midday UTC reads as the same date from UTC-11 to UTC+11.
        body["due_on"] = f"{c['due']}T12:00:00Z" if c["due"] else None
    if c.get("description") is not None:
        body["description"] = c["description"]
    if c.get("state"):
        body["state"] = c["state"]
    if c["op"] == "milestone_create":
        made = json.loads(gh(["api", "--method", "POST", f"repos/{repo}/milestones", "--input", "-"],
                             stdin=json.dumps(body)) or "{}")
        return {**out, "repo": repo, "milestone": made.get("title", c["title"]), "number": made.get("number")}
    gh(["api", "--method", "PATCH", f"repos/{repo}/milestones/{step['milestone']['number']}", "--input", "-"],
       stdin=json.dumps(body))
    return {**out, "repo": repo, "milestone": body.get("title", step["milestone"]["title"])}


for _op in (
        Op("repo_create", "admin",
           "repo (owner/name), visibility private|public|internal (default private), description, homepage, template "
           "(a template repository), license, gitignore, add_readme: a new repository, always on its own card",
           _repo_create_plan, _repo_create_describe, _repo_create_run, required=("repo",),
           optional=("visibility", "description", "homepage", "template", "license", "gitignore", "add_readme"),
           check=_repo_create_check),
        Op("repo_edit", "admin",
           "repo, description, homepage, add_/remove_topics, default_branch, has_issues / has_wiki / has_projects / "
           "has_discussions, allow_merge_commit / allow_squash_merge / allow_rebase_merge / allow_auto_merge / "
           "delete_branch_on_merge / allow_update_branch, is_template: a repository's settings",
           _repo_edit_plan, _repo_edit_describe, _repo_edit_run, optional=("repo", *EDIT_KEYS), check=_repo_edit_check),
        Op("repo_visibility", "admin", "repo, visibility private|public|internal", _repo_visibility_plan,
           _repo_visibility_describe, _repo_visibility_run, required=("visibility",), optional=("repo",)),
        Op("repo_archive", "admin", "repo, unarchive: archive a repository (read-only for everyone) or unarchive it",
           _repo_archive_plan, _repo_archive_describe, _repo_archive_run, optional=("repo", "unarchive")),
        Op("label_create", "create", "repo, name, color (six hex digits), description", _label_plan, _label_describe,
           _label_run, required=("name",), optional=("repo", "color", "description")),
        Op("label_edit", "create", "repo, name, new_name, color, description", _label_plan, _label_describe, _label_run,
           required=("name",), optional=("repo", "new_name", "color", "description")),
        Op("milestone_create", "create", "repo, title, due (YYYY-MM-DD), description", _milestone_plan,
           _milestone_describe, _milestone_run, required=("title",), optional=("repo", "due", "description")),
        Op("milestone_edit", "create", "repo, milestone (its title), new_title, due (\"\" removes), description, state "
           "open|closed", _milestone_plan, _milestone_describe, _milestone_run, required=("milestone",),
           optional=("repo", "new_title", "due", "description", "state"))):
    changes.register(_op)
