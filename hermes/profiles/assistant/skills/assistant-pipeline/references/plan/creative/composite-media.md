# Composite media — decomposition archetype

A deliverable made of parts plus an assembly: a video with scenes,
voiceover, and music; a lettered comic; a captioned explainer; an
article package with illustrations. **A composite is a DAG of
units, never one instruction** — "作って" requests that imply a
composite are decomposed here, at plan time, with the user seeing
the stages.

## Decompose

1. **Name the parts** — each maps to ONE family leaf (scenes →
   `generated-video.md` or `html-motion.md`; voiceover →
   `voice.md`; music bed → `audio-generation.md`; lettering →
   deterministic composition). Fix each part's decision surface
   from its leaf; a part whose text depends on writer work (script,
   lyrics, captions) sequences the writer BEFORE the part.
2. **Name the edges** — which parts feed which (the voice part's
   duration constrains scene timing; the anchor part precedes the
   batch). Independent parts may run in parallel
   (`../../execute/creative/index.md`); dependent parts wait for
   the upstream part to pass your QA.
3. **End with assembly** — one `media-assembly.md` unit whose edit
   spec you fix and whose inputs are exclusively QA-passed part
   paths. A package without a final render (article + images) needs
   no assembly unit — delivery packaging is yours
   (`../../execute/creative/media-ops.md`).
4. **Budget per unit** — each part gets its own `Budget:` line;
   the composite's cost is presented to the user as the sum, per
   stage, at the one approval.

## Expected decomposition (your inspection standard)

An ordered unit list — anchor units first where a family requires
one, parts in dependency order, assembly last — each line naming
its family leaf, spec status (complete/blocked-on), and Budget.
Present it in plain language; one approval covers the DAG and its
total spend.

## Pitfalls

- Releasing the composite as one unit ("make the whole video") —
  sequencing and part QA are yours; wholesale briefs come back as
  spec-gap findings anyway.
- An assembly unit released while a part is unverified — a defect
  found at assembly costs the whole edit.
- Skipping the writer for embedded text (scripts, lyrics,
  captions) — text is a deliverable with its own QA, not a
  side-effect of media work.
- Re-briefing style per part — shared style is an anchor unit whose
  output the parts consume.
