"""Give an idle session a task-branch worktree of its own repository, and take it back.

A plan runs read-only on the default checkout. Once the Client approves, the
session moves into a fresh worktree on a new branch, so the build continues the
same conversation where it may edit. Once that work has landed on the default
branch, `cleanup` moves the caller's sessions back to the main checkout and removes
the worktree and the task branches that landed. The plugin does this itself, in plain
Git and the service's `move` route: a session can also move itself (`session_move`
asks no permission), so the repository the session may work in is fixed here and
checked on every turn (see `__init__._prepare`).

Git runs with a minimal environment and without hooks: the repository's own
hooks (a tracked `core.hooksPath`, say) are code its commits can change, and
this process holds the gateway's secrets.
"""

from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path
import re
import subprocess

BRANCH = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,99}\Z")
BASES = ("default", "head")
FETCH_TIMEOUT = 60
GH_TIMEOUT = 40
GITHUB_ORIGIN = re.compile(r"(?:https?://(?:[^@/]+@)?|ssh://git@|git@)github\.com[:/]([\w.-]+)/([\w.-]+?)(?:\.git)?/?\Z",
                           re.I)
SESSION_PAGES = 5
MERGED_QUERY = (
    "query($owner:String!,$name:String!,$branch:String!){repository(owner:$owner,name:$name){"
    "pullRequests(headRefName:$branch,states:MERGED,first:20){nodes{number headRefName headRefOid "
    "isCrossRepository stack{number size baseRefName entries(first:100){nodes{position pullRequest{number state "
    "headRefOid headRefName headRepository{nameWithOwner} repository{nameWithOwner}}}}} stackEntry{position}}}}}")
# What locating git, its config and an ssh agent for a fetch needs; nothing else passes.
ENV_NAMES = {"PATH", "HOME", "USER", "LOGNAME", "SHELL", "LANG", "TERM", "TMPDIR", "TZ", "SSH_AUTH_SOCK"}
ENV_PREFIXES = ("LC_", "XDG_")
# Where gh keeps its login, when the person moved it; a path, not a secret.
GH_ENV_NAMES = ("GH_CONFIG_DIR",)
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


def repository_name(source, repo):
    """The repository's name on its origin remote (dotconfig for the live checkout), else its
    main checkout's directory name. OpenCode's worktree strategy
    (opencode/lib/worktrees/strategy.ts) names it the same way."""
    proc = subprocess.run(["git", *SAFE_GIT, "-C", str(source), "remote", "get-url", "origin"], capture_output=True,
                          text=True, timeout=30, env=git_env())
    url = proc.stdout.strip().rstrip("/") if proc.returncode == 0 else ""
    name = re.split(r"[/:]", url)[-1].removesuffix(".git") if url else ""
    return name or Path(repo).parent.name


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


def target_path(root, name, branch):
    """<root>/<repository name>/<branch with / as ->."""
    return Path(root) / name / branch.replace("/", "-")


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
    root = Path(settings["worktree_root"]).resolve()
    target = target_path(root, repository_name(source, repo), branch)
    if target.exists():
        raise ValueError(f"{target} already exists")
    start, fetched = _start(source, base, policy)
    target.parent.mkdir(parents=True, exist_ok=True)
    created = False
    try:
        _run(source, "worktree", "add", "--no-track", "-b", branch, str(target), start)
        created = True
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
        if created:
            with contextlib.suppress(Exception):
                turn.call("post", "/api/session/{sid}/move", {"directory": source}, sid=sid)
            with contextlib.suppress(Exception):
                _run(source, "worktree", "remove", "--force", str(target))
            with contextlib.suppress(Exception):
                _run(source, "branch", "-D", branch)
        raise
    result = {"session_id": sid, "directory": str(target), "branch": branch, "base": start, "moved_from": source,
              **({"issue": meta["issue"]} if meta.get("issue") else {})}
    if identity:
        result["commit_identity"] = f"{identity[0]} <{identity[1]}>"
    if fetched is False:
        result["warning"] = f"fetching origin failed: {start} is as of the last fetch"
    return result


def gh_env():
    """git_env() plus the settings gh locates its login by: where its config lives, and no prompts."""
    env = git_env()
    env.update({name: os.environ[name] for name in GH_ENV_NAMES if name in os.environ})
    env.update(GH_PROMPT_DISABLED="1", GH_NO_UPDATE_NOTIFIER="1")
    return env


def graphql(query, variables):
    """`data` of one GraphQL request through the user's own `gh` login, the variables typed as sent on stdin.
    GitHub answers a name that does not exist with null at its path and a NOT_FOUND error: that `data` is
    returned, so the caller says what is missing. Any other error raises with GitHub's messages."""
    try:
        proc = subprocess.run(["gh", "api", "graphql", "--input", "-"], input=json.dumps(
            {"query": query, "variables": variables}), capture_output=True, text=True, timeout=GH_TIMEOUT,
            env=gh_env())
    except subprocess.TimeoutExpired:
        raise ValueError(f"gh did not answer within {GH_TIMEOUT}s") from None
    except OSError as exc:
        raise ValueError(f"gh could not run: {exc.strerror or exc}") from None
    try:
        body = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        body = {}
    if not isinstance(body, dict):
        body = {}
    errors = [e for e in body.get("errors") or [] if isinstance(e, dict)]
    if errors and "data" in body and all(e.get("type") == "NOT_FOUND" for e in errors):
        return body["data"] or {}
    if errors or proc.returncode or "data" not in body:
        detail = "; ".join(str(e.get("message", e)) for e in errors) or \
            (proc.stderr or proc.stdout or "").strip()[-200:] or f"exit {proc.returncode}"
        raise ValueError(f"GitHub refused the request: {detail}"[:200])
    return body["data"] or {}


def stack(pull):
    """The native stack a pull request is in (None when it is in none): its number, base, this
    pull request's position (1 sits on the base) and every layer, bottom first."""
    found, entry = pull.get("stack"), pull.get("stackEntry")
    if not found or not entry:
        return None
    layers = sorted(({"position": e["position"], "number": e["pullRequest"]["number"],
                      "title": e["pullRequest"].get("title") or "", "state": e["pullRequest"]["state"].lower(),
                      "draft": bool(e["pullRequest"].get("isDraft")), "head_sha": e["pullRequest"].get("headRefOid"),
                      "mergeable": (e["pullRequest"].get("mergeable") or "").lower(),
                      "repo": (e["pullRequest"].get("repository") or {}).get("nameWithOwner"),
                      "head": e["pullRequest"].get("headRefName"),
                      "head_repo": (e["pullRequest"].get("headRepository") or {}).get("nameWithOwner")}
                     for e in (found.get("entries") or {}).get("nodes") or [] if e and e.get("pullRequest")),
                    key=lambda layer: layer["position"])
    return {"number": found["number"], "size": found["size"], "base": found["baseRefName"],
            "position": entry["position"], "layers": layers}


def merged_pulls(source, branch):
    """The merged pull requests of origin's GitHub repository whose head branch is `branch`, read with
    `gh`: number, head commit, whether from a fork, and native stack. Empty without a GitHub origin.
    Raises when GitHub cannot be read."""
    try:
        match = GITHUB_ORIGIN.fullmatch(_run(source, "remote", "get-url", "origin"))
    except ValueError:
        return []
    if not match:
        return []
    # The repository's own pull request connection, not `search`: its index trails a fresh merge.
    data = graphql(MERGED_QUERY, {"owner": match.group(1), "name": match.group(2), "branch": branch})
    if not data.get("repository"):
        raise ValueError(f"{match.group(1)}/{match.group(2)} not found or not visible to the viewer")
    nodes = (data["repository"].get("pullRequests") or {}).get("nodes") or []
    return [{"number": node["number"], "head_sha": node["headRefOid"], "fork": bool(node.get("isCrossRepository")),
             "stack": stack(node)} for node in nodes if node and node.get("headRefName") == branch]


def _succeeds(source, *args):
    try:
        _run(source, *args)
    except ValueError:
        return False
    return True


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


def _on_default(source, tip, default):
    return bool(default) and _succeeds(source, "merge-base", "--is-ancestor", tip, default)


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
    """Once the worktree's branch has landed on the default branch, move the caller's sessions in it back to
    the main checkout, remove the worktree and delete the task branches that landed. Refuses, moving and
    removing nothing, when the work has not landed or the worktree holds anything that is not safely gone."""
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

    warnings = []
    if "origin" in _run(main, "remote").splitlines():
        try:
            _run(main, "fetch", "--quiet", "--prune", "origin", timeout=FETCH_TIMEOUT)
        except Exception:
            warnings.append("fetching origin failed: the landed check is as of the last fetch")
        default = policy.default_ref(main)
    tip = _run(main, "rev-parse", "--verify", "refs/heads/" + branch)
    try:
        pulls, unread = merged_pulls(main, branch), None
    except Exception as exc:
        pulls, unread = [], str(exc)[:200]
    own = next((p for p in pulls if not p["fork"] and p["head_sha"] == tip), None)
    if not own and not _on_default(main, tip, default):
        why = [f"GitHub could not be read: {unread}"] if unread else []
        if any(not p["fork"] for p in pulls):
            why.append("a pull request from this branch was merged at another commit, so commits came after the merge")
        elif not unread:
            why.append(f"it is not in {default} and no merged pull request from it was found" if default
                       else "the default branch is unknown here and no merged pull request from it was found")
        raise ValueError(f"the work has not landed on the default branch yet; nothing was moved or removed ({'; '.join(why)})")
    if unread:
        warnings.append(f"GitHub could not be read ({unread}): stacked layers were not considered")

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
        _run(main, "worktree", "remove", worktree)
    except ValueError as exc:
        put_back()
        raise ValueError(f"{exc}; nothing was removed and the sessions are back in the worktree, so cleanup can be "
                         "retried") from None
    if Path(worktree).parent != root:
        with contextlib.suppress(OSError):
            Path(worktree).parent.rmdir()

    deleted, kept = [], []

    def delete(name, expected):
        """Delete the branch only if it still points at the commit the landed check read."""
        try:
            _run(main, "update-ref", "-d", "refs/heads/" + name, expected)
        except ValueError as exc:
            try:
                now = _run(main, "rev-parse", "--verify", "refs/heads/" + name)
            except ValueError:
                now = expected
            kept.append({"branch": name, "reason": "it moved after the landed check" if now != expected else str(exc)})
        else:
            deleted.append(name)

    delete(branch, tip)
    checked_out = {entry["branch"]: entry["path"] for entry in _worktrees(main) if entry["branch"]}
    for layer in ((own or {}).get("stack") or {}).get("layers") or []:
        name = layer.get("head")
        if (layer.get("number") == own["number"] or name == branch or not isinstance(name, str)
                or not BRANCH.fullmatch(name) or ".." in name or name.endswith((".lock", "/", "."))
                or not layer.get("head_repo") or str(layer["head_repo"]).lower() != str(layer.get("repo")).lower()):
            continue
        try:
            layer_tip = _run(main, "rev-parse", "--verify", "refs/heads/" + name)
        except ValueError:
            continue
        if name in protected:
            kept.append({"branch": name, "reason": "a protected or default branch"})
        elif name in checked_out:
            kept.append({"branch": name, "reason": f"checked out in {checked_out[name]}"})
        elif _on_default(main, layer_tip, default) or (layer.get("state") == "merged"
                                                       and layer.get("head_sha") == layer_tip):
            delete(name, layer_tip)
        else:
            kept.append({"branch": name, "reason": "its work has not landed on the default branch"})

    result = {"session_id": sid, "removed": worktree, "moved_to": main, "moved_sessions": [i["id"] for i in moved],
              "left_behind": len(sessions) - len(mine), "branches_deleted": deleted, "branches_kept": kept}
    if warnings:
        result["warning"] = "; ".join(warnings)
    return result
