# Profiles — multi-agent plan

How this machine runs several Hermes agents that cooperate: two **front
doors** a human talks to, plus named **worker** profiles they delegate to in
the background. This is the design doc; [`README.md`](./README.md) covers the
single-profile mechanics (symlinks, skills, cron, secrets).

A profile is just a separate `HERMES_HOME` (`~/.hermes/profiles/<name>/`) with
its own `config.yaml` / `SOUL.md` / `skills/` / `cron/` / state, and a
`~/.local/bin/<name>` alias that runs `hermes -p <name>`. The default profile is
`~/.hermes` itself (it can't be deleted or renamed).

## Topology

```
   human (terminal)            human (Telegram)
          │                              │
        default ──┐                  assistant ──┐   (runs the gateway + kanban dispatcher)
        (CLI)     │                (~/Workspaces)│
                  │                              │
                  └──────────┬───────────────────┘
                             │
        ┌────────────────────┼──────────────────────┐
        │ resident sessions  │ lean kanban cards    │ delegate_task
        │ (default for       │ (fire-and-forget,    │ (in-turn parallel
        │  heavy work)       │  cron, mass-parallel,│  lookups)
        ▼                    ▼  scheduled)          ▼
  hermes -p <specialist>   ~/.hermes/kanban.db    anonymous subagents
  chat --resume <id>         │ dispatcher spawns
        │              ┌─────┴────┬─────────┬────────┬────────┬────────┐
        ▼              ▼          ▼         ▼        ▼        ▼        ▼
   searcher/researcher/engineer/creator/writer/marketer  (same six profiles)
```

Heavy interactive work runs in **resident sessions**: the assistant starts a
persistent `hermes -p <specialist> chat` conversation through
`assistant/scripts/resident-session.sh` (background + completion notify,
per-key serialization, close-on-acceptance) and supervises it turn by turn.
The board remains for work where conversation adds nothing.

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

## Three delegation layers

| | Resident session | Kanban | `delegate_task` |
| --- | --- | --- | --- |
| Worker | **named profile** session with living context | **named profile**, fresh process per run | anonymous subagent |
| Dialogue | conversational turns (feedback in minutes) | STATE/Q<n>/DECISION comments + block round-trips | none — one shot |
| Durability | session registry + durable-path files | persistent queue, resumable | dies with the turn |
| Requires | terminal + the wrapper script | a running gateway (the dispatcher) | nothing |
| Use for | **default for heavy work**: anything you expect to give feedback on | fire-and-forget, cron-originated, mass-parallel, `scheduled` parking | in-turn parallel lookups |

**Fallback story:** resident sessions work whenever `hermes` runs — no
gateway needed. Gateway up adds the board for fire-and-forget work; gateway
down, `default` still parallelizes via `delegate_task`. A specialist may
itself call `delegate_task` during its run.

## Profile roster

| Profile | Role | Front door | `terminal.cwd` | Toolsets | Gateway | Tracked |
| --- | --- | --- | --- | --- | --- | --- |
| **default** | CLI front door — assistant's CLI counterpart (neutral persona) | CLI | `.` (launch dir) | `web,browser,terminal,file,code_execution,vision,x_search,skills,todo,memory,clarify,delegation,cronjob,kanban` | — | yes |
| **assistant** | messaging front door + dispatcher host | Telegram | `~/Workspaces` | `web,browser,terminal,file,vision,x_search,skills,todo,memory,clarify,delegation,cronjob,computer_use,kanban` | **yes** | yes (token per-machine) |
| **engineer** | supervises OpenCode: assess (read-only) / shape (draft decompositions, outlines) / implement, under an Authority grant; GitHub bookkeeping stays with the assistant | — (specialist) | `.` (launch / task ws) | `terminal,file,web,skills,todo,memory,delegation` | — | yes |
| **researcher** | evidence-backed synthesis, comparisons, fact checks, and guidance; heavy breadth is requested from the orchestrator | — (specialist) | `.` (launch / task ws) | `file,web,vision,video,skills,memory,delegation` | — | yes |
| **searcher** | retrieval: lookup / sweep / hunt (multi-hop via `goal_mode` on cards) | — (specialist) | `.` (launch / task ws) | `web,x_search,skills,memory` | — | yes |
| **creator** | all media production — image, video, GIF, audio, song, voice — under a Budget grant, with advisory and style-anchor rounds | — (specialist) | `.` (launch / task ws) | `terminal,file,vision,image_gen,video_gen,video,tts,skills,memory,delegation` + gen plugins | — | yes |
| **writer** | reader-facing prose and producer-facing scripts; draft-only, never publishes | — (specialist) | `.` (launch / task ws) | `file,web,skills,memory,delegation` | — | yes |
| **marketer** | campaign assess/shape/drafts, and publishing only within a Publish grant | — (specialist) | `.` (launch / task ws) | `terminal,file,web,browser,x_search,vision,skills,memory,delegation` | — | yes |

The table lists each role's native capability allowlist. `platform_toolsets` is
the runtime authority; top-level `toolsets` mirrors it and retains `kanban` on
the two front doors for the runtime gate. Dispatcher-spawned workers receive
task-scoped Kanban lifecycle tools automatically. `no_mcp` is present in every
active platform allowlist but omitted from the table because it is a denial
sentinel, not a capability. Worker Telegram / Discord lists, default's messaging
lists, and assistant's disabled Discord list are empty by design.

Role split: **the assistant** plans with the user, supervises specialists,
performs the quality gate itself (the QA contracts under
`skills/orchestration/references/qa/`), owns GitHub bookkeeping, and
delivers; the **producer** self-verifies before reporting. The normal flow
stays **searcher (retrieve) → researcher (synthesize) → engineer
(implement)**, with **creator** (media) and **writer** (prose/scripts) as
production stages and **marketer** as the outbound end stage — the only
profile that publishes to public channels. User approval follows the
assistant's own verification, not instead of it.

### Assistant quality gate

The assistant is the quality gate. Every specialist deliverable — a resident
session reply or a card completion — is a candidate until the assistant
verified the actual artifact per the contracts under
`skills/orchestration/references/qa/` (vision on images/frames, ffprobe on av
media, read the prose, spot-check sources; `delegate_task` fans out
per-artifact checks on large sets). Defects go back to the same resident
session as itemized feedback — a minutes-scale loop, not a card cycle.
Delivery happens only after verification; the session is closed on
acceptance. External factual claims still ride researcher evidence supplied
in the flow.

The org stays **flat by design**: profiles are global, sessions are owned by
the assistant, and the board is one shared queue. Specialists never register
cards; follow-up work they propose returns in their reply or completion
summary, and the assistant decides. Grants never propagate between
specialists.

### Engineer dialogue loop (the four layered loops)

Implementation work runs through four nested loops, each with its own
channel, its own durable state, and its own decision altitude:

| # | Loop | Channel | Durable state | Decides |
| --- | --- | --- | --- | --- |
| L1 requirements | user ↔ assistant | chat + risk/ambiguity-driven `clarify` | the approved plan (one gate); the assistant's OpenCode base plan session | what/why: goal, done criteria, constraints, grant posture |
| L2 detail | assistant ↔ engineer | resident-session turns (default) or kanban block round-trips | session registry + replies; kanban thread on cards | how (shape): feasibility, plan revision, in-grant calls |
| L3 implementation | engineer ↔ OpenCode | `opencode run` (base plan session + per-Wave forks) | base session + git history + plan document | how (detail): unit split, tactics, model, verification |
| L4 in-run | OpenCode ↔ its subagents (reviewer/debugger/…) | OpenCode task tool, per the `opencode/` config | subagent sessions | code-level: review findings, root causes |

Three principles hold the stack together: **escalation moves one layer at a
time** (OpenCode never talks to the assistant, the engineer never talks to
the user — each layer translates what it cannot decide into the next layer
up's format); **the engineer is the translation layer** (upward a worker
speaking kanban — `Q<n>`/`DECISION`/Authority; downward an orchestrator
speaking OpenCode — prompts, forks, permission env); **L4 is hands-off**
(the engineer judges results by independent verification, never micromanages
the subagents).

In a resident session, L2 continuity lives in the session itself; on kanban
cards the worker process stays disposable and continuity lives in the
comment thread + git. In L3 the engineer starts from the **base** plan
session — normally created and approved at L1 by the assistant and handed
over in the brief (`Base session: <id>`) — then implements each Wave in a
short-lived **fork** of it (`run -s <base> --fork`), ending every Wave with
verify → commit → a report carrying the session ids; review/debug primaries
run as fresh read-only sessions. Two bridges wire L3 to OpenCode's non-interactive
reality (both verified against source): the **Permission Bridge** — bare
`run` auto-rejects every `ask`, so the engineer translates the Authority
grant into an `OPENCODE_PERMISSION` overlay (deep-merged; deny beats
`--auto`) plus `--auto`; and the **Question Bridge** — `run` denies the
question tool, so OpenCode escalates only via its final output text, which
the engineer answers with `run -c` or translates into an L2 block.

The L2 protocol: the brief carries an **Authority** grant — a preset
(`A1` commit-only / `A2` +feature-branch push+own PR / `A3` +deps; absent =
A1) plus scope overrides, expanded only by later explicit grants. Anything
outside the effective grant is a question: in a resident session, numbered
questions in the reply, answered in the next turn; on a card,
checkpoint-then-block (WIP commit → `STATE:` → `Q<n>:` comments →
`DECISION(Q<n>):` answers → the guarded `kanban-resolve-block.sh apply`).
`Review: required` presents the deliverable for human sign-off before the
job closes — always relayed to the user. GitHub bookkeeping (Issues, boards,
merges) is the assistant's own `gh` work, after approvals. Details:
engineer's `engineer-pipeline` skill and the orchestration skill.

The dialogue discipline is specialist-generic, not engineer-specific:
**creator** and **writer** also honor the `Review: required` gate; creator
speaks the same protocol with a **Budget** grant as its Authority analog
(generation-spend caps; defaults 4 image variants / 2 video renders per
asset + 1 corrective pass, expanded only via `AUTHORITY+:`), leaves
`PROGRESS:` per finished asset, and — since a task's scratch workspace
survives block/crash respawns (deleted only on completion) — resumes by
inventorying surviving intermediates instead of re-spending credits.
Details: creator's `creator-pipeline` skill. **marketer** speaks it with a
**Publish** grant (publishing is public and irreversible: absent grant =
draft-only + an `APPROVAL:`-headlined block — `kind=needs_input`, always
relayed to the human like `REVIEW:` — showing the exact post
text/attachments/destination; `P1` = autonomous within named caps —
account, post count, content scope), leaves `PROGRESS:` with the posted URL
per post, and treats shipped posts as immutable facts on resume. Details:
marketer's `marketer-pipeline` skill.

### Planning ladder — who plans at which altitude

Planning happens at five altitudes. Each owner decides its own altitude only
and hands a typed result to the next owner; one conversational approval
authorizes execution.

| Altitude | Owner | Deliverable | Durable home |
| --- | --- | --- | --- |
| High-level requirement + plan — what outcome, which specialists, what grants | assistant with the user (consulting resident sessions for feasibility/cost) | the approved plan (one `clarify` gate) | chat + the session briefs it produces |
| Repo grounding — Wave outline for code work | assistant's OpenCode plan session in the repo | Wave outline + base session id | the OpenCode session (handed to engineer) |
| Low-level requirements — feature → concrete requirement units | engineer **shape** (specify), draft-only | decomposition document, user-reviewed; the assistant registers the Issues | GitHub Issues / Projects (assistant-registered) |
| Technical milestones — Wave outline for non-Issue work | engineer **shape** (outline) | Wave list (coarse, one line each) | report + base session |
| Phase/unit decomposition — inside one Wave or one Issue | OpenCode plan agent (L3) | phase breakdown | OpenCode sessions + git |

Feasibility questions are consultation turns to the relevant specialist
session, not a planning rung of their own.

Two rules keep the ladder from collapsing back into confusion:

- **GitHub-flow repos use Issues as the milestone layer.** When specify has
  registered low-level requirement Issues, implement consumes an Issue (its
  body is the outline; the PR closes it) — do NOT also produce a Wave
  outline for the same work. The Wave outline is for repos/work outside the
  GitHub Issue flow (scratch builds, small refactors, non-GitHub targets).
- **Escalation moves one rung at a time** (same principle as the dialogue
  loops): OpenCode's open question goes to the engineer; the engineer's
  material ambiguity goes to the assistant as a `Q<n>` block; only the
  assistant talks to the user.

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
  (absent grant ⇒ A1 commit-only; WIP-commit before pausing; no GitHub
  bookkeeping ever); creator = the Budget/spend floor (default caps, inventory
  surviving work before regenerating); researcher = evidence integrity (no
  fabricated citations); searcher = link integrity (only URLs actually
  retrieved); writer = deliverable integrity (no fabricated
  facts/quotes/URLs; assumptions labeled) + never publishes; marketer = the
  Publish floor (absent grant ⇒ draft-only; every post needs verbatim
  approval or an in-cap P1 grant; posted URLs verified; shipped posts never
  silently edited or deleted); front doors = heavy work never runs in their
  own turn, deliverables are verified before delivery, and blocked cards
  resolve only through the guarded resolver after a complete DECISION batch.
  Each profile also states its **MEMORY.md policy**: durable cross-task facts
  only (task state lives in the kanban thread + git/board; playbook-sized
  knowledge becomes a skill), and `user_profile_enabled` is off for workers —
  they never converse with the human.
- **skills/** — detailed, on-demand playbooks:
  Every local library uses the same ownership types. A worker has one tracked
  `<profile>-pipeline/` plus tracked, directly selectable `technic/` leaves.
  The front doors share tracked `hermes/skills/orchestration/` as their
  pipeline; assistant-only Telegram surfaces live in tracked `desks/`.
  Runtime-authored skills from background review, curator, `/learn`, or normal
  `skill_manage(create)` calls go to the untracked `learned/` category through
  the `skill-topology` plugin. Moving a complete package from `learned/` to
  `technic/` is the explicit maintainer-review boundary. External directories
  remain provider-owned and never become local technics implicitly.
  - assistant + default → `orchestration` v5 (shared front-door playbook,
    lives in default's tree at `hermes/skills/orchestration/`: modes Chat /
    Plan / Execute / QA over tiers inline / resident / kanban; resident
    sessions via `resident-session.sh`; assistant-run QA against
    `references/qa/`; the lean kanban card contract in
    `references/kanban-lite.md`; capability playbooks in
    `references/{creative,engineering,research,writing,marketing}.md`. The
    machine-readable roster, tiers, grants, and retired markers live in
    `references/workflow-contract.yaml`.)
  - engineer → `engineer-pipeline` (dual runtime; assess / shape / implement
    routing with intent triage; Authority parsing + dialogue discipline;
    base-session seeding + per-Wave forks with permission/question bridges;
    quota-gated provider/model routing; verify/report)
  - researcher → `researcher-pipeline` (dual runtime; deliverable-based
    routing — evidence-pack / tradeoff-matrix / fact-check / guidance — plus
    Admiralty/SIFT source evaluation, citation rules, Review gate, and resume
    in the kernel; researcher supplies evidence and does not own
    artifact-vs-brief QA; retrieval strategy in references/gather.md)
  - searcher → `searcher-pipeline` (dual runtime; deliverable-based routing —
    lookup (targeted facts) / sweep (enumeration with a coverage claim) /
    hunt (multi-hop to saturation, signalled by `goal_mode` on cards) — plus
    the link-integrity floor; per-mode playbooks in references/.
    `technic/deep-retrieval` remains only as a deprecated stub)
  - creator → `creator-pipeline` (dual runtime; Advisory / Direction /
    Produce routing with intent triage; the MediaBrief + capability router,
    Budget grant parsing, dialogue discipline, workspace-reuse resume, visual
    verification, and durable-path delivery) + directly selectable in-tree leaves under `skills/technic/`:
    `creator-generated-image`, `creator-article-illustration`,
    `creator-infographic`, `creator-svg-diagram`,
    `creator-excalidraw-diagram`, `creator-logo-icons`, `creator-text-card`,
    `creator-meme`, `creator-ascii-art`, `creator-audio-visualization`,
    `creator-audio-generation`, `creator-song-generation`,
    `creator-gif-sourcing`, `creator-generated-video`, `creator-html-motion`,
    `creator-p5js-experience`, `creator-ascii-video`,
    `creator-manim-explainer`, `creator-pixel-art`, `creator-pixel-video`,
    `creator-knowledge-comic`, and `creator-brand-asset-sourcing`. Leaves own
    one production grammar and its medium QA; styles/presets and same-tool
    modes stay in references. Official creative skills may be implementation
    engines behind these canonical names, but never alternate dispatch
    identities. `creator-html-motion` uses the HyperFrames stack via
    `skills.external_dirs` (`~/.agents/skills` - `hyperframes` is the entry
    point that routes the domain/workflow skills, plus `media-use` for asset
    resolution / TTS / captions; CLI-owned store, see AGENTS.md). The upstream
    bundled `creative/` + `media/` libraries remain available, while optional
    skills are exposed as a curated set of individual directories (article
    illustration, AudioCraft, pixel art, comics, memes, concept diagrams, and
    HeartMuLa) so the official optional `hyperframes` cannot collide with the
    CLI-owned entry skill. MCP-backed entries in that cluster
    (`blender-mcp`, `touchdesigner-mcp`, `unreal-mcp`) are listed in
    `skills.disabled`: the profile runs `no_mcp`, so they can never execute.
    The ambiguous external `pixel-art` name is disabled too; the canonical
    Pixel leaves may use its scripts as opt-in implementation backends but are
    the only stable dispatch identities
  - writer → `writer-pipeline` (dual runtime; routes assess/write by
    deliverable, parses the WritingBrief, and performs one-round tone
    calibration; TypeTable routes copy/article/docs → references/prose.md
    and 台本/絵コンテ/screenplay → references/script.md, with the four-pass
    quality engine references/review.md shared by self-review and critique,
    and consultations/critiques in references/assess.md) + external skills via
    `skills.external_dirs`: the Japanese stack via the curated
    `profiles/writer/external-skills/` symlink dir (japanese-writing /
    tech-prose / prose-rhythm, single-sourced with the shared
    `agents/skills/` store) and upstream `creative/humanizer`
  - marketer → `marketer-pipeline` (dual runtime; parses MarketingBrief +
    Publish grant and routes assess/shape/campaign; requests prose/media/
    research inputs from the orchestrator → assemble → approval-gated xurl
    publish bridge with per-post URL verification; channel extension points
    for future Discord/IG/TikTok accounts; resume treating shipped posts as
    immutable) + the upstream `social-media/xurl` skill via
    `skills.external_dirs`

Routing (assistant): `orchestration` v5 owns it. The skill is
**auto-loaded into every new Telegram DM session** via the chat-wide
`telegram.channel_skill_bindings` entry (root DM plus fixed and user-created
topics; gateway injects the skill body into the session's first turn;
`compression.protect_first_n` keeps it alive; existing sessions pick it up
after `/new` or an idle reset). Every request flows Classify → Locate → Mode
(Chat / Plan / Execute / QA) → Deliver. Questions are risk/ambiguity driven:
a settled request does not pay an interview tax. Tier selection is by context
dependence, not size: `inline` for conversation/quick local work, a
**resident session** for anything the user will give feedback on (the
default for heavy work), and a lean kanban card only for fire-and-forget,
cron-originated, mass-parallel, or `scheduled` work. Plan mode ends in one
conversational approval that sanctions the grants; Execute supervises the
sessions turn by turn; QA verifies actual artifacts before delivery.

The pinned Telegram topics are Assistant-owned **desks**, not worker threads:
Personal binds `personal-desk` (household-budget / People / message-reply plus
personal docs/data), Projects binds `project-desk` (the `pj` registry,
workspace scaffold, and project docs/data), Brainstorm binds `brainstorm`, and
Inbox has no skill because it is only the delivery target for system cron
output. Each desk fixes the tier to `inline`; work that needs a specialist
hands off to a new ad-hoc topic, which inherits chat-wide `orchestration` and
owns the sessions. The fifth Telegram pin remains a UI-managed rotation slot
rather than a configured topic. Kanban completion notifications remain
attached to their originating topic; only maintenance/report/sweeper cron
output targets Inbox: jobs keep bare `deliver: telegram`, while the gateway
launcher derives `TELEGRAM_CRON_THREAD_ID` from the ignored runtime config's
Inbox topic. Time-deferred work parks in `scheduled` via `hermes kanban
schedule <id> "until=<ISO8601> — <reason>"`; the assistant's no_agent
`kanban-scheduled-sweeper.sh` cron releases due cards every 15 minutes. Dead
cards close via `hermes kanban archive <id>`. Blocked cards resume only
through `kanban-resolve-block.sh apply` after a complete `DECISION(...)`
batch.

`auto_decompose` stays off — decomposition is a conversation, not a runtime
fallback. `delegate_task` covers medium parallel lookups the user is actively
waiting on, and absorbs per-artifact QA checks on large sets. Keep routing in
sync with each `profile.yaml` description.

## Models and fallback chains

Each profile carries its own `model:` (tier 1) plus a `fallback_providers:`
list (tiers 2+). `fallback_providers` is **per-turn**: it triggers on errors
(429 / 5xx / 401 / 404 / malformed) and the primary is restored on the next
turn. The default profile already proves the YAML shape.

Most profiles lead with **Claude Opus 5** for judgment and long-context work,
fall back first to **GPT-5.6 Sol**, then keep a role-appropriate OpenRouter
tail. The deliberate exceptions are **researcher**, which leads with GPT-5.6
Sol, and **searcher**, which leads on `xai-oauth` / grok-4.3. xAI capacity is reserved for
Searcher, X search, and Imagine video; Codex is shared because it also serves
Researcher and Creator's images, alongside profile fallbacks. The coding model
inside OpenCode is a separate layer entirely: engineer-pipeline drives a **fixed ladder**
(`claude-opus-5` → `gpt-5.6-sol` at `--variant high` → `grok-4.5` → OpenRouter),
descending only on an error or a spent pool — never by pre-judging the task's
weight.

| Profile | T1 (primary) | T2 | T3 | T4 | `reasoning_effort` |
| --- | --- | --- | --- | --- | --- |
| **default** | `anthropic` / claude-opus-5 | `openai-codex` / gpt-5.6-sol | `openrouter` / `xiaomi/mimo-v2.5` | — | `medium` |
| **assistant** | `anthropic` / claude-opus-5 | `openai-codex` / gpt-5.6-sol | `openrouter` / `xiaomi/mimo-v2.5` | — | `medium` |
| **engineer** | `anthropic` / claude-opus-5 | `openai-codex` / gpt-5.6-sol | `openrouter` / `deepseek/deepseek-v4-flash` | — | `high` |
| **researcher** | `openai-codex` / **gpt-5.6-sol** | `anthropic` / claude-opus-5 | `openrouter` / `xiaomi/mimo-v2.5` | — | `medium` |
| **searcher** | `xai-oauth` / grok-4.3 | `openrouter` / `xiaomi/mimo-v2.5` | — | — | `low` |
| **creator** | `anthropic` / claude-opus-5 | `openai-codex` / gpt-5.6-sol | `openrouter` / `minimax/minimax-m3` | — | `medium` |
| **writer** | `anthropic` / claude-opus-5 | `openai-codex` / gpt-5.6-sol | `openrouter` / `deepseek/deepseek-v4-flash` | — | `medium` |
| **marketer** | `anthropic` / claude-opus-5 | `openai-codex` / gpt-5.6-sol | `openrouter` / `xiaomi/mimo-v2.5` | — | `medium` |

```yaml
# example — a 4-tier chain (the shape any profile may use)
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
  leads with `anthropic` (`base_url: https://api.anthropic.com`) on
  `claude-opus-5`. OAuth resolves from the global Claude Code
  credential/token rather than per-profile `auth.json`.
- **xAI (T1, searcher only)** — searcher runs `xai-oauth`
  (`base_url: https://api.x.ai/v1`), which is a flat-rate **SuperGrok /
  Premium+ subscription**, not the metered `XAI_API_KEY` API. The published
  per-token prices therefore do not apply to this path; searcher spends
  subscription allowance, while xAI capacity is also reserved for X search and
  Imagine video rather than adding another worker to the Max weekly pool.

  **Searcher stays on grok-4.3**, which xAI positions for *tool calling and
  instruction following* — the right shape for link-first retrieval, and whose
  reasoning can be switched off entirely (`none`). It is on the
  reasoning-capable allowlist
  (`model_metadata.py:370-410`), so its `reasoning_effort` really is sent as
  `reasoning: {effort: …}` — it is not a no-op. Non-allowlisted Grok models
  have the field dropped on purpose, because xAI answers an unsupported
  `reasoningEffort` with HTTP 400.

  **A lapsed xAI OAuth does not degrade searcher to its lower tiers.**
  Credential resolution fails before the request is built, so the agent aborts
  with `xAI OAuth state is missing access_token` and `fallback_providers` never
  engages — searcher stops dead rather than falling through. The same gate hides
  the `x_search` tool from the schema, which `hermes doctor`
  reports as `x_search (missing XAI_API_KEY)`; that wording is misleading,
  since the tool prefers the OAuth bearer and only falls back to the API key
  (`tools/xai_http.py:243-310`). Re-authenticate with `hermes model` from the
  **default** profile — never with `-p`, which would write the worker's own
  `auth.json` and shadow the inherited credential.
- **Codex** — every profile except searcher carries `openai-codex` /
  `gpt-5.6-sol` (`base_url: https://chatgpt.com/backend-api/codex`), as T1 on
  researcher and T2 on the Anthropic profiles. Researcher's primary chain and
  Creator's Codex-first image chain make this a shared pool, not a
  researcher-only tier. The former `gpt-5.6-terra` profile routes were
  promoted to Sol; the engineer-pipeline's OpenCode ProviderLadder remains a
  separate model-routing layer.
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
  `deepseek/deepseek-v4-flash` (`engineer`, `writer` tail). Researcher and
  searcher gained vision in the 2026-07 copilot removal as a side effect of
  standardizing on mimo.

Optional: set `delegation.model: google/gemini-3.5-flash` on default /
assistant to route `delegate_task` subagents to a cheap model.

### Fable and the Max weekly pool

No profile currently leads with Fable 5 (the planner profile that did was
retired in the v5 rebuild), but the facts below still govern any future
Fable tier:

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
   At t+61s the primary is restored and Fable is retried. Once the weekly cap
   is hit this costs **one wasted request per turn until the week rolls
   over** — acceptable only on a low-turn-count profile, never on the
   latency-sensitive assistant.
4. **Adaptive thinking, not manual budgets.** Modern Claude — Fable 5 included —
   gets `thinking: {type: adaptive}` + `output_config: {effort: …}`, so the
   effort level passes straight through (`minimal→low`, `ultra→max`); the
   legacy 4k/8k/16k/32k `budget_tokens` table does **not** apply. Long
   structured outputs prefer `high` over `xhigh`: Hermes can otherwise burn
   the whole output budget on reasoning (`conversation_loop.py:2600`). If
   that warning ever appears, drop to `medium` or raise `max_tokens`.

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

Built and verified through v4 (2026-07 → 2026-08-03): the six specialists,
the assistant gateway (keychain-pure LaunchAgent, Telegram-only per #40695,
`dispatch_interval_seconds: 15`), model chains (doctor + live probes), and
the v4 contract's Phase 7 verification (89 tests, live canaries, subscribed
QA). Active model slugs confirmed 2026-07: `anthropic` / `claude-opus-5`,
`xai-oauth` / `grok-4.3` (searcher T1), `openai-codex` / `gpt-5.6-sol`
(researcher T1 + fallbacks), OpenRouter tails `xiaomi/mimo-v2.5` (vision),
`minimax/minimax-m3` (image+video), `deepseek/deepseek-v4-flash`
(text-only).

**Workflow v5 rebuild (2026-08-06)** — driven by the 45s-PV postmortem (38
cards / 9 hours, over half spent on registration accidents, packaging
repair, and QA admission protocol): the v4 shape system, double approval,
fan-out manifests, digest/probe admission, QA cards, and the planner/qa
profiles were retired. Heavy work now runs in resident specialist sessions
(`resident-session.sh`: per-key serialization, session-id recapture,
close-on-acceptance; smoke-tested against creator with retained context);
the assistant owns planning (one conversational approval), the quality gate
(contracts under `orchestration/references/qa/`), and GitHub bookkeeping;
the board shrank to fire-and-forget / cron / mass-parallel / `scheduled`
with a lean card contract. The completion path-guard plugin, admission
probes, and the 5-minute orphan watchdog were removed (the sweeper and the
guarded block resolver remain); the validator now enforces workflow
contract v2. Remaining live verification: a real short-video production run
through the new flow.
