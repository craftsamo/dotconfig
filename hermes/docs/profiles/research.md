# Researcher and Searcher

Research and search dialogue, mode entries and shared stages. Part of the Hermes design docs — index: [`PROFILES.md`](../../PROFILES.md).

## Research and search dialogue

Researcher and Searcher accept Client purpose, consumer, constraints and budget,
not only prereleased units. Researcher proposes questions, option sets, criteria,
exact claims and evidence requirements; Searcher proposes retrieval questions,
coverage/floor, per-item fields, done conditions and exclusions. Each may propose
an ordered sequence of its own units with dependencies and stop points, never
decompose the cross-role project or assign other specialists. The Client agrees
within existing authority, then Build executes and ends by self-checking its result. Caller
acceptance remains separate; Assistant's Client guides and acceptance contracts
are not a duplicate specialist planning or self-QA procedure.

An already explicitly authorized settled execution brief goes directly to Build.
Filled fields, a source/URL or transport kind alone are not authorization. Narrow
authorized inquiry may complete in one shot without ceremonial approval; complex
framing, feedback and work use a resident conversation. Agent Clients may
authorize ordinary inquiry within their grant, never substitute for human-only
permissions. Plan uses supplied material only: needed discovery is a separately
agreed bounded preliminary Build and its self-check, then revised Plan and agreement for
the main scope — not release of the main work. A short approval advances the
retained proposal rather than restarting Plan. Bounded corrections return to
Build within scope/budget; expansion returns to Plan and agreement. Spec gaps and
evidence shortfalls remain explicit, not silently absorbed or narrowed into
success.

### Researcher

Researcher's v11.0.0 `researcher-pipeline` kernel routes four mode entries, one
per kind of question: `investigate-researcher` (an open question, answered as an
evidence pack), `compare-researcher` (named options on fixed criteria, a
tradeoff matrix), `verify-researcher` (exact claims, verdicts and a durable
claim ledger) and `advise-researcher` (directives for a named consumer). Each
entry owns what Plan and Build mean for its question — framing, synthesis,
output template and the Verification its Build ends by self-checking against —
while the stages themselves are shared `references/plan.md` and `build.md`
(the evidence Method and the self-check) beside `references/gather.md`, which is
required beyond a few direct lookups.
On-chain evidence comes from the read-only `evm` and `solana` tools: the
kernel's source evaluation says how chain state, text in the chain and
name-based leads score, and `references/platforms/evm.md` and `solana.md`
(one per chain, like Marketer's per-service references) hold each chain's
patterns — who controls a contract or program, test calls, fund trails — and
limits. This is
the shape of Marketer's and Creator's advisory entries: modes named for the
work, one kernel, shared references. `validate_researcher_entries` enforces the
closed tree, kernel routing and links, canonical recovery paths and each
entry's stage sections. There is no separate QA stage: as in those advisory
entries, Build ends by checking its own result against the mode's
Verification, and acceptance stays with the caller.

Admiralty/SIFT source scoring, verbatim exact claims, durable claim ledgers,
evidence gaps and Review gates remain; research self-check is neither caller
acceptance, artifact-vs-brief craft QA nor the caller's final decision.

Assistant reaches Researcher only through Engineer, Creator or Marketer, its
existing peers/session owners; no new direct peer. The consuming primary owns
the Researcher conversation and must relay the agreed baseline (questions, done
criteria, source policy, budget and approved changes) with conclusions. A
missing baseline stays unverified: Assistant requests it through that primary,
never reconstructs acceptance from purpose alone and never continues the
Researcher handle itself. Assistant's separate research/search Plan and QA
references keep their seven deliverable names (`evidence-pack`,
`tradeoff-matrix`, `fact-check`, `guidance`; `lookup`, `sweep`, `hunt`), which
map to the investigate, compare, verify and advise modes and to Searcher's
modes of the same name; the validator enforces that caller-side mapping.

### Searcher

Searcher's v10.0.0 `searcher-pipeline` kernel (retrieval, release and the
resident runtime) routes three mode entries, `lookup-searcher`,
`sweep-searcher` and `hunt-searcher`, over the same shared Plan and Build
stage references. Retrieval and link integrity remain its limits: no trust
verdicts, synthesis, rankings or production. Beyond web search and `x_search`,
it reads public X posts, YouTube, note and Substack through the `x`, `youtube`,
`note` and `substack` tools, each limited to a public-only action list (see
[x-access.md](../x-access.md) "Profiles"), and reads chains through `evm` and
`solana` (what to record, kept to facts, in its own
`references/platforms/evm.md` and `solana.md`); the `x` tool's `search` is only
the fallback for when `x_search` is unavailable, within a capped share of the
shared X reads. It never gets the messaging tools, the user's own drafts,
statistics or channels, or any write.

Its last cards were the `survey-enumeration` and `exhaustive-hunt` units, which
ran a hunt through a `goal_mode` loop with a completion judge. Both are gone,
and so is `goal_mode`: a long or multi-hop retrieval is one resident
conversation the caller continues. A hunt keeps running hops until saturation,
its done criteria or the agreed cap, and a turn that must end first hands back
its ledger and gaps. The caller may author a complete brief, and an explicitly
authorized settled one goes directly to Build.

### Entries and status

Neither tree keeps an alias for its former `plan-`, `build-` and `qa-` entries
or their per-stage unit references, and neither adds a second common-mode
index. All seven mode entries follow the shared
[entry loading contract](../topology.md#entry-loading-contract): full kernel,
selected mode entry and current stage reference bodies on every
caller/judge/resume/completion turn and before mode/stage/scope changes,
including direct entry. Selection/resume never resets coverage/frontier or
consumed/remaining budget. Parent references are Hermes-specific dependencies:
never duplicate Gather, the stages, evidence floors or the kernel to satisfy
the generic portability check.

Status: implemented candidate, awaiting explicit live cutover and real-model
verification (see [topology](../topology.md) "Candidate rollout and cutover").
`test_researcher_entries.py`, `test_searcher_pipeline.py` and
`test_searcher_entry_runtime.py` stay registered in `verify-work-continuity.py`;
they check mode/stage contracts and real discovery/read/dedup/recovery
mechanics, not model routing or actual research. No new profile, peer, tool
grant, external root or install mapping is introduced, and no other profile
gains these entries.
