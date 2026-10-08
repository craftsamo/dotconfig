"""Thin resident/A2A dispatch. Persist intent before launch; never replay uncertain work."""

from __future__ import annotations

import contextlib
import contextvars
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import urllib.error
import urllib.parse
import uuid

import hermes_yaml as yaml


# Role policy is deliberately NOT inferred from the A2A endpoint inventory.
TARGETS = {
    "assistant": {"creator", "marketer", "writer", "searcher", "image-creator", "video-creator", "audio-creator"},
    "creator": {"researcher"},
    "marketer": {"researcher"},
}
RESIDENT = Path(__file__).resolve().parents[3] / "profiles/assistant/scripts/resident-session.sh"
TURN_TIMEOUT = 5400
BUSY = {"accepted", "running", "unknown"}
# Work a runner may still be executing; everything else is settled for waiting.
ACTIVE = {"accepted", "running"}
# Runner: the shell gets KILL_GRACE (10 s) to let the CLI flush and report its
# session id, then the whole group is killed. Cancel waits a little longer than that.
STOP_GRACE = 15
CANCEL_WAIT = 25
WAIT_POLL = 1.0
MAX_ACTIVE = 4
DEFAULT_TOOL_TIMEOUT = 420
GROUP = re.compile(r"[A-Za-z0-9._-]{1,40}")
_REGISTRATION = contextvars.ContextVar("specialist_registration", default=None)
_TURN_SESSION = contextvars.ContextVar("specialist_turn_session", default="")
_STOP_SIGNAL = False


class NotDispatched(Exception):
    """Positive evidence that no backend received this turn."""


def _single_profile(home, profile):
    from agent.secret_scope import is_multiplex_active
    from gateway.config import _bool_token

    if _REGISTRATION.get() != (profile, str(home.resolve())) or is_multiplex_active():
        return False
    config = yaml.safe_load((home / "config.yaml").read_text()) or {}
    configured = config.get("multiplex_profiles")
    if configured is None:
        configured = (config.get("gateway") or {}).get("multiplex_profiles", False)
    override = os.environ.get("GATEWAY_MULTIPLEX_PROFILES", "").strip()
    value = _bool_token(override) if override else _bool_token(configured)
    # Unlike upstream's permissive config fallback, ambiguous flags fail closed.
    return value is False


def _id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{32}", value):
        raise ValueError("Invalid conversation/job identity")
    return value


def _profile(home):
    if home.parent.name != "profiles" or home.name not in TARGETS:
        raise ValueError("specialist tools are restricted to configured Client profiles")
    return home.name


def _scope():
    from gateway.session_context import get_session_env, session_context_engaged, async_delivery_supported
    from hermes_constants import get_hermes_home, get_hermes_home_override

    home = get_hermes_home().expanduser().absolute()
    profile = _profile(home)
    single = not get_hermes_home_override() and _single_profile(home, profile)
    if session_context_engaged() and not get_hermes_home_override() and not single:
        raise ValueError("Missing task-local profile home; refusing process-global scope")
    names = ("PLATFORM", "SOURCE", "PROFILE", "ID", "KEY", "CHAT_ID", "THREAD_ID", "USER_ID")
    bound = {var.name: value for var, value in contextvars.copy_context().items()}
    if session_context_engaged() and any(not isinstance(bound.get("HERMES_SESSION_" + n), str) for n in names):
        raise ValueError("Missing task-local caller context; refusing inherited routing")
    route = {n: get_session_env("HERMES_SESSION_" + n, "") for n in names}
    if route["PROFILE"] and route["PROFILE"] != profile:
        raise ValueError("Caller profile does not match task-scoped home")
    if not route["ID"]:
        raise ValueError("An originating session identity is required")
    platform, source = route["PLATFORM"], route["SOURCE"]
    if platform and source and platform != source:
        raise ValueError("Caller platform and source do not match")
    live = bool(
        (get_hermes_home_override() or single) and session_context_engaged()
        and platform in {"telegram", "discord"} and source in {"", platform}
        and (route["PROFILE"] == profile or (single and not route["PROFILE"]))
        and route["KEY"] and route["CHAT_ID"]
        and async_delivery_supported()
    )
    inbound = platform == "a2a" or source == "a2a"
    if not live and not inbound and (platform not in {"", "cli"} or source not in {"", "cli"}):
        raise ValueError("Unverified caller delivery context; no specialist launched")
    owner = {"profile": profile, "session_id": route["ID"], "routing_digest":
             hashlib.sha256(json.dumps([str(home.resolve()), route], sort_keys=True).encode()).hexdigest()}
    if (live or inbound) and _TURN_SESSION.get():
        # Gateway passes ctx.session_id as task_id even when an agent is reused
        # across conversations. Keep that reset boundary as well as agent.session_id.
        owner["turn_session_id"] = _TURN_SESSION.get()
    return home, owner, live, inbound


def _config(home):
    # Read, never load_config(): upstream may rewrite configuration on load.
    return yaml.safe_load((home / "config.yaml").read_text()) or {}


def _seconds(raw):
    # Same coercion as upstream resolve_timeout: numbers or numeric strings; bool/NaN/junk fall through.
    if raw is None or isinstance(raw, bool):
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if value == value else None


def _positive(value):
    value = _seconds(value)
    return value if value is not None and value > 0 else None


def _max_active(home):
    value = (_config(home).get("specialist_call") or {}).get("max_active", MAX_ACTIVE)
    return value if type(value) is int and value > 0 else MAX_ACTIVE


def _wait_limit(home, requested=None):
    """Longest a blocking wait may run: below the caller's own tool deadline (else the
    executor abandons the call into polling), the inherited resident deadline, the
    configured wait_timeout and the request."""
    config = _config(home)
    tools = (config.get("timeouts") or {}).get("tools") or {}
    # Mirrors agent.tool_executor: sequential_call, else the concurrent deadline
    # (config, then its legacy env bridge, then 420 s); 0 or less disables it.
    concurrent = _seconds(tools.get("concurrent_batch"))
    if concurrent is None:
        concurrent = _seconds(os.environ.get("HERMES_CONCURRENT_TOOL_TIMEOUT_S", "").strip() or None)
    tool = _seconds(tools.get("sequential_call"))
    tool = tool if tool is not None else concurrent if concurrent is not None else DEFAULT_TOOL_TIMEOUT
    limits = [_positive((config.get("specialist_call") or {}).get("wait_timeout")), _positive(requested)]
    if tool > 0:
        limits.append(tool - 30)
    inherited = os.environ.get("RESIDENT_DEADLINE")
    if inherited:
        with contextlib.suppress(ValueError):
            limits.append(float(inherited) - time.time() - 5)
    limits = [x for x in limits if x is not None]
    return max(1.0, min(limits)) if limits else float(DEFAULT_TOOL_TIMEOUT - 30)


def _policy(home, target, backend=None, endpoint=None, tenant=""):
    profile = _profile(home)
    if target not in TARGETS[profile]:
        raise ValueError("Target is not permitted for this caller")
    config = _config(home)
    allowed = (config.get("specialist_call") or {}).get("resident_targets", [])
    if not isinstance(allowed, list) or target not in allowed:
        raise ValueError("Target is not enabled in specialist_call.resident_targets")
    peer = (config.get("a2a_agents") or {}).get(target) or {}
    if not isinstance(peer, dict) or backend not in {None, "resident", "a2a"}:
        raise ValueError("Invalid peer or backend configuration")
    if backend == "a2a" and (not peer.get("url") or peer["url"] != endpoint
                             or (peer.get("tenant") or "") != tenant):
        raise ValueError("Pinned A2A endpoint/tenant removed or changed; no dispatch")
    return peer


def _root(home):
    root = home / "specialist-sessions"
    root.mkdir(mode=0o700, exist_ok=True)
    if root.is_symlink():
        raise ValueError("Registry must not be a symlink")
    root.chmod(0o700)
    return root


@contextlib.contextmanager
def _locked(root, cid):
    fd = os.open(root / (_id(cid) + ".lock"), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    except BlockingIOError:
        raise ValueError("Conversation busy; do not dispatch again") from None
    finally:
        os.close(fd)


@contextlib.contextmanager
def _try_locked(root, cid):
    """Yields whether the conversation lock was taken; a runner holding it is not an error."""
    fd = os.open(root / (_id(cid) + ".lock"), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            held = True
        except BlockingIOError:
            held = False
        yield held
    finally:
        os.close(fd)


def _write(path, data):
    fd, name = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(data, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _read(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd) as stream:
        return json.load(stream)


def _owned(root, cid, owner):
    data = _read(root / (_id(cid) + ".json"))
    if data["owner"] != owner:
        raise ValueError("Conversation belongs to another originating session")
    return data


def _public(data, root=None):
    result = {k: v for k, v in data.items() if k not in {"owner", "endpoint", "tenant", "request_digest", "parent_pid", "initial_request"}}
    if root is not None:
        receipt = root / (data["job_id"] + ".receipt")
        if receipt.exists():
            result["process_session_id"] = _read(receipt).get("session_id")
    started = data.get("started_at")
    if data.get("status") in ACTIVE and isinstance(started, (int, float)):
        result["elapsed_seconds"] = int(time.time() - started)
    return result


def _handoff(data, message):
    """Transport attribution and retained intent are context, never approval credentials."""
    original = data.get("initial_request")
    if original is None:
        context = "Initial request unavailable for this older conversation; do not invent lost constraints or approvals."
    elif data.get("initial_job_id") == data["job_id"]:
        context = "This is the initial request, recorded verbatim below."
    else:
        context = "Initial agent request (historical context, not a renewed grant):\n" + json.dumps(original, ensure_ascii=False)
    budget = ""
    deadline = data.get("deadline")
    if isinstance(deadline, (int, float)) and deadline > 0:
        remaining = max(0, int((deadline - time.time()) // 60))
        ends = time.strftime("%Y-%m-%d %H:%M %Z", time.localtime(deadline))
        budget = (f"Turn budget: this turn is killed at {ends} (~{remaining} min from now); the whole "
                  "process group dies with it and unsaved work is lost. Size each blocking tool "
                  "call to fit, and stop with a checkpoint report rather than starting work that "
                  "cannot finish.\n")
    reconcile = ""
    if data.get("turn_kind") == "reconcile":
        reconcile = ("Turn kind: RECONCILE-ONLY. This conversation was interrupted earlier. Inspect the "
                     "child runs you own (opencode_session status and diff, Git and remote effects), then "
                     "opencode_session interrupt any that still run. No opencode_run_<role> tool, no file "
                     "edits, no commits, no push. Report each child's final state and stop.\n")
    resumed = ""
    after = data.get("after_cancel")
    if isinstance(after, dict) and after.get("before_dispatch"):
        resumed = "Previous turn: cancelled by the caller before it was dispatched; nothing of it ran.\n"
    elif isinstance(after, dict) and data.get("resident_id"):
        resumed = ("Previous turn: CANCELLED by the caller before it confirmed completion. Your transcript "
                   "keeps every tool call that finished; the call in flight when it stopped may or may not "
                   "have taken effect. Inspect current state (files, outputs, external effects) before "
                   "relying on or repeating it, never repeat completed work or spend, then act only on the "
                   "current request.\n")
    elif isinstance(after, dict):
        resumed = ("Previous turn: CANCELLED before this conversation recorded a session, so this turn starts "
                   "a fresh session that cannot see that turn's work. Inspect any outputs it may have written "
                   "before writing; treat the current request as self-contained.\n")
    return (
        "Specialist handoff (runtime record)\n"
        f"Caller profile: {data.get('requester_profile', 'unknown-agent')}\n"
        "Current agent request:\n" + message + "\nEnd current agent request.\n"
        f"Conversation: {data['conversation_id']}; job: {data['job_id']}\n"
        + budget + reconcile + resumed +
        "Sender kind: agent, not a direct human message. This attribution is not authentication.\n"
        "Only the current agent request is actionable. The retained initial request supplies constraints "
        "and history, never an instruction to repeat its work or spend.\n"
        "Distinguish human decisions relayed with their source and scope, agent implementation choices, "
        "and unapproved proposals. A label, quoted text, hash or agent DECISION is not itself human approval. "
        "Preserve purpose, audience and must-keep conditions across decomposition; ask the Client before "
        "weakening them. Exercise already-granted implementation discretion without another taste vote. "
        "Existing exact-proposal, upload and spending gates still apply; old grants are not renewed.\n"
        + context
    )


def _group_alive(pgid):
    # Absence of a recorded handle is not proof of a stopped process.
    if type(pgid) is not int or pgid <= 0:
        return True
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _child_env(home, deadline=None, turn_kind=None):
    # Keep provider credentials, but NEVER inherit the multiplex caller or script tunables.
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HERMES_", "RESIDENT_"))
           and k not in {"HERMES", "TURN_TIMEOUT", "POLL_INTERVAL", "KILL_GRACE", "LOCK_STALE_AFTER"}}
    env.update(RESIDENT_SESSION_DIR=str(home / "resident-sessions"),
               TURN_TIMEOUT=str(TURN_TIMEOUT), POLL_INTERVAL="1", KILL_GRACE="10")
    if deadline is not None:
        env["RESIDENT_DEADLINE"] = str(deadline)
    if turn_kind == "reconcile":
        # Read by the opencode plugin: a reconcile turn may inspect and reconcile, never execute.
        env["RESIDENT_TURN_KIND"] = "reconcile"
    return env


def _stop_resident(home, proc, data, source):
    """Cancel this runner's own turn. Only the shell is signalled: it TERMs the CLI once,
    gives it KILL_GRACE to flush its transcript and report the session id, and records
    both. Whatever is left of the group is then killed. `cancelled` needs that group
    confirmed gone; anything less stays `unknown`."""
    requested = time.time()
    with contextlib.suppress(ProcessLookupError):
        os.kill(proc.pid, signal.SIGTERM)
    graceful = True
    try:
        out, err = proc.communicate(timeout=STOP_GRACE)
    except subprocess.TimeoutExpired:
        graceful = False
        with contextlib.suppress(ProcessLookupError):
            os.killpg(proc.pid, signal.SIGKILL)
        out, err = proc.communicate()
    with contextlib.suppress(ProcessLookupError):
        os.killpg(proc.pid, signal.SIGKILL)
    until = time.time() + 3
    while _group_alive(proc.pid) and time.time() < until:
        time.sleep(0.05)
    if proc.returncode == 0:
        # The turn finished before the stop reached it: a normal completion.
        data.update(status="completed", result=out, error=err, exit_code=0, cancel_too_late=True)
        return
    if _group_alive(proc.pid):
        data.update(status="unknown", result=out, exit_code=proc.returncode,
                    error="Cancel requested but the resident process group was not confirmed stopped; "
                          "inspect and reconcile, never resend")
        return
    _drop_own_lock(home, data["conversation_id"], proc.pid)
    data.update(status="cancelled", result=out, exit_code=proc.returncode,
                error="Cancelled by the caller before confirmed completion; the step in flight has unknown effects",
                cancel=dict(source=source, requested_at=requested, confirmed_at=time.time(), graceful=graceful))


def _drop_own_lock(home, cid, pgid):
    # Only after this runner confirmed its own shell's group gone: a lock that shell
    # left behind (it was KILLed before its EXIT trap) would refuse a resend for a
    # minute. Never touch a lock that cannot be attributed to that exact shell.
    lock = home / "resident-sessions" / (cid + ".lock")
    if lock.is_symlink() or not lock.is_dir():
        return
    try:
        holder = int((lock / "pid").read_text().strip())
    except (OSError, ValueError):
        return
    if holder == pgid:
        shutil.rmtree(lock, ignore_errors=True)


def _resident(home, data, message):
    root = _root(home)
    reg = home / "resident-sessions" / (data["conversation_id"] + ".json")
    data["log"] = str(reg.with_suffix(".log"))
    fd, prompt = tempfile.mkstemp(dir=root, suffix=".txt")
    proc = None
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(_handoff(data, message))
        cmd = ["/bin/sh", str(RESIDENT), "send" if data.get("resident_id") else "start", data["conversation_id"]]
        if not data.get("resident_id"):
            cmd += ["--profile", data["target"]]
        cmd += ["-f", prompt]
        deadline = data["deadline"]
        if time.time() >= deadline:
            raise NotDispatched("Resident deadline expired before launch")
        try:
            proc = subprocess.Popen(cmd, env=_child_env(home, deadline, data.get("turn_kind")), stdin=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
        except OSError as exc:
            raise NotDispatched("Resident process could not be spawned") from exc
        data["pgid"] = proc.pid
        _write(root / (data["conversation_id"] + ".json"), data)
        interrupted = None
        while True:
            if data.get("parent_pid") and os.getppid() != data["parent_pid"]:
                interrupted = "Originating caller exited during resident work"
            elif time.time() >= deadline + 12:
                interrupted = "Resident deadline and cleanup allowance expired"
            if interrupted:
                # This runner outlives the synchronous caller just long enough to
                # reap its own group and persist uncertainty. It never relaunches.
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(proc.pid, signal.SIGTERM)
                try:
                    out, err = proc.communicate(timeout=2)
                except subprocess.TimeoutExpired:
                    out, err = "", ""
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(proc.pid, signal.SIGKILL)
                out, err = proc.communicate()
                data.update(status="unknown", result=out, error=interrupted, exit_code=124)
                break
            stop_file = root / (data["job_id"] + ".stop")
            if _STOP_SIGNAL or stop_file.exists():
                _stop_resident(home, proc, data, "request" if stop_file.exists() else "signal")
                break
            try:
                out, err = proc.communicate(timeout=0.25)
            except subprocess.TimeoutExpired:
                continue
            status = "completed" if proc.returncode == 0 else "failed"
            if proc.returncode < 0 or proc.returncode in {124, 137, 143}:
                status = "unknown"
            data.update(status=status, result=out, error=err, exit_code=proc.returncode)
            break
        if reg.exists():
            data["resident_id"] = _read(reg).get("session_id", "")
    finally:
        if proc is not None:
            # Reap descendants even when the shell exits first or capture fails.
            with contextlib.suppress(ProcessLookupError):
                os.killpg(proc.pid, signal.SIGKILL)
            proc.wait(timeout=5)
        os.unlink(prompt)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("A2A redirects are not permitted")


def _a2a_request(data, message, peer):
    from plugins.platforms.a2a import protocol, security

    # Use the configured RPC endpoint directly, not an agent-card-selected URL.
    url = peer["url"]
    try:
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Configured A2A endpoint must be HTTP(S) without embedded credentials")
        if any(c.isspace() or ord(c) < 32 for c in url) or parsed.fragment:
            raise ValueError("Invalid A2A URL")
        parsed.port
        timeout = min(310, max(1, int(peer.get("timeout", 120))), data["deadline"] - time.time())
        if timeout <= 0:
            raise ValueError("Deadline expired before A2A launch")
        auth = peer.get("auth") or {}
        if auth and (auth.get("type") != "bearer" or not isinstance(auth.get("token"), str)):
            raise ValueError("Unsupported configured A2A authentication")
        if any(c in auth.get("token", "") for c in "\r\n"):
            raise ValueError("Invalid authentication header")
    except (ValueError, TypeError, AttributeError) as exc:
        raise NotDispatched("Invalid A2A configuration") from exc
    body = {"jsonrpc": "2.0", "id": data["job_id"], "method": "SendMessage",
            "params": {"message": protocol.text_message(protocol.ROLE_USER, security.redact_outbound(_handoff(data, message)),
                                                       context_id=data["context_id"])}}
    if peer.get("tenant"):
        body["params"]["tenant"] = peer["tenant"]
    headers = {"Content-Type": "application/json", "A2A-Version": protocol.PROTOCOL_VERSION}
    auth = peer.get("auth") or {}
    if auth:
        if auth.get("type") != "bearer" or not auth.get("token"):
            raise NotDispatched("Unsupported configured A2A authentication")
        headers["Authorization"] = "Bearer " + auth["token"]
    try:
        request = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    except (ValueError, TypeError) as exc:
        raise NotDispatched("Invalid A2A request") from exc
    return request, timeout


def _a2a(home, data, message, peer):
    try:
        from plugins.platforms.a2a import protocol
        request, timeout = _a2a_request(data, message, peer)
        opener = urllib.request.build_opener(_NoRedirect)
    except Exception as exc:
        raise NotDispatched("A2A preflight failed; no request sent") from exc
    try:
        with opener.open(request, timeout=timeout) as response:
            result = json.load(response)
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, (ConnectionRefusedError, socket.gaierror)):
            raise NotDispatched("A2A connection was not established") from exc
        raise
    except (ConnectionRefusedError, socket.gaierror) as exc:
        raise NotDispatched("A2A connection was not established") from exc
    if result.get("id") != data["job_id"]:
        raise ValueError("A2A response request identity mismatch")
    if "error" in result:
        data.update(status="unknown", error=result["error"])
        return
    payload = protocol.unwrap_send_message_response(result["result"])
    context_id = payload.get("contextId")
    if context_id != data["context_id"]:
        raise ValueError("A2A response context identity mismatch")
    state = (payload.get("status") or {}).get("state", "")
    text = "\n".join(filter(None, [protocol.extract_text(a) for a in payload.get("artifacts", [])]))
    text = text or protocol.extract_text((payload.get("status") or {}).get("message") or payload)
    data.update(backend_id=payload.get("id") or payload.get("messageId"), backend_state=state, result=text)
    if state in {protocol.STATE_COMPLETED, protocol.STATE_INPUT_REQUIRED} or (not state and payload.get("messageId")):
        data["status"] = "completed" if state != protocol.STATE_INPUT_REQUIRED else "input_required"
    elif state == protocol.STATE_REJECTED:
        data["status"] = "failed"
    else:
        # Upstream can emit STATE_FAILED on an inbound future timeout without
        # stopping the agent. Neither that state nor its text proves cancellation.
        data.update(status="unknown", error="Peer completion is uncertain; do not retry or switch backend")


def _run(request_path):
    request = _read(request_path)
    home = Path(request["home"])
    _profile(home)
    root = _root(home)
    cid, job = _id(request["conversation_id"]), _id(request["job_id"])
    if request_path != root / (job + ".request"):
        raise ValueError("Request outside captured caller scope")
    with _locked(root, cid):
        data = _owned(root, cid, request["owner"])
        digest = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
        if data["job_id"] != job or data["status"] != "accepted" or data["request_digest"] != digest:
            raise ValueError("Stale, altered, or already dispatched request")
        if "initial_request_sha256" in request:
            initial_digest = hashlib.sha256(data["initial_request"].encode()).hexdigest()
            if initial_digest != request["initial_request_sha256"]:
                raise ValueError("Initial request changed after this turn was accepted; no dispatch")
        dispatch_entered = False
        stop_file = root / (job + ".stop")
        try:
            peer = _policy(home, data["target"], data["backend"], data.get("endpoint"), data.get("tenant", ""))
            data["deadline"] = request.get("deadline", time.time() + TURN_TIMEOUT)
            data["parent_pid"] = request.get("parent_pid")
            if _STOP_SIGNAL or stop_file.exists():
                # Cancelled while queued for this runner: nothing is dispatched.
                now = time.time()
                data.update(status="cancelled", error="Cancelled before dispatch; nothing ran",
                            cancel=dict(source="request", requested_at=now, confirmed_at=now, before_dispatch=True))
            else:
                data.update(status="running", started_at=time.time())
                _write(root / (cid + ".json"), data)
                dispatch_entered = True
            if dispatch_entered and data["backend"] == "resident":
                _resident(home, data, request["message"])
            elif dispatch_entered:
                from hermes_constants import set_hermes_home_override, reset_hermes_home_override
                token = set_hermes_home_override(home)
                try:
                    _a2a(home, data, request["message"], peer)
                finally:
                    reset_hermes_home_override(token)
        except Exception as exc:
            # Once launched, a transport exception is NOT proof that the peer stopped.
            data.update(status="unknown" if dispatch_entered and not isinstance(exc, NotDispatched) else "failed",
                        error=str(exc) if isinstance(exc, NotDispatched) else
                        f"{type(exc).__name__}: dispatch did not confirm completion; inspect status, do not retry")
        if data.get("turn_kind") == "reconcile" and data["status"] == "completed":
            # Bookkeeping succeeded; the conversation still never resumes work.
            data["status"] = "reconciled"
        _keep_reconcile_only(data)
        data["updated_at"] = time.time()
        _write(root / (cid + ".json"), data)
        if data["status"] != "unknown":
            request_path.unlink()
        stop_file.unlink(missing_ok=True)
    result = _public(data, root)
    if data.get("group"):
        # Read by the caller from the completion notification of a parallel batch.
        result["group_progress"] = _group_progress(root, data["owner"], data["group"])
    return result


def _keep_reconcile_only(data):
    # A cancelled reconcile turn must not turn an interrupted conversation into a
    # resumable one: it goes back to interrupted, still open to reconcile only.
    if data.get("turn_kind") == "reconcile" and data.get("status") == "cancelled":
        data["status"] = "interrupted"


def _owned_rows(root, owner):
    rows = []
    for path in root.glob("*.json"):
        with contextlib.suppress(OSError, ValueError, KeyError):
            data = _read(path)
            if data["owner"] == owner:
                rows.append(data)
    return rows


def _group_progress(root, owner, group):
    rows = [r for r in _owned_rows(root, owner) if r.get("group") == group and r.get("status") != "closed"]
    pending = sorted(r["conversation_id"] for r in rows if r.get("status") in ACTIVE)
    return dict(group=group, settled=len(rows) - len(pending), total=len(rows), pending=pending)


def _launch_failure(root, cid, owner, job, status):
    try:
        with _locked(root, cid):
            data = _owned(root, cid, owner)
            if data["job_id"] == job and data["status"] == "accepted":
                data.update(status=status, error="Launch rejected before dispatch" if status == "failed" else "Launch outcome unknown")
                _write(root / (cid + ".json"), data)
                if status == "failed":
                    (root / (job + ".request")).unlink(missing_ok=True)
            return data["status"]
    except ValueError:
        # A child may have started despite an ambiguous terminal response.
        # Never overwrite its running/completed state or remove its request.
        return _owned(root, cid, owner)["status"]


def _interrupt_probes():
    """(interrupted, yield_requested) for the current tool thread; inert outside Hermes."""
    try:
        from tools.interrupt import consume_yield, is_interrupted
    except ImportError:
        return (lambda: False), (lambda: False)
    tid = threading.current_thread().ident
    return is_interrupted, (lambda: consume_yield(tid))


def _request_stop(root, job):
    _write(root / (_id(job) + ".stop"), dict(requested_at=time.time()))


LAUNCH = Path(__file__).resolve().parent / "launch.py"


def _dependency_root():
    # The Hermes root whose installs/ hold this process's dependency generation, read once
    # at load, while the environment is the one this process was started with.
    try:
        from pm.environments import dependency_home_root
        return dependency_home_root()
    except Exception:
        return None


_DEPENDENCY_ROOT = _dependency_root()


def runner_command(script, *args):
    """Command that runs a plugin script's __main__ as its own process on the same Hermes
    runtime as this one. Hermes puts its checkout and dependency generation on the path
    inside its own bootstrap, so a bare `sys.executable script` child cannot even import
    hermes_yaml. launch.py repeats upstream's launcher bootstrap from a file: the same
    code passed as `python -c` makes the terminal guard ask for approval on every
    messaging call. The bootstrap finds the dependencies through HERMES_HOME, so pin it
    to this process's root rather than trust an inherited value (runners read their home
    from the request and strip HERMES_* for their own children). Outside a PM-managed
    install the plain interpreter is all there is."""
    try:
        from hermes_cli import _launchers
    except ImportError:
        return [sys.executable, str(script), *map(str, args)]
    root = Path(_launchers.__file__).resolve().parents[1]
    python = _launchers.resolve_store_python(root) or Path(sys.executable)
    command = [str(python), "-I", str(LAUNCH), str(root), str(script), *map(str, args)]
    return ["/usr/bin/env", f"HERMES_HOME={_DEPENDENCY_ROOT}", *command] if _DEPENDENCY_ROOT else command


def _reap_later(proc):
    # A detached runner stays this process's child (so it still dies with it); reap it.
    threading.Thread(target=proc.wait, name="specialist-runner-reaper", daemon=True).start()


DETACHED_NOTE = ("Running detached. Collect it with specialist_session(action='wait') before this turn ends: "
                 "a one-shot caller that exits takes its runners down with it.")


def _execute_sync(request_path, detach=False):
    request = _read(request_path)
    root = request_path.parent
    cid, owner = request["conversation_id"], request["owner"]
    try:
        # Output goes to the record; an unread pipe would block a runner with a long reply.
        proc = subprocess.Popen(runner_command(Path(__file__).resolve(), request_path),
                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                start_new_session=True)
    except OSError:
        _launch_failure(root, cid, owner, request["job_id"], "failed")
        return _public(_owned(root, cid, owner), root)
    if detach:
        _reap_later(proc)
        return dict(_public(_owned(root, cid, owner), root), detached=True, note=DETACHED_NOTE)
    # The per-call runner enforces the deadline and watches this process's death. A user
    # interrupt cancels the turn; a request to yield hands it over detached instead.
    interrupted, yielded = _interrupt_probes()
    while proc.returncode is None:
        try:
            proc.wait(timeout=0.5)
            break
        except subprocess.TimeoutExpired:
            pass
        if interrupted():
            _request_stop(root, request["job_id"])
            with contextlib.suppress(subprocess.TimeoutExpired):
                proc.wait(timeout=CANCEL_WAIT)
            if proc.returncode is None:
                _reap_later(proc)
                return dict(_public(_owned(root, cid, owner), root), cancel_requested=True,
                            note="Stop requested on interrupt; not yet confirmed. Check status; never resend before it settles.")
            break
        if yielded():
            _reap_later(proc)
            return dict(_public(_owned(root, cid, owner), root), detached=True, note=DETACHED_NOTE)
    with _locked(root, request["conversation_id"]):
        data = _owned(root, request["conversation_id"], request["owner"])
        if data["job_id"] == request["job_id"] and data["status"] in {"accepted", "running"}:
            data.update(status="failed" if data["status"] == "accepted" else "unknown",
                        error="Runner exited without confirming backend completion")
            _write(root / (request["conversation_id"] + ".json"), data)
            if data["status"] == "failed":
                request_path.unlink(missing_ok=True)
    return _public(_owned(root, request["conversation_id"], request["owner"]), root)


def specialist_call(args, **kwargs):
    try:
        if set(args) - {"target", "message", "conversation_id", "kind", "wait", "group"}:
            raise ValueError("Unexpected arguments; caller identity is runtime-owned")
        wait, group = args.get("wait", True), args.get("group")
        if type(wait) is not bool:
            raise ValueError("wait must be true or false")
        if group is not None and (not isinstance(group, str) or not GROUP.fullmatch(group)):
            raise ValueError("group must be 1-40 characters of [A-Za-z0-9._-]")
        home, owner, live, inbound = _scope()
        if not args.get("conversation_id") and "kind" not in args:
            raise ValueError("Initial calls require kind inquiry|work; all released/metered work must use work")
        target, message, kind = args.get("target"), args.get("message"), args.get("kind", "inquiry")
        if kind not in {"inquiry", "work", "reconcile"} or not isinstance(message, str) or not message.strip():
            raise ValueError("Nonempty message and kind inquiry|work|reconcile required")
        peer = _policy(home, target)
        if inbound and kind != "inquiry":
            raise ValueError("A2A inbound cannot deliver background work; reissue this unit through a resident session")
        if inbound and not wait:
            raise ValueError("A2A inbound inquiries are synchronous; wait=false has no completion delivery here")
        if kind == "reconcile" and not args.get("conversation_id"):
            raise ValueError("reconcile continues an interrupted resident conversation; conversation_id required")
        root = _root(home)
        cid = _id(args["conversation_id"]) if args.get("conversation_id") else uuid.uuid4().hex
        job = uuid.uuid4().hex
        with _locked(root, cid):
            if args.get("conversation_id"):
                data = _owned(root, cid, owner)
                if data["target"] != target:
                    raise ValueError("Target mismatch; no dispatch")
                if kind == "reconcile":
                    # The one permitted continuation of an interrupted conversation: the same
                    # resident session inspects and reconciles the child runs only it owns.
                    if data["backend"] != "resident" or data["status"] not in {"interrupted", "reconciled"}:
                        raise ValueError("reconcile requires a resident conversation already recorded as interrupted")
                    if not data.get("resident_id"):
                        raise ValueError("Interrupted conversation never established a resident session; nothing to reconcile")
                elif data["status"] in BUSY | {"interrupted", "reconciled", "closed"}:
                    raise ValueError("Conversation busy/uncertain/interrupted/closed; no dispatch")
                _policy(home, target, data["backend"], data.get("endpoint"), data.get("tenant", ""))
                if data["backend"] == "a2a" and kind == "work":
                    raise ValueError("A2A conversation is inquiry-only; release work as a new resident conversation")
                data["turn_kind"] = kind if kind == "reconcile" else None
                # A confirmed-stopped cancel is the one stopped turn that may be resumed;
                # the next handoff says so (see _handoff).
                data["after_cancel"] = data.get("cancel") if data["status"] == "cancelled" else None
                for stale in ("cancel", "cancel_too_late", "started_at", "exit_code"):
                    data.pop(stale, None)
            else:
                data = dict(conversation_id=cid, owner=owner, target=target,
                            backend="a2a" if kind == "inquiry" and peer.get("url") else "resident",
                            requester_profile=_profile(home), initial_request=message, initial_job_id=job)
                if data["backend"] == "a2a":
                    data.update(endpoint=peer["url"], tenant=peer.get("tenant") or "", context_id=uuid.uuid4().hex)
            if inbound and data["backend"] != "a2a":
                raise ValueError("A2A inbound supports short peer inquiries only; reissue through resident")
            if group:
                data["group"] = group
            if kind != "reconcile":
                active = [r for r in _owned_rows(root, owner)
                          if r.get("status") in ACTIVE and r.get("conversation_id") != cid]
                limit = _max_active(home)
                if len(active) >= limit:
                    raise ValueError(f"{len(active)} specialist conversations are already running for this session "
                                     f"(limit {limit}); wait for or cancel one first. Nothing was dispatched.")
            deadline = min(time.time() + TURN_TIMEOUT, float(os.environ.get("RESIDENT_DEADLINE", "inf")))
            if deadline <= time.time():
                raise ValueError("Inherited resident deadline has expired; no dispatch")
            request = dict(home=str(home), owner=owner, conversation_id=cid, job_id=job, message=message,
                            deadline=deadline, parent_pid=os.getpid() if not live else None)
            if "initial_request" in data:
                request["initial_request_sha256"] = hashlib.sha256(data["initial_request"].encode()).hexdigest()
            request_path = root / (job + ".request")
            data.update(job_id=job, status="accepted", result="", error="", process_session_id=None, pgid=None,
                        handoff_record=str(root / (job + ".handoff")),
                        updated_at=time.time(), request_digest=hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest())
            _write(root / (job + ".handoff"), dict(requester_profile=_profile(home),
                   conversation_id=cid, job_id=job, initial_job_id=data.get("initial_job_id"),
                   initial_request_sha256=request.get("initial_request_sha256"),
                   message=message, decision_source="agent-request", approval_verified=False))
            _write(request_path, request)
            _write(root / (cid + ".json"), data)
        if not live:
            # Messaging callers are always notified in the background; wait=false is the
            # CLI's way to start several conversations and collect them with wait.
            return json.dumps(_execute_sync(request_path, detach=True) if not wait else _execute_sync(request_path))
        from tools.terminal_tool import terminal_tool

        try:
            result = json.loads(terminal_tool(
                command=shlex.join(runner_command(Path(__file__).resolve(), request_path)),
                background=True, notify_on_complete=True, task_id=kwargs.get("task_id"), _host_local=True))
        except Exception:
            result = {"error": "Launch outcome unknown; inspect conversation status, do not retry", "exit_code": -1}
        process_id = result.get("session_id")
        # Separate receipt avoids racing the child's result write under its lock.
        _write(root / (job + ".receipt"), result)
        status = "accepted"
        if not process_id:
            rejected = result.get("status") in {"pending_approval", "error", "disabled", "degraded", "blocked", "rejected"}
            bare_tool_error = bool(result.get("error")) and "exit_code" not in result and "status" not in result
            status = _launch_failure(root, cid, owner, job,
                                     "failed" if not result.get("pid") and (rejected or bare_tool_error) else "unknown")
        return json.dumps(dict(conversation_id=cid, job_id=job, backend=data["backend"],
                               status=status, process_session_id=process_id,
                               notify_on_complete=bool(process_id and result.get("notify_on_complete") is not False),
                               launch=result))
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def _consume_notifications(root, rows):
    """A messaging caller that already holds a settled result (wait/cancel) must not get
    the same completion again as a separate turn: mark the background runner consumed."""
    try:
        from tools.process_registry import process_registry
    except ImportError:
        return
    for data in rows:
        receipt = root / (data["job_id"] + ".receipt")
        with contextlib.suppress(Exception):
            process_id = _read(receipt).get("session_id") if receipt.exists() else None
            if process_id:
                # The runner exits right after writing the record; wait() marks it consumed.
                process_registry.wait(process_id, timeout=3)


def _wait(home, root, owner, live, args):
    selectors = [k for k in ("conversation_id", "conversation_ids", "group") if args.get(k) is not None]
    if len(selectors) != 1:
        raise ValueError("wait needs exactly one of conversation_id, conversation_ids or group")
    mode, timeout = args.get("mode", "all"), args.get("timeout")
    if mode not in {"all", "any"}:
        raise ValueError("mode must be all or any")
    if timeout is not None and (type(timeout) not in (int, float) or timeout <= 0):
        raise ValueError("timeout must be a positive number of seconds")
    if selectors == ["conversation_ids"]:
        ids = args["conversation_ids"]
        if not isinstance(ids, list) or not ids or len(ids) > 16:
            raise ValueError("conversation_ids must list 1-16 conversation ids")
        cids = list(dict.fromkeys(_id(x) for x in ids))
    elif selectors == ["conversation_id"]:
        cids = [_id(args["conversation_id"])]
    else:
        group = args["group"]
        if not isinstance(group, str) or not GROUP.fullmatch(group):
            raise ValueError("group must be 1-40 characters of [A-Za-z0-9._-]")
        cids = sorted(r["conversation_id"] for r in _owned_rows(root, owner)
                      if r.get("group") == group and r.get("status") != "closed")
        if not cids:
            raise ValueError("No open conversations in this group")
    for cid in cids:
        data = _owned(root, cid, owner)
        _policy(home, data["target"], data["backend"], data.get("endpoint"), data.get("tenant", ""))
    limit = _wait_limit(home, timeout)
    interrupted, yielded = _interrupt_probes()
    started, released = time.monotonic(), None
    while True:
        rows = [_owned(root, cid, owner) for cid in cids]
        pending = [r["conversation_id"] for r in rows if r["status"] in ACTIVE]
        if not pending or (mode == "any" and len(pending) < len(rows)):
            break
        if interrupted():
            released = "interrupt"
            break
        if yielded():
            released = "user_message"
            break
        if time.monotonic() - started >= limit:
            break
        time.sleep(WAIT_POLL)
    settled = [r for r in rows if r["status"] not in ACTIVE]
    if live:
        _consume_notifications(root, settled)
    done = not pending or (mode == "any" and settled)
    result = dict(mode=mode, waited_seconds=int(time.monotonic() - started), limit_seconds=int(limit),
                  timed_out=not done and released is None, released_by=released, pending=pending,
                  conversations=[_public(r, root) for r in rows])
    if released:
        result["note"] = ("Released by a new message; nothing was stopped. Answer it, then wait again "
                          "or let the completions arrive.")
    elif not done:
        result["note"] = ("Wait limit reached; nothing was stopped. Report that the work is still in progress; "
                          "wait again later (CLI) or let the completions arrive (messaging).")
    return result


def _cancel(home, root, owner, live, cid):
    data = _owned(root, cid, owner)
    if data["backend"] != "resident":
        raise ValueError("A2A inquiries cannot be cancelled: the peer offers no stop. Wait for the reply; "
                         "release cancellable work as kind=work")
    if data["status"] not in ACTIVE:
        hint = "; inspect and reconcile instead" if data["status"] == "unknown" else ""
        raise ValueError(f"Nothing to cancel: status is {data['status']}{hint}")
    job = data["job_id"]
    with _try_locked(root, cid) as held:
        if held:
            data = _owned(root, cid, owner)
            if data["job_id"] == job and data["status"] == "accepted":
                # Not picked up by a runner yet: cancel in place; the runner will find no request.
                now = time.time()
                data.update(status="cancelled", error="Cancelled before dispatch; nothing ran", updated_at=now,
                            cancel=dict(source="request", requested_at=now, confirmed_at=now, before_dispatch=True))
                _keep_reconcile_only(data)
                _write(root / (cid + ".json"), data)
                (root / (job + ".request")).unlink(missing_ok=True)
                if live:
                    _consume_notifications(root, [data])
                return dict(_public(data, root), cancel_requested=True)
            if data["status"] in ACTIVE:
                raise ValueError("No live runner holds this conversation; inspect and reconcile instead")
            return dict(_public(data, root), cancel_requested=False)
    _request_stop(root, job)
    interrupted, _ = _interrupt_probes()
    until = time.monotonic() + CANCEL_WAIT
    while time.monotonic() < until and not interrupted():
        data = _owned(root, cid, owner)
        if data["job_id"] != job or data["status"] not in ACTIVE:
            break
        time.sleep(0.25)
    data = _owned(root, cid, owner)
    result = dict(_public(data, root), cancel_requested=True)
    if data["status"] in ACTIVE:
        result["note"] = "Stop requested; not yet confirmed. Check status again; never resend before it settles."
    else:
        if live:
            _consume_notifications(root, [data])
        if data.get("cancel_too_late"):
            result["note"] = "The turn finished before the stop reached it; its result stands."
    return result


SESSION_ARGS = {"action", "conversation_id", "evidence", "conversation_ids", "group", "mode", "timeout"}


def specialist_session(args, **kwargs):
    try:
        if set(args) - SESSION_ARGS:
            raise ValueError("Unexpected arguments")
        if "evidence" in args and args.get("action") != "reconcile":
            raise ValueError("evidence is only accepted for reconcile")
        if {"conversation_ids", "group", "mode", "timeout"} & set(args) and args.get("action") != "wait":
            raise ValueError("conversation_ids, group, mode and timeout are only accepted for wait")
        home, owner, live, _ = _scope()
        root = _root(home)
        action = args.get("action")
        if action == "wait":
            return json.dumps(_wait(home, root, owner, live, args))
        if action == "list":
            rows = []
            for path in root.glob("*.json"):
                data = _read(path)
                if data["owner"] == owner:
                    try:
                        _policy(home, data["target"], data["backend"], data.get("endpoint"), data.get("tenant", ""))
                    except ValueError:
                        continue
                    rows.append(_public(data, root))
            return json.dumps(rows)
        cid = _id(args.get("conversation_id"))
        # Status remains readable during the child-held lock: writes are atomic.
        data = _owned(root, cid, owner)
        _policy(home, data["target"], data["backend"], data.get("endpoint"), data.get("tenant", ""))
        if action == "status":
            return json.dumps(_public(data, root))
        if action == "cancel":
            return json.dumps(_cancel(home, root, owner, live, cid))
        if action == "reconcile":
            evidence = args.get("evidence")
            if not isinstance(evidence, str) or not evidence.strip() or len(evidence) > 8000:
                raise ValueError("Reconcile requires a bounded account of inspected outputs, child jobs and external effects")
            with _locked(root, cid):
                data = _owned(root, cid, owner)
                _policy(home, data["target"], data["backend"], data.get("endpoint"), data.get("tenant", ""))
                if data["backend"] != "resident":
                    raise ValueError("A2A has no owned local liveness evidence; keep unknown and obtain peer confirmation, never replay")
                if data["status"] not in {"running", "unknown"} or _group_alive(data.get("pgid")):
                    raise ValueError("Reconcile requires uncertain work and a recorded, confirmed-stopped process group")
                lock = home / "resident-sessions" / (cid + ".lock")
                lock_observation = "absent"
                if lock.exists() or lock.is_symlink():
                    # A crash may leave our dead shell's lock. Preserve it as evidence;
                    # never infer ownership from its age or reclaim another holder's lock.
                    if lock.is_symlink() or not lock.is_dir():
                        raise ValueError("Resident lock owner cannot be verified")
                    try:
                        holder = _read(lock / "pid")
                    except (OSError, ValueError):
                        raise ValueError("Resident lock owner cannot be verified") from None
                    if type(holder) is not int or holder != data["pgid"]:
                        raise ValueError("Resident lock belongs to another or unknown process")
                    lock_observation = "retained_owned_dead"
                previous = data["status"]
                data.update(status="interrupted", updated_at=time.time(), reconciliation={
                    "previous_status": previous, "transport_stopped": True, "lock": lock_observation,
                    "effects": "unknown", "evidence": evidence, "evidence_source": "caller-report",
                    "resume_permitted": False,
                })
                _write(root / (cid + ".json"), data)
            return json.dumps(_public(data, root))
        if action != "close":
            raise ValueError("Action must be status, list, wait, cancel, reconcile, or close")
        with _locked(root, cid):
            data = _owned(root, cid, owner)
            if data["status"] in BUSY:
                raise ValueError("Cannot close active or uncertain work; close is not cancellation")
            if data["backend"] == "resident" and (home / "resident-sessions" / (cid + ".json")).exists():
                result = subprocess.run(["/bin/sh", str(RESIDENT), "close", cid],
                                        env=_child_env(home), capture_output=True, text=True, timeout=30)
                if result.returncode:
                    raise ValueError("Resident close failed; registry left open")
            data["status"] = "closed"
            _write(root / (cid + ".json"), data)
        return json.dumps(_public(data, root))
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def register(ctx):
    if ctx.profile_name not in TARGETS:
        return
    from hermes_constants import get_hermes_home
    identity = (ctx.profile_name, str(get_hermes_home().resolve()))

    def scoped(handler):
        def invoke(args, **kwargs):
            from gateway.session_context import scoped_current_session_id
            token = _REGISTRATION.set(identity)
            turn_token = _TURN_SESSION.set(kwargs.get("task_id") or "")
            try:
                # Framework kwargs, never model JSON. Also repairs the official
                # terminal notification's parent-session stamp on cached turns.
                with scoped_current_session_id(kwargs.get("session_id")):
                    return handler(args, **kwargs)
            finally:
                _TURN_SESSION.reset(turn_token)
                _REGISTRATION.reset(token)
        return invoke
    for name, handler, properties, required, description in [
        ("specialist_call", specialist_call,
         {"target": {"type": "string"}, "message": {"type": "string"},
          "conversation_id": {"type": "string"}, "kind": {"type": "string", "enum": ["inquiry", "work", "reconcile"],
                                                     "description": "Required on initial calls; continuations retain their backend. reconcile: one inspect-and-reconcile turn on a conversation already recorded as interrupted (no work)."},
          "wait": {"type": "boolean", "description": "CLI only (messaging always runs in the background). false: return at once with the conversation_id so several conversations run in parallel; collect them with specialist_session wait before this turn ends."},
          "group": {"type": "string", "description": "Optional label ([A-Za-z0-9._-], max 40) shared by parallel conversations, e.g. one comparison; wait and completion notices report its progress."}},
         ["target", "message"], "Call an allowed specialist. Short inquiry uses a configured A2A peer; all released/metered work uses resident. Continue with the returned conversation_id. Independent conversations may run in parallel (up to specialist_call.max_active per session). Never retry uncertain work. A cancelled conversation may be continued with a corrected message; an interrupted one accepts only kind=reconcile, so its owning session can reconcile the child runs it holds."),
        ("specialist_session", specialist_session,
         {"action": {"type": "string", "enum": ["status", "list", "wait", "cancel", "reconcile", "close"]}, "conversation_id": {"type": "string"},
          "conversation_ids": {"type": "array", "items": {"type": "string"}, "description": "Wait only: the conversations to wait for (or use conversation_id or group)."},
          "group": {"type": "string", "description": "Wait only: wait for every open conversation with this group label."},
          "mode": {"type": "string", "enum": ["all", "any"], "description": "Wait only: return when all (default) or any of them settle."},
          "timeout": {"type": "number", "description": "Wait only: seconds; capped by specialist_call.wait_timeout and this caller's tool deadline."},
          "evidence": {"type": "string", "description": "Reconcile only: observations of outputs, child jobs and external effects; not proof of completion."}},
          ["action"], "Inspect, wait for, cancel or close your own specialist conversations. wait blocks without spending turns and returns early on a new user message, never stopping work. cancel stops a running resident turn and waits until the stop is confirmed (status cancelled; continue with specialist_call and a corrected message) or reports it unconfirmed. Reconcile confirms a stopped resident transport, never completion or safe replay. Close does not cancel work."),
    ]:
        ctx.register_tool(name=name, toolset="specialist", handler=scoped(handler), description=description,
                          schema={"name": name, "description": description,
                                  "parameters": {"type": "object", "properties": properties,
                                                 "required": required, "additionalProperties": False}})


def _on_stop_signal(*_):
    # Runner only: turn TERM/INT/HUP (cancel, /stop reaping, shutdown) into an orderly
    # stop of its own resident group instead of dying and orphaning it.
    global _STOP_SIGNAL
    _STOP_SIGNAL = True


if __name__ == "__main__":
    for _name in ("SIGTERM", "SIGINT", "SIGHUP"):
        signal.signal(getattr(signal, _name), _on_stop_signal)
    result = _run(Path(sys.argv[1]))
    print(json.dumps(result))
    if result["status"] not in {"completed", "input_required"}:
        raise SystemExit(result.get("exit_code") or 1)
