# Engineering — plan

Every engineering plan, whatever the deliverable, ends in the same goal
state: an OpenCode **base plan session** in the repo holding the
approved Wave outline, plus the sanctioned Authority. The engineer
resumes/forks that session per Wave to implement — the session, not a
prose summary, is the handoff, so the outline stays grounded and
nothing is lost in translation.

## Invariants (apply to every leaf)

- **The assistant manages repos; the engineer only works inside them.**
  Repo creation, ghq clone, workspace symlinks, `pj` registry, Issue
  registration, and merges are yours, through your own `gh`/`ghq`/`pj`.
  The engineer never bootstraps a repo and never merges.
- **Locate the repo** — `pj show --id <Group>` → the
  `~/Workspaces/Projects/<Group>/github/<repo>` symlink (a `~/ghq`
  clone). No repo yet → `bootstrap.md` is Wave 0; the base session
  comes after it, inside the new repo.
- **Base plan session** — a read-only plan run in the repo:

  ```bash
  cd <repo> && opencode run --auto --agent plan --title "waves: <goal>" \
    'Split this goal into WAVES only — coarse milestones and their
     dependency order, one line each. No phase/unit detail.
     <goal, constraints, done criteria — from the leaf's wave prompt>'
  ```

  Recover the id (`opencode session list`) and hand it over as
  `Base session:`. Check the returned outline against the leaf's
  expected shape before presenting it — a malformed outline is re-run,
  not hand-patched in chat.
- **One approval** — present the Wave outline in plain language (what
  lands, in what order, what it costs) plus the Authority the work
  needs (`A1` commit-only default; `A2` push + PR when the user wants a
  PR; `A3` + dependency changes). One `clarify`; for a new repo the
  same approval sanctions the bootstrap decisions.
- **Issue decomposition is drafted in-session, registered by you** —
  for issue-tracked work the engineer session drafts the epic +
  sub-issue split (draft-only), the user approves it, and you register
  the Issues via `gh` (see the execute file's GitHub ops).
- **Resident-only** — no `card_units` exist for engineering, and none
  should be added until a class of work is fully CI-verifiable without
  supervision.

Small settled fixes ("fix the off-by-one in `foo()`, test is
`bar_test.py`") skip the base session: state the intent and go straight
to Execute.

## Leaves — pick by deliverable

Each leaf owns what varies: the Brief to fix before the session, the
wave-prompt shape, the expected outline (your inspection standard), and
Authority/verification defaults.

| Deliverable | Leaf |
| --- | --- |
| Any NEW repo — run first, then a type leaf | `bootstrap.md` |
| Single-page LP / campaign page | `lp.md` |
| Multi-page site / homepage | `website.md` |
| Stateful web app (DB / auth / APIs) | `webapp.md` |
| Script / CLI / automation | `tool.md` |
| Change to an existing repo | `existing-change.md` |
