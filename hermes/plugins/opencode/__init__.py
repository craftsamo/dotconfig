"""OpenCode 2 transport over the shared service's HTTP API; not a planner, approval authority, or sandbox."""

from __future__ import annotations

import contextlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import threading
import time
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

# The stdlib client for the shared OpenCode service, shared with the history reader.
_name = "hermes_opencode_api"
if _name not in sys.modules:
    _spec = importlib.util.spec_from_file_location(_name, Path(__file__).resolve().parent / "api.py")
    _module = importlib.util.module_from_spec(_spec)
    sys.modules[_name] = _module
    _spec.loader.exec_module(_module)
api = sys.modules[_name]

# Read-only session inventory. A stdlib-only sibling so cron scripts can run the
# same code as a CLI; it never touches the execution registry below.
_name = "hermes_opencode_history"
if _name not in sys.modules:
    _spec = importlib.util.spec_from_file_location(_name, Path(__file__).resolve().parent / "history.py")
    _module = importlib.util.module_from_spec(_spec)
    sys.modules[_name] = _module
    _spec.loader.exec_module(_module)
inventory = sys.modules[_name]

AGENTS = {"plan", "build", "review", "debug"}
# Hermes-facing role -> installed OpenCode agent: the hidden non-interactive
# primaries in ~/.config/opencode/agent/hermes-*.md. Every other decision in
# this module keys on the Hermes role, never on this name.
OPENCODE_AGENTS = {"plan": "hermes-plan", "build": "hermes-build", "review": "hermes-review",
                   "debug": "hermes-debug"}
READ_ONLY = {"plan", "review", "debug"}
# Profiles that may drive OpenCode, each with its own registry under its home.
PROFILES = {"engineer", "assistant"}
# `accepted` is set up under the conversation lock; `running` and `waiting`
# belong to the turn's watchdog; `unknown` means the service could not confirm.
BUSY = {"accepted", "running", "waiting", "unknown"}
ACTIVE = {"accepted", "running"}
DECISIONS = ("once", "reject")
SESSION_ID = re.compile(r"ses_[A-Za-z0-9_-]+\Z")
PERMISSION_ID = re.compile(r"per_[A-Za-z0-9_-]{1,64}\Z")
MODEL_NAME = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.:/-]+\Z")
VARIANT_NAME = re.compile(r"[A-Za-z0-9_-]{1,32}\Z")
PROVIDER_NAME = re.compile(r"[A-Za-z0-9_.-]+\Z")
# Speed tiers and dated snapshots serve the same weights as the plain model.
MODEL_ALIAS = re.compile(r"(?:-(?:fast|ultrafast)|-\d{8}|:free)+\Z")
# The main model each Hermes session last answered with (post_api_request), so a
# fallback model counts as the caller's own as well as the configured one.
CALLER_MODELS = {}
CALLER_MODELS_LIMIT = 512
DEFAULT_TIMEOUT = 3600
DEFAULT_WAIT_TIMEOUT = 3300
DEFAULT_PERMISSION_TIMEOUT = 900
DEFAULT_TOOL_TIMEOUT = 420
POLL = 2.0
WAIT_POLL = 1.0
# A turn that is neither running nor idle for this long ended without an
# outcome (the service restarted or crashed under it).
NO_OUTCOME_GRACE = 30
# After the deadline, how long the watchdog keeps trying an unreachable service.
UNREACHABLE_GRACE = 120
# After an interrupt, how long the watchdog waits for the turn's idle outcome
# before resending it, and how long in all before it records the run unknown.
HALT_GRACE = 30
HALT_LIMIT = 180
CATALOG_RETRY = 2.0
TURN_FIELDS = ("result", "error", "outcome", "pending", "changes", "tokens", "exit_code", "reconciliation",
               "stop_reason", "prompt_id", "prompt_time")
NO_DECISION = "No decision from Hermes within {seconds} s; continue without this action or report it."
PROJECT_WRITES = (
    "github_project_create", "github_project_field_ensure", "github_project_item_add",
    "github_project_item_set", "github_project_item_note", "github_project_item_promote",
    "github_project_view_ensure", "github_project_issue_link", "github_project_issue_develop",
)

# Policy split. Each hidden primary's own frontmatter owns its role posture
# (read-only or not, its shell allowlist, its subagents). This module owns the
# per-run constraints set as the session's ruleset. OpenCode appends session
# rules after global and agent rules (last match wins), and every subagent
# session copies its parent's ruleset (measured on 2.0.23). So the ruleset
# below holds only denies, asks and narrow allows: a broad allow here would
# reopen what a subagent's own posture denies (an explore subagent could edit).
#
# V2 wildcards match whole values and `*` crosses `/`, so `**/.env` misses a
# root-level `.env`; secrets are spelled `*.env`.
SECRET_READS = ("*.env", "*.env.*", "*.envrc", "*.pem", "*.key", "*.npmrc", "*.netrc", "*.ssh/*")
SAMPLE_READS = ("*.env.example", "*.env.sample")
# `git diff/log/show --output=<file>` writes a file.
READ_ONLY_DENY_SHELL = ("git * --output*",)
# Build's history rewrites, pushes, branch moves and package runners come back
# to the caller as permission requests. `git -C`/`-c` put options before the
# subcommand, so no `git push *` pattern sees them.
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
ISSUE_WRITES = tuple(f"gh issue {verb} *" for verb in ("create", "edit", "comment", "reopen"))
# Never, for any role or subagent: the caller cannot approve these either.
HARD_DENY_SHELL = (
    "gh pr merge *", "gh repo create *", "gh repo delete *", "gh repo edit *", "gh api *",
    "gh project *", "gh issue delete *", "gh issue close *", "gh auth *", "gh secret *",
    "npm publish *", "pnpm publish *", "git config *",
    "git push *--force*", "git push -f*", "git push * -f*", "git push * +*", "git push *--mirror*",
    "git push *--all*", "git push *--delete*", "git push * :*",
    "git reset *--hard*", "git clean *-*f*",
)


def _rule(action, resource, effect):
    return {"action": action, "resource": resource, "effect": effect}


def _directories(tmp):
    """OpenCode's own scratch dirs, and the read-only config/skill dirs the
    person's global config opens. A session-level `external_directory: *` would
    shadow OpenCode's defaults for them, so they are re-allowed after it."""
    data = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share") / "opencode"
    config = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "opencode"
    scratch = [f"{data}/tool-output/*", f"{data}/shell/*/*"]
    for path in {tmp, str(Path(tmp).resolve())} if tmp else ():
        scratch.append(f"{path}/*")
    readable = [f"{config}/*", f"{Path.home()}/.agents/skills/*", f"{Path.home()}/.claude/skills/*"]
    return scratch, readable


def _rules(role, issue_approval, protected, *, tmp=None, person_denies=()):
    """The session ruleset: one run's constraints for its whole session tree, ordered
    broad to narrow under last-match evaluation. It holds no caller-granted allow:
    any allow here would be copied into every subagent session and evaluated after
    that subagent's own denies."""
    person = [d for d in person_denies if d.get("effect") == "deny"]
    scratch, readable = _directories(tmp)
    rules = [_rule("external_directory", "*", "ask")]
    # The person's own outside-path denies stay denies, not asks the caller could approve.
    rules += [_rule("external_directory", d["resource"], "deny") for d in person
              if d.get("action") == "external_directory"]
    rules += [_rule("external_directory", path, "allow") for path in scratch + readable]
    rules += [_rule("edit", path, "deny") for path in readable]
    rules.append(_rule("question", "*", "deny"))
    rules += [_rule("read", pattern, "deny") for pattern in SECRET_READS]
    rules += [_rule("read", pattern, "allow") for pattern in SAMPLE_READS]
    if role == "plan":
        # Plan leaves the tree as it found it, subagents included.
        rules.append(_rule("edit", "*", "deny"))
    if role in READ_ONLY:
        rules += [_rule("shell", pattern, "deny") for pattern in READ_ONLY_DENY_SHELL + ISSUE_WRITES]
    else:
        rules += [_rule("shell", pattern, "ask") for pattern in BUILD_ASK_SHELL]
        rules += [_rule("shell", pattern, "allow") for pattern in BUILD_ALLOW_AFTER_ASK]
        if not issue_approval:
            rules += [_rule("shell", pattern, "ask") for pattern in ISSUE_WRITES]
    deny = list(HARD_DENY_SHELL)
    for branch in sorted(protected):
        deny += [f"git push * {branch}", f"git push * {branch} *", f"git push *:{branch}*",
                 f"git push *:refs/heads/{branch}*", f"git push * refs/heads/{branch}",
                 f"git push * refs/heads/{branch} *"]
    # The same denies when `-C <dir>` / `-c <k=v>` precede the subcommand. Not a
    # bare `git * push`: that would also match a commit message saying "push".
    deny += [f"git {option} * " + pattern[len("git "):] for option in ("-C", "-c") for pattern in deny
             if pattern.startswith(("git push ", "git reset ", "git clean ", "git config "))]
    rules += [_rule("shell", pattern, "deny") for pattern in deny]
    rules += [_rule(name, "*", "deny") for name in PROJECT_WRITES]
    # A person's own denies are re-stated last, so an agent's broad allow (build's
    # `shell: *`) never reopens `sudo` or `secret get`. Their `external_directory`
    # denies went in above the scratch-dir allows instead.
    rules += [_rule(d["action"], d["resource"], "deny") for d in person
              if d.get("action") != "external_directory"]
    return rules


def _matches(pattern, value, shell=False):
    regex = "".join(".*" if c == "*" else "." if c == "?" else re.escape(c) for c in pattern)
    if re.fullmatch(regex, value, re.S):
        return True
    return shell and pattern.endswith(" *") and value == pattern[:-2]


def _decide(rules, action, resource):
    """OpenCode's evaluation: the last rule whose action and resource match wins;
    with none, ask."""
    effect = "ask"
    for rule in rules:
        if _matches(rule["action"], action) and _matches(rule["resource"], resource, action == "shell"):
            effect = rule["effect"]
    return effect


def _check_agent(role, info, rules):
    """The installed agent must be the hidden primary this role expects; a read-only
    role must stay read-only under the combined ruleset."""
    name = OPENCODE_AGENTS[role]
    if not isinstance(info, dict) or info.get("id") != name or info.get("mode") != "primary" \
            or info.get("hidden") is not True:
        raise ValueError(f"OpenCode agent {name} is not the installed hidden primary")
    combined = (info.get("permissions") or []) + rules
    if role in READ_ONLY:
        for action, resource in (("edit", "src/probe.py"), ("shell", "touch probe"), ("subagent", "worker")):
            if _decide(combined, action, resource) != "deny":
                raise ValueError(f"OpenCode agent {name} is no longer read-only ({action}); no run launched")


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


def _yaml(home):
    return yaml.safe_load((home / "config.yaml").read_text()) or {}


def _config(home):
    config = _yaml(home).get("opencode_cli") or {}
    if not isinstance(config, dict) or config.get("enabled") is not True:
        raise ValueError("OpenCode CLI integration is not enabled")
    for key, default in (("timeout", DEFAULT_TIMEOUT), ("wait_timeout", DEFAULT_WAIT_TIMEOUT),
                         ("permission_timeout", DEFAULT_PERMISSION_TIMEOUT)):
        value = config.get(key, default)
        if type(value) is not int or not 1 <= value <= 5400:
            raise ValueError(f"opencode_cli.{key} must be 1..5400 seconds")
    for key in ("allowed_models", "allowed_variants"):
        if key in config:
            raise ValueError(f"opencode_cli.{key} was replaced by allowed_providers; update the profile config")
    values = config.get("allowed_providers", [])
    if not isinstance(values, list) or not all(isinstance(v, str) and PROVIDER_NAME.fullmatch(v) for v in values):
        raise ValueError("opencode_cli.allowed_providers must be a list of provider names")
    models = config.get("models") or {}
    if not isinstance(models, dict) or set(models) - AGENTS or \
            not all(isinstance(v, str) and _pinned(v) for v in models.values()):
        raise ValueError("opencode_cli.models maps plan/build/review/debug to provider/model or provider/model#variant")
    return config


def _pinned(value):
    """A configured provider/model[#variant], or None when malformed."""
    model, _, variant = value.partition("#")
    if not MODEL_NAME.fullmatch(model) or ("#" in value and not VARIANT_NAME.fullmatch(variant)):
        return None
    return model, variant or None


def _model_key(name):
    """A model's identity across providers and speed tiers: anthropic/claude-opus-5-5,
    claude-opus-5-5-fast and a dated snapshot are one model."""
    return MODEL_ALIAS.sub("", str(name).rsplit("/", 1)[-1].lower())


def _observe(**payload):
    """post_api_request: remember which main model this Hermes session runs on now."""
    session, model = payload.get("session_id"), payload.get("model")
    if isinstance(session, str) and session and isinstance(model, str) and model:
        CALLER_MODELS.pop(session, None)
        CALLER_MODELS[session] = model
        while len(CALLER_MODELS) > CALLER_MODELS_LIMIT:
            CALLER_MODELS.pop(next(iter(CALLER_MODELS)), None)


def _caller_models(home, session):
    """The caller's own models: the configured main model and the one it last answered with."""
    names = set()
    with contextlib.suppress(Exception):
        names.add((_yaml(home).get("model") or {}).get("default"))
    names.add(CALLER_MODELS.get(session or ""))
    return {_model_key(name) for name in names if isinstance(name, str) and name}


def _setting(home, key, default):
    with contextlib.suppress(Exception):
        value = (_yaml(home).get("opencode_cli") or {}).get(key, default)
        if type(value) is int and value > 0:
            return value
    return default


def _selection(args, config):
    """Caller-requested model/variant: any model of an allowed provider; the model
    and its variant are checked against the service's catalog at setup.

    A request outside the allowed providers is refused rather than silently
    replaced: the caller asked for a specific engine, and running another one
    would return a result that is not the one asked for.
    """
    selection = {}
    for key, pattern in (("model", MODEL_NAME), ("variant", VARIANT_NAME)):
        value = args.get(key)
        if value is None:
            continue
        if not isinstance(value, str) or not pattern.fullmatch(value):
            raise ValueError(f"{key} must be a plain name" + (" in provider/model form" if key == "model" else ""))
        if key == "model" and value.split("/", 1)[0] not in config.get("allowed_providers", []):
            raise ValueError(f"model {value!r} is not from opencode_cli.allowed_providers "
                             f"{config.get('allowed_providers', [])}; pick one from opencode_session models")
        selection[key] = value
    if "variant" in selection and "model" not in selection and not (config.get("models") or {}).get(args.get("agent")):
        # A variant is provider-specific reasoning effort; it binds to a model the
        # caller or the maintainer chose, never to whatever the agent pins.
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


# --------------------------------------------------------------------------
# Server access


def _call(method, template, data=None, query=None, **segments):
    return api.call(method, api.path(template, query, **segments), data)


def _session_info(sid):
    return api.data(_call("get", "/api/session/{sid}", sid=sid))


def _active():
    return api.data(_call("get", "/api/session/active"))


def _same_dir(a, b):
    with contextlib.suppress(OSError, TypeError):
        return os.path.realpath(a) == os.path.realpath(b)
    return False


def _running_in(directory, exclude=()):
    """Session ids the service is running in this worktree, from any profile or person."""
    found = []
    for sid in _active():
        if sid in exclude:
            continue
        with contextlib.suppress(api.ApiError):
            if _same_dir((_session_info(sid).get("location") or {}).get("directory"), directory):
                found.append(sid)
    return found


def _in_tree(root_sid, sid, cache):
    """Whether `sid` is the run's root session or one of its subagent sessions."""
    chain = []
    current = sid
    for _ in range(16):
        if current == root_sid or cache.get(current) is True:
            cache.update(dict.fromkeys(chain + [sid], True))
            return True
        if current is None or cache.get(current) is False:
            break
        chain.append(current)
        try:
            current = _session_info(current).get("parentID")
        except api.ApiError:
            break
    cache.update(dict.fromkeys(chain, False))
    return False


def _pending(data, cache):
    requests = api.data(_call("get", "/api/permission/request", query=api.location(data["directory"])), list)
    out = []
    for item in requests:
        sid = item.get("sessionID")
        if isinstance(sid, str) and _in_tree(data["session_id"], sid, cache):
            out.append({"id": item.get("id"), "session_id": sid, "subagent": sid != data["session_id"],
                        "action": item.get("action"), "resources": item.get("resources") or [],
                        "save": item.get("save") or [], "message": item.get("message")})
    return out


def _text(message):
    return "\n".join(part["text"] for part in message.get("content") or []
                     if part.get("type") == "text" and isinstance(part.get("text"), str))


def _result(data):
    """The turn's reply: the newest assistant message with text after the prompt."""
    body = _call("get", "/api/session/{sid}/message", query={"order": "desc", "limit": 100},
                 sid=data["session_id"])
    for message in api.data(body, list):
        if message.get("id") == data.get("prompt_id"):
            break
        if message.get("type") == "assistant" and _text(message):
            return _text(message)
    return ""


def _changes(data):
    body = _call("get", "/api/session/{sid}/diff", query={"from": data.get("prompt_id")}, sid=data["session_id"])
    items = body.get("data") if isinstance(body, dict) else body
    return [{key: item.get(key) for key in ("file", "status", "additions", "deletions")}
            for item in (items or [])[:200] if isinstance(item, dict)]


def _halt(data):
    """Interrupt the run (subagent sessions stop with it) and drop parked input."""
    with contextlib.suppress(api.ApiError):
        _call("post", "/api/session/{sid}/interrupt", sid=data["session_id"])
    with contextlib.suppress(api.ApiError, api.Unavailable):
        for item in api.data(_call("get", "/api/session/{sid}/inbox", sid=data["session_id"]), list):
            with contextlib.suppress(api.ApiError):
                _call("delete", "/api/session/{sid}/inbox/{inbox}", sid=data["session_id"], inbox=item["id"])


# --------------------------------------------------------------------------
# Registry


def _public(data):
    keys = ("conversation_id", "job_id", "directory", "branch", "agent", "model", "variant", "engine", "status",
            "session_id", "result", "error", "outcome", "pending", "changes", "tokens", "updated_at",
            "reconciliation", "stop_reason")
    out = {key: data[key] for key in keys if key in data and data[key] not in (None, [])}
    if data.get("transport") != "api" and "log" in data:
        out["log"] = data["log"]
    return out


def _side(root, name):
    path = root / name
    try:
        return dispatch._read(path)
    except (OSError, ValueError):
        return None


def _answered(root, job):
    return set(_side(root, job + ".answered") or [])


def _watched(root, cid):
    """Whether a live watchdog holds the conversation lock (the OS drops it on death)."""
    with dispatch._try_locked(root, cid) as held:
        return not held


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


def _caller_alive(data):
    """A blocking (CLI/resident) caller's run ends with its process, as a resident
    turn's children must; a live gateway caller records none."""
    pid = data.get("caller_pid")
    if not pid:
        return True
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _handback(root, data):
    """Whether the run is the caller's to act on: finished, uncertain, or waiting
    on a request it has not answered yet."""
    if data["status"] in ACTIVE:
        return False
    if data["status"] == "waiting":
        return bool({p["id"] for p in data.get("pending") or []} - _answered(root, data["job_id"]))
    return True


def _spawn(home, cid, job):
    command = dispatch.runner_command(Path(__file__).resolve(), "watch", str(home), cid, job)
    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, start_new_session=True)
    threading.Thread(target=proc.wait, name="opencode-watchdog-reaper", daemon=True).start()


def _recover(home, root, data):
    """Start a watchdog for a run whose watchdog is gone. It reads the outcome from
    the service, resumes watching a live turn, or records how it ended."""
    if data.get("transport") != "api" or _watched(root, data["conversation_id"]):
        return False
    watchable = data["status"] in {"accepted", "running", "waiting"}
    if data["status"] == "unknown" and data.get("prompt_time"):
        # Re-check an uncertain run only when the service answers again; a watcher
        # stuck on an unreachable service would just hold the lock reconcile needs.
        with contextlib.suppress(api.Unavailable, api.ApiError):
            _active()
            watchable = True
    if watchable:
        _spawn(home, data["conversation_id"], data["job_id"])
        return True
    return False


# --------------------------------------------------------------------------
# Watchdog: one per turn, holding the conversation lock while it lives


def _finish(data, status, error=""):
    data.update(status=status, error=error, pending=[])
    with contextlib.suppress(api.ApiError, api.Unavailable):
        data["result"] = _result(data)
    with contextlib.suppress(api.ApiError, api.Unavailable):
        data["changes"] = _changes(data)


def _watch(home, cid, job, poll=POLL):
    home = Path(home)
    if home.name not in PROFILES or home.parent.name != "profiles":
        raise ValueError("Invalid captured OpenCode caller home")
    root = _root(home)
    cid, job = dispatch._id(cid), dispatch._id(job)
    with dispatch._try_locked(root, cid) as held:
        if not held:
            return None
        path = root / (cid + ".json")
        data = dispatch._read(path)
        if data.get("job_id") != job or data.get("transport") != "api" or data["status"] not in BUSY:
            return _public(data)
        if data["status"] == "accepted":
            # The caller died while setting up the turn: whether a prompt reached the
            # service is not known.
            data.update(status="unknown", error="Turn setup was interrupted; inspect the session before reconciliation",
                        updated_at=time.time())
            dispatch._write(path, data)
            return _public(data)
        if not data.get("session_id") or not data.get("prompt_time"):
            return _public(data)
        permission_timeout = _setting(home, "permission_timeout", DEFAULT_PERMISSION_TIMEOUT)
        stop_path = root / (job + ".stop")
        cache, seen = {}, {p["id"]: p.get("first_seen", time.time()) for p in data.get("pending") or []}
        unseen_since = unreachable_since = halted_at = None
        last_interrupt = None
        while True:
            now = time.time()
            if halted_at is None:
                reason = ("stop requested" if stop_path.exists() else "deadline reached" if now >= data["deadline"]
                          else "the calling Hermes process ended" if not _caller_alive(data) else None)
                if reason:
                    data["stop_reason"] = reason
                    halted_at = now
            if halted_at is not None and (last_interrupt is None or now - last_interrupt >= HALT_GRACE):
                # Resent until the turn settles: one lost interrupt must not let a run
                # outlive its deadline or a stop.
                with contextlib.suppress(api.Unavailable):
                    _halt(data)
                last_interrupt = now
            if halted_at is not None and now - halted_at >= HALT_LIMIT:
                data.update(status="unknown", pending=[], updated_at=now,
                            error=f"Interrupt ({data['stop_reason']}) not confirmed by OpenCode; inspect before "
                            "reconciliation")
                dispatch._write(path, data)
                return _public(data)
            try:
                info = _session_info(data["session_id"])
                running = data["session_id"] in _active()
                pending = [] if halted_at else _pending(data, cache)
                unreachable_since = None
            except api.Unavailable:
                unreachable_since = unreachable_since or now
                if now >= data["deadline"] + UNREACHABLE_GRACE:
                    data.update(status="unknown", pending=[], updated_at=now,
                                error="OpenCode service unreachable; the turn's outcome is not confirmed")
                    dispatch._write(path, data)
                    return _public(data)
                time.sleep(poll)
                continue
            except api.ApiError as exc:
                data.update(status="unknown", pending=[], updated_at=now,
                            error=f"OpenCode session no longer readable ({exc.status}); inspect before reconciliation")
                dispatch._write(path, data)
                return _public(data)
            data["tokens"] = info.get("tokens")
            idle = (info.get("time") or {}).get("idle")
            if not running and isinstance(idle, (int, float)) and idle >= data["prompt_time"]:
                outcome = info.get("outcome")
                data["outcome"] = outcome
                if outcome == "succeeded":
                    _finish(data, "completed")
                elif halted_at or outcome == "interrupted":
                    _finish(data, "interrupted", "Interrupted: " + data.get("stop_reason", "by the service"))
                else:
                    _finish(data, "failed", "OpenCode reported a failed turn; partial effects may exist")
                data["updated_at"] = time.time()
                dispatch._write(path, data)
                return _public(data)
            if not running:
                unseen_since = unseen_since or now
                if now - unseen_since >= NO_OUTCOME_GRACE or (halted_at and now - unseen_since >= HALT_GRACE):
                    _finish(data, "interrupted", "The turn ended without an outcome (the OpenCode service "
                            "restarted or stopped it); inspect its changes, then continue the conversation")
                    data["updated_at"] = time.time()
                    dispatch._write(path, data)
                    return _public(data)
            else:
                unseen_since = None
            for item in pending:
                item["first_seen"] = seen.setdefault(item["id"], now)
                item["expires_at"] = item["first_seen"] + permission_timeout
                if now >= item["expires_at"]:
                    with contextlib.suppress(api.ApiError, api.Unavailable):
                        _call("post", "/api/session/{sid}/permission/{per}/reply",
                              {"decision": "reject", "message": NO_DECISION.format(seconds=permission_timeout)},
                              sid=item["session_id"], per=item["id"])
            pending = [item for item in pending if now < item["expires_at"]]
            status = "waiting" if pending else "running"
            if status != data["status"] or pending != (data.get("pending") or []):
                data.update(status=status, pending=pending, updated_at=now)
                dispatch._write(path, data)
            time.sleep(poll)


# --------------------------------------------------------------------------
# Turn setup


def _engine(data, config, info, caller=frozenset()):
    """The provider model reference for this turn, checked against the service's
    catalog and never one of the caller's own models, which would judge its output."""
    configured = (config.get("models") or {}).get(data["agent"])
    pinned = _pinned(configured) if isinstance(configured, str) else None
    if configured and not pinned:
        raise ValueError("Invalid configured OpenCode model")
    explicit = data.get("model") or (pinned or (None,))[0]
    variant = data.get("variant") or (None if data.get("model") or not pinned else pinned[1])
    if explicit:
        if not isinstance(explicit, str) or not MODEL_NAME.fullmatch(explicit):
            raise ValueError("Invalid configured OpenCode model")
        provider, model = explicit.split("/", 1)
    else:
        if variant:
            # Re-checked at dispatch: the configured per-agent model may have been
            # removed since the conversation bound its variant.
            raise ValueError("Recorded variant has no model to bind to; pass model explicitly")
        pin = info.get("model") or {}
        provider, model, variant = pin.get("providerID"), pin.get("id"), pin.get("variant")
        if not provider or not model:
            raise ValueError(f"OpenCode agent {info.get('id')} pins no model and none is configured")
    if variant is not None and not VARIANT_NAME.fullmatch(variant):
        raise ValueError("Invalid OpenCode variant")
    if _model_key(model) in caller:
        raise ValueError(f"{provider}/{model} is your own model, so it would judge or build what you then "
                         "check yourself; pass model= another one from opencode_session models (no run launched)")
    entry = None
    for attempt in range(2):
        # The catalog is per location (project config may add providers) and can
        # briefly lack a provider while it reloads, so a miss is checked twice.
        catalog = api.data(_call("get", "/api/model", query=api.location(data["directory"])), list)
        entry = next((m for m in catalog if m.get("providerID") == provider and m.get("id") == model), None)
        if entry is not None or attempt:
            break
        time.sleep(CATALOG_RETRY)
    if entry is None:
        raise ValueError(f"OpenCode does not offer {provider}/{model}; no run launched")
    if (entry.get("capabilities") or {}).get("tools") is not True or entry.get("enabled") is False:
        raise ValueError(f"OpenCode model {provider}/{model} cannot run an agent (no tool use); no run launched")
    variants = [v.get("id") for v in entry.get("variants") or [] if isinstance(v, dict)]
    if variant and variant not in variants:
        raise ValueError(f"OpenCode model {provider}/{model} has no variant {variant!r}; no run launched")
    return {"providerID": provider, "id": model, **({"variant": variant} if variant else {})}


def _prompt(data, message):
    text = message
    if data["agent"] == "build":
        text += "\n\nClient implementation scope: " + data["approval"]
        text += "\nIssue management: " + (data.get("issue_approval") or "not granted")
    text += ("\n\nIf anything material is undecided or blocked, stop and state the open question and "
             "options in your final reply. Never guess client approval. A tool call may come back "
             "rejected with a reason from Hermes: follow the reason and do not route around it.\n")
    return text


def _agent(name, where):
    """An agent as resolved at the worktree. The single-agent route answers 404 for
    an agent defined only in the project (2.0.23), so the list confirms a miss."""
    try:
        return api.data(_call("get", "/api/agent/{name}", query=where, name=name))
    except api.ApiError as exc:
        if exc.status != 404:
            raise
    for info in api.data(_call("get", "/api/agent", query=where), list):
        if info.get("id") == name:
            return info
    raise ValueError(f"OpenCode agent {name} is not installed; no run launched")


def _setup(home, root, data, config, protected, fork, caller=frozenset()):
    """Create, resume or fork the session under this turn's agent, model and ruleset,
    and verify the service applied them. Sends no prompt."""
    directory = data["directory"]
    name = OPENCODE_AGENTS[data["agent"]]
    where = api.location(directory)
    # Read-only roles may look at a worktree someone else is changing; a build
    # never edits alongside another running session (another profile or a person).
    if data["agent"] not in READ_ONLY and _running_in(directory):
        raise ValueError("An OpenCode session is already running in this worktree (another Hermes profile "
                         "or a person); no build launched")
    info = _agent(name, where)
    # The built-in build agent adds no denies of its own, so its resolved ruleset
    # carries the person's global and project denies.
    person = _agent("build", where).get("permissions") or []
    server = _call("get", "/api/info") or {}
    tmp = (server.get("paths") or {}).get("tmp") if isinstance(server, dict) else None
    rules = _rules(data["agent"], data.get("issue_approval"), protected, tmp=tmp, person_denies=person)
    _check_agent(data["agent"], info, rules)
    model = _engine(data, config, info, caller)
    metadata = {"hermes": {"profile": home.name, "conversation": data["conversation_id"]}}
    sid = data.get("session_id")
    if sid and fork:
        sid = api.data(_call("post", "/api/session/{sid}/fork", {}, sid=sid))["id"]
    if sid:
        current = _session_info(sid)
        if not _same_dir((current.get("location") or {}).get("directory"), directory):
            raise ValueError("The saved OpenCode session belongs to another directory")
        _call("post", "/api/session/{sid}/agent", {"agent": name}, sid=sid)
        _call("post", "/api/session/{sid}/model", {"model": model}, sid=sid)
        _call("patch", "/api/session/{sid}", {"permissions": rules, "metadata": metadata}, sid=sid)
    else:
        sid = api.data(_call("post", "/api/session", {
            "agent": name, "model": model, "location": {"directory": directory},
            "permissions": rules, "metadata": metadata}))["id"]
    if not SESSION_ID.fullmatch(sid):
        raise ValueError("OpenCode returned an invalid session identity")
    data["session_id"] = sid
    applied = _session_info(sid)
    reported = applied.get("model") or {}
    if applied.get("agent") != name or applied.get("permissions") != rules or \
            {k: reported.get(k) for k in model} != model:
        raise ValueError("OpenCode did not report back this turn's agent, model and ruleset; no prompt sent")
    data["engine"] = f"{model['providerID']}/{model['id']}" + (f"#{model['variant']}" if "variant" in model else "")
    return sid


def _wait_limit(home, requested=None):
    """Longest a blocking wait may run: below the caller's own tool deadline (else the
    executor abandons the call into polling), the inherited resident deadline, the
    configured wait_timeout and the request."""
    config = _yaml(home)
    tools = (config.get("timeouts") or {}).get("tools") or {}
    tool = tools.get("sequential_call", tools.get("concurrent_batch", DEFAULT_TOOL_TIMEOUT))
    tool = tool if isinstance(tool, (int, float)) and not isinstance(tool, bool) else DEFAULT_TOOL_TIMEOUT
    limits = [_setting(home, "wait_timeout", DEFAULT_WAIT_TIMEOUT)]
    if requested is not None:
        limits.append(requested)
    if tool > 0:
        limits.append(tool - 30)
    with contextlib.suppress(ValueError, TypeError):
        limits.append(float(os.environ.get("RESIDENT_DEADLINE", "inf")) - time.time() - 5)
    return max(1.0, min(limits))


def _wait(home, root, cid, owner, requested=None):
    """Block until the run hands back to the caller, or a bounded limit passes.

    The watchdog owns the record; this only reads it (and restarts a lost
    watchdog). It is the cheap alternative to a status/sleep polling loop."""
    if requested is not None and (type(requested) is not int or requested < 1):
        raise ValueError("timeout must be a positive integer number of seconds")
    limit = time.time() + _wait_limit(home, requested)
    started, unwatched = time.time(), None
    while True:
        data = dispatch._owned(root, cid, owner)
        if _handback(root, data) or data.get("transport") != "api":
            timed_out = False
            break
        now = time.time()
        if now >= limit:
            timed_out = True
            break
        if _watched(root, cid):
            unwatched = None
        else:
            unwatched = unwatched or now
            if now - unwatched > 3:
                _recover(home, root, data)
                unwatched = now
        time.sleep(min(WAIT_POLL, max(0.0, limit - now)))
    out = {**_public(data), "waited_seconds": round(time.time() - started, 1), "timed_out": timed_out}
    if data["status"] == "waiting":
        out["note"] = ("OpenCode is paused on the pending request(s). Decide each with opencode_session "
                       "respond: once within the Client's approved scope, otherwise reject "
                       "and ask the Client. Unanswered requests are rejected at expires_at.")
    elif data["status"] in BUSY:
        out["note"] = "Still active or uncertain; wait again, steer, stop, or reconcile. Never retry."
    return out


def _launch_notifier(home, cid, job, task_id):
    """Live callers learn of the next handback through a completion notification."""
    from tools.terminal_tool import terminal_tool
    command = dispatch.runner_command(Path(__file__).resolve(), "notify", str(home), cid, job)
    try:
        launch = json.loads(terminal_tool(command=shlex.join(command), background=True,
                                          notify_on_complete=True, task_id=task_id, _host_local=True))
    except Exception:
        launch = {"error": "Notifier launch outcome unknown"}
    return launch.get("session_id")


def _notify(home, cid, job):
    home = Path(home)
    if home.name not in PROFILES or home.parent.name != "profiles":
        raise ValueError("Invalid captured OpenCode caller home")
    root = _root(home)
    cid, job = dispatch._id(cid), dispatch._id(job)
    path = root / (cid + ".json")
    unwatched = None
    while True:
        data = dispatch._read(path)
        if data.get("job_id") != job or _handback(root, data):
            return _public(data)
        if _watched(root, cid):
            unwatched = None
        else:
            unwatched = unwatched or time.time()
            if time.time() - unwatched > 3:
                _recover(home, root, data)
                unwatched = time.time()
        time.sleep(WAIT_POLL)


def _handoff(home, root, cid, owner, live, task_id):
    data = dispatch._owned(root, cid, owner)
    if live:
        process = _launch_notifier(home, cid, data["job_id"], task_id)
        out = {**_public(data), "process_session_id": process}
        if not process:
            out["note"] = ("No completion notification could be arranged; use opencode_session wait for this "
                           "conversation")
        return out
    return _wait(home, root, cid, owner)


# --------------------------------------------------------------------------
# Tools


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
        fork = bool(args.get("fork"))
        with contextlib.ExitStack() as held:
            data, source, protected = _accept(home, root, owner, args, config, selection, fork, held, live)
            path = root / (data["conversation_id"] + ".json")
            try:
                _setup(home, root, data, config, protected, fork, _caller_models(home, kwargs.get("session_id")))
            except (ValueError, api.ApiError, api.Unavailable) as exc:
                if fork and source and data.get("session_id") == source.get("session_id"):
                    data.pop("session_id", None)
                data.update(status="failed", error=f"{exc} (no OpenCode turn started)", updated_at=time.time())
                dispatch._write(path, data)
                return json.dumps(_public(data))
            try:
                admitted = api.data(_call("post", "/api/session/{sid}/prompt", {"text": _prompt(data, message)},
                                          sid=data["session_id"]))
                data.update(prompt_id=admitted["id"], prompt_time=admitted["time"]["created"], status="running")
            except api.ApiError as exc:
                data.update(status="failed", error=f"Prompt refused ({exc.status}): {exc.detail}")
            except (api.Unavailable, KeyError, TypeError):
                data.update(status="unknown", error="Prompt admission not confirmed; inspect the session before "
                            "reconciliation")
            data["updated_at"] = time.time()
            dispatch._write(path, data)
        if data["status"] != "running":
            return json.dumps(_public(data))
        try:
            _spawn(home, data["conversation_id"], data["job_id"])
            return json.dumps(_handoff(home, root, data["conversation_id"], owner, live, kwargs.get("task_id")))
        except Exception as exc:
            # The turn is running in OpenCode: hand back its record, never a bare error.
            return json.dumps({**_public(data), "error": f"{type(exc).__name__} after the prompt was admitted; "
                               "use opencode_session status/wait, never retry"})
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def _accept(home, root, owner, args, config, selection, fork, held, live):
    """Record the turn as accepted and keep its conversation lock in `held`.

    One short registry transaction prevents concurrent new conversations from
    entering the same worktree; the conversation lock then stays held through
    the turn's setup, so no watchdog can mistake it for an abandoned one."""
    agent = args["agent"]
    with dispatch._locked(root, "0" * 32):
        source = None
        if args.get("conversation_id"):
            source = dispatch._owned(root, args["conversation_id"], owner)
            if source.get("transport") != "api":
                raise ValueError("This conversation ran under the OpenCode 1 runner; start a new conversation")
            if source["status"] in BUSY or _watched(root, source["conversation_id"]):
                raise ValueError("Conversation is active or uncertain; wait, stop or reconcile, never retry")
        elif fork:
            raise ValueError("fork requires an owned conversation_id")
        directory = _worktree(args.get("directory") or (source or {}).get("directory"))
        if source and directory != source["directory"]:
            raise ValueError("A conversation cannot move to another worktree")
        cid = source["conversation_id"] if source and not fork else uuid.uuid4().hex
        for path in root.glob("*.json"):
            with contextlib.suppress(OSError, KeyError, TypeError, json.JSONDecodeError):
                other = dispatch._read(path)
                if other["directory"] == directory and other["status"] in BUSY:
                    _recover(home, root, other)
                    raise ValueError("Worktree has active or uncertain OpenCode work")
        data = {k: v for k, v in (source or {}).items() if k not in TURN_FIELDS}
        data.update(conversation_id=cid, directory=directory, owner=owner, agent=agent, transport="api")
        for key in ("approval", "issue_approval"):
            if key in args:
                data[key] = args[key]
        # An explicit selection binds this and later turns of the conversation;
        # an omitted one keeps the conversation's recorded engine.
        data.update(selection)
        if agent == "build" and not data.get("approval"):
            raise ValueError("Build requires the Client's explicit implementation approval")
        branch, protected = _branch(directory, agent == "build")
        if source and branch != source["branch"]:
            raise ValueError("Worktree branch changed; release a new conversation after inspection")
        deadline = min(time.time() + config.get("timeout", DEFAULT_TIMEOUT),
                       float(os.environ.get("RESIDENT_DEADLINE", "inf")))
        if deadline <= time.time():
            raise ValueError("Inherited execution deadline expired")
        held.enter_context(dispatch._locked(root, cid))
        # A fork starts from the source session; _setup replaces it with the copy.
        data.update(job_id=uuid.uuid4().hex, branch=branch, status="accepted", deadline=deadline,
                    caller_pid=None if live else os.getpid(), updated_at=time.time())
        dispatch._write(root / (cid + ".json"), data)
    return data, source, protected


def _models(home, session):
    """What a caller may pass as model=: tool-capable models of the allowed
    providers, each role's default, and the caller's own models (refused)."""
    config = _config(home)
    allowed = config.get("allowed_providers", [])
    caller = _caller_models(home, session)
    catalog = api.data(_call("get", "/api/model"), list)
    if not catalog:
        time.sleep(CATALOG_RETRY)
        catalog = api.data(_call("get", "/api/model"), list)
    pins = {info.get("id"): info.get("model") or {} for info in api.data(_call("get", "/api/agent"), list)}
    defaults = {}
    for role, name in sorted(OPENCODE_AGENTS.items()):
        configured = (config.get("models") or {}).get(role)
        pin = pins.get(name) or {}
        defaults[role] = configured or ("{}/{}".format(pin.get("providerID"), pin.get("id"))
                                        + (f"#{pin['variant']}" if pin.get("variant") else "") if pin.get("id") else None)
    models = []
    for entry in catalog:
        if entry.get("providerID") not in allowed or entry.get("enabled") is False or \
                (entry.get("capabilities") or {}).get("tools") is not True:
            continue
        cost = (entry.get("cost") or [{}])[0] or {}
        models.append({
            "model": f"{entry['providerID']}/{entry['id']}", "name": entry.get("name"),
            "variants": [v.get("id") for v in entry.get("variants") or [] if isinstance(v, dict)],
            "context": (entry.get("limit") or {}).get("context"),
            "cost_per_mtok": {k: cost.get(k) for k in ("input", "output")} if cost else None,
            **({"yours": True} if _model_key(entry["id"]) in caller else {})})
    return {"allowed_providers": allowed, "defaults": defaults, "models": sorted(models, key=lambda m: m["model"]),
            "note": "Pass model= (and optionally variant= from its variants) to opencode_call. Models marked "
                    "yours are your own and are refused; a default that is yours needs another model."}


def _respond(home, root, data, args):
    request_id, decision, reason = args.get("request_id"), args.get("decision"), args.get("reason")
    if not isinstance(request_id, str) or not PERMISSION_ID.fullmatch(request_id):
        raise ValueError("respond needs the request_id of a pending request")
    if decision not in DECISIONS:
        raise ValueError("decision must be once or reject (never always: it saves a project-wide approval "
                         "people's own sessions would inherit; a session-wide allow would reach every subagent)")
    if reason is not None and (not isinstance(reason, str) or len(reason) > 2000):
        raise ValueError("reason must be text of at most 2000 characters")
    if data.get("transport") != "api" or data["status"] not in {"running", "waiting"}:
        raise ValueError("No paused OpenCode run to respond to")
    request = next((p for p in _pending(data, {}) if p["id"] == request_id), None)
    if request is None:
        raise ValueError("That request is not pending in this run (answered, expired or foreign)")
    reply = {"decision": "reject" if decision == "reject" else "once"}
    if reason:
        reply["message"] = reason
    _call("post", "/api/session/{sid}/permission/{per}/reply", reply, sid=request["session_id"], per=request_id)
    answered = sorted(_answered(root, data["job_id"]) | {request_id})
    dispatch._write(root / (data["job_id"] + ".answered"), answered)


def opencode_session(args, **kwargs):
    try:
        allowed = {"action", "conversation_id", "evidence", "timeout", "request_id", "decision", "reason",
                   "message", "patch"}
        if set(args) - allowed:
            raise ValueError("Unexpected arguments")
        action = args.get("action")
        if "timeout" in args and action != "wait":
            raise ValueError("timeout is only accepted for wait")
        home, owner, live = _scope()
        # Disabling new execution must not remove the owner's ability to inspect,
        # answer or stop a run already in flight.
        root = _root(home)
        if action == "list":
            rows = []
            for path in root.glob("*.json"):
                with contextlib.suppress(OSError, ValueError, KeyError, TypeError, AttributeError):
                    data = dispatch._read(path)
                    if data.get("owner") == owner:
                        _recover(home, root, data)
                        rows.append(_public(data))
            return json.dumps(rows)
        if action == "models":
            return json.dumps(_models(home, kwargs.get("session_id")))
        cid = dispatch._id(args.get("conversation_id"))
        data = dispatch._owned(root, cid, owner)
        if action == "status":
            _recover(home, root, data)
            return json.dumps(_public(data))
        if action == "wait":
            return json.dumps(_wait(home, root, cid, owner, args.get("timeout")))
        if action == "respond":
            _respond(home, root, data, args)
            return json.dumps(_handoff(home, root, cid, owner, live, kwargs.get("task_id")))
        if action == "steer":
            text = args.get("message")
            if not isinstance(text, str) or not text.strip() or len(text) > 20000:
                raise ValueError("steer needs a nonempty message of at most 20000 characters")
            if data.get("transport") != "api" or data["status"] not in {"running", "waiting"}:
                raise ValueError("No running OpenCode turn to steer")
            _call("post", "/api/session/{sid}/prompt", {"text": text, "delivery": "steer"}, sid=data["session_id"])
            return json.dumps({**_public(data), "steered": True,
                               "note": "Delivered at the run's next step boundary; a long tool call finishes first"})
        if action == "diff":
            if data.get("transport") != "api" or not data.get("prompt_id"):
                raise ValueError("No OpenCode turn to diff")
            body = _call("get", "/api/session/{sid}/diff", query={"from": data["prompt_id"]}, sid=data["session_id"])
            items = (body.get("data") if isinstance(body, dict) else body) or []
            keys = ("file", "status", "additions", "deletions") + (("patch",) if args.get("patch") is True else ())
            files, budget = [], 60000
            for item in items[:200]:
                entry = {key: item.get(key) for key in keys}
                if "patch" in entry:
                    entry["patch"] = (entry["patch"] or "")[:max(0, budget)]
                    budget -= len(entry["patch"])
                files.append(entry)
            return json.dumps({"conversation_id": cid, "session_id": data["session_id"], "files": files,
                               **({"truncated": True} if budget < 0 or len(items) > 200 else {})})
        if action == "stop":
            if data["status"] not in BUSY:
                raise ValueError("No active or uncertain run to stop")
            dispatch._write(root / (data["job_id"] + ".stop"), {"requested_at": time.time()})
            if data.get("transport") == "api" and data.get("session_id"):
                with contextlib.suppress(api.ApiError, api.Unavailable):
                    _halt(data)
                _recover(home, root, data)
            return json.dumps({**_public(data), "stop_requested": True,
                               "note": "Interrupt sent; the record settles within seconds. Never a rollback."})
        if action != "reconcile" or not isinstance(args.get("evidence"), str) or not args["evidence"].strip():
            raise ValueError("Use status/list/models/wait/respond/steer/diff/stop, or reconcile with observed "
                             "process/Git/remote-effect evidence")
        if _watched(root, cid):
            raise ValueError("A watcher is still checking this run; wait for it, then reconcile if it stays unknown")
        with dispatch._locked(root, cid):
            data = dispatch._owned(root, cid, owner)
            if data["status"] not in BUSY:
                raise ValueError("Reconcile only uncertain or inactive work")
            if data.get("transport") == "api":
                if data["status"] != "unknown":
                    raise ValueError("A watched run settles by itself; wait or stop it instead")
                with contextlib.suppress(api.Unavailable, api.ApiError):
                    if data.get("session_id") and data["session_id"] in _active():
                        raise ValueError("OpenCode still runs this session; stop it before reconciling")
            elif _group_alive(data.get("pgid")):
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


CALL_DESCRIPTION = (
    "Drive OpenCode in an owned Git worktree on the shared OpenCode service. Blocks until the run hands "
    "back: finished, or paused on a permission request you must decide with opencode_session respond. "
    "Build needs explicit Client implementation approval; Issue writes need separate explicit "
    "issue_approval or a per-request decision. Completion is not acceptance. Never retry uncertain work. "
    "If the call returns while still running, use opencode_session wait, never a status loop.")
SESSION_DESCRIPTION = (
    "Inspect and steer your OpenCode runs. models lists what opencode_call accepts as model=. wait blocks until the run hands back, spending no turns. respond "
    "answers a pending permission request: once only within the Client's approved scope, otherwise reject "
    "with a reason and ask the Client. steer adds an instruction to a running turn. diff lists the turn's changed files (patch=true "
    "adds patches). stop interrupts the run; it never rolls back effects. reconcile is only for unknown "
    "runs, after observing their process, Git and remote effects.")
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

    ctx.register_hook("post_api_request", _observe)
    for name, handler, properties, required, description in (
        ("opencode_call", opencode_call, {
            "directory": {"type": "string"}, "agent": {"type": "string", "enum": sorted(AGENTS)},
            "message": {"type": "string"}, "conversation_id": {"type": "string"},
            "fork": {"type": "boolean"}, "approval": {"type": "string"}, "issue_approval": {"type": "string"},
            "model": {"type": "string", "description": "Optional provider/model from opencode_session models; "
                      "never your own model"},
            "variant": {"type": "string", "description": "Optional reasoning effort from that model's variants"},
        }, ["agent", "message"], CALL_DESCRIPTION),
        ("opencode_session", opencode_session, {
            "action": {"type": "string",
                       "enum": ["status", "list", "models", "wait", "respond", "steer", "diff", "stop",
                                "reconcile"]},
            "conversation_id": {"type": "string"}, "evidence": {"type": "string"},
            "timeout": {"type": "integer", "description": "wait only: seconds to block (bounded by config and turn deadline)"},
            "request_id": {"type": "string", "description": "respond only: the pending request's id (per_…)"},
            "decision": {"type": "string", "enum": list(DECISIONS), "description": "respond only"},
            "reason": {"type": "string", "description": "respond only: shown to OpenCode; required in spirit for reject"},
            "message": {"type": "string", "description": "steer only"},
            "patch": {"type": "boolean", "description": "diff only: include patches (truncated)"},
        }, ["action"], SESSION_DESCRIPTION),
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
    mode, home_arg, cid_arg, job_arg = sys.argv[1:5]
    outcome = (_watch if mode == "watch" else _notify)(home_arg, cid_arg, job_arg)
    print(json.dumps(outcome))
    raise SystemExit(0)
