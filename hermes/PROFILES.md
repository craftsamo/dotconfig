# Profiles — multi-agent plan

How this machine runs several Hermes agents that cooperate: two **front
doors** a human talks to, plus named **worker** profiles they delegate to in
the background. This is the design doc; [`README.md`](./README.md) covers the
single-profile mechanics (symlinks, skills, cron, secrets).

A profile is just a separate `HERMES_HOME` (`~/.hermes/profiles/<name>/`) with
its own `config.yaml` / `.env` / `SOUL.md` / `skills/` / `cron/` / state, and a
`~/.local/bin/<name>` alias that runs `hermes -p <name>`. The default profile is
`~/.hermes` itself (it can't be deleted or renamed).

## Topology

```
   human (terminal)            human (Discord / Telegram)
          │                              │
        default ──┐                  assistant ──┐   (runs the gateway + kanban dispatcher)
        (CLI)     │                (~/Workspaces)│
                  │                              │
                  └──────────┬───────────────────┘
                             │ create kanban tasks
                             ▼
                 ~/.hermes/kanban.db  (one shared board)
                             │ dispatcher (in assistant's gateway) spawns
              ┌──────────────┼──────────────┬──────────────┐
              ▼              ▼              ▼              ▼
           searcher      researcher       engineer       creator
           (retrieve)    (synthesize)     (implement)    (produce media)
```

Verified against the source clone
(`~/ghq/github.com/NousResearch/hermes-agent`):

- **One shared board.** The kanban DB is anchored at the base
  `~/.hermes/kanban.db` via `get_default_hermes_root()` — *not* profile-scoped
  (`kanban_db.py:264-284,429-431`). Every profile reads/writes the same board.
- **One gateway powers everything.** The dispatcher runs inside the gateway and
  sweeps **all** boards each tick, regardless of which profile the gateway runs
  as (`gateway/kanban_watchers.py:861-867`). So `assistant`'s gateway dispatches
  tasks created by `default`'s CLI. `default` needs no gateway of its own.
- **Workers are spawned through the PATH `hermes`.** The dispatcher launches
  `hermes -p <worker> … chat -q "work kanban task <id>"` as a subprocess,
  resolving `hermes` via `shutil.which` (so our `bin/hermes` shim is used) and
  inheriting a copy of the gateway's env with `HERMES_HOME` overridden
  (`kanban_db.py:6705-6837,6607`). Workers therefore get the `global` + `hermes`
  Keychain layers injected automatically — **no per-worker secret is needed.**

## Two delegation layers

| | Kanban | `delegate_task` |
| --- | --- | --- |
| Worker | **named profile** (engineer/researcher/searcher/creator) | anonymous subagent |
| Durability | persistent queue, resumable, human-in-loop | synchronous, dies with the turn |
| Requires | a running gateway (the dispatcher) | nothing — fires automatically |
| Use for | cross-agent / long / auditable work | in-turn parallel research or refactor |

**Fallback story:** gateway up → durable named-worker delegation via Kanban.
Gateway down → `default` still parallelizes via `delegate_task` (anonymous,
in-turn). A Kanban worker may itself call `delegate_task` during its run.

## Profile roster

| Profile | Role | Front door | `terminal.cwd` | Toolsets | Gateway | Tracked |
| --- | --- | --- | --- | --- | --- | --- |
| **default** | CLI front door — assistant's CLI counterpart (neutral persona) | CLI | `.` (launch dir) | full + `kanban` | — | yes |
| **assistant** | messaging front door + dispatcher host | Discord/TG | `~/Workspaces` | full + `kanban` | **yes** | yes (token per-machine) |
| **engineer** | implement via OpenCode (git worktree, tests); confirms material decisions through kanban block round-trips | — (worker) | `.` (launch / task ws) | `hermes-cli` | — | yes |
| **researcher** | synthesize / analyze | — (worker) | `.` (launch / task ws) | `file,web` | — | yes |
| **searcher** | fast retrieval (web / x_search); deep multi-hop via `deep-retrieval` + `goal_mode` | — (worker) | `.` (launch / task ws) | `web,x_search` | — | yes |
| **creator** | ALL media production — image, video, GIF, voice, single and batch (front doors only brief and dispatch) | — (worker) | `.` (launch / task ws) | `hermes-cli,video_gen,video` + gen plugins | — | yes |

Role split: **searcher (retrieve) → researcher (synthesize) → engineer
(implement)**, mirroring the `delegate_task` toolset patterns
(`["web"]` / `["file","web"]` / `["terminal","file"]`), with **creator**
(produce media) as a side stage any pipeline can call on.

The org stays **flat by design**: profiles are global and the board is one
shared queue, so "hierarchy" is expressed as routing policy + `parents`
fan-in, not nested profiles. Workers fan out themselves via `kanban_create`
(e.g. engineer dispatches a searcher lookup or a creator asset mid-task);
a live supervising mid-manager isn't possible anyway — block/done
notifications reach gateway chat sessions, never a parent worker.

### Engineer dialogue loop (the four layered loops)

Implementation work runs through four nested loops, each with its own
channel, its own durable state, and its own decision altitude:

| # | Loop | Channel | Durable state | Decides |
| --- | --- | --- | --- | --- |
| L1 requirements | user ↔ assistant | chat + `clarify` (Plan Loop) | chat + session todo | what/why: goal, scope, Authority level |
| L2 detail | assistant ↔ engineer | kanban block round-trips (`Q<n>`/`DECISION`) | kanban comment thread | how (shape): feasibility, plan revision, in-grant calls |
| L3 implementation | engineer ↔ OpenCode | `opencode run` (P0 master-plan session + per-unit forks) | P0 session + git history + plan attachment | how (detail): unit split, tactics, model, verification |
| L4 in-run | OpenCode ↔ its subagents (reviewer/debugger/…) | OpenCode task tool, per the `opencode/` config | subagent sessions | code-level: review findings, root causes |

Three principles hold the stack together: **escalation moves one layer at a
time** (OpenCode never talks to the assistant, the engineer never talks to
the user — each layer translates what it cannot decide into the next layer
up's format); **the engineer is the translation layer** (upward a worker
speaking kanban — `Q<n>`/`DECISION`/Authority; downward an orchestrator
speaking OpenCode — prompts, forks, permission env); **L4 is hands-off**
(the engineer judges results by independent verification, never micromanages
the subagents).

Workers are disposable processes (a `kanban_block` ends the run; unblock
respawns a fresh one), so continuity lives in the durable layers above —
never in a long-running session. In L3 the engineer plans once in a lean
**P0** session (`--agent plan`; unit split + architecture only), then
implements each PR-sized unit in a short-lived **fork** of P0
(`run -s <P0> --fork`), ending every unit with verify → commit →
`PROGRESS:` comment carrying the session ids; review/debug primaries run as
fresh read-only sessions. Two bridges wire L3 to OpenCode's non-interactive
reality (both verified against source): the **Permission Bridge** — bare
`run` auto-rejects every `ask`, so the engineer translates the Authority
grant into an `OPENCODE_PERMISSION` overlay (deep-merged; deny beats
`--auto`) plus `--auto`; and the **Question Bridge** — `run` denies the
question tool, so OpenCode escalates only via its final output text, which
the engineer answers with `run -c` or translates into an L2 block.

The L2 protocol: the task body carries an **Authority** grant — a preset
(`A1` commit-only / `A2` +feature-branch push+PR / `A3` +deps; absent = A1)
plus scope overrides, expanded mid-task only via `AUTHORITY+:` comments.
Anything outside the effective grant triggers **checkpoint-then-block**
(WIP commit → `STATE:` comment → numbered `Q<n>:` questions with options +
recommendation → block reason as a ≤160-char headline, since the chat
notification truncates it). The assistant `kanban_show`s the thread, answers
autonomously within the grant (`DECISION(Q<n>):` comment per open question +
unblock, then informs the user) and relays out-of-grant questions to the
human. Mid-run visibility is on-demand: engineer leaves `PROGRESS:` comments
at unit boundaries (comments never notify chat) and the assistant summarizes
them when asked (`orchestration` `<StatusCheck>`). The gateway's
`kanban.dispatch_interval_seconds` is lowered to **15** so a round-trip costs
roughly the answer time + ~20 s. Details: engineer's `engineer-loop` skill and
assistant's `orchestration` `<BlockedTriage>`.

The comment protocol is worker-generic, not engineer-specific: **creator**
speaks the same markers with a **Budget** grant as its Authority analog
(generation-spend caps; defaults 4 image variants / 2 video renders per
asset + 1 corrective pass, expanded only via `AUTHORITY+:`), leaves
`PROGRESS:` per finished asset, and — since a task's scratch workspace
survives block/crash respawns (deleted only on completion) — resumes by
inventorying surviving intermediates instead of re-spending credits.
Details: creator's `media-production` skill.

### Default is the assistant's CLI counterpart (and stays a clean baseline)

default and assistant are the two faces of the same front door: identical
orchestration behavior (both run `orchestration`, which lives in
default's skills tree at `hermes/skills/orchestration/` — default loads it
natively, assistant through its `~/.hermes/skills` external dir; the dm_topics
auto-load keeps working since resolution goes through `skill_view`), the same
worker roster, the same media-full-delegation rule. The differences: platform
(CLI vs Telegram gateway), persona (default stays **neutral** — every
`--clone` inherits its `config.yaml`, so voice/character stays out), and
assistant-only surface skills (ccc-course-production,
codebase-fact-finding) stay in the assistant profile. Keep default's `cron/` empty and run no gateway on it; bots and
scheduled automation belong in named profiles.

### Two working directories per worker

- **Kanban-dispatched work** runs in the task workspace
  (`$HERMES_KANBAN_WORKSPACE`): `worktree:` for engineer (isolated + preserved),
  `scratch` for the rest (ephemeral, deleted on completion).
- **Direct / `delegate_task` work** starts in `terminal.cwd` — currently `.`
  (the launch dir) for every worker; pin an absolute path per worker if you want
  a fixed directory. `workspace/` is per-machine and never tracked.

## Operating layers (per profile)

Three per-profile layers, kept separate:

- **SOUL.md** — persona/voice (BASE: Identity/Style/Avoid/Defaults + a one-line Role posture).
- **`agent.system_prompt`** (config.yaml) — the always-on *operating contract*: how the
  profile works each task. Workers open with "first action: load `<skill>`"; the assistant
  carries its chat-output contract + a compact work-routing tripwire here, kept out of
  SOUL so it survives. Note `/personality` shares this slot and would clobber it — don't
  use it on these profiles.

  Every contract also carries an always-on **safety floor** — the rules that must
  hold even when the profile's skill never loads: engineer = the Authority floor
  (absent grant ⇒ A1 commit-only; WIP-commit before blocking) + a non-kanban
  invocation branch; creator = the Budget/spend floor (default caps, inventory a
  surviving workspace before regenerating); researcher = evidence integrity (no
  fabricated citations) + a block baseline for missing premises; searcher = link
  integrity (only URLs actually retrieved); front doors = the blocked-triage
  baseline (kanban_show → in-grant `DECISION(Q<n>)` + unblock → relay the rest).
  Each profile also states its **MEMORY.md policy**: durable cross-task facts
  only (task state lives in the kanban thread + git/board; playbook-sized
  knowledge becomes a skill), and `user_profile_enabled` is off for workers —
  they never converse with the human.
- **skills/** — detailed, on-demand playbooks:
  - assistant + default → `orchestration` (shared front-door playbook, lives in
    default's tree at `hermes/skills/orchestration/`: 7-step pipeline
    (Classify → Locate → Approach → [Plan: Decompose → Register → Plan Loop] →
    Dispatch); task-spec template, topology: single / parents chain / triage
    card, dispatch params, BlockedTriage, failure recovery. Per-approach
    detail in `references/{plan,build,search,research,creative,inline}.md`.)
  - engineer → `engineer-loop` (delegate to OpenCode; Authority parsing + checkpoint-then-block
    dialogue; P0 master-plan + per-unit forks with permission/question bridges;
    fan-out to searcher/researcher/creator; quota-gated provider/model routing;
    intra-unit `-c`/`-s` resume; verify/report)
  - researcher → `research-pipeline` (search route + Admiralty/SIFT source evaluation; evidence discipline)
  - searcher → `breadth-retrieval` (query expansion, source-class routing, link-first hand-off)
    + `deep-retrieval` (explicit multi-hop hunts: `skills: ["deep-retrieval"]` + `goal_mode`)
  - creator → `media-production` (asset-type routing to the gen chains + the
    creative-skill catalog, Budget grant parsing, structured STATE/Qn block
    dialogue, per-asset PROGRESS, workspace-reuse resume, visual verification,
    kanban_attach delivery) + the in-tree `contextual-image-gen` /
    `contextual-video-gen` / `blender-mcp` depth skills, plus the upstream
    `creative/` + `media/` libraries referenced via `skills.external_dirs`
    (comfyui, manim-video, touchdesigner-mcp, gif-search, … — creator owns the
    creative cluster)

Routing (assistant): `orchestration` owns it. The skill is
**auto-loaded into every new Telegram topic session** via the per-topic
`skill:` binding in `platforms.telegram.extra.dm_topics` (gateway injects the
skill body into the session's first turn; `compression.protect_first_n` keeps
it alive; existing sessions pick it up after `/new` or an idle reset). It
triages silently on two axes — can the user wait? does it need a worker's
tools / isolation / durability? — then routes inline (conversation, quick
lookups, workspace skills, cron registration) vs kanban: searcher =
retrieval/web/X (deep hunts via `deep-retrieval` + `goal_mode`), researcher =
analysis/synthesis, engineer = implementation, creator = ALL media production
(the front door only collects the MediaBrief — purpose, destination specs,
style references, quantity — and dispatches; it generates nothing itself).
Multi-stage work ships as a `parents` chain (obvious 2-3 stages) or one
`triage=true` card (auto-decompose); `delegate_task` stays an exception for
medium parallel lookups the user is actively waiting on. The contract keeps a
fallback tripwire for surfaces without the auto-load (CLI, other platforms);
workers write a one-line chat-ready `kanban_complete` summary (the notifier
delivers its first line to the requester's chat verbatim). Keep routing in
sync with each `profile.yaml` description.

## Models and fallback chains

Each profile carries its own `model:` (tier 1) plus a `fallback_providers:`
list (tiers 2+). `fallback_providers` is **per-turn**: it triggers on errors
(429 / 5xx / 401 / 404 / malformed) and the primary is restored on the next
turn. The default profile already proves the YAML shape.

The shape mirrors OpenCode's split: **front doors = Claude (judgment +
long-lived context on the Max plan); workers = GPT / Grok (stateless
task turns); cheap OpenRouter tails.** The engineer's own turns are
orchestration (OpenCode does the coding), so it rides the GPT tier; the
coding model inside OpenCode is chosen per run by the engineer-loop's
comparative QuotaGate.

| Profile | T1 (primary) | T2 | T3 | T4 |
| --- | --- | --- | --- | --- |
| **default** | `anthropic` / claude-opus-4-8 | `openai-codex` / gpt-5.6-terra | `copilot` / claude-sonnet-4.6 | `openrouter` / `xiaomi/mimo-v2.5` |
| **assistant** | `anthropic` / claude-opus-4-8 | `openai-codex` / gpt-5.6-terra | `copilot` / claude-sonnet-4.6 | `openrouter` / `xiaomi/mimo-v2.5` |
| **engineer** | `openai-codex` / gpt-5.6-terra | `copilot` / gpt-5.4 | `openrouter` / `deepseek/deepseek-v4-flash` | — |
| **researcher** | `xai-oauth` / grok-4.3 | `copilot` / claude-sonnet-4.6 | `openrouter` / `deepseek/deepseek-v4-flash` | — |
| **searcher** | `xai-oauth` / grok-4.3 | `copilot` / gpt-5.4 | `openrouter` / `deepseek/deepseek-v4-flash` | — |
| **creator** | `openai-codex` / gpt-5.6-terra | `copilot` / gpt-5.4 | `openrouter` / `google/gemini-3.5-flash` | — |

```yaml
# example — researcher's ~/.hermes/profiles/researcher/config.yaml
model:
  default: grok-4.3
  provider: xai-oauth
  base_url: https://api.x.ai/v1
fallback_providers:
  - provider: copilot
    model: claude-sonnet-4.6
  - provider: openrouter
    model: deepseek/deepseek-v4-flash
    base_url: https://openrouter.ai/api/v1
    api_mode: chat_completions
```

Model facts confirmed during the build (live `provider_models_cache.json` + test
calls):

- **Anthropic native (T1)** — `default` / `assistant` lead with
  `anthropic` / `claude-opus-4-8` (`base_url: https://api.anthropic.com`,
  `api_mode: anthropic_messages`; slug in the live cache). OAuth (Claude
  Pro/Max) — `hermes auth status anthropic` → *logged in*. The engineer left
  the Claude tier 2026-07 (resource rebalance: its own turns are
  orchestration; Claude is spent inside OpenCode via the QuotaGate instead).
- **Grok** — `grok-4.3` is current on `xai-oauth` and verified working (the
  retired `grok-4*` glob doesn't cover it; re-auth via `hermes model` if the
  token lapses). `x-ai/grok-4.3` is the OpenRouter equivalent for per-token use.
- **Copilot catalog drift** — as of 2026-07 the catalog is the gpt-5.4
  generation + `claude-sonnet-4.x` + gemini (no `gpt-5.6-*`, no Grok): the
  old `copilot / gpt-5.6-terra` tiers 404'd and silently fell through, so
  copilot tiers now pin `claude-sonnet-4.6` (front doors, researcher) /
  `gpt-5.4` (engineer, searcher, creator). Re-check the cache after Copilot
  catalog updates.
- **OpenRouter slugs** — `xiaomi/mimo-v2.5`, `deepseek/deepseek-v4-flash`,
  `google/gemini-3.5-flash` (the earlier `*-v3.2` / `gemini-3-flash-preview`
  refs were planning guesses).
- **Deepest-tier split (mimo vs deepseek)** — `default` / `assistant` keep
  `xiaomi/mimo-v2.5` as their deepest tier (now **T4**) because it is
  **vision-capable**, so image input stays native even on a deep fallback turn
  (video analysis is decoupled via the `video-analyze-mimo` plugin — see
  `README.md` "Plugins"). The worker profiles (`engineer` / `researcher` /
  `searcher`, deepest tier each) use the cheaper text-only
  `deepseek/deepseek-v4-flash`; they don't need native image vision. `creator` is the exception: it leads with
  codex/`gpt-5.6-terra` (media work is tool-driven) and keeps vision-capable
  `google/gemini-3.5-flash` as its deepest tier so it can still eyeball
  generated assets on a fallback turn.

Optional: set `delegation.model: google/gemini-3.5-flash` on default /
assistant to route `delegate_task` subagents to a cheap model.

## Authentication inheritance

`auth.json` is per-profile (`auth.py:855-856`, built from `get_hermes_home()`),
**but** a named profile with no entry for a provider falls back **read-only** to
the default profile's `~/.hermes/auth.json` (`auth.py:1131-1157,1215-1259`).

- OAuth logins done in **default** (`hermes model`, no `-p`) — Codex, Copilot,
  xAI-OAuth — are inherited by every worker. **No per-worker re-auth.**
- **Anthropic native** is OAuth (Claude Pro/Max) but its creds live **outside**
  `auth.json` (`~/.hermes/.anthropic_oauth.json` for Hermes' PKCE flow, else the
  Claude Code credential / `CLAUDE_CODE_OAUTH_TOKEN`). That source is
  machine-global, so every profile authenticates with **no per-worker login**
  (`hermes auth status anthropic` → logged in); the auth.json read-only fallback
  does not apply to it.
- Always run OAuth logins from default. Running `hermes model` *inside* a worker
  writes that profile's `auth.json` and shadows the inherited creds for that
  provider (writes never propagate).
- Env tokens work everywhere via the shim: Copilot reads
  `COPILOT_GITHUB_TOKEN` → `GH_TOKEN` → `GITHUB_TOKEN` → `gh auth token`
  (`copilot_auth.py:39,67-95`); xAI accepts `XAI_API_KEY`.

Two caveats:

1. **Copilot token shadowing.** Copilot checks env before stored OAuth creds
   (`COPILOT_GITHUB_TOKEN` → `GH_TOKEN` → `GITHUB_TOKEN` → `gh`). The current
   `hermes`-layer `GITHUB_TOKEN` is already Copilot-capable (verified with a live
   `--provider copilot` call), so this is fine — but if you swap it for a classic
   `ghp_*` token, Copilot 401s. Then set a Copilot-capable
   **`COPILOT_GITHUB_TOKEN`** (highest priority) so it wins regardless.
2. **Parallel OAuth refresh.** Several workers refreshing the same rotating
   refresh token at once can race to `invalid_grant`. If it bites, move
   high-parallelism workers' T1 to an API-key provider (OpenRouter / `XAI_API_KEY`).

## Secrets layering

No `.env`. The `bin/hermes` shim injects two Keychain layers at launch —
`global` (shared by every shimmed tool) then `hermes` (the command name). A
profile alias `~/.local/bin/<name>` runs **bare `hermes -p <name>`**, so it
routes through the same `bin/hermes` shim — **every profile gets `global` +
`hermes`** (`~/.config/bin` precedes `~/.local/bin` on `PATH`). See
[`README.md`](./README.md#secrets).

- **`hermes`** — shared model/fallback keys every profile and every
  dispatcher-spawned worker needs: `OPENROUTER_API_KEY` (T3) and a
  Copilot-capable `GITHUB_TOKEN` (the `copilot` T2 + Skills Hub).
- **`global`** — keys shared with *other* tools (editor, MCP servers, other
  CLIs). Nothing Hermes-specific needs to live here.
- **gateway secrets** (`DISCORD_BOT_TOKEN`, `TELEGRAM_BOT_TOKEN`, +
  `*_ALLOWED_USERS` / `*_HOME_CHANNEL`) currently sit in the **`hermes`** layer,
  so the shim injects them whenever the gateway runs. Move them to a dedicated
  `assistant` layer if you want them off non-gateway profiles.
- **OAuth**: Codex / Copilot / xAI-OAuth in default's `auth.json` (read-only
  fallback to every profile); **Anthropic** resolves separately via the Claude
  Code credential / token (machine-global, every profile).

Workers need no unique secret: the dispatcher execs `hermes -p <worker>`, which
hits the `bin/hermes` shim (`global` + `hermes`), and they also inherit the
gateway's env. A background **LaunchAgent** can start with a stripped `PATH`, so
the assistant launcher sets its own `PATH` and `eval`s the Keychain layers
directly (below).

## Gateway as a persistent service

Assistant hosts the gateway (and the embedded kanban dispatcher) keychain-pure
via a **LaunchAgent**. Three tracked, machine-agnostic files in `hermes/launchd/`:

- **`hermes-gateway-assistant`** — the launcher. Sets `PATH`, `cd`s to
  `~/Workspaces`, logs to `~/.hermes/logs/gateway-assistant.log`, `eval`s the
  `global` + `hermes` Keychain layers (`TELEGRAM_BOT_TOKEN` /
  `OPENROUTER_API_KEY` / `GITHUB_TOKEN` / …) like the shim does, then execs the
  real `hermes -p assistant gateway run`. Every path is `$HOME`-relative — no
  hardcoded home, no `.env`. (`secret env` has **no `-- <cmd>` form**, hence the
  `eval`.)
- **`local.hermes.gateway.assistant.plist.tmpl`** — LaunchAgent template with a
  `__HOME__` placeholder (launchd can't expand `~`). Runs the launcher as
  `ProgramArguments[0]`, so the login item reads `hermes-gateway-assistant`, not
  `sh`.
- **`gateway-launchctl.sh`** — renders the template (`__HOME__` → `$HOME`) into
  `~/Library/LaunchAgents/` (host-local, never committed) and loads it.

**Telegram-only — workaround for upstream #40695.** With Discord connected the
gateway's `_handoff_watcher` blocks the event loop on a `list_pending_handoffs`
SQLite query and hangs (discord heartbeat stalls, dispatcher stops). The launcher
`unset`s `DISCORD_*` so only Telegram runs — verified stable, with the embedded
dispatcher auto-claiming tasks across ticks. Re-enable Discord (drop the `unset`
line) once the bug is fixed.

Activate on the **gateway host only** (one bot token = one live connection — stop
any gateway elsewhere first):

```
hermes/launchd/gateway-launchctl.sh install      # render template + load
hermes/launchd/gateway-launchctl.sh status        # check
hermes/launchd/gateway-launchctl.sh uninstall      # unload + remove
```

## Tracking

Per-profile, tracked in `hermes/profiles/<name>/` and symlinked by
`install.sh`: `config.yaml`, `SOUL.md`, `skills/`, `.no-bundled-skills`, and
**`profile.yaml`** (holds the routing `description`).

- **`install.sh`** links `config.yaml` / `profile.yaml` / `SOUL.md` / `skills/`
  / `.no-bundled-skills` per profile (`mcp.json` / `cron/` when present).
- `cron/` is tracked only where automation lives (assistant, if any).
- Auto-untracked (outside the symlink set): `~/.hermes/kanban.db`, `kanban/`,
  `workspace/`, `auth.json`, `.env`, `memories/`, `sessions/`, `state.db*`.

Routing quality depends on `profile.yaml` descriptions — create workers with
`hermes profile create <name> --description "<role>"` (or
`hermes profile describe <name> --text "…"`).

## Status (as-built)

Built and verified: default (kanban orchestrator), engineer (ex-coder, promoted
2026-07: dialogue-driven OpenCode worker), researcher, searcher, and creator
(added 2026-07: media production worker) workers —
T1–T4 tiers resolve (doctor + live probes) and default-created tasks
dispatch/route to each. Assistant gateway runs keychain-pure (LaunchAgent,
Telegram-only per #40695); the embedded dispatcher auto-claims tasks across
ticks (`dispatch_interval_seconds: 15` for fast block round-trips).
`install.sh` links every tracked profile (incl. `profile.yaml`) with no WARN.

Model slugs confirmed against the live cache (2026-07 rebalance):
`anthropic` / `claude-opus-4-8` (front-door T1; `hermes auth status
anthropic` → logged in), `openai-codex` / `gpt-5.6-terra` (engineer/creator
T1), `grok-4.3` on `xai-oauth`, `claude-sonnet-4.6` + `gpt-5.4` via
`copilot` (the gpt-5.6 copilot slugs 404 — catalog drift),
`deepseek/deepseek-v4-flash`, `google/gemini-3.5-flash`.

Remaining (manual): Telegram round-trip — message the bot and confirm a
reply; re-run `hermes doctor` after the 2026-07 tier rebalance.
