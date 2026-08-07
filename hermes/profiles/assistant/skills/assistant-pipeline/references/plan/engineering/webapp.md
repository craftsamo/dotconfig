# Web app — plan recipe

Stateful: data model, auth, environments. The expensive mistakes are
schema and auth decisions made implicitly, so they are fixed in the
Brief and land in the earliest Waves. Webapps default to issue-tracked
execution — epic + sub-issues — because the work outlives single
sessions.

## Brief — fix before the session

- **Domain & data model sketch** — the core entities and relations in
  a few lines; enough to judge scope, not a schema.
- **Auth** — who logs in, provider (none / OAuth / magic link), roles.
- **External services** — APIs, payments, storage; their credentials
  go through the Keychain, never `.env`.
- **Environments & hosting** — the hosting platform decides the
  starter derivative; prod/dev split, database hosting.
- **Scale & budget posture** — personal tool vs public product changes
  how much hardening the outline should carry.
- **Done criteria** — the user journeys that must work end-to-end.

## Wave prompt — add to the base-session prompt

> Stateful web app. Early Waves fix foundations: schema/data model,
> auth, environment/deploy skeleton. Later Waves are vertical slices
> (one user journey each), tests included per slice. Note the outline
> will be decomposed into a GitHub epic + sub-issues.

## Expected outline — inspection standard

- Foundation Waves (schema, auth, deploy skeleton) precede feature
  Waves; features are vertical slices, each independently verifiable.
- Red flags: UI-first outlines with the data model deferred; a single
  "backend" mega-Wave; slices with no named verification.

## Issue decomposition — default, not optional

Per the index invariant: the engineer session drafts epic +
sub-issues from the approved outline (draft-only), the user approves,
**you** register them via `gh` and keep the board in sync. Hand over
`Issue: #n` per slice thereafter.

## Defaults

- New repo: the starter derivative nearest the hosting decision
  (frontend-platform vs service-platform), discovered per
  `bootstrap.md` — bootstrap Wave 0.
- Authority `A2` (PR per slice is the norm); `A3` when dependency
  work is foreseeable. `scope:` / `do not touch:` still mandatory.
- Verification: per-slice tests actually run, plus an end-to-end check
  of the slice's journey on a running instance.
