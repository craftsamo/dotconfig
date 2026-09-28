"""The repositories under ~/Workspaces: local Git state and open GitHub work.

    ws-repos                        per-Group overview (local state, open PRs and issues)
    ws-repos --group Acme           one Group, repository by repository
    ws-repos prs                    open pull requests, grouped by repository
    ws-repos issues --group tech    open issues of one Group
    ... --no-github                 local state only (no network)
    ... --json                      the raw result instead of the table

A repository is an entry of ``<Area>/<Group>/github/`` (usually a symlink to a
``~/ghq`` clone). Local state comes from Git's own refs and never fetches, so
"behind" is as of the last fetch. Open pull requests, issues and discussion
counts come from one GitHub GraphQL query through ``gh``; when that fails the
local state is still reported and the result is ``partial``.

Read-only: Git runs with optional locks off, so not even the index is
refreshed, and nothing is committed, fetched, pulled or pushed. Stdlib only, so
cron, the ``ws-repos`` launcher and the Hermes tool run the same code.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys


ACTIONS = ("summary", "prs", "issues")
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


# --------------------------------------------------------------------------
# GitHub (one GraphQL query through gh)

PR_FIELDS = """number title url isDraft createdAt updatedAt reviewDecision headRefName
  author { login }
  reviewRequests(first: 10) { nodes { requestedReviewer { ... on User { login } ... on Team { slug } } } }
  commits(last: 1) { nodes { commit { statusCheckRollup { state } } } }"""
ISSUE_FIELDS = """number title url createdAt updatedAt author { login }
  assignees(first: 5) { nodes { login } } labels(first: 5) { nodes { name } } comments { totalCount }"""


def github_query(slugs, *, detail=None):
    """GraphQL text: counts for every repository, and the open items when ``detail``
    is "prs" or "issues"."""
    parts = ["viewer { login }"]
    for i, slug in enumerate(slugs):
        owner, name = slug.split("/", 1)
        items = ""
        if detail == "prs":
            items = f"items: pullRequests(states: OPEN, first: {PR_LIMIT}, orderBy: {{field: UPDATED_AT, direction: DESC}}) {{ nodes {{ {PR_FIELDS} }} }}"
        elif detail == "issues":
            items = f"items: issues(states: OPEN, first: {ISSUE_LIMIT}, orderBy: {{field: UPDATED_AT, direction: DESC}}) {{ nodes {{ {ISSUE_FIELDS} }} }}"
        parts.append(f"r{i}: repository(owner: {json.dumps(owner)}, name: {json.dumps(name)}) {{ nameWithOwner isArchived viewerPermission "
                     "prs: pullRequests(states: OPEN) { totalCount } issues(states: OPEN) { totalCount } "
                     f"discussions {{ totalCount }} {items} }}")
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
            "author": author, "mine": author == viewer, "draft": node.get("isDraft", False),
            "review": node.get("reviewDecision"), "ci": rollup.get("state"),
            "requested": requested, "review_requested_from_you": viewer in requested,
            "branch": node.get("headRefName"), "age_days": _age_days(node.get("createdAt"), now),
            "idle_days": _age_days(node.get("updatedAt"), now)}


def _issue(node, slug, viewer, now):
    assignees = [n["login"] for n in (node.get("assignees") or {}).get("nodes") or []]
    return {"repo": slug, "number": node["number"], "title": node["title"], "url": node["url"],
            "author": (node.get("author") or {}).get("login"), "assignees": assignees,
            "assigned_to_you": viewer in assignees,
            "labels": [n["name"] for n in (node.get("labels") or {}).get("nodes") or []],
            "comments": (node.get("comments") or {}).get("totalCount", 0),
            "age_days": _age_days(node.get("createdAt"), now),
            "idle_days": _age_days(node.get("updatedAt"), now)}


def github(repos, *, detail=None, runner=None, now=None):
    """Attach GitHub counts to ``repos`` in place; return (viewer, items, diagnostics)."""
    now = now or datetime.now(timezone.utc)
    slugs = list(dict.fromkeys(r["slug"] for r in repos if r["slug"]))
    if not slugs:
        return None, [], []
    data, errors = (runner or _gh)(github_query(slugs, detail=detail))
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
        if not by_slug[slug]["writable"]:
            continue                # an upstream you only read: its PRs and issues are not your work
        for item in (node.get("items") or {}).get("nodes") or []:
            items.append(_pr(item, slug, viewer, now) if detail == "prs" else _issue(item, slug, viewer, now))
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
    if action != "summary" and not use_github:
        raise ValueError(f"{action} needs GitHub; drop github=false")
    repos = scan(root)
    groups = list(dict.fromkeys(r["group"] for r in repos))
    if group:
        chosen = resolve_group(group, groups)
        repos = [r for r in repos if r["group"] in chosen]
    diagnostics, viewer, items = [], None, []
    for r in repos:
        r["github"] = None
    if use_github:
        try:
            viewer, items, diagnostics = github(repos, detail=None if action == "summary" else action,
                                                runner=runner, now=now)
        except RuntimeError as exc:
            diagnostics.append({"code": "github-unavailable", "detail": str(exc), "partial": True})
    body = {"action": action, "root": str(Path(root) if root is not None else default_root()),
            "source": "git+github" if use_github else "git", "github": use_github, "viewer": viewer,
            "status": "partial" if any(d.get("partial") for d in diagnostics) else "complete",
            "diagnostics": diagnostics, "groups": groups if not group else chosen, "narrowed": bool(group),
            "totals": _totals(repos), "repos": repos}
    if action != "summary":
        key = "prs" if action == "prs" else "issues"
        body[key] = sorted(items, key=lambda i: (i["repo"], i["idle_days"] or 0, -i["number"]))
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


def _commands(groups, narrowed):
    """Next commands to copy: for one Group its PRs and issues, else every Group."""
    if narrowed:
        names = " ".join(label(g) for g in groups) if len(groups) == 1 else None
        rows = ([f"`/repos {names}`", f"`/repos prs {names}`", f"`/repos issues {names}`"] if names
                else []) + ["`/repos`"]
    else:
        rows = ["`/repos prs`", "`/repos issues`"] + [f"`/repos {label(g)}`" for g in groups]
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
    else:
        items = result[action]
        head.append(f"**{len(items)}** open {'pull requests' if action == 'prs' else 'issues'} in "
                    f"**{len({i['repo'] for i in items})}** repos{partial}")
    head.append("")
    if action == "summary":
        lines = head + _summary_rich(result)
    else:
        lines = head + _items_rich(result)
    notes = _notes(result)
    lines += ["", "<details><summary>How to read</summary>", "",
              "- Local state is read from Git's refs without fetching; \"behind\" is as of the last fetch.",
              "- unpushed: commits on any local branch that no remote branch contains.",
              "- A Group name may be shortened: `/repos tech`, `/repos prs tech`."]
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


def _items_rich(result):
    action = result["action"]
    items = result["prs"] if action == "prs" else result["issues"]
    if action == "prs":
        yours = sum(p["review_requested_from_you"] for p in items)
        failing = sum(p["ci"] in ("FAILURE", "ERROR") for p in items)
        lines = [f"Your review requested **{yours}** · CI failing **{failing}** · "
                 f"yours **{sum(p['mine'] for p in items)}**", ""]
    else:
        lines = [f"Assigned to you **{sum(i['assigned_to_you'] for i in items)}**", ""]
    by_repo = {}
    for item in items:
        by_repo.setdefault(item["repo"], []).append(item)
    order = sorted(by_repo.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    lines += ["| Repo | Open |", "| :--- | ---: |"]
    lines += [f"| {_code(slug)} | {len(rows)} |" for slug, rows in order]
    if not items:
        return lines + ["", "Nothing open."]

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
                body += [f"| [#{i['number']}]({i['url']}) {_title(i['title'])} | "
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
    elif action == "prs":
        rows = [("pr", "state", "idle", "title")]
        rows += [(f"{p['repo']}#{p['number']}", pr_state(p), _days(p["idle_days"]), _title(p["title"], 70))
                 for p in result["prs"]]
    else:
        rows = [("issue", "assignee", "idle", "title")]
        rows += [(f"{i['repo']}#{i['number']}", ",".join(i["assignees"]) or "-", _days(i["idle_days"]),
                  _title(i["title"], 70)) for i in result["issues"]]
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
    parser.add_argument("--root", help="Workspaces root (default $WORKSPACES_ROOT or ~/Workspaces)")
    parser.add_argument("--json", action="store_true")
    ns = parser.parse_args(argv)
    args = {"action": ns.action, "github": not ns.no_github}
    if ns.group:
        args["group"] = ns.group
    try:
        result = run(args, root=ns.root)
    except (ValueError, FileNotFoundError) as exc:
        print(f"ws-repos: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2) if ns.json else render(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
