# GitHub tools

The Assistant's access to GitHub: reading and changing Issues, Projects boards,
pull requests, repositories (labels, milestones, rulesets), releases and
Actions runs, each write after the user answers its approval card. It runs on
the third-party package [craft-agent/github-tools](https://github.com/craft-agent/github-tools),
the same release the person's OpenCode loads, and a dotconfig guard adds what
this setup requires of every access plugin. Why the package and not a plugin
of our own: [decision](decisions/github-tools-plugin.md). Common rules:
[access-common.md](access-common.md). Part of the Hermes design docs — index:
[`PROFILES.md`](../PROFILES.md).

## Shape

| Piece                                                                                  | Home                                                                                                          | Reader    |
| -------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- | --------- |
| Tools (`github_<area>_<verb>`), approval card, skills                                  | the package, installed at `~/.hermes/plugins/github-tools`                                                    | Assistant |
| The pinned release                                                                     | `scripts/external-plugins.json`, installed by `scripts/external-plugins.py`                                   | people    |
| Refusal where no person can answer, terminal and installed-copy guards, progress lines | `plugins/guards/github-tools-guard`                                                                           | Assistant |
| Settings (toolsets, card language)                                                     | `plugins.entries.github-tools.settings` in the Assistant's config                                             | Assistant |
| How the tools are used                                                                 | the package's skills, `github-tools:<name>`: one per toolset, and `planning`                                  | Assistant |
| What the user expects of tracking, pull requests and repositories                      | the Assistant's technics `github-tracking` and `github`                                                       | Assistant |
| When the Assistant uses it in Chat                                                     | the Chat reference `github.md`                                                                                | Assistant |
| OpenCode                                                                               | `opencode/opencode.jsonc` (the npm package), writes denied in Hermes-driven runs ([opencode.md](opencode.md)) | OpenCode  |

Only the Assistant has it. The settings enable all six toolsets (`issues`,
`pull_requests`, `projects`, `repos`, `releases`, `actions`) with
`language: ja`, and the toolsets are in `toolsets` and the `cli`, `telegram`
and `discord` lists of `platform_toolsets`, never `a2a`.

## Approval

Every write is held by the package's own `pre_tool_call` card: what the call
will change and on which target, fitted to the surface the turn runs on. What
the card showed is pinned into the call, and the call fails as `stale` if the
target changed since. An "always" or "session" answer covers the tool and its
target (a repository or a board), not the exact request; a write the user
wants asked again is answered "once". A job's routine updates (ticking a body,
moving a Status) are meant to run on one "session" answer per tool and board.
There are no mandates: a write never runs without a card.

## Guard

`github-tools-guard` adds, for every `github_*` tool:

- **No card where no person can answer.** A write (every tool but the known
  `github_*_read` ones, so a tool added later is held too) is refused under
  YOLO, `approvals.mode: off`, cron, a single query and the unattended
  platforms (`plugins/_shared/human_gate.py`). A block from any plugin beats an
  approve, so the package's card is never drawn there.
- **No inbound A2A.** Every `github_*` call, reads included, is refused for an
  inbound A2A request.
- **No way around the tools.** Terminal calls are blocked when they run a `gh`
  write, `gh api`, print the login's token, define a `gh` alias or install an
  extension, or run the package's command line or MCP server, or name its
  installed copy; file tools are blocked on that copy too. Paths are also
  matched by their real path
  ([bypass guard](access-common.md#bypass-guard-ways-around-the-tool)). `gh`
  reads stay open.
- **Progress lines** for all its tools, naming the operation only, never a
  title, a body or a path.

## Runs

An OpenCode run the Assistant drives reads GitHub (`github_*_read`); a write
run also asks the caller to open its PR (`github_pr_create`), link its stack
(`github_stack_link`) and set its PR's labels, assignees, reviewers and
milestone only (`github_pr_edit`). A create with board arguments
(`project`/`fields`) is refused `once`. Every other `github_*` write is denied
in the run, and the caller can only reject an Issue or board write, or a
`github_pr_edit` that carries anything beyond those four (title, body, base,
closing issues, attachments), never approve it. The Assistant reads the
issue bound to the run and mirrors progress to it with its own tools and
cards ([opencode.md](opencode.md), [decision](decisions/issue-driven-engineering.md)).

## Technics

The package's skills say how each tool works; the Assistant's technic
`github-tracking` holds this user's conventions for Issues and boards (own /
shared / other tiers, wording, setting up a board, mirroring a run), and
`github` holds the habits for pull requests, merges and repositories. Neither
repeats the tool mechanics.

## Install and update

`scripts/external-plugins.py install` (from the live checkout) runs
`hermes plugins install craft-agent/github-tools --ref <commit> --force
--no-deps --no-enable` for the commit `external-plugins.json` pins; `status`
compares the installed commit with the pin. The runtime clones the release
commit (which carries the built `dist/`), verifies it and records the pin in
`~/.hermes/plugins/.install-metadata.json`; `--force` accepts the security
scan's caution on the bundled `dist/cli.js`. Never install it by hand at
another commit or link it from a checkout.

A new release: change `version` and `commit` in `external-plugins.json` and the
npm version in `opencode.jsonc` together, run `install`, restart the gateway
and `opencode service restart`.

The OpenCode plugin and the Hermes run policy go live together: restart the
gateway (`launchd/gateway-launchctl.sh restart`) before `opencode service
restart`, because until the gateway has loaded the run policy a Hermes-driven
build run sees the github-tools writes as asks the caller could approve.

## Setup

1. Install the plugin (above) and enable `github-tools` and
   `github-tools-guard` in the Assistant's `plugins.enabled` (the profile
   validator refuses the first without the second), with the settings and
   toolsets above.
2. Board tools need the `project` scope on the person's `gh` login:
   `gh auth refresh -s project`.
3. Restart the gateway.

## By hand

The Roadmap view's date fields (start and target) are set in the board's own
UI: no tool writes them.
