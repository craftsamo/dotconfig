---
name: opencode-loop
description: Coder's delegate-to-OpenCode implementation loop with model-priority and quota-aware model selection.
version: 0.1.0
author: Hermes Agent
metadata:
  hermes:
    tags: [coding, opencode, delegation, workflow]
    related_skills: [opencode]
---
# OpenCode delegation loop (coder)

Coder implements by driving the OpenCode CLI. This skill defines the loop, the
model-priority ladder, and the quota check. CLI mechanics (one-shot `run` vs
background TUI, flags, pitfalls) live in the bundled `opencode` skill — load it
for syntax.

## When to Use
- Implementing a coder task: writing/refactoring code, fixing bugs, adding tests, PRs.

## Model priority (pick the highest with remaining quota)
Check quota first: `terminal(command="opencode-quota show")`
(or `npx @slkiser/opencode-quota show`; `--provider <name>` narrows it).

Ladder (high → low) — [tune]:
1. Claude — Opus 4.8
2. Claude — Haiku 4.5
3. Copilot — Opus 4.8
4. OpenRouter — Deepseek-4-Flash
5. OpenRouter — Deepseek-4-pro

Rules:
- Use the highest-priority entry that still has quota remaining.
- Weight by task: heavy/complex → prefer an Opus-class model; light/mechanical →
  a cheaper tier (Haiku / Deepseek-Flash) is fine even if a stronger one has quota.
- Resolve the exact `--model provider/model` slug at runtime via
  `terminal(command="opencode models")` — slugs change; don't hard-code stale ones.

## Procedure
1. Scope the task; work inside the task worktree (`$HERMES_KANBAN_WORKSPACE`).
2. `opencode-quota show` → choose a model per the ladder above.
3. Bounded task:
   `terminal(command="opencode run '<task>' --model <provider/model>", workdir="<worktree>")`.
   Iterative task: start the background TUI per the `opencode` skill and submit/poll.
4. Read the result; run tests/builds.
5. If incomplete or tests fail: continue the session with
   `opencode run -c '<follow-up>'` and repeat.
6. On a quota / rate / auth error: drop to the next model in the ladder and retry.
7. Commit minimal, reversible changes; report files changed + test results.

## Pitfalls
- See the bundled `opencode` skill: TUI needs `pty=true`, never `/exit` (use Ctrl+C),
  watch for PATH/binary mismatch, one workdir per session.
- Don't share a workdir across parallel OpenCode sessions.

## Verification
- Tests/build pass; expected files changed; concrete outcome reported back.
