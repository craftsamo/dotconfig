"""github-access: GitHub Issues and Projects (v2) for the Assistant, read side.

The engine behind the plugin's read tools. Everything goes through the user's own ``gh`` login
(``gh api graphql``, the identity the workspace-repos inventory reads with); nothing is stored.

Shared with the write side (``changes.py``) and the mandates (``mandate.py``):

  graphql()       one query or mutation, typed variables on stdin, errors raised
  parse_*()       an issue as 12 / #12 / owner/repo#12 / URL, a repository, a project
  repo_context()  who owns a repository, whether it is private, the viewer's permission
  board_context() the same for a project board
  tier()          own / shared / other: what a write there may skip a card for
  resolve_board() explicit -> linked -> org -> user, with the routes considered
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import time

GH_TIMEOUT = 40
DEFAULT_BOARD = "Roadmap"
LIST_LIMIT = 100
ITEM_CAP = 2000
COMMENTS = 5

ISSUE_ACTIONS = ("view", "list")
BOARD_ACTIONS = ("resolve", "items")

# A write's target is one of three tiers, read from GitHub at the moment of the write:
#   own     the viewer's own private repository or board: nobody else reads it
#   shared  a repository or board others read: the viewer's public ones, an organization's the
#           viewer belongs to
#   other   anything else: someone else's tracker
TIERS = ("own", "shared", "other")


class AccessError(Exception):
    pass


# --- transport ------------------------------------------------------------------------------------

def _gh_env() -> dict:
    return {**os.environ, "GH_PROMPT_DISABLED": "1", "GH_NO_UPDATE_NOTIFIER": "1"}


def run_gh(argv: list[str], stdin: str | None = None, timeout: int = GH_TIMEOUT) -> subprocess.CompletedProcess:
    """``gh`` with no prompts; tests replace this one function."""
    try:
        return subprocess.run(["gh", *argv], input=stdin, capture_output=True, text=True, timeout=timeout,
                              env=_gh_env())
    except FileNotFoundError as exc:
        raise AccessError("gh is not installed") from exc
    except subprocess.TimeoutExpired as exc:
        raise AccessError(f"gh did not answer within {timeout}s") from exc


def graphql(query: str, variables: dict | None = None) -> dict:
    """``data`` of one GraphQL request; any error raises with GitHub's messages."""
    done = run_gh(["api", "graphql", "--input", "-"], stdin=json.dumps({"query": query, "variables": variables or {}}))
    try:
        body = json.loads(done.stdout or "{}")
    except json.JSONDecodeError:
        body = {}
    errors = body.get("errors") or []
    if errors or done.returncode != 0 or "data" not in body:
        detail = "; ".join(str(e.get("message", e)) for e in errors if isinstance(e, dict)) or \
            (done.stderr or done.stdout or "").strip().splitlines()[-1:] or [f"exit {done.returncode}"]
        raise AccessError(f"GitHub refused the request: {detail if isinstance(detail, str) else detail[0]}"[:500])
    return body["data"] or {}


def paginate(query: str, variables: dict, pick, limit: int) -> list:
    """Nodes of a connection whose query takes ``$after``; stops at ``limit``."""
    out, after = [], None
    while True:
        page = pick(graphql(query, {**variables, "after": after})) or {}
        out.extend(page.get("nodes") or [])
        info = page.get("pageInfo") or {}
        if len(out) >= limit:
            return out[:limit]
        if not info.get("hasNextPage") or not info.get("endCursor"):
            return out
        after = info["endCursor"]


# --- references -----------------------------------------------------------------------------------

_ISSUE_URL = re.compile(r"^https?://(?:www\.)?github\.com/([^/\s]+/[^/\s]+)/(issues|pull)/(\d+)(?:[/?#].*)?$")
_ISSUE_SHORT = re.compile(r"^([^/\s#]+/[^/\s#]+)#(\d+)$")
_ISSUE_NUMBER = re.compile(r"^#?(\d+)$")
_REPO = re.compile(r"^(?:https?://(?:www\.)?github\.com/|git@github\.com:)?([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$")
_PROJECT_URL = re.compile(r"^https?://(?:www\.)?github\.com/(?:orgs|users)/([^/\s]+)/projects/(\d+)(?:[/?#].*)?$")
_PROJECT_SHORT = re.compile(r"^([A-Za-z0-9_.-]+)/(\d+)$")
LOGIN = re.compile(r"^(?:@me|[A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))$")


def parse_issue(ref, default_repo: str | None = None, allow_pr: bool = False) -> tuple[str, int]:
    """(owner/repo, number) of a github.com issue reference; a bare number needs ``default_repo``.
    A pull request URL is accepted only with ``allow_pr`` (a board item can be a PR)."""
    text = str(ref or "").strip()
    match = _ISSUE_URL.match(text)
    if match:
        if match.group(2) == "pull" and not allow_pr:
            raise AccessError(f"{text} is a pull request, not an issue")
        return parse_repo(match.group(1)), int(match.group(3))
    match = _ISSUE_SHORT.match(text)
    if match:
        return parse_repo(match.group(1)), int(match.group(2))
    match = _ISSUE_NUMBER.match(text)
    if match:
        if not default_repo:
            raise AccessError(f"issue {text} needs its repository: owner/repo#N, a URL, or repo")
        return parse_repo(default_repo), int(match.group(1))
    raise AccessError(f"not an issue reference: {text!r} (a number, #N, owner/repo#N or a URL)")


def parse_repo(ref) -> str:
    match = _REPO.match(str(ref or "").strip())
    if not match:
        raise AccessError(f"not a repository: {ref!r} (owner/repo or its URL)")
    return f"{match.group(1)}/{match.group(2)}"


def parse_project(ref, owner: str | None = None) -> dict:
    """{owner?, number?, title?} of a project reference: URL, owner/N, N (with owner) or a title."""
    text = str(ref or "").strip()
    if not text:
        return {"owner": owner}
    for pattern in (_PROJECT_URL, _PROJECT_SHORT):
        match = pattern.match(text)
        if match:
            return {"owner": match.group(1), "number": int(match.group(2))}
    if text.isdigit():
        return {"owner": owner, "number": int(text)}
    return {"owner": owner, "title": text}


def same(a, b) -> bool:
    return str(a or "").strip().lower() == str(b or "").strip().lower()


# --- who the viewer is, and what a target is ------------------------------------------------------

_CACHE: dict[str, tuple[float, object]] = {}
_CACHE_LOCK = threading.Lock()
CACHE_TTL = 300


class _Unsure:
    """A loader's answer that must not be cached (it came from an error)."""

    def __init__(self, value):
        self.value = value


def _cached(key: str, load, fresh: bool = False):
    now = time.monotonic()
    with _CACHE_LOCK:
        hit = _CACHE.get(key)
        if hit and not fresh and now - hit[0] < CACHE_TTL:
            return hit[1]
    value = load()
    if isinstance(value, _Unsure):
        return value.value
    with _CACHE_LOCK:
        _CACHE[key] = (now, value)
    return value


def forget() -> None:
    with _CACHE_LOCK:
        _CACHE.clear()


def viewer(fresh: bool = False) -> str:
    return _cached("viewer", lambda: graphql("query{viewer{login}}")["viewer"]["login"], fresh)


def _member(org: str, fresh: bool = False) -> bool:
    def load():
        try:
            data = graphql("query($login:String!){organization(login:$login){viewerIsAMember}}", {"login": org})
            return bool((data.get("organization") or {}).get("viewerIsAMember"))
        except AccessError:
            return _Unsure(False)  # unknown reads as not a member: the stricter tier, never cached
    return _cached(f"member:{org.lower()}", load, fresh)


def tier(owner: str, owner_type: str, private: bool, fresh: bool = False) -> str:
    """own / shared / other for a target owned by ``owner``; ``private`` means only people the owner
    let in read it. ``fresh`` re-reads membership (a write's own check)."""
    if owner_type == "User" and same(owner, viewer(fresh)):
        return "own" if private else "shared"
    if owner_type == "Organization" and _member(owner, fresh):
        return "shared"
    return "other"


REPO_QUERY = ("query($owner:String!,$name:String!){repository(owner:$owner,name:$name){id nameWithOwner "
              "isPrivate isArchived viewerPermission owner{__typename login}}}")


def repo_context(repo: str, fresh: bool = False) -> dict:
    """A repository as a write sees it. ``fresh`` skips the cache (a write's own check)."""
    repo = parse_repo(repo)

    def load():
        owner, name = repo.split("/", 1)
        r = graphql(REPO_QUERY, {"owner": owner, "name": name}).get("repository")
        if not r:
            raise AccessError(f"repository {repo} not found or not visible to the viewer")
        kind = r["owner"]["__typename"]
        permission = r.get("viewerPermission")
        return {"id": r["id"], "repo": r["nameWithOwner"], "owner": r["owner"]["login"], "owner_type": kind,
                "private": bool(r.get("isPrivate")), "archived": bool(r.get("isArchived")),
                "permission": permission, "can_write": permission in ("ADMIN", "MAINTAIN", "WRITE"),
                "tier": tier(r["owner"]["login"], kind, bool(r.get("isPrivate")), fresh)}
    return _cached(f"repo:{repo.lower()}", load, fresh)


PROJECT_FIELDS = ("id number title url closed public viewerCanUpdate "
                  "owner{__typename ... on User{login} ... on Organization{login}}")


def _board(p: dict, fresh: bool = False) -> dict:
    kind = (p.get("owner") or {}).get("__typename", "User")
    owner = (p.get("owner") or {}).get("login", "")
    return {"id": p["id"], "number": p["number"], "title": p["title"], "url": p["url"], "closed": bool(p.get("closed")),
            "public": bool(p.get("public")), "can_update": bool(p.get("viewerCanUpdate")), "owner": owner,
            "owner_type": kind, "tier": tier(owner, kind, not p.get("public"), fresh)}


def board_context(project_id: str, fresh: bool = False) -> dict:
    """A board as a write sees it, read now (boards are never cached)."""
    data = graphql(f"query($id:ID!){{node(id:$id){{... on ProjectV2{{{PROJECT_FIELDS}}}}}}}", {"id": project_id})
    node = data.get("node") or {}
    if not node.get("id"):
        raise AccessError(f"project {project_id} not found")
    return _board(node, fresh)


def _owner_root(login: str) -> str:
    data = graphql("query($login:String!){repositoryOwner(login:$login){__typename}}", {"login": login})
    kind = (data.get("repositoryOwner") or {}).get("__typename")
    if kind not in ("User", "Organization"):
        raise AccessError(f"no user or organization named {login!r}")
    return "organization" if kind == "Organization" else "user"


def boards_titled(login: str, title: str) -> list[dict]:
    """Open boards of ``login`` (or the viewer, for "@me") whose title is ``title``."""
    if login == "@me":
        data = graphql(f"query($q:String!){{viewer{{projectsV2(first:20,query:$q){{nodes{{{PROJECT_FIELDS}}}}}}}}}",
                       {"q": title})
        nodes = ((data.get("viewer") or {}).get("projectsV2") or {}).get("nodes") or []
    else:
        root = _owner_root(login)
        data = graphql(f"query($login:String!,$q:String!){{{root}(login:$login){{projectsV2(first:20,query:$q)"
                       f"{{nodes{{{PROJECT_FIELDS}}}}}}}}}", {"login": login, "q": title})
        nodes = ((data.get(root) or {}).get("projectsV2") or {}).get("nodes") or []
    return [b for b in (_board(n) for n in nodes if n) if same(b["title"], title) and not b["closed"]]


def board_by_number(login: str, number: int) -> dict:
    login = viewer() if login == "@me" else login
    root = _owner_root(login)
    data = graphql(f"query($login:String!,$n:Int!){{{root}(login:$login){{projectV2(number:$n){{{PROJECT_FIELDS}}}}}}}",
                   {"login": login, "n": number})
    node = (data.get(root) or {}).get("projectV2")
    if not node:
        raise AccessError(f"project {login}/{number} not found or not visible to the viewer")
    return _board(node)


def linked_boards(repo: str) -> list[dict]:
    owner, name = parse_repo(repo).split("/", 1)
    data = graphql(f"query($owner:String!,$name:String!){{repository(owner:$owner,name:$name){{projectsV2(first:20)"
                   f"{{nodes{{{PROJECT_FIELDS}}}}}}}}}", {"owner": owner, "name": name})
    nodes = (((data.get("repository") or {}).get("projectsV2")) or {}).get("nodes") or []
    return [b for b in (_board(n) for n in nodes if n) if not b["closed"]]


def resolve_board(project=None, owner=None, repo=None) -> dict:
    """{board, route, considered}: the board a call means.

    An explicit ``project`` wins; otherwise a writable board linked to ``repo`` (the only one, or
    with a title the one titled so; several and no title is an error, never a guess), the owning
    organization's Roadmap, then the viewer's. A route is passed over when its board is missing or
    read-only, and every route is reported."""
    ref = parse_project(project, (owner or "").strip() or None)
    considered = []
    if ref.get("number") is not None:
        login = ref.get("owner") or (repo_context(repo)["owner"] if repo else None)
        if not login:
            raise AccessError(f"project {ref['number']} needs its owner: owner/N, a URL, or owner")
        board = board_by_number(login, ref["number"])
        return {"board": board, "route": "explicit", "considered": [{"route": "explicit", "outcome": f"{login}/{ref['number']}"}]}
    if ref.get("owner"):
        title = ref.get("title") or DEFAULT_BOARD
        found = boards_titled(ref["owner"], title)
        if len(found) != 1:
            raise AccessError(f"{len(found) or 'no'} open board(s) titled {title!r} for {ref['owner']}; "
                              "pass project as a URL or owner/N")
        return {"board": found[0], "route": "explicit", "considered": [{"route": "explicit", "outcome": f"{ref['owner']}/{title!r}"}]}
    wanted = ref.get("title") or DEFAULT_BOARD
    if repo:
        ctx = repo_context(repo)
        linked = linked_boards(ctx["repo"])
        writable = [b for b in linked if b["can_update"]]
        candidates = [b for b in writable if same(b["title"], wanted)] if ref.get("title") else writable
        if len(candidates) == 1:
            pick = candidates[0]
            considered.append({"route": "linked", "outcome": f"{pick['owner']}/{pick['number']} {pick['title']!r}"})
            return {"board": pick, "route": "linked", "considered": considered}
        if len(candidates) > 1:
            named = f" titled {wanted!r}" if ref.get("title") else ""
            raise AccessError(f"{len(candidates)} writable boards{named} are linked to {ctx['repo']} "
                              f"({', '.join(b['owner'] + '/' + str(b['number']) for b in candidates)}); "
                              "pass project as a URL or owner/N")
        considered.append({"route": "linked", "outcome": "no board linked" if not linked else "no writable linked board"
                           if not ref.get("title") else f"no linked board titled {wanted!r}"})
        if ctx["owner_type"] == "Organization":
            found = [b for b in boards_titled(ctx["owner"], wanted) if b["can_update"]]
            if found:
                considered.append({"route": "org", "outcome": f"{found[0]['owner']}/{found[0]['number']}"})
                return {"board": found[0], "route": "org", "considered": considered}
            considered.append({"route": "org", "outcome": f"no writable board titled {wanted!r} in {ctx['owner']}"})
        else:
            considered.append({"route": "org", "outcome": "the repository is user-owned"})
    else:
        considered += [{"route": "linked", "outcome": "no repository given"}, {"route": "org", "outcome": "no repository given"}]
    own = boards_titled("@me", wanted)
    if own:
        considered.append({"route": "user", "outcome": f"{own[0]['owner']}/{own[0]['number']}"})
        return {"board": own[0], "route": "user", "considered": considered}
    considered.append({"route": "user", "outcome": f"no board titled {wanted!r} owned by the viewer"})
    raise AccessError("no board resolved: " + "; ".join(f"{c['route']}: {c['outcome']}" for c in considered) +
                      ". To make one: github_change board_create (owner, title, link_repo), after the user agrees")


# --- issue reads ----------------------------------------------------------------------------------

BRIEF = "number title url state repository{nameWithOwner}"
LABEL_PREFIX = "type:"


def _brief(n: dict) -> dict:
    return {"number": n["number"], "title": n["title"], "url": n["url"], "state": n["state"],
            "repo": (n.get("repository") or {}).get("nameWithOwner", "")}


def kind_of(issue_type, labels: list[str]):
    if issue_type:
        return issue_type
    for label in labels:
        if label.lower().startswith(LABEL_PREFIX):
            return label[len(LABEL_PREFIX):]
    return None


ISSUE_QUERY = (
    "query($owner:String!,$name:String!,$n:Int!,$comments:Int!,$withComments:Boolean!){"
    "repository(owner:$owner,name:$name){issue(number:$n){"
    "id number title url state stateReason body createdAt updatedAt author{login} repository{nameWithOwner} "
    "assignees(first:20){nodes{login}} labels(first:30){nodes{name}} milestone{number title dueOn} "
    f"issueType{{name}} parent{{{BRIEF}}} subIssues(first:100){{nodes{{{BRIEF}}}}} "
    "subIssuesSummary{total completed percentCompleted} linkedBranches(first:20){nodes{ref{name}}} "
    "closedByPullRequestsReferences(first:20,includeClosedPrs:true){nodes{number title url state merged}} "
    "projectItems(first:20){nodes{id isArchived project{id number title url}}} "
    "comments(last:$comments) @include(if:$withComments){totalCount nodes{author{login} createdAt body url}}}}}")
DEPS_QUERY = ("query($owner:String!,$name:String!,$n:Int!){repository(owner:$owner,name:$name){issue(number:$n){"
              f"blockedBy(first:50){{nodes{{{BRIEF}}}}} blocking(first:50){{nodes{{{BRIEF}}}}}}}}}}}")


def issue(repo: str, number: int, comments: int = COMMENTS) -> dict:
    owner, name = parse_repo(repo).split("/", 1)
    data = graphql(ISSUE_QUERY, {"owner": owner, "name": name, "n": number, "comments": max(1, comments),
                                 "withComments": comments > 0})
    i = (data.get("repository") or {}).get("issue")
    if not i:
        raise AccessError(f"issue {repo}#{number} not found")
    labels = [l["name"] for l in (i.get("labels") or {}).get("nodes") or []]
    try:
        deps = graphql(DEPS_QUERY, {"owner": owner, "name": name, "n": number})["repository"]["issue"]
        blocked_by = [_brief(n) for n in deps["blockedBy"]["nodes"]]
        blocking = [_brief(n) for n in deps["blocking"]["nodes"]]
        deps_error = None
    except (AccessError, KeyError, TypeError) as exc:
        blocked_by, blocking, deps_error = [], [], str(exc)
    summary = i.get("subIssuesSummary")
    return {
        "number": i["number"], "title": i["title"], "url": i["url"], "state": i["state"],
        "state_reason": i.get("stateReason"), "repo": i["repository"]["nameWithOwner"], "body": i.get("body") or "",
        "author": (i.get("author") or {}).get("login"),
        "assignees": [a["login"] for a in (i.get("assignees") or {}).get("nodes") or []],
        "labels": labels, "kind": kind_of((i.get("issueType") or {}).get("name"), labels),
        "milestone": i.get("milestone"),
        "parent": _brief(i["parent"]) if i.get("parent") else None,
        "sub_issues": [_brief(n) for n in (i.get("subIssues") or {}).get("nodes") or []],
        "sub_issue_progress": {"total": summary["total"], "completed": summary["completed"],
                               "percent": summary["percentCompleted"]} if summary else None,
        "blocked_by": blocked_by, "blocking": blocking, "dependencies_error": deps_error,
        "linked_branches": [b["ref"]["name"] for b in (i.get("linkedBranches") or {}).get("nodes") or [] if b.get("ref")],
        "closing_prs": (i.get("closedByPullRequestsReferences") or {}).get("nodes") or [],
        "boards": [{"item": p["id"], "archived": bool(p.get("isArchived")), **(p.get("project") or {})}
                   for p in (i.get("projectItems") or {}).get("nodes") or []],
        "comments": [{"author": (c.get("author") or {}).get("login"), "at": c.get("createdAt"), "body": c.get("body"),
                      "url": c.get("url")} for c in ((i.get("comments") or {}).get("nodes") or [])],
        "comment_count": (i.get("comments") or {}).get("totalCount"),
        "created": i.get("createdAt"), "updated": i.get("updatedAt"),
    }


SEARCH_QUERY = ("query($q:String!,$first:Int!,$after:String){search(type:ISSUE,query:$q,first:$first,after:$after){"
                "pageInfo{hasNextPage endCursor}nodes{... on Issue{number title url state updatedAt issueType{name} "
                "repository{nameWithOwner} "
                "labels(first:20){nodes{name}} assignees(first:10){nodes{login}} milestone{title} parent{number} "
                "subIssuesSummary{total completed}}}}}")


def _issue_row(n: dict) -> dict:
    labels = [l["name"] for l in (n.get("labels") or {}).get("nodes") or []]
    summary = n.get("subIssuesSummary")
    return {"number": n["number"], "repo": (n.get("repository") or {}).get("nameWithOwner", ""), "title": n["title"],
            "url": n["url"], "state": n["state"],
            "kind": kind_of((n.get("issueType") or {}).get("name"), labels), "labels": labels,
            "assignees": [a["login"] for a in (n.get("assignees") or {}).get("nodes") or []],
            "milestone": (n.get("milestone") or {}).get("title"), "parent": (n.get("parent") or {}).get("number"),
            "sub_issues": {"total": summary["total"], "completed": summary["completed"]} if summary else None,
            "updated": n.get("updatedAt")}


def _quoted(value: str) -> str:
    if any(ch in value for ch in '"\\\r\n'):
        raise AccessError(f"{value!r} cannot be used as a search value")
    return f'"{value}"'


def issue_list(args: dict) -> dict:
    repo = parse_repo(_text(args, "repo"))
    state = args.get("state") or "open"
    if state not in ("open", "closed", "all"):
        raise AccessError("state is open, closed or all")
    limit = _count(args, "limit", 30, LIST_LIMIT)
    if args.get("parent"):
        parent_repo, number = parse_issue(args["parent"], repo)
        parent = issue(parent_repo, number, comments=0)
        subs = [s for s in parent["sub_issues"] if state == "all" or s["state"].lower() == state][:limit]
        return {"ok": True, "repo": repo, "parent": {"number": parent["number"], "title": parent["title"]},
                "count": len(subs), "issues": subs}
    parts = [f"repo:{repo}", "is:issue"]
    if state != "all":
        parts.append(f"state:{state}")
    if args.get("kind"):
        kind = _text(args, "kind")
        types = issue_types(repo)
        match = next((t for t in types if same(t, kind)), None)
        parts.append(f"type:{_quoted(match)}" if match else f"label:{_quoted(LABEL_PREFIX + kind.lower())}")
    if args.get("milestone"):
        value = _text(args, "milestone")
        parts.append("no:milestone" if value == "none" else f"milestone:{_quoted(value)}")
    if args.get("label"):
        parts.append(f"label:{_quoted(_text(args, 'label'))}")
    if args.get("assignee"):
        value = _text(args, "assignee")
        if value != "none" and not LOGIN.match(value):
            raise AccessError(f"assignee is a login, @me or none, not {value!r}")
        parts.append("no:assignee" if value == "none" else f"assignee:{value}")
    if args.get("query"):
        words = _text(args, "query")
        if re.search(r"(?:^|\s)-?(?:repo|org|user):", words):
            raise AccessError("query cannot name other repositories; list one repository per call")
        parts.append(words)
    query = " ".join(parts)
    nodes = paginate(SEARCH_QUERY, {"q": query, "first": min(limit, 100)}, lambda d: d.get("search"), limit)
    rows = [_issue_row(n) for n in nodes if n.get("number")]
    return {"ok": True, "repo": repo, "query": query, "count": len(rows), "issues": rows}


def issue_types(repo: str) -> list[str]:
    """The enabled Issue Types of the repository's organization; [] for a user-owned repository."""
    ctx = repo_context(repo)
    if ctx["owner_type"] != "Organization":
        return []

    def load():
        try:
            data = graphql("query($login:String!){organization(login:$login){issueTypes(first:25){nodes{name isEnabled}}}}",
                           {"login": ctx["owner"]})
            return [t["name"] for t in ((data.get("organization") or {}).get("issueTypes") or {}).get("nodes") or []
                    if t.get("isEnabled")]
        except AccessError:
            return _Unsure([])  # unknown reads as no types: the kind lands as a label, retried next time
    return _cached(f"types:{ctx['owner'].lower()}", load)


# --- board reads ----------------------------------------------------------------------------------

FIELD_NAME = "field{... on ProjectV2FieldCommon{name}}"
ITEM_FRAGMENT = (
    "id isArchived fieldValues(first:50){nodes{"
    f"... on ProjectV2ItemFieldTextValue{{text {FIELD_NAME}}} "
    f"... on ProjectV2ItemFieldNumberValue{{number {FIELD_NAME}}} "
    f"... on ProjectV2ItemFieldDateValue{{date {FIELD_NAME}}} "
    f"... on ProjectV2ItemFieldSingleSelectValue{{name {FIELD_NAME}}} "
    f"... on ProjectV2ItemFieldIterationValue{{title startDate {FIELD_NAME}}} "
    f"... on ProjectV2ItemFieldMilestoneValue{{milestone{{title}} {FIELD_NAME}}} "
    f"... on ProjectV2ItemFieldRepositoryValue{{repository{{nameWithOwner}} {FIELD_NAME}}} "
    f"... on ProjectV2ItemFieldLabelValue{{labels(first:20){{nodes{{name}}}} {FIELD_NAME}}} "
    f"... on ProjectV2ItemFieldUserValue{{users(first:10){{nodes{{login}}}} {FIELD_NAME}}}"
    "} content{__typename "
    "... on DraftIssue{id title body} "
    "... on Issue{id number title url state repository{nameWithOwner} issueType{name} labels(first:20){nodes{name}} "
    "parent{number} subIssuesSummary{total completed}} "
    "... on PullRequest{id number title url state repository{nameWithOwner}}}")


def _value(v: dict):
    if "text" in v:
        return v["text"]
    if "number" in v:
        return v["number"]
    if "date" in v:
        return v["date"]
    if "startDate" in v:
        return {"title": v.get("title"), "start": v.get("startDate")}
    if "name" in v:
        return v["name"]
    if "milestone" in v:
        return (v.get("milestone") or {}).get("title")
    if "repository" in v:
        return (v.get("repository") or {}).get("nameWithOwner")
    if "labels" in v:
        return [l["name"] for l in (v.get("labels") or {}).get("nodes") or []]
    if "users" in v:
        return [u["login"] for u in (v.get("users") or {}).get("nodes") or []]
    return None


def item(node: dict) -> dict:
    fields = {}
    for v in (node.get("fieldValues") or {}).get("nodes") or []:
        name = ((v or {}).get("field") or {}).get("name")
        if name:
            fields[name] = _value(v)
    c = node.get("content") or {}
    kind = c.get("__typename")
    if kind == "DraftIssue":
        content = {"type": "draft", "id": c["id"], "title": c.get("title", ""), "body": c.get("body") or ""}
    elif kind in ("Issue", "PullRequest"):
        labels = [l["name"] for l in (c.get("labels") or {}).get("nodes") or []]
        summary = c.get("subIssuesSummary")
        content = {"type": "issue" if kind == "Issue" else "pr", "id": c["id"], "number": c["number"],
                   "title": c["title"], "url": c["url"], "state": c["state"],
                   "repo": (c.get("repository") or {}).get("nameWithOwner", ""),
                   "kind": kind_of((c.get("issueType") or {}).get("name"), labels),
                   "parent": (c.get("parent") or {}).get("number"),
                   "sub_issues": {"total": summary["total"], "completed": summary["completed"]} if summary else None}
    else:
        content = None
    return {"item": node["id"], "archived": bool(node.get("isArchived")), "fields": fields, "content": content}


ITEMS_QUERY = (f"query($id:ID!,$after:String){{node(id:$id){{... on ProjectV2{{items(first:100,after:$after)"
               f"{{pageInfo{{hasNextPage endCursor}}nodes{{{ITEM_FRAGMENT}}}}}}}}}}}")
FIELDS_QUERY = ("query($id:ID!){node(id:$id){... on ProjectV2{fields(first:50){nodes{__typename "
                "... on ProjectV2FieldCommon{id name dataType} ... on ProjectV2SingleSelectField{options{id name}} "
                "... on ProjectV2IterationField{configuration{iterations{id title startDate}}}}}}}}")


def fields(project_id: str) -> list[dict]:
    data = graphql(FIELDS_QUERY, {"id": project_id})
    out = []
    for f in (((data.get("node") or {}).get("fields")) or {}).get("nodes") or []:
        if f and f.get("id"):
            out.append({"id": f["id"], "name": f["name"], "type": f["dataType"],
                        "options": [{"id": o["id"], "name": o["name"]} for o in f.get("options") or []] or None,
                        "iterations": [{"id": i["id"], "title": i["title"], "start": i["startDate"]}
                                       for i in ((f.get("configuration") or {}).get("iterations") or [])] or None})
    return out


def board_items(board: dict, args: dict) -> dict:
    limit = _count(args, "limit", 100, ITEM_CAP)
    nodes = paginate(ITEMS_QUERY, {"id": board["id"]}, lambda d: (d.get("node") or {}).get("items"), ITEM_CAP + 1)
    truncated = len(nodes) > ITEM_CAP
    nodes = nodes[:ITEM_CAP]
    statuses = [s.strip() for s in str(args.get("status") or "").split(",") if s.strip()]
    excluded = [s[1:] for s in statuses if s.startswith("-")]
    included = [s for s in statuses if not s.startswith("-")]
    content_type = args.get("content_type")
    if content_type not in (None, "issue", "pr", "draft"):
        raise AccessError("content_type is issue, pr or draft")
    search = str(args.get("search") or "").lower()
    rows = []
    for n in nodes:
        it = item(n)
        status = it["fields"].get("Status")
        if it["archived"] and not args.get("include_archived"):
            continue
        if included and not any(same(status, s) for s in included):
            continue
        if any(same(status, s) for s in excluded):
            continue
        if content_type and (it["content"] or {}).get("type") != content_type:
            continue
        title = (it["content"] or {}).get("title") or it["fields"].get("Title") or ""
        if search and search not in str(title).lower():
            continue
        rows.append(it)
    return {"count": len(rows[:limit]), "truncated": truncated, "items": rows[:limit]}


# --- tools ----------------------------------------------------------------------------------------

def _text(args: dict, key: str, required: bool = True) -> str:
    value = args.get(key)
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise AccessError(f"{key} is required")
        return ""
    if not isinstance(value, str):
        raise AccessError(f"{key} must be text")
    if any(ch in value for ch in "\x00"):
        raise AccessError(f"{key} must not contain NUL")
    return value.strip()


def _count(args: dict, key: str, default: int, maximum: int) -> int:
    value = args.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise AccessError(f"{key} must be a positive integer")
    return min(value, maximum)


def _action(args: dict, actions) -> str:
    action = args.get("action")
    if action not in actions:
        raise AccessError(f"action must be one of: {', '.join(actions)}")
    return action


def _board_summary(resolved: dict) -> dict:
    b = resolved["board"]
    return {"board": {k: b[k] for k in ("id", "number", "title", "url", "owner", "owner_type", "public", "can_update", "tier")},
            "route": resolved["route"], "considered": resolved["considered"]}


def github_issue(args: dict) -> dict:
    action = _action(args, ISSUE_ACTIONS)
    if action == "view":
        repo, number = parse_issue(_text(args, "issue"), _text(args, "repo", required=False) or None)
        comments = args.get("comments", COMMENTS)
        if not isinstance(comments, int) or isinstance(comments, bool) or comments < 0:
            raise AccessError("comments must be 0 or more")
        ctx = repo_context(repo)
        return {"ok": True, "tier": ctx["tier"], "issue": issue(repo, number, min(comments, 50))}
    return issue_list(args)


def github_board(args: dict) -> dict:
    action = _action(args, BOARD_ACTIONS)
    resolved = resolve_board(_text(args, "project", required=False) or None, _text(args, "owner", required=False) or None,
                             _text(args, "repo", required=False) or None)
    out = {"ok": True, **_board_summary(resolved)}
    if action == "resolve":
        out["fields"] = [{k: f[k] for k in ("name", "type")} | ({"options": [o["name"] for o in f["options"]]} if f["options"] else {})
                         for f in fields(resolved["board"]["id"])]
        return out
    return {**out, **board_items(resolved["board"], args)}
