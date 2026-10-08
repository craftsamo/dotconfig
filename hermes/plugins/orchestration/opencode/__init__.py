"""OpenCode 2 sessions over the shared service's HTTP API; not a planner, approval authority, or sandbox.

The plugin keeps no run records. A run is an OpenCode session whose metadata binds
it to the calling Hermes session; its state is read from the service each time
(see turn.py). Roles are configuration: one `opencode_run_<role>` tool per
`opencode.roles` entry, each naming an installed OpenCode agent and a policy.
"""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import importlib.util
import json
import logging
import os
from pathlib import Path
import re
import shlex
import sys
import time

_HERE = Path(__file__).resolve().parent
logger = logging.getLogger(__name__)


def _load(name, path):
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


# Reuse this repository's caller binding. Do not import Hermes' transient/private
# delegate implementation or duplicate its API.
dispatch = _load("hermes_opencode_specialist_transport", _HERE.parents[0] / "specialist-call/__init__.py")
api = _load("hermes_opencode_api", _HERE / "api.py")
config = _load("hermes_opencode_config", _HERE / "config.py")
policy = _load("hermes_opencode_policy", _HERE / "policy.py")
models = _load("hermes_opencode_models", _HERE / "models.py")
turn = _load("hermes_opencode_turn", _HERE / "turn.py")
inventory = _load("hermes_opencode_history", _HERE / "history.py")

PROFILES = {"engineer", "assistant"}
# The tool mechanics skill reaches only the profiles that will drive OpenCode.
SKILLS = {"opencode": {"assistant"}}
TOPIC_FIELDS = ("PLATFORM", "SOURCE", "PROFILE", "KEY", "CHAT_ID", "THREAD_ID", "USER_ID")
SESSION_ID = re.compile(r"ses_[A-Za-z0-9_-]+\Z")
PERMISSION_ID = re.compile(r"per_[A-Za-z0-9_-]{1,64}\Z")
FORM_ID = re.compile(r"frm_[A-Za-z0-9_-]{1,64}\Z")
ENTRY_KEY = re.compile(r"hermes\.[a-z0-9._-]{1,48}\Z")
DECISIONS = ("once", "reject")
RUN_ARGS = {"directory", "session_id", "message", "model", "variant", "fork", "timeout", "output_dir"}
WRITE_ARGS = {"approval", "issue_approval"}
NOTE_KEY = "hermes.note"
DEFAULT_NOTE = (
    "A Hermes agent drives this session over the OpenCode API; no human is at the terminal. Hermes answers "
    "your permission requests and questions, so ask only what you cannot decide yourself. For a decision "
    "that does not block the work, take the recommended default and say so in your final reply. Hermes "
    "switches agents between turns: never switch yourself.")
SETTLE_AFTER_INTERRUPT = 20
NOTIFY_LIMIT = 5400
MESSAGE_LIMIT = 100000
STEER_LIMIT = 20000
LIST_PAGES = 5


# --------------------------------------------------------------------------
# Caller scope and per-worktree start lock


def _topic_owner(home):
    """A live caller's binding: its profile home and conversation route (platform,
    chat, topic/thread, sender, session key) without the Hermes session id. A run
    therefore stays answerable after `/new`, a compression continuation or a restart
    in the same topic, and stays foreign to other topics, senders and profiles."""
    from gateway.session_context import get_session_env
    route = {n: get_session_env("HERMES_SESSION_" + n, "") for n in TOPIC_FIELDS}
    if not route["KEY"] or not route["CHAT_ID"]:
        raise ValueError("A live caller needs its conversation route")
    digest = hashlib.sha256(json.dumps([str(home.resolve()), route], sort_keys=True).encode()).hexdigest()
    return {"profile": home.name, "topic_digest": digest}


def _scope():
    from agent.delegation_context import is_delegated_child_context
    if is_delegated_child_context():
        # A delegate_task child inherits its parent's conversation route, so it would
        # bind as the parent and could answer the parent's permission requests.
        raise ValueError("OpenCode tools are not available to delegated subagents")
    home, owner, live, inbound = dispatch._scope()
    if home.name not in PROFILES or inbound:
        raise ValueError("OpenCode execution requires an Assistant CLI/resident or live conversation")
    # A CLI/resident caller has no route that outlives its session, so it stays
    # bound to the session id that specialist-call derives.
    return home, (_topic_owner(home) if live else owner), live


@contextlib.contextmanager
def _starting(home, directory):
    """Holds a per-worktree lock while a run is set up and its prompt admitted, so two
    concurrent tool calls cannot both start a write run in one worktree. It is a lock
    only: nothing is recorded in it."""
    root = home / "opencode-locks"
    root.mkdir(mode=0o700, exist_ok=True)
    if root.is_symlink():
        raise ValueError("OpenCode lock directory must not be a symlink")
    name = hashlib.sha256(directory.encode()).hexdigest()[:32] + ".lock"
    fd = os.open(root / name, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("Another call is starting a run in this worktree; wait for it") from None
        yield
    finally:
        os.close(fd)


def _session_id(value):
    if not isinstance(value, str) or not SESSION_ID.fullmatch(value):
        raise ValueError("session_id must be a session id like ses_…")
    return value


def _fetch(sid):
    try:
        return turn.session_info(sid)
    except api.ApiError as exc:
        if exc.status == 404:
            raise ValueError(f"Session {sid} does not exist") from None
        raise


def _bound(args, owner):
    """The caller's own session named by `session_id`: (id, info, hermes metadata)."""
    sid = _session_id(args.get("session_id"))
    info = _fetch(sid)
    return sid, info, turn.owned(info, owner)


def _agent(name, where):
    """An agent as resolved at the worktree. The single-agent route answers 404 for an
    agent defined only in the project (2.0.23), so the list confirms a miss."""
    try:
        return api.data(turn.call("get", "/api/agent/{name}", query=where, name=name))
    except api.ApiError as exc:
        if exc.status != 404:
            raise
    for info in api.data(turn.call("get", "/api/agent", query=where), list):
        if info.get("id") == name:
            return info
    raise ValueError(f"OpenCode agent {name} is not installed; no run launched")


# --------------------------------------------------------------------------
# Starting a turn


def _prompt(role, message, approval, issue_approval, output=None):
    text = message
    if output:
        text += ("\n\nOutput directory (outside the repository) for reports, screenshots and other "
                 "results this run produces: " + output)
    if role["policy"] == "write":
        text += "\n\nClient implementation scope: " + approval
        text += "\nIssue management: " + (issue_approval or "not granted")
    return text


def _instructions(role):
    return DEFAULT_NOTE + (("\n\n" + role["note"]) if role.get("note") else "")


def _prepare(home, owner, role_name, role, settings, args, kwargs):
    """Validate, then create/resume/fork the session under this role's agent, model and
    ruleset and verify the service applied them. Sends no prompt."""
    writing = role["policy"] == "write"
    approval, issue_approval = args.get("approval"), args.get("issue_approval")
    for key, value in (("approval", approval), ("issue_approval", issue_approval)):
        if key in args and (not isinstance(value, str) or not value.strip()):
            raise ValueError(f"{key} must quote the Client's scoped approval, never a boolean")
    if writing and not approval:
        raise ValueError("A write run requires the Client's explicit implementation approval")
    if "fork" in args and type(args["fork"]) is not bool:
        raise ValueError("fork must be boolean")
    fork = bool(args.get("fork"))
    chosen = models.selection(args, settings, role)
    sid, meta = args.get("session_id"), {}
    if sid:
        sid, info, meta = _bound(args, owner)
        directory = turn.directory_of(info)
        if args.get("directory") and not policy.same_dir(args["directory"], directory):
            raise ValueError("A session cannot move to another worktree")
    else:
        if fork:
            raise ValueError("fork requires a session_id")
        info = None
        directory = args.get("directory")
    directory = policy.worktree(directory)
    branch, protected = policy.branch(directory, writing)
    if meta and meta.get("branch") != branch:
        raise ValueError("Worktree branch changed; start a new session after inspection")
    stored = meta.get("output_dir")
    try:
        # A stored value is service metadata, not trusted input: it is checked again.
        output = policy.output_dir(args["output_dir"] if "output_dir" in args else stored)
    except ValueError as exc:
        if "output_dir" in args:
            raise
        raise ValueError(f"The session's stored output_dir is no longer valid ({exc}); pass output_dir") from None
    if output and (output == directory or output.startswith(directory + os.sep)):
        raise ValueError("output_dir must lie outside the worktree")
    return {"output": output, "writing": writing, "fork": fork, "chosen": chosen or meta.get("selection") or {},
            "explicit": bool(chosen), "sid": sid, "directory": directory, "branch": branch,
            "protected": protected, "approval": approval, "issue_approval": issue_approval}


def _setup(home, owner, role_name, role, plan, kwargs):
    directory, sid = plan["directory"], plan["sid"]
    where = api.location(directory)
    if sid and sid in turn.active():
        raise ValueError("This session is running; wait, steer or interrupt it, never start another turn")
    # A write run never edits alongside another running session (another profile or a person).
    if plan["writing"] and turn.running_in(directory, policy.same_dir, exclude={sid} if sid else ()):
        raise ValueError("An OpenCode session is already running in this worktree (another Hermes profile "
                         "or a person); no write run launched")
    info = _agent(role["agent"], where)
    if info.get("mode") not in ("primary", "all"):
        raise ValueError(f"OpenCode agent {role['agent']} is not a primary agent")
    # The built-in build agent adds no denies of its own, so its resolved ruleset
    # carries the person's global and project denies.
    person = _agent("build", where).get("permissions") or []
    server = turn.call("get", "/api/info") or {}
    tmp = (server.get("paths") or {}).get("tmp") if isinstance(server, dict) else None
    ruleset = policy.rules(role["policy"], plan["issue_approval"], plan["protected"], tmp=tmp, person_denies=person,
                           output=plan["output"])
    model = models.engine(role, plan["chosen"], info, directory,
                          models.caller_models(home, kwargs.get("session_id")))
    hermes = {"v": 2, "profile": home.name, "owner": owner, "role": role_name, "branch": plan["branch"],
              **({"selection": plan["chosen"]} if plan["chosen"] else {}),
              **({"output_dir": plan["output"]} if plan["output"] else {})}
    metadata = {"hermes": hermes}
    if sid and plan["fork"]:
        sid = api.data(turn.call("post", "/api/session/{sid}/fork", {}, sid=sid))["id"]
    if sid:
        current = turn.session_info(sid)
        if not policy.same_dir(turn.directory_of(current), directory):
            raise ValueError("The saved OpenCode session belongs to another directory")
        turn.call("post", "/api/session/{sid}/agent", {"agent": role["agent"]}, sid=sid)
        turn.call("post", "/api/session/{sid}/model", {"model": model}, sid=sid)
        turn.call("patch", "/api/session/{sid}", {"permissions": ruleset, "metadata": {
            **(current.get("metadata") or {}), **metadata}}, sid=sid)
    else:
        sid = api.data(turn.call("post", "/api/session", {
            "agent": role["agent"], "model": model, "location": {"directory": directory},
            "permissions": ruleset, "metadata": metadata}))["id"]
    if not SESSION_ID.fullmatch(sid):
        raise ValueError("OpenCode returned an invalid session identity")
    applied = turn.session_info(sid)
    reported = applied.get("model") or {}
    if applied.get("agent") != role["agent"] or applied.get("permissions") != ruleset or \
            {k: reported.get(k) for k in model} != model or turn.hermes_meta(applied).get("owner") != owner:
        raise ValueError("OpenCode did not report back this turn's agent, model, ruleset and binding; "
                         "no prompt sent")
    return sid


def _put_note(sid, role):
    """The operating note as a durable session instruction. Experimental on the service:
    when it is refused, the caller prepends the note to the prompt instead."""
    try:
        turn.call("put", "/api/experimental/session/{sid}/instructions/entries/{key}", {"value": _instructions(role)},
                  sid=sid, key=NOTE_KEY)
        return True
    except (api.ApiError, api.Unavailable):
        return False


def _admit(sid, role, message, plan):
    text = _prompt(role, message, plan["approval"], plan["issue_approval"], plan["output"])
    if not _put_note(sid, role):
        text = _instructions(role) + "\n\n" + text
    try:
        admitted = api.data(turn.call("post", "/api/session/{sid}/prompt", {"text": text}, sid=sid))
        return admitted["id"], None
    except api.ApiError as exc:
        raise ValueError(f"Prompt refused ({exc.status}): {exc.detail}") from None
    except (api.Unavailable, KeyError, TypeError):
        return None, {"session_id": sid, "status": "unknown",
                      "error": "Prompt admission not confirmed",
                      "note": turn.note({"status": "unknown"})}


def _launch_notifier(home, sid, task_id):
    """Live callers learn of the next handback through a completion notification."""
    from tools.terminal_tool import terminal_tool
    command = dispatch.runner_command(Path(__file__).resolve(), "notify", str(home), sid)
    try:
        launch = json.loads(terminal_tool(command=shlex.join(command), background=True,
                                          notify_on_complete=True, task_id=task_id, _host_local=True))
    except Exception:
        launch = {"error": "Notifier launch outcome unknown"}
    return launch.get("session_id")


def _handoff(home, live, sid, kwargs, limit=None):
    """A blocking caller (CLI/resident) waits for the hand-back; a live caller gets the
    current state at once and a notifier process for the next hand-back."""
    if live:
        process = _launch_notifier(home, sid, kwargs.get("task_id"))
        out = {**turn.snapshot(sid), "process_session_id": process}
        if not process:
            out["note"] = "No completion notification could be arranged; use opencode_session wait"
        return out
    return turn.await_turn(sid, turn.wait_limit(home, _lenient(home), limit))


def _lenient(home):
    """wait_timeout without requiring the integration to be enabled: disabling new
    execution must not remove the owner's ability to inspect, answer or stop a run."""
    with contextlib.suppress(Exception):
        value = (config.read(home).get(config.KEY) or {}).get("wait_timeout", config.DEFAULT_WAIT_TIMEOUT)
        if type(value) is int and 1 <= value <= config.MAX_WAIT_TIMEOUT:
            return {"wait_timeout": value}
    return {"wait_timeout": config.DEFAULT_WAIT_TIMEOUT}


# --------------------------------------------------------------------------
# Tools


def opencode_run(role_name, args, **kwargs):
    try:
        home, owner, live = _scope()
        settings = config.load(home)
        role = settings["roles"].get(role_name)
        if role is None:
            raise ValueError(f"Unknown role {role_name!r}")
        allowed = RUN_ARGS | (WRITE_ARGS if role["policy"] == "write" else set())
        if set(args) - allowed:
            raise ValueError("Unexpected arguments; identity, executable and permissions are runtime-owned")
        if os.environ.get("RESIDENT_TURN_KIND") == "reconcile":
            raise ValueError("This resident turn is reconcile-only; inspect and stop, never execute OpenCode")
        message = args.get("message")
        if not isinstance(message, str) or not message.strip() or len(message) > MESSAGE_LIMIT:
            raise ValueError(f"A nonempty message of at most {MESSAGE_LIMIT} characters is required")
        requested = args.get("timeout")
        if requested is not None and (type(requested) is not int or requested < 1):
            raise ValueError("timeout must be a positive integer number of seconds")
        plan = _prepare(home, owner, role_name, role, settings, args, kwargs)
        with _starting(home, plan["directory"]):
            try:
                sid = _setup(home, owner, role_name, role, plan, kwargs)
            except (ValueError, api.ApiError, api.Unavailable) as exc:
                raise ValueError(f"{exc} (no OpenCode turn started)") from None
            _, failed = _admit(sid, role, message, plan)
            if failed:
                return json.dumps(failed)
        try:
            return json.dumps(_handoff(home, live, sid, kwargs, requested))
        except Exception as exc:
            # The turn is running in OpenCode: hand back its id, never a bare error.
            return json.dumps({"session_id": sid, "status": "running",
                               "error": f"{type(exc).__name__} after the prompt was admitted; use "
                                        "opencode_session status/wait, never start another turn"})
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def _listing(args, owner):
    directory = args.get("directory")
    if directory is not None and not isinstance(directory, str):
        raise ValueError("directory must be an absolute path")
    limit = args.get("limit", 20)
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("limit must be 1..100")
    running = turn.active()
    rows, cursor = [], None
    for _ in range(LIST_PAGES):
        query = {"limit": 200, "order": "desc", "directory": directory, "cursor": cursor}
        page = turn.call("get", "/api/session", query=query)
        for item in api.data(page, list):
            meta = turn.hermes_meta(item)
            if meta.get("owner") != owner:
                continue
            model = item.get("model") or {}
            rows.append({"session_id": item.get("id"), "role": meta.get("role"), "branch": meta.get("branch"),
                         "directory": turn.directory_of(item), "agent": item.get("agent"),
                         "engine": (f"{model.get('providerID')}/{model['id']}"
                                    + (f"#{model['variant']}" if model.get("variant") else "")) if model.get("id")
                         else None,
                         "running": item.get("id") in running, "updated": (item.get("time") or {}).get("updated")})
        cursor = (page.get("cursor") or {}).get("next") if isinstance(page, dict) else None
        if not cursor or len(rows) >= limit:
            break
    return {"sessions": rows[:limit], **({"more": True} if cursor or len(rows) > limit else {})}


def _messages(sid, args):
    limit = args.get("limit", 10)
    if type(limit) is not int or not 1 <= limit <= 50:
        raise ValueError("limit must be 1..50")
    body = turn.call("get", "/api/session/{sid}/message", query={"order": "desc", "limit": limit}, sid=sid)
    out = []
    for message in api.data(body, list):
        kind = message.get("type")
        entry = {"id": message.get("id"), "type": kind}
        if kind == "assistant":
            entry["text"] = turn.text(message)[:3000]
            tools = [p.get("name") for p in message.get("content") or [] if p.get("type") == "tool"]
            if tools:
                entry["tools"] = tools
            if message.get("error"):
                entry["error"] = turn.provider_problem(message["error"], message.get("model"))
        elif kind == "user":
            entry["text"] = str(message.get("text") or (message.get("payload") or {}).get("text") or "")[:3000]
        elif kind == "agent-switched":
            entry.update(agent=message.get("agent"), previous=message.get("previous"))
        elif kind == "idle":
            entry["outcome"] = message.get("outcome")
        out.append(entry)
    return {"session_id": sid, "messages": out}


def _diff(sid, args):
    start = turn.latest_turn(sid)["start"]
    if not start:
        raise ValueError("No OpenCode turn to diff")
    body = turn.call("get", "/api/session/{sid}/diff", query={"from": start}, sid=sid)
    items = (body.get("data") if isinstance(body, dict) else body) or []
    keys = ("file", "status", "additions", "deletions") + (("patch",) if args.get("patch") is True else ())
    files, budget = [], 60000
    for item in items[:200]:
        entry = {key: item.get(key) for key in keys}
        if "patch" in entry:
            entry["patch"] = (entry["patch"] or "")[:max(0, budget)]
            budget -= len(entry["patch"])
        files.append(entry)
    return {"session_id": sid, "files": files, **({"truncated": True} if budget < 0 or len(items) > 200 else {})}


def opencode_session(args, **kwargs):
    try:
        allowed = {"action", "session_id", "directory", "timeout", "through_retry", "message", "patch", "limit"}
        if set(args) - allowed:
            raise ValueError("Unexpected arguments")
        action = args.get("action")
        if "timeout" in args and action != "wait":
            raise ValueError("timeout is only accepted for wait")
        if "through_retry" in args and action != "wait":
            raise ValueError("through_retry is only accepted for wait")
        home, owner, live = _scope()
        if action == "list":
            return json.dumps(_listing(args, owner))
        sid, info, meta = _bound(args, owner)
        if action == "status":
            return json.dumps(turn.snapshot(sid))
        if action == "wait":
            requested = args.get("timeout")
            if requested is not None and (type(requested) is not int or requested < 1):
                raise ValueError("timeout must be a positive integer number of seconds")
            through = args.get("through_retry", False)
            if type(through) is not bool:
                raise ValueError("through_retry must be boolean")
            limit = turn.wait_limit(home, _lenient(home), requested)
            return json.dumps(turn.await_turn(sid, limit, through_retry=through))
        if action == "steer":
            text = args.get("message")
            if not isinstance(text, str) or not text.strip() or len(text) > STEER_LIMIT:
                raise ValueError(f"steer needs a nonempty message of at most {STEER_LIMIT} characters")
            if sid not in turn.active():
                raise ValueError("No running OpenCode turn to steer")
            turn.call("post", "/api/session/{sid}/prompt", {"text": text, "delivery": "steer"}, sid=sid)
            return json.dumps({"session_id": sid, "steered": True,
                               "note": "Delivered at the run's next step boundary; a long tool call finishes first"})
        if action == "interrupt":
            if sid not in turn.active():
                raise ValueError("No running OpenCode turn to interrupt")
            turn.halt(sid)
            settled = turn.await_turn(sid, SETTLE_AFTER_INTERRUPT, through_retry=True, poll=1.0)
            return json.dumps({**settled, "interrupt_requested": True,
                               "note": "Interrupt sent. Never a rollback: read the diff before continuing."})
        if action == "messages":
            return json.dumps(_messages(sid, args))
        if action == "diff":
            return json.dumps(_diff(sid, args))
        if action == "fork":
            if sid in turn.active():
                raise ValueError("Fork a session when it is idle, not while it runs")
            new = api.data(turn.call("post", "/api/session/{sid}/fork", {}, sid=sid))["id"]
            turn.call("patch", "/api/session/{sid}", {"metadata": {**(info.get("metadata") or {}), "hermes": meta}},
                      sid=new)
            return json.dumps({"session_id": new, "forked_from": sid, "role": meta.get("role")})
        raise ValueError("Use status/list/wait/steer/interrupt/messages/diff/fork")
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def _answer(value):
    ok = (str, int, float, bool)
    if not isinstance(value, dict) or not value or not all(
            isinstance(k, str) and (isinstance(v, ok) or (isinstance(v, list) and all(isinstance(i, ok) for i in v)))
            for k, v in value.items()):
        raise ValueError("answer must map each field key to a string, number, boolean or list of those")
    return value


def opencode_request(args, **kwargs):
    try:
        allowed = {"action", "session_id", "request_id", "decision", "reason", "answer"}
        if set(args) - allowed:
            raise ValueError("Unexpected arguments")
        home, owner, live = _scope()
        sid, info, meta = _bound(args, owner)
        found = turn.pending(sid, turn.directory_of(info), {})
        action = args.get("action")
        if action == "list":
            return json.dumps({"session_id": sid, "pending": found})
        if action != "reply":
            raise ValueError("Use list or reply")
        request_id = args.get("request_id")
        item = next((p for p in found if p["id"] == request_id), None)
        if item is None:
            raise ValueError("That request is not pending in this run (answered, cancelled or foreign)")
        reason, decision = args.get("reason"), args.get("decision")
        if reason is not None and (not isinstance(reason, str) or len(reason) > 2000):
            raise ValueError("reason must be text of at most 2000 characters")
        if item["kind"] == "permission":
            if not PERMISSION_ID.fullmatch(request_id) or decision not in DECISIONS:
                raise ValueError("decision must be once or reject (never always: it saves a project-wide approval "
                                 "people's own sessions would inherit)")
            reply = {"decision": decision, **({"message": reason} if reason else {})}
            turn.call("post", "/api/session/{sid}/permission/{per}/reply", reply, sid=item["session_id"],
                      per=request_id)
        else:
            if not FORM_ID.fullmatch(request_id):
                raise ValueError("Invalid form id")
            if "answer" in args:
                turn.call("post", "/api/session/{sid}/form/{form}/reply", {"answer": _answer(args["answer"])},
                          sid=item["session_id"], form=request_id)
            elif decision == "reject":
                turn.call("delete", "/api/session/{sid}/form/{form}", sid=item["session_id"], form=request_id)
            else:
                raise ValueError("Answer a question with answer={field: value}, or decline it with decision=reject")
        return json.dumps(_handoff(home, live, sid, kwargs))
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def opencode_instructions(args, **kwargs):
    try:
        allowed = {"action", "session_id", "key", "value"}
        if set(args) - allowed:
            raise ValueError("Unexpected arguments")
        home, owner, live = _scope()
        sid, info, meta = _bound(args, owner)
        action = args.get("action")
        if action not in ("list", "put", "remove"):
            raise ValueError("Use list, put or remove")
        if action == "list":
            body = turn.call("get", "/api/experimental/session/{sid}/instructions/entries", sid=sid)
            return json.dumps({"session_id": sid, "entries": api.data(body, list)})
        key = args.get("key")
        if not isinstance(key, str) or not ENTRY_KEY.fullmatch(key):
            raise ValueError("key must be hermes.<name> (lowercase letters, digits, . _ -)")
        if action == "put":
            value = args.get("value")
            if not isinstance(value, str) or not value.strip() or len(value) > 8000:
                raise ValueError("value must be nonempty text of at most 8000 characters")
            turn.call("put", "/api/experimental/session/{sid}/instructions/entries/{key}", {"value": value},
                      sid=sid, key=key)
            return json.dumps({"session_id": sid, "key": key, "set": True,
                               "note": "Announced to the agent at its next step boundary"})
        turn.call("delete", "/api/experimental/session/{sid}/instructions/entries/{key}", sid=sid, key=key)
        return json.dumps({"session_id": sid, "key": key, "removed": True})
    except Exception as exc:
        return json.dumps({"error": str(exc)})


CATALOG = {
    "agents": ("/api/agent", True), "skills": ("/api/skill", True), "commands": ("/api/command", True),
    "vcs": ("/api/vcs/status", True), "info": ("/api/info", False),
}
CATALOG_KEYS = {
    "agents": ("id", "mode", "hidden", "description", "model"),
    "skills": ("id", "name", "description"),
    "commands": ("id", "name", "description"),
}


def opencode_catalog(args, **kwargs):
    try:
        if set(args) - {"what", "directory"}:
            raise ValueError("Unexpected arguments")
        home, owner, live = _scope()
        what, directory = args.get("what"), args.get("directory")
        if what == "models":
            settings = config.load(home)
            return json.dumps(models.listing(settings, settings["roles"], models.caller_models(
                home, kwargs.get("session_id"))))
        if what not in CATALOG:
            raise ValueError("what must be one of models, " + ", ".join(CATALOG))
        route, located = CATALOG[what]
        query = None
        if located:
            query = api.location(policy.worktree(directory))
        body = turn.call("get", route, query=query)
        if what == "info":
            return json.dumps({k: body.get(k) for k in ("version",) if isinstance(body, dict)})
        items = body.get("data") if isinstance(body, dict) else body
        if isinstance(items, list):
            keys = CATALOG_KEYS.get(what)
            items = [{k: i.get(k) for k in keys if k in i} if keys and isinstance(i, dict) else i
                     for i in items[:300]]
        return json.dumps({what: items})
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def opencode_history(args, **kwargs):
    try:
        # Same caller gate as execution (no inbound A2A), but no enabled flag: reading
        # history launches no agent.
        _scope()
        return json.dumps(inventory.run(args), ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


# --------------------------------------------------------------------------
# Registration


def _run_description(name, role):
    mode = ("read-only: it never edits the worktree" if role["policy"] == "read-only" else
            "write: it edits the worktree on a task branch and needs the Client's explicit approval")
    return (f"Run the OpenCode `{role['agent']}` agent as role `{name}` ({mode}) in an owned Git worktree on the "
            "shared OpenCode service. A new session needs directory (an absolute worktree root); session_id "
            "continues one, switching it to this role's agent, model and policy (the same worktree and branch). "
            "Blocks until the run hands back: finished, paused on a permission request or question you must "
            "answer with opencode_request, or stuck in a provider retry you may interrupt and continue on another "
            "model. Completion is not acceptance. Never start a second turn while one runs: use opencode_session "
            "wait.")


def _run_properties(role):
    properties = {
        "directory": {"type": "string", "description": "Absolute Git worktree root; for a new session"},
        "session_id": {"type": "string", "description": "Continue this session (ses_…)"},
        "message": {"type": "string"},
        "model": {"type": "string", "description": "Optional provider/model from opencode_catalog models; "
                                                   "never your own model"},
        "variant": {"type": "string", "description": "Optional reasoning effort from that model's variants"},
        "fork": {"type": "boolean", "description": "Fork session_id first and run on the copy"},
        "timeout": {"type": "integer", "description": "Seconds to block (bounded by config and your tool deadline)"},
        "output_dir": {"type": "string", "description": "Existing job directory under a Workspaces .agent/ draft, "
                                                       "outside the worktree, that the run may write results to "
                                                       "(reports, screenshots); kept for later turns of the session"},
    }
    if role["policy"] == "write":
        properties["approval"] = {"type": "string", "description": "The Client's explicit scoped implementation "
                                                                   "approval, quoted"}
        properties["issue_approval"] = {"type": "string", "description": "Quoted Client approval for Issue writes"}
    return properties


def register_skills(ctx, profile):
    """Register this profile's skills; a skill that cannot be read is logged and never costs the tools."""
    for name, profiles in SKILLS.items():
        if profile not in profiles:
            continue
        try:
            from agent.skill_utils import parse_frontmatter

            path = _HERE / "skills" / name / "SKILL.md"
            meta, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
            ctx.register_skill(name, path, description=meta["description"], frontmatter=meta)
        except Exception as exc:
            logger.warning("opencode skill %s not registered: %s", name, exc)


def register(ctx):
    if ctx.profile_name not in PROFILES:
        return
    register_skills(ctx, ctx.profile_name)
    from hermes_constants import get_hermes_home
    home = get_hermes_home()
    identity = (ctx.profile_name, str(home.resolve()))

    def scoped(handler):
        def invoke(args, **kwargs):
            from gateway.session_context import scoped_current_session_id
            token = dispatch._REGISTRATION.set(identity)
            turn_token = dispatch._TURN_SESSION.set(kwargs.get("task_id") or "")
            try:
                with scoped_current_session_id(kwargs.get("session_id")):
                    return handler(args, **kwargs)
            finally:
                dispatch._TURN_SESSION.reset(turn_token)
                dispatch._REGISTRATION.reset(token)
        return invoke

    def add(name, handler, properties, required, description):
        ctx.register_tool(name=name, toolset="opencode", handler=scoped(handler), description=description,
                          schema={"name": name, "description": description, "parameters": {
                              "type": "object", "properties": properties, "required": required,
                              "additionalProperties": False}})

    ctx.register_hook("post_api_request", models.observe)
    for name, role in config.roles(home).items():
        add(f"opencode_run_{name}", lambda args, _name=name, **kw: opencode_run(_name, args, **kw),
            _run_properties(role), ["message"], _run_description(name, role))
    add("opencode_session", opencode_session, {
        "action": {"type": "string", "enum": ["list", "status", "wait", "steer", "interrupt", "messages", "diff",
                                              "fork"]},
        "session_id": {"type": "string"},
        "directory": {"type": "string", "description": "list only: limit to this worktree"},
        "timeout": {"type": "integer", "description": "wait only: seconds to block"},
        "through_retry": {"type": "boolean", "description": "wait only: keep waiting while OpenCode retries a "
                                                            "provider failure"},
        "message": {"type": "string", "description": "steer only"},
        "patch": {"type": "boolean", "description": "diff only: include patches (truncated)"},
        "limit": {"type": "integer", "description": "list (1..100) or messages (1..50): how many"},
    }, ["action"],
        "Inspect and steer your OpenCode sessions (those bound to this conversation: the same topic and sender, "
        "or this CLI session). status reads a run without waiting; wait blocks until it hands back, spending no turns; steer adds an instruction to a "
        "running turn; interrupt stops it (never a rollback); diff lists the newest turn's changed files "
        "(patch=true adds patches); messages reads recent messages; fork copies an idle session.")
    add("opencode_request", opencode_request, {
        "action": {"type": "string", "enum": ["list", "reply"]},
        "session_id": {"type": "string"},
        "request_id": {"type": "string", "description": "reply only: the pending request's id (per_… or frm_…)"},
        "decision": {"type": "string", "enum": list(DECISIONS), "description": "reply only: a permission request "
                     "takes once or reject; reject also declines a question"},
        "reason": {"type": "string", "description": "reply only: shown to OpenCode; required in spirit for reject"},
        "answer": {"type": "object", "description": "reply only, for a question: field key -> answer"},
    }, ["action", "session_id"],
        "List or answer what a run is paused on: permission requests (once within the Client's approved scope, "
        "otherwise reject with a reason and ask the Client) and questions the agent put to a person (answer "
        "them yourself when it is an in-scope technical question; relay material Client decisions). Requests stay "
        "pending until answered; after a reply this waits for the next hand-back.")
    add("opencode_instructions", opencode_instructions, {
        "action": {"type": "string", "enum": ["list", "put", "remove"]},
        "session_id": {"type": "string"},
        "key": {"type": "string", "description": "hermes.<name>"},
        "value": {"type": "string", "description": "put only"},
    }, ["action", "session_id"],
        "Durable instructions attached to one of your OpenCode sessions, announced to the agent at its next step "
        "boundary. Keys are hermes.<name>; hermes.note is the operating note every run starts with.")
    add("opencode_catalog", opencode_catalog, {
        "what": {"type": "string", "enum": ["models", "agents", "skills", "commands", "vcs", "info"]},
        "directory": {"type": "string", "description": "Absolute worktree root for agents, skills, commands, vcs"},
    }, ["what"],
        "Read what OpenCode offers (read-only). models lists what an opencode_run_<role> tool accepts as model= "
        "with variants, context, cost, each role's default and your own models (refused).")
    add("opencode_history", opencode_history, {
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
    }, ["action"],
        "Read OpenCode session history across all projects (read-only; launches no agent). "
        "list: sessions overlapping [from, to), newest first, paged by limit/offset; kind defaults to root. "
        "get / children: one session or its subagent sessions. usage: message-level tokens and activity for "
        "[from, to) grouped by group_by (default model). Titles and costs only with include_title / "
        "include_cost; message content never. Every result states its source (api or db), status and "
        "diagnostics.")


def _notify(home_arg, sid):
    home = Path(home_arg)
    if home.name not in PROFILES or home.parent.name != "profiles":
        raise ValueError("Invalid captured OpenCode caller home")
    return turn.await_turn(_session_id(sid), NOTIFY_LIMIT)


if __name__ == "__main__":
    mode, home_arg, sid_arg = sys.argv[1:4]
    if mode != "notify":
        raise SystemExit(f"unknown mode {mode}")
    print(json.dumps(_notify(home_arg, sid_arg)))
    raise SystemExit(0)
