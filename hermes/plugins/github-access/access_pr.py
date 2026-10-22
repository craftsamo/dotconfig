"""github-access: pull request reads — one pull request in full, and a repository's pull requests.

The engine behind ``github_pr``, and what the pull request ops of ``github_change`` read before a
card: the state, the head commit a merge is pinned to, whether GitHub would merge it, the checks
and reviews, and the issues a merge closes.
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


access = _load("hermes_github_access_engine", Path(__file__).resolve().parent / "access.py")
AccessError = access.AccessError

PR_ACTIONS = ("view", "list")
COMMENTS = 5
STATES = ("open", "closed", "merged", "all")

PR_QUERY = (
    "query($owner:String!,$name:String!,$n:Int!,$comments:Int!){repository(owner:$owner,name:$name){"
    "pullRequest(number:$n){id number title url state isDraft body author{login} createdAt mergedAt closedAt "
    "baseRefName headRefName headRefOid headRepository{nameWithOwner} isCrossRepository mergeable "
    "mergeStateStatus reviewDecision additions deletions changedFiles commits{totalCount} "
    "labels(first:20){nodes{name}} assignees(first:10){nodes{login}} milestone{title} "
    "reviewRequests(first:10){nodes{requestedReviewer{... on User{login} ... on Team{slug}}}} "
    "latestReviews(first:20){nodes{author{login} state submittedAt}} "
    "closingIssuesReferences(first:20){nodes{number title url state repository{nameWithOwner}}} "
    "autoMergeRequest{mergeMethod} "
    "lastCommit:commits(last:1){nodes{commit{oid statusCheckRollup{state contexts(first:100){nodes{__typename "
    "... on CheckRun{name status conclusion detailsUrl isRequired(pullRequestNumber:$n)} "
    "... on StatusContext{context state targetUrl isRequired(pullRequestNumber:$n)}}}}}}} "
    "comments(last:$comments){nodes{author{login} body createdAt url}}}}}")
SEARCH_QUERY = ("query($q:String!,$first:Int!,$after:String){search(type:ISSUE,query:$q,first:$first,after:$after){"
                "pageInfo{hasNextPage endCursor}nodes{... on PullRequest{number title url state isDraft "
                "author{login} baseRefName headRefName updatedAt reviewDecision labels(first:20){nodes{name}}}}}}")
# Check outcomes, folded: what failed, what is still running, what passed or was skipped.
FAILED = {"FAILURE", "ERROR", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED", "STARTUP_FAILURE", "STALE"}
PASSED = {"SUCCESS", "NEUTRAL", "SKIPPED"}


def _check(node: dict) -> dict:
    if node.get("__typename") == "CheckRun":
        outcome = node.get("conclusion") or node.get("status") or "PENDING"
        return {"name": node.get("name"), "outcome": outcome, "required": bool(node.get("isRequired")),
                "url": node.get("detailsUrl")}
    return {"name": node.get("context"), "outcome": node.get("state") or "PENDING",
            "required": bool(node.get("isRequired")), "url": node.get("targetUrl")}


def checks(rollup: dict | None) -> dict:
    """The head commit's checks: their overall state, and each one failing or still running."""
    if not rollup:
        return {"state": "none", "failing": [], "pending": [], "passed": 0, "required_failing": 0, "required_pending": 0}
    rows = [_check(n) for n in (rollup.get("contexts") or {}).get("nodes") or [] if n]
    failing = [r for r in rows if r["outcome"] in FAILED]
    pending = [r for r in rows if r["outcome"] not in FAILED | PASSED]
    return {"state": (rollup.get("state") or "").lower(), "failing": failing, "pending": pending,
            "passed": len(rows) - len(failing) - len(pending),
            "required_failing": sum(r["required"] for r in failing),
            "required_pending": sum(r["required"] for r in pending)}


def pull_request(repo: str, number: int, comments: int = COMMENTS) -> dict:
    owner, name = access.parse_repo(repo).split("/", 1)
    pr = (access.graphql(PR_QUERY, {"owner": owner, "name": name, "n": number, "comments": comments})
          .get("repository") or {}).get("pullRequest")
    if not pr:
        raise AccessError(f"pull request {repo}#{number} not found or not visible to the viewer")
    head = ((pr.get("lastCommit") or {}).get("nodes") or [{}])[0].get("commit") or {}
    return {
        "number": pr["number"], "repo": access.parse_repo(repo), "id": pr["id"], "title": pr["title"],
        "url": pr["url"], "state": pr["state"].lower(), "draft": bool(pr.get("isDraft")), "body": pr.get("body") or "",
        "author": (pr.get("author") or {}).get("login"), "created": pr.get("createdAt"), "merged": pr.get("mergedAt"),
        "closed": pr.get("closedAt"), "base": pr["baseRefName"], "head": pr["headRefName"],
        "head_sha": pr["headRefOid"], "head_repo": (pr.get("headRepository") or {}).get("nameWithOwner"),
        "fork": bool(pr.get("isCrossRepository")), "mergeable": (pr.get("mergeable") or "").lower(),
        "merge_state": (pr.get("mergeStateStatus") or "").lower(),
        "review_decision": (pr.get("reviewDecision") or "").lower() or None,
        "size": {"additions": pr.get("additions"), "deletions": pr.get("deletions"), "files": pr.get("changedFiles"),
                 "commits": (pr.get("commits") or {}).get("totalCount")},
        "labels": [l["name"] for l in (pr.get("labels") or {}).get("nodes") or []],
        "assignees": [a["login"] for a in (pr.get("assignees") or {}).get("nodes") or []],
        "milestone": (pr.get("milestone") or {}).get("title"),
        "review_requests": [r["requestedReviewer"].get("login") or r["requestedReviewer"].get("slug")
                            for r in (pr.get("reviewRequests") or {}).get("nodes") or [] if r.get("requestedReviewer")],
        "reviews": [{"author": (r.get("author") or {}).get("login"), "state": r["state"].lower(), "at": r.get("submittedAt")}
                    for r in (pr.get("latestReviews") or {}).get("nodes") or []],
        "closes": [{"issue": f"{i['repository']['nameWithOwner']}#{i['number']}", "title": i["title"],
                    "state": i["state"].lower()} for i in (pr.get("closingIssuesReferences") or {}).get("nodes") or []],
        "auto_merge": (pr.get("autoMergeRequest") or {}).get("mergeMethod"),
        "checks": checks(head.get("statusCheckRollup")),
        "comments": [{"author": (c.get("author") or {}).get("login"), "body": c.get("body") or "", "at": c.get("createdAt"),
                      "url": c.get("url")} for c in (pr.get("comments") or {}).get("nodes") or []],
    }


def pr_list(args: dict) -> dict:
    repo = access.parse_repo(access._text(args, "repo"))
    state = args.get("state") or "open"
    if state not in STATES:
        raise AccessError("state is open, closed, merged or all")
    limit = access._count(args, "limit", 30, access.LIST_LIMIT)
    parts = [f"repo:{repo}", "is:pr"]
    if state in ("open", "closed"):
        parts.append(f"state:{state}")
    elif state == "merged":
        parts.append("is:merged")
    for key, qualifier in (("author", "author"), ("base", "base"), ("head", "head"), ("label", "label")):
        if args.get(key):
            value = access._text(args, key)
            if key == "author" and not access.LOGIN.match(value):
                raise AccessError(f"author is a login or @me, not {value!r}")
            parts.append(f"{qualifier}:{value if key == 'author' else access._quoted(value)}")
    if args.get("query"):
        words = access._text(args, "query")
        if re.search(r"(?:^|\s)-?(?:repo|org|user):", words):
            raise AccessError("query cannot name other repositories; list one repository per call")
        parts.append(words)
    query = " ".join(parts)
    nodes = access.paginate(SEARCH_QUERY, {"q": query, "first": min(limit, 100)}, lambda d: d.get("search"), limit)
    rows = [{"number": n["number"], "title": n["title"], "url": n["url"], "state": n["state"].lower(),
             "draft": bool(n.get("isDraft")), "author": (n.get("author") or {}).get("login"), "base": n.get("baseRefName"),
             "head": n.get("headRefName"), "review_decision": (n.get("reviewDecision") or "").lower() or None,
             "labels": [l["name"] for l in (n.get("labels") or {}).get("nodes") or []], "updated": n.get("updatedAt")}
            for n in nodes if n.get("number")]
    return {"ok": True, "repo": repo, "query": query, "count": len(rows), "pull_requests": rows}


def github_pr(args: dict) -> dict:
    action = access._action(args, PR_ACTIONS)
    if action == "list":
        return pr_list(args)
    repo, number = access.parse_issue(access._text(args, "pr"), access._text(args, "repo", required=False) or None,
                                      allow_pr=True)
    comments = args.get("comments", COMMENTS)
    if not isinstance(comments, int) or isinstance(comments, bool) or comments < 0:
        raise AccessError("comments must be 0 or more")
    return {"ok": True, "tier": access.repo_context(repo)["tier"], "pull_request": pull_request(repo, number, min(comments, 50))}
