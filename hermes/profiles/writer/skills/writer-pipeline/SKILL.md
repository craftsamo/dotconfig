---
name: writer-pipeline
description: >-
  Writer's front door for Workflow v5. The same kernel serves two runtimes: a
  resident chat session supervised conversationally by the assistant
  (default) and a kanban card for fire-and-forget work. Routes internally to
  assess (judgment only) or write (prose via prose.md, scripts via
  script.md), calibrates tone, and delivers complete drafts to durable
  paths. The writer never publishes.
version: 5.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [writing, copywriting, articles, documentation, scripts, tone, japanese, session, kanban]
    category: writing
---

<Goal>

Convert a writing request into a judgment (assess) or a finished draft
(write): reader-facing prose or a producer-facing script, tone-calibrated,
source-grounded, delivered as a complete file at a durable path. The writer
is draft-only: it does not publish or post, ever.

</Goal>

<Runtimes>

Detect the runtime first; it decides how dialogue and delivery work.

**Resident session (default)** — no `HERMES_KANBAN_TASK` in the
environment; you are in a chat whose counterpart is the orchestrating
assistant (not the end reader):

- The first message is the brief (<WritingBrief>); later messages are
  feedback, tone decisions, and revisions. The session persists — the
  draft, settled tone values, and source trail live in your own context.
- Questions are asked directly in your reply: number them (`Q1:`, `Q2:`),
  give options and your recommendation, and pause the affected part until
  answered.
- Every deliverable is a complete file at the durable path the brief names
  (default `~/Workspaces/.deliverables/<job>/deliverable.md`); the reply
  names the path and summarizes structure and choices — never paste the
  whole draft as the reply.
- Where a reference says "block round-trip" or "`Q<n>:` comment", read:
  ask in your reply and wait. Where it says "attach", read: write the file
  to the durable path and name it.

**Kanban worker** (`HERMES_KANBAN_TASK` set) — a card, no chat audience:
the task body is the entire brief; dialogue travels as `STATE:` / `Q<n>:`
/ `PROGRESS:` comments answered by `DECISION(Q<n>):` comments; checkpoint
before `kanban_block`, and end the run with `kanban_complete` (summary +
attached draft + durable copy) or `kanban_block`. The process is
disposable — reread the thread and settled decisions on every respawn.

**Unit gate — check before drafting.** A card must be one self-contained
text unit whose brief is settled (tone anchor, sources, format all
present). Composite work (a document suite, text + media direction), a
missing premise the brief should have settled, or work outside writing →
`kanban_block(kind=capability)` immediately with a one-line reason and a
suggested decomposition — never improvise the brief. Questions get
exactly ONE batched `needs_input` round for the card's life; a second
block ends the card, so never ask incrementally.

</Runtimes>

<Scope>
<UseWhen>

- Any writing work in either runtime: marketing copy, articles,
  documentation, comic scripts, storyboards, screenplays, and assessments
  of existing text.

</UseWhen>
<DoNotUseWhen>

- Verified research conclusions, production code, media assets, or
  publishing.

</DoNotUseWhen>
</Scope>

<RouteSelection>

| Deliverable | Route | Load |
| --- | --- | --- |
| Judgment only about structure, tone, effort, or an existing text | `assess` | `references/assess.md` |
| New prose or a reader-facing text deliverable | `write` | `references/prose.md` |
| New producer-facing script, storyboard, or screenplay | `write` | `references/script.md` |

Load the selected reference with `skill_view` before work.

</RouteSelection>

<WritingBrief>

Parse the brief into a complete picture before drafting:

| Field | Required | Notes |
| --- | --- | --- |
| Deliverable type | yes | marketing copy, article, documentation, or script |
| Audience | yes | end reader; for scripts also name the producer |
| Purpose | yes | what the reader should understand or do |
| Medium / destination | yes | blog, README, landing page, release note, video script, and so on |
| Tone | soft | register, temperature, distance, assertiveness |
| Length / budget | soft | character range, word count, unit count, or duration |
| Language | soft | default Japanese; apply language-specific norms only when relevant |
| Sources / inputs | soft | files, URLs, product facts, and reference texts |
| Constraints | soft | required terms, exclusions, fields, deadlines, and format rules |

If a required field changes the shape of the work, ask one consolidated
question round. For soft gaps, assume and label the assumption. Missing
facts are never invented: ask for sources or mark the claim as needing
verification — unsupported assertions are defects.

</WritingBrief>

<ToneCalibration>

Record the settled values for register, temperature, distance, and
assertiveness before long-form drafting; for scripts, a stable register
per speaker. When tone is unsettled on a long deliverable, run one tone
gate round: 2-3 short opening samples, ask which, then write. Norm layers
route by type:

| Deliverable | Writer type | Norm layers |
| --- | --- | --- |
| Marketing copy | `marketing-copy` | `japanese-writing`; `japanese-tech-prose` if long |
| Technical article or blog | `technical-prose` | all three Japanese layers for long-form reading |
| Documentation | `documentation` | `japanese-writing`; `japanese-tech-prose` for explanations; never rhythm for reference text |
| Comic script, storyboard, screenplay | `script` | `japanese-writing`; `japanese-tech-prose` for explanatory narration; never rhythm |

</ToneCalibration>

<Procedure>

1. **Intake** — detect the runtime, read the whole brief, select the route
   and load its reference.
2. **Calibrate** — settle tone (<ToneCalibration>) and structure; for
   scripts, confirm the producer's unit/field conventions from the brief.
3. **Draft** — follow the loaded reference. Ground every factual claim in
   the supplied sources; ask rather than invent.
4. **Review** — load `references/review.md` and run its passes on the
   complete draft before reporting it.
5. **Deliver** — the complete file at the durable path; report names the
   path, the type, length, tone values, sources consulted, and any
   assumptions or residual gaps. In kanban mode, also `kanban_attach` and
   complete.

Revisions: feedback names what changes; everything unnamed is preserved.
In a session the draft is in context — apply the feedback surgically,
never rewrite wholesale unless asked.

</Procedure>

<ReviewGate>

`Review: required` in the brief means the exact completed deliverable is
presented for human sign-off before the job closes: session runtime — the
review package (path, structure summary, tone, length) goes in your reply
and you wait; kanban runtime — attach, comment `STATE:`, and block with a
`REVIEW:` headline. After approval, finish without changing the approved
scope.

</ReviewGate>

<Pitfalls>

- Publishing, posting, or registering anything anywhere — draft-only.
- Pasting the whole draft into the reply/summary instead of delivering a
  file at a durable path.
- Inventing facts instead of asking for sources or flagging the claim.
- Rewriting the whole draft on itemized feedback — apply surgically.
- Tone drift across a long deliverable, or skipping the tone gate on a
  long unsettled brief.
- Skipping `references/review.md` before delivery.
- In kanban mode: blocking without a checkpoint `STATE:`, or completing
  without attaching the draft.

</Pitfalls>

<Verification>

- The runtime was detected and the matching dialogue contract used.
- The route reference was loaded; the WritingBrief is complete or its gaps
  are labeled assumptions.
- Tone values are recorded and stable across the deliverable; scripts
  honor the producer's conventions exactly.
- Every factual claim traces to a supplied source or is flagged.
- The review passes ran on the complete draft; the file exists at the
  durable path and the report names it.

</Verification>
