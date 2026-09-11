---
name: generate-card
description: >-
  A CARD with a generated text-free backdrop and exact font-rendered copy:
  OG/social/header/thumbnail/hero/title image or tiled panorama. Six looks or
  a described style. Explicit paid budget approval before generation; default
  3 variants + 1 corrective total across resumes. Supplied art uses create-card,
  finished raster adaptation edit-card, text-free illustration alone is not Card.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [card, backdrop, generation, typography, panorama]
    category: hands
    hands: image-creator
    cost: metered
    output: "text-free backgrounds + create-card bundles per variant + attempts.json + qa.md"
    form:
      title:
        required: true
        type: text
        label: "exact copy, typeset locally after generation; first tile only"
      destination:
        required: true
        other: true
        label: "og, x-post, x-article, x-header, x-pair, x-carousel, instagram, instagram-square, story, youtube-thumb, hero, slide-title, note, or explicit WxH"
      style:
        required: true
        options: [glass, flat-minimal, dark-pro, gradient-glow, paper, soft-3d]
        other: true
        label: "backdrop direction plus exact typesetting look; free style remains verbatim"
      art:
        required: true
        type: text
        label: "subject/composition for TEXT-FREE generated art, including quiet areas for lettering"
      reference:
        required: false
        type: image
        label: "optional appearance reference; needs explicit upload consent and backend reference support before use"
      subtitle:
        required: false
        type: text
      brand:
        required: false
        type: text
      label:
        required: false
        type: text
      meta:
        required: false
        type: text
      motif:
        required: false
        type: image
        label: "approved local raster for deterministic composition, never implicitly uploaded"
      palette:
        required: false
        label: "surface,ink,accent: three comma-separated #rrggbb colours"
      font:
        required: false
        type: file
      tiles:
        required: false
        type: int
        label: "x-pair=2; x-carousel=3|4, default 3"
      tile:
        required: false
        label: "carousel portrait 4:5 (default)|square 1:1|tall 1:2; pair candidate (7:8 unverified)"
      tile_titles:
        required: false
        type: text
        label: "independent headings as 'n: text' lines, main title/brand/meta only on tile 1"
      gap:
        required: false
        type: int
        label: "legacy source-image-px gap, default 16, 0..128; separate carousel display preview uses canonical CSS-px width/gap"
      slug:
        required: false
        type: text
      note:
        required: false
        type: text
---

<Procedure>

1. Load `skill_view("create-card")` and its destination/spec
   references for all geometry, text and local composition rules. Read ONLY
   this leaf's matching backdrop prompt direction:
   [glass](references/styles/glass.md), [flat-minimal](references/styles/flat-minimal.md),
   [dark-pro](references/styles/dark-pro.md), [gradient-glow](references/styles/gradient-glow.md),
   [paper](references/styles/paper.md), [soft-3d](references/styles/soft-3d.md).
   These are art prose, not duplicated composition CSS. Free style requires a
   concrete backdrop prompt AND task-local CSS under create-card's contract.
2. Before ANY media call, obtain explicit budget approval from the user in the
   current work conversation (Creator relays it). Default proposal is 3 variant
   attempts + 1 corrective TOTAL, not permission to spend. Persist the granted
   cap and approval evidence in `<task>/attempts.json`. On every resume read
   previous entries first; never reset spent calls. Record each invocation
   BEFORE calling, including failed/unknown outcomes; never retry an unknown
   result as a free attempt. Increased caps need renewed explicit approval.
   No approval means a proposal/blocker, zero media calls.
3. Preflight actual configured image backend and fallback capabilities: supported
   aspect/output sizes and reference-input surface. Record the capability
   evidence, requested ratio and fitting strategy. No hardcoded 21:9 support
   promise: a full panorama may exceed the backend's aspect range. Propose a
   supported text-free canvas with explicit cover/contain finishing, or stop
   for scope approval if it cannot preserve the art. Do not silently split a
   panorama into extra paid generations. Confirm reference-upload authority
   before sending reference pixels; a local path alone is not consent.
4. Write prompt and generation inputs into task-local files. Ask image_generate
   for art ONLY: no text, logos, labels, letters, pseudo-writing or watermarks;
   main title/brand/meta area on tile 1 and every tile-title area must stay quiet.
   Generate up to the approved variant count, localize the returned outputs
   through the normal tool result, recording original paths/provider/request
   and actual dimensions. Never fetch extra network assets silently.
5. For each background, inspect it ONCE for unwanted lettering and usable
   composition, append finding to qa.md immediately. Use at most the single
   corrective for a specific background defect, within the same persistent
   allowance. Unusable results stay marked, not delivered as passed.
6. Fit each usable TEXT-FREE background to the exact master canvas using the
   strategy approved at preflight, through the shared helper (output file NEW):

   ```sh
   ${HERMES_SKILL_DIR}/../../scripts/img-postprocess.sh <local-background> <new-fitted.png> --size <masterWxH> --fit <cover-or-contain> --format png
   ```

   Use the destination reference's full panorama dimensions, not one tile.
   This fit applies only to text-free art, never to a finished lettered master.
   Write one create-card JSON per usable variant: remove art/reference, add the
   local background path, preserve exact title and every other composition
   field. Follow create-card's renderer command into fresh variant directories.
   When the layout requires more than the template, author its static source
   through create-card's layout_html path; keep the approved copy/art/placement
   and use explicit copy_blocks for additional approved text. This is local
   finishing within the same grant, not another generation or a legacy fallback.
   It font-renders all copy; never ask the model to fix Japanese lettering.
   Rerendering the same existing background/copy is free and spends no new
   generation attempt. A new art revision consumes the remaining grant.
7. Run bounded QA, recommend one candidate, return paths and the persisted
   tally. Do not start another paid round merely because a client has not yet
   chosen. Long calls run background/polling; Japanese prompt/copy stays in files.

</Procedure>

<QA>

Apply create-card's measurement and bounded visual checks per finished variant,
plus one backdrop look per generation. Compare the optional reference once
against the recommended output for appearance, not exact identity guarantees.
Check unwanted lettering, legible contrast on the actual art, per-tile text
placement and coherent panorama seams. Record backend aspect/preflight evidence
and every attempt, including failures. X ratio/crop/gap uncertainties remain
unchanged by generation. Missing paid live evidence is UNVERIFIED, never a pass.

</QA>

<Report>

generate-card; recommended variant and reason; absolute background/bundle/QA and
attempt-ledger paths; exact destination/tile ordering and local simulation label;
measured checks separate from visual verdicts; backend/aspect/reference preflight;
`spend: img N/<approved total> (variants + corrective; failures included)`;
unverified platform behavior and any paid-live or reference-consent gap.

</Report>
