---
name: plan-assistant-search
description: "Plan search: bring purpose and constraints, then agree Searcher-proposed scope, coverage and units. Preserve settled caller briefs; conclusions and recommendations belong to research."
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: assistant-pipeline
    tags: ["plan", "search"]
---

<ReadBeforeWork>

Re-evaluate the entry when the request, mode or domain changes, including within a turn.
Reuse full-body instructions only while present in the current context, not a past load or summary.
Check the kernel and common mode procedure independently. Load each whose full body is missing:

```text
skill_view(name="assistant-pipeline")
skill_view(name="assistant-pipeline", file_path="references/plan/index.md")
```

These dependencies also apply to direct entry. Loading does not restart an approved plan or expand a grant.
If a tool returns unchanged while the earlier body is unavailable, use read_file on `${HERMES_SKILL_DIR}/../SKILL.md` and `${HERMES_SKILL_DIR}/../references/plan/index.md`.
Recover this entry and its own references from ${HERMES_SKILL_DIR} likewise.
Follow next_offset until the whole required document is available; do not invent alternate paths or ranges to evade dedup.
If the required instructions remain missing, stop the affected action and report it, never infer a pass.
Read only applicable detail references below.

</ReadBeforeWork>

# Search — plan

**The Client owns purpose and agreement; Searcher proposes the retrieval.**
Send purpose, consumer, constraints, budget and durable path. A purpose-first
session request starts specialist Plan without a prebuilt detailed spec.
Searcher proposes questions, population, coverage, per-item fields, freshness,
exclusions, done conditions, output and ordered same-role units. Agree within
already granted discretion; escalate material human-only or out-of-scope
decisions. Assistant retains overall orchestration and cross-role dependencies;
query strategy, source triage and dedup mechanics remain Searcher's craft.

You may still author the full specification. An explicitly authorized settled
brief goes directly to Build without unnecessary reapproval; filled fields or
transport kind alone are not authorization. Open defining choices block Build,
not specialist Plan; unresolved spec-gap and granularity findings stay visible.

Search is retrieval only: links + claims with an honest coverage
statement. Verdicts, synthesis, and comparisons are the
researcher's (`../plan-assistant-research/SKILL.md`).

## Units — the three kinds

| Unit | Agreed before Build | What it is |
| --- | --- | --- |
| **Lookup unit** | the settled question | one specific sourced answer — a fact, a link/doc, "latest on X", who-said-what; batches of related questions release as one unit with an itemized list |
| **Sweep unit** | question + coverage claim/floor + per-item fields | one enumeration/survey — candidates, examples, instances — or a quantified observation of public web state |
| **Hunt unit** | question + done criteria + scope exclusions | one exhaustive multi-hop source hunt — obscure topic, contested claim's primary sources, provenance chase |

A sweep whose coverage claim is really several sweeps, or a lookup
that keeps growing hops, is a **granularity finding** — decompose,
never stretch the unit. A sweep or hunt is a resident
session (`../execute-assistant-search/SKILL.md`), a long one continued in the same conversation; lookups are chat work
or a session turn.

## Proposal and agreement core

Supply known decisions and mark suggestions/open choices; the fields below
are settled by the specialist proposal and Client agreement before Build,
not prerequisites for requesting Plan. The caller may fill all of them.

- **Decision context** — what decision the retrieval serves; it
  sizes the effort and settles what "enough" means.
- **The question** — one line, settled; "research X" is not a
  question.
- **Done criteria** — observable: the fact with its source, the
  floor count met, the done criteria of the hunt satisfied.
- **Freshness** — the date window that matters, and whether stale
  hits are excluded or merely flagged.
- **Scope exclusions** — what NOT to chase; hunts without
  exclusions do not terminate.
- **Durable path** — where large enumerations/tables land; small
  findings live in the reply.
- **Consumer** — who takes the findings next (you, researcher,
  writer, marketer); the consumer's needs fix the per-item fields.

Family-specific decisions live in the leaves. Review the proposed choices
against purpose and grants; answer within discretion and use the existing
`clarify` protocol only for decisions needing the user.

## Grounding — the searcher informs, you decide

Plan uses supplied material only, with no unapproved external search. If
discovery is needed, Searcher may propose a bounded preliminary Build with
scope, output, budget and stop condition. Agree first; after Build and its
specialist self-check, inspect the result, then obtain separate agreement
on the refined main proposal. Preliminary agreement never releases main work.
Use the existing work handle and `specialist_call` messages with its
`conversation_id`; `specialist_session` owns lifecycle, not a new proposal
state tool. A planning reply is not retrieved findings.

## Leaves — pick by unit

| Retrieval | Leaf |
| --- | --- |
| Specific answer, fact, link, latest-on-X | `references/lookup.md` |
| Enumeration / survey with a coverage claim | `references/sweep.md` |
| Exhaustive multi-hop source hunt | `references/hunt.md` |

Each leaf names its QA contract; the validator enforces the
mapping.

## Technics — recurring purposes

Searcher keeps a recipe for some recurring purposes. Name it in the brief
(`technic: <name>`) and Searcher loads it on top of the unit's mode: it brings
the purpose's sources, per-item fields and checks, so the brief adds only the
table's fields to the unit's core above (a hunt still needs done criteria and
exclusions). The unit, its QA contract and release stay those of the mode. A
purpose no row fits is an ordinary unit.

| Technic | Unit | Add to the unit's core |
| --- | --- | --- |
| `public-footprint` — one person's, brand's or organization's public accounts, activity, self-made claims and published addresses, from a starting account | hunt | the start account or URL and its service; subject kind (public figure, business, private individual); services in scope; window; cap |
| `primary-fact-pack` — first-party facts or verbatim quotes on a settled item list | lookup (itemized) | the item list; fields beyond the defaults; what counts as primary; language; cap |
| `release-digest` — changes at named vendors inside a date window, minus what was already covered | sweep | the vendors; the window as dates; audience and inclusion rule; the exclusion-list path; count floor and cap |

A footprint hunt maps what the subject shows of itself, graded by the links
that tie each piece to it; it never names who is behind a pseudonymous account
or gathers private life. Whether the subject or its claims can be trusted is a
researcher question on top of it. A digest returns its candidates ready to
append; you add them to the exclusion list after acceptance.

## Boundaries

- **Retrieval, not depth.** Analysis, synthesis, tradeoffs,
  verification verdicts, and guidance are researcher units
  (`../plan-assistant-research/SKILL.md`); a crafted artifact built on findings is
  writer/creator work.
- **Quick and medium lookups stay in Chat** — a one-minute fact is
  inline, parallel in-turn lookups are `delegate_task`
  (`../chat-assistant/references/lookups.md`). Search units exist for durable,
  supervised retrieval.
- The searcher reads social platforms; it never posts, replies,
  likes, or DMs. Approved service drafts are saved through marketing Execute; the user publishes.
