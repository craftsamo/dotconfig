# hermes/ — maintainer rules (for OpenCode)

Version-controlled, non-secret **Hermes Agent** config. `../install.sh` symlinks
these into `~/.hermes/`; Hermes reads `~/.hermes/`, never `~/.config`. This file
is guidance for the agent maintaining this subtree — **not** Hermes runtime config.
Authoritative depth: `README.md` (mechanics) and `PROFILES.md` (multi-agent design).

## Critical rules

- **Edit here, never `~/.hermes/…`.** Those are symlinks back to this repo. New
  files need `../install.sh` to link them; `link()` never overwrites a real file
  (prints `WARN … not overwriting` and skips). Adopt existing real files via the
  move-then-`install.sh` steps in `README.md`.
- **No secrets, no `.env`.** Keys live in the macOS Keychain, injected by the
  `bin/hermes` shim. See the `keychain-secrets` skill / `opencode/instructions/secrets.md`.
- **`config.yaml` is rewritten by Hermes on load.** Expect re-serialization churn;
  match Hermes' output format (block style, key order), keep diffs minimal — don't
  hand-reformat or alphabetize.
- **`platform_toolsets.<platform>` is the effective tool allowlist.** Keep it granular;
  `hermes-cli` / `hermes-telegram` expand to a broad surface and strip default-off
  tools such as `video` / `video_gen`. Mirror the role in top-level `toolsets`, but
  remember that top-level `kanban` is also the front-door runtime gate. Dispatcher
  workers receive `kanban` automatically; their dormant Telegram / Discord lists stay
  empty, and `no_mcp` prevents accidental inheritance of future global MCP servers.
- **`SOUL.md` = persona only** (voice/posture), per-profile (`HERMES_HOME`). No
  project rules/paths/commands there. Headings aren't parsed (verbatim inject).
- **Keep `default` neutral** — every `--clone` inherits its `config.yaml`.
  Specialized personas, bots, and cron belong in named profiles.
- **OAuth logins from `default` only** (`hermes model`, no `-p`). Codex / Copilot /
  xAI creds are inherited read-only by every profile (Anthropic native resolves
  separately via the global Claude Code credential/token); running `hermes model`
  inside a worker writes that profile's `auth.json` and shadows the inherited creds.
- **Anthropic account mapping — do not cross the streams.** Hermes' resolver
  (`resolve_anthropic_token()`) ALWAYS prefers the default Keychain entry
  `Claude Code-credentials` over the credential pool (pool entries and
  `suppressed_sources` never override it). That default entry must stay logged
  into the **Hermes** account (itourui). OpenCode runs on the **sub account**
  (craftsamo) via the `opencode-claude-auth` plugin pinned to the suffixed entry
  `Claude Code-credentials-aab5ffbd` (`CLAUDE_CONFIG_DIR=~/.claude-sub`,
  alias `claude-sub`). A plain `claude /login` re-login therefore changes
  **Hermes'** account, not OpenCode's — after one, verify with
  `security find-generic-password -s "Claude Code-credentials"` + the OAuth
  profile endpoint before assuming the split still holds.
- **Operating policy lives in `agent.system_prompt`** (per-profile, always-on);
  detailed playbooks are per-profile skills. `SOUL.md` stays persona-only. Do **not**
  run `/personality` on a profile — it shares the `agent.system_prompt` slot and
  silently overwrites the operating contract (the messaging assistant is most at risk).
- **Media stack lives in `plugins/`.** Backends are chosen via `*_gen.provider` /
  `plugins.enabled`. Video analysis runs through the `video-analyze-mimo`
  tool-override (config `video_analyze.model`) so `auxiliary.vision` can stay
  `auto` — **pinning `auxiliary.vision` to a video-capable model disables the
  main model's native image vision.** Custom top-level keys (e.g. `video_analyze:`)
  survive Hermes' config rewrites (`_deep_merge` keeps user keys). Voice routes the
  same way: `tts/tts-fallback` + `transcription/stt-fallback` chains, picked via
  `tts.provider` / `stt.provider` + `*.fallback.chain` (custom keys preserved).
- **Worker terminal approvals cannot prompt — a flagged command just fails.** The
  dispatcher runs workers with `stdin=DEVNULL` but still sets
  `HERMES_INTERACTIVE=1`, so `approvals.mode: manual` reaches EOF, denies, and the
  tool returns `status: "blocked"`. The guard reads only the OUTER command, never
  inside a script — so `./scripts/x.sh`, `bash x.sh`, `opencode run`, `npx
  hyperframes …`, `ffmpeg`, `git commit`, non-force `git push`, `gh pr create`,
  `xurl` and `python3 script.py` all pass. What trips it: inline interpreters
  (`bash -c`, `python3 -c`, `node -e`), `find -delete`, `chmod +x … && ./…`,
  recursive `rm -rf`, `git reset --hard`, `git clean -f`, force push. Write worker
  playbooks around scripts and wrapper CLIs, never inline one-liners.
  `command_allowlist` is the escape hatch (exact match or fnmatch glob against the
  WHOLE command; skipped when it contains `&&` `|` `>` `;`) and stays empty on
  purpose — allowing `bash -c *` would reopen exactly what the guard exists to
  catch. The hardline floor (`rm -rf /`, `$HOME`, system dirs) blocks regardless.
- **HyperFrames skills live outside the repo, on purpose.** `creator` reaches the
  `hyperframes*` / `media-use` playbooks through `skills.external_dirs`
  (`~/.agents/skills`) — a harness-neutral store owned by `hyperframes skills
  update` and shared with Claude Code / Codex / Gemini, so it stays untracked.
  Never symlink them into `profiles/creator/skills/`: the CLI already relocated
  the store once (`~/.claude/skills` → `~/.agents/skills`) and the relative links
  broke silently. A fresh machine needs `hyperframes skills update` before creator
  can load them. Note that a bare `hyperframes skills` **installs** rather than
  reports — verify with `hermes -p creator skills list` instead.

## Layout

```
config.yaml          # model/providers, toolsets, agent settings (Hermes-rewritten)
SOUL.md              # default persona (prompt slot #1)
mcp.json             # MCP servers ({} = none)
cron/                # jobs.json tracked; output/ + .tick.lock ignored
skills/              # shared maintainer-owned skills tracked
  orchestration/     # orchestration skill (SKILL.md + references/<approach>.md) — shared
                     #   front-door playbook (default native; assistant via ~/.hermes/skills
                     #   external dir; Telegram chat-wide auto-load)
  workspaces/        # ~/Workspaces data-skill cluster (people/pp, household-budget/hb,
                     #   projects/pj, message-reply, scaffold) + _cross.py (shared cross-skill
                     #   contract, imported not executed; siblings call each other's CLI,
                     #   never each other's DB; scaffold is a helper outside the contract)
                     # (creative/ moved to profiles/creator/skills — creator owns media)
  learned/           # runtime-authored adaptive skills; mutable and ignored
plugins/             # backend chains (image/video gen) + tool overrides; source tracked, __pycache__ ignored
launchd/             # LaunchAgents: assistant gateway + headless AivisSpeech engine
profiles/<name>/     # assistant, planner, engineer, researcher, searcher, creator, writer, marketer
  - config.yaml      # model/fallback + agent.system_prompt (operating contract)
  - profile.yaml     # routing description (kanban/delegation)
  - SOUL.md          # per-profile persona (BASE + role posture)
  - skills/          # per-profile skills. Every worker has exactly ONE
                     #   root pipeline skill `<profile>-pipeline` (lifecycle +
                     #   capability router, auto-loaded by its operating contract)
                     #   + directly selectable LEAF technics under skills/technic/,
                     #   pinned per task via kanban_create skills:[...]. A technic's
                     #   references are modes only when tools, spend class and QA
                     #   stay the same; styles/presets/formats remain references.
                     #   (searcher: deep-retrieval is a deprecated technic stub;
                     #   creator: canonical creator-* image/video/audio/music/
                     #   browser-motion/diagram/editorial/icon/card/meme/text-art/
                     #   pixel/sourcing leaves;
                     #   writer: Japanese stack via the curated external-skills
                     #   symlink dir / marketer: + upstream social-media/xurl;
                     #   engineer and creator group technics under skills/technic/
                     #   — Hermes walks nested dirs and shows the parent as the
                     #   category, unlike the flat shared agents/skills tree;
                     #   planner-pipeline owns outline schema + granularity rubric;
                     #   assistant keeps only its surface skills — desks/ holds
                     #   topic-bound personal-desk / project-desk / brainstorm
                     #   (Inline-only; worker work spins into a new topic), while
                     #   orchestration lives in the shared skills/ tree above;
                     #   every profile's learned/ holds mutable runtime-authored
                     #   skills and is never a dispatch or Git ownership surface)
  - cron/            # per-profile scheduled jobs (jobs.json; placeholder if empty)
                     # assistant/scripts/ holds cron scripts incl.
                     # kanban-scheduled-sweeper.sh and kanban-orphan-watchdog.sh
setup.sh README.md PROFILES.md
```

## Profiles

default (CLI front door — assistant's CLI counterpart, neutral persona) +
assistant (messaging front door, hosts the
gateway/dispatcher) + planner / engineer / researcher / searcher / creator /
writer / marketer (kanban workers; engineer converses with the assistant via kanban block round-trips
under a structured comment protocol — Authority presets A1/A2/A3,
`STATE:`/`Q<n>:`/`DECISION(Q<n>):`/`PROGRESS:`/`AUTHORITY+:`/`REVIEW:`
(human sign-off gate) markers, plus scheduled parking in `scheduled` via
`SCHEDULED: until=` comments and the assistant sweeper cron — multi-card
plans run through the Planner tree: a planner card (Claude Fable 5,
plan-only) delivers a dependency-graph outline YAML, the user approves it
in chat, and the assistant registers the cards topologically with
idempotency keys (`auto_decompose` is OFF — the upstream aux decomposer's
prompt is hardcoded and can't carry our TaskSpec/grant conventions); all
workers use the continuation-card fan-out pattern — engineer drives
OpenCode through a P0-plan + per-unit-fork loop with permission /
question bridges; creator speaks the same comment protocol with a Budget
grant (generation-spend caps), marketer with a Publish grant (absent =
draft-only; posting needs verbatim approval or in-cap P1) — see PROFILES.md
"Engineer dialogue loop";
workers fan out sub-tasks via kanban_create). Tracked per
profile: `config.yaml`, `profile.yaml`, `SOUL.md`, `skills/`, `.no-bundled-skills`.
Create with `hermes profile create <name> --description "…"`, then adopt into the
repo (move real files → `../install.sh`); see `README.md` / `PROFILES.md`.

## Tracked vs ignored

Tracked: config / SOUL / `profile.yaml`, `plugins/` source, `cron/jobs.json`,
`launchd/`, docs. Ignored (see `../.gitignore`): `auth.json`, `.env`,
`memories/`, `sessions/`, `state.db*`, `logs/`, `workspace/`, `.hub/`,
`.curator_state`, `.usage*`, `cron/output/`, `cron/ticker_*`, `**/__pycache__/`,
`*.pyc`. Never commit secrets, state, or host-rendered plists.

**Skill ownership follows the directory type.** Shared `orchestration/` and
`workspaces/`, every worker's `<profile>-pipeline/` and `technic/`, and the
assistant's `desks/` are maintainer-owned and tracked normally. Runtime creates
are forced into `learned/` by the `skill-topology` plugin; `learned/`, external
skills and Hermes bookkeeping stay ignored. Do not use `skip-worktree` for
managed skills: their changes must remain visible in `git status`. Promotion
from `learned/` to `technic/` is an explicit review step; move the complete
package, normalize its technic metadata and routing, pin it against curator
writes on the current machine, then commit it.

## Commands

- `./setup.sh` — install/refresh the hermes binary (uv venv); idempotent.
- `./scripts/validate-profile-skills.py --all` — validate managed/learned skill
  topology, metadata, routing registries and Git ownership; add `--strict-git`
  in a staged/clean tree to fail on managed files that are still untracked.
- `../install.sh` — create the `~/.hermes/` symlinks (run after adding files).
- `hermes update` — git pull + re-sync (use this to update, not setup.sh).
- `hermes doctor` — validate providers / model tiers.
- `launchd/aivis-launchctl.sh {install,status,uninstall}` — headless AivisSpeech
  Engine LaunchAgent (execs a `hermes-aivis-engine` hardlink shim; backs the
  `aivis` TTS provider on `127.0.0.1:10101`). Re-run `install` after AivisSpeech updates.
- `launchd/gateway-launchctl.sh {install,status,uninstall}` — gateway LaunchAgent,
  **one host only** (one bot token = one live connection). Telegram-only for now
  (workaround for upstream #40695; don't re-enable Discord until fixed).
  `install` re-renders + reloads = **restart** (new process re-reads `config.yaml`);
  to apply config you can also send **`/restart`** in chat (drain → `KeepAlive`
  respawns one). **Stop = `uninstall`** (plist `KeepAlive:true`; a plain `kill` just
  respawns). **Never** run `hermes gateway run`/`restart` in a terminal while it's
  loaded — the 2nd poller causes Telegram `getUpdates` 409 conflicts
  (verify a single instance: `pgrep -fl 'gateway run'` ⇒ exactly 1).

## Commits

Conventional Commits with the `(hermes)` scope: `feat(hermes): …`,
`chore(hermes): …`, `docs(hermes): …`, `refactor(hermes): …`.
