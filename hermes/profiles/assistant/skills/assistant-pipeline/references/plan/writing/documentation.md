# Documentation — decision surface

Text readers scan to get something done: README, manuals, reference
pages, runbooks, onboarding guides. Flat scannable structure is
correct here — the writer's norms stack enforces it; you decide what
the documentation covers and for whom.

Writer type `documentation` · QA `prose` · units: whole small job
for a single document; piece units per file for a doc set.

## Fix before release

- **Reader tasks** — the concrete things a reader is trying to do
  when they open this document; every section must serve one. Docs
  without a named reader task document the author's knowledge, not
  the reader's need.
- **Doc shape** — README (what + who-for in the first screen) /
  how-to (task steps) / reference (lookup tables) / explanation
  (design rationale) — a set mixes shapes as separate files, not
  one hybrid wall.
- **Scope boundary** — what is documented and what is explicitly
  NOT (versions, platforms, audiences out of scope); "document
  everything" is a granularity finding.
- **Ground truth sources** — the real commands, configs, and
  behaviors being documented (verified facts in the brief; for a
  repo, the engineer's assess output is the ground truth — the
  writer documents, it does not discover).
- **Terminology set** — the project's canonical names; where a
  glossary already exists, paste it.
- **Destination & maintenance** — where the files land (a repo path
  means the QA-passed text becomes a part of an engineering unit —
  the writer never commits), and who updates the doc on what
  trigger.

## Defaults

- Doc sets decompose one piece unit per file, entry-point file
  first (it fixes shared structure and terminology).
- README opener judged by a stranger in ~30 seconds: what this is,
  who it serves, first action.
- Runbooks: every step carries its observable result and its
  failure branch.

## Red flags

- Narrative walls where a table or task list belongs.
- Documentation briefed from memory instead of verified ground
  truth — drift by design.
- A "README update" that is really a doc-set restructure —
  granularity finding.
- Docs planned with no maintenance owner — stale on arrival.
