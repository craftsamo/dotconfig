"""cloudflare-tools-guard: what the third-party ``cloudflare-tools`` plugin leaves to Hermes.

``cloudflare-tools`` (installed outside this repo, at ``~/.hermes/plugins/cloudflare-tools``) registers the
``cloudflare_*`` tools. Its own ``pre_tool_call`` hook answers ``approve`` (its own card) for every write and
leaves "is a person there to answer the card" to Hermes, which approves a card unasked under YOLO,
``approvals.mode: off``, cron and ``hermes -z``. This plugin stays separate so that a plugin update
never touches the policy, and it adds what that plugin does not do:

- a ``cloudflare_*`` write is refused where nobody can answer a card (``human_gate``) and to an inbound A2A
  request; the reads stay open to both (a specialist serves them over A2A). The reads are named one by one,
  never by a ``_read`` suffix, and a tool that is not a named read counts as a write, so a tool the plugin
  adds later fails closed.
- the terminal and file tools may not reach Cloudflare around its tools: the Cloudflare CLIs (``wrangler``,
  ``cloudflared``, ``flarectl``; a project's own ``wrangler`` through its package manager stays allowed, as
  ``project_place`` defines it), the API by hand or through an SDK, the plugin's CLI, install and state (its
  grants), the CLIs' logins, and the token variables. The terminal keeps its directory between calls, so a
  terminal call is also judged by where it runs (its ``workdir``, else the session's recorded directory) and
  every word of the command is resolved against that directory.
- the terminal may not print the process environment. The plugin reads its API tokens
  (``CLOUDFLARE_API_TOKEN[_<LABEL>]`` and ``CLOUDFLARE_ACCOUNT_ID[_<LABEL>]``) and its grant key from the
  gateway's environment, and the terminal tool passes that environment on to its children, so ``env``,
  ``printenv``, ``export -p``, ``ps e``, ``os.environ``, ``jq -n env``, Perl's ``%ENV``, ``compgen -e``, an
  indirect ``${!name}`` and the like would show them even where no command names a variable. Such commands
  are refused (a best-effort list: the forms above, not every way a program can read its environment) and a
  single non-secret variable is read with ``echo "$NAME"``. A command that only mentions one
  (``grep -n printenv docs/x.md``) runs nothing and passes.
- a word of a terminal call is a protected path when it resolves into the plugin's state, install or a
  CLI's login (as given, existing or not), or to a directory named ``cloudflare-tools`` that exists; a word
  that merely names a git ref (``git push origin hermes/cloudflare-tools``) resolves to nothing and passes.
- the retired ``cloudflare-access`` plugin's token scope and state are guarded the same way until it is
  removed (the ``OLD_`` constants).

Hermes collects every plugin's ``pre_tool_call`` result and a valid ``block`` from any of them wins over
any ``approve``, with no card shown, so this guard needs no card of its own. A pattern match on a call's
text and on the real paths it names, not a sandbox: a script file's contents are never seen, and the
gateway's environment still reaches every subprocess the terminal starts. The hook never raises: where it
cannot check a ``cloudflare_*`` write, the terminal or a file tool, it blocks.
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
PREFIX = "cloudflare_"
READS = frozenset({
    "cloudflare_access_read", "cloudflare_account_read", "cloudflare_analytics_read", "cloudflare_dns_read",
    "cloudflare_email_read", "cloudflare_grant_read", "cloudflare_hyperdrive_read", "cloudflare_pages_read",
    "cloudflare_queues_read", "cloudflare_registrar_read", "cloudflare_rules_read", "cloudflare_storage_read",
    "cloudflare_tunnel_read", "cloudflare_turnstile_read", "cloudflare_vectorize_read", "cloudflare_workers_read",
    "cloudflare_zone_read",
})
FILE_TOOLS = frozenset({"read_file", "write_file", "patch", "search_files"})
RESOLVE_MAX = 4096          # a longer argument is not a path worth resolving
STATE_NAME = "cloudflare-tools"
GRANTS_ENV = "CLOUDFLARE_TOOLS_GRANTS_DIR"
GATEWAY_JOB = "ai.hermes.multiplex"

# Progress lines: the declared choices of a tool's `method`, and a fixed label for each write.
METHODS = {
    "cloudflare_access_read": ("apps", "app", "policies"),
    "cloudflare_account_read": ("list", "view", "audit"),
    "cloudflare_analytics_read": ("traffic", "paths", "countries", "statuses", "security", "security_events",
                                  "workers"),
    "cloudflare_dns_read": ("list", "view", "export"),
    "cloudflare_email_read": ("routing", "rules", "addresses"),
    "cloudflare_grant_read": ("list", "log"),
    "cloudflare_hyperdrive_read": ("list", "view"),
    "cloudflare_pages_read": ("list", "view", "deployments", "logs", "domains"),
    "cloudflare_queues_read": ("list", "view"),
    "cloudflare_registrar_read": ("list", "view"),
    "cloudflare_rules_read": ("phases", "rules"),
    "cloudflare_storage_read": ("buckets", "bucket", "objects", "namespaces", "keys", "databases", "database"),
    "cloudflare_tunnel_read": ("tunnels", "tunnel"),
    "cloudflare_turnstile_read": ("list", "view"),
    "cloudflare_vectorize_read": ("list", "view"),
    "cloudflare_workers_read": ("list", "view", "deployments", "versions", "routes", "domains", "schedules",
                                "secrets"),
    "cloudflare_zone_read": ("list", "view", "settings", "ssl", "dnssec"),
}
LABELS = {
    "cloudflare_dns_record_add": "add DNS records",
    "cloudflare_dns_record_delete": "delete DNS records",
    "cloudflare_dns_record_edit": "edit DNS records",
    "cloudflare_email_address_add": "add email address",
    "cloudflare_email_address_delete": "delete email address",
    "cloudflare_email_catchall_edit": "edit catch-all rule",
    "cloudflare_email_rule_add": "add email rule",
    "cloudflare_email_rule_delete": "delete email rule",
    "cloudflare_email_rule_edit": "edit email rule",
    "cloudflare_grant_create": "create grant",
    "cloudflare_grant_revoke": "revoke grant",
    "cloudflare_pages_domain_add": "add Pages domain",
    "cloudflare_pages_domain_remove": "remove Pages domain",
    "cloudflare_pages_rollback": "roll back Pages",
    "cloudflare_rules_add": "add rule",
    "cloudflare_rules_delete": "delete rule",
    "cloudflare_rules_edit": "edit rule",
    "cloudflare_storage_create": "create storage",
    "cloudflare_storage_delete": "delete storage",
    "cloudflare_tunnel_route_add": "add tunnel route",
    "cloudflare_tunnel_route_edit": "edit tunnel route",
    "cloudflare_tunnel_route_remove": "remove tunnel route",
    "cloudflare_workers_rollback": "roll back Worker",
    "cloudflare_zone_cache_purge": "purge cache",
    "cloudflare_zone_cache_purge_all": "purge whole cache",
    "cloudflare_zone_dnssec_disable": "disable DNSSEC",
    "cloudflare_zone_dnssec_enable": "enable DNSSEC",
    "cloudflare_zone_setting_edit": "edit zone setting",
    "cloudflare_zone_setting_weaken": "weaken zone setting",
}

# Ways around the tools. The Cloudflare CLIs, where a command runs them: directly, behind a wrapper such as
# sudo or env, inside `bash -c`, or through a package runner such as npx or pnpm exec (shell_commands).
# Mentions that run nothing (`grep wrangler package.json`, `brew install cloudflared`) stay allowed.
# `_CLI_TEXT` judges a line that cannot be read that way: the command itself after a separator, a wrapper or
# a runner, or the CLI anywhere with a command that uses the account after it.
CLIS = ("wrangler", "cloudflared", "flarectl")
# In a project repository (project_place), wrangler may run as one of the project's own dependencies through
# its package manager (`pnpm exec wrangler deploy`): that is the project's tooling, signed in with the user's
# own wrangler login, not this plugin's token.
PROJECT_CLIS = ("wrangler",)
_RUNNER = r"(?:npx|bunx|pnpx|(?:pnpm|npm|yarn|bun)\s+(?:exec|dlx|x)|yarn)\s+(?:-\S+\s+)*"
_CLIS = r"(?:wrangler|cloudflared|flarectl)(?:@\S*)?"   # a package runner may pin a version: wrangler@4
_CLI_COMMANDS = (r"login|logout|whoami|deploy|publish|delete|rollback|versions|deployments|secret|secrets-store|kv"
                 r"|r2|d1|pages|tail|queues|hyperdrive|vectorize|dispatch-namespace|ai|workflows|triggers"
                 r"|pipelines|containers|cert|mtls-certificate|dev|tunnel|access|service|zone|dns|user|firewall"
                 r"|pagerules")
_CLI_TEXT = re.compile(
    r"(?:^|[;&|`\n]|\$\()\s*(?:(?:sudo|env|command|exec|nohup|time|xargs)\s+(?:-\S+\s+|\w+=\S*\s+)*)*"
    r"(?:" + _RUNNER + r")?(?:\S*/)?" + _CLIS + r"(?=\s|$)"
    r"|(?:^|[\s;&|()`'\"=/])" + _CLIS + r"(?:\s+-{1,2}[A-Za-z][\w-]*(?:[=\s]+(?!-)\S+)?)*\s+(?:" + _CLI_COMMANDS
    + r")\b", re.IGNORECASE)
# This plugin's own CLI (`_PACKAGE_CLI`, the name as a word anywhere, judges a line that cannot be read that way).
# Its MCP server's bin, `cloudflare-tools`, is not installed on PATH and is reached only as
# `@craftsamo/cloudflare-tools` through a package runner (`_PATHS`); as a word it would read every git ref
# named like the package (`git merge origin/cloudflare-tools`) as a run.
PACKAGE_CLIS = ("cloudflare-tools-cli",)
_PACKAGE_CLI = re.compile(r"(?:^|[\s;&|()`'\"=])(?:[^\s;&|()`'\"]*/)?(?:" + "|".join(map(re.escape, PACKAGE_CLIS))
                          + r")(?=$|[\s;&|()`'\"])")
#
# The plugin's install, state and the CLIs' logins, in a call's text, for the terminal and the file tools.
# Only the specific forms are matched as text: a bare `cloudflare-tools` word is also a git branch or a
# remote ref (`git push origin hermes/cloudflare-tools`). A directory of that name, wherever it sits, is
# caught by `_names_protected` instead, through the real path a word resolves to (`state//cloudflare-tools`,
# `state/./cloudflare-tools`, a quoted component, a bare `cloudflare-tools` after a `cd`).
_PATHS = re.compile(r"state/cloudflare-tools(?![\w-])|\.hermes/plugins/cloudflare-tools(?![\w-])"
                    r"|@craftsamo/cloudflare-tools|cloudflare-tools/dist/"
                    r"|\.cloudflared(?![\w-])|\.wrangler/config\b",
                    re.IGNORECASE)
# The API, the credentials and the Keychain, in a terminal call's text only: a file tool may write a note
# that names a variable or the API host, and runs nothing.
_TERMINAL = re.compile(
    r"api\.cloudflare\.com|\bcf(?:ut|at|k)_[A-Za-z0-9_-]{8,}|\bX-Auth-Key\b"
    r"|\bimport\s+cloudflare\b|\bfrom\s+cloudflare(?:\.\w+)*\s+import\b|\bfrom\s+['\"]cloudflare['\"]"
    r"|\bimport\s*\(\s*['\"]cloudflare['\"]|\brequire\s*\(?\s*['\"]cloudflare['\"]|github\.com/cloudflare/cloudflare-go"
    # The tokens' names are free, and a read that leaves out the scope searches the one named after the working
    # directory's repository: so any value read or change of an item in the hermes project (where the access
    # plugins keep their credentials) and the Keychain's own password reads are blocked; ls and show stay open.
    r"|\bsecret\s+(?:-k\s+\S+\s+)?(?:get|set|update|rm|import|env)\b[^;&|\n]*?(?:-p|--project)(?:\s+|=)['\"]?hermes"
    r"(?![\w-])|find-generic-password"
    r"|dump-keychain|\bsecret\s+export\b", re.IGNORECASE)
# The variables the plugin and the Cloudflare CLIs read, with any label suffix (CLOUDFLARE_API_TOKEN_WORK).
# Shell variable names are case-sensitive, so this pattern is too.
_VARIABLES = re.compile(r"(?<!\w)(?:CLOUDFLARE_API_(?:TOKEN|KEY)|CLOUDFLARE_ACCOUNT_ID|CF_API_(?:TOKEN|KEY)"
                        r"|CLOUDFLARE_TOOLS_)\w*")
# The retired cloudflare-access plugin's token scope and state, until it is removed. The dot directory is
# judged for the file tools too (its source under hermes/plugins/cloudflare-access stays readable by them);
# the word only in a terminal call.
OLD_STATE_NAME = ".cloudflare-access"
OLD_STORE = re.compile(r"\.cloudflare-access(?![\w-])", re.IGNORECASE)
OLD_TERMINAL = re.compile(r"(?<![\w-])cloudflare-access(?![\w-])", re.IGNORECASE)

# The process environment holds the tokens, and the terminal's children inherit it. Where a command runs one
# of these, it prints the whole environment (or, for `ps`, other processes'): `_ENV_DUMPS` pairs the program
# names the line must run with the pattern for the form that prints. `runs` reads by command position, so a
# mention that runs nothing (`grep -n printenv docs/x.md`, `echo "run printenv"`) passes; a form it cannot
# follow (an unclosed quote, a here-document) is judged by the pattern alone. `env FOO=1 cmd` and
# `env -u X cmd` run another command and print nothing; `env -i` clears the environment first.
_LEAD = (r"(?:^|[;&|(`'\"{\n]|\$\()\s*(?:(?:then|do|else|elif|if|while|until|!)\s+)*"
         r"(?:(?:sudo|doas|exec|command|nohup|time|xargs)\s+(?:-\S+\s+)*)*(?:\S*/)?")
_END = r"\s*(?=$|[;&|)`'\"\n]|\d*[<>])"
_PRINTENV = re.compile(r"(?:^|[\s;&|()`'\"=/])printenv(?=$|[\s;&|()`'\"])")
_ENV_DUMP = re.compile(_LEAD + r"env(?:\s+(?:-0|--null|-v|--debug|--|-[uC]\s*\S+|--(?:unset|chdir)=\S+"
                       r"|[A-Za-z_]\w*=\S*))*" + _END)
_SHELL_DUMP = re.compile(_LEAD + r"(?:export(?:\s+-p)?|(?:declare|typeset)(?:\s+-[A-Za-z]*[px][A-Za-z]*)?|set)"
                         + _END)
# `ps` shows the environment of processes with BSD `e` (`ps eww`, `ps auxe`) or `-E`; `-e` and `-ef` list all
# processes and show none.
_PS_FLAGS = "AaCcEefhjLlMmrSTuvwx"
_PS_ENV = re.compile(_LEAD + r"ps(?=\s)(?:\s+[^\s;&|()`'\"<>]+)*?\s+(?:-[A-Za-z]*E[A-Za-z]*"
                     r"|[" + _PS_FLAGS + r"]*[eE][" + _PS_FLAGS + r"]*)(?=$|[\s;&|)`'\"<>])")
# Interpreters reading the whole environment, and the launchd job the gateway runs as.
_ENV_READERS = re.compile(r"os\.environ|process\.env|Deno\.env|Bun\.env|\benviron\b", re.IGNORECASE)
_LAUNCHCTL = re.compile(r"(?<![\w-])launchctl\s+(?:getenv|procinfo)\b"
                        r"|(?<![\w-])launchctl\s+(?:print|list|dumpstate|blame)\b[^;&|\n]*" + re.escape(GATEWAY_JOB),
                        re.IGNORECASE)
# The whole environment through the languages a command may carry: jq's `env` and `$ENV` (a bare program
# after the flags, or inside the first quoted argument; `.env` and `env.NAME` are a field and one variable),
# Perl's `%ENV`, Ruby's `ENV` taken whole or through an enumerating method (`ENV['X']` is one variable), PHP's
# `getenv()` with no name, `$_ENV`, `$_SERVER` and `phpinfo()`, and bash's `compgen -e` / `-v`, which list names.
_JQ_PROGRAM = r"(?<![\w.$/-])env(?![\w.-])|\$ENV\b(?!\.)"
_JQ_ENV = re.compile(r"(?<![\w-])jq(?:\s+-{1,2}[A-Za-z][\w-]*)*\s+(?:env|\$ENV)(?![\w.$-])"
                     r"|(?<![\w-])jq\b[^;&|\n'\"]*['\"][^'\"]*?(?:" + _JQ_PROGRAM + r")")
_PERL_ENV = re.compile(r"%ENV\b")
_RUBY_ENV = re.compile(r"(?<![\w$@%.:/-])ENV(?:\.(?:to_h|to_hash|to_a|each\w*|keys|values|map|select|filter|reject"
                       r"|inspect|to_s|sort\w*|collect|find\w*|count|size|dup|clone|merge|slice|group_by|sum|reduce"
                       r"|inject|entries|filter_map|first|lazy)\b|(?![\w.:\[{=])(?!\s*[\[{=]))")
_PHP_ENV = re.compile(r"getenv\(\s*\)|\$_ENV\b(?!\s*\[)|\$_SERVER\b(?!\s*\[)|phpinfo\s*\(")
_COMPGEN = re.compile(r"(?<![\w-])compgen\s+(?:-[ev]+|-A\s+(?:variable|export))(?=$|[\s;&|)`'\"])")
_ENV_DUMPS = (
    (("printenv",), _PRINTENV),
    (("env",), _ENV_DUMP),
    (("export", "declare", "typeset", "set"), _SHELL_DUMP),
    (("ps",), _PS_ENV),
    ((), _ENV_READERS),
    (("launchctl",), _LAUNCHCTL),
    (("jq",), _JQ_ENV),
    (("perl",), _PERL_ENV),
    (("ruby", "irb"), _RUBY_ENV),
    (("php",), _PHP_ENV),
    (("compgen",), _COMPGEN),
)
# A process's environment as a file, wherever it is read: the file tools and `cat` both.
_ENVIRON_FILE = re.compile(r"/proc/[^/\s'\"]+/environ")
# Bash's indirect expansion reads a variable by a name or a prefix (`${!CLOUD*}`, `${!name}`): in a terminal
# call's text, wherever it stands.
_INDIRECT = re.compile(r"\$\{!")

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
    "Cloudflare runs only through the cloudflare_* tools, never through the terminal or file tools: not "
    "wrangler, cloudflared or flarectl, the API with curl or an SDK, the cloudflare-tools CLI, its install "
    "and state (the grants), the tokens (the process environment, the Keychain), or the CLIs' logins "
    "(~/.wrangler/config, ~/.cloudflared). Use the cloudflare_* tools; storing a token is the user's job. "
    "Deploying code is a job for the project's own tooling, which runs from the terminal in its repository "
    "(workdir, or a leading `cd <absolute path> &&`): `pnpm run deploy`, or the project's own wrangler as "
    "`pnpm exec wrangler …`."
)
ENV_MESSAGE = (
    "The environment of this session holds the Cloudflare tokens, so commands that print it (env, printenv, "
    "export -p, set, declare -p, ps with the environment, os.environ, process.env, /proc/*/environ, "
    "launchctl getenv, jq env, compgen -e, ${!name}) are not run. Read a single non-secret variable with "
    "`echo \"$NAME\"`."
)
CWD_MESSAGE = (
    "The terminal's working directory is inside Cloudflare's files (the cloudflare-tools package or its "
    "state, a CLI's login), which the terminal and file tools never use; Cloudflare is reached only "
    "through the cloudflare_* tools. Run commands with a workdir outside that directory."
)
UNCHECKED_MESSAGE = "The cloudflare-tools guard could not check this call, so it was not run."

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


def _inbound_peer() -> bool:
    """A peer agent's A2A request never changes the user's Cloudflare account."""
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


def _state_root() -> str:
    """Where cloudflare-tools keeps its state: $XDG_STATE_HOME/cloudflare-tools when that is absolute
    (as the package reads it), else ~/.local/state/cloudflare-tools."""
    xdg = os.environ.get("XDG_STATE_HOME")
    if xdg and os.path.isabs(xdg):
        return os.path.join(xdg, STATE_NAME)
    return os.path.expanduser(os.path.join("~", ".local", "state", STATE_NAME))


def _protected_roots() -> set[tuple[str, ...]]:
    """The directories Cloudflare is reached through, as given and as resolved, as lower-case path
    components; read at each call."""
    home = os.path.expanduser("~")
    roots = {
        _state_root(),
        os.path.join(home, ".hermes", "plugins", STATE_NAME),
        os.path.join(home, ".cloudflared"),
        os.path.join(home, ".wrangler", "config"),
        os.path.join(home, OLD_STATE_NAME),
    }
    grants = os.environ.get(GRANTS_ENV)
    if grants:
        roots.add(os.path.expanduser(grants))
    return {_names(path) for root in roots for path in (os.path.abspath(root), os.path.realpath(root))}


def _has_protected_part(path: str) -> bool:
    """Whether a component of the resolved ``path`` is a protected directory name: a literal one only where
    the path up to and including it exists (a word like ``hermes/cloudflare-tools`` that names a git ref
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
        logger.debug("cloudflare-tools-guard: no tracked terminal cwd: %s", exc)
    return None


def _runs_cli(command: str, args: dict) -> bool:
    """Whether the command runs a Cloudflare CLI or this plugin's own, bar a project's own wrangler."""
    place = project_place.project_dir(args)

    def local(name):
        return name in PROJECT_CLIS and project_place.local_bin(place, name)

    return (shell_commands.runs(command, CLIS, _CLI_TEXT, project=place is not None, local=local,
                                moves=project_place.leading_moves(args))
            or shell_commands.runs(command, PACKAGE_CLIS, _PACKAGE_CLI))


def _prints_environment(command: str) -> bool:
    """Whether the command runs one of the forms that print the process environment."""
    return any(shell_commands.runs(command, names, pattern) and pattern.search(command)
               for names, pattern in _ENV_DUMPS)


def bypass(tool: str, args, cwd: str | None = None) -> str | None:
    """A block message when a terminal or file call would go around the tools, else None. ``cwd`` is
    the directory a terminal call runs in, against which its relative words resolve.
    A pattern match on the call's text and on the real paths it names, not a sandbox."""
    args = args if isinstance(args, dict) else {}
    if tool != "terminal" and tool not in FILE_TOOLS:
        return None
    texts = list(_strings(args))
    paths = []
    patterns = (_PATHS, OLD_STORE)
    environment = (_ENVIRON_FILE,)
    if tool == "terminal":
        patterns += (_TERMINAL, _VARIABLES, OLD_TERMINAL)
        environment += (_INDIRECT,)
        command = args.get("command")
        if isinstance(command, str):
            if _prints_environment(command):
                return ENV_MESSAGE
            if _runs_cli(command, args):
                return BYPASS_MESSAGE
            paths = _word_paths(command, cwd)
    else:
        cwd = None
    if any(pattern.search(text) for pattern in environment for text in texts):
        return ENV_MESSAGE
    if any(pattern.search(text) for pattern in patterns for text in texts):
        return BYPASS_MESSAGE
    roots = _protected_roots()
    if cwd and _names_protected(cwd, roots):
        return CWD_MESSAGE
    if any(_names_protected(path, roots, here) for path, here in [*((text, cwd) for text in texts), *paths]):
        return BYPASS_MESSAGE
    return None


def _block(message: str) -> dict[str, str]:
    return {"action": "block", "message": message}


def _check(tool: str, args, task_id: str = "", session_id: str = ""):
    if tool.startswith(PREFIX):
        if not _is_write(tool):
            return None
        if _inbound_peer():
            return _block(f"{tool} is not available to inbound A2A requests")
        reason = human_gate.no_human()
        if reason:
            return _block(human_gate.refusal(tool, reason))
        return None
    if tool == "terminal" or tool in FILE_TOOLS:
        cwd = _terminal_cwd(args, task_id, session_id) if tool == "terminal" and isinstance(args, dict) else None
        message = bypass(tool, args, cwd=cwd)
        if message:
            return _block(message)
    return None


def gate(tool_name="", args=None, **kwargs):
    """pre_tool_call: a block for a cloudflare_* write nobody can answer, for a write of an inbound A2A
    request, and for ways around the tools. Where the check itself fails, a write, the terminal and the
    file tools are blocked and every other call goes on."""
    tool = tool_name if isinstance(tool_name, str) else ""
    try:
        return _check(tool, args, str(kwargs.get("task_id") or ""), str(kwargs.get("session_id") or ""))
    except Exception as exc:  # noqa: BLE001 - fail closed for what the guard protects
        logger.warning("cloudflare-tools-guard could not check %s: %s", tool, exc)
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
