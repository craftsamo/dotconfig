"""git-tools-guard: block the terminal ``git`` commands that go around the ``git_*`` tools.

A terminal ``git`` command runs only when it reads, fetches or clones: the commands in
``READ_COMMANDS`` (``status``, ``log``, ``diff``, ``show``, …), ``fetch``, ``clone``, ``pull --ff-only``,
and the list-only forms of ``branch``, ``tag``, ``remote``, ``stash``, ``worktree``, ``config``,
``notes`` and ``submodule``. Every other one is blocked with the message that fits it: a command that
changes a repository (``MESSAGE``: the ``git_*`` tools do it on a card, a target repository's commits
and pushes are OpenCode's, a finished worktree goes through ``git_worktree_remove``), one that sets
configuration or names a program for git to run (``UNSAFE_MESSAGE``: ``-c``, ``--config-env``, an
unknown global option, a ``GIT_CONFIG*``, ``GIT_SSH*``, ``GIT_EXEC_PATH``, ``GIT_ASKPASS``,
``GIT_EXTERNAL_DIFF``, ``GIT_EDITOR`` or ``GIT_SEQUENCE_EDITOR`` assignment, ``--upload-pack``,
``--ext-diff``, ``--textconv``, and ``--output``, which writes a file), and anything else (``UNKNOWN_MESSAGE``:
a subcommand git gains later, a user alias, ``bisect``, ``fsck``).

Commands are found inside ``sh -c '…'``, ``eval '…'``, wrappers (``env``, ``sudo``, ``xargs``,
``timeout``, ``find -exec``, …) and environment assignments' values too; a ``git-<command>`` binary
called by its own name reads as ``git <command>``, ``hub`` reads as ``git``, and ``lazygit`` and
``gitui`` are blocked outright. The package's own ``git-tools`` and ``git-tools-cli`` are not git
commands here: the guard's entry-point check judges them. The changes that have no read form are also
caught when they are only mentioned (``echo git commit``), conservatively.

A pattern match on the text, not a sandbox: a script file's contents are never seen, and the
repository's own configuration (an ``fsmonitor`` or ``diff.external`` setting, a hook a checkout or
pull fires) is code git runs for the read it is asked.

Loaded by path from this plugin's ``__init__.py``; it is not a plugin and has no manifest.
"""

from __future__ import annotations

import re
import shlex
from typing import NamedTuple

FRONTEND_MARK = "\0frontend"  # the "subcommand" of a git front-end that writes (read as a write)
FRONTEND = [FRONTEND_MARK]
TOO_DEEP = ["\0too-deep"]  # read as an unknown command: a line nested past the limits is blocked
PACKAGE_BINS = frozenset({"git-tools", "git-tools-cli"})  # the package's entry points, not `git-<command>`
FRONTENDS = frozenset({"lazygit", "gitui"})
GITS = frozenset({"git", "hub"})

READ_COMMANDS = frozenset({
    "status", "log", "show", "diff", "blame", "annotate", "shortlog", "describe", "rev-parse", "rev-list",
    "ls-files", "ls-tree", "ls-remote", "cat-file", "merge-base", "for-each-ref", "show-ref", "grep", "reflog",
    "version", "help", "count-objects", "check-ignore", "name-rev", "whatchanged", "range-diff", "cherry", "var",
})
# Commands that always change a repository: the message for them, and the mention check.
WRITES = frozenset({
    "add", "am", "apply", "bisect", "checkout", "cherry-pick", "clean", "commit", "filter-branch", "gc", "init",
    "merge", "mv", "prune", "push", "rebase", "reset", "restore", "revert", "rm", "switch", "symbolic-ref",
    "update-index", "update-ref", FRONTEND_MARK,
})
# group -> its subcommands that change a repository (the mention check; the list-only forms are judged
# from the arguments).
GROUP_WRITES = {
    "stash": {"push", "pop", "apply", "drop", "clear", "save", "branch", "create", "store"},
    "remote": {"add", "remove", "rm", "rename", "set-url", "set-head", "set-branches", "prune", "update"},
    "worktree": {"add", "remove", "move", "prune", "lock", "unlock", "repair"},
    "submodule": {"add", "init", "update", "sync", "deinit", "foreach", "set-url", "set-branch", "absorbgitdirs"},
    "notes": {"add", "append", "copy", "edit", "merge", "remove", "prune"},
    "reflog": {"expire", "delete"},
}
REFLOG_WRITES = GROUP_WRITES["reflog"]

# Options before the subcommand: git's global options that only point it somewhere or switch paging
# off; any other (`-c`, `--config-env`, `--exec-path=`, `--upload-pack`, an unknown one) can set
# configuration, an alias or a hook.
GLOBAL_FLAGS = frozenset({"--no-pager", "-P", "--paginate", "-p", "--literal-pathspecs", "--no-optional-locks",
                          "--version", "--help"})
GLOBAL_VALUED = frozenset({"-C", "--git-dir", "--work-tree"})

# Long options that run a program or write a file wherever they appear, as name -> the fewest characters
# of it git accepts as an abbreviation of it (`--output` is also `--outp=x`).
PROGRAM_OPTIONS = {"--output": 3, "--ext-diff": 5, "--textconv": 7, "--upload-pack": 3, "--receive-pack": 3,
                   "--exec": 3, "--open-files-in-pager": 3}
FETCH_OPTIONS = {"--update-head-ok": 3}  # fetching into the checked-out branch
CLONE_OPTIONS = {"--config": 3, "--template": 3}  # settings and hooks copied into the new repository
PULL_OPTIONS = {"--rebase": 3, "--ff": 4, "--no-ff": 7, "--autostash": 11, "--squash": 8}  # more than a fast-forward

CONFIG_MODES = frozenset({"--get", "--get-all", "--get-regexp", "--list", "-l"})
CONFIG_FLAGS = CONFIG_MODES | {"--show-origin", "--show-scope", "--name-only", "--global", "--local", "--system",
                               "--worktree", "--null", "-z", "--includes", "--no-includes", "--all", "--regexp",
                               "--show-names"}
CONFIG_SUBCOMMANDS = frozenset({"get", "list"})

WRAPPERS = {"command", "exec", "env", "nohup", "time", "sudo", "doas", "xargs", "nice", "timeout", "gtimeout",
            "stdbuf", "caffeinate", "find", "parallel", "watch", "builtin", "chronic", "unbuffer", "arch", "setsid",
            "script", "flock"}
SHELLS = {"sh", "bash", "zsh", "dash", "ksh", "fish"}
KEYWORDS = {"if", "then", "else", "elif", "do", "while", "until", "!", "{", "}"}
FIND_EXEC = {"-exec", "-execdir", "-ok", "-okdir"}
DEPTH = 8
BUDGET = 400
_SEPARATOR = re.compile(r"[;&|\n()`]|\$\(")

ELSEWHERE = ("Commits and pushes on a target repository are OpenCode's, commissioned through the engineering "
             "pipeline; a finished worktree is removed with git_worktree_remove. Nothing was run.")
MESSAGE = ("Blocked: git changes (staging, commits, amends, rebases, branches, stashes, worktrees, pushes) go only "
           "through the git_* tools, where the user approves each on a card; read with git_repo_read, "
           "git_commit_read, git_rebase_read, git_worktree_read and git_push_read, or with git's own reads in the "
           "terminal. " + ELSEWHERE)
UNSAFE_MESSAGE = ("Blocked: this git command sets configuration or names a program or a file for git to run or "
                  "write (-c, --config-env, an unknown global option, a GIT_CONFIG*, GIT_SSH*, GIT_EXEC_PATH, "
                  "GIT_ASKPASS, GIT_EXTERNAL_DIFF or GIT_EDITOR assignment, --upload-pack, --ext-diff, "
                  "--textconv, --output), which the terminal never does; change git through the git_* tools. "
                  + ELSEWHERE)
UNKNOWN_MESSAGE = ("Blocked: the terminal runs only git's reads (status, log, show, diff, …), fetch, clone and "
                   "pull --ff-only, and this is not one. Read with git_repo_read, git_commit_read, "
                   "git_rebase_read, git_worktree_read and git_push_read, change git through the git_* tools. "
                   + ELSEWHERE)

_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_NUMBER = re.compile(r"^\d+(?:\.\d+)?[smhd]?$")  # a wrapper's duration or count (timeout 10)
_SHELL_C = re.compile(r"^-[A-Za-z]*c[A-Za-z]*$")
# An assignment of a variable that makes git run a program or read other settings, anywhere on a line
# that runs git (`export GIT_SSH_COMMAND=…; git fetch` too).
_UNSAFE_ENV = re.compile(r"(?<!\w)(?:GIT_CONFIG\w*|GIT_SSH\w*|GIT_EXEC_PATH|GIT_ASKPASS|SSH_ASKPASS|GIT_EXTERNAL_DIFF"
                         r"|GIT_EDITOR|GIT_SEQUENCE_EDITOR|GIT_PROXY_COMMAND)\+?=")


class _Listing(NamedTuple):
    """What makes a ``branch`` or ``tag`` call list: its short-option cluster, the letters in it and the
    long options that put it in list mode, and the long options that take a value."""

    cluster: re.Pattern
    letters: str
    longs: frozenset
    listing: frozenset
    valued: frozenset


_FILTERS = frozenset({"--contains", "--no-contains", "--merged", "--no-merged", "--points-at"})
_DISPLAY = frozenset({"--color", "--no-color", "--column", "--no-column", "--ignore-case", "--sort", "--format"})
_LIST_LONGS = frozenset({"--list"}) | _FILTERS
_LIST_VALUED = frozenset({"--sort", "--format", "--points-at"})
BRANCH = _Listing(re.compile(r"-[arvli]+"), "l",
                  _LIST_LONGS | _DISPLAY | {"--all", "--remotes", "--verbose", "--show-current", "--abbrev",
                                            "--no-abbrev"},
                  _LIST_LONGS | {"--show-current"}, _LIST_VALUED)
TAG = _Listing(re.compile(r"-[lin]+\d*"), "ln", _LIST_LONGS | _DISPLAY, _LIST_LONGS, _LIST_VALUED)


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
    """The program a command word names: its last path part, in lower case (macOS paths ignore case)."""
    return token.rsplit("/", 1)[-1].lower()


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


def _candidates(rest: list[str]) -> list[int]:
    """Where a wrapper may find the command it runs in ``rest``. A flag before it may or may not take
    the next token as its value, so after a flag without ``=`` both that token and the one after it
    count."""
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


def _simple(tokens: list[str], depth: int, budget: list, wrapped: bool = False):
    """The arguments of each ``git`` one simple command may run. An environment assignment's value
    is read as a command too (a pager or an editor git starts). A wrapper's own flags may or may not
    take a value, so every token that may be the command it runs is followed (``sudo -u x git``,
    ``xargs -I {} git``, ``timeout -s KILL 10 git``); for ``find``, what follows each ``-exec``.
    Nesting or readings past the limits fail closed."""
    budget[0] -= 1
    if depth > DEPTH or budget[0] < 0:
        yield TOO_DEEP
        return
    i = 0
    while i < len(tokens) and (_ASSIGN.match(tokens[i]) or tokens[i] in KEYWORDS
                               or (wrapped and _NUMBER.match(tokens[i]))):
        if _ASSIGN.match(tokens[i]):
            yield from _invocations(tokens[i].split("=", 1)[1], depth + 1, budget)
        i += 1
    rest = tokens[i:]
    name = _name(rest[0]) if rest else ""
    if name in GITS:
        yield rest[1:]
    elif name in FRONTENDS:
        yield FRONTEND
    elif name.startswith("git-") and name not in PACKAGE_BINS:
        yield [name[len("git-"):], *rest[1:]]
    elif wrapped and rest and re.search(r"\s", rest[0]):
        yield from _invocations(rest[0], depth + 1, budget)  # a command line given as one word: watch 'git …'
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
        for j in _candidates(rest[1:]):
            yield from _simple(rest[j + 1:], depth + 1, budget, wrapped=True)


def _invocations(command: str, depth: int = 0, budget: list | None = None):
    """The arguments of each ``git`` a shell line runs, inside ``sh -c '…'`` and ``eval '…'`` too."""
    budget = [BUDGET] if budget is None else budget
    for tokens in _segments(command):
        yield from _simple(tokens, depth, budget)


def _options(rest: list[str]):
    """The tokens of ``rest`` git reads as options or their values: those before a ``--``."""
    for token in rest:
        if token == "--":
            return
        yield token


def _has_option(rest: list[str], longs: dict[str, int], shorts: str = "", valued: str = "") -> bool:
    """Whether ``rest`` holds one of the ``longs`` (name -> the fewest characters git accepts of it, so
    an abbreviation counts) or a short option in ``shorts``, also inside a cluster (``-qr``) up to the
    first letter in ``valued``, which takes the rest of the token as its value."""
    for token in _options(rest):
        if token.startswith("--"):
            given = token.partition("=")[0]
            if any(len(given) >= least and name.startswith(given) for name, least in longs.items()):
                return True
        elif token.startswith("-") and shorts:
            for letter in token[1:]:
                if letter in shorts:
                    return True
                if letter in valued:
                    break
    return False


def _first_word(rest: list[str]) -> str:
    return next((t for t in rest if not t.startswith("-")), "")


def _list_only(rest: list[str], form: _Listing) -> bool:
    """Whether a ``branch`` or ``tag`` call only lists: every option is one of ``form``'s, and an
    operand (a pattern, a commit) is there only with an option that puts the command in list mode."""
    listing = positional = ended = pending = False
    for token in rest:
        if ended or not token.startswith("-"):
            if pending:
                pending = False
            else:
                positional = True
            continue
        pending = False
        if token == "--":
            ended = True
            continue
        name = token.partition("=")[0]
        if token.startswith("--"):
            if name not in form.longs:
                return False
            listing = listing or name in form.listing
            pending = name in form.valued and "=" not in token
        elif form.cluster.fullmatch(token):
            listing = listing or any(letter in form.letters for letter in token[1:])
        else:
            return False
    return listing or not positional


def _config_reads(rest: list[str]) -> bool:
    """Whether a ``config`` call only reads: ``config get|list …``, or a read mode (``--get``,
    ``--list``, …) with output and scope options only. Every other option, and the bare ``config
    key value`` form, can set."""
    modern = rest[:1] and rest[0] in CONFIG_SUBCOMMANDS
    flags = [t.partition("=")[0] for t in rest if t.startswith("-")]
    return all(f in CONFIG_FLAGS for f in flags) and bool(modern or any(f in CONFIG_MODES for f in flags))


def _remote(rest: list[str]) -> str | None:
    rest = list(rest)
    while rest and rest[0] in ("-v", "--verbose"):
        rest.pop(0)
    return None if not rest or rest[0] in ("show", "get-url") else MESSAGE


def _fetch(rest: list[str]) -> str | None:
    return UNSAFE_MESSAGE if _has_option(rest, FETCH_OPTIONS, "u", "jo") else None


def _clone(rest: list[str]) -> str | None:
    return UNSAFE_MESSAGE if _has_option(rest, CLONE_OPTIONS, "cu", "boj") else None


def _pull(rest: list[str]) -> str | None:
    """A pull is a fetch and a merge: only one that must fast-forward."""
    if "--ff-only" not in _options(rest) or _has_option(rest, PULL_OPTIONS, "r", "sXSj"):
        return MESSAGE
    return None


def _grep(rest: list[str]) -> str | None:
    return UNSAFE_MESSAGE if _has_option(rest, {}, "O", "ABCefmO") else None


def _reflog(rest: list[str]) -> str | None:
    return MESSAGE if _first_word(rest) in REFLOG_WRITES else None


def _only(rest: list[str], allowed: frozenset, bare: bool) -> str | None:
    """A group whose first operand picks what it does: ``allowed`` reads, and with no operand, ``bare``."""
    first = rest[0] if rest else ""
    return None if first in allowed or (not rest and bare) else MESSAGE


# subcommand -> the check of its call: None for a call that reads, fetches or clones, else the message.
FORMS = {
    "fetch": _fetch,
    "clone": _clone,
    "pull": _pull,
    "grep": _grep,
    "reflog": _reflog,
    "branch": lambda rest: None if _list_only(rest, BRANCH) else MESSAGE,
    "tag": lambda rest: None if _list_only(rest, TAG) else MESSAGE,
    "remote": _remote,
    "config": lambda rest: None if _config_reads(rest) else MESSAGE,
    "stash": lambda rest: _only(rest, frozenset({"list", "show"}), False),
    "worktree": lambda rest: _only(rest, frozenset({"list"}), False),
    "notes": lambda rest: _only(rest, frozenset({"list", "show"}), True),
    "submodule": lambda rest: _only(rest, frozenset({"status", "summary"}), True),
}


def _verdict(args: list[str]) -> str | None:
    """The message for one reading of a git command (its arguments, without ``git``), or None for a
    read, a fetch or a clone."""
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in GLOBAL_VALUED:
            i += 2
        elif (arg.partition("=")[0] in GLOBAL_VALUED and "=" in arg) or arg in GLOBAL_FLAGS:
            i += 1
        elif arg.startswith("-"):
            return UNSAFE_MESSAGE
        else:
            break
    if i >= len(args):
        return None
    sub, rest = args[i], args[i + 1:]
    if sub in READ_COMMANDS or sub in FORMS:
        if _has_option(rest, PROGRAM_OPTIONS):
            return UNSAFE_MESSAGE
        return FORMS[sub](rest) if sub in FORMS else None
    return MESSAGE if sub in WRITES else UNKNOWN_MESSAGE


# The writes with no read form over the whole text, quotes and all, so one wrapped in `python -c "…"`,
# `awk` or split by a backslash-newline is caught too (and one only mentioned, conservatively).
# Flags may stand before the command (`git -C dir commit`, `git --no-pager push`).
_FLAGS = r"(?:-\S+\s+(?:[^-\s]\S*\s+)?)*"
_GIT = r"(?:(?<=/)|(?<![\w./-]))(?:git|hub)\s+" + _FLAGS


def _verbs(verbs) -> str:
    return "|".join(re.escape(v) for v in sorted(verbs, key=len, reverse=True))


_ANYWHERE = re.compile(
    _GIT + "(?:" + "|".join(
        [rf"(?:{_verbs(WRITES - {FRONTEND_MARK})})(?![\w-])"]
        + [rf"{group}\s+{_FLAGS}(?:{_verbs(verbs)})(?![\w-])" for group, verbs in GROUP_WRITES.items()]) + ")"
    + rf"|(?<![\w.-])git-(?:{_verbs(WRITES - {FRONTEND_MARK})})(?![\w.-])")


def blocked(command: str) -> str | None:
    """The message for a terminal command that goes around the tools, or None. A git command passes
    only when every way git may read its arguments is a read, a fetch or a clone."""
    command = command.replace("\\\n", " ")
    if _ANYWHERE.search(command):
        return MESSAGE
    found = {_verdict(args) for args in _invocations(command)}
    if found and _UNSAFE_ENV.search(command):
        found.add(UNSAFE_MESSAGE)
    return next((m for m in (MESSAGE, UNSAFE_MESSAGE, UNKNOWN_MESSAGE) if m in found), None)
