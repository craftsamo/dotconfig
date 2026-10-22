"""github-access: block the Assistant's ways around the tools.

A terminal ``gh`` command that makes a change ``github_change`` offers (``TOOL_WRITES``: issues,
boards, labels, repositories, pull requests, releases, Actions runs), reaches the API directly, prints the login's token (which ``curl``
could then use) or defines an alias or extension (which could hide any of those) would skip the
card and the tiers, so the hook blocks it, also when it is wrapped in quotes. So is a write the
Assistant never makes at all (``NEVER``: secrets and variables, gists, deleting, renaming or
forking a repository, deploy, SSH and GPG keys, deleting releases, runs and caches, reviewing a
pull request), with a message that says so. Reading through ``gh`` (``gh issue view``, ``gh
project list``, ``gh repo view``, ``gh pr view``, ``gh pr checks``) stays open. File and terminal calls that touch the plugin's state directory are
blocked too (mandate.py keeps its records there).
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
        return tokens[i + 1:]
    return None


def _words(rest: list[str]) -> list[int]:
    """Where gh may find its next (sub)command in ``rest``. A flag before it may or may not take the
    next token as its value (gh strips ``--flag value`` it does not know as a switch), so after a
    flag without ``=`` both that token and the one after it count."""
    found, i, valued = [], 0, False
    while i < len(rest):
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
    rf"|auth\s+{_FLAGS}token\b|auth\s+status\b[^;&|\n]*--show-token"
    rf"|alias\s+{_FLAGS}(?:set|import)\b|ext(?:ension|ensions)?\b)")
_NEVER_ANYWHERE = re.compile(_GH + "(?:" + "|".join(
    rf"{re.escape(group)}\s+{_FLAGS}(?:{_verbs(verbs)})(?![\w-])" for group, verbs in NEVER.items()) + ")")


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
        for group, verb in _commands(args):
            if verb in NEVER.get(group, ()):
                return NEVER_MESSAGE
            if group == "api" or verb in TOOL_WRITES.get(group, ()):
                return MESSAGE
            if group == "project" and verb not in PROJECT_READS:
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
