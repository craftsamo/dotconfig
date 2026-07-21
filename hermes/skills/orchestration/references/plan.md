# Plan approach — reference

Loaded after Step 3 picks **Approach=Plan**. Plan owns the request through
to dispatch — you walk Steps 4-6 here, then hand off to Step 7 in the main
skill.

## When to pick Plan

- **Implementation work always enters Plan** (standing rule): code, tests,
  builds, restructure — even when it looks small.
- For non-implementation, pick Plan when the request is:
  - **ambiguous** — the goal could be read several ways
  - **multi-stage** — obvious 2+ stages, fan-in, or mixed worker types
  - **destructive / irreversible** — migrations, deletes, scope expansion,
    spend

If the user has already specified scope and approach in detail, prefer Build
(`references/build.md`). When unsure between Plan and Build for
implementation, default to **Plan**.

## Step 4 — Decompose

Apply these four principles throughout the Plan Loop:

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
(see "Worker consultations" below) to ground the decomposition in reality.

## Step 5 — Register

Capture the decomposed steps in the **session `todo` tool** — it is
session-local (in-memory `TodoStore`), which matches the chat-only Plan
persistence model. One todo item per concrete step, status `pending`. Mark
`in_progress` when you start refining it in the Plan Loop, `completed` when
folded into the signed-off plan, `cancelled` if dropped.

The todo list is the shared scratch state between you and the user during
Plan Loop iterations — both of you can see what's settled and what's open.
On sign-off, the surviving items become the dispatch task specs (Step 7).

## Step 6 — Plan Loop

Iterate with the user until the plan is signed off. Each cycle:

1. Present the current plan shape (or delta) compactly.
2. Wherever a choice exists, fire a `clarify` with up to 4 options + your
   recommendation in the question text. **One question at a time.**
3. On the user's answer, update the `todo` list and the plan draft.
4. Repeat until the user signs off (or revises scope).

### Worker consultations during Plan

When you need facts to make the plan concrete, dispatch via **kanban**
(not `delegate_task` — durability over tempo). Mark them advisory so they
don't get confused with deliverables:

- `workspace_kind: scratch`, small `max_runtime_seconds` (e.g. 600).
- Body opens with **"Advisory — inform the plan, don't ship."** — this
  opener is the universal advisory marker: every worker's loop skill
  routes on it into a consultation playbook (short assessment, nothing
  produced or shipped). Close the body with what the plan needs from the
  result (a feasibility verdict, a landscape scan, a tradeoff matrix).
- Any worker can be consulted, each at its own altitude:
  - **engineer** — feasibility ("is this buildable, what's the shape,
    what's the risk, rough size"), not implementation.
  - **searcher** — landscape scans; **researcher** — synthesis / tradeoff
    matrices.
  - **creator** — media feasibility, chain fit, Budget estimate (no
    generation spend).
  - **writer** — structure, tone/norms recommendation, effort.
  - **marketer** — channel fit, campaign shape, effort.
- Ack the user in chat when consultations are in flight; never poll. Worker
  completion notifications resume the Plan Loop where you left off.

### Sign-off gate

One final `clarify` ("Plan looks like X, dispatch as Y/Z/W — proceed?")
before Step 7. The signed-off plan + the Authority grant for engineer tasks
become the artifact that crosses into dispatch.

Translate the sign-off into the Authority preset (`<TaskSpec>` table):
what the user sanctioned during the loop decides the level — nothing
remote said → `A1`; PR/push agreed → `A2`; dependency changes agreed →
`A3` — plus scope-boundary override lines from the plan. Don't grant
beyond what the loop actually settled.

### Session continuity

The Plan lives in chat + the `todo` list only. If the session compresses or
resets, ask the user "what did we agree on?" and rebuild from the todo
state.

## After sign-off

Hand off to Step 7 (Dispatch) in the main skill — apply `<Topology>`,
write self-contained task specs (engineer tasks carry the Authority from
sign-off; media tasks carry a MediaBrief from `references/creative.md`),
ack, and recover from failures per `<Failures>` / `<BlockedTriage>`.
