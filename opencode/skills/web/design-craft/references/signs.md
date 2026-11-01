# Tells of generated UI

Audit the interface against each category below. Record every tell found, noting
its exact component, file, or selector; multiple locations may share one line. Each
tell is listed with its remediation and the pass number (1–9) that resolves it.

A tell named in the direction's Licensed line is permitted in its named place only;
any tell not explicitly licensed must be eliminated.

## 1. Page and surfaces

| Tell | Fix | Pass |
|---|---|---|
| Radial color washes or blurred chromatic blobs placed behind content | Remove entirely | 2 |
| Multi-hue gradients (e.g. violet-to-pink or purple-to-blue) on backgrounds or cards | Single neutral surface derived from world-tinted ramp; reserve accent for state | 2 |
| Colored glows (e.g. `shadow-[0_0_24px_rgba(168,85,247,0.6)]`, glowing cards, drop shadows on emoji) | Remove glow; establish depth through surface elevation steps and hairlines | 2 |
| Glassmorphic translucent cards featuring white inner highlights and colored shadows | Solid raised surface bordered with a clean hairline | 2 |
| High-contrast or neon saturated borders | Hairline border using primary text tone at 6–10% opacity | 2 |
| Ubiquitous chromatic highlighting where every surface competes for attention | Single accent color used once or twice per viewport | 2 |
| Asymmetrical rhythm with a section that floats in empty headroom yet crowds whatever follows it | Balanced, intentional vertical pacing throughout | 1 |
| Disparate padding values across sibling cards | Equal padding on all peer components | 1 |
| Multiple near-identical tints of one hue used for text (e.g. a stack of pale violets that differ by a few percent) | Three distinct text roles (primary, secondary, muted) from one neutral ramp | 2 |
| Arbitrary padding and spacing values (`pt-[15px]`, `gap-[9px]`, `w-[213px]`, `px-[11px]`) | Multiples of the 4px scale | 1 |

## 2. Chrome and navigation

| Tell | Fix | Pass |
|---|---|---|
| Brand logo rendered with gradient tiles, sparkles, or chromatic typography | Clean brand wordmark in primary typeface paired with a flat vector glyph if present | 7 |
| Geometric logo marks rendered as glossy spheres, iridescent bubbles, or glowing dots | Flat graphic glyph in a single solid tone, or unadorned wordmark | 7 |
| Chromatic gradient on active navigation row or header buttons | Subtle neutral surface step with hairline highlight | 2 |
| Luminous or glowing pill badges for counters, status, shortcuts, or plans | Subdued monospace typography or subtle physical keycaps | 7 |
| Decorative status tags scattered across cards (`Fresh 🎉`, `Early access 🔥`) | Remove decorative badges; retain `PRO` only when denoting real functional tier | 4 |
| Uniform fully rounded pill geometry forced onto search bars, inputs, and cards | Proportional radius tied to component scale via nested corner math | 7 |
| Inconsistent heights or row gaps within sidebar or list navigation | Uniform row height (32–36px) and equal vertical spacing (2–4px) | 1 |
| Sidebar category labels spaced awkwardly relative to navigation items | Position label ~24px above its group and 8px below | 1 |
| Verbose or conversational search placeholder (`Type to search everything…`) | Concise action verb (`Search`) | 4 |

## 3. Text and numbers

| Tell | Fix | Pass |
|---|---|---|
| Gradient typography in headings, figures, or brand marks | Solid primary text tone from neutral ramp | 2 |
| Headings set at extreme heavy weights (700–900) | 400 and 500 (600 for rare emphasis); moods may override within their stated bounds | 5 |
| All-caps labels with wide tracking (`QUICK LINKS`, `TOTAL BALANCE`) | Sentence case ("Quick links", "Total balance") with normal or slightly open tracking | 5 |
| Sprawling scale of uncoordinated font sizes and weights | Restrained set of steps from a defined scale, 400 and 500 (600 for rare emphasis) | 5 |
| Inconsistent number formatting (`€9,340` beside `€27,118.65`, zero-padded `03`) | Uniform notation with tabular numerals (`font-variant-numeric: tabular-nums`) | 5 |
| Negative letter-spacing applied to small interface text | Zero or slightly positive letter-spacing; small text gets bigger or looser, never tighter | 5 |
| Italic styling used for arbitrary interface emphasis | Differentiation through size, weight step, or tonal contrast | 5 |

## 4. Words

| Tell | Fix | Pass |
|---|---|---|
| Generic greeting titles (`Good morning, Priya ☀️`, 「こんにちは、田中さん！」) | Contextual page title or active reporting interval ("Week 44", 「第44週」, "Q3 2026") | 4 |
| Exclamation points and sensational punctuation (`!!`) | Calm, factual phrasing | 4 |
| Metric shifts without clear comparative baselines (`+31%!!`, `down 4!!`) | Explicit comparisons (`+8% vs last week`, `5 fewer than in September`) | 4 |
| Unsubstantiated social proof banners (`Join 50,000+ happy users`, `3x more productive`, unlinked star rows) | Verify authenticity; present with specific provenance or remove | 4 |
| Artificial or unrealistic dummy data (`$000,000`, `Lorem ipsum`, `[X]`) | Realistic figures, plausible names, and domain-appropriate context | 4 |
| Vague marketing superlatives, "game-changing", blanket "AI-powered" copy | Literal description of actual capabilities and outcomes | 4 |
| Trailing periods on short UI strings, buttons, and captions | Omit trailing periods on non-sentences | 4 |

## 5. Icons and emoji

| Tell | Fix | Pass |
|---|---|---|
| Emoji used as navigation icons, label accents, or status markers (📁 ⚙️ 💬 🎯 📣 ⭐ 🧾) | Clean vector line icons from a single cohesive set (Lucide/project), or plain text | 3 |
| Sparkle glyphs applied indiscriminately to denote AI features | Remove, or use an explanatory icon only where functional clarification is necessary | 3 |
| Emoji embedded in count badges or pill elements (`42 🧑‍💻`) | Plain numerical text | 3 |
| Mixed icon sizes, styles, and disparate colors across controls | Uniform dimension (16px or 18px), consistent 1.5px stroke, colored via text role tokens | 3 |
| Icons drifting out of vertical alignment across rows | Fixed icon bounding box width per list or row, with 8–10px gap to label | 3 |

## 6. Data display

| Tell | Fix | Pass |
|---|---|---|
| Complex charts rendered with rainbow gradients, glowing segments, rounded bar caps, or uppercase day tags | 1–2 clean series, muted grid lines, monospace labels, and one focal accent color | 7 |
| Multiple competing shades of an accent used across chart series | Neutral steps for background data, reserving primary accent strictly for active metric | 7 |
| Generic sparklines, tally ticks, or miniature bar charts crammed into every metric card | Clear numerical figure, concise label, and comparative delta | 7 |
| Identically sized cards tiled across a grid with duplicated layout templates | Distinct hierarchy: one primary expanded visualization paired with compact metric summaries | 7 |
| Uniform card widths repeating across an entire grid | Vary widths and structural rhythm (e.g. compact stats above wide chart) | 7 |

## 7. Hero and marketing sections

| Tell | Fix | Pass |
|---|---|---|
| Floating decorative shapes, wireframe grids, particle clouds, or abstract glow fields behind hero text | Clean backdrop or an authentic product scene | 8 |
| Shimmer effects, rainbow fills, or animated gradients spanning headline text | Solid primary text tone | 2 |
| Pill banner floating over hero headline (`🚀 Now with AI agents`) | Remove, or present as a discreet text link if referencing genuine updates | 6 |
| Unnecessary parallax scrolling or hovering ambient cards | Solid static layout with purposeful interactive transitions only | 9 |
| Centered, vertically stacked hero layouts (headline, copy, multiple CTAs, mockup below) | Asymmetric split layout or concise text placed above an expansive product interface | 6 |
| Crowded button clusters or avatar rows stacked beneath primary actions | A single primary action, plus one secondary if needed | 6 |
| Interchangeable hero titles (`Unleash your team's potential with AI`) | Specific description of what the product accomplishes and for whom | 4 |
| Feature grids composed of an emoji, bold generic title, and vague description per card | Focused selection of real capabilities explained with precise copy and uniform line icons | 4 |

## 8. Imagery

| Tell | Fix | Pass |
|---|---|---|
| Glossy 3D shapes, floating liquid chrome, neon spheres, or purple nebulae | Genuine product views or an authentic physical metaphor grounded in the product domain | 8 |
| Cliché artificial intelligence graphics (glowing cybernetic brains, circuit traces, androids, holograms) | Remove, or display the real work output generated by the tool | 8 |
| Image assets with misaligned background tones or sharp rectangular edges that clash with the page | Canvas-matched background color, or gentle radial edge masking | 8 |
| Simulated typography, fake controls, or mock brand marks rasterized directly into image assets | Genuine DOM elements rendered above a clean graphic | 8 |
| Decorative graphics inserted into every content section | Single focal visual applied where it delivers clear informational value, typically in hero | 8 |
| Inconsistent narrative details across composition (e.g. purchase order mismatch) | Unified narrative details throughout (e.g. purchase order `PO-2291` consistent everywhere) | 8 |

## 9. Motion and states

| Tell | Fix | Pass |
|---|---|---|
| Looping animations on passive elements (`animate-pulse`, `animate-ping`, breathing glow layers) | Static presentation unless indicating live asynchronous streaming | 9 |
| Staggered entrances flying into viewport from contradictory angles upon load | Restrained, unified fade-and-rise entrance for primary content | 9 |
| Ambient parallax shifts, perpetual floating loops, and scroll-linked spatial distortions | Stable static compositions | 9 |
| Exaggerated spring physics and bouncy overshoots on basic interface controls | Single cohesive ease-out curve | 9 |
| Sweeping `transition-all` definitions or aggressive `hover:scale` transforms on cards and controls | Immediate surface tint on hover, minute scale reduction (0.97–0.98) on active press; nothing moves more than a few px on hover | 9 |
| Animated layout dimensions such as `width`, `height`, `top`, or `left` | Hardware-accelerated transforms and opacity adjustments only | 9 |
| Missing interactive states on buttons, inputs, links | Explicit `hover`, `focus-visible`, `active`, and `disabled` styles | 7 |
| Missing state representations on data views | Explicit `empty`, `loading`, `error`, and `overflow` representations | 7 |
| Absence of accessibility accommodations for reduced motion settings | Complete suppression of spatial movement under `prefers-reduced-motion: reduce` | 9 |

## 10. Japanese UI

| Tell | Fix | Pass |
|---|---|---|
| Conversational or cheerleader greeting banners (「こんにちは、田中さん！」, 「さあ、始めよう！」) | Functional screen title or active reporting interval ("Week 44", 「第44週」) | 4 |
| Exclamation marks, paired exclamations, musical notes, or decorative emoji in interface strings (「！」, 「！！」, 「♪」) | Composed, factual terminology | 4 |
| Hype katakana jargon and formulaic buzzwords (シームレス, 革新的, 圧倒的, 爆速, 次世代, 〜を加速) | Clear, literal explanation of real utility | 4 |
| Latin-only typography cascades causing arbitrary Japanese system font fallbacks, or unstructured mixing of Gothic and Mincho | Intentional Japanese typeface family matched with Latin face and explicit OS fallbacks | 5 |
| Japanese paragraph copy constrained by Latin line-height ratios (1.2–1.4) | Comfortable vertical rhythm set at 1.7–1.9 line-height for body reading | 5 |
| Browser-synthesized artificial bold or slanted faux-italics applied to Japanese typefaces lacking native weight variants | Load the real weight from the family, or express emphasis with size or color; never let the browser synthesize bold or italic | 5 |
| Fragmented word wrapping or orphan punctuation marks abandoned on solitary trailing lines | Appropriate line breaking via `word-break: auto-phrase` where supported, `line-break: strict`, or manual phrase shaping | 5 |
| Negative letter-spacing or Latin-style wide uppercase tracking applied to full-width Japanese characters | Letter-spacing between 0 and 0.04em, reserving `palt` proportional metrics strictly for display titles | 5 |
| Disorganized mixing of full-width and half-width alphanumerics (`１２件` beside `12件`) | Standardized half-width numerals and Latin characters, maintaining unified spacing discipline | 5 |
| Typography below legibility threshold | Minimum 12px for Japanese typography (11px for Latin) | 5 |

## 11. After the passes: template drift

Run this group last. Nothing here is a tell on its own; each item is a default that fills the gap when a decision was skipped.

| Drift pattern | Correction | Pass |
|---|---|---|
| Hero visual consisting of a blank outline container or generic stock composition | Functional coded component preview or an evocative scene from the product's realm | 8 |
| A bakery-ordering app that ended up in the same cold grey-on-charcoal, system-font look as a server console | Tint the ramp toward the product's world and take the accent from it | 2 |
| Hero headline that could easily describe any competing service if the brand name were swapped | Copy built around specific nouns and tangible outcomes of this product | 4 |
| Repeating identical grid layouts, typography pairings, and color structures across unrelated client domains | Distinct direction shaped by the unique operational character of each product | 6 |
