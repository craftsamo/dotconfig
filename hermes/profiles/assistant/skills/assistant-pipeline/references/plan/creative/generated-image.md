# Generated image — decision surface

Text-free generated raster art: covers, heroes, illustrations,
thumbnails, social backgrounds, document art. Exact copy on an image
→ `text-card.md`; icon sets → `logo-icons.md`; pixel grid →
`pixel-art.md`.

Technic `creator-generated-image` · QA `raster-image` · metered
`image_generate` · card: `anchored-image-batch` (approved anchor
required).

## Fix before release

- Every rendered ratio and the crop behavior (`cover`, `contain`,
  fixed) — one image may serve several placements.
- Target format, alpha/background rule, file-size cap.
- Style direction: tone, palette, brand colors/assets, reference
  images (pass via `--image` or Inputs paths), prohibited motifs.
- **Exact text stays OUT of generated pixels** — letters, numbers,
  logos route to a deterministic composition (`text-card.md`) or a
  post overlay, as their own budgeted stage.
- Count and per-item subjects for a set.

## Defaults

- Anchor: a locked style block (prompt skeleton + palette), reused
  verbatim with only the subject swapped. Any consistent set or
  unpinned high-cost single → anchor unit first (`asset-set.md`).
- Budget shape: 4 variants per asset, 1 corrective pass.
