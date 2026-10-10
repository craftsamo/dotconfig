---
name: evidence-screen
description: >-
  Use to screen a list of items (businesses, listings, candidates) against the
  client's rubric from evidence the client already saved: one status per item
  from the client's closed list, backed by attributed observations and
  per-criterion evidence, in one file. A verify technic; the client keeps the
  go/no-go.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: technic
    mode: verify
    tags: [research, screening, rubric, evidence, classification]
---

<ReadBeforeWork>

This technic adds to `verify-researcher` and never replaces it. Require the
full-body kernel (`skill_view(name="researcher-pipeline")`), the verify entry
(`skill_view(name="verify-researcher")`), the current stage reference
(`skill_view(name="researcher-pipeline", file_path="references/<stage>.md")`)
and this body in current context, not a past load or summary. If unchanged is
returned while the earlier body is unavailable, use read_file on
`${HERMES_SKILL_DIR}/SKILL.md` and the kernel's canonical
`${HERMES_SKILL_DIR}/../../researcher-pipeline/SKILL.md`; stop the affected
action if they stay unavailable. Selecting this technic is not the
caller's release and never widens the agreed scope or budget.

</ReadBeforeWork>

# Evidence screen

The client has already captured the evidence (page text, saved JSON, screenshots
of listings, photos, sites) and needs each item placed in one of its own statuses
with the evidence that puts it there.

## How verify applies here

Every verify obligation holds; this is what each one means for a screen:

- **Fixed claim list** — items × rubric criteria, agreed in Plan by agreeing
  the item list and the rubric. A claim reads "`<item id>` meets `<criterion>`".
- **Original** — the criterion's text verbatim from the rubric, with the item id;
  the restatement says what evidence would show it.
- **Source requirement** — the supplied evidence only, agreed in Plan; each file
  is a source, cited by its path, with reliability and credibility.
- **Strength** — the item's own statement, or a single capture, makes a
  criterion `partly true` or low confidence at most, never `supported` alone;
  `supported` needs two independent captures that agree (the item's own site and
  an independent listing, say) or a record that settles it directly.
- **Counterevidence** — sought in all of the item's files; "none found in the
  supplied files" when there is none.
- **Status** — derived from the criterion verdicts by the rubric's own rule,
  mechanically. It is not a verdict on fit, quality or what the client should
  do next.

## Brief

Plan settles, or a settled brief carries:

- **Items** — the ordered list of item ids (and names) to screen, and the
  count; the whole list belongs in one resident work conversation, not one
  call per few items.
- **Evidence** — the directory of saved evidence, read only, and how files map
  to items (one folder per id, a file per capture kind).
- **Rubric** — the document that defines the criteria, and how the criteria
  decide a status.
- **Statuses** — the client's closed list of statuses, each with its meaning.
  Every item gets exactly one of them.
- **Output** — the file path and its schema (or the previous delivery to match),
  and the ledger path (default `claim-ledger.md` beside it).
- **Allowed actions** — normally none beyond reading the supplied files: no web,
  no database or sheet, no sends. A brief that allows web reads says which.

A status that does not fit any item is not invented: an item that the
evidence cannot place takes the client's "not completed" (or nearest named)
status with the reason, and a missing status the list needs is a spec gap
returned in Plan or the report.

## Route

Per item, in order:

1. Read the text captures first (page text, saved JSON, notes), then only the
   images the text cannot settle. One image at a time; write what it shows to
   the output before the next.
2. For each criterion, quote the evidence that bears on it, with the file and
   who says it: the business itself, its own site, a sign, an ad, a
   third-party listing, a review.
3. Record identity conflicts (a similar name, another address, a second
   listing) side by side; never merge or drop one.
4. Take the status the rubric gives; write the item to the output file before
   moving on, so a turn that ends early leaves every finished item on disk.

## Floors here

- A review, photo, sign or ad is evidence of what it shows, not of current
  capability, material, installer, stock, hours or quality.
- A date on a page is not proof of an update or of current operation.
- A login wall or blocked page is "viewing blocked" (or the client's
  equivalent), recorded once; "no link listed" is not "no site", and "no photo
  shown" is not "no photos exist".
- An image you did not see yourself is the capturing agent's observation and
  labelled so.
- Owner intent, authority and permission to contact stay unconfirmed unless the
  evidence states them.
- Contact values (phone, email, personal names) never enter the output unless
  the brief asks for them.
- Whether an item should go to a writer, a campaign or a call is the client's
  decision. Report the rubric evidence only; no field recommends a next step,
  even when the brief's schema has one (leave it to the client and say so).

## Output additions

Per item, in the brief's schema or else:

```json
{"id": "...", "status": "<one of the client's list>", "reason": "...",
 "observed": [{"file": "...", "quote": "...", "by": "self|site|sign|ad|listing|review|capturer"}],
 "criteria": {"<criterion>": {"verdict": "supported|refuted|partly true|unverifiable",
   "confidence": "high|med|low", "evidence": [{"file": "...", "reliability": "A-F", "credibility": "1-6"}],
   "counterevidence": "... | none found in the supplied files"}},
 "identity_conflicts": ["..."], "unverified": ["..."]}
```

Beside it, the verify ledger at the agreed path holds the same criterion
verdicts in the verify entry's Output template, so the client's fact-check QA
reads them as it reads any ledger. The reply names both files, the count per
status, and the items left not completed with why.

## Verification additions

- The output parses; it holds exactly the listed items, in the listed order.
- Every status is one of the client's list; no new status appeared.
- Every quote is found in the file it names, and every named file exists.
- Every criterion verdict rests on quoted evidence or is `unverifiable` with
  what was missing; none is `supported` on the item's own word or one capture.
- The ledger exists at the agreed path and matches the item file.
- No contact value or merged identity is in the output; the floors above hold
  for every item.
