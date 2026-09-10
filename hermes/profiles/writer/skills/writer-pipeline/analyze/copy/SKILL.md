---
name: analyze-copy
description: >-
  Describe, review or compare existing landing-page copy, promotional email
  or an announcement using the actual text and supplied evidence. Explain
  persuasion without inventing effectiveness, legal clearance or reader
  reactions. Return analysis, not rewritten copy, strategy or publication.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: writing
    output: "Copy analysis with anchored observations, interpretations and unknowns; original unchanged and no conversion or legal certification"
    form:
      source: {required: true, type: text, label: "Existing copy text, local path or readable URL"}
      question: {required: true, label: "What the requester wants explained or checked"}
      mode: {required: false, options: [describe, review, compare], label: "Infer from the question; description need not identify defects"}
      focus: {required: false, type: text, label: "One or more aspects: message, proof, offer, disclosures, action, tone or structure"}
      destination:
        required: false
        options: [landing-page, email, announcement]
        other: true
        references: references/*.md
        label: "Infer from the target; needed only for destination-specific assessment"
      criteria: {required: false, label: "Known audience, purpose, approved message and constraints when evaluating fit"}
      offer: {required: false, type: text, label: "Known commercial conditions to compare with the copy's assertions"}
      compare_with: {required: false, type: text, label: "Comparison text/path/URL; required for compare"}
      sources: {required: false, type: text, label: "Supplied evidence for claim/offer checks; not a grant for new research or experiments"}
      language: {required: false, label: "Report language; default to the requester's language"}
      length: {required: false, label: "Requested analysis depth or report length"}
      humanizer: {required: false, options: ["yes", "no"], label: "Default no; explicit analysis guidance only, never permission to rewrite"}
      note: {required: false, type: text, label: "Other analysis constraints"}
---

<Procedure>

1. Read the actual target and question. Identify the available brief/evidence;
   a missing original goes back to the requester. Pre-draft advice is a
   consultation, not analysis of imaginary copy. Do not require a full writing
   brief for a bounded question about wording or structure.
2. Choose describe/review/compare from the question. Read both inputs for a
   comparison and use comparable criteria. If destination rules matter, read
   only [landing page](references/landing-page.md), [email](references/email.md)
   or [announcement](references/announcement.md). Custom destinations use the
   supplied constraints; do not assume platform capabilities or benchmarks.
3. Anchor observations to the words and structure of the copy. Explain how
   claims, proof, conditions and actions relate. Distinguish the text's explicit
   assertion, your interpretation and an unknown effect. Description need not
   find defects or select a winning variant. No universal persuasion template.
4. For claim/offer review, compare with supplied evidence and qualifications.
   A source may be limited, contradictory or unavailable; that does not
   establish independent truth or falsity. Flag the gap without inventing a
   testimonial, experiment, legal opinion or stronger alternative claim.
5. Separate textual clarity from actual conversions, reader response, delivered
   email, rendered layout and legal compliance. These need their own evidence;
   do not browse a live flow, submit forms or run a campaign to settle them.
   No statistical quality/authorship scores or guessed performance lift.
6. Use `japanese-writing` for Japanese expression observations, without legacy
   layers or inspection scripts. `humanizer` is explicit-only and provides
   observations, never permission to rewrite the source. Quote sensitive
   evidence only as necessary; do not expose raw customer records in reports.
7. Apply QA to the report. Return a permitted short analysis in the reply or
   save it at the requested durable path. Do not produce replacement copy,
   revise offer/strategy decisions or publish. The original remains unchanged.

</Procedure>

<QA>

- Substantive findings quote the target and answer the question within the read
  scope. Observations, interpretations and unknowns remain distinguishable.
- Comparisons use both inputs; descriptive analysis need not invent faults or
  winners. Review criteria come from the actual request, not personal taste.
- Claim and offer observations distinguish what the copy says from what the
  available evidence supports. No unsupported conversion or legal verdict.
- Check this report, not an imaginary sales page: it needs no new headline,
  offer, testimonial, CTA or publishable body. Analysis does not authorize
  rewriting, sending or changing a campaign.
- Report checked / unmet / unverified evidence. Missing required evidence
  limits the conclusion; it is not a pass or a reason to fabricate a measurement.

</QA>

<Report>

Name `analyze-copy`, target, read scope, mode and relevant destination. Provide
anchored observations and requested recommendations with evidence and limits.
Do not deliver a rewritten source or certify actual campaign performance,
legal approval, successful delivery or publication.

</Report>
