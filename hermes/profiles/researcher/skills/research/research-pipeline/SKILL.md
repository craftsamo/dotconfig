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

## Search route (breadth, in order) — [tune]
1. Primary / official (docs, specs, papers, filings, source code)
2. Google (general web)
3. X (real-time, expert takes)
4. Reddit (community experience)
5. Blogs / individual posts

Delegate breadth-gathering to `searcher` when it speeds things up.

## Source trust scores (weight every claim by these) — [tune]
| Source | Trust |
|---|---|
| Primary/official, peer-reviewed, source code | 5 |
| Reputable docs / established news | 4 |
| Google-surfaced general web | 3 |
| X (verified / expert) | 3 |
| Reddit / forums | 2 |
| Individual blogs / anonymous | 1–2 |

A claim resting only on trust ≤ 2 needs corroboration before you rely on it.
Classify sources as **primary** (originator), **secondary** (reputable
reporting/docs), or **noisy** (X, forums, reposts, SEO summaries).

## Procedure
1. **Scope.** Restate the question, the caller's decision context, success
   criteria, and key sub-questions. State an assumption and proceed when a
   missing detail doesn't change the search strategy.
2. **Gather breadth** along the route. For each candidate source record: URL/id,
   author/publisher, publication time, retrieval time (when recency matters),
   trust score, what it supports, and what it does *not* prove.
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
  - Supports: <…>   Does not prove: <…>   Trust: <1–5>
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
