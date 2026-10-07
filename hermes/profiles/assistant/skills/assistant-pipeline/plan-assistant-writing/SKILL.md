---
name: plan-assistant-writing
description: "Plan writing: prose, documents, scripts and storyboards. Frame the client brief, released units and sources; use Writer consultation for decisions, not media production, artifact acceptance or publishing."
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: assistant-pipeline
    tags: ["plan", "writing"]
---

<ReadBeforeWork>

Re-evaluate the entry when the request, mode or domain changes, including within a turn.
Reuse full-body instructions only while present in the current context, not a past load or summary.
Check the kernel and common mode procedure independently. Load each whose full body is missing:

```text
skill_view(name="assistant-pipeline")
skill_view(name="assistant-pipeline", file_path="references/plan/index.md")
```

These dependencies also apply to direct entry. Loading does not restart an approved plan or expand a grant.
If a tool returns unchanged while the earlier body is unavailable, use read_file on `${HERMES_SKILL_DIR}/../SKILL.md` and `${HERMES_SKILL_DIR}/../references/plan/index.md`.
Recover this entry and its own references from ${HERMES_SKILL_DIR} likewise.
Follow next_offset until the whole required document is available; do not invent alternate paths or ranges to evade dedup.
If the required instructions remain missing, stop the affected action and report it, never infer a pass.
Read only applicable detail references below.

</ReadBeforeWork>

# Writing — plan

One mental model governs writing: **you are the editor-in-chief and
the writer is your hands on the text.** What a text must achieve —
its type, reader, claim, medium, length, and sources — is fixed
HERE, with the user, before anything is released; the writer turns a
decided brief into structure and prose under its own craft (skeleta,
Japanese expression/notation knowledge, tone mechanics are its business — brief the
WHAT, never the style rules). A brief whose deliverable-defining
decisions are still open is not releasable — the writer returns it
as a **spec-gap finding**.

## Units — the three kinds

| Unit | Releases with | What it is |
| --- | --- | --- |
| **Outline unit** | the decided brief | structure + 2-3 tone samples for a long deliverable — gated BEFORE drafting, because restructuring a full draft costs a rewrite |
| **Piece unit** | the approved outline (or set decomposition) | one chapter/section of a long text, or one file of a set (doc set, site copy, mail sequence) |
| **Whole small job** | the decided brief | a short piece with no ceremony — copy, a release note, a single README |

Long-form and sets get the outline unit first; a "one article" that
is really a series or a book is a **granularity finding**, not a
bigger draft. The writer holds the document — contiguous text needs
no assembly unit.

## The decision core (every brief)

- **Type** — routes the leaf below; mixed types are separate units.
- **Audience & purpose** — who reads it, what they should
  understand or do; for scripts, also the downstream producer.
- **Medium & destination** — where it appears, and the constraints
  that destination imposes.
- **Tone** — register (敬体/常体), voice anchors, pasteable samples
  when they exist; unsettled long-form tone is settled by the
  outline unit's samples, not mid-draft. For text in a person's or
  character's own name (本人名義 included), name the `characters`
  slug as the voice source in any medium; Writer reads the guide
  itself, so do not paste or restate its rules.
- **Length / language.**
- **Sources** — pasted research conclusions, product facts, links
  (`../plan-assistant-research/SKILL.md`); the writer never invents facts, so a
  brief expecting claims must carry their sources.
- **Done criteria** — what acceptance looks like, observable.

Family-specific decisions live in the leaves; fill objective
defaults yourself and say so, one `clarify` round at most.

For the article pilot, [article.md](references/article.md) interprets this core by operation.
A bounded edit or analysis of existing text does not require every new-writing
decision, a new outline or new research. Preserve the original's settled choices;
ask only what affects the authorized change or requested finding. Writer still
owns form interpretation and craft; editorial scope and acceptance stay here.

## Grounding — the writer informs, you decide

Structure, tone, and effort judgment comes from a writer
consultation turn (Writer's own pre-draft advisory skill, `consult-writer` — still delegated to Writer, not executed by Assistant): a
recommended shape, requested sizing, relevant constraints, inputs and risks.
Read the full reply as planning input, not an approved draft or a writing-QA
pass. The decisions stay here. Reference text can inform advice without becoming
an edit target.
An explicit outline unit still uses the write leaf and its artifact gate;
requests to evaluate or edit an actual target use the analyze/edit leaf.
No installed leaf for the requested work means clarify the scope, not a
generic fallback or permission to create another skill.

## Leaves — pick by type

| Deliverable | Leaf |
| --- | --- |
| Marketing copy — LP body, promotional announcement, promotional mail | `references/copy.md` |
| Article / tutorial / book chapter — read start-to-finish | `references/article.md` |
| Document — README, guide, reference, report, minutes, proposal, slide outline, release notes, issue | `references/documentation.md` |
| Message — email, chat reply, notification, UI or error wording | `references/message.md` |
| Producer-facing script — comic, storyboard, screenplay, timed/TTS | `references/script.md` |
| X single/long post or thread; Instagram feed/reel caption | `references/post.md` |

Each leaf names its QA contract; the validator enforces the
mapping. A text class fitting no leaf is a decision with the user,
grounded by a writer consultation — never a generic brief.

Technical and business documents use `write-document`, `edit-document` or
`analyze-document` through `references/documentation.md`. Existing documentation and
business-document briefs keep their meaning. Factual release notes route
there; a promotional announcement remains copy. An existing document to
analyze is not a request to produce a new one. Pre-document advice remains
a planning consultation.

Message wording uses `write-message`, `edit-message` or `analyze-message`
through `references/message.md`. The requester supplies the relevant context and intended
stance; Writer neither resolves contacts nor sends the resulting text. Public
social posts and promotional mail retain their own routes.

Promotional copy uses `write-copy`, `edit-copy` or `analyze-copy` through
`references/copy.md`, including existing marketing-copy briefs. The selected leaf owns
destination guidance and QA. Keep approved claims, offer terms and disclosures;
do not infer a new campaign or turn analysis into replacement copy.

Production text uses `write-script`, `edit-script` or `analyze-script` through
`references/script.md`. The producer's actual fields and text representation govern the
handoff; a script analysis is a report, not speech input. Do not assume arbitrary
storyboards are supported by a media tool, or treat text acceptance as production
approval. Plain narration does not require scene fields.

## Boundaries

- Writing is **resident-only for now** — no `card_units`; tone and
  structure feedback arrives mid-flight by nature. Revisit only if
  a truly templated text class (fixed format, fixed tone anchor,
  zero taste iteration) proves itself in resident use first.
- The writer drafts; it never publishes. Service-side drafts are marketing
  Execute's gated work; the user publishes. Committing docs into a repo is an
  engineering unit consuming the QA-passed text as a part.
- X/Instagram text uses Writer's `write-post`, `edit-post` or `analyze-post`
  leaf (`references/post.md`). Marketing Execute consumes accepted bodies unchanged
  and owns platform inspection, remote-save consent and draft operations. Other unmigrated
  platform-post channels retain their existing drafting owner; never improvise integration.
