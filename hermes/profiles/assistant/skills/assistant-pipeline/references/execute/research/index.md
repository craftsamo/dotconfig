---
card_units:
  - name: claim-verification
    assignee: researcher
    required_inputs: [claims-list, source-requirements]
    unit_cap: "verification of one fixed list of claims, each with sources and verdicts"
    runtime_cap: 1800
---

# Research — execute

The specialist is the **researcher** — analytic hands; it verifies
and concludes, it never retrieves at breadth and never crafts.
Sessions are the default; the card unit above is the only research
work that may ride kanban: a settled fact-check unit as
`claim-verification`. You release the plan's units one at a time and
gate between them.

## Resident session

Start the session with the brief fixed by the unit leaf
(`../../plan/research/`): the decision core, the leaf's decisions,
and the unit being released. One session per question cluster — the
source trail and trust scores live in the session's context, so
narrowing is cheap ("その3件を深掘り", "2024年以前は除外").
Conclusions arrive in the reply; ledgers and long reports land at
the durable path the brief names.

## The unit loop

1. **Release one unit** — an evidence-pack unit (settled question),
   a tradeoff-matrix unit (decision + options + criteria), a
   fact-check unit (fixed claims list + source requirements), or a
   guidance unit (consumer + decision points + evidence base).
   QA-passed search parts the unit consumes are pasted into the
   brief — including the `Open for researcher` items the searcher
   named. Undecided deliverable-defining choices come back as
   **spec-gap findings**; work bigger than its unit (a question
   that is several questions, a matrix whose options keep growing)
   as **granularity findings** — both go back to Plan, not into a
   bigger analysis.
2. **Receive the report** — the conclusion leading, evidence
   behind it: scored sources, corroboration status, per-claim
   confidence, uncertainty stated; the ledger written when the
   unit's consumer needs one.
3. **Gate** — per `../../quality-assurance/research/index.md`, by
   unit type. Feedback turns are itemized and scope-anchored
   ("この2件のverdictの根拠を一次情報まで", "軸3の空セルを埋めるか
   Unknownの理由を"); everything unnamed is preserved.
4. **Accept → hand off or release the next unit.** A fact-check
   whose claims list survived a session turn may cycle to a
   `claim-verification` card next time.

## Card units

- `claim-verification` — a fixed claims list to verify; the card
  returns per-claim verdicts + sources (and the ledger when the
  body names a consumer). Framing still moving → researcher
  session, not a card.
- Evidence-packs, matrices, and guidance never ride kanban —
  synthesis and comparison move with the user on purpose.
- Gap-filling after QA (a claim left unverdicted, thin sourcing)
  may be a fresh card with the same unit and a narrowed spec —
  evidence is additive, so card-cycling a fix is normal here.

## Part handoff

QA-passed conclusions are a **part** for other capabilities — paste
the conclusions (not a pointer) into the consuming brief; the
consumer never reaches into the researcher's session:

- A verdict ledger feeding your own QA pass → read the ledger file
  at its durable path; the artifact gate stays yours.
- Guidance feeding a writer/creator/marketer unit → the directives
  travel in the consuming brief (or its named file); the worker
  never rereads the sources.
- A recommendation feeding your Plan work → the matrix informs the
  decision you make with the user; carry the confidence and
  `Unknown` cells alongside, not just the winner.

## Pitfalls

- Sending retrieval to the researcher — enumerations and hunts are
  search units; depth starts from their QA-passed findings.
- Deep analysis inline — it floods your own context.
- Briefs or cards that ask "research X" with no decision context or
  done criteria.
- Accepting a crafted artifact from the researcher — conclusions
  only; the defect is yours if you asked for the 台本.
- Forwarding conclusions whose load-bearing sources you never
  opened.
- Re-briefing method (search routes, trust scoring) the
  researcher's craft already owns.
