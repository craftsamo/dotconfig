"""Give an idle session a task-branch worktree of its own repository.

A plan runs read-only on the default checkout. Once the Client approves, the
session moves into a fresh worktree on a new branch, so the build continues the
same conversation where it may edit. The plugin does this itself, in plain Git
and the service's `move` route: a session can also move itself (`session_move`
asks no permission), so the repository the session may work in is fixed here and
checked on every turn (see `__init__._prepare`).

Git runs with a minimal environment and without hooks: the repository's own
hooks (a tracked `core.hooksPath`, say) are code its commits can change, and
this process holds the gateway's secrets.
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path
import re
import subprocess

BRANCH = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,99}\Z")
BASES = ("default", "head")
FETCH_TIMEOUT = 60
# What locating git, its config and an ssh agent for a fetch needs; nothing else passes.
ENV_NAMES = {"PATH", "HOME", "USER", "LOGNAME", "SHELL", "LANG", "TERM", "TMPDIR", "TZ", "SSH_AUTH_SOCK"}
ENV_PREFIXES = ("LC_", "XDG_")
SAFE_GIT = ("-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false")


def git_env():
    env = {k: v for k, v in os.environ.items() if k in ENV_NAMES or k.startswith(ENV_PREFIXES)}
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def _run(directory, *args, timeout=30):
    proc = subprocess.run(["git", *SAFE_GIT, "-C", str(directory), *args], capture_output=True, text=True,
                          timeout=timeout, env=git_env())
    if proc.returncode:
        raise ValueError("git " + " ".join(args[:2]) + " failed: " + (proc.stderr.strip() or "no output")[:200])
    return proc.stdout.strip()


def branch_name(value, source, policy):
    """A new, safe task-branch name: not protected, not the default branch, not existing."""
    if not isinstance(value, str) or not BRANCH.fullmatch(value) or ".." in value or value.endswith((".lock", "/", ".")):
        raise ValueError("branch must be a plain git branch name such as task/short-name")
    _run(source, "check-ref-format", "--branch", value)
    if value in policy.PROTECTED_BRANCHES:
        raise ValueError(f"{value} is a protected branch; choose a task branch name")
    default = policy.default_ref(source)
    if default and value == default.removeprefix("origin/"):
        raise ValueError(f"{value} is the default branch; choose a task branch name")
    exists = subprocess.run(["git", "-C", source, "show-ref", "--verify", "--quiet", "refs/heads/" + value],
                            env=git_env())
    if not exists.returncode:
        raise ValueError(f"branch {value} already exists; choose a new name")
    return value


def target_path(root, repo, branch):
    """<root>/<main checkout's directory name>/<branch with / as ->."""
    return Path(root) / Path(repo).parent.name / branch.replace("/", "-")


def _start(source, base, policy):
    """The commit the branch starts from, and whether a fetch succeeded."""
    if base == "head":
        return "HEAD", None
    if "origin" not in _run(source, "remote").splitlines():
        raise ValueError("there is no remote to start from; pass base=head to start from the current commit")
    fetched = True
    try:
        _run(source, "fetch", "--quiet", "origin", timeout=FETCH_TIMEOUT)
    except Exception:
        fetched = False
    ref = policy.default_ref(source)
    if not ref:
        raise ValueError("the remote default branch is unknown here; pass base=head to start from the current commit")
    return ref, fetched


def create(*, sid, info, meta, args, settings, policy, turn):
    """Create the worktree, move the idle session into it and rebind it. Returns the new place."""
    if sid in turn.active():
        raise ValueError("Move a session when it is idle, not while it runs")
    base = args.get("base", "default")
    if base not in BASES:
        raise ValueError("base must be default (the fetched remote default branch) or head (the current commit)")
    source = policy.worktree(turn.directory_of(info))
    repo = policy.common_dir(source)
    # The same binding every run is held to: a session that was moved elsewhere is not re-bound here.
    if not meta.get("repo"):
        raise ValueError("This session was bound before repository binding; start a new session")
    if meta["repo"] != repo:
        raise ValueError("The session is no longer in the repository it was bound to; start a new session")
    if meta.get("branch") != policy.branch(source, False)[0]:
        raise ValueError("Worktree branch changed; start a new session after inspection")
    branch = branch_name(args.get("branch"), source, policy)
    root = Path(settings["worktree_root"]).resolve()
    target = target_path(root, repo, branch)
    if target.exists():
        raise ValueError(f"{target} already exists")
    start, fetched = _start(source, base, policy)
    target.parent.mkdir(parents=True, exist_ok=True)
    created = False
    try:
        _run(source, "worktree", "add", "--no-track", "-b", branch, str(target), start)
        created = True
        # The service must be given the real path: moved to a symlinked spelling
        # (/var for /private/var) it files the worktree outside its project, and
        # snapshots and diffs stop working (measured on 2.0.23).
        target = target.resolve(strict=True)
        if root not in target.parents:
            raise ValueError("the new worktree would lie outside opencode.worktree_root")
        policy.worktree(str(target))
        turn.call("post", "/api/session/{sid}/move", {"directory": str(target)}, sid=sid)
        moved = turn.session_info(sid)
        if not policy.same_dir(turn.directory_of(moved), str(target)):
            raise ValueError("OpenCode did not move the session to the new worktree")
        label = Path(meta["output_dir"]).name if meta.get("output_dir") else Path(repo).parent.name
        turn.call("patch", "/api/session/{sid}", {
            "title": f"{label} · {branch}",
            "metadata": {**(moved.get("metadata") or {}), "hermes": {**meta, "branch": branch, "repo": repo}}},
            sid=sid)
    except Exception:
        # Best effort: the move may have landed, so the session is not left half-bound.
        if created:
            with contextlib.suppress(Exception):
                turn.call("post", "/api/session/{sid}/move", {"directory": source}, sid=sid)
            with contextlib.suppress(Exception):
                _run(source, "worktree", "remove", "--force", str(target))
            with contextlib.suppress(Exception):
                _run(source, "branch", "-D", branch)
        raise
    result = {"session_id": sid, "directory": str(target), "branch": branch, "base": start, "moved_from": source}
    if fetched is False:
        result["warning"] = f"fetching origin failed: {start} is as of the last fetch"
    return result
