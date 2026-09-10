---
name: analyze-emoji
description: >-
  Findings on an existing emoji file or pack — does each file meet a
  platform's size / format / byte cap / alpha, do the expressions read at
  32 px, does the set hold one character against its anchor, does it
  survive a light and a dark chat background, is any key colour left —
  each with a measurement or a vision verdict and the leaf that would fix
  it. Returns text only; writes no deliverable. Zero spend.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [emoji, analyze, qa, legibility, identity, free]
    category: hands
    hands: image-creator
    cost: free
    output: "a findings table in the reply (no file); `deliver:` may be omitted"
    form:
      source:
        required: true
        type: path
        label: "one emoji file, or a directory holding a pack (every png / webp / jpg / gif inside is measured)"
        example: "~/Workspaces/Projects/Acme/.agent/deliverables/emoji/slack/"
      platform:
        required: true
        options: [slack, discord, telegram, telegram-emoji, line, generic]
        label: "the platform whose spec the files are judged against"
      against:
        required: false
        type: image
        label: "the character anchor the pack must match (identity check)"
      items:
        required: false
        type: text
        label: "the expression each file should read as — `name: expression`, one per line — so the 32 px check has something to read against"
      note:
        required: false
        type: text
---

<Procedure>

1. Measure everything:

   ```
   ${HERMES_SKILL_DIR}/scripts/emoji-measure.sh <source> --platform <platform> \
     --sheet-dir /tmp/analyze-emoji/<stem> [--against <against>]
   ```

   `SPEC:` is the platform row (from `emoji-fit.sh --spec`, the one
   table). `MEASURE:` per file gives `size_ok`, `format_ok`, `bytes_ok`,
   `alpha`, `corner_alpha`, `coverage`, `key_px`. `SUMMARY:` counts.
   Sheets: `pack.png` (128 on grey), `pack32.png` (the 32 px read,
   point-magnified 4×), `light.png` / `dark.png` (64 on a light and a
   dark chat), `anchor.png` (anchor beside item 1).
2. Look, in this order, writing the finding per sheet before the next
   look — vision holds about three images and a run holds about eight
   looks, so a pack of more than six items is read in halves: crop each
   of `pack.png` and `pack32.png` into two (`magick sheet.png -crop 2x1@
   +repage half-%d.png`) and read the halves, never the whole strip
   (earned on a 12-item pack: the whole-strip reads ran out of looks
   with four tiles unread). (a) `pack.png` halves — one character
   throughout? any item that drifts in hair, eyes, colours, proportion;
   forbidden elements; text; a ghost rectangle or fringe; (b)
   `pack32.png` halves — with `items`, read each tile back as its
   expression and name the ones that do not read; without `items`, name
   what each tile reads as; (c) `light.png` and `dark.png` — one look
   each, whole: an item that disappears on either (a white stroke on a
   light theme, a dark silhouette on a dark theme); (d) `anchor.png`
   when `against` was given — the identity verdict in one line. Spend
   the looks in that order; a check you could not reach is reported as
   GAP, never as PASS.
3. Judge by the platform: `size_ok`, `format_ok`, `bytes_ok`, `alpha=yes`
   are blocking on every platform except `generic`; `key_px > 0` is
   blocking (the cut-out leaked); `corner_alpha ≠ 0` is blocking (the
   background is still there); 32 px legibility is blocking for
   `slack` / `discord` / `telegram-emoji` (shown at 22-32 px) and a
   warning for `telegram` / `line` stickers (shown large); light / dark
   is a warning; identity drift is a FAIL when `against` was given.
4. Produce nothing else. The sheets stay under `/tmp/analyze-emoji/`
   (the OS clears it; a multi-file `rm` trips the terminal guard, so do
   not).

</Procedure>

<QA>

A finding without a measurement or a named vision verdict is not a
finding. Every row of the table names: the check, the file (or "set"),
the evidence (`MEASURE:` field or "vision: <what was seen>"), PASS /
WARN / FAIL, and for WARN / FAIL the fix — `edit-emoji` (re-platform,
stroke, `--cutout key`, crop), `generate-emoji` corrective on that item
(with the prop rule: large, saturated, off the hair), `create-emoji`
(text belongs there), or "re-anchor the pack" (Creator's / the client's
decision, not yours).

</QA>

<Report>

`analyze-emoji` + platform; the `SUMMARY:` line; the findings table
(check · file · evidence · verdict · fix); one line of overall verdict
("ships on slack" / "not on telegram: 3 files are png, re-platform with
edit-emoji"); `spend: free`; anything Creator must decide.

</Report>
