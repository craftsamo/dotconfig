---
name: writing-pipeline
description: >-
  Writer's task front door — route every task by purpose (ModeRouting): write
  (the deliverable pipeline, in this file — WritingBrief parsing, tone
  calibration via a one-round sample block, deliverable-type routing onto the
  layered Japanese norms skills, structure -> draft -> self-review passes,
  final-message delivery) vs advisory (Plan-Loop writing consultations —
  structure, tone, effort; playbook in references/advisory.md, loaded via
  skill_view file_path). For reader-facing prose only; never publishes.
version: 2.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [writing, copywriting, articles, documentation, tone, japanese]
    category: writing
---

<Goal>

Produce reader-facing prose the requester can ship as-is: marketing long copy,
tech articles / blog posts, documentation. Quality bar = the reader's
understanding and the requester's voice — not word count, not speed. The writer
drafts; it never publishes or posts.

</Goal>

<Scope>
<UseWhen>

- Any writing task assigned to the writer (kanban or delegate_task).
- NOT for analysis with verified conclusions (researcher), production code
  (engineer), media assets (creator), or posting/distribution (marketer).

</UseWhen>
</Scope>

<ModeRouting>

Pick the mode first:

| Signal | Mode | Playbook |
| --- | --- | --- |
| Task body opens with `Advisory — inform the plan, don't ship.` — or only asks questions (how to structure X, which tone/medium fits, effort estimate) and requests no deliverable text | Advisory | load `references/advisory.md` via `skill_view` (`file_path=references/advisory.md`) before doing any work |
| Anything that delivers prose | Write | the rest of THIS file — the deliverable type (copy / article / documentation) routes the norms layers per <TypeRouting> |

Advisory tasks deliver an assessment, not prose — an advisory task that
turns out to need the actual text is reported as such, not silently written.

</ModeRouting>

<WritingBrief>

Parse the task body into this brief before writing anything:

| Field | Required | Notes |
| --- | --- | --- |
| Deliverable type | yes | copy / article / documentation (see TypeRouting) |
| Audience | yes | who reads it, what they already know |
| Purpose | yes | what the reader should think/do after reading |
| Medium / destination | yes | X thread, blog, README, LP, release note, … |
| Tone | soft | axes below; unsettled -> ToneCalibration |
| Length | soft | target range; infer from medium if absent |
| Language | soft | default Japanese; JP norms apply only to JP text |
| Sources / inputs | soft | files, URLs, product facts, prior copies to match |
| Constraints | soft | terminology, must-include/-avoid, deadlines |

A missing REQUIRED field (or anything that shapes the whole text) ->
`kanban_block(kind=needs_input)` with numbered `Q<n>` questions (2-4 options +
recommendation), state note comment first — per the operating contract. Soft
gaps: assume, label the assumption in the final message, proceed.

</WritingBrief>

<ToneCalibration>

Tone axes (record the settled values; reuse via MEMORY.md for recurring
projects): register (敬体/常体/だ・である), temperature (calm ↔ energetic),
distance (formal ↔ familiar), assertiveness (hedged ↔ declarative).

- Tone given in the brief, or a reference text supplied -> extract the axes,
  state them in one line in the final message, write.
- Tone unsettled AND the deliverable is long (roughly > 400 chars / anything
  the requester will publish under their name) -> write TWO contrasting
  openings (~200 chars each), then `kanban_block(kind=needs_input)` with
  `Q1: which tone?` presenting both samples as options + your recommendation.
  One round only: on `DECISION(Q1)` lock the tone and write the full text.
- Tone unsettled and the deliverable is short/low-stakes -> pick the
  medium-conventional tone, label it as an assumption, proceed.

</ToneCalibration>

<TypeRouting>

Layered norms skills (load via skill_view; they compose — lower layers always
apply to Japanese text):

| Deliverable | japanese-writing | japanese-tech-prose | japanese-prose-rhythm |
| --- | --- | --- | --- |
| Marketing copy (LP, 告知, release note) | yes | if long-form argument | no |
| Tech article / blog / tutorial | yes | yes | yes (read start-to-finish) |
| Documentation (README, manual, reference) | yes | explanatory sections only | NEVER — scannable docs stay flat |

Non-Japanese deliverables: skip the notation layer; the argumentation
discipline of `japanese-tech-prose` (one topic per paragraph, no unsupported
assertions, no hollow phrases) still guides structure.

</TypeRouting>

<Procedure>

1. **Brief** — parse WritingBrief; block on required gaps (one consolidated
   block, not one per gap).
2. **Inputs** — read every supplied file/URL before writing. Heavy retrieval
   (competitive scans, multi-source fact hunts) -> fan out via `kanban_create`
   to searcher/researcher; do not burn your turns on breadth.
3. **Structure** — outline first: copy = hook -> value -> proof -> CTA;
   article = claim -> argument paragraphs (one topic each); docs = task-ordered
   sections the reader can scan.
4. **Tone gate** — ToneCalibration above.
5. **Draft** — full text, applying the TypeRouting layers.
6. **Self-review** — three passes before delivery:
   a. Norms pass: the loaded japanese-* checklists (notation, argumentation,
      rhythm where applicable).
   b. Humanizer pass: load `humanizer`; strip AI-writing patterns, hollow
      intensifiers, symmetric filler.
   c. Integrity pass: every fact, quote, number, and URL traces to the brief
      or a retrieved source; assumptions are labeled; nothing invented.
7. **Deliver** — final message: the complete deliverable text first, then a
   short footer (tone axes used, assumptions, open gaps, optional variant
   suggestions). `kanban_complete` summary = 1-2 plain sentences, no
   deliverable text.

</Procedure>

<Resume>

A respawn after block/crash: reread the kanban thread (`STATE:` notes,
`DECISION(Q<n>)` answers) before writing; honor settled decisions instead of
re-asking. Drafts do not survive in the workspace contract — long tasks leave
the current outline/tone in a `STATE:` comment at each block so nothing is
lost.

</Resume>
