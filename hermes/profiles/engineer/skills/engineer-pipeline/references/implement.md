# Implement mode — the Wave-fork OpenCode loop

Loaded for implementation tasks (with `references/model-routing.md` for the
provider/model decision). The core file's Authority contract, comment
protocol, and checkpoint-then-block apply throughout.

Implement consumes a **Wave outline** — the coarse milestones and their order
— and builds it Wave by Wave. The outline comes from a preceding **plan**
slice (`references/plan.md`), or implement generates its own for a Build-path
task. Session context is NOT the durable layer — the Wave outline (text), git
history, and kanban comments are.

## RiskGate

Plan-approval is risk-tiered, not unconditional:

| Tier | Examples | Gate |
| --- | --- | --- |
| Low | mechanical fix, docs, small test, cleanup within scope | no base, no Waves; implement directly in one session |
| Medium | standard feature/refactor inside granted scope | establish the base (plan outline), run the Wave loop, self-review; attach the outline (kanban_attach) for the audit trail |
| High | architecture change, public API/schema change, dependency change, anything outside Authority | establish the base, then — unless a plan slice already produced an **approved** outline — checkpoint-then-block with the outline attached, wait for approval before the Wave loop |

## OpenCodeLoop

### Base — the Wave outline (established in THIS task)

The base is a plan session in this worktree that holds the Wave outline; each
Wave forks from it. Establish it in-task — never depend on a session reaching
across tasks (opencode sessions are project-keyed; a prior plan task's session
may not be visible here):

- **A plan slice ran** (the task body / an attachment carries the approved
  Wave outline): seed the base from that outline verbatim —

  ```text
  opencode run --auto --agent plan --title "waves: <goal>" --model <m> \
    'This Wave outline is already approved — hold it as the plan to implement,
     do not re-plan: <the approved Waves, verbatim>'
  ```

  Optimization: if `opencode session list` in this worktree shows the plan
  slice's base session id, fork it directly and skip re-seeding.
- **No outline** (Build path, Medium/High): generate it yourself —

  ```text
  opencode run --auto --agent plan --title "waves: <goal>" --model <m> \
    'Split this goal into WAVES only — coarse milestones and their dependency
     order, one line each. No phase/unit detail. <goal, constraints, done>'
  ```

  then self-review it (risks, ordering). High tier additionally blocks for
  approval (RiskGate) before the loop.
- Recover the base id (`opencode session list`), record it in a `PROGRESS:`
  comment, and attach the outline (`kanban_attach`). The **durable handoff is
  the outline text + git**; the session id is just the fork handle.

### Wave loop (Wave 1 → Wave 2 → …, in outline order)

Per Wave, a decompose → confirm → build sub-cycle. **OpenCode owns the phase
granularity; you judge it, you don't dictate it.**

1. **Decompose** — fork the base with the plan agent (read-only):

   ```text
   opencode run --auto -s <base-id> --fork --agent plan --model <m> \
     'Decompose Wave N — "<wave intent>" — into phases/units, grounded on the
      current worktree (prior Waves are already committed here). Phases only,
      no code. If something material is undecided, say so.'
   ```

2. **Confirm** — read the phase breakdown and sanity-check it: does it match
   the Wave's intent, stay inside the granted scope, and hang together? This is
   your L3 review of OpenCode's plan — judge it, don't re-granularize it.
   - Off target / too broad → correct via `run -c '<redirect>'`.
   - Reveals a need outside the grant (a dependency, a push, an
     architecture/public-API change) → **checkpoint-then-block** (core
     <CheckpointThenBlock>) — this is the exception that goes to the
     orchestrator; the Wave outline's approval does not cover a new grant.
   - Leave a one-line `PROGRESS:` naming the confirmed phases (visibility).

3. **Implement** — fork the confirmed phase-plan to build, wrapped per
   <PermissionBridge>:

   ```text
   OPENCODE_PERMISSION='<per PermissionBridge>' opencode run --auto \
     -s <phase-plan-id> --fork --agent build --model <m> \
     'Implement these phases for Wave N: <the confirmed breakdown>. Prior Waves
      are committed — build on them. If something material is undecided, stop
      and state it in your final message instead of guessing.'
   ```

   Follow-ups within the Wave: `opencode run -c '<follow-up>'` (or
   `-s <build-fork-id>`). The permission env, `--auto`, and `--model <m>` are
   **per-invocation** — wrap every build call, including `-c`/`-s` resumes.
   OpenCode handles the phases' own sub-steps/subagents; **don't micromanage
   L4** — judge the result by your own verification.

4. **Close the Wave** — verify independently → commit (sub-commits per phase
   are fine) → `PROGRESS:` with ids (`[base <id> | wave <name> <build-fork-id>
   | phases: …]`) → discard the Wave's forks. The **next Wave forks fresh from
   the base** — never carry a session across a Wave boundary (that is how cost
   and compaction creep back in).

Grounding: prior Waves are committed, so each Wave's decompose/build reads the
**current worktree** for context — grounding travels through git, not through
session lineage. You only ever track two live ids: the base and the current
Wave's fork.

Prompt scoping rule: every decompose/build prompt names ONE Wave, never the
whole goal — narrow scope is what buys quality.

Escape hatch: if fork mechanics misbehave, commit the outline as `PLAN.md` in
the worktree and run each Wave as a fresh session that reads `PLAN.md` + the
current code.

### Inspection primaries (fresh sessions, not forks)

- `opencode run --auto --agent review --model <m> '<review this worktree's
  diff …>'` — after a Wave or before handing back; unbiased eyes, read-only
  by its own permissions (plain `--auto`, no env).
- `opencode run --auto --agent debug --model <m> '<symptom, repro …>'` —
  stubborn bugs; read-only diagnosis. Apply the fix in the Wave's build fork
  (`run -c`).
- Their findings flow back as `run -c` follow-ups into the Wave's build fork.
  Both delegate internally (reviewer/debugger subagents) per the opencode
  config — **don't micromanage L4**; judge the results with your own
  verification.

## PermissionBridge

Non-interactive `opencode run` **auto-rejects** every permission that
resolves to `ask` (verified) — with the machine's interactive-first opencode
config, a bare `run` cannot even edit files. Translate the effective
Authority into permissions per invocation:

```bash
OPENCODE_PERMISSION='{"edit":"allow","bash":{"*":"allow",<authority-denies>}}' \
  opencode run --auto ...
```

| Effective grant | `<authority-denies>` |
| --- | --- |
| A1 | `"git push*":"deny","gh pr create*":"deny","gh pr merge*":"deny","npm publish*":"deny"` |
| A2 | drop the push/PR-create denies; keep `"gh pr merge*":"deny"` (merging is never yours) |
| A3 | same as A2 |

Verified mechanics this relies on:

- `OPENCODE_PERMISSION` **deep-merges over** the global config — set keys
  win, everything else (the global protective denies: sudo, `.env` reads,
  `secret get`, …) persists. Never set a bare `{"*":"allow"}`.
- **`deny` beats `--auto`**: `--auto` only approves what still resolves to
  `ask`, so the deny list machine-enforces the **remote/publish boundary**
  of the grant.
- Everything not pattern-enforceable — scope boundaries (`do not touch:`),
  dependency limits at A1/A2, destructive ops — is enforced by the prompt
  plus your **independent verification at every tier**: inspect the diff
  for out-of-scope files and lockfile/manifest changes; an ungranted dep
  change → revert it or block, never wave it through.
- **Agent frontmatter beats the env** — review/debug keep their own
  read-only permissions regardless; for them plain `--auto` (no env) is
  enough and their `edit: deny` still holds.

`! permission requested: … auto-rejecting` in run output = your bridge is
mis-set for something the grant allows. Fix the env, don't prompt around it.

## QuestionBridge

OpenCode **cannot ask you questions**: `run` denies its question tool at the
session level (verified), and permission asks are auto-answered per
PermissionBridge. Its only escalation channel is **text in the run's final
output**. So:

- End prompts with: "If something material is undecided or blocked, stop
  and state the open question and options in your final message instead of
  guessing."
- Read every run's output for open questions, stated assumptions, and
  permission-denial notes — not just the success claim.
- Open question in the output → decide at your altitude if the effective
  Authority covers it and answer via `run -c`; otherwise translate it into a
  `Q<n>` and checkpoint-then-block (one layer up, never skip to the user).
- A denial the grant should NOT allow (e.g. push at A1) appearing as an
  attempted action is working as intended — tell OpenCode the constraint in
  the follow-up rather than widening the bridge.

## FanOut

You may dispatch sub-tasks to other workers with `kanban_create` instead of
doing their job badly yourself:

- research / docs / current-info lookup → `assignee: searcher` (breadth) or
  `assignee: researcher` (analysis/synthesis)
- media assets (icons, images, video) → `assignee: creator`

Rules:

- The sub-task body must be self-contained (the worker can't see your task).
- Continue your own work while it runs when possible; otherwise set your task
  as the child's downstream: create your remaining work as a task with
  `parents: [<child-id>]`, complete your current run with a state note, and
  let dependency promotion resume the pipeline.
- Read results from the child's completion summary / attachments
  (`kanban_show <child-id>`).
- Don't fan out trivia you can answer with your own tools in seconds.

## Steps

1. **Quota → provider/model** per `references/model-routing.md`.
2. **RiskGate.** Low → implement directly in one session, skip the base and
   the Wave loop. Medium/High → establish the base per OpenCodeLoop (seed the
   approved outline, or self-generate one); High without a prior approved
   outline → checkpoint-then-block for approval before the loop.
3. **Run the Wave loop** per OpenCodeLoop: for each Wave, decompose (plan
   fork) → confirm the breakdown → implement (build fork, wrapped per
   PermissionBridge) → verify → commit → `PROGRESS:` (with ids) → next Wave
   forks fresh from the base. Read each run's output per QuestionBridge.
   Interpose `--auto --agent review` / `--agent debug` fresh sessions where a
   Wave warrants it.
4. **Verify independently** — never trust the agent's self-report:
   `git status --short`, `git diff`, read changed files, run targeted tests /
   build / lint. If nothing is runnable, say so and explain what you checked.
5. **On quota / rate / auth error**, drop to the next provider/model and retry
   (`references/model-routing.md`).
6. **Commit** minimal, reversible changes; push/PR only under an explicit
   Authority grant (otherwise block to ask).

## Pitfalls

- Carrying one session across a Wave boundary (cost + compaction creep) — fork
  fresh from the base per Wave and ground on git; or the opposite: restarting
  from scratch after an unblock instead of rejoining the recorded Wave fork
  (`-s <fork-id>`, see `references/resume.md`).
- Dictating the phase granularity instead of judging OpenCode's decomposition
  — or skipping the confirm step and building a bad breakdown.
- Building a Wave whose decompose surfaced an out-of-grant need (dependency,
  push, architecture change) without a block round-trip.
- Un-recorded base / Wave-fork ids — a respawn that can't find them restarts
  blind; ids belong in every `STATE:`/`PROGRESS:` comment.
- Bloating the base with phase detail (keep it the coarse Wave outline), or
  prompting "the whole goal" in one Wave instead of that Wave only.
- Bare `opencode run` without the PermissionBridge env — edits get silently
  auto-rejected and the model "completes" around them.
- `OPENCODE_PERMISSION='{"*":"allow"}'` — the merge would bury the global
  protective denies; set only `edit`/`bash` keys plus the Authority denies.
- Ignoring `auto-rejecting` lines or unstated-assumption text in run output —
  that is OpenCode's only voice (QuestionBridge).
- Trusting a completion message without inspecting the diff.
- TUI: needs `pty=true`, exit with Ctrl+C (never `/exit`); one workdir per session.

## Verification

- The base was established in-task (seeded from the approved outline, or
  self-generated + self-reviewed); base and Wave-fork ids are recorded.
- Medium/high-risk work has the Wave outline attached; high-risk without a
  prior approved outline had an approval round-trip.
- Each Wave ran decompose (plan fork) → confirm → implement (build fork),
  ending verify → commit → `PROGRESS:` with ids; no session crossed a Wave
  boundary; grounding read the committed prior Waves; run outputs were read
  for open questions (QuestionBridge).
- Every build run carried the matching PermissionBridge env + `--auto`; every
  remote/destructive action maps to a grant or a block round-trip.
- `git status` / `git diff` inspected; tests / build / lint run or explicitly
  skipped.
