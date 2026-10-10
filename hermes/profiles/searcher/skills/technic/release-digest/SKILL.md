---
name: release-digest
description: >-
  Use to watch named vendors or products for changes inside a date window:
  release notes, changelogs, help-centre updates, official posts and
  announcements, minus the items the caller has already covered, each with its
  primary URL, dates and who can use it. A sweep technic; dated order is not a
  ranking.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: technic
    mode: sweep
    tags: [search, release-notes, changelog, digest, news, monitoring]
---

<ReadBeforeWork>

This technic adds to `sweep-searcher` and never replaces it. Require the
full-body kernel (`skill_view(name="searcher-pipeline")`), the sweep entry
(`skill_view(name="sweep-searcher")`), the current stage reference
(`skill_view(name="searcher-pipeline", file_path="references/<stage>.md")`)
and this body in current context, not a past load or summary. If unchanged is
returned while the earlier body is unavailable, use read_file on
`${HERMES_SKILL_DIR}/SKILL.md` and the kernel's canonical
`${HERMES_SKILL_DIR}/../../searcher-pipeline/SKILL.md`; stop the affected action
if they stay unavailable. Selecting this technic is not the caller's release
and never widens the agreed scope or cap.

</ReadBeforeWork>

# Release digest

A recurring digest needs the same thing every time: what changed at the
watched vendors inside the window, from their own pages, that the audience can
actually use and that has not been covered before. The coverage matrix is
vendor × source class; the window and the exclusion list fix the population.

## Brief

Plan settles, or a settled brief carries:

- **Watched** — the vendors or products, by name, and their official
  domains when known.
- **Window** — absolute from and to dates. A relative window ("this week") is
  turned into dates from the current date and stated in the first line.
- **Audience and inclusion rule** — who the digest is for and what makes an
  item eligible (for example: usable by an individual on a public plan;
  enterprise-only, waitlist-only or rumoured items excluded).
- **Exclusion list** — the path of the caller's file of already-covered
  items. Searcher reads it and never writes it: the caller adds items after it
  accepts them, so the report lists the delivered candidates ready to append.
- **Count** — a floor and a cap of candidates, **per-item fields** beyond the
  defaults below, the **durable path** and a finite **cap**.

## Route

Per watched vendor, every source class, inside the window:

1. Release notes, changelogs and the help centre's "what's new" pages.
2. The official blog or newsroom.
3. The vendor's official X account (`x_search` with `from:` and `since:`) and
   its official YouTube channel's uploads in the window (`youtube`
   `playlist`), through the service references.
4. News or community posts only to find an item the official pages missed;
   the candidate then rests on the vendor's own page, or is marked
   `no first-party page found`.

Compare each candidate against the exclusion list by what it is (product and
feature), not by wording. A later update to a covered item is a new candidate
only when the inclusion rule says so.

## Per-item fields

Title as the primary page gives it; vendor; announced date; availability date
or rollout state; who can use it (plan, region, platform); primary URL; the
page's heading or first sentence verbatim; one line of what changed in the
source's own terms; the official post that echoes it, if any; flags (beta,
staged rollout, stale, no first-party page).

## Floors here

- Announced and available are separate dates; a staged rollout says so.
- Candidates are listed newest first by announced date. That order is not a
  ranking: no "best", "biggest" or recommendation.
- Over the cap, the newest within the cap are listed and the rest are named
  in the coverage statement.
- Zero candidates is a result only after every watched vendor's official
  sources were read for the whole window; the coverage says, per vendor, what
  was read.

## Output additions

Add to the sweep's coverage statement: the window as dates; per vendor the
source classes read and found empty; the exclusion-list matches that removed
candidates (count and names); items found eligible but over the cap. Close
with the delivered candidates as lines ready for the caller to append to its
exclusion list after acceptance.

## Verification additions

- Every candidate rests on a first-party URL read this run, or is flagged
  `no first-party page found`.
- No candidate matches an exclusion-list item by identity.
- Every candidate meets the inclusion rule as its source states it; announced
  and available dates are separate.
- Each vendor × source class cell is read or named as unsearched ground.
