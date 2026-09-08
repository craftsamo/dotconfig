---
name: write-copy
description: >-
  Draft landing-page copy, promotional email or an announcement from an
  approved message, audience and supported offer. Keep claims and commercial
  conditions faithful to the brief. Not strategy, social posts, ordinary
  correspondence, factual release notes, page implementation or publication.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: writing
    output: "Complete copy draft at the requested path with applicable evidence and open conditions; never published or sent"
    form:
      audience: {required: true, label: "Who the copy addresses, including relevant eligibility or exclusions"}
      message: {required: true, label: "Approved message or benefit to convey; not permission to invent positioning or proof"}
      destination:
        required: true
        options: [landing-page, email, announcement]
        other: true
        references: references/*.md
        label: "Infer the stated destination; a described custom destination is equally valid"
      offer: {required: false, type: text, label: "Actual price, eligibility, availability, dates and other commercial conditions, when applicable"}
      action: {required: false, label: "Requested reader action and actual target; needed only when the released purpose calls for action"}
      sources: {required: false, type: text, label: "Supplied facts, ledger entries, paths/URLs or excerpts supporting claims and offer conditions"}
      language: {required: false, label: "Explicit output preference wins; otherwise default Japanese"}
      tone: {required: false, label: "Voice in ordinary words, not model temperature or a change to the approved claim"}
      style_reference: {required: false, type: text, label: "Expression or structure example; not evidence of this client's results or endorsements"}
      reference_focus: {required: false, label: "Which aspects of the example to borrow"}
      must_keep: {required: false, label: "Protected wording, qualifiers, disclosures, identifiers or approved commercial conditions"}
      avoid: {required: false, label: "Excluded content; clarify conflicts with protected meaning or necessary disclosures"}
      length: {required: false, label: "Target or hard bound with units; do not infer a universal destination limit"}
      humanizer: {required: false, options: ["yes", "no"], label: "Default no; explicit request only"}
      note: {required: false, type: text, label: "Other requirements, including custom destination constraints"}
---

<Procedure>

1. Read the released brief and supplied sources. Infer answered fields before
   asking Q<n>. The requester decides audience, message, offer and scope; you
   choose expression within those decisions, not a new strategy or campaign.
   If an essential claim or condition is unsupported or conflicts with evidence,
   return the gap. Do not invent proof or silently weaken a mandatory promise.
2. Read only the selected destination: [landing page](references/landing-page.md),
   [email](references/email.md) or [announcement](references/announcement.md).
   Custom destinations use the actual supplied constraints, not guessed features.
   Social posts, ordinary correspondence and factual release notes keep their
   separate families. Select by purpose, not length or the email medium.
3. Map factual claims to their supporting material and retain its qualifications.
   A case study from one trial is not a universal guarantee. Do not borrow a
   style example's experience, testimonial, customer count or results. Omit an
   optional proof slot when no evidence exists; do not omit a mandatory condition
   just to make the draft persuasive. Resolve contradictory required claims first.
4. Build only the released unit. An outline stops at structure and requested
   samples; a piece follows its approved outline; a small whole job needs no
   forced outline or alternatives round. A mail sequence or campaign beyond
   the unit goes back for decomposition. Use an action only when requested or
   entailed by the agreed purpose; do not force a CTA into every announcement.
5. Draft the message and supported benefit with relevant offer conditions near
   the claim they qualify. Do not invent urgency, scarcity, discounts, guarantees
   or endorsements. Preserve qualifications even when they reduce intensity.
   A required action must have a real destination, not a fabricated URL/control.
6. Use `japanese-writing` as Japanese expression/notation knowledge only, not
   retained legacy layers or inspection scripts. `humanizer` is explicit-only
   and cannot change commercial terms, evidence or protected content. Requested
   warmth, brevity or confidence does not authorize a stronger factual claim.
7. Apply QA and save the complete draft at the requested durable path. Clearly
   separate publishable headings/body/action text from field labels, source
   notes and review instructions. Do not rely on hidden HTML comments. Missing
   assets, links or editor work remain explicit dependencies, not fake completed
   media. Do not build a page, send mail, test a purchase flow or publish.

</Procedure>

<QA>

- Compare the draft with the actual message, audience, scope and destination.
  The claim is supported within its original qualifications; offer amounts,
  dates, eligibility and disclosures are preserved and not contradicted by a
  headline. Evidence-backed description is not independent fact verification.
- Protected text survives. No invented proof, testimonial, scarcity or urgency;
  source conflicts are resolved or remain a blocker, not an eloquent compromise.
- An action is required only when the purpose needs one. Its wording and target
  agree with the supplied destination; a supplied URL is not proof of a tested
  flow. Missing mandatory assets or conditions prevent claiming that scope done.
- Body fields are separable from labels and production/review notes. Actual
  render fit, inbox delivery, legal clearance and conversion performance require
  separate evidence; text quality does not establish them. Hard bounds require
  a reliable count and method rather than an estimate.
- Report checked / unmet / unverified criterion evidence, not a four-pass receipt
  or naturalness score. Unmet or unverified required checks are not complete.
  Self-review is not the requester's acceptance or publication approval.

</QA>

<Report>

Name `write-copy`, destination, released unit and draft path. Summarize relevant
choices, used sources, applicable evidence and remaining requirements without
exposing sensitive source material. Deliver the complete file, not a whole draft
pasted in the reply. The consumer receives exact text; publication or sending
requires its separate gate. No page was implemented or campaign result measured.

</Report>
