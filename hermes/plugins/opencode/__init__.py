"""OpenCode CLI transport, not a planner, approval authority, or process sandbox."""

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
import time
import uuid

import yaml


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
BUSY = {"accepted", "running", "unknown"}
MAX_LOG = 8 * 1024 * 1024
MAX_LINE = 1024 * 1024
SESSION_ID = re.compile(r"ses_[A-Za-z0-9_-]+\Z")
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
    approves it, so it never means "ask" on this transport.
    """
    data = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
    return {"*": "deny",
            str(data / "opencode/tool-output/*"): "allow",
            str(Path(os.environ.get("TMPDIR") or "/tmp") / "opencode/*"): "allow"}


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


def _command(data, config):
    command = ["opencode", "run", "--format", "json", "--agent", OPENCODE_AGENTS[data["agent"]],
               "--dir", data["directory"]]
    if data["agent"] == "build":
        command.append("--auto")
    model = data.get("model") or (config.get("models") or {}).get(data["agent"])
    if model:
        if not isinstance(model, str) or not re.fullmatch(r"[A-Za-z0-9_.:/-]+", model):
            raise ValueError("Invalid configured OpenCode model")
        command += ["--model", model]
    variant = data.get("variant")
    if variant:
        if not isinstance(variant, str) or not VARIANT_NAME.fullmatch(variant):
            raise ValueError("Invalid recorded OpenCode variant")
        if not model:
            # Re-checked at dispatch: the configured per-agent model may have been
            # removed since the conversation bound its variant.
            raise ValueError("Recorded variant has no model to bind to; pass model explicitly")
        command += ["--variant", variant]
    if data.get("session_id"):
        if not SESSION_ID.fullmatch(data["session_id"]):
            raise ValueError("Invalid saved OpenCode session identity")
        command += ["--session", data["session_id"]]
    if data.get("fork"):
        command.append("--fork")
    # stdin carries the prompt, not a shell fragment or a process-list argument.
    return command


def _env(data, protected):
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("HERMES_", "RESIDENT_"))
           and key not in {"OPENCODE_PERMISSION", "OPENCODE_CONFIG_CONTENT"}}
    permission = _permissions(data["agent"], data.get("issue_approval"), protected)
    env["OPENCODE_PERMISSION"] = json.dumps(permission)
    env["OPENCODE_CONFIG_CONTENT"] = json.dumps({
        "share": "disabled", "agent": {OPENCODE_AGENTS[data["agent"]]: {"permission": permission}},
    })
    return env


def _public(data):
    keys = ("conversation_id", "job_id", "directory", "branch", "agent", "model", "variant", "status",
            "session_id", "result", "error", "exit_code", "log", "updated_at", "reconciliation")
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
        proc = None
        original_sid = data.get("session_id")
        stop_path = root / (job + ".stop")
        old_handlers = {}
        interrupted = False

        def interrupt(signum, frame):
            nonlocal interrupted
            interrupted = True

        try:
            for sig in (signal.SIGTERM, signal.SIGINT):
                old_handlers[sig] = signal.signal(sig, interrupt)
            config = _config(home)
            if _worktree(data["directory"]) != data["directory"]:
                raise ValueError("Worktree identity changed")
            branch, protected = _branch(data["directory"], data["agent"] == "build")
            if branch != data["branch"]:
                raise ValueError("Worktree branch changed since dispatch")
            if time.time() >= request["deadline"] or stop_path.exists():
                raise ValueError("Stopped or expired before dispatch")
            command = _command(data, config)
            data.update(status="running", result="", error="")
            dispatch._write(root / (cid + ".json"), data)
            with open(root / (job + ".prompt"), "x", encoding="utf-8") as prompt:
                os.chmod(prompt.name, 0o600)
                prompt.write(request["message"])
                if data["agent"] == "build":
                    prompt.write("\n\nClient implementation scope: " + data["approval"])
                    prompt.write("\nIssue management: " + (data.get("issue_approval") or "not granted"))
                prompt.write("\n\nIf anything material is undecided or blocked, stop and state "
                             "the open question and options in your final reply. Never guess client approval.\n")
                prompt.flush()
            with open(root / (job + ".prompt")) as prompt:
                proc = subprocess.Popen(command, cwd=data["directory"], env=_env(data, protected), stdin=prompt,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
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
                    if (interrupted or stop_path.exists() or time.time() >= request["deadline"]
                            or (request.get("parent_pid") and os.getppid() != request["parent_pid"])):
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
        except Exception as exc:
            data.update(status="unknown" if proc else "failed",
                        error=f"{type(exc).__name__}: execution not confirmed" if proc else str(exc))
        finally:
            if proc is not None:
                # Only this live runner signals its own child group, never a stored PID.
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(proc.pid, signal.SIGKILL)
                proc.wait(timeout=5)
                proc.stdout.close()
                proc.stderr.close()
            for sig, handler in old_handlers.items():
                signal.signal(sig, handler)
            data["updated_at"] = time.time()
            dispatch._write(root / (cid + ".json"), data)
    return _public(data)


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
                for key in ("exit_code", "reconciliation"):
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
                request = dict(home=str(home), owner=owner, conversation_id=cid, job_id=job,
                               message=message, deadline=deadline, parent_pid=None if live else os.getpid())
                data.update(job_id=job, branch=branch, status="accepted", result="", error="", pgid=None,
                            log=str(root / (job + ".events")), updated_at=time.time(),
                            request_digest=hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest())
                dispatch._write(root / (job + ".request"), request)
                dispatch._write(root / (cid + ".json"), data)
        request_path = root / (job + ".request")
        command = [sys.executable, str(Path(__file__).resolve()), str(request_path)]
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
        try:
            proc.wait(timeout=config.get("timeout", 3600) + 15)
        except subprocess.TimeoutExpired:
            dispatch._write(root / (job + ".stop"), {"requested_at": time.time()})
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                return json.dumps({**_public(dispatch._owned(root, cid, owner)), "stop_requested": True,
                                   "error": "Runner has not confirmed termination; do not retry"})
        data = dispatch._owned(root, cid, owner)
        if data["status"] in {"accepted", "running"}:
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
        # unfinalized record (or a still-live group) is worth waiting on.
        if data["status"] not in {"accepted", "running"} and not (
                data["status"] == "unknown" and data.get("pgid") and _group_alive(data["pgid"])):
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
    return {**_public(data), "waited_seconds": round(time.time() - started, 1), "timed_out": timed_out,
            **({"note": "Still active or uncertain; inspect, wait again, stop, or reconcile. Never retry."}
               if data["status"] in BUSY else {})}


def opencode_session(args, **kwargs):
    try:
        if set(args) - {"action", "conversation_id", "evidence", "timeout"}:
            raise ValueError("Unexpected arguments")
        if "timeout" in args and args.get("action") != "wait":
            raise ValueError("timeout is only accepted for wait")
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
        if action != "reconcile" or not isinstance(args.get("evidence"), str) or not args["evidence"].strip():
            raise ValueError("Use status/list/stop, or reconcile with observed process/Git/remote-effect evidence")
        with dispatch._locked(root, cid):
            data = dispatch._owned(root, cid, owner)
            if data["status"] not in BUSY or _group_alive(data.get("pgid")):
                raise ValueError("Reconcile only uncertain/inactive work after its process group has stopped")
            data.update(status="reconciled", reconciliation=args["evidence"], updated_at=time.time())
            dispatch._write(root / (cid + ".json"), data)
        return json.dumps(_public(data))
    except Exception as exc:
        return json.dumps({"error": str(exc)})


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
         "Drive OpenCode in an owned Git worktree; blocks until the run finishes. Build needs explicit Client "
         "implementation approval; Issue writes need separate explicit issue_approval. Completion is not acceptance. "
         "Never retry uncertain work. If the call returns a timeout error, use opencode_session wait, never a status loop."),
        ("opencode_session", opencode_session, {
            "action": {"type": "string", "enum": ["status", "list", "wait", "stop", "reconcile"]},
            "conversation_id": {"type": "string"}, "evidence": {"type": "string"},
            "timeout": {"type": "integer", "description": "wait only: seconds to block (bounded by config and turn deadline)"},
        }, ["action"], "Inspect, wait for, or request stopping your OpenCode run. wait blocks until the run leaves "
         "active/uncertain state, spending no turns. Stop never rolls back effects. "
         "Reconcile inactive uncertain work only after observing its process, Git and remote effects."),
    ):
        ctx.register_tool(name=name, toolset="opencode", handler=scoped(handler), description=description,
                          schema={"name": name, "description": description, "parameters": {
                              "type": "object", "properties": properties, "required": required,
                              "additionalProperties": False}})


if __name__ == "__main__":
    outcome = _run(Path(sys.argv[1]))
    print(json.dumps(outcome))
    raise SystemExit(0 if outcome["status"] == "completed" else 1)
