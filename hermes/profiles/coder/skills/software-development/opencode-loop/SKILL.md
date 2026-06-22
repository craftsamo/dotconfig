---
name: opencode-loop
description: Coder's delegate-to-OpenCode loop — quota-gated provider/model routing, plan-first for non-trivial work, independent verification, and structured reporting. CLI mechanics live in the bundled opencode/claude-code/codex skills.
version: 1.1.0
author: CraftSamo
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
# also: --provider copilot | openai | zai ; npx -y @slkiser/opencode-quota show … if not on PATH
```
- Usable Anthropic quota → Claude may be used.
- Missing command / auth failure / no quota data → **treat Claude as unavailable**
  even if Claude auth looks valid. (`claude auth status` is NOT sufficient.)
- GLM fallback: gate on `--provider zai` (Coding Plan 5h + weekly windows). `glm-5.2`
  bills ~3× at peak (14:00–18:00 UTC+8), 2× off-peak — prefer `glm-4.7` for routine work.

## Provider selection (high → low)
1. **Claude via OpenCode** — only when the Anthropic quota gate passes.
   Heavy/high-risk → Opus 4.8; light/mechanical → Haiku 4.5.
   If OpenCode-native Claude is gated/unavailable, **Copilot** is the alternate
   Claude-family source (Opus 4.8 first, then OpenAI-family).
2. **GLM via OpenCode (`zai-coding-plan`)** — primary fallback once Claude is gated
   out, and the cost-saver for routine work. Strong → `glm-5.2`; routine/cheap →
   `glm-4.7` / `glm-5-turbo`. Works through OpenCode because the local `zai-sanitize`
   plugin neutralizes Z.ai's system-prompt filter (otherwise these requests fail with
   code `1305` / "temporarily overloaded"). Gate on `--provider zai`.
3. **OpenRouter** — cheap coding-capable models only. **Never Claude/GPT via OpenRouter**
   (exclude `anthropic` / `claude` / `openai` / `gpt`). Prefer Deepseek-4-Flash, then Deepseek-4-pro.
4. Direct `claude-code` / `codex` only on explicit request or when OpenCode is unsuitable.

Resolve exact `--model provider/model` slugs at runtime (`opencode models`) — don't hard-code stale ones.

## Model choice (weight by task risk)
| Class | Use for |
|---|---|
| Opus 4.8 / GPT-5.5 | high-risk architecture, complex refactor, hard debugging |
| Sonnet / GLM-5.2 | default implementation, standard features, tests |
| Haiku / GLM-4.7 / glm-5-turbo / cheap OpenRouter | small/mechanical fixes, docs, low-risk cleanup |

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
- Using `zai-coding-plan` in OpenCode without the `zai-sanitize` plugin loaded — Z.ai's
  system-prompt filter then rejects the request as `1305` / "temporarily overloaded".
- Letting OpenCode implement before the caller confirms a material plan.
- Trusting a completion message without inspecting the diff.
- TUI: needs `pty=true`, exit with Ctrl+C (never `/exit`); one workdir per session.

## Verification
- Quota/provider decision recorded (or failure reported).
- Non-trivial work had a reviewed plan + required confirmations.
- `git status` / `git diff` inspected; tests / build / lint run or explicitly skipped.
- No secrets or unrelated files included; report covers model, changes, validation, risk.
