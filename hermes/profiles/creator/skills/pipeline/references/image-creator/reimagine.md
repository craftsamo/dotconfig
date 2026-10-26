# image-creator: reimagine

Read the [kernel](../../SKILL.md) first. The leaf's form is authoritative; this says what it can express.

## Leaves

- `generate-reimagine` — a client's photo (person, pet, object, scene) re-rendered by an image model in a named or described style, with the same subject, pose and composition; two candidates per style, with a comparison sheet.

## Range

- One or several styles per photo in one request; output at the photo's own size, or a chosen `size`, `aspect` (keep, square, portrait, landscape) and `format` (png, webp, jpg).
- Styles: 3d-character, comic-book, chibi, 70s-street, 80s-anime, risograph, sumi-ink, watercolor, origami, stained-glass, crayon, or a described one.
- `keep: identity+pose+composition` (default) restyles the same picture; `keep: identity` keeps only the subject so the style's world may replace scene, clothes and camera. `background` can name a replacement.
- Always starts from the photo as edit input; it does not invent a subject. The photo leaves the machine, so any photo (not only a person's) needs the user's consent.

## Where directions go

- `style` carries the look (a comma list for several); one file per option under `references/styles/` of `generate-reimagine`, e.g. `skill_view(name="generate-reimagine", file_path="references/styles/watercolor.md")`.
- `keep`, `background`, `aspect`, `size`, `format` and `note` carry the rest.

## Boundaries

- No photo, a new character: [mascot](mascot.md). A set of expressions of a character: [emoji](emoji.md).
- Text on the image: [card](card.md). Motion from the photo: [clip](../video-creator/clip.md) with the photo as its starting still.
- Deterministic edits of a finished image (cutout, crop, recolour) belong to the edit leaves of [icon](icon.md), [emoji](emoji.md) or [mascot](mascot.md).

## Examples

No stored example; propose the leaf's representative sample unit: one photo in one or two named styles, two candidates each, shown on a comparison sheet.
