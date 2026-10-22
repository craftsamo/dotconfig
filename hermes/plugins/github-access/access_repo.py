"""github-access: repository reads — a repository's settings, labels and milestones, its releases,
and its GitHub Actions workflows and runs.

The engine behind ``github_repo``, and what the repository, release and Actions ops of
``github_change`` read before a card (the settings a change would move from, the labels,
milestones, releases, workflows and runs it names). Read through the user's own ``gh`` login like
every other read; nothing is stored.
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


access = _load("hermes_github_access_engine", Path(__file__).resolve().parent / "access.py")
AccessError = access.AccessError

REPO_ACTIONS = ("view", "labels", "milestones", "releases", "workflows", "runs", "run", "rules")
LABEL_CAP = 500
MILESTONE_CAP = 300
LOG_LINES = 120
LOG_CHARS = 8000
RUN_STATUSES = ("queued", "in_progress", "completed", "success", "failure", "cancelled", "action_required",
                "waiting", "pending", "requested", "skipped", "stale", "startup_failure", "timed_out", "neutral")

VIEW_QUERY = (
    "query($owner:String!,$name:String!){repository(owner:$owner,name:$name){id nameWithOwner description "
    "homepageUrl visibility isPrivate isArchived isTemplate isFork defaultBranchRef{name} viewerPermission "
    "owner{__typename login} hasIssuesEnabled hasWikiEnabled hasProjectsEnabled hasDiscussionsEnabled "
    "mergeCommitAllowed squashMergeAllowed rebaseMergeAllowed autoMergeAllowed deleteBranchOnMerge "
    "allowUpdateBranch repositoryTopics(first:20){nodes{topic{name}}} licenseInfo{spdxId} "
    "templateRepository{nameWithOwner} pushedAt}}")
LABELS_QUERY = ("query($owner:String!,$name:String!,$after:String){repository(owner:$owner,name:$name){"
                "labels(first:100,after:$after,orderBy:{field:NAME,direction:ASC}){pageInfo{hasNextPage endCursor}"
                "nodes{name color description}}}}")
MILESTONES_QUERY = ("query($owner:String!,$name:String!,$states:[MilestoneState!],$after:String){repository("
                    "owner:$owner,name:$name){milestones(first:100,after:$after,states:$states,orderBy:{field:DUE_DATE,"
                    "direction:ASC}){pageInfo{hasNextPage endCursor}nodes{number title state dueOn description "
                    "progressPercentage open:issues(states:OPEN){totalCount} closed:issues(states:CLOSED){totalCount}}}}}")
STATES = {"open": ["OPEN"], "closed": ["CLOSED"], "all": ["OPEN", "CLOSED"]}


def _split(repo: str) -> dict:
    owner, name = access.parse_repo(repo).split("/", 1)
    return {"owner": owner, "name": name}


def settings(repo: str) -> dict:
    """A repository's settings, read now."""
    r = access.graphql(VIEW_QUERY, _split(repo)).get("repository")
    if not r:
        raise AccessError(f"repository {access.parse_repo(repo)} not found or not visible to the viewer")
    owner = r["owner"]["login"]
    return {
        "repo": r["nameWithOwner"], "id": r["id"], "visibility": (r.get("visibility") or "").lower(),
        "archived": bool(r.get("isArchived")), "is_template": bool(r.get("isTemplate")), "fork": bool(r.get("isFork")),
        "default_branch": (r.get("defaultBranchRef") or {}).get("name"), "description": r.get("description") or "",
        "homepage": r.get("homepageUrl") or "", "permission": r.get("viewerPermission"),
        "topics": [n["topic"]["name"] for n in (r.get("repositoryTopics") or {}).get("nodes") or []],
        "license": (r.get("licenseInfo") or {}).get("spdxId"),
        "template_repository": (r.get("templateRepository") or {}).get("nameWithOwner"),
        "pushed_at": r.get("pushedAt"),
        "features": {"has_issues": bool(r.get("hasIssuesEnabled")), "has_wiki": bool(r.get("hasWikiEnabled")),
                     "has_projects": bool(r.get("hasProjectsEnabled")),
                     "has_discussions": bool(r.get("hasDiscussionsEnabled"))},
        "merge": {"allow_merge_commit": bool(r.get("mergeCommitAllowed")),
                  "allow_squash_merge": bool(r.get("squashMergeAllowed")),
                  "allow_rebase_merge": bool(r.get("rebaseMergeAllowed")),
                  "allow_auto_merge": bool(r.get("autoMergeAllowed")),
                  "delete_branch_on_merge": bool(r.get("deleteBranchOnMerge")),
                  "allow_update_branch": bool(r.get("allowUpdateBranch"))},
        "tier": access.tier(owner, r["owner"]["__typename"], bool(r.get("isPrivate"))),
    }


def labels(repo: str) -> list[dict]:
    nodes = access.paginate(LABELS_QUERY, _split(repo), lambda d: (d.get("repository") or {}).get("labels"), LABEL_CAP)
    return [{"name": n["name"], "color": n.get("color"), "description": n.get("description") or ""} for n in nodes if n]


def milestones(repo: str, state: str = "open") -> list[dict]:
    if state not in STATES:
        raise AccessError("state is open, closed or all")
    nodes = access.paginate(MILESTONES_QUERY, {**_split(repo), "states": STATES[state]},
                            lambda d: (d.get("repository") or {}).get("milestones"), MILESTONE_CAP)
    return [{"number": n["number"], "title": n["title"], "state": n["state"].lower(),
             "due": (n.get("dueOn") or "")[:10] or None, "description": n.get("description") or "",
             "progress": n.get("progressPercentage"), "open_issues": (n.get("open") or {}).get("totalCount"),
             "closed_issues": (n.get("closed") or {}).get("totalCount")} for n in nodes if n]


RELEASE_FIELDS = ("tagName name isDraft isPrerelease isLatest createdAt publishedAt url tagCommit{oid} "
                  "releaseAssets(first:20){nodes{name size downloadCount}}")
RELEASES_QUERY = ("query($owner:String!,$name:String!,$n:Int!){repository(owner:$owner,name:$name){releases(first:$n,"
                  f"orderBy:{{field:CREATED_AT,direction:DESC}}){{nodes{{{RELEASE_FIELDS} description}}}}}}}}")
RELEASE_QUERY = ("query($owner:String!,$name:String!,$tag:String!){repository(owner:$owner,name:$name){"
                 f"release(tagName:$tag){{{RELEASE_FIELDS} description}}}}}}")


def _release(n: dict) -> dict:
    return {"tag": n["tagName"], "title": n.get("name") or "", "draft": bool(n.get("isDraft")),
            "prerelease": bool(n.get("isPrerelease")), "latest": bool(n.get("isLatest")), "created": n.get("createdAt"),
            "published": n.get("publishedAt"), "url": n.get("url"), "commit": (n.get("tagCommit") or {}).get("oid"),
            "notes": n.get("description") or "",
            "assets": [{"name": a["name"], "size": a.get("size"), "downloads": a.get("downloadCount")}
                       for a in (n.get("releaseAssets") or {}).get("nodes") or []]}


def releases(repo: str, limit: int = 20) -> list[dict]:
    data = access.graphql(RELEASES_QUERY, {**_split(repo), "n": limit})
    return [_release(n) for n in ((data.get("repository") or {}).get("releases") or {}).get("nodes") or [] if n]


def release(repo: str, tag: str) -> dict | None:
    """The release of ``tag``, or None. Looked for among the latest 100 releases, which hold drafts
    for a viewer who can push (a draft's tag does not exist until it is published, so a lookup by
    tag alone could miss it)."""
    found = next((r for r in releases(repo, 100) if r["tag"] == tag), None)
    if found:
        return found
    hit = (access.graphql(RELEASE_QUERY, {**_split(repo), "tag": tag}).get("repository") or {}).get("release")
    return _release(hit) if hit else None


def _gh_json(argv: list[str]):
    done = access.run_gh(argv)
    if done.returncode != 0:
        detail = (done.stderr or done.stdout or "").strip().splitlines()
        raise AccessError(f"gh {' '.join(argv[:2])} failed: {detail[-1] if detail else f'exit {done.returncode}'}"[:400])
    try:
        return json.loads(done.stdout or "null")
    except json.JSONDecodeError as exc:
        raise AccessError(f"gh {' '.join(argv[:2])} printed no JSON") from exc


def workflows(repo: str) -> list[dict]:
    rows = _gh_json(["workflow", "list", "--repo", repo, "--all", "--limit", "100", "--json", "id,name,path,state"]) or []
    return [{"id": w["id"], "name": w["name"], "path": w["path"], "state": w["state"]} for w in rows]


RUN_FIELDS = "databaseId,name,displayTitle,status,conclusion,event,headBranch,headSha,createdAt,url,workflowName,attempt"


def _run_row(r: dict) -> dict:
    return {"id": r["databaseId"], "workflow": r.get("workflowName") or r.get("name"), "title": r.get("displayTitle"),
            "status": r.get("status"), "conclusion": r.get("conclusion") or None, "event": r.get("event"),
            "branch": r.get("headBranch"), "sha": r.get("headSha"), "attempt": r.get("attempt"),
            "created": r.get("createdAt"), "url": r.get("url")}


def runs(repo: str, args: dict) -> list[dict]:
    argv = ["run", "list", "--repo", repo, "--limit", str(access._count(args, "limit", 20, access.LIST_LIMIT)),
            "--json", RUN_FIELDS]
    for key, flag in (("branch", "--branch"), ("workflow", "--workflow")):
        if args.get(key):
            argv += [flag, access._text(args, key)]
    if args.get("status"):
        if args["status"] not in RUN_STATUSES:
            raise AccessError(f"status is one of {', '.join(RUN_STATUSES)}")
        argv += ["--status", args["status"]]
    return [_run_row(r) for r in _gh_json(argv) or []]


def run(repo: str, run_id: int, log: bool = True) -> dict:
    """One run with its jobs, and the end of its failed steps' log (other people's text, capped)."""
    found = _gh_json(["run", "view", str(run_id), "--repo", repo, "--json", f"{RUN_FIELDS},updatedAt,jobs"])
    out = {**_run_row(found), "updated": found.get("updatedAt"),
           "jobs": [{"id": j.get("databaseId"), "name": j.get("name"), "status": j.get("status"),
                     "conclusion": j.get("conclusion") or None,
                     "failed_steps": [s.get("name") for s in j.get("steps") or []
                                      if (s.get("conclusion") or "") in ("failure", "timed_out", "cancelled")]}
                    for j in found.get("jobs") or []]}
    if log and out["conclusion"] in ("failure", "timed_out", "startup_failure"):
        done = access.run_gh(["run", "view", str(run_id), "--repo", repo, "--log-failed"])
        text = CONTROL.sub("", ANSI.sub("", done.stdout or "")) if done.returncode == 0 else ""
        out["failed_log"] = "\n".join(text.splitlines()[-LOG_LINES:])[-LOG_CHARS:] or None
    return out


PROTECTION_QUERY = ("query($owner:String!,$name:String!){repository(owner:$owner,name:$name){branchProtectionRules("
                    "first:50){nodes{pattern requiresApprovingReviews requiredApprovingReviewCount requiresStatusChecks "
                    "requiredStatusCheckContexts allowsForcePushes allowsDeletions requiresLinearHistory isAdminEnforced}}}}")


def ruleset(repo: str, ruleset_id: int) -> dict:
    r = _gh_json(["api", f"repos/{repo}/rulesets/{ruleset_id}"]) or {}
    ref = ((r.get("conditions") or {}).get("ref_name") or {})
    return {"id": r.get("id"), "name": r.get("name"), "target": r.get("target"), "enforcement": r.get("enforcement"),
            "source": r.get("source_type"), "include": ref.get("include") or [], "exclude": ref.get("exclude") or [],
            "bypass": [f"{b.get('actor_type')}:{b.get('actor_id')}:{b.get('bypass_mode')}" for b in r.get("bypass_actors") or []],
            "rules": [{"type": x.get("type"), "parameters": x.get("parameters")} for x in r.get("rules") or []],
            "updated": r.get("updated_at")}


def rules(repo: str) -> dict:
    """The repository's rulesets in full (an organization's that reach it included, marked by their
    source) and its classic branch protection rules."""
    listed = _gh_json(["api", f"repos/{repo}/rulesets?includes_parents=true&per_page=50"]) or []
    found = [ruleset(repo, r["id"]) for r in listed[:20]]
    data = access.graphql(PROTECTION_QUERY, _split(repo))
    classic = [{"pattern": n["pattern"], "approvals": n["requiredApprovingReviewCount"] if n["requiresApprovingReviews"] else 0,
                "checks": n["requiredStatusCheckContexts"] if n["requiresStatusChecks"] else [],
                "force_push": n["allowsForcePushes"], "deletion": n["allowsDeletions"],
                "linear_history": n["requiresLinearHistory"], "admins_too": n["isAdminEnforced"]}
               for n in ((data.get("repository") or {}).get("branchProtectionRules") or {}).get("nodes") or [] if n]
    return {"rulesets": found, "classic": classic, "more": len(listed) > 20}


ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff]")


def _run_id(args: dict, repo: str | None = None) -> int:
    """A run id from an id or a run URL; a URL of another repository than ``repo`` is refused."""
    value = args.get("run")
    text = str(value).strip() if isinstance(value, (int, str)) and not isinstance(value, bool) else ""
    match = re.fullmatch(r"(?:https?://github\.com/([^/]+/[^/]+)/actions/runs/)?(\d+)(?:/.*)?", text)
    if not match:
        raise AccessError("run is a run id or its URL")
    if match.group(1) and repo and not access.same(match.group(1), repo):
        raise AccessError(f"run {text} is a run of {match.group(1)}, not of {repo}")
    return int(match.group(2))


def github_repo(args: dict) -> dict:
    action = access._action(args, REPO_ACTIONS)
    repo = access.parse_repo(access._text(args, "repo"))
    if action == "view":
        return {"ok": True, "repository": settings(repo)}
    tier = access.repo_context(repo)["tier"]
    head = {"ok": True, "repo": repo, "tier": tier}
    if action == "labels":
        found = labels(repo)
        return {**head, "count": len(found), "labels": found}
    if action == "milestones":
        found = milestones(repo, args.get("state") or "open")
        return {**head, "count": len(found), "milestones": found}
    if action == "releases":
        found = releases(repo, access._count(args, "limit", 20, access.LIST_LIMIT))
        return {**head, "count": len(found), "releases": found}
    if action == "workflows":
        found = workflows(repo)
        return {**head, "count": len(found), "workflows": found}
    if action == "runs":
        found = runs(repo, args)
        return {**head, "count": len(found), "runs": found}
    if action == "rules":
        return {**head, **rules(repo)}
    return {**head, "run": run(repo, _run_id(args, repo), log=args.get("log", True) is not False)}
