# Assess mode — read-only findings

Loaded when the brief wants **knowledge, not changes**: the deliverable is
facts, a feasibility verdict, a root-cause diagnosis, or a review — never
code. Absorbs the former orient and advisory modes (their openers still
route here). Four branches share the same floor rules; pick by what the
brief asks for:

| Branch | The brief asks | Deliverable |
| --- | --- | --- |
| **facts** (ex-orient) | "what IS the state of the repo / environment / GitHub?" — no judgment requested | ground-truth report |
| **feasibility** (ex-advisory) | "is this buildable? shape? risk? size?" — a plan consultation | verdict + shape + risks + size |
| **diagnosis** | "why is this broken / what's the root cause?" — no fix requested | evidence-backed cause + fix direction |
| **review** | "evaluate this PR / diff / implementation" | verdict + concerns with evidence |

Intent mapping (core <IntentTriage>): `investigate` → facts or feasibility;
`diagnose` → diagnosis; `review` → review.

## Floor rules (all branches)

- **Read-only.** No commits, edits, installs, scaffolding, repo creation, or
  GitHub writes. An Authority line never authorizes a write from an assess
  task. Throwaway notes in a scratch dir are fine; the worktree stays clean.
- **Time-boxed.** Answer from inspection (git, gh, reading files). Read-only
  OpenCode primaries (`references/opencode.md` <InspectionPrimaries>, plain
  `--auto`, no permission env) are fine for heavier recon — model per
  <ModelRouting> — but only when a repo exists; never on an empty workspace.
- **Assume, don't block, by default.** The caller is usually waiting inside a
  live loop; a labeled assumption beats a block round-trip. Block (core
  <CheckpointThenBlock>) only when every plausible reading changes the
  verdict.
- **Environment claims need recipes.** If the verdict turns on what OpenCode
  or the machine can do here, load `opencode-env` / `machine-env` and confirm
  with their inspection recipes — an unverified capability claim is the one
  assumption you may not label and move past.
- Findings that reveal the task was mis-scoped (assess asked, implement
  needed) do NOT silently switch mode — report the mismatch as a finding;
  the orchestrator dispatches the real task.

## Branch: facts (ground truth)

The first thing to settle is **whether a repo exists** — every downstream
OpenCode slice is meaningless without one. No repo → report the bootstrap
signal (below) and stop; never scaffold or clone from assess.

When a repo exists, gather (skip what's irrelevant to the ask): repo state
(`git status -sb`, `git log --oneline -5`), stack & structure (manifests),
conventions (AGENTS.md / README / lint config / commit style from `git log`),
build/test/run/lint commands (manifests, CI config), GitHub state
(`gh pr list`, `gh issue list`, `gh run list` — best-effort), and — only when
asked — toolchain/environment via `machine-env` / `opencode-env` recipes.

```markdown
## Repo
<name/path, or "none — bootstrap needed">, branch <cur>@<default>, <clean|dirty>
## Stack & layout
<languages, framework, package manager, key dirs, entry points — 3-6 lines>
## Conventions
<AGENTS.md/README rules, lint/format, commit convention — what a builder must honor>
## Build / test / run
<the commands, verbatim>
## GitHub
<open PRs / issues / CI status — or "n/a">
## Notable
<risks, oddities, half-done work — anything a plan should know>
```

**Bootstrap signal (no repo):** report the state (greenfield vs
remote-exists-not-cloned), the environment relevant to a stack choice, and
the options for the decider (`clone <remote>` / `starter: <candidates>` /
`greenfield`). Ground the `starter:` option with the `starter-catalog`
technic skill — run its discovery + fit-evaluation recipes and report 2-3
candidates (lineage, platform fit, freshness) with a marked
recommendation; never name candidates from memory. The decision and the
actual clone/scaffold belong to the assistant + an implement task's
bootstrap branch (`references/implement.md`) — assess stops at the report.

## Branch: feasibility (plan consultation)

The assistant is mid-plan with the user and needs a fast verdict at the
**feasibility altitude** — not implementation altitude. Restate the
decision the plan is waiting on in one line, inspect, then:

```markdown
## Question
<the decision the plan is waiting on, one line>
## Verdict
<buildable / buildable-with-caveats / not-as-stated — one line>
## Shape
<how it would be built: components touched, integration points, 3-6 lines>
## Risks
<what could sink or reshape it, with where in the code the risk lives>
## Rough size
<PR-sized-unit count estimate, e.g. "2-3 units: foundation, feature, tests">
## Assumptions
<what you assumed instead of asking, labeled>
```

If the question genuinely cannot be answered without building, that IS the
answer ("needs a spike"). A **Wave outline** is not a feasibility
deliverable — planning belongs to the assistant's own OpenCode plan
session; say so and give the verdict inline.

## Branch: diagnosis (root cause, no fix)

The bugfix discipline without the fix: the deliverable is a cause someone
else (or a later implement task) can act on.

1. **Reproduce first.** Drive the real entry point until the symptom shows;
   record the exact steps/commands and observed vs expected. Cannot
   reproduce → that is the finding (report what you varied).
2. **Localize** — narrow by evidence, not intuition: read the failing path,
   bisect history if cheap (`git log` on the touched area), add temporary
   instrumentation only in a scratch copy. For stubborn cases use a
   read-only debug session (`references/opencode.md` <InspectionPrimaries>)
   and judge its hypothesis against your own repro.
3. **Name the mechanism** — the cause states WHY the code produces the
   symptom (file:line + the causal chain), not just where it hurts.

```markdown
## Symptom
<observed vs expected, one line>
## Repro
<exact steps/commands that show it — someone else can replay this>
## Root cause
<file:line + the mechanism, evidence-backed>
## Fix direction
<smallest viable fix + risks; alternatives if material — NOT a patch>
## Assumptions / not ruled out
<labeled>
```

## Branch: review (evaluate someone's change)

Input: a PR number/URL, branch, or diff named by the body. Read the change
AND its requirement (Issue, task description) — a review without the
requirement is style commentary.

1. `gh pr view <n> --comments`, `gh pr diff <n>` (or `git diff <range>`);
   read the linked Issue/criteria.
2. Judge: does it satisfy the requirement (verify.md V1 lens)? Test
   adequacy (V3 lens — do assertions pin the right expectations)?
   Conventions, risk hotspots (V2 lens)? Run the suite locally when cheap.
3. Every concern carries evidence (file/line, failing scenario) and a
   severity; the verdict is justified, not vibes.

```markdown
## Verdict
<approve / request-changes / needs-discussion — one line why>
## Concerns
1. <severity> <file:line> — <what + why it matters + suggested direction>
## Covered well
<what is solid — reviewers who only complain get tuned out>
```

Deliver the review as the task report. Posting it to the PR is a GitHub
write — only with an explicit grant line (e.g. `pr-review: write`), and then
via OpenCode (`references/delivery.md`), never raw `gh`.

## MEMORY.md

Persist only durable, cross-job repo facts (build/test/lint commands,
layout, environment quirks, commit convention) so later jobs start
informed. Never job state or transient report bodies — those live in the
session dialogue.

## Report

- Final report = the branch's deliverable (or its summary + the file path
  of the full write-up).
- The reply/summary = 1-2 plain sentences carrying the headline (state /
  verdict / cause / review verdict).
- Name the machine-consumable facts plainly at the end (e.g. "repo: none —
  bootstrap needed") so the orchestrator can act without re-reading.

## Pitfalls

- Writing anything — assess is read-only; the fix belongs to a bugfix job,
  the scaffold to implement's bootstrap branch.
- Branch drift: facts drifting into judgment, feasibility into solution
  design, diagnosis into patching, review into rewriting. Report at the
  asked altitude.
- A diagnosis without a repro, or a cause stated as a location without a
  mechanism.
- A review that ignores the requirement, or posts to the PR without a grant.
- Burning the time box on OpenCode runs when direct reads answer it.
- Blocking on detail an assumption would cover — label and proceed.
- An unlabeled assumption load-bearing under the verdict.

## Verification

- Nothing was committed, edited, or installed; `git status` unchanged.
- The deliverable follows its branch format; assumptions labeled; claims
  carry evidence (commands, file:line, repro output).
- diagnosis: the repro is replayable from the report alone. review: every
  concern has file:line + severity; the requirement was read.
- facts: the repo-exists question was answered first; no-repo produced the
  bootstrap signal with options, not an OpenCode run.
- Runtime stayed inside the time box.
