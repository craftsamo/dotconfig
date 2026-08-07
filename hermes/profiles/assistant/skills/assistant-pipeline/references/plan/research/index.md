# Research — plan

One mental model governs research: **you own the question and the
researcher is your hands on the evidence.** What a research unit must
settle — the question, the decision it serves, the axes or claims,
the source policy, what "answered" looks like — is fixed HERE, with
the user, before anything is released; the researcher turns a decided
brief into a verified conclusion under its own craft (gathering
strategy, trust scoring, corroboration mechanics are its business —
brief the WHAT, never the method). A brief whose deliverable-defining
decisions are still open is not releasable — the researcher returns
it as a **spec-gap finding**.

Research is depth only: verified conclusions with the evidence behind
them. Retrieval — sourced facts, enumerations, hunts — is the
searcher's (`../search/index.md`); a crafted artifact (台本, copy,
media) built on a conclusion is writer/creator work consuming it.

## Units — the four kinds

| Unit | Releases with | What it is |
| --- | --- | --- |
| **Evidence-pack unit** | the settled question + done criteria | one open question answered with verified evidence — deep synthesis, landscape analysis, "what do we actually know about X" |
| **Tradeoff-matrix unit** | decision + closed option set + criteria | one comparison — named options scored against fixed axes, with a recommendation |
| **Fact-check unit** | fixed claims list + source requirements | per-claim verdicts (supported / refuted / partly true / unverifiable) with sources and counterevidence |
| **Guidance unit** | consumer + decision points + evidence base | evidence-backed direction — MUST/SHOULD directives and open choices a downstream worker can act on |

A question that is really several questions, or a matrix whose option
set keeps growing, is a **granularity finding** — decompose, never
stretch the unit. Card eligibility: a settled fact-check unit may
ride kanban as `claim-verification`
(`../../execute/research/index.md`); every other unit stays resident —
synthesis and comparison move with the user on purpose.

## The decision core (every brief)

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
  the brief (not pointers); breadth the unit will need is a search
  unit released first, never ground by the researcher.
- **Durable path** — where ledgers and long reports land; the
  conclusion lives in the reply.
- **Consumer** — who acts on the conclusion next (you, the user,
  writer, marketer, the QA pass); the consumer fixes the output
  shape and the ledger requirement.

Family-specific decisions live in the leaves; fill objective
defaults yourself and say so, one `clarify` round at most.

## Grounding — the researcher informs, you decide

Uncertain scope ("how deep does this go?") is grounded by opening
the session with the open question and letting its first reply size
the work before you promise depth to the user. A live planning
decision of your own is a tradeoff-matrix unit briefed as a
consultation — the matrix informs; the decision stays here.

## Leaves — pick by unit

| Depth work | Leaf |
| --- | --- |
| Open question, synthesis, landscape | `evidence-pack.md` |
| Compare named options, recommend one | `tradeoff-matrix.md` |
| Verify specific claims / sources / specs | `fact-check.md` |
| Direction for a downstream worker | `guidance.md` |

Each leaf names its QA contract; the validator enforces the
mapping.

## Boundaries

- **Depth, not retrieval.** Enumerations, surveys, and source hunts
  are searcher units (`../search/index.md`); the researcher starts
  from their QA-passed findings.
- **Conclusions, not artifacts.** The researcher never drafts the
  台本, copy, media, or code its conclusion feeds — that is
  writer/creator/engineer work consuming the unit.
- **Evidence, not artifact QA.** Artifact-vs-brief verdicts belong
  to your own QA pass; the researcher supplies the claim ledger it
  reads (`../../quality-assurance/research/index.md`).
- **Quick facts stay in Chat** — a one-minute lookup is inline,
  parallel in-turn lookups are `delegate_task`
  (`../../chat/lookups.md`). Research units exist for supervised
  depth.
