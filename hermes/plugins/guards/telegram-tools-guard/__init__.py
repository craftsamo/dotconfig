"""telegram-tools-guard: what the third-party ``telegram-tools`` plugin leaves to Hermes.

``telegram-tools`` (installed outside this repo, at ``~/.hermes/plugins/telegram-tools``) registers the
``telegram_*`` tools. Its own ``pre_tool_call`` hook answers ``approve`` for every tool that is not a read
and leaves "is a person there to answer the card" to Hermes, which approves a card unasked under YOLO,
``approvals.mode: off``, cron and ``hermes -z``. This plugin stays separate so that a plugin update
never touches the policy, and it adds what that plugin does not do:

- a ``telegram_*`` write is refused where nobody can answer a card (``human_gate``), and every
  ``telegram_*`` tool is refused to an inbound A2A request. The reads are named one by one, never by a
  ``_read`` suffix (``telegram_chat_mark_read`` sends read receipts and is a write), and a tool that is not
  a named read counts as a write, so a tool the plugin adds later fails closed.
- the terminal and file tools may not reach the Telegram account around its tools: the plugin's CLI and
  MCP server, its state (the session's auth key, the API credentials, the mirror), logs and launch agents,
  and Telegram Desktop's data, and
  nothing inside a ``.unpacked`` folder of a received archive may be run. The terminal keeps its directory
  between calls, so a terminal call is also judged by where it runs (its ``workdir``, else the session's
  recorded directory) and every word of the command is resolved against that directory.

Hermes collects every plugin's ``pre_tool_call`` result and a valid ``block`` from any of them wins over
any ``approve``, with no card shown, so this guard needs no card of its own. A pattern match on a call's
text and on the real paths it names, not a sandbox. The hook never raises: where it cannot check a
``telegram_*`` write, the terminal or a file tool, it blocks.
"""

from __future__ import annotations

import fnmatch
import glob
import importlib.util
import logging
import os
from pathlib import Path
import re
import shlex
import sys

PLUGINS = Path(__file__).resolve().parents[2]
PREFIX = "telegram_"
READS = frozenset({"telegram_account_read", "telegram_chat_read", "telegram_sync_read"})
FILE_TOOLS = frozenset({"read_file", "write_file", "patch", "search_files"})
RESOLVE_MAX = 4096          # a longer argument is not a path worth resolving
STATE_ENV = "TELEGRAM_TOOLS_STATE_DIR"
STATE_NAME = "telegram-tools"
LOG_NAME = "io.github.craft-agent.telegram-tools"

# Progress lines: the declared choices of a tool's `method`, and a fixed label for each other tool.
METHODS = {
    "telegram_chat_read": ("list", "view", "topics", "search", "around", "fetch"),
    "telegram_sync_read": ("list",),
}
LABELS = {
    "telegram_account_read": "account",
    "telegram_message_send": "send",
    "telegram_file_send": "send files",
    "telegram_file_save": "save files",
    "telegram_message_edit": "edit",
    "telegram_message_delete": "delete",
    "telegram_message_react": "react",
    "telegram_message_pin": "pin",
    "telegram_chat_mark_read": "mark read",
    "telegram_sync_add": "add to sync list",
    "telegram_sync_remove": "remove from sync list",
}

# Ways around the tools: the CLIs where a command runs them (shell_commands; `_CLI`, the name as a word
# anywhere, judges a line that cannot be read that way), the state, logs, launch agents and env of the
# plugin, its install and Telegram Desktop's data.
CLIS = ("telegram-tools-cli", "telegram-tools")
_CLI = re.compile(r"(?:^|[\s;&|()`'\"=])(?:[^\s;&|()`'\"]*/)?(?:" + "|".join(map(re.escape, CLIS))
                  + r")(?=$|[\s;&|()`'\"])")
#
# `telegram-tools` as a whole path component (or a word) is the plugin's directory wherever it sits, so
# `state//telegram-tools`, `state/./telegram-tools`, a quoted component or a bare `telegram-tools` after a
# `cd` are caught; `telegram-tools-guard`, `telegram-tools.md` and `feat-hermes-telegram-tools` are not.
_PATHS = re.compile(r"state/telegram-tools|io\.github\.craft-agent\.telegram-tools|TELEGRAM_TOOLS_"
                    r"|\.hermes/plugins/telegram-tools|@craftsamo/telegram-tools|telegram-tools/dist/"
                    r"|ru\.keepcoder\.Telegram|Application(?:\\? |%20)Support/Telegram(?:\\? |%20)Desktop"
                    r"|(?:^|[/\s'\"=;&|()])telegram-tools(?=/|$|[\s'\"`;&|()])",
                    re.IGNORECASE)
# Directory and file names that belong to the account wherever they sit (the package installed under a
# profile's own plugins, a copy of its state), compared lower-case against each
# component of a resolved path.
PROTECTED_PARTS = (STATE_NAME, LOG_NAME)
_GLOB = re.compile(r"[*?\[]")
GLOB_LITERALS = 4           # a glob component names a directory only with this much fixed text
BYPASS_MESSAGE = (
    "The Telegram account is reached only through its telegram_* tools, never through the terminal or "
    "file tools: the telegram-tools CLI, its state, logs and launch agents, and Telegram Desktop's "
    "data are off limits there. Use the telegram_* tools; setting "
    "up the account and its services is the user's job."
)
CWD_MESSAGE = (
    "The terminal's working directory is inside the Telegram account's files (the telegram-tools package, "
    "its state or logs), which the terminal and file tools never use; the account is reached only "
    "through its telegram_* tools. Run commands with a workdir outside that directory."
)
UNCHECKED_MESSAGE = "The telegram-tools guard could not check this call, so it was not run."

logger = logging.getLogger(__name__)


def _load(name: str, path: Path):
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


human_gate = _load("hermes_human_gate", PLUGINS / "_shared" / "human_gate.py")
tool_preview = _load("hermes_tool_preview", PLUGINS / "_shared" / "tool_preview.py")
shell_commands = _load("hermes_shell_commands", PLUGINS / "_shared" / "shell_commands.py")
archives = _load("hermes_archive_check", PLUGINS / "messaging" / "_shared" / "archive_check.py")


def _inbound_peer() -> bool:
    """A peer agent's A2A request never touches the user's Telegram."""
    try:
        from gateway.session_context import get_session_env
    except Exception:
        return False
    return "a2a" in (get_session_env("HERMES_SESSION_PLATFORM", ""), get_session_env("HERMES_SESSION_SOURCE", ""))


def _is_write(tool: str) -> bool:
    return tool.startswith(PREFIX) and tool not in READS


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def _expand(text: str) -> str:
    """``text`` with ``~`` and environment variables (``$HOME``, ``${HOME}``, …) expanded."""
    return os.path.expanduser(os.path.expandvars(text.strip()))


def _resolved(text: str, cwd: str | None = None) -> str:
    """The real path a path-like argument names (``~``, variables, ``..`` and links resolved; a
    relative one against ``cwd``), else ''. A path with a glob keeps its glob unresolved, its fixed
    leading directories resolved."""
    if not text or "\n" in text or len(text) > RESOLVE_MAX:
        return ""
    try:
        path = _expand(text)
        if cwd and not os.path.isabs(path):
            path = os.path.join(cwd, path)
        glob_match = _GLOB.search(path)
        if not glob_match:
            return os.path.realpath(path)
        head = path[:glob_match.start()].rpartition("/")[0]
        return (os.path.realpath(head) if head else "") + path[len(head):]
    except (OSError, ValueError):
        return ""


def _names(path: str) -> tuple[str, ...]:
    return tuple(name for name in path.casefold().split(os.sep) if name)


def _wildcard(name: str) -> bool:
    """A glob component with enough fixed text to name something (a bare ``*`` names nothing)."""
    return bool(_GLOB.search(name)) and len(_GLOB.sub("", name)) >= GLOB_LITERALS


def _name_matches(name: str, protected: str) -> bool:
    if _GLOB.search(name):
        return _wildcard(name) and fnmatch.fnmatchcase(protected, name)
    return name == protected


def _agent_file(name: str) -> bool:
    """A launch agent's file or label of the plugin: ``<service id>.<label>.plist``."""
    if _GLOB.search(name):
        return _wildcard(name) and fnmatch.fnmatchcase(f"{LOG_NAME}.plist", name)
    return name.startswith(f"{LOG_NAME}.")


def _state_root() -> str:
    """Where telegram-tools keeps its state: its env var, else $XDG_STATE_HOME/telegram-tools when that
    is absolute (as the package reads it), else ~/.local/state/telegram-tools."""
    configured = os.environ.get(STATE_ENV)
    if configured:
        return os.path.expanduser(configured)
    xdg = os.environ.get("XDG_STATE_HOME")
    if xdg and os.path.isabs(xdg):
        return os.path.join(xdg, STATE_NAME)
    return os.path.expanduser(os.path.join("~", ".local", "state", STATE_NAME))


def _protected_roots() -> set[tuple[str, ...]]:
    """The directories the Telegram account lives in, as given and as resolved, as lower-case path
    components; read at each call."""
    home = os.path.expanduser("~")
    roots = {
        _state_root(),
        os.path.join(home, ".hermes", "plugins", STATE_NAME),
        os.path.join(home, "Library", "Logs", LOG_NAME),
        os.path.join(home, "Library", "Application Support", "Telegram Desktop"),
        *glob.glob(os.path.join(glob.escape(home), "Library", "Group Containers", "*.ru.keepcoder.Telegram")),
    }
    return {_names(path) for root in roots for path in (os.path.abspath(root), os.path.realpath(root))}


def _names_protected(text: str, roots: set[tuple[str, ...]], cwd: str | None = None) -> bool:
    """Whether the path ``text`` names (against ``cwd`` when relative) is, or is inside, a protected root
    or a directory named like one: a copy of the package under another profile's plugins, say, a launch
    agent's file. A glob counts when one of its components could name a protected directory."""
    names = _names(_resolved(text, cwd))
    if any(_name_matches(name, part) for name in names for part in PROTECTED_PARTS):
        return True
    if any(_agent_file(name) for name in names):
        return True
    return any(len(names) >= len(root) and all(_name_matches(n, r) for n, r in zip(names, root))
               for root in roots)


def _words(command: str) -> list[str]:
    """The words of a shell line, quotes removed; a line that does not parse is split at spaces."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        return list(lexer)
    except ValueError:
        return command.split()


def _paths_of(word: str) -> list[str]:
    """A word as a path, and the value of an ``--option=value`` or ``NAME=value`` word as one."""
    return [word, word.partition("=")[2]] if "=" in word else [word]


def _terminal_cwd(args: dict, task_id: str, session_id: str) -> str | None:
    """Where the terminal runs this call: its ``workdir`` when given, else the directory the session
    is in; None when that cannot be told, and the text checks alone judge the call."""
    workdir = args.get("workdir")
    given = _expand(workdir) if isinstance(workdir, str) and workdir.strip() else ""
    if given and os.path.isabs(given):
        return given
    tracked = _tracked_cwd(task_id, session_id)
    if not tracked or not os.path.isabs(tracked):
        return None
    return os.path.join(tracked, given) if given else tracked


def _tracked_cwd(task_id: str = "", session_id: str = "") -> str | None:
    """The session's working directory as the terminal tool keeps it (``get_session_cwd`` in the
    runtime's tools/terminal_tool.py, written after each completed command by
    tools/terminal_tool_result.py ``finalize_foreground_result``), keyed as the terminal tool keys it:
    the current session key, else the task id. None when it cannot be read."""
    try:
        from tools.approval import get_current_session_key
        from tools.terminal_tool import get_session_cwd
        for key in (get_current_session_key(default=""), task_id, session_id):
            cwd = get_session_cwd(key) if key else None
            if isinstance(cwd, str) and cwd.strip():
                return cwd
    except Exception as exc:  # noqa: BLE001 - no record: the text checks judge the call
        logger.debug("telegram-tools-guard: no tracked terminal cwd: %s", exc)
    return None


def bypass(tool: str, args, cwd: str | None = None) -> str | None:
    """A block message when a terminal or file call would go around the tools, else None. ``cwd`` is
    the directory a terminal call runs in, against which its relative words resolve.
    A pattern match on the call's text and on the real paths it names, not a sandbox."""
    args = args if isinstance(args, dict) else {}
    if tool != "terminal" and tool not in FILE_TOOLS:
        return None
    texts = list(_strings(args))
    words = []
    if tool == "terminal":
        command = args.get("command")
        if isinstance(command, str):
            if shell_commands.runs(command, CLIS, _CLI):
                return BYPASS_MESSAGE
            words = [path for word in _words(command) for path in _paths_of(word)]
    else:
        cwd = None
    if any(_PATHS.search(text) for text in texts):
        return BYPASS_MESSAGE
    roots = _protected_roots()
    if cwd and _names_protected(cwd, roots):
        return CWD_MESSAGE
    if any(_names_protected(text, roots, cwd) for text in [*texts, *words]):
        return BYPASS_MESSAGE
    return None


def _block(message: str) -> dict[str, str]:
    return {"action": "block", "message": message}


def _check(tool: str, args, task_id: str = "", session_id: str = ""):
    if tool.startswith(PREFIX):
        if _inbound_peer():
            return _block(f"{tool} is not available to inbound A2A requests")
        if _is_write(tool):
            reason = human_gate.no_human()
            if reason:
                return _block(human_gate.refusal(tool, reason))
        return None
    if tool == "terminal" or tool in FILE_TOOLS:
        cwd = _terminal_cwd(args, task_id, session_id) if tool == "terminal" and isinstance(args, dict) else None
        message = bypass(tool, args, cwd=cwd) or archives.unpacked_guard(tool, args)
        if message:
            return _block(message)
    return None


def gate(tool_name="", args=None, **kwargs):
    """pre_tool_call: a block for a telegram_* write nobody can answer, for an inbound A2A request, and
    for ways around the tools. Where the check itself fails, a write, the terminal and the file tools
    are blocked and every other call goes on."""
    tool = tool_name if isinstance(tool_name, str) else ""
    try:
        return _check(tool, args, str(kwargs.get("task_id") or ""), str(kwargs.get("session_id") or ""))
    except Exception as exc:  # noqa: BLE001 - fail closed for what the guard protects
        logger.warning("telegram-tools-guard could not check %s: %s", tool, exc)
        guarded = _is_write(tool) or tool == "terminal" or tool in FILE_TOOLS
        return _block(UNCHECKED_MESSAGE) if guarded else None


def register(ctx):
    ctx.register_hook("pre_tool_call", gate)
    for tool, methods in METHODS.items():
        schema = {
            "name": tool,
            "parameters": {
                "type": "object",
                "properties": {"method": {"type": "string", "enum": list(methods)}},
            },
        }
        tool_preview.enums(tool, schema, "method")
    for tool, label in LABELS.items():
        tool_preview.fixed(tool, label)
