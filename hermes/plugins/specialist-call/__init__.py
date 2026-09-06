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
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.error
import urllib.parse
import uuid

import yaml


# Role policy is deliberately NOT inferred from the A2A endpoint inventory.
TARGETS = {
    "assistant": {"engineer", "creator", "marketer", "writer", "searcher"},
    "creator": {"researcher"},
}
RESIDENT = Path(__file__).resolve().parents[2] / "profiles/assistant/scripts/resident-session.sh"
TURN_TIMEOUT = 5400
BUSY = {"accepted", "running", "unknown"}
_REGISTRATION = contextvars.ContextVar("specialist_registration", default=None)
_TURN_SESSION = contextvars.ContextVar("specialist_turn_session", default="")


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
        raise ValueError("specialist tools are restricted to assistant and creator")
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


def _policy(home, target, backend=None, endpoint=None, tenant=""):
    profile = _profile(home)
    if target not in TARGETS[profile]:
        raise ValueError("Target is not permitted for this caller")
    # Read, never load_config(): upstream may rewrite configuration on load.
    config = yaml.safe_load((home / "config.yaml").read_text()) or {}
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
    result = {k: v for k, v in data.items() if k not in {"owner", "endpoint", "tenant", "request_digest", "parent_pid"}}
    if root is not None:
        receipt = root / (data["job_id"] + ".receipt")
        if receipt.exists():
            result["process_session_id"] = _read(receipt).get("session_id")
    return result


def _child_env(home, deadline=None):
    # Keep provider credentials, but NEVER inherit the multiplex caller or script tunables.
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HERMES_", "RESIDENT_"))
           and k not in {"HERMES", "TURN_TIMEOUT", "POLL_INTERVAL", "KILL_GRACE", "LOCK_STALE_AFTER"}}
    env.update(RESIDENT_SESSION_DIR=str(home / "resident-sessions"),
               TURN_TIMEOUT=str(TURN_TIMEOUT), POLL_INTERVAL="1", KILL_GRACE="10")
    if deadline is not None:
        env["RESIDENT_DEADLINE"] = str(deadline)
    return env


def _resident(home, data, message):
    root = _root(home)
    reg = home / "resident-sessions" / (data["conversation_id"] + ".json")
    data["log"] = str(reg.with_suffix(".log"))
    fd, prompt = tempfile.mkstemp(dir=root, suffix=".txt")
    proc = None
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(message)
        cmd = ["/bin/sh", str(RESIDENT), "send" if data.get("resident_id") else "start", data["conversation_id"]]
        if not data.get("resident_id"):
            cmd += ["--profile", data["target"]]
        cmd += ["-f", prompt]
        deadline = data["deadline"]
        if time.time() >= deadline:
            raise NotDispatched("Resident deadline expired before launch")
        try:
            proc = subprocess.Popen(cmd, env=_child_env(home, deadline), stdin=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
        except OSError as exc:
            raise NotDispatched("Resident process could not be spawned") from exc
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
            "params": {"message": protocol.text_message(protocol.ROLE_USER, security.redact_outbound(message),
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
        dispatch_entered = False
        try:
            peer = _policy(home, data["target"], data["backend"], data.get("endpoint"), data.get("tenant", ""))
            data["deadline"] = request.get("deadline", time.time() + TURN_TIMEOUT)
            data["parent_pid"] = request.get("parent_pid")
            data["status"] = "running"
            _write(root / (cid + ".json"), data)
            dispatch_entered = True
            if data["backend"] == "resident":
                _resident(home, data, request["message"])
            else:
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
        data["updated_at"] = time.time()
        _write(root / (cid + ".json"), data)
        if data["status"] != "unknown":
            request_path.unlink()
    return _public(data, root)


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


def _execute_sync(request_path):
    request = _read(request_path)
    root = request_path.parent
    try:
        proc = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), str(request_path)],
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, start_new_session=True)
    except OSError:
        _launch_failure(root, request["conversation_id"], request["owner"], request["job_id"], "failed")
        return _public(_owned(root, request["conversation_id"], request["owner"]), root)
    # The per-call runner enforces the deadline and watches this process's death.
    proc.communicate()
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
        if set(args) - {"target", "message", "conversation_id", "kind"}:
            raise ValueError("Unexpected arguments; caller identity is runtime-owned")
        home, owner, live, inbound = _scope()
        if not args.get("conversation_id") and "kind" not in args:
            raise ValueError("Initial calls require kind inquiry|work; all released/metered work must use work")
        target, message, kind = args.get("target"), args.get("message"), args.get("kind", "inquiry")
        if kind not in {"inquiry", "work"} or not isinstance(message, str) or not message.strip():
            raise ValueError("Nonempty message and kind inquiry|work required")
        peer = _policy(home, target)
        if inbound and kind == "work":
            raise ValueError("A2A inbound cannot deliver background work; reissue this unit through a resident session")
        root = _root(home)
        cid = _id(args["conversation_id"]) if args.get("conversation_id") else uuid.uuid4().hex
        job = uuid.uuid4().hex
        with _locked(root, cid):
            if args.get("conversation_id"):
                data = _owned(root, cid, owner)
                if data["target"] != target or data["status"] in BUSY | {"closed"}:
                    raise ValueError("Target mismatch or conversation busy/uncertain/closed; no dispatch")
                _policy(home, target, data["backend"], data.get("endpoint"), data.get("tenant", ""))
                if data["backend"] == "a2a" and kind == "work":
                    raise ValueError("A2A conversation is inquiry-only; release work as a new resident conversation")
            else:
                data = dict(conversation_id=cid, owner=owner, target=target,
                            backend="a2a" if kind == "inquiry" and peer.get("url") else "resident")
                if data["backend"] == "a2a":
                    data.update(endpoint=peer["url"], tenant=peer.get("tenant") or "", context_id=uuid.uuid4().hex)
            if inbound and data["backend"] != "a2a":
                raise ValueError("A2A inbound supports short peer inquiries only; reissue through resident")
            deadline = min(time.time() + TURN_TIMEOUT, float(os.environ.get("RESIDENT_DEADLINE", "inf")))
            if deadline <= time.time():
                raise ValueError("Inherited resident deadline has expired; no dispatch")
            request = dict(home=str(home), owner=owner, conversation_id=cid, job_id=job, message=message,
                           deadline=deadline, parent_pid=os.getpid() if not live else None)
            request_path = root / (job + ".request")
            data.update(job_id=job, status="accepted", result="", error="", process_session_id=None,
                        updated_at=time.time(), request_digest=hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest())
            _write(request_path, request)
            _write(root / (cid + ".json"), data)
        if not live:
            return json.dumps(_execute_sync(request_path))
        from tools.terminal_tool import terminal_tool

        try:
            result = json.loads(terminal_tool(
                command=shlex.join([sys.executable, str(Path(__file__).resolve()), str(request_path)]),
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


def specialist_session(args, **kwargs):
    try:
        if set(args) - {"action", "conversation_id"}:
            raise ValueError("Unexpected arguments")
        home, owner, _, _ = _scope()
        root = _root(home)
        action = args.get("action")
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
        if action != "close":
            raise ValueError("Action must be status, list, or close")
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
          "conversation_id": {"type": "string"}, "kind": {"type": "string", "enum": ["inquiry", "work"],
                                                     "description": "Required on initial calls; continuations retain their backend."}},
         ["target", "message"], "Call an allowed specialist. Short inquiry uses a configured A2A peer; all released/metered work uses resident. Continue with the returned conversation_id. Never retry uncertain work."),
        ("specialist_session", specialist_session,
         {"action": {"type": "string", "enum": ["status", "list", "close"]}, "conversation_id": {"type": "string"}},
         ["action"], "Inspect or close your originating session's specialist conversations. Close does not cancel work."),
    ]:
        ctx.register_tool(name=name, toolset="specialist", handler=scoped(handler), description=description,
                          schema={"name": name, "description": description,
                                  "parameters": {"type": "object", "properties": properties,
                                                 "required": required, "additionalProperties": False}})


if __name__ == "__main__":
    result = _run(Path(sys.argv[1]))
    print(json.dumps(result))
    if result["status"] not in {"completed", "input_required"}:
        raise SystemExit(result.get("exit_code") or 1)
