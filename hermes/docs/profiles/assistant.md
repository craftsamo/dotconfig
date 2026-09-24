# Assistant

Front-door Client: quality gate, visual design and timeline, creative early delivery, entry routing, tiers and pinned topics. Part of the Hermes design docs — index: [`PROFILES.md`](../../PROFILES.md).

## Assistant quality gate

For non-creative work, the assistant is the quality gate. Every specialist deliverable — a resident
session reply or a card completion — is a candidate until the assistant
verified the actual artifact per the contracts under
`profiles/assistant/skills/assistant-pipeline/qa-assistant-*/` and common QA
(`references/quality-assurance/index.md`; Writing QA uses Writer's public
acceptance contract — see [writer.md](./writer.md) "Writer craft and independent
editorial QA"): vision on images/frames, ffprobe on av
media, read the prose, spot-check sources; `delegate_task` fans out
per-artifact checks on large sets. Defects go back to the same resident
session as itemized feedback — a minutes-scale loop, not a card cycle.
Delivery happens only after verification; the session is closed on
acceptance. External factual claims still ride researcher evidence supplied
in the flow.

## Visual design and timeline

Assistant is a deliverable-first Client, not a second production broker. For
newly authored video it passes intent and acceptance — purpose, audience,
destination, fixed words, brand rules, exclusions, inputs, references and
what each is for — and the producer designs the storyboard, which Assistant
relays for the user's approval. In a blind study (2026-09-24,
`~/Workspaces/.deliverables/video-craft-ab-2026-09/`) every film whose visual
design the Assistant authored as a timeline ranked in the bottom half, with or
without a motion vocabulary, because the diagram's shapes and opacities bind
the producer; producer-designed storyboards ranked first. Static UI images
still use Assistant's component design without an invented video duration.

Assistant authors a designed timeline only when the user explicitly asks for
one; then it owns concrete visible intent — complete scene progression,
intermediate changes, deliberate holds, camera/text/audio relations and
per-component UI anatomy, typography, surfaces and states — and conditional
reference research connects inspected examples to scene/event/component
decisions. Exact edits, analysis, research-only and frozen render resumes keep
their existing scope.

The existing private Plan entry owns a plain `video-design.md` guide; no new
profile, skill root, toolset or card is added. Its public stdlib helper at
`profiles/assistant/scripts/creative-timeline.py` renders validated data into
an inert, self-contained HTML timeline, with retained JSON and an identity
receipt in a fresh exclusive bundle. This is a planning-only document for the
existing plan agreement — not production HTML, another hands form, a media
render or arbitrary HTML execution. Diagrams and complete design text are
visible together; omitted intermediate states or unaccounted visual time fail
structural checks, but the helper validates structure, not artistic quality or
user authority. Open issues stay discussion-only. Telegram receives a document;
attached HTML opening needs actual client verification, not a promise based on
message `parse_mode`. No hosting, Mini App or remote asset fetch is introduced.

Use that identified version for the existing plan agreement, not a new approval
ceremony. Creator owns the actual supported technology, realization and
production approvals: its shared craft contract owns the technical realization
map and sends full design requirements through existing hands fields/note.
Preserve full design identity/IDs and intermediate states across the handoff.
Required parallax, occlusion, material changes, 3D/shader motion or bespoke
components cannot be silently flattened into simpler substitutes or generic
controls. Actual GSAP/Three.js/GLSL/Anime.js roles must be checked against the
selected producer; this feature changes neither the available renderers nor
frozen jobs, and Three.js/shader runtime expansion is separate implementation
work, not implied by reference access. Hands keep their own proposal/preview
approvals, rendered checks and budgets. Ordinary production still delivers
without another broker aesthetic inspection. Assistant's retired house formats,
device catalog and blanket past-film recipes are not transplanted into Creator.
Client guides, legacy references and upload consent: [`broker.md`](../broker.md)
"Assistant Client guides and retirement gates".

Status: deployed. Validation covered structure, restricted model probes and a
native Telegram document the user opened; it does not establish artistic
quality, actual video rendering, new Three.js/GLSL runtime support, primary-model
behavior or automatic failover. Required craft bodies unavailable through name
lookup recover from canonical files. Existing conversation histories are not
presumed refreshed.

## Creative early delivery candidate

Normal creative production is Plan -> Build/Execute -> delivery. Creator and
Assistant do not run a routine perceptual acceptance stage, repeat measurements,
invoke learned verification for a second gate or autonomously polish a candidate
before showing it; do not restore routine broker inspection through learned
skills or delivery references. This includes confirmed legacy methods and
creative cards. The producer keeps its self-checks; brokers read report
completeness, obvious settled-constraint conflicts and spend, then forward
artifacts and limitations. Required failures still block final readiness and
dependent use, but a viewable preview can be shown with those failures
disclosed. Delivery is not acceptance, and an early preview establishes neither
final readiness nor approval.

`qa-creator` and `qa-assistant-creative` remain explicit user-requested inspection
entries, not automatic completion steps. They return one scoped findings pass,
not an automatic repair grant or a chain of broker reviews. Existing entry
topology, hands forms, producer scripts, failed/unknown disclosure,
proposal/preview hashes and approvals, upload and remote-analysis consent,
budgets and non-creative QA remain unchanged.

Use an early supported representative sample for unresolved direction. With a
moving reference, demonstrate composition and progression, not just an ending
or static frame. Rejection of the idea returns to interpretation rather than
minor polish. Samples retain their existing approval and spending rules.

Status: paired public/private candidate, not a live cutover; paired candidate
verification does not authorize it. Timing and creative quality require fresh
real work after explicit rollout approval (see [topology](../topology.md)
"Candidate rollout and cutover").

## Assistant entry routing

The deployed layout retains the `assistant-pipeline` root name and private directory
overlay. The root owns invariant lifecycle, grants and delivery policy. Its
19 independent child skills are `chat-assistant` plus
`{plan,execute,qa}-assistant-<domain>` for engineering, creative, writing,
research, search and marketing. Each child root `SKILL.md` owns its former
mode/domain index; each child's `references/` holds details and creative legacy.
No entry lives below the parent's `references/`. The shared parent files are
only `references/plan/index.md`, `references/execute/{index,resident-sessions,kanban-lite,scheduled}.md`
and `references/quality-assurance/index.md`; Chat's common procedure is its
entry body. No aliases, generated index, new overlay/symlink install mapping or
default `skills.external_dirs` expansion. Writer's acceptance rubric remains in
its public pipeline, not copied into private QA entries.

Loading follows the shared [entry loading contract](../topology.md#entry-loading-contract):
each entry requires the invariant kernel and its mode-common procedure before
applying relevant details. An approval-only reply follows existing job state
and scope; it never restarts planning or widens a grant. Default's CLI adapter
reads the same tree through the filesystem (see [topology](../topology.md)
"Default is the assistant's CLI counterpart").

Status: deployed; existing messaging histories are not proven refreshed.

### Routing and tiers

Telegram auto-loads the root skill through its chat-wide
`channel_skill_bindings` entry (root DM plus fixed and user-created topics).
Discord binds the allowlisted guild channel explicitly; auto-created threads
inherit that parent binding and channel prompt. Discord DM bindings require the
literal DM channel ID and cannot use a user-ID wildcard: the first authorized DM
is bootstrap-only, then its channel ID is added to both `channel_skill_bindings`
and `channel_prompts`, the gateway is restarted, and `/new` starts the first
working session. The gateway injects the skill body into the session's first
turn; `compression.protect_first_n` protects initial context but does not prove
all required bodies remain present. After an approved restart, `/new` starts a
session on the refreshed index.

Every working request flows Classify → Locate → Mode (Chat / Plan / Execute /
Quality Assurance) → Deliver. Questions are risk/ambiguity driven: a settled
request does not pay an interview tax. Tier selection is by context dependence,
not size: `inline` for conversation/quick local work, a **resident session** for
anything the user will give feedback on (the default for heavy work, started
through `specialist_call(kind="work")`), and a lean kanban card only for
fire-and-forget, cron-originated, mass-parallel, or `scheduled` work. Plan mode
ends in one conversational approval that sanctions the grants; Execute
supervises the sessions turn by turn, sizing each resident turn to one
verifiable increment and continuing in the same conversation; QA verifies actual
artifacts before delivery.

The org stays **flat by design**: profiles are global, resident sessions are
owned by their originating Client, and the board is one shared queue.
Specialists never register cards; follow-up work they propose returns in their
reply or completion summary, and the assistant decides. Grants never propagate
between specialists. `auto_decompose` stays off — decomposition is a
conversation, not a runtime fallback. `delegate_task` covers medium parallel
lookups the user is actively waiting on, and absorbs per-artifact QA checks on
large sets. Keep routing in sync with each `profile.yaml` description.

### Kanban catalog

The kanban catalog is closed and per-assignee: its machine-readable surface is
the union of `card_units` frontmatter in
`assistant-pipeline/execute-assistant-creative/SKILL.md` and
`assistant-pipeline/execute-assistant-search/SKILL.md` only; detail references
must never declare card units. Each unit names its `assignee` worker, and the
validator cross-checks worker kernels against it. Seeded units are creative:
`anchored-image-batch`, `deterministic-render`; and search:
`survey-enumeration`, `exhaustive-hunt`. Engineering, writing, marketing and
research are card-free and refuse every card (the research `claim-verification`
unit is retired; fact-checks travel through the researcher's A2A peers).

A card must match one unit and carry every required input; otherwise the work
stays resident or is decomposed during planning. Composites are never one card
(never send 0→10 as one card). All six worker pipelines fail fast at the Unit
gate with `kanban_block(kind=capability)` for composite or malformed cards.
The card is lean: no manifests, digests or probes.

On cards, specialists speak the `STATE:` / `Q<n>:` / `DECISION(Q<n>):` /
`PROGRESS:` / `AUTHORITY+:` / `REVIEW:` comment protocol. Only terminal events
(completed / blocked / gave_up / crashed / timed_out) wake the assistant;
comments do not. Workers batch questions into one `needs_input` block, and the
assistant answers once via `DECISION(Q<n>):` comments plus
`kanban-resolve-block.sh apply`. A second block, any `capability` block, or a
spec-gap question pulls the card back for a resident session or re-plan.
Time-deferred work parks in `scheduled` via `hermes kanban schedule <id>
"until=<ISO8601> — <reason>"` (a `SCHEDULED: until=` comment); the assistant's
no_agent `kanban-scheduled-sweeper.sh` cron releases due cards every 15 minutes.
Dead cards close via `hermes kanban archive <id>`.

### Pinned Telegram topics

The assistant's `platforms.telegram.extra.dm_topics` (private `config.yaml`)
declares exactly two pinned topics, both skill-less Assistant surfaces rather
than worker threads — the chat-wide `assistant-pipeline` binding is the only
skill surface, and a per-topic skill layer only duplicated that routing. Each
topic's contract lives entirely in its `channel_prompts['<thread_id>']` entry
(template in `config.example.yaml`). The validator
(`validate_assistant_dm_topics`) rejects any topic carrying a `skill:` key and
any `dm_topics` list without a topic literally named `Inbox`, so the retired
desk layer (Personal / Projects / Brainstorm and their skills and `desks/`
overlay link) cannot creep back.

- **Inbox** receives system cron output and starts no work. Jobs keep bare
  `deliver: telegram`; `scripts/profile-secrets.sh` derives
  `TELEGRAM_CRON_THREAD_ID` from the topic literally named `Inbox`, so renaming
  it makes every such job fail closed. Kanban completion notifications stay
  attached to their originating topic; only maintenance/report/sweeper cron
  output targets Inbox.
- **Admin** is the inline surface for small administrative work: workspace
  bookkeeping (`pj` registry, scaffold, `pp` / `hb` records, docs/data
  touch-ups), edits to the `~/.config` dotconfig repo and its Hermes profiles,
  and Hermes upkeep (browser relaunch, cron / validator checks, skill
  housekeeping). No resident session, delegation or kanban card. Its OpenCode
  grant is limited to this scope (see [engineer.md](./engineer.md) "OpenCode
  runtime").

Both fix the tier to `inline`; work that needs a specialist hands off to a new
ad-hoc topic, which inherits chat-wide `assistant-pipeline` and owns the
sessions. A new pinned topic is a `dm_topics` entry WITHOUT `thread_id`: the next
gateway start creates the forum topic and writes the id back through the symlink
into the private `config.yaml`; only then can its `channel_prompts` entry be
keyed, followed by `/restart`. Hermes never deletes a Telegram topic: close retired ones by hand in the
client.
