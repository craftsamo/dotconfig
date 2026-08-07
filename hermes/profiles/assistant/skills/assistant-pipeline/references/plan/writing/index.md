# Writing — plan

One mental model governs writing: **you are the editor-in-chief and
the writer is your hands on the text.** What a text must achieve —
its type, reader, claim, medium, length, and sources — is fixed
HERE, with the user, before anything is released; the writer turns a
decided brief into structure and prose under its own craft (skeleta,
Japanese norms layers, tone mechanics are its business — brief the
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
  outline unit's samples, not mid-draft.
- **Length / language.**
- **Sources** — pasted research conclusions, product facts, links
  (`../research/index.md`); the writer never invents facts, so a
  brief expecting claims must carry their sources.
- **Done criteria** — what acceptance looks like, observable.

Family-specific decisions live in the leaves; fill objective
defaults yourself and say so, one `clarify` round at most.

## Grounding — the writer informs, you decide

Structure, tone, and effort judgment comes from a writer
consultation turn (its assess route): recommended shape, outline
sketch, norms layers, effort, risks. Use it to ground the brief and
the decomposition — the verdict informs; the decisions stay here.

## Leaves — pick by type

| Deliverable | Leaf |
| --- | --- |
| Marketing copy — LP body, release note, announcement, mail text | `copy.md` |
| Article / tutorial / book chapter — read start-to-finish | `article.md` |
| Documentation — README, manual, reference, runbook | `documentation.md` |
| Producer-facing script — comic, storyboard, screenplay, timed/TTS | `script.md` |

Each leaf names its QA contract; the validator enforces the
mapping. A text class fitting no leaf is a decision with the user,
grounded by a writer consultation — never a generic brief.

## Boundaries

- Writing is **resident-only for now** — no `card_units`; tone and
  structure feedback arrives mid-flight by nature. Revisit only if
  a truly templated text class (fixed format, fixed tone anchor,
  zero taste iteration) proves itself in resident use first.
- The writer drafts; it never publishes. Shipping text is the
  marketer's gated work; committing docs into a repo is an
  engineering unit consuming the QA-passed text as a part.
- Short-form platform post copy is the **marketer's own craft** —
  the writer produces the long-form parts (`copy.md`).
