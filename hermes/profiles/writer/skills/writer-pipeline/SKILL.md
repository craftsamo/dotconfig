---
name: writer-pipeline
description: >-
  Writer's task front door — the kernel every writer card runs on. Routes by
  deliverable (ModeRouting): write (new text — WritingBrief parsing, tone
  calibration, TypeTable routing onto references/prose.md or
  references/script.md, four-pass review via references/review.md,
  final-message delivery) vs assess (judgment only — consultation or critique,
  references/assess.md). Covers reader-facing prose AND producer-facing
  scripts/storyboards; never publishes. Detailed playbooks live in
  references/, loaded via skill_view file_path.
version: 3.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [writing, copywriting, articles, documentation, scripts, tone, japanese]
    category: writing
---

<Goal>

Produce text the requester can use as-is: marketing long copy, tech
articles / blog posts, documentation (reader-facing prose), and comic
scripts / storyboards / screenplays (producer-facing scripts consumed by a
downstream worker or artist). Quality bar = the consumer's understanding
and the requester's voice — not word count, not speed. The writer drafts;
it never publishes or posts.

This file is the KERNEL: routing, contracts, and protocols only. How-to
detail lives in `references/` — keep it that way. Anything that must never
be skipped (mode choice, brief gates, review gate, grant rules) belongs
here; anything that explains how belongs in a reference.

</Goal>

<Scope>
<UseWhen>

- Any writing task assigned to the writer (kanban or delegate_task).
- NOT for analysis with verified conclusions (researcher), production code
  (engineer), media assets (creator), or posting/distribution (marketer).

</UseWhen>
</Scope>

<ModeRouting>

Route by what the task wants delivered — openers are optional hints, the
deliverable decides:

| The task wants | Mode | Load first |
| --- | --- | --- |
| Judgment only — structure/tone/effort advice for a future text, or an evaluation of an existing text — and no new deliverable text | Assess | `references/assess.md` via `skill_view` (`file_path=references/assess.md`) |
| New text to deliver (prose or script) | Write | the entry reference the TypeTable assigns (`references/prose.md` or `references/script.md`) |

- Legacy opener `Advisory — inform the plan, don't ship.` → Assess.
- A respawn (prior runs / comments on the card) is not a mode: reread the
  thread first per <Resume>, then route as above.
- Never proceed on this kernel alone — load the routed reference before
  doing any work.

Assess tasks deliver an assessment, not prose — an assess task that turns
out to need the actual text is reported as such, not silently written.

</ModeRouting>

<WritingBrief>

Parse the task body into this brief before writing anything:

| Field | Required | Notes |
| --- | --- | --- |
| Deliverable type | yes | copy / article / documentation / script (see TypeTable) |
| Audience | yes | who consumes it; for scripts BOTH the end audience and the producer |
| Purpose | yes | what the consumer should think/do after |
| Medium / destination | yes | X thread, blog, README, LP, release note, 漫画/絵コンテ, video script, … |
| Tone | soft | axes in ToneCalibration; unsettled -> calibrate |
| Length / budget | soft | target range, unit counts, durations; infer from medium if absent |
| Language | soft | default Japanese; JP norms apply only to JP text |
| Sources / inputs | soft | files, URLs, product facts, prior texts to match |
| Constraints | soft | terminology, must-include/-avoid, field lists for scripts, deadlines |

A missing REQUIRED field (or anything that shapes the whole text) ->
`kanban_block(kind=needs_input)` with numbered `Q<n>` questions (2-4
options + recommendation), state note comment first — per the operating
contract. One consolidated block, not one per gap. Soft gaps: assume,
label the assumption in the final message, proceed.

</WritingBrief>

<ToneCalibration>

Tone axes (record the settled values; reuse via MEMORY.md for recurring
projects): register (敬体/常体/だ・である), temperature (calm ↔ energetic),
distance (formal ↔ familiar), assertiveness (hedged ↔ declarative). For
scripts, fix each speaker's register once and keep it per-character
consistent.

- Tone given in the brief, or a reference text supplied -> extract the
  axes, state them in one line in the final message, write.
- Tone unsettled AND the deliverable is long (roughly > 400 chars /
  anything the requester will publish under their name) -> write TWO
  contrasting openings (~200 chars each), then
  `kanban_block(kind=needs_input)` with `Q1: which tone?` presenting both
  samples as options + your recommendation. One round only: on
  `DECISION(Q1)` lock the tone and write the full text.
- Tone unsettled and the deliverable is short/low-stakes -> pick the
  medium-conventional tone, label it as an assumption, proceed.

</ToneCalibration>

<TypeTable>

The deliverable type routes the entry reference and the Japanese norms
layers (loaded via skill_view; layers compose — notation always applies
to Japanese text):

| Deliverable | Entry reference | japanese-writing | japanese-tech-prose | japanese-prose-rhythm |
| --- | --- | --- | --- | --- |
| Marketing copy (LP, 告知, release note, X post) | `references/prose.md` | yes | if long-form argument | no |
| Tech article / blog / tutorial | `references/prose.md` | yes | yes | yes (read start-to-finish) |
| Documentation (README, manual, reference) | `references/prose.md` | yes | explanatory sections only | NEVER — scannable docs stay flat |
| Script (漫画台本, 絵コンテ, storyboard, screenplay) | `references/script.md` | yes (all verbatim text) | narration that explains | NEVER — producers scan |

Non-Japanese deliverables: skip the notation layer; the argumentation
discipline of `japanese-tech-prose` still guides structure.

</TypeTable>

<Procedure>

Write mode. Each step's how-to lives in the named reference.

1. **Brief** — parse WritingBrief; block on required gaps (one
   consolidated block).
2. **Inputs** — read every supplied file/URL before outlining. Heavy
   retrieval (competitive scans, multi-source fact hunts) -> fan out per
   <FanOut>; do not burn your turns on breadth.
3. **Route** — load the TypeTable's entry reference
   (`references/prose.md` / `references/script.md`) + the assigned norms
   layers.
4. **Tone gate** — <ToneCalibration>.
5. **Structure, then draft** — per the entry reference: outline first,
   full text second.
6. **Review** — load `references/review.md` via `skill_view` and run its
   four passes (structure, norms, humanizer, integrity), self-review
   usage.
7. **Review gate** — body carries `Review:` (e.g. `Review: required`) →
   <ReviewGate> before any completion call.
8. **Deliver** — final message: the complete deliverable text first, then
   a short footer (tone axes used, assumptions, open gaps, optional
   variant suggestions). Scripts also write/attach the named artifact per
   `references/script.md`. `kanban_complete` summary = 1-2 plain
   sentences, no deliverable text.

</Procedure>

<ReviewGate>

`Review: required` in the task body means the user signs off on the text
BEFORE the task completes. After the review passes:

1. Put the complete deliverable where the reviewer can read it: attach it
   as a file via `kanban_attach` (drafts don't survive respawns) and leave
   a `STATE:` comment naming the attachment + a 3-5 line synopsis.
2. `kanban_block(kind=needs_input, reason="REVIEW: <one-line description
   of the deliverable>")` — the `REVIEW:` prefix makes the orchestrator
   relay it to the human instead of deciding itself.
3. On respawn: `DECISION(REVIEW): approved` → deliver per Procedure step 8
   (final message carries the full text as usual). `changes — <list>` →
   revise, then a fresh `REVIEW:` round. Scripts: revision rounds never
   renumber units (`references/script.md`).

No `Review:` section → deliver directly; never invent a review round.

</ReviewGate>

<FanOut>

When part of the task belongs to another worker (parallel lookups, an
asset, analysis) or exceeds your tools, decompose on the board — never
wait in-process:

1. `kanban_create` the child cards — each body self-contained per the
   orchestrator's task-spec rules (a child never sees this task's thread;
   e.g. competitive scans to searcher/researcher instead of burning your
   turns on breadth).
2. `kanban_create` a **continuation card assigned to your own profile**
   with `parents=[the child ids]`: its body says what to do with their
   results (their completion summaries/metadata arrive in the injected
   context; `kanban_show` a parent id for detail). It is a bookmark for a
   future run of you — that run starts with zero memory of this one, so
   the body must stand alone.
3. `kanban_complete` the current card ("decomposed into <ids>") and stop —
   never wait for children. The dispatcher wakes the continuation card
   when they all finish (fan-in).

Rules:

- **Grants never propagate.** Write into a child at most your own
  effective grant (writer never publishes; children inherit draft-only) —
  never more. A child that would need a wider grant is a question for the
  orchestrator: block on YOUR card, don't mint.
- Children you create notify nobody (no chat subscription); the
  orphan-watchdog cron is the safety net, not a license. Decisions that
  need the user go through your own card's block round-trip, never a
  child's.
- `delegate_task` stays right for quick in-turn parallel lookups you can
  wait out inside one run; the board is for heavier or durable stages.

</FanOut>

<Resume>

A respawn after block/crash: reread the kanban thread (`STATE:` notes,
`DECISION(Q<n>)` answers) before writing; honor settled decisions instead
of re-asking. Drafts do not survive in the workspace contract — long tasks
leave the current outline/tone in a `STATE:` comment at each block so
nothing is lost.

</Resume>
