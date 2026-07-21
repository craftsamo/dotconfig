---
name: engineer-loop
description: Engineer's dialogue-driven OpenCode loop — parse the task's Authority grant (preset A1/A2/A3 + overrides, expanded only by AUTHORITY+ comments), run quota-gated provider/model routing, gate material decisions through checkpoint-then-block (WIP commit + structured STATE/Qn comments + a <=160-char block reason), keep an on-demand progress trail with PROGRESS comments, fan out research/media sub-tasks to searcher/researcher/creator via kanban_create, resume prior OpenCode sessions after unblock with `opencode run -c` and Qn<->DECISION(Qn) matching, verify independently, and report with kanban_attach artifacts. CLI mechanics live in the bundled opencode/claude-code/codex skills.
version: 2.2.0
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
one), so continuity lives in two durable layers: the kanban comment thread
(decisions) and the OpenCode session in the preserved worktree (implementation
context, resumed with `opencode run -c`). This skill defines the loop, the
Authority contract, the checkpoint-then-block protocol, quota-gated model
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
  the pending question(s) decide, and that the OpenCode session in this
  worktree is resumable (`opencode run -c`).
- `Q<n>: <question>` — one numbered question per comment (or one comment with
  `Q1:`/`Q2:`… lines): 2-4 concrete options, your recommendation marked.
  Numbering continues across the task's lifetime — never reuse an n.
- `PROGRESS: <one-two lines>` — phase/milestone completed, what's next.
  Comments are NOT pushed to chat; the orchestrator reads them on demand
  (`kanban_show`), so keep them frequent but terse.

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
| Low | mechanical fix, docs, small test, cleanup within scope | no plan round-trip; implement directly |
| Medium | standard feature/refactor inside granted scope | OpenCode plan first, self-review it, implement; attach the plan to the task (kanban_attach) for the audit trail |
| High | architecture change, public API/schema change, dependency change, anything outside Authority | OpenCode plan first, then <CheckpointThenBlock> with the plan attached — wait for approval before implementing |

</RiskGate>

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
3. **Continue the prior OpenCode session**: `opencode run -c '<follow-up
   incorporating the DECISION(s)>'` in the same worktree. Only start a fresh
   session when the answer invalidates the previous approach.
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

Check before choosing a model:
```text
terminal(command="opencode-quota show --provider anthropic", workdir="<wd>", timeout=60)
# also: --provider copilot | openai ; npx -y @slkiser/opencode-quota show ... if not on PATH
```
- Usable Anthropic quota → Claude may be used.
- Missing command / auth failure / no quota data → **treat Claude as unavailable**
  even if Claude auth looks valid. (`claude auth status` is NOT sufficient.)
- OpenAI fallback: gate on `--provider openai` (OpenAI Pro windows). Prefer
  `gpt-5.6-sol` for high-risk work, `gpt-5.6-terra` for standard work, and
  `gpt-5.6-luna` for routine/mechanical work.

</QuotaGate>

<ProviderSelection>

High → low:

1. **Claude via OpenCode** — only when the Anthropic quota gate passes.
   Heavy/high-risk → Opus 4.8; light/mechanical → Haiku 4.5.
   If OpenCode-native Claude is gated/unavailable, **Copilot** is the alternate
   Claude-family source (Opus 4.8 first, then OpenAI-family).
2. **OpenAI via OpenCode** — primary fallback once Claude is gated out. High-risk →
   `gpt-5.6-sol`; standard → `gpt-5.6-terra`; routine/cheap → `gpt-5.6-luna`
   or the configured light model.
   Gate on `--provider openai`.
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
3. **Risk-gate the plan** per <RiskGate>. High tier → plan via
   `opencode run 'Plan only, do not edit files: <task>' --agent plan --model <m>`,
   then <CheckpointThenBlock> for approval.
4. **Implement.** `opencode run '<task>' --model <m>` in the workdir; for iterative
   work use the background TUI (see `opencode` skill). Continue with `opencode run -c '<follow-up>'`.
   Drop a `PROGRESS:` comment at each phase boundary (plan done, feature
   builds, tests green, …) — that trail is the orchestrator's only mid-run
   visibility, read on demand.
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
- Restarting OpenCode from scratch after an unblock instead of `opencode run -c`.
- Reusing a question number or re-asking an already-DECIDED Q<n>.
- Treating an absent Authority section as more than A1 — absence means the
  default preset, and everything beyond it means ask.
- Acting on a grant you inferred from chat-style comments — only the body
  `Authority:` and `AUTHORITY+:` comments count.
- Long silent runs with no `PROGRESS:` comments — the orchestrator can't see
  inside your run any other way.
- Treating `claude auth status` as enough — Claude needs usable `opencode-quota` data.
- Falling back to OpenRouter but selecting Claude/GPT there.
- Treating OpenAI Pro quota as interchangeable with Codex/Copilot quota; check the
  provider actually selected for the run.
- Trusting a completion message without inspecting the diff.
- TUI: needs `pty=true`, exit with Ctrl+C (never `/exit`); one workdir per session.

</Pitfalls>

<Verification>

- Effective Authority computed (preset + overrides + `AUTHORITY+` comments);
  every remote/destructive action maps to a grant or a block round-trip.
- Quota/provider decision recorded (or failure reported).
- Medium/high-risk work has a plan artifact; high-risk had an approval round-trip.
- Blocks were preceded by a WIP commit + `STATE:`/`Q<n>:` comments, with a
  <=160-char reason headline; resumes used `opencode run -c` after matching
  every open `Q<n>` to its `DECISION(Q<n>)`.
- Phase boundaries left a `PROGRESS:` trail.
- `git status` / `git diff` inspected; tests / build / lint run or explicitly skipped.
- No secrets or unrelated files included; report covers model, changes, validation, risk.

</Verification>
