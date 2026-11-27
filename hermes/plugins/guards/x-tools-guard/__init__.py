"""x-tools-guard: what the third-party ``x-tools`` plugin leaves to Hermes.

``x-tools`` (installed outside this repo, at ``~/.hermes/plugins/x-tools``) registers the ``x_*`` tools that
read X through a reading account's cookies. Nothing it does writes to X: its writes (``x_media_download``,
``x_grant_create``, ``x_grant_revoke``) change the local disk only. Its own ``pre_tool_call`` hook answers
``approve`` (its own card) for those writes and leaves "is a person there to answer the card" to Hermes, which
approves a card unasked under YOLO, ``approvals.mode: off``, cron and ``hermes -z``. This plugin stays separate
so that a plugin update never touches the policy, and it adds what that plugin does not do:

- an ``x-tools`` write is refused where nobody can answer a card (``human_gate``) and to an inbound A2A
  request; the reads stay open to both (a profile's ``platform_toolsets`` decide whether a specialist serves
  them over A2A). The reads are named one by one, never by a ``_read`` suffix, and an ``x_*`` tool that is
  neither a named read nor a named foreign tool counts as an ``x-tools`` write, so a tool the plugin adds
  later fails closed. Hermes has a built-in ``x_search`` (xAI) that is not from ``x-tools``: it is read-only
  and this guard leaves it alone entirely (``OTHER_TOOLS``). A new foreign ``x_`` tool must be added there,
  or it counts as a write; that failure is the safe one.
- the terminal and file tools may not reach X around the tools: the plugin's CLI (``x-tools-cli``: engine
  install, login, remove are the user's), its install and state (the reading account's cookies, the engine,
  FxTwitter's record, the grants), ``twscrape`` (the engine's library) and FxTwitter with its mirrors, the
  session cookies as text, the cookie variables, and the Keychain item the cookies come from. The terminal
  keeps its directory between calls, so a terminal call is also judged by where it runs (its ``workdir``, else
  the session's recorded directory) and every word of the command is resolved against that directory. The
  file tools resolve a relative path against that same recorded directory (the runtime's
  ``tools/file_tools_paths.py``), not the gateway's own, so each path argument is resolved against the
  session's recorded directory, ``$TERMINAL_CWD`` and the process directory, and is blocked when any of them
  puts it inside the protected files; the runtime's resolver is private and backend-specific, so it is not
  called.
- a word of a terminal call is a protected path when it resolves into the plugin's state or install (as
  given, existing or not), or to a directory named ``x-tools`` that exists; a word that merely names a git ref
  (``git push origin hermes/x-tools``) resolves to nothing and passes. A mention of an ``x.com`` URL is never
  blocked: the agent handles post URLs.

Hermes collects every plugin's ``pre_tool_call`` result and a valid ``block`` from any of them wins over
any ``approve``, with no card shown, so this guard needs no card of its own. A pattern match on a call's
text and on the real paths it names, not a sandbox: a script file's contents are never seen. The hook never
raises: where it cannot check an ``x-tools`` write, the terminal or a file tool, it blocks.
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
PREFIX = "x_"
READS = frozenset({
    "x_account_read", "x_post_read", "x_user_read", "x_list_read", "x_community_read", "x_trend_read",
    "x_grant_read",
})
# `x_` tools that are not x-tools': Hermes' own, read-only. A tool here is never a write and never blocked.
OTHER_TOOLS = frozenset({"x_search"})
FILE_TOOLS = frozenset({"read_file", "write_file", "patch", "search_files"})
RESOLVE_MAX = 4096          # a longer argument is not a path worth resolving
STATE_NAME = "x-tools"
STATE_ENV = "X_TOOLS_STATE_DIR"
GRANTS_ENV = "X_TOOLS_GRANTS_DIR"

# Progress lines: the declared choices of a tool's `method`, and a fixed label for each other tool.
METHODS = {
    "x_post_read": ("view", "search", "quotes", "mentions", "conversation", "thread", "timeline"),
    "x_user_read": ("view", "search", "followers", "following", "reposters"),
    "x_list_read": ("posts", "members"),
    "x_community_read": ("view", "posts", "members"),
    "x_trend_read": ("explore",),
    "x_grant_read": ("list", "log"),
}
LABELS = {
    "x_account_read": "account",
    "x_media_download": "save media",
    "x_grant_create": "grant",
    "x_grant_revoke": "revoke grant",
}

# Ways around the tools. This plugin's CLI and twscrape (the engine's library, which a command would run with
# the reading account's cookies), where a command runs them: directly, behind a wrapper such as sudo or env,
# inside `bash -c`, or through a package runner (shell_commands). Mentions that run nothing
# (`grep twscrape notes.md`) stay allowed. `_CLI` judges a line that cannot be read that way.
# The MCP server's bin, `x-tools`, is not installed on PATH and is reached only as `@craftsamo/x-tools`
# through a package runner (`_PATHS`); as a word it would read every git ref named like the package
# (`git merge origin/x-tools`) as a run.
CLIS = ("x-tools-cli", "twscrape")
_CLI = re.compile(r"(?:^|[\s;&|()`'\"=])(?:[^\s;&|()`'\"]*/)?(?:" + "|".join(map(re.escape, CLIS))
                  + r")(?=$|[\s;&|()`'\"])")
#
# The plugin's install and state, in a call's text, for the terminal and the file tools. Only the specific
# forms are matched as text: a bare `x-tools` word is also a git branch or a remote ref
# (`git push origin hermes/x-tools`). A directory of that name, wherever it sits, is caught by
# `_names_protected` instead, through the real path a word resolves to (`state//x-tools`, `state/./x-tools`,
# a quoted component, a bare `x-tools` after a `cd`).
_PATHS = re.compile(r"state/x-tools(?![\w-])|\.hermes/plugins/x-tools(?![\w-])|@craftsamo/x-tools"
                    r"|(?<![\w-])x-tools/dist/", re.IGNORECASE)
# The engine's library, FxTwitter and its mirrors, the session cookies as text, the cookies' Keychain item
# and scope, and the Keychain's own reads, in a terminal call's text only: a file tool may write a note that
# names one of them, and runs nothing.
_TERMINAL = re.compile(
    r"(?<![\w-])(?:import|from)\s+twscrape\b|(?<![\w-])-m\s+twscrape\b"
    r"|fxtwitter|fixupx|vxtwitter|fixvx"
    r"|(?<!\w)(?:auth_token|ct0)\s*="
    r"|X_READER_COOKIES|(?<![\w-])x-reader(?![\w-])"
    # A read that leaves out the scope searches the one named after the working directory's repository, and
    # the item's scope is free: so any value read or change of an item in the hermes project (where the
    # access plugins keep their credentials) and the Keychain's own password reads are blocked; ls and show
    # stay open.
    r"|\bsecret\s+(?:-k\s+\S+\s+)?(?:get|set|update|rm|import|env)\b[^;&|\n]*?(?:-p|--project)(?:\s+|=)['\"]?hermes"
    r"(?![\w-])|find-generic-password"
    r"|dump-keychain|\bsecret\s+export\b", re.IGNORECASE)
# The variables the plugin reads, with any label suffix (X_TOOLS_COOKIES_WORK, X_TOOLS_GRANT_KEY). Shell
# variable names are case-sensitive, so this pattern is too.
_VARIABLES = re.compile(r"(?<!\w)X_TOOLS_\w*")

# Directory names that belong to the plugin wherever they sit (the package installed under a profile's own
# plugins, a copy of its state, a checkout named like it), compared lower-case against each component of a
# resolved path that exists, or that a glob could name.
PROTECTED_PARTS = (STATE_NAME,)
_GLOB = re.compile(r"[*?\[]")
GLOB_LITERALS = 4           # a glob component names a directory only with this much fixed text
CD_COMMANDS = frozenset({"cd", "pushd"})
SEPARATORS = ";&|()<>"      # what ends a command in a shell line
NESTED_DEPTH = 4            # how many scripts held in a word (`bash -c '…'`) are read
BYPASS_MESSAGE = (
    "X is read only through the x-tools tools (x_post_read, x_user_read, …), never through the terminal or "
    "file tools: not x-tools-cli, twscrape, FxTwitter or its mirrors, the reading account's state (its "
    "cookies, the engine, the grants) or the Keychain item that holds the cookies. Use the x_* tools; "
    "logging the reading account in is the user's job."
)
CWD_MESSAGE = (
    "The terminal's working directory is inside the x-tools files (the package or its state: the reading "
    "account's cookies, the engine, the grants), which the terminal and file tools never use; X is read only "
    "through the x_* tools. Run commands with a workdir outside that directory."
)
UNCHECKED_MESSAGE = "The x-tools guard could not check this call, so it was not run."

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


def _inbound_peer() -> bool:
    """A peer agent's A2A request never writes on the user's machine through x-tools."""
    try:
        from gateway.session_context import get_session_env
    except Exception:
        return False
    return "a2a" in (get_session_env("HERMES_SESSION_PLATFORM", ""), get_session_env("HERMES_SESSION_SOURCE", ""))


def _is_write(tool: str) -> bool:
    """An x-tools tool that is not a named read: any ``x_*`` tool bar the named foreign ones."""
    return tool.startswith(PREFIX) and tool not in READS and tool not in OTHER_TOOLS


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


def _default_state_root() -> str:
    """Where x-tools keeps its state unless told otherwise: $XDG_STATE_HOME/x-tools when that is absolute
    (as the package reads it), else ~/.local/state/x-tools. The grants default to a folder here whatever
    the state directory setting says."""
    xdg = os.environ.get("XDG_STATE_HOME")
    if xdg and os.path.isabs(xdg):
        return os.path.join(xdg, STATE_NAME)
    return os.path.expanduser(os.path.join("~", ".local", "state", STATE_NAME))


def _state_root() -> str:
    """Where x-tools keeps the reading accounts' cookies and the engine: its env var, else the default."""
    configured = (os.environ.get(STATE_ENV) or "").strip()
    return os.path.expanduser(configured) if configured else _default_state_root()


def _protected_roots() -> set[tuple[str, ...]]:
    """The directories X is reached through, as given and as resolved, as lower-case path components;
    read at each call."""
    home = os.path.expanduser("~")
    roots = {
        _state_root(),
        _default_state_root(),
        os.path.join(home, ".hermes", "plugins", STATE_NAME),
    }
    grants = os.environ.get(GRANTS_ENV)
    if grants:
        roots.add(os.path.expanduser(grants))
    return {_names(path) for root in roots for path in (os.path.abspath(root), os.path.realpath(root))}


def _has_protected_part(path: str) -> bool:
    """Whether a component of the resolved ``path`` is a protected directory name: a literal one only where
    the path up to and including it exists (a word like ``hermes/x-tools`` that names a git ref resolves to
    nothing), a glob where it could name one."""
    parts = [part for part in path.split(os.sep) if part]
    for index, part in enumerate(parts):
        name = part.casefold()
        for protected in PROTECTED_PARTS:
            if _GLOB.search(name):
                if _name_matches(name, protected):
                    return True
            elif name == protected and os.path.lexists(os.sep + os.sep.join(parts[:index + 1])):
                return True
    return False


def _names_protected(text: str, roots: set[tuple[str, ...]], cwd: str | None = None) -> bool:
    """Whether the path ``text`` names (against ``cwd`` when relative) is, or is inside, a protected root
    (as given, existing or not) or a directory named like one that exists: a copy of the package under
    another profile's plugins, say. A glob counts when one of its components could name a protected
    directory."""
    resolved = _resolved(text, cwd)
    if _has_protected_part(resolved):
        return True
    names = _names(resolved)
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


def _word_paths(command: str, cwd: str | None, depth: int = 0) -> list[tuple[str, str | None]]:
    """Each path a word of the line may name, with the directory it resolves against: ``cwd``, or where
    the line's own ``cd`` or ``pushd`` moved to before it. A word holding a script (``bash -c '…'``) is read
    as a line of its own."""
    found, here, moving = [], cwd, False
    for word in _words(command):
        if depth < NESTED_DEPTH and re.search(r"\s", word):
            found.extend(_word_paths(word, here, depth + 1))
        found.extend((path, here) for path in _paths_of(word))
        if moving and not word.startswith("-"):
            moving = False
            if word[:1] not in SEPARATORS:
                here = _resolved(word, here) or here
        elif word in CD_COMMANDS:
            moving = True
    return found


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
        logger.debug("x-tools-guard: no tracked terminal cwd: %s", exc)
    return None


def _file_tool_bases(recorded: str | None) -> list[str | None]:
    """The directories a file tool's relative path may resolve against: the session's recorded
    directory (``recorded``), an absolute ``$TERMINAL_CWD`` and the process directory, the runtime's anchors
    in its order. Each is checked, so a path that resolves into the protected files under any of them is
    caught; ``[None]`` when none can be told (a relative word then resolves against the process directory)."""
    configured = os.environ.get("TERMINAL_CWD", "").strip()
    try:
        process = os.getcwd()
    except OSError:
        process = None
    bases: list[str | None] = []
    for base in (recorded, configured if os.path.isabs(configured) else None, process):
        if base and base not in bases:
            bases.append(base)
    return bases or [None]


def bypass(tool: str, args, cwd: str | None = None) -> str | None:
    """A block message when a terminal or file call would go around the tools, else None. ``cwd`` is
    the directory a terminal call runs in, against which its relative words resolve; for a file tool it is
    the session's recorded directory, one of the directories its relative paths resolve against.
    A pattern match on the call's text and on the real paths it names, not a sandbox."""
    args = args if isinstance(args, dict) else {}
    if tool != "terminal" and tool not in FILE_TOOLS:
        return None
    texts = list(_strings(args))
    paths = []
    patterns = (_PATHS,)
    bases = [cwd]
    if tool == "terminal":
        patterns += (_TERMINAL, _VARIABLES)
        command = args.get("command")
        if isinstance(command, str):
            if shell_commands.runs(command, CLIS, _CLI):
                return BYPASS_MESSAGE
            paths = _word_paths(command, cwd)
    else:
        bases = _file_tool_bases(cwd)
        cwd = None
    if any(pattern.search(text) for pattern in patterns for text in texts):
        return BYPASS_MESSAGE
    roots = _protected_roots()
    if cwd and _names_protected(cwd, roots):
        return CWD_MESSAGE
    if any(_names_protected(path, roots, here)
           for path, here in [*((text, base) for base in bases for text in texts), *paths]):
        return BYPASS_MESSAGE
    return None


def _block(message: str) -> dict[str, str]:
    return {"action": "block", "message": message}


def _check(tool: str, args, task_id: str = "", session_id: str = ""):
    if _is_write(tool):
        if _inbound_peer():
            return _block(f"{tool} is not available to inbound A2A requests")
        reason = human_gate.no_human()
        if reason:
            return _block(human_gate.refusal(tool, reason))
        return None
    if tool == "terminal" or tool in FILE_TOOLS:
        if tool == "terminal":
            cwd = _terminal_cwd(args, task_id, session_id) if isinstance(args, dict) else None
        else:
            cwd = _tracked_cwd(task_id, session_id)
        message = bypass(tool, args, cwd=cwd)
        if message:
            return _block(message)
    return None


def gate(tool_name="", args=None, **kwargs):
    """pre_tool_call: a block for an x-tools write nobody can answer, for a write of an inbound A2A
    request, and for ways around the tools. Where the check itself fails, a write, the terminal and the
    file tools are blocked and every other call goes on."""
    tool = tool_name if isinstance(tool_name, str) else ""
    try:
        return _check(tool, args, str(kwargs.get("task_id") or ""), str(kwargs.get("session_id") or ""))
    except Exception as exc:  # noqa: BLE001 - fail closed for what the guard protects
        logger.warning("x-tools-guard could not check %s: %s", tool, exc)
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
