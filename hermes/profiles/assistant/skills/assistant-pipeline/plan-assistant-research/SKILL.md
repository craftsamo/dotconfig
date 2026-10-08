---
name: plan-assistant-research
description: "Plan research: bring purpose and constraints through the consuming primary, then agree the Researcher proposal. Preserve caller-authored briefs; retrieval-only work belongs to search."
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: assistant-pipeline
    tags: ["plan", "research"]
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

# Research — plan

**The Client owns purpose and agreement; Researcher proposes the research.**
Send purpose, consumer, constraints, budget and durable path through engineer,
creator, or marketer. A purpose-first session/peer request starts specialist
Plan without a prebuilt detailed spec. Researcher proposes questions, options,
criteria, exact claims, source policy, exclusions, done conditions, output and
ordered same-role units. The immediate primary Client agrees within already
granted discretion; escalate material human-only or out-of-scope decisions.
Assistant retains overall orchestration and cross-role dependencies, not the
researcher's gathering strategy, trust scoring or corroboration mechanics.

You may still author the full specification. An explicitly authorized settled
brief goes directly to Build without unnecessary reapproval; filled fields or
transport kind alone are not authorization. Open defining choices block Build,
not specialist Plan; unresolved spec-gap and granularity findings stay visible.

Research is depth only: verified conclusions with the evidence behind
them. Retrieval-only facts and heavy breadth (enumerations, surveys, hunts) are
the searcher's (`../plan-assistant-search/SKILL.md`); bounded preliminary depth
discovery may be agreed with Researcher. A crafted artifact (台本, copy,
media) built on a conclusion is writer/creator work consuming it.

## Units — the four kinds

| Unit | Agreed before Build | What it is |
| --- | --- | --- |
| **Evidence-pack unit** | the settled question + done criteria | one open question answered with verified evidence — deep synthesis, landscape analysis, "what do we actually know about X" |
| **Tradeoff-matrix unit** | decision + closed option set + criteria | one comparison — named options scored against fixed axes, with a recommendation |
| **Fact-check unit** | fixed claims list + source requirements | per-claim verdicts (supported / refuted / partly true / unverifiable) with sources and counterevidence |
| **Guidance unit** | consumer + decision points + evidence base | evidence-backed direction — MUST/SHOULD directives and open choices a downstream worker can act on |

A question that is really several questions, or a matrix whose option
set keeps growing, is a **granularity finding** — decompose, never
stretch the unit. No research unit is released to the
researcher directly: the purpose or settled unit travels inside the brief of the
consuming primary — engineer, creator, or marketer — whose peer the
researcher is (`../execute-assistant-research/SKILL.md`).

## Proposal and agreement core

Supply known decisions and mark suggestions/open choices; the fields below
are settled by the specialist proposal and Client agreement before Build,
not prerequisites for requesting Plan. The caller may fill all of them.

- **Decision context** — what decision the conclusion serves; it
  sizes the effort and settles what "enough evidence" means.
- **The question** — one line, settled; "research X" is not a
  question.
- **Done criteria** — observable: the sub-questions closed, every
  option scored on every criterion, every claim verdicted.
- **Source policy** — the freshness window, the reliability floor
  for load-bearing claims, and any required source classes (primary
  docs, filings, papers).
- **Inputs** — QA-passed search parts and prior results pasted into
  the brief (not pointers); heavy breadth the unit needs is a Searcher dependency
  released by the Client. Bounded preliminary depth discovery may instead be
  proposed by Researcher and separately agreed before gathering.
- **Durable path** — where ledgers and long reports land; the
  conclusion lives in the reply.
- **Consumer** — who acts on the conclusion next (you, the user,
  writer, marketer, the QA pass); the consumer fixes the output
  shape and the ledger requirement.

Family-specific decisions live in the leaves. Review the proposed choices
against purpose and grants; answer within discretion and use the existing
`clarify` protocol only for decisions needing the user.

## Grounding — the researcher informs, you decide

Plan uses supplied material only, with no unapproved external search. If
discovery is needed, Researcher may propose a bounded preliminary Build with
scope, output, budget and stop condition. The primary Client must agree first;
after Build and its specialist self-check, the primary inspects the result and
gives separate agreement on the refined main proposal within its grant.
Preliminary agreement never releases main work. The primary owns and continues
the Researcher work handle and `conversation_id`. Assistant uses only its own
PRIMARY work handle for `specialist_call` messages and `specialist_session`
lifecycle; Assistant never holds or uses the Researcher conversation. The primary
relays the agreed baseline and findings per `../execute-assistant-research/SKILL.md`;
Assistant requests missing material through that primary, not Researcher.
No new proposal state tool is needed. A researched consultation still needs bounded execution
authorization; a planning proposal is not a verified conclusion.

## Leaves — pick by unit

| Depth work | Leaf |
| --- | --- |
| Open question, synthesis, landscape | `references/evidence-pack.md` |
| Compare named options, recommend one | `references/tradeoff-matrix.md` |
| Verify specific claims / sources / specs | `references/fact-check.md` |
| Direction for a downstream worker | `references/guidance.md` |

Each leaf names its QA contract; the validator enforces the
mapping.

## Boundaries

- **Depth, not heavy breadth.** Enumerations, surveys, and exhaustive source hunts
  are searcher units (`../plan-assistant-search/SKILL.md`); Researcher consumes
  their QA-passed findings. Agreed bounded preliminary depth discovery stays
  with Researcher and does not authorize a breadth survey or main investigation.
- **Conclusions, not artifacts.** The researcher never drafts the
  台本, copy, media, or code its conclusion feeds — that is
  writer/creator/engineer work consuming the unit.
- **Evidence, not artifact QA.** Artifact-vs-brief verdicts belong
  to your own QA pass; the researcher supplies the claim ledger it
  reads (`../qa-assistant-research/SKILL.md`).
- **Quick facts stay in Chat** — a one-minute lookup is inline,
  parallel in-turn lookups are `delegate_task`
  (`../chat-assistant/references/lookups.md`). Research units exist for supervised
  depth.
