"""github-access: branch protection — one ruleset per branch that this plugin manages (``admin``: it
decides who can push and merge there, for everyone at once).

Registered into ``changes.py``. The ruleset is named ``Managed protection: <branch>`` and is the only
one ``branch_rule`` ever writes: rulesets someone else made (a repository's own, an
organization's) are read, never changed, and GitHub applies every ruleset that reaches a branch
together. A change names only what it moves; the rest keeps what the ruleset says now (or, for a
new one, blocks force pushes and deletion and lets repository admins bypass).
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
reads = _load("hermes_github_access_repo_reads", HERE / "access_repo.py")
repo_ops = _load("hermes_github_access_ops_repo", HERE / "ops_repo.py")
release_ops = _load("hermes_github_access_ops_release", HERE / "ops_release.py")
access = changes.access
AccessError = changes.AccessError
Op, say, gh = changes.Op, changes.say, changes.gh

PREFIX = "Managed protection: "
DEFAULT_BRANCH = "~DEFAULT_BRANCH"
ADMIN_ROLE = {"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}  # the repository admin role
MAX_APPROVALS = 10
BRANCH = re.compile(r"^(?!.*\.\.)(?!/)(?!.*/$)[A-Za-z0-9._/-]{1,200}$")
# setting -> the rule type that carries it; other rule types in the ruleset are kept as they are
RULE_TYPES = {"block_force_push": "non_fast_forward", "block_deletion": "deletion",
              "linear_history": "required_linear_history"}
MANAGED_TYPES = {"pull_request", "required_status_checks", *RULE_TYPES.values()}
NEW = {"require_pr": False, "approvals": 0, "required_checks": [], "block_force_push": True, "block_deletion": True,
       "linear_history": False, "admin_bypass": True, "disable": False}
SETTINGS = tuple(NEW)

changes.key("branch", "str", description="branch_rule: the branch (default: the repository's default branch)")
changes.key("require_pr", "bool")
changes.key("approvals", "int")
changes.key("required_checks", "list", text=True)
changes.key("block_force_push", "bool")
changes.key("block_deletion", "bool")
changes.key("linear_history", "bool")
changes.key("admin_bypass", "bool")
changes.key("disable", "bool")


def _is_admin(actor: dict) -> bool:
    return actor.get("actor_type") == ADMIN_ROLE["actor_type"] and actor.get("actor_id") == ADMIN_ROLE["actor_id"]


def _state(raw: dict | None) -> dict:
    """What a managed ruleset says now, in the op's own keys (and how admins bypass, for the card)."""
    if raw is None:
        return {**NEW, "admin_mode": ADMIN_ROLE["bypass_mode"]}
    by_type = {r.get("type"): r.get("parameters") or {} for r in raw.get("rules") or []}
    pr = by_type.get("pull_request")
    checks = (by_type.get("required_status_checks") or {}).get("required_status_checks") or []
    admin = next((b for b in raw.get("bypass_actors") or [] if _is_admin(b)), None)
    return {"require_pr": pr is not None, "approvals": (pr or {}).get("required_approving_review_count") or 0,
            "required_checks": [c.get("context") for c in checks if c.get("context")],
            **{key: kind in by_type for key, kind in RULE_TYPES.items()},
            "admin_bypass": admin is not None, "admin_mode": (admin or ADMIN_ROLE)["bypass_mode"],
            # "evaluate" (a dry run some plans offer) enforces nothing either
            "disable": raw.get("enforcement") in ("disabled", "evaluate")}


def _body(name: str, include: str, raw: dict | None, want: dict) -> dict:
    """The ruleset to send: the managed rules as ``want`` says, anything else in it kept."""
    old = {r.get("type"): r for r in (raw or {}).get("rules") or []}
    rules = [r for t, r in old.items() if t not in MANAGED_TYPES]
    if want["require_pr"]:
        params = {"dismiss_stale_reviews_on_push": False, "require_code_owner_review": False,
                  "require_last_push_approval": False, "required_review_thread_resolution": False,
                  **((old.get("pull_request") or {}).get("parameters") or {})}
        params["required_approving_review_count"] = want["approvals"]
        rules.append({"type": "pull_request", "parameters": params})
    if want["required_checks"]:
        params = {"strict_required_status_checks_policy": False,
                  **((old.get("required_status_checks") or {}).get("parameters") or {})}
        known = {c.get("context"): c for c in params.get("required_status_checks") or []}
        params["required_status_checks"] = [known.get(c) or {"context": c} for c in want["required_checks"]]
        rules.append({"type": "required_status_checks", "parameters": params})
    rules += [{"type": kind} for key, kind in RULE_TYPES.items() if want[key]]
    actors = (raw or {}).get("bypass_actors") or []
    bypass = [b for b in actors if not _is_admin(b)]
    if want["admin_bypass"]:
        # The admin entry the ruleset has stays as it is (bypassing in pull requests only stays so).
        bypass.append(next((b for b in actors if _is_admin(b)), dict(ADMIN_ROLE)))
    enforcement = (raw or {}).get("enforcement") or "active"
    if not want["disable"]:
        enforcement = "active"
    elif enforcement == "active":
        enforcement = "disabled"
    return {"name": name, "target": "branch", "enforcement": enforcement,
            "conditions": {"ref_name": {"include": [include], "exclude": []}}, "rules": rules, "bypass_actors": bypass}


def _bypass(s: dict) -> str:
    if not s["admin_bypass"]:
        return "admins too, no bypass"
    return "admins may bypass" + (" in PRs only" if s.get("admin_mode") == "pull_request" else "")


def _summary(s: dict) -> list[str]:
    """The whole rule, what decides who gets through first: the check names, which can run long, last."""
    out = ["⚠️ NOT ENFORCED (off)"] if s["disable"] else []
    out.append(_bypass(s))
    if s["require_pr"]:
        out.append(f"PR with {s['approvals']} approval{'s' if s['approvals'] != 1 else ''}")
    out += [label for key, label in (("block_force_push", "no force push"), ("block_deletion", "no deletion"),
                                     ("linear_history", "linear history")) if s[key]]
    if s["required_checks"]:
        out.append(f"{len(s['required_checks'])} check(s): {', '.join(s['required_checks'])}")
    return out


def _diff(before: dict, after: dict) -> list[str]:
    """What moves, what decides who gets through first."""
    out = []
    if before["disable"] != after["disable"]:
        out.append("⚠️ turned off" if after["disable"] else "turned on")
    if before["admin_bypass"] != after["admin_bypass"]:
        out.append(_bypass(after))
    if before["require_pr"] != after["require_pr"]:
        out.append(f"+ PR with {after['approvals']} approval(s)" if after["require_pr"] else "− PR")
    elif after["require_pr"] and before["approvals"] != after["approvals"]:
        out.append(f"approvals {before['approvals']} → {after['approvals']}")
    for key, label in (("block_force_push", "no force push"), ("block_deletion", "no deletion"),
                       ("linear_history", "linear history")):
        if before[key] != after[key]:
            out.append(f"{'+' if after[key] else '−'} {label}")
    if before["required_checks"] != after["required_checks"]:
        out.append(f"checks → {', '.join(after['required_checks'])}" if after["required_checks"] else "− checks")
    return out


def _managed(repo: str, name: str) -> dict | None:
    """The repository's own ruleset of that name (raw), or None; never one an organization made."""
    listed = reads._gh_json(["api", f"repos/{repo}/rulesets?includes_parents=false&per_page=100"]) or []
    found = [r for r in listed if r.get("name") == name and r.get("source_type", "Repository") == "Repository"]
    if len(found) > 1:
        raise AccessError(f"branch_rule: {repo} has {len(found)} rulesets named {name!r}; remove the extra ones")
    return reads._gh_json(["api", f"repos/{repo}/rulesets/{found[0]['id']}"]) if found else None


def _branch_rule_check(change):
    branch = change.get("branch")
    if branch is not None and not BRANCH.match(branch):
        raise AccessError(f"branch_rule: {branch!r} is not a branch name (no patterns: one branch per rule)")
    if change.get("approvals") is not None and not 0 <= change["approvals"] <= MAX_APPROVALS:
        raise AccessError(f"branch_rule: approvals is 0 to {MAX_APPROVALS}")
    if change.get("approvals") and change.get("require_pr") is False:
        raise AccessError("branch_rule: approvals need require_pr")
    for check in change.get("required_checks") or []:
        if len(check) > 200:
            raise AccessError("branch_rule: a check name is at most 200 characters")
    if not any(change.get(k) is not None for k in SETTINGS):
        raise AccessError(f"branch_rule: nothing to change; set any of {', '.join(SETTINGS)}")


def _branch_rule_plan(step, planned):
    c = step["change"]
    repo = planned.repo_of(c)
    repo_ops._admin(repo, "branch_rule")
    branch = c.get("branch")
    if branch and not release_ops.ref_sha(repo["repo"], f"refs/heads/{branch}"):
        raise AccessError(f"branch_rule: {repo['repo']} has no branch {branch!r}")
    where = branch or "default branch"
    name = PREFIX + where
    raw = _managed(repo["repo"], name)
    before = _state(raw)
    after = {**before, **{k: c[k] for k in SETTINGS if c.get(k) is not None}}
    if c.get("approvals") and c.get("require_pr") is None:
        after["require_pr"] = True
    if not after["require_pr"]:
        after["approvals"] = 0
    after["required_checks"] = list(dict.fromkeys(after["required_checks"]))
    if raw is not None and not _diff(before, after):
        raise AccessError(f"branch_rule: {name!r} on {repo['repo']} already says this")
    body = _body(name, f"refs/heads/{branch}" if branch else DEFAULT_BRANCH, raw, after)
    if not body["rules"]:
        raise AccessError("branch_rule: that leaves the ruleset no rule; set disable: true to turn it off instead")
    step.update(repo=repo, where=where, name=name, raw=raw, before=before, after=after, body=body)
    # Bound by its last update: a ruleset changed in GitHub's page after the card is a different change.
    planned.note(f"ruleset:{repo['repo'].lower()}:{name.lower()}",
                 {"kind": "ruleset", "name": f"{name} of {repo['repo']} ({'#' + str(raw['id']) if raw else 'new'})",
                  "tier": repo["tier"], "id": f"{(raw or {}).get('id', 'new')}:{(raw or {}).get('updated_at', '')}"})


def _branch_rule_describe(step):
    which = f"branch {say(step['change']['branch'], 40)}" if step["change"].get("branch") else "the default branch"
    if step["raw"] is None:
        return f"Protect {which} of {step['repo']['repo']}: {say(', '.join(_summary(step['after'])), 90)}"
    return (f"Change the protection of {which} of {step['repo']['repo']}: "
            f"{say('; '.join(_diff(step['before'], step['after'])), 90)}")


def _branch_rule_run(step, out):
    repo, raw = step["repo"]["repo"], step["raw"]
    now = _managed(repo, step["name"])
    if (now or {}).get("id") != (raw or {}).get("id") or (now or {}).get("updated_at") != (raw or {}).get("updated_at"):
        raise AccessError(f"{step['name']!r} on {repo} changed since the card; nothing was sent. Send it again for a "
                          "new card")
    route = f"repos/{repo}/rulesets/{raw['id']}" if raw else f"repos/{repo}/rulesets"
    made = json.loads(gh(["api", "--method", "PUT" if raw else "POST", route, "--input", "-"],
                         stdin=json.dumps(step["body"])) or "{}")
    return {**out, "repo": repo, "ruleset": step["name"], "id": made.get("id") or (raw or {}).get("id"),
            "enforcement": made.get("enforcement") or step["body"]["enforcement"], "now": _summary(step["after"])}


changes.register(Op(
    "branch_rule", "admin",
    "repo, branch (default: the default branch), require_pr, approvals (0-10), required_checks [names], "
    "block_force_push, block_deletion, linear_history, admin_bypass, disable: the branch's managed ruleset "
    "(\"Managed protection: <branch>\"), made or changed; what a change leaves out keeps its current value (a new "
    "one blocks force pushes and deletion and lets admins bypass)",
    _branch_rule_plan, _branch_rule_describe, _branch_rule_run,
    optional=("repo", "branch", *SETTINGS), check=_branch_rule_check))
