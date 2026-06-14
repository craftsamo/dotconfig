---
name: opencode-loop
description: Coder's delegate-to-OpenCode loop — quota-gated provider/model routing, plan-first for non-trivial work, independent verification, and structured reporting. CLI mechanics live in the bundled opencode/claude-code/codex skills.
version: 1.0.0
author: Hermes Agent
metadata:
  hermes:
    tags: [coding, opencode, delegation, model-routing, quota, verification]
    category: software-development
    related_skills: [opencode, claude-code, codex, github-pr-workflow, test-driven-development, systematic-debugging]
---
# OpenCode delegation loop (coder)

Coder implements by driving OpenCode. This skill defines the loop, quota-gated
model routing, and the verify/report discipline. CLI syntax (one-shot `run` vs
background TUI, flags, pitfalls) lives in the bundled `opencode` skill — load it
when you need mechanics.

## When to Use
- Implementing a coder task: writing/refactoring code, fixing bugs, adding tests, PRs.
- Not for web research, non-code writing, or work outside the caller's workdir.

## Prerequisites
- A real workdir (the task worktree `$HERMES_KANBAN_WORKSPACE` for kanban work).
- `terminal`, OpenCode installed + authenticated, `git`, and `opencode-quota`
  for the Claude gate.

## Quota gate (check before choosing a model)
```text
terminal(command="opencode-quota show --provider anthropic", workdir="<wd>", timeout=60)
# also: --provider copilot | openai ; npx -y @slkiser/opencode-quota show … if not on PATH
```
- Usable Anthropic quota → Claude may be used.
- Missing command / auth failure / no quota data → **treat Claude as unavailable**
  even if Claude auth looks valid. (`claude auth status` is NOT sufficient.)

## Provider selection (high → low)
1. **Claude via OpenCode** — only when the Anthropic quota gate passes.
2. **Copilot** — Claude-family first (after Anthropic quota/auth limits), then OpenAI-family.
3. **Direct OpenAI** via OpenCode — prefer GPT-5.5 when Copilot is unavailable.
4. **OpenRouter** — cheap coding-capable models only. **Never Claude/GPT via OpenRouter**
   (exclude `anthropic` / `claude` / `openai` / `gpt`).
5. Direct `claude-code` / `codex` only on explicit request or when OpenCode is unsuitable.

Resolve exact `--model provider/model` slugs at runtime (`opencode models`) — don't hard-code stale ones.

## Model choice (weight by task risk)
| Class | Use for |
|---|---|
| Opus / GPT-5.5 | high-risk architecture, complex refactor, hard debugging |
| Sonnet | default implementation, standard features, tests |
| Haiku / GPT-5.4 / cheap OpenRouter | small/mechanical fixes, docs, low-risk cleanup |

## Procedure
1. **Scope** the task; confirm workdir, success criteria, and whether commits /
   pushes / PRs are allowed. Work inside the task worktree.
2. **Quota → provider/model** per the gate and ladder above.
3. **Plan first (non-trivial).** Ask OpenCode for an edit-free plan:
   `opencode run 'Plan only, do not edit files: <task>' --agent plan --model <m>`.
   Review it; reject plans that exceed scope or skip validation.
4. **Confirm** with the caller before material file / dependency / architecture
   changes, commits, pushes, PRs, or merges.
5. **Implement.** `opencode run '<task>' --model <m>` in the workdir; for iterative
   work use the background TUI (see `opencode` skill). Continue with `opencode run -c '<follow-up>'`.
6. **Verify independently** — never trust the agent's self-report:
   `git status --short`, `git diff`, read changed files, run targeted tests /
   build / lint. If nothing is runnable, say so and explain what you checked instead.
7. **On quota / rate / auth error**, drop to the next provider/model and retry.
8. **Commit** minimal, reversible changes (only when allowed).

## Report (final message)
- Provider/model used and why.
- Files changed or inspected.
- Validation commands + outcomes (or what was skipped and why).
- Remote / GitHub actions performed, if any.
- Remaining risks, blockers, or decisions needed.

## Pitfalls
- Treating `claude auth status` as enough — Claude needs usable `opencode-quota` data.
- Falling back to OpenRouter but selecting Claude/GPT there.
- Letting OpenCode implement before the caller confirms a material plan.
- Trusting a completion message without inspecting the diff.
- TUI: needs `pty=true`, exit with Ctrl+C (never `/exit`); one workdir per session.

## Verification
- Quota/provider decision recorded (or failure reported).
- Non-trivial work had a reviewed plan + required confirmations.
- `git status` / `git diff` inspected; tests / build / lint run or explicitly skipped.
- No secrets or unrelated files included; report covers model, changes, validation, risk.
