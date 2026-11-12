# Git tools

The Assistant reads repositories and manages worktrees through the third-party
package [craft-agent/git-tools](https://github.com/craft-agent/git-tools), the
same release the person's OpenCode loads. The Hermes native plugin calls the
package's own CLI; a dotconfig guard keeps writes on its approval cards and
target code work in OpenCode. Why this split:
[decision](decisions/git-tools-plugin.md). Common approval and bypass rules:
[access-common.md](access-common.md). Part of the Hermes design docs — index:
[`PROFILES.md`](../PROFILES.md).

## Shape

| Piece                                                                    | Home                                                                        | Reader    |
| ------------------------------------------------------------------------ | --------------------------------------------------------------------------- | --------- |
| Tools, approval cards, CLI and skills                                    | the package, installed at `~/.hermes/plugins/git-tools`                     | Assistant |
| The pinned release                                                       | `scripts/external-plugins.json`, installed by `scripts/external-plugins.py` | people    |
| Human gate, A2A and bypass refusals, terminal git policy, progress lines | `plugins/guards/git-tools-guard`                                            | Assistant |
| Settings                                                                 | `plugins.entries.git-tools.settings` in the Assistant's config              | Assistant |
| How the tools are used                                                   | the package's skills, `git-tools:repo` and `git-tools:worktree`             | Assistant |
| OpenCode                                                                 | `opencode/opencode.jsonc` (the npm package)                                 | OpenCode  |

## Toolsets

The Assistant enables only `repo` and `worktree` (`git-tools-repo` and
`git-tools-worktree`) on `cli`, `telegram` and `discord`, never `a2a`.
`commit`, `rebase` and `push` stay off: committing, rebasing and pushing a
target repository belong to OpenCode, commissioned through the engineering
pipeline. The Assistant never writes target code.

- `git_repo_read`: status, conflicts, conventions and origin.
- `git_worktree_read`: list worktrees.
- `git_worktree_add`: create a worktree under `~/Worktrees`.
- `git_worktree_remove`: remove a worktree, never force it. A branch is deleted
  only once landed: its tip is an ancestor of origin's default branch after a
  fetch, or a merged same-repository PR has that tip as its head.

The package registers `git-tools:repo` and `git-tools:worktree` for the enabled
toolsets. Settings select `toolsets`, `language: ja` and
`worktree_root: ~/Worktrees`. The Assistant needs no published-text rules,
since it cannot push.

## Approval

Every write gets the package's own `pre_tool_call` approval card, showing its
targets. What the card showed is pinned into the call; a changed target makes
the call stale. An "always" or "session" answer covers the tool and its
target, as in github-tools, not just the exact request. Answer "once" for a
write that should be asked again.

The guard (`plugins/guards/git-tools-guard`) adds:

- **No card where no person can answer.** Writes are refused through
  `plugins/_shared/human_gate.py`, including YOLO, approvals off and
  unattended turns. A block beats the package's approve. The pin requires the
  guard, and the profile validator refuses enabling the package without it.
- **No inbound A2A.** Every `git_*` call, reads included, is refused for an
  inbound A2A request.
- **No way around the tools.** The package's CLI, MCP and npm entry points and
  installed directory are blocked, including lexical and real paths and
  profile copies ([bypass guard](access-common.md#bypass-guard-ways-around-the-tool)).
- **Terminal git stays narrow.** Only reads (including list-only forms of
  branch, tag, remote, stash, worktree, config, notes and submodule), `fetch`,
  `pull --ff-only` and `clone` pass. Global `-c`, `--config-env`, `--exec-path`
  and unknown global options, program-running or file-writing options, and
  environment overrides such as `GIT_CONFIG_*`, `GIT_SSH_COMMAND` and
  `GIT_EXTERNAL_DIFF` are blocked. Aliases and unknown subcommands are blocked;
  `git-<command>` and `hub` are judged as git, and `lazygit` and `gitui` are
  blocked outright. The check follows shell wrappers and nested commands.
- **Progress lines** show a read's method or a fixed write label, never a
  path, branch or message.

The terminal check is a pattern match, not a sandbox: it does not read script
contents or cover a repository's own config (`fsmonitor`, `diff.external`)
or the hooks that fetch, pull and clone fire. Its policy lives in
`plugins/guards/git-tools-guard/git_terminal.py`.

The package runs a repository's hooks where the person's own command would
(commit, rebase, push, fetch and removal). It passes git only an allowlisted
environment, so no caller secret reaches git or a hook; hooks are turned off
only for the package's own plumbing.

## Install and update

`scripts/external-plugins.py install` (from the live checkout) runs
`hermes plugins install craft-agent/git-tools --ref <commit> --force
--no-deps --no-enable` at the commit `scripts/external-plugins.json` pins;
`status` compares the installed commit with the pin. Never install another
commit by hand or link a checkout into the plugin directory.

For a new release, change `version` and `commit` in `external-plugins.json`
and the npm version in `opencode/opencode.jsonc` together (a test holds the
versions equal), run `install`, then restart the gateway and
`opencode service restart`.

## Setup

1. Install Node 24 or later and the pinned plugin (above).
2. Enable `git-tools` and `git-tools-guard` in the Assistant's
   `plugins.enabled`. Add `git-tools-repo` and `git-tools-worktree` to
   `toolsets` and the `cli`, `telegram` and `discord` lists of
   `platform_toolsets`, never `a2a`.
3. Set `plugins.entries.git-tools.settings` as in "Toolsets" and restart the
   gateway.

## OpenCode

OpenCode runs the Assistant drives load git-tools through OpenCode's own
config too. The run ruleset and `workspace` / `cleanup`, which use the
package's CLI, are owned by [opencode.md](opencode.md).
