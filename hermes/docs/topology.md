# Topology and operating layers

Process topology, the multiplex gateway and A2A peer graph, delegation layers, the profile roster, the per-profile operating layers and the shared entry/rollout contracts. Part of the Hermes design docs — index: [`PROFILES.md`](../PROFILES.md).

## Topology

```
   human (terminal)     human (Telegram × 4 bots + Discord)
          │                │        │        │        │
        default        assistant engineer creator marketer   ← four PRIMARY bots
        (CLI)              │      (all adapters live in ONE multiplex gateway
          │                │       process, hosted by default; + dispatcher)
          └──────┬─────────┘
                 │                        peer graph (specialist_call; A2A = localhost HTTP):
        ┌────────┼──────────────────┐       assistant → engineer creator marketer writer (+ resident searcher)
        │ resident sessions         │       engineer  → marketer researcher writer (+ resident UI evaluators)
        │ lean kanban cards         │       creator   → engineer marketer researcher writer
        │ delegate_task             │                   + image-creator video-creator audio-creator
        ▼                           ▼       marketer  → engineer creator researcher writer
  hermes -p <specialist>   anonymous subagents      (writer / researcher / hands: receive-only;
  chat --resume <id> / ~/.hermes/kanban.db           searcher: no endpoint — resident/kanban only)
```

Four profiles are **primaries** — assistant (the original front door),
engineer, creator and marketer — each with its own Telegram bot. Primaries reach
each other and the specialists only through `specialist_call` against configured
targets, never a direct URL; Telegram cannot carry bot-to-bot traffic. writer,
researcher and the three hands serve inbound A2A but initiate nothing; searcher
has no A2A endpoint. Heavy interactive work runs in **resident sessions** (a
persistent `hermes -p <specialist> chat` started by `specialist_call(kind="work")`
and supervised turn by turn); short `kind="inquiry"` requests use configured A2A
peers. This grants assistant no direct researcher access and gives the hands no
delegation tools. Allowlists, completion, ownership and failure handling:
[specialist-calls](./profiles/specialist-calls.md). The board remains for work
where conversation adds nothing.

### Multiplex gateway and A2A peer graph

- **One gateway** — default, with `gateway.multiplex_profiles: true` — hosts
  every served profile's adapters, the A2A endpoints and the embedded dispatcher,
  which sweeps **all** boards each tick (`gateway/kanban_watchers.py`) and ticks
  each profile's cron store; secondary profiles never start their own (see
  [operations](./operations.md) "Gateway as a persistent service").
- **A2A ports** are per-profile config in `platforms.a2a.extra.port`, not an env
  var (the process env is shared by every multiplexed profile): engineer `:9902`
  (inquiry-only), creator `:9903`, marketer `:9904`, writer `:9905`, researcher
  `:9906`, image-creator `:9907`, video-creator `:9908`, audio-creator `:9909`.
- **Peer lists** live per profile in `a2a_agents` (the graph above) with
  `timeout: 310` — the 120 s caller default undercuts the 300 s server reply
  window. Enforcement is config plus operating contract, not a plugin hook.
- **Secrets.** Under multiplex, scope-aware reads (bot tokens, provider and
  web-search keys) NEVER fall back to the process env; each profile's keys come
  from `secrets.command` → `scripts/profile-secrets.sh <profile>`, and only
  raw-env readers (`BU_CDP_URL`, dashboard auth) see the launcher env. See
  [`models-auth.md`](./models-auth.md) "Secrets layering".
- **One shared board** at the base `~/.hermes/kanban.db`
  (`get_default_hermes_root()`, not profile-scoped).
- **Workers spawn through the PATH `hermes`**: the dispatcher runs `hermes -p
  <worker> … chat -q "work kanban task <id>"` via `shutil.which` (so the
  `bin/hermes` shim is used) with a copy of the gateway env and `HERMES_HOME`
  overridden, so workers get the `global` + `hermes` Keychain layers — no
  per-worker secret is needed.

## Three delegation layers

| | Resident session | Kanban | `delegate_task` |
| --- | --- | --- | --- |
| Worker | **named profile** session with living context | **named profile**, fresh process per run | anonymous subagent |
| Dialogue | conversational turns (feedback in minutes) | STATE/Q<n>/DECISION comments + block round-trips | none — one shot |
| Durability | session registry + durable-path files | persistent queue, resumable | dies with the turn |
| Requires | terminal + the wrapper script | a running gateway (the dispatcher) | nothing |
| Use for | **default for heavy work**: anything you expect to give feedback on | fire-and-forget, cron-originated, mass-parallel, `scheduled` parking | in-turn parallel lookups |

**Fallback story:** resident sessions work whenever `hermes` runs — no gateway
needed. Gateway up adds the board for fire-and-forget work; gateway down,
`default` still parallelizes via `delegate_task`. A specialist may itself call
`delegate_task` during its run.

## Profile roster

| Profile | Role | Front door | `terminal.cwd` | Toolsets | Gateway | Tracked |
| --- | --- | --- | --- | --- | --- | --- |
| **default** | CLI front door — assistant's CLI counterpart (neutral persona); hosts the multiplex gateway | CLI | `.` (launch dir) | `web,browser,terminal,file,code_execution,vision,x_search,skills,todo,memory,clarify,delegation,cronjob,kanban` | host | yes |
| **assistant** | primary: messaging front door, dispatcher home board, non-creative quality gate, GitHub bookkeeping | Telegram + Discord | `~/Workspaces` | `web,browser,terminal,file,vision,x_search,skills,todo,memory,clarify,delegation,cronjob,computer_use,kanban,specialist,opencode` + `unreal-engine` MCP | served | yes (private overlay) |
| **engineer** | developer using OpenCode; human/Assistant Clients; technical planning, approved implementation through PR and independent UI/UX QA; Issue writes only on explicit request | Telegram (own bot) | explicit task worktree | `terminal,file,web,browser,vision,skills,todo,memory,clarify,delegation,specialist,opencode` | bot + inquiry-only a2a :9902 | yes |
| **ui-review / ux-persona** | independent visual review / isolated user simulation for Engineer; no code edits or self-acceptance | resident only | owned non-Git job dir | `browser,vision,skills,ui-inspection` | no bot or A2A endpoint | yes (inherited default OAuth) |
| **researcher** | purpose-first depth Plan / Build / QA: evidence-pack / tradeoff-matrix / fact-check / guidance; proposes own-role scope, requests heavy breadth from the caller; serves engineer/creator/marketer only (not Assistant directly), cards refused | — (A2A receive-only) | `.` (launch / task ws) | `file,web,vision,video,skills,memory,delegation` | served (a2a :9906) | yes |
| **searcher** | purpose-first retrieval Plan / Build / QA: lookup / sweep / hunt; valid settled catalog cards go directly Build / QA / terminal (multi-hop via `goal_mode`) | — (specialist) | `.` (launch / task ws) | `web,x_search,skills,memory` | — | yes |
| **creator** | primary: plans with human/assistant clients, delegates served image/video/speech/sfx/music/mix forms, gates evidence and delivers; remaining technics cover images, authored video and assembly of supplied parts; vocal-song generation and standalone audio visualization remain withdrawn | Telegram (own bot) | `.` (launch / task ws) | `terminal,file,vision,image_gen,video_gen,video,tts,skills,memory,delegation,specialist,clarify` + gen plugins + `unreal-engine` MCP | served (bot + a2a :9903) | yes |
| **image-creator** | Creator's still-image hands: runs one `<verb>/<subject>` leaf from a filled form, QA with evidence, report; answers only Creator | — (A2A receive-only) | `.` (launch / task ws) | `terminal,file,vision,image_gen,skills,memory` | served (a2a :9907) | yes |
| **video-creator** | Creator's video hands: clip, tour, ad, explainer-video and music-video leaves from approved forms; answers only Creator | — (A2A receive-only) | `.` (launch / task ws) | `terminal,file,vision,video_gen,video,skills,memory` | served (a2a :9908) | yes |
| **audio-creator** | Creator's audio hands: speech, sfx, music (instrumental BGM/melodic pieces only) and mix (placing already-finished sources, never synthesis) from approved forms; measured/readback QA, no claims of listening; no full songs or voice registration | — (A2A receive-only) | `.` (launch / task ws) | `terminal,file,tts,sfx_gen,music_gen,skills,memory` | served (a2a :9909) | yes |
| **writer** | reader-facing prose and producer-facing scripts from released units (outline / piece / whole job); draft-only, never publishes; serves all four primaries | — (A2A receive-only) | `.` (launch / task ws) | `writing-inspection,file,web,skills,memory,delegation` | served (a2a :9905) | yes |
| **marketer** | primary: strategy, offer discovery, producer coordination, existing-browser service drafts and outcome analysis; no publishing | Telegram (own bot) | `.` (launch / task ws) | `terminal,file,web,browser,x_search,vision,skills,memory,delegation,specialist,clarify` | served (bot + a2a :9904) | yes |

### Toolsets

The table lists each role's native capability allowlist.
`platform_toolsets.<platform>` is the effective runtime allowlist and stays
granular: the composite `hermes-cli` / `hermes-telegram` toolsets expand to a
broad surface and strip default-off tools such as `video` / `video_gen`.
Top-level `toolsets` mirrors the role; top-level `kanban` is also the front-door
runtime gate, and dispatcher-spawned workers receive task-scoped Kanban lifecycle
tools automatically.

- **Messaging lists.** The four bots (assistant, engineer, creator, marketer)
  carry real `telegram` lists; assistant alone adds `discord`. writer,
  researcher, searcher, the hands and default keep their Telegram / Discord lists
  empty.
- **A2A lists.** Every A2A-serving profile has an `a2a` list for its inbound peer
  sessions, usually narrower than CLI (Marketer's inbound A2A has no browser,
  terminal or delegation, so authenticated work needs a resident session).
  `a2a` is also the name of the OUTBOUND toolset (the five default-off `a2a_*`
  tools); assistant, creator, marketer and engineer expose only `specialist` for
  outbound requests.
- **MCP.** Platforms without MCP access carry the `no_mcp` denial sentinel;
  otherwise each allowed server is listed explicitly (assistant and creator name
  only `unreal-engine`) so future servers are never inherited.

Role split: **the assistant** plans with the user, supervises specialists,
performs the non-creative quality gate itself (see
[assistant.md](./profiles/assistant.md) "Assistant quality gate"), owns GitHub
bookkeeping and delivers; the **producer** self-verifies before reporting. The
normal flow stays **searcher (retrieve) → researcher (synthesize) → engineer
(implement)**, with **creator** (media) and **writer** (prose/scripts) as
production stages and **marketer** as the outbound end stage — it saves service
drafts only; the user publishes. User approval follows the domain's checks.
Creative production uses direct early delivery rather than another broker
inspection.

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
workflow behavior (assistant runs its own `assistant-pipeline`; default runs the
thin `default-pipeline` adapter over the assistant tree at
`~/.hermes/profiles/assistant/skills/assistant-pipeline/`), the same worker
roster, the same media-full-delegation rule. The differences: platform (CLI vs
Telegram gateway), persona (default stays **neutral** — every `--clone` inherits
its `config.yaml`, so voice/character stays out), and assistant-only surface
skills (ccc-course-production, codebase-fact-finding). Keep default's `cron/`
empty and run no bots on it; bots and scheduled automation belong in named
profiles.

For Assistant entry routing, default discovers the same child names via a
bounded filesystem listing under that known root, reads the root common contract
and selected child `SKILL.md` with `read_file`, then mode-common and relevant
details. It translates dependency names/file paths to canonical files even when
Assistant names are hidden from CLI `skill_view`; no generated index or extra
`skills.external_dirs` entry is needed. The 19 entries and Writer's production
leaves are not imposed on default's menu or its clones. In raw content,
`${HERMES_SKILL_DIR}` is the owning child's directory, never the adapter's or
whichever skill was last loaded. When `writer-pipeline` is unavailable by name,
requester QA reads the documented
`~/.hermes/profiles/writer/skills/writer-pipeline/references/acceptance/index.md`
and selected `prose.md`/`script.md` with `read_file`, for inspection only. Do not
expose Writer's production leaves to solve a reference lookup.

### Two working directories per worker

- **Kanban-dispatched work** runs in the task workspace
  (`$HERMES_KANBAN_WORKSPACE`): `worktree:` for engineer (isolated + preserved),
  `scratch` for the rest (ephemeral, deleted on completion).
- **Direct / `delegate_task` work** starts in `terminal.cwd` — currently `.`
  (the launch dir) for most workers; pin an absolute path per worker for a fixed
  directory. `workspace/` is per-machine and never tracked.

## Operating layers (per profile)

Three per-profile layers, kept separate:

- **SOUL.md** — persona/voice (BASE: Identity/Style/Avoid/Defaults + a one-line Role posture).
- **`agent.system_prompt`** (config.yaml) — the always-on *operating contract*: how the
  profile works each task. Workers open with "first action: load `<skill>`"; the assistant
  carries its chat-output contract + a compact work-routing tripwire here, kept out of
  SOUL so it survives. `/personality` shares this slot and would clobber it — don't
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
- **skills/** — detailed, on-demand playbooks. Every local library uses the same
  ownership types. A worker has one tracked `<profile>-pipeline/` plus tracked,
  directly selectable `technic/` leaves. The assistant owns `assistant-pipeline/`
  (kernel + 19 child entries), a private-overlay symlink — maintainer-owned but
  tracked by the private-dotconfig repo; default owns the shared tracked
  `default-pipeline/` adapter. Pinned Telegram topics bind no skill (see
  [assistant.md](./profiles/assistant.md) "Pinned Telegram topics").
  Runtime-authored skills (background review, curator, `/learn`, ordinary
  `skill_manage(create)`) go to the untracked `learned/` category through
  `skills.create_dir: skills/learned` in every `config.yaml` (an optional
  `category` nests as `learned/<category>/<name>`). Moving a complete package
  from `learned/` to `technic/` is the explicit maintainer-review boundary.
  External directories remain provider-owned and never become local technics
  implicitly.
  - assistant → `assistant-pipeline` (Chat / Plan / Execute / Quality Assurance
    over tiers inline / resident / kanban; `chat-assistant` and
    `{plan,execute,qa}-assistant-<domain>` children; resident sessions via
    `resident-session.sh`; assistant-run QA contracts; the closed `card_units`
    catalog only in authorized Execute SKILL frontmatter). Default's
    `default-pipeline` records only terminal-specific deltas. External libraries
    via `skills.external_dirs`: official apple / creative / email / github / media
    / note-taking / productivity / research / smart-home / social-media plus
    optional `one-three-one-rule` (decision framing) and `watchers` (RSS/API
    polling for cron sweeps); heavy tool-bound creative entries (`comfyui`,
    `touchdesigner-mcp`, `manim-video`, `ascii-video`) sit in `skills.disabled` —
    media production is creator's.
  - engineer → `engineer-pipeline` (cards refused; see
    [engineer.md](./profiles/engineer.md)) + official `autonomous-ai-agents` /
    `software-development` / `github` plus optional `code-wiki`,
    `rest-graphql-debug`, `subagent-driven-development`, `docker-management`,
    `pinggy-tunnel`, `fastmcp`, `mcporter` and `cloudflare-temporary-deploy`
    (all key-free, script/CLI-based via uv / npx / docker).
  - researcher → `researcher-pipeline` (resident sessions + inbound A2A from
    engineer/creator/marketer; every card refused; returns spec-gap and
    granularity findings; see [research.md](./profiles/research.md)) + optional
    `domain-intel` and `osint-investigation` (stdlib-only recon /
    public-records) plus keyless `duckduckgo-search` (run through `uvx ddgs`).
  - searcher → `searcher-pipeline` (dual runtime — cards only for the
    `survey-enumeration` / `exhaustive-hunt` catalog units; lookup / sweep / hunt
    with spec-gap and granularity findings and the link-integrity floor; no
    technics; see [research.md](./profiles/research.md)) + keyless optional
    `duckduckgo-search` and `domain-intel`.
  - image-creator → `image-creator-pipeline` (the hands root: validate the filled
    form → load the leaf → run → QA → report; shared `img-postprocess.sh` /
    `icon-finish.sh` / `emoji-fit.sh`) + icon leaves `source`, `create`,
    `generate` (styles flat-minimal / glass / pixel / line / clay), `edit`,
    `analyze`; emoji leaves `create` (text emoji), `generate` (two rounds — anchor
    then pack; packs expressions / gaming / love-hype / meme-classics / custom;
    styles chibi-cartoon / kawaii-pastel / pixel / flat-sticker / clay), `edit`,
    `analyze`; plus the card and kit families — see
    [`hands/overview.md`](./hands/overview.md).
    video-creator and audio-creator follow the same shape
    ([`hands/video.md`](./hands/video.md), [`hands/audio.md`](./hands/audio.md)).
  - creator → `creator-pipeline` v9: `plan-creator` (runtime caller context
    before message shape; agent follow-ups are not direct human approval; fill the
    leaf's form via `clarify` or the brief; composites = a sequence of forms),
    `build-creator` (handoff text, specialist inquiry / work session, supervision,
    relaying `Q<n>`, direct delivery), `qa-creator` (explicit user request only;
    bounded findings, no automatic revision). Each entry reads only the selected
    `references/<hands>/<subject>.md`; the hands leaf remains the only form (see
    [`broker.md`](./broker.md) "Broker shape"). `capabilities.md` routes served
    families first, then the technic table. Families with no hands yet keep the
    technic-era contract under `references/legacy/`: produce / direction /
    advisory + iterate / verify / delivery / resume, the MediaBrief `brief.md` and
    its validation, intent triage, the unit discipline (released-spec consumption,
    spec-gap findings, verbatim part inputs), Budget grant parsing,
    workspace-reuse resume, visual verification, durable-path delivery, and
    `card.md` (cards are legacy-only, for `anchored-image-batch` /
    `deterministic-render`, until they move to the hands with their family).
    `skills/technic/` leaves: `creator-generated-image`,
    `creator-article-illustration`, `creator-infographic`, `creator-svg-diagram`,
    `creator-excalidraw-diagram`, `creator-text-card`, `creator-meme`,
    `creator-ascii-art`, `creator-gif-sourcing`, `creator-generated-video`,
    `creator-html-motion`, `creator-p5js-experience`, `creator-ascii-video`,
    `creator-manim-explainer`, `creator-pixel-art`, `creator-pixel-video`,
    `creator-knowledge-comic`, `creator-brand-asset-sourcing`,
    `creator-media-assembly`. Each owns one production grammar and its medium QA;
    styles/presets and same-tool modes stay in references. Official creative
    skills may be engines behind these canonical names, never alternate dispatch
    identities. `creator-html-motion` uses the CLI-owned HyperFrames store
    (`~/.agents/skills` via `skills.external_dirs`: `hyperframes` routes the
    domain/workflow skills, `media-use` resolves assets / captions; new narration
    is a separate audio-creator input, never an external TTS bypass). Bundled
    `creative/` + `media/` stay available; optional skills are a curated set of
    individual directories (article illustration, pixel art, comics, memes,
    concept diagrams, creative ideation) so the official optional `hyperframes`
    and `tldraw-offline` cannot collide with the store's names. `unreal-mcp` is
    wired for assistant and creator, backed by their `unreal-engine` MCP
    allowlist; `blender-mcp`, `touchdesigner-mcp` and the ambiguous external
    `pixel-art` stay in `skills.disabled` (the canonical Pixel leaves may use its
    scripts as opt-in backends but are the only stable dispatch identities).
  - writer → `writer-pipeline` (resident + inbound A2A, cards refused; released
    units — outline / piece / whole job — with spec-gap and granularity findings;
    18 `<write|edit|analyze>/<subject>/SKILL.md` leaves across post, article,
    document, message, copy and script plus `consult-writer`; see
    [writer.md](./profiles/writer.md)). External skills: the curated
    `profiles/writer/external-skills/` symlink dir (the single `japanese-writing`
    language core with five notation defaults and a bounded read-only inspector,
    single-sourced with the shared `agents/curated/` store) and upstream
    `creative/humanizer` (explicit-request only).
  - marketer → `marketer-pipeline` (resident-only for authenticated work, cards
    refused; see [marketer.md](./profiles/marketer.md)). Writer's pipeline is
    readable through `skills.external_dirs` for shared requester acceptance, not
    local manuscript production. No xurl/humanizer imports or publish engine.

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

## Entry loading contract

Assistant, Engineer, Creator, Researcher, Searcher, Writer and Marketer expose
their modes/phases as independent child skills below an invariant root kernel.
Profile docs list only their deltas to this shared contract:

- **Selection.** Re-select the applicable entry on each user/caller, judge/resume
  and completion turn, and BEFORE a midturn action changing mode, phase, domain,
  unit, subject or scope.
- **Dependencies and reuse.** Direct entry still requires the full kernel (and a
  shared mode-common body where one exists), the selected entry and its required
  detail references in current context. Only full bodies present in current
  context are reusable — never a past load, loaded-record, summary or root preload.
- **Recovery.** If `skill_view` dedup returns unchanged with the body missing,
  recover via canonical `read_file`, following genuine `next_offset` truncation
  offsets; if a required body is still unavailable, stop the affected action —
  never an invented pass. Never evade dedup through aliases, alternate paths or
  artificial ranges. Read dedup (`tools/skills_tool_dedup.py`,
  `tools/file_tools.py`) and compression-aware resets do not guarantee that
  instructions remain visible.
- **No authority from loading.** Selection, reading or resume never grants scope,
  widens or resets approvals/grants/budget/coverage, restarts planning or replays
  completed work; a short approval advances the retained plan.
- **Shape.** No aliases for retired mode/unit skill names, no second common-mode
  index, no generated menu; detail references are reached through their entry,
  not discovered as independent skills. Nested entries, parent/sibling references
  and `metadata.hermes` are intentional exceptions to the generic
  skill-authoring validator (which also treats named cross-checkout OpenCode
  resources as local files); the repository validator and isolated runtime tests
  check the real owner. Never duplicate a kernel or shared reference to silence
  that portability check; the exception never authorizes a broken dependency.
- **Cached index.** The gateway caches its skill index in-process; manual file
  edits do not invalidate it, and a fresh session alone is not invalidation.

## Candidate rollout and cutover

- Validate paired public/private candidates offline in worktrees with an
  isolated HOME and their own overlay links. Never install or link candidates
  into live paths, run candidate install scripts against live homes, repoint live
  links, or weaken live Git/symlink ownership checks for a test.
- `scripts/verify-work-continuity.py` runs the strict Git/topology validator,
  paired tests and runtime regressions before cutover and after an upstream
  update; it never installs, restarts or migrates jobs. Offline suites prove
  discovery/read/dedup/recovery mechanics, not model selection, approval
  compliance or live service effects.
- Cutover needs explicit approval, a controlled gateway restart (refreshing the
  applicable gateway/resident/worker process index) AND fresh sessions; candidate
  validation authorizes none. Existing messaging histories are not presumed
  refreshed.
- Preserve the previous paired revisions and active-job decisions first. Cutover
  never replays active resident work or migrates/rewrites task artifacts, frozen
  outputs, grants or approvals; old sessions/grants are reconciled into a new
  release, not silently adopted. Rollback restores the paired prior configuration
  and matched caller/producer contracts — not frozen job state, saved drafts,
  user data or completed Git/remote effects.
