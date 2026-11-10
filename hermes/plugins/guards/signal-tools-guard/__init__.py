"""signal-tools-guard: what the third-party ``signal-tools`` plugin leaves to Hermes.

``signal-tools`` (installed outside this repo, at ``~/.hermes/plugins/signal-tools``) registers the
``signal_*`` tools. Its own ``pre_tool_call`` hook answers ``approve`` for every tool that is not a read
and leaves "is a person there to answer the card" to Hermes, which approves a card unasked under YOLO,
``approvals.mode: off``, cron and ``hermes -z``. This plugin stays separate so that a plugin update
never touches the policy, and it adds what that plugin does not do:

- a ``signal_*`` write is refused where nobody can answer a card (``human_gate``), and every ``signal_*``
  tool is refused to an inbound A2A request. A tool that is not a known read counts as a write, so a tool
  the plugin adds later fails closed.
- the terminal and file tools may not reach the Signal account around its tools: ``signal-cli``, the
  plugin's CLI and MCP server, its state, logs and launch agents, Signal Desktop's database and the old
  plugin's state, and nothing inside a ``.unpacked`` folder of a received archive may be run. The
  terminal keeps its directory between calls, so a terminal call is also judged by where it runs (its
  ``workdir``, else the session's recorded directory) and every word of the command is resolved
  against that directory.

Hermes collects every plugin's ``pre_tool_call`` result and a valid ``block`` from any of them wins over
any ``approve``, with no card shown, so this guard needs no card of its own. A pattern match on a call's
text and on the real paths it names, not a sandbox. The hook never raises: where it cannot check a
``signal_*`` write, the terminal or a file tool, it blocks.
"""

from __future__ import annotations

import fnmatch
import importlib.util
import logging
import os
from pathlib import Path
import re
import shlex
import sys

PLUGINS = Path(__file__).resolve().parents[2]
PREFIX = "signal_"
READS = frozenset({"signal_account_read", "signal_chat_read", "signal_contact_read"})
FILE_TOOLS = frozenset({"read_file", "write_file", "patch", "search_files"})
RESOLVE_MAX = 4096          # a longer argument is not a path worth resolving
STATE_ENV = "SIGNAL_TOOLS_STATE_DIR"
STATE_NAME = "signal-tools"
LOG_NAME = "io.github.craft-agent.signal-tools"

# Progress lines: the declared choices of a tool's `method`, and a fixed label for each other tool.
METHODS = {
    "signal_chat_read": ("list", "view", "search", "around"),
    "signal_contact_read": ("list", "check"),
}
LABELS = {
    "signal_account_read": "account",
    "signal_message_send": "send",
    "signal_file_send": "send files",
    "signal_file_save": "save files",
    "signal_message_edit": "edit",
    "signal_message_delete": "delete",
    "signal_message_react": "react",
}

# Ways around the tools: the CLIs where a command runs them (shell_commands; `_CLI`, the name as a word
# anywhere, judges a line that cannot be read that way), the state, logs, launch agents and env of the
# plugin, its install, signal-cli's data, Signal Desktop's database, and the old plugin's state.
CLIS = ("signal-cli", "signal-tools-cli", "signal-tools")
_CLI = re.compile(r"(?:^|[\s;&|()`'\"=])(?:[^\s;&|()`'\"]*/)?(?:" + "|".join(map(re.escape, CLIS))
                  + r")(?=$|[\s;&|()`'\"])")
#
# `signal-tools` as a whole path component (or a word) is the plugin's directory wherever it sits, so
# `state//signal-tools`, `state/./signal-tools`, a quoted component or a bare `signal-tools` after a
# `cd` are caught; `signal-tools-guard`, `signal-tools.md` and `feat-hermes-signal-tools` are not.
_PATHS = re.compile(r"state/signal-tools|io\.github\.craft-agent\.signal-tools|SIGNAL_TOOLS_"
                    r"|\.hermes/plugins/signal-tools|@craftsamo/signal-tools|signal-tools/dist/"
                    r"|share/signal-cli|Application(?:\\? |%20)Support/Signal|hermes-signal(?!-tools)"
                    r"|(?:^|[/\s'\"=;&|()])signal-tools(?=/|$|[\s'\"`;&|()])",
                    re.IGNORECASE)
# Directory names that belong to the account wherever they sit (the package installed under a profile's
# own plugins, a copy of its state), compared lower-case against each component of a resolved path.
PROTECTED_PARTS = (STATE_NAME, LOG_NAME, "hermes-signal")
_GLOB = re.compile(r"[*?\[]")
GLOB_LITERALS = 4           # a glob component names a directory only with this much fixed text
BYPASS_MESSAGE = (
    "The Signal account is reached only through its signal_* tools, never through the terminal or file "
    "tools: signal-cli, the signal-tools CLI, its state, logs and launch agents, and Signal Desktop's "
    "database are off limits there. Use the signal_* tools; setting up the account and its services is "
    "the user's job."
)
CWD_MESSAGE = (
    "The terminal's working directory is inside the Signal account's files (the signal-tools package, "
    "its state or logs), which the terminal and file tools never use; the account is reached only "
    "through its signal_* tools. Run commands with a workdir outside that directory."
)
UNCHECKED_MESSAGE = "The signal-tools guard could not check this call, so it was not run."

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
    """A peer agent's A2A request never touches the user's Signal."""
    try:
        from gateway.session_context import get_session_env
    except Exception:
        return False
    return "a2a" in (get_session_env("HERMES_SESSION_PLATFORM", ""), get_session_env("HERMES_SESSION_SOURCE", ""))


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
        glob = _GLOB.search(path)
        if not glob:
            return os.path.realpath(path)
        head = path[:glob.start()].rpartition("/")[0]
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


def _state_root() -> str:
    """Where signal-tools keeps its state: its env var, else $XDG_STATE_HOME/signal-tools, else
    ~/.local/state/signal-tools."""
    configured = os.environ.get(STATE_ENV)
    if configured:
        return os.path.expanduser(configured)
    xdg = os.environ.get("XDG_STATE_HOME")
    if xdg:
        return os.path.join(os.path.expanduser(xdg), STATE_NAME)
    return os.path.expanduser(os.path.join("~", ".local", "state", STATE_NAME))


def _protected_roots() -> set[tuple[str, ...]]:
    """The directories the Signal account lives in, as given and as resolved, as lower-case path
    components; read at each call."""
    roots = {
        _state_root(),
        os.path.expanduser("~/.local/state/hermes-signal"),
        os.path.expanduser("~/.hermes/plugins/signal-tools"),
        os.path.expanduser(f"~/Library/Logs/{LOG_NAME}"),
    }
    return {_names(path) for root in roots for path in (os.path.abspath(root), os.path.realpath(root))}


def _names_protected(text: str, roots: set[tuple[str, ...]], cwd: str | None = None) -> bool:
    """Whether the path ``text`` names (against ``cwd`` when relative) is, or is inside, a protected root
    or a directory named like one: a copy of the package under another profile's plugins, say. A glob
    counts when one of its components could name a protected directory."""
    names = _names(_resolved(text, cwd))
    if any(_name_matches(name, part) for name in names for part in PROTECTED_PARTS):
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
        logger.debug("signal-tools-guard: no tracked terminal cwd: %s", exc)
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
        if tool not in READS:
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
    """pre_tool_call: a block for a signal_* write nobody can answer, for an inbound A2A request, and
    for ways around the tools. Where the check itself fails, a write, the terminal and the file tools
    are blocked and every other call goes on."""
    tool = tool_name if isinstance(tool_name, str) else ""
    try:
        return _check(tool, args, str(kwargs.get("task_id") or ""), str(kwargs.get("session_id") or ""))
    except Exception as exc:  # noqa: BLE001 - fail closed for what the guard protects
        logger.warning("signal-tools-guard could not check %s: %s", tool, exc)
        guarded = (tool.startswith(PREFIX) and tool not in READS) or tool == "terminal" or tool in FILE_TOOLS
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
