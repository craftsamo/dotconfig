# Commission — image-creator: pixel-art

Read [commissioning](../SKILL.md) first.

## Leaves

| Deliverable | Leaf | Notes |
| --- | --- | --- |
| a grid-exact pixel still as a native PNG master plus an integer-scale preview | `create-pixel-art` | free, deterministic, fixed palette |

## Choosing and filling

A grid-exact still is this leaf. A model-drawn "pixel" look is not: that is
the `pixel` style of `generate-icon`, `generate-emoji`, `generate-mascot` or
`generate-kit`, and it guarantees neither grid nor palette.

Settle with the user:

- **Purpose** → `what_for`.
- **Grid** → `grid`, the native size (e.g. 32x32). A thin logo or diagonal
  needs the grid size settled before production.
- **Palette** → `palette`: a named one (pico8, gameboy, nes), a colour cap,
  or none.
- **Transparency** → `background`: transparent (default) or a colour.
- **Reduce from a source or draw** → `mode`: `reduce` needs a `source`;
  `draw` needs a `subject` (silhouette, pose, features).
- Optional `preview_scale` (default 16) and `note`.

A generated base image is its own earlier unit (a `generate-*` leaf); its
delivery becomes `source` of a `reduce` unit. A batch is several units with
the same `palette: from:<path of the first delivery's palette.json>`.

## Transport

Free and bounded: `kind="inquiry"` for one small still — use the generic
`inquiry` row in [commissioning](../SKILL.md)'s transport table. Use
`kind="work"` for a batch or when several revisions are expected.

## Round-trip and approvals

No proposal round. A revision is `intent: revise <path of the previous
delivery>` with the change only; the hands keep the previous `palette.json`.
