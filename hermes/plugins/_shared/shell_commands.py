"""shell_commands: whether a shell line runs a named program, read by command position.

The access plugins' bypass guards block a terminal call that runs a CLI the plugin owns (``gcloud``,
``wrangler``, ``stripe``, …). Matching the name anywhere in the text also blocks calls that only
mention it: ``grep -n 'gcloud auth' scripts/deploy.sh``, ``sed -n 1,60p deploy.sh | grep gcloud``.
``runs`` reads the line the way a shell would: quotes, separators, ``$(…)`` and backticks, and the
commands that run other commands (``bash -c``, ``eval``, ``trap``, ``env``, ``sudo``, ``xargs``,
``find -exec``, package runners such as ``npx`` and ``pnpm exec``), and reports a name where it is
the program a simple command runs.

A mention passes only as an argument of a command known to treat its arguments as data (``grep``,
``sed`` without its ``e`` command, ``cat``, ``echo``, ``git log``, …). Any other command that names
one in its arguments may run it in a way this reader does not follow (``ssh host gcloud``,
``script -q /dev/null gcloud``), so it is judged by the caller's strict pattern, as is a line this
reader cannot follow (an unclosed quote, a here-document, a command name built from an expansion,
a shell or an interpreter reading its code from a pipe or an argument, nesting past the limits).

A guard of text, not a sandbox: a script file's contents are never seen.

Shared by the access plugins (each loads this file by path; it is not a plugin and has no
manifest).
"""

from __future__ import annotations

import re

DEPTH = 8
BUDGET = 400
SHELLS = {"sh", "bash", "zsh", "dash", "ksh", "fish"}
SHELL_VALUED = {"-o", "+o", "-O", "+O", "--rcfile", "--init-file"}
# Commands whose arguments name the command they run (their own flags may take a value).
WRAPPERS = {"command", "exec", "env", "nohup", "time", "sudo", "doas", "nice", "timeout", "gtimeout", "stdbuf",
            "caffeinate", "builtin", "chronic", "unbuffer", "arch", "setsid", "script", "flock"}
# Package runners that run a package's binary: `npx wrangler`, `pnpm exec wrangler`, `pnpm wrangler`.
RUNNERS = {"npx", "bunx", "pnpx", "uvx"}
MANAGERS = {"pnpm": {"exec", "dlx", "x"}, "yarn": {"exec", "dlx"}, "bun": {"x", "exec"}, "npm": {"exec", "x"},
            "uv": {"run"}, "poetry": {"run"}, "pipx": {"run"}, "pdm": {"run"}, "hatch": {"run"}, "rye": {"run"},
            "bundle": {"exec"}}
# A manager that runs a dependency's binary by its bare name (`pnpm wrangler`) unless it is one of its own
# commands; npm does not.
BARE_BIN = {"pnpm", "yarn", "bun"}
MANAGER_COMMANDS = {"add", "install", "i", "remove", "rm", "uninstall", "update", "up", "upgrade", "run", "test",
                    "start", "build", "view", "info", "list", "ls", "why", "outdated", "audit", "init", "link",
                    "unlink", "pack", "prune", "rebuild", "config", "store", "licenses", "dedupe", "import"}
KEYWORDS = {"if", "then", "else", "elif", "fi", "do", "done", "while", "until", "case", "esac", "{", "}", "!",
            "[[", "]]", "select", "noglob", "nocorrect"}
# Interpreters, which read their code from input when no script or code argument is given.
INTERPRETERS = re.compile(r"^(?:python[\d.]*|node|perl|ruby|php|osascript|deno|bun|tsx|ts-node|lua|r|rscript"
                          r"|jshell|swift|irb|pwsh)$")
# Commands whose arguments are data: they may name a CLI without running it.
DATA = {"grep", "egrep", "fgrep", "rg", "ag", "ack", "sed", "gsed", "cat", "bat", "head", "tail", "less", "more",
        "echo", "printf", "ls", "wc", "cut", "tr", "nl", "column", "fold", "uniq", "diff", "cmp", "comm", "jq",
        "yq", "which", "whereis", "type", "file", "stat", "test", "[", "[[", "true", "false", "cd", "pwd", "mkdir",
        "touch", "rm", "tee", "basename", "dirname", "realpath", "readlink", "read", "export", "local", "declare",
        "typeset", "unset", "set", "shift", "return", "exit", "date", "sleep", "du", "df", "tree", "man", "open",
        "pbcopy", "base64", "shasum", "sha256sum", "md5", "xxd", "od", "strings", "git", "wait", "sort"}
# git commands that run nothing the line names (aliases, `-c` settings, `bisect run` and `rebase --exec` do).
GIT_DATA = {"log", "show", "diff", "grep", "status", "commit", "add", "blame", "branch", "checkout", "switch",
            "fetch", "pull", "push", "stash", "tag", "ls-files", "rev-parse", "remote", "restore", "reset",
            "clone", "init", "describe", "shortlog", "worktree", "mv", "rm", "merge-base", "cat-file", "rev-list"}
# git options that run a command they are given.
_GIT_EXEC = re.compile(r"^(?:-c.*|--config.*|--upload-pack.*|--receive-pack.*|--exec.*|--ext-diff|--textconv|-u)$")
# sed's `e` command (also after an address: `1e cmd`, `/x/e cmd`) and the `e` flag of `s` with any
# delimiter run a command (GNU sed).
_SED_EXEC = re.compile(r"(?:^|[;{}\n\d$/!,])\s*e(?:\s|;|}|$)"
                       r"|s([^\\\n])(?:\\.|(?!\1).)*\1(?:\\.|(?!\1).)*\1[gIipmM0-9w]*e")
# Flags known to take no value, per wrapper, so the word after them is the command and not a value.
SWITCHES = {
    "xargs": {"-0", "-t", "-p", "-r", "-x", "-o", "--null", "--verbose", "--no-run-if-empty", "--interactive"},
    "sudo": {"-E", "-H", "-n", "-b", "-i", "-s", "-k", "-K", "-P", "-S", "-A", "-B", "--preserve-env",
             "--non-interactive", "--login", "--shell", "--stdin"},
    "env": {"-i", "-0", "-v", "--ignore-environment", "--null", "--debug"},
    "timeout": {"--preserve-status", "--foreground", "-v", "--verbose"},
    "nohup": set(), "command": {"-p"}, "exec": {"-c", "-l"},
    "npx": {"-y", "--yes", "-q", "--quiet", "--no-install", "--no"},
    "pnpm": {"-r", "--recursive", "-w", "--workspace-root", "-s", "--silent", "--shell-mode"},
}
# Commands that may run what they are fed, beside interpreters and shells reading a file or input.
EXECUTORS = {"parallel", "source", "."}
# awk reads records as data; its program runs commands only through system(), a pipe or getline.
AWKS = {"awk", "gawk", "nawk", "mawk"}
_AWK_EXEC = re.compile(r"system|\||getline|@load|ENVIRON")
_GLOB = re.compile(r"[*?]|\[.*\]|\{.*(?:,|\.\.).*\}")
FIND_EXEC = {"-exec", "-execdir", "-ok", "-okdir"}

_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\+?=")
_NUMBER = re.compile(r"^\d+(?:\.\d+)?[smhd]?$")  # a wrapper's duration or count (timeout 10)
_SEPARATORS = set(";|&\n()")
_SPACE = set(" \t\r")


class Unreadable(Exception):
    """The line holds a form this reader does not follow."""


class _Word:
    __slots__ = ("text", "clean", "kind")

    def __init__(self, text: str, clean: bool, kind: str):
        self.text, self.clean, self.kind = text, clean, kind  # kind: word | target | herestring


def _close_paren(text: str, start: int) -> int:
    """The index of the `)` closing a `$(` or `<(` whose body starts at ``start``."""
    depth, i, n = 1, start, len(text)
    while i < n:
        c = text[i]
        if c == "\\":
            i += 2
            continue
        if c == "'":
            j = text.find("'", i + 1)
            if j < 0:
                raise Unreadable("unclosed quote")
            i = j + 1
            continue
        if c == '"':
            i = _skip_double(text, i + 1)
            continue
        if c == "#" and (i == start or text[i - 1] in " \t\n;(|&"):
            j = text.find("\n", i)  # a comment: its `)` closes nothing
            if j < 0:
                raise Unreadable("unclosed substitution")
            i = j
            continue
        if c == "$" and text.startswith(("$'", '$"'), i):
            raise Unreadable("ANSI-C or locale quoting")
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise Unreadable("unclosed substitution")


def _skip_double(text: str, i: int) -> int:
    n = len(text)
    while i < n:
        c = text[i]
        if c == "\\":
            i += 2
            continue
        if c == '"':
            return i + 1
        if c == "$" and text.startswith("$(", i):
            i = _close_paren(text, i + 2) + 1
            continue
        if c == "`":
            j = _backtick_end(text, i + 1)
            i = j + 1
            continue
        i += 1
    raise Unreadable("unclosed quote")


def _backtick_end(text: str, i: int) -> int:
    n = len(text)
    while i < n:
        if text[i] == "\\":
            if text.startswith("\\`", i):
                raise Unreadable("nested backticks")
            i += 2
            continue
        if text[i] == "`":
            return i
        i += 1
    raise Unreadable("unclosed backtick")


def _split(text: str, out: list, depth: int, budget: list) -> None:
    """Append each simple command in ``text`` to ``out`` as a list of words; the bodies of
    command and process substitutions are read as command lines of their own. ``budget`` is
    [steps left, whether a pipe or an input redirection feeds some command]."""
    budget[0] -= 1
    if depth > DEPTH or budget[0] < 0:
        raise Unreadable("nested too deep")
    words: list[_Word] = []
    cur: list[str] = []
    state = {"started": False, "clean": True, "kind": "word"}
    pending = ["word"]  # the kind of the next word: a redirection's target or a here-string

    def end_word():
        if state["started"]:
            words.append(_Word("".join(cur), state["clean"], pending[0]))
            pending[0] = "word"
        cur.clear()
        state["started"], state["clean"] = False, True

    def end_command():
        end_word()
        if words:
            out.append(list(words))
        words.clear()
        pending[0] = "word"

    def substitute(body: str):
        _split(body, out, depth + 1, budget)
        cur.append("$(…)")
        state["started"], state["clean"] = True, False

    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == "\\":
            if text.startswith("\\\n", i):
                i += 2
                continue
            if i + 1 < n:
                cur.append(text[i + 1])
                state["started"] = True
            i += 2
            continue
        if c == "'":
            j = text.find("'", i + 1)
            if j < 0:
                raise Unreadable("unclosed quote")
            cur.append(text[i + 1:j])
            state["started"] = True
            i = j + 1
            continue
        if c == '"':
            i = _double(text, i + 1, cur, state, substitute)
            continue
        if c == "$" and text.startswith("$((", i):
            j = text.find("))", i + 3)
            if j < 0 or "$(" in text[i + 3:j] or "`" in text[i + 3:j]:
                raise Unreadable("arithmetic holding a command")
            cur.append(text[i:j + 2])
            state["started"], state["clean"] = True, False
            i = j + 2
            continue
        if c == "$" and text.startswith("$(", i):
            j = _close_paren(text, i + 2)
            substitute(text[i + 2:j])
            i = j + 1
            continue
        if c == "`":
            j = _backtick_end(text, i + 1)
            substitute(text[i + 1:j])
            i = j + 1
            continue
        if c == "$" and text.startswith(("$'", '$"'), i):
            raise Unreadable("ANSI-C or locale quoting")  # $'\'' holds an escaped quote
        if c == "$":
            cur.append(c)
            state["started"], state["clean"] = True, False
            i += 1
            continue
        if c in _SPACE:
            end_word()
            i += 1
            continue
        if c == "#" and not state["started"]:
            j = text.find("\n", i)
            i = n if j < 0 else j
            continue
        if c in "<>" or (c == "&" and text.startswith("&>", i)):
            if text.startswith("<<", i) and not text.startswith("<<<", i):
                raise Unreadable("here-document")
            if state["started"] and state["clean"] and "".join(cur).isdigit():
                cur.clear()
                state["started"] = False  # a file descriptor: 2>&1
            end_word()
            herestring = text.startswith("<<<", i)
            if c == "<":
                budget[1] = True  # a command is fed input
            j = i + 1
            while j < n and text[j] in "<>&|":
                j += 1
            if j < n and text[j] == "(" and c in "<>":
                k = _close_paren(text, j + 1)
                _split(text[j + 1:k], out, depth + 1, budget)  # process substitution
                if pending[0] == "target":
                    pending[0] = "word"  # it was the redirection's target: `2> >(cat) cmd`
                else:
                    words.append(_Word("<(…)", False, "word"))  # an argument: a file the command reads
                i = k + 1
                continue
            pending[0] = "herestring" if herestring else "target"
            i = j
            continue
        if c in _SEPARATORS:
            if c == "|" and not text.startswith("||", i) and not (i and text[i - 1] == "|"):
                budget[1] = True  # a pipe feeds the next command
            end_command()
            i += 1
            continue
        cur.append(c)
        state["started"] = True
        i += 1
    end_command()


def _double(text: str, i: int, cur: list, state: dict, substitute) -> int:
    """Read a double-quoted string from ``i`` (past the quote) into ``cur``; the index after it."""
    n = len(text)
    state["started"] = True
    while i < n:
        c = text[i]
        if c == "\\" and i + 1 < n and text[i + 1] in '$`"\\\n':
            if text[i + 1] != "\n":
                cur.append(text[i + 1])
            i += 2
            continue
        if c == '"':
            return i + 1
        if c == "$" and text.startswith("$(", i) and not text.startswith("$((", i):
            j = _close_paren(text, i + 2)
            substitute(text[i + 2:j])
            i = j + 1
            continue
        if c == "`":
            j = _backtick_end(text, i + 1)
            substitute(text[i + 1:j])
            i = j + 1
            continue
        if c == "$":
            state["clean"] = False
        cur.append(c)
        i += 1
    raise Unreadable("unclosed quote")


def _name(word: str) -> str:
    """The program a command word names: its last path part, without a package runner's version
    pin (`wrangler@4`), in lower case (macOS paths ignore case)."""
    base = word.rstrip("/").rsplit("/", 1)[-1]
    if "@" in base[1:]:
        base = base[0] + base[1:].split("@", 1)[0]
    return base.lower()


def _positions(rest: list[str], switches=frozenset()) -> list[int]:
    """Where a wrapper may find the command it runs in ``rest``. A flag before it may or may not
    take the next token as its value (unless it is one of ``switches``), so after a flag without
    ``=`` both that token and the one after it count."""
    found, i, valued = [], 0, False
    while i < len(rest):
        token = rest[i]
        if token.startswith("-"):
            valued = "=" not in token and token != "--" and token not in switches
        elif _ASSIGN.match(token) or _NUMBER.match(token):
            pass
        else:
            found.append(i)
            if not valued:
                break
            valued = False
        i += 1
    return found


def _shell_input(words: list[_Word]) -> tuple[str, _Word | None]:
    """How a shell gets its script: ("string", word) after -c, ("file", word) for a script file,
    ("input", None) when it reads standard input (-s, or no script at all)."""
    rest, j, string, stdin = words[1:], 0, False, False
    while j < len(rest):
        t = rest[j].text
        if t == "--":
            j += 1
            break
        if t in SHELL_VALUED:
            j += 2
            continue
        if t[:1] in ("-", "+") and len(t) > 1:
            if not t.startswith("--") and t[0] == "-":
                string = string or "c" in t[1:]
                stdin = stdin or "s" in t[1:]
            j += 1
            continue
        break
    operand = rest[j] if j < len(rest) else None
    if string:
        if operand is None:
            raise Unreadable("shell -c without a script")
        return "string", operand
    if stdin or operand is None:
        return "input", None
    return "file", operand


def _git_verb(texts: list[str]) -> str:
    """git's command, past its global options and their operands (`git -C dir grep …`)."""
    i = 0
    while i < len(texts):
        t = texts[i]
        if t in ("-C", "-c", "--git-dir", "--work-tree", "--namespace"):
            i += 2
        elif t.startswith("-"):
            i += 1
        else:
            return t
    return ""


def _sed_scripts(texts: list[str]) -> list[str | None]:
    """sed's scripts: each -e value (also bundled, `-ne'1e cmd'`), else its first operand; None for
    a script file (-f), unseen."""
    scripts, i, given = [], 0, False
    while i < len(texts):
        t = texts[i]
        if t.startswith("--"):
            if t in ("--expression", "--file"):
                given = True
                scripts.append(texts[i + 1] if t == "--expression" and i + 1 < len(texts) else None)
                i += 1
            elif t.startswith("--expression="):
                given = True
                scripts.append(t.split("=", 1)[1])
            elif t.startswith("--file="):
                given = True
                scripts.append(None)
        elif t.startswith("-") and len(t) > 1:
            for k, letter in enumerate(t[1:], 1):
                if letter in "efl":
                    value = t[k + 1:]
                    if not value:
                        value = texts[i + 1] if i + 1 < len(texts) else ""
                        i += 1
                    if letter != "l":
                        given = True
                        scripts.append(value if letter == "e" else None)
                    break
                if letter == "i":
                    break  # -i[SUFFIX]: the rest is a suffix
        elif not given:
            return [t]
        i += 1
    return scripts


def _awk_program(texts: list[str]) -> str | None:
    """awk's program: its first operand past -v and -F; None when it may come from anywhere else
    (-f, -e, --source, --include, …), which is not read."""
    i = 0
    while i < len(texts):
        t = texts[i]
        if t == "--":
            return texts[i + 1] if i + 1 < len(texts) else ""
        if t in ("-v", "-F", "--assign", "--field-separator"):
            i += 2
            continue
        if t.startswith(("-v", "-F", "--assign=", "--field-separator=")):
            i += 1
            continue
        if t.startswith("-"):
            return None
        return t
    return ""


def _reads_input(word: _Word) -> bool:
    return not word.clean or word.text in ("-", "/dev/stdin") or word.text.startswith("/dev/fd/")


class _Reader:
    def __init__(self, names, fallback: re.Pattern):
        self.names = {name.lower() for name in names}
        self.fallback = fallback
        self.budget = [BUDGET, False]
        # A data command's mention passes only while nothing on the line runs what it is fed:
        # `echo 'gcloud x' | python3 -W ignore`, `echo gcloud | xargs -I CMD CMD auth`; a command
        # this reader does not know counts as one when the line feeds input to a command.
        self.executor = False
        self.unknown = False
        self.data_mention = False

    def runs_fed_input(self) -> bool:
        return self.executor or (self.unknown and self.budget[1])

    def line(self, text: str, depth: int = 0) -> bool:
        commands: list = []
        _split(text, commands, depth, self.budget)
        return any(self.simple(words, depth) for words in commands)

    def simple(self, words: list[_Word], depth: int) -> bool:
        herestrings = [w.text for w in words if w.kind == "herestring"]
        words = [w for w in words if w.kind == "word"]
        if any("[" in w.text and ("$(" in w.text or "`" in w.text) for w in words):
            raise Unreadable("a subscript holding a command")  # printf -v 'a[$(cmd)]' evaluates it
        while words and words[0].clean:
            first = words[0].text
            if first == "function":  # function NAME { …; }
                words = words[2:]
            elif first == "coproc":  # coproc [NAME] { …; } or coproc COMMAND
                words = words[2:] if len(words) > 2 and words[2].text == "{" else words[1:]
            elif first == "time":
                words = words[1:]
                while words and words[0].text.startswith("-"):
                    words = words[1:]
            elif first in KEYWORDS:
                words = words[1:]
            else:
                break
        while words and _ASSIGN.match(words[0].text):  # the value may expand: f=$(…)
            if words[0].clean and self.value(words[0].text.split("=", 1)[1], depth):
                return True  # a value that is itself run (a pager, an editor, `X=gcloud; $X`)
            words = words[1:]
        return self.argv(words, depth, herestrings)

    def value(self, text: str, depth: int) -> bool:
        """Whether an assigned value, read as a command line, runs a name. A value that does not
        read as one (`MSG="don't"`) runs nothing by being assigned; using it as a command name later
        is an expansion, which this reader does not follow. Reading it leaves the line's other
        marks as they were: a value is not run by being assigned."""
        marks = (self.executor, self.unknown, self.data_mention, self.budget[1])
        try:
            return self.line(text, depth + 1)
        except Unreadable:
            return False
        finally:
            self.executor, self.unknown, self.data_mention, self.budget[1] = marks

    def mentioned(self, words: list[_Word], herestrings=()) -> bool:
        """A command not known to treat its arguments (or here-strings) as data, naming a CLI in
        them, is judged by the strict pattern; otherwise it runs nothing named."""
        if any(self.fallback.search(t) for t in [w.text for w in words] + list(herestrings)):
            raise Unreadable("a CLI named in the arguments of a command not known to be data")
        return False

    def follow(self, words: list[_Word], depth: int, wrapper: str = "") -> bool:
        """The command a wrapper runs, at each place its flags leave open."""
        texts = [w.text for w in words]
        at = _positions(texts, SWITCHES.get(wrapper, ()))
        if not at:
            self.unknown = True  # `sudo -s` with no command runs a shell on its input
        return any(self.argv(words[j:], depth + 1) for j in at)

    def argv(self, words: list[_Word], depth: int, herestrings=()) -> bool:
        self.budget[0] -= 1
        if depth > DEPTH or self.budget[0] < 0:
            raise Unreadable("nested too deep")
        while words and _ASSIGN.match(words[0].text):
            words = words[1:]
        if not words:
            return False
        head, rest = words[0], words[1:]
        if not head.clean:
            raise Unreadable("command name from an expansion")
        if any(c in head.text for c in " \t\n;|&"):
            return self.line(head.text, depth + 1)  # a command string: env -S '…', npx -c '…'
        if head.text not in ("[", "[[") and _GLOB.search(head.text):
            raise Unreadable("command name from a pattern")
        name = _name(head.text)
        texts = [w.text for w in rest]
        if name in self.names:
            return True
        if name in EXECUTORS or INTERPRETERS.match(name):
            self.executor = True
        if name in SHELLS:
            how, operand = _shell_input(words)
            if how == "string":
                if not operand.clean:
                    raise Unreadable("shell script from an expansion")
                return self.line(operand.text, depth + 1)
            self.executor = True
            if how == "input":
                if herestrings:
                    return any(self.line(h, depth + 1) for h in herestrings)
                raise Unreadable("a shell reading its script from input")
            if _reads_input(operand):
                raise Unreadable("a shell reading its script from input")
            return self.mentioned(rest)  # a script file: its contents are not seen
        if name in ("source", "."):
            if not rest or _reads_input(rest[0]):
                raise Unreadable("a script read from input")
            return self.mentioned(rest)
        if name == "eval":
            return self.line(" ".join(texts), depth + 1)
        if name == "trap":
            at = _positions(texts)
            return bool(at) and self.line(texts[at[0]], depth + 1)
        if name == "alias":
            return any(self.line(t.split("=", 1)[1], depth + 1) for t in texts if "=" in t)
        if name == "watch":
            at = _positions(texts)
            return bool(at) and self.line(" ".join(texts[at[0]:]), depth + 1)
        if name == "find":
            found = [j for j, t in enumerate(texts) if t in FIND_EXEC]
            if any("{}" in texts[j + 1] for j in found if j + 1 < len(texts)):
                raise Unreadable("find runs the files it finds")  # find -name gcloud -exec {} …
            return any(self.argv(rest[j + 1:], depth + 1) for j in found)
        if name == "xargs":
            # Input becomes the command's arguments, or with -I/-J the text replacing a string,
            # which may be its name; and a wrapper, runner or shell run by xargs takes its
            # command from input.
            at = _positions(texts, SWITCHES["xargs"])
            marks = {"{}"} | {texts[k + 1] for k, t in enumerate(texts[:-1]) if t in ("-I", "-J")}
            marks |= {t[2:] for t in texts if t[:2] in ("-I", "-J", "-i") and len(t) > 2}
            marks |= {t.split("=", 1)[1] for t in texts if t.startswith("--replace=")}
            if any(any(m and m in texts[j] for m in marks) for j in at):
                raise Unreadable("xargs runs a command its input names")
            for j in at:
                runner = _name(texts[j])
                if runner in WRAPPERS | RUNNERS | set(MANAGERS) | SHELLS | EXECUTORS | {"eval"} or \
                        INTERPRETERS.match(runner):
                    self.executor = True
            return any(self.argv(rest[j:], depth + 1) for j in at)
        if name == "parallel":
            raise Unreadable("parallel runs commands its input or arguments name")
        if name == "command" and texts[:1] in (["-v"], ["-V"]):
            return False  # `command -v gcloud` only looks the name up
        if name == "env":
            for t in texts:
                if t.startswith("--split-string="):
                    return self.line(t.split("=", 1)[1], depth + 1)
                if t.startswith("-S") and len(t) > 2:
                    return self.line(t[2:], depth + 1)
            return self.follow(rest, depth, "env")
        if name in WRAPPERS or name in RUNNERS:
            for t in texts:
                if t.startswith("--call="):
                    return self.line(t.split("=", 1)[1], depth + 1)
            return self.follow(rest, depth, "npx" if name in RUNNERS else name)
        if name in MANAGERS and not (name == "bun" and any(t in ("-e", "--eval", "-p", "--print") for t in texts)):
            for t in texts:
                if t.startswith("--call="):
                    return self.line(t.split("=", 1)[1], depth + 1)
            for j in _positions(texts, SWITCHES.get(name, ())):
                if texts[j] in MANAGERS[name]:
                    return self.follow(rest[j + 1:], depth, "npx")
                if texts[j] in MANAGER_COMMANDS:
                    return False
                if name not in BARE_BIN:
                    return self.mentioned(rest)
                if self.argv(rest[j:], depth + 1):
                    return True
            return False
        if INTERPRETERS.match(name):
            if not any(not t.startswith("-") for t in texts) or any(_reads_input(w) for w in rest):
                raise Unreadable("an interpreter reading its code from input")
            return self.mentioned(rest, herestrings)
        if name in AWKS:
            program = _awk_program(texts)
            if program is None or _AWK_EXEC.search(program):
                self.executor = True  # a program file, or one that runs commands
                return self.mentioned(rest, herestrings)
            return self.data(texts, herestrings)
        if name in DATA:
            if name in ("sed", "gsed") and any(s is None or _SED_EXEC.search(s) for s in _sed_scripts(texts)):
                self.executor = True  # a script file (even /dev/stdin), or one that runs commands
                return self.mentioned(rest, herestrings)
            if name == "rg" and any(t == "--pre" or t.startswith("--pre=") for t in texts):
                return self.mentioned(rest, herestrings)
            if name == "sort" and any(t.startswith("--compress-program") for t in texts):
                return self.mentioned(rest, herestrings)
            if name == "git" and (_git_verb(texts) not in GIT_DATA or any(_GIT_EXEC.match(t) for t in texts)):
                return self.mentioned(rest, herestrings)
            return self.data(texts, herestrings)
        self.unknown = True
        return self.mentioned(rest, herestrings)

    def data(self, texts: list[str], herestrings) -> bool:
        if any(self.fallback.search(t) for t in list(texts) + list(herestrings)):
            self.data_mention = True
        return False


def runs(command: str, names, fallback: re.Pattern) -> bool:
    """Whether the shell line ``command`` may run a program named in ``names``.

    ``fallback`` is the caller's strict pattern, searched over the whole line when the line holds a
    form this reader cannot follow, or names a CLI in the arguments of a command not known to treat
    them as data."""
    reader = _Reader(names, fallback)
    try:
        if reader.line(command):
            return True
        if reader.data_mention and reader.runs_fed_input():
            raise Unreadable("a mention on a line that also runs what it is fed")
        return False
    except Unreadable:
        return bool(fallback.search(command))
