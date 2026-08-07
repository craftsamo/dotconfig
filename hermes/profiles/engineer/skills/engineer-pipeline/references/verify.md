# Verification — never trust the self-report (engine)

Load this whenever OpenCode produced something you are about to accept —
every implement unit close, every assess deliverable that leaned on an
OpenCode run. OpenCode does the work; **you own the judgment that it is
right**. A completion message is a claim, not evidence.

Six checks, V1-V6. Run the ones the intent profile (below) marks required;
record commands + outcomes as you go — they become the report's
`verification` evidence (see `references/delivery.md`).

## V1 — AcceptanceCheck (deliverable vs the task)

Re-read the task body's Goal / Done criteria (and the Issue, if the work is
Issue-driven) AFTER the work sits in the worktree. For each criterion: where
is it satisfied, and how do you know? A criterion you cannot point at is not
done — no matter what the run output said. Scope check in the same pass:
nothing material the body asked for is missing, nothing significant beyond
the ask crept in.

## V2 — DiffReview (quality and boundaries)

Read the actual diff: `git status --short`, `git diff` (or `git diff
<base>..HEAD`), and open the changed files around the changes.

- Out-of-scope files? (`scope:` / `do not touch:` lines are hard limits.)
- Lockfile / manifest changes without a dependency grant → revert or block.
- Conventions honored (repo lint/format rules, naming, AGENTS.md)?
- Risk hotspots read line-by-line (auth, migrations, deletion paths,
  concurrency).

For an unbiased second pass on medium/high-risk diffs, interpose a fresh
review session (`references/opencode.md` <InspectionPrimaries>) — then judge
its findings yourself; delegation does not transfer the responsibility.

## V3 — TestAdequacy (are the expectations RIGHT?)

Green is not the bar — **correct expectations** are. Read the tests OpenCode
wrote or touched:

- Does each new behavior have a test that would FAIL without the change?
  (Spot-check the critical one: revert mentally — would this assertion catch
  it?)
- Do assertions encode the task's Done criteria, or just mirror what the
  implementation happens to output? (Snapshot-updated-to-match is the classic
  false green.)
- Were existing assertions weakened, skipped, or deleted to get to green?
  (`git diff` on test files — any loosened expectation is a finding.)
- Edge cases the criteria imply (empty, error, boundary) present?

A suite that passes with wrong expectations is worse than a missing test —
it certifies the bug.

## V4 — MechanicalChecks (run them yourself)

Run the repo's own commands — tests, build, lint/format, typecheck — from the
repo's conventions (manifest scripts, CI config, MEMORY.md). Prefer scripts
and wrapper CLIs (`npm test`, `cargo test`, `./scripts/…`); never inline
interpreters (`bash -c`, `python3 -c` — the worker guard fails them). Targeted
first (the changed area), full suite before handing back when the repo has
one. If nothing is runnable, say so explicitly in the report and name what
you checked instead.

## V5 — BehaviorCheck (run the thing)

Exercise the changed behavior as a user would, not as a code reader:

- CLI/service: invoke the real entry point (run the command, curl the
  endpoint, run the script) against the Done criteria's scenario.
- Web UI: rendered output is the ground truth — drive a browser-based check
  through OpenCode (its UI-verification capabilities are catalogued in
  `opencode-env`) and demand concrete evidence (what was rendered, screenshot
  paths) in its output; code-only inspection is not UI verification.
- Bug fixes: replay the ORIGINAL repro steps and watch them fail to
  reproduce.

When behavior genuinely cannot be exercised (no runtime here, external
service), name the gap and what stands in for it — never imply it ran.

## V6 — DeliveryCheck (git and GitHub state)

After OpenCode's git/GitHub operations (it executes them — you audit them,
see `references/delivery.md`):

- `git log` — commits are atomic (one concern each), messages match the
  repo's own convention, no WIP/fixup noise left for a handoff branch.
- `git show --stat` per commit — no stray files (editor droppings, `.env`,
  logs, secrets), no unrelated churn.
- Branch is the granted one; nothing touched default/main.
- A2+, after push/PR: the PR exists with the intended base/head, body carries
  `Closes #n` when Issue-driven, CI status checked (`gh pr view`, `gh pr
  checks`), review threads answered with commit refs.
- Rebase/history rewrites (when granted): linear history achieved, no
  dropped commits (`git range-diff` or before/after log comparison).

## Intent profiles — what each kind of work must pass

`REQ` = required, `–` = usually skippable (judgment stands):

| Intent | V1 | V2 | V3 | V4 | V5 | V6 | Intent-specific gate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| feature | REQ | REQ | REQ | REQ | REQ | REQ | the NEW path exercised end-to-end (V5) |
| bugfix | REQ | REQ | REQ | REQ | REQ | REQ | repro recorded BEFORE the fix; replay fails to reproduce AFTER; a regression test pins it |
| refactor | REQ | REQ | REQ | REQ | – | REQ | full suite green BEFORE and AFTER; zero behavior/public-API change in the diff |
| rebuild | REQ | REQ | REQ | REQ | REQ | REQ | cutover criteria from the task met; data parity / old-path evacuation verified |
| perf | REQ | REQ | – | REQ | REQ | REQ | baseline measured BEFORE, re-measured AFTER under the same conditions; target met, suite not regressed |
| deps | REQ | REQ | – | REQ | – | REQ | lockfile resolves to the patched version; build + tests pass; no unrelated bumps |
| bootstrap | REQ | – | – | – | – | REQ | empty-target guard ran; initial commit exists; remote/push only under B2; pj untouched |
| investigate / diagnose / review | REQ | – | – | – | – | – | worktree untouched (`git status` clean); every claim carries evidence (file/line, repro output) |

The profile is a floor, not a ceiling — escalate checks when the diff's risk
warrants it regardless of intent.

## Pitfalls

- Accepting "all tests pass" without reading what the tests assert (V3) —
  the most common false green.
- Verifying by re-reading the code instead of running it (V5) — reading
  confirms intent, not behavior.
- Skipping V6 because "OpenCode's git skills are good" — they are; audit
  anyway. Trust the executor, verify the outcome.
- Running verification inside the same OpenCode session that built the
  change — its context is invested in success; verify from YOUR shell (V4)
  or a fresh session (V2).
- A bugfix verified only by the new test, never by replaying the original
  repro.
- A refactor "verified" against a suite that was already red — record the
  BEFORE state first.
- Letting evidence live only in your head — every check lands in the report
  (`references/delivery.md`).

## Verification (of this engine's own use)

- The intent profile was identified and its REQ checks all ran (or each skip
  is named + justified in the report).
- Commands + outcomes recorded; failures led to fixes or blocks, never to
  silent acceptance.
- The intent-specific gate passed (repro replay, before/after suite,
  baseline re-measure, lockfile resolution — as applicable).
