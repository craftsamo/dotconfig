---
name: kanban-dispatch
description: Assistant's kanban dispatch playbook — pick the topology (single task / parents chain / triage card), write self-contained task specs workers can run without chat context, set workspace and dispatch params, ack with the task id, and recover from blocked/gave_up/crashed/timed_out events. The inline-vs-kanban routing decision lives in the operating contract; this skill is the "dispatch well" half.
version: 1.0.0
author: CraftSamo
metadata:
  hermes:
    tags: [kanban, orchestration, delegation, task-spec, triage, workers]
    category: orchestration
    related_skills: []
---

<Goal>

Turn a routed-to-kanban request into board tasks the dispatcher can run
unattended: right worker, self-contained spec, cheapest topology that fits,
clean ack, and sane failure recovery.

</Goal>

<Scope>
<UseWhen>

- The operating contract classified a request as kanban work (heavy retrieval,
  analysis/synthesis, code, or multi-stage) and you are about to create tasks.
- A kanban notification (done / blocked / gave up / crashed / timed out) needs
  follow-up: expanding results or re-dispatching.

</UseWhen>

<DoNotUseWhen>

- Inline work: conversation, quick lookups, workspace skills, media
  generation, cron registration.

</DoNotUseWhen>
</Scope>

<Workers>

Keep in sync with each worker's `profile.yaml` description:

| Assignee | Sweet spot | Tools |
| --- | --- | --- |
| searcher | breadth-first retrieval: web/X search, links, latest/current info | web, x_search |
| researcher | depth: analysis, synthesis, comparison, evaluation, reports | file, web |
| coder | implementation: code changes, debugging, tests, builds, PRs | terminal (hermes-cli) |

Mixed pipelines flow searcher -> researcher -> coder.

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
  profile when the task depends on it.
- `goal_mode: true` (+ `goal_max_turns`): open-ended cards where one shot
  rarely finishes — a judge loops the worker until done or budget exhausted.

</Parameters>

<AfterCreate>

- Creating from a gateway chat auto-subscribes this chat to the task's
  terminal events; the create call returns the task id.
- Ack immediately in 雪音's voice: what was dispatched, to whom, the task id.
  Then end the turn — never poll, busy-wait, or promise a completion time.
- Completion arrives as an automatic template notification (✔ + title + first
  summary line + artifacts). When the user wants more, `kanban_show <id>` and
  present the result in 雪音's voice — summarize, never paste raw worker output.

</AfterCreate>

<Failures>

Notifications also fire for `blocked`, `gave_up` (after `failure_limit`
failed runs), `crashed`, and `timed_out`:

1. `kanban_show <id>` — read status, comments, and the worker's last report.
2. State the cause plainly in chat; never hide a failure.
3. Blocked on a question -> supply the answer via `kanban_comment`, then
   `kanban_unblock`. Broken or impossible spec -> fix the spec and re-create
   with an `idempotency_key`; don't re-run the same failure unchanged.
4. Wrong worker or scope -> re-route to a new task with the right assignee and
   close out the dead card, so the board stays truthful.

</Failures>

<AntiPatterns>

- Quick lookups on the board — dispatch ticks are ~60s, so a 30-second job
  takes minutes via kanban. Answer inline instead.
- Task bodies that depend on chat context the worker can't see.
- Polling the board after dispatch (notifications are automatic).
- Duplicate cards for the same ask (use `idempotency_key` on retries).
- Hand-decomposing a large fuzzy requirement into many thin cards — that is
  the triage card's job.
- Raw worker reports pasted into chat.

</AntiPatterns>
