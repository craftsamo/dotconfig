# Existing-repo change — plan recipe

Feature add, bug fix, refactor, performance — the repo already
exists, so no bootstrap; grounding is everything. Do not design in
chat what the plan session reads better from the worktree.

## Unit choice — first decision

- **`Issue: #n` already exists** → the Issue IS the unit; hand it
  over as-is. Only when the Issue is coarser than one handoff do you
  split it first — draft the purpose split in your plan session, get
  approval, register the sub-issues through an OpenCode run in the
  repo.
- **Issue-tracked repo, or the change spans sessions** → purposes
  (epic + sub-issues sized 1–3 PRs), as in `webapp.md`.
- **Small linear change** → Waves from a base session.
- **Settled fix** → a single unit, straight to Execute (index
  invariant) — no session, no Issue ceremony.

## Brief — fix before the session

- **Goal & done criteria** — observable behavior, named checks/tests.
- **Scope boundaries** — `scope:` / `do not touch:` lines for the
  Authority grant; call out anything irreversible (migrations, data).
- **Change class** — feature / fix / refactor / performance. This is
  routing information for the session, not methodology you narrate:
  the plan agent loads its own approach skills (new-feature,
  refactor, rebuild-migration, performance) against the live code.

## Decomposition prompt — add to the base-session prompt

> Change to an existing codebase; class: <feature|fix|refactor|
> performance>. Ground every unit in current code paths (name files/
> modules). Refactor: behavior-preserving steps under tests.
> Performance: baseline measurement is the first unit. Keep
> out-of-scope cleanup out of the decomposition.

## Expected decomposition — inspection standard

- Units reference actual code locations, not generic phases.
- Fix/refactor decompositions stay inside the stated scope;
  performance ones start with measurement, not optimization.
- Red flags: rewrite units smuggled into a "refactor"; scope creep
  ("also modernize X"); a fix decomposition with no failing-test
  unit.

## Defaults

- Authority `A1`; `A2` when the user wants the PR flow; `A3` only
  for sanctioned dependency work.
- Verification: the repo's own checks/tests actually run per unit;
  regressions gate on the named done criteria.
