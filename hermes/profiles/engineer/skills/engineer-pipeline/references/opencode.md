# Driving OpenCode — sessions, models, bridges (engine)

Load this before the FIRST OpenCode invocation of any job — implement
always; assess only when it actually runs OpenCode sessions. The core
file's Authority contract, dialogue protocol, and checkpoint-then-block
apply throughout. This engine owns the HOW of delegation: session mechanics, model
routing, run execution, the unit cycle, the permission/question bridges, and
course correction. WHAT to produce comes from the mode file; whether it
passed comes from `references/verify.md`.

## SessionBasics

- One flavor per job: `opencode run --auto --agent <plan|build|review|debug>
  --model <m> '<prompt>'`. `plan`/`review`/`debug` are read-only by their own
  agent permissions; only `build` edits (and only under <PermissionBridge>).
- Continue: `run -c '<follow-up>'` (last session) or `-s <id>` (named).
  Fork: `-s <id> --fork` — branch a session without mutating it.
- `--auto`, the permission env, `--model <m>` and `--variant` are
  **per-invocation** — wrap every call, including `-c`/`-s` resumes.
- Session context is NOT the durable layer: outlines/Issues (text), git
  history, and your session reports are. Record every base/fork id in your
  replies — a resumed job that can't find ids restarts blind.
- One workdir per session. TUI needs `pty=true`, exit with Ctrl+C (never
  `/exit`) — but prefer `run` over the TUI in worker context.

## PromptContract

Every OpenCode session already carries an **injected system layer** before
your prompt arrives: the global AGENTS.md (delegation + skill routing,
language policy), the target repo's own AGENTS.md/CLAUDE.md (build/test
commands, conventions), each agent's frontmatter (model + permissions —
plan/review/debug are read-only by themselves), the `opencode.jsonc`
permission tree (protective denies), and the skill catalog. The map of that
layer is `opencode-env` <InjectedLayer> — **read it before writing your
first prompt of a task**: if you cannot predict what OpenCode already
knows, you cannot know what to leave out.

**A dispatch prompt carries only the DELTA on top of that layer.**
Restating what the layer already says is not "being safe" — it is noise
that dilutes the few constraints that genuinely need the prompt.

Anatomy per run type:

- **decompose / derive**: the unit intent (one line) + reference paths +
  "phases only, no code" + the closer.
- **build**: the confirmed phase breakdown (OpenCode's own words, from the
  gate artifact) + the scope boundaries that are NOT machine-enforced +
  "run the repo's own checks and report the actual output" + the closer.
- **redirect** (`run -c`): what is off + the expected direction. Nothing
  else.

Never restate (the layer already carries it):

1. Role or behavior preambles — "you are …", or telling the plan agent not
   to implement (its frontmatter makes it read-only).
2. Agent permissions — review/debug read-only, edit rights.
3. Anything the <PermissionBridge> env already denies (push / PR / merge /
   issue writes).
4. Skill content — name the skill ("load and follow `approach-refactor`");
   never paste its discipline.
5. Repo conventions the target repo's AGENTS.md documents — including
   verification commands: say "run the repo's check suite, report actual
   output" and enumerate commands only to override or extend them.

Always keep (no layer carries these):

- The <QuestionBridge> closer — OpenCode's only escalation channel.
- Scope boundaries that no pattern can enforce (`do not write to <sibling
  repo>`, `do not touch <file>` — per <PermissionBridge>, prompt +
  verification is their designed enforcement).
- The expected report format, when it matters.

Shape heuristic: a build prompt that looks like a numbered per-file spec is
an altitude violation — that content belongs to the decompose output (the
gate artifact) or the referenced plan document, never to your prompt.

## RunExecution

`opencode run` routinely takes 5-20+ minutes, and every supervision cycle
spends turns from the same `max_turns` budget that funds the real work — past
runs have died at `max_iterations_reached` on polling alone. Two execution
shapes:

- **Foreground by default**: `terminal(command="opencode run …", timeout=<generous>)`
  — one turn per run. The per-call `timeout` is not clamped; size it to the
  expected run (1800 for a build unit is reasonable) instead of accepting the
  default. While the run executes you have nothing else to do — blocking is
  correct, not a problem.
- **Background only when you must interleave** (two runs in parallel, or a
  run that may outlive any sane single timeout): start it in background, then
  wait in the longest slices the tool allows — `process` wait is clamped to
  the profile's `terminal.timeout` (600 on this profile; requesting less is
  pure waste). Cycle `wait(600)` → `wait(600)` …. The wait's return already
  carries the output tail: add no status-check terminal calls between
  waits, and read logs only after the wait reports exit.

Budget math: a 180 s wait + status check cycle costs ~60 turns/hour;
`wait(600)` costs ~12.

## ModelRouting

A **fixed ladder**, not a per-task weighing. Always start at the top rung and
descend only when the rung above is unusable. You do **not** pre-classify the
work as heavy or light to pick a cheaper model — OpenCode is the only layer
that can measure the real weight of a job, and it does that inside the run.
Risk shapes the unit cycle's rigor (implement.md <RiskDiscipline>),
never the model.

### ProviderLadder

Rung 1 depends on what the run is FOR — reading and judging code, or writing
it. That split is the only per-task choice in this section; from rung 2 down
the order is fixed and identical.

| # | reading runs (`plan` / `review` / `debug` / `explain`) | writing runs (`build`) | Descend when |
| --- | --- | --- | --- |
| 1 | `anthropic/claude-fable-5-1` | `openai/gpt-6-astra` | quota / rate / auth error on that pool |
| 2 | `anthropic/claude-opus-5` | `anthropic/claude-opus-5` | same, on the Claude pool |
| 3 | `openai/gpt-6-astra` | `openai/gpt-5.6-sol` + `--variant high` | OpenAI pool spent (QuotaCheck) or erroring |
| 4 | `openai/gpt-5.6-sol` + `--variant high` | `xai/grok-4.5` | — |
| 5 | `xai/grok-4.5` | OpenRouter, cheap coding-capable only | xAI OAuth missing/lapsed |
| 6 | OpenRouter, cheap coding-capable only | direct `claude-code` / `codex` | — last metered resort |
| 7 | direct `claude-code` / `codex` | — | only on explicit request, or OpenCode unsuitable |

- **Why the split.** Fable 5.1 reads and plans best; Astra writes code best.
  Both then fall to Opus 5, which is the one model always reachable on the
  Claude pool even when Fable's sub-cap is spent (see PROFILES.md "Fable and
  the Max weekly pool").
- **Variants.** Anthropic already defaults to `high`, so the Claude rungs need
  no `--variant` (`max` exists for a deliberately larger thinking budget).
  OpenAI defaults to the model's built-in effort, so the `gpt-5.6-sol` rung
  states `--variant high` explicitly; Astra's own default effort is left
  alone. An unrecognized variant name is **silently ignored** (verified — no
  error), so a typo degrades the run invisibly.
- **The OpenRouter rung excludes `anthropic` / `claude` / `openai` / `gpt`
  slugs** — paying per token for a model you already hold a subscription to is
  the mistake this rule exists to prevent. Prefer
  `deepseek/deepseek-v4-flash`, then `deepseek/deepseek-v4-pro`.
- Resolve exact `provider/model` slugs at runtime (`opencode models`) — the
  catalog moves; don't hard-code stale ones. `gpt-6-astra` needs opencode
  >= 1.18.29; on an older build it is absent from the catalog and the rung is
  simply unavailable. On a mid-task error drop **one** rung and retry; the
  final report names the provider/model actually used.

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
- OpenAI reports a real remaining %. Under ~15% treat the OpenAI rungs as gone
  and skip past them instead of fighting the human for the last slice.
- **Astra is the expensive tenant of the OpenAI pool.** ChatGPT Pro 5x meters
  it at roughly 25-225 messages per 5h window, and that window is shared with
  OpenCode's `build` primary, its `debugger` subagent, and Hermes' own
  researcher and creator profiles (both Astra-first). Treat an Astra rung as
  contended by default: when QuotaCheck is already low, prefer descending over
  retrying it.
- **Every run draws on BOTH subscription pools regardless of `--model`** —
  OpenCode's own subagents are pinned to their own models in frontmatter
  (2026-09-05 split: explore-medium/high/max, worker, reviewer and
  reviewer-deep on Claude Sonnet 5 / Opus 5; explore-spark/small, verifier,
  the search tiers, ui-review, ux-persona and compaction on the OpenAI pool;
  debugger on GPT-6 Astra — the same weighted rate as a Build run). A Claude
  run is never purely Claude and an OpenAI run is never purely OpenAI, so
  headroom on both pools matters on every rung.
- **Primaries carry pinned defaults** (`plan`/`review`/`debug`/`explain` =
  `anthropic/claude-fable-5-1`, `build` = `openai/gpt-6-astra`), which is why
  the ladder passes `--model` explicitly: the CLI flag beats the agent's
  default, and an omitted flag silently runs whatever is pinned.
- `claude auth status` is never the gate.

## UnitCycle

The build choreography for every released unit: ground the unit's
plan context, decompose into phases, confirm, build, close. The
pacing contract (kernel <Runtimes>) bounds each turn to the released
unit(s); at the boundary of the released set, close the unit, report,
and wait for the next release.

### Grounding — where the unit's plan context comes from

- **Wave unit** (`Base session: <id>` + the Wave to implement): the
  assistant's approved plan session IS the base — verify it is
  visible here (`opencode session list` in the worktree), fork the
  unit's decompose straight from it, and never re-plan what it holds.
  Not visible (wrong project key, pruned) → ask; do not silently
  re-plan.
- **Purpose unit** (`Issue: #n`): no base session — the Issue text is
  the spec. Read it first (`gh issue view <n> --comments`); the
  unit's decompose is a fresh plan run grounded on the Issue and the
  current worktree (see the cycle below).
- **Whole small job** (no base, no Issue): the brief itself grounds
  the unit; the job runs as ONE unit through the same cycle. If the
  decompose reveals the job is really several units, that is a
  granularity finding — checkpoint and report; the assistant
  re-plans. Never self-generate a multi-unit outline.
- **An approved Wave outline exists only as text** (in the brief / a
  worktree file): seed a base from its unit lines verbatim —

  ```text
  opencode run --auto --agent plan --title "waves: <goal>" --model <m> \
    'This outline is already approved — hold it as the plan to implement,
     do not re-plan: <the approved units, verbatim>'
  ```

  **Seed ONLY the coarse unit lines.** When the approved deliverable
  is a detailed plan document (a long PLAN.md, a spec with per-file
  steps), do not paste it wholesale into the base — reference it by
  path and let the unit's decompose read it (<DetailedPlanRule>). A
  base bloated with phase detail poisons every fork taken from it.
- Record every base / plan-run id (`opencode session list`) in your
  replies. The **durable handoff is the Issue/outline text + git**;
  the session id is just the resume handle.

### The cycle — per released unit

Decompose → confirm → build → close. **OpenCode owns the phase
granularity; you judge it, you don't dictate it.** The cycle is
mandatory for every unit — no risk level, schedule pressure, or
already-detailed plan waives it (<DetailedPlanRule>).

1. **Decompose** — a read-only plan run producing the unit's phases.
   Wave unit — fork the base:

   ```text
   opencode run --auto -s <base-id> --fork --agent plan --model <m> \
     'Decompose Wave N — "<unit intent>" — into phases, grounded on the
      current worktree (prior units are already committed here). Phases
      only, no code. If something material is undecided, say so.'
   ```

   Purpose unit — fresh plan run, no fork:

   ```text
   opencode run --auto --agent plan --model <m> \
     'Decompose the implementation of Issue #<n> into phases, grounded
      on the Issue (gh issue view <n>) and the current worktree. Phases
      only, no code. If something material is undecided, say so.'
   ```

2. **Confirm — the GO gate** — read the phase breakdown and
   sanity-check it: does it match the unit's intent, stay inside the
   granted scope, and hang together? This is your review of
   OpenCode's plan — judge it, don't re-granularize it.
   - Off target / too broad → correct via `run -c '<redirect>'`.
   - Reveals a need outside the grant (a dependency, a push, an
     architecture/public-API change) → **checkpoint-then-block** (core
     <CheckpointThenBlock>) — the decomposition's approval does not
     cover a new grant.
   - The plan run says something material is undecided (the decompose
     prompts' "say so" line exists exactly for this) → a **spec-gap
     finding** back to the assistant (`Q<n>` / report), never a local
     decision — the spec, not your judgment, must determine the unit.
   - Accepted → report `<unit ref> phases confirmed: <the phases, one
     line>` (e.g. `Wave 2 phases confirmed:` / `Issue #12 phases
     confirmed:`) with the plan-run id in your reply. This line is
     the **gate artifact**: no build fork for the unit may start
     until it exists. If you cannot point at a phases-confirmed line
     for the unit, you are not cleared to build it.

3. **Implement** — fork the confirmed phase plan to build, wrapped per
   <PermissionBridge>:

   ```text
   OPENCODE_PERMISSION='<per PermissionBridge>' opencode run --auto \
     -s <phase-plan-id> --fork --agent build --model <m> \
     'Implement these phases for <unit ref>: <the confirmed breakdown>.
      Prior units are committed — build on them. If something material is
      undecided, stop and state it in your final message instead of
      guessing.'
   ```

   Follow-ups within the unit: `opencode run -c '<follow-up>'` (or
   `-s <build-fork-id>`). OpenCode handles the phases' own
   sub-steps/subagents; **don't micromanage its internals** — judge the
   result by your own verification (`references/verify.md`).

4. **Close the unit** — verify per `references/verify.md` → commit
   (sub-commits per phase are fine; delivery writes per
   `references/delivery.md` when the grant covers them) → report with
   ids (`[base <id> | <unit ref> <build-fork-id> | phases: …]`) →
   discard the unit's forks — the next unit starts from a fresh plan
   context, never a carried session (that is how cost and compaction
   creep back in) — then **stop at the released set's boundary** and
   wait for the next release (continue only under an explicit batch
   grant).

Grounding: prior units are committed, so each unit's decompose/build
reads the **current worktree** for context — grounding travels
through git, not through session lineage. You only ever track two
live ids: the grounding session (base or the unit's plan run) and the
current build fork.

Prompt scoping rule: every decompose/build prompt names ONE unit,
never the whole goal — narrow scope is what buys quality.

Escape hatch: if fork mechanics misbehave, commit the outline as
`PLAN.md` in the worktree and run the unit as a fresh session that
reads `PLAN.md` + the current code — and record in your reply that
the escape hatch is in use. The decompose → confirm gate still
applies: the fresh session starts as a plan run deriving the unit's
phases, confirmed before its build run.

### DetailedPlanRule — a detailed plan never waives decompose

An approved artifact that already carries phase-level detail (a
reviewed PLAN.md, a spec with per-file steps, a richly specified
Issue body) is the situation MOST likely to tempt you into skipping
the plan run and pasting its steps straight into a build prompt.
Don't — that is double harm: it violates "prompt intent, don't paste
procedure", and it ships a plan that was written before the current
worktree existed (prior units have landed since; the plan may have
drifted).

Instead, change the unit's decompose prompt to a **derive** variant:

```text
opencode run --auto -s <base-id> --fork --agent plan --model <m> \
  'Derive the phase breakdown for <unit ref> from the approved plan at
   <path/attachment>, grounded on the CURRENT worktree (prior units are
   committed). Flag every point where the plan and the code have
   drifted. Phases only, no code.'
```

(For a purpose unit the same derive prompt runs as a fresh plan run
against the Issue body.) OpenCode still produces the breakdown; you
still confirm it and write the gate artifact. The step costs one
short plan run and buys a fresh grounding check on a stale document —
it is never redundant.

## InspectionPrimaries

Fresh sessions, not forks — usable from any mode (assess uses them
standalone; implement interposes them where a unit warrants it):

- `opencode run --auto --agent review --model <m> '<review this worktree's
  diff …>'` — after a unit or before handing back; unbiased eyes, read-only
  by its own permissions (plain `--auto`, no env).
- `opencode run --auto --agent debug --model <m> '<symptom, repro …>'` —
  stubborn bugs; read-only diagnosis. Apply the fix in the unit's build fork
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

**Issue/board writes are never granted** — GitHub bookkeeping belongs to
the orchestrator. Every build run therefore also carries:

- bash: `"gh issue create*":"deny","gh issue edit*":"deny","gh issue comment*":"deny","gh issue close*":"deny","gh project *":"deny"`
- `<tool-denies>` — OpenCode's custom GitHub Projects tools are `allow` in its
  global config, so deny the write ones by name:
  `"github_project_create":"deny","github_project_field_ensure":"deny","github_project_item_add":"deny","github_project_item_set":"deny","github_project_item_note":"deny","github_project_item_promote":"deny","github_project_view_ensure":"deny","github_project_issue_link":"deny","github_project_issue_develop":"deny"`
  (`github_project_item_list` stays allowed — read-only).

Reading (`gh issue view/list`, `gh pr view/diff`,
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
3. **Restart the unit** — the breakdown was wrong, not the build: re-run
   decompose with what you learned, then build fresh.

Never argue with a degraded session for more than one redirect — re-forking
is cheaper than persuasion. Record what was discarded and why in your
reply so a later resume doesn't repeat it.

## Pitfalls

- Supervising a run with short poll cycles — 180 s waits, status-check calls
  between waits, per-cycle log reads — instead of RunExecution's foreground
  default or full-length `wait(600)` slices; polling is what starves
  `max_turns`.
- Carrying one session across a unit boundary (cost + compaction creep) —
  ground each unit's fresh plan context on git; or the opposite:
  restarting from scratch after an interruption instead of rejoining the
  recorded fork (`-s <fork-id>` from the ids in your replies).
- Dictating the phase granularity instead of judging OpenCode's decomposition
  — or skipping the confirm step and building a bad breakdown.
- Starting a build fork without that unit's reported `phases confirmed` line —
  the gate artifact is the license to build; "the plan was already detailed"
  is the classic rationalization, answered by <DetailedPlanRule>.
- Writing the phase procedure into the build prompt yourself because the
  approved plan spelled it out — that skips decompose + confirm and pastes
  a possibly-stale document over the current worktree.
- Restating the injected layer in prompts — role preambles, "read-only!"
  to a plan agent, denies the bridge already enforces, skill content, the
  repo's own check commands (<PromptContract>): insurance prose that only
  buries the constraints the prompt actually has to carry.
- Bare `opencode run` without the PermissionBridge env — edits get silently
  auto-rejected and the model "completes" around them.
- `OPENCODE_PERMISSION='{"*":"allow"}'` — the merge would bury the global
  protective denies; set only `edit`/`bash` keys plus the Authority denies.
- Ignoring `auto-rejecting` lines or unstated-assumption text in run output —
  that is OpenCode's only voice (QuestionBridge).
- Un-recorded base / fork ids — ids belong in every per-unit report.
- Bloating a base with phase detail (keep it the coarse unit outline), or
  prompting "the whole goal" in one unit instead of that unit only.
- Running past the released set — the next unit needs a release or an
  explicit batch grant (kernel <Runtimes>).
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
- Each unit's grounding matches its kind (base fork for a Wave, a
  fresh Issue-grounded plan run for a purpose, the brief for a whole
  small job); grounding and fork ids are recorded in the replies.
- Each unit ran decompose (plan run) → confirm → implement (build fork),
  and a reported `<unit ref> phases confirmed` line exists for every unit
  with a timestamp BEFORE its build fork (the gate artifact); detailed
  approved plans went through the derive variant (<DetailedPlanRule>),
  never straight to build; no session crossed a unit boundary; work
  stopped at the released set's boundary; run outputs were read for
  open questions (QuestionBridge).
- Every build run carried the matching PermissionBridge env + `--auto`
  (including the issue/board tool denies).
- Prompts carried only the delta per <PromptContract>: no role preambles,
  no restated permissions/denies/skill content/repo conventions; scope
  boundaries and the QuestionBridge closer present where required.
