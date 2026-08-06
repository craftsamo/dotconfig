# Verify engine — never trust a deliverable, including your own

Shared engine for every act of marketing judgment: accepting requested
inputs, gating drafts before approval or publishing, and critique
tasks where the assessment itself is the deliverable (assess mode). The
same checks apply everywhere — only how the result is used differs.

## Checks

- **V1 Brief fit.** Does the deliverable do what the MarketingBrief asks —
  subject, goal, audience, channel? A beautiful post aimed at the wrong
  audience fails here, not at V2.
- **V2 Brand & voice.** Tone matches the brief / per-project voice; audience
  fit over volume or hype. Would shipping this embarrass the owner in front
  of exactly the people it targets?
- **V3 Fact grounding.** Every claim, metric, name, URL, hashtag and mention
  traces to the brief or retrieved facts. Nothing is invented — an
  ungrounded claim is a defect even when plausible. Links resolve; handles
  exist.
- **V4 Platform compliance.** Current specs of the destination surface:
  text limits, media formats/aspect ratios, alt text, thread mechanics.
  Specs drift — when staleness matters (video encodings, new surfaces),
  refetch official sources or request research rather than trusting
  memory.
- **V5 Asset inspection.** For writer/creator deliverables: the files
  actually exist as attachments, open/play, match destination specs, and
  match what the copy references (a post naming a chart needs the chart).
  Japanese copy follows `japanese-writing` notation norms (writer output
  arrives compliant; your own assembly must be too).
- **V6 Post-publish.** After each shipped post: re-fetch the returned
  id/URL once to confirm it is live, then record the URL in a `PROGRESS:`
  comment. A returned id is not proof the post is up.

## Where each check runs

| Situation | Checks | On failure |
| --- | --- | --- |
| Fan-in: accepting a child's deliverable | V1 V3 V4 V5 | Reject against the brief: re-dispatch with a corrected brief (delegate engine) or escalate |
| Draft delivery (no grant / draft-only goal) | V1 V2 V3 V4 | Fix before delivering; label residual assumptions |
| Pre-publish gate (before approval block or in-cap P1 post) | V1-V5, all | Do not ship; fix or block — publishing is irreversible |
| Critique task (assess mode: judge an existing asset/draft) | V1-V5 as the rubric | The findings ARE the deliverable — report severity-ranked, no fixing |
| After publishing | V6 | Mid-thread failure → checkpoint-then-block (publish engine); never re-post shipped items |

## Verdict discipline

- Findings name the check they fail (V1-V6) and the concrete evidence —
  "V3: the 40% metric appears nowhere in the brief or research", not "feels
  off".
- Severity: blocker (do not ship) / fix-first (fix before approval) /
  note (ship, but record). In critique tasks, rank findings and lead with
  the verdict.
- Honest verdicts over comfortable ones — "do not ship this" is a valid,
  complete outcome (SOUL: don't ship a post that shouldn't ship).

## Pitfalls

- Rubber-stamping requested inputs because rejecting feels expensive —
  a revision round is cheaper than a bad post.
- Verifying your own assembly less rigorously than a child's deliverable.
- Treating V4 platform memory as current — specs drift; refetch when it
  matters.
- Fixing the asset inside a critique task — critique reports, it does not
  repair (that is a revision request).

## Verification

- Every shipped post passed V1-V5 before its approval/grant and V6 after.
- Every consumed input has an explicit accept/reject trace
  (accepted into the assembly, or rejected with the failing check named).
- Critique deliverables name checks + evidence + severity for each finding.
