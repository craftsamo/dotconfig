---
name: researcher-pipeline
description: >-
  Researcher's task kernel — pinned on every dispatched card. Routes every
  task by deliverable (ModeRouting): evidence-pack (deep synthesis, default)
  vs tradeoff-matrix (decision support — options × criteria with a
  recommendation) vs fact-check (external claim/source/specification verdicts)
  vs guidance (evidence-backed direction for a downstream worker or QA).
  This core file always applies — it owns the shared method: dual-axis
  source evaluation (reliability A-F × credibility 1-6, NATO/Admiralty +
  SIFT), the gather → cross-reference → counterevidence discipline that
  keeps observation, inference, and uncertainty separate, citation rules,
  and the Review gate. Output formats live in references/{evidence-pack,
  tradeoff-matrix,fact-check,guidance}.md; retrieval strategy and fan-out
  live in references/gather.md — load via skill_view file_path, never skip.
version: 3.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [research, methodology, sources, citations, synthesis, verification, tradeoff, fact-check, guidance]
    category: research
---

<Goal>

The standard method for research tasks. Accuracy outranks speed, confidence,
and completeness — the goal is evidence the caller can verify and act on,
shaped to what the caller actually asked for:

- **Evidence-pack** — deep synthesis of a question (default).
- **Tradeoff-matrix** — decision support: compare named options against
  criteria, recommend one (the Plan-Loop consultation form).
- **Fact-check** — verify specific external claims, cited sources, or current
  specifications — narrow and fast. An artifact may locate the claims, but
  artifact-vs-brief quality gates belong to QA.
- **Guidance** — evidence-backed direction (constraints, principles,
  dos/don'ts) for a downstream worker; the analysis, not the artifact.

</Goal>

<Scope>
<UseWhen>

- Any analysis / synthesis / research task assigned to the researcher.
- Skip only when the caller explicitly wants unsupported brainstorming.

</UseWhen>
</Scope>

<ModeRouting>

Route by the **deliverable the body asks for** — openers are hints, never
required. Pick the mode first, then **load the matching reference with
`skill_view` (`file_path=references/<file>`) before gathering**. Never
deliver from this core file alone.

| Signal (check in order) | Mode | Load |
| --- | --- | --- |
| Body opens with `Advisory — inform the plan, don't ship.` (legacy opener) — or asks to compare named options / pick between approaches for a decision | Tradeoff-matrix | `references/tradeoff-matrix.md` |
| Body presents specific external claim(s), sources, or current specifications to verify ("is it true that…", "confirm/refute…") | Fact-check | `references/fact-check.md` |
| Deliverable is direction a downstream worker (or the user) will act on — design principles, constraints, dos/don'ts derived from sources or parent results | Guidance | `references/guidance.md` |
| Anything else (open question, landscape analysis, synthesis) | Evidence-pack | `references/evidence-pack.md` |

The shared method below applies in every mode; the reference sets the
procedure emphasis, output format, and done criteria. Gathering strategy —
search route, searcher fan-out, technic choice — lives in
`references/gather.md`; load it whenever gathering goes beyond a few
direct lookups.

</ModeRouting>

<QABoundary>

Research may inspect a final artifact to extract the exact factual claims it
must verify. It does not judge composition, prose craft, media defects,
dimensions, delivery completeness, or whether the artifact satisfies the user
brief. A task asking for those verdicts is misrouted to `qa`; report the scope
mismatch instead of producing an artifact-quality pass/fail.

</QABoundary>

<SourceEvaluation>

Rate reliability and credibility SEPARATELY. Adapted from the NATO/Admiralty system
(AJP-2.1) + SIFT (Caulfield) + primary/secondary/tertiary. Keep the two axes
independent — a reputable outlet can still carry an uncorroborated claim, and a weak
source can still be right; separating them prevents halo bias.

Source reliability (the outlet/author, by class):
- A Reliable — primary/official: standards & specs, official docs, source code/repos,
  peer-reviewed papers, filings, the originator's own statement.
- B Usually reliable — reputable secondary: established docs, major references,
  journalism with a track record, recognized domain experts.
- C Fairly reliable — identifiable author + reputation/editorial signal
  (known-practitioner blog, accepted/high-voted Q&A).
- D Not usually reliable — anonymous/low-history web, marketing, SEO summaries, unvetted forums.
- E Unreliable — content farms, known-bad track record, undisclosed agenda.
- F Can't judge yet — new/unknown source; verify before relying.

Claim credibility (the specific claim, by corroboration):
- 1 Confirmed (>=2 independent reliable sources, consistent) · 2 Probably true ·
  3 Possibly true · 4 Doubtful · 5 Improbable (contradicted) · 6 Can't judge yet.

Rule of thumb: rely on ~A/B + 1/2. Treat single-source, reliability <= C, or
credibility >= 3 as needing corroboration. Never present E/5 or F/6 as fact.
Classify sources as **primary** (originator), **secondary** (reputable reporting/docs),
or **noisy** (X, forums, reposts, SEO summaries), and feed both axes into the
Observation / Corroboration / Inference / Uncertainty buckets below.

</SourceEvaluation>

<Method>

The shared gathering discipline, every mode:

1. **Scope.** Restate the question, the caller's decision context, success
   criteria, and key sub-questions. State an assumption and proceed when a
   missing detail doesn't change the search strategy.
2. **Gather breadth** per `references/gather.md` (search route, own tools
   vs searcher fan-out vs technics). For each candidate source record: URL/id,
   author/publisher, publication time, retrieval time (when recency matters),
   reliability (A–F), what it supports, and what it does *not* prove.
3. **Extract directly, not from memory.** Fetch and read the source (web extract,
   browser, file). Don't rely on remembered summaries when the source is fetchable.
4. **Deep-read** the highest-trust sources. Quote exactly only when wording
   matters and keep quotes short; otherwise summarize and label it a summary.
5. **Cross-reference / triangulate.** Do independent sources agree? Weight by
   trust. Mark a claim with only one source as single-source.
6. **Seek counterevidence.** Actively look for material that contradicts or
   weakens the emerging conclusion; don't stop at confirming sources.
7. **Separate categories** explicitly:
   - Observation — what a source directly says/shows
   - Corroboration — independent support (or single-source / contradicted)
   - Inference — what may follow from the evidence
   - Uncertainty — unknown, stale, or weakly supported

Then synthesize and deliver per the loaded reference's format.

</Method>

<ReviewGate>

A body carrying `Review: required — <what to present>` never completes
directly: at the point the deliverable is ready, post a comment opening
with a `REVIEW:` headline presenting exactly what the body asked for, then
`kanban_block(kind=needs_input)` and stop. Complete only after a comment
approves (a `DECISION:` or equivalent explicit go); revisions loop through
the same gate. Without a Review line, deliver and complete normally —
post-hoc review via the completion notification is the default.

</ReviewGate>

<CitationRules>

- Never invent URLs, authors, timestamps, or quotes.
- Don't cite a source you didn't inspect (or mark it unverified/secondhand).
- Don't quote search snippets as if they were source text.
- If a source was inaccessible or may be dynamic, say so.

</CitationRules>

<FactCheckHandoff>

Fact-check cards that feed QA must write the complete verdict ledger, sources,
trust scores, counterevidence, confidence, and open gaps to the filename named
by `Output` (default `claim-ledger.md`) and attach it with `kanban_attach` before
completion. The one-line `kanban_complete` summary is not evidence and never
replaces this attachment. Record the attachment name in completion metadata.

</FactCheckHandoff>

<Resume>

A task with prior runs or comments (respawn after a block, crash, or
timeout) starts with zero memory: reread the body and EVERY comment first.
Honor recorded `DECISION:` answers — never re-ask; rebuild from your own
`STATE:`/`REVIEW:` notes and the final messages of parent tasks. The
scratch workspace does not survive runs — anything not in the card thread
or attachments is gone; re-gather only what is not recoverable, and post a
brief `STATE:` note before continuing so the next respawn starts warmer.

</Resume>

<Pitfalls>

- Delivering without loading the mode reference — the output format and done
  criteria live there.
- A high search ranking is not high trust — score the source, not its position.
- Virality / repetition is evidence of attention, not truth.
- One plausible source is not enough for a high-impact claim.
- Letting your own inference blur into observed source content.

</Pitfalls>

<Verification>

- Mode routed per <ModeRouting>; output follows the loaded reference's format.
- Every nontrivial claim traces to a scored source, a direct observation, or a
  stated uncertainty.
- Quotes are verbatim and short; metadata suffices for later verification.
- Counterevidence was considered; confidence and open gaps are stated.
- A `Review: required` body blocked at the gate instead of completing.
- A fact-check feeding QA attached its complete claim ledger.

</Verification>
