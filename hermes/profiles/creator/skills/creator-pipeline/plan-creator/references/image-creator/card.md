# Plan — image-creator: card

Read [common plan](../../SKILL.md) first.

## Card: one subject, several destinations

Card is one image subject across OG, social/header/thumbnail/title and tiled
panoramas. Read create/generate/edit/analyze-card before legacy text-card.
Fill exact title/destination/style; generate adds art/reference and omits
background, create consumes approved local background. Custom style is literal
direction, not permission to select a nearby named look. ImageCreator can use
the existing template or author a static layout through create-card's
`layout_html` path. Centering, independent typography and additional copy regions
need not fit the template. Let the hands author the source; the client supplies
intent, exact copy and constraints, not HTML. Do not offer generation to satisfy
a CSS-only style change or relax a protected layout because the template cannot
express it. A remaining unsupported requirement is a finding, not user approval
to substitute. An Assistant implementation choice is not a human scope change.

For x-pair explain that 7:8 is only an unverified candidate; obtain the user's
current recommendation or authorized read-only evidence before claiming any
ratio is verified. No posting or account access for testing. For x-carousel
settle 3/4 tiles and portrait/square; tile_titles is an ordered set of per-tile
headings, not a global title repeated across crops. The main title/brand/meta
stay on tile 1; explicit authored copy_blocks can add exact copy or repeat
branding on other tiles without changing those saved fields' meaning.
Preview gaps are simulation choices, never known platform UI.
Other destinations use their reference's authoring default, not an upload cap.
Finished-card edits need explicit fit and must-keep content; own source specs
rerender at each destination. Analyze accepts files as an ordered JSON array
and input_kind single/tiles/panorama, never squeezes them into an image field.

Generate-card's 3 variants + 1 corrective is a proposed total across resumes.
Unlike a metered leaf's documented default allowance, paid Card generation
always needs explicit user budget approval in this work conversation before
any call. Ask in the same round as reference-upload
consent and backend aspect limitations; never promise unsupported panorama
ratios or silently spend extra per tile.
