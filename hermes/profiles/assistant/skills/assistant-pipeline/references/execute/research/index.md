---
card_units:
  - name: evidence-pack
    assignee: researcher
    required_inputs: [claims-list, source-requirements]
    unit_cap: "verification of one fixed list of claims, each with sources and verdicts"
    runtime_cap: 1800
---

# Research — execute

The specialist is the **researcher** — depth: analysis, synthesis,
comparison, evaluation, verification, evidence-backed guidance
(`../../plan/research/index.md` has the routing table; retrieval is
the searcher's — `../search/index.md`). Sessions are the default;
`evidence-pack` above is the only research work that may ride
kanban.

## Resident session

Start the session with the SessionBrief; the pipeline routes
internally by deliverable (evidence-pack / tradeoff-matrix /
fact-check / guidance) — write what you want, not how.

- Follow-ups sharpen scope in place: "その3件を深掘り",
  "2024年以前は除外". The session keeps its source trail, so
  refinement is cheap.
- QA-passed searcher findings feeding a researcher unit are pasted
  into the brief as a part — including the `Open for researcher`
  items the searcher named.
- Research feeding another specialist: wait for the turn, QA it,
  then paste the conclusions (not a pointer) into the consuming
  session's brief.

## Card units

- `evidence-pack` — a fixed claims list to verify; the card returns
  per-claim verdicts + sources. Framing still moving → researcher
  session, not a card.
- Analysis, synthesis, and anything whose framing may move with the
  user stay resident — no unit exists for them on purpose.

Gap-filling after QA (a claim left unverdicted, thin sourcing) may
be a fresh card with the same unit and a narrowed spec — evidence
is additive, so card-cycling a fix is normal here.

## Pitfalls

- Sending retrieval to the researcher — enumerations and hunts are
  searcher units; depth starts from their QA-passed findings.
- Deep analysis inline — it floods your own context.
- Briefs or cards that ask "research X" with no decision context or
  done criteria.
- Forwarding conclusions whose load-bearing sources you never
  opened.
