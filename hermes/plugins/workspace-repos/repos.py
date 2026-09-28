"""The repositories under ~/Workspaces: local Git state and open GitHub work.

    ws-repos                        per-Group overview (local state, open PRs and issues)
    ws-repos --group Acme           one Group, repository by repository
    ws-repos prs                    open pull requests, grouped by repository
    ws-repos issues --group tech    open issues of one Group
    ws-repos commits --period week  your commits of the last 7 days, by repository
    ws-repos prs --period week      pull requests updated in the period, merged and closed too
    ... --no-github                 local state only (no network)
    ... --json                      the raw result instead of the table

A repository is an entry of ``<Area>/<Group>/github/`` (usually a symlink to a
``~/ghq`` clone). Local state comes from Git's own refs and never fetches, so
"behind" is as of the last fetch. Open pull requests, issues and discussion
counts come from one GitHub GraphQL query through ``gh``; when that fails the
local state is still reported and the result is ``partial``. A period (today,
week, month or N local calendar days) lists your commits from the local and
remote-tracking branches, or the pull requests and issues updated in it.

Read-only: Git runs with optional locks off, so not even the index is
refreshed, and nothing is committed, fetched, pulled or pushed. Stdlib only, so
cron, the ``ws-repos`` launcher and the Hermes tool run the same code.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time, timedelta, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys


ACTIONS = ("summary", "prs", "issues", "commits")
PERIODS = {"today": 1, "week": 7, "month": 30}
MAX_DAYS = 365
COMMIT_LIMIT = 300
AREAS = ("Projects", "Personal")
FLAGS = ("broken", "not-git", "no-remote", "remote-missing", "shared-origin", "dirty", "unpushed",
         "no-upstream", "behind", "detached", "stash", "worktrees", "read-only")
ATTENTION = ("broken", "not-git", "no-remote", "remote-missing", "shared-origin", "dirty", "unpushed",
             "no-upstream", "stash", "worktrees")
WRITABLE = ("ADMIN", "MAINTAIN", "WRITE")
GIT_TIMEOUT = 15
GH_TIMEOUT = 40
PR_LIMIT = 30
ISSUE_LIMIT = 50
PERIOD_LIMIT = 50           # items per repository when a period also brings merged and closed ones
ITEM_CHUNK = 4              # repositories per items query; one large query times out on GitHub
GITHUB = re.compile(r"(?:git@github\.com:|ssh://git@github\.com/|https://github\.com/)"
                    r"([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?\Z")


def default_root():
    return Path(os.environ.get("WORKSPACES_ROOT") or Path.home() / "Workspaces")


# --------------------------------------------------------------------------
# Local Git state


def _git(repo, *args):
    """stdout of a read-only git command, or None when it fails."""
    env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C"}
    try:
        done = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                              timeout=GIT_TIMEOUT, env=env)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout if done.returncode == 0 else None


def _entries(root):
    """(group, path) for every entry of <Area>/<Group>/github/."""
    for area in AREAS:
        try:
            groups = sorted(p for p in (root / area).iterdir()
                            if p.is_dir() and not p.is_symlink() and not p.name.startswith("."))
        except FileNotFoundError:
            continue
        for group in groups:
            try:
                repos = sorted(p for p in (group / "github").iterdir() if not p.name.startswith("."))
            except (FileNotFoundError, NotADirectoryError):
                continue
            for repo in repos:
                yield f"{area}/{group.name}", repo


def _slug(url):
    match = GITHUB.match((url or "").strip())
    return f"{match.group(1)}/{match.group(2)}" if match else None


def inspect(group, path, root):
    """One repository's local state. Missing pieces become flags, never exceptions."""
    row = {"group": group, "name": path.name, "path": str(path), "relative": str(path.relative_to(root)),
           "target": os.readlink(path) if path.is_symlink() else None, "remote": None, "slug": None,
           "branch": None, "upstream": None, "ahead": 0, "behind": 0, "changed": 0, "unpushed": 0,
           "stashes": 0, "worktrees": 1, "last_commit": None, "flags": []}
    if not path.exists():
        row["flags"].append("broken")
        return row
    status = _git(path, "status", "--porcelain=v2", "--branch", "--untracked-files=normal")
    if status is None:
        row["flags"].append("not-git")
        return row
    for line in status.splitlines():
        if line.startswith("# branch.head "):
            head = line.split(" ", 2)[2]
            row["branch"] = None if head == "(detached)" else head
        elif line.startswith("# branch.upstream "):
            row["upstream"] = line.split(" ", 2)[2]
        elif line.startswith("# branch.ab "):
            ahead, behind = line.split(" ")[2:4]
            row["ahead"], row["behind"] = int(ahead), -int(behind)
        elif line and not line.startswith("#"):
            row["changed"] += 1
    remotes = (_git(path, "remote") or "").split()
    if "origin" in remotes or remotes:
        row["remote"] = (_git(path, "remote", "get-url", "origin" if "origin" in remotes else remotes[0])
                         or "").strip() or None
        row["slug"] = _slug(row["remote"])
        # Commits on any local branch that no remote-tracking ref contains.
        row["unpushed"] = int((_git(path, "rev-list", "--count", "--branches", "--not", "--remotes")
                               or "0").strip() or 0)
    row["stashes"] = len((_git(path, "stash", "list") or "").splitlines())
    row["worktrees"] = sum(line.startswith("worktree ")
                           for line in (_git(path, "worktree", "list", "--porcelain") or "").splitlines()) or 1
    last = (_git(path, "log", "-1", "--format=%cI") or "").strip()
    row["last_commit"] = last or None
    flags = row["flags"]
    if not remotes:
        flags.append("no-remote")
    if row["changed"]:
        flags.append("dirty")
    if row["unpushed"]:
        flags.append("unpushed")
    if row["branch"] is None:
        flags.append("detached")
    elif remotes and row["upstream"] is None:
        flags.append("no-upstream")
    if row["behind"]:
        flags.append("behind")
    if row["stashes"]:
        flags.append("stash")
    if row["worktrees"] > 1:
        flags.append("worktrees")
    return row


def scan(root=None):
    root = Path(root) if root is not None else default_root()
    if not root.is_dir():
        raise FileNotFoundError(f"no Workspaces root at {root}")
    entries = list(_entries(root))
    with ThreadPoolExecutor(max_workers=8) as pool:
        repos = list(pool.map(lambda e: inspect(e[0], e[1], root), entries))
    slugs = [r["slug"] for r in repos if r["slug"]]
    for r in repos:                 # two local repos pushing to one GitHub repo is almost always a mistake
        if r["slug"] and slugs.count(r["slug"]) > 1:
            r["flags"].append("shared-origin")
    return repos


def period_start(days, now):
    """Local midnight ``days - 1`` days before today: the same window as /activity."""
    local = now.astimezone()
    return datetime.combine(local.date() - timedelta(days=days - 1), time.min, tzinfo=local.tzinfo)


BOT = re.compile(r"\[bot\]|^dependabot|^renovate", re.I)


def commits_of(repo, since, until=None):
    """Your commits in [since, until) on local and remote-tracking branches, merges excluded.
    "Yours" = author name or email equal to the repo's configured user.name / user.email."""
    path = Path(repo["path"])
    if any(f in repo["flags"] for f in ("broken", "not-git")):
        return []
    me = {v.strip().lower() for v in ((_git(path, "config", "user.name") or ""),
                                      (_git(path, "config", "user.email") or "")) if v.strip()}
    stamp = since.isoformat()
    window = [f"--since={stamp}"] + ([f"--until={until.isoformat()}"] if until else [])
    log = _git(path, "log", "--branches", "--remotes", "--no-merges", "--source", *window,
               f"--max-count={COMMIT_LIMIT}", "--format=%H%x1f%an%x1f%ae%x1f%cI%x1f%S%x1f%s")
    unpushed = set((_git(path, "rev-list", "--branches", "--not", "--remotes", f"--since={stamp}")
                    or "").split())
    # --source names the first ref that reaches a commit; show origin/HEAD as the branch it points at.
    heads = {}
    for ref in (_git(path, "for-each-ref", "--format=%(refname) %(symref)", "refs/remotes") or "").splitlines():
        name, _, target = ref.partition(" ")
        if target:
            heads[name.removeprefix("refs/remotes/")] = target.removeprefix("refs/remotes/")
    out = []
    for line in (log or "").splitlines():
        parts = line.split("\x1f")
        if len(parts) != 6:
            continue
        sha, name, email, when, source, subject = parts
        if until and datetime.fromisoformat(when) >= until:
            continue                # --until is inclusive; the window is half-open
        if BOT.search(name) or (me and name.lower() not in me and email.lower() not in me):
            continue
        branch = re.sub(r"^refs/(heads|remotes)/", "", source)
        branch = heads.get(branch, branch)
        pushed = sha not in unpushed
        linkable = pushed and repo["slug"] and "remote-missing" not in repo["flags"]
        out.append({"repo": f"{label(repo['group'])}/{repo['name']}", "slug": repo["slug"], "sha": sha,
                    "short": sha[:7], "author": name, "date": when, "branch": branch, "subject": subject,
                    "pushed": pushed,
                    "url": f"https://github.com/{repo['slug']}/commit/{sha}" if linkable else None})
    return out


def commits(repos, since, until=None):
    """Commits of every repo; a commit reached from two clones of one GitHub repo counts once."""
    with ThreadPoolExecutor(max_workers=8) as pool:
        found = list(pool.map(lambda r: commits_of(r, since, until), repos))
    seen, out = set(), []
    for repo, rows in zip(repos, found):
        for c in rows:
            key = (repo["slug"] or repo["path"], c["sha"])
            if key not in seen:
                seen.add(key)
                out.append(c)
    return sorted(out, key=lambda c: c["date"], reverse=True)


# --------------------------------------------------------------------------
# GitHub (one GraphQL query through gh)

PR_FIELDS = """number title url state isDraft createdAt updatedAt mergedAt closedAt reviewDecision headRefName
  author { login }
  reviewRequests(first: 10) { nodes { requestedReviewer { ... on User { login } ... on Team { slug } } } }
  commits(last: 1) { nodes { commit { statusCheckRollup { state } } } }"""
ISSUE_FIELDS = """number title url state createdAt updatedAt closedAt author { login }
  assignees(first: 5) { nodes { login } } labels(first: 5) { nodes { name } } comments { totalCount }"""


def github_query(slugs):
    """GraphQL text: open counts and your permission for every repository."""
    parts = ["viewer { login }"]
    for i, slug in enumerate(slugs):
        owner, name = slug.split("/", 1)
        parts.append(f"r{i}: repository(owner: {json.dumps(owner)}, name: {json.dumps(name)}) {{ nameWithOwner "
                     "isArchived viewerPermission prs: pullRequests(states: OPEN) { totalCount } "
                     "issues(states: OPEN) { totalCount } discussions { totalCount } }")
    return "query {\n  " + "\n  ".join(parts) + "\n}"


def items_query(slugs, detail, since=None):
    """GraphQL text for the items of a few repositories: open PRs or issues, or with
    ``since`` every one updated since then, merged and closed included."""
    order = "orderBy: {field: UPDATED_AT, direction: DESC}"
    if detail == "prs":
        states, limit, extra, fields = ("[OPEN, MERGED, CLOSED]", PERIOD_LIMIT, "", PR_FIELDS) if since else \
            ("OPEN", PR_LIMIT, "", PR_FIELDS)
        connection = "pullRequests"
    else:
        stamp = json.dumps(since.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")) if since else None
        states, limit, extra, fields = ("[OPEN, CLOSED]", PERIOD_LIMIT, f", filterBy: {{since: {stamp}}}",
                                        ISSUE_FIELDS) if since else ("OPEN", ISSUE_LIMIT, "", ISSUE_FIELDS)
        connection = "issues"
    parts = []
    for i, slug in enumerate(slugs):
        owner, name = slug.split("/", 1)
        parts.append(f"r{i}: repository(owner: {json.dumps(owner)}, name: {json.dumps(name)}) {{ "
                     f"items: {connection}(states: {states}, first: {limit}, {order}{extra}) "
                     f"{{ nodes {{ {fields} }} }} }}")
    return "query {\n  " + "\n  ".join(parts) + "\n}"


def _gh(query):
    """(data, errors) from ``gh api graphql``. GraphQL answers partial data plus errors
    for a repository it cannot see, so both are returned."""
    try:
        done = subprocess.run(["gh", "api", "graphql", "-f", f"query={query}"], capture_output=True,
                              text=True, timeout=GH_TIMEOUT, env={**os.environ, "GH_PROMPT_DISABLED": "1"})
    except FileNotFoundError:
        raise RuntimeError("gh is not installed")
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"gh timed out after {GH_TIMEOUT}s")
    try:
        body = json.loads(done.stdout or "{}")
    except json.JSONDecodeError:
        body = {}
    if not body.get("data"):
        lines = (done.stderr or done.stdout or "").strip().splitlines()
        raise RuntimeError(lines[-1][:200] if lines else f"gh failed (exit {done.returncode})")
    return body["data"], body.get("errors") or []


def _age_days(iso, now):
    if not iso:
        return None
    moment = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return max(0, (now - moment).days)


def _pr(node, slug, viewer, now):
    commits = (node.get("commits") or {}).get("nodes") or []
    rollup = ((commits[0].get("commit") or {}).get("statusCheckRollup") or {}) if commits else {}
    requested = [(n.get("requestedReviewer") or {}) for n in (node.get("reviewRequests") or {}).get("nodes") or []]
    requested = [r.get("login") or r.get("slug") for r in requested if r]
    author = (node.get("author") or {}).get("login")
    return {"repo": slug, "number": node["number"], "title": node["title"], "url": node["url"],
            "state": node.get("state", "OPEN"), "created": node.get("createdAt"),
            "updated": node.get("updatedAt"), "merged": node.get("mergedAt"), "closed": node.get("closedAt"),
            "author": author, "mine": author == viewer, "draft": node.get("isDraft", False),
            "review": node.get("reviewDecision"), "ci": rollup.get("state"),
            "requested": requested, "review_requested_from_you": viewer in requested,
            "branch": node.get("headRefName"), "age_days": _age_days(node.get("createdAt"), now),
            "idle_days": _age_days(node.get("updatedAt"), now)}


def _issue(node, slug, viewer, now):
    assignees = [n["login"] for n in (node.get("assignees") or {}).get("nodes") or []]
    return {"repo": slug, "number": node["number"], "title": node["title"], "url": node["url"],
            "state": node.get("state", "OPEN"), "created": node.get("createdAt"),
            "updated": node.get("updatedAt"), "closed": node.get("closedAt"),
            "author": (node.get("author") or {}).get("login"), "assignees": assignees,
            "assigned_to_you": viewer in assignees,
            "labels": [n["name"] for n in (node.get("labels") or {}).get("nodes") or []],
            "comments": (node.get("comments") or {}).get("totalCount", 0),
            "age_days": _age_days(node.get("createdAt"), now),
            "idle_days": _age_days(node.get("updatedAt"), now)}


def _stamp(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00")) if iso else None


def _collect(nodes, slug, detail, since, viewer, now, items, diagnostics):
    """Items of one repository, cut to the period; a full page still inside it is disclosed."""
    for node in nodes:
        row = _pr(node, slug, viewer, now) if detail == "prs" else _issue(node, slug, viewer, now)
        if since and row["updated"] and _stamp(row["updated"]) < since:
            continue
        items.append(row)
    if since and len(nodes) >= PERIOD_LIMIT and (_stamp(nodes[-1].get("updatedAt")) or since) >= since:
        diagnostics.append({"code": "github-items-truncated", "repos": [slug],
                            "detail": f"{slug}: more than {PERIOD_LIMIT} updated in the period",
                            "partial": True})


def github(repos, *, detail=None, since=None, runner=None, now=None):
    """Attach GitHub counts to ``repos`` in place; return (viewer, items, diagnostics)."""
    now = now or datetime.now(timezone.utc)
    slugs = list(dict.fromkeys(r["slug"] for r in repos if r["slug"]))
    if not slugs:
        return None, [], []
    runner = runner or _gh
    data, errors = runner(github_query(slugs))
    viewer = (data.get("viewer") or {}).get("login")
    by_slug, items, diagnostics = {}, [], []
    for i, slug in enumerate(slugs):
        node = data.get(f"r{i}")
        if not node:
            by_slug[slug] = None
            continue
        by_slug[slug] = {"prs": node["prs"]["totalCount"], "issues": node["issues"]["totalCount"],
                         "discussions": (node.get("discussions") or {}).get("totalCount", 0),
                         "archived": node.get("isArchived", False),
                         "writable": node.get("viewerPermission") in WRITABLE}
    # Items come in small parallel queries, only for repositories you can write to:
    # an upstream you only read is not your work, and one large query times out.
    targets = [s for s in slugs if by_slug.get(s) and by_slug[s]["writable"]] if detail else []
    chunks = [targets[i:i + ITEM_CHUNK] for i in range(0, len(targets), ITEM_CHUNK)]

    def fetch(chunk):
        try:
            return chunk, runner(items_query(chunk, detail, since))[0], None
        except RuntimeError as exc:
            return chunk, {}, str(exc)
    with ThreadPoolExecutor(max_workers=8) as pool:
        answers = list(pool.map(fetch, chunks))
    for chunk, answer, failure in answers:
        if failure:
            diagnostics.append({"code": "github-items-unavailable", "repos": chunk,
                                "detail": f"{', '.join(chunk)}: {failure}", "partial": True})
            continue
        for j, slug in enumerate(chunk):
            nodes = ((answer.get(f"r{j}") or {}).get("items") or {}).get("nodes") or []
            _collect(nodes, slug, detail, since, viewer, now, items, diagnostics)
    missing = [s for s, v in by_slug.items() if v is None]
    if missing:
        detail_text = "; ".join(e.get("message", "") for e in errors)[:300] or "not visible to gh"
        # NOT_FOUND is a finding about the remote (flagged per repo), not a failed read.
        partial = any(e.get("type") != "NOT_FOUND" for e in errors) or not errors
        diagnostics.append({"code": "github-repo-unavailable", "count": len(missing), "repos": missing,
                            "detail": detail_text, "partial": partial})
    for repo in repos:
        repo["github"] = by_slug.get(repo["slug"]) if repo["slug"] else None
        if repo["slug"] in missing:
            repo["flags"].append("remote-missing")
        elif repo["github"] and not repo["github"]["writable"]:
            repo["flags"].append("read-only")
    return viewer, items, diagnostics


# --------------------------------------------------------------------------
# Requests


def parse_period(word):
    """today | week | month | N (days) → days, or None when the word is no period."""
    word = str(word).strip().lower()
    if word in PERIODS:
        return PERIODS[word]
    if word.isdigit():
        if not 1 <= int(word) <= MAX_DAYS:
            raise ValueError(f"a period is 1..{MAX_DAYS} days")
        return int(word)
    return None


class UnknownGroup(ValueError):
    """No Group matches; carries the names a caller can offer instead."""

    def __init__(self, needle, groups):
        self.needle, self.groups = needle, groups
        super().__init__(f"no Group matches {needle!r}; Groups: " + ", ".join(label(g) for g in groups))


def label(group):
    return group.partition("/")[2]


def resolve_group(needle, groups):
    """Group keys for a typed name: exact name, then prefix, then substring, case-insensitive."""
    text = needle.strip().lower()
    names = {g: (g.lower(), label(g).lower()) for g in groups}
    for test in (lambda full, name: text in (full, name),
                 lambda full, name: name.startswith(text),
                 lambda full, name: text in name):
        found = [g for g, (full, name) in names.items() if test(full, name)]
        if found:
            return found
    raise UnknownGroup(needle, groups)


def run(args, *, root=None, runner=None, now=None):
    """Tool/CLI entry. Every result states source, status and diagnostics."""
    action = args.get("action", "summary")
    if action not in ACTIONS:
        raise ValueError("action must be one of " + ", ".join(ACTIONS))
    group = args.get("group")
    if group is not None and (not isinstance(group, str) or not group.strip()):
        raise ValueError("group must be a nonempty string")
    use_github = args.get("github", True)
    if not isinstance(use_github, bool):
        raise ValueError("github must be true or false")
    days = args.get("days")
    if days is not None and (type(days) is not int or not 1 <= days <= MAX_DAYS):
        raise ValueError(f"days must be an integer in 1..{MAX_DAYS}")
    if action == "summary" and days is not None:
        raise ValueError("days applies to commits, prs and issues, not the summary")
    if action == "commits":
        days, use_github = days or 1, False       # commits are local; no network needed
    elif action != "summary" and not use_github:
        raise ValueError(f"{action} needs GitHub; drop github=false")
    now = now or datetime.now(timezone.utc)
    since = period_start(days, now) if days else None
    repos = scan(root)
    groups = list(dict.fromkeys(r["group"] for r in repos))
    if group:
        chosen = resolve_group(group, groups)
        repos = [r for r in repos if r["group"] in chosen]
    diagnostics, viewer, items = [], None, []
    for r in repos:
        r["github"] = None
    if action == "commits":
        items = commits(repos, since)
    elif use_github:
        try:
            viewer, items, diagnostics = github(repos, detail=None if action == "summary" else action,
                                                since=since, runner=runner, now=now)
        except RuntimeError as exc:
            diagnostics.append({"code": "github-unavailable", "detail": str(exc), "partial": True})
    body = {"action": action, "root": str(Path(root) if root is not None else default_root()),
            "source": "git+github" if use_github else "git", "github": use_github, "viewer": viewer,
            "status": "partial" if any(d.get("partial") for d in diagnostics) else "complete",
            "diagnostics": diagnostics, "groups": groups if not group else chosen, "narrowed": bool(group),
            "days": days, "since": since.isoformat() if since else None,
            "totals": _totals(repos), "repos": repos}
    if action == "commits":
        body["commits"] = items
    elif action != "summary":
        body[action] = sorted(items, key=lambda i: (i["repo"], i["idle_days"] or 0, -i["number"]))
    return body


def _totals(repos):
    counts = {f: sum(f in r["flags"] for r in repos) for f in FLAGS}
    # One GitHub repository counts once however many local clones point at it,
    # and a read-only upstream's open work is not yours.
    gh = list({r["slug"]: r["github"] for r in repos
               if r.get("github") and r["github"]["writable"]}.values())
    return {"repos": len(repos), **counts,
            "attention": sum(any(f in r["flags"] for f in ATTENTION) for r in repos),
            "prs": sum(g["prs"] for g in gh), "issues": sum(g["issues"] for g in gh),
            "discussions": sum(g["discussions"] for g in gh)}


# --------------------------------------------------------------------------
# Rendering

RICH_LIMIT = 30000          # Telegram rich messages cap at 32,768 characters
SECTION_ROWS = 20


def _home(path):
    home = str(Path.home())
    return "~" + path[len(home):] if path.startswith(home + "/") or path == home else path


def state_text(repo):
    """The local state of one repository in a few words, worst first."""
    f, parts = repo["flags"], []
    if "broken" in f:
        return "link target missing"
    if "not-git" in f:
        return "not a Git repository"
    if "remote-missing" in f:
        parts.append("origin not found on GitHub")
    if "shared-origin" in f:
        parts.append(f"origin shared with another repo ({repo['slug']})")
    if "dirty" in f:
        parts.append(f"{repo['changed']} changed")
    if "unpushed" in f:
        parts.append(f"{repo['unpushed']} unpushed")
    if "no-remote" in f:
        parts.append("no remote")
    if "no-upstream" in f:
        parts.append(f"{repo['branch']} has no upstream")
    if "detached" in f:
        parts.append("detached HEAD")
    if "behind" in f:
        parts.append(f"{repo['behind']} behind")
    if "stash" in f:
        parts.append(f"{repo['stashes']} stash")
    if "worktrees" in f:
        parts.append(f"{repo['worktrees']} worktrees")
    if "read-only" in f:
        parts.append("read-only upstream")
    return ", ".join(parts) or "clean"


def _gh_cell(repo, key, enabled=True):
    g = repo.get("github")
    if not enabled or not repo.get("slug") or "read-only" in repo["flags"]:
        return "-"
    return "?" if g is None else str(g[key])


def _code(text):
    return "`" + str(text).replace("`", "'").replace("|", "/") + "`"


def _title(text, width=60):
    text = " ".join(str(text).split()).replace("|", "/").replace("<", "‹").replace(">", "›")
    text = text.replace("[", "(").replace("]", ")")
    return text if len(text) <= width else text[:width - 1] + "…"


def _days(n):
    return "?" if n is None else f"{n}d"


def pr_state(pr):
    if pr.get("state") == "MERGED":
        return "merged"
    if pr.get("state") == "CLOSED":
        return "closed"
    parts = []
    if pr["draft"]:
        parts.append("draft")
    ci = {"FAILURE": "CI failing", "ERROR": "CI error", "PENDING": "CI running", "EXPECTED": "CI waiting"}
    if pr["ci"] in ci:
        parts.append(ci[pr["ci"]])
    review = {"APPROVED": "approved", "CHANGES_REQUESTED": "changes requested"}
    if pr["review"] in review:
        parts.append(review[pr["review"]])
    if pr["review_requested_from_you"]:
        parts.append("your review")
    return ", ".join(parts) or ("open" if not pr["mine"] else "yours")


def _fit(lines, build):
    """Largest section cap whose Markdown stays under the Telegram limit."""
    for cap in (SECTION_ROWS, 10, 5, 2):
        body = build(cap)
        if len("\n".join(lines + body)) <= RICH_LIMIT:
            return body
    return body


def period_label(days):
    return {1: "today", 7: "week", 30: "month"}.get(days, f"{days} days")


def _since_text(result):
    since = datetime.fromisoformat(result["since"])
    return f"since {since:%m-%d} ({period_label(result['days'])})"


def _commands(groups, narrowed):
    """Next commands to copy: for one Group its views, else every Group."""
    if narrowed:
        names = " ".join(label(g) for g in groups) if len(groups) == 1 else None
        rows = ([f"`/repos {names}`", f"`/repos prs {names}`", f"`/repos issues {names}`",
                 f"`/repos commits week {names}`"] if names else []) + ["`/repos`"]
    else:
        rows = (["`/repos prs`", "`/repos issues`", "`/repos commits`", "`/repos commits week`",
                 "`/repos prs week`"] + [f"`/repos {label(g)}`" for g in groups])
    return ["", "<details><summary>Open (tap to copy)</summary>", ""] + rows + ["", "</details>"]


def _notes(result):
    out = []
    for d in result["diagnostics"]:
        count = f" ×{d['count']}" if "count" in d else ""
        out.append(f"- `{d['code']}`{count}: {_title(d.get('detail', ''), 120)}")
    return out


def render_rich(result, *, title="Repos"):
    """Markdown for a chat that renders tables and <details> (Telegram rich messages)."""
    t, action = result["totals"], result["action"]
    head = [f"## {title}", ""]
    partial = "" if result["status"] == "complete" else " · *partial*"
    if action == "summary":
        gh_line = (f" · PRs **{t['prs']}** · issues **{t['issues']}**" if result["github"] else "")
        head.append(f"**{t['repos']}** repos · need attention **{t['attention']}**{gh_line}{partial}")
    elif action == "commits":
        items = result["commits"]
        head.append(f"**{len(items)}** commits in **{len({c['repo'] for c in items})}** repos · "
                    f"{_since_text(result)} · unpushed **{sum(not c['pushed'] for c in items)}**{partial}")
    else:
        items, noun = result[action], ("pull requests" if action == "prs" else "issues")
        scope = (f"updated {_since_text(result)}" if result["since"] else "open")
        head.append(f"**{len(items)}** {noun} {scope} in **{len({i['repo'] for i in items})}** repos{partial}")
    head.append("")
    if action == "summary":
        lines = head + _summary_rich(result)
    elif action == "commits":
        lines = head + _commits_rich(result)
    else:
        lines = head + _items_rich(result)
    notes = _notes(result)
    lines += ["", "<details><summary>How to read</summary>", "",
              "- Local state is read from Git's refs without fetching; \"behind\" is as of the last fetch.",
              "- unpushed: commits on any local branch that no remote branch contains.",
              "- A Group name may be shortened: `/repos tech`, `/repos prs tech`.",
              "- Periods: today, week (7 days), month (30 days) or a number of days, in local calendar "
              "days: `/repos commits week`, `/repos prs week tech`. With a period, PRs and issues "
              "include merged and closed ones updated in it.",
              "- commits: yours (author matches the repo's Git user.name or user.email) on local and "
              "remote-tracking branches as of the last fetch; merges and bots excluded."]
    if result["github"] and t["discussions"]:
        lines.append(f"- Discussions: {t['discussions']} in total, not listed here.")
    upstream = [r["name"] for r in result["repos"] if "read-only" in r["flags"]]
    if upstream:
        lines.append(f"- Read-only upstreams, not counted: {', '.join(upstream)}.")
    lines += notes + ["", "</details>"] + _commands(result["groups"], result["narrowed"])
    return "\n".join(lines)


def _summary_rich(result):
    repos = result["repos"]
    one_group = len({r["group"] for r in repos}) <= 1
    if one_group:
        lines = ["| Repo | Local | PRs | Issues |", "| :--- | :--- | ---: | ---: |"]
        lines += [f"| {_code(r['name'])} | {state_text(r)} | {_gh_cell(r, 'prs', result['github'])} | "
                  f"{_gh_cell(r, 'issues', result['github'])} |"
                  for r in repos]
        return lines
    by_group = {}
    for r in repos:
        by_group.setdefault(r["group"], []).append(r)
    lines = ["| Group | Repos | Attention | PRs | Issues |", "| :--- | ---: | ---: | ---: | ---: |"]
    for group, rows in by_group.items():
        tt = _totals(rows)
        gh = (str(tt["prs"]), str(tt["issues"])) if result["github"] else ("-", "-")
        lines.append(f"| {label(group)} | {tt['repos']} | {tt['attention']} | {gh[0]} | {gh[1]} |")
    attention = [r for r in repos if any(f in r["flags"] for f in ATTENTION)]
    if attention:
        lines += ["", f"<details><summary>Needs attention · {len(attention)}</summary>", "",
                  "| Repo | Local |", "| :--- | :--- |"]
        lines += [f"| {_code(label(r['group']) + '/' + r['name'])} | {state_text(r)} |" for r in attention]
        lines += ["", "</details>"]
    return lines


def _when(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone().strftime("%m-%d %H:%M")


def _commits_rich(result):
    items = result["commits"]
    by_repo = {}
    for c in items:
        by_repo.setdefault(c["repo"], []).append(c)
    order = sorted(by_repo.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    lines = ["| Repo | Commits | Unpushed |", "| :--- | ---: | ---: |"]
    lines += [f"| {_code(repo)} | {len(rows)} | {sum(not c['pushed'] for c in rows)} |" for repo, rows in order]
    if not items:
        return lines + ["", "No commits in the period."]

    def build(cap):
        body = []
        for repo, rows in order:
            body += ["", f"<details><summary>{repo} · {len(rows)}</summary>", "",
                     "| Commit | Branch | When |", "| :--- | :--- | ---: |"]
            for c in rows[:cap]:
                sha = f"[{c['short']}]({c['url']})" if c["url"] else f"`{c['short']}`"
                mark = "" if c["pushed"] else " (unpushed)"
                body.append(f"| {sha} {_title(c['subject'])}{mark} | {_code(c['branch'] or '-')} | "
                            f"{_when(c['date'])} |")
            if len(rows) > cap:
                body += ["", f"… {len(rows) - cap} more (`ws-repos commits --group …`)"]
            body += ["", "</details>"]
        return body
    return lines + _fit(lines, build)


def _items_rich(result):
    action = result["action"]
    items = result["prs"] if action == "prs" else result["issues"]
    if action == "prs":
        yours = sum(p["review_requested_from_you"] for p in items)
        failing = sum(p["ci"] in ("FAILURE", "ERROR") and p["state"] == "OPEN" for p in items)
        merged = f" · merged **{sum(p['state'] == 'MERGED' for p in items)}**" if result["since"] else ""
        lines = [f"Your review requested **{yours}** · CI failing **{failing}** · "
                 f"yours **{sum(p['mine'] for p in items)}**{merged}", ""]
    else:
        closed = f" · closed **{sum(i['state'] == 'CLOSED' for i in items)}**" if result["since"] else ""
        lines = [f"Assigned to you **{sum(i['assigned_to_you'] for i in items)}**{closed}", ""]
    by_repo = {}
    for item in items:
        by_repo.setdefault(item["repo"], []).append(item)
    order = sorted(by_repo.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    column = "Updated" if result["since"] else "Open"
    lines += [f"| Repo | {column} |", "| :--- | ---: |"]
    lines += [f"| {_code(slug)} | {len(rows)} |" for slug, rows in order]
    if not items:
        return lines + ["", "Nothing updated in the period." if result["since"] else "Nothing open."]

    def build(cap):
        body = []
        for slug, rows in order:
            body += ["", f"<details><summary>{slug} · {len(rows)}</summary>", ""]
            if action == "prs":
                body += ["| PR | State | Idle |", "| :--- | :--- | ---: |"]
                body += [f"| [#{p['number']}]({p['url']}) {_title(p['title'])} | {pr_state(p)} | "
                         f"{_days(p['idle_days'])} |" for p in rows[:cap]]
            else:
                body += ["| Issue | Assignee | Idle |", "| :--- | :--- | ---: |"]
                body += [f"| [#{i['number']}]({i['url']}) {_title(i['title'])}"
                         f"{' (closed)' if i['state'] == 'CLOSED' else ''} | "
                         f"{', '.join(i['assignees']) or '-'} | {_days(i['idle_days'])} |" for i in rows[:cap]]
            if len(rows) > cap:
                body += ["", f"… {len(rows) - cap} more (`ws-repos {action} --group …`)"]
            body += ["", "</details>"]
        return body
    return lines + _fit(lines, build)


def render(result):
    """Plain text for a terminal."""
    t, action = result["totals"], result["action"]
    lines = [f"Repos under {_home(result['root'])}  [{result['status']}]  source={result['source']}",
             f"{t['repos']} repos, {t['attention']} need attention; dirty {t['dirty']}, unpushed {t['unpushed']}, "
             f"no-upstream {t['no-upstream']}, broken {t['broken']}"
             + (f"; open PRs {t['prs']}, issues {t['issues']}, discussions {t['discussions']}"
                if result["github"] else ""), ""]
    if action == "summary":
        rows = [("repo", "branch", "local", "prs", "issues")]
        rows += [(f"{label(r['group'])}/{r['name']}", r["branch"] or "-", state_text(r),
                  _gh_cell(r, "prs", result["github"]), _gh_cell(r, "issues", result["github"]))
                 for r in result["repos"]]
    elif action == "commits":
        lines[-1:] = [f"{len(result['commits'])} commits {_since_text(result)}", ""]
        rows = [("when", "repo", "commit", "branch", "subject")]
        rows += [(_when(c["date"]), c["repo"], c["short"] + ("" if c["pushed"] else "*"), c["branch"] or "-",
                  _title(c["subject"], 70)) for c in result["commits"]]
    elif action == "prs":
        rows = [("pr", "state", "idle", "title")]
        rows += [(f"{p['repo']}#{p['number']}", pr_state(p), _days(p["idle_days"]), _title(p["title"], 70))
                 for p in result["prs"]]
    else:
        rows = [("issue", "state", "assignee", "idle", "title")]
        rows += [(f"{i['repo']}#{i['number']}", i["state"].lower(), ",".join(i["assignees"]) or "-",
                  _days(i["idle_days"]), _title(i["title"], 70)) for i in result["issues"]]
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    lines += ["  ".join(c.ljust(w) for c, w in zip(r, widths)).rstrip() for r in rows]
    for d in result["diagnostics"]:
        lines.append(f"! {d['code']}: {d.get('detail', '')}")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# CLI


def main(argv=None):
    parser = argparse.ArgumentParser(prog="ws-repos", description=__doc__.split("\n\n")[0])
    parser.add_argument("action", nargs="?", choices=ACTIONS, default="summary")
    parser.add_argument("--group", help="Group name (a unique prefix or substring also matches)")
    parser.add_argument("--no-github", action="store_true", help="local Git state only; no network")
    parser.add_argument("--period", help="today, week, month or a number of days (commits, prs, issues)")
    parser.add_argument("--root", help="Workspaces root (default $WORKSPACES_ROOT or ~/Workspaces)")
    parser.add_argument("--json", action="store_true")
    ns = parser.parse_args(argv)
    args = {"action": ns.action, "github": not ns.no_github}
    if ns.group:
        args["group"] = ns.group
    try:
        if ns.period:
            args["days"] = parse_period(ns.period)
        result = run(args, root=ns.root)
    except (ValueError, FileNotFoundError) as exc:
        print(f"ws-repos: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2) if ns.json else render(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
