# Visuals

Replace decorative filler with visuals that belong directly to the product. When an
image generation tool is available, generate purposeful imagery tailored to the
design direction. For the deeper craft of standalone image assets (compositional
balance, studio lighting, critique), load `media-craft-visual`. This guide governs
the strategic decision, generation, and integration of imagery within a web interface.

## Step 1 — Does the screen need an image?

Run the need test first:
- Operational dashboards, settings consoles, tables, and routine application views
  almost never need generated graphics; their richness comes from real data, live
  status, and typography.
- Marketing hero sections, onboarding flows, and zero-state screens usually benefit
  from a dedicated visual.
- Use one visual where it helps the page communicate, typically in the hero. Never
  insert decorative graphics into every content section.

## Step 2 — Pick the source

Choose the source that best substantiates the product's core claim:

| Source | When to use | What it must show |
|---|---|---|
| Coded preview | Below a hero scene, or as the main visual when no image generator is active | The single scene of use that makes the headline true, built with actual project components or tailored HTML in the new palette, plausible data, and real names. |
| Generated object | Inside the interface, overlapping a card, window, or preview panel | A single physical artifact grounded in the product's world that gives the coded preview weight and tactile reality. |
| Generated scene | Full-width marketing hero backdrop | An expansive environment from the product's world with the subject positioned to one side and calm space reserved for text. |

Coded preview moments:
- A payroll tool shows one payslip with its net amount.
- An API monitor shows one endpoint's latency line with an incident marker.
- A recipe app shows one recipe card with its timer running.

Put a coded preview inside a browser or device bezel only when the frame makes it
easier to read as "the app"; otherwise let it sit on the page.

Narrative consistency within the visual: every detail must tell the same story. If an
adjacent list references purchase order `PO-2291` for a particular client, the
rendered preview or device display must show that exact purchase order number, client
name, and total.

## Step 3 — Write the brief

State the subject in a single sentence with one noun at its centre; a sentence that
needs 'and' is describing two pictures. The following samples show the expected shape:
- "A brass vernier caliper resting on blueprints under low, angled morning sun."
- "An analog telemetry dial in a dark steel chassis, illuminated by a warm indicator needle."
- "A stack of letterpress botanical notebooks tied with twine on a sanded oak workbench."
- "A porcelain coffee cup on a marble counter at dawn."

These are samples of the format. Build yours from the product you are working on.

Then fill the brief. It is what you show the user before generating and what goes in
the report when nothing is generated:

```
subject:      <the one sentence>
composition:  <which side the subject takes, which area stays empty for the headline;
               a full-hero scene is 16:9 or wider with a quiet bottom fifth, because
               the product view overlaps it>
world/light:  <a simple setting, the page background color the edges must melt into,
               where the light comes from>
look:         <one row of the look table below; one look per page>
deliverable:  <slot aspect ratio, rendered at twice its display size>
keep out:     any lettering, marks, interface or watermark
```

Looks, keyed by medium. Pick by the Character line, and check the last column before
you commit to one:

| Medium | What it looks like | Suits | Goes wrong when |
|---|---|---|---|
| Photography | One real thing on a plain field, lit hard from one side | Serious, trustworthy products | The field gets busy or a second object sneaks in |
| Studio render | A real-looking product object (bank card, handset, parcel) with true materials, placed as a moment inside the UI | Products that touch the physical world | The model invents UI text on the object; ask for blank surfaces and overlay HTML |
| Matte 3D | A small scene or object with soft, non-reflective surfaces and gentle light | Friendly, playful products | Gloss, chrome or iridescence creeps in |
| Painting | A sky or landscape backdrop with one subject, painted by hand, wide open sky left for type | Warm, hopeful, human products | The prompt asks for grain or paper texture: the output comes back with a tiled, pixel-level mesh; ask for a clean surface and add texture in CSS |
| Print | One ink, engraving or woodcut, on a tinted page | Heritage, craft, editorial voices | One print-style image sits on an otherwise plain modern page; it reads as a filter unless type and palette live in the same world |
| Physics | A single optical event on a dark field (a prism split, one laser line) | Technical, data-minded products | It turns into rainbow neon, or several effects stack up |

Never brief the stock AI imagery unless the product is literally about it. Three
families cover most of it: sci-fi props (robots, rockets, holograms, glowing brains,
neon circuit boards), abstract shine (orbs, blobs, crystals, liquid chrome, floating
cubes) and cosmic haze (nebulas, any purple-and-blue glossy abstraction).
Montages fail for the same reason a two-noun sentence does: nobody reads them at a
glance.

## Step 4 — Generate, or reserve the slot

With a generator (an image MCP server such as fal, Replicate, OpenAI images or
Higgsfield, or a design tool):

1. Post the filled brief with the model and pixel size, say it may cost money, and
   wait for a yes.
2. Generate once. Hold the result against the subject sentence and the palette.
3. If it misses, find the brief field that caused the miss, change that field, and
   only then generate again. Rerunning an unchanged brief is a lottery.
4. Save the keeper inside the project's asset folder; a remote URL can expire.

Without a generator, and the screen calls for a scene or object: say so ahead of
pass 8 and propose hooking one up; resume when it is available. If the user would
rather skip it, reserve the slot as an empty box in a surface color, sized and rounded
exactly like the final image, with nothing written inside it; an empty box cannot ship
looking finished. The report then carries the brief, the kind of service that could
render it, and the file name the asset should get.

### Objects that sit on the interface

- Brief: one object, studio lighting, a backdrop in the exact page color, a gentle
  shadow where it rests, and an otherwise empty frame; name the angle the layout needs (for example a
  three-quarter view from slightly above).
- Isolate: use the tool's background removal when it has one, otherwise mask its rim
  so it dissolves into the page color. Watch any region whose tone is near the
  backdrop: a powered-off display goes transparent along with the background. Give
  such parts a vivid flat fill in the brief, or regenerate the mask from the object's
  silhouette alone.
- Devices with real UI: generate the device face-on with no perspective, measure the
  screen's rectangle, place live HTML on it, then rotate the wrapper that holds both
  so the text stays crisp and selectable.
- Placement: let the object hang over a card's or panel's border, tipped a few
  degrees, its shadow cast in the deepest ramp tone, so it shares the
  interface's space instead of floating beside it.

## Step 5 — Fit it into the page

- File: WebP or AVIF, rendered at 2× the displayed size; `alt` text names what is
  pictured.
- Edges: the image's background must equal the page color. When it does not, feather
  it (`mask-image: radial-gradient(closest-side, black 65%, transparent)`) or lay a
  page-colored gradient over the seam; a hard rectangle on a different color is a
  tell.
- Loading: give the hero image `fetchpriority="high"` and explicit `width` and
  `height` so nothing shifts while it arrives.
- Motion: none, or one slow movement that belongs to the subject. No parallax, and
  nothing moves under `prefers-reduced-motion: reduce`.
- Code treatments: only on the main visual, only when the Character asks for it, and
  never as fresh decoration elsewhere.
  - Duotone: map the darkest surface to the accent or primary text (CSS grayscale
    paired with a `mix-blend-mode: color` layer or SVG `feColorMatrix`). The quickest
    route from a generated image to one that matches the palette.
  - Halftone: rasterize with dot radius proportional to brightness (editorial,
    print).
  - Dithering: dither into 2–3 ramp colors once at load (retro, technical, playful).
  - Glyph grid: render the composition as a glyph cell (6–10px in the chosen mono,
    colored from the image or ramp) drawn from domain materials (digits and currency
    for finance, brackets and operators for code, note names for music, letters for
    writing, dots and bars for monitoring).
  - Performance rules for animated code treatments: sample pixels once upon
    initialization (avoid recurring `getImageData` calls per animation tick),
    pre-render glyph sprite atlases, limit refresh rate to 8–12 steps per second
    updating a minor fraction of cells, halt execution when scrolled off-screen, and
    cap `devicePixelRatio` at 2.

## Before you hand it over

- [ ] One dominant visual moment anchors the screen, bordered by quiet chrome.
- [ ] The visual explains itself in one sentence with a single focal noun.
- [ ] Headlines sit within calm space intentionally reserved for them.
- [ ] Visual richness springs from authentic materials of the product itself.
