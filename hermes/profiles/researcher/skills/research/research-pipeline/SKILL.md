---
name: research-pipeline
description: Researcher's standard gather -> cross-reference -> synthesize -> judge pipeline, with a search route and source trust scores.
version: 0.1.0
author: Hermes Agent
metadata:
  hermes:
    tags: [research, methodology, sources, synthesis]
---
# Research pipeline (researcher)

The standard method for research tasks. Tune the route and trust scores to taste.

## When to Use
- Any analysis / synthesis / research task assigned to the researcher.

## Search route (breadth, in order) — [tune]
1. Primary / official sources (docs, specs, papers, source code)
2. Google (general web)
3. X (real-time, expert takes)
4. Reddit (community experience)
5. Blogs / individual posts

Delegate breadth gathering to `searcher` when it speeds things up.

## Source trust scores (weight claims by these) — [tune]
| Source | Trust |
|---|---|
| Primary/official, peer-reviewed, source code | 5 |
| Reputable docs / established news | 4 |
| Google-surfaced general web | 3 |
| X (verified / expert) | 3 |
| Reddit / forums | 2 |
| Individual blogs / anonymous | 1–2 |

A claim resting only on trust ≤ 2 needs corroboration before you rely on it.

## Procedure
1. Scope: restate the question, success criteria, and key sub-questions.
2. Gather breadth along the search route; record each candidate source with its trust score.
3. Deep-read the highest-trust sources; extract concrete claims + evidence.
4. Cross-reference / triangulate: do independent sources agree? Weight by trust.
5. Synthesize: structured findings — lead with the conclusion, then the evidence.
6. Judge: state confidence (high / med / low) per claim and list open gaps.

## Pitfalls
- A high search ranking is not high trust — score the source, not its position.
- Separate evidence from speculation explicitly; cite every nontrivial claim.

## Verification
- Each conclusion is traceable to scored sources; uncertainty and gaps are stated.
