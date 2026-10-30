"""workspace-drive: which folders under ~/Workspaces live in Google Drive, and moving them there and back.

One tool, ``workspace_drive`` (toolset ``workspace_drive``), over the engine ``drive.py`` beside this
file, which is also the ``ws-drive`` command and the LaunchAgent ``local.hermes.workspaces-drive.mount``.
Every profile the plugin is enabled in reads status; only the Assistant moves and restores. A
``pre_tool_call`` hook holds each move or restore for Hermes' human approval gate (the card names the
folder, its size, how Drive keeps it and what happens to the local copy; blocked where no person can
answer), and the approved call only queues the work: the LaunchAgent runs it, so a move outlives a
gateway restart and the gateway never reads the Keychain. A background watcher reports the outcome to
the conversation. The same hook blocks terminal and file calls that would go around the tool.
Contract: docs/ops/workspaces-drive.md.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import logging
import re
import secrets
import shlex
import shutil
import sys
import threading
import time
from pathlib import Path

TOOL = "workspace_drive"
TOOLSET = "workspace_drive"
PLUGIN = "workspace-drive"
READS = ("status",)
WRITES = ("move", "restore")
# The actions a profile's schema offers (checked again by the gate and the handler). A profile not
# listed only reads: every profile the plugin is enabled in may ask where folders live.
PROFILES = {"assistant": READS + WRITES}
WRITERS = {p for p, actions in PROFILES.items() if set(actions) & set(WRITES)}
# Skill -> the profiles it is registered for (a profile that cannot do what a skill describes is not given it).
SKILLS = {"manage": set(WRITERS)}
APPROVAL_TTL = 900
LIMIT = 60000
logger = logging.getLogger(__name__)


def _load(name, path):
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


HERE = Path(__file__).resolve().parent
drive = _load("hermes_workspace_drive", HERE / "drive.py")
human_gate = _load("hermes_human_gate", HERE.parents[1] / "_shared" / "human_gate.py")
cards = _load("hermes_card", HERE.parents[1] / "_shared" / "card.py")
tool_preview = _load("hermes_tool_preview", HERE.parents[1] / "_shared" / "tool_preview.py")

READ_DESCRIPTION = (
    "Which folders under ~/Workspaces live in Google Drive (read-only). status: whether the Drive mount is up, "
    "every folder that is a link into Drive (each Group's assets/ and the folders moved there), the assets/ "
    "this Mac keeps locally, interrupted work, and moves queued, running or recently finished. A folder on "
    "Drive keeps its usual path, so read and write it as usual; a file not read recently is downloaded when "
    "opened. When the mount is down the links point at nothing: report it, never save the file elsewhere.")
WRITE_DESCRIPTION = READ_DESCRIPTION + (
    " move (path: a folder inside a Group, <Tree>/<Group>/<folder>[/...]): copies it to Google Drive, checks "
    "the copy twice, deletes it here and leaves a link in its place; Personal/ is stored encrypted, Projects/ "
    "as is (readable in Drive's apps). restore (path: a folder on Drive): copies it back here and sends the "
    "Drive copy to Drive's trash. Each asks the user on an approval card; agree it in chat first and never "
    "retry a denied one unchanged. github/, folders whose name starts with '.', a Group itself and folders "
    "holding links or a Git repository stay here; drafts and the inbox are promoted first. The approved call "
    "only queues the work: the outcome arrives later as a notification (a large folder takes up to an hour), "
    "and status shows it meanwhile. Before proposing a move or restore, load "
    'skill_view(name="workspace-drive:manage").')


def actions_for(profile: str) -> tuple:
    return PROFILES.get(profile, READS)


def schema_for(profile: str) -> dict:
    actions = actions_for(profile)
    properties = {"action": {"type": "string", "enum": list(actions)}}
    description = READ_DESCRIPTION
    if profile in WRITERS:
        properties["path"] = {"type": "string", "description": "move / restore: the folder, <Tree>/<Group>/<folder>"
                                                               "[/...] under ~/Workspaces"}
        description = WRITE_DESCRIPTION
    return {"name": TOOL, "description": description, "parameters": {
        "type": "object", "properties": properties, "required": ["action"], "additionalProperties": False}}


def _inbound_peer():
    """An A2A turn (a peer agent's request) never reads or changes this machine's workspace."""
    try:
        from gateway.session_context import get_session_env
    except Exception:
        return False
    return "a2a" in (get_session_env("HERMES_SESSION_PLATFORM", ""), get_session_env("HERMES_SESSION_SOURCE", ""))


def _call_id() -> str:
    try:
        from tools.approval_context import _approval_tool_call_id
        return _approval_tool_call_id.get() or ""
    except Exception:
        return ""


def _refusal(profile: str, args) -> str | None:
    action = args.get("action") if isinstance(args, dict) else None
    allowed = actions_for(profile)
    if action not in allowed:
        if action in WRITES:
            return f"{TOOL}: this profile reads where folders live; moving them is the Assistant's"
        return f"{TOOL}: action is one of " + ", ".join(allowed)
    if _inbound_peer():
        return f"{TOOL} is not available to inbound A2A requests"
    return None


# --- the approval card -------------------------------------------------------------------

def card(plan: dict, free: int | None = None) -> str:
    size = f"{plan['files']} files, {cards.human(plan['bytes'])}"
    folder = cards.line(plan["path"], 200)
    if plan["kind"] == "move":
        return cards.compose(
            "Workspaces Drive", "Move to Drive",
            (cards.CAUTION, "Copied to your Google Drive and checked twice, then deleted here; a link keeps the path"),
            [("Folder", folder), ("Size", size),
             ("On Drive", "encrypted" if plan["encrypted"] else "as is, readable in Drive's apps")],
            context=[("Undo", "a restore brings it back")])
    return cards.compose(
        "Workspaces Drive", "Bring back from Drive",
        (cards.SAFE, "Copied back here and checked, then the Drive copy goes to Drive's trash (kept 30 days)"),
        [("Folder", folder), ("Size", size)],
        context=[("Free here", cards.human(free) if free is not None else None)])


def digest(plan: dict) -> str:
    return drive.plan_digest(plan)


# The gate's view of each move or restore, per tool call, so the queued work is what the card showed:
# (when, the plan's digest).
_approved: dict[str, tuple[float, str]] = {}
_approved_lock = threading.Lock()


def _call_key(args: dict, call_id: str) -> str:
    return hashlib.sha256(json.dumps([call_id or "", args], sort_keys=True, default=str).encode()).hexdigest()


def approval_request(args: dict, call_id: str = "") -> tuple[str, str]:
    """(card, allowlist rule key); raises for a call that would fail anyway, so it is blocked unasked."""
    plan = drive.plan(args.get("action"), str(args.get("path") or ""))
    if not drive.mounted():
        raise drive.DriveError("the Drive mount is not up; the user restarts it (ws-drive restart)")
    free = shutil.disk_usage(drive.WORKSPACES).free if plan["kind"] == "restore" else None
    text = card(plan, free)
    with _approved_lock:
        now = time.monotonic()
        for old in [k for k, (at, _) in _approved.items() if now - at > APPROVAL_TTL]:
            _approved.pop(old, None)
        _approved[_call_key(args, call_id)] = (now, digest(plan))
    # Every move is its own decision: an "always" answer never covers the next one.
    return text, f"{PLUGIN}:{plan['kind']}:{secrets.token_hex(8)}"


def _approved_write(args: dict, call_id: str) -> str | None:
    with _approved_lock:
        entry = _approved.pop(_call_key(args, call_id), None)
    if not entry or time.monotonic() - entry[0] > APPROVAL_TTL:
        return None
    return entry[1]


# --- ways around the tool ----------------------------------------------------------------

BYPASS_MESSAGE = (
    f"Folders move to and from Google Drive only through the {TOOL} tool, after the user's approval card: "
    "never through ws-drive's move, restore or other changing commands, rclone with the mount's remotes or "
    "config, its Keychain items, its state folder (~/.hermes/local/workspaces-drive), its LaunchAgent, or the "
    "mount itself (~/Workspaces/.drive). Read and write a folder on Drive at its usual path. Restarting or "
    "setting up the mount is the user's job (ws-drive restart).")
# Matched after quotes and backslashes are dropped, so `"…/ws-drive" 'move'` reads as `…/ws-drive move`.
# A changing command anywhere in the same shell segment as the launcher or the engine counts; the
# mount's state folder, LaunchAgent and log (all named workspaces-drive) are off limits whatever
# the command, the working directory included.
_CHANGES = r"(?:move|restore|setup|install|uninstall|restart|run|links)"
_TERMINAL = re.compile(
    r"\bws-drive\b[^;&|\n]*?\b" + _CHANGES + r"\b"
    r"|\bdrive\.py\b[^;&|\n]*?\b" + _CHANGES + r"\b"
    r"|workspaces-drive|\bwsdrive-(?:drive|crypt)\b|\bWORKSPACES_DRIVE_[A-Z_]+"
    r"|(?:^|[\s=:/])\.drive(?:[/\s]|$)", re.IGNORECASE)
_FILES = re.compile(r"workspaces-drive|(?:^|/)\.drive(?:/|$)", re.IGNORECASE)
_QUOTES = re.compile(r"[\"'\\]")
FILE_TOOLS = {"read_file", "write_file", "patch", "search_files"}


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def bypass(tool: str, args) -> str | None:
    """A block message when a terminal or file call would go around the tool, else None. A pattern
    match on the call's text, not a sandbox."""
    args = args if isinstance(args, dict) else {}
    if tool in ("terminal", "execute_code"):
        if any(_TERMINAL.search(_QUOTES.sub("", text)) for text in _strings(args)):
            return BYPASS_MESSAGE
    elif tool in FILE_TOOLS:
        if any(_FILES.search(_QUOTES.sub("", text)) for text in _strings(args)):
            return BYPASS_MESSAGE
    return None


# --- the tool -----------------------------------------------------------------------------

PATH_KEYS = ("on_drive", "local_assets", "foreign_links", "leftovers", "would_link")


def _projects_only(data: dict) -> dict:
    """Status for a profile that is not the Assistant: Personal/ is the Assistant's alone."""
    def keep(path) -> bool:
        return not str(path or "").startswith("Personal/")
    data = {**data, **{k: [p for p in data.get(k, []) if keep(p)] for k in PATH_KEYS}}
    data["interrupted"] = [e for e in data.get("interrupted", []) if keep(e.get("path"))]
    data["jobs"] = {k: [e for e in v if keep(e.get("path"))] for k, v in data.get("jobs", {}).items()}
    return data


def _watch(job: str, task_id) -> dict:
    """A background process that waits for the job's outcome; Hermes reports its line to the
    conversation when it ends."""
    try:
        from tools.terminal_tool import terminal_tool

        result = json.loads(terminal_tool(
            command=shlex.join([sys.executable, "-I", str(HERE / "drive.py"), "wait", job]),
            background=True, notify_on_complete=True, task_id=task_id, _host_local=True))
        return {"watching": bool(result.get("session_id")), "process_session_id": result.get("session_id")}
    except Exception as exc:  # noqa: BLE001 - the job runs either way; status shows its outcome
        return {"watching": False, "note": f"no watcher ({exc}); workspace_drive status shows the outcome"}


def make_handler(profile: str):
    def workspace_drive(args, **kwargs):
        try:
            args = args if isinstance(args, dict) else {}
            refusal = _refusal(profile, args)
            if refusal:
                raise drive.DriveError(refusal)
            action = args["action"]
            if action == "status":
                data = drive.status_data()
                if profile not in WRITERS:
                    data = _projects_only(data)
                text = json.dumps(data, ensure_ascii=False)
                return text if len(text) <= LIMIT else json.dumps({"ok": False, "error": "status is too long"})
            reason = human_gate.no_human()
            if reason:
                return json.dumps({"ok": False, "error": human_gate.refusal(TOOL, reason)})
            approved = _approved_write(args, _call_id())
            if approved is None:
                return json.dumps({"ok": False, "error": "not done: this did not pass its approval card; nothing "
                                                         "was queued"})
            plan = drive.plan(action, str(args.get("path") or ""))
            if digest(plan) != approved:
                return json.dumps({"ok": False, "error": "not done: the folder changed after the card was shown; "
                                                         "nothing was queued. Ask again"})
            job = drive.enqueue(action, plan["path"], origin=profile, expect=approved)
            return json.dumps({"ok": True, "queued": job, **_watch(job["id"], kwargs.get("task_id")),
                               "note": "the Drive mount's agent runs it now; the outcome arrives as a "
                                       "notification, and status shows it meanwhile"}, ensure_ascii=False)
        except Exception as exc:  # noqa: BLE001 - a tool answers with its error
            return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)
    return workspace_drive


def make_gate(profile: str):
    def gate(**kwargs):
        """pre_tool_call: approval for every move and restore, a block for what the profile is not
        offered, for a move no person can approve or that would fail, and for ways around the tool."""
        tool = kwargs.get("tool_name")
        args = kwargs.get("args")
        if tool == TOOL:
            refusal = _refusal(profile, args)
            if refusal:
                return {"action": "block", "message": refusal}
            if args.get("action") not in WRITES:
                return None
            reason = human_gate.no_human()
            if reason:
                return {"action": "block", "message": human_gate.refusal(TOOL, reason)}
            try:
                text, rule_key = approval_request(args, call_id=str(kwargs.get("tool_call_id") or ""))
            except Exception as exc:  # noqa: BLE001 - a call that would fail is blocked, not asked
                return {"action": "block", "message": f"{TOOL}: not done: {exc}"}
            return {"action": "approve", "message": text, "rule_key": rule_key}
        message = bypass(tool, args)
        if message:
            return {"action": "block", "message": message}
        return None
    return gate


def register_skills(ctx, profile):
    """Register this profile's skills; a skill that cannot be read is logged and never costs the tool."""
    for name, profiles in SKILLS.items():
        if profile not in profiles:
            continue
        try:
            from agent.skill_utils import parse_frontmatter

            path = HERE / "skills" / name / "SKILL.md"
            meta, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
            ctx.register_skill(name, path, description=meta["description"], frontmatter=meta)
        except Exception as exc:
            logger.warning("%s skill %s not registered: %s", PLUGIN, name, exc)


def register(ctx):
    profile = ctx.profile_name
    schema = schema_for(profile)
    ctx.register_tool(name=TOOL, toolset=TOOLSET, handler=make_handler(profile), description=schema["description"],
                      schema=schema, emoji="☁️")
    tool_preview.enums(TOOL, schema, "action")
    ctx.register_hook("pre_tool_call", make_gate(profile))
    register_skills(ctx, profile)
