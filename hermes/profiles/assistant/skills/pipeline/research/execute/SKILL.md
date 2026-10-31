---
name: execute-research
description: "Execute research: agree proposals, supervise Build and self-check directly or through the consuming primary. Accept conclusions independently."
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: pipeline
    tags: ["execute", "research"]
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
If a tool returns unchanged while the earlier body is unavailable, use read_file on `${HERMES_SKILL_DIR}/../../SKILL.md` and `${HERMES_SKILL_DIR}/../../references/execute/index.md`.
Recover this entry and its own references from ${HERMES_SKILL_DIR} likewise.
Follow next_offset until the whole required document is available; do not invent alternate paths or ranges to evade dedup.
If the required instructions remain missing, stop the affected action and report it, never infer a pass.
Read only applicable detail references below.

</ReadBeforeWork>

# Research — execute

The specialist is the **researcher** — analytic hands; it verifies
and concludes, it never performs heavy breadth retrieval and never crafts.
Bounded preliminary depth discovery is allowed only after primary agreement;
enumerations, surveys and exhaustive hunts remain Searcher dependencies — yours
to release, or the consuming primary's within the budget you granted it, in
which case it relays Searcher's coverage statement and spend with the baseline.
**Calling Researcher**: call researcher directly for standalone research
deliverables (evidence-pack, tradeoff-matrix, fact-check, guidance); route
through creator or marketer when grounding their own creative or marketing work.
Code-level evidence (what a repository actually does)
comes from an OpenCode plan run, not from Researcher.

## Routing: direct or through peers

For standalone research, call Researcher directly via `specialist_call`: kind="inquiry"
for short bounded consultation (A2A), or kind="work" (resident) for planning dialogue,
complex framing or metered work. Assistant is Researcher's immediate Client, agrees
the proposal within existing authority, and independently accepts conclusions.

When research grounds media or marketing work, send purpose, consumer, constraints, budget and durable path, or your explicitly
authorized settled brief (`../plan/references`), to the consuming
primary: the marketer
verifies public claims against sources, the creator grounds factual
content in media. That primary is Researcher's immediate Client: it requests
specialist Plan for purpose-first work, agrees the proposed same-role units
within its granted scope, then releases Build. It escalates material human-only
or out-of-scope decisions through you. Researcher's Build ends with a specialist
self-check; the primary independently accepts conclusions and returns its own
deliverable for your acceptance. Self-QA is not an external pass.

When routing through a primary, require the primary to return the agreed research proposal/scope alongside
conclusions: questions, done criteria, source policy, budget and approved changes
(explicitly none when unchanged). The primary owns this agreement; Assistant
uses the relayed baseline for acceptance, never reconstructs it from purpose.
An explicitly authorized original settled brief is the alternative baseline
when it remains unchanged. Missing baseline means unverified: request it as a
spec-gap through the primary before acceptance.

A bounded authorized researcher inquiry may be one-shot (directly over A2A or via the primary's
configured peer route); `kind="inquiry"` alone is not authorization. An explicitly
authorized settled brief goes directly to Build without unnecessary reapproval.
Complex proposal/approval back-and-forth uses resident `kind="work"`.
When calling directly, Assistant owns and continues the Researcher work handle and `conversation_id`.
When routing through a primary, that primary owns and continues the Researcher work handle and `conversation_id`;
Assistant uses only its own PRIMARY work handle for `specialist_call` messages with that primary.
Fields or transport choice never release work. Plan permits no unapproved
search: a bounded preliminary Build needs agreement, followed by its result
and separate agreement on the refined main proposal before main Build.
Undecided defining choices are **spec-gap findings** for Plan; work larger than
its agreed unit is a **granularity finding**, not permission to expand Build.

Every research unit type — evidence-pack, tradeoff-matrix,
fact-check, guidance — moves this way, and
synthesis never lands in your own turn.

## Part handoff

QA-passed conclusions remain a **part** for other capabilities —
paste the conclusions (not a pointer) into the consuming brief; the
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

- Calling Researcher directly for work that grounds creator or marketer output —
  route that work through the consuming primary so it owns the baseline and media grounding.
- Sending heavy breadth retrieval through this path: enumerations and hunts are
  search units. This does not prohibit agreed bounded preliminary depth discovery.
- Deep analysis inline — it floods your own context.
- Treating a purpose-first Plan request as malformed because it lacks detailed
  questions, or releasing Build without agreed done criteria and authorization.
- Forwarding conclusions whose load-bearing sources the consuming
  primary never opened — its verification duty travels with the
  request.
