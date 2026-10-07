# Composite media — decomposition archetype

Enter only through the confirmed legacy route in [index](index.md).

This is legacy decomposition — qualify it against a Creator
coverage check first ([Client plan](../../SKILL.md)): a
complete hands-served deliverable (an ad, a tour, a served video)
can be ONE Creator brief, even though it has parts internally.
Decompose here only for a confirmed legacy job.

A deliverable made of parts plus an assembly: a video with scenes,
voiceover, and music; a lettered comic; a captioned explainer; an
article package with illustrations. **A composite is a DAG of
units, never one instruction** — "作って" requests that imply a
composite are decomposed here, at plan time, with the user seeing
the stages.

## Decompose

1. **Name the parts** — each maps to ONE family leaf, or, for a
   hands-served family, a Creator brief. Do not route scenes
   straight into `generated-video.md` or `html-motion.md` by
   default: check Creator coverage first, and load those legacy
   leaves only once the job is confirmed legacy (voiceover → a
   Creator brief for audio-creator's `generate-speech`, approved
   script required
   (`../../../execute-assistant-creative/SKILL.md` "Hands-served families"); music
   bed → an existing track or separately approved Creator-brokered music
   delivery, consumed as a finished input; lettering →
   deterministic composition). Fix each part's decision surface
   from its leaf; a part whose text depends on writer work (script,
   lyrics, captions) sequences the writer BEFORE the part.
2. **Name the edges** — which parts feed which (the voice part's
   duration constrains scene timing; the anchor part precedes the
   batch). Independent parts may run in parallel
   (`../../../execute-assistant-creative/references/legacy/index.md`); dependent parts wait for
   the upstream part to pass your QA.
3. **End with assembly** — one `media-assembly.md` unit whose edit
   spec you fix and whose inputs are exclusively QA-passed part
   paths. A package without a final render (article + images) needs
   no assembly unit — delivery packaging is yours
   (`../../../execute-assistant-creative/references/media-ops.md`).
4. **Budget per unit** — each part gets its own `Budget:` line;
   the composite's cost is presented to the user as the sum, per
   stage, at the one approval.

## Expected decomposition (your inspection standard)

An ordered unit list — anchor units first where a family requires
one, parts in dependency order, assembly last — each line naming
its family leaf, spec status (complete/blocked-on), and Budget.
Present it in plain language; approval covers the released DAG and its
sanctioned spend, not a dependent leaf's later exact-plan or preview gate.

## Pitfalls

- Treating "the whole video always gets rejected as one unit" as a
  blanket rule — it only holds for a legacy unit where the
  assistant itself agreed to this decomposition; a Creator-served
  deliverable can be one brief.
- An assembly unit released while a part is unverified — a defect
  found at assembly costs the whole edit.
- Skipping the writer for embedded text (scripts, lyrics,
  captions) when it was asked for or genuinely depended-on — text
  is a deliverable with its own QA; a separate writing/research job
  is not mandatory for every piece of copy.
- Re-briefing style per part — shared style is an anchor unit whose
  output the parts consume.
