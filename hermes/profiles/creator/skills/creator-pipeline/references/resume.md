# Resume — continuity across respawns and salvage cards (entry overlay)

Two continuity cases, same discipline: **work that already cost credits is
raw material, never waste**. Resume covers re-entering the SAME card after
a block/crash/timeout; <Salvage> covers a FRESH card asked to recover
another effort's surviving work.

## Resume — re-entry on the same card (load FIRST, then the mode's file)

Every respawned run (the task has prior runs/comments):

1. `kanban_show <id>` — rebuild the dialogue state mechanically: match
   every `Q<n>` against a `DECISION(Q<n>)` (unanswered + gating →
   re-block with the SAME n), recompute the effective Budget (body +
   `AUTHORITY+:` comments), and re-read the mode + intent noted in the
   earlier `STATE:`/`PROGRESS:` comments.
2. **Inventory the workspace** (`$HERMES_KANBAN_WORKSPACE`): scratch dirs
   survive block/crash respawns — deletion happens only on completion.
   List what's already generated; find the locked anchor values (comments,
   attachments).
3. **Spent budget stays spent**: take the tally from the latest
   `STATE:`/`PROGRESS:` comment — never from counting files (failed
   attempts also cost). No recorded tally after a crash → count
   conservatively (files present + 1).
4. **Reuse, don't regenerate**: apply the DECISION to the surviving
   intermediates (post-process, re-crop, continue the batch). Regenerate
   only what the DECISION actually invalidates.
5. Record the re-entry in a short `PROGRESS:` comment (state found, plan,
   tally), then continue the underlying mode's playbook where it stopped.

## Salvage — a fresh card recovering another effort's work (intent)

The card's job is to rescue, complete, or canonicalize assets an earlier
card already paid for (an interrupted batch, candidates needing a canonical
export, work stranded by a crash or an archived chain).

1. **Locate the source** — the body's Inputs must point at it: the source
   card id (its attachments + comment trail) and/or a preserved workspace
   path. Missing provenance → ONE `Q<n>` block; never regenerate what the
   task says already exists.
2. **Inventory BEFORE any spend** — list every surviving artifact and its
   state (complete / needs post-processing / genuinely missing). Attach or
   comment the inventory: it is the salvage plan and the evidence for the
   verify gate.
3. **Classify each item**: reusable as-is → post-process/export only
   (ffmpeg, scripts — costs nothing); incomplete → finish from the locked
   anchor; genuinely missing → produce fresh (`references/produce.md`),
   counted against THIS card's Budget.
4. **Canonicalize** — exact target specs (dimensions, format, naming) per
   the brief; the point of salvage is usually turning candidates into the
   one true set.
5. Verify per `references/verify.md` (salvage profile: the gate is the
   inventory trail — nothing regenerated that existed), deliver per
   `references/delivery.md`.

## Pitfalls

- Regenerating after a respawn what already sits in the workspace —
  inventory before spending, always.
- Counting spend from surviving files — the comment trail is the ledger;
  failures cost too.
- Re-asking an already-DECIDED `Q<n>`, or re-blocking with a new number
  for the same unanswered question.
- Salvage without provenance — "close enough" regeneration drifts the set
  and double-spends.
- Treating salvage's missing pieces as a fresh brief — the inherited
  anchor still governs style; only the spend is new.

## Verification

- Dialogue state rebuilt (Q/DECISION matched, Budget recomputed) and the
  inventory ran before any generation.
- The tally carried forward from the comment ledger; nothing that
  survived was regenerated.
- Salvage cards: inventory attached/commented, every fresh spend maps to
  a genuinely missing item.
