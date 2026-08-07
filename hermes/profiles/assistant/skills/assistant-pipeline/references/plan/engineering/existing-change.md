# Existing-repo change — plan recipe

Feature add, bug fix, refactor, performance — the repo already exists,
so no bootstrap; grounding is everything. Do not design in chat what
the plan session reads better from the worktree.

## Brief — fix before the session

- **Goal & done criteria** — observable behavior, named checks/tests.
- **Scope boundaries** — `scope:` / `do not touch:` lines for the
  Authority grant; call out anything irreversible (migrations, data).
- **Change class** — feature / fix / refactor / performance. This is
  routing information for the session, not methodology you narrate:
  the plan agent loads its own approach skills (new-feature, refactor,
  rebuild-migration, performance) against the live code.
- **Issue linkage** — `Issue: #n` exists → the Issue text is the
  outline; a base session is only needed when the Issue is coarser
  than Waves.

## Wave prompt — add to the base-session prompt

> Change to an existing codebase; class: <feature|fix|refactor|
> performance>. Ground every Wave in current code paths (name files/
> modules). Refactor: behavior-preserving steps under tests.
> Performance: baseline measurement is Wave 1. Keep out-of-scope
> cleanup out of the outline.

## Expected outline — inspection standard

- Waves reference actual code locations, not generic phases.
- Fix/refactor outlines stay inside the stated scope; performance
  outlines start with measurement, not optimization.
- Red flags: rewrite Waves smuggled into a "refactor"; scope creep
  ("also modernize X"); a fix outline with no failing-test Wave.

## Defaults

- Authority `A1`; `A2` when the user wants the PR flow; `A3` only for
  sanctioned dependency work.
- Small settled fixes skip the session entirely (index invariant) —
  state intent, straight to Execute.
- Verification: the repo's own checks/tests actually run per Wave;
  regressions gate on the named done criteria.
