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
- `--auto`, the permission env, `--model <m>` and `--variant` are
  **per-invocation** — wrap every call, including `-c`/`-s` resumes.
- Session context is NOT the durable layer: outlines/Issues (text), git
  history, and kanban comments are. Record every base/fork id in
  `STATE:`/`PROGRESS:` comments — a respawn that can't find ids restarts blind.
- One workdir per session. TUI needs `pty=true`, exit with Ctrl+C (never
  `/exit`) — but prefer `run` over the TUI in worker context.

## ModelRouting

A **fixed ladder**, not a per-task weighing. Always start at the top rung and
descend only when the rung above is unusable. You do **not** pre-classify the
work as heavy or light to pick a cheaper model — OpenCode is the only layer
that can measure the real weight of a job, and it does that inside the run.
Your risk tier (implement.md) shapes the Wave loop, never the model.

### ProviderLadder

| # | `--model` | Descend when |
| --- | --- | --- |
| 1 | `anthropic/claude-opus-5` | quota / rate / auth error, or Claude unavailable |
| 2 | `openai/gpt-5.6-sol` + `--variant high` | OpenAI pool spent (QuotaCheck) or erroring |
| 3 | `xai/grok-4.5` | xAI OAuth missing/lapsed |
| 4 | OpenRouter, cheap coding-capable only | — last metered resort |
| 5 | direct `claude-code` / `codex` | only on explicit request, or OpenCode unsuitable |

- **Variants.** Anthropic already defaults to `high`, so rung 1 needs no
  `--variant` (`max` exists for a deliberately larger thinking budget).
  OpenAI defaults to the model's built-in effort, so rung 2 states
  `--variant high` explicitly. An unrecognized variant name is **silently
  ignored** (verified — no error), so a typo degrades the run invisibly.
- **Rung 4 excludes `anthropic` / `claude` / `openai` / `gpt` slugs** — paying
  per token for a model you already hold a subscription to is the mistake this
  rule exists to prevent. Prefer `deepseek/deepseek-v4-flash`, then
  `deepseek/deepseek-v4-pro`.
- Resolve exact `provider/model` slugs at runtime (`opencode models`) — the
  catalog moves; don't hard-code stale ones. On a mid-task error drop **one**
  rung and retry; the final report names the provider/model actually used.

### QuotaCheck

The ladder sets the order; this check only says whether the rung you are on
still has room. Both subscription pools are shared with the human's own
interactive OpenCode use, so draining one takes it from them.

```text
terminal(command="npx -y @slkiser/opencode-quota show", workdir="<wd>", timeout=90)
```

- **Anthropic reports `Unavailable (not detected)` on this machine — always.**
  It is not a quota signal (the locally patched copy behaves the same). Rung 1
  is therefore driven by errors, not by the meter: anthropic models present in
  `opencode models` → use it; a quota / rate error mid-run → descend.
- OpenAI reports a real remaining %. Under ~15% treat rung 2 as gone and skip
  to rung 3 instead of fighting the human for the last slice.
- **Every run draws on the OpenAI (and xAI) pools regardless of `--model`** —
  OpenCode's own subagents are pinned to their own models in frontmatter
  (explore / worker / reviewer / verifier / debugger on OpenAI, the search
  tiers on xAI). A Claude run is never purely Claude, so OpenAI headroom
  matters even on rung 1.
- `claude auth status` is never the gate.

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
  "Unavailable (not detected)" as "no Claude" — rung 1 descends on errors, not
  on the meter.
- Judging the job "light" and starting below rung 1 — the ladder is fixed;
  weighing the work is OpenCode's job, inside the run.
- Skipping rungs on a single error instead of descending exactly one.
- Falling back to OpenRouter but selecting Claude/GPT there.
- Hard-coding stale model slugs instead of resolving via `opencode models`, or
  passing a `--variant` name the provider doesn't know (silently ignored).

## Verification

- The run started at ProviderLadder rung 1 unless a recorded error or
  QuotaCheck reading forced a descent; the report names the provider/model
  (and variant) actually used, plus the reason for any descent.
- The base was established in-task; base and fork ids are recorded in
  comments.
- Each Wave ran decompose (plan fork) → confirm → implement (build fork);
  no session crossed a Wave boundary; run outputs were read for open
  questions (QuestionBridge).
- Every build run carried the matching PermissionBridge env + `--auto`
  (including the issue/board tool denies when `issues: write` is absent).
