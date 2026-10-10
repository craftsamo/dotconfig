---
name: lookup-searcher
description: >-
  Lookup specific facts, documents, links, latest events or who-said-what:
  agree the question, retrieve sourced answers item by item, check them and
  hand off link-first. Not enumeration, source trails or synthesis.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: searcher-pipeline
    tags: [search, lookup]
---

<ReadBeforeWork>

On every caller, resume or completion turn and before a midturn mode, stage or
scope change, require full-body kernel, this mode entry and the current stage
reference in current context, not a past load or summary. Direct entry requires
`skill_view(name="searcher-pipeline")` before any stage. Load
`skill_view(name="lookup-searcher")` and the current stage with
`skill_view(name="searcher-pipeline", file_path="references/<stage>.md")`:
[Plan](../references/plan.md) or [Build](../references/build.md). Retrieval on a service also requires its
shared reference: [X](../references/platforms/x.md),
[YouTube](../references/platforms/youtube.md), [note](../references/platforms/note.md),
[Substack](../references/platforms/substack.md), [EVM](../references/platforms/evm.md) or
[Solana](../references/platforms/solana.md).
If unchanged is returned while the earlier body is unavailable, or a body is
missing, use read_file on canonical
`${HERMES_SKILL_DIR}/../SKILL.md`, `${HERMES_SKILL_DIR}/SKILL.md` and
`${HERMES_SKILL_DIR}/../references/<stage>.md`. Follow next_offset through
actual truncation; stop the affected action if unavailable. Never evade dedup
with alternate paths or artificial ranges. Raw skill_dir is this entry's
directory. Loading does not restart coverage or the frontier, reset a budget or
replay work. Expansion needs the caller's release; selection is not a new grant.

</ReadBeforeWork>

# Lookup

Use when the unit wants **specific answers**: a fact, a doc/link,
"latest on X", who-said-what, a version, a date. This is the **default mode**
when no other fits; a batch releases as one unit with an itemized question
list — answer item by item, none silently dropped. Deliverable = claims +
source URLs. Done when the question is answered with sources — not when the
web is exhausted.

## Plan

Choose lookup for specific facts, documents/links, latest events, who-said-what,
versions or dates; it is the default when neither enumeration nor a source trail
is needed. Propose one question or an itemized batch with no silently dropped
items. Set entities, time window/freshness, source classes, exclusions, finite
query cap and link-first output. Done means each question has a sourced answer
or named miss with attempts, not exhausting the web. Where stakes warrant,
include independent corroboration, leaving conflicting answers unadjudicated.

## Build

### Steps

1. **Frame the query.** Restate it; pull out entities and keywords; generate a
   few variants (synonyms, narrower/broader, site- or time-scoped).
2. **Route by source class:**
   - Official / primary (docs, specs, repos, filings) first.
   - General web via `web_search`.
   - `x_search` for real-time events, expert takes, and sentiment.
   - What someone published on a service — a video or channel, a note
     article, a Substack post, a post or profile on X — through that service's
     tool and reference, not a web snippet of it.
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

### X search guidance

- Use for breaking events, primary accounts, and expert commentary.
- Virality / engagement is attention, not truth — mark it as such, never as
  corroboration.

### Pitfalls

- Search ranking ≠ relevance ≠ trust.
- Don't synthesize, conclude, or implement — that's the next profile's job.
- Don't over-collect: this mode stops at "answered", not at "covered"
  (coverage is sweep's job).

## Output template

```text
- <title / claim> — <URL> (<source>, <date?>) [flag: stale | low-confidence | conflicting?]
…
Open for researcher: <what needs verification / deeper reading>
```

Keep it link-first. No essays.

## Verification

- Every hit has a URL retrieved this run and an identified source; time-sensitive
  claims have source dates. Dedup by URL/domain/claim is complete.
- Low-confidence, stale and conflicting hits are flagged. X engagement is
  attention, not truth or corroboration; search ranking is not relevance/trust.
- Each agreed question or batch item is answered with sources or explicitly
  unanswerable with attempts named. Required corroboration is present or a gap.
- Link-first findings include coverage and open gaps, with deeper reading or
  verification under Open for researcher, not synthesized conclusions.

## Handoff

Plan ends at the client's agreement. Build ends, in the same turn, with the
check against this entry's Verification, and the reply carries it. Each
stage's own Handoff in its shared reference says what follows. Keep this mode for the unit; another kind of retrieval is another
agreed unit with its own mode entry, never a silent switch.
