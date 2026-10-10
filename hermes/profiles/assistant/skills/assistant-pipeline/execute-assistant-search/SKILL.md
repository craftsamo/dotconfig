---
name: execute-assistant-search
description: "Execute search: release retrieval units and source handoffs. Supervise resident sessions, including a multi-hop hunt; searchers never issue verdicts."
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: assistant-pipeline
    tags: ["execute", "search"]
---

<ReadBeforeWork>

Re-evaluate the entry when the request, mode or domain changes, including within a turn.
Reuse full-body instructions only while present in the current context, not a past load or summary.
Check the kernel and common mode procedure independently. Load each whose full body is missing:

```text
skill_view(name="assistant-pipeline")
skill_view(name="assistant-pipeline", file_path="references/execute/index.md")
```

These dependencies also apply to direct entry. Loading does not restart an approved plan or expand a grant.
If a tool returns unchanged while the earlier body is unavailable, use read_file on `${HERMES_SKILL_DIR}/../SKILL.md` and `${HERMES_SKILL_DIR}/../references/execute/index.md`.
Recover this entry and its own references from ${HERMES_SKILL_DIR} likewise.
Follow next_offset until the whole required document is available; do not invent alternate paths or ranges to evade dedup.
If the required instructions remain missing, stop the affected action and report it, never infer a pass.
Read only applicable detail references below.

</ReadBeforeWork>

# Search — execute

The specialist is the **searcher** — retrieval hands; it gathers,
it never concludes. Search is resident-only. You release the plan's units one at a
time and gate between them.

## Resident session

Start with purpose, consumer, constraints, budget and durable path, plus known
decisions or your full specification (`../plan-assistant-search/references/`).
Purpose-first work starts specialist Plan: Searcher proposes questions, coverage,
fields and same-role units; the Client agrees within granted discretion and
escalates material human-only or out-of-scope decisions. No detailed prebuilt
spec is required to start Plan. An explicitly authorized settled brief can go
directly to Build without unnecessary reapproval; fields or transport kind alone
are not authorization. A recurring purpose names its Searcher technic in the
brief (`../plan-assistant-search/SKILL.md` "Technics"). One session per
question cluster retains the source trail.

Use `specialist_call(target="searcher", kind="work", message=...)` and retain
`conversation_id` for proposal, agreement and feedback messages;
`specialist_session` retains its existing lifecycle role, with no new state tool.
Plan allows no unapproved external search. Agree any bounded preliminary Build
(scope, output, budget, stop condition) first; inspect its result after Build
and its specialist self-check, then separately agree the refined main proposal.
Preliminary agreement never releases main work. Assistant retains overall
orchestration and cross-role dependencies.

## The unit loop

1. **Release one agreed unit to Build** — a lookup unit (single question or an
   itemized batch), a sweep unit, or a hunt unit. Undecided
   deliverable-defining choices come back as **spec-gap findings**;
   work bigger than its unit (a sweep spanning populations, a
   lookup growing hops) as **granularity findings** — both go back
   to Plan, not into a bigger crawl.
2. **Receive the report with its specialist self-check** — findings with per-claim sources and
   dates, the coverage statement (sweep: matrix + floor met; hunt:
   source map + trail notes + gaps), `Open for researcher` items
   named, interpretation labeled when the brief was assumed-on.
3. **Independently gate** — self-QA is not an external pass;
   apply `../qa-assistant-search/SKILL.md`, by
   unit type. Feedback turns are itemized and scope-anchored
   ("floor未達のセルはEU圏のみ再掃引", "この2件のリンクが死んでいる");
   everything unnamed is preserved.
4. **Accept → hand off or release the next unit.**

## Long retrievals

- A long or multi-hop retrieval is one conversation: keep the
  `conversation_id` and send a continue message; the searcher restates its
  ledger each turn and consumed budget carries over. A settled sweep or hunt
  needs a full brief (question, coverage claim or done criteria, exclusions).
- Lookups run inline, through `delegate_task`, or as a session turn.
- Gap-filling after QA (thin coverage, dead links) is a feedback turn in the
  same conversation, with a narrowed, itemized scope.

## Part handoff

QA-passed findings are a **part** for other capabilities — paste
the findings (not a pointer) into the consuming brief; the consumer
never reaches into the searcher's session:

- Sourced facts feeding depth → the researcher's brief
  (`../execute-assistant-research/SKILL.md`); the researcher adjudicates what the
  searcher flagged `Open for researcher`.
- Enumeration tables feeding a decision → your own delivery, with
  the coverage statement carried alongside.
- Facts feeding text or media → the writer/creator brief's source
  pack; the writer never re-retrieves.

## Pitfalls

- Sending a 30-second lookup to a session.
- Deep multi-hop retrieval inline — it floods your own context.
- Treating a purpose-first Plan request as malformed because it lacks detailed
  questions, or sending that unsettled purpose as a Build request.
- Accepting rankings, recommendations, or verdicts from the
  searcher — retrieval-only is its floor; the defect is yours if
  you asked for them.
- Forwarding findings whose load-bearing links you never opened.
- Re-briefing search tactics (query strings, site lists) the
  searcher's craft already owns.
