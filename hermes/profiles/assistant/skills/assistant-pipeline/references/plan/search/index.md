# Search — plan

One mental model governs search: **you own the question and the
searcher is your hands on the open web.** What a retrieval must
answer — the question, the coverage claim, the freshness window,
what "answered" looks like — is fixed HERE, with the user, before
anything is released; the searcher turns a decided brief into
sourced findings under its own craft (query strategy, source
triage, dedup mechanics are its business — brief the WHAT, never
the search tactics). A brief whose deliverable-defining decisions
are still open is not releasable — the searcher returns it as a
**spec-gap finding**.

Search is retrieval only: links + claims with an honest coverage
statement. Verdicts, synthesis, and comparisons are the
researcher's (`../research/index.md`).

## Units — the three kinds

| Unit | Releases with | What it is |
| --- | --- | --- |
| **Lookup unit** | the settled question | one specific sourced answer — a fact, a link/doc, "latest on X", who-said-what; batches of related questions release as one unit with an itemized list |
| **Sweep unit** | question + coverage claim/floor + per-item fields | one enumeration/survey — candidates, examples, instances — or a quantified observation of public web state |
| **Hunt unit** | question + done criteria + scope exclusions | one exhaustive multi-hop source hunt — obscure topic, contested claim's primary sources, provenance chase |

A sweep whose coverage claim is really several sweeps, or a lookup
that keeps growing hops, is a **granularity finding** — decompose,
never stretch the unit. Card eligibility: a settled sweep unit may
ride kanban as `survey-enumeration`, a settled hunt unit as
`exhaustive-hunt` (`../../execute/search/index.md`); lookups never
ride kanban — they are chat work or a session turn.

## The decision core (every brief)

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

Family-specific decisions live in the leaves; fill objective
defaults yourself and say so, one `clarify` round at most.

## Grounding — the searcher informs, you decide

Uncertain scope ("how much is even out there?") is grounded by a
cheap lookup unit first — its coverage statement sizes the sweep or
hunt before you promise breadth to the user. The finding informs;
the decisions stay here.

## Leaves — pick by unit

| Retrieval | Leaf |
| --- | --- |
| Specific answer, fact, link, latest-on-X | `lookup.md` |
| Enumeration / survey with a coverage claim | `sweep.md` |
| Exhaustive multi-hop source hunt | `hunt.md` |

Each leaf names its QA contract; the validator enforces the
mapping.

## Boundaries

- **Retrieval, not depth.** Analysis, synthesis, tradeoffs,
  verification verdicts, and guidance are researcher units
  (`../research/index.md`); a crafted artifact built on findings is
  writer/creator work.
- **Quick and medium lookups stay in Chat** — a one-minute fact is
  inline, parallel in-turn lookups are `delegate_task`
  (`../../chat/lookups.md`). Search units exist for durable,
  supervised retrieval.
- The searcher reads social platforms; it never posts, replies,
  likes, or DMs — publishing actions are the marketer's gated work.
