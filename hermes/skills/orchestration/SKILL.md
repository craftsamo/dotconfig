---
name: orchestration
description: >-
  Front-door playbook shared by both profiles (assistant on Telegram, default
  on the CLI) — walk every request through a 7-step pipeline: Classify
  (Projects / Personal / cross-cutting / neither), Locate (workspace group +
  repo), Approach (Plan / Build / Search / Research / Creative / Inline —
  exclusive), then for Plan only: Decompose the goal with the inlined
  methodology, Register the steps in the session `todo`, run the Plan Loop with
  the user (worker consultations via kanban, advisory). On sign-off,
  Dispatch via the existing topology (single / parents / triage card) with
  self-contained task specs (engineer tasks carry an Authority grant —
  preset A1/A2/A3 + overrides; media tasks carry a MediaBrief; deliverables
  needing human sign-off carry a Review gate), ack with
  the task id, answer engineer questions within the granted authority
  autonomously via `DECISION(Q<n>):` comments (always resetting the
  block-loop counter after a DECISION unblock), relay `REVIEW:` blocks to
  the user untouched, expand grants only through
  `AUTHORITY+:` comments, park time-deferred work in `scheduled` with an
  `until=` comment (the sweeper cron releases it), answer progress
  questions from the task's PROGRESS
  trail (StatusCheck), recover from blocked/gave_up/crashed/timed_out
  events and silent block-loop triage falls, and close dead cards via CLI
  archive. Auto-loaded into each Telegram
  DM session via the chat-wide skill binding; load it via skill_view
  before non-trivial work elsewhere. Prefer the `clarify` tool over
  plain-chat questions whenever options exist. Each approach has its own
  reference under `references/<approach>.md` — load the matching one after
  Step 3.
version: 3.3.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [orchestration, pipeline, classify, locate, approach, plan, dispatch, triage, routing, kanban, delegation, task-spec, workers]
    category: orchestration
    related_skills: []
---

<Goal>

Walk every request through a 7-step pipeline and dispatch well at the end.

Classify → Locate → Approach → (if Plan: Decompose → Register → Plan Loop,
detailed in `references/plan.md`) → Dispatch. At every user-facing choice,
prefer the `clarify` tool over plain-chat questions. When dispatching,
produce board tasks the dispatcher can run unattended: right worker,
self-contained spec, cheapest topology that fits, clean ack, sane failure
recovery.

</Goal>

<Scope>
<UseWhen>

- Always in a Telegram DM session: this skill is auto-loaded at session
  start (chat-wide skill binding) — apply <Pipeline> to every request.
- Elsewhere (CLI session, other platforms): load it before any non-trivial
  work.
- A kanban notification (done / blocked / gave up / crashed / timed out)
  needs follow-up: expanding results or re-dispatching.

</UseWhen>
<DoNotUseWhen>

- Never skip <Pipeline>; the sections from <Workers> onward apply only to
  requests that route to dispatch (Plan / Build / Search / Research /
  Creative).

</DoNotUseWhen>
</Scope>

<UserInteraction>

Prefer the `clarify` tool over plain-chat questions whenever the user has
options to pick from. `clarify` shows up to 4 choices as buttons (CLI
arrows → inline buttons → numbered text on simpler platforms) and appends
an automatic "Other (type your answer)" for free-text — one structured
question, no chat noise.

Use `clarify` for:
- Step 1 ambiguity (Projects vs Personal vs cross-cutting)
- Step 2 ambiguity (which group/repo)
- Step 3 ambiguity (Plan vs Build, which approach)
- Plan Loop iterations (approach pick, scope cut, sign-off gate — see
  `references/plan.md`)
- <BlockedTriage> relays (worker questions that come with options)

Plain chat is fine only when:
- The question is open-ended with no meaningful preset options — even then,
  `clarify` with no `choices` is cleaner than prose.
- You're informing, not asking.

Rules:
- **One question at a time.** `clarify` enforces this; don't stack.
- Put your recommendation in the question text ("I'd pick X because …"),
  not as a fifth option.
- **Max 4 choices.** The auto "Other" covers free-text — don't bypass this
  by pouring more options into chat around the call.

</UserInteraction>

<Pipeline>

Every request walks these steps once. Approach is **exclusive** — one entry
mode per request. Plan handles the request through to dispatch; the other
approaches hand off to dispatch (or end inline) right after Step 3.

```
Step 1  Classify    Projects | Personal | cross-cutting | neither
Step 2  Locate      <Group> (and repo if Projects)
Step 3  Approach    Plan | Build | Search | Research | Creative | Inline
                     │  load references/<approach>.md
                     │
                     ├─ Inline            → done (no dispatch)
                     ├─ Build/Search/      → Step 7
                     │  Research/Creative
                     └─ Plan              → references/plan.md
                                          (Decompose → Register → Plan Loop)
                                          → Step 7
Step 7  Dispatch   <Topology> → <Parameters> → <AfterCreate> → <Failures>
```

Each reference owns its approach's trigger and dispatch notes; load the
matching one right after Step 3. Classify and Locate are silent — never
name the categories in chat unless genuine ambiguity merits a `clarify`.

</Pipeline>

<Step1Classify>

Sort the request by where its work lives:

| Request kind | Category |
| --- | --- |
| Code, repos, builds, project docs/data | **Projects** (`~/Workspaces/Projects/<Group>/`) |
| Personal data & automation (people, household-budget, etc.) | **Personal** (`~/Workspaces/Personal/<Group>/`) |
| Cross-cutting notes, scratch, deliverables, inbox triage | **cross-cutting** (`~/Workspaces/.{notes,scratch,deliverables,inbox}/`) |
| Pure conversation / emotion / opinion / no workspace | **neither** |

- Decide silently; surface only if ambiguous enough to merit a `clarify`
  (e.g. a request that could be Projects or Personal).
- Note: there is a `Projects/Personal/` directory — that is a project group
  named "Personal", not the Personal category. Disambiguate by path level:
  the **category** is the first segment under `~/Workspaces/`.

</Step1Classify>

<Step2Locate>

Identify the workspace concretely:

- **Projects**: identify the `<Group>` (e.g. `CareerCodeClub`, `SEVENDAO`)
  and the `github/<repo>` if code work is implied. Confirm via the registry:
  `pj show <Group>` returns identity, repos, links, members. The full path
  becomes `~/Workspaces/Projects/<Group>/github/<repo>` for code, or
  `~/Workspaces/Projects/<Group>/{docs,data}` for project prose/data.
- **Personal**: identify the `<Group>` (e.g. `HouseholdBudget`, `People`).
  No registry — directory lookup only. The full path is
  `~/Workspaces/Personal/<Group>/{data,docs}`. **Personal data is
  sensitive**: never dump raw values to chat or send externally without an
  explicit OK.
- **cross-cutting**: pick the right `.{notes,scratch,deliverables,inbox}/`
  subdir.
- **neither**: no workspace; the request lives entirely in chat/memory.

Surface a `clarify` only if the user's reference is ambiguous between
several groups/repos.

</Step2Locate>

<Step3Approach>

Pick **exactly one** entry mode — they are exclusive. Each approach has its
own reference; load `references/<approach>.md` after selecting for the
trigger details and approach-specific dispatch notes:

| Approach | Reference | Next step |
| --- | --- | --- |
| **Plan** | `references/plan.md` | Steps 4-6 (in the reference) → Step 7 |
| **Build** | `references/build.md` | Step 7 |
| **Search** | `references/search.md` | Step 7 |
| **Research** | `references/research.md` | Step 7 |
| **Creative** | `references/creative.md` (includes MediaBrief) | Step 7 |
| **Inline** | `references/inline.md` | (no dispatch) |

Decision rule:
- **Implementation work always enters Plan** (standing rule). Build is only
  for cases where the user has already specified scope and approach in
  detail.
- For non-implementation, enter Plan when the request is ambiguous,
  multi-stage, or destructive/irreversible; otherwise pick the matching
  worker approach (Build / Search / Research / Creative) or Inline.
- When unsure between Plan and Build, default to **Plan** for
  implementation.
- When unsure between Inline and a worker approach, fire one `clarify`.

Exception — `delegate_task` (in-turn subagents): for medium parallel
lookups the user is actively waiting on; anything heavier goes to kanban.
Dispatch ticks run ~every 15s, so never send quick jobs to the board — a
30-second job still takes noticeably longer via kanban.

</Step3Approach>

<Workers>

Keep in sync with each worker's `profile.yaml` description:

| Assignee | Sweet spot | Tools |
| --- | --- | --- |
| searcher | breadth-first retrieval: web/X search, links, latest/current info; deep multi-hop via the `deep-retrieval` skill + `goal_mode` | web, x_search |
| researcher | depth: analysis, synthesis, comparison, evaluation, reports | file, web |
| engineer | implementation: drives OpenCode, code changes, debugging, tests, builds, PRs; confirms material decisions via block round-trips | terminal (hermes-cli) |
| creator | ALL media production: image, video, GIF, voice assets, batch and single; delivers via kanban_attach | media gen chains + terminal |
| writer | reader-facing prose: marketing long copy, tech articles/blog, documentation; tone-calibrated JP quality; drafts only — never publishes | file, web |
| marketer | campaign orchestration + approved publishing (X via xurl): content strategy, post/thread copy, ship within a Publish grant; fans out prose to writer, media to creator, research to searcher/researcher | terminal (hermes-cli), web, x_search |

Mixed pipelines flow searcher -> researcher -> engineer, with creator (assets)
and writer (prose deliverables) as side stages. Workers can fan out themselves
(`kanban_create` + `parents`): e.g. engineer dispatches a searcher lookup or a
creator asset mid-implementation — don't pre-decompose what the worker can
request itself. When a worker needs its children's RESULTS, it uses the
**continuation-card pattern** (each worker skill's `<FanOut>` section):
children + a card assigned back to itself gated on them, then complete —
never waiting in-process. Grants never propagate to worker-created
children, and such children notify nobody (the orphan-watchdog cron is
the safety net). Writer vs researcher: researcher's deliverable is a verified
conclusion; writer's is the text itself (voice, structure, reader experience).
Writer tasks: pass the WritingBrief fields you already know — audience,
purpose, medium, tone, length, source links — in the body; the writer blocks
once (tone samples / missing premises) rather than guessing.

During Plan Loop, workers can also be **consulted at advisory altitude**
(see `references/plan.md` "Worker consultations") — the same roster, but
the deliverable is an assessment, not the work product itself.

</Workers>

<TaskSpec>

Workers never see this chat — the task body is their entire context. Always
self-contained:

```text
title: <imperative, <=80 chars>
body:
  Goal: <what outcome, for whom — one short paragraph>
  Inputs: <links, paths, parent task ids, pasted data the worker needs>
  Done criteria: <objective checks the worker can verify itself>
  Output: <shape of the final message: language, format, length; name any
          artifact files to produce>
  Constraints: <scope limits, deadlines, things NOT to do>
  Review: <optional — human-approval gate, decided at Plan sign-off (see
          references/plan.md). "Review: required — <what to present>"
          makes the worker checkpoint and block with a `REVIEW:` headline
          instead of completing, so the user approves the deliverable
          before the task closes. Omit for fire-and-forget tasks — the
          default stays post-hoc review via the completion notification.>
  Budget: <creator tasks only — generation-spend caps; omitted = creator
          defaults. See references/creative.md. Expanded mid-task only via
          AUTHORITY+ comments.>
  Authority: <engineer tasks only — the pre-approval grant, carried over
             from the Plan Loop sign-off (or written tight when Build skips
             Plan — see references/build.md). Open with a preset level,
             then optional override lines. Anything not granted forces the
             engineer into a block round-trip, so grant what the user has
             already sanctioned and no more.>
  Publish: <marketer tasks only — the publishing grant. Omitted = draft-only:
           the marketer blocks with the exact post text/attachments/
           destination and ships only what a DECISION approves, verbatim.
           P1 grants autonomous posting within named caps (account, post
           count, content scope), e.g. "Publish: P1 @acct, <=3 posts".
           Expanded mid-task only via AUTHORITY+ comments. Publishing is
           irreversible — grant only what the user already sanctioned.>
```

Authority presets (shared contract with engineer's `engineer-loop` skill):

| Preset | Grants | Give when |
| --- | --- | --- |
| `A1` | commit to the worktree only | **default** — user hasn't sanctioned anything remote |
| `A2` | A1 + push feature branch + open PR | user already asked for a PR / push in chat or Plan sign-off |
| `A3` | A2 + dependency additions/upgrades | user explicitly sanctioned dependency changes |

- Override lines refine the preset: `scope: only src/foo`,
  `do not touch: migrations/`, `branch: feat/x`. Overrides win.
- An absent Authority section is read as bare `A1` — write it anyway, with
  scope boundaries.
- Mid-task expansions never edit the body: post an `AUTHORITY+: <grant>`
  comment (see <BlockedTriage>). Grants only expand; a shrink means the
  plan changed — revise the plan and issue a replacement task (never edit
  the live task's Authority body).

- Write the body in the language you want the deliverable in.
- Never reference "the conversation above", screenshots, or memories the
  worker lacks; paste or link what matters.
- Scratch workspaces are deleted on completion: require findings in the
  final message / completion summary, never only in files.

</TaskSpec>

<Topology>

Pick the cheapest shape that fits:

1. **Single task** (default) — one clear job, one worker:
   `kanban_create(title=..., assignee=..., body=...)`.
2. **Parents chain** — the stages are obvious and few (2-3): create each stage
   with `parents` set to the prior stage's task id(s). A child stays `todo`
   until every parent is `done`, then auto-promotes to `ready`. Fan-in works
   (several searcher tasks -> one researcher synthesis). Tell each downstream
   body to read its parents' results and list the parent ids.
3. **Triage card** — big or fuzzy: one `kanban_create(..., triage=true)` card
   carrying the whole requirement. The gateway auto-decomposes it into a
   routed child graph using the profile descriptions (a few cards per tick).
   Don't pre-chop the work yourself — invest in the requirement text instead.
4. **Board Plan tree** — the *planning itself* should run unattended:
   investigation advisory cards + one assistant-assigned synthesis card
   (`parents` fan-in, `Review: required`) that drafts the outline, gets it
   approved via a `REVIEW:` block, then opens the build cards. Conditions
   and the synthesis-card template: `references/plan.md` "Board Plan".

Coming out of a Plan Loop (`references/plan.md`), the topology choice is
usually obvious from the signed-off plan — the plan's shape dictates
single / parents / triage.

</Topology>

<Parameters>

- `assignee` is required — tasks without one never dispatch.
- `workspace_kind`: `scratch` (fresh tmp, deleted on completion) is right for
  searcher/researcher and for Plan-loop advisory consultations. Coder work
  on a repo: `worktree` + absolute `workspace_path`, or `project: <slug>`
  for a deterministic project branch. `dir` (shared directory, absolute
  path, no isolation) is rare.
- `priority` (int): dispatcher tiebreaker among ready tasks; higher = sooner.
- `idempotency_key`: set when retrying or re-dispatching — a duplicate card
  returns the existing task id instead of forking work.
- `max_runtime_seconds`: cap runaway tasks (exceeded -> SIGTERM + `timed_out`).
  Set small (e.g. 600) for Plan-loop advisory consultations.
- `skills: [...]`: force-load a specialist skill installed on the assignee's
  profile when the task depends on it (e.g. searcher's `deep-retrieval`).
- `goal_mode: true` (+ `goal_max_turns`): open-ended cards where one shot
  rarely finishes — a judge loops the worker until done or budget exhausted.
  Pair it with `deep-retrieval` for exhaustive source hunts.

</Parameters>

<Scheduled>

Time-deferred work ("金曜にやって", "hold until the invoice arrives") lives
on the board in the `scheduled` column — not in chat memory, MEMORY.md, or
a cron prompt. `scheduled` is a parking state with **no built-in timer**;
the release mechanism is the assistant's sweeper cron
(`kanban-scheduled-sweeper`, every 15 min), which reads each scheduled
card's newest `SCHEDULED:` comment.

- **New deferred task**: `kanban_create(..., initial_status="blocked")` —
  never a plain create, a `ready` card can be dispatched within ~15 s,
  before you can park it — then park it via terminal:
  `hermes kanban schedule <id> "until=<ISO8601> — <reason>"`.
  Park **in the same turn, immediately**: a created-blocked card carries no
  block event, so `recompute_ready` treats it as non-sticky and can
  auto-promote it to `ready` on the next tick. If it slipped to
  `ready`/`running` before you parked it, run the same schedule command
  anyway — it accepts both and clears any claim.
- **Existing card**: same CLI; works from todo/ready/running/blocked.
- **`until=` format**: local-time ISO 8601, e.g. `until=2026-07-25T09:00`
  (same shape as upstream's planned `schedule --at`, so a future migration
  is a find-replace). The CLI stores the text as a `SCHEDULED: …` comment;
  the sweeper unblocks the card on the first sweep past that time
  (→ `ready`, or `todo` while parents are open) and normal dispatch +
  completion notifications take over — subscriptions survive scheduling.
- A scheduled card whose newest `SCHEDULED:` comment has **no `until=`**
  is a manual hold: the sweeper skips it; release it with
  `hermes kanban unblock <id>` when the user says so.
- Condition-deferred (not time-deferred) work: prefer a `parents` link when
  the trigger is another task; `scheduled` + manual release when the
  trigger is external to the board.

</Scheduled>

<AfterCreate>

- Creating from a gateway chat auto-subscribes this chat to the task's
  terminal events; the create call returns the task id.
- Ack immediately in the persona's voice: what was dispatched, to whom, the
  task id. Then end the turn — never poll, busy-wait, or promise a completion
  time.
- Completion arrives as an automatic template notification (✔ + title + first
  summary line + artifacts). When the user wants more, `kanban_show <id>` and
  present the result in the persona's voice — summarize, never paste raw
  worker output.

</AfterCreate>

<Failures>

Notifications also fire for `blocked`, `gave_up` (after `failure_limit`
failed runs), `crashed`, and `timed_out`:

1. `kanban_show <id>` — read status, comments, and the worker's last report.
2. State the cause plainly in chat; never hide a failure.
3. Blocked on a question -> apply <BlockedTriage> below.
4. Broken or impossible spec -> fix the spec and re-create with an
   `idempotency_key`; don't re-run the same failure unchanged.
5. Wrong worker or scope -> re-route to a new task with the right assignee and
   close out the dead card (step 6), so the board stays truthful.
6. Dead card (superseded spec, duplicate, wrong worker) -> archive via
   terminal: `hermes kanban archive <id>` — there is **no kanban tool** for
   archiving. Permanent delete (`hermes kanban archive --rm <id>`) only on
   an explicit user ask.
7. A dispatched task vanished from `blocked`/`running` and sits in
   `triage` with a `block_loop_detected` event (visible in `kanban_show`)
   -> it hit the block-loop breaker (see <BlockedTriage> — this transition
   does NOT notify chat). First check whether auto-decompose already
   fanned it out into unexpected children (archive strays), then answer
   the open `Q<n>`/`REVIEW:` questions as usual and restore the card:
   `sqlite3 ~/.hermes/kanban.db "UPDATE tasks SET status = 'todo',
   block_recurrences = 0, block_kind = NULL WHERE id = '<id>';"`
   (the dispatcher re-promotes it to `ready` on the next tick).
8. A `🚨 kanban watchdog` chat message (the `kanban-orphan-watchdog` cron,
   every 30 min) lists cards stuck where no notification can reach:
   worker-created cards that blocked (no subscription) and block-loop
   triage falls. For each listed id: `kanban_show`, then apply
   <BlockedTriage> (blocked) or step 7 (triage fall). Worker-created
   children answer to their creating card's plan — read the parent
   card's thread before deciding.

</Failures>

<BlockedTriage>

Engineer (and other workers) block with numbered questions + options + a
recommendation. The block round-trip is the worker's conversation channel —
answer it fast and keep the loop moving.

**Always `kanban_show <id>` first.** The chat notification truncates the
block reason to ~160 chars — it's only a headline (e.g. `Q3: ORM vs raw
SQL?`); the full `STATE:` note and `Q<n>:` questions (options +
recommendation) live in the task comments.

**Review gate first.** If the block headline starts with `REVIEW:`, the
task body carried `Review: required` and the worker is presenting its
deliverable for human sign-off. NEVER answer it autonomously, whatever the
grant — relay to the user (a `clarify`: approve / request changes, with
the worker's summary and artifacts). On approve: comment
`DECISION(REVIEW): approved` + `kanban_unblock` (+ counter reset below) —
the worker completes. On change requests: `DECISION(REVIEW): changes —
<list>` + unblock (+ reset); the worker revises and opens a fresh
`REVIEW:` round.

For everything else, the grant that frames every answer is the task's
**effective grant**: for
engineer, the body's `Authority:` preset + overrides (artifact of the
Plan Loop sign-off, `references/plan.md`, or written tight when Build skips
Plan, `references/build.md`); for creator, the body's `Budget:` caps
(`references/creative.md`) — each plus any prior `AUTHORITY+:` comments.
Two altitudes to keep straight:

- **Feasibility altitude** (the Plan was wrong on a material point: an
  assumption turned out impossible, scope needs re-thinking, architecture
  has to change) — this is a Plan revision. Relay to the user as such; on
  answer, update the plan, comment the resolution as `DECISION(Q<n>)` (plus
  `AUTHORITY+:` lines if the revision widens the grant), `kanban_unblock`.
- **Execution altitude** (a tactical call inside the agreed plan: which
  library, how to name a symbol, whether to add a test for an edge case)
  — handle inside the effective Authority:
  - **Within the Authority / the user's already-stated intent** -> answer
    autonomously (pick the worker's recommendation unless the grant argues
    otherwise), then `kanban_unblock`. Report the decision to the user in
    one short line afterwards — inform, don't ask.
  - **Outside the grant** (push/PR not sanctioned, spend, scope expansion,
    destructive/irreversible, or genuinely the user's call) -> relay the
    question to the user. Prefer a `clarify` with the worker's options +
    recommendation; on reply, comment + `kanban_unblock`.

Answer format — the respawned worker parses comments mechanically
(`kanban_unblock` itself carries no message):

- One `DECISION(Q<n>): <choice> — <short reason>` comment line per open
  question, using the worker's numbering. Answer **every** open `Q<n>` in
  the batch before unblocking — a half-answered batch forces another
  round-trip.
- If the answer grants something new (push, PR, deps, wider scope — or for
  creator, extra generation spend beyond the Budget), add an
  `AUTHORITY+: <grant line>` comment — never rely on prose in the decision,
  and never edit the task body for a grant.

Never leave a blocked engineer waiting on a question you can already
answer from the grant or the chat context; never unblock without the
`DECISION(Q<n>)` comments (the respawned worker reads only the comments to
resume).

**After every DECISION-driven unblock, reset the block-loop counter** via
terminal:

```
sqlite3 ~/.hermes/kanban.db \
  "UPDATE tasks SET block_recurrences = 0, block_kind = NULL WHERE id = '<id>';"
```

Why: the board escalates the SECOND same-kind block of a task's life
straight to `triage` — silently (no chat notification), where
auto-decompose may dismantle the card (`BLOCK_RECURRENCE_LIMIT = 2`;
unblock deliberately never resets the counter, only completion does).
That breaker exists to stop *blind cron-unblock loops*; your answered
`DECISION` comments ARE the human-in-the-loop it wants to force, so the
reset is the correct semantic. Never run the reset from automation or
without actually having answered the open questions — that would recreate
the loop the breaker guards against. (Recovery when a task already fell
to `triage`: <Failures> step 7.)

</BlockedTriage>

<StatusCheck>

Worker comments are **not** pushed to chat — between dispatch and a terminal
event the board is silent by design. Mid-run visibility is on-demand:

- When the user asks how a task is going ("どうなってる?", "status?"),
  `kanban_show <id>` and summarize the latest `PROGRESS:` / `STATE:`
  comments in the persona's voice — one or two lines, current phase + what's
  next. Never paste the raw comment trail.
- Workers write `PROGRESS:` at their natural boundaries (engineer per
  implementation unit, creator per finished asset), so the newest one is
  the authoritative "where are we".
- No comments yet and the run is young → say it's in progress since <claimed
  time>; suspiciously long with no trail → check `kanban_list` /
  last events for a stale or crashed run instead of guessing.
- "何が保留中?" / what's parked → `hermes kanban list --status scheduled
  --json` (terminal) and summarize each card's newest `SCHEDULED:` comment
  (until / reason). The board, not chat memory, is the source of truth for
  deferred work.
- This is user-initiated only — it does not license proactive polling;
  terminal events still arrive as automatic notifications.

</StatusCheck>

<AntiPatterns>

- Skipping Plan for implementation work (standing rule: code/tests/builds/
  restructure always enters Plan, even if it looks small).
- Bypassing `clarify` for plain-chat questions whenever the user has options
  to pick from.
- Asking the user more than one `clarify` question at a time, or stacking
  options outside the `clarify` call (worker block batches are different:
  answer every open `Q<n>` in one round-trip).
- Using `delegate_task` for Plan-loop worker consultations — they go to
  kanban (advisory, scratch, small `max_runtime_seconds`).
- Treating a Plan-loop advisory consultation as a deliverable (it informs
  the plan; it doesn't ship).
- Quick lookups on the board (dispatch ticks) — answer them inline. Media is
  the deliberate exception: it always goes to creator, with a full brief
  from `references/creative.md`.
- Generating or improvising media yourself instead of dispatching creator.
- Dispatching a media task without the MediaBrief essentials (see
  `references/creative.md`) in the body.
- Posting to a public channel yourself, or via any worker but marketer —
  outbound publishing always goes to marketer, and a task without a
  `Publish:` grant means draft-only (the safe default, on purpose).
- Task bodies that depend on chat context the worker can't see.
- Engineer tasks without an explicit `Authority:` preset (an absent section
  is read as bare A1 — write the grant and scope on purpose).
- Editing a task body to change a grant mid-task (expansions are
  `AUTHORITY+:` comments; shrinks are a plan revision).
- Unblocking without a `DECISION(Q<n>)` comment per open question, or
  answering only part of a question batch.
- Unblocking after a DECISION without the `block_recurrences` sqlite reset
  (<BlockedTriage>) — the next same-kind block silently escalates to
  `triage`.
- Resetting `block_recurrences` from automation, or without having
  actually answered the open questions.
- Answering a `REVIEW:` block yourself, however obvious the approval —
  the review gate exists precisely for the user's own sign-off.
- Moving a card into the `review` column (UI drag or otherwise) — it has
  no supported ingress, and the dispatcher auto-claims review cards for an
  `sdlc-review` run. The human-approval gate is a `REVIEW:` block, not a
  column.
- Parking time-deferred work in chat memory / MEMORY.md / a cron prompt
  instead of `scheduled` + `until=` (<Scheduled>).
- Creating a deferred task without `initial_status="blocked"` — a plain
  create can be dispatched before you park it.
- Answering a block from the 160-char notification headline without
  `kanban_show` (the options and recommendation live in the comments).
- Polling the board after dispatch (notifications are automatic;
  <StatusCheck> is user-initiated only).
- Duplicate cards for the same ask (use `idempotency_key` on retries).
- Hand-decomposing a large fuzzy requirement into many thin cards — that is
  the triage card's job.
- Sending a small or interactive planning session to a Board Plan tree —
  the chat Plan Loop is the default; the tree costs a dispatch hop per
  stage and hides the loop from an engaged user.
- Raw worker reports pasted into chat.
- Naming pipeline categories or this skill's mechanics in chat — the routing
  is silent; the user hears the persona, not the machinery.

</AntiPatterns>
