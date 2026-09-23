# Researcher and Searcher

Research and search dialogue. Part of the Hermes design docs — index: [`PROFILES.md`](../../PROFILES.md).

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
framing and feedback use a resident conversation. Agent Clients may authorize
ordinary inquiry within their grant, never infer human-only permissions. Plan
uses supplied material only: needed discovery is a separately agreed bounded
preliminary Build, then QA, then revised Plan and agreement for the main scope.
A short approval advances the retained proposal rather than restarting Plan.

Researcher's v9.0.0 `researcher-pipeline` kernel routes three independent entries
outside `references/`: `plan-researcher`, `build-researcher`, `qa-researcher`.
Each owns four plain `references/<unit>.md` files for `evidence-pack` (question
and done conditions), `tradeoff-matrix` (options and equal criteria), `fact-check`
(exact claims and source requirements) and `guidance` (consumer decisions and
evidence base). Shared `references/gather.md` stays at the parent and is required
beyond a few direct lookups. Admiralty/SIFT scoring, exact claims, durable claim
ledgers and Review gates remain; research self-check is neither artifact craft QA
nor the caller's final decision. Assistant reaches Researcher only through
Engineer, Creator or Marketer, its existing peers/session owners; no new direct
peer. Researcher refuses every card, including the retired `claim-verification`.
The consuming primary owns the Researcher conversation and relays the agreed
baseline (questions, done criteria, source policy, budget and approved changes)
with conclusions. A missing baseline is unverified, not acceptable from purpose
alone. Assistant's separate research/search Plan and QA references retain the
seven unit contract names; the validator enforces that caller-side mapping.

Searcher's v7.0.0 `searcher-pipeline` kernel routes `plan-searcher`,
`build-searcher`, `qa-searcher`. Each independent entry owns three plain
`references/<unit>.md` files for `lookup`, `sweep`, `hunt`. Retrieval and link
integrity remain its limits: no trust verdicts, synthesis, rankings or production.
Only two cards remain legal: `survey-enumeration` requires a settled question,
coverage claim/floor count and per-item fields; `exhaustive-hunt` requires a
settled question, done criteria and scope exclusions. The caller may author the
complete spec. A valid card goes directly Build -> QA -> terminal without Plan
negotiation or new approval; malformed/missing-input/non-catalog/composite cards
block with `kanban_block(kind=capability)` before any phase, not Plan on the card.
Existing dialogue, review, goal-mode and guarded-resume protocols remain.

Both trees preserve the exact old unit names as references, remove old unit-skill
names without aliases and add no second common-mode index. All six phase entries
require full kernel, selected entry and selected unit-reference bodies in current
context on every caller/judge/resume/completion turn and before phase/unit/scope
changes, including direct entry. Past loads, summaries and root preload are not
sufficient. If `skill_view` dedup returns unchanged with a missing body, recover
via canonical `read_file`, following `next_offset` through actual truncation, or
stop the affected action. No alternate paths or artificial ranges to evade dedup.
Selection/resume never grants scope, resets coverage/frontier or consumed/remaining
budget, or replays completed work. Bounded corrections return to Build within
scope/budget; expansion returns to Plan and agreement. Spec gaps and evidence
shortfalls remain explicit, not silently absorbed or narrowed into success.

This is an implemented isolated candidate, awaiting explicit live cutover and
real-model verification; other roles' recorded deployment dates remain unchanged.
The existing `test_researcher_entries.py`, `test_searcher_pipeline.py` and
`test_searcher_entry_runtime.py` suites remain in `verify-work-continuity.py`.
They check phase/unit contracts and real discovery/read/dedup/recovery mechanics,
not model compliance or live research. Use provisioned Hermes Python/source
PYTHONPATH, isolated HOME and paired public/private candidates through
`HERMES_PRIVATE_ROOT` / `HERMES_PUBLIC_ROOT`, respectively. Never install/restart
or repoint live links for tests, relax Git ownership checks, or rewrite runtime
jobs, frozen outputs or approvals. Approved cutover refreshes applicable process
indexes and uses fresh sessions; file edits do not invalidate cached indexes.
The generic skill-authoring parent-reference portability exception remains:
Hermes validates the real pipeline owner, not standalone child packages. Do not
duplicate Gather or the kernel to silence that check. No new profiles, tool
grants, external roots, card types or install mappings are introduced.
