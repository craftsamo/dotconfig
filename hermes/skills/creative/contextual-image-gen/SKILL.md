---
name: contextual-image-gen
description: >-
  Produce images that actually fit where they will be used. BEFORE generating,
  discover the destination's constraints (display size, aspect ratios, crop
  behavior, file format/size, storage path) and the brand/design system (colors,
  type, logo, existing assets), then pick the right strategy — AI-generate,
  derive-from-logo (icons), or template+text (OG/cards) — generate, review, tune,
  and post-process to the exact target. Triggers: generate/create image, cover
  image, hero image, OG image, Twitter/social card, favicon, app icon, apple-icon,
  illustration, thumbnail, ブランド画像, カバー画像, アイキャッチ, OG画像, ファビコン.
version: 0.1.0
author: Hermes Agent
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [image-generation, branding, design-system, icons, og-image, creative]
    category: creative
---

# Contextual Image Generation

Make an image **fit its destination and brand** instead of prompting blind. The
value of this skill is the work done *before* `image_generate`: figure out where
the image lives, what shape/size/format it must be, and what the brand looks
like — then choose the right production strategy.

## When to Use

- The user asks to create/generate a cover, hero, OG/social card, favicon, app
  icon, illustration, thumbnail, or any branded image — especially "for our app /
  site / repo / deck".
- Use it whenever the image must match an existing product's look or slot into a
  specific place with fixed dimensions.

**Not** for: editing an existing photo's content, pure cropping of a user-supplied
file (just run a script), or vision/analysis of an image (that's `vision_analyze`).

## Core principle: gather preconditions first

Never jump straight to a prompt. Two homework passes drive everything downstream:

1. **Destination** — where will it render? Exact pixel size(s) and aspect
   ratio(s), crop behavior (`object-cover`?), file format + max size, and the
   storage/upload path.
2. **Design system** — brand colors (hex/OKLCH/tokens), typography, logo and its
   style (flat line-art? gradient?), and any existing image assets to match.

If you can't find these (no codebase, no brand given), **ask the user** rather
than guessing. See `references/discovery.md`.

## Workflow

1. **Identify the asset type** → load `references/asset-types.md` and route. If the
   destination is unclear, ask: "Where will this be used (web app, social, slides),
   and what exact size?"
2. **Discover preconditions** (`references/discovery.md`): codebase grep / Figma /
   stated specs → destination constraints + design tokens.
3. **Pick the strategy** for the asset type:
   | Strategy | Asset types | How |
   |---|---|---|
   | **generate** | cover / hero / illustration / social background | `image_generate` → `references/ai-imagery.md` |
   | **derive-from-logo** | favicon / apple-icon / PWA / maskable | render the logo SVG → `references/icons.md` (do **not** AI-generate) |
   | **template + text** | OG / Twitter / title cards | background (generated or solid) + composited text → `references/text-cards.md` |
4. **Confirm tradeoffs** with the user before producing a set (see below).
5. **Produce → review → tune → iterate** (dials below). Write the final prompt /
   command to a file first so it is reproducible.
6. **Post-process** to the exact target (`scripts/img-postprocess.sh`): correct
   dimensions, format, and ≤ size cap. Then place/upload per the discovered
   convention (don't commit/upload without the user's go-ahead).

## Tradeoffs to confirm (ask before batch work)

These materially change output, so confirm up front (mirror the user's language):

- **Text in the image?** Usually **no** — UI/platform shows the title separately,
  AI text renders unreliably, and it breaks under cropping. Prefer text via
  `template + text` compositing when a title is truly needed.
- **Style direction** — flat line-art / solid two-tone / gradient+icon / isometric.
- **Brand logos/marks** — abstract them out (safest) vs. approximate. AI renders
  real logos badly; for exact marks use `derive-from-logo` or composite the SVG.
- **Avatars/people** — usually none; a human↔AI chat reads better as left/right
  bubbles by color, not two person avatars.

## `image_generate` essentials (read before generating)

- **Prompt-only**: takes `prompt` + `aspect_ratio` (`landscape` | `portrait` |
  `square`). No reference-image input — encode style/consistency as **text**.
- **Aspect mapping**: 16:9 → `landscape`, 9:16 → `portrait`, 1:1 → `square`.
  Other ratios → nearest, then crop/pad to the exact target in post-process.
- **Return value**: a JSON result whose `image` is **either a URL or a local
  absolute path** (this machine's chain saves locally, e.g. xai/codex →
  `$HERMES_HOME/cache/images/...`). Always normalize via `scripts/img-postprocess.sh`.
- **Backend is not agent-selectable**: it uses the user's configured provider
  (here: the `img-xai-codex-fal` fallback chain). **Do not** write model names in
  the prompt expecting routing. For prompt-adherence-heavy brand work, gpt-image-2
  follows detailed prompts best — suggest the user switch
  `image_gen.provider: img-codex-xai` for cover/brand runs if results drift.
- **Reproducibility**: save each final prompt to `prompts/NN-<slug>.md` before
  calling `image_generate`, so you can regenerate or switch backends later.

## Tuning dials (iterate, don't restart)

- Washed out at thumbnail size → bolder strokes + **solid fills**, higher contrast.
- Too busy / clipped on crop → fewer, larger elements; composition ~65-70% of
  frame with 15-18% margin; keep the subject center-safe for 2:1 / 21:9.
- Background too strong/weak → adjust the gradient stops.
- Weird emblem/spinner → "keep it simple: no radial/sunburst shapes".
- Heavy 3D shadows → "flatter, lighter shadows".

## Pitfalls (hard-won)

- Thin, pale line-art disappears as a small thumbnail and on dark UIs.
- AI-approximated logos/sunbursts look cheap and vary across a set → derive or
  composite instead.
- Oversized elements touching the edges get cropped at 2:1 / 21:9.
- Two person avatars imply human↔human; use bubbles by side+color for human↔AI.
- AI text is unreliable — keep words out of generated images.

## Files

- `references/asset-types.md` — router: type → size → strategy → reference.
- `references/discovery.md` — find destination specs + design tokens.
- `references/ai-imagery.md` — covers/heroes/illustrations via `image_generate`.
- `references/social-specs.md` — platform dimension tables (OG/X/IG/YT/…).
- `references/icons.md` — favicon / apple-icon / PWA from the logo SVG.
- `references/text-cards.md` — OG/Twitter background + composited title.
- `references/docs.md` — slides / figures / print.
- `scripts/img-postprocess.sh` — normalize → resize/crop → format → size cap.
- `scripts/logo-to-icons.sh` — logo SVG → favicon `.ico` + PNG icon set.
- `scripts/text-card.sh` — background + brand title → OG/Twitter card.

Run scripts via `${HERMES_SKILL_DIR}/scripts/<name>` (pass `--help` for usage).
Tooling (ImageMagick, cwebp, librsvg, Geist font) is declared in the repo Brewfile.
