"""github-access: issue changes — creating, editing, relating, commenting on, closing and reopening
issues, and turning a board's draft into one.

Registered into ``changes.py``. Also the issue helpers later domains share: a milestone by title
and an issue's kind.
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
access = changes.access
AccessError = changes.AccessError
Op, say, gh, EARLIER = changes.Op, changes.say, changes.gh, changes.EARLIER

REASONS = ("completed", "not planned", "duplicate")
RELATIONS = ("add_sub_issues", "remove_sub_issues", "add_blocked_by", "remove_blocked_by")

changes.key("issue", "str")
changes.key("append_body", "str", text=True)
changes.key("comment", "str", text=True)
changes.key("reason", "str", enum=list(REASONS))
changes.key("kind", "str", text=True)
changes.key("milestone", "str", text=True)
changes.key("create_milestone", "bool")
changes.key("parent", "str")
changes.key("remove_parent", "bool")
changes.key("board_fields", "map", text=True)
for _name, _text in (("labels", True), ("assignees", False), ("blocked_by", False), ("add_labels", True),
                     ("remove_labels", False), ("add_assignees", False), ("remove_assignees", False),
                     *((r, False) for r in RELATIONS)):
    changes.key(_name, "list", text=_text)

# An issue edit that touches more than its own words notifies people or changes how it is filed.
EDIT_NOTIFIES = ("kind", "add_labels", "remove_labels", "add_assignees", "remove_assignees", "milestone")
EDIT_KEYS = ("title", "body", "append_body", "kind", "add_labels", "remove_labels", "add_assignees",
             "remove_assignees", "milestone", "create_milestone")
MENTION = re.compile(r"(?<![\w`/.@-])@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:/[A-Za-z0-9_.-]+)?")
KIND_COLORS = {"feature": "0E8A16", "enhancement": "1D76DB", "bug": "D73A4A", "task": "6F42C1", "chore": "BFD4F2",
               "docs": "0075CA", "test": "FBCA04", "design": "E99695"}


# --- shared helpers -------------------------------------------------------------------------------

def url(repo: str, number: int) -> str:
    return f"https://github.com/{repo}/issues/{number}"


def ref_url(ref: str, repo: str, created: dict | None = None) -> str:
    """The URL of an issue reference; ``$N`` is the issue change N of this list created
    (``created``: change number -> (repo, number), filled by ``apply``)."""
    match = EARLIER.match(ref.strip())
    if match:
        if int(match.group(1)) not in (created or {}):
            raise AccessError(f"{ref}: change {match.group(1)} created no issue")
        r, n = created[int(match.group(1))]
    else:
        r, n = access.parse_issue(ref, repo)
    return url(r, n)


def short(issue_url: str) -> str:
    r, n = access.parse_issue(issue_url)
    return f"{r}#{n}"


def number_of(url_out: str) -> int:
    match = re.search(r"/issues/(\d+)\s*$", url_out.strip())
    if not match:
        raise AccessError(f"gh printed no issue URL: {url_out.strip()[:200]}")
    return int(match.group(1))


def milestone(repo: str, title: str, create: bool) -> str:
    pages = changes.gh_json(["api", "--paginate", "--slurp", f"repos/{repo}/milestones?state=all&per_page=100"])
    found = next((m for page in pages for m in page if access.same(m.get("title"), title)), None)
    if found:
        return found["title"]
    if not create:
        raise AccessError(f"no milestone {title!r} in {repo}; set create_milestone to make it")
    return changes.gh_json(["api", f"repos/{repo}/milestones", "-f", f"title={title}"])["title"]


def apply_kind(repo: str, number: int, kind: str) -> str:
    """The kind lands as the organization's Issue Type when it defines one, else a type:<kind> label;
    the other type:* labels come off."""
    kind = kind.strip()
    match = next((t for t in access.issue_types(repo) if access.same(t, kind)), None)
    current = changes.gh_json(["issue", "view", str(number), "--repo", repo, "--json", "labels"]).get("labels") or []
    stale = [l["name"] for l in current if l["name"].lower().startswith(access.LABEL_PREFIX)]
    if match:
        gh(["issue", "edit", str(number), "--repo", repo, "--type", match])
        landed = f"type {match}"
    else:
        label = f"{access.LABEL_PREFIX}{kind.lower()}"
        stale = [l for l in stale if not access.same(l, label)]
        listed = json.loads(gh(["label", "list", "--repo", repo, "--search", label, "--json", "name", "--limit", "100"]) or "[]")
        names = [l["name"] for l in listed]
        if not any(access.same(n, label) for n in names):
            gh(["label", "create", label, "--repo", repo, "--color", KIND_COLORS.get(kind.lower(), "EDEDED"),
                "--description", f"Kind: {kind}"])
        gh(["issue", "edit", str(number), "--repo", repo, "--add-label", label])
        landed = f"label {label}"
    for label in stale:
        gh(["issue", "edit", str(number), "--repo", repo, "--remove-label", label])
    return landed


def _ref(step: dict) -> str:
    return f"{step['repo']['repo']}#{step['number']}"


# --- draft_promote --------------------------------------------------------------------------------

def _draft_promote_plan(step, planned):
    change = step["change"]
    it = board.plan_item(step, planned, draft=True)
    step["repo"] = planned.repo_of(change)
    # Promoting publishes the draft's words where the repository's readers see them: its title and
    # body as they will be then, after the earlier edits and notes of this list.
    title, body = it["title"], it["body"]
    for prior in planned.steps:
        p = prior["change"]
        if p.get("item") != change["item"]:
            continue
        if p["op"] == "draft_edit":
            title = p["title"] if p.get("title") is not None else title
            body = p["body"] if p.get("body") is not None else body
        elif p["op"] == "draft_note":
            body = f"{body.rstrip()}\n\n{p['text'].strip()}\n" if body.strip() else f"{p['text'].strip()}\n"
    step["carried"] = [("draft title", title), ("draft body", body)]


def _draft_promote_run(step, out):
    c, repo = step["change"], step["repo"]
    data = access.graphql("mutation($item:ID!,$repo:ID!){convertProjectV2DraftIssueItemToIssue(input:{itemId:$item,"
                          "repositoryId:$repo}){item{content{... on Issue{number url}}}}}",
                          {"item": c["item"], "repo": repo["id"]})
    content = (((data.get("convertProjectV2DraftIssueItemToIssue") or {}).get("item")) or {}).get("content") or {}
    if not content.get("number"):
        raise AccessError("the draft was not converted")
    number = content["number"]
    out.update({"issue": f"{repo['repo']}#{number}", "url": content.get("url")})
    if c.get("kind"):
        out["kind"] = apply_kind(repo["repo"], number, c["kind"])
    edit = []
    for label in c.get("labels") or []:
        edit += ["--add-label", label]
    if c.get("milestone"):
        edit += ["--milestone", milestone(repo["repo"], c["milestone"], bool(c.get("create_milestone")))]
    if edit:
        gh(["issue", "edit", str(number), "--repo", repo["repo"], *edit])
    return out


# --- issue_create ---------------------------------------------------------------------------------

def _issue_create_plan(step, planned):
    change = step["change"]
    step["repo"] = planned.repo_of(change)
    for ref in [change.get("parent"), *(change.get("blocked_by") or [])]:
        if ref:
            planned.repo(planned.earlier_repo(ref) or access.parse_issue(ref, step["repo"]["repo"])[0])
    if "board_fields" in change:
        step["board"] = planned.list_board()
        board.plan_fields(step, planned, change.get("board_fields"))


def _issue_create_describe(step):
    c = step["change"]
    named = lambda ref: EARLIER.sub(r"change \1's issue", ref.strip())  # noqa: E731
    extra = [f"kind {c['kind']}" if c.get("kind") else "", f"parent {named(c['parent'])}" if c.get("parent") else "",
             f"after {', '.join(map(named, c['blocked_by']))}" if c.get("blocked_by") else "",
             f"milestone {c['milestone']}" if c.get("milestone") else "",
             f"assign {', '.join(c['assignees'])}" if c.get("assignees") else ""]
    extra = [e for e in extra if e]
    return f"Create issue in {step['repo']['repo']}: {say(c['title'], 60)}" + (f" ({say('; '.join(extra), 60)})" if extra else "")


def _issue_create_run(step, out):
    c = step["change"]
    repo = step["repo"]["repo"]
    argv = ["issue", "create", "--repo", repo, "--title", c["title"], "--body-file", "-"]
    for label in c.get("labels") or []:
        argv += ["--label", label]
    for who in c.get("assignees") or []:
        argv += ["--assignee", who]
    if c.get("milestone"):
        argv += ["--milestone", milestone(repo, c["milestone"], bool(c.get("create_milestone")))]
    number = number_of(gh(argv, stdin=c.get("body") or ""))
    out.update({"issue": f"{repo}#{number}", "url": url(repo, number)})
    if c.get("kind"):
        out["kind"] = apply_kind(repo, number, c["kind"])
    if c.get("parent"):
        parent = ref_url(c["parent"], repo, step.get("created"))
        gh(["issue", "edit", str(number), "--repo", repo, "--parent", parent])
        out["parent"] = short(parent)
    for ref in c.get("blocked_by") or []:
        blocker = ref_url(ref, repo, step.get("created"))
        gh(["issue", "edit", str(number), "--repo", repo, "--add-blocked-by", blocker])
        out.setdefault("blocked_by", []).append(short(blocker))
    if step.get("board"):
        out["item"] = board.add_to_board(step["board"], url(repo, number))
        if c.get("board_fields"):
            out["fields"] = board.set_fields(step["board"], out["item"], c["board_fields"], [])
    return out


# --- the ops on one issue -------------------------------------------------------------------------

def plan_issue(step, planned):
    """The issue a change names and every repository the change writes to: its own, and those of the
    issues it relates (a relation writes on both ends)."""
    change = step["change"]
    repo, number = access.parse_issue(change["issue"], planned.default_repo)
    step["repo"] = planned.repo(repo)
    step["number"] = number
    for name in ("parent", *RELATIONS):
        refs = change.get(name)
        for ref in ([refs] if isinstance(refs, str) else refs or []):
            planned.repo(access.parse_issue(ref, repo)[0])
    if change["op"] == "issue_relate" and (change.get("parent") or change.get("remove_parent")):
        # Replacing or removing a parent also changes the old parent's sub-issue list.
        current = access.issue(repo, number, comments=0).get("parent")
        if current:
            planned.repo(current["repo"])


def _issue_edit_check(change):
    if change.get("body") is not None and change.get("append_body") is not None:
        raise AccessError("issue_edit: body or append_body, not both")
    if not any(changes.given(change, k) for k in EDIT_KEYS if k != "create_milestone"):
        raise AccessError("issue_edit: nothing to change")


def _issue_edit_class(change):
    if any(changes.given(change, k) for k in EDIT_NOTIFIES):
        return "create"
    # A mention in an issue's own words notifies the person or team it names.
    if any(MENTION.search(change.get(k) or "") for k in ("title", "body", "append_body")):
        return "create"
    return "routine"


def _issue_edit_describe(step):
    c = step["change"]
    parts = []
    if c.get("title") is not None:
        parts.append(f"title → {say(c['title'], 50)}")
    if c.get("body") is not None:
        parts.append(f"body replaced ({len(c['body'])} chars)")
    if c.get("append_body"):
        parts.append(f"append: {say(c['append_body'], 60)}")
    for name in EDIT_NOTIFIES:
        if changes.given(c, name):
            value = c[name] if isinstance(c[name], str) else ", ".join(c[name])
            parts.append("milestone removed" if name == "milestone" and value == "" else
                         f"{name.replace('_', ' ')} {say(value, 40)}")
    return f"Edit {_ref(step)}: " + "; ".join(parts)


def _issue_edit_run(step, out):
    c = step["change"]
    repo, number = step["repo"]["repo"], step["number"]
    argv = ["issue", "edit", str(number), "--repo", repo]
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
            ["--milestone", milestone(repo, c["milestone"], bool(c.get("create_milestone")))]
    out["issue"] = f"{repo}#{number}"
    if len(argv) > 5:
        gh(argv, stdin=stdin)
        out["edited"] = True
    if c.get("kind"):
        out["kind"] = apply_kind(repo, number, c["kind"])
    return out


def _issue_comment_run(step, out):
    repo, number = step["repo"]["repo"], step["number"]
    out["issue"] = f"{repo}#{number}"
    out["url"] = gh(["issue", "comment", str(number), "--repo", repo, "--body-file", "-"],
                    stdin=step["change"]["body"]).strip() or None
    return out


def _issue_relate_check(change):
    if change.get("parent") and change.get("remove_parent"):
        raise AccessError("issue_relate: parent or remove_parent, not both")
    if not any(change.get(k) for k in ("parent", "remove_parent", *RELATIONS)):
        raise AccessError("issue_relate: nothing to change")


def _issue_relate_describe(step):
    c = step["change"]
    parts = []
    if c.get("parent"):
        parts.append(f"parent → {c['parent']}")
    if c.get("remove_parent"):
        parts.append("remove parent")
    for name in RELATIONS:
        if c.get(name):
            parts.append(f"{name.replace('_', ' ')} {', '.join(c[name])}")
    return f"Relate {_ref(step)}: {say('; '.join(parts), 100)}"


def _relate(repo: str, number: int, change: dict, done: list[str]) -> list[str]:
    current = access.issue(repo, number, comments=0)
    key = lambda b: f"{b['repo'].lower()}#{b['number']}"  # noqa: E731
    target = lambda ref: access.parse_issue(ref, repo)  # noqa: E731
    if change.get("parent"):
        r, n = target(change["parent"])
        if not current["parent"] or key(current["parent"]) != f"{r.lower()}#{n}":
            gh(["issue", "edit", str(number), "--repo", repo, "--parent", url(r, n)])
            done.append(f"parent {r}#{n}")
    if change.get("remove_parent") and current["parent"]:
        gh(["issue", "edit", str(number), "--repo", repo, "--remove-parent"])
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
                gh(["issue", "edit", str(number), "--repo", repo, flags[0], url(r, n)])
                done.append(f"{add_key.replace('_', ' ')} {r}#{n}")
        for ref in change.get(remove_key) or []:
            r, n = target(ref)
            if f"{r.lower()}#{n}" in present:
                gh(["issue", "edit", str(number), "--repo", repo, flags[1], url(r, n)])
                done.append(f"{remove_key.replace('_', ' ')} {r}#{n}")
    return done


def _issue_relate_run(step, out):
    out["issue"] = _ref(step)
    out["done"] = []
    _relate(step["repo"]["repo"], step["number"], step["change"], out["done"])
    return out


def _issue_close_run(step, out):
    c = step["change"]
    argv = ["issue", "close", str(step["number"]), "--repo", step["repo"]["repo"], "--reason", c["reason"]]
    if c.get("comment"):
        argv += ["--comment", c["comment"]]
    gh(argv)
    return {"issue": _ref(step), "closed": c["reason"]}


def _issue_reopen_run(step, out):
    gh(["issue", "reopen", str(step["number"]), "--repo", step["repo"]["repo"]])
    return {"issue": _ref(step), "reopened": True}


for _op in (
        Op("draft_promote", "create", "item, repo, kind, labels, milestone, create_milestone", _draft_promote_plan,
           lambda s: f"Turn draft {say(s['item']['title'], 50)} into an issue in {s['repo']['repo']}", _draft_promote_run,
           required=("item",), optional=("repo", "kind", "labels", "milestone", "create_milestone"), creates_issue=True),
        Op("issue_create", "create",
           "repo, title, body, kind, labels, assignees, milestone, create_milestone, parent, blocked_by (either may be "
           "\"$N\": the issue change N of this list creates), board_fields: also put it on the board with these fields",
           _issue_create_plan, _issue_create_describe, _issue_create_run, required=("title",),
           optional=("repo", "body", "kind", "labels", "assignees", "milestone", "create_milestone", "parent", "blocked_by",
                     "board_fields"),
           needs_board=lambda c: "board_fields" in c, creates_issue=True),
        Op("issue_edit", "routine",
           "issue, title, body or append_body, kind, add_/remove_labels, add_/remove_assignees, milestone (\"\" removes), "
           "create_milestone", plan_issue, _issue_edit_describe, _issue_edit_run, required=("issue",), optional=EDIT_KEYS,
           check=_issue_edit_check, classify=_issue_edit_class),
        Op("issue_comment", "create", "issue, body", plan_issue,
           lambda s: f"Comment on {_ref(s)}: {say(s['change']['body'], 90)}", _issue_comment_run,
           required=("issue", "body")),
        Op("issue_relate", "create", "issue, parent or remove_parent, add_/remove_sub_issues, add_/remove_blocked_by",
           plan_issue, _issue_relate_describe, _issue_relate_run, required=("issue",),
           optional=("parent", "remove_parent", *RELATIONS), check=_issue_relate_check),
        Op("issue_close", "create", "issue, reason completed|not planned|duplicate, comment", plan_issue,
           lambda s: f"Close {_ref(s)} as {s['change']['reason']}" + (
               f", saying: {say(s['change']['comment'], 70)}" if s["change"].get("comment") else ""),
           _issue_close_run, required=("issue", "reason"), optional=("comment",)),
        Op("issue_reopen", "create", "issue", plan_issue, lambda s: f"Reopen {_ref(s)}", _issue_reopen_run,
           required=("issue",))):
    changes.register(_op)
