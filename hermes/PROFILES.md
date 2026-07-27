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
               ┌──────────────┼──────────────┬──────────────┬──────────────┬──────────────┐
               ▼              ▼              ▼              ▼              ▼              ▼
            searcher      researcher       engineer       creator        writer        marketer
            (retrieve)    (synthesize)     (implement)    (produce media) (write prose) (publish)
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
| **default** | CLI front door — assistant's CLI counterpart (neutral persona) | CLI | `.` (launch dir) | `web,browser,terminal,file,code_execution,vision,x_search,skills,todo,memory,clarify,delegation,cronjob,kanban` | — | yes |
| **assistant** | messaging front door + dispatcher host | Telegram | `~/Workspaces` | `web,browser,terminal,file,vision,x_search,skills,todo,memory,clarify,delegation,cronjob,computer_use,kanban` | **yes** | yes (token per-machine) |
| **engineer** | implement via OpenCode (git worktree, tests); confirms material decisions through kanban block round-trips | — (worker) | `.` (launch / task ws) | `terminal,file,web,skills,todo,memory,delegation` | — | yes |
| **researcher** | synthesize / analyze | — (worker) | `.` (launch / task ws) | `file,web,video,skills,memory,delegation` | — | yes |
| **searcher** | fast retrieval (web / x_search); deep multi-hop via `deep-retrieval` + `goal_mode` | — (worker) | `.` (launch / task ws) | `web,x_search,skills,memory` | — | yes |
| **creator** | ALL media production — image, video, GIF, voice, single and batch (front doors only brief and dispatch) | — (worker) | `.` (launch / task ws) | `terminal,file,vision,image_gen,video_gen,video,tts,skills,memory,delegation` + gen plugins | — | yes |
| **writer** | reader-facing prose — marketing long copy, tech articles/blog, documentation (tone-calibrated, JP norms); never publishes | — (worker) | `.` (launch / task ws) | `file,web,skills,memory,delegation` | — | yes |
| **marketer** | campaign orchestration + approved publishing (X via xurl); confirms every post through Publish-grant block round-trips | — (worker) | `.` (launch / task ws) | `terminal,file,web,x_search,vision,skills,memory,delegation` | — | yes |

The table lists each role's native capability allowlist. `platform_toolsets` is
the runtime authority; top-level `toolsets` mirrors it and retains `kanban` on
the two front doors for the runtime gate. Dispatcher-spawned workers receive
task-scoped Kanban lifecycle tools automatically. `no_mcp` is present in every
active platform allowlist but omitted from the table because it is a denial
sentinel, not a capability. Worker Telegram / Discord lists, default's messaging
lists, and assistant's disabled Discord list are empty by design.

Role split: **searcher (retrieve) → researcher (synthesize) → engineer
(implement)**, mirroring the `delegate_task` toolset patterns
(`["web"]` / `["file","web"]` / `["terminal","file"]`), with **creator**
(produce media) and **writer** (produce reader-facing prose — the deliverable
is the text itself, vs researcher's verified conclusions) as side stages any
pipeline can call on, and **marketer** as the outbound end stage: it
orchestrates campaigns (fanning out to writer/creator/searcher/researcher)
and is the only profile that publishes to public channels.

The org stays **flat by design**: profiles are global and the board is one
shared queue, so "hierarchy" is expressed as routing policy + `parents`
fan-in, not nested profiles. Workers fan out themselves via `kanban_create`
(e.g. engineer dispatches a searcher lookup or a creator asset mid-task);
staged supervision is expressed via the continuation-card pattern: a worker
creates its children plus a self-assigned fan-in card (formalized in each
worker skill's `<FanOut>`); grants never propagate to worker-created children.
A live supervising mid-manager isn't possible anyway — block/done
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
human. When the spec says `Review: required — <what to present>`, the worker
checkpoints and blocks with a `REVIEW:` headline (`kind=needs_input`) for human
sign-off; the assistant always relays that block rather than answering
autonomously, then replies `DECISION(REVIEW): approved` or `changes — <list>`
and unblocks. After every DECISION-driven unblock, the assistant resets the
block-loop counter: the breaker targets blind cron loops, while a DECISION is
the human-in-the-loop it wants. Mid-run visibility is on-demand: engineer
leaves `PROGRESS:` comments at unit boundaries (comments never notify chat) and
the assistant summarizes them when asked (`orchestration` `<StatusCheck>`).
The gateway's
`kanban.dispatch_interval_seconds` is lowered to **15** so a round-trip costs
roughly the answer time + ~20 s. Details: engineer's `engineer-pipeline` skill and
assistant's `orchestration` `<BlockedTriage>`.

The comment protocol is worker-generic, not engineer-specific: **creator** and
**writer** also honor the `Review: required` gate; creator speaks the same
markers with a **Budget** grant as its Authority analog
(generation-spend caps; defaults 4 image variants / 2 video renders per
asset + 1 corrective pass, expanded only via `AUTHORITY+:`), leaves
`PROGRESS:` per finished asset, and — since a task's scratch workspace
survives block/crash respawns (deleted only on completion) — resumes by
inventorying surviving intermediates instead of re-spending credits.
Details: creator's `creator-pipeline` skill. **marketer** speaks it with a
**Publish** grant (publishing is public and irreversible: absent grant =
draft-only + a needs_approval block showing the exact post
text/attachments/destination; `P1` = autonomous within named caps —
account, post count, content scope), leaves `PROGRESS:` with the posted URL
per post, and treats shipped posts as immutable facts on resume. Details:
marketer's `marketer-pipeline` skill.

### Default is the assistant's CLI counterpart (and stays a clean baseline)

default and assistant are the two faces of the same front door: identical
orchestration behavior (both run `orchestration`, which lives in
default's skills tree at `hermes/skills/orchestration/` — default loads it
natively, assistant through its `~/.hermes/skills` external dir; the Telegram
chat-wide auto-load keeps working since resolution goes through `skill_view`),
the same worker roster, the same media-full-delegation rule. The differences: platform
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
  integrity (only URLs actually retrieved); writer = deliverable integrity (no
  fabricated facts/quotes/URLs; assumptions labeled) + never publishes + a
  tone-sample block before long unsettled-tone deliverables; marketer = the
  Publish floor (absent grant ⇒ draft-only; every post needs a verbatim
  DECISION approval or an in-cap P1 grant; posted URLs verified; shipped
  posts never silently edited or deleted); front doors = the blocked-triage
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
  - engineer → `engineer-pipeline` (delegate to OpenCode; Authority parsing + checkpoint-then-block
    dialogue; P0 master-plan + per-unit forks with permission/question bridges;
    fan-out to searcher/researcher/creator; quota-gated provider/model routing;
    intra-unit `-c`/`-s` resume; verify/report)
  - researcher → `researcher-pipeline` (search route + Admiralty/SIFT source evaluation; evidence discipline)
  - searcher → `searcher-pipeline` (query expansion, source-class routing, link-first hand-off)
    + `deep-retrieval` (explicit multi-hop hunts: `skills: ["deep-retrieval"]` + `goal_mode`)
  - creator → `creator-pipeline` (asset-type routing to the gen chains + the
    creative-skill catalog, Budget grant parsing, structured STATE/Qn block
    dialogue, per-asset PROGRESS, workspace-reuse resume, visual verification,
    kanban_attach delivery) + the in-tree `contextual-image-gen` /
    `contextual-video-gen` / `blender-mcp` depth skills, plus the upstream
    `creative/` + `media/` libraries referenced via `skills.external_dirs`
    (comfyui, manim-video, touchdesigner-mcp, gif-search, … — creator owns the
    creative cluster)
  - writer → `writer-pipeline` (WritingBrief parsing; one-round tone
    calibration via sample-variant blocks; deliverable-type routing onto the
    layered Japanese norms; structure → draft → norms/humanizer/integrity
    self-review; final-message delivery) + external skills shared via
    `skills.external_dirs`: the opencode Japanese stack
    (`~/.config/opencode/skills/japanese` — japanese-writing / tech-prose /
    prose-rhythm, single-sourced with OpenCode) and upstream
    `creative/humanizer`
  - marketer → `marketer-pipeline` (MarketingBrief + Publish-grant parsing;
    strategy → fan-out to writer/creator/searcher/researcher → assemble →
    approval-gated xurl publish bridge with per-post PROGRESS + URL
    verification; channel extension points for future Discord/IG/TikTok
    accounts; kanban-thread resume treating shipped posts as immutable) +
    the upstream `social-media/xurl` skill via `skills.external_dirs`

Routing (assistant): `orchestration` owns it. The skill is
**auto-loaded into every new Telegram DM session** via the chat-wide
`telegram.channel_skill_bindings` entry (root DM plus fixed and user-created
topics; gateway injects the skill body into the session's first turn;
`compression.protect_first_n` keeps it alive; existing sessions pick it up
after `/new` or an idle reset). It
triages silently on two axes — can the user wait? does it need a worker's
tools / isolation / durability? — then routes inline (conversation, quick
lookups, workspace skills, cron registration) vs kanban: planner =
multi-card decomposition (the Planner tree — dependency-graph outline for
user approval; plan-only, never executes), searcher =
retrieval/web/X (deep hunts via `deep-retrieval` + `goal_mode`), researcher =
analysis/synthesis, engineer = implementation, creator = ALL media production
(the front door only collects the MediaBrief — purpose, destination specs,
style references, quantity — and dispatches; it generates nothing itself),
writer = reader-facing prose (marketing copy, articles/blog, docs — the front
door passes the WritingBrief fields it has: audience, purpose, medium, tone,
length; the writer blocks once for the rest), marketer = campaign
orchestration + ALL outbound publishing (the front door collects the
MarketingBrief and writes the `Publish:` grant line on purpose — an omitted
grant means draft-only; it never posts anything itself).
Time-deferred work parks in `scheduled` via `hermes kanban schedule <id>
"until=<ISO8601> — <reason>"`; the assistant's no_agent
`kanban-scheduled-sweeper.sh` cron releases due cards every 15 minutes. Dead
cards close via `hermes kanban archive <id>`.
Chat Plan Loop remains the default for settling requirements; multi-card
graphs run through the **Planner tree**: optional investigation parents +
one planner-assigned plan card that delivers a dependency-graph outline
YAML (assignees, technic `skills:`, grants, parents), the user approves it
in chat, and the assistant registers the cards in topological order with
idempotency keys — no worker ever creates build cards. The no_agent
`kanban-orphan-watchdog.sh`
cron runs every 30 minutes and surfaces unsubscribed blocked cards plus silent
block-loop triage falls to chat.
Multi-stage work ships as a `parents` chain (obvious 2-3 stages) or a
Planner tree (`auto_decompose` is off — the upstream aux decomposer's
hardcoded prompt can't carry the TaskSpec/grant/granularity conventions);
`delegate_task` stays an exception for
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

Most profiles lead with **Claude Opus 5** for judgment and long-context work,
fall back first to **GPT-5.6 Sol**, then keep a role-appropriate OpenRouter
tail. Three exceptions: **planner** leads with **Claude Fable 5** and inserts
Opus 5 as its T2 (see "Fable and the Max weekly pool" below), while
**researcher** and **searcher** lead on `xai-oauth` — grok-4.5 and grok-4.3
respectively, splitting the load across two flat-rate subscriptions instead of
piling every worker onto the Max weekly pool. The coding model inside OpenCode
remains a separate decision chosen per run by the engineer-pipeline's
comparative QuotaGate.

| Profile | T1 (primary) | T2 | T3 | T4 | `reasoning_effort` |
| --- | --- | --- | --- | --- | --- |
| **default** | `anthropic` / claude-opus-5 | `openai-codex` / gpt-5.6-sol | `openrouter` / `xiaomi/mimo-v2.5` | — | `medium` |
| **assistant** | `anthropic` / claude-opus-5 | `openai-codex` / gpt-5.6-sol | `openrouter` / `xiaomi/mimo-v2.5` | — | `medium` |
| **planner** | `anthropic` / **claude-fable-5** | `anthropic` / claude-opus-5 | `openai-codex` / gpt-5.6-sol | `openrouter` / `deepseek/deepseek-v4-flash` | `high` |
| **engineer** | `anthropic` / claude-opus-5 | `openai-codex` / gpt-5.6-sol | `openrouter` / `deepseek/deepseek-v4-flash` | — | `high` |
| **researcher** | `xai-oauth` / **grok-4.5** | `anthropic` / claude-opus-5 | `openai-codex` / gpt-5.6-sol | `openrouter` / `xiaomi/mimo-v2.5` | `medium` |
| **searcher** | `xai-oauth` / grok-4.3 | `openrouter` / `xiaomi/mimo-v2.5` | — | — | `low` |
| **creator** | `anthropic` / claude-opus-5 | `openai-codex` / gpt-5.6-sol | `openrouter` / `minimax/minimax-m3` | — | `medium` |
| **writer** | `anthropic` / claude-opus-5 | `openai-codex` / gpt-5.6-sol | `openrouter` / `deepseek/deepseek-v4-flash` | — | `medium` |
| **marketer** | `anthropic` / claude-opus-5 | `openai-codex` / gpt-5.6-sol | `openrouter` / `xiaomi/mimo-v2.5` | — | `medium` |

```yaml
# example — planner's ~/.hermes/profiles/planner/config.yaml (the 4-tier shape)
model:
  default: claude-fable-5
  provider: anthropic
  base_url: https://api.anthropic.com
fallback_providers:
  - provider: anthropic          # same provider, different model — allowed
    model: claude-opus-5         # (only an identical provider+model pair is skipped)
    base_url: https://api.anthropic.com
  - provider: openai-codex
    model: gpt-5.6-sol
    base_url: https://chatgpt.com/backend-api/codex
  - provider: openrouter
    model: deepseek/deepseek-v4-flash
    base_url: https://openrouter.ai/api/v1
    api_mode: chat_completions
agent:
  reasoning_effort: high
```

A `fallback_providers` entry carries no per-entry `reasoning_effort` or
`api_mode` for the main agent: on each fallback activation Hermes re-reads the
profile config and re-resolves both from provider / base URL / model
(`chat_completion_helpers.py:1668,1846`). Use `agent.reasoning_overrides`
(model → effort) if one tier needs a different depth from the rest.

Model facts confirmed during the build (live `provider_models_cache.json` + test
calls):

- **Anthropic native (T1)** — every profile except `researcher` / `searcher`
  leads with `anthropic` (`base_url: https://api.anthropic.com`):
  `claude-fable-5` on planner, `claude-opus-5` everywhere else. OAuth resolves
  from the global Claude Code credential/token rather than per-profile
  `auth.json`.
- **xAI (T1, researcher / searcher)** — both run `xai-oauth`
  (`base_url: https://api.x.ai/v1`), which is a flat-rate **SuperGrok /
  Premium+ subscription**, not the metered `XAI_API_KEY` API. The published
  per-token prices therefore do not apply to this path; what the two profiles
  actually spend is subscription allowance, which is why they sit here rather
  than adding two more consumers to the Max weekly pool.

  The split is by job shape. **Researcher takes grok-4.5**, xAI's frontier
  reasoning SKU, and stacks Opus 5 and Sol beneath it. **Searcher stays on
  grok-4.3**, which xAI positions for *tool calling and instruction
  following* — the right shape for link-first retrieval, and the only one of
  the two whose reasoning can be switched off entirely (`none`). Grok 4.5
  cannot disable reasoning and **defaults to `high` when the key is omitted**,
  so an unset effort there is an expensive surprise rather than a cheap one.
  Both are on the reasoning-capable allowlist
  (`model_metadata.py:370-410`), so their `reasoning_effort` really is sent as
  `reasoning: {effort: …}` — it is not a no-op. Non-allowlisted Grok models
  have the field dropped on purpose, because xAI answers an unsupported
  `reasoningEffort` with HTTP 400.

  **A lapsed xAI OAuth does not degrade these two to their lower tiers.**
  Credential resolution fails before the request is built, so the agent aborts
  with `xAI OAuth state is missing access_token` and `fallback_providers` never
  engages — researcher and searcher stop dead rather than falling through, so
  researcher's Opus 5 tier is no insurance against this particular failure. The
  same gate hides the `x_search` tool from the schema, which `hermes doctor`
  reports as `x_search (missing XAI_API_KEY)`; that wording is misleading,
  since the tool prefers the OAuth bearer and only falls back to the API key
  (`tools/xai_http.py:243-310`). Re-authenticate with `hermes model` from the
  **default** profile — never with `-p`, which would write the worker's own
  `auth.json` and shadow the inherited credential.
- **Codex** — every profile except searcher carries `openai-codex` /
  `gpt-5.6-sol` (`base_url: https://chatgpt.com/backend-api/codex`), as T2 on
  the Anthropic profiles and T3 on planner and researcher. The former
  `gpt-5.6-terra` profile routes were promoted to Sol; the engineer-pipeline's
  OpenCode QuotaGate remains a separate model-routing layer.
- **Copilot retired from every chain** (2026-07): the subscription became
  unusable, and its catalog drift had already 404'd tiers silently once.
  Profile fallbacks now use Codex first and OpenRouter as the final tail.
  `GITHUB_TOKEN` stays in the `hermes` Keychain layer for the Skills Hub — it
  is no longer a model-provider credential.
- **OpenRouter slugs** — `xiaomi/mimo-v2.5`, `deepseek/deepseek-v4-flash`,
  `google/gemini-3.5-flash` (the earlier `*-v3.2` / `gemini-3-flash-preview`
  refs were planning guesses).
- **OpenRouter tail split (vision vs text-only)** — profiles whose fallback
  turns may need to SEE something keep a vision-capable tail:
  `default` / `assistant` / `researcher` / `searcher` / `marketer` use
  `xiaomi/mimo-v2.5` (omnimodal, cheap; video analysis stays decoupled via
  the `video-analyze-mimo` plugin — see `README.md` "Plugins"), and
  `creator` uses `minimax/minimax-m3` (image + video input) so it can still
  eyeball generated assets. Text-only work rides the cheaper
  `deepseek/deepseek-v4-flash` (`planner`, `engineer`, `writer` tail). Researcher and
  searcher gained vision in the 2026-07 copilot removal as a side effect of
  standardizing on mimo.

Optional: set `delegation.model: google/gemini-3.5-flash` on default /
assistant to route `delegate_task` subagents to a cheap model.

### Fable and the Max weekly pool

Only **planner** runs Fable 5, and the `anthropic` / `claude-opus-5` T2 beneath
it exists for exactly one failure mode. Four facts drive the design:

1. **Fable is not a separate quota tank.** On Max it is included but capped at
   **≤50% of the plan's weekly pool**, drawn from the *same* pool as Opus, and
   it burns that pool faster. So `Fable → Opus` only rescues the case where the
   Fable sub-cap is exhausted while the overall weekly still has room. If the
   shared weekly or the 5-hour session limit is what tripped, Opus is dead too
   and the chain correctly continues to Codex.
2. **The T2 step depends on the token being resolvable outside the credential
   pool.** A `usage_limit_reached` 429 marks the *credential* exhausted, and
   that mark has **no model dimension** (`credential_pool.py:662`) — the pool
   then refuses to hand it out. The Opus attempt only succeeds because
   `resolve_anthropic_token()` checks `ANTHROPIC_TOKEN` /
   `CLAUDE_CODE_OAUTH_TOKEN` / the Claude Code Keychain entry **before** the
   pool (`anthropic_adapter.py:1401`). Park the Max subscription *only* in the
   credential pool and the Opus tier is silently skipped — the chain quietly
   degrades to `Fable → Codex`.
3. **Hermes has no per-model quota memory.** The "included Fable 5 usage for
   this week" message carries no parseable reset, so a fixed **1-hour** local
   cooldown is applied (`credential_pool.py:117`), while the agent-level
   fallback cooldown is only **60 seconds** (`chat_completion_helpers.py:1549`).
   At t+61s the primary is restored and Fable is retried. Once the weekly cap is
   hit this costs **one wasted request per turn until the week rolls over** —
   accepted deliberately, and a reason planner (low turn count) carries Fable
   while assistant (highest turn count, latency-sensitive) does not.
4. **Adaptive thinking, not manual budgets.** Modern Claude — Fable 5 included —
   gets `thinking: {type: adaptive}` + `output_config: {effort: …}`, so the
   effort level passes straight through (`minimal→low`, `ultra→max`); the
   legacy 4k/8k/16k/32k `budget_tokens` table does **not** apply. planner sits
   at `high` rather than `xhigh` because its deliverable is a long outline YAML
   and Hermes can otherwise burn the whole output budget on reasoning
   (`conversation_loop.py:2600`). If that warning ever appears, drop to
   `medium` or raise `max_tokens`.

### `agent.*` does not inherit from the root profile

A named profile's config is `$HERMES_HOME/config.yaml` deep-merged with the
built-in `DEFAULT_CONFIG` **only** (`hermes_cli/config.py:680,7456`) — the root
`~/.hermes/config.yaml` is never a parent. `--clone` copies it once at creation
time; that is not live inheritance.

This bites hardest on `agent.reasoning_effort`, because `DEFAULT_CONFIG["agent"]`
has **no** `reasoning_effort` key. Omitting it does not inherit the root's
`medium` — it resolves to `None`, and each provider path then does something
different: native Anthropic sends no `thinking`/`output_config` at all
(`anthropic_adapter.py:2854`), Codex defaults to `medium`
(`transports/codex.py:170`), OpenRouter to `{enabled: true, effort: medium}`.
The result is a profile whose T1 is unspecified while its fallbacks are
`medium`. Five profiles sat in that state until 2026-07; every profile now
carries an explicit value. **Set `agent.*` keys per profile, always.**

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
- **Shadowed creds survive a default re-login, and `hermes doctor` will not see
  it.** Doctor inspects default, so it reports the provider healthy while a
  worker still loads its own stale entry — the fallback only applies to a
  profile with *no* entry at all. The symptom is uneven: the model can keep
  answering while a tool that resolves through the credential pool goes
  missing, so `x_search` returns unavailable on a profile whose grok replies
  fine. Confirm with `providers` in the worker's own
  `~/.hermes/profiles/<name>/auth.json`; the repair is to drop that provider
  key so the profile inherits default again. Prefer editing the file over
  `hermes auth logout`, which may revoke upstream and take the shared
  credential down with it.
- Env tokens work everywhere via the shim: Copilot reads
  `COPILOT_GITHUB_TOKEN` → `GH_TOKEN` → `GITHUB_TOKEN` → `gh auth token`
  (`copilot_auth.py:39,67-95`); xAI accepts `XAI_API_KEY`.

Two caveats:

1. **Copilot token shadowing** (historical — copilot left every model chain
   2026-07, kept for if it returns). Copilot checks env before stored OAuth
   creds (`COPILOT_GITHUB_TOKEN` → `GH_TOKEN` → `GITHUB_TOKEN` → `gh`); a
   non-Copilot-capable `GITHUB_TOKEN` in the `hermes` layer would 401 it.
   `COPILOT_GITHUB_TOKEN` (highest priority) overrides regardless.
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
  dispatcher-spawned worker needs: `OPENROUTER_API_KEY` (the OpenRouter
  fallback tails) and `GITHUB_TOKEN` (Skills Hub; no longer a model
  provider since the 2026-07 copilot retirement).
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
2026-07: dialogue-driven OpenCode worker), researcher, searcher, creator
(added 2026-07: media production worker), writer (added 2026-07: prose
worker; skills shared from the opencode Japanese
stack via external_dirs), and marketer (added 2026-07: campaign/publishing
worker; posts to X via the bundled xurl skill + external CLI under the
Publish-grant floor) workers —
T1–T3 tiers resolve (doctor + live probes) and default-created tasks
dispatch/route to each. Assistant gateway runs keychain-pure (LaunchAgent,
Telegram-only per #40695); the embedded dispatcher auto-claims tasks across
ticks (`dispatch_interval_seconds: 15` for fast block round-trips).
`install.sh` links every tracked profile (incl. `profile.yaml`) with no WARN.
The 2026-07 kanban workflow conventions (Review gate, scheduled sweeper cron,
Planner trees (planner profile, Claude Fable 5, plan-only; replaced the
assistant-run Board Plan synthesis cards and the auto-decompose triage
route), continuation-card fan-out, the
`kanban-orphan-watchdog.sh` cron, and block-loop reset discipline) shipped in
the orchestration and worker skills.

Active profile-chain model slugs confirmed 2026-07 (provider checks +
OpenRouter model pages): `anthropic` / `claude-opus-5`, `anthropic` /
`claude-fable-5` (planner T1), `xai-oauth` / `grok-4.5` (researcher T1) and
`grok-4.3` (searcher T1), `openai-codex` / `gpt-5.6-sol`, and the
OpenRouter tails `xiaomi/mimo-v2.5` (vision; live on openrouter.ai but
missing from a stale local model cache — refresh before trusting doctor),
`minimax/minimax-m3` (image+video), `deepseek/deepseek-v4-flash`
(text-only).

Remaining (manual): Telegram round-trip — message the bot and confirm a
reply. `hermes doctor` passed for default and every named profile after the
2026-07 tier rebalance.
