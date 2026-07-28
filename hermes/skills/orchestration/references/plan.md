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

### Planner tree — multi-card plans, user-approved before registration

The chat Plan Loop settles **requirements** (what to build, scope, grant
posture). When the signed-off goal needs a **multi-card dependency graph**,
the graph itself is drafted by the **planner** profile and registered by
you only after the user approves it. Activation — any ONE of:

- the work implies **3+ cards** or **2+ worker profiles**
- fan-out / fan-in parallelism is on the table
- grants (Authority A2+/Budget/Publish/Review) must be distributed across
  several cards
- the user wants to see the structure before it runs, or signalled async
  ("任せる", "まとまったら見せて")

Not for single-card work (write the TaskSpec yourself — a planner hop costs
a dispatch tick + an Opus turn) and not for unsettled requirements (settle
them in the chat loop first).

Flow:

1. **(Optional) pre-seed investigations.** When grounding is obviously
   needed (implementation goal → engineer orient card; unknown landscape →
   searcher/researcher advisories, previous section), create them first and
   list them as `parents` of the plan card. The planner reads their
   summaries on wake. For repo work, orient results replace guessing.
2. **Create the plan card.** `title: 計画: <goal>`, `assignee: planner`,
   `workspace_kind: scratch`, modest `max_runtime_seconds` (e.g. 900),
   parents = the investigation ids (if any). Body: Goal / Inputs (paths,
   repo, parent ids, the user's constraints and sanctioned grant posture) /
   Done criteria ("outline YAML attached + final message") — self-contained
   as always. The planner may fan out its own advisories mid-plan
   (continuation card, its pipeline's Tier 3); it never creates build cards.
3. **Receive the outline.** The plan card completes with `outline.yaml`
   attached (schema: planner-pipeline `<OutlineSchema>` — cards with `key` /
   `assignee` / `skills` / `parents` / `params` / self-contained `body`
   with grant lines, plus `plan.notes`). Render it for the user: a compact
   tree/graph summary (per card: title, assignee+technics, grants, deps) +
   the planner's notes. Then ONE `clarify`: approve / request changes /
   discard.
4. **Approval = grant sanction.** The user approves topology AND the grant
   lines inside the card bodies — equivalent to a chat sign-off. Never
   register grants the approved outline doesn't carry; widening later is a
   normal `AUTHORITY+:` flow on the live card.
5. **Register (you, not the planner).** Create cards in topological order —
   parents before children, mapping outline `key`s to returned task ids:
   - validate first: every `assignee` exists, every `skills:` entry is a
     known technic for that profile (`<Workers>` table); on mismatch go
     back to step 3's clarify, don't improvise.
   - `kanban_create(title, assignee, body, parents=[mapped ids],
     skills=[...], **params, idempotency_key="<plan-card-id>:<key>")` —
     the idempotency key makes re-registration after a partial failure
      safe. Cards for a pinned profile (engineer / creator / writer /
      marketer / researcher, <Workers>) always get their
      `"<profile>-pipeline"` prepended to `skills` (the mandatory pin) —
      add it if the outline omitted it.
   - ack in chat: card ids per outline key, then hand off to normal
     <AfterCreate> / <Failures> handling.
6. **Changes / rejection.** Comment nothing on the completed plan card:
   create a **new** plan card carrying the user's feedback + a pointer to
   the previous card id and its outline attachment, and archive the old one
   (`hermes kanban archive <id>`) so the board stays truthful. Repeated
   rounds (>2) mean requirements weren't settled — drop back to the chat
   Plan Loop.

For implementation goals, the outline carries ONE engineer card per
deliverable (Wave/phase detail is the engineer's own plan altitude at
implement time); it may also include an upfront engineer **plan** slice
(body opens `Plan — outline the Waves, don't build.`, see
engineer-pipeline) when the user wants the technical shape validated before
approving the graph.

### Sign-off gate

One final `clarify` ("Plan looks like X, dispatch as Y/Z/W — proceed?")
before Step 7. The signed-off plan + the Authority grant for engineer tasks
become the artifact that crosses into dispatch.

Translate the sign-off into the Authority preset (`<TaskSpec>` table):
what the user sanctioned during the loop decides the level — nothing
remote said → `A1`; PR/push agreed → `A2`; dependency changes agreed →
`A3` — plus scope-boundary override lines from the plan. Don't grant
beyond what the loop actually settled.

**Feature-sized goals on a GitHub-flow repo route through specify first**
(the planning ladder, PROFILES.md): your loop settles the HIGH-level
requirement only ("login feature" — goal, scope, grant posture); the
LOW-level split into requirement Issues is the engineer's **specify**
altitude (main skill `<Workers>`), not this loop's job and not planner's
(planner decomposes into board cards across workers; specify decomposes one
feature into repo-grounded GitHub Issues). Don't over-settle detail in chat
that specify will re-derive grounded on the code — hand it the settled
requirement and review its decomposition instead.

Settle the **Review gate** in the same breath: does the user want to
approve the deliverable before the task closes? Yes → write `Review:
required — <what to present>` into the task spec (worker blocks with a
`REVIEW:` headline instead of completing; see `<TaskSpec>` /
`<BlockedTriage>`). Default is no gate — completion notification + post-hoc
review. Lean toward the gate for irreversible or user-facing deliverables
(published prose, PR merges the user will own, expensive media batches).

### Session continuity

The Plan lives in chat + the `todo` list only. If the session compresses or
resets, ask the user "what did we agree on?" and rebuild from the todo
state. A **Planner tree** does not share this fragility: the outline and
its notes live on the plan card (attachment + final message) — on any
reset, `kanban_show` the plan card instead of re-asking the user.

## After sign-off

Hand off to Step 7 (Dispatch) in the main skill — apply `<Topology>`,
write self-contained task specs (engineer tasks carry the Authority from
sign-off; media tasks carry a MediaBrief from `references/creative.md`),
ack, and recover from failures per `<Failures>` / `<BlockedTriage>`.
