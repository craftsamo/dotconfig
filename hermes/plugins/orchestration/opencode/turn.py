"""Reading a run from the service. The plugin keeps no run record: a turn's state is
derived each time from the session's messages (the `idle` marker closes a turn and
carries its outcome), the active-session list, pending permission requests and
forms, and the session's own metadata.
"""

from __future__ import annotations

import contextlib
import importlib.util
import os
from pathlib import Path
import re
import sys
import time


def _load(name, filename):
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parent / filename)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


api = _load("hermes_opencode_api", "api.py")
config = _load("hermes_opencode_config", "config.py")

POLL = 2.0
# A turn that is neither running nor closed by an idle marker for this long ended
# without an outcome (the service restarted or crashed under it).
NO_OUTCOME_GRACE = 30
# How long an unreachable service is retried before the outcome is called unknown.
UNREACHABLE_GRACE = 120
# How often a wait looks for a provider retry, and from which attempt a retry that
# is not a usage/rate limit (a 502, an overload) hands back.
RETRY_POLL = 10.0
RETRY_HANDBACK_ATTEMPTS = 3
DEFAULT_TOOL_TIMEOUT = 420
# OpenCode's own split: limits retry with backoff or fail at once, so a caller
# that waits on them may wait on.
LIMIT_ERROR = re.compile(r"usage[-_\s]?limit|quota|insufficient[-_\s]?(?:quota|balance)|limit (?:exhausted|reached)|"
                         r"rate[-_\s]?limit|too[-_\s]?many[-_\s]?requests|overloaded|\b(?:429|529)\b", re.I)
AUTH_ERROR = re.compile(r"credential|unauthori[sz]ed|\b401\b|expired|api[-_\s]?key|ProviderAuthError", re.I)
PROBLEM_HINTS = {
    "limit": "The provider refused for usage or rate limits: continue with the role's alternate from "
             "opencode_catalog models (else another listed model); a read-only run can simply rerun, for a "
             "write run read the diff first.",
    "auth": "OpenCode's login for this provider is missing or expired: tell the Client, or continue with "
            "another provider's model.",
}


def call(method, template, data=None, query=None, **segments):
    return api.call(method, api.path(template, query, **segments), data)


def session_info(sid):
    return api.data(call("get", "/api/session/{sid}", sid=sid))


def active():
    return api.data(call("get", "/api/session/active"))


def hermes_meta(info):
    meta = (info.get("metadata") or {}).get("hermes")
    return meta if isinstance(meta, dict) else {}


def owned(info, owner):
    """The session's Hermes binding; raises unless it was bound by this caller."""
    meta = hermes_meta(info)
    if not meta or meta.get("owner") != owner:
        raise ValueError("Session is not bound to this conversation (topic, sender and profile) or CLI session")
    return meta


def directory_of(info):
    return (info.get("location") or {}).get("directory")


def running_in(directory, same, exclude=()):
    """Session ids the service is running in this worktree, from any profile or person."""
    found = []
    for sid in active():
        if sid in exclude:
            continue
        with contextlib.suppress(api.ApiError):
            if same(directory_of(session_info(sid)), directory):
                found.append(sid)
    return found


def in_tree(root_sid, sid, cache):
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
            current = session_info(current).get("parentID")
        except api.ApiError:
            break
    cache.update(dict.fromkeys(chain, False))
    return False


def _field(item):
    out = {key: item[key] for key in ("key", "title", "description", "type") if item.get(key) is not None}
    options = [{k: o.get(k) for k in ("value", "label", "description") if o.get(k) is not None}
               for o in item.get("options") or [] if isinstance(o, dict)]
    if options:
        out["options"] = options
    if item.get("custom") is not None:
        out["custom"] = item["custom"]
    return out


def pending(root_sid, directory, cache):
    """Permission requests and forms (questions) this run's sessions are paused on."""
    out = []
    where = api.location(directory)
    for item in api.data(call("get", "/api/permission/request", query=where), list):
        sid = item.get("sessionID")
        if isinstance(sid, str) and in_tree(root_sid, sid, cache):
            out.append({"kind": "permission", "id": item.get("id"), "session_id": sid, "subagent": sid != root_sid,
                        "action": item.get("action"), "resources": item.get("resources") or [],
                        "save": item.get("save") or [], "message": item.get("message")})
    for item in api.data(call("get", "/api/form", query=where), list):
        sid = item.get("sessionID")
        if isinstance(sid, str) and in_tree(root_sid, sid, cache):
            kind = (item.get("metadata") or {}).get("kind")
            out.append({"kind": "question" if kind == "question" else "form", "id": item.get("id"),
                        "session_id": sid, "subagent": sid != root_sid, "title": item.get("title"),
                        "fields": [_field(f) for f in item.get("fields") or [] if isinstance(f, dict)]})
    return out


def text(message):
    return "\n".join(part["text"] for part in message.get("content") or []
                     if part.get("type") == "text" and isinstance(part.get("text"), str))


def latest_turn(sid):
    """The newest turn: where it started (its first user message), its outcome when an
    idle marker closed it, and the newest assistant text in it.

    A turn runs from the first prompt after the session was last idle to the next idle
    marker, so prompts steered in while it was busy belong to the same turn."""
    body = call("get", "/api/session/{sid}/message", query={"order": "desc", "limit": 100}, sid=sid)
    start = outcome = reply = None
    for message in api.data(body, list):
        kind = message.get("type")
        if kind == "idle":
            if start is not None:
                break
            outcome = outcome or message.get("outcome") or "failed"
        elif kind == "user":
            start = message.get("id")
        elif kind == "assistant" and reply is None and text(message):
            reply = text(message)
    return {"start": start, "outcome": outcome, "reply": reply}


def latest_assistant(sid, after=None):
    """The session's newest assistant message, or None (none since `after`)."""
    body = call("get", "/api/session/{sid}/message", query={"order": "desc", "limit": 10}, sid=sid)
    for message in api.data(body, list):
        if after and message.get("id") == after:
            return None
        if message.get("type") == "assistant":
            return message
    return None


def provider_problem(error, model):
    """A provider failure as the caller needs it: limit, auth or other, with its text."""
    inner = error.get("data") if isinstance(error, dict) and isinstance(error.get("data"), dict) else {}
    if isinstance(error, dict):
        message = str(error.get("message") or inner.get("message") or error.get("name") or error.get("type") or "")
        status = error.get("statusCode") or inner.get("statusCode")
        label = " ".join(str(v) for v in (error.get("name"), error.get("type"), status) if v)
    else:
        message, label = str(error or ""), ""
    probe = f"{message} {label}"
    kind = "limit" if LIMIT_ERROR.search(probe) else "auth" if AUTH_ERROR.search(probe) else "other"
    model = model if isinstance(model, dict) else {}
    engine = f"{model.get('providerID')}/{model.get('id')}" if model.get("id") else None
    return {"kind": kind, "message": message[:500] or label or "unknown provider error",
            **({"model": engine} if engine else {})}


def retrying(root_sid, start, running_sessions, cache):
    """A provider retry OpenCode is sitting in for this run (root or subagent), or None."""
    for sid in [root_sid] + sorted(s for s in running_sessions if s != root_sid and in_tree(root_sid, s, cache)):
        message = latest_assistant(sid, start if sid == root_sid else None)
        retry = (message or {}).get("retry")
        if isinstance(retry, dict):
            return {"session_id": sid, "subagent": sid != root_sid, "attempt": retry.get("attempt"),
                    "next_at": retry.get("at"), **provider_problem(retry.get("error"), message.get("model"))}
    return None


def actionable(retry):
    """A retry worth the caller's decision: a limit at once, anything else after a few attempts."""
    return bool(retry) and (retry.get("kind") == "limit" or (retry.get("attempt") or 0) >= RETRY_HANDBACK_ATTEMPTS)


def failure(sid, start):
    """Why a failed turn failed, from its last assistant message's provider error."""
    with contextlib.suppress(api.ApiError, api.Unavailable):
        message = latest_assistant(sid, start)
        if message and message.get("error"):
            return provider_problem(message["error"], message.get("model"))
    return None


def changes(sid, start):
    """The turn's changed files as OpenCode computes them (per-turn snapshots)."""
    body = call("get", "/api/session/{sid}/diff", query={"from": start}, sid=sid)
    items = body.get("data") if isinstance(body, dict) else body
    return [{key: item.get(key) for key in ("file", "status", "additions", "deletions")}
            for item in (items or [])[:200] if isinstance(item, dict)]


def halt(sid):
    """Interrupt the run (subagent sessions stop with it) and drop parked input."""
    with contextlib.suppress(api.ApiError):
        call("post", "/api/session/{sid}/interrupt", sid=sid)
    with contextlib.suppress(api.ApiError, api.Unavailable):
        for item in api.data(call("get", "/api/session/{sid}/inbox", sid=sid), list):
            with contextlib.suppress(api.ApiError):
                call("delete", "/api/session/{sid}/inbox/{inbox}", sid=sid, inbox=item["id"])


# --------------------------------------------------------------------------
# The record handed to the caller


def describe(sid, info, status, *, turn=None, found=(), extra=None):
    """One run's state for the caller. `info` is the session as the service reports it."""
    meta = hermes_meta(info)
    model = info.get("model") or {}
    record = {"session_id": sid, "role": meta.get("role"), "directory": directory_of(info),
              "branch": meta.get("branch"), "agent": info.get("agent"), "status": status}
    if model.get("id"):
        record["engine"] = f"{model.get('providerID')}/{model['id']}" + (f"#{model['variant']}"
                                                                          if model.get("variant") else "")
    if turn and turn.get("outcome"):
        record["outcome"] = turn["outcome"]
    if info.get("tokens"):
        record["tokens"] = info["tokens"]
    if found:
        record["pending"] = list(found)
    record.update({k: v for k, v in (extra or {}).items() if v not in (None, [], "")})
    return record


def note(record):
    status = record["status"]
    if status == "waiting":
        return ("OpenCode is paused on the pending request(s). Answer each with opencode_request reply: a permission "
                "request once within the Client's approved scope, otherwise reject with a reason; a question "
                "with its answer. They stay pending until answered.")
    if status == "running" and record.get("retrying"):
        retry = record["retrying"]
        who = "a subagent of the run" if retry.get("subagent") else "the run"
        return (f"OpenCode keeps retrying {retry.get('model') or 'the model'} for {who} after: "
                f"{retry.get('message')} (attempt {retry.get('attempt')}). Wait on (opencode_session wait with "
                "through_retry) if it should recover soon; otherwise interrupt it and run again on the same session "
                "with model= another one from opencode_catalog models.")
    if status == "running":
        return ("Still running. Wait again, steer, or interrupt; never start another turn on this session while "
                "it runs.")
    if status == "unknown":
        return ("OpenCode could not confirm how this turn ended. Read the diff and the worktree before sending "
                "another turn; never replay the original prompt blindly.")
    return None


def wait_limit(home, settings, requested=None):
    """Longest a blocking wait may run: below the caller's own tool deadline (else the
    executor abandons the call into polling), the inherited resident deadline, the
    configured wait_timeout and the request."""
    tools = (config.read(home).get("timeouts") or {}).get("tools") or {}
    tool = tools.get("sequential_call", tools.get("concurrent_batch", DEFAULT_TOOL_TIMEOUT))
    tool = tool if isinstance(tool, (int, float)) and not isinstance(tool, bool) else DEFAULT_TOOL_TIMEOUT
    limits = [settings["wait_timeout"]]
    if requested is not None:
        limits.append(requested)
    if tool > 0:
        limits.append(tool - 30)
    with contextlib.suppress(ValueError, TypeError):
        limits.append(float(os.environ.get("RESIDENT_DEADLINE", "inf")) - time.time() - 5)
    return max(1.0, min(limits))


def await_turn(sid, limit, *, through_retry=False, poll=None, sleep=time.sleep, clock=time.time):
    """Block until the newest turn hands back to the caller, or `limit` seconds pass.

    Handing back means: the turn finished (an idle marker closed it), it is paused on a
    permission request or question, it is stuck in a provider retry worth a decision, or
    its outcome cannot be confirmed. Nothing is written anywhere."""
    poll = POLL if poll is None else poll
    deadline = clock() + limit
    cache, last_retry = {}, None
    unseen = unreachable = None
    retry = None
    while True:
        now = clock()
        try:
            info = session_info(sid)
            running_sessions = active()
            running = sid in running_sessions
            turn = latest_turn(sid)
            found = pending(sid, directory_of(info), cache)
            unreachable = None
        except api.Unavailable:
            unreachable = unreachable or now
            if now - unreachable >= UNREACHABLE_GRACE:
                record = {"session_id": sid, "status": "unknown",
                          "error": "OpenCode service unreachable; the turn's outcome is not confirmed"}
                return {**record, "note": note(record)}
            sleep(poll)
            continue
        except api.ApiError as exc:
            record = {"session_id": sid, "status": "unknown",
                      "error": f"OpenCode session no longer readable ({exc.status})"}
            return {**record, "note": note(record)}
        if not running and turn["outcome"]:
            return finished(sid, info, turn)
        if found:
            return with_note(describe(sid, info, "waiting", turn=turn, found=found))
        if not running and turn["start"] is None:
            return describe(sid, info, "idle")
        if running:
            unseen = None
            if not through_retry and (last_retry is None or now - last_retry >= RETRY_POLL):
                last_retry = now
                with contextlib.suppress(api.ApiError, api.Unavailable):
                    retry = retrying(sid, turn["start"], running_sessions, cache)
                if actionable(retry):
                    return with_note(describe(sid, info, "running", turn=turn, extra={"retrying": retry}))
        else:
            unseen = unseen or now
            if now - unseen >= NO_OUTCOME_GRACE:
                record = describe(sid, info, "unknown", turn=turn, extra={
                    "error": "The turn ended without an outcome (the OpenCode service restarted or stopped it)",
                    "changes": safe_changes(sid, turn["start"])})
                return with_note(record)
        if now >= deadline:
            if running:
                return with_note(describe(sid, info, "running", turn=turn, extra={"timed_out": True}))
            return with_note(describe(sid, info, "unknown", turn=turn, extra={
                "error": "The session is not running and no idle marker closed its newest turn",
                "changes": safe_changes(sid, turn["start"])}))
        sleep(min(poll, max(0.0, deadline - now)))


def safe_changes(sid, start):
    if not start:
        return None
    with contextlib.suppress(api.ApiError, api.Unavailable):
        return changes(sid, start)
    return None


def with_note(record):
    message = note(record)
    return {**record, "note": message} if message else record


def finished(sid, info, turn):
    outcome = turn["outcome"]
    status = {"succeeded": "completed", "interrupted": "interrupted"}.get(outcome, "failed")
    extra = {"result": turn["reply"], "changes": safe_changes(sid, turn["start"])}
    if status == "failed":
        problem = failure(sid, turn["start"])
        message = "OpenCode reported a failed turn"
        if problem:
            message += f" ({problem.get('model', 'model')}: {problem['message']})"
        message += "; partial effects may exist"
        if problem and problem["kind"] in PROBLEM_HINTS:
            message += ". " + PROBLEM_HINTS[problem["kind"]]
        extra.update(error=message, provider_error=problem)
    elif status == "interrupted":
        extra["error"] = "Interrupted before finishing"
    return describe(sid, info, status, turn=turn, extra=extra)


def snapshot(sid):
    """The run's current state without waiting."""
    record = await_turn(sid, 0, poll=0, sleep=lambda _: None)
    record.pop("timed_out", None)
    if record.get("status") == "running":
        record["note"] = note(record) or record.get("note")
    return {k: v for k, v in record.items() if v is not None}
