---
card_units:
  - name: survey-enumeration
    assignee: searcher
    required_inputs: [settled-question, coverage-claim, per-item-fields]
    unit_cap: "one enumeration/survey with an explicit floor count and per-item field list"
    runtime_cap: 1800
  - name: exhaustive-hunt
    assignee: searcher
    required_inputs: [settled-question, done-criteria, scope-exclusions]
    unit_cap: "one goal-mode multi-hop source hunt; goal_mode: true + goal_max_turns"
    runtime_cap: 3600
---

# Search — execute

The specialist is the **searcher** — retrieval hands; it gathers,
it never concludes. Sessions are the default; the card units above
are the only search work that may ride kanban: a settled sweep unit
as `survey-enumeration`, a settled hunt unit as `exhaustive-hunt`.
You release the plan's units one at a time and gate between them.

## Resident session

Start the session with the brief fixed by the unit leaf
(`../../plan/search/`): the decision core, the leaf's decisions,
and the unit being released. One session per question cluster — the
source trail lives in the session's context, so narrowing is cheap
("その3件の一次情報だけ", "2024年以前は除外"). Findings arrive in
the reply; large enumerations land at the durable path the brief
names.

## The unit loop

1. **Release one unit** — a lookup unit (single question or an
   itemized batch), a sweep unit, or a hunt unit. Undecided
   deliverable-defining choices come back as **spec-gap findings**;
   work bigger than its unit (a sweep spanning populations, a
   lookup growing hops) as **granularity findings** — both go back
   to Plan, not into a bigger crawl.
2. **Receive the report** — findings with per-claim sources and
   dates, the coverage statement (sweep: matrix + floor met; hunt:
   source map + trail notes + gaps), `Open for researcher` items
   named, interpretation labeled when the brief was assumed-on.
3. **Gate** — per `../../quality-assurance/search/index.md`, by
   unit type. Feedback turns are itemized and scope-anchored
   ("floor未達のセルはEU圏のみ再掃引", "この2件のリンクが死んでいる");
   everything unnamed is preserved.
4. **Accept → hand off or release the next unit.** A settled sweep
   or hunt whose spec survived a session turn may cycle to a card
   next time.

## Card units

- `survey-enumeration` / `exhaustive-hunt` — the spec is settled:
  the question, the coverage claim ("≥15 candidates, each with
  pricing URL and date") or done criteria, and exclusions are fixed
  in the body; you would accept the result sight unseen. Hunts run
  `goal_mode: true` + `goal_max_turns`.
- Lookups never ride kanban — inline, `delegate_task`, or a session
  turn.
- Gap-filling after QA (thin coverage, dead links) may be a fresh
  card with the same unit and a narrowed spec — evidence is
  additive, so card-cycling a fix is normal here.

## Part handoff

QA-passed findings are a **part** for other capabilities — paste
the findings (not a pointer) into the consuming brief; the consumer
never reaches into the searcher's session:

- Sourced facts feeding depth → the researcher's brief
  (`../research/index.md`); the researcher adjudicates what the
  searcher flagged `Open for researcher`.
- Enumeration tables feeding a decision → your own delivery, with
  the coverage statement carried alongside.
- Facts feeding text or media → the writer/creator brief's source
  pack; the writer never re-retrieves.

## Pitfalls

- Sending a 30-second lookup to a session or the board.
- Deep multi-hop retrieval inline — it floods your own context.
- Briefs or cards that ask "research X" with no decision context or
  done criteria.
- Accepting rankings, recommendations, or verdicts from the
  searcher — retrieval-only is its floor; the defect is yours if
  you asked for them.
- Forwarding findings whose load-bearing links you never opened.
- Re-briefing search tactics (query strings, site lists) the
  searcher's craft already owns.
