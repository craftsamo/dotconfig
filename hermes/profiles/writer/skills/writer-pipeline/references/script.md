# Script deliverables — comic scripts, storyboards, screenplays

Text consumed by a downstream producer (creator worker, video pipeline,
human artist) who turns it into another medium. Two audiences at once:
the END audience shapes the content; the PRODUCER shapes the format. A
script that reads beautifully but can't be typeset deterministically has
failed its contract.

Loaded from the kernel's Procedure when the TypeTable routes the
deliverable here (漫画台本, 絵コンテ, storyboard, screenplay, 脚本,
scene-by-scene video script).

## Unit contract (the core discipline)

- **Deterministic units.** Number every unit (コマ / ページ / シーン /
  カット) continuously — no gaps, no unnumbered interludes. The producer
  addresses work by unit number.
- **Per-unit fields.** Default set (the brief may override; if it names
  its own field list, that list wins):
  1. 番号 + そのユニットの役割 (what this unit does for the whole)
  2. 見出し (if the medium carries one)
  3. セリフ / ナレーション — verbatim text, ready to render
  4. 構図・表情・行動 — instructions to the producer
  5. 展開上の位置づけ (how it advances the story)
- **Verbatim vs instruction separation.** Text meant to be typeset or
  spoken EXACTLY must be unambiguously marked (its own field or quoted
  block). Instructions never leak into renderable text — a producer must
  be able to copy the verbatim fields without reading anything else.
- **Budget discipline.** Respect stated caps and state the ones you
  chose: dialogue length per panel (可読性 first — a comic balloon holds
  roughly 20-40 JP chars), beats per second for timed scripts (a 60-second
  piece holds ~8-12 beats; the hook lands in the first 3 seconds).

## Story shape defaults

- 4-6 コマ: 起承転結 — one turn, placed at the 転.
- 8-page knowledge comic (X/Instagram): page 1 = cover/hook that survives
  as a thumbnail; one idea per page; last page = recap + CTA.
- Timed screenplay: open on the hook, not the setup; every beat either
  advances or pays off; end with the action you want from the viewer.
- Character voice: fix each speaker's register once (kernel
  ToneCalibration) and keep it per-character consistent across units.

## Layers

- `japanese-writing` (notation): always, for all Japanese verbatim text —
  dialogue, captions, headlines.
- `japanese-tech-prose` (argumentation): narration that explains (knowledge
  comics, tutorial videos) — clarity rules apply to the narration line.
- `japanese-prose-rhythm`: NEVER. Producers scan scripts; rhythm belongs
  inside a unit's dialogue, not across the document.

## Artifact delivery

- The brief names a file (storyboard.md, a screenplay path) → write that
  file exactly where instructed AND attach it via `kanban_attach`
  (workspace files don't survive completion). The final message still
  carries the full script per kernel delivery rules.
- Downstream cards consume this script by unit number — never renumber in
  a revision round; mark dropped units as `(削除)` to keep numbering
  stable.

## Self-review additions

Run via the structure pass of `references/review.md`:

- Numbering continuous; every unit carries all contract fields.
- Verbatim fields contain zero instructions (and vice versa).
- Budgets checked by counting, not by eye — chars per balloon, beats per
  duration.
- The script works WITHOUT the pictures: role + 展開 fields alone should
  tell the whole story in order.

## Pitfalls

- Writing prose that happens to have panel numbers — if a unit can't be
  drawn from its 構図 field alone, it's not a script yet.
- Beautiful dialogue over the balloon budget — the producer will cut it
  blind; cut it yourself first.
- Renumbering units between revision rounds (breaks the producer's
  addressing).
- Loading the rhythm layer because the story "should flow" — flow lives
  inside units; the document stays scannable.
