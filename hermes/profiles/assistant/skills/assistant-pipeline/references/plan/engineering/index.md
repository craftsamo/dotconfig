# Engineering — plan

One mental model governs engineering: **you are the project owner and
the engineer is your hands.** You plan the way the user would plan
for themselves — decompose the goal, own the sequence, hold the
quality gate — and the engineer receives **one unit at a time**,
translating it into an OpenCode plan → build cycle inside the repo.
A whole deliverable ("build the LP") is never an instruction to the
engineer: that shape outsources sequencing and QA, which are yours.

Every engineering plan therefore ends in the same goal state: an
approved, ordered **unit decomposition** the engineer can consume one
unit at a time, plus the sanctioned Authority.

## Units — the two kinds

| Unit | Handoff | What it is |
| --- | --- | --- |
| **Purpose** | `Issue: #n` | A registered GitHub Issue sized 1–3 PRs; the Issue text is the spec. Multi-purpose work hangs the purposes as sub-issues off an epic, mirrored on the user's Roadmap project board. |
| **Wave** | `Base session: <id>` + `Wave N` | One coarse milestone line from your base plan session in the repo. |

Purposes are the default whenever the work is issue-tracked or
outlives one session; Waves cover small linear work where Issue
ceremony costs more than it buys (each leaf sets its default). Both
decompositions are **drafted by you in your own OpenCode plan
session, approved by the user once, and registered by you** (`gh`
for epic + sub-issues, board sync included). The engineer never
drafts, registers, or re-plans a decomposition — it details one unit
inside OpenCode when handed that unit.

## Invariants (apply to every leaf)

- **The assistant manages repos; the engineer only works inside
  them.** Repo creation, ghq clone, workspace symlinks, `pj`
  registry, Issue/board registration, and merges are yours, through
  your own `gh`/`ghq`/`pj`. Worktree-side repo establishment is
  delegable only under an explicit, user-sanctioned `B1`/`B2` grant —
  the GitHub/registry side stays yours even then.
- **Locate the repo** — `pj show --id <Group>` → the
  `~/Workspaces/Projects/<Group>/github/<repo>` symlink (a `~/ghq`
  clone). No repo yet → `bootstrap.md` runs first; the base session
  comes after it, inside the new repo.
- **Base plan session** — a read-only plan run in the repo:

  ```bash
  cd <repo> && opencode run --auto --agent plan --title "waves: <goal>" \
    'Split this goal into WAVES only — coarse milestones sized for
     one engineer handoff each, in dependency order, one line each.
     No phase/unit detail.
     <goal, constraints, done criteria — from the leaf's prompt>'
  ```

  Recover the id (`opencode session list`) and hand it over as
  `Base session:`. Check the returned decomposition against the
  leaf's expected shape before presenting it — a malformed one is
  re-run, not hand-patched in chat. Purpose-unit work uses the same
  session to draft the epic + purpose split instead; once registered,
  the Issues replace the session as the handoff artifact.
- **One unit per handoff** — execution releases units strictly one at
  a time: hand a unit, receive the report, pass your QA gate, then
  release the next (see the execute file). Batch autonomy ("run
  units 1–3 unattended") is an explicit, named grant in the plan —
  never the default.
- **One approval** — present the decomposition in plain language
  (what lands, in what order, what it costs) plus the Authority the
  work needs (`A1` commit-only default; `A2` push + PR/stack when
  the user wants PRs; `A3` + dependency changes). One `clarify`; for
  a new repo the same approval sanctions the bootstrap decisions.
- **Resident-only** — no `card_units` exist for engineering, and none
  should be added until a class of work is fully CI-verifiable
  without supervision.

Small settled fixes ("fix the off-by-one in `foo()`, test is
`bar_test.py`") skip decomposition: state the intent and go straight
to Execute — the fix is its own single unit.

## Leaves — pick by archetype

Leaves are keyed to **planning archetypes**, not product nouns. A
product noun (blog, portfolio, admin dashboard) belongs to whichever
archetype matches; extend that leaf with a shape row rather than
creating a file.

| Archetype | Leaf |
| --- | --- |
| Any NEW repo — run first, then an archetype leaf | `bootstrap.md` |
| Content-led web frontend (LP / site / blog / portfolio) | `web-content.md` |
| Stateful web app (DB / auth / APIs) | `webapp.md` |
| Script / CLI / automation | `tool.md` |
| Change to an existing repo | `existing-change.md` |

**New-leaf test** — a deliverable earns a NEW leaf only when it
differs from every existing archetype on at least one of the four
planning variables: (1) starter/platform family, (2) the foundational
first units, (3) the verification default, (4) the unit-kind default
(purposes vs Waves). A desktop app passes (different family,
packaging, verification); a blog does not (a `web-content.md` row).

Each leaf owns what varies: the Brief to fix before the session, the
decomposition-prompt shape, the expected decomposition (your
inspection standard), and Authority/verification defaults.
