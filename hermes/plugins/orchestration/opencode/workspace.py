"""Give an idle session a task-branch worktree of its own repository, and take it back.

A plan runs read-only on the default checkout. Once the Client approves, the
session moves into a fresh worktree on a new branch, so the build continues the
same conversation where it may edit. Once that work has landed or been
abandoned, `cleanup` moves the caller's sessions back to the main checkout and removes
the worktree, and its branch once it has landed. The worktree itself is made and removed
by the git-tools command line (the package whose layout and landed-branch proof
OpenCode's own worktree strategy shares), started with a minimal environment, never the
gateway's: the package passes git an allowlisted environment, so a repository's hooks
(which run on fetch, removal and branch deletion as they would for the person's own
command, and already in the run's commits) never see the gateway's secrets. Session
binding, the move, the commit identity and the rollback stay here: a session can also
move itself (`session_move` asks no permission), so the repository the session may work
in is fixed here and checked on every turn (see `__init__._prepare`).
"""

from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess

BRANCH = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,99}\Z")
BASES = ("default", "head")
FETCH_TIMEOUT = 60
# The command line fetches, then removes or reads GitHub; its own limits sit inside this one.
CLI_TIMEOUT = FETCH_TIMEOUT + 60
SESSION_PAGES = 5
# What locating git, its config and an ssh agent for a fetch needs; nothing else passes.
ENV_NAMES = {"PATH", "HOME", "USER", "LOGNAME", "SHELL", "LANG", "TERM", "TMPDIR", "TZ", "SSH_AUTH_SOCK"}
ENV_PREFIXES = ("LC_", "XDG_")
# Where gh keeps its login, when the person moved it; a path, not a secret.
GH_ENV_NAMES = ("GH_CONFIG_DIR",)
SAFE_GIT = ("-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false")
# The git-tools plugin as `scripts/external-plugins.py` installs it: <hermes home>/plugins/<name>/dist/cli.js.
GIT_TOOLS_PLUGIN = "git-tools"
GIT_TOOLS_CLI = Path("dist") / "cli.js"
GIT_TOOLS_TOOLSET = "worktree"
NOT_INSTALLED = "the git-tools plugin is not installed (run scripts/external-plugins.py install)"
KEPT_BECAUSE = {
    "not_landed": "its work has not landed on the default branch (no merged pull request from it has its tip as "
                  "head, and it is not in the remote default branch)",
    "checked_out": "it is checked out in another worktree",
    "default_branch": "it is the default branch",
    "delete_failed": "git could not delete it",
}


def git_env():
    env = {k: v for k, v in os.environ.items() if k in ENV_NAMES or k.startswith(ENV_PREFIXES)}
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def gh_env():
    """git_env() plus the settings gh locates its login by: where its config lives, and no prompts."""
    env = git_env()
    env.update({name: os.environ[name] for name in GH_ENV_NAMES if name in os.environ})
    env.update(GH_PROMPT_DISABLED="1", GH_NO_UPDATE_NOTIFIER="1")
    return env


def _node():
    """Hermes' own node when it has installed one, else the one on the minimal PATH."""
    try:
        from hermes_constants import find_node_executable
        found = find_node_executable("node")
    except Exception:
        found = None
    return found or shutil.which("node", path=gh_env().get("PATH"))


def _plugin_homes():
    homes = []
    try:
        from hermes_constants import get_default_hermes_root, get_hermes_home
        homes += [get_hermes_home(), get_default_hermes_root()]
    except Exception:
        pass
    return [*homes, Path("~/.hermes").expanduser()]


def default_cli():
    """`[node, <hermes home>/plugins/git-tools/dist/cli.js]`, looked for now: a profile's own home first, then
    the root's. Raises ValueError when node or the installed plugin is missing."""
    node = _node()
    if not node:
        raise ValueError("git-tools needs node, which was not found; install Node.js 24 or later")
    for home in _plugin_homes():
        cli = Path(home) / "plugins" / GIT_TOOLS_PLUGIN / GIT_TOOLS_CLI
        if cli.is_file():
            return [node, str(cli)]
    raise ValueError(NOT_INSTALLED)


def _stop(process):
    """End the command line and whatever it started, which share its process group."""
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(process.pid, signal.SIGKILL)
    process.communicate()


def git_tools(tool_id, args, cwd, settings):
    """The `result` of one git-tools tool, run through its command line in `cwd` with the arguments as JSON
    on stdin and `opencode.worktree_root` as its worktree root. The command line runs with gh_env() alone:
    it hands git an allowlisted environment of its own, so nothing else of the gateway's reaches a hook.
    Raises ValueError with the tool's code and message when it fails."""
    command = settings.get("git_tools_cli") or default_cli()
    argv = [*command, "run", tool_id, "--cwd", str(cwd), "--toolsets", GIT_TOOLS_TOOLSET,
            "--worktree-root", settings["worktree_root"]]
    try:
        process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, env=gh_env(), start_new_session=True)
    except FileNotFoundError:
        raise ValueError(NOT_INSTALLED) from None
    except OSError as exc:
        raise ValueError(f"git-tools could not run: {exc.strerror or exc}") from None
    try:
        stdout, stderr = process.communicate(json.dumps(args), timeout=CLI_TIMEOUT)
    except subprocess.TimeoutExpired:
        _stop(process)
        raise ValueError(f"git-tools {tool_id} did not finish within {CLI_TIMEOUT}s") from None
    except BaseException:
        _stop(process)
        raise
    try:
        body = json.loads(stdout)
    except ValueError:
        body = None
    if process.returncode or not isinstance(body, dict) or "result" not in body:
        error = body.get("error") if isinstance(body, dict) else None
        if isinstance(error, dict):
            detail = f"{error.get('code')}: {error.get('message')}"
        else:
            detail = (stderr or stdout).strip() or f"exit {process.returncode}"
        raise ValueError(f"git-tools {tool_id} failed: {detail[:200]}")
    if not isinstance(body["result"], dict):
        raise ValueError(f"git-tools {tool_id} answered with no result")
    return body["result"]


def _run(directory, *args, timeout=30):
    proc = subprocess.run(["git", *SAFE_GIT, "-C", str(directory), *args], capture_output=True, text=True,
                          timeout=timeout, env=git_env())
    if proc.returncode:
        raise ValueError("git " + " ".join(args[:2]) + " failed: " + (proc.stderr.strip() or "no output")[:200])
    return proc.stdout.strip()


def default_branch(meta, issue_ref):
    """`task/issue-<N>` for a session bound to an issue, else nothing: the branch is then
    the caller's to name. The stored issue is service metadata, checked like a new one."""
    if meta.get("issue") is None:
        return None
    issue = issue_ref(meta["issue"])
    if not issue:
        raise ValueError("The session's stored issue is not owner/repo#N; start the next turn with issue= to rebind it")
    return "task/issue-" + issue.rsplit("#", 1)[1]


def branch_name(value, source, policy):
    """A new, safe task-branch name: not protected, not the default branch, not existing."""
    if value is None:
        raise ValueError("branch is required for a session bound to no issue: a plain git branch name such as "
                         "task/short-name")
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


def commit_identity():
    """The gateway's own commit name and email, or None when it has none.

    The shared OpenCode service runs with its starter's environment, never the
    gateway's, so a run's commits would otherwise carry the person's identity."""
    for role in ("AUTHOR", "COMMITTER"):
        name, email = os.environ.get(f"GIT_{role}_NAME"), os.environ.get(f"GIT_{role}_EMAIL")
        if name and email:
            return name, email
    return None


def set_identity(source, target, identity):
    """Pin the identity in the new worktree's own config, leaving every other checkout as it was."""
    _run(source, "config", "--local", "extensions.worktreeConfig", "true")
    _run(target, "config", "--worktree", "user.name", identity[0])
    _run(target, "config", "--worktree", "user.email", identity[1])


def create(*, sid, info, meta, args, settings, policy, turn, issue_ref):
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
    branch = branch_name(args["branch"] if "branch" in args else default_branch(meta, issue_ref), source, policy)
    if base == "default" and "origin" not in _run(source, "remote").splitlines():
        raise ValueError("there is no remote to start from; pass base=head to start from the current commit")
    root = Path(settings["worktree_root"]).resolve()
    # The command line lays the worktree out under the root, cuts the branch (fetching origin first) and
    # checks it out without hooks; it refuses a directory or a branch that already exists.
    added = git_tools("git_worktree_add", {"branch": branch, **({"from": "HEAD"} if base == "head" else {})},
                      source, settings)
    if not isinstance(added.get("directory"), str):
        raise ValueError("git-tools did not say where the worktree is")
    target = Path(added["directory"])
    try:
        if not added.get("new_branch"):
            raise ValueError(f"branch {branch} already exists; choose a new name")
        identity = commit_identity()
        if identity:
            set_identity(source, target, identity)
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
        with contextlib.suppress(Exception):
            turn.call("post", "/api/session/{sid}/move", {"directory": source}, sid=sid)
        with contextlib.suppress(Exception):
            _run(source, "worktree", "remove", "--force", str(target))
        if added.get("new_branch"):
            with contextlib.suppress(Exception):
                _run(source, "branch", "-D", branch)
        raise
    result = {"session_id": sid, "directory": str(target), "branch": branch,
              "base": (added.get("base") or {}).get("ref"), "moved_from": source,
              **({"issue": meta["issue"]} if meta.get("issue") else {})}
    if identity:
        result["commit_identity"] = f"{identity[0]} <{identity[1]}>"
    if added.get("warnings"):
        result["warning"] = "; ".join(map(str, added["warnings"]))
    return result


def _worktrees(source):
    """Every worktree of the repository as {path, branch, bare, locked}, its main checkout first. `locked` is
    None, or the lock's reason (empty when it has none)."""
    found = []
    for block in _run(source, "worktree", "list", "--porcelain").split("\n\n"):
        lines = block.splitlines()
        if lines and lines[0].startswith("worktree "):
            branch = next((line[len("branch refs/heads/"):] for line in lines if line.startswith("branch refs/heads/")),
                          None)
            lock = next((line[len("locked"):].strip() for line in lines if line == "locked" or line.startswith("locked ")),
                        None)
            found.append({"path": lines[0][len("worktree "):], "branch": branch, "bare": "bare" in lines,
                          "locked": lock})
    return found


def _sessions_in(directory, policy, turn):
    """The sessions the service files under this worktree, from any profile or person."""
    found, cursor = [], None
    for _ in range(SESSION_PAGES):
        page = turn.call("get", "/api/session",
                         query={"limit": 200, "order": "desc", "directory": directory, "cursor": cursor})
        found += [item for item in turn.api.data(page, list) if policy.same_dir(turn.directory_of(item), directory)]
        cursor = (page.get("cursor") or {}).get("next") if isinstance(page, dict) else None
        if not cursor:
            return found
    raise ValueError("too many sessions in this worktree to move them all back")


def _checked(meta, worktree, policy):
    """The worktree's branch and the branches never to delete, once the session's binding holds."""
    repo = policy.common_dir(worktree)
    if not meta.get("repo"):
        raise ValueError("This session was bound before repository binding; start a new session")
    if meta["repo"] != repo:
        raise ValueError("The session is no longer in the repository it was bound to; start a new session")
    branch, protected = policy.branch(worktree, False)
    if meta.get("branch") != branch:
        raise ValueError("Worktree branch changed; start a new session after inspection")
    if branch.startswith("detached:"):
        raise ValueError("The worktree is on a detached HEAD, not a task branch")
    return branch, protected


def cleanup(*, sid, info, meta, owner, settings, policy, turn):
    """Move the caller's sessions in the worktree back to the main checkout and remove the worktree through
    git-tools, never forced: it goes only when it is clean, in no operation and holds no commit that no ref
    holds. Its branch is deleted only once it has landed (in the remote default branch, or as the head of a
    merged pull request of this repository) and kept, with the reason, otherwise. Refuses, moving and removing
    nothing, while a session runs, the binding or the worktree is not as `workspace` left it, or it has changes."""
    if sid in turn.active():
        raise ValueError("Clean up a session's worktree when it is idle, not while it runs")
    worktree = policy.worktree(turn.directory_of(info))
    running = turn.running_in(worktree, policy.same_dir)
    if running:
        raise ValueError("A session is running in this worktree (" + ", ".join(running) + "); wait for it to stop")
    branch, protected = _checked(meta, worktree, policy)
    entries = _worktrees(worktree)
    if not entries or entries[0]["bare"]:
        raise ValueError("The repository has no main checkout to move the sessions back to")
    main = str(Path(entries[0]["path"]).resolve())
    if policy.same_dir(worktree, main):
        raise ValueError("The session is in the repository's main checkout, not in a task worktree")
    locked = next((e["locked"] for e in entries if policy.same_dir(e["path"], worktree)), None)
    if locked is not None:
        raise ValueError("The worktree is locked" + (f": {locked}" if locked else "") + "; unlock it first")
    root = Path(settings["worktree_root"]).resolve()
    if root not in Path(worktree).parents:
        raise ValueError("The session's worktree lies outside opencode.worktree_root; it was not made by workspace")
    changed = _run(worktree, "status", "--porcelain", "--untracked-files=normal").splitlines()
    if changed:
        raise ValueError(f"The worktree has {len(changed)} changed path(s); commit or discard them first")
    default = policy.default_ref(main)
    protected = {*protected, *policy.PROTECTED_BRANCHES, *([default.removeprefix("origin/")] if default else [])}
    if branch in protected:
        raise ValueError(f"{branch} is a protected or default branch; its worktree is not cleaned up here")

    sessions = _sessions_in(worktree, policy, turn)
    if sid not in [item.get("id") for item in sessions]:
        sessions.append(info)
    mine = [item for item in sessions if turn.hermes_meta(item).get("owner") == owner]
    target = policy.branch(main, False)[0]
    moved = []

    def put_back():
        # Best effort: a move may have landed, so no session is left bound to the wrong place.
        for item in reversed(moved):
            with contextlib.suppress(Exception):
                turn.call("post", "/api/session/{sid}/move", {"directory": worktree}, sid=item["id"])
            with contextlib.suppress(Exception):
                turn.call("patch", "/api/session/{sid}", {"metadata": item.get("metadata") or {}}, sid=item["id"])

    try:
        for item in mine:
            # Listed before the call: a move that raised may still have landed.
            moved.append(item)
            turn.call("post", "/api/session/{sid}/move", {"directory": main}, sid=item["id"])
            now = turn.session_info(item["id"])
            if not policy.same_dir(turn.directory_of(now), main):
                raise ValueError("OpenCode did not move the session to the main checkout")
            turn.call("patch", "/api/session/{sid}", {
                "metadata": {**(now.get("metadata") or {}), "hermes": {**turn.hermes_meta(now), "branch": target}}},
                sid=item["id"])
    except Exception:
        put_back()
        raise

    try:
        removed = git_tools("git_worktree_remove", {"directory": worktree}, main, settings)
    except ValueError as exc:
        put_back()
        raise ValueError(f"{exc}; nothing was removed and the sessions are back in the worktree, so cleanup can be "
                         "retried") from None

    deleted = [branch] if removed.get("branch_deleted") is True else []
    code = removed.get("kept_because")
    kept = [] if deleted else [{"branch": branch, "reason": KEPT_BECAUSE.get(code, code) or "it was not deleted"}]
    result = {"session_id": sid, "removed": worktree, "moved_to": main, "moved_sessions": [i["id"] for i in moved],
              "left_behind": len(sessions) - len(mine), "branches_deleted": deleted, "branches_kept": kept}
    if removed.get("warnings"):
        result["warning"] = "; ".join(map(str, removed["warnings"]))
    return result
