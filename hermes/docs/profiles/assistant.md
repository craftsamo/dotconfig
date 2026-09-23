# Assistant

Front-door Client: quality gate, visual design and timeline, creative early delivery, entry routing. Part of the Hermes design docs — index: [`PROFILES.md`](../../PROFILES.md).

## Assistant quality gate

For non-creative work, the assistant is the quality gate. Every specialist deliverable — a resident
session reply or a card completion — is a candidate until the assistant
verified the actual artifact per the contracts under
`profiles/assistant/skills/assistant-pipeline/qa-assistant-*/` and common QA (vision on images/frames, ffprobe on av
media, read the prose, spot-check sources; `delegate_task` fans out
per-artifact checks on large sets). Defects go back to the same resident
session as itemized feedback — a minutes-scale loop, not a card cycle.
Delivery happens only after verification; the session is closed on
acceptance. External factual claims still ride researcher evidence supplied
in the flow.

## Visual design and timeline

Assistant owns concrete visible intent for newly authored video: complete scene
progression, intermediate changes, deliberate holds, camera/text/audio relations
and per-component UI anatomy, typography, surfaces and states. Conditional
reference research connects inspected studio process and actual UI examples to
scene/event/component decisions, not just aesthetic labels. Exact edits,
analysis, research-only and frozen render resumes keep their existing scope;
static UI images use component design without an invented video duration.

The existing private Plan entry owns a plain `video-design.md` guide; no new
profile, skill root, toolset or card is added. Its public stdlib helper at
`profiles/assistant/scripts/creative-timeline.py` renders validated data into
an inert, self-contained HTML timeline, with retained JSON and an identity
receipt in a fresh exclusive bundle. This is the narrow local planning-document
exception, not a production renderer or arbitrary HTML execution. Diagrams
and complete design text are visible together; omitted intermediate states or
unaccounted visual time fail structural checks, but a pass is not artistic
acceptance. Open issues stay discussion-only. Telegram receives a document;
attached HTML opening needs actual client verification, not a promise based on
message `parse_mode`. No hosting, Mini App or remote asset fetch is introduced.

Use that identified version for the existing plan agreement, not a new approval
ceremony. Creator's shared craft contract owns the technical realization map
and sends full design requirements through existing hands fields/note. Required
parallax, occlusion, material changes or bespoke components cannot be silently
flattened into simpler substitutes. Actual GSAP/Three.js/GLSL/Anime.js roles
must be checked against the selected producer; this feature does not install
or newly support those runtimes. Three.js/shader runtime expansion is separate
implementation work, not implied by reference access. Hands keep their own
proposal/preview approvals, rendered checks and budgets. Ordinary production
still delivers without another broker aesthetic inspection.

Cut over on 2026-09-13 with explicit approval. Both live source trees were
updated together on deployment branches; existing script-directory links were
preserved. One launchd-owned SIGUSR1 restart restored all 13 connections with
no adapter failure, secret timeout, duplicate poller or traceback in the bounded
restart log. No existing job, frozen output or approval was rewritten.

Preflight passed strict Git/topology validation, 1,137 public tests (14 skipped,
203 subtests), 97 private tests and 66 runtime tests. Fresh restricted model
probes used deployed profiles/instructions and actual local helper execution:
Assistant authored a six-second fictional design with intermediate states and
component appearances, then passed check/output; Creator read that same JSON
and mapped requirements to technical methods while retaining unverified limits.
These were separate process-local probes with no delegation or media generation,
not an unrestricted end-to-end production conversation. The primary Assistant
Claude request returned 429 before any instruction read; both successful probes
explicitly used the already-configured Codex fallback without changing the live
model configuration. Primary-Claude behavior and automatic failover remain
unverified by this test.

One explicitly approved native Telegram document send reached the user's
Assistant DM; downloading that document reproduced the exact HTML hash, and
the user confirmed opening it and seeing the diagrams and explanations. The
ordinary gateway bare-path extractor also recognized the actual HTML under
the deployed profile policy without changing it. This checks transport and
client opening separately from the model probe; it does not prove artistic
quality, actual video rendering or new Three.js/GLSL runtime support. Required
craft bodies unavailable through name lookup recovered from canonical files;
future rollouts still need paired validation, explicit restart approval and
fresh-session checks. Existing conversation histories are not presumed refreshed.

## Creative early delivery candidate

Normal creative production is Plan -> Build/Execute -> delivery. Creator and
Assistant do not run a routine perceptual acceptance stage, repeat measurements,
invoke learned verification for a second gate or autonomously polish a candidate
before showing it. This includes confirmed legacy methods and creative cards.
The producer keeps its self-checks; brokers read report completeness, obvious
settled-constraint conflicts and spend, then forward artifacts and limitations.
Required failures still block final readiness and dependent use, but a viewable
preview can be shown with those failures disclosed. Delivery is not acceptance.

`qa-creator` and `qa-assistant-creative` remain explicit user-requested inspection
entries, not automatic completion steps. They return one scoped findings pass,
not an automatic repair grant or a chain of broker reviews. Existing topology,
hands forms, producer scripts, proposal/preview hashes and approvals, upload and
remote-analysis consent, budgets and non-creative QA remain unchanged.

Use an early supported representative sample for unresolved direction. With a
moving reference, demonstrate composition and progression, not just an ending
or static frame. Rejection of the idea returns to interpretation rather than
minor polish. Samples retain their existing approval and spending rules.

This is a paired public/private candidate, not a live cutover. Validate discovery
and contracts offline; timing and creative quality require fresh real work after
explicit rollout approval. Rollback restores the paired prior configuration;
never rewrite frozen jobs, outputs, grants or approvals.

The org stays **flat by design**: profiles are global, resident sessions are
owned by their originating Client, and the board is one shared queue. Specialists never register
cards; follow-up work they propose returns in their reply or completion
summary, and the assistant decides. Grants never propagate between
specialists.

## Assistant entry routing

The deployed layout retains the `assistant-pipeline` root name and private directory
overlay. The root owns invariant lifecycle, grants and delivery policy. Its
19 independent child skills are `chat-assistant` plus
`{plan,execute,qa}-assistant-<domain>` for engineering, creative, writing,
research, search and marketing. Each child root `SKILL.md` owns its former
mode/domain index; each child's `references/` holds details and creative legacy.
No entry lives below the parent's `references/`. The shared parent files are
`references/plan/index.md`, `references/execute/{index,resident-sessions,kanban-lite,scheduled}.md`
and `references/quality-assurance/index.md`; Chat's common procedure is its
entry body. No aliases, generated index or new symlink install mapping.

Always-on routing selects the relevant entry from the available skill index on
each user turn and completion notification, and BEFORE an action changing mode,
domain or scope midturn. Full bodies already present in current context can be
reused; a past load or summary cannot. If needed, read the selected entry, the
full kernel, mode-common and relevant details. Direct entry has the same
dependencies; root preload is not proof they are present. An approval-only reply
follows existing job state and scope, never restarts planning or widens a grant.
An unchanged result with a missing body requires the entry-local canonical
`read_file` fallback, following `next_offset` for truncation, or stopping the
affected action. Read dedup is a source/runtime limitation, not a prompt-level
guarantee of complete current context; never evade it with alternate paths or
artificial ranges. Writer's acceptance rubric remains in its public pipeline.

**Cut over 2026-09-12.** Live strict topology/Git validation passed, the single
multiplex gateway restored all 13 configured connections, and a restricted
two-turn Assistant CLI probe loaded the document guide then reused the current
entry/common bodies while loading the script guide. No production or message
sending was exercised; existing messaging histories are not proven refreshed.
Paired candidate checks use `HERMES_PRIVATE_ROOT` on public
tests and `HERMES_PUBLIC_ROOT` on private tests, without installing/linking live
paths or relaxing their Git ownership checks. Manual edits do not invalidate
the gateway's process skill-index cache: cutover requires explicit approval,
a controlled restart AND a fresh session. Restore paired public/private sources
for rollback without changing frozen outputs or approvals.

Routing (assistant): Telegram auto-loads the root skill
through its chat-wide `channel_skill_bindings` entry (root DM plus fixed and
user-created topics). Discord binds the allowlisted guild channel explicitly;
auto-created threads inherit that parent binding and channel prompt. Discord DM
bindings require the literal DM channel ID and cannot use a user-ID wildcard: the
first authorized DM is bootstrap-only, then its channel ID is added to both
`channel_skill_bindings` and `channel_prompts`, the gateway is restarted, and
`/new` starts the first working session. The gateway injects the skill body into
the session's first turn; `compression.protect_first_n` protects initial context,
but does not prove all required bodies remain present. After the approved
restart, `/new` starts a session on the refreshed index. Every working request flows
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
`card_units` frontmatter in `assistant-pipeline/execute-assistant-creative/SKILL.md`
and `assistant-pipeline/execute-assistant-search/SKILL.md` only. Detail references
must never declare card units.
A card must match one unit and carry every required input; otherwise the work
stays resident or is decomposed during planning. Composites are never one card
(never send 0→10 as one card). Seeded units are creative:
`anchored-image-batch`, `deterministic-render`; and search:
`survey-enumeration`, `exhaustive-hunt`. Engineering, writing, marketing,
and research are card-free (the research `claim-verification` unit was
retired in the 2026-09 peer rebuild; fact-checks now travel through the
researcher's A2A peers). All six worker pipelines fail fast at the
Unit gate with `kanban_block(kind=capability)` for composite or malformed cards.

The pinned Telegram topics are two skill-less Assistant surfaces, not worker
threads (`platforms.telegram.extra.dm_topics`; the 2026-09-14 rebuild retired
the four-desk layout — Personal / Projects / Brainstorm and their
`personal-desk` / `project-desk` / `brainstorm` skills — because the
chat-wide `assistant-pipeline` binding plus the workspace skills already
covered every desk operation, and a per-topic skill layer only duplicated
the routing). **Inbox** is the delivery target for system cron output and
starts no work; **Admin** is the inline surface for small administrative
work that does not deserve its own topic — workspace bookkeeping (`pj`
registry, scaffold, `pp` / `hb` records, docs/data touch-ups), edits to the
`~/.config` dotconfig repo and its Hermes profiles, and Hermes upkeep
(browser relaunch, cron / validator checks, skill housekeeping). Each
topic's contract lives entirely in its `channel_prompts` entry; neither
binds a `skill`, and the validator rejects one (`validate_assistant_dm_topics`)
so the desk layer cannot creep back. Both fix the tier to `inline`; work
that needs a specialist hands off to a new ad-hoc topic, which inherits
chat-wide `assistant-pipeline` and owns the sessions. Kanban completion
notifications remain attached to their originating topic; only
maintenance/report/sweeper cron output targets Inbox: jobs keep bare
`deliver: telegram`, while `scripts/profile-secrets.sh` derives
`TELEGRAM_CRON_THREAD_ID` from the topic literally named `Inbox` in the
assistant config (the validator requires that name to survive). A new
pinned topic is a `dm_topics` entry WITHOUT `thread_id`: the next gateway
start creates the forum topic and writes the id back into the (private,
symlinked) `config.yaml`, and only then can its `channel_prompts` entry be
keyed. Time-deferred work parks in `scheduled` via `hermes kanban
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
