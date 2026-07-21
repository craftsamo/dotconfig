# Implement mode — the dialogue-driven OpenCode loop

Loaded for implementation tasks (with `references/model-routing.md` for the
provider/model decision). The core file's Authority contract, comment
protocol, and checkpoint-then-block apply throughout.

## RiskGate

Plan-approval is risk-tiered, not unconditional:

| Tier | Examples | Gate |
| --- | --- | --- |
| Low | mechanical fix, docs, small test, cleanup within scope | no P0, no plan round-trip; implement directly in one session |
| Medium | standard feature/refactor inside granted scope | P0 master plan (OpenCodeLoop), self-review it, implement; attach the plan (kanban_attach) for the audit trail |
| High | architecture change, public API/schema change, dependency change, anything outside Authority | P0 master plan, then checkpoint-then-block with the plan attached — wait for approval before implementing |

## OpenCodeLoop

Plan once, then implement in short-lived scoped sessions. Session context is
NOT the durable layer — the plan session, git history, and kanban comments
are.

**P0 — master plan (one live P0 per task; Low-tier tasks skip P0 and run
as a single unit):**

```text
opencode run --auto --agent plan --title "plan: <task>" --model <m> \
  'Split this task into implementation units and sketch the architecture.
   Units only — no per-unit detail: <task goal, constraints, done criteria>'
```

(P0 is read-only planning — plain `--auto` suffices, no permission env. If
a DECISION later invalidates the plan itself, redo P0 as a successor and
note the supersession; the old P0's forks are dead.)

- Keep P0 **lean**: unit list + architecture shape + risks. Per-unit detail
  is planned inside each fork — every fork re-sends P0's transcript, so P0
  bloat taxes every unit.
- **Unit granularity**: one PR-sized concern (foundation, feature A, …) that
  finishes implement→verify in ONE session without compaction. Too big to
  fit → split it in P0.
- Recover the id via `opencode session list`; record it in a `PROGRESS:`
  comment; attach the plan text with `kanban_attach`.

**Unit loop (foundation → feature A → feature B → …):**

1. Fork from P0 — the fork inherits the plan context:
   `OPENCODE_PERMISSION='<per PermissionBridge>' opencode run --auto
   -s <P0-id> --fork --agent build --title "unit: <name>" --model <m>
   '<scoped unit goal — this unit only, with done criteria>'`
2. Follow-ups within the unit: `opencode run -c '<follow-up>'` (or
   `-s <fork-id>`). The permission env and `--auto` are **per-invocation**,
   not per-session — wrap every build call, including `-c`/`-s` resumes,
   and pass the same `--model <m>` explicitly each time.
3. Unit done: **verify independently → commit → `PROGRESS:` comment (with
   ids) → discard the fork.** Next unit forks fresh from P0 — never carry a
   session across unit boundaries (that is how cost and compaction creep
   back in).
4. Prompt scoping rule: every planning/implementing prompt names ONE scoped
   deliverable ("build the data layer"), never the whole task ("build the
   app") — narrow scope is what buys plan quality.

**Inspection primaries (fresh sessions, not forks):**

- `opencode run --auto --agent review --model <m> '<review this worktree's
  diff …>'` — after a unit or before handing back; unbiased eyes, read-only
  by its own permissions (plain `--auto`, no env).
- `opencode run --auto --agent debug --model <m> '<symptom, repro …>'` —
  stubborn bugs; read-only diagnosis. Apply the fix in the unit fork
  (`run -c`).
- Their findings flow back as `run -c` follow-ups into the unit fork. Both
  delegate internally (reviewer/debugger subagents) per the opencode config —
  **don't micromanage L4**; judge the results with your own verification.

Escape hatch: if fork mechanics misbehave, fall back to committing the plan
as `PLAN.md` in the worktree and starting each unit as a fresh session that
reads it.

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
2. **Risk-gate the plan** per RiskGate: Medium/High → run P0 per
   OpenCodeLoop; High additionally → checkpoint-then-block for approval
   before implementing.
3. **Implement unit-by-unit** per OpenCodeLoop, every invocation wrapped
   per PermissionBridge: fork from P0 → build → verify → commit →
   `PROGRESS:` (with session ids) → next unit. Read each run's output per
   QuestionBridge. Interpose `--auto --agent review` / `--agent debug`
   fresh sessions where a unit warrants it.
4. **Verify independently** — never trust the agent's self-report:
   `git status --short`, `git diff`, read changed files, run targeted tests /
   build / lint. If nothing is runnable, say so and explain what you checked instead.
5. **On quota / rate / auth error**, drop to the next provider/model and retry
   (`references/model-routing.md`).
6. **Commit** minimal, reversible changes; push/PR only under an explicit
   Authority grant (otherwise block to ask).

## Pitfalls

- Restarting from scratch after a mid-unit unblock instead of rejoining the
  recorded fork (`-s <fork-id>`) — or the opposite: carrying one session
  across unit boundaries (cost + compaction creep back in).
- Un-recorded session ids — a respawn that can't find P0 or the unit fork
  restarts blind; ids belong in every `STATE:`/`PROGRESS:` comment.
- Bloating P0 with per-unit detail (every fork re-sends its transcript), or
  planning "the whole app" in one prompt instead of one scoped unit.
- Bare `opencode run` without the PermissionBridge env — edits get
  silently auto-rejected and the model "completes" around them.
- `OPENCODE_PERMISSION='{"*":"allow"}'` — the merge would bury the global
  protective denies; set only `edit`/`bash` keys plus the Authority denies.
- Ignoring `auto-rejecting` lines or unstated-assumption text in run output —
  that is OpenCode's only voice (QuestionBridge).
- Trusting a completion message without inspecting the diff.
- TUI: needs `pty=true`, exit with Ctrl+C (never `/exit`); one workdir per session.

## Verification

- Every run carried the matching PermissionBridge env + `--auto`; every
  remote/destructive action maps to a grant or a block round-trip.
- Medium/high-risk work has a P0 plan artifact attached; high-risk had an
  approval round-trip.
- Units were implemented in per-unit forks of a lean P0, each ending
  verify → commit → `PROGRESS:` with session ids; no session crossed a unit
  boundary; run outputs were read for open questions (QuestionBridge).
- `git status` / `git diff` inspected; tests / build / lint run or
  explicitly skipped.
