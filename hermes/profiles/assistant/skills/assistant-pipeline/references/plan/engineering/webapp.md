# Web app — plan recipe

Stateful: data model, auth, environments. The expensive mistakes are
schema and auth decisions made implicitly, so they are fixed in the
Brief and land in the earliest units. Webapps default to
**purpose-tracked execution** — an epic with purpose sub-issues sized
1–3 PRs each — because the work outlives single sessions.

## Brief — fix before the session

- **Domain & data model sketch** — the core entities and relations in
  a few lines; enough to judge scope, not a schema.
- **Auth** — who logs in, provider (none / OAuth / magic link), roles.
- **External services** — APIs, payments, storage; their credentials
  go through the Keychain, never `.env`.
- **Environments & hosting** — the hosting platform decides the
  starter derivative; prod/dev split, database hosting.
- **Scale & budget posture** — personal tool vs public product changes
  how much hardening the decomposition should carry.
- **Done criteria** — the user journeys that must work end-to-end.

## Decomposition prompt — add to the base-session prompt

> Stateful web app. Split into PURPOSES sized 1–3 PRs each. Early
> purposes fix foundations: schema/data model, auth, environment +
> deploy skeleton. Later purposes are vertical slices (one user
> journey each), tests included per slice. This decomposition will
> be registered as a GitHub epic + sub-issues.

## Expected decomposition — inspection standard

- Foundation purposes (schema, auth, deploy skeleton) precede feature
  purposes; features are vertical slices, each independently
  verifiable and honestly sized 1–3 PRs.
- Red flags: UI-first decompositions with the data model deferred; a
  single "backend" mega-purpose; slices with no named verification; a
  purpose that cannot land in 3 PRs (split it further).

## Registration & handoff — yours

Per the index: you draft the epic + purpose split in your own plan
session, the user approves it once, and you register it via `gh`
(sub-issues linked to the epic, the user's Roadmap board in sync).
Execution then hands the engineer **one `Issue: #n` at a time** — the
Issue text is the spec; no base session rides along. At `A2` a
multi-PR purpose grows as a stack, one layer at a time.

## Defaults

- New repo: the starter derivative nearest the hosting decision
  (frontend-platform vs service-platform), discovered per
  `bootstrap.md` — bootstrap first.
- Authority `A2` (PR per slice is the norm); `A3` when dependency
  work is foreseeable. `scope:` / `do not touch:` still mandatory.
- Verification: per-slice tests actually run, plus an end-to-end
  check of the slice's journey on a running instance.
