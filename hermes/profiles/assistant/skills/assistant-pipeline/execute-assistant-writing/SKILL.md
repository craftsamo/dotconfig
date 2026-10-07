---
name: execute-assistant-writing
description: "Execute writing: supervise released units and revisions. Preserve Writer ownership and the shared acceptance gate; do not patch text, publish or send messages."
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: assistant-pipeline
    tags: ["execute", "writing"]
---

<ReadBeforeWork>

Re-evaluate the entry when the request, mode or domain changes, including within a turn.
Reuse full-body instructions only while present in the current context, not a past load or summary.
Check the kernel and common mode procedure independently. Load each whose full body is missing:

```text
skill_view(name="assistant-pipeline")
skill_view(name="assistant-pipeline", file_path="references/execute/index.md")
```

These dependencies also apply to direct entry. Loading does not restart an approved plan or expand a grant.
If a tool returns unchanged while the earlier body is unavailable, use read_file on `${HERMES_SKILL_DIR}/../SKILL.md` and `${HERMES_SKILL_DIR}/../references/execute/index.md`.
Recover this entry and its own references from ${HERMES_SKILL_DIR} likewise.
Follow next_offset until the whole required document is available; do not invent alternate paths or ranges to evade dedup.
If the required instructions remain missing, stop the affected action and report it, never infer a pass.
Read only applicable detail references below.

</ReadBeforeWork>

# Writing — execute

The specialist is the **writer** resident session — it drafts; it
never publishes. Writing is **resident-only**
(tone and structure feedback arrives mid-flight by nature; the
revisit condition lives in `../plan-assistant-writing/SKILL.md`). You
release the plan's units one at a time and gate between them.

## Resident session

Start the session with the brief fixed by the type leaf
(`../plan-assistant-writing/references/`): the decision core, the leaf's decisions,
pasted sources, and the unit being released. One session per
document or set — the draft, settled tone, and source trail live in
the session's context, so revisions are cheap. **One owner per
document**: give feedback, never patch the file yourself.

## The unit loop

Served post work selects `write-post`, `edit-post` or `analyze-post` under
`../plan-assistant-writing/references/post.md`. Its receipt is the leaf name, actual artifact
path (or a permitted short analysis reply), post IDs/media mapping and
applicable checks with checked / unmet / unverified evidence. Do not require
the legacy four-pass receipt, old lint, or automatic humanizer for that unit.
Served articles similarly select `write-article`, `edit-article` or
`analyze-article` under `../plan-assistant-writing/references/article.md`. Their evidence names
the released unit, selected destination and any same-stem production notes.
Text acceptance is separate from asset/editor finishing or publication fit.
For articles, carry the requested edit scope unchanged: proofreading is minimal
correction, wording is polishing, and findings-only work is analysis. An article
edit or analysis uses the existing text as its unit, not a new outline release
solely because it is long. The new-writing outline and full-draft instructions
below do not add requirements to a bounded article correction or report. Accept
a checked no-change result; do not request another pass merely to obtain edits.
Return scope conflicts to Plan, not a silently broader writing job.
Served documents select `write-document`, `edit-document` or `analyze-document`
under `../plan-assistant-writing/references/documentation.md`. Their receipt identifies format,
scope, released unit, sources and applicable checked / unmet / unverified
evidence. Edits also name the original and authorized changes. Document analysis
is a report, not a replacement document requiring its target's template.
Do not require legacy lint, four passes or automatic humanizer for these units.
Served messages select `write-message`, `edit-message` or `analyze-message`
under `../plan-assistant-writing/references/message.md`. Require the actual draft/report, channel,
authorized intent/edit scope and applicable criterion evidence. Read only the
necessary context; a receipt must not expose private records or secret values.
Text acceptance is not sending, UI implementation or verified delivery.
Message analysis is a report, not a reply draft. No legacy review is added.
Served copy selects `write-copy`, `edit-copy` or `analyze-copy` under
`../plan-assistant-writing/references/copy.md`. Inspect the actual draft/report, sources and
applicable checked / unmet / unverified evidence; edits also name the original
and authorized changes. Preserve approved claims, commercial conditions and
disclosures. Copy analysis is a report, not a new sales page needing a CTA.
No legacy lint, four-pass receipt or automatic humanizer is added to this unit.
Served scripts select `write-script`, `edit-script` or `analyze-script` under
`../plan-assistant-writing/references/script.md`. Their receipt names format, released unit,
master/raw-text paths, production notes and applicable criterion evidence.
Read originals for edits and targets for analysis. The script QA contract has
separate draft and analysis branches; do not require new dialogue/units from
an analysis report or add legacy lint, four passes or automatic humanizer.
Planning-only consultation uses Writer's own pre-draft advisory skill, `consult-writer` (still delegated to Writer, not executed by Assistant)
and returns advice, not an artifact or acceptance evidence. A released outline
still uses a write leaf; editing/evaluating an existing target selects its leaf.
No additional common review workflow is run after a leaf's own checks.

1. **Release one unit** — the outline unit for long-form/sets
   ("outline + 2-3 opening samples first"), a piece unit against
   the approved outline, or the whole small job. Undecided
   deliverable-defining choices come back as **spec-gap findings**;
   work bigger than its unit (a series inside "one article") as
   **granularity findings** — both go back to Plan, not into a
   bigger draft.
2. **Receive the report** — the file at its durable path, structure
   summary, tone values, sources consulted, the selected contract's review
   evidence, assumptions labeled. Do not require a fixed pass count or score.
3. **Gate** — per `../qa-assistant-writing/SKILL.md`:
   outline gate for outline units (structure against the leaf's
   standard — the cheap moment to restructure), full gate for
   drafts. Feedback turns are itemized and quote-anchored
   ("リード文が硬い — 例: …", "第2章は結論を先に"); everything
   unnamed is preserved.
4. **Accept → hand off or release the next piece.** The approved
   outline governs the piece units that follow; tone settled at the
   outline is never re-litigated per piece.

## Bounded QA revisions

For units enrolled in [Writing QA scoring](../qa-assistant-writing/SKILL.md#evidence-anchored-scoring),
Assistant owns the scorecard; Writer's self-review, including its full-depth
final review score, is evidence to read, never a substitute for it.
Attach each review to the released unit, candidate path or exact permitted
reply, and review round. Before releasing the unit, communicate the applicable
acceptance criteria, authorized scope and correction budget; do not introduce
new taste requirements after seeing the result.

Return only concrete defects: a stable finding label, quoted passage or missing
requirement, evidence, reader impact and required outcome. Preserve everything
unnamed. Writer returns the changed locations and unresolved points in the
existing report. Re-read the complete latest candidate and required exports,
compare the cited corrections and check surrounding continuity; a prior score
or unchanged pathname is not evidence that the new contents passed. Changed
approved text requires renewed acceptance and applicable downstream approval.

Enforce the [QA correction ceiling](../qa-assistant-writing/SKILL.md#correction-ceiling)
for this release, including early stops and post-acceptance consumer defects.
Carry the review-round count and unresolved findings across resumes, never
resetting them because the file or finding was renamed. Release a consumer's
new post-acceptance correction explicitly to the same Writer with its scope;
do not edit the part yourself or waive its renewed acceptance/approval.
Optional improvements on a passing score of 90-94 do not consume a correction
round or require another draft.

## Part handoff

QA-passed text is a **part** for other capabilities — you carry it,
the consumer never reaches into the writer's session:

- Scripts → the actual named producer after independent writing QA and required
  approval. For Creator/audio-creator speech, pass only the approved raw spoken
  file, never a structured master, labels or `.production.md` notes. Map raw
  exports to unit/speaker and verify agreement with the master. Consumer bounds
  come from its actual contract; sectioning or new takes need their own release.
  Text edits require renewed approval and may invalidate prior audio/timing.
  An analyze-script report is decision input, never a production part. Do not
  claim synchronized captions or rendered footage from a written script alone.
- Promotional copy → the marketing job's message units or named web-content
  consumer after independent writing QA. Preserve exact body fields, offer
  conditions and disclosures; no local shortening or humanizer rewrite.
  Corrections return to Writer and changed approved text needs renewed approval.
  Text acceptance is not legal clearance, rendered fit or publication approval.
  An analyze-copy report is decision input, not publishable copy.
- X/Instagram post drafts → marketing Execute unchanged, with post IDs and
  attachment assignments, after writing QA. Analyze results are decision input, never
  publishable post text. Missing media or required unverified checks block
  a complete publishable-unit claim; feedback returns to Writer.
- Repo docs → an engineering unit commits them; the writer never
  touches the repo.
- Document text → the named consumer with source gaps and unperformed checks
  intact. Text acceptance is not execution, reproduced research or a rendered
  deck. Keep known decisions distinct from missing records; request missing
  evidence rather than assigning owners, deadlines or results during handoff.
- Message drafts → the requester or authorized implementation/sending owner,
  with recipient-facing text separate from field labels and QA notes. Acceptance
  never dispatches a message. Changed approved text needs renewed approval;
  consumer corrections return to Writer rather than altering the accepted part.
  A message-analysis report must not be sent as a reply on the user's behalf.
- Article source drafts → the named consumer with production notes and
  unresolved asset/editor dependencies intact. No marker is deleted to make
  a draft look final. Arrange authorized media/assembly work separately and
  verify the assembled result before claiming publication readiness.

## Pitfalls

- Publishing writer output anywhere: the user publishes; marketing Execute
  saves approved service-side drafts only. Repo commits are the engineer's.
- Releasing a long draft with no outline unit, then paying for the
  restructure in a full rewrite.
- Briefing style mechanics already owned by the writing leaf and language core.
- Judging a draft by its reply summary, or forwarding unread text.
- Splitting one document between writer turns and your own inline
  edits.
- Re-opening outline-settled structure/tone in piece feedback —
  that is a plan change, not a revision.
