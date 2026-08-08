# Verify engine — the four-stage pre-ship inspection

Every public candidate passes four stages **in order**: mechanical →
style → factual → legal. The floor is non-waivable (kernel
<RedFloor>): no grant, deadline, or instruction skips a stage.
Drafts and internal documents are the only exception. Changed copy —
even one word after approval — re-enters inspection; **numeric
claims always take the double check** (factual AND legal).

## Stage 1 — mechanical

Machine-checkable form, on the RENDERED output, not the source:

- Platform limits: length, media formats/aspect, alt text, thread
  mechanics — verified against current specs (refetch when
  staleness could matter; memory of a platform spec is not a spec).
- Formatting: no exposed markup, no stray placeholders, links
  resolve, mentions/hashtags exist and come from the brief.
- Text hygiene: banned expressions from the brief/voice canon,
  foreign-script contamination, mandatory elements present.
- Sweeps run across the whole approved inventory when it changes,
  not only the newest draft.

## Stage 2 — style

- Compare against the positioning record's voice, as evidence-based
  comparison, not taste: register, vocabulary, rhythm.
- Emotional narration and plain factual matter (prices, dates,
  numbers, links, conditions) stay separated — facts are stated
  flat.
- Flag stock phrasing, uniform rhythm, and empty politeness; fix
  surgically — never rewrite an approved draft wholesale to
  "improve" it.

## Stage 3 — factual

- **Extract every claim** — performance numbers, testimonials,
  quotes, names, URLs, dates, product facts — and resolve each to a
  fact-ledger entry. No entry → remove the claim or return a
  spec-gap finding asking the assistant to register it (with
  source). Plausibility is not evidence.
- Time-sensitive figures: check the entry's date against use;
  expired facts are findings.
- Anonymize identifiable third parties unless consent is on the
  ledger.
- Record the trace: which claims checked, matched where, what was
  removed/queried — accepted AND rejected.

## Stage 4 — legal (triage, not judgment)

Output per candidate: **pass / needs-specialist / block** — a pass
is triage, never a guarantee of legality. Checks by domain:

- **景表法** — superiority claims ("No.1", "cheapest", "guaranteed",
  efficacy) require objective substantiation, with survey source,
  scope, and date stated. Reference/strikethrough prices must
  reflect real sales history (the recent-sales standard) — no
  fictitious regular prices, no perpetual discounts.
- **ステマ規制** — paid, affiliated, or supplied-product content is
  clearly marked as advertising/PR.
- **特商法** — sales paths show required seller disclosures; total
  cost, recurring commitments, duration, and cancellation method
  are clear BEFORE the final confirmation; nothing obscures
  cancellation.
- **特電法** — commercial mail only to opted-in recipients, sender
  identified, working unsubscribe honored immediately.
- **薬機法** — no cure/prevention/improvement claims for
  supplements or cosmetics; testimonials stay inside authorized
  efficacy bounds.
- **Categorical blocks** — unsupported investment returns,
  income-guarantee, token/crypto performance claims.

Anything in the needs-specialist band goes up as a finding with the
concrete doubt named; block means the candidate does not leave the
session in that form.

## Where the stages run

| Situation | Stages |
| --- | --- |
| Accepting a supplied part (`parts.md`) | 1 + 3 (+ 4 when the part carries claims) |
| Draft delivery (no ship) | 1–4, results itemized in the report |
| Pre-publish (P0 relay or in-cap P1) | 1–4, all, freshly on the exact candidate |
| Critique rubric (`ground.md`) | 1–4 as findings, severity-ranked, no fixing |

## Report discipline

Findings name the stage and the concrete evidence ("factual: the
40% figure has no ledger entry"), with severity: block / fix-first /
note. An unnamed check did not happen; "inspected: pass" without the
four stages itemized is itself a finding against the report.
