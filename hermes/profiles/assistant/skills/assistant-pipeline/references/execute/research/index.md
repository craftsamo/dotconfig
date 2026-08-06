---
card_units:
  - name: survey-enumeration
    required_inputs: [settled-question, coverage-claim, per-item-fields]
    unit_cap: "one enumeration/survey with an explicit floor count and per-item field list"
    runtime_cap: 1800
  - name: exhaustive-hunt
    required_inputs: [settled-question, done-criteria, scope-exclusions]
    unit_cap: "one goal-mode multi-hop source hunt; goal_mode: true + goal_max_turns"
    runtime_cap: 3600
  - name: evidence-pack
    required_inputs: [claims-list, source-requirements]
    unit_cap: "verification of one fixed list of claims, each with sources and verdicts"
    runtime_cap: 1800
---

# Research — execute

Retrieval belongs to **searcher**, depth to **researcher**
(`../../plan/research/index.md` has the routing table). Sessions are the
default; the card units above are the only research work that may ride
kanban — `survey-enumeration` and `exhaustive-hunt` go to searcher,
`evidence-pack` to researcher.

## Resident session

Start the session with the SessionBrief; the pipeline routes internally
by deliverable (evidence-pack / tradeoff-matrix / fact-check / guidance
for researcher; lookup / survey / hunt for searcher) — write what you
want, not how.

- Follow-ups sharpen scope in place: "その3件を深掘り", "2024年以前は除外".
  The session keeps its source trail, so refinement is cheap.
- Research feeding another specialist: wait for the turn, QA it, then
  paste the conclusions (not a pointer) into the consuming session's
  brief.

## Card units

- `survey-enumeration` / `exhaustive-hunt` — the spec is settled: the
  question, the coverage claim ("≥15 candidates, each with pricing URL
  and date"), and exclusions are fixed in the body; you would accept the
  result sight unseen. Hunts run `goal_mode: true` + `goal_max_turns`.
- `evidence-pack` — a fixed claims list to verify; the card returns
  per-claim verdicts + sources. Framing still moving → researcher
  session, not a card.
- Analysis, synthesis, and anything whose framing may move with the user
  stay resident — no unit exists for them on purpose.

Gap-filling after QA (thin coverage, dead links) may be a fresh card with
the same unit and a narrowed spec — evidence is additive, so this is the
one capability where card-cycling a fix is normal.

## Pitfalls

- Sending a 30-second lookup to a session or the board.
- Deep multi-hop research inline — it floods your own context.
- Briefs or cards that ask "research X" with no decision context or done
  criteria.
- Forwarding conclusions whose load-bearing sources you never opened.
