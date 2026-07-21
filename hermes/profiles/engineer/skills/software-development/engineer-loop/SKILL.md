---
name: engineer-loop
description: Engineer's dialogue-driven OpenCode loop — parse the task's Authority grant (preset A1/A2/A3 + overrides, expanded only by AUTHORITY+ comments), translate it into an OPENCODE_PERMISSION overlay + --auto (Permission Bridge), plan once in a lean P0 master-plan session and implement unit-by-unit in short-lived forks (-s <P0> --fork; PR-sized units, no compaction), run review/debug primaries as fresh sessions, handle OpenCode's needs via its final output (Question Bridge: run -c answer or L2 block), gate material decisions through checkpoint-then-block (WIP commit + structured STATE/Qn comments + a <=160-char block reason), keep an on-demand PROGRESS trail with session ids, fan out research/media sub-tasks via kanban_create, verify independently, and report with kanban_attach artifacts. CLI mechanics live in the bundled opencode/claude-code/codex skills.
version: 2.4.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [coding, opencode, delegation, model-routing, quota, verification, dialogue, checkpoint]
    category: software-development
    related_skills: [opencode, claude-code, codex, github-pr-workflow, test-driven-development, systematic-debugging]
---

<Goal>

Engineer implements by driving OpenCode **in dialogue with the orchestrator**.
The worker process is disposable (block ends the run; unblock respawns a fresh
one), so continuity lives in durable layers only: the kanban comment thread
(decisions + session ids), the P0 master-plan session and its per-unit forks
in the preserved worktree (<OpenCodeLoop>), and git history. Never rely on a
long-running session's memory — sessions are short-lived by design. This
skill defines the loop, the Authority contract and its machine enforcement
(<PermissionBridge>), the checkpoint-then-block protocol, quota-gated model
routing, and the verify/report discipline. CLI syntax lives in the bundled
`opencode` skill — load it when you need mechanics.

</Goal>

<Scope>
<UseWhen>

- Implementing an engineer task: writing/refactoring code, fixing bugs, adding tests, PRs.
- Resuming a task after an unblock (respawn) — see <Resume>.

</UseWhen>

<DoNotUseWhen>

- Web research, non-code writing, or work outside the caller's workdir.

</DoNotUseWhen>
</Scope>

<Prerequisites>

- A real workdir (the task worktree `$HERMES_KANBAN_WORKSPACE` for kanban work).
- `terminal`, OpenCode installed + authenticated, `git`, and `opencode-quota`
  for the Claude gate.

</Prerequisites>

<CommentProtocol>

All dialogue with the orchestrator travels as kanban comments with a fixed
marker as the first token. Markers you WRITE:

- `STATE:` — checkpoint note before a block: what's done, current plan, what
  the pending question(s) decide, plus the **session ids** needed to resume
  (P0 id, current unit-fork id, current unit — see <OpenCodeLoop>).
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

Anything bulky (plans, diffs, logs) goes through `kanban_attach` /
`kanban_attach_url` and is referenced from the comment, never inlined.

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
  overrides.
- Not granted (by preset, override, or `AUTHORITY+`) → NOT allowed:
  **push, PR creation, dependency changes, architecture or public-API
  changes, destructive operations, and material plan choices require a
  block round-trip.**
- Never exceed an explicit scope limit even if technically convenient.

</Authority>

<RiskGate>

Plan-approval is risk-tiered, not unconditional:

| Tier | Examples | Gate |
| --- | --- | --- |
| Low | mechanical fix, docs, small test, cleanup within scope | no P0, no plan round-trip; implement directly in one session |
| Medium | standard feature/refactor inside granted scope | P0 master plan (<OpenCodeLoop>), self-review it, implement; attach the plan (kanban_attach) for the audit trail |
| High | architecture change, public API/schema change, dependency change, anything outside Authority | P0 master plan, then <CheckpointThenBlock> with the plan attached — wait for approval before implementing |

</RiskGate>

<OpenCodeLoop>

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
   `OPENCODE_PERMISSION='<per <PermissionBridge>>' opencode run --auto
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

</OpenCodeLoop>

<PermissionBridge>

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

</PermissionBridge>

<QuestionBridge>

OpenCode **cannot ask you questions**: `run` denies its question tool at the
session level (verified), and permission asks are auto-answered per
<PermissionBridge>. Its only escalation channel is **text in the run's final
output**. So:

- End prompts with: "If something material is undecided or blocked, stop
  and state the open question and options in your final message instead of
  guessing."
- Read every run's output for open questions, stated assumptions, and
  permission-denial notes — not just the success claim.
- Open question in the output → decide at your altitude if the effective
  Authority covers it and answer via `run -c`; otherwise translate it into a
  `Q<n>` and <CheckpointThenBlock> (one layer up, never skip to the user).
- A denial the grant should NOT allow (e.g. push at A1) appearing as an
  attempted action is working as intended — tell OpenCode the constraint in
  the follow-up rather than widening the bridge.

</QuestionBridge>

<CheckpointThenBlock>

When you need the orchestrator's answer (approval, choice, missing input):

1. **Checkpoint the work.** Commit WIP in the worktree
   (`git add -A && git commit -m "wip: <state>"`) so nothing is lost across
   the respawn.
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

<Resume>

Every respawned run (task has prior runs/comments):

1. `kanban_show <id>` — read the full comment thread and prior-attempt
   summaries. Rebuild the dialogue state mechanically:
   - **Match every `Q<n>` against a `DECISION(Q<n>)`.** Unanswered Q<n> →
     still open; if it gates the next step, re-block referencing the same n
     (don't renumber, don't re-ask answered questions).
   - **Recompute the effective Authority**: body grant + every `AUTHORITY+:`
     comment (see <Authority>).
2. Confirm the worktree state: `git log --oneline -5`, `git status --short`.
3. **Rejoin the right session** (ids from the latest `STATE:`/`PROGRESS:`
   comment):
   - Blocked **mid-unit** → continue the unit fork:
     `opencode run -s <fork-id> '<follow-up incorporating the DECISION(s)>'`.
   - Between units (or the DECISION invalidates the current unit's approach)
     → fork fresh from P0 per <OpenCodeLoop>.
   - The DECISION invalidates the plan itself → redo P0 (new master plan),
     attach it, note the supersession.
4. Record the outcome in a short `PROGRESS:` comment so the thread stays an
   audit trail.

</Resume>

<FanOut>

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

</FanOut>

<QuotaGate>

The gate is **comparative** — both subscription pools are shared with the
human's interactive OpenCode use, so route to the pool with headroom:

```text
terminal(command="npx -y @slkiser/opencode-quota show", workdir="<wd>", timeout=90)
```

- Both pools report a remaining % → pick the one with **more headroom**
  (tie → Claude for heavy/high-risk, OpenAI for standard).
- A pool under ~15% left → treat it as exhausted for heavy work; only
  small/mechanical jobs may still use it.
- **Anthropic `Unavailable (not detected)` is a known false negative** (the
  tool cannot read Claude subscription usage on this machine) — it does NOT
  mean "no quota". Fall back to an auth check: anthropic models listed in
  `opencode models` → Claude is usable; prefer Claude when OpenAI is below
  ~30% or the work is heavy/high-risk, otherwise OpenAI.
- Neither pool usable (auth missing / both exhausted) → cheap tier per
  <ProviderSelection>. `claude auth status` alone is never the gate.

Within the chosen pool, weight the model by task risk per <ModelChoice>.

</QuotaGate>

<ProviderSelection>

High → low:

1. **Claude via OpenCode** — when <QuotaGate> routes to Claude.
   Heavy/high-risk → Opus 4.8; light/mechanical → Haiku 4.5.
   If OpenCode-native Claude is gated/unavailable, **Copilot** is the alternate
   Claude-family source (Claude-family first, then OpenAI-family).
2. **OpenAI via OpenCode** — when <QuotaGate> routes to OpenAI. High-risk →
   `gpt-5.6-sol`; standard → `gpt-5.6-terra`; routine/cheap → `gpt-5.6-luna`
   or the configured light model.
3. **OpenRouter** — cheap coding-capable models only. **Never Claude/GPT via OpenRouter**
   (exclude `anthropic` / `claude` / `openai` / `gpt`). Prefer Deepseek-4-Flash, then Deepseek-4-pro.
4. Direct `claude-code` / `codex` only on explicit request or when OpenCode is unsuitable.

Resolve exact `--model provider/model` slugs at runtime (`opencode models`) — don't hard-code stale ones.

</ProviderSelection>

<ModelChoice>

Weight by task risk:

| Class | Use for |
|---|---|
| Opus 4.8 / GPT-5.6 Sol | high-risk architecture, complex refactor, hard debugging |
| Sonnet / GPT-5.6 Terra | default implementation, standard features, tests |
| Haiku / GPT-5.6 Luna / cheap OpenRouter | small/mechanical fixes, docs, low-risk cleanup |

</ModelChoice>

<Steps>

1. **Orient.** `kanban_show`; if prior runs exist, switch to <Resume>. Parse
   the <Authority> grant and success criteria; confirm the worktree.
2. **Quota → provider/model** per the gate and ladder above.
3. **Risk-gate the plan** per <RiskGate>: Medium/High → run P0 per
   <OpenCodeLoop>; High additionally → <CheckpointThenBlock> for approval
   before implementing.
4. **Implement unit-by-unit** per <OpenCodeLoop>, every invocation wrapped
   per <PermissionBridge>: fork from P0 → build → verify → commit →
   `PROGRESS:` (with session ids) → next unit. Read each run's output per
   <QuestionBridge>. Interpose `--auto --agent review` / `--agent debug`
   fresh sessions where a unit warrants it.
5. **Verify independently** — never trust the agent's self-report:
   `git status --short`, `git diff`, read changed files, run targeted tests /
   build / lint. If nothing is runnable, say so and explain what you checked instead.
6. **On quota / rate / auth error**, drop to the next provider/model and retry.
7. **Commit** minimal, reversible changes; push/PR only under an explicit
   Authority grant (otherwise block to ask).

</Steps>

<Report>

Final message:

- Provider/model used and why.
- Files changed or inspected.
- Validation commands + outcomes (or what was skipped and why).
- Remote / GitHub actions performed, if any (and the Authority line that allowed them).
- Remaining risks, blockers, or decisions needed.
- Attach bulky artifacts (full plans, large diffs, logs) with `kanban_attach`.

</Report>

<Pitfalls>

- Blocking without checkpointing first — the respawn loses uncommitted work
  and the next run restarts blind.
- Vague block reasons ("thoughts?") — always `Q<n>` comments with options +
  recommendation, and a reason line that survives 160-char truncation.
- Putting the full question only in the block reason — the notification is
  truncated; comments are the durable copy.
- Restarting from scratch after a mid-unit unblock instead of rejoining the
  recorded fork (`-s <fork-id>`) — or the opposite: carrying one session
  across unit boundaries (cost + compaction creep back).
- Un-recorded session ids — a respawn that can't find P0 or the unit fork
  restarts blind; ids belong in every `STATE:`/`PROGRESS:` comment.
- Bloating P0 with per-unit detail (every fork re-sends its transcript), or
  planning "the whole app" in one prompt instead of one scoped unit.
- Bare `opencode run` without the <PermissionBridge> env — edits get
  silently auto-rejected and the model "completes" around them.
- `OPENCODE_PERMISSION='{"*":"allow"}'` — the merge would bury the global
  protective denies; set only `edit`/`bash` keys plus the Authority denies.
- Ignoring `auto-rejecting` lines or unstated-assumption text in run output —
  that is OpenCode's only voice (<QuestionBridge>).
- Reusing a question number or re-asking an already-DECIDED Q<n>.
- Treating an absent Authority section as more than A1 — absence means the
  default preset, and everything beyond it means ask.
- Acting on a grant you inferred from chat-style comments — only the body
  `Authority:` and `AUTHORITY+:` comments count.
- Long silent runs with no `PROGRESS:` comments — the orchestrator can't see
  inside your run any other way.
- Treating `claude auth status` as the quota gate, or reading Anthropic
  "Unavailable (not detected)" as "no Claude" — use the comparative gate and
  its auth fallback (<QuotaGate>).
- Falling back to OpenRouter but selecting Claude/GPT there.
- Treating OpenAI Pro quota as interchangeable with Codex/Copilot quota; check the
  provider actually selected for the run.
- Trusting a completion message without inspecting the diff.
- TUI: needs `pty=true`, exit with Ctrl+C (never `/exit`); one workdir per session.

</Pitfalls>

<Verification>

- Effective Authority computed (preset + overrides + `AUTHORITY+` comments);
  every remote/destructive action maps to a grant or a block round-trip, and
  every run carried the matching <PermissionBridge> env + `--auto`.
- Quota/provider decision recorded (or failure reported).
- Medium/high-risk work has a P0 plan artifact attached; high-risk had an
  approval round-trip.
- Units were implemented in per-unit forks of a lean P0, each ending
  verify → commit → `PROGRESS:` with session ids; no session crossed a unit
  boundary; run outputs were read for open questions (<QuestionBridge>).
- Blocks were preceded by a WIP commit + `STATE:`/`Q<n>:` comments (ids
  included), with a <=160-char reason headline; resumes rejoined the
  recorded session after matching every open `Q<n>` to its `DECISION(Q<n>)`.
- `git status` / `git diff` inspected; tests / build / lint run or explicitly skipped.
- No secrets or unrelated files included; report covers model, changes, validation, risk.

</Verification>
