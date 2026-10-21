"""github-access: block the Assistant's ways around the tools.

A terminal ``gh`` command that writes Issues, boards or labels, reaches the API directly, prints
the login's token (which ``curl`` could then use) or defines an alias or extension (which could
hide any of those) would skip the card and the tiers, so the hook blocks it, also when it is
wrapped in quotes. So is a write the Assistant never makes at all (``NEVER``: secrets and
variables, gists, deleting, renaming or forking a repository, deploy, SSH and GPG keys, deleting
releases, runs and caches), with a message that says so. Reading through ``gh`` (``gh issue
view``, ``gh project list``, ``gh pr``, ``gh repo create`` the pipeline uses) stays open. File and
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
# gh group -> the subcommands no tool offers and the Assistant never runs: they hold or reveal
# credentials, publish outside a repository, or destroy or move what others rely on.
NEVER = {
    "secret": {"set", "delete", "remove"},
    "variable": {"set", "delete", "remove"},
    "gist": {"create", "new", "edit", "delete", "rename"},
    "repo": {"delete", "rename", "fork", "deploy-key", "autolink", "sync"},
    "ssh-key": {"add", "delete"},
    "gpg-key": {"add", "delete"},
    "release": {"delete", "delete-asset"},
    "run": {"delete"},
    "cache": {"delete"},
}
FILE_TOOLS = {"read_file", "write_file", "patch", "search_files"}
STATE_NAME = "github-access"
# The state directory is <HERMES_HOME>/github-access/; the plugin's own source
# (plugins/github-access/) and names that merely contain the words stay readable. Matched without
# regard to case (macOS paths are case-insensitive), on the text and on the path it resolves to.
_STATE = re.compile(r"(?<!plugins/)(?<![\w.-])github-access(?:/|\s|['\"]|$)", re.IGNORECASE)
_SEPARATOR = re.compile(r"[;&|\n()`]|\$\(")

MESSAGE = ("Blocked: GitHub Issues, boards and labels change only through github_change, where the user "
           "approves on a card; read them with github_issue and github_board. Nothing was run.")
NEVER_MESSAGE = ("Blocked: the Assistant never does this on GitHub (secrets and variables, gists, deleting, "
                 "renaming or forking a repository, deploy, SSH or GPG keys, deleting releases, runs or caches). "
                 "Tell the user what to do, and they do it themselves. Nothing was run.")


def _segments(command: str):
    """Each simple command in a shell line, as tokens (best effort; quotes kept together)."""
    for part in _SEPARATOR.split(command):
        try:
            tokens = shlex.split(part, posix=True)
        except ValueError:
            tokens = part.split()
        if tokens:
            yield tokens


def _gh_args(tokens: list[str]):
    """The arguments after ``gh`` in a simple command, past env assignments and wrappers."""
    i = 0
    while i < len(tokens) and (re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tokens[i]) or
                               tokens[i] in ("command", "exec", "env", "nohup", "time", "sudo", "xargs")):
        i += 1
    if i < len(tokens) and tokens[i].rsplit("/", 1)[-1] == "gh":
        args = tokens[i + 1:]
        while args and args[0].startswith("-"):  # global flags before the command
            args = args[2:] if args[0] in ("-R", "--repo") else args[1:]
        return args
    return None


# The same rule over the whole text, quotes and all, so a write wrapped in `bash -c "…"`, `eval '…'`
# or split by a backslash-newline is caught too. A guard of text, not a sandbox: a script file's
# contents are never seen, which is why the token and the aliases are closed as well.
_GH = r"(?:(?<=/)|(?<![\w./-]))gh\s+(?:(?:-R|--repo)\s+\S+\s+|-\S+\s+)*"


def _verbs(verbs) -> str:
    return "|".join(re.escape(v) for v in sorted(verbs, key=len, reverse=True))


_ANYWHERE = re.compile(
    _GH + r"(?:api\b"
    rf"|issue\s+(?:{_verbs(ISSUE_WRITES)})\b"
    rf"|project\s+(?!(?:{_verbs(PROJECT_READS)})\b)[\w-]"
    rf"|label\s+(?:{_verbs(LABEL_WRITES)})\b"
    r"|auth\s+token\b|auth\s+status\b[^;&|\n]*--show-token"
    r"|alias\s+(?:set|import)\b|ext(?:ension|ensions)?\b)")
_NEVER_ANYWHERE = re.compile(_GH + "(?:" + "|".join(
    rf"{re.escape(group)}\s+(?:{_verbs(verbs)})(?![\w-])" for group, verbs in NEVER.items()) + ")")


def blocked(command: str) -> str | None:
    """The message for a terminal command that goes around the tools, or None."""
    command = command.replace("\\\n", " ")
    if _NEVER_ANYWHERE.search(command):
        return NEVER_MESSAGE
    if _ANYWHERE.search(command):
        return MESSAGE
    for tokens in _segments(command):
        args = _gh_args(tokens)
        if not args:
            continue
        group, verb = args[0], next((a for a in args[1:] if not a.startswith("-")), "")
        if verb in NEVER.get(group, ()):
            return NEVER_MESSAGE
        if group == "api":
            return MESSAGE
        if group == "issue" and verb in ISSUE_WRITES:
            return MESSAGE
        if group == "project" and verb not in PROJECT_READS:
            return MESSAGE
        if group == "label" and verb in LABEL_WRITES:
            return MESSAGE
        if group in ("alias", "extension", "extensions", "ext") or (group == "auth" and verb == "token"):
            return MESSAGE
    return None


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
