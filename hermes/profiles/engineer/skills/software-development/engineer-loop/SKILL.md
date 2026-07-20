---
name: engineer-loop
description: Engineer's dialogue-driven OpenCode loop — parse the task's Authority grant, run quota-gated provider/model routing, gate material decisions through checkpoint-then-block (WIP commit + state note + one crisp question), resume prior OpenCode sessions after unblock with `opencode run -c`, verify independently, and report with kanban_attach artifacts. CLI mechanics live in the bundled opencode/claude-code/codex skills.
version: 2.0.0
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

<Authority>

The task body's `Authority:` section is the orchestrator's pre-approval grant.
Parse it first; it decides what you may do without asking.

- Listed as allowed (e.g. `commit: yes`, `push: yes`, `PR: yes`,
  `deps: allowed`, scope boundaries) → proceed without blocking.
- Not listed, listed as `ask`, or absent entirely → treat as NOT granted:
  commits to the worktree are always fine; **push, PR creation, dependency
  additions/upgrades, architecture or public-API changes, destructive
  operations, and material plan choices require a block round-trip.**
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
2. **Write a state note** with `kanban_comment`: what's done, current plan,
   what the question decides, and that the OpenCode session in this worktree
   is resumable (`opencode run -c`). Long plans/diffs go through
   `kanban_attach` / `kanban_attach_url`, not inline.
3. **Block with ONE crisp question**: `kanban_block(kind=needs_input,
   reason=...)`. The reason must be answerable in ~30 seconds: one question,
   2-4 concrete options, your recommendation marked. No code dumps.
4. **Stop.** Produce no further work after the block call — the dispatcher
   will respawn you after the answer arrives.

Batch questions: if several decisions are pending, ask them in one block
round-trip (numbered, each with options + recommendation), never serially.

</CheckpointThenBlock>

<Resume>

Every respawned run (task has prior runs/comments):

1. `kanban_show <id>` — read the full comment thread, prior-attempt summaries,
   and the answers to your blocked question(s).
2. Confirm the worktree state: `git log --oneline -5`, `git status --short`.
3. **Continue the prior OpenCode session**: `opencode run -c '<follow-up
   incorporating the answer>'` in the same worktree. Only start a fresh
   session when the answer invalidates the previous approach.
4. Record the decision outcome in a short `kanban_comment` so the thread stays
   an audit trail.

</Resume>

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
- Vague block reasons ("thoughts?") — always options + recommendation.
- Restarting OpenCode from scratch after an unblock instead of `opencode run -c`.
- Treating an absent Authority section as permission — absence means ask.
- Treating `claude auth status` as enough — Claude needs usable `opencode-quota` data.
- Falling back to OpenRouter but selecting Claude/GPT there.
- Treating OpenAI Pro quota as interchangeable with Codex/Copilot quota; check the
  provider actually selected for the run.
- Trusting a completion message without inspecting the diff.
- TUI: needs `pty=true`, exit with Ctrl+C (never `/exit`); one workdir per session.

</Pitfalls>

<Verification>

- Authority section parsed; every remote/destructive action maps to a grant or a block round-trip.
- Quota/provider decision recorded (or failure reported).
- Medium/high-risk work has a plan artifact; high-risk had an approval round-trip.
- Blocks were preceded by a WIP commit + state note; resumes used `opencode run -c`.
- `git status` / `git diff` inspected; tests / build / lint run or explicitly skipped.
- No secrets or unrelated files included; report covers model, changes, validation, risk.

</Verification>
