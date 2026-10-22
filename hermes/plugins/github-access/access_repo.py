"""github-access: repository reads — a repository's settings, labels and milestones.

The engine behind ``github_repo``, and what the repository ops of ``github_change`` read before a
card (the settings a change would move from, the labels and milestones it names). Read through
the user's own ``gh`` login like every other read; nothing is stored.
"""

from __future__ import annotations

import importlib.util
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

REPO_ACTIONS = ("view", "labels", "milestones")
LABEL_CAP = 500
MILESTONE_CAP = 300

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


def github_repo(args: dict) -> dict:
    action = access._action(args, REPO_ACTIONS)
    repo = access.parse_repo(access._text(args, "repo"))
    if action == "view":
        return {"ok": True, "repository": settings(repo)}
    tier = access.repo_context(repo)["tier"]
    if action == "labels":
        found = labels(repo)
        return {"ok": True, "repo": repo, "tier": tier, "count": len(found), "labels": found}
    found = milestones(repo, args.get("state") or "open")
    return {"ok": True, "repo": repo, "tier": tier, "count": len(found), "milestones": found}
