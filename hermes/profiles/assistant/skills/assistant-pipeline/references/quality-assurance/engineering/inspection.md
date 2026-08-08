# Engineering QA — deliverable inspection

Step 4 of the gate: inspect what the unit actually produced, keyed
to the plan archetype's verification default. Inspection executes
and observes in the worktree — read-only toward the repo state: run
things, open things, measure things; never edit, install, or
regenerate. Route by the deliverable, not the repo layout; one unit
may need several rows.

| Archetype | Inspect |
| --- | --- |
| web-content | the rendered page, not the source |
| webapp | the named flow, exercised |
| tool | the entry command, executed |
| bootstrap | the established repo, six points |
| existing-change | the regression evidence |

- **web-content** — open the built or deployed page (or the
  engineer's screenshot when the report carries one — then verify
  it reflects the landed commit, not an earlier state). Check the
  rendered copy verbatim against the brief where copy was
  specified, links resolve, and the viewports the brief names. A
  build that passes with a broken render is a fail.
- **webapp** — exercise the flow the unit claims: start per the
  report (or repo `AGENTS.md`/README) and hit the named
  route/action once. Migration work: the up (and rollback, when
  claimed) output is in the report evidence. Auth/data flows:
  verify the named test covering them ran, not just a suite total.
  UI portions follow the web-content row.
- **tool** — execute the entry command: `--help`/usage plus one
  sample invocation from the brief's done criteria; check exit
  codes and output shape against the brief.
- **bootstrap** — the six-point establishment check (the verifying
  mirror of `../../execute/engineering/github-ops.md` step 6): the
  `Projects/<Group>/github/<repo>` symlink resolves; `.git` exists
  with the intended remote; starter files are present; `AGENTS.md`
  is filled (not the stub); the `pj` registry row exists; the repo
  is on GitHub under the intended owner and visibility.
- **existing-change** — the named regression checks passed with
  actual output, and the scope check (gate step 3) shows no
  out-of-scope diff; for a behavior change, one observed
  before/after example is in the report evidence.

Embedded non-code artifacts route to their own capability
contracts: images/media in a page → `../creative/index.md`; prose
written by the writer → `../writing/index.md`. Engineering QA
checks they are wired in; those contracts check they are good.
