---
name: primary-fact-pack
description: >-
  Use to collect first-party facts on a settled list of items (products,
  specs, prices, benchmarks, policies): each item's defining wording, numbers
  with units and conditions, availability and dates from its own source; or a
  voices pack of who-said-what quotes in the speakers' own words. A lookup
  technic run as one itemized batch.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: technic
    mode: lookup
    tags: [search, primary-source, facts, specs, pricing, quotes, voices]
---

<ReadBeforeWork>

This technic adds to `lookup-searcher` and never replaces it. Require the
full-body kernel (`skill_view(name="searcher-pipeline")`), the lookup entry
(`skill_view(name="lookup-searcher")`), the current stage reference
(`skill_view(name="searcher-pipeline", file_path="references/<stage>.md")`)
and this body in current context, not a past load or summary. If unchanged is
returned while the earlier body is unavailable, use read_file on
`${HERMES_SKILL_DIR}/SKILL.md` and the kernel's canonical
`${HERMES_SKILL_DIR}/../../searcher-pipeline/SKILL.md`; stop the affected action
if they stay unavailable. Selecting this technic is not the caller's release
and never widens the agreed scope or cap.

</ReadBeforeWork>

# Primary fact pack

A writer, an analyst or the Assistant needs facts it can cite without
re-checking: what each item officially is, in its maker's words, with the
numbers and the conditions they hold under, and when the source said so.

## Brief

Plan settles, or a settled brief carries:

- **Items** — the list, one line each. An item list that first has to be
  found ("every benchmark that …") is an earlier sweep unit; this pack starts
  once the list is settled.
- **Fields** — the default per item is: official name; what it is, quoted
  from its own source; how it works or how it is measured, quoted; key numbers
  with unit and condition (plan, region, model or version, date); availability
  or status; source URL; the source's own date or last update; read date. The
  consumer may add fields and say which defaults it does not need. These fields
  are what "answered" means for each item in the lookup: reading the primary
  page far enough to fill them is not the deep read the lookup entry rules out,
  and explaining beyond the quotes still is.
- **Source policy** — what counts as primary for these items (official docs,
  spec, paper, repository, filing, pricing or help page, release notes, the
  maker's own post), and whether a secondary source may stand in when no
  primary is reachable.
- **Freshness**, **language** of the deliverable, **consumer**, **durable
  path** for the table, and a finite **cap**.

**Voices variant.** When the items are people's statements rather than
things, the fields are: speaker; role as the speaker describes it; venue
(X, YouTube, note, Substack, blog, talk); date; the quote verbatim in its
original language with a language label; URL; timestamp for a video. The
brief sets any count floors (in total, per language, per venue).

## Route

Per item, in this order:

1. The maker's own domain: `web_search` with `site:` on it, then its docs,
   spec, paper or repository, then its release notes or changelog for the
   date the fact took effect.
2. The maker's own channels when the fact was announced there: its X account
   (`x_search` `from:`), YouTube channel, note or Substack — through the
   service's tool and reference.
3. A secondary source only to find the primary. When no primary is reachable,
   and the policy allows it, the secondary stands in marked `secondary` with
   the reason.

For the voices variant, read the statement where it was made (the post, the
video's transcript at its timestamp, the article) rather than a quote of it
elsewhere.

## Floors here

- The defining sentence is quoted, not paraphrased; a paraphrase is labelled
  as such.
- A number without its unit, condition or date is incomplete: record what is
  missing.
- A pricing or spec page that does not render its numbers (client-side
  rendering, a region wall) is a gap with its URL; try the help centre, API
  docs or pricing API docs before recording it.
- When the maker's marketing page and its docs disagree, both go side by side
  with their dates; neither is chosen.
- A quote is never assembled from two places or translated into the
  original-language field.

## Output additions

The deliverable is a table at the durable path, one row per item and one
column per field, and in the reply the items with their primary URL and any
gap. Add per item: `primary` or `secondary (<reason>)`, and the field names
left empty with why.

## Verification additions

- Every item has a primary source, an allowed secondary marked as such, or a
  gap with the attempts named; no item is dropped.
- Every number carries unit, condition and date, or names what is missing.
- Every quote is verbatim from the venue it was made in, with its URL and, for
  a video, its timestamp; voices floors are met or the shortfall is named.
