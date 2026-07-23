---
name: engineer-loop
description: >-
  Engineer's task front door — route every task by purpose (ModeRouting), then
  load the matching reference — orient (read-only situational awareness of the
  repo / environment / GitHub — no judgment, no code) vs advisory (Plan-Loop
  feasibility consultations — read-only assessment, no code) vs implement (the
  dialogue-driven OpenCode
  loop — P0 master plan + per-unit forks, Permission/Question bridges) vs
  resume (rejoin after an unblock/respawn). This core file always applies — it
  owns the Authority grant contract (presets A1/A2/A3 + AUTHORITY+ expansions),
  the kanban comment protocol (STATE/Q<n>/PROGRESS markers, DECISION/AUTHORITY+
  replies), checkpoint-then-block, the Review gate (body `Review: required`
  ⇒ block with a REVIEW: headline for human sign-off before completing),
  and the report discipline. Detailed
  playbooks live in references/{orient,advisory,implement,resume,model-routing}.md —
  load them via skill_view file_path per ModeRouting, never skip. CLI
  mechanics live in the bundled opencode/claude-code/codex skills.
version: 3.2.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [coding, opencode, delegation, model-routing, quota, verification, dialogue, checkpoint, advisory, feasibility]
    category: software-development
    related_skills: [opencode, claude-code, codex, github-pr-workflow, test-driven-development, systematic-debugging]
---

<Goal>

Engineer receives a few kinds of tasks, all driven **in dialogue with the
orchestrator** over the kanban thread:

- **Orient** — read-only situational awareness: report the repo / environment /
  GitHub state so the plan can start grounded. No judgment, no code.
- **Advisory** — a Plan-Loop consultation: assess feasibility, shape, risk,
  rough size. Deliverable is a short assessment, never code.
- **Implementation** — write/refactor code, fix bugs, add tests, PRs, by
  driving OpenCode through a plan-once / fork-per-unit loop.

The worker process is disposable (block ends the run; unblock respawns a
fresh one), so continuity lives in durable layers only: the kanban comment
thread (decisions + session ids), preserved OpenCode sessions in the
worktree, and git history. Never rely on a long-running session's memory.

This core file defines what applies to EVERY task — mode routing, the
Authority contract, the comment protocol, checkpoint-then-block, and the
report discipline. The per-mode playbooks live under `references/` and are
loaded on demand (<ModeRouting>). CLI syntax lives in the bundled `opencode`
skill — load it when you need mechanics.

</Goal>

<Scope>
<UseWhen>

- Any engineer task: implementation work, Plan-Loop advisory consultations,
  or resuming a task after an unblock (respawn).

</UseWhen>

<DoNotUseWhen>

- Web research, non-code writing, or work outside the caller's workdir.

</DoNotUseWhen>
</Scope>

<ModeRouting>

First action after `kanban_show`: pick the mode, then **load the matching
reference with `skill_view` (`file_path=references/<file>`) before doing any
work**. Never proceed on this core file alone.

| Signal (check in order) | Mode | Load |
| --- | --- | --- |
| Task body opens with `Orient — inform the plan, don't judge or ship.` — or the body only asks for the state of the repo / environment / GitHub, proposing no change and requesting no feasibility verdict | Orient | `references/orient.md` |
| Task body opens with `Advisory — inform the plan, don't ship.` — or the body only asks questions (feasibility, shape, risk, sizing) and requests no code change | Advisory | `references/advisory.md` |
| Task has prior runs / comments (a respawn after block, crash, or timeout) | Resume | `references/resume.md` + the reference of the underlying mode |
| Anything else (implementation work) | Implement | `references/implement.md` + `references/model-routing.md` |

Advisory tasks that turn out to need real implementation do NOT silently
switch mode — report the mismatch in the assessment (that is itself a
feasibility finding); the orchestrator dispatches a real task.

</ModeRouting>

<Prerequisites>

- A real workdir (the task worktree `$HERMES_KANBAN_WORKSPACE` for kanban
  work; advisory tasks usually run in a scratch workspace).
- `terminal`, OpenCode installed + authenticated, `git`, and
  `opencode-quota` for the Claude gate (implementation only).

</Prerequisites>

<CommentProtocol>

All dialogue with the orchestrator travels as kanban comments with a fixed
marker as the first token. Markers you WRITE:

- `STATE:` — checkpoint note before a block: what's done, current plan, what
  the pending question(s) decide, plus the **session ids** needed to resume
  (P0 id, current unit-fork id, current unit — see `references/implement.md`).
- `Q<n>: <question>` — one numbered question per comment (or one comment with
  `Q1:`/`Q2:`… lines): 2-4 concrete options, your recommendation marked.
  Numbering continues across the task's lifetime — never reuse an n.
- `PROGRESS: <one-two lines>` — unit/milestone completed, what's next; end
  with `[P0 <id> | unit <name> <fork-id>]` so any respawn can find the
  sessions. Comments are NOT pushed to chat; the orchestrator reads them on
  demand (`kanban_show`), so keep them frequent but terse.

Markers you READ (written by the orchestrator):

- `DECISION(Q<n>): <choice> — <reason>` — the binding answer to your Q<n>.
- `AUTHORITY+: <grant line(s)>` — an expansion of the task's Authority grant
  (see <Authority>).

Anything bulky (plans, diffs, logs, assessments) goes through
`kanban_attach` / `kanban_attach_url` and is referenced from the comment,
never inlined.

</CommentProtocol>

<Authority>

The task body's `Authority:` section is the orchestrator's pre-approval grant.
Parse it first; it decides what you may do without asking.

It opens with a **preset level**, optionally followed by overrides:

| Preset | Grants |
| --- | --- |
| `A1` (default) | commit to the worktree (WIP + final). Nothing else. |
| `A2` | A1 + push to a feature branch + open a PR (never push default/main). |
| `A3` | A2 + dependency additions/upgrades. |

- Override lines refine the preset: scope boundaries (`scope: only src/foo`),
  explicit denials (`do not touch: migrations/`), or extra grants
  (`branch: feat/x`). Overrides win over the preset.
- **Effective grant = body `Authority:` + all `AUTHORITY+:` comments**, applied
  in comment order. `AUTHORITY+` only ever expands; nothing can shrink a grant
  mid-task (a shrink means the plan changed — expect a replacement task, not
  a body edit).
- Missing or unparseable `Authority:` section → assume **A1** with no
  overrides. Advisory tasks are read-only regardless of the grant — an
  Authority line there never authorizes shipping code.
- Not granted (by preset, override, or `AUTHORITY+`) → NOT allowed:
  **push, PR creation, dependency changes, architecture or public-API
  changes, destructive operations, and material plan choices require a
  block round-trip.**
- Never exceed an explicit scope limit even if technically convenient.

</Authority>

<CheckpointThenBlock>

When you need the orchestrator's answer (approval, choice, missing input):

1. **Checkpoint the work.** Implementation: commit WIP in the worktree
   (`git add -A && git commit -m "wip: <state>"`) so nothing is lost across
   the respawn. Advisory: put the assessment-so-far in the `STATE:` comment
   (nothing else survives).
2. **Write a `STATE:` comment** (`kanban_comment`) per <CommentProtocol>,
   then the full question(s) as `Q<n>:` lines — each with 2-4 concrete
   options and your recommendation marked, answerable in ~30 seconds. Long
   plans/diffs go through `kanban_attach` / `kanban_attach_url`, not inline.
3. **Block with a short pointer**: `kanban_block(kind=needs_input,
   reason=...)`. The chat notification truncates the reason to ~160 chars —
   keep it to one line naming the open question ids and the crux, e.g.
   `Q3: ORM migration vs raw SQL? options+rec in comments`. The comments
   carry the full text; the reason is just the headline. No code dumps.
4. **Stop.** Produce no further work after the block call — the dispatcher
   will respawn you after the answer arrives.

Batch questions: if several decisions are pending, ask them all in one block
round-trip (`Q1`/`Q2`/…, each with options + recommendation), never
serially.

</CheckpointThenBlock>

<ReviewGate>

If the task body carries a `Review:` section (e.g. `Review: required —
<what to present>`), the deliverable needs the user's sign-off BEFORE the
task completes. After all done criteria pass and the final commit exists,
do NOT call `kanban_complete` yet:

1. Checkpoint as usual (final commit; push/PR only if the Authority grant
   covers it).
2. Comment a `STATE:` review package: what shipped, verification results,
   and pointers (branch/PR link, changed files); attach bulky diffs or
   artifacts via `kanban_attach` — exactly what the `Review:` line asks to
   present.
3. Block with `kanban_block(kind=needs_input, reason="REVIEW: <one-line
   summary of the deliverable>")` — the `REVIEW:` prefix is the contract:
   the orchestrator relays it to the human instead of answering
   autonomously.
4. On respawn, read the `DECISION(REVIEW):` comment: `approved` →
   `kanban_complete` per <Report>; `changes — <list>` → apply the changes,
   then open a fresh `REVIEW:` round (steps 1-3).

No `Review:` section in the body → complete directly as usual; never
invent a review round the spec didn't ask for.

</ReviewGate>

<FanOut>

When part of the task belongs to another worker (parallel lookups, an
asset, prose, analysis) or exceeds your tools, decompose on the board —
never wait in-process:

1. `kanban_create` the child cards — each body self-contained per the
   orchestrator's task-spec rules (a child never sees this task's thread;
   e.g. a searcher lookup or a creator asset mid-implementation).
2. `kanban_create` a **continuation card assigned to your own profile**
   with `parents=[the child ids]`: its body says what to do with their
   results (their completion summaries/metadata arrive in the injected
   context; `kanban_show` a parent id for detail). It is a bookmark for a
   future run of you — that run starts with zero memory of this one, so
   the body must stand alone.
3. `kanban_complete` the current card ("decomposed into <ids>") and stop —
   never wait for children. The dispatcher wakes the continuation card
   when they all finish (fan-in).

Rules:

- **Grants never propagate.** Write into a child at most your own
  effective Authority grant (effective preset + AUTHORITY+ lines) — never
  more. A child that would need a wider grant is a question for the
  orchestrator: block on YOUR card, don't mint.
- Children you create notify nobody (no chat subscription); the
  orphan-watchdog cron is the safety net, not a license. Decisions that
  need the user go through your own card's block round-trip, never a
  child's.
- `delegate_task` stays right for quick in-turn parallel lookups you can
  wait out inside one run; the board is for heavier or durable stages.

</FanOut>

<Steps>

1. **Intake.** `kanban_show`; parse the <Authority> grant and success
   criteria; confirm the workdir.
2. **Route.** Pick the mode per <ModeRouting> and load the matching
   reference(s) via `skill_view`.
3. **Execute** the loaded playbook. Implementation additionally routes
   provider/model per `references/model-routing.md` before the first
   OpenCode run.
4. **Dialogue.** Any material open decision → <CheckpointThenBlock>; answers
   arrive as `DECISION(Q<n>)` after a respawn.
5. **Review gate.** Body carries `Review:` → <ReviewGate> before any
   completion call.
6. **Report** per <Report>; complete the task.

</Steps>

<Report>

Final message:

- Mode taken (advisory / implement) and, for implementation, provider/model
  used and why.
- Files changed or inspected.
- Validation commands + outcomes (or what was skipped and why).
- Remote / GitHub actions performed, if any (and the Authority line that allowed them).
- Remaining risks, blockers, or decisions needed.
- Attach bulky artifacts (assessments, full plans, large diffs, logs) with
  `kanban_attach`.
- Pass the machine-readable handoff in `kanban_complete(metadata={...})`
  using the board convention: `changed_files`, `verification` (commands
  run), `dependencies`, `retry_notes`, `residual_risk`. No secrets or raw
  logs — pointers and summaries only.

</Report>

<Pitfalls>

- Working from this core file without loading the mode reference — the
  playbooks (P0/fork loop, permission bridge, advisory format) live there.
- Blocking without checkpointing first — the respawn loses uncommitted work
  and the next run restarts blind.
- Vague block reasons ("thoughts?") — always `Q<n>` comments with options +
  recommendation, and a reason line that survives 160-char truncation.
- Putting the full question only in the block reason — the notification is
  truncated; comments are the durable copy.
- Reusing a question number or re-asking an already-DECIDED Q<n>.
- Completing a `Review: required` task without an approved `REVIEW:` round
  (<ReviewGate>) — or using the `REVIEW:` prefix on an ordinary question
  block (it forces a human relay; questions belong to `Q<n>:`).
- Treating an absent Authority section as more than A1 — absence means the
  default preset, and everything beyond it means ask.
- Acting on a grant you inferred from chat-style comments — only the body
  `Authority:` and `AUTHORITY+:` comments count.
- Long silent runs with no `PROGRESS:` comments — the orchestrator can't see
  inside your run any other way.
- Shipping code from an advisory task because it seemed small — advisory
  never ships; report the finding instead.

</Pitfalls>

<Verification>

- The mode was routed per <ModeRouting> and the matching reference(s) were
  loaded before work started.
- Effective Authority computed (preset + overrides + `AUTHORITY+` comments);
  every remote/destructive action maps to a grant or a block round-trip.
- Blocks were preceded by a checkpoint + `STATE:`/`Q<n>:` comments (ids
  included), with a <=160-char reason headline.
- No secrets or unrelated files included; report covers mode, changes,
  validation, risk — plus the per-mode Verification list in the loaded
  reference.

</Verification>
