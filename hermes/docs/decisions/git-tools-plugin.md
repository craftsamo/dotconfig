# Git runs on one package, guarded here

Status: in force
Owner doc: docs/git-tools.md

## Decision

The Assistant reaches git through craft-agent/git-tools, pinned to a release
commit as a Hermes native plugin. OpenCode loads the same release from npm.

- **Its card is the package's.** Each write shows its targets and pins what
  was shown into the call; a changed target makes it stale. That is the
  guarantee our own plugins get from `card.py` and a digest check, so the
  package's card is accepted as it is.
- **A standing answer covers the tool and its target.** "Always" or
  "session" lets later calls of that tool on that target run unasked, as in
  github-tools. A write the user wants asked again is answered "once".
- **The guard is ours.** `plugins/guards/git-tools-guard` refuses writes where
  no person can answer, every inbound A2A `git_*` call and the ways around the
  package. It also restricts terminal git to reads, fetch, fast-forward-only
  pull and clone, refusing configuration and program-running overrides. The
  pin requires it and the profile validator refuses enabling the package
  without it; a block wins over the package's approve.
- **The Assistant reads and removes landed worktrees; OpenCode commits and
  pushes.** The Assistant has only `repo` and `worktree`, not `commit`,
  `rebase` or `push`. It commissions target code work through the engineering
  pipeline, never writes that code itself.
- **One worktree implementation.** OpenCode, the Assistant and the workspace
  plugin share the package's layout and landed-branch rule, rather than
  keeping independent proofs of when a branch may be deleted. The workspace
  plugin follows the package's hook policy with a minimal environment: hooks
  run where the person's command would, but never receive caller secrets.
  Only the package's own plumbing turns hooks off.

## Why

One implementation serves every harness the person uses. Sharing the worktree
layout and landed rule avoids divergent cleanup decisions; keeping the
package's hooks while passing only an allowlisted environment preserves the
repository's own checks without exposing the gateway's secrets.

## Consequences

- A new release is a pin change in `scripts/external-plugins.json` and
  `opencode/opencode.jsonc` together; a test keeps them equal.
- Package skills follow the enabled toolsets; the Assistant does not need
  published-text rules because it cannot push.
- The terminal guard is not a sandbox: repository config and hooks remain
  executable code, with the limits recorded in [git-tools.md](../git-tools.md).
