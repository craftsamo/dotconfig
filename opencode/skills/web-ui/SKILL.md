---
name: web-ui
description: Use when implementing or modifying any web frontend UI — pages, components, layout, styling, CSS, themes, visual states, or when the user wants a specific look (UI 実装, フロントエンド, 画面, 見た目, デザイン, かっこいい, 可愛い, 綺麗, お洒落, 未来的, ダサい, スタイリング, コンポーネント, レイアウト, web design, aesthetic, look and feel, frontend, component, styling). Fixes an aesthetic direction before implementing (style catalog, reference extraction, or disposable style tiles), enforces verification against the real rendering with agent-browser (never claim UI work done from code alone), applies design principles (typography scale, spacing system, color restraint, hierarchy, states), and routes substantial UI work to the ui-review subagent for an unbiased multi-viewport screenshot critique. Do NOT use for TUI/CLI output or non-visual backend work.
---

<Goal>

Web UI work is only done when the real rendering has been seen and judged.
Code-only inspection is not verification: CSS interacts, defaults leak, and
layout breaks in ways invisible in source. Apply the design principles while
building, then close the loop against actual pixels with `agent-browser`.

</Goal>

<Scope>
<UseWhen>

- Implementing or modifying web pages, components, layout, or styling.
- The user says the UI looks wrong, ugly, broken, or inconsistent.
- Reviewing or verifying frontend changes that render in a browser.

</UseWhen>

<DoNotUseWhen>

- TUI/CLI output, emails, PDFs, native mobile screens (no browser rendering).
- Pure logic changes with no visual surface.

</DoNotUseWhen>
</Scope>

<AestheticDirection>

Craft correctness (the principles below) prevents amateur mistakes but does
not produce a look. A UI can pass every checklist item and still be generic —
the stock framework default with nothing memorable. Direction is chosen, not
emergent: do not start implementing visual work until one is fixed.

A fixed direction = a named style (from <DesignDirections> or custom) + its
mood adjectives + the concrete tokens derived from it (fonts, palette, radius,
depth, density, signature element). State it in one line before coding, e.g.
"Direction: Dark Tech — near-black, one cyan accent, mono data, 2px radius."

Resolve it by the first path that applies:

1. The project already has an established look or design system → consistency
   wins. Extend the existing direction; do not introduce a new one unless the
   user explicitly asked for a restyle.
2. The user names a style or mood (かっこいい, 可愛い, futuristic, editorial,
   like-a-terminal, ...) → map it to the closest <DesignDirections> entry,
   confirm the mapping in one line, derive tokens.
3. The user points at a reference site → open it with agent-browser,
   screenshot, Read the image, and extract its decisions (palette, type
   choices, radius, density, depth, signature elements) into tokens. A
   reference is worth more than adjectives — prefer this path when offered.
4. The user cannot verbalize it → build STYLE TILES: pick 2–3 plausible
   catalog directions and implement the SAME representative screen once per
   direction as a disposable, self-contained single-file HTML (inline CSS,
   realistic content, no project scaffolding) under the temp dir. Render each
   via `file://` with agent-browser, screenshot, present to the user, and let
   them point. Style tiles are throwaway — never wire them into the project.
   Do this only when direction is genuinely unresolved; do not ceremony-load
   small tweaks.

Once fixed, the direction is law: derive every token from it, and treat
deviations (an off-mood color, a friendly round button in a sharp technical
UI) as findings. Pass the direction to `ui-review` when delegating so it can
judge mood consistency. A mediocre direction executed consistently beats a
great direction executed inconsistently.

</AestheticDirection>

<DesignDirections>

Compressed catalog. Each entry: mood / type / color / shape / depth /
signature / kills-it (anti-patterns that break the mood) / fits. When the
project uses Tailwind + shadcn/ui, express tokens via CSS variables
(`--radius`, `--primary`, `--background`, font variables) so the direction
lands in one edit.

Dark Tech / Cyber — かっこいい・未来的 (precise, glowing, dense, cold)

- Type: geometric grotesk + monospace for data/labels; tabular numbers.
- Color: near-black bg (#0B0D10-ish), ONE neon accent (cyan/indigo/green),
  cool gray ramp. Accent = signal only.
- Shape: radius 0–4px; 1px hairline borders; visible grid lines.
- Depth: glow and layered translucency, not soft drop shadows.
- Signature: terminal/coordinate motifs, live tabular numbers, scanline or
  grid texture.
- Kills it: warm pastels, radius ≥ 8px, rounded friendly type, cream bg.
- Fits: dashboards, dev tools, web3, monitoring.

Clean SaaS / Trust — 誠実・整然 (calm, competent, unsurprising)

- Type: one humanist sans (Inter-class); strong weight contrast for headings.
- Color: white/near-white bg, one confident brand hue, warm-neutral grays.
- Shape: radius 6–10px, consistent; subtle borders or bg shifts to separate.
- Depth: one soft shadow step for cards, one for overlays. Nothing else.
- Signature: generous whitespace + one accent-colored primary CTA per screen.
- Kills it: more than two hues, dense borders everywhere, gradient buttons.
- Fits: B2B SaaS, admin consoles, docs. NOTE: this is the default-look zone —
  it MUST carry a deliberate brand hue and one signature choice, or it reads
  as unstyled framework output.

Playful Pop — 可愛い・楽しい (round, bouncy, sweet, bright)

- Type: rounded sans, chunky weights; oversized display numbers.
- Color: 2–3 saturated pastels + cream bg; colored (not gray) secondary text.
- Shape: radius 12–24px; pill buttons; organic blobs allowed.
- Depth: flat colors + hard offset shadows or thick outlines; sticker feel.
- Signature: mascot/emoji-grade icons, bounce on interaction, playful empty
  states.
- Kills it: pure black, hairline borders, sharp corners, corporate grays.
- Fits: consumer apps, education, community, kids.

Elegant Minimal — 綺麗・上品 (restrained, airy, precise, quiet)

- Type: one refined sans, light-to-regular weights; larger sizes instead of
  bold; wide letter-spacing on small caps labels.
- Color: off-white bg, near-black text, ONE muted accent (sage/navy/plum);
  hierarchy carried almost entirely by grays and spacing.
- Shape: radius 0–6px; separation by whitespace, almost no borders.
- Depth: essentially flat; at most one whisper-level shadow.
- Signature: extreme whitespace discipline; thin 1px rules used sparingly.
- Kills it: loud accent colors, heavy bold everywhere, tight packing.
- Fits: portfolios, galleries, premium consumer, settings-heavy UIs.

Editorial — お洒落・雑誌的 (curated, typographic, confident)

- Type: serif display for headlines + neutral sans for UI; dramatic size
  jumps (16 → 40+); tight leading on display.
- Color: paper-white or warm-cream bg, ink-black text, one editorial accent
  (red/cobalt) used like a highlighter.
- Shape: sharp corners; strong grid with intentional asymmetry; big margins.
- Depth: flat; hierarchy from type scale, not elevation.
- Signature: oversized headlines, pull-quotes, numbered sections, ALL-CAPS
  micro-labels.
- Kills it: bubbly rounded cards, glassmorphism, centered-everything.
- Fits: content sites, landing pages, blogs, media.

Luxury — 高級・重厚 (dark, slow, gold-accented, spacious)

- Type: high-contrast serif (Didone-class) for display; restrained sans body.
- Color: deep charcoal/ink bg OR ivory bg; metallic accent (gold/champagne)
  in tiny doses; desaturated everything else.
- Shape: sharp or barely-rounded; thin 1px gold rules as dividers.
- Depth: flat with vignette-like large imagery; no cartoon shadows.
- Signature: small centered serif wordmark, wide letter-spaced uppercase,
  slow fades (300–500ms).
- Kills it: bright saturated colors, chunky buttons, busy layouts, emoji.
- Fits: brand sites, e-commerce for premium goods, hospitality.

Brutalist — 尖った・生 (raw, loud, honest, anti-polish)

- Type: default-stack or mono pushed to extreme sizes; no subtlety.
- Color: white/black base + 1–2 shocking accents (electric blue, acid
  yellow); system-default link blue is allowed as a statement.
- Shape: zero radius; thick 2–4px borders; visible structure, no decoration.
- Depth: none, or hard non-blurred offset shadows.
- Signature: exposed grid, underlined links, marquee-grade oversized text.
- Kills it: soft shadows, gradients, pastel harmony, polish of any kind.
- Fits: portfolios, event sites, dev culture, statements. Rarely right for
  products with forms.

</DesignDirections>

<RenderingLoop>

Never claim a UI change is complete without having looked at a screenshot of
the real rendering. The loop:

1. Resolve the app's real entry URL — never assume `localhost:3000`. In
   order: what the user told you; the dev server's startup output; project
   docs (README, AGENTS.md); config (`package.json` scripts, docker-compose
   port mappings, proxy configs). As a last resort, extract ONLY url/port
   keys from `.env` files with a targeted grep, e.g.
   `grep -hE '^(PORT|HOST|BASE_URL|APP_URL|.*_URL)=' .env* 2>/dev/null` —
   never read a whole `.env` into context; it may hold secrets. When a reverse
   proxy fronts the app (e.g. nginx on `http://localhost/` routing to
   internal services), verify through the PROXY url — hitting an internal
   port bypasses the routing users actually go through. Confirm the URL
   responds before capturing; if it does not, start the dev server the way
   the project prescribes.
2. Read the command reference once per session:
   `agent-browser skills get core --full` (ships with the CLI,
   version-matched — prefer it over guessing flags).
3. Render and capture:

   ```bash
   agent-browser open <app-url>/path
   agent-browser wait --load networkidle
   agent-browser set viewport 1440 900          # desktop
   agent-browser screenshot /tmp/ui-desktop.png
   agent-browser set viewport 375 812           # mobile
   agent-browser screenshot /tmp/ui-mobile.png
   agent-browser errors                         # page errors
   agent-browser console                        # console noise
   ```

4. Read the screenshot image(s) with the Read tool and judge them against
   <DesignChecklist> — actually look; do not assume.
5. Fix, re-screenshot, re-judge. Repeat until the checklist passes.
6. Interactive states matter: hover/focus/empty/loading/error states need to
   be driven (click, fill, route mocking) and captured too when they changed.

Session hygiene: when a `ui-review` subagent may run concurrently, keep the
primary's browser isolated with `--session main` (the subagent uses its own
session).

</RenderingLoop>

<Delegation>

- Small change (one component, a copy/spacing tweak): verify inline — one or
  two screenshots read directly in the primary session.
- Substantial UI work (new page/feature, restyle, "design is bad" complaints):
  after your own loop passes, delegate an unbiased critique to the `ui-review`
  subagent via the `task` tool. Give it: the URL(s), what changed, the fixed
  aesthetic direction (name + mood adjectives), and any states to exercise.
  It returns a severity-ranked critique with measurements
  and screenshot paths — apply fixes, then re-invoke it with the same
  `task_id` to confirm.
- Screenshots are token-heavy. Keep bulk multi-viewport/multi-state capture in
  `ui-review`; only Read into the primary the images you need to fix against.
- Behavioral testing (would a hostile, reluctant, or novice user survive this
  flow?) is not this skill's job: once the render loop passes, load
  `ux-persona-testing` and run personas through the `ux-persona` subagent.

</Delegation>

<DesignPrinciples>

Defaults produce bad design; constraints produce good design. When the project
has a design system or style guide, it wins — read it first. Otherwise:

Typography

- One font family (two max). Define a scale and stick to it, e.g.
  12 / 14 / 16 / 20 / 24 / 32 / 48px — never invent in-between sizes ad hoc.
- Body text 16px, line-height ~1.5. Headings tighter (1.1–1.3) and clearly
  distinct from body — differentiate with size AND weight, not size alone.
- Line length 45–75 characters. Constrain text columns (`max-width: 65ch`).
- Prefer weight/color changes over more sizes: secondary text is a muted
  color, not a smaller font.

Spacing and layout

- All spacing from one scale: 4 / 8 / 12 / 16 / 24 / 32 / 48 / 64px.
  Arbitrary values (13px, 22px) are a smell.
- Related items sit closer than unrelated items (proximity = grouping). A
  label belongs to its field, not floating between two.
- Start with too much whitespace and remove; cramped is the default failure.
- Align to something: pick a container width, a grid, consistent gutters.
  Mixed alignment (some centered, some left) reads as broken.

Color

- One primary/brand color, a neutral gray ramp (5–9 steps), plus semantic
  colors (success/warning/danger). Nothing else without a reason.
- Never pure black on pure white; use near-black on near-white.
- Grays carry the hierarchy: primary text darkest, secondary muted, disabled
  faint. Saturated color is for action and emphasis only.
- Contrast: body text ≥ 4.5:1, large text ≥ 3:1 (WCAG AA). Check, don't
  eyeball.

Hierarchy

- Every screen has ONE primary action, visually dominant. Secondary actions
  are outline/ghost; destructive actions are quiet until confirmed.
- If everything is bold, nothing is. De-emphasize the rest instead of
  emphasizing the thing.
- Use size/weight/color to encode importance before adding boxes and borders.
  Prefer whitespace or background shifts over border lines to separate.

States and depth

- Every interactive element has visible hover, focus (keyboard!), active, and
  disabled states. Focus must never be `outline: none` without a replacement.
- Every data view has empty, loading, error, and overflow (long text, many
  items) states designed — the happy path is the easy 20%.
- Shadows: small and subtle for slight elevation (cards), larger and softer
  for overlays (modals). One shadow scale, not per-component improvisation.

</DesignPrinciples>

<DesignChecklist>

Judge each screenshot against these; a miss is a finding, not a vibe:

- [ ] Spacing values come from the scale; gaps group related things.
- [ ] Type scale respected; clear heading/body distinction; line length sane.
- [ ] Alignment consistent; nothing visually drifting or off-grid.
- [ ] One clear primary action; hierarchy readable at squint distance.
- [ ] Color count restrained; grays doing the hierarchy work; AA contrast.
- [ ] No layout breakage at 1440px and 375px (overflow, wrapping, squash).
- [ ] Interactive/empty/loading/error states present where relevant.
- [ ] Mood consistent with the fixed direction; no off-direction elements.
- [ ] Not generic: at least one deliberate signature choice — this would not
      be mistaken for an unstyled framework default.
- [ ] `agent-browser errors` clean; console free of new errors.

</DesignChecklist>

<AntiPatterns>

- Declaring UI work done after only reading/writing code — the whole point of
  this skill is that rendering is the ground truth.
- Starting visual implementation with no fixed direction, or "styling" by
  accepting framework defaults — passing the checklist while looking like
  every other stock app is a failure of this skill.
- Mixing directions mid-project (a playful button in a luxury layout) or
  drifting from the agreed tokens because a component "looked better" that
  way.
- Screenshotting but not Reading the image, or Reading it and not comparing
  against the checklist.
- Verifying only the desktop viewport, or only the happy path.
- Inventing one-off font sizes, spacing values, or colors mid-implementation.
- Piling every screenshot into the primary context when `ui-review` should
  absorb the bulk capture.

</AntiPatterns>
