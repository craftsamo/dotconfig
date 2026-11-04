# A parent and its units, worked

A made-up job in an English repository: an app gains export and import. In
another language the section names are that repository's own words for the
same meanings ("Issue bodies").

## The parent

Title: `Let people move their notes in and out of the app`

```markdown
## Overview

People can export their notes and import them elsewhere, so leaving or
switching devices loses nothing.

## Details

- One file format for both directions; the app's own fields survive a round
  trip.
- Attachments travel with the notes; large ones are linked rather than
  embedded (decided on #12).

## Plan

- #11 Settle the file format and the shared reader and writer
- #12 Export from the settings page
- #13 Import, with a preview before anything is written
- #17 Keep tags on notes written before tags existed

## Acceptance

- [ ] A note exported and imported again is unchanged, attachments included
- [ ] The help page describes both directions
```

#17 was found while #12 was built; the goal needs it, so it is a sibling under
the parent, and the Plan gained its line. The numbers between (#14, #15) are
pull requests.

## A unit at Fixed, when it lands

Title: `Export from the settings page` (blocked by #11)

```markdown
## Purpose

People download all their notes as one file from the settings page.

## Requirements

- The export holds every note, its tags and its attachments.
- Attachments over the size limit are linked rather than embedded.
- A failed export leaves nothing half-written on the device.

## Research

- The reader and writer from #11 stream, so memory stays flat for large
  accounts (the measurement of 2026-03-02 is a comment).

## Implementation outline

- [x] The export job and its file writer — #14
- [x] The settings page button and progress — #15

## Acceptance

- [x] An account with 10,000 notes exports in one file
- [x] An interrupted export leaves no partial file
- [x] The help page describes the export — moved to #13

## Evidence

The decisions and the measurement are the comments on this issue.
```

At Draft the same issue had a prose outline and an `## Open decisions`
section (the size limit); kickoff settled it with the user, folded it into the
requirements and removed the section.

## Comments on the unit

```markdown
**Measurement: export memory on a large account** (2026-03-02).

| Notes  | Peak memory | Time |
| ------ | ----------- | ---- |
| 1,000  | 48 MB       | 2 s  |
| 10,000 | 51 MB       | 19 s |

Run on the staging build with the streaming writer from #11.
```

```markdown
**Decision: attachments over 25 MB are linked, not embedded.**

- Embedding them made the largest test exports too big to send by mail.
- A link keeps the export one file; the import follows it.
```

```markdown
**Defaults taken (not asked).**

- The file is named after the account and the date, so repeated exports do
  not overwrite each other.
```

```markdown
Landed in #15 (with #14): the settings page exports every note in one file.

The help page section moves to #13, which describes both directions at once;
its acceptance gained the line.
```
