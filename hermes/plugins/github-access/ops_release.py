"""github-access: release changes — a draft release (``create``: only people who can push see a
draft), editing a release (``routine`` while it is a draft, ``admin`` once published), and
publishing one (``admin``: it makes the tag and tells everyone watching).

Registered into ``changes.py``. Each reads the release before the card (``access_repo.py``).
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


HERE = Path(__file__).resolve().parent
changes = _load("hermes_github_access_changes", HERE / "changes.py")
reads = _load("hermes_github_access_repo_reads", HERE / "access_repo.py")
access = changes.access
AccessError = changes.AccessError
Op, say, gh = changes.Op, changes.say, changes.gh

TAG = re.compile(r"^(?!.*\.\.)(?!.*//)[A-Za-z0-9][A-Za-z0-9._/+-]{0,99}$")
SHA = re.compile(r"^[0-9a-f]{40}$")
REF_QUERY = ("query($owner:String!,$name:String!,$ref:String!){repository(owner:$owner,name:$name){"
             "ref(qualifiedName:$ref){name target{oid}}}}")

changes.key("tag", "str")
changes.key("target", "str", description="release_create: the branch or full commit SHA a new tag points at")
changes.key("notes", "str", text=True)
changes.key("generate_notes", "bool")
changes.key("prerelease", "bool")
changes.key("latest", "bool")


def ref_sha(repo: str, qualified: str) -> str | None:
    owner, name = repo.split("/", 1)
    found = (access.graphql(REF_QUERY, {"owner": owner, "name": name, "ref": qualified}).get("repository") or {}).get("ref")
    return ((found or {}).get("target") or {}).get("oid") if found else None


def _tag_check(change):
    if not TAG.match(change["tag"]):
        raise AccessError(f"{change['op']}: tag {change['tag']!r} is not a tag name (letters, digits, . _ / + -)")


def _release_of(step, planned) -> dict:
    """The release a change names, bound by its state and its tag's commit: a draft published (or a
    tag moved) after the card is a different change, whatever class the card was drawn for."""
    c = step["change"]
    repo = step["repo"] = planned.repo_of(c)
    found = reads.release(repo["repo"], c["tag"])
    if not found:
        raise AccessError(f"{c['op']}: {repo['repo']} has no release {c['tag']!r}")
    step["release"] = found
    step["tag_sha"] = ref_sha(repo["repo"], f"refs/tags/{found['tag']}")
    state = "draft" if found["draft"] else "published"
    planned.note(f"release:{repo['repo'].lower()}:{found['tag']}",
                 {"kind": "release", "name": f"{found['tag']} ({state}) of {repo['repo']}", "tier": repo["tier"],
                  "id": f"{found['tag']}:{state}:{step['tag_sha'] or 'no tag yet'}"})
    return found


def _release_create_plan(step, planned):
    c = step["change"]
    repo = planned.repo_of(c)
    step["repo"] = repo
    if reads.release(repo["repo"], c["tag"]):
        raise AccessError(f"release_create: {repo['repo']} already has a release {c['tag']!r}; change it with release_edit")
    step["tag_sha"] = ref_sha(repo["repo"], f"refs/tags/{c['tag']}")
    if c.get("target"):
        if step["tag_sha"]:
            raise AccessError(f"release_create: tag {c['tag']} exists already; target is for a new tag")
        if not SHA.match(c["target"]) and not ref_sha(repo["repo"], f"refs/heads/{c['target']}"):
            raise AccessError(f"release_create: {repo['repo']} has no branch {c['target']!r} (or give a full commit SHA)")


def _release_create_describe(step):
    c = step["change"]
    where = (f"tag {c['tag']} at {step['tag_sha'][:7]}" if step["tag_sha"]
             else f"new tag {c['tag']} from {c.get('target') or 'the default branch'}")
    notes = ("generated notes" if c.get("generate_notes") else "") + \
        (f"{' + ' if c.get('generate_notes') else ''}notes ({len(c['notes'])} chars)" if c.get("notes") else "")
    extra = "; ".join(x for x in (where, notes, "prerelease" if c.get("prerelease") else "") if x)
    return (f"Draft release {say(c.get('title') or c['tag'], 40)} in {step['repo']['repo']}, seen only by pushers "
            f"until published ({say(extra, 80)})")


def _release_create_run(step, out):
    c = step["change"]
    argv = ["release", "create", c["tag"], "--repo", step["repo"]["repo"], "--draft", "--notes-file", "-"]
    if c.get("title"):
        argv += ["--title", c["title"]]
    if c.get("target"):
        argv += ["--target", c["target"]]
    if c.get("generate_notes"):
        argv.append("--generate-notes")
    if c.get("prerelease"):
        argv.append("--prerelease")
    printed = gh(argv, stdin=c.get("notes") or "").strip()
    return {**out, "repo": step["repo"]["repo"], "release": c["tag"], "draft": True,
            "url": printed.splitlines()[-1] if printed else None}


def _release_edit_check(change):
    if not any(change.get(k) is not None for k in ("title", "notes", "prerelease", "target")):
        raise AccessError("release_edit: title, notes, prerelease or target is required")


def _release_edit_plan(step, planned):
    found = _release_of(step, planned)
    if not found["draft"]:
        step["class"] = changes.ADMIN  # what everyone reads, at once
        if step["change"].get("target"):
            raise AccessError(f"release_edit: {found['tag']} is published; its tag already points at a commit")


def _release_edit_describe(step):
    c, r = step["change"], step["release"]
    parts = [f"title → {say(c['title'], 50)}" if c.get("title") is not None else "",
             f"notes replaced ({len(c['notes'])} chars)" if c.get("notes") is not None else "",
             f"prerelease {'on' if c['prerelease'] else 'off'}" if c.get("prerelease") is not None else "",
             f"target → {c['target']}" if c.get("target") else ""]
    state = "draft" if r["draft"] else "published"
    return f"Edit {state} release {say(r['tag'], 40)} in {step['repo']['repo']}: " + "; ".join(p for p in parts if p)


def _release_edit_run(step, out):
    c = step["change"]
    argv = ["release", "edit", c["tag"], "--repo", step["repo"]["repo"]]
    stdin = None
    if c.get("title") is not None:
        argv += ["--title", c["title"]]
    if c.get("notes") is not None:
        argv += ["--notes-file", "-"]
        stdin = c["notes"]
    if c.get("prerelease") is not None:
        argv.append(f"--prerelease={'true' if c['prerelease'] else 'false'}")
    if c.get("target"):
        argv += ["--target", c["target"]]
    gh(argv, stdin=stdin)
    return {**out, "repo": step["repo"]["repo"], "release": c["tag"]}


def _release_publish_plan(step, planned):
    found = _release_of(step, planned)
    if not found["draft"]:
        raise AccessError(f"release_publish: {found['tag']} is published already")


def _release_publish_describe(step):
    r = step["release"]
    tag = f"tag {r['tag']} at {step['tag_sha'][:7]}" if step["tag_sha"] else f"creates tag {r['tag']}"
    latest = "; marked Latest" if step["change"].get("latest") else ""
    return (f"Publish release {say(r['title'] or r['tag'], 40)} of {step['repo']['repo']}, seen by every reader and "
            f"told to watchers ({say(tag, 40)}{latest})")


def _release_publish_run(step, out):
    argv = ["release", "edit", step["release"]["tag"], "--repo", step["repo"]["repo"], "--draft=false"]
    if step["change"].get("latest"):
        argv.append("--latest")
    gh(argv)
    return {**out, "repo": step["repo"]["repo"], "release": step["release"]["tag"], "published": True}


for _op in (
        Op("release_create", "create",
           "repo, tag, target (a branch or full SHA, for a new tag), title, notes, generate_notes, prerelease: always a "
           "draft", _release_create_plan, _release_create_describe, _release_create_run, required=("tag",),
           optional=("repo", "target", "title", "notes", "generate_notes", "prerelease"), check=_tag_check),
        Op("release_edit", "routine",
           "repo, tag, title, notes, prerelease, target (a draft's): routine on a draft, admin once published",
           _release_edit_plan, _release_edit_describe, _release_edit_run, required=("tag",),
           optional=("repo", "title", "notes", "prerelease", "target"),
           check=lambda c: (_tag_check(c), _release_edit_check(c))),
        Op("release_publish", "admin", "repo, tag, latest: publish a draft release", _release_publish_plan,
           _release_publish_describe, _release_publish_run, required=("tag",), optional=("repo", "latest"),
           check=_tag_check)):
    changes.register(_op)
