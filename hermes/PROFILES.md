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
   human (terminal)     human (Telegram × 4 bots + Discord)
          │                │        │        │        │
        default        assistant engineer creator marketer   ← four PRIMARY bots
        (CLI)              │      (all adapters live in ONE multiplex gateway
          │                │       process, hosted by default; + dispatcher)
          └──────┬─────────┘
                 │                        A2A peer graph (localhost HTTP):
        ┌────────┼──────────────────┐       assistant → engineer creator marketer writer
        │ resident sessions         │       engineer  → marketer researcher writer
        │ lean kanban cards         │       creator   → engineer marketer researcher writer
        │ delegate_task             │       marketer  → engineer creator researcher writer
        ▼                           ▼       (writer / researcher: receive-only endpoints;
  hermes -p <specialist>   anonymous subagents      searcher: no peer — classic
  chat --resume <id> / ~/.hermes/kanban.db          delegation paths only)
```

Four profiles are **primaries**: assistant (the original front door),
engineer, creator, and marketer each run their own Telegram bot, all
hosted by ONE `gateway.multiplex_profiles` process (see "Gateway as a
persistent service"). Bots exchange work over the **A2A platform**
(localhost JSON-RPC, `specialist_call` for Assistant/Creator and raw
`a2a_call` for Engineer/Marketer against the per-profile `a2a_agents`
peer list — configured peers only, never a direct URL; Telegram itself
cannot carry bot-to-bot traffic). writer and researcher serve inbound
A2A requests but initiate nothing; searcher keeps the classic
resident/kanban/delegate paths and no A2A endpoint.

Heavy interactive work runs in **resident sessions**: the assistant starts a
persistent `hermes -p <specialist> chat` conversation through
`specialist_call(kind="work")`, backed by `assistant/scripts/resident-session.sh`,
and supervises it turn by turn. Short `kind="inquiry"` requests use configured
A2A peers; the route and target remain pinned for the conversation. The plugin
is restricted to assistant (engineer, creator, marketer, writer, plus resident
searcher) and creator (engineer, marketer, researcher, writer, image-creator,
video-creator, audio-creator). This entry point does not grant assistant
direct researcher access or expose delegation tools to the hands profiles.
Live messaging receives a background completion; nested resident/CLI calls
wait synchronously. See [Specialist Calls](README.md#specialist-calls) for
ownership, uncertainty, and A2A inbound lifetime limits.
The board remains for work where conversation adds nothing.

Verified against the source clone
(`~/ghq/github.com/NousResearch/hermes-agent`):

- **One shared board.** The kanban DB is anchored at the base
  `~/.hermes/kanban.db` via `get_default_hermes_root()` — *not* profile-scoped
  (`kanban_db.py:264-284,429-431`). Every profile reads/writes the same board.
- **One gateway powers everything.** Since the 2026-09 multiplex rebuild the
  gateway runs as **default** with `gateway.multiplex_profiles: true`: the one
  process hosts every served profile's adapters (assistant Telegram + Discord,
  the engineer / creator / marketer bots, the A2A endpoints) plus the embedded
  dispatcher, which sweeps **all** boards each tick
  (`gateway/kanban_watchers.py`). Secondary profiles never start their own
  gateway, and per-profile cron stores are ticked individually by the same
  process.
- **Workers are spawned through the PATH `hermes`.** The dispatcher launches
  `hermes -p <worker> … chat -q "work kanban task <id>"` as a subprocess,
  resolving `hermes` via `shutil.which` (so our `bin/hermes` shim is used) and
  inheriting a copy of the gateway's env with `HERMES_HOME` overridden
  (`kanban_db.py:6705-6837,6607`). Workers therefore get the `global` + `hermes`
  Keychain layers injected automatically — **no per-worker secret is needed.**
  In-gateway turns are different: under multiplex, scope-aware reads (bot
  tokens, provider and web-search keys) resolve ONLY from each profile's
  secret scope, filled from the Keychain by `secrets.command` →
  `scripts/profile-secrets.sh` (see "Secrets layering").

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
| **assistant** | primary: messaging front door; A2A peers engineer/creator/marketer/writer | Telegram + Discord | `~/Workspaces` | `web,browser,terminal,file,vision,x_search,skills,todo,memory,clarify,delegation,cronjob,computer_use,kanban,a2a` + `unreal-engine` MCP | served | yes (token per-machine) |
| **engineer** | primary: supervises OpenCode: assess (read-only) / implement (from the assistant's plan session or an Issue; delegated worktree bootstrap in a repo the assistant created), under an Authority grant; planning documents, repo creation, and GitHub bookkeeping stay with the assistant; A2A peers marketer/researcher/writer | Telegram (own bot) | `.` (launch / task ws) | `terminal,file,web,skills,todo,memory,delegation,a2a` | served (bot + a2a :9902) | yes |
| **researcher** | verified conclusions from released units: evidence-pack / tradeoff-matrix / fact-check / guidance; heavy breadth is requested from the orchestrator as a search unit; serves engineer/creator/marketer only (not the assistant), cards refused | — (A2A receive-only) | `.` (launch / task ws) | `file,web,vision,video,skills,memory,delegation` | served (a2a :9906) | yes |
| **searcher** | retrieval from released units: lookup / sweep / hunt (multi-hop via `goal_mode` on cards) | — (specialist) | `.` (launch / task ws) | `web,x_search,skills,memory` | — | yes |
| **creator** | primary: plans with human/assistant clients, delegates served image/clip/speech forms, gates evidence and delivers; remaining technics cover images, authored video and assembly of supplied parts; music/song generation is withdrawn | Telegram (own bot) | `.` (launch / task ws) | `terminal,file,vision,image_gen,video_gen,video,tts,skills,memory,delegation,a2a` + gen plugins + `unreal-engine` MCP | served (bot + a2a :9903) | yes |
| **image-creator** | Creator's hands for still images: runs one `<verb>/<subject>` leaf from a filled form (icon family: source / create / generate / edit / analyze; emoji family: create / generate / edit / analyze), QA with evidence, report; answers only Creator | — (A2A receive-only) | `.` (launch / task ws) | `terminal,file,vision,image_gen,skills,memory` | served (a2a :9907) | yes |
| **audio-creator** | Creator's spoken-audio hands: generate/edit/analyze-speech from approved forms; measured/readback QA, no claims of listening; no music or voice registration | — (A2A receive-only) | `.` (launch / task ws) | `terminal,file,tts,skills,memory` | served (a2a :9909) | yes |
| **writer** | reader-facing prose and producer-facing scripts from released units (outline / piece / whole job); draft-only, never publishes; serves all four primaries | — (A2A receive-only) | `.` (launch / task ws) | `file,web,skills,memory,delegation` | served (a2a :9905) | yes |
| **marketer** | primary: platform copy from released message units, four-stage pre-ship inspection, grounding judgment, and publishing only within a Publish grant; A2A peers engineer/creator/researcher/writer | Telegram (own bot) | `.` (launch / task ws) | `terminal,file,web,browser,x_search,vision,skills,memory,delegation,a2a` | served (bot + a2a :9904) | yes |

The table lists each role's native capability allowlist. `platform_toolsets` is
the runtime authority; top-level `toolsets` mirrors it and retains `kanban` on
the two front doors for the runtime gate. Dispatcher-spawned workers receive
task-scoped Kanban lifecycle tools automatically. Platforms without MCP access
carry the `no_mcp` denial sentinel; assistant CLI/Telegram/Discord and creator
CLI instead name only `unreal-engine`, which prevents inheritance of future MCP
servers. Worker Telegram / Discord lists and default's messaging lists are empty
by design.

Role split: **the assistant** plans with the user, supervises specialists,
performs the quality gate itself (the QA contracts under
`profiles/assistant/skills/assistant-pipeline/references/quality-assurance/`), owns GitHub bookkeeping, and
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
`profiles/assistant/skills/assistant-pipeline/references/quality-assurance/` (vision on images/frames, ffprobe on av
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
| L1 requirements | user ↔ assistant | chat + risk/ambiguity-driven `clarify` | the approved plan + unit decomposition (one gate): registered purpose Issues or the assistant's OpenCode base plan session | what/why: goal, done criteria, constraints, grant posture |
| L2 detail | assistant ↔ engineer | resident-session turns — the assistant releases one unit per turn (engineering defines no card units) | session registry + replies | how: unit release/pacing, feasibility, plan revision, in-grant calls |
| L3 implementation | engineer ↔ OpenCode | `opencode run` (the unit cycle: per-unit plan runs/forks) | Issue/outline text + git history + session reports | how (detail): phase split, tactics, model, verification |
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
comment thread + git. In L3 the engineer consumes **released units**: a
purpose Issue grounds a fresh plan run; a Wave forks the assistant's
approved base plan session (`run -s <base> --fork`). Each unit ends with
verify → commit → a report carrying the session ids, and the engineer
stops at the unit boundary until the next release (batch runs only under
an explicit grant); review/debug primaries run as fresh read-only
sessions. Two bridges wire L3 to OpenCode's non-interactive
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
job closes — always relayed to the user. GitHub bookkeeping stays with the
assistant, split by the write boundary: merges and board sync are its own
direct `gh` work, while Issue/epic registration runs through an OpenCode
session in the repo (codebase-grounded bodies) — all after approvals.
Details: engineer's `engineer-pipeline` skill and the front-door pipeline.

The dialogue discipline is specialist-generic, not engineer-specific:
**creator** and **writer** also honor the `Review: required` gate; creator
speaks the same protocol with a **Budget** grant as its Authority analog
(generation-spend caps; defaults 4 image variants / 2 video renders per
asset + 1 corrective pass, expanded only via `AUTHORITY+:`), leaves
`PROGRESS:` per finished asset, and — since a task's scratch workspace
survives block/crash respawns (deleted only on completion) — resumes by
inventorying surviving intermediates instead of re-spending credits.
Creator consumes **released units** (anchor / part / assembly) whose
deliverable-defining decisions the assistant fixed in its plan family
leaves; a spec gap or implied composite returns as a finding, input
parts are consumed verbatim, and the production boundary keeps every
content-altering transform on the creator side (the assistant handles
bytes, never re-encodes). Details: creator's `creator-pipeline` skill.
**writer** consumes released units the same way — an outline unit
(structure + tone samples, gated before drafting), piece units against
the approved outline, or a whole small job — under a non-waivable
four-pass review floor, returning undecided deliverable-defining
choices as spec-gap or granularity findings. Details: writer's
`writer-pipeline` skill. **marketer** speaks it with a
**Publish** grant (publishing is public and irreversible: absent grant =
draft-only + an `APPROVAL:`-headlined block — `kind=needs_input`, always
relayed to the human like `REVIEW:` — showing the exact post
text/attachments/destination; `P1` = consuming approved inventory within
named caps — account, post count, content scope — never new claims),
leaves `PROGRESS:` with the posted URL per post, and treats shipped posts
as immutable facts on resume. It consumes **released message units**
(settled claim + fact-ledger references + QA-passed parts) under a
non-waivable four-stage pre-ship inspection (mechanical / style /
factual / legal); strategy, offers, pricing, and calendars stay with the
assistant, and open decisions return as spec-gap or granularity
findings. Details: marketer's `marketer-pipeline` skill.
**searcher** consumes released retrieval units the same way — a lookup
unit (settled question), a sweep unit (coverage claim/floor + per-item
fields), or a hunt unit (done criteria + scope exclusions) — under the
link-integrity and retrieval-only floors, returning undecided briefs as
spec-gap or granularity findings; its two catalog cards are the
card-eligible forms of sweep and hunt. The assistant's search plan
leaves (`plan/search/`) fix the decisions, and search QA gates each
unit against lookup/sweep/hunt contracts (validator-enforced mapping).
Details: searcher's `searcher-pipeline` skill.
**researcher** consumes released depth units the same way — an
evidence-pack unit (settled question + done criteria), a
tradeoff-matrix unit (closed option set + criteria), a fact-check unit
(fixed claims list + source requirements), or a guidance unit
(consumer + decision
points + evidence base) — under the evidence-integrity floor and the
Admiralty/SIFT method, returning undecided briefs as spec-gap or
granularity findings. Research units reach it only from engineer,
creator, or marketer (its A2A peers / session owners) — never from the
assistant directly, and never as cards (the `claim-verification`
catalog unit was retired in the 2026-09 peer rebuild). The assistant's
research plan leaves
(`plan/research/`) fix the decisions, and research QA gates each unit
against evidence-pack/tradeoff-matrix/fact-check/guidance contracts
(validator-enforced mapping). Details: researcher's
`researcher-pipeline` skill.

### Planning ladder — who plans at which altitude

Planning happens at five altitudes. Each owner decides its own altitude only
and hands a typed result to the next owner; one conversational approval
authorizes execution.

| Altitude | Owner | Deliverable | Durable home |
| --- | --- | --- | --- |
| High-level requirement + plan — what outcome, which specialists, what grants | assistant with the user (consulting resident sessions for feasibility/cost) | the approved plan (one `clarify` gate) | chat + the session briefs it produces |
| Repo grounding — unit decomposition for code work | assistant's OpenCode plan session in the repo | purpose split (epic + Issues sized 1–3 PRs) or Wave outline + base session id | registered Issues (purposes) / the OpenCode session (Waves) |
| Low-level requirements — feature → purpose Issues sized 1–3 PRs | assistant Plan mode (grounded via engineer assess turns), user-reviewed | registered GitHub Issues (via an assistant OpenCode run in the repo) | GitHub Issues / Projects |
| Technical milestones — Wave outline for non-Issue work | assistant's OpenCode plan session | Wave list (coarse, one line each) | plan session / worktree outline file |
| Phase decomposition — inside one released unit | OpenCode plan agent (L3) | phase breakdown | OpenCode sessions + git |

Feasibility questions are consultation turns to the relevant specialist
session, not a planning rung of their own.

Two rules keep the ladder from collapsing back into confusion:

- **GitHub-flow repos use Issues as the milestone layer.** When the
  assistant has registered purpose Issues, implement consumes an Issue
  (its body is the spec; the PR closes it) — do NOT also produce a Wave
  outline for the same work. The Wave outline is for repos/work outside the
  GitHub Issue flow (scratch builds, small refactors, non-GitHub targets).
- **Escalation moves one rung at a time** (same principle as the dialogue
  loops): OpenCode's open question goes to the engineer; the engineer's
  material ambiguity goes to the assistant as a `Q<n>` block; only the
  assistant talks to the user.

### Default is the assistant's CLI counterpart (and stays a clean baseline)

default and assistant are the two faces of the same front door: identical
workflow behavior (assistant runs its own `assistant-pipeline`; default runs
the thin `default-pipeline` adapter over the assistant tree at
`~/.hermes/profiles/assistant/skills/assistant-pipeline/references/`), with the
Telegram chat-wide auto-load bound to `assistant-pipeline`,
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
  facts/quotes/URLs; assumptions labeled; the four-pass review floor
  never skipped) + never publishes; marketer = the
  Publish + red floor (absent grant ⇒ draft-only; every post needs verbatim
  approval or in-cap consumption of approved inventory; claims resolve to
  the fact ledger; no price/deadline/scarcity changes; the four-stage
  pre-ship inspection is never skipped; posted URLs verified; shipped posts
  never silently edited or deleted); front doors = heavy work never runs in their
  own turn, deliverables are verified before delivery, and blocked cards
  resolve only through the guarded resolver after the one complete DECISION
  batch; a second block or a capability/spec-gap block pulls the card back.
  Each profile also states its **MEMORY.md policy**: durable cross-task facts
  only (task state lives in the kanban thread + git/board; playbook-sized
  knowledge becomes a skill), and `user_profile_enabled` is off for workers —
  they never converse with the human.
- **skills/** — detailed, on-demand playbooks:
  Every local library uses the same ownership types. A worker has one tracked
  `<profile>-pipeline/` plus tracked, directly selectable `technic/` leaves.
  The assistant owns `assistant-pipeline/` and its mode-first reference
  tree; default owns the shared tracked `default-pipeline/` adapter. Assistant-only
  Telegram surfaces live in `desks/`. Both assistant dirs are private-overlay
  symlinks — maintainer-owned, but tracked by the private-dotconfig repo.
  Runtime-authored skills from background review, curator, `/learn`, or normal
  `skill_manage(create)` calls go to the untracked `learned/` category through
  `skills.create_dir: skills/learned` in every `config.yaml` (an optional
  `category` nests as `learned/<category>/<name>`). Moving a complete package from `learned/` to
  `technic/` is the explicit maintainer-review boundary. External directories
  remain provider-owned and never become local technics implicitly.
  - assistant → `assistant-pipeline` (front-door playbook: modes Chat / Plan /
    Execute / Quality Assurance over tiers inline / resident / kanban; the
    mode-first reference tree at `references/{chat,plan,execute,quality-assurance}/`;
    resident sessions via `resident-session.sh`; assistant-run QA contracts;
    and the closed `card_units` catalog in `execute/**` front matter).      Default
    runs the thin `default-pipeline` CLI adapter over this tree; it records only
    terminal-specific deltas. The assistant also reads the upstream official
    libraries (apple / creative / email / github / media / note-taking /
    productivity / research / smart-home / social-media) plus optional
    `one-three-one-rule` (decision framing) and `watchers` (RSS/API polling
    for cron sweeps) via `skills.external_dirs`; heavy tool-bound creative
    entries (`comfyui`, `touchdesigner-mcp`, `manim-video`, `ascii-video`)
    sit in `skills.disabled` — media production is creator's.
  - engineer → `engineer-pipeline` (resident-only, cards refused; assess /
    implement routing with intent triage; Authority parsing + dialogue
    discipline; the unit cycle over released units with
    permission/question bridges; quota-gated provider/model routing;
    verify/report) + upstream libraries via `skills.external_dirs`: official
    `autonomous-ai-agents` / `software-development` / `github` plus optional
    per-skill dirs `code-wiki`, `rest-graphql-debug`,
    `subagent-driven-development`, `docker-management`, `pinggy-tunnel`,
    `fastmcp`, `mcporter`, and `cloudflare-temporary-deploy` (all key-free,
    script/CLI-based via uv / npx / docker)
  - researcher → `researcher-pipeline` (resident sessions + inbound A2A
    peer requests from engineer/creator/marketer; every card refused —
    the `claim-verification` unit is retired; consumes released units with unit
    discipline — evidence-pack / tradeoff-matrix / fact-check /
    guidance — returning spec-gap and granularity findings, plus
    Admiralty/SIFT source evaluation, citation rules, and the Review gate
    in the kernel; researcher supplies evidence and does not own
    artifact-vs-brief QA; retrieval strategy in references/gather.md) +
    optional research skills via `skills.external_dirs`: `domain-intel` and
    `osint-investigation` (stdlib-only recon / public-records) plus keyless
    `duckduckgo-search` (run through `uvx ddgs`)
  - searcher → `searcher-pipeline` (dual runtime — cards only for the
    `survey-enumeration` / `exhaustive-hunt` catalog units; consumes
    released units with unit discipline — lookup (targeted facts) /
    sweep (enumeration with a coverage claim) / hunt (multi-hop to
    saturation, signalled by `goal_mode` on cards) — returning spec-gap
    and granularity findings, plus the link-integrity floor; per-unit
    playbooks in references/; no technics — the deprecated
    `deep-retrieval` stub was removed in the search rebuild) + keyless
    optional retrieval skills via `skills.external_dirs`:
    `duckduckgo-search` and `domain-intel`
  - image-creator → `image-creator-pipeline` (the hands root: validate
    the filled form → load the leaf → run → QA → report; shared
    `img-postprocess.sh` / `icon-finish.sh` / `emoji-fit.sh`) + leaves
    `source/icon`, `create/icon`, `generate/icon` (styles flat-minimal /
    glass / pixel / line / clay), `edit/icon`, `analyze/icon`;
    `create/emoji` (text emoji), `generate/emoji` (two rounds — anchor
    then pack; packs expressions / gaming / love-hype / meme-classics /
    custom; styles chibi-cartoon / kawaii-pastel / pixel / flat-sticker /
    clay), `edit/emoji`, `analyze/emoji` — see "Creator hands (v3)"
  - creator → `creator-pipeline` v7 — clients and hands: Plan
    (`references/plan.md`: tell the client apart by the message's shape —
    brief lines = the assistant, conversational = a human; fill the leaf's
    form with `clarify` or by parsing the brief; composites = a sequence of
    forms), Build (`build.md`: the handoff text, specialist inquiry / work
    session, supervision, relaying `Q<n>`), Quality assurance
    (`quality-assurance.md`: vision at native size and at the size of use,
    revise as a handoff, delivery). `capabilities.md` is the only router
    (served families first, then the technic table). Families with no
    hands yet keep the technic-era contract under `references/legacy/`
    (produce / direction / advisory + iterate / verify / delivery / resume,
    the MediaBrief `brief.md`, and `card.md` — cards are legacy-only until
    they move to the hands with their family). Legacy runtime: cards only for the
    `anchored-image-batch` / `deterministic-render` catalog
    units; Advisory / Direction /
    Produce routing with intent triage + the unit discipline (released-spec
    consumption, spec-gap findings, verbatim part inputs); the MediaBrief
    validation contract + capability router,
    Budget grant parsing, dialogue discipline, workspace-reuse resume, visual
    verification, and durable-path delivery) + directly selectable in-tree leaves under `skills/technic/`:
    `creator-generated-image`, `creator-article-illustration`,
    `creator-infographic`, `creator-svg-diagram`,
    `creator-excalidraw-diagram`, `creator-text-card`,
    `creator-meme`, `creator-ascii-art`,
    `creator-gif-sourcing`, `creator-generated-video`, `creator-html-motion`,
    `creator-p5js-experience`, `creator-ascii-video`,
    `creator-manim-explainer`, `creator-pixel-art`, `creator-pixel-video`,
    `creator-knowledge-comic`, `creator-brand-asset-sourcing`, and
    `creator-media-assembly`. Leaves own
    one production grammar and its medium QA; styles/presets and same-tool
    modes stay in references. Official creative skills may be implementation
    engines behind these canonical names, but never alternate dispatch
    identities. `creator-html-motion` uses the HyperFrames stack via
    `skills.external_dirs` (`~/.agents/skills` - `hyperframes` is the entry
    point that routes the domain/workflow skills, plus `media-use` for asset
    resolution / captions; new narration is a separate audio-creator input,
    never an external TTS bypass; CLI-owned store, see AGENTS.md). The upstream
    bundled `creative/` + `media/` libraries remain available, while optional
    skills are exposed as a curated set of individual directories (article
    illustration, pixel art, comics, memes, concept diagrams,
    and creative ideation) so the official optional `hyperframes`
    cannot collide with the CLI-owned entry skill (the official optional
    `tldraw-offline` stays unwired for the same reason — the `~/.agents/skills`
    store already owns that name). `unreal-mcp` is wired individually for the
    assistant and creator and backed by their explicit `unreal-engine` MCP
    allowlist. The other MCP-backed entries in that cluster (`blender-mcp`,
    `touchdesigner-mcp`) remain in `skills.disabled` and cannot execute.
    The ambiguous external `pixel-art` name is disabled too; the canonical
    Pixel leaves may use its scripts as opt-in implementation backends but are
    the only stable dispatch identities
  - writer → `writer-pipeline` (resident-only, cards refused; consumes
    released units — outline / piece / whole job — with spec-gap and
    granularity findings, routes assess/write by deliverable, and performs
    one-round tone calibration; TypeTable routes copy/article/docs →
    references/prose.md and 台本/絵コンテ/screenplay →
    references/script.md, with the non-waivable four-pass quality engine
    references/review.md shared by self-review and critique, and
    consultations/critiques in references/assess.md) + external skills via
    `skills.external_dirs`: the Japanese stack via the curated
    `profiles/writer/external-skills/` symlink dir (the single
    `japanese-writing` skill bundling the notation / tech-prose /
    prose-rhythm / business-docs / inspection layers, single-sourced with
    the shared `agents/curated/` store) and upstream `creative/humanizer`
  - marketer → `marketer-pipeline` (resident-only, cards refused; consumes
    released message units under the Publish grant + red floor; engines
    ground / produce / parts / verify / publish — grounding judgment and
    red-team dissent, platform copy craft, QA-passed part consumption, the
    four-stage pre-ship inspection with Japanese ad-law triage, and the
    approval-gated xurl publish bridge with per-post URL verification;
    channel extension points for future Discord/IG/TikTok accounts;
    shipped posts treated as immutable) + the upstream `social-media/xurl`
    and `creative/humanizer` skills via `skills.external_dirs`

  Upstream wiring pattern: official `skills/` libraries attach per category
  directory, `optional-skills/` per individual skill directory, and unwanted
  names are pruned with `skills.disabled` — never `hermes skills install`,
  which would copy into the symlinked repo store. Setup-gated candidates stay
  on the backlog until their prerequisite exists: `sherlock` (docker image),
  `qmd` (~2 GB local models), `scrapling` (browser install), `parallel-cli` /
  `searxng-search` / `agentmail` / `page-agent` / inference.sh `cli`
  (accounts, keys, or servers), `jupyter-notebook` (JupyterLab + hamelnb),
  `media/gif-search` for marketer (`TENOR_API_KEY`), and the `mlops/`
  library (HF-account-centric).

Routing (assistant): `assistant-pipeline` owns it. Telegram auto-loads the skill
through its chat-wide `channel_skill_bindings` entry (root DM plus fixed and
user-created topics). Discord binds the allowlisted guild channel explicitly;
auto-created threads inherit that parent binding and channel prompt. Discord DM
bindings require the literal DM channel ID and cannot use a user-ID wildcard: the
first authorized DM is bootstrap-only, then its channel ID is added to both
`channel_skill_bindings` and `channel_prompts`, the gateway is restarted, and
`/new` starts the first working session. The gateway injects the skill body into
the session's first turn; `compression.protect_first_n` keeps it alive; existing
sessions pick it up after `/new` or an idle reset. Every working request flows
Classify → Locate → Mode
(Chat / Plan / Execute / Quality Assurance) → Deliver. Questions are risk/ambiguity driven:
a settled request does not pay an interview tax. Tier selection is by context
dependence, not size: `inline` for conversation/quick local work, a
**resident session** for anything the user will give feedback on (the
default for heavy work), and a lean kanban card only for fire-and-forget,
cron-originated, mass-parallel, or `scheduled` work. Plan mode ends in one
conversational approval that sanctions the grants; Execute supervises the
sessions turn by turn; QA verifies actual artifacts before delivery.

The kanban catalog is closed: its machine-readable surface is the union of
`card_units` front matter across `assistant-pipeline/references/execute/**`.
A card must match one unit and carry every required input; otherwise the work
stays resident or is decomposed during planning. Composites are never one card
(never send 0→10 as one card). Seeded units are creative:
`anchored-image-batch`, `deterministic-render`; and search:
`survey-enumeration`, `exhaustive-hunt`. Engineering, writing, marketing,
and research are card-free (the research `claim-verification` unit was
retired in the 2026-09 peer rebuild; fact-checks now travel through the
researcher's A2A peers). All six worker pipelines fail fast at the
Unit gate with `kanban_block(kind=capability)` for composite or malformed cards.

The pinned Telegram topics are Assistant-owned **desks**, not worker threads:
Personal binds `personal-desk` (household-budget / People / message-reply plus
personal docs/data), Projects binds `project-desk` (the `pj` registry,
workspace scaffold, and project docs/data), Brainstorm binds `brainstorm`, and
Inbox has no skill because it is only the delivery target for system cron
output. Each desk fixes the tier to `inline`; work that needs a specialist
hands off to a new ad-hoc topic, which inherits chat-wide `assistant-pipeline` and
owns the sessions. The fifth Telegram pin remains a UI-managed rotation slot
rather than a configured topic. Kanban completion notifications remain
attached to their originating topic; only maintenance/report/sweeper cron
output targets Inbox: jobs keep bare `deliver: telegram`, while the gateway
launcher derives `TELEGRAM_CRON_THREAD_ID` from the ignored runtime config's
Inbox topic. Time-deferred work parks in `scheduled` via `hermes kanban
schedule <id> "until=<ISO8601> — <reason>"`; the assistant's no_agent
`kanban-scheduled-sweeper.sh` cron releases due cards every 15 minutes. Dead
cards close via `hermes kanban archive <id>`. Only terminal events
(completed / blocked / gave_up / crashed / timed_out) wake the assistant;
 comments do not. Workers batch questions into one `needs_input` block, and
 the assistant answers once via `DECISION(Q<n>):` comments plus
 `kanban-resolve-block.sh apply`. A second block, any `capability` block, or a
 spec-gap question pulls the card back for a resident session or re-plan.

`auto_decompose` stays off — decomposition is a conversation, not a runtime
fallback. `delegate_task` covers medium parallel lookups the user is actively
waiting on, and absorbs per-artifact QA checks on large sets. Keep routing in
sync with each `profile.yaml` description.

## Creator hands (v3, 2026-09)

Creator's production is moving, one asset family at a time, out of the 23
generic `creator-*` technics and into **hands** profiles — `image-creator`
(A2A `:9907`), `video-creator` (`:9908`), and `audio-creator`
(`:9909`) — each a receive-only A2A endpoint with the tools of its medium
and nothing else. Two earlier shapes failed in opposite directions and this
section exists so the third does not repeat either: the technics
**decided nothing** (a "generated image" leaf that accepts any size, look
and tool still needs the whole spec written from scratch, so 23 assistant
plan leaves + a QA index had to be sewn to them 1:1), and the
`refactor/creator-profile` branch **governed everything** (director + three
hands + menu.yaml + generated MENU.md + presets + cross-media Styles +
palette roles + grammars: thirteen interpretive layers between a request
and a tool call, the same choice encoded in five places, and the docs drifted
before the branch was done). The v3 rule is: **one skill = one concrete
deliverable = one form**, nothing above the skill but a reader.

### Card family

Card now has four image-creator leaves: create/generate/edit/analyze-card.
Destinations are values of one subject (OG, social, headers, thumbnails, title
cards, X pair/carousel and custom WxH), not a menu or a new profile. The shared
card.py owns file-spec rendering/fit/measurement; create/card destination front
matter and CSS blocks are canonical. Generate styles own backdrop prompt prose
only. Exact text is font-rendered after generation; proposed allowance 3+1
across resumes requires explicit current-work user budget approval before paid
calls. Renders are local, isolated and exclusive; previews prove only local
appearance. Pair 7:8 is unverified, carousel scroll with 3 images user-observed,
X article 5:2 user-verified ratio only; all pixel defaults/gaps are authoring
choices. Do not post tests or inspect authenticated accounts without consent.
Retirement gate: keep creator-text-card and private-overlay 1:1 mapping until
handoff coverage, paid backdrop validation and old caller migration are proven.
New Card work routes to hands first; no changes to ports/toolsets/secrets.

### Client model

Creator has **clients**, not entry points. A client is either the human
(Creator's own Telegram bot) or the assistant (resident session / A2A,
carrying a SessionBrief). Creator's job is the same for both: pick the
skill, **fill its form** — with the `clarify` tool when the client is
human (Telegram renders one inline button per option; the form's
`options` become the choices, `other: true` is the UI's own "Other" row),
by parsing the brief when the client is the assistant, returning a text
`Q<n>:` block for whatever required field it cannot fill, hand the filled form to the hands, gate the
result against the intent (visual inspection or audio evidence), deliver.
The hands never see the client or invent its requirements: they receive a
filled form or return `Q<n>:`. A leaf may own creative execution within that
form (MV direction, for example), with its explicit proposal approval gate.
The assistant keeps
delivery to the user, the durable path, Budget lines and GitHub bookkeeping;
it no longer makes creative decisions on Creator's behalf, so the
`plan/creative/<family>.md` leaves and the QA `Covers` mapping retire family
by family as hands skills land (Phase 4 of the migration).

### Skill tree

```
profiles/<hands>/skills/
  <hands>-pipeline/
    SKILL.md                 # <=40 lines: validate form -> load leaf -> run -> QA -> report
    scripts/                 # helpers shared by several leaves (e.g. img-postprocess.sh)
    <verb>/<subject>/
      SKILL.md               # name: <verb>-<subject>  (one deliverable, one form)
      references/styles/*.md # this leaf's style notes only — never cross-media
      assets/reference-*.*   # optional: a sample the leaf has actually produced
      scripts/
```

- **Verbs** (closed set): `create` — drawn deterministically from inputs
  (script / SVG / grid; free); `generate` — a model draws the pixels or the
  waveform (free local synthesis or metered provider); `edit` — transform an existing asset (free unless the
  edit itself generates); `source` — fetch a published asset and record its
  license (free); `analyze` — inspect an existing asset and return findings,
  not new/repaired media (free). Most analyze leaves return reply findings;
  analyze-ad may retain its report and evidence at an explicit deliver path
  for a later creative brief, never a new ad. The `create`/`generate` boundary is whether a
  generation model is asked to draw.
- **Cost is independent of verb.** `free` means no metered media-provider fee,
  not zero reasoning cost or unlimited compute. Local speech synthesis still
  has a take allowance: one take plus one corrective per script by default.
  Failed synthesis invocations count. Long free work still uses resident sessions.
- **Subjects** are concrete nouns (`icon`, `hero`, `clip`, `voice-line`),
  **unique across all hands** because Creator reads every hands' tree through
  `skills.external_dirs`; the validator rejects a subject that appears under
  two hands. `name` equals `<verb>-<subject>` and equals the path.
- The pipeline root holds no router and no lifecycle beyond the five steps
  above; discovery is Creator reading the leaves' front matter directly. No
  generated index, no `menu.yaml`, no preset layer, no shared Style system,
  no palette vocabulary above the leaf. A leaf's execution-environment traps
  (Japanese `。` in an argv string trips the terminal guard → text travels as
  a file; foreground terminal calls die at 420 s → long renders run
  `background: true` and are polled; vision holds ~3 images → contact sheet
  first, then one frame at a time with the finding written down) are written
  into that leaf's Procedure, not into a shared note.

### The form (front matter is the only representation)

```yaml
---
name: generate-icon
description: >-
  <one sentence: what this leaf delivers, from which inputs — the only line
  Creator needs to choose it>
version: 1.0.0
metadata:
  hermes:
    category: hands
    hands: image-creator
    cost: metered                      # free | metered
    output: "icon_<slug>_<size>.png (transparent, square) + .svg when vector"
    form:
      what_for:   {required: true,  label: "何のアイコンか", example: "Slack 通知 bot"}
      style:      {required: true,  options: [flat-minimal, glass, pixel, line, clay], other: true}
      background: {required: false, options: [transparent, brand-fill, tile], other: true}
      reference:  {required: false, type: image, label: "参照画像のパス"}
      note:       {required: false, type: text}
---
```

Field keys: `required` (bool), `label` / `example` (interview prompts),
`options` + `other: true` (a controlled vocabulary that still accepts a
free value — the leaf's `references/styles/<option>.md` backs each listed
option), `type` (`text` default, `image`, `file`, `path`, `int`). `note` is
the escape hatch every leaf carries. The SKILL.md body has exactly three
sections — `<Procedure>`, `<QA>`, `<Report>` — no Goal / Inputs / Presets
sections, because `description` and `form` already say that.

If a field has options and its leaf has `references/<field>/`, every
listed option must have a matching Markdown file. `style` keeps its
existing mandatory `references/styles/` mapping. This lets kit content
tables live under `references/contents/` without a generated registry.
Theme uses `references/themes/`; an explicit `references` declaration makes
option backing mandatory even when the directory is missing. MV keeps style
(rendering), theme (world vocabulary) and direction (staging) within one leaf.
Multi-value text fields describe their comma-list syntax in the label;
`other: true` permits that string at intake, and the leaf validates each
member. An option is not a requirement to generate every default item:
Creator confirms the expanded item list and spend before batch production.

### Handoff message (Creator → hands, A2A or resident session alike)

```
skill: generate-icon
intent: new | revise <path of the previous delivery>
deliver: ~/Workspaces/Projects/<Group>/.agent/deliverables/<job>/
budget: 4 variants + 1 corrective          # media calls or local speech takes
form:
  what_for: Slack 通知 bot のアプリアイコン
  style: glass
  background: transparent
  reference: /path/to/ref.png
  note: 青系、角丸は控えめ
```

The selected Group must already exist. Its `.agent/deliverables/<job>/`
directory and job-owned descendants (such as `video-plan` or `music-plan`)
are accepted by all three hands; the Group root itself and
`~/Workspaces/.deliverables/<job>/` remain valid for existing callers.
A job directory may be created beneath an existing parent, subject to the
leaf's exclusive-output checks. Never create a new Group or relocate a
valid Group-local job merely because it is below the Group root. This is
an operating contract, not a filesystem sandbox or upload/overwrite consent.

The hands reply with the leaf's `<Report>` (paths, every QA check with its
evidence, spend) or with one batched `Q<n>:` block naming the missing
required fields — never with a substitute. A request no leaf fits is a
finding back to Creator (`no skill fits: …`), which Creator relays to the
client and records for the maintainer; neither side improvises a leaf.
Short free single-reply leaves use `specialist_call(kind="inquiry")`; anything
metered, multi-turn or longer than one reply window uses `kind="work"` from
Creator. Continue with the same target and returned conversation_id. Released
inputs, permissions, budgets and the exact handoff text are unchanged. CLI
calls wait within a finite deadline; A2A inbound cannot launch work and must
ask its caller to reissue the unit through a work conversation.

### Ad family

`ad` belongs to video-creator. The first release is `analyze-ad` and
`create-ad`; `generate-ad` and PV are planned, not advertised capabilities.
No legacy technic or mapping is retired. Both leaves use specialist
kind="work" even though media-generation cost is free.

An Ad addresses a specific audience with a promise and intended action. A
PV primarily introduces a subject's qualities, experience or world. Both
may contain a CTA, so neither CTA presence nor duration alone routes them.
Product categories stay form values, not separate ad skill families.

- `analyze-ad` reads one local <=60-second video for reference or review:
  measured metadata, timestamp-labeled overview, at most two dense windows
  and three native detail looks, then a timeline, visual construction,
  persuasion, issues and production handoff. Source claims are quoted as
  claims, not inherited client facts. Report observations, interpretations
  and unknowns separately; no provenance/model/conversion guessing. The
  helper uses clip-media's probe and only writes exclusive local evidence
  directories. Remote video analysis needs explicit yes and at most one call;
  image vision keeps the normal profile policy. No audio-stream-to-listening
  inference. Technical-only questions stay analyze-clip, even what_for: ad.
- `create-ad` authors a 6..30-second, 30fps HTML/CSS/GSAP ad from
  approved copy and local assets. Aspect selects 9:16 (1080x1920, default),
  16:9 (1920x1080), 1:1 (1080x1080), or 4:5 (1080x1350). Changing ratio
  means re-layout and a separately approved plan/source/preview, never a
  scaled or cropped old composition. Existing version-1 plans without
  aspect remain portrait; validation does not insert the new field or alter
  their hashes. Default office/bold-graphic/claim-led each
  has a concrete leaf-local reference; custom values override defaults.
  It does not generate media, synthesize speech, capture, or load external
  runtime skills. Client-finished PCM WAV and muted supplied MP4 are inputs.
  Raster product/logo files are validated; no SVG input in this first release.
- Content approval binds plan.json (exact copy/holds, supplied claims,
  complete asset hashes, proof samples). Preview approval binds the frozen
  source/checks/frames before final render. Creator relays both in the same
  work conversation; file hashes are integrity checks, not authentication.
  Local helper primitives come from tour; its existing contracts are not
  changed and no ad layout generator or generic render framework is added.
  Static copy checks do not prove visible text/reading time/claim truth.
  Final decode and visual evidence must retain temporal/listening gaps.

Verification is staged: helper/unit and real local render checks are distinct
from fresh specialist/client-path tests. Do not call direct fixture renders
client-live evidence. Reference video, output frames and jobs stay local and
untracked; never commit a downloaded reference ad or its commercial claims.
The initial local check used 30 overview frames, an 8-frame focused window
and one native detail of a supplied portrait ad, with no remote video call.
A clearly fictional text-only fixture passed real HyperFrames check/snapshot/
render and final full decode at 1080x1920, 30fps, 15 seconds; its three copy
holds were inspected. This proves the local path, not production art quality,
Japanese typography, listening or the two live client entry paths. Those
remain live acceptance work, not claims made by the helper tests. Runtime
identity is bound to preview approval; a changed CLI needs a new preview.
Aspect selection was checked with real local 15-second fixture renders at
all four native sizes, 30fps/H.264/yuv420p, full decode and sampled copy/CTA
inspection. The aspect-less plan/preview byte-preservation test passes. An
older scratch project's independent rescan was blocked by a Finder-created
.DS_Store under its frozen root, not by ratio validation; it was not deleted
or ignored to make the check pass. This does not relax frozen-source rules.

### Music-video family

`video-creator-pipeline/generate/music-video/` serves `generate-music-video`, not a collection of
character-mv/product-mv/character-loop combinations. Subject is a form input;
the distinct deliverable is a short MV-style progression with performance,
coherent world and highlights rather than clip's silent single shot. Existing
`video_generate` and `clip-media.py` remain the generation/finish path. No new
provider, API wrapper, gateway endpoint, TTS or external skill is introduced.

User shorthand "MV" routes to generate-music-video. This is a skill name/path
rename only: `mv_<slug>` output filenames, runtime job paths and historical
artifacts stay unchanged. No generate-mv alias leaf remains. Reissue active
legacy jobs under the new name with a new proposal and client approval,
preserving consumed attempts; never edit frozen old jobs or approvals. Historical
trial names below describe the leaf used at the time, not current routing.
The frontmatter closes within 3800 characters so upstream's 4000-character
discovery scan retains every form field, with room for future metadata.

- Style choices: anime-3d, anime-2d, live-action, mixed-media. Theme choices:
  theater, night-city, dream-garden, graphic-space. Direction choices:
  performance, typographic, montage. All accept free text. These are authored
  reference recipes, not live-render-certified presets. Only chosen references
  load; no menu/index generator or cross-media vocabulary service exists.
- A theme specifies space, materials, light, default colors and opportunities
  for staging. theme_detail/must_keep override those defaults. Theater includes
  both playing-card red/black/white and ice-blue/silver examples: a meaningful
  starting point, not an immutable look or fixed timeline. Style owns rendering;
  direction and tempo choices guide the approved proposal's staging and timing.
- Optional pace (relaxed/steady/snappy/intense) and transition
  (continuous/cut/match-cut/whip/dissolve) are local reference-backed fields,
  both open to free text. New proposals default steady + cut, where cut applies
  only at proposed shot changes, not a mandatory cut count. Snappy means crisp
  action/camera accents and short holds, including the ending; continuous can
  still be snappy without edits. Separate actor/camera/edit speeds may be
  described. Conflicting continuous/cut-montage instructions need resolution
  before approval. Prompt and QA carry these choices, not just the form.
  Tempo changes require renewed approval and never reset spent allowance.
  Existing approved plans without these fields keep their frozen timing/prompt.
  Exact cut timing/BPM is not guaranteed, and a global post-render speedup is
  not a substitute for the requested direction.
- Round A writes a new proposal-v<N>.md with the expanded world, identity lock, short
  beat progression, effective form/input hashes, actual prompt/backend limits,
  sound/finishing choices, consents and call allowance. It makes no media
  generation or remote-analysis calls. Creator shows the proposal to its human
  client through clarify or its assistant client through text. A budget alone
  never authorizes generation.
- Supplied music need not exist for Round A: a textual `music_plan` records
  the producer, specification, duration and music/finishing order. The proposal
  is `pending-inputs` with `can_generate: false`, not a generation release.
  Pending character-image upload consent likewise permits only local planning.
  Creator obtains the separate music production release, then supplies the
  real music_file and resolved consents for a NEW numbered proposal/hash and
  approval. Never mutate or execute the preliminary proposal, invent a WAV/hash,
  reset attempts or ask the client to reselect the already accepted direction.
- Round B continues the same specialist_call work conversation with the exact
  approved_plan path and approval_sha256, unchanged form and inputs. A mismatch
  or changed creative choice needs renewed approval. The digest binds content,
  not identity; this is an agent operating contract, not a tool-level payment
  authorization mechanism. Default 2 variants + 1 corrective counts every tool
  invocation including failures. Unknown results must be reconciled, never
  blindly retried, and the allowance does not reset on resume.
- Audio modes are generated (only when the actual backend advertises native
  audio; NOT advertised by the current xAI-first chain), supplied (silent visual master for separate approved assembly), or
  explicitly silent. A supplied track is not an audio reference sent to the
  model. Reference video stays local or becomes a client's written description;
  the current tool cannot consume reference video/audio. Character-image upload
  consent and generated-video remote-analysis consent remain separate.
- xAI silently caps reference-image requests to 10s even though its general
  capabilities say 15s. Default 10s with character_reference, otherwise 15s;
  reject an explicitly longer reference-mode request before spend. Never change
  the input's role to starting frame or drop it merely to bypass this limit.
- Exact text needs a text-free base and separately agreed finishing; exact
  lyric/beat/lip sync is not promised. No required finish with an unknown route
  may be hidden until after spend. A visual master is needs finishing, not a
  complete musical MV. A MiniMax mention does not reconfigure the xAI-first
  chain or justify pretending an actual output used that model.
- QA covers identity, world, performance/progression, text/audio policy,
  technical decode and budget evidence. Sampled frames do not establish full
  motion or sound quality. Declined/failed remote analysis stays UNVERIFIED;
  model audio findings are not a claim of human listening.

Implementation status: skill/routing and reference recipes added. An actual
assistant-shaped Creator CLI -> specialist_call(kind="work") -> VideoCreator
proposal round passed on 2026-09-07: versioned proposal and matching SHA-256,
expanded red/black/white theater with defaults overridden, four-beat direction,
no approval fields, and zero video_generate/video_analyze calls confirmed in
the session records. The work conversation remains idle awaiting a client
decision. Reference media was only probed/sampled locally, not visually
interpreted or uploaded; direction used the supplied textual description.
The subsequent user-approved silent trial made one video_generate call and no
retry/corrective/remote-analysis calls: xAI/grok-imagine-video returned a
15.041667s 1280x720/24fps result; raw audio was preserved in raw and removed
from the delivered H.264/yuv420p MP4. Full decode passed. Sampled primary-session
review found the requested theater/colors/cards and readable words, but a more
2D-anime appearance, less spatial camera staging and overlapping FLIP/BREAK
than the reference intended. This is one live trial, not recipe-wide quality
certification; temporal continuity remains unverified. Human-client live
handoff remains untested; the actual run used an assistant-shaped Creator CLI.
User feedback accepted the general direction but found action/cuts sluggish.
Version 1.1 adds the tempo controls above; snappy + cut is the proposed next
comparison, not an already-generated improvement. The previous 1-call grant
is exhausted; no additional generation is implied by updating the skill.
The user-authorized snappy/cut comparison then failed on input length: a
5158-byte local prompt (5157 after stripping) hit xAI's reported 4096 limit
and the reached FAL backend's 2048 UTF-8 byte limit. No video was returned;
the failed tool call consumed the second grant, with no resubmission and no
usage/cost returned. Version 1.1.1 separates the detailed direction proposal
from an exact prompt-only file, measured at 1..1800 UTF-8 bytes and hashed
before approval, then rechecked before submission. This is a conservative
limit for the observed chain, not a universal provider guarantee. New text
must be reapproved; failed attempts are never silently refunded or retried.
A subsequent proposal-only run through the same Creator/hands conversation
produced a compact 1683-byte prompt (including newline), independently measured
and hashed. Subject/world/style, snappy hard cuts, sequential lettering and
short ending were retained. No new generation or analysis call was made;
cumulative attempts remain 2/2 and the compact proposal awaits approval and
a new explicit grant. The user then approved that compact prompt and one
additional call: trial 3 succeeded via xAI/grok-imagine-video at 1280x720,
24fps, 15.041667s; silent finishing and full decode passed. Cumulative usage
is 3/3 including the failed length attempt, with no manual retries or remote
video analysis. Sampled comparison shows better sequential word separation,
but blended transition frames and a long-looking raised-card ending remain
despite snappy/cut instructions. This does not certify hard cuts, exact hold
duration or improved playback rhythm; no extra generation/edit was performed.
A user-requested original-recreation experiment then used one more call on
the same xAI text-to-video route, with a primary-authored 1778-byte prompt
grounded in 4fps reference samples rather than the stock theater outline.
Female character details, iris FALL, corridor, door/keyhole and ivory/gold
palette appeared, exposing omissions/conflicts in our earlier prompts. The
sampled result still showed blended transitions and depicted a keyhole without
the specified passage/vortex; object vocabulary did not guarantee camera/object
relationships. Cumulative calls are 4/4; no further retry ran. This is a single
stochastic compliance test, not a MiniMax-vs-Grok benchmark or proof of model
incapacity. Preserve source-specific spatial transitions before adding more
generic pace/style choices; the original's model/inputs/editing remain unknown.
Two further bounded tests used the same text-only Grok route: a 5s isolated
aperture passage (one call, generate-clip) and a 15s integrated MV (one call,
generate-mv). In sampled evidence the isolated camera crosses a growing rim
and continues inside the card/cloth tunnel, but the opening is a round peephole
above a small keyhole, not the intended contiguous keyhole. The integrated
version restores keyhole shape but substitutes blended scenic views for the
crossing/interior continuation; pupil entry is blended too. Cumulative calls
are 6/6, no retries. Unequal duration, narrative load and stochastic samples
prevent a causal model-capacity claim; isolated success is not an integration pass.
Version 1.2 makes source-specific START/CROSS/AFTER relations explicit in the
proposal and compact prompt through local references/spatial-direction.md,
with shape and passage graded separately. Two bounded local review windows
(<=2s,12fps each) may supplement global samples where consent allows; decode
does not prove continuity. Failed critical motion remains a quality gap even
when objects/styles match. Shot isolation or multi-shot production needs its
own release/allowance, never hidden expansion of one MV generation call.
This is additive: clip/tour and the broader legacy video families stay intact;
no legacy technic or assistant QA mapping retires on partial MV coverage.

### Speech family

`audio-creator-pipeline/<verb>/speech/` contains three leaves, not a second
menu system. Its model/fallback/auxiliary pins mirror ImageCreator's; tools
are terminal/file/tts/skills/memory, with no vision, generation-image/video,
outbound A2A or external skill library. The existing profile secret helper
already accepts this profile; a dedicated empty Keychain layer is not required.

- `generate-speech`: one approved UTF-8 script, up to 600 characters. `voice`
  is `house` or a qualified registered ID. House may use online Edge fallback;
  local-only requests choose a qualified local voice. Style/seed require the
  selected engine's advertised capabilities and are never silently dropped.
  Default one take plus one corrective, including failures; packaging retries
  reuse raw audio and do not spend a new take.
- `edit-speech`: approved-order concatenation, boundary-only silence trim,
  pitch-preserving speed, measured two-pass normalization, format conversion.
  No new synthesis. New bundle only, preserving originals; at most 64 inputs
  and 600 seconds. Valid unchanged sidecars reuse exact decoded-duration
  offsets; timing changes require fresh ASR. A stale matching sidecar fails.
- `analyze-speech`: input format, decode, loudness/peak/silence and optional
  script readback, returned as findings without a deliverable file.

The shared `speech-media.py` keeps WAV + `.words.json` + SRT + `.take.json`
together (48 kHz mono PCM master; optional Opus or MP3 derivative). It uses
the already-cached faster-whisper `base`, never a download or installation.
Caption times are estimated from ASR, not forced alignment. Exact normalized
text matches are PASS, near matches WARN, missing/mismatched speech FAIL;
coverage cannot excuse missing foreign words. None verifies pronunciation,
emotion or voice likeness. Returned tool identity/seed and decoded PCM hashes
are evidence, never a fabricated listening claim. ASR confidence is retained.

Live verification (2026-09-06): English house narration produced a 5.520 s
WAV/Opus pair with zero clipping and -15.52 LUFS. Japanese qualified-voice
renders with identical script/style/seed produced identical decoded PCM in
two distinct takes (6.680 s, -18.99 LUFS, zero clipping). Japanese house
also rendered successfully but retained an unresolved low-confidence ASR
substitution. The word/number spelling differences remained WARN, without
automatic corrective synthesis. The joined Japanese pair measured 13.560 s,
with the second timeline offset by 6.880 s, and normalized to -16.08 LUFS
(WAV) / -16.07 LUFS (Opus), -1 dBTP and zero clipping. Analysis returned
findings without an audio output.

Natural-language and Assistant-shaped Creator CLI requests each called the
configured audio-creator A2A peer exactly once. Receiver sessions executed
the edit, not Creator; both delivered unchanged-duration 6.680 s masters at
-16.18 LUFS and -1 dBTP, carrying readback warnings. An incomplete Assistant
brief returned a text Q1 with zero takes. These are CLI/two-client-shape
checks, not a native Telegram interaction test or a prolonged soak.
The caller-owned resident-session wrapper also ran analyze-speech against
the English Opus file, returned findings with zero takes, and was closed.
The gateway owns :9909 in the same process as the other peers; startup took
about 95 s to audio readiness and 133 s overall. Agent-card HTTP 200 and
listener ownership, not launchctl's return, prove readiness. A premature CLI
`Unknown toolsets: a2a` warning occurred while plugin discovery was pending;
actual A2A calls succeeded. Do not add a second gateway to work around it.

Final ownership cutover exposed a different upstream defect: after Creator
lost character-voice, its warm `tts` toolset memo hid AudioCreator's correctly
registered character tools. The local Hermes checkout at `4f0309e9cf` now
adds profile scope to `resolve_toolset`'s cache key; the real-registry
regression failed before the fix and passed afterwards in both warming
orders. Upstream's canonical toolsets test file passes (26 tests); dotconfig
also carries a real-resolver guard to catch loss of the fix during updates.
The fix lives in the hermes-agent checkout as `fix/toolset-profile-scope-memo`
merged into `local` — a runtime dependency of this migration, not a file here.
After restarting with that fix, a fresh Creator A2A catalog request exposed
character_voices on AudioCreator and returned both local engines and their
supported controls, with zero synthesis takes. Creator's character tools
remain disabled; no permission widening was needed.

Migration: speech's old voice card, assistant plan/QA contract and canonical
TTS special case are retired. Character-voice tools register only for
audio-creator; Creator retains generic TTS for conversational replies only.
The former AudioCraft/HeartMuLa/songsee technics and assistant plan/QA routes
are deliberately withdrawn without replacements, per the agreed scope.
Music/SFX/song generation and standalone audio visualization are future
families, not external-skill fallbacks. Existing audio may still be supplied
to a legacy assembly.

Recovery points: public tracked baseline `8b392d9` and private-overlay
baseline `2d12e8d`. Restore only task-owned configuration/routes from those
revisions if withdrawing this change; do not reset other work. Remove the
audio-creator peer/external-root/allowlist entry together and restart the
single gateway after restoring the old routing/plugin ownership. Keep all
audio, sessions, models and voice data. Existing ignored menu/hub state was
left intact; upstream seeded SKILL.md was retained as `SKILL.upstream.md`.
The existing broken private persona link was repaired by supplying its
missing private target; no personalized file was overwritten.

### Tour family

`video-creator-pipeline/create/tour/` serves `create-tour`, a new subject:
recreate from reference/design/text, edit supplied local footage, or capture an
explicitly approved sanitized Web demo for a <=60-second UI walkthrough.
Creator owns what_for/audience, semantic flow, fidelity and choice approvals;
VideoCreator authors task-local HTML/CSS/GSAP, state changes and camera/pointer.
No per-step screenshots or client-written steps JSON are required. Frame and
decorative background are separate from faithful product internals; simplified
UI is explicitly approved/labeled, never invented real-product functionality.
Intro/outro default ON (title-reveal/result-hold). The three references for each
are examples with other:true, not exhaustive presets. Custom directions remain
verbatim with concrete authored beats; only explicit none omits. Ambiguity goes
back as one clarification or proposed beat, never nearest-preset fallback.
Styles can also be authored locally beyond flat/glass/outline, without a registry.
Reference is inspiration/context, source is actual local footage, target is an
operation destination. None is capture consent. Omitted screen_mode preserves
recreate/v2 behavior; explicit recreate/supplied/capture uses v3 proposal approval.
Only VideoCreator's narrow capture.py wrapper operates sanitized Web demos under
approved scope. Native capture, login recording and privacy redaction are unavailable.
Narration consumes finished audio-creator WAV plus
current words.json; video-creator has no TTS or external runtime skills.

Creator routes this free leaf with `specialist_call(kind="work")`, never raw
A2A or a direct resident script. `authored.py` freezes v2/v3 source/contract/form,
checks real renders and publishes fresh preview/final evidence with full decode.
It does not generate layout or enumerate UI actions. The unchanged `tour.py`
direct entry remains usable for actual persisted v1 screenshot projects and
v1 scaffold calls; no migration or v2 interpretation of old forms is promised.
Only small IO/media primitives are shared, not the old composition engine.
GSAP core is vendored from npm 3.14.2 with hash/integrity provenance and its
own Standard No Charge license, not the skill's MIT license. Authoring is allowed
in task-local source, never managed scripts or frozen projects. Helpers are not
a sandbox for untrusted downloaded HTML; source must be reviewed before execution.
The portable skill-authoring validator's directory-name warning is intentional:
Hermes names nested leaves `<verb>-<subject>` (`create-tour` in `create/tour`),
with structured Hermes metadata and the established author/version fields.

Projects freeze source copies and hashes. Preview=yes authors/freezes/checks/
snapshots only; client approval resumes that unchanged project into a fresh
final directory. Changed fields need a new project/preview. Existing runtime
data, input files, deliveries and failed evidence are never deleted or
overwritten. Real render/decode and sampled contrast/layout evidence are
distinct from human task correctness, temporal quality and listening.

Verification belongs to `scripts/tests/test_tour.py` (v1) and
`scripts/tests/test_authored_tour.py` (v2); authored visual fixtures live under
`scripts/tests/fixtures/authored-tour/`. Synthetic render tests
are not earned product-live evidence; human-conversational and Assistant-
brief-shaped two-client handoffs remain pending until explicitly exercised.
Legacy v1 verification (2026-09-06, after independent review): 108 targeted tests plus 14 subtests
passed, including actual desktop/mobile MP4s, all decorative frame variants,
preview approval/tampering, text overflow and a timed synthetic WAV render.
HyperFrames 0.8.30 and ffmpeg 8.1.2 were exercised; sampled authored-text
contrast passed (desktop 12/12, mobile 11/11). English OCR ran locally;
Japanese language data was absent and its actionable failure was tested.
Timeline construction/registration is synchronous; only font-dependent
layout guards wait for fonts. Goal/first-step RGB hashes differ in both
previews and decoded MP4 frames, without requiring every step to differ.
OCR TSV preserves literal quotes and skips rows missing text. Tests default
to the system temp directory (TOUR_TEST_ROOT overrides it), clean ordinary
fixtures and intentionally retain only render-test evidence.
No gateway restart is needed for the on-disk implementation; loaded sessions
may retain their earlier contract. This subject does not retire or alter
creator-html-motion, legacy routes, clip/speech helpers or global 1:1 mappings.

Authored v2 verification (2026-09-07): the selected tour/clip/video-routing and
profile-validator suites passed 155 tests plus 18 subtests (3 opt-in legacy
render tests skipped). HyperFrames 0.8.30 rendered a 20-second illustrative
Light/Dark UI and 8-second overview, result-first, free-text and explicit-none
alternatives. All five have 13 distinct decoded sample hashes, full decode and
nonzero contrast audits. One contrast warning per video samples the hint hidden
behind the intentionally opaque modal; it is not a claim of zero findings.
Headless fixture checks cover selection, modal, partial/full typing, save,
four pointer contacts and reverse seeking. Browser pixel comparison records
hashes and permits only <=48 RGB channel differences of <=1/255 (observed
four one-unit pixels), never content or geometry drift. Main/alternate renders
are direct local evidence, not live Creator/hands sessions or real macOS actions.

Reproduce only with explicit local fixture-render approval and a new physical
scratch child (Pillow Python, installed HyperFrames/ffmpeg; no installs):

```sh
python scripts/tests/fixtures/authored-tour/example.py --root <fresh-absolute-child> --variant main --render
python scripts/tests/fixtures/authored-tour/audit.py <rendered-fixture-root>
node scripts/tests/fixtures/authored-tour/seek.mjs <installed-hyperframes-package.json> <headless-browser-binary> <rendered-fixture-root>
```

#### Footage And Capture v3

The same leaf preserves frame/style/background/backdrop/free-text intro/outro.
Creator proposes semantic steps from goal/audience/start_state and optional flow;
clients need not write action scripts. An explicit mode first returns only
proposal-vN.md and SHA-256. The proposal's `tour` block binds the normalized form
and capture scope. Creator relays client approval in the same work conversation;
hashes bind bytes, not caller identity. Approved reconnaissance precedes approved
stateful recording. Changed scope needs a new proposal, not per-click approval
inside the existing scope. Exact preview approval remains a separate final gate.

`footage.py` fully decodes and trims local raw video at 1x, validates source
ranges, and records explicit keep/mute audio and source-to-timeline mapping.
Raw limits (300 s / 512 MB each, 1 GB selected inputs) are independent of final
<=60 s and prepared <=64 MB / bundle <=128 MB. `<video>` remains moving footage,
with unique id, muted/playsinline and framework-owned timing. Keep uses a separate
timed audio element. No screenshot replacement, fabricated event timings or
double cursor. Raw/source hashes, proposal and logs stay private, outside final.

`capture.py` runs installed agent-browser via the existing terminal surface.
It binds a private namespace/config/session to the job/proposal, holds an
exclusive flock, independently caps reconnaissance at four sessions and recording
at two takes per job (failures counted across proposal versions), checks origin/tab
state before/after actions, rejects arbitrary eval/navigation/login/upload and
unapproved selectors/data, and fsyncs pending action evidence before dispatch.
Recording replaces the context and leaves the old tab: only that verified owned
tab is closed, then page state and fresh snapshot are checked. Interruptions
retain raw/unknown actions; recovery closes only the owned session and cannot
replay an interrupted approval. SIGKILL cleanup relies on a private idle timeout
and explicit lease recovery, not a finally-block promise.
Unknown-selector discovery can use v1 recon, v2 recon plus an interrupted first
take, then v3 recon plus the reapproved second take. Recon under the exact current
proposal is still mandatory; no consent or evidence is relabeled/reused, and new
proposals cannot reset either budget or permit a third take.

Launch capture/recon/recovery using terminal background:true and notify:true from
the outset; save its terminal session_id and poll/wait only that process. A 180 s
scope can exceed the profile's 180 s foreground timeout after cleanup/validation,
so never retry a terminated foreground recording as a workaround. The browser
closes before probing/decoding; ordinary browser subprocesses are capped at 20 s
and the remaining <=180 s lease, stop/close at 20 s each, ffprobe at 180 s and
decode at 360 s. Validation subprocess work is <=540 s, the normal capture path
<=760 s plus bounded-size IO/scheduling. Background terminal timeout is not a
lifetime cap: supervise with bounded process waits and a 900 s operating cutoff,
then terminate only the owned terminal process and reconcile/recover its lease.
Do not replay interrupted approvals or launch a duplicate after a wait timeout.

This is a wrapper boundary, NOT a terminal/website sandbox. Existing terminal
access can bypass it; operating contracts forbid bypass. Agent-browser domain
filtering and post-action origin/tab checks do not guarantee arbitrary websites
are safe: GET/page scripts can mutate state, and popup/redirect loading can occur
before detection. Only approved controlled sanitized demos qualify. Source crops
are decorative, not verified privacy redaction. No new plugin/toolset or broad
browser/computer_use grant was added; cli/a2a retain terminal and existing scoped
registry rules. No global permission, dependency or gateway change is required
for the local wrapper.

Native proof gate: cua-driver 0.23.2 start_recording has only output_dir and
record_video; video captures the main display, not a scoped window. Existing
driver TCC grants were observed read-only, not changed or tested by capture.
Native remains blocked until continuous window-scoped capture AND a shared
desktop-action guard covering Assistant's existing computer_use are proven.
Never route around this through Assistant or full-desktop capture/cropping.

Local verification uses `scripts/tests/test_tour_footage.py` and
`scripts/tests/fixtures/captured-tour/`. The opt-in proof serves a dummy modal,
typing and scrolling UI only on loopback, records continuous WebM in an isolated
browser, trims it, and renders with HyperFrames 0.8.30. It is not a product-live
or two-client Hermes handoff. No durable client destination or model session is
selected automatically. Run with an existing physical scratch parent:

```sh
python scripts/tests/fixtures/captured-tour/proof.py --root <fresh-absolute-child> --render
node scripts/tests/fixtures/captured-tour/seek.mjs <installed-hyperframes-package.json> <headless-browser-binary> <project> <fresh-seek-output>
python scripts/tests/fixtures/captured-tour/audit.py --project <project> --final <final> --out <fresh-audit-output> --supplied-audio <fresh-audio-fixture>
```

Measured local v3 proof (2026-09-07): 10.2 s continuous WebM of a real loopback
dummy page, trimmed to 10.1 s and rendered into a 20 s 1280x720/30 fps H.264 MP4
with intro/outro. Full decode passed. Five source-time samples match forward and
reverse HyperFrames runtime seeks with identical screenshot hashes; decoded
source/final alignment is checked separately with explicit lossy pixel tolerances.
A separate supplied fixture adds a synthetic 440 Hz tone: keep produced nonzero
audio only in the footage window, with silent intro/outro. This is not a browser
audio-recording or subjective listening claim. Live local boundary tests exercised
password rejection, popup detection, redirect/GET side effects and SIGTERM with
retained raw evidence and blocked replay. Unit tests cover leases, recovery,
budgets, mode/approval integrity, media ranges and the unchanged legacy paths.
Primary-session safety review was followed by independent review, which found
two issues: the combined recon/take ceiling prevented the
documented second-take recovery flow, and capture lacked explicit background
execution/polling guidance. Both were addressed with separate budgets, a retry
provenance regression, background/recovery instructions and browser closure before
bounded media validation. Independent re-review confirmed both fixes and approved
the revised code within the documented limits. The follow-up targeted run
passed 137 tests plus 18 subtests (3 skipped); the full plugins/scripts run with
live local capture enabled passed 748 tests plus 64 subtests (4 skipped). Both
skill validators passed with only the existing untracked/Hermes-portability
warnings. A fresh real loopback acquisition, decode, preparation and freeze also
passed after the browser-close ordering change; that follow-up did not rerender
the already-proven MP4. Native capture remains
pending/blocked; review did not establish window-scoped recording or shared
desktop exclusion. Existing real probes demonstrated config/namespace/session
isolation arguments, record-start tab IDs and fresh-context behavior; they do not
prove isolation from every future agent-browser configuration surface.

Activation: the profile skill roots are already linked by install.sh, so new
children are visible through those directory links; verify links read-only.
Do not run the project-wide installer just to refresh this leaf. Loaded resident
sessions can retain old instructions; use a fresh approved work session for the
new contract. Gateway restart, native activation and real two-client handoff are
separate gates and were not performed. Rollback without rewriting data: route
new work to recreate, stop only owned capture sessions, preserve private evidence,
and resume old v1/v2 projects with their existing entry points. Do not delete or
downgrade existing v3 projects; render them with the version that created them.

Fixture variants are test cases only: `main`, `overview`, `result`, `custom`,
`none`. They are not production presets. The production helper has no such
dispatch. `reviewer-deep` reviewed the helper and its follow-up fixes; verifier
ran the scoped tests and both validators. Profile warnings are newly untracked
managed files until committed; portable skill warnings are the documented Hermes
metadata/nested-name exceptions. No gateway restart or live handoff was performed.

### Clip family

`video-creator-pipeline/<verb>/clip/` is the first video hands family:
one short shot, not a generic film-production workflow. The profile uses
the same main/auxiliary model settings as image-creator, keeps native image
vision, and has video generation/analysis but no TTS, image generation,
outbound A2A or external skill directories. Later deterministic families
may call HyperFrames through their own scripts; no external menu/router
is pulled into this one.

- `generate-clip`: 1-15 seconds, silent MP4, requested 720p, text or one
  starting image and one appearance reference. Styles are cinematic,
  flat-animation, clay, pixel or described. Default: 2 variant attempts +
  1 corrective total; failures count. Pixel is an aesthetic, not a proven
  sprite grid. Exact model capabilities are checked before spending.
- `edit-clip`: trim/contain-or-cover/mute/encode one <=60-second segment.
  MP4/WebM use optional two-pass byte targeting and an actual cap check;
  GIF checks its cap without silently changing size/fps. GIF repeat is
  playback metadata, never proof of a seamless loop. Outputs are exclusive
  and fully decoded before publication. Odd exact dimensions are refused;
  an original odd-sized clip is padded up, not cropped down.
- `analyze-clip`: findings on one <=60-second clip, no new video; `deliver`
  may be omitted. Original-file metrics, bounded sample frames and optional
  one-call whole-clip analysis are separate evidence sources. Frame times
  in `frames.json` are seek positions, not exact decoded PTS.

`clip-media.py` is the shared stdlib/ffmpeg helper (`probe`, `frames`,
`edit`); tests cover real MP4/WebM/GIF, trim, audio, SAR/rotation, byte caps,
odd dimensions and preservation of existing paths. GIF trimming happens
before palette generation and palette buffering is bounded. `free` means
zero media-generation calls, not zero reasoning/analysis cost. Uploading
an input image (`upload_inputs`) and remote video analysis
(`remote_analysis`) need separate consent. No means local sampled review
with temporal/audio quality unverified. Large authorized movies get a
proxy BEFORE the single analysis call; the ~50 MB limit is on base64.
The profile disables xAI persistent public storage; localize temporary
URLs immediately. No create-clip/source-clip leaf is invented: authored
motion and licensed stock sourcing are separate future families.

Live checks (2026-09-06): hands CLI edited a synthetic test pattern to
160x90, one second, silent H.264; local-only analysis respected no-upload
and reported temporal checks unverified; missing generation inputs stopped
with Q1/Q2 and zero generation. One generated clay-ball shot returned
1280x720, 24 fps, 3.041667 s. QA caught opening-frame clipping instead of
accepting it. The first analysis exposed an upstream-deleted
`_download_video` import; the MiMo plugin now calls `_download_media` and
has real-import handler tests. Analysis of the SAME shot then succeeded
and corroborated the framing defect, with no new generation. The initial
shot used the upstream persistent-storage default before it was disabled;
that pre-existing hosted artifact is not deleted by this config change.

Creator natural-language and Assistant-shaped CLI briefs both reached
video-creator through A2A with matching source/destination/fit/trim/mute/
format/slug fields (job directory and note differed), and produced matching
160x90/1 s/9378-byte outputs. Initial runs exposed two workflow limits:
loopback A2A carries an IP, not a verified profile name (a verbal origin
confirmation proves nothing); supplemental inline pixel scripts can hit
approval timeouts. The contract now states the transport limitation and
keeps edit QA to the existing helper plus bounded vision checks. Native
Telegram interaction and prolonged soak remain separate verification.
After that correction, fresh natural-language and Assistant-shaped runs
each completed with ONE A2A handoff (97 s and 92 s respectively), no
origin-confirmation round or supplemental approval block. Both outputs
are byte-identical to the direct hands CLI edit (SHA-256 verified).
The caller-owned resident wrapper was also exercised with missing
generation fields and a zero-call budget: it returned Q1/Q2, recorded the
video-creator session in Creator's registry, and was closed after the test.

Migration/rollback: keep `creator-generated-video` and its assistant
plan/QA mapping for explicitly requested legacy coverage, notably local
ComfyUI. That clip migration retired no other video/audio technic or card;
the subsequent speech retirement is described above. A failed served clip is a finding, never a
silent fallback. To withdraw the new route, remove the video-creator peer,
external skill root and served-clip routing plus the multiplex allowlist
entry, then restart the single gateway; leave artifacts and session state
intact. The pre-change tracked state is commit `47f9374`; do not reset a
working tree over other changes. Prior ignored learned content is retained
(the menu-era video-render-environment skill is disabled), and bundled
hermes-agent residue is retained as `SKILL.upstream.md`, not an active leaf.

### Kit family

`image-creator-pipeline/<verb>/kit/` carries all five verbs. The family
is game props and UI images, not website components or 3D mesh files.
The user-facing starting fields are `what_for`, `style`, `contents` and
optional `reference`. `contents` is a comma-list; explicit `items` is the
whole list, replacing defaults. State variants are named items and count
toward the generation budget. Unknown styles/categories remain possible
through described inputs, with item sizes settled before production.

- `generate-kit`: pixel, 3d-render, cel-shaded, hand-painted, flat-vector
  and described looks. Round A proposes style sheets containing examples
  from the selected categories; it stops before production. Round B
  needs approved sheet, item list and design lock. Defaults: 3 candidates,
  then 1 call/item + ceil(n/4) correctives; over 24 items requires explicit
  budget. Shared reference guidance does not guarantee exact state geometry.
- `create-kit`: deterministic flat-vector/pixel buttons, panels and bars,
  with state colours, SVG/PNG pairs and tested 9-slice borders. Its UI
  geometry is deliberately simple, not a generative style renderer.
  Flat-vector requires installed librsvg; no lower-fidelity fallback.
  Window slice insets protect the title band as well as the corners.
- `edit-kit`: lossless native-frame atlas or explicit fitting/palette
  changes; transforms may invalidate existing pivots/slicing metadata.
- `analyze-kit`: measured dimensions/alpha/palette plus visual findings;
  absent expectations remain GAP. It never performs a repair.
- `source-kit`: Kenney page discovery and CC0-verified ZIP retrieval,
  selected files under assets, source license and SHA-256 provenance.
  ZIP paths/symlinks/case collisions and decompressed size are checked
  before publication. READMEs are preserved, never quoted as licenses.

`kit-images.py` is the shared local image helper (stdlib + ImageMagick):
fit, palette, atlas, measure. Atlas/measure have a 64-file limit and
reject nonempty output directories; split large kits into category
subsets and use fresh QA directories after corrections. Alpha bounds
come from alpha, not colour trimming: a hollow frame touches its canvas
corners and must not be cropped to its transparent interior. Palette
remapping detaches/reattaches alpha with scoped ImageMagick operations;
tests assert actual hues, not only a palette-size ceiling. Pixel native
intermediates live outside the final assets tree.

Verification (2026-09-06): all five leaves were exercised through the
image-creator CLI. A generated forest kit used one style sheet and three
item calls (4 total); approval stopped the first round correctly.
Independent normal/pressed drawings drifted in width and decoration,
and native inspection found magenta fringes missed by reduced sheets
and `key_px=0`. Failed assets remained marked in the manifest. Free
re-finishing from saved raws with `--cutout key --fuzz 30` removed the
fringes; exact state registration remains a `create-kit` use case, not
something a shared style anchor proves. Zero-call-cost finishing is
allowed even when the image-call grant forbids retries.

The deterministic pixel fixture produced eight assets, lossless atlas
crop round-trips, fixed state silhouettes and 9-slice corner checks.
Inspection correctly warned about pale borders on white. Tests also
cover title-band preservation, translucent alpha, palette hues and
hostile ZIP fixtures. Kenney sourcing delivered four selected arrows
with verified license/provenance. Two client-shaped Creator CLI runs
verified assistant brief -> generate-kit style question (zero spend),
and human request -> source-kit through the named image-creator A2A
peer -> delivery. A React component-library near miss stayed outside kit.
These are smoke fixtures, not a claim that every style has earned
production use. A further round (2026-09-06) went beyond that CLI smoke:
a full Creator session invoked the image-creator resident and resumed it
across two client-shaped brief turns, stopping Round A for the same
style-sheet approval gate before Round B batch production in the same
specialist session and Creator's own QA in the parent session. Independent
raw-pixel inspection
of that batch's potion/herb and inventory-panel assets (outside the style
sheet, which stays full-colour and is not native-pixel proof) found all
12 opaque colours inside the supplied palette (below the 16-colour cap),
binary 0/255 alpha, every
aligned 2x2 RGBA block matching its native source, and `kit.zip`'s CRC
and byte coverage exact across its 24 packaged members. Four image calls
were used (one sheet, three items); the resident session was closed after
accepting the test evidence. The taller potion was an approved fixture
variance; a small herb tie and minor panel-edge shading remain caveats.
Continued soak against real Telegram/client jobs remains future work; no legacy
technic is retired for kit because no existing family maps to it 1:1.

### Migration

Family by family, each step verified before the next: (0) contract +
validator, (1) `image-creator` skeleton, (2) the family's leaves proven from
the hands' own CLI with a pasted filled form, (3) Creator routes that family
to the hands while every other family stays on its technic, (4) the
assistant's plan leaf and the creator technic for that family retire, (5)
soak from both clients and record what the form got wrong. The first family
is `icon` (`source` / `create` / `generate` / `edit` / `analyze`). Nothing is
retired in bulk; `refactor/creator-profile` is read only for scripts worth
porting (`icon-fetch.sh`, `tour.py`, `explainer.py`, `item-loop.py`).

**Creator's own pipeline is shaped for this** (v7, 2026-09-05): Plan →
Build → Quality assurance, with the technic-era routes parked under
`references/legacy/` for the families still to move. Each family that
lands on a hands deletes its technic, its assistant plan leaf and QA
contract, and — once every family it covered has moved — its card. When
the last family moves, `legacy/` goes, and so do `image_gen` /
`video_gen` / `tts` / `unreal-engine` from Creator's toolsets.

Done 2026-09-05 (icon): steps 0-4 — validator rules, `image-creator`
(:9907, in the multiplex allowlist), the five leaves each proven from the
hands' CLI, Creator routing icon to the hands (`references/hands.md`,
`a2a_agents.image-creator`), `creator-logo-icons` retired together with
the assistant's `plan/creative/logo-icons.md` and the `icon-set.md` QA
contract. Both client paths verified from the CLI: a human sentence →
`a2a_call` with the filled `source-icon` form (56 s end to end); an
assistant SessionBrief without a style → `generate-icon` form filled and
ONE `Q1:` on `style` with three options, no spend. Pipeline v7 verified
the same way plus a legacy family (an OG text card → `creator-text-card`,
zero spend, 57 s). Step 5 (soak from the Telegram bot and from assistant
sessions) is open.

Done 2026-09-05 (emoji): the second family, same steps. Prerequisite
found on the way: the `image-fallback` chain never declared
`capabilities()`, so `image_generate` hid `image_url` /
`reference_image_urls` from every profile — fixed in the plugin (the
chain reports the first available member's surface and skips text-only
members for image-carrying calls). One shared script, `emoji-fit.sh`,
is the only home of the platform table (slack / discord 128 PNG,
telegram 512 WebP + stroke, telegram-emoji 100 WebP, line 180 PNG;
`--spec` prints a row for `analyze-emoji`). `generate-emoji` is the
first TWO-ROUND leaf: without `anchor` it draws three character sheets
and stops; `intent: revise` + `anchor:` draws the pack on that one
reference. Earned on Lethe (12 expressions, telegram): identity held
across all twelve; the pack needed `--cutout key` (background trapped
between long side locks and the shoulders — unreachable by the corner
flood at any fuzz) and four correctives, every one of them a prop that
had vanished at 32 px — so the expressions pack now writes every prop
large, saturated and off the hair, and `thinking` carries a blue "?"
instead of a skin-on-skin hand. `create-emoji` (文字絵文字, Hiragino
Sans W8, text via an items FILE) and the two free leaves earned on the
same pack: `edit-emoji` re-cut it for Slack, `analyze-emoji` found white
steam invisible on white hair and that a 12-tile strip exhausts a run's
vision looks (packs over six are read in halves; an unreached check is a
GAP). No technic retires with this family — emoji never had one —
and there is no `source-emoji` on purpose: `source-icon` with
`icon: twemoji:<name>` covers published glyphs. Both client paths
verified from the CLI: a human sentence (three text emoji for Slack) →
`create-emoji` form → `a2a_call` → three files delivered with the hands'
QA relayed; an assistant brief without a style → `generate-emoji` form
filled and ONE `Q1:` on `style` (plus a `Q2:` offering the prior
approved anchor to skip round A), zero spend. The human run also caught
the hands patching `text-emoji.sh` in place — the contract said report,
not patch — so `skill-topology` now blocks writes into tracked skill
roots at the tool layer.

Done 2026-09-05 (mascot): the third family, same steps, three leaves —
`generate-mascot` (two rounds: three full-body concepts + a silhouette
sheet, then `anchor:` + `pack:` turnaround / poses / custom),
`edit-mascot` (background swap incl. a chroma key that re-composites the
cut-out on flat `#00ff00`, head / bust crop, resize, outline — never a
recolour) and `analyze-mascot` (square / cut-out / silhouette / 64 px /
light-dark / measured palette vs asked / identity vs anchor). No
`source-` or `create-mascot` on purpose: a mascot is designed, not
fetched, and a first-party mark becomes an icon set. The finish is
`mascot-fit.sh` (corner flood or global key, `key_px` in its RESULT).
Earned on Forge (a work-robot, game-2d, electric blue + storm grey):
the FIRST run never reported — it looked 152 times at three candidates,
because each image leaves the context three looks later and the model
had written nothing down between looks; the pipeline root now requires
every finding appended to `qa.md` before the next vision call, and round
A is exactly three looks (sheet, silhouette, the recommended one at
native size — no per-candidate look). Same run: on a white `<bg>` the
finish's `key_px` counted eye whites and speculars (thousands on a
clean cut-out), so a mascot is drawn on chroma green (magenta when the
palette has green), never white — and on green the count caught real
background trapped between arms and body and inside the claws, cleared
by `--cutout key` with no coverage loss. The second run: round A in
4 min, round B held identity across eight poses on one corrective (an
`oops` sweat drop too pale and on the head — the emoji prop rule
again). The free leaves on the same delivery: `edit-mascot` re-keyed the
pack for video and cut a head avatar (the 0.40 head default cut the
chin on a big-headed build → 0.50), and `analyze-mascot` found the one
pose whose rig drifted from the anchor (black mitts, long boots) that
round B's own sheet look had passed, plus two instrument lessons — a
20 % key detector read a saturated artwork blue as a leak (now 8 %
around green / magenta only) and a three-colour palette scored FAIL on
its own line-art ink (ink and highlights are tagged, not scored). The
write guard also refused `cp … && <skill script>` as a write into the
skill tree: a skill script runs in a command of its own. Both client
paths verified from the CLI: an assistant brief without a style →
`generate-mascot` form filled and ONE `Q1:` on `style` (three options
with a recommendation), zero spend, 45 s; a human sentence (this
concept, chroma key for video) → `edit-mascot` form → `a2a_call` → the
file delivered with Creator's own measurement of the key, 2 min.

Done 2026-09-05 (reimagine): the fourth family is ONE metered leaf,
`generate-reimagine` — a client's photo re-rendered in a style
(3d-character, comic-book, chibi, 70s-street, 80s-anime, or described)
with the same subject, pose and composition. The photo is the EDIT
INPUT (`image_url`), never a `reference_image_urls` entry; the hands
look at it once and write `subject.md`, the identity lock every look
is judged against (`keep: identity` relaxes it to the subject alone);
one or several styles per form, two candidates each, finished to the
photo's own size next to a photo-plus-candidates sheet per style. No
edit- or analyze-reimagine on purpose: size and format are the leaf's
own fields and identity against the photo is its own QA. Earned on a
rose hedge (comic-book + 80s-anime, then 3d-character as a revise on
the same lock, then chibi from the human path): three of the first
four candidates came back as the photo with a saturation filter — an
edit model keeps the photograph's texture unless told what the picture
IS — so every style reference now opens with a **Medium** line
(redraw / repaint / rebuild / re-photograph; the photo's own texture
must go) and the prompt leads with it; the corrective that did so
passed and every later first pass passed on style. The one shared
corrective left the second style with a named defect and nothing to
spend, so the budget is 2 + 1 corrective PER STYLE. gpt-image-2
transposed a landscape call twice in a row: prompts end with the
canvas spelled out ("a WIDE HORIZONTAL landscape image, do not
rotate"), every raw is measured as it lands, and a transposed raw is
marked failed rather than cover-cropped in half. A corrective rebuilds
the sheet with every candidate; `qa.md` is appended, never rewritten
(one look was lost to a whole-file write). The 80s-anime cues now tell
a figure (cel line) from a place (background art) and forbid opening a
sky the photo does not have; chibi has a reading for a photo with no
figure in it (the touch, not an added character). Both client paths
verified from the CLI: an assistant brief without a style →
`generate-reimagine` chosen, the surviving run on the same photo found
and inspected, ONE `Q1:` on style with the three existing candidates
as options and a `Q2:` on size, zero spend, 100 s; a human sentence
(chibi, one candidate, consent to upload given in the sentence) →
form → hands → delivered in Japanese with Creator's own look and the
hands' maintainer note relayed verbatim, 1 call, 5.5 min. Creator's
plan.md carries the consent rule: a human client hears that the photo
leaves the machine in the SAME clarify round as the style, never
after.

## Models and fallback chains

Each profile carries its own `model:` (tier 1) plus a `fallback_providers:`
list (tiers 2+). `fallback_providers` is **per-turn**: it triggers on errors
(429 / 5xx / 401 / 404 / malformed) and the primary is restored on the next
turn. The default profile already proves the YAML shape.

The fleet is split across the two subscription pools by role (2026-09-05).
Most profiles lead with **Claude Fable 5.1** for judgment, long-context work
and prose, and fall to **Claude Opus 5** before ever touching the OpenAI pool.
**Researcher**, **creator** and creator's hands lead the other way, on **GPT-6
Astra**. Every chain then keeps a role-appropriate OpenRouter tail, and a hand
inherits its parent's tail so it can still eyeball what it produced.
**Searcher** is unchanged
on `xai-oauth` / grok-4.3: xAI capacity is reserved for Searcher, X search and
Imagine video. The coding model inside OpenCode is a separate layer entirely —
engineer-pipeline drives a **fixed ladder** whose top rung splits by run type
(reading runs lead with `claude-fable-5-1`, writing runs with `gpt-6-astra`),
descending only on an error or a spent pool, never by pre-judging the task's
weight.

| Profile | T1 (primary) | T2 | T3 | T4 | `reasoning_effort` |
| --- | --- | --- | --- | --- | --- |
| **default** | `anthropic` / claude-opus-5 | `openai-codex` / gpt-5.6-sol | `openrouter` / `xiaomi/mimo-v2.5` | — | `medium` |
| **assistant** | `anthropic` / **claude-fable-5-1** | `anthropic` / claude-opus-5 | `openai-codex` / gpt-6-astra | `openrouter` / `xiaomi/mimo-v2.5` | `medium` |
| **engineer** | `anthropic` / **claude-fable-5-1** | `anthropic` / claude-opus-5 | `openai-codex` / gpt-6-astra | `openrouter` / `deepseek/deepseek-v4-flash` | `high` |
| **researcher** | `openai-codex` / **gpt-6-astra** | `openai-codex` / gpt-5.6-sol | `anthropic` / claude-opus-5 | `openrouter` / `xiaomi/mimo-v2.5` | `medium` |
| **searcher** | `xai-oauth` / grok-4.3 | `openrouter` / `xiaomi/mimo-v2.5` | — | — | `low` |
| **creator** | `openai-codex` / **gpt-6-astra** | `anthropic` / claude-fable-5-1 | `anthropic` / claude-opus-5 | `openrouter` / `minimax/minimax-m3` | `medium` |
| **image-creator** | `openai-codex` / **gpt-6-astra** | `anthropic` / claude-fable-5-1 | `anthropic` / claude-opus-5 | `openrouter` / `minimax/minimax-m3` | `medium` |
| **audio-creator** | `openai-codex` / **gpt-6-astra** | `anthropic` / claude-fable-5-1 | `anthropic` / claude-opus-5 | `openrouter` / `minimax/minimax-m3` | `medium` |
| **writer** | `anthropic` / **claude-fable-5-1** | `anthropic` / claude-opus-5 | `openai-codex` / gpt-6-astra | `openrouter` / `deepseek/deepseek-v4-flash` | `medium` |
| **marketer** | `anthropic` / **claude-fable-5-1** | `anthropic` / claude-opus-5 | `openai-codex` / gpt-6-astra | `openrouter` / `xiaomi/mimo-v2.5` | `medium` |

**`default` stays on Opus 5 deliberately** — every `--clone` inherits its
chain, and a neutral starting point should not lead with the model that has a
sub-cap.

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
(`chat_completion_helpers.py:1668,1846`). **There is no per-tier effort knob
in 0.21.0** — `agent.reasoning_overrides` is a *session* concept
(`gateway/session_state.py:226`, driven by `/model`), not a config key, so a
profile's single `agent.reasoning_effort` applies to every tier in its chain.

Model facts confirmed during the build (live `provider_models_cache.json` + test
calls):

- **Anthropic native** — every profile except `researcher` / `creator` /
  `searcher` leads with `anthropic`
  (`base_url: https://api.anthropic.com`), on `claude-fable-5-1` for the
  five judgment/prose profiles and `claude-opus-5` on `default`. OAuth
  resolves from the global Claude Code credential/token rather than
  per-profile `auth.json`. **Fable 5.1 is not in the `hermes model` picker** —
  `/v1/models` lags the alias, so the curated list stops at `claude-fable-5`.
  It is written straight into `config.yaml` instead; live one-shot calls
  confirm the slug resolves and answers (2026-09-05), and
  `get_model_context_length` already reports 1M for it via the `claude-fable`
  prefix entry.
- **GPT-6 Astra (T1 on researcher / creator)** — reached over the same
  `openai-codex` OAuth path as Sol. Hermes identifies itself honestly
  (`originator: hermes-agent`, `User-Agent: HermesAgent/<ver>`,
  `agent/codex_headers.py:49-59`) and the Codex backend serves Astra to that
  identity; verified with a live one-shot call (2026-09-05). Like Fable it is
  **absent from the picker** (`DEFAULT_CODEX_MODELS` in
  `hermes_cli/codex_models.py` stops at the 5.x series and live discovery did
  not return it), so it is config-only; `get_model_context_length` resolves
  1,050,000 locally, so no `hermes update` is required for it.
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
- **Codex** — every profile except searcher carries an `openai-codex` tier
  (`base_url: https://chatgpt.com/backend-api/codex`): Astra as T1 on
  researcher, creator and image-creator, Astra as T3 on the Fable profiles,
  and Sol as researcher's T2. Creator's Codex-first image chain uses the same
  pool, as do OpenCode's `build` primary and `debugger` subagent — so this one
  ChatGPT Pro subscription now carries both harnesses. The former `gpt-5.6-terra` profile
  routes were promoted to Sol; the engineer-pipeline's OpenCode ProviderLadder
  remains a separate model-routing layer.

  **Sizing the shared pool.** On Pro 5x, Astra meters at roughly 25-225
  messages per 5h window for the whole account. Move to Pro 20x when either
  signal repeats: the OpenAI meter (`npx -y @slkiser/opencode-quota show`)
  drops under ~15% partway through a window on ordinary days, or the
  Astra-first profiles and OpenCode Build visibly fall through to their T2
  more often than they run on Astra. **The upgrade needs no config change** — the same chains
  simply stop descending.
- **Auxiliary models are pinned, not `auto`** (2026-09-05). `auto` resolves to
  the profile's own main provider *and main model*
  (`agent/auxiliary_client.py:7-15`), so compression, title generation, triage
  and the rest were all running on the profile's most expensive model. Every
  task except `vision` and `web_extract` is now pinned to a cheap sibling on
  the same pool — Claude profiles to `anthropic` / `claude-sonnet-5`, Astra
  profiles to `openai-codex` / `gpt-5.6-luna` — each with a `fallback_chain`
  to `openrouter` / `deepseek/deepseek-v4-flash`. Two safety nets already
  exist below that: the configured chain (`auxiliary_client.py:3887`) and a
  last-resort hop to the main agent model (`:3801`), so a pinned aux model
  never becomes a single point of failure. **`vision` deliberately stays
  `auto`** — pinning it disables the main model's native image vision (see
  `AGENTS.md`).
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

Five profiles now lead with **Fable 5.1** (assistant, engineer, writer,
marketer; creator carries it at T2). These facts govern that tier — they were
measured on Fable 5 and the 5.1 alias behaves the same way:

1. **Fable is not a separate quota tank.** On Max it is included but capped at
   **≤50% of the plan's weekly pool**, drawn from the *same* pool as Opus, and
   it burns that pool faster. So `Fable → Opus` only rescues the case where the
   Fable sub-cap is exhausted while the overall weekly still has room. If the
   shared weekly or the 5-hour session limit is what tripped, Opus is dead too
   and the chain correctly continues to Codex.

   **This is why Opus sits at T2, ahead of Astra**, on every Fable profile.
   The sub-cap case is the *long* failure — it persists until the week rolls
   over — and in exactly that case Opus is still alive. Putting Astra there
   instead would hand days of ordinary traffic to the ChatGPT Pro pool that
   OpenCode Build and the two Astra-first profiles depend on. Creator inverts
   the pair for the same reason read from the other side: it leads on Astra,
   so its Claude tiers are the rescue.
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
   over**. Engineer, writer and marketer absorb that cheaply — they are
   low-turn profiles. The **assistant** is the exception: it is the
   latency-sensitive front door, so when the cap is reached, switch its live
   sessions off Fable with **`/model`** rather than waiting out the week. That
   manual escape is what makes a Fable T1 acceptable there at all.
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
  provider since the 2026-07 copilot retirement). The legacy messaging keys
  (`TELEGRAM_*` / `DISCORD_*`) still parked here are IGNORED by the profile
  scopes (filtered by `profile-secrets.sh`) — the per-bot copies below are
  authoritative.
- **`global`** — keys shared with *other* tools (editor, MCP servers, other
  CLIs). Nothing Hermes-specific needs to live here.
- **`hermes-<profile>`** (assistant / engineer / creator / marketer) — that
  bot's own `TELEGRAM_BOT_TOKEN` + `TELEGRAM_ALLOWED_USERS` (assistant also
  `TELEGRAM_HOME_CHANNEL` / `TELEGRAM_DM_CHAT_ID` / `DISCORD_*`). One bot,
  one layer; never share a token between layers.
- **OAuth**: Codex / Copilot / xAI-OAuth in default's `auth.json` (read-only
  fallback to every profile); **Anthropic** resolves separately via the Claude
  Code credential / token (machine-global, every profile).

**Multiplex changes where these layers land.** Scope-aware reads inside the
gateway (bot tokens, `OPENROUTER_API_KEY`, `EXA/PARALLEL/FIRECRAWL/XAI` keys,
`GITHUB_TOKEN`, TTS keys, …) resolve ONLY from each profile's secret scope and
never fall back to the process env. Every profile therefore carries
`secrets.command` → `scripts/profile-secrets.sh <profile>`, which emits
`global` + `hermes` (minus messaging keys) + `hermes-<profile>` as dotenv
lines at startup (and derives `TELEGRAM_CRON_THREAD_ID` from the persisted
Inbox topic for assistant). Raw-env readers (dashboard auth) still read the
process env the launcher injects — which is also why `BU_CDP_URL` must never
be in those layers: `browser_exec` copies it raw from the process env and it
would pre-empt real-profile browsing for every profile at once (see the
browser-stack rule in `AGENTS.md`).

Workers need no unique secret: the dispatcher execs `hermes -p <worker>`, which
hits the `bin/hermes` shim (`global` + `hermes`), and they also inherit the
gateway's env. A background **LaunchAgent** can start with a stripped `PATH`, so
the gateway launcher sets its own `PATH` and `eval`s the Keychain layers
directly (below).

## Gateway as a persistent service

The **default** profile hosts ONE multiplex gateway (and the embedded kanban
dispatcher) keychain-pure via a **LaunchAgent**: `gateway.multiplex_profiles:
true` + the allowlist (assistant, engineer, creator, marketer, writer,
researcher) in the root `config.yaml` make that single process connect every
served profile's enabled platforms — assistant Telegram (+ topics) and
Discord, the engineer / creator / marketer Telegram bots, and the A2A
endpoints on 127.0.0.1:9902-9906. Secondary profiles never run their own
gateway. Three tracked, machine-agnostic files in `hermes/launchd/`:

- **`hermes-gateway-multiplex`** — the launcher. Sets `PATH`, `cd`s to
  `~/Workspaces`, logs to `~/.hermes/logs/gateway-multiplex.log`, `eval`s the
  `global` + `hermes` Keychain layers into the process env (raw-env readers +
  subprocess inheritance; the scope-aware keys come per profile from
  `secrets.command`), then execs the real `hermes gateway run` (no `-p` —
  default is the multiplex host). Every path is
  `$HOME`-relative — no
  hardcoded home, no `.env`. (`secret env` has **no `-- <cmd>` form**, hence the
  `eval`.) It exports no `HERMES_PROFILE`: one process serves many profiles.
- **`local.hermes.gateway.multiplex.plist.tmpl`** — LaunchAgent template with a
  `__HOME__` placeholder (launchd can't expand `~`). Runs the launcher as
  `ProgramArguments[0]`, so the login item reads `hermes-gateway-multiplex`, not
  `sh`.
- **`gateway-launchctl.sh`** — renders the template (`__HOME__` → `$HOME`) into
  `~/Library/LaunchAgents/` (host-local, never committed) and loads it; on
  install it also unloads the legacy `local.hermes.gateway.assistant` agent so
  two pollers never race one bot token.

**Telegram + Discord.** Upstream #40695 previously let `_handoff_watcher` block
the asyncio loop on synchronous SQLite access, stalling Discord heartbeats and
the dispatcher. The installed fork now wraps gateway DB calls in
`AsyncSessionDB` / `asyncio.to_thread` and carries dedicated regression tests, so
the launcher exposes both platform credentials. Keep the Discord toolset
granular and equal to Telegram; never replace either list with a broad bundled
toolset.

Discord is limited to the private config's user and channel allowlists. A channel
mention creates a thread; the parent channel's `assistant-pipeline` binding and
prompt carry into that thread. Live voice uses `/voice join` and the existing
STT/TTS fallback chains. It leaves after five idle minutes by default, and a
gateway restart requires a manual rejoin. Cron/system Inbox delivery stays on
Telegram to avoid duplicate proactive notifications.

Activate on the **gateway host only** (one bot token = one live connection —
four bots means four tokens, all owned by this one process; stop
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
  / `.no-bundled-skills` per profile (`mcp.json` when present).
- `cron/` is never linked or tracked — Hermes owns it machine-local.
- Auto-untracked (outside the symlink set): `~/.hermes/kanban.db`, `kanban/`,
  `workspace/`, `auth.json`, `.env`, `memories/`, `sessions/`, `state.db*`.

Routing quality depends on `profile.yaml` descriptions — create workers with
`hermes profile create <name> --description "<role>"` (or
`hermes profile describe <name> --text "…"`).

## Status (as-built)

Built and verified through v4 (2026-07 → 2026-08-03): the six specialists,
the assistant gateway (keychain-pure LaunchAgent; Telegram + Discord after
upstream issue #40695's async-DB fix; `dispatch_interval_seconds: 15`), model
chains (doctor + live probes), and
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
(contracts under `assistant-pipeline/references/quality-assurance/`), and GitHub bookkeeping;
the board shrank to fire-and-forget / cron / mass-parallel / `scheduled`
with a lean card contract. The completion path-guard plugin, admission
probes, and the 5-minute orphan watchdog were removed (the sweeper and the
guarded block resolver remain); the validator now enforces the
assistant-pipeline topology, routing completeness, `card_units` schema and
required QA contracts. Remaining live verification: a real short-video production run
through the new flow.

**Multi-primary peer rebuild (2026-09-01)** — assistant, engineer, creator,
and marketer were promoted to primaries: each runs its own Telegram bot out
of ONE default-hosted multiplex gateway (`gateway.multiplex_profiles`), and
the peer graph rides the A2A platform (per-profile `a2a_agents`, localhost
ports 9902-9906, `timeout: 310` because the caller default of 120s undercuts
the server's 300s reply window). writer / researcher became receive-only A2A
endpoints; researcher's `claim-verification` card was retired (research is
card-free; the assistant reaches research only through engineer / creator /
marketer). Secrets moved to per-profile scopes via `secrets.command` →
`scripts/profile-secrets.sh` (multiplex scope-aware reads never fall back to
the process env). Peer-list enforcement is config + operating contract
(`a2a_agents` names the callable peers; contracts forbid direct URLs), not a
plugin hook. The old v5 supervision shape (assistant as front door / quality
gate / dispatcher host, heavy work in resident sessions) is retained for
now, with a stated intent to move stepwise toward a flatter, equal-primary
operation. Verified live 2026-09-01/02: 4 bots + Discord connected, A2A
round-trips (assistant→writer, engineer→researcher), dispatcher singleton,
cron ticking all 7 profiles. First regression found and fixed 2026-09-02:
upstream's completion-notification injector only knew `self.adapters`, so a
resident-session turn finishing in the assistant's (now secondary) chat
never woke it — carried fix `fix/watch-notification-multiplex-route` in the
hermes-agent checkout (see AGENTS.md).

**Creator hands v3 (2026-09-05, in progress)** — see "Creator hands (v3)".
Started after the `refactor/creator-profile` branch (director + three hands +
menu / preset / Style governance) was abandoned as over-abstracted. Progress
is tracked per family in that section's "Migration" list; the first family
is `icon` on `image-creator`, the second `emoji`.
