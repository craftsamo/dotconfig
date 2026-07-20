---
name: orchestration
description: >-
  Front-door playbook shared by both profiles (assistant on Telegram, default
  on the CLI) — walk every request through a 7-step pipeline: Classify
  (Projects / Personal / cross-cutting / neither), Locate (workspace group +
  repo), Approach (Plan / Build / Search / Research / Creative / Inline —
  exclusive), then for Plan only: Decompose the goal with the `approach`
  skill, Register the steps in the session `todo`, run the Plan Loop with
  the user (worker consultations via kanban, advisory). On sign-off,
  Dispatch via the existing topology (single / parents / triage card) with
  self-contained task specs (engineer tasks carry an Authority grant; media
  tasks carry a MediaBrief), ack with the task id, answer engineer
  questions within the granted authority autonomously, and recover from
  blocked/gave_up/crashed/timed_out events. Auto-loaded into each Telegram
  topic session via the dm_topics skill binding; load it via skill_view
  before non-trivial work elsewhere. Prefer the `clarify` tool over
  plain-chat questions whenever options exist. Each approach has its own
  reference under `references/<approach>.md` — load the matching one after
  Step 3.
version: 3.1.0
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

Classify → Locate → Approach → (if Plan: Decompose → Register → Plan Loop,
detailed in `references/plan.md`) → Dispatch. At every user-facing choice,
prefer the `clarify` tool over plain-chat questions. When dispatching,
produce board tasks the dispatcher can run unattended: right worker,
self-contained spec, cheapest topology that fits, clean ack, sane failure
recovery.

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

Mixed pipelines flow searcher -> researcher -> engineer, with creator as a
side stage for assets. Workers can fan out themselves (`kanban_create` +
`parents`): e.g. engineer dispatches a searcher lookup or a creator asset
mid-implementation — don't pre-decompose what the worker can request itself.

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
  Authority: <engineer tasks only — the pre-approval grant, carried over
             from the Plan Loop sign-off (or written tight when Build skips
             Plan — see references/build.md). Explicitly state what is
             allowed without asking: commit (usually yes), push, PR,
             dependency changes, scope boundaries. Anything not granted
             here forces the engineer into a block round-trip, so grant
             what the user has already sanctioned and no more.>
```

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
section, which itself is the artifact of the Plan Loop sign-off
(`references/plan.md`) or written tight when Build skips Plan
(`references/build.md`). Two altitudes to keep straight:

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
  the deliberate exception: it always goes to creator, with a full brief
  from `references/creative.md`.
- Generating or improvising media yourself instead of dispatching creator.
- Dispatching a media task without the MediaBrief essentials (see
  `references/creative.md`) in the body.
- Task bodies that depend on chat context the worker can't see.
- Polling the board after dispatch (notifications are automatic).
- Duplicate cards for the same ask (use `idempotency_key` on retries).
- Hand-decomposing a large fuzzy requirement into many thin cards — that is
  the triage card's job.
- Raw worker reports pasted into chat.
- Naming pipeline categories or this skill's mechanics in chat — the routing
  is silent; the user hears the persona, not the machinery.

</AntiPatterns>
