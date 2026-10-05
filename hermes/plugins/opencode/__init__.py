"""OpenCode transport (`opencode run` on 1, a private API server on 2), not a planner,
approval authority, or process sandbox."""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import selectors
import shlex
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

import hermes_yaml as yaml


# Reuse this repository's caller binding and atomic-record primitives. Do not
# import Hermes' transient/private delegate implementation or duplicate its API.
_name = "hermes_engineer_specialist_transport"
if _name not in sys.modules:
    _spec = importlib.util.spec_from_file_location(
        _name, Path(__file__).resolve().parents[1] / "specialist-call/__init__.py")
    _module = importlib.util.module_from_spec(_spec)
    sys.modules[_name] = _module
    _spec.loader.exec_module(_module)
dispatch = sys.modules[_name]

# Read-only session inventory. A stdlib-only sibling so cron scripts can run the
# same code as a CLI; it never touches the execution registry above.
_name = "hermes_opencode_history"
if _name not in sys.modules:
    _spec = importlib.util.spec_from_file_location(_name, Path(__file__).resolve().parent / "history.py")
    _module = importlib.util.module_from_spec(_spec)
    sys.modules[_name] = _module
    _spec.loader.exec_module(_module)
inventory = sys.modules[_name]

AGENTS = {"plan", "build", "review", "debug"}
# Hermes-facing role -> installed OpenCode agent. plan/build/review run on the
# hidden non-interactive primaries in ~/.config/opencode/agent/hermes-*.md
# (no question tool, no plan->build handoff, verifier-only checks, review
# passes only on request); debug still shares the human TUI primary. Every
# other decision in this module keys on the Hermes role, never on this name.
OPENCODE_AGENTS = {"plan": "hermes-plan", "build": "hermes-build", "review": "hermes-review", "debug": "debug"}
# Profiles that may drive OpenCode. Engineer is the developer; Assistant uses it
# for its own admin-scope work (this config repo, Hermes upkeep), never on a
# worktree an Engineer job owns. Registries stay per profile home.
PROFILES = {"engineer", "assistant"}
# `waiting`: an OpenCode 2 run is paused on a permission request the caller answers.
BUSY = {"accepted", "running", "waiting", "unknown"}
MAX_LOG = 8 * 1024 * 1024
MAX_LINE = 1024 * 1024
SESSION_ID = re.compile(r"ses_[A-Za-z0-9_-]+\Z")
PERMISSION_ID = re.compile(r"per_[A-Za-z0-9_-]{1,64}\Z")
DECISIONS = ("once", "reject")
# Per-job fields a new turn must not inherit from the previous one.
TURN_FIELDS = ("exit_code", "reconciliation", "pending", "progress", "changes", "changes_error", "denied",
               "replies")
PROGRESS_EVERY = 5.0
NO_APPROVER = ("No approver is attached to this run. Continue without this action, or stop and report "
               "what you needed and why.")
REJECTED = "Rejected by Hermes Engineer: outside the approved scope. Do not retry it another way."
WAITING_NOTE = ("OpenCode is paused on the pending permission request(s). Decide each one (ask the Client "
                "when it is theirs to decide), answer with opencode_session answer, then wait.")
MODEL_NAME = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.:-]+\Z")
VARIANT_NAME = re.compile(r"[A-Za-z0-9_-]{1,32}\Z")
DEFAULT_WAIT_TIMEOUT = 3300
WAIT_POLL = 1.0
PROJECT_WRITES = (
    "github_project_create", "github_project_field_ensure", "github_project_item_add",
    "github_project_item_set", "github_project_item_note", "github_project_item_promote",
    "github_project_view_ensure", "github_project_issue_link", "github_project_issue_develop",
)
# This module is the ONLY owner of the hidden primaries' permission policy. The
# agent files in ~/.config/opencode/agent/hermes-*.md carry no `permission:`
# block: OpenCode deep-merges frontmatter and OPENCODE_CONFIG_CONTENT (the
# latter wins per key, nested maps union), so a rule that lived in both places
# had no single source of truth. Read-only roles (plan / review / debug) share
# one posture apart from their subagents; build gets the write surface below. An agent-level "*": deny
# also shadows the user's global tool allows, so every tool a read-only role
# needs is listed here explicitly.
READ_ONLY_BASH = (
    "git status*", "git diff*", "git log*", "git show*", "git blame*", "git ls-files*",
    "git rev-parse*", "git merge-base*", "git branch --show-current", "git remote -v",
    "git remote get-url*",
    "gh issue view*", "gh issue list*", "gh pr view*", "gh pr diff*", "gh pr checks*",
    "gh pr status*", "gh pr list*", "gh repo view*",
)
# Subagents per Hermes role. Plan only explores and researches; review fans
# out to reviewer* and verifier; debug isolates through debugger and verifies.
# verifier is not read-only in effect (it may apply a formatter), so plan
# does not get it: a plan run leaves the tree exactly as it found it.
ROLE_TASKS = {
    "plan": ("explore*", "searcher*"),
    "review": ("explore*", "searcher*", "reviewer*", "verifier"),
    "debug": ("explore*", "searcher*", "debugger", "verifier"),
    "build": ("explore*", "searcher*", "verifier", "worker", "reviewer", "reviewer-deep"),
}
GIT_READ_TOOLS = ("git_provenance", "git_history_digest", "git_related_scan")
READ_RULES = {"*": "allow", "**/.env": "deny", "**/.env.*": "deny", "**/*.env": "deny",
              "**/.ssh/**": "deny", "**/*.pem": "deny",
              "**/.env.example": "allow", "**/.env.sample": "allow"}


def _external_directory():
    """Nothing outside the worktree, except OpenCode's own scratch locations.

    OpenCode's global layer allows its truncated-tool-output dir and its temp dir
    for every agent, but an agent-level "*" deny is evaluated last and shadows
    them (measured 2026-09-16), so they are re-allowed here. A plain `ask` is
    no alternative: `opencode run` without --auto rejects it, and with --auto
    approves it, so it never means "ask" on this transport. OpenCode 2 adds its
    shell-output dir and spells the temp dir by its resolved path (/private/var
    on macOS), so both spellings are listed.
    """
    data = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
    tmp = Path(os.environ.get("TMPDIR") or "/tmp") / "opencode"
    scratch = [data / "opencode/tool-output/*", data / "opencode/shell/*/*", tmp / "*", tmp.resolve() / "*"]
    return {"*": "deny", **{str(path): "allow" for path in scratch}}


# ~/.config/opencode/agent/worker.md opens worktree homes outside the session
# directory (allow) and asks for any other outside path, for interactive use.
# Under `run --auto` that ask is an approval, so a role that may spawn worker
# re-closes it here. Nested maps union on merge and the injected value wins per
# key, so every pattern worker.md names must be re-stated as a deny: an omitted
# key would keep its allow. Literal keys, not expanded — they must match
# worker.md's spelling to override it. A test keeps this list in sync.
WORKER_EXTERNAL_KEYS = ("*", "~/.local/share/opencode/worktree/*", "*/.worktrees/*")


def _worker_external_directory():
    return {**{key: "deny" for key in WORKER_EXTERNAL_KEYS}, **_external_directory()}


# OpenCode 2 policy: one ordered ruleset set on the session itself. The session's
# rules are evaluated after the global and agent rules (last match wins), they
# survive a resume or fork on any server, and every subagent session copies them,
# so a subagent can do nothing its parent session denies. V2 matches whole values:
# `*` also crosses `/`, and a shell pattern ending in " *" also matches the bare
# command, so `*.env` covers `.env` at the root and below (V1's `**/.env` did not).
# The shell scanner splits compound commands (`;`, `&&`, `|`, `$(…)`) and checks
# each part, so an allowed prefix cannot carry another command (measured on 2.0.23).
#
# Only plan and build run on OpenCode 2. Review and debug are build's subagents
# there (reviewer*, debugger, verifier), under build's ruleset; a read-only
# primary whose subagents inherit a read-only policy could not run a single check.
V2_AGENTS = {"plan", "build"}
V2_TASKS = {"plan": ROLE_TASKS["plan"], "build": ROLE_TASKS["build"] + ("debugger",)}
SECRET_READS = ("*.env", "*.env.*", "*.envrc", "*.pem", "*.key", "*.npmrc", "*.netrc", "*.ssh/*")
SAMPLE_READS = ("*.env.example", "*.env.sample")
READ_ONLY_SHELL = (
    "git status *", "git diff *", "git log *", "git show *", "git blame *", "git ls-files *",
    "git rev-parse *", "git merge-base *", "git branch --show-current", "git remote -v",
    "git remote get-url *",
    "gh issue view *", "gh issue list *", "gh pr view *", "gh pr diff *", "gh pr checks *",
    "gh pr status *", "gh pr list *", "gh repo view *",
)
# `git diff/log/show --output=<file>` writes a file.
READ_ONLY_DENY_SHELL = ("git * --output*",)
# Build runs without a person, so these come back to the caller as permission
# requests: history rewrites, pushes, branch moves and package installers. `git
# -C`/`-c` put options before the subcommand, so no `git push *` pattern sees them.
BUILD_ASK_SHELL = (
    "git push *", "git rebase *", "git reset *", "git checkout *", "git switch *", "git restore *",
    "git clean *", "git merge *", "git revert *", "git cherry-pick *",
    "git commit *--amend*", "git commit *--no-verify*", "git -C *", "git -c *",
    "npm exec *", "npm create *", "pnpm dlx *", "pnpm exec *", "pnpm create *", "yarn dlx *",
    "yarn create *", "bun x *", "cargo install *", "go install *",
)
# Read-only git with `-C <dir>` would otherwise pause on the `git -C *` ask.
BUILD_ALLOW_AFTER_ASK = tuple(f"git -C * {verb} *" for verb in ("status", "diff", "log", "show", "rev-parse",
                                                               "ls-files", "blame", "merge-base"))
BUILD_DENY_SHELL = (
    "gh pr merge *", "gh repo create *", "gh repo delete *", "gh repo edit *", "gh api *",
    "gh project *", "gh issue delete *", "gh issue close *", "gh auth *", "gh secret *",
    "npm publish *", "pnpm publish *", "git config *",
    "git push *--force*", "git push -f*", "git push * -f*", "git push * +*", "git push *--mirror*",
    "git push *--all*", "git push *--delete*", "git push * :*",
    "git reset *--hard*", "git clean *-*f*",
)


def _rule(action, resource, effect):
    return {"action": action, "resource": resource, "effect": effect}


def _rules(role, issue_approval, protected, denies=()):
    """The V2 session ruleset for plan or build, ordered broad to narrow.

    Plan starts from a full deny and lists what it may do. Build allows routine
    edits and commands, returns the person-gated commands as requests, and
    denies what it must never do. `denies` — every deny OpenCode resolved for
    the agent from the global and project config — goes last, so a session
    allow never reopens a person's own hard deny.
    """
    rules = [] if role == "build" else [_rule("*", "*", "deny")]
    rules += [_rule("read", "*", "allow"), *(_rule("read", r, "deny") for r in SECRET_READS),
              *(_rule("read", r, "allow") for r in SAMPLE_READS)]
    # Code Mode (`execute`) is build's only: its nested tools are not plan's surface.
    rules += [_rule(action, "*", "allow") for action in ("glob", "grep", "skill", "webfetch", "websearch", "todo*")
              + (("execute",) if role == "build" else ())]
    rules.append(_rule("question", "*", "deny"))
    rules += [_rule("external_directory", key, effect) for key, effect in _external_directory().items()]
    rules += [_rule("subagent", "*", "deny"), *(_rule("subagent", name, "allow") for name in V2_TASKS[role])]
    if role == "plan":
        rules.append(_rule("edit", "*", "deny"))
        rules += [_rule("shell", pattern, "allow") for pattern in READ_ONLY_SHELL]
        rules += [_rule("shell", pattern, "deny") for pattern in READ_ONLY_DENY_SHELL]
        rules += [_rule(name, "*", "allow") for name in GIT_READ_TOOLS]
    else:
        rules += [_rule("edit", "*", "allow"), _rule("shell", "*", "allow")]
        rules += [_rule("shell", pattern, "ask") for pattern in BUILD_ASK_SHELL]
        rules += [_rule("shell", pattern, "allow") for pattern in BUILD_ALLOW_AFTER_ASK]
        deny = list(BUILD_DENY_SHELL)
        for branch in sorted(protected):
            deny += [f"git push * {branch}", f"git push * {branch} *", f"git push *:{branch}*",
                     f"git push *:refs/heads/{branch}*", f"git push * refs/heads/{branch}",
                     f"git push * refs/heads/{branch} *"]
        # The same denies when `-C <dir>` / `-c <k=v>` precede the subcommand. Not a
        # bare `git * push`: that would also match a commit message saying "push".
        deny += [f"git {option} * " + pattern[len("git "):] for option in ("-C", "-c") for pattern in deny
                 if pattern.startswith(("git push ", "git reset ", "git clean ", "git config "))]
        if not issue_approval:
            deny += [f"gh issue {verb} *" for verb in ("create", "edit", "comment", "reopen")]
        rules += [_rule("shell", pattern, "deny") for pattern in deny]
        rules += [_rule(name, "*", "deny") for name in PROJECT_WRITES]
    # A person's denies are re-stated verbatim, except `external_directory`:
    # its deny would shadow the re-allowed OpenCode scratch dirs above it.
    return rules + [_rule(d["action"], d["resource"], "deny") for d in denies
                    if d.get("action") != "external_directory"]


def _root(home):
    root = home / "opencode-sessions"
    root.mkdir(mode=0o700, exist_ok=True)
    if root.is_symlink():
        raise ValueError("OpenCode registry must not be a symlink")
    root.chmod(0o700)
    return root


def _scope():
    home, owner, live, inbound = dispatch._scope()
    if home.name not in PROFILES or inbound:
        raise ValueError("OpenCode execution requires an Engineer/Assistant CLI/resident or live conversation")
    return home, owner, live


def _config(home):
    data = yaml.safe_load((home / "config.yaml").read_text()) or {}
    config = data.get("opencode_cli") or {}
    if not isinstance(config, dict) or config.get("enabled") is not True:
        raise ValueError("OpenCode CLI integration is not enabled")
    timeout = config.get("timeout", 3600)
    if type(timeout) is not int or not 1 <= timeout <= 5400:
        raise ValueError("opencode_cli.timeout must be 1..5400 seconds")
    wait_timeout = config.get("wait_timeout", DEFAULT_WAIT_TIMEOUT)
    if type(wait_timeout) is not int or not 1 <= wait_timeout <= 5400:
        raise ValueError("opencode_cli.wait_timeout must be 1..5400 seconds")
    for key in ("allowed_models", "allowed_variants"):
        values = config.get(key, [])
        if not isinstance(values, list) or not all(isinstance(v, str) and v for v in values):
            raise ValueError(f"opencode_cli.{key} must be a list of names")
    return config


def _selection(args, config):
    """Caller-requested model/variant, accepted only from the configured allowlists.

    A request outside the allowlist is refused rather than silently replaced:
    the caller asked for a specific engine, and running another one would return
    a result that is not the one asked for.
    """
    selection = {}
    for key, pattern, config_key in (("model", MODEL_NAME, "allowed_models"),
                                     ("variant", VARIANT_NAME, "allowed_variants")):
        value = args.get(key)
        if value is None:
            continue
        if not isinstance(value, str) or not pattern.fullmatch(value):
            raise ValueError(f"{key} must be a plain name" + (" in provider/model form" if key == "model" else ""))
        if value not in config.get(config_key, []):
            raise ValueError(f"{key} {value!r} is not in opencode_cli.{config_key}; ask the maintainer or omit it")
        selection[key] = value
    if "variant" in selection and "model" not in selection and not (config.get("models") or {}).get(args.get("agent")):
        # A variant is provider-specific reasoning effort; without a chosen model it
        # would bind to whatever OpenCode's own default resolves to.
        raise ValueError("variant requires a model (explicit or configured for this agent)")
    return selection


def _git(directory, *args):
    proc = subprocess.run(["git", "-C", str(directory), *args], capture_output=True,
                          text=True, timeout=15)
    if proc.returncode:
        raise ValueError("Cannot establish the requested Git worktree state")
    return proc.stdout.strip()


def _worktree(value):
    if not isinstance(value, str) or not Path(value).is_absolute():
        raise ValueError("directory must be an absolute Git worktree path")
    directory = Path(value).resolve(strict=True)
    if directory != Path(_git(directory, "rev-parse", "--show-toplevel")).resolve():
        raise ValueError("Use the worktree root, not a subdirectory")
    return str(directory)


def _branch(directory, building):
    protected = {"main", "master"}
    symbolic = subprocess.run(["git", "-C", directory, "symbolic-ref", "--quiet", "--short", "HEAD"],
                              capture_output=True, text=True, timeout=15)
    if symbolic.returncode:
        if building or symbolic.returncode != 1:
            raise ValueError("Build requires a named task branch; Git branch identity is unavailable")
        return "detached:" + _git(directory, "rev-parse", "--verify", "HEAD"), protected
    branch = symbolic.stdout.strip()
    remote = subprocess.run(["git", "-C", directory, "symbolic-ref", "--quiet", "--short",
                             "refs/remotes/origin/HEAD"], capture_output=True, text=True, timeout=15)
    if not remote.returncode:
        protected.add(remote.stdout.strip().removeprefix("origin/"))
    if building and "origin" in _git(directory, "remote").splitlines():
        # Local origin/HEAD can be absent or stale after the host changes its
        # default branch. Resolve the remote's symbolic HEAD before any build.
        head = subprocess.run(["git", "-C", directory, "ls-remote", "--symref", "origin", "HEAD"],
                              env={**os.environ, "GIT_TERMINAL_PROMPT": "0"}, capture_output=True,
                              text=True, timeout=20)
        match = re.search(r"^ref: refs/heads/(.+)\s+HEAD$", head.stdout, re.MULTILINE)
        if head.returncode or not match:
            raise ValueError("Remote default branch could not be verified; no build launched")
        protected.add(match.group(1))
    if building and branch in protected:
        raise ValueError("Build requires a separate task branch/worktree, never the default branch")
    return branch, protected


def _permissions(agent, issue_approval, protected):
    if agent != "build":
        # No human answers an ask in `opencode run`, and a read-only role has no
        # business outside its worktree, so external_directory and question are
        # denied outright rather than left to whatever run mode does with ask.
        return {
            "*": "deny", "read": dict(READ_RULES),
            "glob": "allow", "grep": "allow", "list": "allow",
            "skill": "allow", "webfetch": "allow", "websearch": "allow", "todowrite": "allow",
            "question": "deny", "external_directory": _external_directory(), "edit": "deny",
            "task": {"*": "deny", **{name: "allow" for name in ROLE_TASKS[agent]}},
            "bash": {"*": "deny", **{pattern: "allow" for pattern in READ_ONLY_BASH}},
            **{name: "allow" for name in GIT_READ_TOOLS},
        }
    # Leave global protective rules intact. --auto resolves asks as approvals,
    # so anything that must not happen is a deny here, never an ask; no wildcard
    # allow is injected. These rules are defence in depth, not a shell sandbox.
    bash = {pattern: "deny" for pattern in (
        "gh pr merge*", "gh repo create*", "gh repo delete*", "gh repo edit*", "gh api*",
        "gh project *", "gh issue delete*", "gh issue close*", "npm publish*", "pnpm publish*",
        "git push*--force*", "git push* -f*", "git push*--mirror*", "git push*--all*",
        "git reset --hard*", "git clean -f*",
    )}
    for branch in protected:
        bash.update({f"git push* {branch}": "deny", f"git push* {branch} *": "deny",
                     f"git push*:{branch}*": "deny", f"git push*:refs/heads/{branch}*": "deny"})
    if not issue_approval:
        bash.update({f"gh issue {verb}*": "deny" for verb in ("create", "edit", "comment", "reopen")})
    return {
        "edit": "allow", "read": dict(READ_RULES), "todowrite": "allow", "skill": "allow",
        "question": "deny", "external_directory": _external_directory(),
        "task": {"*": "deny", **{name: "allow" for name in ROLE_TASKS["build"]}},
        "bash": bash, **{name: "deny" for name in PROJECT_WRITES},
    }


def _model(data, config):
    """(model, variant) bound by the conversation, else configured for the role."""
    model = data.get("model") or (config.get("models") or {}).get(data["agent"])
    if model:
        if not isinstance(model, str) or not re.fullmatch(r"[A-Za-z0-9_.:/-]+", model):
            raise ValueError("Invalid configured OpenCode model")
    variant = data.get("variant")
    if variant:
        if not isinstance(variant, str) or not VARIANT_NAME.fullmatch(variant):
            raise ValueError("Invalid recorded OpenCode variant")
        if not model:
            # Re-checked at dispatch: the configured per-agent model may have been
            # removed since the conversation bound its variant.
            raise ValueError("Recorded variant has no model to bind to; pass model explicitly")
    return model, variant


def _command(data, config):
    """OpenCode 1 only; OpenCode 2 runs through `_run_api`."""
    command = ["opencode", "run", "--format", "json", "--agent", OPENCODE_AGENTS[data["agent"]],
               "--dir", data["directory"]]
    if data["agent"] == "build":
        command.append("--auto")
    model, variant = _model(data, config)
    command += ["--model", model] if model else []
    command += ["--variant", variant] if variant else []
    if data.get("session_id"):
        if not SESSION_ID.fullmatch(data["session_id"]):
            raise ValueError("Invalid saved OpenCode session identity")
        command += ["--session", data["session_id"]]
    if data.get("fork"):
        command.append("--fork")
    # stdin carries the prompt, not a shell fragment or a process-list argument.
    return command


def _env(data, protected):
    """OpenCode 1 only: the policy rides the environment of the run process."""
    env = inventory.child_env()
    permission = _permissions(data["agent"], data.get("issue_approval"), protected)
    env["OPENCODE_PERMISSION"] = json.dumps(permission)
    agents = {OPENCODE_AGENTS[data["agent"]]: {"permission": permission}}
    if "worker" in ROLE_TASKS[data["agent"]]:
        agents["worker"] = {"permission": {"external_directory": _worker_external_directory()}}
    env["OPENCODE_CONFIG_CONTENT"] = json.dumps({"share": "disabled", "agent": agents})
    return env


def _public(data):
    keys = ("conversation_id", "job_id", "directory", "branch", "agent", "model", "variant", "status",
            "session_id", "result", "error", "exit_code", "log", "updated_at", "reconciliation",
            "pending", "progress", "changes", "changes_error", "denied", "replies")
    return {key: data[key] for key in keys if key in data}


def _group_alive(pgid):
    if not pgid:
        return False
    try:
        os.killpg(pgid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _prompt(request, data):
    text = request["message"]
    if data["agent"] == "build":
        text += "\n\nClient implementation scope: " + data["approval"]
        text += "\nIssue management: " + (data.get("issue_approval") or "not granted")
    return text + ("\n\nIf anything material is undecided or blocked, stop and state "
                   "the open question and options in your final reply. Never guess client approval.\n")


def _run(request_path):
    request = dispatch._read(request_path)
    home = Path(request["home"])
    if home.name not in PROFILES or home.parent.name != "profiles":
        raise ValueError("Invalid captured OpenCode caller home")
    root = _root(home)
    cid, job = dispatch._id(request["conversation_id"]), dispatch._id(request["job_id"])
    if request_path != root / (job + ".request"):
        raise ValueError("Request is outside its captured registry")
    with dispatch._locked(root, cid):
        data = dispatch._owned(root, cid, request["owner"])
        digest = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
        if data["job_id"] != job or data["status"] != "accepted" or data["request_digest"] != digest:
            raise ValueError("Stale, altered, or already dispatched request")
        # `launched`: from here on effects are possible, so a failure is `unknown`.
        state = {"proc": None, "launched": False}
        stop_path = root / (job + ".stop")
        old_handlers = {}
        interrupted = False

        def interrupt(signum, frame):
            nonlocal interrupted
            interrupted = True

        def should_stop():
            return (interrupted or stop_path.exists() or time.time() >= request["deadline"]
                    or bool(request.get("parent_pid") and os.getppid() != request["parent_pid"]))

        try:
            for sig in (signal.SIGTERM, signal.SIGINT):
                old_handlers[sig] = signal.signal(sig, interrupt)
            config = _config(home)
            if _worktree(data["directory"]) != data["directory"]:
                raise ValueError("Worktree identity changed")
            branch, protected = _branch(data["directory"], data["agent"] == "build")
            if branch != data["branch"]:
                raise ValueError("Worktree branch changed since dispatch")
            # Probe first: the stop/deadline gate below must be the last check
            # before launch, and the probe itself can take seconds.
            major = inventory.opencode_major()
            if major == 2 and data["agent"] not in V2_AGENTS:
                raise ValueError(f"{data['agent']} is not an OpenCode 2 role: ask build to run its "
                                 "reviewer/debugger/verifier subagents and report their findings")
            if time.time() >= request["deadline"] or stop_path.exists():
                raise ValueError("Stopped or expired before dispatch")
            data.update(status="running", result="", error="")
            dispatch._write(root / (cid + ".json"), data)
            prompt = _prompt(request, data)
            with open(root / (job + ".prompt"), "x", encoding="utf-8") as stream:
                os.chmod(stream.name, 0o600)
                stream.write(prompt)
            if major == 1:
                _run_cli(root, cid, job, data, config, protected, should_stop, state)
            else:
                _run_api(root, cid, job, data, config, protected, prompt, request, should_stop, state)
        except Exception as exc:
            data.update(status="unknown" if state["launched"] else "failed",
                        error=f"{type(exc).__name__}: {exc}: execution not confirmed" if state["launched"] else str(exc))
        finally:
            proc = state["proc"]
            if proc is not None:
                # Only this live runner signals its own child group, never a stored PID.
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(proc.pid, signal.SIGKILL)
                proc.wait(timeout=5)
                proc.stdout.close()
                proc.stderr.close()
            for sig, handler in old_handlers.items():
                signal.signal(sig, handler)
            data.pop("pending", None)
            data["updated_at"] = time.time()
            dispatch._write(root / (cid + ".json"), data)
    return _public(data)


def _run_cli(root, cid, job, data, config, protected, should_stop, state):
    """OpenCode 1: one `opencode run` process, completion read from its JSON events."""
    command = _command(data, config)
    original_sid = data.get("session_id")
    with open(root / (job + ".prompt")) as prompt:
        proc = state["proc"] = subprocess.Popen(
            command, cwd=data["directory"], env=_env(data, protected), stdin=prompt,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    state["launched"] = True
    data["pgid"] = proc.pid
    dispatch._write(root / (cid + ".json"), data)
    buffers = {"stdout": b"", "stderr": b""}
    texts = {}
    last_finish = None
    seen_sid = None
    protocol_error = False
    event_error = False
    total = 0
    stopped = False
    with selectors.DefaultSelector() as selector, open(root / (job + ".events"), "xb") as log:
        os.chmod(log.name, 0o600)
        for name in buffers:
            stream = getattr(proc, name)
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, name)

        def event(line):
            nonlocal seen_sid, last_finish, protocol_error, event_error
            try:
                item = json.loads(line)
                sid = item.get("sessionID")
                if sid:
                    if not isinstance(sid, str) or not SESSION_ID.fullmatch(sid):
                        raise ValueError("Invalid event session ID")
                    if seen_sid and sid != seen_sid:
                        raise ValueError("Event session changed")
                    if original_sid and ((data.get("fork") and sid == original_sid)
                                         or (not data.get("fork") and sid != original_sid)):
                        raise ValueError("Unexpected resumed/forked session")
                    seen_sid = sid
                    data["session_id"] = sid
                    dispatch._write(root / (cid + ".json"), data)
                part = item.get("part") or {}
                if item.get("type") == "error":
                    event_error = True
                elif item.get("type") == "text" and isinstance(part.get("text"), str):
                    texts.setdefault(part.get("messageID"), []).append(part["text"])
                elif item.get("type") == "step_finish":
                    last_finish = part
            except (ValueError, TypeError, AttributeError):
                protocol_error = True

        while selector.get_map():
            if should_stop():
                stopped = True
                break
            if total > MAX_LOG or any(len(buf) > MAX_LINE for buf in buffers.values()):
                protocol_error = True
                break
            for key, _ in selector.select(0.2):
                chunk = os.read(key.fileobj.fileno(), 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                    if buffers[key.data] and key.data == "stdout":
                        event(buffers[key.data])
                    buffers[key.data] = b""
                    continue
                total += len(chunk)
                log.write(chunk)
                buffers[key.data] += chunk
                while b"\n" in buffers[key.data]:
                    line, buffers[key.data] = buffers[key.data].split(b"\n", 1)
                    if key.data == "stdout" and line.strip():
                        event(line)
        log.flush()
    if stopped or protocol_error:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(proc.pid, signal.SIGTERM)
    try:
        code = proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(proc.pid, signal.SIGKILL)
        code = proc.wait(timeout=5)
        stopped = True
    finished = bool(last_finish and last_finish.get("reason") == "stop" and seen_sid)
    message_id = last_finish.get("messageID") if last_finish else None
    data["result"] = "\n".join(texts.get(message_id) or [t for group in texts.values() for t in group])
    data["exit_code"] = code
    if stopped or protocol_error or code < 0:
        data.update(status="unknown", error="Completion not confirmed; inspect effects before reconciliation")
    elif event_error or code:
        data.update(status="failed", error="OpenCode reported an error; partial effects may exist")
    elif not finished:
        data.update(status="unknown", error="Completion not confirmed; inspect effects before reconciliation")
    else:
        data.update(status="completed", error="")


class _NotFound(ValueError):
    pass


class _Api(inventory.ApiServer):
    """The history module's private loopback server, plus JSON writes."""

    def call(self, method, path, body=None, timeout=inventory.REQUEST_TIMEOUT):
        payload = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(self.base + path, data=payload, method=method, headers={
            "Authorization": self.auth, "Accept": "application/json",
            **({"Content-Type": "application/json"} if payload is not None else {})})
        # Name the route, not the identities in it.
        route = re.sub(r"/(ses|msg|per)_[A-Za-z0-9_-]+", r"/{\1}", path.split("?", 1)[0])
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            kind = _NotFound if exc.code == 404 else ValueError
            raise kind(f"OpenCode API {method} {route} returned HTTP {exc.code}") from None
        except (urllib.error.URLError, OSError) as exc:
            raise ValueError(f"OpenCode API {method} {route} failed: {type(exc).__name__}") from None
        data = json.loads(raw) if raw else None
        return data["data"] if isinstance(data, dict) and "data" in data else data


# Stops the job's server if its runner dies without cleaning up (SIGKILL, OOM):
# `opencode serve` never exits by itself and would hold the worktree forever.
WATCHDOG = """
import os, signal, sys, time
runner, server = int(sys.argv[1]), int(sys.argv[2])
def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
# Reparented the moment the runner exits, reaped or not.
while os.getppid() == runner and alive(server):
    time.sleep(1)
for sig in (signal.SIGTERM, signal.SIGKILL):
    if not alive(server):
        break
    try:
        os.killpg(server, sig)
    except ProcessLookupError:
        break
    time.sleep(5)
"""
POLL_TIMEOUT = 10
SETUP_TIMEOUT = 30
# After a stop or the deadline, each remaining call gets this long, so the
# runner settles within the caller's grace (opencode_call allows 15 s).
TAIL_TIMEOUT = 3
AGENT_READY = 20


def _watch(server_pid):
    return subprocess.Popen([sys.executable, "-I", "-c", WATCHDOG, str(os.getpid()), str(server_pid)],
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)


def _text(message):
    return "\n".join(c["text"] for c in message.get("content") or []
                     if isinstance(c, dict) and c.get("type") == "text" and isinstance(c.get("text"), str))


def _iso_ms(value):
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(value / 1000)) if isinstance(value, (int, float)) else None


def _progress(api, sid):
    """Where the run is now: the newest step's time and its last tool, cumulative tokens."""
    info = api.call("GET", f"/api/session/{sid}", timeout=POLL_TIMEOUT) or {}
    newest = (api.call("GET", f"/api/session/{sid}/message?type=assistant&order=desc&limit=1",
                       timeout=POLL_TIMEOUT) or [None])[0]
    tool = None
    if isinstance(newest, dict):
        tools = [c for c in newest.get("content") or [] if isinstance(c, dict) and c.get("type") == "tool"]
        if tools:
            tool = {"name": tools[-1].get("name"), "status": (tools[-1].get("state") or {}).get("status")}
    times = (newest or {}).get("time") or {}
    last = max((v for v in times.values() if isinstance(v, (int, float))), default=None)
    return {"last_activity": _iso_ms(last), "tool": tool, "tokens": info.get("tokens")}


def _in_tree(api, root_sid, sid, cache):
    """Whether `sid` is the run's session or one of its subagent sessions."""
    walked, current, found = [], sid, False
    for _ in range(8):
        if current == root_sid:
            found = True
            break
        if current in cache:
            found = cache[current]
            break
        walked.append(current)
        parent = (api.call("GET", f"/api/session/{current}", timeout=POLL_TIMEOUT) or {}).get("parentID")
        if not isinstance(parent, str) or not SESSION_ID.fullmatch(parent):
            break
        current = parent
    for item in walked:
        cache[item] = found
    return found


def _agent(api, agent, where, should_stop):
    """The agent as this server resolved it for the worktree: model and full ruleset.

    The server loads agents a moment after it starts listening (404 until then).
    """
    limit = time.time() + AGENT_READY
    while True:
        if should_stop():
            raise ValueError("Stopped or expired before the prompt")
        try:
            resolved = api.call("GET", f"/api/agent/{agent}?{where}", timeout=POLL_TIMEOUT)
            if isinstance(resolved, dict):
                return resolved
        except _NotFound:
            pass
        if time.time() >= limit:
            raise ValueError(f"OpenCode agent {agent} is not available for this worktree")
        time.sleep(0.25)


def _run_api(root, cid, job, data, config, protected, prompt, request, should_stop, state):
    """OpenCode 2: one private loopback server per job, the session driven over its API.

    The session carries the role's ruleset, so a resume or fork on a later
    server keeps it and every subagent inherits it. A rule that resolves to
    `ask` — in the session or any of its subagents — reaches the caller as a
    pending request: the record turns `waiting` and the caller answers once or
    reject (never always: that would save an approval for every later session
    of the project). A live caller has no turn to answer in, so its requests
    are rejected on the spot. Completion is this turn's own idle outcome.
    """
    agent = OPENCODE_AGENTS[data["agent"]]
    record = root / (cid + ".json")
    answer_mode = request.get("answer_mode", "reject")
    where = "location%5Bdirectory%5D=" + urllib.parse.quote(data["directory"], safe="")

    def save(**fields):
        data.update(fields)
        dispatch._write(record, data)

    def bounded(cap=POLL_TIMEOUT):
        return max(1.0, min(cap, request["deadline"] - time.time()))

    def tail():
        return POLL_TIMEOUT if time.time() < request["deadline"] else TAIL_TIMEOUT

    with _Api(major=2) as api, contextlib.ExitStack() as cleanup:
        save(pgid=api.proc.pid)
        watchdog = _watch(api.proc.pid)
        # Stopped before the server is, so it can never signal a reused PID.
        cleanup.callback(lambda: (watchdog.kill(), watchdog.wait()))
        resolved = _agent(api, agent, where, should_stop)
        model, variant = _model(data, config)
        if not model:
            # An agent's own model is not applied to a session it runs (2.0.23).
            pin = resolved.get("model") or {}
            if isinstance(pin.get("providerID"), str) and isinstance(pin.get("id"), str):
                model = pin["providerID"] + "/" + pin["id"]
                variant = pin.get("variant") if pin.get("variant") not in (None, "", "default") else None
        if not model or not MODEL_NAME.fullmatch(model) or (variant and not VARIANT_NAME.fullmatch(variant)):
            raise ValueError(f"OpenCode 2 needs a model: agent {agent} pins none and none is configured")
        provider, _, model_id = model.partition("/")
        ref = {"providerID": provider, "id": model_id, **({"variant": variant} if variant else {})}
        resolved_rules = resolved.get("permissions")
        # A person's hard denies must be restated; a ruleset we cannot read would
        # silently drop them under build's `shell *` allow, so it stops the run.
        if not isinstance(resolved_rules, list) or not resolved_rules or not all(
                isinstance(r, dict) and all(isinstance(r.get(k), str) for k in ("action", "resource", "effect"))
                for r in resolved_rules):
            raise ValueError(f"OpenCode returned no readable ruleset for agent {agent}; no run launched")
        denies = [r for r in resolved_rules if r["effect"] == "deny"]
        rules = _rules(data["agent"], data.get("issue_approval"), protected, denies)
        sid = data.get("session_id")
        resumed = bool(sid)
        if sid:
            if not SESSION_ID.fullmatch(sid):
                raise ValueError("Invalid saved OpenCode session identity")
            if data.get("fork"):
                forked = (api.call("POST", f"/api/session/{sid}/fork", {}, timeout=bounded(SETUP_TIMEOUT)) or {}).get("id")
                if forked == sid:
                    raise ValueError("OpenCode fork returned the source session")
                sid = forked
        else:
            sid = (api.call("POST", "/api/session", {
                "agent": agent, "model": ref, "permissions": rules,
                "location": {"directory": data["directory"]}}, timeout=bounded(SETUP_TIMEOUT)) or {}).get("id")
        if not isinstance(sid, str) or not SESSION_ID.fullmatch(sid):
            raise ValueError("OpenCode returned no valid session identity")
        info = api.call("GET", f"/api/session/{sid}", timeout=bounded(SETUP_TIMEOUT)) or {}
        where_session = (info.get("location") or {}).get("directory")
        if not where_session or Path(where_session).resolve() != Path(data["directory"]):
            raise ValueError("OpenCode session belongs to another directory")
        save(session_id=sid)
        if resumed:
            # Reapplied every turn: the role, the grants, the engine or the policy
            # may have changed since the session's last turn (plan -> build).
            api.call("PATCH", f"/api/session/{sid}", {"permissions": rules}, timeout=bounded(SETUP_TIMEOUT))
            api.call("POST", f"/api/session/{sid}/agent", {"agent": agent}, timeout=bounded(SETUP_TIMEOUT))
            api.call("POST", f"/api/session/{sid}/model", {"model": ref}, timeout=bounded(SETUP_TIMEOUT))
            info = api.call("GET", f"/api/session/{sid}", timeout=bounded(SETUP_TIMEOUT)) or {}
        current = info.get("model") or {}
        if info.get("permissions") != rules or info.get("agent") != agent or (
                current.get("providerID"), current.get("id")) != (provider, model_id) or (
                variant and current.get("variant") != variant):
            raise ValueError("OpenCode session did not take the role's agent, model and permissions")
        if should_stop():
            raise ValueError("Stopped or expired before the prompt")
        state["launched"] = True
        turn = api.call("POST", f"/api/session/{sid}/prompt", {"text": prompt}, timeout=bounded(SETUP_TIMEOUT)) or {}
        started = (turn.get("time") or {}).get("created")
        bound = isinstance(turn.get("id"), str) and turn["id"].startswith("msg_") and isinstance(started, (int, float))
        outcome = {}

        def wait():
            try:
                api.call("POST", f"/api/experimental/session/{sid}/wait", {},
                         timeout=max(1.0, request["deadline"] - time.time() + 30))
                outcome["idle"] = True
            except Exception as exc:  # reported through the status below
                outcome["error"] = exc

        waiter = threading.Thread(target=wait, daemon=True)
        waiter.start()
        pending, owners, handled, replies, tree = {}, {}, set(), [], {sid: True}
        stopped = False
        next_progress = 0.0
        try:
            while waiter.is_alive():
                if should_stop():
                    stopped = True
                    break
                if api.proc.poll() is not None:
                    break
                live = {}
                # Subagents' requests are listed per location, not on the parent session.
                listing = api.call("GET", f"/api/permission/request?{where}", timeout=bounded()) or []
                for item in listing:
                    if not isinstance(item, dict) or not PERMISSION_ID.fullmatch(str(item.get("id"))):
                        continue
                    owner_sid = item.get("sessionID")
                    if isinstance(owner_sid, str) and SESSION_ID.fullmatch(owner_sid) \
                            and _in_tree(api, sid, owner_sid, tree):
                        live[item["id"]] = item
                for pid, item in live.items():
                    if pid in handled or pid in pending:
                        continue
                    owners[pid] = item["sessionID"]
                    view = {"id": pid, "action": str(item.get("action"))[:64],
                            "resources": [str(r)[:500] for r in (item.get("resources") or [])][:20],
                            **({"from": "subagent"} if item["sessionID"] != sid else {})}
                    if answer_mode == "caller":
                        pending[pid] = view
                        continue
                    api.call("POST", f"/api/session/{owners[pid]}/permission/{pid}/reply",
                             {"decision": "reject", "message": NO_APPROVER}, timeout=bounded())
                    handled.add(pid)
                    replies.append({**view, "decision": "reject", "by": "runner"})
                consumed = []
                for path in root.glob(job + ".per_*.answer"):
                    pid = path.name[len(job) + 1:-len(".answer")]
                    answer = dispatch._read(path)
                    # Removed only after the record shows the answer, so a caller's
                    # wait never sees an answered request as still pending.
                    consumed.append(path)
                    if pid not in pending or pid not in live or answer.get("decision") not in DECISIONS:
                        continue
                    message = answer.get("message") or (REJECTED if answer["decision"] == "reject" else None)
                    api.call("POST", f"/api/session/{owners[pid]}/permission/{pid}/reply",
                             {"decision": answer["decision"], **({"message": message} if message else {})},
                             timeout=bounded())
                    handled.add(pid)
                    replies.append({**pending.pop(pid), "decision": answer["decision"], "by": "caller"})
                for pid in [pid for pid in pending if pid not in live]:
                    # Answered elsewhere, e.g. by a person who opened the session.
                    handled.add(pid)
                    replies.append({**pending.pop(pid), "decision": "answered elsewhere", "by": "other"})
                status = "waiting" if pending else "running"
                now = time.time()
                if (status != data["status"] or list(pending.values()) != data.get("pending", [])
                        or replies != data.get("replies", []) or now >= next_progress):
                    fields = {"status": status, "pending": list(pending.values()), "replies": list(replies)}
                    if now >= next_progress:
                        with contextlib.suppress(Exception):
                            fields["progress"] = _progress(api, sid)
                        next_progress = now + PROGRESS_EVERY
                    save(**fields)
                for path in consumed:
                    path.unlink(missing_ok=True)
                waiter.join(1.0)
        finally:
            if not outcome.get("idle"):
                # Any exit short of an idle turn ends the turn's tools first.
                with contextlib.suppress(Exception):
                    api.call("POST", f"/api/session/{sid}/interrupt", {}, timeout=tail())
                waiter.join(tail())
            for path in root.glob(job + ".per_*.answer"):
                path.unlink(missing_ok=True)
        messages = api.call("GET", f"/api/session/{sid}/message?order=desc&limit=200", timeout=tail()) or []
        turn_messages = [m for m in messages if isinstance(m, dict) and bound
                         and ((m.get("time") or {}).get("created") or 0) >= started]
        idle = next((m for m in turn_messages if m.get("type") == "idle"), None)
        if idle is None and outcome.get("idle"):
            # `wait` returned, yet this turn never went idle: it may still be running.
            with contextlib.suppress(Exception):
                api.call("POST", f"/api/session/{sid}/interrupt", {}, timeout=tail())
        steps = [m for m in turn_messages if m.get("type") == "assistant"]
        reply = next((text for m in steps if (text := _text(m))), "")
        denied = []
        for message in reversed(steps):
            for c in message.get("content") or []:
                error = (c.get("state") or {}).get("error") if isinstance(c, dict) else None
                if isinstance(error, dict) and error.get("type") == "permission.rejected":
                    denied.append({"tool": c.get("name"),
                                   "input": json.dumps((c.get("state") or {}).get("input"))[:300]})
        changes, changes_error = None, None
        if bound:
            try:
                files = api.call("GET", f"/api/session/{sid}/diff?from={turn['id']}&context=3",
                                 timeout=tail()) or []
                with open(root / (job + ".diff"), "x", encoding="utf-8") as stream:
                    os.chmod(stream.name, 0o600)
                    stream.write("".join(str(f.get("patch") or "") for f in files)[:MAX_LOG])
                changes = [{k: f.get(k) for k in ("file", "status", "additions", "deletions")} for f in files[:200]]
            except Exception as exc:
                changes_error = f"{type(exc).__name__}: changes unknown; inspect Git"
        with open(root / (job + ".events"), "x", encoding="utf-8") as log:
            os.chmod(log.name, 0o600)
            log.write("\n".join(json.dumps(m) for m in reversed(turn_messages))[:MAX_LOG])
        info = {}
        with contextlib.suppress(Exception):
            info = api.call("GET", f"/api/session/{sid}", timeout=tail()) or {}
    data.update(result=reply, denied=denied[:50], changes=changes, replies=replies,
                progress={**(data.get("progress") or {}), "tokens": info.get("tokens")})
    if changes_error:
        data["changes_error"] = changes_error
    result = (idle or {}).get("outcome")
    if stopped or not bound or "error" in outcome or not outcome.get("idle") or result == "interrupted":
        data.update(status="unknown", error="Completion not confirmed; inspect effects (see changes) before reconciliation")
    elif result == "failed":
        data.update(status="failed", error="OpenCode reported a failed turn; partial effects may exist")
    elif result == "succeeded":
        data.update(status="completed", error="")
    else:
        data.update(status="unknown", error="OpenCode reported no outcome for this turn; inspect effects before reconciliation")


def opencode_call(args, **kwargs):
    try:
        allowed = {"directory", "agent", "message", "conversation_id", "fork", "approval", "issue_approval",
                   "model", "variant"}
        if set(args) - allowed:
            raise ValueError("Unexpected arguments; identity, executable and permissions are runtime-owned")
        home, owner, live = _scope()
        if os.environ.get("RESIDENT_TURN_KIND") == "reconcile":
            raise ValueError("This resident turn is reconcile-only; inspect and reconcile, never execute OpenCode")
        config, root = _config(home), _root(home)
        agent, message = args.get("agent"), args.get("message")
        if agent not in AGENTS or not isinstance(message, str) or not message.strip() or len(message) > 100000:
            raise ValueError("An allowed agent and a nonempty message of at most 100000 characters are required")
        selection = _selection(args, config)
        if "fork" in args and type(args["fork"]) is not bool:
            raise ValueError("fork must be boolean")
        for key in ("approval", "issue_approval"):
            if key in args and (not isinstance(args[key], str) or not args[key].strip()):
                raise ValueError(f"{key} must quote the Client's scoped approval, never a boolean")
        # One short registry transaction prevents concurrent new conversations
        # from entering the same worktree before their individual runners start.
        with dispatch._locked(root, "0" * 32):
            source = None
            if args.get("conversation_id"):
                source = dispatch._owned(root, args["conversation_id"], owner)
                if source["status"] in BUSY or _group_alive(source.get("pgid")):
                    raise ValueError("Conversation is active or uncertain; inspect/stop/reconcile, never retry")
            elif args.get("fork"):
                raise ValueError("fork requires an owned conversation_id")
            directory = _worktree(args.get("directory") or (source or {}).get("directory"))
            if source and directory != source["directory"]:
                raise ValueError("A conversation cannot move to another worktree")
            cid = source["conversation_id"] if source and not args.get("fork") else uuid.uuid4().hex
            for path in root.glob("*.json"):
                other = dispatch._read(path)
                if other["directory"] == directory and other["status"] in BUSY:
                    raise ValueError("Worktree has active or uncertain OpenCode work")
            with dispatch._locked(root, cid):
                data = dict(source or {})
                for key in TURN_FIELDS:
                    data.pop(key, None)
                data.update(conversation_id=cid, directory=directory, owner=owner, agent=agent,
                            fork=bool(args.get("fork")))
                for key in ("approval", "issue_approval"):
                    if key in args:
                        data[key] = args[key]
                # An explicit selection binds this and later turns of the conversation;
                # an omitted one keeps the conversation's recorded engine.
                data.update(selection)
                if agent == "build" and not data.get("approval"):
                    raise ValueError("Build requires the Client's explicit implementation approval")
                branch, _ = _branch(directory, agent == "build")
                if source and branch != source["branch"]:
                    raise ValueError("Worktree branch changed; release a new conversation after inspection")
                job = uuid.uuid4().hex
                deadline = min(time.time() + config.get("timeout", 3600),
                               float(os.environ.get("RESIDENT_DEADLINE", "inf")))
                if deadline <= time.time():
                    raise ValueError("Inherited execution deadline expired")
                # A blocking caller answers permission requests between its own tool
                # calls; a live (background, notify-on-complete) caller cannot.
                request = dict(home=str(home), owner=owner, conversation_id=cid, job_id=job,
                               message=message, deadline=deadline, parent_pid=None if live else os.getpid(),
                               answer_mode="reject" if live else "caller")
                data.update(job_id=job, branch=branch, status="accepted", result="", error="", pgid=None,
                            log=str(root / (job + ".events")), updated_at=time.time(),
                            request_digest=hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest())
                dispatch._write(root / (job + ".request"), request)
                dispatch._write(root / (cid + ".json"), data)
        request_path = root / (job + ".request")
        command = dispatch.runner_command(Path(__file__).resolve(), request_path)
        if live:
            from tools.terminal_tool import terminal_tool
            try:
                launch = json.loads(terminal_tool(command=shlex.join(command), background=True,
                    notify_on_complete=True, task_id=kwargs.get("task_id"), _host_local=True))
            except Exception:
                launch = {"error": "Launch outcome unknown"}
            dispatch._write(root / (job + ".receipt"), launch)
            if not launch.get("session_id"):
                try:
                    with dispatch._locked(root, cid):
                        data = dispatch._owned(root, cid, owner)
                        if data["job_id"] == job and data["status"] == "accepted":
                            data.update(status="unknown", error="Launch outcome unknown; inspect before reconciliation")
                            dispatch._write(root / (cid + ".json"), data)
                except ValueError:
                    # A running child owns the lock; a lost launch receipt must
                    # not overwrite it or hide its conversation handle.
                    pass
            return json.dumps({**_public(dispatch._owned(root, cid, owner)),
                               "process_session_id": launch.get("session_id")})
        try:
            proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, start_new_session=True)
        except OSError:
            with dispatch._locked(root, cid):
                data = dispatch._owned(root, cid, owner)
                data.update(status="failed", error="Runner could not be launched; no OpenCode process started")
                dispatch._write(root / (cid + ".json"), data)
            return json.dumps(_public(data))
        limit = time.time() + config.get("timeout", 3600) + 15
        try:
            while proc.poll() is None:
                if time.time() >= limit:
                    raise subprocess.TimeoutExpired(command, config.get("timeout", 3600) + 15)
                data = dispatch._owned(root, cid, owner)
                if data["job_id"] == job and data["status"] == "waiting":
                    # The runner keeps the run paused, within its deadline, for this caller.
                    dispatch._reap_later(proc)
                    return json.dumps({**_public(data), "note": WAITING_NOTE})
                time.sleep(0.25)
        except subprocess.TimeoutExpired:
            dispatch._write(root / (job + ".stop"), {"requested_at": time.time()})
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                return json.dumps({**_public(dispatch._owned(root, cid, owner)), "stop_requested": True,
                                   "error": "Runner has not confirmed termination; do not retry"})
        data = dispatch._owned(root, cid, owner)
        if data["status"] in {"accepted", "running", "waiting"}:
            with dispatch._locked(root, cid):
                data.update(status="unknown", error="Runner exited without confirming completion")
                dispatch._write(root / (cid + ".json"), data)
        return json.dumps(_public(data))
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def _wait(root, cid, owner, data, requested, home):
    """Block until the owned run leaves BUSY, or a bounded deadline passes.

    The runner owns the record; this only reads it. It is the cheap alternative
    to a status/sleep polling loop: no model turn is spent while waiting.
    """
    if requested is not None and (type(requested) is not int or requested < 1):
        raise ValueError("timeout must be a positive integer number of seconds")
    limit = time.time() + float(requested if requested is not None else DEFAULT_WAIT_TIMEOUT)
    with contextlib.suppress(ValueError):
        limit = min(limit, time.time() + _config(home).get("wait_timeout", DEFAULT_WAIT_TIMEOUT))
    with contextlib.suppress(ValueError, TypeError):
        limit = min(limit, float(os.environ.get("RESIDENT_DEADLINE", "inf")))
    request_path = root / (data["job_id"] + ".request")
    with contextlib.suppress(OSError, ValueError, KeyError, TypeError):
        # The runner reaps its child within seconds of the job deadline.
        limit = min(limit, float(dispatch._read(request_path)["deadline"]) + 30)
    started = time.time()
    dead_since = None
    while True:
        data = dispatch._owned(root, cid, owner)
        # `unknown` is the runner's own verdict once its group is gone; only an
        # unfinalized record (or a still-live group) is worth waiting on. A
        # `waiting` record whose requests are all answered is about to resume.
        if data["status"] not in {"accepted", "running"} and not (
                data["status"] == "unknown" and data.get("pgid") and _group_alive(data["pgid"])) and not (
                data["status"] == "waiting" and not _unanswered(root, data)):
            timed_out = False
            break
        now = time.time()
        if now >= limit:
            timed_out = True
            break
        if data.get("pgid") and not _group_alive(data["pgid"]):
            # Process gone but record not finalized: give the runner a moment to
            # write its verdict, then return the record rather than hang.
            dead_since = dead_since or now
            if now - dead_since > 15:
                timed_out = False
                break
        else:
            dead_since = None
        time.sleep(min(WAIT_POLL, max(0.0, limit - now)))
    runner_gone = data.get("pgid") and not _group_alive(data["pgid"])
    note = (WAITING_NOTE if data["status"] == "waiting" and not runner_gone else
            "Still active or uncertain; inspect, wait again, stop, or reconcile. Never retry.")
    return {**_public(data), "waited_seconds": round(time.time() - started, 1), "timed_out": timed_out,
            **({"note": note} if data["status"] in BUSY else {})}


def _unanswered(root, data):
    return [p for p in data.get("pending") or []
            if not (root / f"{data['job_id']}.{p['id']}.answer").exists()]


def opencode_session(args, **kwargs):
    try:
        if set(args) - {"action", "conversation_id", "evidence", "timeout", "permission_id", "decision", "message"}:
            raise ValueError("Unexpected arguments")
        if "timeout" in args and args.get("action") != "wait":
            raise ValueError("timeout is only accepted for wait")
        if {"permission_id", "decision", "message"} & set(args) and args.get("action") != "answer":
            raise ValueError("permission_id, decision and message are only accepted for answer")
        home, owner, _ = _scope()
        # Disabling new execution must not remove the owner's ability to inspect
        # or stop a run already in flight.
        root = _root(home)
        action = args.get("action")
        if action == "list":
            return json.dumps([_public(data) for path in root.glob("*.json")
                               if (data := dispatch._read(path))["owner"] == owner])
        cid = dispatch._id(args.get("conversation_id"))
        data = dispatch._owned(root, cid, owner)
        if action == "status":
            return json.dumps(_public(data))
        if action == "wait":
            return json.dumps(_wait(root, cid, owner, data, args.get("timeout"), home))
        if action == "stop":
            if data["status"] not in BUSY:
                raise ValueError("No active or uncertain run to stop")
            dispatch._write(root / (data["job_id"] + ".stop"), {"requested_at": time.time()})
            return json.dumps({**_public(data), "stop_requested": True,
                               "note": "Request recorded; not proof of termination or rollback"})
        if action == "answer":
            pid, decision, message = args.get("permission_id"), args.get("decision"), args.get("message")
            if decision not in DECISIONS:
                # `always` would save an approval that every later session of the
                # project inherits, including people's own.
                raise ValueError("decision must be once or reject; a saved approval is never given")
            if message is not None and (not isinstance(message, str) or len(message) > 2000):
                raise ValueError("message must be text of at most 2000 characters")
            if data["status"] != "waiting" or not any(p["id"] == pid for p in _unanswered(root, data)):
                raise ValueError("No such unanswered permission request on this run")
            dispatch._write(root / f"{data['job_id']}.{pid}.answer",
                            {"decision": decision, **({"message": message} if message else {})})
            return json.dumps({**_public(data), "answer_recorded": True,
                               "note": "Recorded for the runner, not yet applied: wait, then check replies "
                                       "(an answer the run no longer needed is not listed there)."})
        if action != "reconcile" or not isinstance(args.get("evidence"), str) or not args["evidence"].strip():
            raise ValueError("Use status/list/wait/stop/answer, or reconcile with observed process/Git/remote-effect evidence")
        with dispatch._locked(root, cid):
            data = dispatch._owned(root, cid, owner)
            if data["status"] not in BUSY or _group_alive(data.get("pgid")):
                raise ValueError("Reconcile only uncertain/inactive work after its process group has stopped")
            data.update(status="reconciled", reconciliation=args["evidence"], updated_at=time.time())
            dispatch._write(root / (cid + ".json"), data)
        return json.dumps(_public(data))
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def opencode_history(args, **kwargs):
    try:
        # Same caller gate as execution (no inbound A2A), but no registry, grant
        # or opencode_cli.enabled: reading history launches no agent.
        _scope()
        return json.dumps(inventory.run(args), ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


HISTORY_DESCRIPTION = (
    "Read OpenCode session history across all projects (read-only; launches no agent). "
    "list: sessions overlapping [from, to) (created before to, last updated at or after from), newest first, "
    "paged by limit/offset; kind defaults to root. get / children: one session or its subagent sessions. "
    "usage: message-level tokens and activity for [from, to) grouped by group_by (default model); kind "
    "defaults to all. active_seconds = time assistant steps were running (model output plus tool execution), "
    "clipped to the window, minus question-tool waits; active_union_seconds = the same with parallel "
    "sessions' overlap removed; question_wait_seconds = time steps sat waiting on a person's answer. "
    "A tool held on a permission prompt still counts as active. None of these measure human working "
    "time. usage includes archived sessions unless archived is false. Tokens count steps started in the "
    "window; day groups by "
    "step start in timezone. Dates are YYYY-MM-DD at local midnight of timezone (default system); "
    "days=N is the last N local days ending today. "
    "Titles and costs are returned only when include_title / include_cost is true; message content never. "
    "Every result states its source (api or db), status (complete or partial) and diagnostics.")


def register(ctx):
    if ctx.profile_name not in PROFILES:
        return
    from hermes_constants import get_hermes_home
    identity = (ctx.profile_name, str(get_hermes_home().resolve()))

    def scoped(handler):
        def invoke(args, **kwargs):
            from gateway.session_context import scoped_current_session_id
            token = dispatch._REGISTRATION.set(identity)
            turn = dispatch._TURN_SESSION.set(kwargs.get("task_id") or "")
            try:
                with scoped_current_session_id(kwargs.get("session_id")):
                    return handler(args, **kwargs)
            finally:
                dispatch._TURN_SESSION.reset(turn)
                dispatch._REGISTRATION.reset(token)
        return invoke

    for name, handler, properties, required, description in (
        ("opencode_call", opencode_call, {
            "directory": {"type": "string"}, "agent": {"type": "string", "enum": sorted(AGENTS)},
            "message": {"type": "string"}, "conversation_id": {"type": "string"},
            "fork": {"type": "boolean"}, "approval": {"type": "string"}, "issue_approval": {"type": "string"},
            "model": {"type": "string", "description": "Optional provider/model from opencode_cli.allowed_models"},
            "variant": {"type": "string", "description": "Optional reasoning-effort variant from opencode_cli.allowed_variants"},
        }, ["agent", "message"],
         "Drive OpenCode in an owned Git worktree; blocks until the run finishes or pauses with status waiting "
         "on pending permission requests (answer them with opencode_session answer, then wait). On OpenCode 2 "
         "only plan and build run; ask build for review/diagnosis through its subagents. Build needs "
         "explicit Client implementation approval; Issue writes need separate explicit issue_approval. "
         "Completion is not acceptance; changes lists the files the turn touched. Never retry uncertain work. "
         "If the call returns a timeout error, use opencode_session wait, never a status loop."),
        ("opencode_session", opencode_session, {
            "action": {"type": "string", "enum": ["status", "list", "wait", "stop", "answer", "reconcile"]},
            "conversation_id": {"type": "string"}, "evidence": {"type": "string"},
            "timeout": {"type": "integer", "description": "wait only: seconds to block (bounded by config and turn deadline)"},
            "permission_id": {"type": "string", "description": "answer only: a pending request id (per_...)"},
            "decision": {"type": "string", "enum": list(DECISIONS), "description": "answer only"},
            "message": {"type": "string", "description": "answer only: reason or instruction shown to OpenCode"},
        }, ["action"], "Inspect, wait for, answer, or request stopping your OpenCode run. status shows progress "
         "(last activity, current tool, tokens) while it runs. wait blocks until the run finishes or pauses on a "
         "permission request, spending no turns. answer gives once or reject to a pending request; decide what "
         "is the Client's to decide with the Client. Stop never rolls back effects. "
         "Reconcile inactive uncertain work only after observing its process, Git and remote effects."),
        ("opencode_history", opencode_history, {
            "action": {"type": "string", "enum": list(inventory.ACTIONS)},
            "session_id": {"type": "string", "description": "get / children only"},
            "from": {"type": "string", "description": "YYYY-MM-DD or ISO 8601; usage needs from+to or days"},
            "to": {"type": "string", "description": "Exclusive end; YYYY-MM-DD or ISO 8601; required for usage"},
            "days": {"type": "integer", "description": "Instead of from/to: the last N local days ending today (1 = today)"},
            "timezone": {"type": "string", "description": "IANA name for dates and day groups"},
            "directory": {"type": "string", "description": "Absolute path; matches it and everything below"},
            "kind": {"type": "string", "enum": list(inventory.KINDS)},
            "agent": {"type": "string"}, "model": {"type": "string", "description": "provider/model or model"},
            "archived": {"type": "boolean", "description": "Include archived sessions"},
            "search": {"type": "string", "description": "list only: title substring"},
            "include_title": {"type": "boolean"}, "include_cost": {"type": "boolean"},
            "limit": {"type": "integer", "description": f"list only: 1..{inventory.MAX_LIMIT}"},
            "offset": {"type": "integer", "description": "list only"},
            "group_by": {"type": "array", "items": {"type": "string", "enum": list(inventory.GROUPS)},
                         "description": "usage only"},
            "source": {"type": "string", "enum": list(inventory.SOURCES),
                       "description": "auto (API, disclosed database fallback), api, or db"},
        }, ["action"], HISTORY_DESCRIPTION),
    ):
        ctx.register_tool(name=name, toolset="opencode", handler=scoped(handler), description=description,
                          schema={"name": name, "description": description, "parameters": {
                              "type": "object", "properties": properties, "required": required,
                              "additionalProperties": False}})


if __name__ == "__main__":
    outcome = _run(Path(sys.argv[1]))
    print(json.dumps(outcome))
    raise SystemExit(0 if outcome["status"] == "completed" else 1)
