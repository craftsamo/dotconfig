# Design direction catalog (shared reference)

Loaded from `plan/web-ui.md` (to fix a direction before building) and
`quality-assurance/web-ui.md` (to judge mood consistency in review). Not a
mode file on its own — never load it standalone.

Compressed catalog. Each entry: mood / type / color / shape / depth /
signature / kills-it (anti-patterns that break the mood) / fits. When the
project uses Tailwind + shadcn/ui, express tokens via CSS variables
(`--radius`, `--primary`, `--background`, font variables) so the direction
lands in one edit.

Dark Tech / Cyber — precise, glowing, dense, cold

- Type: geometric grotesk + monospace for data/labels; tabular numbers.
- Color: near-black bg (#0B0D10-ish), ONE neon accent (cyan/indigo/green),
  cool gray ramp. Accent = signal only.
- Shape: radius 0–4px; 1px hairline borders; visible grid lines.
- Depth: glow and layered translucency, not soft drop shadows.
- Signature: terminal/coordinate motifs, live tabular numbers, scanline or
  grid texture.
- Kills it: warm pastels, radius >= 8px, rounded friendly type, cream bg.
- Fits: dashboards, dev tools, web3, monitoring.

Clean SaaS / Trust — calm, competent, unsurprising

- Type: one humanist sans (Inter-class); strong weight contrast for headings.
- Color: white/near-white bg, one confident brand hue, warm-neutral grays.
- Shape: radius 6–10px, consistent; subtle borders or bg shifts to separate.
- Depth: one soft shadow step for cards, one for overlays. Nothing else.
- Signature: generous whitespace + one accent-colored primary CTA per screen.
- Kills it: more than two hues, dense borders everywhere, gradient buttons.
- Fits: B2B SaaS, admin consoles, docs. NOTE: this is the default-look zone —
  it MUST carry a deliberate brand hue and one signature choice, or it reads
  as unstyled framework output.

Playful Pop — round, bouncy, sweet, bright

- Type: rounded sans, chunky weights; oversized display numbers.
- Color: 2-3 saturated pastels + cream bg; colored (not gray) secondary text.
- Shape: radius 12–24px; pill buttons; organic blobs allowed.
- Depth: flat colors + hard offset shadows or thick outlines; sticker feel.
- Signature: mascot/emoji-grade icons, bounce on interaction, playful empty
  states.
- Kills it: pure black, hairline borders, sharp corners, corporate grays.
- Fits: consumer apps, education, community, kids.

Elegant Minimal — restrained, airy, precise, quiet

- Type: one refined sans, light-to-regular weights; larger sizes instead of
  bold; wide letter-spacing on small caps labels.
- Color: off-white bg, near-black text, ONE muted accent (sage/navy/plum);
  hierarchy carried almost entirely by grays and spacing.
- Shape: radius 0–6px; separation by whitespace, almost no borders.
- Depth: essentially flat; at most one whisper-level shadow.
- Signature: extreme whitespace discipline; thin 1px rules used sparingly.
- Kills it: loud accent colors, heavy bold everywhere, tight packing.
- Fits: portfolios, galleries, premium consumer, settings-heavy UIs.

Editorial — curated, typographic, confident

- Type: serif display for headlines + neutral sans for UI; dramatic size
  jumps (16 -> 40+); tight leading on display.
- Color: paper-white or warm-cream bg, ink-black text, one editorial accent
  (red/cobalt) used like a highlighter.
- Shape: sharp corners; strong grid with intentional asymmetry; big margins.
- Depth: flat; hierarchy from type scale, not elevation.
- Signature: oversized headlines, pull-quotes, numbered sections, ALL-CAPS
  micro-labels.
- Kills it: bubbly rounded cards, glassmorphism, centered-everything.
- Fits: content sites, landing pages, blogs, media.

Luxury — dark, slow, gold-accented, spacious

- Type: high-contrast serif (Didone-class) for display; restrained sans body.
- Color: deep charcoal/ink bg OR ivory bg; metallic accent (gold/champagne)
  in tiny doses; desaturated everything else.
- Shape: sharp or barely-rounded; thin 1px gold rules as dividers.
- Depth: flat with vignette-like large imagery; no cartoon shadows.
- Signature: small centered serif wordmark, wide letter-spaced uppercase,
  slow fades (300–500ms).
- Kills it: bright saturated colors, chunky buttons, busy layouts, emoji.
- Fits: brand sites, e-commerce for premium goods, hospitality.

Brutalist — raw, loud, honest, anti-polish

- Type: default-stack or mono pushed to extreme sizes; no subtlety.
- Color: white/black base + 1-2 shocking accents (electric blue, acid
  yellow); system-default link blue is allowed as a statement.
- Shape: zero radius; thick 2–4px borders; visible structure, no decoration.
- Depth: none, or hard non-blurred offset shadows.
- Signature: exposed grid, underlined links, marquee-grade oversized text.
- Kills it: soft shadows, gradients, pastel harmony, polish of any kind.
- Fits: portfolios, event sites, dev culture, statements. Rarely right for
  products with forms.

## Craft baseline (design principles, all directions)

Typography: one font family (two max), a fixed scale (e.g. 12/14/16/20/24/
32/48px), body 16px at ~1.5 line-height, line length 45–75ch, weight/color
over more sizes for secondary text.

Spacing: one scale (4/8/12/16/24/32/48/64px); proximity = grouping; start
generous and remove; align to one grid — mixed alignment reads as broken.

Color: one primary + a neutral gray ramp (5-9 steps) + semantic colors only;
near-black on near-white, never pure/pure; grays carry hierarchy; body
contrast >= 4.5:1 (WCAG AA), checked not eyeballed.

Hierarchy: one dominant primary action per screen; de-emphasize the rest
instead of bolding everything; size/weight/color before boxes/borders.

States and depth: every interactive element needs hover/focus(keyboard!)/
active/disabled; every data view needs empty/loading/error/overflow states;
one shadow scale (small for cards, larger/softer for overlays).

## Design checklist

A miss is a finding, not a vibe:

- [ ] Spacing values come from the scale; gaps group related things.
- [ ] Type scale respected; clear heading/body distinction; line length sane.
- [ ] Alignment consistent; nothing visually drifting or off-grid.
- [ ] One clear primary action; hierarchy readable at squint distance.
- [ ] Color count restrained; grays doing the hierarchy work; AA contrast.
- [ ] No layout breakage at 1440px and 375px (overflow, wrapping, squash).
- [ ] Interactive/empty/loading/error states present where relevant.
- [ ] Mood consistent with the fixed direction; no off-direction elements.
- [ ] Not generic: at least one deliberate signature choice.
- [ ] No new runtime/console errors introduced.
