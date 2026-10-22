"""github-access: block the Assistant's ways around the tools.

A terminal ``gh`` command runs only when it is one of the reads in ``READS`` (``gh issue view``,
``gh pr checks``, ``gh run view``, ``gh search``, …); every other one is blocked, a subcommand gh
gains later or an extension included, with the message that fits it. A change ``github_change``
offers (``TOOL_WRITES``: issues, boards, labels, repositories, pull requests, releases, Actions
runs), the API reached directly, the login's token printed (which ``curl`` could then use) or an
alias or extension defined (which could hide any of those) would skip the card and the tiers; a
write the Assistant never makes at all (``NEVER``: secrets and variables, gists, deleting, renaming
or forking a repository, deploy, SSH and GPG keys, deleting releases, runs and caches, reviewing a
pull request) says so; anything else is not the Assistant's to run. Commands are found inside
``sh -c '…'`` and ``eval '…'`` too, and the changes also when they are only mentioned. File and
terminal calls that touch the plugin's state directory are blocked too (mandate.py keeps its
records there).
"""

from __future__ import annotations

import os
import re
import shlex

ISSUE_WRITES = {"create", "new", "edit", "comment", "close", "reopen", "delete", "transfer", "pin", "unpin",
                "lock", "unlock", "develop"}
PROJECT_READS = {"list", "ls", "view", "item-list", "field-list"}
LABEL_WRITES = {"create", "edit", "delete", "clone"}
REPO_WRITES = {"create", "new", "edit", "archive", "unarchive"}
PR_WRITES = {"create", "new", "edit", "comment", "close", "reopen", "ready", "merge"}
# gh group -> the subcommands github_change makes on a card (a gh project command is a write unless
# it is one of PROJECT_READS).
TOOL_WRITES = {"issue": ISSUE_WRITES, "label": LABEL_WRITES, "repo": REPO_WRITES, "pr": PR_WRITES,
               "release": {"create", "new", "edit"}, "run": {"rerun"}, "workflow": {"run"}}
# gh group -> the subcommands no tool offers and the Assistant never runs: they hold or reveal
# credentials, publish outside a repository, or destroy or move what others rely on.
NEVER = {
    "secret": {"set", "delete", "remove"},
    "variable": {"set", "delete", "remove"},
    "gist": {"create", "new", "edit", "delete", "rename"},
    "repo": {"delete", "rename", "fork", "deploy-key", "autolink", "sync"},
    "ssh-key": {"add", "delete"},
    "gpg-key": {"add", "delete"},
    "release": {"delete", "delete-asset", "upload"},
    "run": {"delete", "cancel"},
    "workflow": {"enable", "disable"},
    "cache": {"delete"},
    # A review is the user's own judgement under their name; the rest no tool offers.
    "pr": {"review", "revert", "lock", "unlock", "update-branch"},
}
ANY = frozenset({"*"})  # every subcommand of the group reads
# gh group -> the subcommands that only read (or act on a local checkout); a bare group prints its
# help. A group or subcommand missing here is blocked.
READS = {
    "issue": {"list", "ls", "view", "status"},
    "pr": {"list", "ls", "view", "status", "checks", "diff", "checkout", "co"},
    "repo": {"view", "list", "ls", "clone", "set-default", "license", "gitignore"},
    "project": PROJECT_READS,
    "label": {"list", "ls"},
    "release": {"list", "ls", "view", "download", "verify", "verify-asset"},
    "run": {"list", "ls", "view", "watch", "download"},
    "workflow": {"list", "ls", "view"},
    "cache": {"list", "ls"},
    "secret": {"list", "ls"},
    "variable": {"list", "ls", "get"},
    "gist": {"list", "ls", "view", "clone"},
    "auth": {"status"},
    "config": {"get", "list", "ls"},
    "org": {"list", "ls"},
    "ruleset": {"list", "ls", "view", "check"},
    "ssh-key": {"list", "ls"},
    "gpg-key": {"list", "ls"},
    "attestation": {"verify", "download", "trusted-root"},
    **{group: ANY for group in ("search", "status", "browse", "help", "version", "completion")},
}
ALIAS_GROUPS = {"alias", "extension", "extensions", "ext"}
WRAPPERS = {"command", "exec", "env", "nohup", "time", "sudo", "doas", "xargs", "nice", "timeout", "stdbuf",
            "caffeinate", "find", "parallel", "watch"}
SHELLS = {"sh", "bash", "zsh", "dash", "ksh", "fish"}
FIND_EXEC = {"-exec", "-execdir", "-ok", "-okdir"}
FILE_TOOLS = {"read_file", "write_file", "patch", "search_files"}
STATE_NAME = "github-access"
# The state directory is <HERMES_HOME>/github-access/; the plugin's own source
# (plugins/github-access/) and names that merely contain the words stay readable. Matched without
# regard to case (macOS paths are case-insensitive), on the text and on the path it resolves to.
_STATE = re.compile(r"(?<!plugins/)(?<![\w.-])github-access(?:/|\s|['\"]|$)", re.IGNORECASE)
_SEPARATOR = re.compile(r"[;&|\n()`]|\$\(")

MESSAGE = ("Blocked: GitHub changes (issues, boards, labels, repositories, pull requests, releases, Actions "
           "runs) go only through github_change, where the user approves on a card; read them with github_issue, "
           "github_board, github_repo and github_pr. Nothing was run.")
NEVER_MESSAGE = ("Blocked: the Assistant never does this on GitHub (secrets and variables, gists, deleting, "
                 "renaming or forking a repository, deploy, SSH or GPG keys, deleting releases, runs or caches, "
                 "uploading release assets, cancelling runs, enabling or disabling workflows, reviewing, reverting, "
                 "locking or updating a pull request). Tell the user what to do, and they do it themselves. Nothing "
                 "was run.")
UNKNOWN_MESSAGE = ("Blocked: the Assistant runs only gh's reads from the terminal (view, list, status, checks, "
                   "diff, search, …), and this is not one. Read GitHub with github_issue, github_board, github_repo "
                   "and github_pr, change it through github_change; anything else is the user's to do. Nothing was "
                   "run.")

_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_NUMBER = re.compile(r"^\d+(?:\.\d+)?[smhd]?$")  # a wrapper's duration or count (timeout 10)
_SHELL_C = re.compile(r"^-[A-Za-z]*c[A-Za-z]*$")
_SHOW_TOKEN = re.compile(r"^(?:--show-token(?:=.*)?|-[A-Za-z]*t[A-Za-z]*)$")


def _segments(command: str):
    """Each simple command in a shell line, as tokens (best effort; quotes kept together, and stray
    quotes dropped from a part a separator cut through)."""
    for part in _SEPARATOR.split(command):
        try:
            tokens = shlex.split(part, posix=True)
        except ValueError:
            tokens = [t.strip("'\"") for t in part.split()]
        if tokens:
            yield tokens


def _name(token: str) -> str:
    return token.rsplit("/", 1)[-1]


def _script(rest: list[str]) -> str | None:
    """The script a shell runs from a string: after ``-c`` (past its options, ``-o name`` and
    ``--``), else a here-string ``<<<`` it reads as its input. A script file or a pipe into the
    shell is not seen."""
    at = next((j for j, t in enumerate(rest[1:], 1) if _SHELL_C.match(t)), None)
    if at is not None:
        j = at + 1
        while j < len(rest) and rest[j][:1] in ("-", "+"):
            j += 2 if rest[j] in ("-o", "+o", "-O", "+O") else 1
        return rest[j] if j < len(rest) else None
    if "<<<" in rest[:-1]:
        return rest[rest.index("<<<") + 1]
    return None


DEPTH = 8
BUDGET = 400
TOO_DEEP = ["\0too-deep"]  # read as an unknown command: a line nested past the limits is blocked


def _simple(tokens: list[str], depth: int, budget: list, wrapped: bool = False):
    """The arguments of each ``gh`` one simple command may run. An environment assignment's value
    is read as a command too (a pager or an editor gh starts). A wrapper's own flags may or may not
    take a value, so every token that may be the command it runs is followed (``sudo -u x gh``,
    ``xargs -I {} gh``, ``timeout -s KILL 10 gh``); for ``find``, what follows each ``-exec``.
    Nesting or readings past the limits fail closed."""
    budget[0] -= 1
    if depth > DEPTH or budget[0] < 0:
        yield TOO_DEEP
        return
    i = 0
    while i < len(tokens) and (_ASSIGN.match(tokens[i]) or (wrapped and _NUMBER.match(tokens[i]))):
        if _ASSIGN.match(tokens[i]):
            yield from _invocations(tokens[i].split("=", 1)[1], depth + 1, budget)
        i += 1
    rest = tokens[i:]
    name = _name(rest[0]) if rest else ""
    if name == "gh":
        yield rest[1:]
    elif name in SHELLS:
        script = _script(rest)
        if script is not None:
            yield from _invocations(script, depth + 1, budget)
    elif name == "eval":
        yield from _invocations(" ".join(rest[1:]), depth + 1, budget)
    elif name == "find":
        for j, token in enumerate(rest):
            if token in FIND_EXEC:
                yield from _simple(rest[j + 1:], depth + 1, budget)
    elif name in WRAPPERS:
        for j in _words(rest[1:]):
            yield from _simple(rest[j + 1:], depth + 1, budget, wrapped=True)


def _invocations(command: str, depth: int = 0, budget: list | None = None):
    """The arguments of each ``gh`` a shell line runs, inside ``sh -c '…'`` and ``eval '…'`` too."""
    budget = [BUDGET] if budget is None else budget
    for tokens in _segments(command):
        yield from _simple(tokens, depth, budget)


def _words(rest: list[str]) -> list[int]:
    """Where gh may find its next (sub)command in ``rest``. A flag before it may or may not take the
    next token as its value (gh strips ``--flag value`` it does not know as a switch), so after a
    flag without ``=`` both that token and the one after it count. ``-R`` / ``--repo`` always take
    one."""
    found, i, valued = [], 0, False
    while i < len(rest):
        if rest[i] in ("-R", "--repo"):
            i, valued = i + 2, False
            continue
        if rest[i].startswith("-"):
            valued = "=" not in rest[i]
        else:
            found.append(i)
            if not valued:
                break
            valued = False
        i += 1
    return found


def _commands(args: list[str]):
    """Every (group, verb) gh may read from its arguments."""
    for g in _words(args):
        rest = args[g + 1:]
        verbs = [rest[v] for v in _words(rest)] or [""]
        for verb in verbs:
            yield args[g], verb


# The same rule over the whole text, quotes and all, so a write wrapped in `bash -c "…"`, `eval '…'`
# or split by a backslash-newline is caught too. A guard of text, not a sandbox: a script file's
# contents are never seen, which is why the token and the aliases are closed as well.
# Flags may stand before the group and between the group and its verb (`gh -R a/b secret set`,
# `gh secret --org o set`), each with or without a value after it.
_FLAGS = r"(?:-\S+\s+(?:[^-\s]\S*\s+)?)*"
_GH = r"(?:(?<=/)|(?<![\w./-]))gh\s+" + _FLAGS


def _verbs(verbs) -> str:
    return "|".join(re.escape(v) for v in sorted(verbs, key=len, reverse=True))


_ANYWHERE = re.compile(
    _GH + r"(?:api\b"
    + "".join(rf"|{re.escape(group)}\s+{_FLAGS}(?:{_verbs(verbs)})(?![\w-])" for group, verbs in TOOL_WRITES.items())
    + rf"|project\s+(?!(?:{_verbs(PROJECT_READS)})\b)[\w-]"
    rf"|auth\s+{_FLAGS}token\b|auth\s+{_FLAGS}status\b[^;&|\n]*(?:--show-token|\s-[A-Za-z]*t[A-Za-z]*\b)"
    rf"|alias\s+{_FLAGS}(?:set|import)\b|ext(?:ension|ensions)?\b)")
_NEVER_ANYWHERE = re.compile(_GH + "(?:" + "|".join(
    rf"{re.escape(group)}\s+{_FLAGS}(?:{_verbs(verbs)})(?![\w-])" for group, verbs in NEVER.items()) + ")")


def _verdict(group: str, verb: str) -> str | None:
    """The message for one reading of a gh command, or None for a read."""
    if verb in NEVER.get(group, ()):
        return NEVER_MESSAGE
    if group == "api" or group in ALIAS_GROUPS or (group == "auth" and verb == "token") or \
            verb in TOOL_WRITES.get(group, ()):
        return MESSAGE
    allowed = READS.get(group)
    if allowed is not None and (allowed is ANY or verb == "" or verb in allowed):
        return None
    return MESSAGE if group == "project" else UNKNOWN_MESSAGE


def blocked(command: str) -> str | None:
    """The message for a terminal command that goes around the tools, or None. A gh command passes
    only when every way gh may read its arguments is a read."""
    command = command.replace("\\\n", " ")
    if _NEVER_ANYWHERE.search(command):
        return NEVER_MESSAGE
    if _ANYWHERE.search(command):
        return MESSAGE
    found = set()
    for args in _invocations(command):
        for group, verb in _commands(args):
            found.add(_verdict(group, verb))
            if group == "auth" and any(_SHOW_TOKEN.match(a) for a in args):
                found.add(MESSAGE)  # `auth status -t` prints the token
    return next((m for m in (NEVER_MESSAGE, MESSAGE, UNKNOWN_MESSAGE) if m in found), None)


def writes(command: str) -> bool:
    return blocked(command) is not None


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def _resolved(text: str) -> str:
    """The real path a path-like argument names (``~``, ``..`` and symlinks resolved), else ''."""
    if not text or "\n" in text or len(text) > 4096:
        return ""
    try:
        return os.path.realpath(os.path.expanduser(text.strip()))
    except (OSError, ValueError):
        return ""


def touches_state(value) -> bool:
    for text in _strings(value):
        if _STATE.search(text):
            return True
        real = _resolved(text)
        if real and _STATE.search(real + "/"):
            return True
    return False


def bypass(tool: str, args) -> str | None:
    args = args if isinstance(args, dict) else {}
    if tool == "terminal":
        command = args.get("command")
        message = blocked(command) if isinstance(command, str) else None
        if message:
            return message
        if touches_state(args):
            return MESSAGE
    elif tool in FILE_TOOLS and touches_state(args):
        return MESSAGE
    return None
