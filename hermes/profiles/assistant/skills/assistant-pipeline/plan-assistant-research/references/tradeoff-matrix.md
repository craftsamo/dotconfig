# Tradeoff-matrix — decision surface

Decision support: named options scored against fixed criteria, with
a recommendation — the consultation form your own Plan work
dispatches when a decision needs evidence. The researcher owns the
gathering, cell scoring, and deal-breaker hunting; its Plan proposes options
and axes for Client agreement against your decision and constraints.

Researcher unit `tradeoff-matrix` · QA `tradeoff-matrix` · units:
one decision per unit; a live decision loop
needs the session's back-and-forth.

## Agree before Build

These are proposal choices, not required inputs for a purpose-first Plan.
The caller may author them fully; otherwise Researcher proposes them through
the consuming primary. Follow the parent entry's agreement and preliminary
Build gates; retain same-role unit boundaries.

- **The decision** — one line: what is being decided, for what
  context ("pick the CI runner for a 3-person team self-hosting on
  one box").
- **The option set** — closed and named before scoring. Plan may propose from
  supplied material; missing external options need an agreed preliminary Build
  or a search dependency released by the Client, then main-proposal agreement.
- **The criteria** — the axes every option is judged on, with
  weights when the caller has priorities; Researcher may propose the 2-3 axes
  the caller forgot (ops burden, reversibility, maturity), labeling additions
  and obtaining agreement before scoring against them.
- **Evidence floor per cell** — what a cell must cite before it
  counts (primary docs? credible experience reports?); gaps become
  `Unknown` cells, never guesses.
- **Effort bound** — time-boxed by the decision's stakes; a Plan
  consultation compresses to the session's budget, not an
  exhaustive survey per option.
- **Done criteria** — every option scored on every criterion (or
  explicitly `Unknown`), deal-breakers named, one recommendation
  with confidence.
- **Durable path** — the matrix and source table land in a file
  when large; the recommendation lives in the reply.

## Defaults

- Recommendation may be conditional ("A unless X") — but present:
  a matrix with no recommendation fails its own done criteria.
- Options are judged on the same axes — an option's marketing
  strengths never become its private criteria.
- Harmless assumptions are labeled; changes to options, criteria or weights
  need agreement before Build, not merely an additions label.

## Red flags

- The option set keeps growing during Build — granularity finding; return to
  Plan rather than silently expand scoring. An open set is valid Plan input.
- Criteria undecided ("just compare them") — specialist Plan proposes axes
  for Client agreement; unresolved criteria remain a Build spec-gap finding.
- The matrix wants the options enumerated AND scored in one unit —
  enumeration is a search sweep; score the QA-passed table.
- The "comparison" is really one option's feasibility — an
  evidence-pack unit with a settled question, not a matrix.
