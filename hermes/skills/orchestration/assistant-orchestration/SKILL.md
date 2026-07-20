---
name: assistant-orchestration
description: >-
  Orchestration playbook for the front-door profiles (assistant on Telegram,
  default on the CLI) — walk every request through a 7-step pipeline:
  Classify (Projects / Personal / cross-cutting / neither), Locate (workspace
  group + repo), Approach (Plan / Build / Search / Research / Creative /
  Inline — exclusive), then for Plan only: Decompose the goal with the
  `approach` skill, Register the steps in the session `todo`, run the Plan
  Loop with the user (worker consultations via kanban, advisory). On
  sign-off, Dispatch via the existing topology (single / parents / triage
  card) with self-contained task specs (engineer tasks carry an Authority
  grant; media tasks carry a MediaBrief), ack with the task id, answer
  engineer questions within the granted authority autonomously, and recover
  from blocked/gave_up/crashed/timed_out events. Auto-loaded into each
  Telegram topic session via the dm_topics skill binding; load it via
  skill_view before non-trivial work elsewhere. Prefer the `clarify` tool
  over plain-chat questions whenever options exist.
version: 3.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [orchestration, pipeline, classify, locate, approach, plan, dispatch, triage, routing, kanban, delegation, task-spec, workers]
    category: orchestration
    related_skills: [plan/approach]
---

<Goal>

Walk every request through a 7-step pipeline and dispatch well at the end.

Classify → Locate → Approach → (if Plan: Decompose → Register → Plan Loop)
→ Dispatch. At every user-facing choice, prefer the `clarify` tool over
plain-chat questions. When dispatching, produce board tasks the dispatcher
can run unattended: right worker, self-contained spec, cheapest topology
that fits, clean ack, sane failure recovery.

</Goal>

<Scope>
<UseWhen>

- Always in a Telegram topic session: this skill is auto-loaded at session
  start (dm_topics skill binding) — apply <Pipeline> to every request.
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
- Step 6 Plan Loop iterations (approach pick, scope cut, sign-off gate)
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
                     │
                     ├─ Inline (no dispatch)            ┐
                     ├─ Build/Search/Research/Creative  ├─ done
                     └─ Plan                            │
                         Step 4  Decompose              │
                         Step 5  Register (todo)        │
                         Step 6  Plan Loop              │
                                                          ▼
Step 7  Dispatch   <Topology> → <Parameters> → <AfterCreate> → <Failures>
```

Classify and Locate are silent — never name the categories in chat unless
genuine ambiguity merits a `clarify`.

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

Pick **exactly one** entry mode — they are exclusive:

| Approach | Trigger | Next step |
| --- | --- | --- |
| **Plan** | Implementation work (code/tests/builds/restructure), **or** any request that's ambiguous / multi-stage / irreversible and would benefit from upfront alignment | Step 4 |
| **Build** | Well-specified implementation the user has already detailed (clear scope, known approach) — skip Plan and dispatch directly to engineer | Step 7 |
| **Search** | Retrieval: web/X search, links, latest info, single or shallow multi-hop | Step 7 |
| **Research** | Analysis / synthesis / comparison / evaluation / reports | Step 7 |
| **Creative** | Any media production — image / video / GIF / voice (always creator, after collecting the <MediaBrief>) | Step 7 |
| **Inline** | Conversation; single quick lookup; workspace data ops via the workspace skills (people/household-budget/projects); recurring request → register a cron job | (no dispatch) |

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

<Step4Decompose>

Entered only when Approach=Plan. Load and follow the `approach` skill
(`skill_view approach`) — its principles apply directly:

1. **Investigate before asserting** — read the relevant repo, docs, history,
   workspace skill output before drafting.
2. **Don't assume intent** — mirror the real goal back; surface ambiguity.
3. **Co-design top-down, one decision at a time** — abstract → concrete:
   goal → shape → specifics. Each step: options + tradeoffs + a recommended
   default; the user picks.
4. **Align on a plan** — synthesize decisions into a concise plan; confirm
   before dispatch.

Reverse-engineer from the goal: what must be true at the end → what work
produces that → what steps each worker can own. Consult workers as needed
(Step 6 worker consultations) to ground the decomposition in reality.

</Step4Decompose>

<Step5Register>

Capture the decomposed steps in the **session `todo` tool** — it is
session-local (in-memory `TodoStore`), which matches the chat-only Plan
persistence model. One todo item per concrete step, status `pending`. Mark
`in_progress` when you start refining it in the Plan Loop, `completed` when
folded into the signed-off plan, `cancelled` if dropped.

The todo list is the shared scratch state between you and the user during
Plan Loop iterations — both of you can see what's settled and what's open.
On sign-off, the surviving items become the dispatch task specs (Step 7).

</Step5Register>

<Step6PlanLoop>

Iterate with the user until the plan is signed off. Each cycle:

1. Present the current plan shape (or delta) compactly.
2. Wherever a choice exists, fire a `clarify` with up to 4 options + your
   recommendation in the question text. **One question at a time.**
3. On the user's answer, update the `todo` list and the plan draft.
4. Repeat until the user signs off (or revises scope).

**Worker consultations during Plan** — when you need facts to make the plan
concrete, dispatch via kanban (not `delegate_task` — durability over
tempo). Mark them advisory so they don't get confused with deliverables:

- `workspace_kind: scratch`, small `max_runtime_seconds` (e.g. 600).
- Body opens with **"Advisory — inform the plan, don't ship."** and closes
  with what the plan needs from the result (a feasibility verdict, a
  landscape scan, a tradeoff matrix).
- Engineer at the **feasibility altitude** ("is this buildable, what's the
  shape, what's the risk, rough size") — not implementation altitude. The
  deliverable is a short assessment, not code.
- Searcher for landscape scans; researcher for synthesis / tradeoff
  matrices.
- Ack the user in chat when consultations are in flight; never poll. Worker
  completion notifications resume the Plan Loop where you left off.

**Sign-off gate** — one final `clarify` ("Plan looks like X, dispatch as
Y/Z/W — proceed?") before Step 7. The signed-off plan + the Authority
grant for engineer tasks become the artifact that crosses into dispatch.

**Session continuity** — the Plan lives in chat + the `todo` list only. If
the session compresses or resets, ask the user "what did we agree on?" and
rebuild from the todo state.

</Step6PlanLoop>

<Workers>

Keep in sync with each worker's `profile.yaml` description:

| Assignee | Sweet spot | Tools |
| --- | --- | --- |
| searcher | breadth-first retrieval: web/X search, links, latest/current info; deep multi-hop via the `deep-retrieval` skill + `goal_mode` | web, x_search |
| researcher | depth: analysis, synthesis, comparison, evaluation, reports | file, web |
| engineer | implementation: drives OpenCode, code changes, debugging, tests, builds, PRs; confirms material decisions via block round-trips | terminal (hermes-cli) |
| creator | ALL media production: image, video, GIF, voice assets, batch and single; delivers via kanban_attach | media gen chains + terminal |

Mixed pipelines flow searcher -> researcher -> engineer, with creator as a
side stage for assets. Workers can fan out themselves (`kanban_create` +
`parents`): e.g. engineer dispatches a searcher lookup or a creator asset
mid-implementation — don't pre-decompose what the worker can request itself.

During Plan Loop, workers can also be **consulted at advisory altitude**
(see <Step6PlanLoop>) — the same roster, but the deliverable is an
assessment, not the work product itself.

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
  Authority: <engineer tasks only — the pre-approval grant, carried over
             from the Plan Loop sign-off. Explicitly state what is allowed
             without asking: commit (usually yes), push, PR, dependency
             changes, scope boundaries. Anything not granted here forces
             the engineer into a block round-trip, so grant what the user
             has already sanctioned and no more.>
```

- Write the body in the language you want the deliverable in.
- Never reference "the conversation above", screenshots, or memories the
  worker lacks; paste or link what matters.
- Scratch workspaces are deleted on completion: require findings in the
  final message / completion summary, never only in files.

</TaskSpec>

<MediaBrief>

You produce no media yourself — creator does. Your job is the brief: collect
what creator needs to generate right on the first pass, so it never has to
block on style questions or burn credits guessing. Gather (from the chat,
the user, and memory) before dispatching:

- Purpose & audience — what the asset is for, where it will be seen.
- Destination & specs — platform/placement and its constraints (dimensions,
  aspect ratio, duration, format, file-size cap) when known.
- Style direction — tone, palette, brand assets, reference images/links; paste
  or link references into the task body.
- Quantity & variants — how many, which sizes/crops.
- Deadline / priority.

Ask the user at most one compact round of questions for missing essentials
(a `clarify` if options exist); fill sensible defaults yourself and say so.
Put all of it in the task body (Inputs/Constraints) — creator cannot see
this chat. Small single assets go to creator too; ack with the task id and
deliver on the completion notification.

</MediaBrief>

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

Coming out of a Plan Loop (Step 6), the topology choice is usually obvious
from the signed-off plan — the plan's shape dictates single / parents /
triage.

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
   close out the dead card, so the board stays truthful.

</Failures>

<BlockedTriage>

Engineer (and other workers) block with one question + options + a
recommendation. The block round-trip is the worker's conversation channel —
answer it fast and keep the loop moving.

The grant that frames every answer comes from the task's **Authority**
section, which itself is the artifact of the Plan Loop sign-off (Step 6).
Two altitudes to keep straight:

- **Feasibility altitude** (the Plan was wrong on a material point: an
  assumption turned out impossible, scope needs re-thinking, architecture
  has to change) — this is a Plan revision. Relay to the user as such; on
  answer, update the plan + Authority, `kanban_comment` the resolution,
  `kanban_unblock`.
- **Execution altitude** (a tactical call inside the agreed plan: which
  library, how to name a symbol, whether to add a test for an edge case)
  — handle inside the Authority grant:
  - **Within the Authority / the user's already-stated intent** -> answer
    autonomously: `kanban_comment` with the decision (pick the worker's
    recommendation unless the grant argues otherwise), then
    `kanban_unblock`. Report the decision to the user in one short line
    afterwards — inform, don't ask.
  - **Outside the grant** (push/PR not sanctioned, spend, scope expansion,
    destructive/irreversible, or genuinely the user's call) -> relay the
    question to the user. Prefer a `clarify` with the worker's options +
    recommendation; on reply, `kanban_comment` the answer +
    `kanban_unblock`.

Never leave a blocked engineer waiting on a question you can already
answer from the grant or the chat context; never silently unblock without
a comment (the respawned worker reads the comments to resume).

</BlockedTriage>

<AntiPatterns>

- Skipping Plan for implementation work (standing rule: code/tests/builds/
  restructure always enters Plan, even if it looks small).
- Bypassing `clarify` for plain-chat questions whenever the user has options
  to pick from.
- Asking more than one question at a time, or stacking options outside the
  `clarify` call.
- Using `delegate_task` for Plan-loop worker consultations — they go to
  kanban (advisory, scratch, small `max_runtime_seconds`).
- Treating a Plan-loop advisory consultation as a deliverable (it informs
  the plan; it doesn't ship).
- Quick lookups on the board (dispatch ticks) — answer them inline. Media is
  the deliberate exception: it always goes to creator, with a full brief.
- Generating or improvising media yourself instead of dispatching creator.
- Dispatching a media task without the <MediaBrief> essentials in the body.
- Task bodies that depend on chat context the worker can't see.
- Polling the board after dispatch (notifications are automatic).
- Duplicate cards for the same ask (use `idempotency_key` on retries).
- Hand-decomposing a large fuzzy requirement into many thin cards — that is
  the triage card's job.
- Raw worker reports pasted into chat.
- Naming pipeline categories or this skill's mechanics in chat — the routing
  is silent; the user hears the persona, not the machinery.

</AntiPatterns>
