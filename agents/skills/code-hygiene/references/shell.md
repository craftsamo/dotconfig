# Shell (zsh, bash, sh)

Read with `SKILL.md`; `.shellcheckrc`, `.editorconfig` and the script's
shebang win over everything here. Identify the dialect from the shebang or
the sourcing shell before applying any rule: zsh, bash and POSIX `sh` differ
in ways that silently change behavior.

## Constants and variables

- Values used throughout a script (paths, URLs, retry counts, names) go to
  the top. Use `readonly NAME=value` (zsh: `typeset -r`) only in a script
  that is executed; in a file that is sourced, use a plain assignment, since
  sourcing it again (a reloaded `.zshrc`, a test that sources a library
  twice) fails on the read-only variable.
- Variables inside functions are declared `local` only when no caller reads
  them afterwards; check every caller first.
- Do not turn an environment override (`: "${FOO:=default}"`) into a constant.

## Doc comments

- A comment describing a function moves directly above it as a header block.
  Use the repository's form; when there is none, follow the Google shell
  style headings and fill only what the comment already said: a description,
  then `Globals:`, `Arguments:`, `Outputs:`, `Returns:`.
- A comment describing the script moves under the shebang.
- Comments inside function bodies stay inline.

## Quoting and syntax

- bash and sh: quote expansions (`"$var"`, `"$@"`) unless the code depends on
  word splitting, globbing or an empty value disappearing: `cmd $opt` passes
  no argument when `opt` is empty, `cmd "$opt"` passes an empty one, and a
  variable holding several options (`cp $CP_FLAGS`) needs the split. When
  any of these can apply, leave it and report it. Quoting the right side of
  a plain assignment (`x=$1`) changes nothing and is churn; `local` and
  `export` forms split differently across shells, so leave those as they are.
- zsh does not split unquoted parameters by default and indexes arrays from
  1; do not apply bash quoting fixes or 0-based indexing to zsh code.
- `$(...)` replaces backticks safely when the command inside holds no
  backslash or nested backtick; inside backticks `\$`, `\\` and `` \` `` lose
  one level of escaping, so such a command is rewritten only with that
  escaping adjusted.
- Keep `[ ]` in POSIX `sh` scripts; `[[ ]]` is for bash and zsh only.
- Keep the option handling a zsh function already has (`emulate -L zsh`,
  `setopt local_options`); adding it changes which options apply inside.

## Files

- Tier A: extracting shared functions into a sibling file that the script
  sources through a path anchored at the script itself, not the working
  directory (`${0:A:h}` in zsh, `$(dirname -- "${BASH_SOURCE[0]}")` in bash).
- Tier B: moving functions into a different directory's library, renaming
  a sourced file, splitting a function others source by name.
- Tier C: entry scripts and anything referenced by path from PATH links,
  launchd/systemd units, cron, Git hooks, CI configuration or other
  repositories; zsh startup files (`.zshrc`, `.zshenv`) and autoloaded
  function directories (the file name is the function name).

## Behavior traps

- Adding `set -e`, `set -u`, `set -o pipefail` or `setopt err_exit` changes
  control flow: report it, never add it during cleanup.
- `local` and `readonly` change scope and mutability; a later assignment to a
  `readonly` aborts the script.
- Replacing `echo` with `printf` changes escape handling and trailing
  newlines.
- Exit codes and stdout are the interface of a script; keep both identical.
- Run `shellcheck` for bash and sh. It does not support zsh; use `zsh -n` for
  a syntax check instead.
