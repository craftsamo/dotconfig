# Icons — favicon, apple-icon, PWA (derive from the logo)

**Do not `image_generate` icons.** AI can't produce crisp tiny marks or exact
pixel sets, and a set must be visually identical across sizes. Instead **render
the existing logo SVG** to the required raster sizes with `scripts/logo-to-icons.sh`
(uses `rsvg-convert` for the SVG raster and ImageMagick for `.ico`).

If there is no logo SVG, ask for one (or a high-res master PNG). A simplified,
high-contrast mark is best — fine detail vanishes at 16px.

## Standard outputs

| File | Size(s) | Notes |
|---|---|---|
| `favicon.ico` | 16, 32, 48 (multi-res) | classic browser favicon |
| `icon.svg` | vector | modern browsers; keep the source SVG |
| `apple-icon.png` (apple-touch-icon) | 180×180 | iOS home screen; **no transparency** (flat bg) |
| PWA `icon-192.png`, `icon-512.png` | 192, 512 | `manifest` icons |
| Maskable icon | 512 with ~20% safe padding | mark within the central ~80% safe zone |
| Android legacy | 48–192 | optional |

Next.js app-dir conventions: place `app/icon.svg`, `app/apple-icon.png`,
`app/favicon.ico`; the framework wires `<link rel>` automatically. Match whatever
the codebase already uses (from `discovery.md`).

## Procedure

1. Locate the logo SVG (e.g. `public/**/logo.svg`, `app/icon.svg`) and the brand
   color. Note `currentColor` — pass an explicit color if needed.
2. Run:
   ```
   ${HERMES_SKILL_DIR}/scripts/logo-to-icons.sh <logo.svg> <out-dir> [--bg "#FFFFFF"] [--color "#E26E54"]
   ```
   Produces `favicon.ico` + `icon-16/32/48/180/192/512.png` + a maskable variant.
3. **apple-icon**: flatten onto the brand background (iOS ignores transparency
   and adds its own corners — never pre-round).
4. **Maskable**: keep the mark inside the central 80%; pad with the brand bg.
5. Verify legibility at 16×16 (zoom in). If the mark is too detailed, simplify the
   SVG (fewer strokes) and re-render.

## Pitfalls

- Transparent apple-icon → ugly black corners on iOS. Always flatten.
- Mark touching the maskable edge → cropped by the OS mask. Respect the safe zone.
- Re-coloring via `currentColor` only works if you set a color; otherwise it
  renders black. Pass `--color`.
