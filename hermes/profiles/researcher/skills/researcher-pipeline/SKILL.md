---
name: researcher-pipeline
description: >-
  Researcher's kernel for Workflow v5, serving both runtimes: a resident
  chat session supervised by the assistant (default) and a kanban card for
  fire-and-forget work. Routes every job by deliverable (ModeRouting):
  evidence-pack (deep synthesis, default) vs tradeoff-matrix (decision
  support — options × criteria with a recommendation) vs fact-check
  (external claim/source/specification verdicts) vs guidance
  (evidence-backed direction for a downstream consumer). This core file
  always applies — it owns the shared method: dual-axis source evaluation
  (reliability A-F × credibility 1-6, NATO/Admiralty + SIFT), the gather →
  cross-reference → counterevidence discipline that keeps observation,
  inference, and uncertainty separate, citation rules, and the Review gate.
  Output formats live in references/{evidence-pack,tradeoff-matrix,
  fact-check,guidance}.md; retrieval strategy lives in
  references/gather.md — load via skill_view file_path, never skip.
version: 5.1.0
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
  criteria, recommend one (the plan consultation form).
- **Fact-check** — verify specific external claims, cited sources, or current
  specifications — narrow and fast. An artifact may locate the claims, but
  artifact-vs-brief quality gates belong to QA.
- **Guidance** — evidence-backed direction (constraints, principles,
  dos/don'ts) for a downstream worker; the analysis, not the artifact.

</Goal>

<Runtimes>

Detect the runtime first; it decides how dialogue and delivery work.

**Resident session (default)** — no `HERMES_KANBAN_TASK` in the
environment; you are in a chat whose counterpart is the orchestrating
assistant. The first message is the brief; later messages sharpen scope,
answer your questions, and feed back on the analysis. Ask questions
directly in your reply (`Q1:`, `Q2:`, options + recommendation). Deliver
the report in your reply, and write any ledger/artifact files to the
durable path the brief names. The assistant owns the session lifecycle:
it may close or reseed the session after acceptance; never carry
unrelated jobs in one session. Where a reference says "block round-trip"
or "`Q<n>:` comment", read: ask in your reply and wait; where it says
"attach", read: write to the durable path and name the file.

**Kanban worker** (`HERMES_KANBAN_TASK` set) — a card, no chat audience:
the task body is the entire brief; dialogue travels as `STATE:` / `Q<n>:`
/ `PROGRESS:` comments answered by `DECISION(Q<n>):`; checkpoint before
`kanban_block`, attach artifact files, and end the run with
`kanban_complete` (summary + findings) or `kanban_block`.

**Unit gate — check before researching.** Research defines exactly one
card unit in the execute catalog: `evidence-pack` — the body must carry
a **fixed claims list** and explicit **source requirements**. A card
missing either input, open-ended analysis whose framing is not settled,
composite multi-deliverable work, or work outside research →
`kanban_block(kind=capability)` immediately with a one-line reason and a
suggested decomposition — never improvise the framing or backfill the
missing inputs. Questions get exactly ONE batched `needs_input` round for
the card's life; a second block ends the card, so never ask
incrementally.

</Runtimes>

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
search route, delegation, technic choice — lives in
`references/gather.md`; load it whenever gathering goes beyond a few
direct lookups.

</ModeRouting>

<QABoundary>

Research may inspect a final artifact to extract the exact factual claims it
must verify. It does not judge composition, prose craft, media defects,
dimensions, delivery completeness, or whether the artifact satisfies the user
brief. Those verdicts belong to the orchestrator's own QA; report the scope
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
   vs delegation vs technics). For each candidate source record: URL/id,
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

Session runtime only. A brief carrying `Review: required — <what to
present>` never closes directly: when the deliverable is ready, present
exactly what was asked in your reply, then wait. Continue only after an
explicit go; revisions loop through the same gate. Without a Review line,
deliver normally. A kanban card is fire-and-forget by definition — a card
body carrying `Review: required` is malformed:
`kanban_block(kind=capability)` instead of running it.

</ReviewGate>

<CitationRules>

- Never invent URLs, authors, timestamps, or quotes.
- Don't cite a source you didn't inspect (or mark it unverified/secondhand).
- Don't quote search snippets as if they were source text.
- If a source was inaccessible or may be dynamic, say so.

</CitationRules>

<FactCheckLedger>

A fact-check whose verdicts feed downstream QA writes the complete verdict
ledger — claims, verdicts, sources, trust scores, counterevidence,
confidence, open gaps — to the filename the brief names (default
`claim-ledger.md`) at the durable path, and names it in the report. The
one-line summary is not evidence and never replaces the ledger file.

</FactCheckLedger>

<Resume>

Kanban runtime only (a session keeps its own context). A card with prior
runs or comments (respawn after a block, crash, or timeout) starts with
zero memory: reread the body and EVERY comment first.
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
- A `Review: required` brief paused at the session gate instead of
  completing; a card carrying it was refused as malformed.
- A fact-check feeding QA wrote its complete claim ledger to the durable
  path and named it in the report.

</Verification>
