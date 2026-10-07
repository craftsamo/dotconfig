# Generated image — decision surface

Legacy only: use after Creator confirms this method, per [index](index.md).
Never use it as a fallback for a served failure or unsupported field.

Text-free generated raster art: covers, heroes, illustrations,
thumbnails, social backgrounds, document art. Exact copy on an image
→ `text-card.md`; icons of any kind → Creator's hands (`index.md`); pixel grid →
`pixel-art.md`.

Technic `creator-generated-image` · QA `raster-image` · metered
generation through the selected Backend · card: `anchored-image-batch`
(approved anchor required).

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
- **Backend** — name exactly one:
  - `core:image_generate` for the Creator profile's configured cloud
    chain. Prefer it for a handful of finished assets, short deadlines,
    or when local setup time dominates. Its existing in-chain fallback
    remains enabled.
  - `external:comfyui` for a preflighted local workflow. Prefer it for
    high trial counts, character/style consistency, IP-Adapter/ControlNet/
    LoRA work, or a reusable local graph. This backend never falls through
    to cloud; an unavailable runtime comes back to Plan.
  Ask Creator for a zero-spend advisory when hardware, workflow fit, or
  runtime is not already established. Do not release the unit with the
  Backend open.

## Defaults

- Anchor: a locked style block (prompt skeleton + palette), reused
  verbatim with only the subject swapped. Any consistent set or
  unpinned high-cost single → anchor unit first (`asset-set.md`).
- Budget shape: 4 variants per asset, 1 corrective pass.
