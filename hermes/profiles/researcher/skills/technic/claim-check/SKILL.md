---
name: claim-check
description: >-
  Use to check the factual claims of a script, article or post before it
  ships: a verdict per claim mapped to the client's scale, the strongest safe
  wording within a length bound, what not to say, number cautions and the
  sources actually opened, in a claim ledger. A verify technic; fact errors and
  era or context errors are told apart.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: technic
    mode: verify
    tags: [research, fact-check, script, claims, wording]
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

# Claim check

A narration script, an article or a post is about to ship, and its factual
lines must hold up. The verify entry owns the method (exact originals, origins,
corroboration, counterevidence, the four verdicts); this technic adds what the
writer and the reviewer need to act on each claim.

## Brief

Plan settles, or a settled brief carries:

- **Claims** — the lines to check, verbatim, numbered, with the surrounding
  sentence when the claim leans on it. A full text with "check the facts" is
  turned into this list in Plan and agreed.
- **Use** — script, article or post; the audience; and how strongly the text
  may assert (a children's narration and an analyst note differ).
- **Scale** — the client's verdict labels, if any (for example established /
  mainstream with dissent / disputed / wrong). Each is mapped to the verify
  verdicts in Plan; with no client scale, the verify verdicts are used as they
  are.
- **Source ladder** — the source classes that count first (government and
  agency pages, national institutes and museums, signed reference works,
  primary papers), and those that never stand alone.
- **Wording bound** — the length limit for a safe rewording (characters or
  words), and whether a claim may be swapped for a supplied backup.
- **Ledger** — the durable path and filename, default `claim-ledger.md`, and a
  time cap; partial results with their status beat a timed-out reply.

## Route

Per claim, as the verify entry orders it: origin first, then the ladder's
sources, then counterevidence. Read the source itself; a source recalled rather
than opened this run is labelled `recalled` and never carries a verdict alone.
Check the claim's own words and what the sentence around it implies (order,
"first", "only", "never", an era label, a superlative): a claim can be true
while its framing is wrong.

## Per-claim record

- The original, verbatim; the verify verdict and confidence; the client's label
  it maps to.
- The kind of problem, if any: a **fact error** (the claim is wrong), a
  **framing error** (true fact, wrong era, order, scope or emphasis), an
  **overclaim** (true in part, stated too strongly) or a **number caution**
  (a figure that varies by source, date or definition).
- The strongest safe wording that the sources support, within the bound, and
  the phrasing not to use.
- Keep, reword or swap, as a suggestion tied to the verdict; choosing and
  rewriting the line stays with the writer and the client.
- Sources opened, with reliability and credibility; counterevidence or "none
  found" with where it was sought.

## Floors here

- A safe wording never asserts more than the cited sources do, and never
  adds a new claim. It is a statement of what the evidence supports, not
  production prose: it stays inside the bound and leaves voice and rhythm to
  the writer.
- A popular etymology, anecdote or "fun fact" is checked against its origin,
  not its repetitions.
- Numbers keep their unit, date and definition; a rounded figure says so.
- Nothing outside the claims list is judged: tone, pacing, length and fit to
  the brief are the client's.

## Output additions

The full verify ledger at the agreed path, each claim extended with the
per-claim record above; the reply lists the claims marked reword or swap first,
then the rest, and names the ledger file.

## Verification additions

- Every listed claim has a verdict, its mapped client label, the problem kind
  (or none), a safe wording within the bound and sources opened this run.
- No safe wording asserts beyond its sources; no verdict rests on a `recalled`
  source alone.
- Framing errors are kept apart from fact errors.
- The ledger file exists at the agreed path and holds every claim.
