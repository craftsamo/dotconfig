# AGENTS

Rules for agents working in this dotconfig repo (`~/.config`). Subtree-specific
rules live in nested `AGENTS.md` files — read them when your task touches that area.

## Who reads what

Documentation here is split by audience. Put new content where its reader
actually loads it.

| Reader | Loads | How |
|---|---|---|
| Maintainer — OpenCode, or a Hermes profile doing repo upkeep (Engineer via OpenCode, the Assistant's Admin topic) | this file, then the subtree's `AGENTS.md` | on demand, when a task touches the subtree |
| OpenCode, every session | `opencode/AGENTS.md`, `opencode/instructions/*.md` | global instructions (`opencode.jsonc`) |
| Hermes profiles at runtime | their `config.yaml` (`agent.system_prompt`), `SOUL.md`, skills | per `HERMES_HOME`; never this repo's docs |
| Hermes Assistant at runtime | also `~/Workspaces/AGENTS.md` (private overlay) | its `terminal.cwd` is `~/Workspaces` |
| Other CLIs (Claude, Codex, Gemini, Grok, Copilot) | `<tool>/` instruction files | symlinked to each tool's home by `install.sh` |

So: rules for editing the repo go in `AGENTS.md`; mechanics and design go in
the subtree's `README.md` / `docs/`; knowledge a Hermes profile needs while
working goes into that profile's skill references (or `~/Workspaces/AGENTS.md`
for rules of the Assistant's working area), because Hermes never reads the
repo docs.

## Subtree: hermes/

When a task touches files under `hermes/**` (Hermes Agent config), read
`@hermes/AGENTS.md` first and follow it. Load it on demand (don't preempt).
