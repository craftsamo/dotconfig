---
name: analyze-mascot
description: >-
  Findings on an existing mascot file, a concept round or a pack — is it
  square and cut out cleanly, does the silhouette read as a shape, does
  it survive 64 px and a light and a dark page, do the measured colours
  match the palette asked for, does every item hold one character against
  its anchor, is any chroma key left — each with a measurement or a
  vision verdict and the leaf that would fix it. Returns text only;
  writes no deliverable. Zero spend.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [mascot, analyze, qa, silhouette, palette, identity, free]
    category: hands
    hands: image-creator
    cost: free
    output: "a findings table in the reply (no file); `deliver:` may be omitted"
    form:
      source:
        required: true
        type: path
        label: "one mascot file, or a directory holding a concept round or a pack (every png / webp / jpg inside is measured)"
        example: "~/Workspaces/Projects/Forge/.agent/deliverables/mascot/pack/"
      against:
        required: false
        type: image
        label: "the approved concept the files must match (identity check)"
      palette:
        required: false
        label: "the palette the character was asked for, as hex — each measured colour is matched to its nearest"
        example: "#2563eb, #6b7280, #fbbf24"
      items:
        required: false
        type: text
        label: "the pose each file should read as — `name: pose`, one per line — so the 64 px check has something to read against"
      note:
        required: false
        type: text
---

<Procedure>

1. Measure everything:

   ```
   ${HERMES_SKILL_DIR}/scripts/mascot-measure.sh <source> \
     --sheet-dir /tmp/analyze-mascot/<stem> [--against <against>] [--palette "#rrggbb,#rrggbb"]
   ```

   `MEASURE:` per file gives `square`, `alpha`, `corner_alpha`,
   `background` (transparent | chromakey | flat, read from the corner),
   `coverage`, `key_px`, `bbox`, `fill`. `PALETTE:` per file gives the
   top 8 opaque colours with their share and, with `--palette`, the
   nearest asked colour and its RGB distance (`d0` exact, under `d40`
   the same colour by eye, over `d100` a different colour). `SUMMARY:`
   counts. Sheets: `pack.png` (256 on grey), `pack64.png` (the 64 px
   read, point-magnified 4×), `silhouette.png` (alpha as black on
   white), `light.png` / `dark.png` (128 on a light and a dark page),
   `anchor.png` (anchor beside item 1). Words in `palette` (`electric
   blue`) are resolved to a hex by you before the call and named in the
   report as your reading.
2. Look, in this order, writing the finding per sheet before the next
   look — vision holds about three images and a run holds about eight
   looks, so a set of more than six files is read in halves: crop
   `pack.png`, `pack64.png` and `silhouette.png` into two (`magick
   sheet.png -crop 2x1@ +repage half-%d.png`) and read the halves, never
   the whole strip. (a) `silhouette.png` — does each shape read as the
   character (or at least as A character with a head, a body and
   limbs) without its colours; a blob, a sliver, or a shape fused with
   its prop is named; a chroma-key or flat file has no silhouette (it
   shows as a full square) and is reported as `n/a`; (b) `pack.png`
   halves — one character throughout? any file that drifts in features,
   palette or proportion; forbidden elements (text, a watermark, a
   ground shadow, a second character); a ghost rectangle, a hole or a
   fringe on the cut-out edge; (c) `pack64.png` halves — with `items`,
   read each tile back as its pose and name the ones that do not read;
   without `items`, name what each tile reads as; a face that has lost
   its eyes at 64 px is named; (d) `light.png` and `dark.png` — one look
   each, whole: a file that loses its edge on either (a white outline on
   a light page, a dark silhouette on a dark page); (e) `anchor.png`
   when `against` was given — the identity verdict in one line. Spend
   the looks in that order; a check you could not reach is reported as
   GAP, never as PASS.
3. Judge: `square=no` is a FAIL (every mascot delivery is square);
   `background=transparent` with `key_px > 50` is a FAIL (the key
   leaked — or a pocket the corner flood missed); `corner_alpha ≠ 0` on
   a file that was asked transparent is a FAIL; `fill` under 0.15 (a
   sliver on an empty canvas) or over 0.95 (touching the edges) is a
   WARN; a palette colour over `d100` from every asked colour and above
   5 % share is a WARN (drift), over 20 % share a FAIL; a silhouette
   that does not read is a FAIL for the recommended concept and a WARN
   for a pack item; 64 px legibility is a WARN (mascots are shown
   large) unless `note` says the file is an avatar, then a FAIL; light /
   dark is a WARN; identity drift is a FAIL when `against` was given.
4. Produce nothing else. The sheets stay under `/tmp/analyze-mascot/`
   (the OS clears it; a multi-file `rm` trips the terminal guard, so do
   not).

</Procedure>

<QA>

A finding without a measurement or a named vision verdict is not a
finding. Every row of the table names: the check, the file (or "set"),
the evidence (`MEASURE:` / `PALETTE:` field or "vision: <what was
seen>"), PASS / WARN / FAIL / GAP, and for WARN / FAIL the fix —
`edit-mascot` (`--cutout key`, another `--fuzz`, a background swap, a
`--crop`), `generate-mascot` corrective on that item (with the prop
rule: large, saturated, off the body's colours), a `generate-mascot`
revise with the palette written as hex in the form, or "re-anchor the
pack" (Creator's / the client's decision, not yours).

</QA>

<Report>

`analyze-mascot`; the `SUMMARY:` line; the findings table (check · file
· evidence · verdict · fix); one line of overall verdict ("the concept
holds; ship" / "not as a pack: 3 items drift from the anchor, corrective
or re-anchor"); `spend: free`; anything Creator must decide.

</Report>
