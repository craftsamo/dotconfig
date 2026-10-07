# opencode

XDG native: OpenCode 2 reads `~/.config/opencode/` directly — no symlinks
needed. Installed from the `anomalyco/tap/opencode-v2` formula (see the
[`Brewfile`](../Brewfile)).

## User-managed content

| Path              | Purpose                                                     |
| ----------------- | ----------------------------------------------------------- |
| `opencode.jsonc`  | main configuration (models, permissions, MCP, ...)          |
| `cli.json`        | terminal UI preferences (theme, keybinds, session view)     |
| `AGENTS.md`       | global instructions, loaded into every session              |
| `agent/`          | custom agents / subagents (`*.md`)                          |
| `command/`        | custom slash commands (`*.md`)                              |
| `plugins/`        | local plugins (`*.ts`), auto-discovered                     |
| `lib/`            | code imported by plugins (not scanned by OpenCode)          |
| `skills/`         | opencode-only skills (`<name>/SKILL.md`)                    |
| `package.json`    | plugin dependencies (zod), installed by `install.sh --deps` |
| `opencode-quota/` | quota plugin settings (`quota-toast.jsonc`)                 |

A fresh clone needs `./install.sh --deps` once: OpenCode 2 does not install
config-directory dependencies, and without `node_modules/zod` the custom-tools
plugin fails to load. The `opencode-v2` formula conflicts with the 1.x
`opencode` formula; uninstall that first on a machine that still has it.

Custom tools live in `lib/custom-tools/<file>.ts` and are registered by
`plugins/custom-tools.ts`, which exports both a V1 `server()` and a V2
`setup()`. Tool IDs keep the `<file>_<export>` form (`git_secret_scan`,
`x_search`, ...), matching the permission keys in `opencode.jsonc`. Do not
add a `tools/` directory: V1 would register the same IDs twice and V2 does
not load it. Keep subdirectories out of `plugins/`; V2 loads each one as a
plugin package.

All global instructions live in `AGENTS.md`. Do not reintroduce an
`instructions` array: OpenCode V2 accepts the key but does not load its files
(anomalyco/opencode#51341).

## Delegation and progress in V2

V2's `subagent` tool takes `agent`, not V1's `task` / `subagent_type`.
The files remain under `agent/` and retain supported legacy frontmatter;
V2 normalizes those settings without rewriting them.

`hidden: true` hides an agent from both interactive discovery and the model's
subagent catalog. The twelve specialist subagents are therefore visible;
the four API-only `hermes-*` primary agents remain hidden. Visibility is not
authorization: caller-specific permissions decide which specialists may run.

- Plan allows read-only exploration, research, diagnosis, and review, but not
  `general`, `worker`, or `verifier` (which can apply formatters).
- Debug and Review exclude editing agents and ask `verifier` for checks only,
  never formatter application. Build may request scoped formatter application.
- Plan and the built-in Explore explicitly deny edits, overriding the global
  `edit: ask`. Plan retains its exception for `~/.opencode/plan/*`; writing a
  plan file still requires the user's explicit request.

New subagents use their configured model, otherwise the parent's model. A
user-requested per-call `model` override takes precedence. General and the
built-in Explore have no model configured and inherit the parent; use the
specialists for their role and cheaper default models. Primary sessions retain
their selected model when switching agents; the agent configuration is not a
guarantee of the model currently selected in a session.

V2 has no native Todo tool. Keep ephemeral execution steps in the conversation
as `Phase{N}.{m} - <task> (executor)`, updating pending / in-progress / completed /
blocked statuses and restating unfinished work at handoffs. Plan asks the user
to switch to Build before execution. Do not create local TODO files or claim
that a native list was registered. Durable work still uses GitHub Projects
when requested; no Todo plugin is installed for this workaround.

Empty directories carry a `.gitkeep` so the skeleton survives a fresh clone.

`skills/` holds only the skills that depend on opencode itself — its
subagents, custom tools, or the Plan/Build handoff. Skills any agent can
follow live in [`agents/curated/`](../agents/README.md) and are picked up here
too, since opencode scans `~/.agents/skills` alongside this directory.

## Accounts

- **Anthropic** (Claude Pro/Max, the sub account): OpenCode's own OAuth login
  through the `@ex-machina/opencode-anthropic-auth` plugin. It never reads or
  writes Claude Code's Keychain entries, so Hermes' account (the default
  `Claude Code-credentials` entry) and Claude Code stay untouched. Log in from
  a browser signed into the sub account:
  `opencode auth login anthropic --method claude-max`.
- **OpenAI**: built-in ChatGPT login,
  `opencode auth login openai --method chatgpt-browser`.
- **xAI** (`x_search`): built-in SuperGrok login,
  `opencode auth login xai --method device`; `XAI_API_KEY` wins when set.

`opencode auth list` shows the stored logins; `opencode auth switch` picks
another one. Credentials live in OpenCode's database, not in `auth.json`.

## Web access

The shared background service listens on `127.0.0.1:49374` and serves the web
UI as well; `opencode service status|restart|stop` manage it. It generates and
keeps its own password, which local clients read from its registration. To
reach it from other devices, expose it to the tailnet with Tailscale Serve
instead of binding OpenCode to the LAN:

```sh
tailscale serve --bg 127.0.0.1:49374
```

Then sign a browser or phone in with a one-time link (five minutes, single
use; the QR code encodes the first link):

```sh
opencode pair --url https://<machine>.<tailnet>.ts.net
```

Ignore the hint to `opencode service set hostname 0.0.0.0`: that exposes the
service to the whole LAN. Rotating the password (`opencode service set
password ...`) revokes every paired browser.

`opencode reload` (tmux `prefix O`) rebuilds configuration for every loaded
project; configuration and plugin files are also watched and reloaded on
change. After changing Keychain secrets, run `opencode service restart`: the
service keeps the environment of the client that started it.

`opencode serve` (a foreground, private server) still exists; the secret shim
refuses it unless `OPENCODE_PASSWORD` or `OPENCODE_SERVER_PASSWORD` is set, so
it is never started unauthenticated.

## Ignored machine state

`node_modules/` and the lockfiles — see [`.gitignore`](./.gitignore).
