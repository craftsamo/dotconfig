# Tokens

Starting values for every design pass. These tokens represent baseline craft
recommendations rather than an inflexible house style; a project's established
design system takes precedence, and the active design direction may calibrate them.

## Spacing

- Base scale: 4, 8, 12, 16, 20, 24, 32, 40, 48, 64, 80, 96, 128px. Any multiple of 4 is fine even when not in the scale list (e.g. 28, 104); do not over-snap.
- Internal control padding: 4–12px.
- Gap between closely related elements (e.g. list rows): 2–8px.
- Separation between groups: 12–24px.
- Section spacing in applications: 32–64px; marketing landing sections: 80–128px.
- Interactive row heights: 32px (compact), 36px (default), rows 40–44 on touch, with the hit area extended to 44×44.
- Touch target minimum: at least 44×44px on touch viewports (WCAG 2.2 absolute minimum is 24×24px).
- Hero vertical offset: 96–128px from navigation to headline on desktop; 48–64px on mobile (stacked hero configurations only).

## App layout

- Sidebar width: 240–280px; main content area remains fluid with 24–32px page padding, max-width bounded at ~1440–1600px.
- Application top bar / primary header: 56–64px height.
- Navigation item rows: 32–36px height with 2–4px vertical gap; category header positioned ~24px above and 8px below.
- Sibling metric cards across a single row must share identical height; desktop rows usually hold three or four of them.
- Primary analytics chart: occupies at least two-thirds of content column width at 280–360px height. Adjacent data blocks should present alternative formats (compact table or ranked list), never a competing chart of identical dimensions.

## Neutral ramp

Generate surfaces and text from a unified OKLCH ramp keyed to the product's world hue.
Using a shared hue `H` and subtle chroma `C`, define lightness levels across every role.

- Chroma boundaries: 0–0.006 for application dashboards (maintains perceived neutrality); up to ~0.012 for marketing landing surfaces; up to ~0.02 for text elements. Values above 0.012 make surface backgrounds read as deliberate color washes.
- Baseline world hues:
  - Graphite: `C = 0`, any `H` (neutral, austere).
  - Warm: `H ≈ 70–85` (paper, timber, culinary, artisanal, human).
  - Ink: `H ≈ 255–265` (night, celestial, aquatic, technical precision).
  - Natural: `H ≈ 130–150` (foliage, organic environments).
- Dark theme lightness values:
  - Deepest surface (sidebar / canvas): `0.155`
  - Page backdrop: `0.180`
  - Elevated card: `0.205`
  - Raised element (active list row, input fill): `0.245`
  - Primary text: `0.945`
  - Secondary text: `0.735`
  - Muted text and iconography: `0.625`
- Light theme lightness values:
  - Page canvas: `0.985`
  - Card surface: `1.0` (or `0.995` with tint)
  - Raised element: `0.965`
  - Primary text: `0.205`
  - Secondary text: `0.435`
  - Muted text: `0.540` (note: `0.555` falls short of the required 4.5:1 ratio against raised surfaces)
- Hairline borders: primary text tone rendered at 8% alpha (acceptable range 6–10%).
- Typography rules: muted text is reserved strictly for metadata and captions, requiring at least 4.5:1 contrast against its underlying surface. Body content uses primary or secondary tokens. Never pair pure black `#000000` with pure white `#ffffff`.
- CSS variable structure:

```css
:root {
  --hue: 260;
  --chroma: 0.005;

  --surface-deep: oklch(0.155 var(--chroma) var(--hue));
  --surface-page: oklch(0.180 var(--chroma) var(--hue));
  --surface-card: oklch(0.205 var(--chroma) var(--hue));
  --surface-raised: oklch(0.245 var(--chroma) var(--hue));

  --text-primary: oklch(0.945 var(--chroma) var(--hue));
  --text-secondary: oklch(0.735 var(--chroma) var(--hue));
  --text-muted: oklch(0.625 var(--chroma) var(--hue));

  --border-hairline: oklch(from var(--text-primary) l c h / 8%);
}
```

- Semantic status tokens in OKLCH:
  - Positive / success: `oklch(0.75 0.14 155)` on dark themes; `oklch(0.55 0.15 150)` on light themes.
  - Negative / critical: `oklch(0.65 0.19 25)` on dark themes; `oklch(0.56 0.20 27)` on light themes.
- Contrast validation: test computed sRGB output against WCAG AA standards. OKLCH perceptual lightness values do not directly guarantee WCAG relative luminance compliance.

## Accent

- Preserve authentic brand identity. A multi-hue gradient glow is an anti-pattern rather than brand color, unless explicitly mandated.
- When selecting an accent without an established identity, derive it from the product's world:
  - Warm worlds: amber `oklch(0.80 0.15 75)`, coral `oklch(0.72 0.15 35)`, ember orange `oklch(0.70 0.17 45)`.
  - Cool worlds: cobalt `oklch(0.55 0.18 260)`, teal `oklch(0.68 0.11 190)`, sky `oklch(0.72 0.12 235)`.
  - Natural worlds: moss `oklch(0.62 0.10 135)`, sage `oklch(0.72 0.06 150)`.
  - Avoid purple-to-blue spectrums unless established by actual brand equity.
- Contrast requirement: text rendered over an accent background must meet or exceed 4.5:1; adjust lightness or switch to dark text. When the accent itself colors text or strokes on a pale background, lower its lightness until that pair clears 4.5:1 as well. Verify computed contrast after choosing.
- Screen surface coverage: limit accent usage to a few percent of the viewport (primary call to action, active selection state, single key metric). Chart accent defaults to the current period unless the page is about something else.

## Buttons

- Sizing: hero actions 44–48px height; navigation actions 32–36px height; horizontal padding 16–20px.
- Primary buttons:
  - Dark themes: off-white fill drawn from the neutral ramp with dark text, or solid accent color.
  - Light themes: primary text color as solid fill with white text, or solid accent color.
- Secondary buttons: raised surface fill paired with a hairline border and primary text color.
- Subtle depth: dark theme buttons may incorporate a delicate 1px inner top highlight (`box-shadow: inset 0 1px 0 rgb(255 255 255 / 10%)`) to provide definition without glow.
- Interaction states: all interactive elements must define `hover`, `focus-visible`, `active`, and `disabled` styles. Data displays must provide `empty`, `loading`, `error`, and `overflow` representations.

## Type families

| Character | Latin UI family | Partner | Japanese family |
|---|---|---|---|
| Engineered, exact, steady | Geist, IBM Plex Sans, Inter | Geist Mono or JetBrains Mono for figures and meta | IBM Plex Sans JP, Noto Sans JP |
| Warm, human | Figtree, Nunito Sans, Instrument Sans | Fraunces for hero headlines only | Zen Kaku Gothic New, M PLUS 2 |
| Editorial, literary | Inter or Instrument Sans for UI | Newsreader or Source Serif 4 for headlines | Shippori Mincho or Noto Serif JP for headlines, a Gothic for UI |
| Playful, bold | Bricolage Grotesque, Space Grotesk, Outfit | a mono for small labels | M PLUS Rounded 1c |
| Public, high-legibility (government, health, finance forms) | Public Sans, Atkinson Hyperlegible | none | BIZ UDPGothic |

All listed typefaces are freely available. A partner font may come from any row of the family table. Expressive display serifs are restricted to major hero titles, never small UI labels or button text. Standard weights are 400 and 500; 600 only for rare emphasis and the wordmark; moods may override within their stated bounds. Minimum legibility size is 11px for Latin, 12px for Japanese.

## Type scale

| Role | Size (px) | Line height | Weight | Note |
|---|---|---|---|---|
| Small labels, metadata, counts | 12 | 16px | 400 | Good place for the mono partner |
| Secondary copy, captions | 13–14 | 20px | 400 | Secondary text role |
| Body copy, navigation links | 14–15 | 20–22px | 400–500 | Content-heavy reading: 16px at ~1.5, length 45–75ch |
| Brand logo wordmark | 16–18 | 1.0 | 500–600 | Main interface family or flat mark |
| Hero subhead | 18–20 | 28–30px | 400 | Secondary color, max ~36rem wide |
| Metric card figures | 28–32 | 1.0 | 500 | Tabular numbers |
| Page titles | 28–36 | 1.15 | 400–500 | Standard page heading |
| Hero headlines | 56–72 (desktop) / 36–44 (mobile) | 1.02–1.08 | 400–500 | Display scale, tighter tracking |

- Letter-spacing (tracking):
  - 0 for sizes under 16px (subtle `0.01em` acceptable on small muted metadata).
  - Scale down to `-0.02em` from 40px upwards.
  - Scale down to `-0.03em` from 56px upwards.

## Japanese text

- Typeface selection:
  - Interface Gothic: IBM Plex Sans JP, Noto Sans JP, Zen Kaku Gothic New, M PLUS 2, M PLUS Rounded 1c, BIZ UDPGothic (high legibility).
  - Editorial Mincho (headlines only): Shippori Mincho, Noto Serif JP.
  - Font stack ordering: specify Latin fonts ahead of Japanese fonts so western characters inherit Latin styling before falling back to Japanese glyphs, followed by operating system defaults (`"Hiragino Sans", "Yu Gothic UI", sans-serif`).
- Sizing: body text 14–16px (never below 12px to preserve complex kanji legibility). Headlines scale one step smaller than western equivalents due to higher optical visual density (hero titles 40–56px on desktop, 28–36px on mobile).
- Line height: paragraph copy 1.7–1.9; concise UI labels 1.4–1.5; major titles 1.3–1.4.
- Tracking: body text 0–0.04em; headings may apply `font-feature-settings: "palt"` with 0–0.02em letter spacing; never apply negative tracking to Japanese body text.
- Font weights: standard 400 and 500 weights (600 only when natively supported by font files; avoid synthetic browser bolding). Never use synthetic italics.
- Measure: 30–40 full-width characters per line for sustained reading.
- Word wrap and punctuation: apply `line-break: strict` and `word-break: auto-phrase` where supported; prevent solitary orphan characters on closing lines.
- Alphanumerics: use standard half-width characters for numerals and Latin words; adopt a consistent spacing policy between Japanese text and Latin characters per project conventions.

## Radius

| Component | Radius |
|---|---|
| Keycaps, status tags, compact buttons | 4–6px |
| Table rows, form inputs, standard buttons | 8–10px |
| Content cards | 12–16px |
| Modals, major panels, floating windows | 14–20px |

- Nested corner geometry: `inner_radius = outer_radius - padding` (never below the mood's stated minimum (default 4)). Example: a card with 16px outer radius and 8px internal padding takes an 8px inner element radius.

## Icons

- Use Lucide icons or the existing project icon library.
- Fixed sizing: 16px or 18px with 1.5px stroke width.
- Coloring: inherit from current text role token (secondary or muted).
- Spacing: consistent 8–10px horizontal gap between icon and adjoining label.

## Depth

- Dark themes: establish depth via surface lightness increments and hairline borders; active items or buttons may include a 1px top highlight (`inset 0 1px 0 rgb(255 255 255 / 10%)`). A floating window or modal over a backdrop may keep a soft neutral shadow (`0 12px 32px rgb(0 0 0 / 25%)`).
- Light themes: restrained two-level elevation scale:
  - Resting cards: `0 1px 2px rgb(0 0 0 / 6%)`.
  - Floating overlays / modals: `0 12px 32px rgb(0 0 0 / 8%)`.

## Motion

- Standard easing: single decelerated curve across all transitions, such as `cubic-bezier(0.22, 1, 0.36, 1)` (ease-out-quint) or Material 3 emphasized deceleration `cubic-bezier(0.05, 0.7, 0.1, 1)`. Maintain one curve across the project.
- Duration tiers:
  - Hover states, button presses, micro-toggles: 120–180ms.
  - Dropdown menus, popovers, tooltips: 160–220ms.
  - Page entrances, modal sheets: 300–500ms.
  - Stagger delay between sequential items: 40–60ms (limit stagger to at most 6 elements).
- Transform ranges: initial entrance translation 6–12px vertical rise; button press active scale 0.97–0.98.
- Animate only paint properties (`color`, `background-color`, `border-color`) and composite properties (`opacity`, `transform`). Never animate layout dimensions (`width`, `height`, `top`, `left`, `margin`), and avoid animating large blur as it is an expensive paint/filter effect.
- Accessibility: enforce `@media (prefers-reduced-motion: reduce)` by removing spatial movement and transforms, restricting feedback to instantaneous transitions or gentle opacity shifts.
