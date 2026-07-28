# Driving OpenCode — sessions, models, bridges (engine)

Load this before the FIRST OpenCode invocation of any task — implement always;
assess/shape only when they actually run OpenCode sessions. The core file's
Authority contract, comment protocol, and checkpoint-then-block apply
throughout. This engine owns the HOW of delegation: session mechanics, model
routing, the Wave loop, the permission/question bridges, and course
correction. WHAT to produce comes from the mode file; whether it passed comes
from `references/verify.md`.

## SessionBasics

- One flavor per job: `opencode run --auto --agent <plan|build|review|debug>
  --model <m> '<prompt>'`. `plan`/`review`/`debug` are read-only by their own
  agent permissions; only `build` edits (and only under <PermissionBridge>).
- Continue: `run -c '<follow-up>'` (last session) or `-s <id>` (named).
  Fork: `-s <id> --fork` — branch a session without mutating it.
- `--auto`, the permission env, and `--model <m>` are **per-invocation** —
  wrap every call, including `-c`/`-s` resumes.
- Session context is NOT the durable layer: outlines/Issues (text), git
  history, and kanban comments are. Record every base/fork id in
  `STATE:`/`PROGRESS:` comments — a respawn that can't find ids restarts blind.
- One workdir per session. TUI needs `pty=true`, exit with Ctrl+C (never
  `/exit`) — but prefer `run` over the TUI in worker context.

## ModelRouting

### QuotaGate

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
  ProviderSelection. `claude auth status` alone is never the gate.

### ProviderSelection

High → low:

1. **Claude via OpenCode** — when QuotaGate routes to Claude.
   Heavy/high-risk → Opus 4.8; light/mechanical → Haiku 4.5.
   If OpenCode-native Claude is gated/unavailable, **Copilot** is the alternate
   Claude-family source (Claude-family first, then OpenAI-family).
2. **OpenAI via OpenCode** — when QuotaGate routes to OpenAI. High-risk →
   `gpt-5.6-sol`; standard → `gpt-5.6-terra`; routine/cheap → `gpt-5.6-luna`
   or the configured light model.
3. **OpenRouter** — cheap coding-capable models only. **Never Claude/GPT via
   OpenRouter** (exclude `anthropic` / `claude` / `openai` / `gpt`). Prefer
   Deepseek-4-Flash, then Deepseek-4-pro.
4. Direct `claude-code` / `codex` only on explicit request or when OpenCode
   is unsuitable.

Resolve exact `--model provider/model` slugs at runtime (`opencode models`) —
don't hard-code stale ones. On quota / rate / auth errors mid-task, drop to
the next rung and retry; the final report names the provider/model actually
used.

### ModelChoice

Weight by task risk:

| Class | Use for |
|---|---|
| Opus 4.8 / GPT-5.6 Sol | high-risk architecture, complex refactor, hard debugging |
| Sonnet / GPT-5.6 Terra | default implementation, standard features, tests |
| Haiku / GPT-5.6 Luna / cheap OpenRouter | small/mechanical fixes, docs, low-risk cleanup |

## OpenCodeLoop

The medium/high-risk build choreography: a base plan session holds the Wave
outline; each Wave forks from it.

### Base — the Wave outline (established in THIS task)

Establish the base in-task — never depend on a session reaching across tasks
(opencode sessions are project-keyed; a prior task's session may not be
visible here):

- **An approved outline exists** (shape slice output in the task body / an
  attachment): seed the base from it verbatim —

  ```text
  opencode run --auto --agent plan --title "waves: <goal>" --model <m> \
    'This Wave outline is already approved — hold it as the plan to implement,
     do not re-plan: <the approved Waves, verbatim>'
  ```

  Optimization: if `opencode session list` in this worktree shows the shape
  slice's base session id, fork it directly and skip re-seeding.
- **No outline** (Build path, Medium/High): generate it yourself —

  ```text
  opencode run --auto --agent plan --title "waves: <goal>" --model <m> \
    'Split this goal into WAVES only — coarse milestones and their dependency
     order, one line each. No phase/unit detail. <goal, constraints, done>'
  ```

  then self-review it (risks, ordering). High tier additionally blocks for
  approval (the mode file's RiskGate) before the loop.
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
   the Wave's intent, stay inside the granted scope, and hang together? This
   is your review of OpenCode's plan — judge it, don't re-granularize it.
   - Off target / too broad → correct via `run -c '<redirect>'`.
   - Reveals a need outside the grant (a dependency, a push, an
     architecture/public-API change) → **checkpoint-then-block** (core
     <CheckpointThenBlock>) — the Wave outline's approval does not cover a
     new grant.
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
   `-s <build-fork-id>`). OpenCode handles the phases' own
   sub-steps/subagents; **don't micromanage its internals** — judge the
   result by your own verification (`references/verify.md`).

4. **Close the Wave** — verify per `references/verify.md` → commit
   (sub-commits per phase are fine) → `PROGRESS:` with ids (`[base <id> |
   wave <name> <build-fork-id> | phases: …]`) → discard the Wave's forks. The
   **next Wave forks fresh from the base** — never carry a session across a
   Wave boundary (that is how cost and compaction creep back in).

Grounding: prior Waves are committed, so each Wave's decompose/build reads
the **current worktree** for context — grounding travels through git, not
through session lineage. You only ever track two live ids: the base and the
current Wave's fork.

Prompt scoping rule: every decompose/build prompt names ONE Wave, never the
whole goal — narrow scope is what buys quality.

Escape hatch: if fork mechanics misbehave, commit the outline as `PLAN.md` in
the worktree and run each Wave as a fresh session that reads `PLAN.md` + the
current code.

## InspectionPrimaries

Fresh sessions, not forks — usable from any mode (assess uses them
standalone; implement interposes them where a Wave warrants it):

- `opencode run --auto --agent review --model <m> '<review this worktree's
  diff …>'` — after a Wave or before handing back; unbiased eyes, read-only
  by its own permissions (plain `--auto`, no env).
- `opencode run --auto --agent debug --model <m> '<symptom, repro …>'` —
  stubborn bugs; read-only diagnosis. Apply the fix in the Wave's build fork
  (`run -c`).
- Their findings flow back as `run -c` follow-ups into the build fork. Both
  delegate internally (reviewer/debugger subagents) per the opencode config —
  don't micromanage; judge the results with your own verification.

## PermissionBridge

Non-interactive `opencode run` **auto-rejects** every permission that
resolves to `ask` (verified) — with the machine's interactive-first opencode
config, a bare `run` cannot even edit files. Translate the effective
Authority into permissions per invocation:

```bash
OPENCODE_PERMISSION='{"edit":"allow","bash":{"*":"allow",<authority-denies>},<tool-denies>}' \
  opencode run --auto ...
```

| Effective grant | `<authority-denies>` (bash) |
| --- | --- |
| A1 | `"git push*":"deny","gh pr create*":"deny","gh pr merge*":"deny","gh pr comment*":"deny","gh pr edit*":"deny","gh pr review*":"deny","npm publish*":"deny"` + the issue-write denies below |
| A2 | drop the push/PR-create/comment/edit/review denies — A2 includes maintaining YOUR OWN PR (reply to review comments, edit the body, re-request review); keep `"gh pr merge*":"deny"` (merging is never yours) + the issue-write denies below |
| A3 | same as A2 |

**Issue/board writes are in NO A-preset** — only the override line
`issues: write` (or an `AUTHORITY+:` expansion) grants them. Until granted,
every build run also carries:

- bash: `"gh issue create*":"deny","gh issue edit*":"deny","gh issue comment*":"deny","gh issue close*":"deny","gh project *":"deny"`
- `<tool-denies>` — OpenCode's custom GitHub Projects tools are `allow` in its
  global config, so deny the write ones by name:
  `"github_project_create":"deny","github_project_field_ensure":"deny","github_project_item_add":"deny","github_project_item_set":"deny","github_project_item_note":"deny","github_project_item_promote":"deny","github_project_view_ensure":"deny","github_project_issue_link":"deny","github_project_issue_develop":"deny"`
  (`github_project_item_list` stays allowed — read-only).

With `issues: write`: drop the issue/board denies above, but ALWAYS keep
`"gh issue delete*":"deny"` (deleting is never yours, mirroring the tools'
own no-delete policy). Reading (`gh issue view/list`, `gh pr view/diff`,
`github_project_item_list`) is never denied at any grant.

Verified mechanics this relies on:

- `OPENCODE_PERMISSION` **deep-merges over** the global config — set keys
  win, everything else (the global protective denies: sudo, `.env` reads,
  `secret get`, …) persists. Never set a bare `{"*":"allow"}`.
- **`deny` beats `--auto`**: `--auto` only approves what still resolves to
  `ask`, so the deny list machine-enforces the **remote/publish boundary**
  of the grant.
- Everything not pattern-enforceable — scope boundaries (`do not touch:`),
  dependency limits at A1/A2, destructive ops — is enforced by the prompt
  plus your **independent verification at every tier** (`references/verify.md`):
  inspect the diff for out-of-scope files and lockfile/manifest changes; an
  ungranted dep change → revert it or block, never wave it through.
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

## CourseCorrect

When a run drifts, pick the cheapest recovery that restores quality:

1. **Redirect** (`run -c '<what's off + what to do instead>'`) — the session
   understood the goal but took a wrong turn. First resort.
2. **Re-fork** — the session context itself is poisoned (compaction, wrong
   assumptions baked in): discard the fork, fork the base again with a
   corrected prompt. Cheap because the base holds the plan.
3. **Restart the Wave** — the breakdown was wrong, not the build: re-run
   decompose with what you learned, then build fresh.

Never argue with a degraded session for more than one redirect — re-forking
is cheaper than persuasion. Record what was discarded and why in a
`PROGRESS:` note so a respawn doesn't repeat it.

## Pitfalls

- Carrying one session across a Wave boundary (cost + compaction creep) —
  fork fresh from the base per Wave and ground on git; or the opposite:
  restarting from scratch after an unblock instead of rejoining the recorded
  fork (`-s <fork-id>`, see `references/resume.md`).
- Dictating the phase granularity instead of judging OpenCode's decomposition
  — or skipping the confirm step and building a bad breakdown.
- Bare `opencode run` without the PermissionBridge env — edits get silently
  auto-rejected and the model "completes" around them.
- `OPENCODE_PERMISSION='{"*":"allow"}'` — the merge would bury the global
  protective denies; set only `edit`/`bash` keys plus the Authority denies.
- Ignoring `auto-rejecting` lines or unstated-assumption text in run output —
  that is OpenCode's only voice (QuestionBridge).
- Un-recorded base / fork ids — ids belong in every `STATE:`/`PROGRESS:`
  comment.
- Bloating the base with phase detail (keep it the coarse Wave outline), or
  prompting "the whole goal" in one Wave instead of that Wave only.
- Treating `claude auth status` as the quota gate, or reading Anthropic
  "Unavailable (not detected)" as "no Claude" — use the comparative gate and
  its auth fallback.
- Falling back to OpenRouter but selecting Claude/GPT there.
- Hard-coding stale model slugs instead of resolving via `opencode models`.

## Verification

- Quota/provider decision recorded in the report; on quota / rate / auth
  errors the run dropped to the next rung and the report names the
  provider/model actually used.
- The base was established in-task; base and fork ids are recorded in
  comments.
- Each Wave ran decompose (plan fork) → confirm → implement (build fork);
  no session crossed a Wave boundary; run outputs were read for open
  questions (QuestionBridge).
- Every build run carried the matching PermissionBridge env + `--auto`
  (including the issue/board tool denies when `issues: write` is absent).
