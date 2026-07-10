---
name: web-ui
description: Use when implementing or modifying any web frontend UI — pages, components, layout, styling, CSS, themes, visual states (UI 実装, フロントエンド, 画面, 見た目, デザイン, スタイリング, コンポーネント, レイアウト, web design, frontend, component, styling). Enforces verification against the real rendering with agent-browser (never claim UI work done from code alone), applies design principles (typography scale, spacing system, color restraint, hierarchy, states), and routes substantial UI work to the ui-review subagent for an unbiased multi-viewport screenshot critique. Do NOT use for TUI/CLI output or non-visual backend work.
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
  subagent via the `task` tool. Give it: the URL(s), what changed, and any
  states to exercise. It returns a severity-ranked critique with measurements
  and screenshot paths — apply fixes, then re-invoke it with the same
  `task_id` to confirm.
- Screenshots are token-heavy. Keep bulk multi-viewport/multi-state capture in
  `ui-review`; only Read into the primary the images you need to fix against.

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
- [ ] `agent-browser errors` clean; console free of new errors.

</DesignChecklist>

<AntiPatterns>

- Declaring UI work done after only reading/writing code — the whole point of
  this skill is that rendering is the ground truth.
- Screenshotting but not Reading the image, or Reading it and not comparing
  against the checklist.
- Verifying only the desktop viewport, or only the happy path.
- Inventing one-off font sizes, spacing values, or colors mid-implementation.
- Piling every screenshot into the primary context when `ui-review` should
  absorb the bulk capture.

</AntiPatterns>
