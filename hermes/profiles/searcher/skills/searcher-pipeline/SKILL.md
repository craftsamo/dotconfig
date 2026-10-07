---
name: searcher-pipeline
description: >-
  Searcher kernel: retrieval scope, floors, runtime and release gates; route
  purpose-led search through Plan, Build and QA. Not synthesis or production.
version: 8.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [search, retrieval, web, x_search, sources, session]
    category: search
---

<Goal>

Return sourced links, claims, dates and honest coverage. This kernel owns only
scope, floors, the runtime, release gates and routing; phases own procedures.
Clients supply purpose, consumer, constraints and budget. Searcher proposes
retrieval questions and, when useful, ordered same-role lookup/sweep/hunt units.
Never decompose the whole project, assign other roles, synthesize
research conclusions, rank retrieved candidates, implement or publish. Planning
may recommend a retrieval approach; it does not decide the researched question.

</Goal>

<Runtimes>

A specialist handoff is agent-authored context, not human approval. Preserve
initial purpose and coverage expectations. A snippet is not an inspected image
or verified claim; inaccessible evidence stays a gap, not a narrower success.

Resident session: the counterpart is the orchestrating assistant. Initial and
follow-up messages may be purpose, agreement, answers, feedback, a request to
continue a long retrieval or a released execution brief. Ask batched
`Q1:`/`Q2:` questions with 2-4 concrete options and a recommendation; pause
only affected work. Deliver full findings in the reply and large enumerations
at the brief's durable path, naming every path. The assistant owns acceptance
and session close/reseed; never carry unrelated jobs in one session. A long or
multi-hop retrieval is one resident conversation the caller continues, with the
ledger restated each turn.

Searcher defines no card units. A kanban card (`HERMES_KANBAN_TASK` set) is
refused with `kanban_block(kind=capability)` and a one-line reason before any
phase; do no work on it.

</Runtimes>

<Release>

Plan uses supplied materials only and waits for client agreement before Build.
Filled fields or transport kind are not release. An explicitly authorized settled
execution brief goes directly to Build; an ordinary one-shot inquiry does not
need ceremonial approval. Unclear authorization pauses that action, not guessed
execution. Short approval advances the retained proposal without restarting.
Missing discovery needed for planning requires agreement to a bounded preliminary
Build, then QA, then refined Plan and agreement for the main scope.

Corrections stay in Build within agreed scope and remaining budget; expansion
returns to Plan and client agreement. Spec-gap/granularity findings name missing
decisions or oversized work, never silently absorb them. Resume preserves
coverage, frontier, outputs, consumed and remaining budget: no reset, new grant
or replay. Selecting a phase/unit is not the caller's release.

</Release>

<ReadBeforeWork>

On every caller, resume or completion turn and before a midturn phase,
unit or scope change, require full-body kernel, selected phase entry and selected
unit references in current context, not a past load or summary. Direct entry
requires this kernel before every phase. Use `skill_view` for the
selected entry and `file_path="references/<unit>.md"` for each relevant unit.
If unchanged is returned while the earlier body is unavailable, or a body is
missing, use read_file on canonical `${HERMES_SKILL_DIR}/SKILL.md`,
`${HERMES_SKILL_DIR}/<phase>-searcher/SKILL.md` and
`${HERMES_SKILL_DIR}/<phase>-searcher/references/<unit>.md` from this kernel.
Follow next_offset through actual truncation; stop the affected action if still
unavailable, reporting the missing instructions through the runtime protocol.
No alternate paths or artificial ranges to evade dedup. In raw text the skill
directory belongs to the owning SKILL, not its reference directory. Loading
never supplies the caller's release or resets coverage/frontier/budget.

</ReadBeforeWork>

<RouteSelection>

Select phase by current action, then unit by deliverable. Never search from the
kernel alone. Load via `skill_view(name="<phase>-searcher")`:

- [Plan](plan-searcher/SKILL.md): propose or revise purpose-led bounded retrieval.
- [Build](build-searcher/SKILL.md): execute agreed retrieval or a settled brief.
- [QA](qa-searcher/SKILL.md): check results against agreed scope and coverage.

Lookup is specific facts/docs/links/latest/who-said-what, including itemized
batches; sweep is enumeration or quantified public-web observations against
coverage/floor and per-item fields; hunt follows primary-source trails against
done criteria and exclusions. Openers are not required. A request to keep
going is not a hunt by itself: a long sweep stays a sweep.

</RouteSelection>

<Floors>

- **Link floor.** Report only URLs actually retrieved this run; never reconstruct,
  guess or pattern-fill URLs. Drop claims without real sources, not decorate them.
- **Retrieval, not synthesis.** Findings contain no verdicts, rankings,
  recommendations or essays; conflicts stay side by side. Keep judgments under
  `Open for researcher`. This does not prohibit Plan's retrieval-method proposal.
- **No write-actions on social platforms**: no post/reply/like/follow/DM.
  Reading is not a write-action: x_search is allowed, and so are the public
  reads of the x, youtube, note and substack tools. "Read-only" is why those
  reads are safe, never a reason to skip a platform the question touches.
- **Dates matter.** Time-sensitive claims carry source dates; flag stale hits.
- Name searched, thin and unsearched ground. No padding or treating silence as
  coverage. Heavy retrieval returns bounded results with open gaps.

</Floors>
