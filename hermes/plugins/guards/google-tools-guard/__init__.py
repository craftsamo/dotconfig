"""google-tools-guard: what the third-party ``google-tools`` plugin leaves to Hermes.

``google-tools`` (installed outside this repo, at ``~/.hermes/plugins/google-tools``) registers the ``google_*``
tools that read and change Google Sheets, Gmail, Drive, comments and Cloud Run through the user's own account.
Its own ``pre_tool_call`` hook answers ``approve`` (its own card) for every write and leaves "is a person there
to answer the card" to Hermes, which approves a card unasked under YOLO, ``approvals.mode: off``, cron and
``hermes -z``. This plugin stays separate so that a plugin update never touches the policy, and it adds what
that plugin does not do:

- a ``google_*`` write is refused where nobody can answer a card (``human_gate``) and to an inbound A2A
  request; the reads stay open to both (a profile's ``platform_toolsets`` decide whether a specialist serves
  them over A2A). The reads are named one by one, never by a ``_read`` suffix, and a ``google_*`` tool that is
  not a named read counts as a write, so a tool the plugin adds later fails closed. The retired
  ``google-access`` plugin's ``google_sheets``, ``google_gmail`` and ``google_drive`` are not from
  ``google-tools``: they gate their own writes and this guard leaves them alone (``OTHER_TOOLS``).
- a file of a sensitive Workspaces area never leaves in the clear. ``google_drive_upload`` encrypts a file
  with age only when it lies under an ``encrypt_dirs`` directory of the profile's settings and sends anything
  else as it is; the Gmail tools carry ``attachments`` that are never encrypted. So an upload of a file in a
  sensitive area (``plugins/_shared/workspace_layout.py``) is refused unless ``encrypt_dirs`` covers it and
  ``age_recipients`` names a key, and a mail never attaches such a file. Files are judged by their real path,
  with case and Unicode form folded away (macOS folders ignore both); a layout that cannot be read refuses the
  call, and a path outside the Workspaces root is left to the package's own ``upload_dirs``. The package reads
  its settings once, when it registers, so cover is judged by the settings the profile had when this plugin
  registered (``_SNAPSHOTS``), never by the file as it is now: settings added since say so and ask for a
  gateway restart, and a profile with no readable snapshot refuses the upload.
- the terminal and file tools may not reach Google around the tools: the plugin's CLI (``google-tools-cli``:
  login and remove are the user's), the Google Cloud CLIs (``gcloud``, ``gsutil``, ``bq``; a project's own
  entry points through ``project_place`` stay allowed), the package's install and state (the accounts'
  refresh tokens and OAuth client secret, the grants), its variables, the OAuth token shapes as text and the
  Keychain. The retired ``google-access`` plugin's secrets stay guarded until it is removed: its CLI
  (``gaccess``), its state, the upstream Google scripts and its variables (``RETIRED_CLIS``,
  ``_RETIRED_PATHS``, ``_RETIRED_VARIABLES``). The terminal keeps its directory between calls, so a terminal call is also judged by
  where it runs (its ``workdir``, else the session's recorded directory) and every word of the command is
  resolved against that directory. The file tools resolve a relative path against that same recorded
  directory (the runtime's ``tools/file_tools_paths.py``), not the gateway's own, so each path argument is
  resolved against the session's recorded directory, ``$TERMINAL_CWD`` and the process directory, and is
  blocked when any of them puts it inside the protected files; the runtime's resolver is private and
  backend-specific, so it is not called.
- a word of a terminal call is a protected path when it resolves into the plugin's state or install (as
  given, existing or not), or to a directory named ``google-tools`` that exists; a word that merely names a
  git ref (``git push origin hermes/google-tools``) resolves to nothing and passes.

Hermes collects every plugin's ``pre_tool_call`` result and a valid ``block`` from any of them wins over
any ``approve``, with no card shown, so this guard needs no card of its own. A pattern match on a call's
text and on the real paths it names, not a sandbox: a script file's contents are never seen. The hook never
raises: where it cannot check a ``google_*`` write, the terminal or a file tool, it blocks.
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
import unicodedata

import hermes_yaml as yaml

PLUGINS = Path(__file__).resolve().parents[2]
PREFIX = "google_"
READS = frozenset({
    "google_account_read", "google_sheets_read", "google_gmail_read", "google_drive_read", "google_comments_read",
    "google_run_read", "google_grant_read",
})
UPLOAD_TOOL = "google_drive_upload"
MAIL_TOOLS = frozenset({"google_gmail_send", "google_gmail_draft_create", "google_gmail_draft_edit"})
FILE_TOOLS = frozenset({"read_file", "write_file", "patch", "search_files"})
RESOLVE_MAX = 4096          # a longer argument is not a path worth resolving
STATE_NAME = "google-tools"
STATE_ENV = "GOOGLE_TOOLS_STATE_DIR"
GRANTS_ENV = "GOOGLE_TOOLS_GRANTS_DIR"
GRANTS_NAME = "grants"
# The plugin's settings in a profile's config.yaml: plugins.entries.<PLUGIN_KEY>.settings.
PLUGIN_KEY = "google-tools"
STATE_SETTINGS = ("state_dir", "grants_dir")
ENCRYPT_DIRS_SETTING = "encrypt_dirs"
AGE_RECIPIENTS_SETTING = "age_recipients"
SNAPSHOT_SETTINGS = (ENCRYPT_DIRS_SETTING, AGE_RECIPIENTS_SETTING)
# The encryption settings each profile home had when `register` ran (None: they could not be read).
_SNAPSHOTS: dict[str, dict | None] = {}

# Progress lines: the declared choices of a tool's `method`, and a fixed label for each tool without one.
METHODS = {
    "google_account_read": ("list", "check"),
    "google_sheets_read": ("list", "view", "values", "snapshot", "format", "structure", "metadata"),
    "google_gmail_read": ("search", "message", "thread", "labels", "attachment", "drafts", "draft"),
    "google_drive_read": ("search", "file", "drives", "download"),
    "google_run_read": ("services", "service", "revisions", "revision", "jobs", "job", "executions", "execution",
                        "tasks", "iam", "operation"),
    "google_grant_read": ("list", "log"),
}
LABELS = {
    "google_comments_read": "read comments",
    "google_sheets_edit": "edit sheet",
    "google_sheets_append": "append rows",
    "google_sheets_clear": "clear cells",
    "google_sheets_create": "create spreadsheet",
    "google_sheets_tab_add": "add tab",
    "google_sheets_format": "format sheet",
    "google_sheets_add": "add to sheet",
    "google_sheets_restructure": "restructure sheet",
    "google_sheets_transform": "transform sheet",
    "google_sheets_protect": "protect sheet",
    "google_gmail_send": "send mail",
    "google_gmail_draft_create": "create draft",
    "google_gmail_draft_edit": "edit draft",
    "google_gmail_draft_delete": "delete draft",
    "google_gmail_label": "label mail",
    "google_gmail_label_create": "create label",
    "google_gmail_trash": "trash mail",
    "google_drive_upload": "upload file",
    "google_drive_folder_create": "create folder",
    "google_drive_copy": "copy file",
    "google_drive_rename": "rename file",
    "google_drive_move": "move file",
    "google_drive_trash": "trash file",
    "google_drive_restore": "restore file",
    "google_comments_add": "add comment",
    "google_comments_status": "set comment status",
    "google_comments_edit": "edit comment",
    "google_comments_delete": "delete comment",
    "google_run_service_deploy": "deploy service",
    "google_run_job_deploy": "deploy job",
    "google_run_job_run": "run job",
    "google_run_execution_cancel": "cancel execution",
    "google_run_job_delete": "delete job",
    "google_run_revision_delete": "delete revision",
    "google_run_service_delete": "delete service",
    "google_run_traffic_set": "set traffic",
    "google_grant_create": "create grant",
    "google_grant_revoke": "revoke grant",
}

# Ways around the tools. This plugin's CLI and the Google Cloud CLIs, where a command runs them: directly,
# behind a wrapper such as sudo or env, inside `bash -c`, or through a package runner (shell_commands).
# Mentions that run nothing (`grep gcloud notes.md`) stay allowed. `_CLI` judges a line that cannot be read
# that way. In a project repository (project_place) the project's own entry points and scripts run
# (`pnpm run deploy`, `./scripts/deploy.sh`, `make deploy`), but never a CLI named directly, and never this
# plugin's own CLI, which is not a dependency a project has.
# The MCP server's bin, `google-tools`, is not installed on PATH and is reached only as
# `@craftsamo/google-tools` through a package runner (`_PATHS`); as a word it would read every git ref named
# like the package (`git merge origin/google-tools`) as a run.
CLIS = ("google-tools-cli", "gcloud", "gsutil", "bq")
_CLI = re.compile(r"(?:^|[\s;&|()`'\"=])(?:[^\s;&|()`'\"]*/)?(?:" + "|".join(map(re.escape, CLIS))
                  + r")(?=$|[\s;&|()`'\"])")
PACKAGE_CLIS = ("google-tools-cli",)
_PACKAGE_CLI = re.compile(r"(?:^|[\s;&|()`'\"=])(?:[^\s;&|()`'\"]*/)?(?:" + "|".join(map(re.escape, PACKAGE_CLIS))
                          + r")(?=$|[\s;&|()`'\"])")
#
# The plugin's install and state, in a call's text, for the terminal and the file tools. Only the specific
# forms are matched as text: a bare `google-tools` word is also a git branch or a remote ref
# (`git push origin hermes/google-tools`). A directory of that name, wherever it sits, is caught by
# `_names_protected` instead, through the real path a word resolves to (`state//google-tools`,
# `state/./google-tools`, a quoted component, a bare `google-tools` after a `cd`).
_PATHS = re.compile(r"state/google-tools(?![\w-])|\.hermes/plugins/google-tools(?![\w-])|@craftsamo/google-tools"
                    r"|(?<![\w-])google-tools/dist/", re.IGNORECASE)
# The retired google-access plugin, until it is removed: remove everything down to `_RETIRED_VARIABLES`, their
# checks in `_is_write`, `_runs_cli` and `bypass`, and the mention of `gaccess` in BYPASS_MESSAGE, together
# with the plugin, which stays installed (disabled) until then.
# Its tools gate their own writes, so `_is_write` leaves them alone: `google_` tools that are not google-tools'.
OTHER_TOOLS = frozenset({"google_sheets", "google_gmail", "google_drive"})
# Its setup CLI, read like the others but never allowed, not even in a project repository.
RETIRED_CLIS = ("gaccess",)
_RETIRED_CLI = re.compile(r"(?:^|[\s;&|()`'\"=])(?:[^\s;&|()`'\"]*/)?(?:" + "|".join(map(re.escape, RETIRED_CLIS))
                          + r")(?=$|[\s;&|()`'\"])")
# The secrets that plugin keeps: its state directory (with its gcloud configuration, mandates and age identity),
# the user's own gcloud configuration, the upstream Google scripts and the token files they write. Its source
# under plugins/ stays readable.
_RETIRED_PATHS = re.compile(r"(?<!plugins/)google-access|\.config/gcloud|google-workspace/scripts|google_api\.py"
                            r"|google_token\.json|google_client_secret\.json", re.IGNORECASE)
# Its variables and secrets: names, so case-sensitive like the shell's (`google_oauth.py` is a file name).
_RETIRED_VARIABLES = re.compile(r"CLOUDSDK_|GOOGLE_OAUTH|GOOGLE_ACCESS_AGE|GCLOUD_MANDATE_KEY|AGE-SECRET-KEY")
# The OAuth token shapes (an access token, a client secret) and the Keychain's own reads, in a terminal call's
# text only: a file tool may write a note that names one of them, and runs nothing.
_TERMINAL = re.compile(
    r"(?<!\w)ya29\.|(?<!\w)GOCSPX-"
    # A read that leaves out the scope searches the one named after the working directory's repository, and
    # the item's scope is free: so any value read or change of an item in the hermes project (where the
    # access plugins keep their credentials) and the Keychain's own password reads are blocked; ls and show
    # stay open.
    r"|\bsecret\s+(?:-k\s+\S+\s+)?(?:get|set|update|rm|import|env)\b[^;&|\n]*?(?:-p|--project)(?:\s+|=)['\"]?hermes"
    r"(?![\w-])|find-generic-password"
    r"|dump-keychain|\bsecret\s+export\b", re.IGNORECASE)
# The variables the plugin reads, with any label suffix (GOOGLE_TOOLS_CREDENTIALS_WORK, GOOGLE_TOOLS_GRANT_KEY).
# Shell variable names are case-sensitive, so this pattern is too.
_VARIABLES = re.compile(r"(?<!\w)GOOGLE_TOOLS_\w*")

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
    "Google (Sheets, Gmail, Drive, comments, Cloud Run) is reached only through the google_* tools "
    "(google_sheets_read, google_gmail_send, …), never through the terminal or file tools: not "
    "google-tools-cli, gcloud, gsutil, bq or gaccess, the package's state or install (the accounts' credentials, the "
    "grants), its variables or the Keychain. Use the google_* tools; logging in is the user's job. A project's "
    "own tooling runs from the terminal in its repository (workdir, or a leading `cd <absolute path> &&`): "
    "`pnpm run deploy`, `./scripts/deploy.sh`."
)
CWD_MESSAGE = (
    "The terminal's working directory is inside the google-tools files (the package or its state: the "
    "accounts' credentials, the grants), which the terminal and file tools never use; Google is reached only "
    "through the google_* tools. Run commands with a workdir outside that directory."
)
UPLOAD_MESSAGE = (
    "A file in a sensitive Workspaces area goes to Drive only encrypted, and this profile's google-tools "
    "settings (encrypt_dirs, age_recipients) do not cover it, so it was not uploaded. Setting them is the "
    "user's job; do not send the file another way."
)
ATTACHMENT_MESSAGE = (
    "Mail attachments go out in the clear, so a file in a sensitive Workspaces area is never attached. Upload "
    "it to Drive with google_drive_upload instead, which encrypts it where the profile's settings allow."
)
LAYOUT_MESSAGE = (
    "The Workspaces layout cannot be read, so whether a file lies in a sensitive area is unknown and the call "
    "was not run: {error}"
)
SNAPSHOT_MESSAGE = (
    "The google-tools settings this profile started with were not read when the guard loaded, so whether "
    "they encrypt a file in a sensitive Workspaces area is unknown and it was not uploaded. Restarting the "
    "gateway reloads them; that is the user's job (`launchd/gateway-launchctl.sh restart`)."
)
RESTART_MESSAGE = (
    "The google-tools encryption settings (encrypt_dirs, age_recipients) cover this file now, but they "
    "changed after the gateway started, and the package reads its settings only when it starts: it would "
    "still send the file unencrypted, so it was not uploaded. The user must restart the gateway "
    "(`launchd/gateway-launchctl.sh restart`)."
)
UNCHECKED_MESSAGE = "The google-tools guard could not check this call, so it was not run."

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
project_place = _load("hermes_project_place", PLUGINS / "_shared" / "project_place.py")
workspace_layout = _load("hermes_workspace_layout", PLUGINS / "_shared" / "workspace_layout.py")


def _inbound_peer() -> bool:
    """A peer agent's A2A request never changes the user's Google account."""
    try:
        from gateway.session_context import get_session_env
    except Exception:
        return False
    return "a2a" in (get_session_env("HERMES_SESSION_PLATFORM", ""), get_session_env("HERMES_SESSION_SOURCE", ""))


def _is_write(tool: str) -> bool:
    """A google-tools tool that is not a named read: any ``google_*`` tool bar the named reads and the
    retired plugin's own tools (``OTHER_TOOLS``)."""
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


def _hermes_home() -> Path:
    """The running profile's home, the directory its ``config.yaml`` is in."""
    from hermes_constants import get_hermes_home
    return Path(get_hermes_home())


def _mapping(value) -> dict:
    return value if isinstance(value, dict) else {}


def _settings() -> dict:
    """The plugin's settings in the profile's ``config.yaml``, read at each call; ``{}`` when it has none.
    Read, never ``load_config()``: upstream may rewrite configuration on load. Raises when the file cannot
    be read or is not a mapping."""
    config = yaml.safe_load((_hermes_home() / "config.yaml").read_text(encoding="utf-8")) or {}
    if not isinstance(config, dict):
        raise ValueError("config.yaml is not a mapping")
    entry = _mapping(_mapping(_mapping(config.get("plugins")).get("entries")).get(PLUGIN_KEY))
    return _mapping(entry.get("settings"))


def _setting_dirs(settings: dict, key: str) -> list[str]:
    """The real paths a path setting (a path, or a list of them) names, ``~`` expanded; a relative or
    non-text entry names nothing, since the package refuses it."""
    value = settings.get(key)
    items = value if isinstance(value, list) else [value]
    expanded = (os.path.expanduser(item.strip()) for item in items if isinstance(item, str))
    return [os.path.realpath(path) for path in expanded if os.path.isabs(path)]


def _home_key() -> str:
    """The running profile's home as ``register`` keys its snapshot: the resolved ``get_hermes_home()``, which
    a multiplex gateway answers per turn (as ``specialist-call`` keys its registration)."""
    return str(_hermes_home().resolve())


def _take_snapshot() -> None:
    """Record the encryption settings the running profile has now. The package captures its settings once, when
    it registers, so these (not the file as it is later) say what it will do; a profile whose settings cannot
    be read gets ``None``, which covers nothing. A later registration of the same home replaces it, as the
    package's own does."""
    key = _home_key()
    try:
        settings = _settings()
    except Exception as exc:  # noqa: BLE001 - an unknown snapshot covers nothing
        logger.warning("google-tools-guard could not read the settings of %s: %s", key, exc)
        _SNAPSHOTS[key] = None
        return
    _SNAPSHOTS[key] = {name: settings.get(name) for name in SNAPSHOT_SETTINGS}


def _configured_dirs() -> list[str]:
    """The state and grants directories the profile's settings name. A configuration that cannot be read
    adds nothing, so an ordinary terminal call is never refused for it."""
    try:
        settings = _settings()
        return [path for key in STATE_SETTINGS for path in _setting_dirs(settings, key)]
    except Exception as exc:  # noqa: BLE001 - the environment and default roots still guard the state
        logger.debug("google-tools-guard: no state settings: %s", exc)
        return []


def _default_state_root() -> str:
    """Where google-tools keeps its state unless told otherwise: $XDG_STATE_HOME/google-tools when that is
    absolute (as the package reads it), else ~/.local/state/google-tools. The grants default to a folder
    here whatever the state directory setting says."""
    xdg = os.environ.get("XDG_STATE_HOME")
    if xdg and os.path.isabs(xdg):
        return os.path.join(xdg, STATE_NAME)
    return os.path.expanduser(os.path.join("~", ".local", "state", STATE_NAME))


def _state_root() -> str:
    """Where google-tools keeps the accounts' credentials: its env var, else the default."""
    configured = (os.environ.get(STATE_ENV) or "").strip()
    return os.path.expanduser(configured) if configured else _default_state_root()


def _protected_roots() -> set[tuple[str, ...]]:
    """The directories Google is reached through, as given and as resolved, as lower-case path components;
    read at each call."""
    home = os.path.expanduser("~")
    roots = {
        _state_root(),
        _default_state_root(),
        os.path.join(_default_state_root(), GRANTS_NAME),
        os.path.join(home, ".hermes", "plugins", STATE_NAME),
        *_configured_dirs(),
    }
    grants = os.environ.get(GRANTS_ENV)
    if grants:
        roots.add(os.path.expanduser(grants))
    return {_names(path) for root in roots for path in (os.path.abspath(root), os.path.realpath(root))}


def _has_protected_part(path: str) -> bool:
    """Whether a component of the resolved ``path`` is a protected directory name: a literal one only where
    the path up to and including it exists (a word like ``hermes/google-tools`` that names a git ref
    resolves to nothing), a glob where it could name one."""
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
        logger.debug("google-tools-guard: no tracked terminal cwd: %s", exc)
    return None


def _file_tool_bases(recorded: str | None) -> list[str | None]:
    """The directories a file tool's relative path may resolve against: the session's recorded
    directory (``recorded``), an absolute ``$TERMINAL_CWD`` and the process directory, the runtime's
    anchors in its order. Each is checked, so a path that resolves into the protected files under any of
    them is caught; ``[None]`` when none can be told (a relative word then resolves against the process
    directory)."""
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


def _runs_cli(command: str, args: dict) -> bool:
    """Whether the command runs a Google CLI or this plugin's own, bar a project's own entry points."""
    place = project_place.project_dir(args)
    return (shell_commands.runs(command, CLIS, _CLI, project=place is not None)
            or shell_commands.runs(command, PACKAGE_CLIS, _PACKAGE_CLI)
            or shell_commands.runs(command, RETIRED_CLIS, _RETIRED_CLI))


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
    patterns = (_PATHS, _RETIRED_PATHS, _RETIRED_VARIABLES)
    bases = [cwd]
    if tool == "terminal":
        patterns += (_TERMINAL, _VARIABLES)
        command = args.get("command")
        if isinstance(command, str):
            if _runs_cli(command, args):
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


def _area_key(name: str) -> str:
    """A folder name with its Unicode form and case folded away: macOS folders ignore both, so a path
    spelled ``personal/`` is the ``Personal`` area."""
    return unicodedata.normalize("NFC", name).casefold()


def _folded(path: str) -> tuple[str, ...]:
    return tuple(_area_key(part) for part in path.split(os.sep) if part)


def _below(path: str, root: str) -> tuple[str, ...] | None:
    """The folded components of the real path ``path`` under the real path ``root``; None when it is not
    inside it (``root`` itself is not)."""
    names, base = _folded(path), _folded(root)
    return names[len(base):] if len(names) > len(base) and names[:len(base)] == base else None


def _real(text: str, cwd: str | None) -> str:
    """The real path a file argument names, ``~`` and variables expanded, a relative one against ``cwd``;
    a path that does not exist is resolved as written. Raises where it cannot be resolved (a NUL byte)."""
    path = _expand(text)
    if cwd and not os.path.isabs(path):
        path = os.path.join(cwd, path)
    return os.path.realpath(path)


def _sensitive(real: str, layout) -> bool:
    """Whether the real path lies inside a sensitive area of the Workspaces layout: under its root, with
    the first component below the root naming a sensitive area. The area folder itself is in none."""
    below = _below(real, os.path.realpath(layout.root))
    if not below or len(below) < 2:
        return False
    return any(area.sensitive and _area_key(area.name) == below[0] for area in layout.areas)


def _encrypted(real: str, settings: dict) -> bool:
    """Whether google-tools sends the file at ``real`` age-encrypted: under an ``encrypt_dirs`` directory
    and with ``age_recipients`` naming at least one key, as the profile's settings read."""
    recipients = settings.get(AGE_RECIPIENTS_SETTING)
    if not isinstance(recipients, list) or not recipients:
        return False
    return any(_below(real, directory) is not None for directory in _setting_dirs(settings, ENCRYPT_DIRS_SETTING))


def _local_files(tool: str, args, task_id: str, session_id: str) -> str | None:
    """A block message when a google-tools write sends a file of a sensitive Workspaces area in the clear:
    an upload not covered by the profile's ``encrypt_dirs`` and ``age_recipients`` as ``register`` read them
    (``_SNAPSHOTS``), or any mail attachment. A layout that cannot be read, and a profile with no snapshot,
    block; a file outside the Workspaces root is not judged here."""
    args = args if isinstance(args, dict) else {}
    if tool == UPLOAD_TOOL:
        key = "path"
    elif tool in MAIL_TOOLS:
        key = "attachments"
    else:
        return None
    files = [text for text in _strings(args.get(key)) if text.strip()]
    if not files:
        return None
    try:
        layout = workspace_layout.load()
    except workspace_layout.LayoutError as exc:
        return LAYOUT_MESSAGE.format(error=exc)
    # google-tools resolves a relative path against the directory Hermes hands it, which this hook cannot
    # read: judge it against every directory it may be, and count it sensitive under any of them.
    bases = _file_tool_bases(_tracked_cwd(task_id, session_id))
    sensitive = [real for text in files for real in {_real(text, base) for base in bases}
                 if _sensitive(real, layout)]
    if not sensitive:
        return None
    if tool in MAIL_TOOLS:
        return ATTACHMENT_MESSAGE
    # The package encrypts by the settings it registered with, not by the file as it is now: only the
    # snapshot decides. Settings added since (and still in the file) are told apart, so the user knows the
    # fix is a restart.
    snapshot = _SNAPSHOTS.get(_home_key())
    if snapshot is None:
        return SNAPSHOT_MESSAGE
    if all(_encrypted(real, snapshot) for real in sensitive):
        return None
    try:
        current = _settings()
    except Exception as exc:  # noqa: BLE001 - the snapshot already refuses; only the wording is lost
        logger.debug("google-tools-guard: no current settings: %s", exc)
        return UPLOAD_MESSAGE
    return RESTART_MESSAGE if all(_encrypted(real, current) for real in sensitive) else UPLOAD_MESSAGE


def _block(message: str) -> dict[str, str]:
    return {"action": "block", "message": message}


def _check(tool: str, args, task_id: str = "", session_id: str = ""):
    if _is_write(tool):
        if _inbound_peer():
            return _block(f"{tool} is not available to inbound A2A requests")
        reason = human_gate.no_human()
        if reason:
            return _block(human_gate.refusal(tool, reason))
        message = _local_files(tool, args, task_id, session_id)
        return _block(message) if message else None
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
    """pre_tool_call: a block for a google_* write nobody can answer, for a write of an inbound A2A
    request, for a file of a sensitive area sent in the clear, and for ways around the tools. Where the
    check itself fails, a write, the terminal and the file tools are blocked and every other call goes on."""
    tool = tool_name if isinstance(tool_name, str) else ""
    try:
        return _check(tool, args, str(kwargs.get("task_id") or ""), str(kwargs.get("session_id") or ""))
    except Exception as exc:  # noqa: BLE001 - fail closed for what the guard protects
        logger.warning("google-tools-guard could not check %s: %s", tool, exc)
        guarded = _is_write(tool) or tool == "terminal" or tool in FILE_TOOLS
        return _block(UNCHECKED_MESSAGE) if guarded else None


def register(ctx):
    ctx.register_hook("pre_tool_call", gate)
    try:
        _take_snapshot()
    except Exception as exc:  # noqa: BLE001 - no snapshot: an upload from a sensitive area is refused
        logger.warning("google-tools-guard has no settings snapshot: %s", exc)
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
