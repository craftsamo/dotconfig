"""github-tools-guard: what the third-party ``github-tools`` plugin leaves to Hermes.

``github-tools`` (installed outside this repo, at ``~/.hermes/plugins/github-tools``) registers the
``github_<area>_<verb>`` tools. Its own ``pre_tool_call`` hook answers ``approve`` for every tool that is
not a read and leaves "is a person there to answer the card" to Hermes, which approves a card unasked
under YOLO, ``approvals.mode: off``, cron and ``hermes -z``. This plugin stays separate so that a plugin
update never touches the policy, and it adds what that plugin does not do:

- a ``github_*`` write is refused where nobody can answer a card (``human_gate``), and every
  ``github_*`` tool is refused to an inbound A2A request. A tool that is not a known read counts as a
  write, so a tool the plugin adds later fails closed.
- the terminal and file tools may not write to GitHub around the tools' cards: a ``gh`` command other
  than a read is refused (``gh_terminal``), and so are the package's own entry points
  (``github-tools-cli``, the ``github-tools`` MCP server, ``@craftsamo/github-tools``, its
  ``dist/cli.js`` and ``dist/mcp.js``), which would run a write with no card, and the installed plugin
  directory. The terminal keeps its directory between calls, so a terminal call is also judged by where
  it runs (its ``workdir``, else the session's recorded directory) and every word of the command is
  resolved against that directory; a file tool's relative path is resolved against the recorded
  directory too, as the runtime does. A source checkout of the package elsewhere is ordinary work.

Hermes collects every plugin's ``pre_tool_call`` result and a valid ``block`` from any of them wins over
any ``approve``, with no card shown, so this guard needs no card of its own. A pattern match on a call's
text and on the real paths it names, not a sandbox. The hook never raises: where it cannot check a
``github_*`` write, the terminal or a file tool, it blocks.
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

HERE = Path(__file__).resolve().parent
PLUGINS = HERE.parents[1]
TOOL = re.compile(r"github_[a-z]+_[a-z_]+")
READS = frozenset({
    "github_issue_read", "github_pr_read", "github_stack_read", "github_project_read", "github_repo_read",
    "github_label_read", "github_milestone_read", "github_ruleset_read", "github_release_read",
    "github_workflow_read", "github_run_read",
})
FILE_TOOLS = frozenset({"read_file", "write_file", "patch", "search_files"})
RESOLVE_MAX = 4096          # a longer argument is not a path worth resolving
HERMES_HOME_ENV = "HERMES_HOME"
PLUGIN_NAME = "github-tools"
INSTALL_PARTS = ("plugins", PLUGIN_NAME)

# Progress lines: the declared choices of a read tool's `method`, and a fixed label for each write.
METHODS = {
    "github_issue_read": ("view", "list"),
    "github_pr_read": ("view", "list", "checks", "diff"),
    "github_stack_read": ("view", "list"),
    "github_project_read": ("view", "list", "item_list"),
    "github_repo_read": ("view", "list"),
    "github_label_read": ("list",),
    "github_milestone_read": ("list",),
    "github_ruleset_read": ("view", "list"),
    "github_release_read": ("list", "view"),
    "github_workflow_read": ("list", "view"),
    "github_run_read": ("list", "view"),
}
LABELS = {
    "github_issue_close": "close issue",
    "github_issue_comment": "comment on issue",
    "github_issue_create": "create issue",
    "github_issue_develop": "link branch to issue",
    "github_issue_edit": "edit issue",
    "github_issue_relate": "relate issues",
    "github_issue_reopen": "reopen issue",
    "github_label_create": "create label",
    "github_label_delete": "delete label",
    "github_label_edit": "edit label",
    "github_milestone_create": "create milestone",
    "github_milestone_edit": "edit milestone",
    "github_pr_close": "close PR",
    "github_pr_comment": "comment on PR",
    "github_pr_create": "create PR",
    "github_pr_edit": "edit PR",
    "github_pr_merge": "merge PR",
    "github_pr_ready": "mark PR ready",
    "github_pr_reopen": "reopen PR",
    "github_pr_review": "review PR",
    "github_project_create": "create project",
    "github_project_field_ensure": "ensure project field",
    "github_project_item_add": "add project item",
    "github_project_item_archive": "archive project item",
    "github_project_item_convert": "convert project item",
    "github_project_item_create": "create project item",
    "github_project_item_edit": "edit project item",
    "github_project_item_unarchive": "unarchive project item",
    "github_project_link": "link project",
    "github_project_unlink": "unlink project",
    "github_project_view_ensure": "ensure project view",
    "github_release_create": "create release",
    "github_release_delete": "delete release",
    "github_release_edit": "edit release",
    "github_release_publish": "publish release",
    "github_repo_archive": "archive repo",
    "github_repo_create": "create repo",
    "github_repo_edit": "edit repo",
    "github_repo_unarchive": "unarchive repo",
    "github_repo_visibility": "change repo visibility",
    "github_ruleset_create": "create ruleset",
    "github_ruleset_delete": "delete ruleset",
    "github_ruleset_edit": "edit ruleset",
    "github_run_cancel": "cancel run",
    "github_run_rerun": "rerun run",
    "github_stack_link": "link stack",
    "github_stack_unlink": "unlink stack",
    "github_workflow_run": "run workflow",
}

# Ways around the tools: the package's CLIs where a command runs them (shell_commands; `_CLI`, the name
# as a word anywhere, judges a line that cannot be read that way: `github-tools-cli` at any path, the
# MCP bin `github-tools` bare or under a `bin` directory, since a path ending in `github-tools` is the
# source checkout), the package named to a runner, its dist entry points, and the installed plugin.
CLIS = ("github-tools-cli", PLUGIN_NAME)
_BEFORE = r"(?:^|[\s;&|()`'\"=])"
_AFTER = r"(?=$|[\s;&|()`'\"])"
_CLI = re.compile(_BEFORE + r"(?:[^\s;&|()`'\"]*/)?github-tools-cli" + _AFTER
                  + "|" + _BEFORE + r"(?:[^\s;&|()`'\"]*/bin/)?github-tools" + _AFTER)
_ENTRY = re.compile(r"@craftsamo/github-tools|github-tools/dist/", re.IGNORECASE)
_INSTALL = re.compile(r"plugins/github-tools(?![\w.-])", re.IGNORECASE)
_GLOB = re.compile(r"[*?\[]")
# The file headers of a V4A patch, as the runtime's patch parser reads them (tools/patch_parser.py,
# tools/file_tools.py `_collect_v4a_header_paths`): a line starting with the marker, a Move naming
# both ends.
_PATCH_HEADER = re.compile(r"^\*\*\*\s*(?:Update|Add|Delete)\s+File:\s*(.+)$", re.MULTILINE)
_PATCH_MOVE = re.compile(r"^\*\*\*\s*Move\s+File:\s*(.+?)\s*->\s*(.+)$", re.MULTILINE)
GLOB_LITERALS = 4           # a glob component names a directory only with this much fixed text
BYPASS_MESSAGE = (
    "GitHub is written only through the github_* tools, each asking on a card, never through the "
    "terminal or file tools: the github-tools CLI and MCP server, its package and its installed plugin "
    "directory are off limits there. Use the github_* tools; setting up the plugin is the user's job."
)
CWD_MESSAGE = (
    "The terminal's working directory is inside the installed github-tools plugin, which the terminal "
    "and file tools never use; GitHub is written only through the github_* tools. Run commands with a "
    "workdir outside that directory."
)
UNCHECKED_MESSAGE = "The github-tools guard could not check this call, so it was not run."

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
gh_terminal = _load("hermes_github_tools_gh_terminal", HERE / "gh_terminal.py")


def _inbound_peer() -> bool:
    """A peer agent's A2A request never touches the user's GitHub."""
    try:
        from gateway.session_context import get_session_env
    except Exception:
        return False
    return "a2a" in (get_session_env("HERMES_SESSION_PLATFORM", ""), get_session_env("HERMES_SESSION_SOURCE", ""))


def _is_tool(tool: str) -> bool:
    """Whether ``tool`` is one of github-tools': ``github_<area>_<verb>``."""
    return TOOL.fullmatch(tool) is not None


def _is_write(tool: str) -> bool:
    return _is_tool(tool) and tool not in READS


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


def _install_roots() -> set[tuple[str, ...]]:
    """The directories the plugin is installed in (``~/.hermes`` and the running ``HERMES_HOME``), as
    given and as resolved, as lower-case path components; read at each call."""
    homes = {os.path.expanduser("~/.hermes")}
    configured = os.environ.get(HERMES_HOME_ENV)
    if configured:
        homes.add(os.path.expanduser(configured))
    roots = {os.path.join(home, *INSTALL_PARTS) for home in homes}
    return {_names(path) for root in roots for path in (os.path.abspath(root), os.path.realpath(root))}


def _names_install(text: str, roots: set[tuple[str, ...]], cwd: str | None = None) -> bool:
    """Whether the path ``text`` names (against ``cwd`` when relative) is, or is inside, an installed
    plugin directory: a root, or any ``plugins/github-tools`` (a profile's own copy). A glob counts
    when its components could name one. A directory called ``github-tools`` anywhere else is not."""
    names = _names(_resolved(text, cwd))
    if any(_name_matches(a, INSTALL_PARTS[0]) and _name_matches(b, INSTALL_PARTS[1])
           for a, b in zip(names, names[1:])):
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


def _patch_paths(patch) -> list[str]:
    """The paths a V4A patch string names in its file headers (both ends of a move), else []."""
    if not isinstance(patch, str):
        return []
    named = [m.group(1) for m in _PATCH_HEADER.finditer(patch)]
    named += [end for m in _PATCH_MOVE.finditer(patch) for end in m.groups()]
    return [path.strip() for path in named]


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


def _file_cwd(task_id: str, session_id: str) -> str | None:
    """The directory a file tool resolves a relative path against: the one the terminal recorded for
    the session (tools/file_operations.py); None when that cannot be told."""
    tracked = _tracked_cwd(task_id, session_id)
    return tracked if tracked and os.path.isabs(tracked) else None


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
        logger.debug("github-tools-guard: no tracked terminal cwd: %s", exc)
    return None


def bypass(tool: str, args, cwd: str | None = None) -> str | None:
    """A block message when a terminal or file call would go around the tools, else None. ``cwd`` is
    the directory against which relative words resolve: where a terminal call runs, or where a file
    tool's relative path points; only the terminal is refused for running inside the plugin.
    A pattern match on the call's text and on the real paths it names, not a sandbox."""
    args = args if isinstance(args, dict) else {}
    if tool != "terminal" and tool not in FILE_TOOLS:
        return None
    texts = list(_strings(args))
    words = []
    if tool == "terminal":
        command = args.get("command")
        if isinstance(command, str):
            message = gh_terminal.blocked(command)
            if message:
                return message
            if _ENTRY.search(command) or shell_commands.runs(command, CLIS, _CLI):
                return BYPASS_MESSAGE
            words = [path for word in _words(command) for path in _paths_of(word)]
    elif tool == "patch":
        words = _patch_paths(args.get("patch"))
    if any(_INSTALL.search(text) for text in texts):
        return BYPASS_MESSAGE
    roots = _install_roots()
    if tool == "terminal" and cwd and _names_install(cwd, roots):
        return CWD_MESSAGE
    if any(_names_install(text, roots, cwd) for text in [*texts, *words]):
        return BYPASS_MESSAGE
    return None


def _block(message: str) -> dict[str, str]:
    return {"action": "block", "message": message}


def _check(tool: str, args, task_id: str = "", session_id: str = ""):
    if _is_tool(tool):
        if _inbound_peer():
            return _block(f"{tool} is not available to inbound A2A requests")
        if tool not in READS:
            reason = human_gate.no_human()
            if reason:
                return _block(human_gate.refusal(tool, reason))
        return None
    if tool == "terminal" or tool in FILE_TOOLS:
        cwd = None
        if isinstance(args, dict):
            cwd = _terminal_cwd(args, task_id, session_id) if tool == "terminal" else _file_cwd(task_id, session_id)
        message = bypass(tool, args, cwd=cwd)
        if message:
            return _block(message)
    return None


def gate(tool_name="", args=None, **kwargs):
    """pre_tool_call: a block for a github_* write nobody can answer, for an inbound A2A request, and
    for ways around the tools. Where the check itself fails, a write, the terminal and the file tools
    are blocked and every other call goes on."""
    tool = tool_name if isinstance(tool_name, str) else ""
    try:
        return _check(tool, args, str(kwargs.get("task_id") or ""), str(kwargs.get("session_id") or ""))
    except Exception as exc:  # noqa: BLE001 - fail closed for what the guard protects
        logger.warning("github-tools-guard could not check %s: %s", tool, exc)
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
