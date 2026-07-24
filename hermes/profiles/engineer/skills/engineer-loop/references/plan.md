# Plan mode — outline the Waves before building

Loaded when <ModeRouting> detects a plan task: the body opens with
`Plan — outline the Waves, don't build.`. The orchestrator has an
implementation goal (requirements already settled in its own Plan Loop) and
needs a **grounded technical outline** before implement runs. The deliverable
is the **Wave outline** — the coarse milestones and their order — produced in
an OpenCode plan session, self-assessed, and handed back for approval. No
code ships; nothing below the Wave line is decided here.

This is the read-only planning slice. It replaces the old "plan-draft"
advisory variant: advisory judges *whether* a change is feasible; plan lays
out *how*, at Wave granularity, on a repo that already exists.

## The Wave line — what plan decides vs what OpenCode owns

- **Plan decides Waves** — the human/orchestrator-meaningful milestones and
  their dependency order (e.g. LP: `Wave1 theme colors → Wave2 layout →
  Wave3 sections → Wave4 responsive`). Each Wave is a one-line intent, coarse
  enough to review in seconds.
- **OpenCode owns everything below the Wave** — the Phase/unit decomposition
  inside each Wave is decided at implement time, per Wave, by OpenCode's plan
  agent (human vs LLM sub-task granularity differs; don't impose it here).
  **Never write Phase-level detail in this slice.**

## Rules

- **Read-only.** No commits, edits, scaffolding, dependency installs. An
  Authority line never authorizes shipping from a plan task; a plan primary
  runs plain `--auto` (no permission env).
- **A repo must exist.** Plan grounds on a codebase — orient confirmed one (or
  bootstrap established it). No repo → report "no repo, bootstrap needed" and
  stop, exactly as orient/implement do; never plan against an empty workspace.
- **Coarse, not deep.** Waves + order + a one-line intent each. If you find
  yourself listing files or steps inside a Wave, stop — that is OpenCode's job
  in implement.

## Procedure

1. **Model** — pick the plan model per `references/model-routing.md` (read-only
   planning; plain `--auto`).
2. **Ground** — read the repo (structure, conventions, entry points), or use an
   attached orient report if the body provides one. Understand what exists
   before splitting the goal.
3. **Produce the Wave outline** with an OpenCode plan primary:

   ```text
   opencode run --auto --agent plan --title "waves: <goal>" --model <m> \
     'Split this implementation goal into WAVES only — coarse milestones and
      their dependency order, one line each. Do NOT plan phases/units inside a
      wave. <goal, constraints, done criteria, grounded on this repo>'
   ```

4. **Self-assess** the outline — apply the risks lens to your own Waves: what's
   uncertain, where the ordering could be wrong, what a reviewer should
   challenge.
5. **Record the base session id.** Recover the plan session
   (`opencode session list`) and record its id — this is the **base** the
   implement slice will fork each Wave from, so the settled outline carries
   forward without drift. Put it in the report, a `PROGRESS:` comment, and
   `kanban_complete` metadata.
6. **Report** the outline (attach if long) and complete. Approval is the
   orchestrator's post-completion call (it reviews the outline, then dispatches
   implement). If the body carries `Review: required`, use the <ReviewGate>
   instead — block with a `REVIEW:` headline for the human before completing.

## Report format

```markdown
## Goal
<the implementation goal, one line>
## Waves
1. <Wave 1 — one-line intent>
2. <Wave 2 — one-line intent>  (depends on 1)
3. …
## Self-assessment
<risks / uncertainties / what a reviewer should challenge — 3-6 lines>
## Base session
opencode plan session <id> — implement forks each Wave from this
```

## Report

- Final message = the Wave outline + self-assessment + the base session id.
- `kanban_complete` summary = 1-2 plain sentences carrying the outline's shape
  and Wave count (e.g. "4-Wave outline for the landing page: theme → layout →
  sections → responsive; base plan session s_ab12 — ready to implement.") —
  delivered verbatim to the requester's chat.
- `metadata` carries the machine-readable handoff: `{"waves": [...],
  "base_session": "<id>"}` so implement and the orchestrator can act on it
  without re-reading the prose.

## MEMORY.md

Nothing durable by default — a Wave outline is task-specific and lives in the
kanban thread + attachment. Persist only a genuinely reusable architectural
fact if one surfaced (rare).

## Pitfalls

- Writing Phase/unit detail inside a Wave — that is OpenCode's job in
  implement; keep Waves coarse and one-line.
- Shipping code or scaffolding — plan is read-only; building is the implement
  slice.
- Planning against no repo — bootstrap must run first; report and stop.
- Forgetting the base session id — implement then can't fork from the settled
  plan and the outline drifts on re-planning.
- Bloating the outline into many thin Waves — Waves are milestones, not steps;
  if it reads like a checklist, it's too fine.
- Treating an Authority line as permission to build — plan never ships.

## Verification

- A repo existed; the outline was grounded on it (or bootstrap was reported).
- Deliverable is Waves only — coarse milestones + order, one line each, no
  Phase/unit detail.
- The base OpenCode plan session id is recorded (report + PROGRESS + metadata).
- A self-assessment is included; nothing was committed, edited, or installed.
