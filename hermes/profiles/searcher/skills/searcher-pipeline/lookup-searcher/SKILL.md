---
name: lookup-searcher
description: >-
  Lookup: targeted answers and links; retrieval only. Use for a specific fact,
  document, version, date or itemized question batch. Not an enumeration,
  exhaustive source hunt, truth verdict, recommendation or production task.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: searcher-pipeline
    tags: [search, lookup]
---

<ReadBeforeWork>

Re-evaluate the entry every caller, judge, resume or completion turn and before
an action whose unit or scope changes. Reuse full-body instructions only while
present in the current context, not a past load or summary. Direct entry requires
the full kernel before searching, including its runtime and card gate:

```text
skill_view(name="searcher-pipeline")
```

If a tool returns unchanged while the earlier body is unavailable, use read_file
on `${HERMES_SKILL_DIR}/../SKILL.md` for the kernel and
`${HERMES_SKILL_DIR}/SKILL.md` for this entry. Follow next_offset until the whole
required document is available; do not invent alternate paths or artificial
ranges to evade dedup. If the body remains missing, stop the affected search and
report the missing instructions; on a card follow the kernel's blocking protocol,
never claim completion. In raw file text, HERMES_SKILL_DIR is this entry's directory.

Loading does not restart coverage or the frontier, reset a budget, or release
another unit. Preserve the initial purpose and settled constraints. A change
outside the released unit requires the caller's release, not self-decomposition.
This entry owns the unit procedure and checks below; do not also load every entry.

</ReadBeforeWork>

# Lookup unit — targeted facts, fast

Loaded when the released unit wants **specific answers**: a fact, a doc/link,
"latest on X", who-said-what, a version, a date. This is the **default unit**
when no other fits; a batch releases as one unit with an itemized question
list — answer item by item, none silently dropped. Deliverable = claims +
source URLs. Done when the question is answered with sources — not when the
web is exhausted.

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

## Handoff

Verify each URL was retrieved in this run, then deliver the findings —
sources, coverage, open gaps — in the final reply/message.

## Pitfalls

- Search ranking ≠ relevance ≠ trust.
- Don't synthesize, conclude, or implement — that's the next profile's job.
- Don't over-collect: this mode stops at "answered", not at "covered"
  (coverage is sweep's job).

## Verification

- Every hit has a URL and an identified source.
- Duplicates removed; low-confidence / stale / conflicting flagged.
- The brief's question is either answered with sources or explicitly reported
  as unanswerable (with what was tried).
