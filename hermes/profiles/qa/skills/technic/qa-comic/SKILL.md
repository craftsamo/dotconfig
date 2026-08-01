---
name: qa-comic
description: Read-only QA inspection of immutable comic pages and lettering.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [qa, technic, comic, panels, lettering, continuity]
    category: technic
---
<Scope>
Inspect the actual comic pages, not a storyboard or producer summary. Check
sequence, lettering, visual continuity, narrative continuity, and destination
trim/safe areas without redrawing or rewriting.
</Scope>

<RequiredEvidence>
The immutable page set and digests, expected page/panel count and order, approved
dialogue/caption ledger, character/style anchors, trim/safe-area dimensions, and
Researcher evidence for factual claims or quotations.
</RequiredEvidence>

<ChecksProcedure>
1. Inventory and hash every page; remeasure dimensions, page and panel count,
   order, trim, and safe areas.
2. Read every balloon, caption, and sign exactly against the approved ledger;
   check legibility, balloon/tail attachment, clipping, and overlap.
3. Compare characters, props, palette, and style across pages; read the panel
   sequence for action, spatial, and narrative continuity.
4. Return page/panel/line-specific evidence and findings to `qa-pipeline`.

</ChecksProcedure>

<FailOrCantVerify>
Missing page, unreadable lettering, inaccessible render, broken order/continuity,
or missing Researcher evidence for a gating claim is `can't_verify`. Do not
renumber, rewrite lettering, redraw panels, crop, re-export, or publish.
</FailOrCantVerify>
