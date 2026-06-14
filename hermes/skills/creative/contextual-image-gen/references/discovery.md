# Discovery — gather preconditions

Goal: produce two fact sets before generating — **destination constraints** and
the **design system**. Source order: codebase → Figma/brand doc → ask the user.

## A. Destination constraints

What to find:

- **Exact size(s) & aspect ratio(s)** the image renders at, and **all** of them
  (the same asset is often shown at multiple ratios).
- **Crop behavior** — `object-cover` (cropped, plan a center-safe area) vs
  `object-contain` (letterboxed) vs fixed.
- **File format & max size** (e.g. JPEG/PNG/WebP, ≤ 5 MB).
- **Storage / upload path** (bucket, public URL pattern, signed-upload flow,
  or a file-convention path like Next.js `app/opengraph-image.png`).

### In a codebase (web/app)

Use `search_files` / `terminal` grep; delegate big repos to an `explore` task.

- Render component & ratios: search the image field name and
  `object-cover|object-contain|aspect-\[|aspect-video|next/image|<img`.
- Data field & limits: search the schema/DTO for the field (e.g. `coverImage`)
  and upload constraints (`contentType|maxBytes|image/(png|jpe?g|webp)`).
- Storage: search `storage.googleapis.com|S3|bucket|signed`-URL builders.
- Framework conventions (Next.js app dir): `icon.svg`, `apple-icon.png`,
  `opengraph-image.*`, `twitter-image.*`, `favicon.ico`, `manifest`.

Record exact file:line so the user can verify.

### Figma / brand doc / none

- Ask for the frame size, export settings (format, scale), and placement.
- If nothing exists, ask the user for size + format + where it will live. Do not
  assume.

## B. Design system

What to find:

- **Colors** — primary / accent / background, as hex (convert OKLCH/HSL if
  needed). Source of truth is usually CSS vars / Tailwind theme / a tokens file
  (`globals.css`, `tailwind.config.*`, `theme.*`).
- **Typography** — font family/families (e.g. Geist) and where set
  (`next/font`, `layout.tsx`, font config).
- **Logo & style** — the logo file (SVG preferred) and its visual language
  (flat single-stroke line-art? gradient? 3D?). Note `currentColor`/CSS use.
- **Existing assets** — OG images, icons, illustrations to match for consistency.

Grep hints: `--primary|--accent|--background|oklch\(|#[0-9a-fA-F]{6}`,
`font-(sans|mono)|next/font|fontFamily`, `logo|icon|brand`, `public/**/*.svg`.

## Output (feed into the chosen strategy)

- **Master aspect** = the widest/most-constrained ratio; design a **center-safe
  area** that survives every crop.
- **Format + size target** for export.
- **Palette** (hexes), **font**, **logo path**, **style** (one line).
- **Negative list** appropriate to the destination (no text / no logos / etc.).

If a fact is missing and matters, ask one focused question rather than guessing.
