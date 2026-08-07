# Infographic — decision surface

An information-led visual summary with a layout × style grammar.
Dense exact text, precise labels, or number tables → `svg-diagram.md`
(generated rendering cannot guarantee them).

Technic `creator-infographic` · QA `infographic` · metered
`image_generate` · resident-only.

## Fix before release

- The source information set — the data, order, and hierarchy the
  graphic must carry; content fidelity is an invariant (every
  rendered word/number is read back against it).
- Layout × style grammar: which organizing structure (timeline,
  comparison, flow, map) and which visual style.
- Ratio/dimensions — custom ratios render at the nearest supported
  enum and are normalized after; fix the final target.
- Destination format and size cap.

## Defaults

- Anchor: none for a single graphic; a series shares one locked
  grammar (anchor unit first per `asset-set.md`).
- Budget shape: 4 variants, 1 corrective pass. Unreadable or altered
  data is a defect, not taste — it re-routes to SVG rather than
  burning passes.
