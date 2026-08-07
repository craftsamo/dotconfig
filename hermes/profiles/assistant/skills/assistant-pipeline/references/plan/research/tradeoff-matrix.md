# Tradeoff-matrix — decision surface

Decision support: named options scored against fixed criteria, with
a recommendation — the consultation form your own Plan work
dispatches when a decision needs evidence. The researcher owns the
gathering, cell scoring, and deal-breaker hunting; you own what is
being decided, which options compete, and which axes matter.

Researcher unit `tradeoff-matrix` · QA `tradeoff-matrix` · units:
one decision per unit; never card-eligible — a live decision loop
needs the session's back-and-forth.

## Fix before release

- **The decision** — one line: what is being decided, for what
  context ("pick the CI runner for a 3-person team self-hosting on
  one box").
- **The option set** — closed and named. "What are my options?" is
  a search sweep (or a grounding lookup) first; the matrix compares
  a decided list.
- **The criteria** — the axes every option is judged on, with
  weights when the caller has priorities; the researcher may add
  the 2-3 axes the caller forgot (ops burden, reversibility,
  maturity) and must label them as additions.
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
- Assumptions are labeled and proceeded on; only an ambiguous
  option set itself blocks.

## Red flags

- The option set is open or keeps growing mid-brief — granularity
  finding; ground it with a search sweep, then release the matrix
  against the closed list.
- Criteria undecided ("just compare them") — spec-gap finding; the
  axes are the decision's shape and belong to you and the user.
- The matrix wants the options enumerated AND scored in one unit —
  enumeration is a search sweep; score the QA-passed table.
- The "comparison" is really one option's feasibility — an
  evidence-pack unit with a settled question, not a matrix.
