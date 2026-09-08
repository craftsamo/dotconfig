# File-based execution contract

The filled leaf form is the client contract. The hands serialize it as one
UTF-8 JSON object for the pipeline root's shared card helper; unknown keys and duplicate JSON
keys fail. All asset/font/CSS paths are absolute, local files, not URLs.
Output is an exclusive NEW directory whose parent exists. Never reuse even an
empty output directory or symlink. Failed bundles retain diagnostics, no
successful manifest; use a new path after correcting the cause. `slug` identifies
the spec, not filesystem paths. No helper invokes shell commands from the spec.

```json
{
  "title": "A clear idea",
  "destination": "x-carousel",
  "style": "paper",
  "tiles": 3,
  "tile": "portrait",
  "tile_titles": [
    {"tile": 1, "text": "The overview"},
    {"tile": 2, "text": "The detail"},
    {"tile": 3, "text": "The next step"}
  ],
  "brand": "Example Studio",
  "gap": 16
}
```

`tile_titles` also accepts the form's newline string `1: text\n2: text`.
Indices must be unique, in 1..tiles. Missing later titles intentionally leave
text-free tiles; never repeat the main title on every tile. Empty text is not
an automatic permission to invent copy. Text is HTML-escaped; line breaks stay.
At most 4 tiles, 8192 master width and 24 million output pixels. Those bounds
are LOCAL safety bounds, not platform limits. Input raster assets are at most
40 million pixels / 64 MB and one frame. No SVG, animation or remote reference
is evaluated inside the page. Font files are at most 32 MB and are embedded.

## Tile geometry and preview units

`x-carousel` accepts `tiles: 3|4` and `tile: portrait|square|tall` (default
portrait). Canonical dimensions and display-preview defaults live only in
[the destination metadata](destination/x-carousel.md). `tall` is 1:2; three
tall tiles form an overall 3:2 master. `x-pair` still accepts only candidate
and exactly two tiles, not tall.

Existing saved JSON (including files named card.json) keeps its semantics:
`gap` is 0..128 SOURCE-IMAGE pixels, default 16 for tiled destinations.
`simulated-gap.png` still places full-resolution tiles with that gap.
Do not reinterpret saved gap values as CSS pixels or rewrite old specs.

Carousel create/edit additionally produce `simulated-display.png` and its
`simulated-display.json` label: each image is resized to the canonical declared
CSS display width before spacing it with the canonical effective CSS image gap.
One raster pixel represents one CSS pixel; view at 100% for that scale.
The JSON records image width/height, gap units, scale and LOCAL SIMULATION label;
relay that label alongside the image. This is not a viewport or X UI screenshot,
nor an emulation of DPR, scroll/snap, wrappers or platform crops. `gap` does not
control this separate preview. Upload tiles and master have no baked-in gaps
or seam-content compensating crops. Analyze reports these resolved settings
without rendering media. Pair output remains unchanged.

## Described style

Author a task-local UTF-8 `.css` file and add `style_css: /absolute/look.css`
to the execution JSON while retaining the free description in `style`.
Named styles reject style_css rather than secretly overriding their identity.
One or more flat rules only; allowed selectors:
`:root`, `.stage`, `.panel`, `.accent`, `.orb`, `h1`, `.label`, `.brand`.
Allowed properties: `background`, `background-color`, `background-size`, `color`,
`border`, `border-radius`, `outline`, `outline-offset`, `box-shadow`,
`backdrop-filter`, `font-weight`, `letter-spacing`, `--surface`, `--ink`, `--accent`.
Declare all three root palette variables as #rrggbb. No other variables, URLs,
imports, comments, escapes, nested rules, markup or `!important`. This is an
appearance contract, NOT arbitrary HTML/JS or positioning code. Concrete example:

```css
:root { --surface: #fff4bc; --ink: #232330; --accent: #c83538; }
.stage { background: var(--surface); }
.panel { border: 4px solid var(--ink); box-shadow: 12px 12px 0 var(--accent); }
.accent { background: var(--accent); }
h1 { font-weight: 800; letter-spacing: -0.025em; }
```

If the requested look needs a layout outside this bounded contract, surface
that limitation to Creator instead of substituting a named style. The CSS
allowlist and offline CSP reduce exposure; they do not certify aesthetic
fidelity or trusted local font/image decoder safety. Read the actual screenshot.

## Raster edit

`edit` JSON uses source, destination, explicit fit, optional protected source
rectangles `[[x,y,w,h], ...]`, normalized focus `[0..1,0..1]` only with fit=focus,
and optional title + text_band together. cover centers and crops; focus chooses
the crop center with edge clamping; contain scales inside an opaque cream canvas;
pad never scales and requires the source to fit. No automatic orientation change.
Protected rectangles are checked against the actual rounded scaled crop.
Text band (pixels, at most half height) reserves new space BELOW the fitted
source, never covers it. It is single-card only. Missing protected rectangles
is not proof a destructive crop is safe: the hands must review source content.

## Measurement-only analyze

`analyze` JSON takes `files` as an ORDERED array of absolute image paths,
`input_kind: single|tiles|panorama`, destination and optional tiles/tile/gap,
expected_text and note. Single requires one single-card destination. Tiles
requires exactly the destination's tile count; panorama takes exactly one
full-width image. It returns JSON on stdout, no corrected/new media. The caller
may retain those measurements and a written report at deliver. Dimension
mismatches are findings, not silently resized inputs. It does not infer reading
order from filenames, perform OCR, or assert platform crop safety.
