# Topology and operating layers

Process topology, the multiplex gateway and A2A peer graph, delegation layers, the profile roster, the per-profile operating layers and the shared entry/rollout contracts. Read it before changing profiles, peers, toolsets or a rollout. Part of the Hermes design docs — index: [`PROFILES.md`](../PROFILES.md).

## Topology

```
   human (terminal)     human (Telegram × 2 bots + Discord)
          │                │        │
        default        assistant  marketer   ← two PRIMARY bots
         (CLI)              │      (all adapters live in ONE multiplex gateway
          │                │       process, hosted by default)
          └──────┬─────────┘
                 │                        peer graph (specialist_call; A2A = localhost HTTP):
        ┌────────┼──────────────────┐       assistant → creator marketer writer (+ resident searcher)
        │ resident sessions         │                   + image-creator video-creator audio-creator
        │ delegate_task             │       creator   → researcher
        │                           │       marketer  → researcher
        ▼                           ▼
  hermes -p <specialist>   anonymous subagents      (writer / researcher / hands: receive-only;
  chat --resume <id>                       searcher: no endpoint — resident only)
```

Two profiles are **primaries** — assistant (the original front door) and
marketer — each with its own Telegram bot. Primaries and Creator
reach the specialists only through `specialist_call` against configured
targets, never a direct URL; Telegram cannot carry bot-to-bot traffic. Creator
is the Assistant's creative advisor with no bot; it calls only Researcher.
writer, researcher and the three hands serve inbound A2A but initiate nothing;
searcher has no A2A endpoint. Heavy interactive work runs in **resident sessions** (a
persistent `hermes -p <specialist> chat` started by `specialist_call(kind="work")`
and supervised turn by turn); short `kind="inquiry"` requests use configured A2A
peers. This grants assistant no direct researcher access and gives the hands no
delegation tools. Allowlists, completion, ownership and failure handling:
[specialist-calls](./profiles/specialist-calls.md). Work where conversation adds
nothing runs as a cron job.

### Multiplex gateway and A2A peer graph

- **One gateway** — default, with `gateway.multiplex_profiles: true` — serves
  every profile directory under `profiles/` (there is no allowlist; a profile
  leaves only when parked by `hermes -p <name> gateway stop`, so never run that
  on a role that must stay reachable). It hosts their adapters, the A2A
  endpoints and ticks each profile's cron store; secondary
  profiles never start their own (see [operations](./operations.md) "Gateway as
  a persistent service"). Profiles without platforms (searcher) are served
  too, so each carries `secrets.command` like the rest.
- **A2A ports** are per-profile config in `platforms.a2a.extra.port`, not an env
  var (the process env is shared by every multiplexed profile): creator `:9903`,
  marketer `:9904`, writer `:9905`, researcher `:9906`, image-creator `:9907`, video-creator `:9908`, audio-creator `:9909`.
- **Peer lists** live per profile in `a2a_agents` (the graph above) with
  `timeout: 310` — the 120 s caller default undercuts the 300 s server reply
  window. Enforcement is config plus operating contract, not a plugin hook.
- **Secrets.** Under multiplex each profile's keys come from its own
  `secrets.command`, never the process env: [`models-auth.md`](./models-auth.md)
  "Secrets layering".

## Two delegation layers

|            | Resident session                                                    | `delegate_task`          |
| ---------- | ------------------------------------------------------------------- | ------------------------ |
| Worker     | **named profile** session with living context                       | anonymous subagent       |
| Dialogue   | conversational turns (feedback in minutes)                          | none — one shot          |
| Durability | session registry + durable-path files                               | dies with the turn       |
| Requires   | terminal + the wrapper script                                       | nothing                  |
| Use for    | **default for heavy work**: anything you expect to give feedback on | in-turn parallel lookups |

**Fallback story:** resident sessions work whenever `hermes` runs — no gateway
needed. Gateway up adds cron for fire-and-forget work; gateway down,
`default` still parallelizes via `delegate_task`. A specialist may itself call
`delegate_task` during its run.

## Profile roster

| Profile           | Role                                                                                                                                                                                                                                                                    | Front door           | `terminal.cwd`         | Toolsets                                                                                                                                                    | Gateway                  | Tracked               |
| ----------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------- | ---------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------ | --------------------- |
| **default**       | CLI front door — assistant's CLI counterpart (neutral persona); hosts the multiplex gateway                                                                                                                                                                             | CLI                  | `.` (launch dir)       | `web,browser,terminal,file,code_execution,vision,x_search,skills,todo,memory,clarify,delegation,cronjob`                                                    | host                     | yes                   |
| **assistant**     | primary: messaging front door, non-creative quality gate, GitHub bookkeeping; drives OpenCode (see [opencode.md](./opencode.md))                                                                                                                                        | Telegram + Discord   | `~/Workspaces`         | `web,browser,terminal,file,vision,x_search,skills,todo,memory,clarify,delegation,cronjob,computer_use,specialist,opencode,characters` + `unreal-engine` MCP | served                   | yes (private overlay) |
| **researcher**    | purpose-first depth modes investigate / compare / verify / advise over shared Plan / Build stages (Build ends with a self-check); proposes own-role scope, requests heavy breadth from the caller; serves creator/marketer only (not Assistant directly), cards refused | — (A2A receive-only) | `.` (launch / task ws) | `file,web,vision,video,skills,memory,delegation`                                                                                                            | served (a2a :9906)       | yes                   |
| **searcher**      | purpose-first retrieval modes lookup / sweep / hunt over shared Plan / Build stages (Build ends with a check); resident sessions only, cards refused; a multi-hop hunt is one conversation the caller continues                                                         | — (specialist)       | `.` (launch / task ws) | `file,web,x_search,x_access,youtube_access,note_access,substack_access,skills,memory`                                                                       | served (no platforms)    | yes                   |
| **creator**       | the Assistant's creative advisor: turns intent into 2-3 named directions with draft hands handoffs, and feedback into located, named revisions; never produces or commissions (see [creator.md](./profiles/creator.md))                                                 | — (Assistant only)   | `.` (launch / task ws) | `file,vision,web,skills,memory,specialist,media_inspect`                                                                                                    | served (a2a :9903)       | yes                   |
| **image-creator** | still-image hands: runs one `<verb>/<subject>` leaf from a filled form, QA with evidence, report; answers only the Assistant                                                                                                                                            | — (A2A receive-only) | `.` (launch / task ws) | `terminal,file,vision,image_gen,skills,memory`                                                                                                              | served (a2a :9907)       | yes                   |
| **video-creator** | video hands: clip, tour, ad, explainer-video, promotion, story, master, pixel-animation and music-video leaves from approved forms; answers only the Assistant                                                                                                          | — (A2A receive-only) | `.` (launch / task ws) | `terminal,file,vision,video_gen,video,skills,memory`                                                                                                        | served (a2a :9908)       | yes                   |
| **audio-creator** | audio hands: speech, sfx, music (instrumental BGM/melodic pieces only) and mix (placing already-finished sources, never synthesis) from approved forms; measured/readback QA, no claims of listening; no full songs or voice registration; answers only the Assistant   | — (A2A receive-only) | `.` (launch / task ws) | `terminal,file,tts,sfx_gen,music_gen,skills,memory`                                                                                                         | served (a2a :9909)       | yes                   |
| **writer**        | reader-facing prose and producer-facing scripts from released units (outline / piece / whole job); draft-only, never publishes; serves the assistant                                                                                                                    | — (A2A receive-only) | `.` (launch / task ws) | `writing-inspection,characters,file,web,skills,memory,delegation`                                                                                           | served (a2a :9905)       | yes                   |
| **marketer**      | primary: strategy advisor — discovery, positioning, campaigns, review findings and outcome analysis for the assistant and the human; read-only toward every service; clients execute                                                                                    | Telegram (own bot)   | `.` (launch / task ws) | `terminal,file,web,browser,x_search,x_access,substack_access,youtube_access,note_access,vision,skills,memory,delegation,specialist,clarify`                 | served (bot + a2a :9904) | yes                   |

### Toolsets

The table lists each role's native capability allowlist.
`platform_toolsets.<platform>` is the effective runtime allowlist and stays
granular: the composite `hermes-cli` / `hermes-telegram` toolsets expand to a
broad surface and strip default-off tools such as `video` / `video_gen`.
Top-level `toolsets` mirrors the role.

- **Messaging lists.** The two bots (assistant, marketer) carry
  real `telegram` lists; assistant alone adds `discord`. creator, writer,
  researcher, searcher, the hands and default keep their Telegram / Discord lists
  empty.
- **A2A lists.** Every A2A-serving profile has an `a2a` list for its inbound peer
  sessions, usually narrower than CLI (Marketer's inbound A2A has no browser,
  terminal or delegation, so its browsing needs a resident session).
  `a2a` is also the name of the OUTBOUND toolset (the five default-off `a2a_*`
  tools); assistant, creator and marketer expose only `specialist` for
  outbound requests.
- **MCP.** Platforms without MCP access carry the `no_mcp` denial sentinel;
  otherwise each allowed server is listed explicitly (assistant names only
  `unreal-engine`) so future servers are never inherited.

Role split: **the assistant** plans with the user, supervises specialists,
performs the non-creative quality gate itself (see
[assistant.md](./profiles/assistant.md) "Assistant quality gate"), owns GitHub
bookkeeping and delivers; the **producer** self-verifies before reporting. The
normal flow stays **searcher (retrieve) → researcher (synthesize) → OpenCode
(implement, driven by the assistant)**, with the **hands** (media) and **writer** (prose/scripts) as
production stages, and **creator** (creative direction) and **marketer**
(strategy) as advisors beside them; the assistant commissions the hands itself,
saves the resulting service drafts and the user publishes. User approval follows
the domain's checks. Creative production uses direct early delivery rather than
another broker inspection.

### Planning ownership

Assistant coordinates cross-specialist outcomes as a Client. OpenCode plan runs
own code-grounded technical proposals and sequencing, which the Assistant agrees
with the user ([opencode.md](./opencode.md)); Client approval chooses scope and
important tradeoffs. The technical plan lives in the agreed
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
`skills.external_dirs` entry is needed. The Assistant's entries and Writer's
production leaves are not imposed on default's menu or its clones. In raw content,
`${HERMES_SKILL_DIR}` is the owning child's directory, never the adapter's or
whichever skill was last loaded. When `writer-pipeline` is unavailable by name,
requester QA reads the documented
`~/.hermes/profiles/writer/skills/writer-pipeline/references/acceptance/index.md`
and selected `prose.md`/`script.md` with `read_file`, for inspection only. Do not
expose Writer's production leaves to solve a reference lookup.

### Two working directories per worker

- **Direct / `delegate_task` work** starts in `terminal.cwd` — currently `.`
  (the launch dir) for most workers; pin an absolute path per worker for a fixed
  directory. `workspace/` is per-machine and never tracked.

## Operating layers (per profile)

Three per-profile layers, kept separate:

- **SOUL.md** — persona/voice (BASE: Identity/Style/Avoid/Defaults + a one-line Role posture).
- **`agent.system_prompt`** (config.yaml) — the always-on _operating contract_: how the
  profile works each task. Workers open with "first action: load `<skill>`"; the assistant
  carries its chat-output contract + a compact work-routing tripwire here, kept out of
  SOUL so it survives. `/personality` shares this slot and would clobber it — don't
  use it on these profiles.

  Every contract also carries an always-on **safety floor** — the rules that must
  hold even when the profile's skill never loads: creator = the
  advisory floor (no production, no commissioning, no design that binds the
  producer, no verdicts; a recommendation is never approval); researcher = evidence integrity (no
  fabricated citations); searcher = link integrity (only URLs actually
  retrieved); writer = deliverable integrity (no fabricated
  facts/quotes/URLs; assumptions labeled; the selected leaf's applicable
  checks with explicit evidence gaps) + never publishes; marketer = the
  advisory + evidence floor (read-only toward every service: no posting,
  editor entry, draft saving or sending; traceable claims and no fabricated
  demand/metrics; user-owned commitments; a review is advice, never
  acceptance); the assistant's marketing entries carry the draft floor (exact
  remote-save consent before input; no publishing, scheduling or sending;
  reopened unpublished draft verification; uncertain effects never blindly
  retried) and its creative entries carry the hands floor (Budget/spend caps,
  exact approval relay, explicit upload consent); front doors = heavy work never
  runs in their own turn, deliverables are verified before delivery, and code
  changes only through an approved OpenCode build.
  Each profile also states its **MEMORY.md policy**: durable cross-task facts
  only (task state lives in git and the session; playbook-sized
  knowledge becomes a skill), and `user_profile_enabled` is off for workers —
  they never converse with the human.

- **skills/** — detailed, on-demand playbooks. Every local library uses the same
  ownership types. A worker has one tracked `<profile>-pipeline/` plus tracked,
  directly selectable `technic/` leaves. The assistant owns a tracked
  `assistant-pipeline/` (kernel + child entries) and may add private
  technics on the overlay's own `technic/` shelf, read through
  `skills.external_dirs` (see
  [ops/skills.md "Skill placement"](ops/skills.md)); default owns the shared tracked
  `default-pipeline/` adapter. A plugin's own tool mechanics are skills shipped
  inside the plugin and registered per profile as `<plugin>:<skill>` (see
  [ops/skills.md "Skill placement"](ops/skills.md)). Pinned Telegram topics bind no skill (see
  [assistant.md](./profiles/assistant.md) "Pinned Telegram topics").
  Runtime-authored skills (background review, curator, `/learn`, ordinary
  `skill_manage(create)`) go to the untracked `learned/` category through
  `skills.create_dir: skills/learned` in every `config.yaml` (an optional
  `category` nests as `learned/<category>/<name>`). Moving a complete package
  from `learned/` to `technic/` is the explicit maintainer-review boundary.
  External directories remain provider-owned and never become local technics
  implicitly.
  - assistant → `assistant-pipeline` (Chat / Plan / Execute / Quality Assurance
    over tiers inline / resident; `chat-assistant` and
    `{plan,execute,qa}-assistant-<domain>` children; resident sessions via
    `resident-session.sh`; assistant-run QA contracts). Default's
    `default-pipeline` records only terminal-specific deltas. External libraries
    via `skills.external_dirs`: official apple / creative / email / github / media
    / note-taking / productivity / research / smart-home / social-media plus
    optional `one-three-one-rule` (decision framing) and `watchers` (RSS/API
    polling for cron sweeps), the three hands pipelines (read for their forms;
    the commissioning references live in `execute-assistant-creative`, see
    [`broker.md`](./broker.md)); heavy tool-bound creative entries (`comfyui`,
    `touchdesigner-mcp`, `manim-video`, `ascii-video`) sit in `skills.disabled` —
    media production is the hands'.
  - researcher → `researcher-pipeline` (resident sessions + inbound A2A from
    creator/marketer; investigate / compare / verify / advise modes;
    returns spec-gap and granularity findings; see [research.md](./profiles/research.md)) + optional
    `domain-intel` and `osint-investigation` (stdlib-only recon /
    public-records) plus keyless `duckduckgo-search` (run through `uvx ddgs`).
  - searcher → `searcher-pipeline` (resident sessions only; lookup / sweep / hunt
    modes with spec-gap and granularity findings and the
    link-integrity floor; no technics; see [research.md](./profiles/research.md)) +
    keyless optional `duckduckgo-search` and `domain-intel`.
  - image-creator → `image-creator-pipeline` (the hands root: validate the filled
    form → load the leaf → run → QA → report; leaves are
    `<verb>/<subject>`, see [`hands/overview.md`](./hands/overview.md)).
    video-creator and audio-creator follow the same shape
    ([`hands/video.md`](./hands/video.md), [`hands/audio.md`](./hands/audio.md)).
  - creator → `creator-pipeline`: `propose-creator` (intent into 2-3
    named directions, each with an existing example and a draft hands handoff)
    and `revise-creator` (verbatim feedback into located, named changes, each
    with a draft revision handoff); one capability reference per served subject
    under `references/<hands>/<subject>.md` (see
    [creator.md](./profiles/creator.md)). No technics.
    External libraries: the three hands pipelines (read-only, for forms and
    option references), the curated `media-craft-*` skills and the HyperFrames
    store's knowledge skills for vocabulary; no production engines.
  - writer → `writer-pipeline` (resident + inbound A2A, cards refused; released
    units — outline / piece / whole job — with spec-gap and granularity findings;
    `<write|edit|analyze>/<subject>/SKILL.md` leaves across post, article,
    document, message, copy and script plus `consult-writer`; see
    [writer.md](./profiles/writer.md)). External skills: the curated
    `profiles/writer/external-skills/` symlink dir (the single `japanese-writing`
    skill — shared Japanese workflow, references and read-only inspector,
    single-sourced with the shared `agents/curated/` store) and upstream
    `creative/humanizer` (explicit-request only).
  - marketer → `marketer-pipeline` (plan / review / analyze advisory entries;
    browsing resident-only, cards refused; see [marketer.md](./profiles/marketer.md)).
    Its only external skill is the private `hermes-browser-relaunch`; Writer's
    pipeline is not readable there. No xurl/humanizer imports or publish engine.

  **Upstream wiring pattern.** Official `skills/` libraries attach per category
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

Assistant, Creator, Researcher, Searcher, Writer and Marketer expose
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
