# Lookup mode — targeted facts, fast

Loaded when the card wants **specific answers**: a fact, a doc/link, "latest
on X", who-said-what, a version, a date. This is the **default mode** when no
other fits. Deliverable = claims + source URLs. Done when the question is
answered with sources — not when the web is exhausted.

## Steps

1. **Frame the query.** Restate it; pull out entities and keywords; generate a
   few variants (synonyms, narrower/broader, site- or time-scoped).
2. **Route by source class:**
   - Official / primary (docs, specs, repos, filings) first.
   - General web via `web_search`.
   - `x_search` for real-time events, expert takes, and sentiment.
   - Forums / community for lived experience.
3. **Capture each hit shallowly** — title, URL, source/author, date (when
   time-sensitive), and a one-line gist. Do **not** deep-read or summarize at
   length.
4. **Deduplicate** by URL / domain / claim; drop SEO mirrors and reposts.
5. **Flag** low-confidence, stale, or conflicting hits.
6. **Stop when answered.** The question has a sourced answer (corroborated by
   a second independent source when it matters); conflicting answers are
   reported side by side, not adjudicated.
7. **Hand off** a concise, link-first list, plus a short note of what still
   needs verification or synthesis by researcher.

## X search guidance

- Use for breaking events, primary accounts, and expert commentary.
- Virality / engagement is attention, not truth — mark it as such, never as
  corroboration.

## Output template

```text
- <title / claim> — <URL> (<source>, <date?>) [flag: stale | low-confidence | conflicting?]
…
Open for researcher: <what needs verification / deeper reading>
```

Keep it link-first. No essays.

## Pitfalls

- Search ranking ≠ relevance ≠ trust.
- Don't synthesize, conclude, or implement — that's the next profile's job.
- Don't over-collect: this mode stops at "answered", not at "covered"
  (coverage is sweep's job).

## Verification

- Every hit has a URL and an identified source.
- Duplicates removed; low-confidence / stale / conflicting flagged.
- The card's question is either answered with sources or explicitly reported
  as unanswerable (with what was tried).
