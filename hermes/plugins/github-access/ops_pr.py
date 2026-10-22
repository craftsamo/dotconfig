"""github-access: pull request changes — opening one, editing, commenting, marking it ready or
draft, closing and reopening (``create``), and merging (``admin``). Opening, editing and
commenting can upload images and videos into the text (``attachments``).

Registered into ``changes.py``. Each reads the pull request before the card (``access_pr.py``).
An upload is permanent and readable by anyone who can read the repository (by anyone at all on a
public one), so every file is a target of its own: shown on the card with its size, bound by its
SHA-256 (a file changed after the card is a different change), checked again right before gh
uploads it, and never covered by a mandate.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import time
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
repo_ops = _load("hermes_github_access_ops_repo", HERE / "ops_repo.py")
issue_ops = _load("hermes_github_access_ops_issue", HERE / "ops_issue.py")
reads = _load("hermes_github_access_pr_reads", HERE / "access_pr.py")
repo_reads = _load("hermes_github_access_repo_reads", HERE / "access_repo.py")
access = changes.access
AccessError = changes.AccessError
Op, say, gh = changes.Op, changes.say, changes.gh

METHODS = ("merge", "squash", "rebase")
METHOD_SETTING = {"merge": "allow_merge_commit", "squash": "allow_squash_merge", "rebase": "allow_rebase_merge"}
MIB = 1024 * 1024
ATTACH_LIMIT = 50
ATTACH_VERSION = (2, 99, 0)
# extension -> (kind, size limit, does the file start like one)
MEDIA = {
    ".png": ("image", 10 * MIB, lambda h: h.startswith(b"\x89PNG\r\n\x1a\n")),
    ".jpg": ("image", 10 * MIB, lambda h: h.startswith(b"\xff\xd8\xff")),
    ".jpeg": ("image", 10 * MIB, lambda h: h.startswith(b"\xff\xd8\xff")),
    ".gif": ("image", 10 * MIB, lambda h: h[:6] in (b"GIF87a", b"GIF89a")),
    ".webp": ("image", 10 * MIB, lambda h: h[:4] == b"RIFF" and h[8:12] == b"WEBP"),
    ".svg": ("image", 10 * MIB, lambda h: b"<svg" in h.lower()),
    ".mp4": ("video", 100 * MIB, lambda h: h[4:8] == b"ftyp"),
    ".mov": ("video", 100 * MIB, lambda h: h[4:8] in (b"ftyp", b"moov", b"wide", b"mdat", b"free")),
    ".webm": ("video", 100 * MIB, lambda h: h.startswith(b"\x1a\x45\xdf\xa3")),
}

changes.key("pr", "str", description="12, #12, owner/repo#12 or a pull request URL")
changes.key("head", "str", description="pr_create: the branch with the work, or owner:branch from a fork")
changes.key("base", "str")
changes.key("draft", "bool")
changes.key("undo", "bool")
changes.key("method", "str", enum=list(METHODS))
changes.key("delete_branch", "bool")
changes.key("subject", "str", text=True)
changes.key("add_reviewers", "list")
changes.key("remove_reviewers", "list")
changes.key("attachments", "map", text=True,
            description="absolute path of an image or video -> its alt text (\"\" for none)")

BRANCH_QUERY = repo_ops.BRANCH_QUERY
_version: tuple | None = None


# --- attachments ----------------------------------------------------------------------------------

def gh_version() -> tuple:
    global _version
    if _version is None:
        done = access.run_gh(["--version"])
        found = re.search(r"(\d+)\.(\d+)\.(\d+)", done.stdout or "")
        _version = tuple(int(x) for x in found.groups()) if found else (0, 0, 0)
    return _version


def _size(n: int) -> str:
    return f"{n / MIB:.1f} MiB" if n >= MIB else f"{max(1, n // 1024)} KiB"


def _home(path: str) -> str:
    """A path for the card, whole (two files must never read alike), with the home folder as ~."""
    home = os.path.expanduser("~")
    return "~" + path[len(home):] if path == home or path.startswith(home + os.sep) else path


def _read(real: str, limit: int, op: str, name: str) -> bytes:
    """A regular file's bytes, at most ``limit``. Opened without blocking and checked on the open
    descriptor, so a FIFO or a device is refused instead of waited on."""
    try:
        fd = os.open(real, os.O_RDONLY | os.O_NONBLOCK)
    except OSError as exc:
        raise AccessError(f"{op}: attachment {name} cannot be read ({exc.strerror})") from exc
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size == 0:
            raise AccessError(f"{op}: attachment {name} is not a file with content")
        chunks, total = [], 0
        while block := os.read(fd, 1 << 20):
            total += len(block)
            if total > limit:
                break
            chunks.append(block)
    finally:
        os.close(fd)
    if total > limit:
        raise AccessError(f"{op}: {name} is over {limit // MIB} MiB, the most GitHub takes for its type")
    return b"".join(chunks)


def attachment(path_text: str, alt: str, op: str) -> dict:
    """One file to upload, read now: an image or video whose content starts like its type, within
    GitHub's size limits, named by an absolute path a body can reference as written."""
    written = path_text.strip()
    path = os.path.expanduser(written)
    if not os.path.isabs(path):
        raise AccessError(f"{op}: attachment {path_text!r} is not an absolute path")
    if "#" in path:
        raise AccessError(f"{op}: attachment {path_text!r} has a # in its path; copy it to a name without one")
    if "#" in alt:
        raise AccessError(f"{op}: the alt text of {os.path.basename(path)} cannot hold a #")
    kind = MEDIA.get(os.path.splitext(path)[1].lower())
    if not kind:
        raise AccessError(f"{op}: {os.path.basename(path)} is not an image or video GitHub takes "
                          f"({', '.join(MEDIA)})")
    media, limit, looks = kind
    real = os.path.realpath(path)
    data = _read(real, limit, op, os.path.basename(path))
    if not looks(data[:64]):
        raise AccessError(f"{op}: {os.path.basename(path)} does not start like a {os.path.splitext(path)[1]} file")
    if media == "video" and alt:
        raise AccessError(f"{op}: a video plays as a player and takes no alt text ({os.path.basename(path)})")
    shown = _home(path) if real == path else f"{_home(path)} → {_home(real)}"
    return {"written": written, "path": path, "real": real, "name": os.path.basename(path), "kind": media,
            "size": len(data), "limit": limit, "alt": alt, "shown": shown, "sha256": hashlib.sha256(data).hexdigest()}


def plan_attachments(step: dict, planned, repo: dict) -> None:
    files = step["change"].get("attachments") or {}
    if not files:
        return
    op = step["change"]["op"]
    if len(files) > ATTACH_LIMIT:
        raise AccessError(f"{op}: at most {ATTACH_LIMIT} attachments per change")
    if gh_version() < ATTACH_VERSION:
        raise AccessError(f"{op}: attaching files needs gh {'.'.join(map(str, ATTACH_VERSION))} or later")
    step["files"] = []
    for path_text, alt in files.items():
        f = attachment(path_text, alt, op)
        if any(x["real"] == f["real"] for x in step["files"]):
            raise AccessError(f"{op}: {f['name']} is attached twice")
        step["files"].append(f)
        planned.note(f"file:{f['sha256']}:{repo['repo'].lower()}",
                     {"kind": "file", "name": f"{f['shown']} ({f['kind']}, {_size(f['size'])})",
                      "tier": repo["tier"], "id": f"sha256:{f['sha256']}"})
    # The spellings a body may use for a file this change uploads (gh swaps them for its URL).
    step["attached"] = {p for f in step["files"] for p in (f["written"], f["path"])}


@contextlib.contextmanager
def _snapshots(step: dict):
    """Private copies of exactly the bytes the card bound, which gh then reads: the file named on the
    card is read once more here and compared, and gh never reopens a path the model chose (a symlink
    retargeted after the card uploads nothing it points to now). Yields path -> copy."""
    files = step.get("files") or []
    if not files:
        yield {}
        return
    folder = tempfile.mkdtemp(prefix="github-access-")
    try:
        copies = {}
        for i, f in enumerate(files):
            data = _read(f["real"], f["limit"], step["change"]["op"], f["name"])
            if hashlib.sha256(data).hexdigest() != f["sha256"]:
                raise AccessError(f"{f['name']} changed since the card; nothing of this change was sent. Send it "
                                  "again for a new card")
            inner = os.path.join(folder, str(i))
            os.mkdir(inner, 0o700)
            copy = os.path.join(inner, f["name"])  # the same name: gh uses it as the alt text when none is given
            fd = os.open(copy, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
            copies[f["path"]] = copy
        yield copies
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def _uploads(step: dict) -> str:
    files = step.get("files") or []
    if not files:
        return ""
    who = "people who can read the repository" if step["repo"]["private"] else "anyone, signed in or not"
    return f"; uploads {len(files)} file{'s' if len(files) > 1 else ''} ({say(', '.join(f['name'] for f in files), 50)}), " \
           f"permanent, readable by {who}"


def _run_attaching(step: dict, argv: list[str], stdin: str | None, out: dict) -> str:
    """Run a gh command that may upload the step's files (from their copies; a body's references to a
    file point at its copy, so gh swaps them for the uploaded URL). gh still makes the pull request or
    comment when some files fail, exiting non-zero with its URL on stdout: that URL is recorded before
    the failure is raised."""
    with _snapshots(step) as copies:
        flags = []
        for f in step.get("files") or []:
            flags.append(f"--attach={copies[f['path']]}" + (f"#{f['alt']}" if f["alt"] else ""))
            if stdin is not None:
                for spelled in sorted({f["written"], f["path"]}, key=len, reverse=True):
                    stdin = stdin.replace(spelled, copies[f["path"]])
        done = access.run_gh([*argv, *flags], stdin=stdin)
    printed = (done.stdout or "").strip()
    url = next((l for l in printed.splitlines() if l.startswith("https://")), None)
    if url:
        out["url"] = url
    if done.returncode != 0:
        detail = (done.stderr or "").strip().splitlines()
        raise AccessError(f"gh {' '.join(argv[:2])} failed: {detail[-1] if detail else f'exit {done.returncode}'}"
                          + (" (it was made; some attachments may be missing)" if url else ""))
    return printed


# --- the pull request a change names --------------------------------------------------------------

def _ref(step: dict) -> str:
    return f"{step['repo']['repo']}#{step['pr_number']}"


def plan_pr(step, planned, open_only: bool = True) -> dict:
    c = step["change"]
    repo, number = access.parse_issue(c["pr"], planned.default_repo, allow_pr=True)
    step["repo"] = planned.repo(repo)
    # Not "number": a mandate reads that as an issue of its parent's tree, and a pull request is
    # never inside one.
    step["pr_number"] = number
    pr = reads.pull_request(step["repo"]["repo"], number, comments=0)
    if open_only and pr["state"] != "open":
        raise AccessError(f"{c['op']}: {_ref(step)} is {pr['state']}")
    step["pr"] = pr
    plan_attachments(step, planned, step["repo"])
    return pr


def _branch_exists(repo: str, branch: str) -> bool:
    owner, name = repo.split("/", 1)
    found = access.graphql(BRANCH_QUERY, {"owner": owner, "name": name, "ref": f"refs/heads/{branch}"})
    return bool((found.get("repository") or {}).get("ref"))


FORKS_QUERY = ("query($login:String!){repositoryOwner(login:$login){repositories(first:100,isFork:true,"
               "orderBy:{field:PUSHED_AT,direction:DESC}){nodes{nameWithOwner parent{nameWithOwner}}}}}")


def _fork_of(owner: str, repo: str) -> str:
    """``owner``'s fork of ``repo``, whatever it is named."""
    nodes = ((access.graphql(FORKS_QUERY, {"login": owner}).get("repositoryOwner") or {}).get("repositories") or {})
    found = next((n["nameWithOwner"] for n in nodes.get("nodes") or []
                  if access.same((n.get("parent") or {}).get("nameWithOwner"), repo)), None)
    if not found:
        raise AccessError(f"pr_create: {owner} has no fork of {repo}")
    return found


# --- pr_create ------------------------------------------------------------------------------------

def _pr_create_plan(step, planned):
    c = step["change"]
    repo = planned.repo_of(c)
    step["repo"] = repo
    settings = repo_reads.settings(repo["repo"])
    base = c.get("base") or settings["default_branch"]
    head = c["head"].strip()
    owner, _, branch = head.rpartition(":")
    source = _fork_of(owner, repo["repo"]) if owner and not access.same(owner, repo["owner"]) else repo["repo"]
    if not _branch_exists(source, branch):
        raise AccessError(f"pr_create: {source} has no branch {branch!r}; push it first")
    if not _branch_exists(repo["repo"], base):
        raise AccessError(f"pr_create: {repo['repo']} has no base branch {base!r}")
    if not owner and branch == base:
        raise AccessError("pr_create: head and base are the same branch")
    found = reads.pr_list({"repo": repo["repo"], "state": "open", "head": branch, "base": base, "limit": 5})
    if found["pull_requests"]:
        raise AccessError(f"pr_create: {repo['repo']}#{found['pull_requests'][0]['number']} is already open for {head}")
    step["base"], step["head"] = base, head
    plan_attachments(step, planned, repo)


def _pr_create_describe(step):
    c = step["change"]
    kind = "draft PR" if c.get("draft") else "PR"
    return (f"Open {kind} {step['head']} → {step['base']} in {step['repo']['repo']}: {say(c['title'], 60)}"
            + _uploads(step))


def _pr_create_run(step, out):
    c = step["change"]
    repo = step["repo"]["repo"]
    argv = ["pr", "create", "--repo", repo, "--base", step["base"], "--head", step["head"], "--title", c["title"],
            "--body-file", "-"]
    if c.get("draft"):
        argv.append("--draft")
    printed = _run_attaching(step, argv, c.get("body") or "", out)
    match = re.search(r"/pull/(\d+)", out.get("url") or printed)
    if match:
        out["pr"] = f"{repo}#{match.group(1)}"
    return out


# --- pr_edit, pr_comment --------------------------------------------------------------------------

EDIT_KEYS = ("title", "body", "base", "add_labels", "remove_labels", "add_assignees", "remove_assignees",
             "add_reviewers", "remove_reviewers", "milestone", "attachments")
EDIT_NOTIFIES = ("base", "add_labels", "remove_labels", "add_assignees", "remove_assignees", "add_reviewers",
                 "remove_reviewers", "milestone", "attachments")


def _pr_edit_check(change):
    if not any(changes.given(change, k) for k in EDIT_KEYS):
        raise AccessError("pr_edit: nothing to change")


def _pr_edit_class(change):
    if any(changes.given(change, k) for k in EDIT_NOTIFIES):
        return "create"
    if any(issue_ops.MENTION.search(change.get(k) or "") for k in ("title", "body")):
        return "create"
    return "routine"


def _pr_edit_plan(step, planned):
    c = step["change"]
    plan_pr(step, planned, open_only=False)
    if c.get("base") and not _branch_exists(step["repo"]["repo"], c["base"]):
        raise AccessError(f"pr_edit: {step['repo']['repo']} has no branch {c['base']!r}")


def _pr_edit_describe(step):
    c = step["change"]
    parts = []
    if c.get("title") is not None:
        parts.append(f"title → {say(c['title'], 50)}")
    if c.get("body") is not None:
        parts.append(f"body replaced ({len(c['body'])} chars)")
    if c.get("base"):
        parts.append(f"base {step['pr']['base']} → {c['base']}")
    for key in ("add_labels", "remove_labels", "add_assignees", "remove_assignees", "add_reviewers", "remove_reviewers"):
        if c.get(key):
            parts.append(f"{key.replace('_', ' ')} {', '.join(c[key])}")
    if c.get("milestone") is not None:
        parts.append("milestone removed" if c["milestone"] == "" else f"milestone {say(c['milestone'], 30)}")
    return f"Edit {_ref(step)}: " + "; ".join(parts) + _uploads(step)


def _pr_edit_run(step, out):
    c = step["change"]
    argv = ["pr", "edit", str(step["pr_number"]), "--repo", step["repo"]["repo"]]
    if c.get("title") is not None:
        argv += ["--title", c["title"]]
    stdin = None
    if c.get("body") is not None:
        argv += ["--body-file", "-"]
        stdin = c["body"]
    if c.get("base"):
        argv += ["--base", c["base"]]
    for key, flag in (("add_labels", "--add-label"), ("remove_labels", "--remove-label"),
                      ("add_assignees", "--add-assignee"), ("remove_assignees", "--remove-assignee"),
                      ("add_reviewers", "--add-reviewer"), ("remove_reviewers", "--remove-reviewer")):
        for value in c.get(key) or []:
            argv += [flag, value]
    if c.get("milestone") is not None:
        argv += ["--remove-milestone"] if c["milestone"] == "" else ["--milestone", c["milestone"]]
    out["pr"] = _ref(step)
    _run_attaching(step, argv, stdin, out)
    return out


def _pr_comment_plan(step, planned):
    plan_pr(step, planned, open_only=False)


def _pr_comment_run(step, out):
    out["pr"] = _ref(step)
    _run_attaching(step, ["pr", "comment", str(step["pr_number"]), "--repo", step["repo"]["repo"], "--body-file", "-"],
                   step["change"]["body"], out)
    return out


# --- pr_ready, pr_close, pr_reopen ----------------------------------------------------------------

def _pr_ready_plan(step, planned):
    pr = plan_pr(step, planned)
    if step["change"].get("undo") and pr["draft"]:
        raise AccessError(f"pr_ready: {_ref(step)} is already a draft")
    if not step["change"].get("undo") and not pr["draft"]:
        raise AccessError(f"pr_ready: {_ref(step)} is already ready for review")


def _pr_ready_run(step, out):
    argv = ["pr", "ready", str(step["pr_number"]), "--repo", step["repo"]["repo"]]
    gh([*argv, "--undo"] if step["change"].get("undo") else argv)
    return {**out, "pr": _ref(step), "draft": bool(step["change"].get("undo"))}


def _pr_reopen_plan(step, planned):
    pr = plan_pr(step, planned, open_only=False)
    if pr["state"] != "closed":
        raise AccessError(f"pr_reopen: {_ref(step)} is {pr['state']}")


def _pr_state_run(step, out):
    c = step["change"]
    verb = "close" if c["op"] == "pr_close" else "reopen"
    argv = ["pr", verb, str(step["pr_number"]), "--repo", step["repo"]["repo"]]
    if c.get("comment"):
        argv += ["--comment", c["comment"]]
    gh(argv)
    return {**out, "pr": _ref(step), "state": "closed" if verb == "close" else "open"}


# --- pr_merge -------------------------------------------------------------------------------------

def _pr_merge_plan(step, planned):
    c = step["change"]
    pr = plan_pr(step, planned)
    repo = step["repo"]
    if pr["draft"]:
        raise AccessError(f"pr_merge: {_ref(step)} is a draft; mark it ready first")
    if pr["merge_state"] == "dirty" or pr["mergeable"] == "conflicting":
        raise AccessError(f"pr_merge: {_ref(step)} conflicts with {pr['base']}; it needs a rebase or a merge of its base")
    merge = repo_reads.settings(repo["repo"])["merge"]
    allowed = [m for m in METHODS if merge[METHOD_SETTING[m]]]
    method = c.get("method")
    if method is None:
        if len(allowed) != 1:
            raise AccessError(f"pr_merge: method is required; {repo['repo']} allows {', '.join(allowed)}")
        method = allowed[0]
    elif method not in allowed:
        raise AccessError(f"pr_merge: {repo['repo']} does not allow {method} merges; it allows {', '.join(allowed)}")
    step["method"] = method
    below = _below(pr)
    if pr["stack"]:
        if c.get("delete_branch"):
            raise AccessError(f"pr_merge: {_ref(step)} is in a stack, whose merge deletes no branch itself; the "
                              "repository's setting for deleting a branch on merge decides")
        if len(pr["stack"]["layers"]) < pr["stack"]["size"]:
            raise AccessError(f"pr_merge: stack {pr['stack']['number']} has {pr['stack']['size']} layers and only "
                              f"{len(pr['stack']['layers'])} could be read; it is not merged unseen")
        for layer in below:
            if layer["repo"] and not access.same(layer["repo"], repo["repo"]):
                raise AccessError(f"pr_merge: #{layer['number']} below it in the stack is in {layer['repo']}, "
                                  f"not {repo['repo']}")
            if layer["draft"]:
                raise AccessError(f"pr_merge: #{layer['number']} below it in the stack is a draft; mark it ready first")
            if layer["mergeable"] == "conflicting":
                raise AccessError(f"pr_merge: #{layer['number']} below it in the stack has conflicts")
    step["below"] = below
    # What lands where, bound like a target: a push, a retargeted base, another method or a layer below
    # that moved, after the card, is a different merge. (The head is pinned at the write; the base has
    # no such pin, so the re-read just before the write is the check.)
    planned.note(f"head:{repo['repo'].lower()}#{step['pr_number']}",
                 {"kind": "head", "name": f"{_ref(step)} at {pr['head_sha'][:7]} into {pr['base']} by {method}",
                  "tier": repo["tier"], "id": f"{pr['head_sha']}:{pr['base']}:{method}"})
    # Each layer the merge also lands is a target of its own, on a line of its own: never cut from the card.
    for layer in below:
        planned.note(f"layer:{repo['repo'].lower()}#{layer['number']}",
                     {"kind": "layer", "name": f"#{layer['number']} at {(layer['head_sha'] or '')[:7]} "
                                               f"{layer['title']}", "tier": repo["tier"],
                      "id": f"{layer['number']}@{layer['head_sha']}"})


def _below(pr: dict) -> list[dict]:
    """The open layers under a pull request in its stack: a stack merge lands them with it."""
    if not pr["stack"]:
        return []
    return [layer for layer in pr["stack"]["layers"]
            if layer["position"] < pr["stack"]["position"] and layer["state"] == "open"]


def _merge_warnings(pr: dict) -> list[str]:
    ch, out = pr["checks"], []
    if ch["failing"]:
        out.append(f"{len(ch['failing'])} check{'s' if len(ch['failing']) > 1 else ''} failing"
                   + (f" ({ch['required_failing']} required)" if ch["required_failing"] else ""))
    if ch["pending"]:
        out.append(f"{len(ch['pending'])} pending")
    if ch["state"] == "none":
        out.append("no checks ran")
    if pr["review_decision"] == "changes_requested":
        out.append("changes requested")
    elif pr["review_decision"] == "review_required":
        out.append("review required")
    if pr["merge_state"] in ("blocked", "behind", "unstable", "unknown"):
        out.append(f"GitHub says {pr['merge_state']}")
    return out


def _pr_merge_describe(step):
    c, pr = step["change"], step["pr"]
    below = step.get("below") or []
    # The layers that merge with it come first: a long line is cut at its end.
    with_ = f" and the {len(below)} open layer{'s' if len(below) > 1 else ''} below it" if below else ""
    extra = [f"closes {', '.join(i['issue'] for i in pr['closes'])}" if pr["closes"] else "",
             "deletes its branch" if c.get("delete_branch") else ""]
    warn = _merge_warnings(pr)
    return (f"Merge {_ref(step)}{with_} into {pr['base']} by {step['method']} (head {pr['head_sha'][:7]})"
            + "".join(f"; {e}" for e in extra if e) + (f"; ⚠️ {', '.join(warn)}" if warn else ""))


def _pr_merge_run(step, out):
    c, pr = step["change"], step["pr"]
    # Read once more right before the merge: an earlier change of this list (a retargeted base) or a
    # push since the plan makes it a different merge. What remains is the moment between this read
    # and GitHub's merge, where gh pins the head and nothing pins the base.
    now = reads.pull_request(step["repo"]["repo"], step["pr_number"], comments=0)
    moved = [what for what, before, after in (("head", pr["head_sha"], now["head_sha"]), ("base", pr["base"], now["base"]),
                                             ("state", "open", now["state"]), ("draft", False, now["draft"]))
             if before != after]
    if bool(pr["stack"]) != bool(now["stack"]) or \
            [(x["number"], x["head_sha"]) for x in step.get("below") or []] != \
            [(x["number"], x["head_sha"]) for x in (_below(now) if now["stack"] else [])]:
        moved.append("the stack below it")
    if moved:
        raise AccessError(f"{_ref(step)} changed since the card ({', '.join(moved)}); it was not merged. Read it again "
                          "and send the merge again for a new card")
    if pr["stack"]:
        return _merge_stack(step, out)
    argv = ["pr", "merge", str(step["pr_number"]), "--repo", step["repo"]["repo"], f"--{step['method']}",
            "--match-head-commit", pr["head_sha"]]
    if c.get("delete_branch"):
        argv.append("--delete-branch")
    if c.get("subject"):
        argv += ["--subject", c["subject"]]
    stdin = None
    if c.get("body") is not None:
        argv += ["--body-file", "-"]
        stdin = c["body"]
    # Away from any checkout: gh also deletes a local branch, and switches branches, where it can.
    gh(argv, stdin=stdin, cwd=tempfile.gettempdir())
    out.update({"pr": _ref(step), "head": pr["head_sha"], "method": step["method"]})
    # Read back: a repository with a merge queue takes the pull request into the queue instead.
    try:
        state = reads.pull_request(step["repo"]["repo"], step["pr_number"], comments=0)["state"]
    except AccessError:
        state = "unknown"
    out["state"] = state
    if state != "merged":
        out["note"] = "gh accepted the merge but the pull request is not merged yet (a merge queue, or GitHub " \
                      "still working); read it again before reporting it merged"
    return out


# GitHub merges a pull request in a native stack only through its asynchronous merge route (gh's
# own merge refuses one): it lands the open layers below in the same request.
API_VERSION = "2026-03-10"
POLL_EVERY = 3
POLL_FOR = 120


def _async(argv: list[str], stdin: str | None = None) -> dict:
    """One call of the asynchronous merge route. A 409 means a merge of this pull request is already
    running (a request sent earlier, perhaps one whose answer never came): its answer names that
    request, which is then followed instead of failing or sending another."""
    done = access.run_gh(["api", *argv, "-H", f"X-GitHub-Api-Version: {API_VERSION}"], stdin=stdin)
    try:
        answer = json.loads(done.stdout or "{}")
    except json.JSONDecodeError:
        answer = {}
    if done.returncode == 0:
        return answer
    detail = (done.stderr or "").strip().splitlines()
    detail = detail[-1] if detail else f"exit {done.returncode}"
    if "409" in detail and ((answer.get("details") or {}).get("uuid") or answer.get("uuid")):
        return {"status": "pending", "details": answer.get("details") or answer, "already": True}
    raise AccessError(f"gh api {argv[-1] if argv[0] != '--method' else argv[2]} failed: {detail}"[:400])


def _merge_stack(step, out):
    c, pr = step["change"], step["pr"]
    repo, number = step["repo"]["repo"], step["pr_number"]
    route = f"repos/{repo}/pulls/{number}/merge-async"
    body = {"merge_method": step["method"], "sha": pr["head_sha"]}
    if c.get("subject"):
        body["commit_title"] = c["subject"]
    if c.get("body") is not None:
        body["commit_message"] = c["body"]
    below = [layer["number"] for layer in step.get("below") or []]
    out.update({"pr": _ref(step), "head": pr["head_sha"], "method": step["method"], "with": [f"#{n}" for n in below]})
    answer = _async(["--method", "PUT", route, "--input", "-"], json.dumps(body))
    status, details = answer.get("status"), answer.get("details") or {}
    out["request"] = details.get("uuid")
    if answer.get("already"):
        out["already_running"] = True  # followed, not sent again
    deadline = time.monotonic() + POLL_FOR
    while status == "pending" and details.get("uuid") and time.monotonic() < deadline:
        time.sleep(POLL_EVERY)
        try:
            answer = _async([f"{route}/{details['uuid']}"])
        except AccessError as exc:
            if "404" in str(exc) or "Not Found" in str(exc):
                break  # a finished request can be gone at once: the read-back below says what landed
            raise
        status, details = answer.get("status"), answer.get("details") or details
    out["async"] = status
    # Read every layer back: a stack merge that fails part-way can leave the lower layers merged.
    states = {}
    for n in [*below, number]:
        try:
            states[n] = reads.pull_request(repo, n, comments=0)["state"]
        except AccessError:
            states[n] = "unknown"
    out["states"] = {f"#{n}": s for n, s in states.items()}
    out["state"] = states[number]
    if status == "failed":
        landed = [f"#{n}" for n, s in states.items() if s == "merged"]
        raise AccessError(f"GitHub did not merge {_ref(step)}: {details.get('message') or 'no reason given'}"
                          + (f" (already merged: {', '.join(landed)})" if landed else ""))
    if states[number] != "merged":
        out["note"] = {"enqueued": "the stack went into the merge queue; it is not merged yet",
                       "pending": "GitHub is still merging; read it again before reporting it merged"}.get(
            status, "GitHub accepted the merge but the pull request is not merged yet; read it again before "
                    "reporting it merged")
    return out


def _pr_merge_check(change):
    if change.get("body") is not None and not change.get("subject"):
        raise AccessError("pr_merge: a merge commit body goes with its subject")


for _op in (
        Op("pr_create", "create",
           "repo, head (the pushed branch, or owner:branch from a fork), base (default: the default branch), title, "
           "body, draft, attachments {absolute path: alt text}: a pull request; reference an attachment in the body "
           "as ![alt](<the same path>) and it is uploaded there, else appended",
           _pr_create_plan, _pr_create_describe, _pr_create_run, required=("head", "title"),
           optional=("repo", "base", "body", "draft", "attachments")),
        Op("pr_edit", "routine",
           "pr, title, body, base, add_/remove_labels, add_/remove_assignees, add_/remove_reviewers, milestone "
           "(\"\" removes), attachments (appended to the body unless it references them)",
           _pr_edit_plan, _pr_edit_describe, _pr_edit_run, required=("pr",), optional=("repo", *EDIT_KEYS),
           check=_pr_edit_check, classify=_pr_edit_class),
        Op("pr_comment", "create", "pr, body, attachments", _pr_comment_plan,
           lambda s: f"Comment on {_ref(s)}: {say(s['change']['body'], 80)}" + _uploads(s), _pr_comment_run,
           required=("pr", "body"), optional=("repo", "attachments")),
        Op("pr_ready", "create", "pr, undo: ready for review (undo: back to draft)", _pr_ready_plan,
           lambda s: f"{'Turn' if s['change'].get('undo') else 'Mark'} {_ref(s)} "
                     f"{'back into a draft' if s['change'].get('undo') else 'ready for review'}",
           _pr_ready_run, required=("pr",), optional=("repo", "undo")),
        Op("pr_close", "create", "pr, comment: close without merging", lambda s, p: plan_pr(s, p),
           lambda s: f"Close {_ref(s)} unmerged" + (f", saying: {say(s['change']['comment'], 70)}"
                                                   if s["change"].get("comment") else ""),
           _pr_state_run, required=("pr",), optional=("repo", "comment")),
        Op("pr_reopen", "create", "pr", _pr_reopen_plan, lambda s: f"Reopen {_ref(s)}", _pr_state_run,
           required=("pr",), optional=("repo",)),
        Op("pr_merge", "admin",
           "pr, method merge|squash|rebase (required when the repository allows more than one), delete_branch, "
           "subject and body of the merge commit: pinned to the head commit the card shows",
           _pr_merge_plan, _pr_merge_describe, _pr_merge_run, required=("pr",),
           optional=("repo", "method", "delete_branch", "subject", "body"), check=_pr_merge_check)):
    changes.register(_op)
