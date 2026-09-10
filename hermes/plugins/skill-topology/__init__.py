"""Keep runtime-authored Hermes skills inside the learned boundary.

Placement of new skills is NOT decided here. Every ``config.yaml`` sets
``skills.create_dir: skills/learned`` (HERMES_HOME-relative), which
``skill_manage`` consults on every create — flat or ``operations[]``
shape, curator, ``/learn``, background review and the ``/skills approve``
replay alike — so a runtime-authored skill lands at
``<HERMES_HOME>/skills/learned/[<category>/]<name>``.

This plugin used to inject ``category: learned`` through a ``tool_request``
middleware keyed on a top-level ``action == "create"``. Upstream ``72874b0675``
(2026-08-28) made ``operations[]`` the only advertised call shape, so the
rewrite silently missed every batched create and those skills landed in the
profile's skill root (2026-09-07..09). ``create_dir`` cannot miss, and with
it a middleware would only double the path (``learned/learned/<name>``), so
the rewrite is gone. The plugin stays registered as the home of the
topology guard (maintainer-owned skill roots are read-only at runtime).

The remaining policy: maintainer-owned skill files are read-only at
runtime. ``write_file`` / ``patch`` / ``skill_manage`` edits and terminal
writes that resolve into a tracked skill root (``<repo>/hermes/**/skills/…``
outside ``learned/``) are blocked. A hands leaf's procedure that no longer
matches the runtime is REPORTED in the reply ("reported, never patched: the
tree is the maintainer's"); on 2026-09-05 image-creator patched
``text-emoji.sh`` in place instead, and the fix it chose was not the one
the maintainer wanted.

Terminal checks cover literal redirects and known mutators, not arbitrary
program behavior or persistent shell state. This is a topology guard, not a
terminal sandbox. Unsupported evaluation is blocked only with a visible managed
reference; known writes with unresolved targets fail closed.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, NamedTuple


LEARNED_CATEGORY = "learned"
MANAGED_ROOT = Path(__file__).resolve().parents[2]  # <repo>/hermes
_FILE_WRITE_TOOLS = {"write_file", "patch"}
_MUTATORS = {"cp", "mv", "rm", "chmod", "truncate", "tee", "sed"}
_SHELL_OPERATOR = re.compile(r"(?:\d*(?:<<<|<<-|<<|>>|>\||>&|<&|<>|>|<)|&>>|&>|&&|\|\||\|&|;;|;&|[;|&\n()])")
_ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z_0-9]*=")
_GHQ_ROOT = "$(ghq root)"
_RUNTIME_COMMAND_PATH = re.compile(
    r"(?:\$(?:HERMES_SKILL_DIR|HOME)|\$\{(?:HERMES_SKILL_DIR|HOME)\}|"
    + re.escape(_GHQ_ROOT) + r")(?:/[A-Za-z0-9_.+-]+)+"
)


class _ShellToken(NamedTuple):
    text: str
    operator: bool = False
    dynamic: bool = False


class _UnresolvedWrite(ValueError):
    """A known write whose target cannot safely be determined."""


def _shell_tokens(command: str) -> list[_ShellToken]:
    """Lex literal shell words, retaining operator identity across quoting.

    This is not a shell evaluator. Expansions stay unresolved; only the exact
    ghq-root placeholder is recognized. Other substitutions, grouping and
    here-documents are outside this guard's supported syntax.
    """
    tokens: list[_ShellToken] = []
    i = 0
    while i < len(command):
        if command[i].isspace() and command[i] != "\n":
            i += 1
            continue
        if command.startswith("\\\n", i):
            i += 2
            continue
        if command[i] == "#":
            end = command.find("\n", i)
            i = len(command) if end < 0 else end
            continue
        match = _SHELL_OPERATOR.match(command, i)
        if match:
            op = match.group()
            if op in {"(", ")", ";;", ";&"} or "<<" in op:
                raise ValueError("unsupported shell grouping or here-document")
            tokens.append(_ShellToken(op, operator=True))
            i = match.end()
            continue
        word: list[str] = []
        start = i
        quote = ""
        dynamic = False
        while i < len(command):
            char = command[i]
            if not quote and (char.isspace() or char in ";|&<>()"):
                break
            if char == "\\" and quote != "'":
                i += 1
                if i == len(command):
                    raise ValueError("unfinished shell escape")
                escaped = command[i]
                if escaped != "\n":
                    if quote == '"' and escaped not in '$`"\\':
                        word.append("\\")
                    word.append(escaped)
            elif char == quote:
                quote = ""
            elif not quote and char in "'\"":
                quote = char
            else:
                if quote != "'":
                    if command.startswith(_GHQ_ROOT, i):
                        # Preserve the fragment, never execute it or invent a path.
                        word.append(_GHQ_ROOT)
                        dynamic = True
                        i += len(_GHQ_ROOT)
                        continue
                    if char == "`" or command.startswith("$(", i):
                        raise ValueError("opaque shell substitution")
                    dynamic |= char == "$" or (not quote and char in "*?[]{}")
                # Only an unquoted leading tilde is expanded, never variables.
                if not quote and i == start and char == "~":
                    end = i + 1
                    while end < len(command) and command[end] not in "/ \t\r\n;|&<>()'\"":
                        end += 1
                    home = command[i:end]
                    expanded = os.path.expanduser(home)
                    dynamic |= expanded == home
                    word.append(expanded)
                    i = end - 1
                else:
                    word.append(char)
            i += 1
        if quote:
            raise ValueError("unfinished shell quote")
        tokens.append(_ShellToken("".join(word), dynamic=dynamic))
    return tokens


def _unwrap_command(words: list[_ShellToken]) -> list[_ShellToken]:
    """Remove literal assignments and common, non-evaluating wrappers."""
    while words:
        if _ASSIGNMENT.match(words[0].text):
            words = words[1:]
            continue
        if words[0].dynamic and not _RUNTIME_COMMAND_PATH.fullmatch(words[0].text):
            raise ValueError("unresolved command name")
        name = os.path.basename(words[0].text)
        if name not in {"env", "command", "builtin", "sudo"}:
            return words
        words = words[1:]
        while words and words[0].text.startswith("-"):
            option = words[0]
            words = words[1:]
            if option.dynamic:
                raise ValueError("unresolved wrapper option")
            if option.text == "--":
                break
            if name == "command" and option.text in {"-v", "-V"}:
                return []  # Command lookup, not execution.
            flags = {
                "env": {"-i", "--ignore-environment", "-0", "--null"},
                "command": {"-p"},
                "builtin": set(),
                "sudo": {"-n", "-E", "-H", "-S", "-b", "-k", "-K"},
            }[name]
            values = {
                "env": {"-u", "--unset"},
                "command": set(),
                "builtin": set(),
                "sudo": {"-u", "-g", "-h", "-p", "-C", "-T", "--user", "--group"},
            }[name]
            if option.text in values:
                if not words or words[0].dynamic:
                    raise ValueError("unresolved wrapper option value")
                words = words[1:]
            elif option.text not in flags and not any(
                option.text.startswith(flag + "=") if flag.startswith("--")
                else option.text.startswith(flag) and len(option.text) > len(flag)
                for flag in values
            ):
                raise ValueError(f"unsupported {name} wrapper option")
    return words


def _command_write_targets(words: list[_ShellToken], cwd: Path | None) -> tuple[list[_ShellToken], bool]:
    """Return write operands and whether enclosing directories are at risk."""
    if not words:
        return [], False
    name = os.path.basename(words[0].text)
    args = words[1:]
    if name in {"eval", "source", ".", "exec",
                "if", "then", "else", "elif", "fi", "for", "while", "until",
                "do", "done", "case", "esac", "function", "!"}:
        raise ValueError("opaque shell evaluation or shell state change")
    shells = {"sh", "bash", "dash", "zsh", "ksh", "fish"}
    python = bool(re.fullmatch(r"python(?:\d+(?:\.\d+)*)?", name))
    if name in shells | {"node", "nodejs", "perl", "ruby"} or python:
        flags = "cCs" if name in shells else "c" if python else "ep"
        value_options = {"-W", "-X"} if python else {"-o", "-O"} if name in shells else set()
        options = iter(args)
        for arg in options:
            if arg.text in {"--", "-"} or not arg.text.startswith("-"):
                break
            if arg.text in value_options:
                next(options, None)
                continue
            if python and arg.text.startswith(("-W", "-X")):
                continue
            if ((not arg.text.startswith("--") and any(flag in arg.text[1:] for flag in flags)) or
                    arg.text.split("=")[0] in {"--command", "--init-command", "--eval", "--print"}):
                raise ValueError("opaque inline interpreter evaluation")
            if arg.dynamic:
                break
        return [], False  # Script paths (including templates) and arguments are reads.
    if name not in _MUTATORS:
        if name not in {"echo", "printf", "cat", "ls", "pwd", "cd", "pushd", "popd"} and any(
            os.path.basename(arg.text) in _MUTATORS for arg in args
        ):
            raise ValueError("known mutator behind an unrecognized wrapper or subcommand")
        return [], False
    if name != "sed" and any(arg.dynamic for arg in args):
        raise _UnresolvedWrite(f"unresolved {name} write operands or options")

    operands: list[_ShellToken] = []
    target_directory = None
    in_place = False
    explicit_sed_script = False
    implicit_chmod_mode = False
    recursive = False
    options = True
    i = 0
    while i < len(args):
        arg = args[i]
        text = arg.text
        i += 1
        if options and text == "--":
            options = False
            continue
        if not options or not text.startswith("-") or text == "-":
            operands.append(arg)
            continue
        if name == "cp" and (text in {"--recursive", "--archive"} or
                             (not text.startswith(("-t", "-S")) and re.fullmatch(r"-[A-Za-z]+", text) and
                              any(flag in text[1:] for flag in "rRa"))):
            recursive = True
        if name == "sed" and (text.startswith("-i") or text.split("=")[0] == "--in-place"):
            in_place = True
            if text == "-i" and i < len(args) and args[i].text == "":
                i += 1  # BSD's explicit empty backup suffix.
            continue
        if name == "chmod":
            if text.split("=")[0] == "--reference" or re.fullmatch(r"-[rwxXstugo,+=-]+", text):
                implicit_chmod_mode = True
            elif not re.fullmatch(r"-[RcfvHLPh]+|--(?:recursive|changes|silent|quiet|verbose|preserve-root|no-preserve-root|help|version)", text):
                raise ValueError("unsupported chmod flag or combined mode")
        if name in {"cp", "mv"} and (text.startswith("-t") or text.split("=")[0] == "--target-directory"):
            value = text[2:] if text.startswith("-t") else text.partition("=")[2]
            if not value:
                if i == len(args):
                    raise ValueError("missing target directory")
                value = args[i].text
                i += 1
            target_directory = _ShellToken(value)
            continue
        takes_value = {
            "cp": {"-S", "--suffix"}, "mv": {"-S", "--suffix"},
            "truncate": {"-s", "--size", "-r", "--reference"},
            "chmod": {"--reference"}, "sed": {"-e", "--expression", "-f", "--file"},
        }.get(name, set())
        # Abbreviations of these options change which operands are targets.
        if ((name in {"cp", "mv"} and text.startswith("--t")) or
                (name == "chmod" and text.startswith("--r") and
                 "--reference".startswith(text.split("=")[0]) and text.split("=")[0] != "--reference")):
            raise ValueError("abbreviated target-changing option")
        if text in takes_value:
            explicit_sed_script |= name == "sed"
            i += 1
        elif name == "sed" and text.startswith(("-e", "-f", "--expression=", "--file=")):
            explicit_sed_script = True
        elif name == "sed" and not re.fullmatch(r"-[nErsu]+|--(?:quiet|silent|posix)", text):
            # Combined sed flags can hide -i; don't guess their option grammar.
            raise ValueError("unsupported sed option")
        elif name in {"cp", "mv"} and re.search(r"[tS]", text[1:]) and not text.startswith("--"):
            raise ValueError("unsupported combined copy/move option")
    if name == "sed":
        if in_place and any(arg.dynamic for arg in args):
            raise _UnresolvedWrite("unresolved sed write operands or options")
        targets = operands if explicit_sed_script else operands[1:]
        return (targets if in_place else []), False
    if name == "chmod":
        return (operands if implicit_chmod_mode else operands[1:]), True
    if name == "cp":
        if not operands:
            return [], False
        destination = target_directory or operands[-1]
        sources = operands if target_directory else operands[:-1]
        # Include implicit destination filenames, including symlinks in a dir.
        targets = [destination]
        if target_directory or ((cwd is not None or Path(destination.text).is_absolute()) and
                                ((cwd or Path("/")) / destination.text).is_dir()):
            targets.extend(
                _ShellToken(str(Path(destination.text) / Path(source.text).name))
                for source in sources
            )
        return targets, recursive
    return operands + ([target_directory] if target_directory else []), name in {"rm", "mv"}


def _terminal_managed_path(token: _ShellToken, cwd: Path | None, destructive: bool = False) -> str | None:
    if token.dynamic:
        raise _UnresolvedWrite("unresolved write target")
    if cwd is None and not Path(token.text).is_absolute():
        raise _UnresolvedWrite("relative write target without a known terminal working directory")
    try:
        # Tilde expansion already happened in the lexer, respecting quotes.
        path = ((cwd or Path("/")) / token.text).resolve()
    except (OSError, RuntimeError, ValueError) as exc:
        raise _UnresolvedWrite("unresolvable write target") from exc
    if _is_managed(str(path)):
        return str(path)
    root = MANAGED_ROOT.resolve()
    if destructive and root.is_relative_to(path):
        return str(path)
    if path.is_relative_to(root):
        parts = path.relative_to(root).parts
        if parts and parts[-1] == "skills" and "skills" not in parts[:-1]:
            return str(path)
        if destructive and (not parts or parts == ("profiles",) or
                            (len(parts) == 2 and parts[0] == "profiles")):
            return str(path)
    return None


def _has_managed_reference(command: str, cwd: Path | None) -> bool:
    """Best-effort fallback for opaque syntax, never a shell expansion engine."""
    if re.search(r"\$(?:HERMES_SKILL_DIR\b|\{HERMES_SKILL_DIR\b)", command):
        return True
    home = os.path.expanduser("~")
    text = command.replace("${HOME}", home).replace("$HOME/", home + "/")
    candidates = re.findall(r"[^\s'\"`;|&<>()=]*[/~][^\s'\"`;|&<>()]*", text)
    candidates += re.findall(r"[~/][^\s'\"`;|&<>()]*", text)  # Also -t/path and inline code.
    for quote in ("'", '"'):
        candidates.extend(value for value in re.findall(quote + "([^" + quote + "]*)" + quote, text)
                          if value.startswith(("/", "~")))
    for value in candidates:
        try:
            value = os.path.expanduser(value)
            path = ((cwd or Path("/")) / value).resolve()
            # Include managed containers, but not arbitrary ancestors such as /tmp.
            if _terminal_managed_path(_ShellToken(value), cwd, destructive=path.is_relative_to(MANAGED_ROOT)):
                return True
        except (OSError, RuntimeError, ValueError):
            continue
    return False


def _guard_terminal(command: str, args: Mapping) -> dict[str, str] | None:
    # A persistent terminal need not share the plugin process's working directory.
    cwd = None
    try:
        cwd_text = args.get("workdir") or args.get("cwd")
        if isinstance(cwd_text, str) and not any(char in cwd_text for char in "$`"):
            explicit_cwd = Path(cwd_text).expanduser()
            if explicit_cwd.is_absolute():
                cwd = explicit_cwd.resolve()
        words: list[_ShellToken] = []
        tokens = iter([*_shell_tokens(command), _ShellToken(";", operator=True)])
        for token in tokens:
            if not token.operator:
                words.append(token)
                continue
            if token.text in {";", "&&", "||", "|", "|&", "&", "\n"}:
                words = _unwrap_command(words)
                if words and words[0].text in {"cd", "pushd", "popd"}:
                    # Conditional success, pipelines and CDPATH make a single new
                    # cwd unsafe to assume. Only subsequent relative writes care.
                    cwd = None
                targets, destructive = _command_write_targets(words, cwd)
                for target in targets:
                    managed = _terminal_managed_path(target, cwd, destructive)
                    if managed:
                        return _block(managed)
                words = []
                continue
            target = next(tokens, None)
            if target is None or target.operator:
                raise ValueError("missing literal redirection target")
            op = token.text.lstrip("0123456789")
            if op in {">&", "<&"} and (target.text.isdecimal() or target.text == "-"):
                continue  # File descriptor duplication/closure, not a path.
            if op != "<":
                managed = _terminal_managed_path(target, cwd)
                if managed:
                    return _block(managed)
        return None
    except (OSError, RuntimeError, ValueError) as exc:
        if not isinstance(exc, _UnresolvedWrite) and not _has_managed_reference(command, cwd):
            return None  # General command approval belongs to terminal policy.
        return {
            "action": "block",
            "message": f"Conservatively blocked terminal command: {exc}. "
                       "Use literal commands and write targets with an explicit workdir; "
                       "maintainer-owned skills are read-only.",
        }


def _is_managed(path_text: str) -> bool:
    """True when the path resolves into a tracked skill root (not learned/)."""
    try:
        resolved = Path(os.path.expanduser(path_text)).resolve()
    except (OSError, RuntimeError, ValueError):
        return False
    try:
        rel = resolved.relative_to(MANAGED_ROOT)
    except ValueError:
        return False
    parts = rel.parts
    if "skills" not in parts:
        return False
    after = parts[parts.index("skills") + 1:]
    return bool(after) and after[0] != LEARNED_CATEGORY


def _block(path_text: str) -> dict[str, str]:
    return {
        "action": "block",
        "message": (
            f"{path_text} is a maintainer-owned skill file. A procedure that no "
            "longer matches the runtime is REPORTED in your reply, never patched; "
            "runtime-authored skills belong under learned/."
        ),
    }


def _guard_managed_skill_writes(**kwargs: Any) -> dict[str, str] | None:
    tool_name = kwargs.get("tool_name")
    args = kwargs.get("args")
    if not isinstance(args, Mapping):
        return None

    if tool_name in _FILE_WRITE_TOOLS:
        path_text = args.get("path")
        if isinstance(path_text, str) and _is_managed(path_text):
            return _block(path_text)
        patch_text = args.get("patch")
        if isinstance(patch_text, str):
            for line in patch_text.splitlines():
                for prefix in ("*** Update File: ", "*** Add File: ", "*** Delete File: "):
                    if line.startswith(prefix) and _is_managed(line[len(prefix):].strip()):
                        return _block(line[len(prefix):].strip())
        return None

    if tool_name == "skill_manage":
        if args.get("action") == "create":
            return None
        for key in ("name", "path", "file_path"):
            value = args.get(key)
            if isinstance(value, str) and "/" in value and _is_managed(value):
                return _block(value)
        return None

    if tool_name == "terminal":
        command = args.get("command")
        if isinstance(command, str):
            return _guard_terminal(command, args)
    return None


def register(ctx: Any) -> None:
    """Register the write guard (placement is skills.create_dir)."""
    ctx.register_hook("pre_tool_call", _guard_managed_skill_writes)
