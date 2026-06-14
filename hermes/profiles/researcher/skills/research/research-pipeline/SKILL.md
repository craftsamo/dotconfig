---
name: research-pipeline
description: Researcher's evidence-grounded pipeline — search route, source trust scores, and a gather -> cross-reference -> synthesize -> judge procedure that keeps observation, inference, and uncertainty separate.
version: 1.0.0
author: Hermes Agent
metadata:
  hermes:
    tags: [research, methodology, sources, citations, synthesis, verification]
    category: research
---
# Research pipeline (researcher)

The standard method for research tasks. Accuracy outranks speed, confidence, and
completeness. The goal is evidence the caller can verify and act on — not a
confident-sounding answer.

## When to Use
- Any analysis / synthesis / research task assigned to the researcher.
- Skip only when the caller explicitly wants unsupported brainstorming.

## Search route (breadth, in order; trace every claim to its original context)
1. Primary / official (docs, specs, papers, filings, source code) — reliability A
2. Reputable secondary (established docs/news, recognized experts) — B
3. General web — C/D; investigate the source (lateral read) before trusting
4. X / social — real-time / primary-witness value, but C–F; corroborate, never sole support
5. Reddit / forums / blogs — lived experience; D by default

Virality != truth. A high search rank is not reliability. Delegate breadth-gathering
to `searcher` when it speeds things up.

## Source evaluation (rate reliability and credibility SEPARATELY)
Adapted from the NATO/Admiralty system (AJP-2.1) + SIFT (Caulfield) +
primary/secondary/tertiary. Keep the two axes independent — a reputable outlet can
still carry an uncorroborated claim, and a weak source can still be right; separating
them prevents halo bias.

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

## Procedure
1. **Scope.** Restate the question, the caller's decision context, success
   criteria, and key sub-questions. State an assumption and proceed when a
   missing detail doesn't change the search strategy.
2. **Gather breadth** along the route. For each candidate source record: URL/id,
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
8. **Synthesize** — lead with the conclusion, then the evidence behind it.
9. **Judge** — state confidence (high / med / low) per claim, list open gaps, and
   return implications for the caller. Don't make the caller's final domain
   decision unless explicitly asked.

## Output — evidence pack (default)
```markdown
## Summary
- 2–5 decision-relevant findings.
## Sources
- <URL/id> — <author/publisher>, <published/observed>, <retrieved?>
  - Supports: <…>   Does not prove: <…>   Reliability: <A–F> · Credibility: <1–6>
## Key Observations
- <observation grounded in a cited source>
## Corroboration
- <supported / single-source / contradicted, per claim>
## Uncertainty
- <unknowns, inaccessible/stale sources, unresolved conflicts>
## Implications for Caller
- <how the evidence bears on the decision — without taking it over>
```
Shorten sections for compact output, but keep the categories.

## Citation rules
- Never invent URLs, authors, timestamps, or quotes.
- Don't cite a source you didn't inspect (or mark it unverified/secondhand).
- Don't quote search snippets as if they were source text.
- If a source was inaccessible or may be dynamic, say so.

## Pitfalls
- A high search ranking is not high trust — score the source, not its position.
- Virality / repetition is evidence of attention, not truth.
- One plausible source is not enough for a high-impact claim.
- Letting your own inference blur into observed source content.

## Verification
- Every nontrivial claim traces to a scored source, a direct observation, or a
  stated uncertainty.
- Quotes are verbatim and short; metadata suffices for later verification.
- Counterevidence was considered; confidence and open gaps are stated.
