"""github-access: GitHub Actions changes — re-running a run and starting a workflow by hand. Both
are ``admin``: a workflow can deploy, publish or spend, whatever its name says.

Registered into ``changes.py``. Each reads the run or the workflow, and the commit it would run
on, before the card; that commit is bound like a target, so a push after the card is a different
change.
"""

from __future__ import annotations

import importlib.util
import json
import os
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
release_ops = _load("hermes_github_access_ops_release", HERE / "ops_release.py")
access = changes.access
AccessError = changes.AccessError
Op, say, gh = changes.Op, changes.say, changes.gh

RERUNNABLE = ("failure", "cancelled", "timed_out", "startup_failure")
FILE_QUERY = ("query($owner:String!,$name:String!,$expr:String!){repository(owner:$owner,name:$name){"
              "object(expression:$expr){... on Blob{text}}}}")

changes.key("run", "str", description="a workflow run id or its URL")
changes.key("failed_only", "bool")
changes.key("workflow", "str", description="a workflow's name, file name or id")
changes.key("ref", "str")
changes.key("inputs", "map", text=True)


# --- run_rerun ------------------------------------------------------------------------------------

def _run_rerun_plan(step, planned):
    c = step["change"]
    repo = planned.repo_of(c)
    step["repo"] = repo
    found = reads.run(repo["repo"], reads._run_id({"run": c["run"]}, repo["repo"]), log=False)
    if found["status"] != "completed":
        raise AccessError(f"run_rerun: run {found['id']} is {found['status']}; wait for it to finish")
    failed_only = c.get("failed_only", True) is not False
    if failed_only and found["conclusion"] not in RERUNNABLE:
        raise AccessError(f"run_rerun: run {found['id']} ended {found['conclusion']}; it has no failed jobs to re-run")
    step["run"], step["failed_only"] = found, failed_only
    # The attempt is bound: a re-run someone else starts after the card is a different run.
    planned.note(f"run:{repo['repo'].lower()}:{found['id']}",
                 {"kind": "run", "name": f"{found['workflow']} run {found['id']} on {found['branch']} at "
                                         f"{(found['sha'] or '')[:7]}", "tier": repo["tier"],
                  "id": f"{found['id']}:{found['attempt']}"})


def _run_rerun_describe(step):
    r = step["run"]
    what = "the failed jobs of" if step["failed_only"] else "every job of"
    return (f"Re-run {what} {say(r['workflow'], 40)} run {r['id']}, its steps again, a deploy included "
            f"({r['conclusion']}, {r['event']} on {say(r['branch'], 30)})")


def _run_rerun_run(step, out):
    argv = ["run", "rerun", str(step["run"]["id"]), "--repo", step["repo"]["repo"]]
    gh([*argv, "--failed"] if step["failed_only"] else argv)
    return {**out, "repo": step["repo"]["repo"], "run": step["run"]["id"], "failed_only": step["failed_only"]}


# --- workflow_dispatch ----------------------------------------------------------------------------

# workflow_dispatch as a trigger, outside comments: `on: workflow_dispatch`, `[push, workflow_dispatch]`
# or a `workflow_dispatch:` key.
COMMENT = re.compile(r"(?m)(?:^|\s)#.*$")
DISPATCH = re.compile(r"(?<![\w-])workflow_dispatch(?![\w-])")


def _workflow(repo: str, wanted: str) -> dict:
    """The one workflow ``wanted`` names: its id or path first, then its file name or name, which must
    name exactly one."""
    listed = reads.workflows(repo)
    if len(listed) >= 100:
        raise AccessError(f"workflow_dispatch: {repo} has 100 workflows or more; name it by id or path")
    exact = [w for w in listed if str(w["id"]) == wanted or access.same(w["path"], wanted)]
    loose = [w for w in listed if access.same(os.path.basename(w["path"]), wanted) or access.same(w["name"], wanted)]
    found = exact or loose
    if not found:
        raise AccessError(f"workflow_dispatch: {repo} has no workflow {wanted!r}")
    if len(found) > 1:
        raise AccessError(f"workflow_dispatch: {wanted!r} names {len(found)} workflows "
                          f"({', '.join(f'{w['name']} {w['path']} #{w['id']}' for w in found)}); name it by id or path")
    return found[0]

def _workflow_dispatch_plan(step, planned):
    c = step["change"]
    repo = planned.repo_of(c)
    step["repo"] = repo
    found = _workflow(repo["repo"], c["workflow"].strip())
    if found["state"] != "active":
        raise AccessError(f"workflow_dispatch: {found['name']} is {found['state']}")
    ref = c.get("ref") or reads.settings(repo["repo"])["default_branch"]
    sha = (release_ops.ref_sha(repo["repo"], f"refs/heads/{ref}")
           or release_ops.ref_sha(repo["repo"], f"refs/tags/{ref}"))
    if not sha:
        raise AccessError(f"workflow_dispatch: {repo['repo']} has no branch or tag {ref!r}")
    owner, name = repo["repo"].split("/", 1)
    blob = ((access.graphql(FILE_QUERY, {"owner": owner, "name": name, "expr": f"{sha}:{found['path']}"})
             .get("repository") or {}).get("object") or {})
    if not DISPATCH.search(COMMENT.sub("", blob.get("text") or "")):
        raise AccessError(f"workflow_dispatch: {found['name']} at {ref} cannot be started by hand (no workflow_dispatch)")
    step["workflow"], step["ref"], step["sha"] = found, ref, sha
    # The commit is bound: a push to the ref after the card runs other code, so it is a different change.
    planned.note(f"workflow:{repo['repo'].lower()}:{found['id']}",
                 {"kind": "workflow", "name": f"{found['name']} ({found['path']}) on {ref} at {sha[:7]}",
                  "tier": repo["tier"], "id": f"{found['id']}@{sha}"})


def _workflow_dispatch_describe(step):
    inputs = ", ".join(f"{k}={v}" for k, v in (step["change"].get("inputs") or {}).items())
    return (f"Run workflow {say(step['workflow']['name'], 40)}, whatever it does (a deploy, a publish), on "
            f"{say(step['ref'], 30)} at {step['sha'][:7]}" + (f" with {say(inputs, 60)}" if inputs else ""))


def _workflow_dispatch_run(step, out):
    c = step["change"]
    argv = ["workflow", "run", str(step["workflow"]["id"]), "--repo", step["repo"]["repo"], "--ref", step["ref"]]
    stdin = None
    if c.get("inputs"):
        # Inputs as JSON on stdin: never -F, which reads a value that starts with @ as a file.
        argv.append("--json")
        stdin = json.dumps(c["inputs"])
    gh(argv, stdin=stdin)
    return {**out, "repo": step["repo"]["repo"], "workflow": step["workflow"]["name"], "ref": step["ref"],
            "sha": step["sha"], "note": "started; read github_repo runs for its run"}


for _op in (
        Op("run_rerun", "admin", "repo, run (an id or its URL), failed_only (default true): re-run a finished run",
           _run_rerun_plan, _run_rerun_describe, _run_rerun_run, required=("run",), optional=("repo", "failed_only")),
        Op("workflow_dispatch", "admin",
           "repo, workflow (name, file name or id), ref (default: the default branch), inputs {name: value}: start a "
           "workflow that takes workflow_dispatch", _workflow_dispatch_plan, _workflow_dispatch_describe,
           _workflow_dispatch_run, required=("workflow",), optional=("repo", "ref", "inputs"))):
    changes.register(_op)
