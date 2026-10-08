"""Session policy and repository guards. Pure functions plus read-only git.

OpenCode appends a session's rules after global and agent rules (last match wins)
and every subagent session copies its parent's ruleset. So the ruleset built here
holds only denies, asks and narrow allows, with one deliberate exception: a write
run allows edits in its worktree (see `rules`). Any other broad allow would reopen
what a subagent's own posture denies.

V2 wildcards match whole values and `*` crosses `/`, so `**/.env` misses a
root-level `.env`; secrets are spelled `*.env`.
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path
import re
import subprocess

SECRET_READS = ("*.env", "*.env.*", "*.envrc", "*.pem", "*.key", "*.npmrc", "*.netrc", "*.ssh/*")
SAMPLE_READS = ("*.env.example", "*.env.sample")
# `git diff/log/show --output=<file>` writes a file.
READ_ONLY_DENY_SHELL = ("git * --output*",)
# A read-only run never hands work to an agent that can edit.
READ_ONLY_DENY_SUBAGENTS = ("worker", "general")
# Writes that rewrite history, move branches or run packages come back to the
# caller as permission requests. `git -C`/`-c` put options before the subcommand,
# so no `git push *` pattern sees them.
WRITE_ASK_SHELL = (
    "git push *", "git rebase *", "git reset *", "git checkout *", "git switch *", "git restore *",
    "git clean *", "git merge *", "git revert *", "git cherry-pick *",
    "git commit *--amend*", "git commit *--no-verify*", "git -C *", "git -c *",
    "npm exec *", "npm create *", "pnpm dlx *", "pnpm exec *", "pnpm create *", "yarn dlx *",
    "yarn create *", "bun x *", "cargo install *", "go install *",
)
# Read-only git with `-C <dir>` would otherwise pause on the `git -C *` ask.
WRITE_ALLOW_AFTER_ASK = tuple(f"git -C * {verb} *" for verb in (
    "status", "diff", "log", "show", "rev-parse", "ls-files", "blame", "merge-base"))
ISSUE_WRITES = tuple(f"gh issue {verb} *" for verb in ("create", "edit", "comment", "reopen"))
# Never, for any policy or subagent: the caller cannot approve these either.
HARD_DENY_SHELL = (
    "gh pr merge *", "gh repo create *", "gh repo delete *", "gh repo edit *", "gh api *",
    "gh project *", "gh issue delete *", "gh issue close *", "gh auth *", "gh secret *",
    "npm publish *", "pnpm publish *", "git config *",
    "git push *--force*", "git push -f*", "git push * -f*", "git push * +*", "git push *--mirror*",
    "git push *--all*", "git push *--delete*", "git push * :*",
    "git reset *--hard*", "git clean *-*f*",
)
PROJECT_WRITES = (
    "github_project_create", "github_project_field_ensure", "github_project_item_add",
    "github_project_item_set", "github_project_item_note", "github_project_item_promote",
    "github_project_view_ensure", "github_project_issue_link", "github_project_issue_develop",
)


def rule(action, resource, effect):
    return {"action": action, "resource": resource, "effect": effect}


def directories(tmp):
    """OpenCode's own scratch dirs, and the read-only config/skill dirs the person's
    global config opens. A session-level `external_directory: *` would shadow
    OpenCode's defaults for them, so they are re-allowed after it."""
    data = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share") / "opencode"
    config = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "opencode"
    scratch = [f"{data}/tool-output/*", f"{data}/shell/*/*"]
    for path in {tmp, str(Path(tmp).resolve())} if tmp else ():
        scratch.append(f"{path}/*")
    readable = [f"{config}/*", f"{Path.home()}/.agents/skills/*", f"{Path.home()}/.claude/skills/*"]
    return scratch, readable


def output_dir(value):
    """The caller's output directory for a run's reports and screenshots: an existing
    directory inside a Workspaces draft (`.agent/`), never the repository, and spelled
    without wildcards so its rule cannot widen."""
    if value is None:
        return None
    if not isinstance(value, str) or not Path(value).is_absolute() or any(c in value for c in "*?"):
        raise ValueError("output_dir must be an absolute path without wildcards")
    path = Path(value).resolve()
    if not path.is_dir():
        raise ValueError("output_dir must be an existing directory; create it first")
    if ".agent" not in path.parts[:-1] and path.name != ".agent":
        raise ValueError("output_dir must lie inside a draft directory (.agent/)")
    if path.name == ".agent":
        raise ValueError("output_dir must be a job directory below .agent/, not .agent/ itself")
    return str(path)


def rules(policy, issue_approval, protected, *, tmp=None, person_denies=(), output=None):
    """The session ruleset for one run, ordered broad to narrow under last-match
    evaluation. Its one caller-chosen allow is the output directory, which the
    person's own outside-path denies still override."""
    person = [d for d in person_denies if d.get("effect") == "deny"]
    scratch, readable = directories(tmp)
    out = [rule("external_directory", "*", "ask")]
    if output:
        out += [rule("external_directory", output, "allow"), rule("external_directory", f"{output}/*", "allow")]
    # The person's own outside-path denies stay denies, not asks the caller could approve.
    out += [rule("external_directory", d["resource"], "deny") for d in person
            if d.get("action") == "external_directory"]
    out += [rule("external_directory", path, "allow") for path in scratch + readable]
    if policy == "write":
        # The one broad allow: edits inside the worktree (a path outside it is a separate,
        # asking `external_directory` request). Without it every edit would be a round trip
        # to the caller, as OpenCode's own build mode asks a person each time. The cost is
        # that a subagent which denies itself edits (explore) loses that denial for this
        # run. It comes before every edit deny below, which therefore still win.
        out.append(rule("edit", "*", "allow"))
    out += [rule("edit", path, "deny") for path in readable]
    out += [rule("read", pattern, "deny") for pattern in SECRET_READS]
    out += [rule("read", pattern, "allow") for pattern in SAMPLE_READS]
    out += [rule("edit", pattern, "deny") for pattern in SECRET_READS]
    out += [rule("edit", pattern, "allow") for pattern in SAMPLE_READS]
    if policy == "read-only":
        out.append(rule("edit", "*", "deny"))
        if output:
            # A read-only run may still write its report into the output directory,
            # never a secret-looking file there.
            out += [rule("edit", output, "allow"), rule("edit", f"{output}/*", "allow")]
            out += [rule("edit", pattern, "deny") for pattern in SECRET_READS]
        out += [rule("shell", pattern, "deny") for pattern in READ_ONLY_DENY_SHELL + ISSUE_WRITES]
        out += [rule("subagent", name, "deny") for name in READ_ONLY_DENY_SUBAGENTS]
    else:
        out += [rule("shell", pattern, "ask") for pattern in WRITE_ASK_SHELL]
        out += [rule("shell", pattern, "allow") for pattern in WRITE_ALLOW_AFTER_ASK]
        if not issue_approval:
            out += [rule("shell", pattern, "ask") for pattern in ISSUE_WRITES]
    deny = list(HARD_DENY_SHELL)
    for branch in sorted(protected):
        deny += [f"git push * {branch}", f"git push * {branch} *", f"git push *:{branch}*",
                 f"git push *:refs/heads/{branch}*", f"git push * refs/heads/{branch}",
                 f"git push * refs/heads/{branch} *"]
    # The same denies when `-C <dir>` / `-c <k=v>` precede the subcommand. Not a
    # bare `git * push`: that would also match a commit message saying "push".
    deny += [f"git {option} * " + pattern[len("git "):] for option in ("-C", "-c") for pattern in deny
             if pattern.startswith(("git push ", "git reset ", "git clean ", "git config "))]
    out += [rule("shell", pattern, "deny") for pattern in deny]
    out += [rule(name, "*", "deny") for name in PROJECT_WRITES]
    # A person's own denies are re-stated last, so an agent's broad allow (build's
    # `shell: *`) never reopens `sudo` or `secret get`. Their `external_directory`
    # denies went in above the scratch-dir allows instead.
    out += [rule(d["action"], d["resource"], "deny") for d in person if d.get("action") != "external_directory"]
    return out


def matches(pattern, value, shell=False):
    regex = "".join(".*" if c == "*" else "." if c == "?" else re.escape(c) for c in pattern)
    if re.fullmatch(regex, value, re.S):
        return True
    return shell and pattern.endswith(" *") and value == pattern[:-2]


def decide(ruleset, action, resource):
    """OpenCode's evaluation: the last rule whose action and resource match wins;
    with none, ask."""
    effect = "ask"
    for item in ruleset:
        if matches(item["action"], action) and matches(item["resource"], resource, action == "shell"):
            effect = item["effect"]
    return effect


# --------------------------------------------------------------------------
# Repository guards


def git(directory, *args):
    proc = subprocess.run(["git", "-C", str(directory), *args], capture_output=True, text=True, timeout=15)
    if proc.returncode:
        raise ValueError("Cannot establish the requested Git worktree state")
    return proc.stdout.strip()


def worktree(value):
    if not isinstance(value, str) or not Path(value).is_absolute():
        raise ValueError("directory must be an absolute Git worktree path")
    directory = Path(value).resolve(strict=True)
    if directory != Path(git(directory, "rev-parse", "--show-toplevel")).resolve():
        raise ValueError("Use the worktree root, not a subdirectory")
    return str(directory)


def branch(directory, writing):
    """(branch name, protected branch names) of the worktree. A write run needs a named
    task branch that is not the default branch, local or remote."""
    protected = {"main", "master"}
    symbolic = subprocess.run(["git", "-C", directory, "symbolic-ref", "--quiet", "--short", "HEAD"],
                              capture_output=True, text=True, timeout=15)
    if symbolic.returncode:
        if writing or symbolic.returncode != 1:
            raise ValueError("A write run requires a named task branch; Git branch identity is unavailable")
        return "detached:" + git(directory, "rev-parse", "--verify", "HEAD"), protected
    name = symbolic.stdout.strip()
    remote = subprocess.run(["git", "-C", directory, "symbolic-ref", "--quiet", "--short",
                             "refs/remotes/origin/HEAD"], capture_output=True, text=True, timeout=15)
    if not remote.returncode:
        protected.add(remote.stdout.strip().removeprefix("origin/"))
    if writing and "origin" in git(directory, "remote").splitlines():
        # Local origin/HEAD can be absent or stale after the host changes its
        # default branch. Resolve the remote's symbolic HEAD before any write.
        head = subprocess.run(["git", "-C", directory, "ls-remote", "--symref", "origin", "HEAD"],
                              env={**os.environ, "GIT_TERMINAL_PROMPT": "0"}, capture_output=True,
                              text=True, timeout=20)
        match = re.search(r"^ref: refs/heads/(.+)\s+HEAD$", head.stdout, re.MULTILINE)
        if head.returncode or not match:
            raise ValueError("Remote default branch could not be verified; no write run launched")
        protected.add(match.group(1))
    if writing and name in protected:
        raise ValueError("A write run requires a separate task branch/worktree, never the default branch")
    return name, protected


def same_dir(a, b):
    with contextlib.suppress(OSError, TypeError):
        return os.path.realpath(a) == os.path.realpath(b)
    return False
