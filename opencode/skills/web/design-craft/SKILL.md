---
name: web-design-craft
description: >-
  Use when a web UI needs a visual direction or looks AI-generated / vibecoded
  and must be redesigned into a crafted interface: audits common tells
  (gradients, glows, gradient titles, emoji, badges, 3D shapes, all-caps tags,
  pulsing, bad spacing, hype copy), sets a direction, then works through nine
  passes from spacing to motion. Also proposes a direction when no design system
  exists. Japanese triggers: (AIっぽい, AI感, AIっぽいUI, AI感を消す, 垢抜けさせて,
  UIを磨いて, デザインを整えて, デザインの方向性, 配色, タイポグラフィ,
  ビジュアル方針, 既存デザインシステムなし). English triggers: ("make it not look
  AI-generated", "AI slop", "vibecoded UI", "polish this dashboard", "design
  direction", "visual direction", "look and feel", "pick a mood"). Real brand or
  design system wins. Not for measuring rendered images
  (verify-visual-artifact), naming motion (motion-vocabulary), comparing concepts
  beyond web UI (media-craft-direction), standalone assets (media-craft-visual)
  or page capture (web-live-page-capture).
license: MIT
---

# Web Design Craft

Generated interfaces carry a recognizable fingerprint: decoration everywhere,
spacing nobody chose, copy that performs instead of informs. This skill removes the
fingerprint and then gives the screen an identity. What the product does stays
untouched — its features, its content and the sequence of its sections; how it looks and reads is
decided item by item. A tidy screen that could ship under any other name has not
reached the goal.

## Core principle: where the richness goes

Budget the richness. Treat color, material and effects as a small budget: spend
almost none on chrome (backgrounds, buttons, borders, labels) and nearly all of it
on one or two pieces of content the user came for — a chart drawn with care, an
object rendered with real material, an image from the product's world.

## Target qualities

| Quality | Test you can run |
|---|---|
| Focus | Cover the main moment with your hand: the rest of the screen should look nearly monochrome. |
| Restrained chrome | Navigation, buttons and labels use only ramp neutrals and the single accent; no element emits light. |
| Explainable visual | One sentence says what the visual shows and why only this product would show it. |
| Breathing room for words | The headline sits on space kept free for it; one primary action, a secondary only when needed. |
| Believable content | Previews could pass for screenshots; objects show weight, light and shadow. |

## Two entry points

- **A. Direction only**: the interface lacks an established design system and the
  user requests a visual direction, mood, color palette, or typography pairing.
  Consult [references/directions.md](references/directions.md), select or blend an
  appropriate mood for the product, write the five direction lines, select baseline
  tokens from [references/tokens.md](references/tokens.md), and conclude with the
  proposal unless explicitly directed to implement it.
- **B. Redesign**: an existing screen looks generated, vibecoded, or unpolished.
  Execute the complete redesign workflow.
- **Precedence**: an existing design system, authentic brand identity assets (vector
  logos, brand colors, distinctive typefaces not themselves tells), and explicit user
  instructions supersede these defaults. When an adequate token system exists,
  preserve its values and refine only how they are applied.

## Workflow

1. **Inspect the screen**: Locate the rendering source files. Launch the application
   or open the target markup and capture a screenshot to evaluate what users actually
   see, rather than inspecting code in isolation.
   - Local HTML file: serve its directory (`python3 -m http.server` in that folder)
     and capture a screenshot with Playwright (installed under
     `~/.config/opencode/node_modules`) or `web_ui_check`, which only accepts
     local/private URLs (no `file://`). The baseline screenshot does not count
     toward the three-render budget.
   - Live URL without code: save the rendered DOM with inlined styles and assets to a
     local HTML file via Playwright, work on a duplicate, and verify parity with the
     live screenshot before editing. Canvas animations do not survive inlined markup;
     document them from the live page during audit. Emulate the user's active theme
     (light/dark).
   - Screenshot only: rebuild as one static HTML file matching the image closely,
     treating that markup as the baseline.
   - Report note: redesigned code is handed to site maintainers. Keep the UI's
     language; do not translate unless asked. Japanese UI rules apply when UI strings
     are Japanese or localization is requested.
2. **Audit**: Review every category in [references/signs.md](references/signs.md).
   Record each detected tell on one line, with several locations allowed on one line.
   When longer than ~25 lines, lead with the five tells that change the screen most,
   followed by the full list.
3. **Calibrate depth honestly**:
   - Heavy (tells pervasive across color, typography, icons, and copy): execute the
     full nine-pass redesign.
   - Light (a designed screen with a handful of tells): correct exactly the audited
     items. The existing brand is the direction; palette, fonts, layout and imagery
     stay. Anything bigger, such as a new chart or generated
     imagery, is proposed in the report and left unbuilt.
   - None: if the audit is empty, report that, offer at most three exact tweaks, and
     change nothing unless the user picks them.
4. **Formulate direction**: Draft the five direction lines and stop. Present the
   audit findings and proposed direction, then wait for user approval before editing.
   Ask through the `question` tool; without it, end the turn with the question in
   the reply.
   Alternatives list only the lines that differ from the recommended direction. Skip
   the wait only if the user explicitly requested unattended execution.
   - Handling unknowns: when a comparison basis, audience, or reporting period is
     missing from the page, or the page contradicts itself (such as a monthly figure
     over a weekly chart), write the explicit assumption into the direction and ask
     about it in the approval question; never present a guess as fact.
5. **Apply the nine passes in order**: Complete each pass across the entire screen
   before proceeding to the next. When almost every line changes, decide all nine
   passes first, then rewrite the screen in a single edit that honors each of them.

| Pass group | Why it comes here |
|---|---|
| Rhythm first | Spacing settles the grid and proportions; color cannot be judged while gaps are unresolved. |
| Words before type and layout | Copy length dictates font sizes, line wrapping, and container bounds. |
| Imagery and motion last | Visual moments and motion fit into an interface that must already function without them. |

6. **Verify**: Run mechanical checks and audit validation (see Verification).
7. **Report**: State the adopted direction, summarize changes per pass, list removed
   or unverified marketing claims, and include any authored image generation prompts.

Checking budget: three renders per run (the baseline is free). Kick off any image
generation the moment the direction is approved; do spacing, color and icons while
it renders.

## Direction

Every line must be traceable to something on the page or in the brief; if you
cannot point to its source, it is a trend talking:

- **Product**: what it accomplishes and for whom, stated in one concise sentence.
  The product name may seed the World when it names a material or place.
- **Character**: two or three concrete descriptive words (e.g. "dry, exact, quick";
  "soft-spoken, tactile, careful"; 「きびきび、几帳面、少し茶目っ気」). Banned empty
  descriptors: clean, modern, sleek, minimal, premium (and Japanese equivalents:
  シンプル, モダン, 洗練された, おしゃれ).
- **World**: the natural physical environment or material realm the product inhabits
  (e.g. a recipe app near cutting boards and steam; a payroll tool near ledgers and
  Friday afternoons; a weather app near barometers and open windows). Dictates the
  neutral ramp tint, accent hue, and visual assets. Keep the existing theme
  (dark/light) unless the direction gives a reason; offer the other as an
  alternative.
- **Moments**: one or two specific focal points granted rich chromatic depth and
  tactile detail (an authentic preview card or device render, an analytics chart with
  distinct categorical colors, an evocative physical artifact).
- **Signature**: a single distinctive recurring detail unique to this product (e.g.
  a tick mark on settled items for a bookkeeping tool; a small barometer needle for
  weather; a dashed seam line for a sewing-pattern shop; a timecode stamp for a
  video editor). Choose exactly one.
- **Mood (optional sixth line)**: an aesthetic mood selected from
  [references/directions.md](references/directions.md) when applicable. Its licensed
  treatments apply only when recorded here.

These are samples of the format. Build yours from the product you are working on.
A logo does not launder a tell: sparkles, glow and violet-to-blue blends count as
brand only when the user says so.

## Licensing rule

Treatments cataloged in [references/signs.md](references/signs.md) are classified as
tells when applied indiscriminately. A treatment is licensed only when the direction
explicitly names it, specifies its exact element, and confines it strictly to that
role. For example, a Dark Tech direction may license a single neon accent and glow on
live telemetry streams; an Editorial direction may license uppercase micro-labels on
section indices; Playful Pop may license hard offset drop shadows and active button
bounce; Brutalist may license heavy borders and system-blue links. Any tell not
explicitly licensed remains an anti-pattern to be eliminated. Document every licensed
treatment in the final summary.

## The nine passes

Baseline metrics and scales are defined in [references/tokens.md](references/tokens.md).

### 1. Spacing
- Align all dimensions, margins, paddings, gaps, and heights to a 4px grid. Any
  multiple of 4 is fine even when not in the scale list (e.g. 28, 104); do not
  over-snap. 2px nudges inside small controls and optical centering are fine.
- Eliminate arbitrary custom values (`pt-[15px]`, `gap-[9px]`, `w-[213px]`,
  `px-[11px]`) in favor of scale steps.
- Enforce strict consistency: list rows share identical height; peer cards share
  identical padding.
- Proximity shows grouping: members of a group sit tighter to each other than the
  group sits to its neighbours; start generous and remove.
- Maintain planar alignment: icons share a fixed-width column, labels share a common
  baseline, tabular numbers align along a shared right boundary.
- Navigation requires the highest density: rows 32–36px tall, separated by 2–4px gaps,
  with section labels spaced ~24px above and 8px below. Measure the sidebar after the
  spacing pass; spacing breaks there most often.
- Calibrate padding to density: compact sidebars ~16px, cards 20–24px, outer canvas
  edges 24–32px.

### 2. Color
- Remove multi-hue surface gradients, gradient text, glowing drop shadows, chromatic
  radial blobs, and neon borders. Borders become hairlines at 6–10% opacity.
- Derive every surface, border and text color from a single low-chroma ramp whose
  hue comes from the World line (tokens reference). If a
  screenshot of the background alone could be named by its hue, it is too tinted;
  operational dashboards and apps remain near-grey.
- Maintain three clear text roles: primary, secondary, and muted (muted text strictly
  for meta and captions, verified >= 4.5:1 on its surface).
- Apply a single accent color across chrome: primary CTA, active selection, key
  metric. Text on accent >= 4.5:1. When the accent itself colors text or strokes on a
  pale background, step its lightness down until it clears 4.5:1.
- An established brand hue serves as the accent and departs surface backgrounds;
  content moments carry rich meaningful color.
- Dark themes have a second option for the primary button: the ramp's lightest step
  as fill with page-dark text, which leaves the accent free for smaller marks such as the active row or one headline number.
- Depth on dark canvases uses surface lightness increments and hairlines; a floating
  window or modal over a backdrop may keep a soft neutral shadow. Light canvases use
  small, soft neutral shadows.
- Semantic indicators carry clear functional meaning and match the ramp's tonal
  saturation.
- The only permitted gradient is a subtle tonal transition within a single neutral
  step.

### 3. Icons
- First delete: an icon that repeats its label or decorates a title goes. Categories
  that need a color cue get a small status dot instead of a pictogram.
- Then convert: every remaining emoji used as an icon, status or tag (📁 ⚙️ 💬 🎯 📣
  ⭐ 🧾) becomes a line icon from one set (the project's, else Lucide) or plain text.
- Spec for every icon: 16 or 18px, 1.5px stroke, colored like the text role beside it
  (secondary or muted); icons never get hues of their own.
- Give each row the same icon box width and an 8–10px gap so labels start on one
  line.

### 4. Copy
- Headlines articulate concrete functionality and audience using existing facts
  without fabricating new claims.
- Strip marketing buzzwords (supercharge, seamless, unlock, magic, revolutionize,
  game-changing, blanket AI-powered; Japanese: 革新的, 圧倒的, シームレス,
  魔法のように, 爆速, 次世代, 〜を加速).
- Eliminate greeting banners (`Good morning, Priya ☀️`, `「こんにちは、田中さん！」`);
  use functional context or reporting intervals (`Week 44`, `「第44週」`, `Q3 2026`).
- Prohibit exclamation marks in UI copy, and never use `!!`, `「！」`, `「♪」`, or
  decorative emoji.
- Keep controls concise (`Search`, not `Type to search everything…` /
  `「キーワードを入力して何でも探そう！」`).
- State explicit comparative baselines for all metrics (`+8% vs last week`, `5 fewer
  than in September`).
- Omit trailing periods on titles, subheads, labels, buttons, and captions; retain
  them only in multi-sentence paragraphs.
- Flag unverified social claims (`Join 50,000+ happy users`, `3x more productive`,
  unlinked star rows); confirm authenticity, make them specific, or remove; note in
  report.
- Use realistic, domain-accurate mock data rather than placeholder tokens (`[X]`,
  `$000,000`, `Lorem ipsum`).
- Remove decorative badges (`Fresh 🎉`, `Early access 🔥`); retain `PRO` only when
  denoting a real functional tier.
- For Japanese prose beyond interface labels, consult `japanese-writing`.

### 5. Type
- Draw sizes strictly from a fixed scale; standard weights are 400 and 500; 600 only
  for rare emphasis and the wordmark; moods may override within their stated bounds.
  Prohibit 700–900 weights and gradient fills.
- Enforce sentence case for Latin typography; convert wide-tracked all-caps strings
  (`QUICK LINKS`, `TOTAL BALANCE` -> `Quick links`, `Total balance`).
- Tracking below 16px stays at zero or above; to make small text easier to read,
  raise its size or open its spacing, never tighten it. Minimum legibility size is 11px for Latin, 12px for Japanese.
- Standardize numbers using `font-variant-numeric: tabular-nums` and a consistent
  formatting structure across the entire view (not `€9,340` beside `€27,118.65`,
  not a zero-padded `03`).
- Match type families to the product character (see typography catalog in tokens).
  Preserve genuine brand typefaces; replace unselected defaults. Pair one interface
  family with at most one partner family (monospace or display serif; a partner font
  may come from any row of the family table).
- Express visual hierarchy through size and tonal contrast rather than font weight.
- Avoid italics for arbitrary emphasis, and never synthesize artificial italics on
  Japanese typography.
- Follow Japanese typographic specifications detailed in the tokens reference.

### 6. Layout
- Separate things with size, tone and space before reaching for boxes and borders.
  Visual hierarchy readable at squint distance.
- Software interfaces occupy full viewport bounds: 240–280px sidebar, fluid content
  capped at ~1440–1600px, page as long as its content. An original presented as a
  framed mockup floating on a colored backdrop may stay framed, but the app inside
  the frame grows to desktop proportions.
  Below ~1024px the sidebar becomes a drawer behind one menu button; content stacks.
- Limit hero actions to a single primary action, plus one secondary if needed.
- Marketing heroes, first choice when an image tool exists: a scene image behind the
  whole hero. Its subject takes one side, the headline uses the empty side, and a
  product view overlaps the image from below and continues past the fold.
- Alternative hero structures: asymmetric split (text beside a visual occupying at
  least half width) or centered text positioned over an expansive lower product view.
  Stacked, centered layouts are reserved only for concise heroes lacking imagery.
- Position hero copy at the optical center between nav and the top of the product view.
  In split heroes, align copy vertically against the visual; shorten a tall visual
  rather than push text down. Prefer a single cohesive visual asset over clusters of
  floating cards.
- Align extended headlines to the left; center text only for concise one- or
  two-line headings.
- Keep navigation minimal: brand mark, essential links, single action. Secondary
  actions remain quiet text links. Collapse links on mobile screens.
- Compose the initial viewport holistically: ensure the hero spans viewport height
  without dead gaps, positioning the product view to cross the fold and prompt
  scrolling.
- Mobile viewports (375px): stack content vertically in natural reading order, scale
  headlines down, position imagery after CTAs, and simplify a dense preview (fewer
  rows and columns) instead of scaling it down; no text below 11px Latin / 12px Japanese.
- Preserve existing functional sections and sequential order; adjust internal
  alignment and proportions to enhance clarity.

### 7. Details
- Calculate nested corner geometry: `inner_radius = outer_radius - padding` (never
  below the mood's stated minimum (default 4)). Standardize controls at 8–10px,
  cards at 12–16px, panels at 14–20px. Avoid making every container a pill.
- All interactive elements provide `hover`, `focus-visible` (visible ring for keyboard
  users), `active`, and `disabled` states. Data views provide `empty`, `loading`,
  `error`, and `overflow` representations.
- Active states employ a subtle surface elevation step paired with a hairline border,
  not glowing gradients.
- Format metadata, counts, and indicators as quiet monospace text; format keyboard
  shortcuts as discrete physical keycaps.
- Metric cards display concise numbers: category label, primary tabular figure, and
  comparative delta. An object may sit in a stat card only if the figure is a count
  or sum of exactly that object (a receipt beside paid revenue). Decorative emoji
  objects (a giant 💳) are removed; they become a Moment only if the direction names
  one. Vary card widths to establish rhythm.
- Analytics charts rest on muted grids with monospace labels. Eliminate rainbow
  bars, glowing edges, rounded bar caps, and uppercase day tags.
- Establish chart hierarchy: one primary, expansively detailed chart drawn with care
  (smooth line, mirrored comparison), supported by smaller, distinct secondary
  representations (compact ranked lists or tables).
- Apply a single accent color to the primary trend line or active period (defaults
  to current period); render secondary series in neutral steps.
- Select appropriate chart geometry: line for continuous trends, bars for discrete
  comparisons, stacked bars for distributions, progress bars for single targets.
- Brand logos: render as clean text in the primary typeface paired with a flat vector
  mark if present. Eliminate iridescent spheres, gradient tiles, and sparkle icons.
- Apply the product signature detail strictly where functionally appropriate.

### 8. Visuals
- Eliminate decorative filler: 3D spheres, floating chrome shapes, glowing grids,
  wireframe nebulae, and generic AI robotics.
- Landing page heroes require visuals that illustrate authentic product truth.
- Operational dashboards and web applications rarely require generated imagery;
  visual richness stems from authentic interface materials (data visualizations,
  refined typography, product photography, live status). Physical artifacts (such as
  a bank card) are preferably constructed in markup and CSS.
- Reserve image generation for marketing heroes, onboarding sequences, and empty
  states.
- When image generation tools are available, prioritize an expansive world scene
  leaving negative space for text layout.
- Beneath the scene, or as the standalone visual when no generator is configured,
  present a coded interface preview demonstrating the core claim with realistic
  data. Rendering a capability the copy already promises counts as illustration,
  not as a new feature. The preview carries a moment, never a labeled placeholder.
- Consult [references/visuals.md](references/visuals.md) before executing this pass.

### 9. Motion
- Remove loops on anything that is not actually live (`animate-pulse`,
  `animate-ping`, ambient breathing glows, floating transforms) and all parallax.
- Remove sweeping `transition-all` definitions, bouncy physics, and card scale
  transforms on hover; nothing moves more than a few px on hover.
- Preserve purposeful motion: immediate hover surface shifts, minute active scale
  reduction on press (0.97–0.98), dropdowns rising 6–12px while fading in, and smooth
  numerical transitions.
- Explicitly declare transitioned properties (`transition-colors`,
  `transition-[transform,opacity]`). Never animate layout dimensions (`width`,
  `height`, `top`, `left`, `margin`), and avoid animating large blur.
- Respect accessibility settings: under `@media (prefers-reduced-motion: reduce)`,
  suppress spatial movement and transforms, restricting feedback to instantaneous
  changes or gentle opacity shifts.
- Apply a single ease-out curve and standard durations from the tokens reference.
- Restrict initial page load to at most one coordinated entrance: a brief fade-and-rise
  transition with subtle stagger (40–60ms, maximum 6 elements).
- For identifying specific motion concepts or code implementations, consult
  `motion-vocabulary`.

## Boundaries

- Keep the product's name, even when it contains "AI". Preserve authentic brand
  marks.
- Rebuild a logo that is itself a tell as plain type in the interface family, or as
  a single solid glyph.
- Leave features, content and section sequence alone unless asked; rendering a
  capability the copy already promises is not a new feature.
- Meaningless placeholder content may become plausible content.
- What was stripped as decoration is not replaced by the next trend (bento tiles,
  frosted panels, neon edging, film grain or noise overlays).
- Never fabricate features, claims or statistics.
- Let each product's direction decide its look instead of falling back to the same
  familiar template.

## Verification

- Following edits that modify rendered views, execute `web_ui_check` against the
  active development server across desktop and mobile viewports and all supported
  color schemes. Remediate all layout overflow, accessibility violations, missing
  focus rings, console errors, and broken asset links.
- Use `verify-visual-artifact` to measure specific rendered visual properties (exact
  color values, optical centering, contrast ratios of generated PNG assets).
- Walk through the audit checklist; every tell identified during the initial audit
  must be resolved.

## Checklist

### Measured
- [ ] Spacing scale: every value is a 4px multiple, and equivalent components share identical padding and gaps.
- [ ] Contrast pairs: body text contrast >= 4.5:1 measured; accent verified >= 4.5:1 against surfaces and when coloring text or strokes on light backgrounds.
- [ ] Corner geometry: nested corner radii satisfy inner = outer - padding (never below the mood's stated minimum (default 4)).
- [ ] Alignment: icons, label starts and right-aligned numbers each form one straight column.
- [ ] Viewport integrity: tested at 1440px desktop and 375px mobile width with zero overflow.
- [ ] Minimum text size: no typography below 11px for Latin, 12px for Japanese.
- [ ] Reduced motion: complete suppression of spatial transforms under `@media (prefers-reduced-motion: reduce)`.

### Inspected
- [ ] Neutral ramp & roles: single world-tinted neutral ramp defines three text roles (primary, secondary, muted).
- [ ] Clean surfaces: free of chromatic gradients, glowing shadows, gradient text, and color blobs (unless licensed).
- [ ] Iconography: interface chrome and labels are completely free of decorative emoji.
- [ ] Icon consistency: single vector icon library throughout, maintaining identical bounding box dimensions and stroke weight.
- [ ] Typography: weights 400 and 500; 600 only for rare emphasis and the wordmark; moods may override within their stated bounds. Labels avoid tracked all-caps, small text avoids negative tracking, and italics are omitted.
- [ ] Interface copy: factual statements with zero exclamation points, no trailing periods on short UI strings, no greeting banners, and no unverified claims.
- [ ] Number formatting: uniform figure notation throughout, displayed with tabular numerals.
- [ ] States & interaction: interactive elements provide hover, focus-visible (clear ring), active, disabled; data views provide empty, loading, error, overflow.
- [ ] Motion discipline: single decelerated easing curve, zero gratuitous looping or spring bounces, no animated layout properties.

### Judged
- [ ] Direction followed: documented five-line direction respected across all passes, with every licensed tell explicitly recorded.
- [ ] Hero visual: focal visual represents authentic product reality or a coded preview moment, never generic filler and never a labeled placeholder.
- [ ] First viewport: initial screen is holistically composed with no dead vertical bands, inviting exploration below the fold.
- [ ] Squint test: visual hierarchy and primary action remain immediately readable at squint distance.
- [ ] Specificity audit: swapping the brand name for a competitor's exposes any generic template defaults, prompting sharper copy, visual identity, and signature detail.

## Related skills

- `media-craft-visual` (craft and prompt of a standalone image asset)
- `media-craft-direction` (reading references, competing concepts)
- `motion-vocabulary`, `verify-visual-artifact`, `web-live-page-capture`, `japanese-writing`
