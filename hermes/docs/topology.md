# Topology and operating layers

Process topology, delegation layers, the profile roster and the per-profile operating layers. Part of the Hermes design docs — index: [`PROFILES.md`](../PROFILES.md).

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
        │ resident sessions         │       engineer  → marketer researcher writer (+ resident UI evaluators)
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
(localhost JSON-RPC, `specialist_call` for Assistant/Creator/Marketer and raw
`a2a_call` for Engineer against the per-profile `a2a_agents`
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
video-creator, audio-creator), marketer (engineer, creator, researcher, writer),
and engineer (marketer, researcher, writer, ui-review, ux-persona). This entry point does not grant assistant
direct researcher access or expose delegation tools to the hands profiles.
Live messaging receives a background completion; nested resident/CLI calls
wait synchronously. See [Specialist Calls](../README.md#specialist-calls) for
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
  `scripts/profile-secrets.sh` (see [`models-auth.md`](./models-auth.md) "Secrets layering").

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
| **engineer** | developer using OpenCode; human/Assistant Clients; technical planning, approved implementation through PR and independent UI/UX QA; Issue writes only on explicit request | Telegram (own bot) | explicit task worktree | `terminal,file,web,browser,vision,skills,todo,memory,clarify,delegation,specialist,opencode` | bot + inquiry-only a2a :9902 | yes |
| **ui-review / ux-persona** | independent visual review / isolated user simulation for Engineer; no code edits or self-acceptance | resident only | isolated test browser | `browser,vision,skills,ui-inspection` | no bot or A2A endpoint | inherited default OAuth |
| **researcher** | purpose-first depth Plan / Build / QA: evidence-pack / tradeoff-matrix / fact-check / guidance; proposes own-role scope, requests heavy breadth from caller; serves engineer/creator/marketer only (not Assistant directly), cards refused | — (A2A receive-only) | `.` (launch / task ws) | `file,web,vision,video,skills,memory,delegation` | served (a2a :9906) | yes |
| **searcher** | purpose-first retrieval Plan / Build / QA: lookup / sweep / hunt; valid settled catalog cards go directly Build / QA / terminal (multi-hop via `goal_mode`) | — (specialist) | `.` (launch / task ws) | `web,x_search,skills,memory` | — | yes |
| **creator** | primary: plans with human/assistant clients, delegates served image/clip/speech/sfx/music/mix forms, gates evidence and delivers; remaining technics cover images, authored video and assembly of supplied parts; vocal-song generation and standalone audio visualization remain withdrawn | Telegram (own bot) | `.` (launch / task ws) | `terminal,file,vision,image_gen,video_gen,video,tts,skills,memory,delegation,a2a` + gen plugins + `unreal-engine` MCP | served (bot + a2a :9903) | yes |
| **image-creator** | Creator's hands for still images: runs one `<verb>/<subject>` leaf from a filled form (icon family: source / create / generate / edit / analyze; emoji family: create / generate / edit / analyze), QA with evidence, report; answers only Creator | — (A2A receive-only) | `.` (launch / task ws) | `terminal,file,vision,image_gen,skills,memory` | served (a2a :9907) | yes |
| **audio-creator** | Creator's spoken-audio hands: generate/edit/analyze-speech, create/generate/edit/analyze-sfx, create/generate/edit/analyze-music (instrumental BGM/melodic pieces only) and create/edit/analyze-mix (placing already-finished sources on a timeline, never synthesis) from approved forms; measured/readback QA, no claims of listening; no full songs or voice registration | — (A2A receive-only) | `.` (launch / task ws) | `terminal,file,tts,sfx_gen,music_gen,skills,memory` | served (a2a :9909) | yes |
| **writer** | reader-facing prose and producer-facing scripts from released units (outline / piece / whole job); draft-only, never publishes; serves all four primaries | — (A2A receive-only) | `.` (launch / task ws) | `file,web,skills,memory,delegation` | served (a2a :9905) | yes |
| **marketer** | primary: strategy, offer discovery, producer coordination, existing-browser service drafts and outcome analysis; specialist peers engineer/creator/researcher/writer; no publishing | Telegram (own bot) | `.` (launch / task ws) | `terminal,file,web,browser,x_search,vision,skills,memory,delegation,specialist,clarify` | served (bot + a2a :9904) | yes |

The table lists each role's native capability allowlist. `platform_toolsets` is
the runtime authority; top-level `toolsets` mirrors it and retains `kanban` on
the two front doors for the runtime gate. Dispatcher-spawned workers receive
task-scoped Kanban lifecycle tools automatically. Platforms without MCP access
carry the `no_mcp` denial sentinel; assistant CLI/Telegram/Discord and creator
CLI instead name only `unreal-engine`, which prevents inheritance of future MCP
servers. Worker Telegram / Discord lists and default's messaging lists are empty
by design.

Role split: **the assistant** plans with the user, supervises specialists,
performs the non-creative quality gate itself (the QA contracts under
`profiles/assistant/skills/assistant-pipeline/qa-assistant-*/` plus shared QA), owns GitHub bookkeeping, and
delivers; the **producer** self-verifies before reporting. The normal flow
stays **searcher (retrieve) → researcher (synthesize) → engineer
(implement)**, with **creator** (media) and **writer** (prose/scripts) as
production stages and **marketer** as the outbound end stage — the only
profile that publishes to public channels. User approval follows the
domain's checks. Creative production uses direct early delivery below rather
than another broker inspection.

### Planning ownership

Assistant coordinates cross-specialist outcomes as a Client. Engineer owns
code-grounded technical proposals and sequencing with OpenCode; Client approval
chooses scope and important tradeoffs. The technical plan lives in the agreed
private job record unless the Client explicitly requests Issue registration.
Do not infer tracking permission from complexity, project type or duration.
OpenCode session IDs are resume handles, not the only durable copy of decisions.
Researcher and Searcher likewise own their role-specific proposals and unit
sequencing from Client purpose; they do not inherit cross-role orchestration.
Agreement, specialist self-check and caller acceptance remain distinct gates.

### Default is the assistant's CLI counterpart (and stays a clean baseline)

default and assistant are the two faces of the same front door: identical
workflow behavior (assistant runs its own `assistant-pipeline`; default runs
the thin `default-pipeline` adapter over the assistant tree at
`~/.hermes/profiles/assistant/skills/assistant-pipeline/` kernel and child entries), with the
Telegram chat-wide auto-load bound to `assistant-pipeline`,
the same worker roster, the same media-full-delegation rule. The differences: platform
(CLI vs Telegram gateway), persona (default stays **neutral** — every
`--clone` inherits its `config.yaml`, so voice/character stays out), and
assistant-only surface skills (ccc-course-production,
codebase-fact-finding) stay in the assistant profile. Keep default's `cron/` empty and run no gateway on it; bots and
scheduled automation belong in named profiles.

For Assistant entry routing, default discovers the same child names via
a bounded filesystem listing under that known root, reads the root common
contract and selected child `SKILL.md` with `read_file`, then mode-common and
relevant details. It translates dependency names/file paths to canonical files
even when Assistant names are hidden from CLI `skill_view`; no generated index
or extra `skills.external_dirs` entry is needed. The 19 entries are not imposed
on default or its clones. In raw content, `${HERMES_SKILL_DIR}` is the owning
child's directory, never the adapter's or whichever skill was last loaded.
When `writer-pipeline` is unavailable by name, requester QA reads the documented
`~/.hermes/profiles/writer/skills/writer-pipeline/references/acceptance/index.md`
and selected `prose.md`/`script.md` with `read_file`, for inspection only.
Do not expose Writer's production leaves to solve a reference lookup.

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
  hold even when the profile's skill never loads: engineer = explicit implementation
  approval through PR, separate explicit-only Issue management, no merge/deploy/
  default-branch push, preserve changes and uncertain effects; creator = the Budget/spend floor (default caps, inventory
  surviving work before regenerating); researcher = evidence integrity (no
  fabricated citations); searcher = link integrity (only URLs actually
  retrieved); writer = deliverable integrity (no fabricated
  facts/quotes/URLs; assumptions labeled; the selected leaf's applicable
  checks with explicit evidence gaps) + never publishes; marketer = the
  draft + evidence floor (exact remote-save consent before input; no publishing,
  scheduling or sending; traceable claims and no fabricated demand/metrics;
  user-owned commitments; independent content acceptance and reopened unpublished
  draft verification; uncertain effects never blindly retried); front doors = heavy work never runs in their
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
  The assistant owns `assistant-pipeline/`, its invariant kernel and 19 child
  entries with local details; default owns the shared tracked `default-pipeline/` adapter. The
  assistant-pipeline dir is a private-overlay symlink — maintainer-owned, but
  tracked by the private-dotconfig repo. (The topic-bound `desks/` overlay was
  retired on 2026-09-14; pinned Telegram topics are skill-less, see "Routing".)
  Runtime-authored skills from background review, curator, `/learn`, or normal
  `skill_manage(create)` calls go to the untracked `learned/` category through
  `skills.create_dir: skills/learned` in every `config.yaml` (an optional
  `category` nests as `learned/<category>/<name>`). Moving a complete package from `learned/` to
  `technic/` is the explicit maintainer-review boundary. External directories
  remain provider-owned and never become local technics implicitly.
  - assistant → `assistant-pipeline` (front-door playbook: modes Chat / Plan /
    Execute / Quality Assurance over tiers inline / resident / kanban; the
    `chat-assistant` and `{plan,execute,qa}-assistant-<domain>` children;
    resident sessions via `resident-session.sh`; assistant-run QA contracts;
    and the closed `card_units` catalog only in authorized Execute SKILL frontmatter). Default
    runs the thin `default-pipeline` CLI adapter over this tree; it records only
    terminal-specific deltas. The assistant also reads the upstream official
    libraries (apple / creative / email / github / media / note-taking /
    productivity / research / smart-home / social-media) plus optional
    `one-three-one-rule` (decision framing) and `watchers` (RSS/API polling
    for cron sweeps) via `skills.external_dirs`; heavy tool-bound creative
    entries (`comfyui`, `touchdesigner-mcp`, `manim-video`, `ascii-video`)
    sit in `skills.disabled` — media production is creator's.
  - engineer → `engineer-pipeline` (cards refused; Plan/Build/Quality assurance/
    Assess modes; technical planning with OpenCode, explicit implementation
    approval through PR, scoped CLI conversations and independent UI evaluation;
    Issue management only on explicit request) + upstream libraries via
    `skills.external_dirs`: official
    `autonomous-ai-agents` / `software-development` / `github` plus optional
    per-skill dirs `code-wiki`, `rest-graphql-debug`,
    `subagent-driven-development`, `docker-management`, `pinggy-tunnel`,
    `fastmcp`, `mcporter`, and `cloudflare-temporary-deploy` (all key-free,
    script/CLI-based via uv / npx / docker)
  - researcher → `researcher-pipeline` (resident sessions + inbound A2A
    peer requests from engineer/creator/marketer; every card refused —
    the `claim-verification` unit is retired; purpose-first v9 kernel with
    independent `plan-researcher` / `build-researcher` / `qa-researcher` entries,
    each owning plain evidence-pack / tradeoff-matrix / fact-check / guidance
    references; proposes own-role scope for Client agreement, then executes and
    self-checks, returning spec-gap and granularity findings, plus
    Admiralty/SIFT source evaluation, citation rules, and the Review gate
    in the kernel; researcher supplies evidence and does not own
    artifact-vs-brief QA; retrieval strategy in references/gather.md) +
    optional research skills via `skills.external_dirs`: `domain-intel` and
    `osint-investigation` (stdlib-only recon / public-records) plus keyless
    `duckduckgo-search` (run through `uvx ddgs`)
  - searcher → `searcher-pipeline` (dual runtime — cards only for the
    `survey-enumeration` / `exhaustive-hunt` catalog units; purpose-first v7
    Plan / Build / QA with Client agreement and own-role sequencing; lookup (targeted facts) /
    sweep (enumeration with a coverage claim) / hunt (multi-hop to
    saturation, signalled by `goal_mode` on cards) — returning spec-gap
    and granularity findings, plus the link-integrity floor; per-unit
    references in each independent plan-searcher / build-searcher / qa-searcher
    child; valid settled cards bypass Plan for Build / QA / terminal;
    caller acceptance is separate; no technics — the deprecated
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
    clay), `edit/emoji`, `analyze/emoji` — see [`hands/overview.md`](./hands/overview.md)
  - creator → `creator-pipeline` v9 — clients and hands: Plan
    (`plan-creator`: use runtime caller context before message shape;
    agent follow-ups are not direct human approval; fill the leaf's
    form with `clarify` or by parsing the brief; composites = a sequence of
    forms), Build (`build-creator`: the handoff text, specialist inquiry / work
    session, supervision, relaying `Q<n>` and direct delivery), optional inspection
    (`qa-creator`: only on explicit user request, bounded findings without
    automatic revision). Each entry leads to only the selected
    `references/<hands>/<subject>.md`; verbs stay inside that subject reference and the
    hands leaf remains the only form. `capabilities.md` is the capability router
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
    granularity findings). Its v8 candidate kernel selects the unchanged 18
    `<write|edit|analyze>/<subject>/SKILL.md` leaves in category `writing`.
    Each leaf owns its form, Procedure, QA and Report. Pre-draft advice uses
    `consult-writer`, an independent non-production direct child, not a fourth
    production verb/form or another writing/review pipeline;
    unsupported requests return for clarification. The post family serves
    `write-post`, `edit-post` and
    `analyze-post` for X/Instagram, with per-leaf forms, platform references
    and QA. The article family now serves `write-article`, `edit-article`
    and `analyze-article`, with destination-format references and separate
    asset/editor notes. The document family serves `write-document`,
    `edit-document` and `analyze-document`, with local format references and
    separate source/runtime boundaries. The message family serves
    `write-message`, `edit-message` and `analyze-message` for email, chat,
    notification, UI and error wording, never delivery or system diagnosis.
    Copy and production scripts also use their three operation-specific leaves.
    External skills remain via
    `skills.external_dirs`: the Japanese stack via the curated
    `profiles/writer/external-skills/` symlink dir (the single
    `japanese-writing` language core with five notation defaults and a bounded
    read-only inspector, single-sourced with the shared `agents/curated/`
    store) and upstream `creative/humanizer`
    (explicit-request only)
  - marketer → `marketer-pipeline` (resident-only, cards refused; Plan / Build /
    Quality assurance / Analyze, one shared file per platform and a private-state
    schema; strategy and browser work stay here, no SNS hand/login profile).
    Writer's pipeline is readable through `skills.external_dirs` for shared
    requester acceptance, not local manuscript production. The old xurl/humanizer
    imports and publish engine are absent from the active marketer path.

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
