# Mood directions

Each mood provides a starting vocabulary for the Mood line of a design direction.
The five direction lines and the actual product always decide the final execution;
an existing design system or genuine brand guidelines outrank this catalog.
A mood may move token values (radius, weights, chroma, accent count) within the
bounds it states; that is not a tell. Anything listed in [signs.md](signs.md) still
needs a Licensed entry. The catalog is vocabulary, never a scoring rubric. Mood
names (Clean, Minimal, Luxury…) are not Character words.

Compressed catalog. Each entry specifies: Type / Color / Shape / Depth /
Signature (Signature lines list candidates; a direction picks one) / Licensed
(treatments otherwise classified as tells in [signs.md](signs.md), permitted only
in the named place) / Kills it (anti-patterns that break the mood) / Fits. When
using Tailwind with shadcn/ui, map tokens to CSS variables (`--radius`,
`--primary`, `--background`, font variables) for unified application.

### Dark Tech / Cyber — precise, glowing, dense, cold

- Type: geometric grotesk + monospace for data/labels; tabular numbers.
- Color: near-black bg (#0B0D10-ish), ONE neon accent (electric cyan or signal
  green), cool gray ramp. Accent = signal only.
- Shape: radius 0–4px (token override); 1px hairline borders; visible grid lines.
- Depth: surface steps and hairlines; glow and translucency only as licensed.
- Signature: terminal/coordinate motifs, live tabular numbers, scanline or grid
  texture.
- Licensed: one neon accent and glow on live/signal data only; translucency on
  overlays only; a visible hairline grid as structure (never a glowing grid); a
  scanline texture drawn in code in one place.
- Kills it: warm pastels, radius >= 8px, rounded friendly type, cream bg.
- Fits: dashboards, dev tools, web3, monitoring.

### Clean SaaS / Trust — calm, competent, unsurprising

- Type: one humanist sans (Inter-class); hierarchy by size steps; 500 for headings,
  400 for body.
- Color: white/near-white bg, one confident brand hue, warm-neutral grays.
- Shape: radius 6–10px, consistent; subtle borders or bg shifts to separate.
- Depth: one soft shadow step for cards, one for overlays. Nothing else.
- Signature: generous whitespace + one accent-colored primary CTA per screen.
- Licensed: none.
- Kills it: more than two hues, dense borders everywhere, gradient buttons.
- Fits: B2B SaaS, admin consoles, docs.

### Playful Pop — round, bouncy, sweet, bright

- Type: rounded sans; 600 for display sizes only; oversized display numbers.
- Color: 2-3 saturated pastels + cream bg; colored (not gray) secondary text.
- Shape: radius 12–24px; pill buttons; organic blobs allowed.
- Depth: flat colors + hard offset shadows or thick outlines; sticker feel.
- Signature: mascot/emoji-grade icons, bounce on interaction, playful empty
  states.
- Licensed: colored secondary text from the palette, pill buttons, thick 2px
  outlines, hard offset shadows, one bounce on the primary action, saturated pastel
  surfaces, organic shapes as background art in one place; emoji-grade icons only
  as illustration, never as nav icons.
- Kills it: pure black, hairline borders, sharp corners, corporate grays.
- Fits: consumer apps, education, community, kids.

### Elegant Minimal — restrained, airy, precise, quiet

- Type: one refined sans; 300 allowed for display sizes ≥ 40px, 400 elsewhere;
  wide letter-spacing on small caps labels.
- Color: off-white bg, near-black text, ONE muted accent (sage/navy/deep olive);
  hierarchy carried almost entirely by grays and spacing.
- Shape: radius 0–6px; separation by whitespace, almost no borders.
- Depth: essentially flat; at most one whisper-level shadow.
- Signature: extreme whitespace discipline; thin 1px rules used sparingly.
- Licensed: wide-tracked small-caps labels for section names only.
- Kills it: loud accent colors, heavy bold everywhere, tight packing.
- Fits: portfolios, galleries, premium consumer, settings-heavy UIs.

### Editorial — curated, typographic, confident

- Type: serif display for headlines + neutral sans for UI; dramatic size jumps
  (16 -> 40+); tight leading on display.
- Color: paper-white or warm-cream bg, ink-black text, one editorial accent
  (red/cobalt) used like a highlighter.
- Shape: sharp corners (token override); strong grid with intentional asymmetry;
  big margins.
- Depth: flat; hierarchy from type scale, not elevation.
- Signature: oversized headlines, pull-quotes, numbered sections, ALL-CAPS
  micro-labels.
- Licensed: uppercase micro-labels for section numbers and kickers; italic only
  for real titles of works.
- Kills it: bubbly rounded cards, glassmorphism, centered-everything.
- Fits: content sites, landing pages, blogs, media.

### Luxury — dark, slow, gold-accented, spacious

- Type: high-contrast serif (Didone-class) for display; restrained sans body.
- Color: deep charcoal/ink bg OR ivory bg; metallic accent (gold/champagne) in
  tiny doses; desaturated everything else.
- Shape: sharp or barely-rounded; thin 1px gold rules as dividers.
- Depth: flat with vignette-like large imagery; no cartoon shadows.
- Signature: small centered serif wordmark, wide letter-spaced uppercase, slow
  fades (300–500ms).
- Licensed: wide-tracked uppercase wordmark and section labels; slow fades
  300–500ms; serif wordmark.
- Kills it: bright saturated colors, chunky buttons, busy layouts, emoji.
- Fits: brand sites, e-commerce for premium goods, hospitality.

### Brutalist — raw, loud, honest, anti-polish

- Type: default-stack or mono pushed to extreme sizes; no subtlety.
- Color: white/black base + 1-2 shocking accents (electric blue, acid yellow);
  system-default link blue is allowed as a statement; accent count: up to two
  (token override).
- Shape: zero radius / sharp corners (token override); thick 2–4px borders;
  visible structure, no decoration.
- Depth: none, or hard non-blurred offset shadows.
- Signature: exposed grid, underlined links, marquee-grade oversized text.
- Licensed: thick 2–4px borders, hard unblurred offset shadows, system-blue
  underlined links, oversized type.
- Kills it: soft shadows, gradients, pastel harmony, polish of any kind.
- Fits: portfolios, event sites, dev culture, statements. Rarely right for
  products with forms.

## Blending and the template trap

You may blend two complementary moods—for example, pairing typography from
Editorial with color discipline from Clean SaaS—provided both moods are explicitly
named in the direction line.

Avoid the Clean SaaS template trap: Clean SaaS occupies the default visual zone of
modern frameworks. Unless it is anchored by a deliberate brand hue and a clear
signature detail, it flattens into generic, unstyled framework output.
