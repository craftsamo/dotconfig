---
name: breadth-retrieval
description: Searcher's breadth-first retrieval — query expansion, source-class routing across web + x_search, dedup, and concise link-first findings handed off to researcher/coder.
version: 1.0.0
author: Hermes Agent
metadata:
  hermes:
    tags: [search, retrieval, web, x_search, sources, triage]
    category: research
---
# Breadth-first retrieval (searcher)

Searcher gathers candidate sources fast and wide, then hands off. The job is
coverage and link-first findings — not analysis or conclusions.

## When to Use
- Any searcher retrieval task: "find sources / what's out there / latest on X".
- Not for synthesis, deep analysis, or implementation — hand those to
  researcher / coder.

## Procedure
1. **Frame the query.** Restate it; pull out entities and keywords; generate a
   few variants (synonyms, narrower/broader, site- or time-scoped).
2. **Route by source class:**
   - Official / primary (docs, specs, repos, filings) first.
   - General web via `web_search`.
   - `x_search` for real-time events, expert takes, and sentiment.
   - Forums / community for lived experience.
3. **Capture each hit shallowly** — title, URL, source/author, date (when
   time-sensitive), and a one-line gist. Do **not** deep-read or summarize at length.
4. **Deduplicate** by URL / domain / claim; drop SEO mirrors and reposts.
5. **Flag** low-confidence, stale, or conflicting hits.
6. **Hand off** a concise, link-first list, plus a short note of what still needs
   verification or synthesis by researcher.

## x_search guidance
- Use for breaking events, primary accounts, and expert commentary.
- Virality / engagement is attention, not truth — mark it as such, never as corroboration.

## Output (default)
```text
- <title / claim> — <URL> (<source>, <date?>) [flag: stale | low-confidence | conflicting?]
…
Open for researcher: <what needs verification / deeper reading>
```
Keep it link-first. No essays.

## Pitfalls
- Search ranking ≠ relevance ≠ trust.
- Don't synthesize, conclude, or implement — that's the next profile's job.
- Don't over-collect: stop when coverage is good, not exhaustive.
- No write-actions on social platforms (post / reply / like / follow / DM).

## Verification
- Every hit has a URL and an identified source.
- Duplicates removed; low-confidence / stale / conflicting flagged.
- Output is breadth (many sources, shallow) with a clear hand-off note.
