# Researcher and Searcher

Research and search dialogue, phase entries and card gates. Part of the Hermes design docs — index: [`PROFILES.md`](../../PROFILES.md).

## Research and search dialogue

Researcher and Searcher accept Client purpose, consumer, constraints and budget,
not only prereleased units. Researcher proposes questions, option sets, criteria,
exact claims and evidence requirements; Searcher proposes retrieval questions,
coverage/floor, per-item fields, done conditions and exclusions. Each may propose
an ordered sequence of its own units with dependencies and stop points, never
decompose the cross-role project or assign other specialists. The Client agrees
within existing authority, then Build executes and QA self-checks. Caller
acceptance remains separate; Assistant's Client guides and acceptance contracts
are not a duplicate specialist planning or self-QA procedure.

An already explicitly authorized settled execution brief goes directly to Build.
Filled fields, a source/URL or transport kind alone are not authorization. Narrow
authorized inquiry may complete in one shot without ceremonial approval; complex
framing, feedback and work use a resident conversation. Agent Clients may
authorize ordinary inquiry within their grant, never substitute for human-only
permissions. Plan uses supplied material only: needed discovery is a separately
agreed bounded preliminary Build, then QA, then revised Plan and agreement for
the main scope — not release of the main work. A short approval advances the
retained proposal rather than restarting Plan. Bounded corrections return to
Build within scope/budget; expansion returns to Plan and agreement. Spec gaps and
evidence shortfalls remain explicit, not silently absorbed or narrowed into
success.

### Researcher

Researcher's v9.0.0 `researcher-pipeline` kernel routes three independent entries
outside `references/`: `plan-researcher`, `build-researcher`, `qa-researcher`.
Each owns four plain `references/<unit>.md` files for `evidence-pack` (question
and done conditions), `tradeoff-matrix` (options and equal criteria), `fact-check`
(exact claims and source requirements) and `guidance` (consumer decisions and
evidence base). Shared `references/gather.md` stays at the parent and is required
beyond a few direct lookups. `validate_researcher_entries` enforces the closed
tree, kernel dependencies, canonical recovery paths, output/verification
sections and the absence of card declarations.

Admiralty/SIFT source scoring, verbatim exact claims, durable claim ledgers,
evidence gaps and Review gates remain; research self-check is neither caller
acceptance, artifact-vs-brief craft QA nor the caller's final decision.
Researcher refuses every card, including the retired `claim-verification`.

Assistant reaches Researcher only through Engineer, Creator or Marketer, its
existing peers/session owners; no new direct peer. The consuming primary owns
the Researcher conversation and must relay the agreed baseline (questions, done
criteria, source policy, budget and approved changes) with conclusions. A
missing baseline stays unverified: Assistant requests it through that primary,
never reconstructs acceptance from purpose alone and never continues the
Researcher handle itself. Assistant's separate research/search Plan and QA
references retain the seven unit contract names; the validator enforces that
caller-side mapping.

### Searcher

Searcher's v7.0.0 `searcher-pipeline` kernel (retrieval, release and card gate)
routes `plan-searcher`, `build-searcher`, `qa-searcher`. Each independent entry
owns three plain `references/<unit>.md` files for `lookup`, `sweep`, `hunt`.
Retrieval and link integrity remain its limits: no trust verdicts, synthesis,
rankings or production.

Only two cards remain legal: `survey-enumeration` requires a settled question,
coverage claim/floor count and per-item fields; `exhaustive-hunt` requires a
settled question, done criteria and scope exclusions. The caller may author the
complete spec. A valid card goes directly Build -> QA -> terminal without Plan
negotiation or new approval; malformed/missing-input/non-catalog/composite cards
block with `kanban_block(kind=capability)` before any phase, never Plan on the
card. Existing dialogue, review, goal-mode and guarded-resume protocols remain.

### Entries and status

Both trees keep the exact old unit names as references, remove the old
unit-named skills without aliases and add no second common-mode index. All six
phase entries follow the shared [entry loading contract](../topology.md#entry-loading-contract):
full kernel, selected entry and selected unit-reference bodies on every
caller/judge/resume/completion turn and before phase/unit/scope changes,
including direct entry. Selection/resume never resets coverage/frontier or
consumed/remaining budget. Parent references are Hermes-specific dependencies:
never duplicate Gather, evidence floors or the kernel to satisfy the generic
portability check.

Status: implemented candidate, awaiting explicit live cutover and real-model
verification (see [topology](../topology.md) "Candidate rollout and cutover").
`test_researcher_entries.py`, `test_searcher_pipeline.py` and
`test_searcher_entry_runtime.py` stay registered in `verify-work-continuity.py`;
they check phase/unit contracts, card gates and real
discovery/read/dedup/recovery mechanics, not model routing or actual research.
No new profile, peer, tool grant, external root, card type or install mapping is
introduced, and no other profile gains these entries.
