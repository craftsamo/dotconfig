---
name: execute-assistant-research
description: "Execute research: supervise proposal agreement, Build and self-check through the consuming primary. Accept conclusions independently; never call Researcher directly."
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: assistant-pipeline
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
If a tool returns unchanged while the earlier body is unavailable, use read_file on `${HERMES_SKILL_DIR}/../SKILL.md` and `${HERMES_SKILL_DIR}/../references/execute/index.md`.
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
**The researcher is not your peer**: you never start researcher
sessions. Research is consumed through
the peers whose peer the researcher is — creator or marketer —
inside their own work. Code-level evidence (what a repository actually does)
comes from an OpenCode plan run, not from Researcher.

## Routing through peers

Send purpose, consumer, constraints, budget and durable path, or your explicitly
authorized settled brief (`../plan-assistant-research/references/`), to the consuming
primary: the marketer
verifies public claims against sources, the creator grounds factual
content in media. That primary is Researcher's immediate Client: it requests
specialist Plan for purpose-first work, agrees the proposed same-role units
within its granted scope, then releases Build. It escalates material human-only
or out-of-scope decisions through you. Researcher's Build ends with a specialist
self-check; the primary independently accepts conclusions and returns its own
deliverable for your acceptance. Self-QA is not an external pass.

Require the primary to return the agreed research proposal/scope alongside
conclusions: questions, done criteria, source policy, budget and approved changes
(explicitly none when unchanged). The primary owns this agreement; Assistant
uses the relayed baseline for acceptance, never reconstructs it from purpose.
An explicitly authorized original settled brief is the alternative baseline
when it remains unchanged. Missing baseline means unverified: request it as a
spec-gap through the primary before acceptance.

A bounded authorized researcher inquiry may be one-shot over the primary's
configured peer route; `kind="inquiry"` alone is not authorization. An explicitly
authorized settled brief goes directly to Build without unnecessary reapproval.
Complex proposal/approval back-and-forth uses resident `kind="work"`.
The primary owns and continues the Researcher work handle and `conversation_id`.
Assistant uses only its own PRIMARY work handle for `specialist_call` messages
and `specialist_session` lifecycle; Assistant never holds or uses the Researcher
conversation. Ask the primary to relay proposals, agreements, baselines and
feedback, never contact Researcher directly. Do not invent proposal state tooling.
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

- Starting a researcher session —
  the direct assistant→researcher path is closed; route through the
  consuming primary.
- Sending heavy breadth retrieval through this path: enumerations and hunts are
  search units. This does not prohibit agreed bounded preliminary depth discovery.
- Deep analysis inline — it floods your own context.
- Treating a purpose-first Plan request as malformed because it lacks detailed
  questions, or releasing Build without agreed done criteria and authorization.
- Forwarding conclusions whose load-bearing sources the consuming
  primary never opened — its verification duty travels with the
  request.
