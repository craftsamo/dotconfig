---
name: assistant-orchestration
description: Assistant's orchestration playbook — silently triage every request along two axes (can the user wait; does it need a worker's tools) into inline vs kanban, then dispatch well: pick the topology (single task / parents chain / triage card), write self-contained task specs workers can run without chat context (engineer tasks carry an Authority grant), set workspace and dispatch params, ack with the task id, answer engineer questions within the granted authority autonomously, and recover from blocked/gave_up/crashed/timed_out events. Auto-loaded into each Telegram topic session via the dm_topics skill binding; load it via skill_view before non-trivial work elsewhere.
version: 2.1.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [orchestration, triage, routing, kanban, delegation, task-spec, workers]
    category: orchestration
    related_skills: []
---

<Goal>

Route every request to the right lane — answer inline, or dispatch to the
kanban workers — and when dispatching, produce board tasks the dispatcher can
run unattended: right worker, self-contained spec, cheapest topology that
fits, clean ack, and sane failure recovery.

</Goal>

<Scope>
<UseWhen>

- Always in a Telegram topic session: this skill is auto-loaded at session
  start (dm_topics skill binding) — apply <Triage> to every request.
- Elsewhere (CLI session, other platforms): load it before any non-trivial
  work.
- A kanban notification (done / blocked / gave up / crashed / timed out)
  needs follow-up: expanding results or re-dispatching.

</UseWhen>
<DoNotUseWhen>

- Never skip <Triage>; the sections after it apply only to requests that
  route to kanban.

</DoNotUseWhen>
</Scope>

<Triage>

Coordinate more than you implement. Classify every request silently (never
name the category in chat) along two axes, then route:

1. Wait — can you deliver well while the user waits: a minute or two, a few
   tool calls, your own toolset?
2. Shape — does it need a worker's tools (deep retrieval, heavy analysis,
   code execution), isolation, durability, or an audit trail?

| Request | Route |
| --- | --- |
| conversation / emotion / opinion | inline, no tools; memory tool as needed |
| single quick lookup (one URL / fact / file) | inline, light tools |
| workspace data ops (people / household-budget / projects) | inline via the workspace skills |
| single quick asset (one image / short clip / voice line) | inline toolsets |
| batch, long-render, or multi-asset media production | kanban: creator |
| recurring request ("every morning ...") | inline: register a cron job |
| broad or current-info retrieval | kanban: searcher |
| deep multi-hop retrieval (exhaustive source hunt) | kanban: searcher + `skills: ["deep-retrieval"]`, `goal_mode: true` |
| analysis / synthesis / comparison / reports | kanban: researcher |
| code / repos / tests / builds | kanban: engineer |
| multi-stage (search -> analyze -> build) | kanban: see <Topology> |
| ambiguous, or destructive / irreversible | ask exactly one clarifying question, then re-classify |

Exception — delegate_task (in-turn subagents): only for medium parallel
lookups the user is actively waiting on; anything heavier goes to kanban.
Dispatch ticks run ~every 15s, so never send quick jobs to the board — a
30-second job still takes noticeably longer via kanban.

</Triage>

<Workers>

Keep in sync with each worker's `profile.yaml` description:

| Assignee | Sweet spot | Tools |
| --- | --- | --- |
| searcher | breadth-first retrieval: web/X search, links, latest/current info; deep multi-hop via the `deep-retrieval` skill + `goal_mode` | web, x_search |
| researcher | depth: analysis, synthesis, comparison, evaluation, reports | file, web |
| engineer | implementation: drives OpenCode, code changes, debugging, tests, builds, PRs; confirms material decisions via block round-trips | terminal (hermes-cli) |
| creator | media production: batch/long-render/multi-asset image, video, GIF, voice; delivers via kanban_attach | media gen chains + terminal |

Mixed pipelines flow searcher -> researcher -> engineer, with creator as a
side stage for assets. Workers can fan out themselves (`kanban_create` +
`parents`): e.g. engineer dispatches a searcher lookup or a creator asset
mid-implementation — don't pre-decompose what the worker can request itself.

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
  Authority: <engineer tasks only — the pre-approval grant. Explicitly state
             what is allowed without asking: commit (usually yes), push,
             PR, dependency changes, scope boundaries. Anything not granted
             here forces the engineer into a block round-trip, so grant
             what the user has already sanctioned and no more.>
```

- Write the body in the language you want the deliverable in.
- Never reference "the conversation above", screenshots, or memories the
  worker lacks; paste or link what matters.
- Scratch workspaces are deleted on completion: require findings in the final
  message / completion summary, never only in files.

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

</Topology>

<Parameters>

- `assignee` is required — tasks without one never dispatch.
- `workspace_kind`: `scratch` (fresh tmp, deleted on completion) is right for
  searcher/researcher. Coder work on a repo: `worktree` + absolute
  `workspace_path`, or `project: <slug>` for a deterministic project branch.
  `dir` (shared directory, absolute path, no isolation) is rare.
- `priority` (int): dispatcher tiebreaker among ready tasks; higher = sooner.
- `idempotency_key`: set when retrying or re-dispatching — a duplicate card
  returns the existing task id instead of forking work.
- `max_runtime_seconds`: cap runaway tasks (exceeded -> SIGTERM + `timed_out`).
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
answer it fast and keep the loop moving:

- **Within the task's Authority / the user's already-stated intent** ->
  answer autonomously: `kanban_comment` with the decision (pick the
  recommendation unless the thread argues otherwise), then `kanban_unblock`.
  Report the decision to the user in one short line afterwards — inform,
  don't ask.
- **Outside the grant** (push/PR not sanctioned, spend, scope expansion,
  destructive/irreversible, or genuinely the user's call) -> relay the
  question to the user verbatim-but-compact with the options and the
  worker's recommendation; on reply, `kanban_comment` the answer +
  `kanban_unblock`.
- Never leave a blocked engineer waiting on a question you can already
  answer from the grant or the chat context; never silently unblock without
  a comment (the respawned worker reads the comments to resume).

</BlockedTriage>

<AntiPatterns>

- Quick lookups on the board (dispatch ticks) — answer them inline.
- Task bodies that depend on chat context the worker can't see.
- Polling the board after dispatch (notifications are automatic).
- Duplicate cards for the same ask (use `idempotency_key` on retries).
- Hand-decomposing a large fuzzy requirement into many thin cards — that is
  the triage card's job.
- Raw worker reports pasted into chat.
- Naming triage categories or this skill's mechanics in chat — the routing is
  silent; the user hears the persona, not the machinery.

</AntiPatterns>
