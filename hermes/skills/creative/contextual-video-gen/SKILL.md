---
name: contextual-video-gen
description: >-
  Produce short generated videos that actually fit where they'll play. BEFORE
  generating, discover the destination's constraints (duration, aspect ratio,
  resolution, container/codec, file-size cap, autoplay/mute/loop behaviour) and
  the source/brand (a still to animate, reference frames, palette, motion
  language), then pick the right strategy — text-to-video, image-to-video
  (animate a brand still), or reference-guided — generate, review, tune, and
  post-process with ffmpeg to the exact target. Generation is slow and metered,
  so confirm duration/count before producing a set. Triggers: generate/create
  video, hero video, looping background, product demo, explainer clip, social
  reel, animate this image, image-to-video, 動画生成, 動画作成, ループ動画,
  デモ動画, リール, 静止画を動かす, アイキャッチ動画.
version: 0.1.0
author: Hermes Agent
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [video-generation, motion, image-to-video, branding, creative]
    category: creative
---

# Contextual Video Generation

Make a generated clip **fit its destination and brand** instead of prompting
blind. The value of this skill is the work done *before* `video_generate`:
figure out where the video plays, how long / what shape / what codec it must be,
and whether you should animate an existing brand still — then choose the right
strategy. Video is **slow and metered** (tens of seconds to minutes per clip,
priced per second/clip), so the pre-work pays for itself.

This is the motion sibling of `contextual-image-gen`; the philosophy is the same.

## When to Use

- The user asks to create/generate a hero loop, looping background, product
  demo, explainer clip, social reel, teaser, or any short branded video —
  especially "for our app / site / landing page / launch".
- Use it whenever the clip must match an existing product's look or slot into a
  specific place with fixed duration/aspect/codec.

**Not** for: editing/trimming a user-supplied video (just run
`scripts/video-postprocess.sh`), video *understanding* (that's `video_analyze`),
HTML/canvas-composited motion graphics, title cards, captions, or shader
transitions (that's the bundled `hyperframes` skill), or a full multi-agent
production pipeline (bundled `kanban-video-orchestrator`).

## Core principle: gather preconditions first

Never jump straight to a prompt. Two homework passes drive everything downstream:

1. **Destination** — where will it play? Exact **duration**, **aspect ratio**,
   **resolution**, **container/codec** (mp4/H.264, webm/VP9), **max file size**,
   and the **playback contract** (autoplay needs muted; loop = seamless;
   poster/preview frame; does it need an `<video>` `poster`?). See
   `references/delivery-types.md` and `references/discovery.md`.
2. **Source & motion** — is there a **brand still to animate** (image-to-video
   keeps brand identity far better than text-to-video)? Reference frames?
   Palette, subject, and the **motion language** (locked vs moving camera, how
   much subject motion, pacing). See `references/image-to-video.md`.

If you can't find these (no codebase, no brand, no source still), **ask the
user** rather than guessing — a wrong 8-second 1080p clip is expensive to redo.

## Workflow

1. **Identify the delivery type** → load `references/delivery-types.md` and
   route. If the destination is unclear, ask: "Where will this play (web hero,
   social reel, in-app demo), how long, and what exact size?"
2. **Discover preconditions** (`references/discovery.md`): codebase grep / stated
   specs → destination constraints + brand/source assets.
3. **Pick the strategy**:
   | Strategy | When | How |
   |---|---|---|
   | **image-to-video** | a brand still / first frame exists; brand consistency matters | `video_generate(prompt=…, image_url=…)` → `references/image-to-video.md` |
   | **text-to-video** | no source; concept/atmosphere clip | `video_generate(prompt=…)` → `references/text-to-video.md` |
   | **reference-guided** | identity must persist across shots (xAI: up to 7 refs) | `reference_image_urls=[…]` → `references/image-to-video.md` |
4. **Confirm tradeoffs** with the user before producing a set (cost × duration ×
   count; audio yes/no; text-in-video = no). See below.
5. **Produce → review → tune → iterate** (dials below). Write the final prompt +
   params to `prompts/NN-<slug>.md` first so it is reproducible and cheap to
   re-run on another backend.
6. **Post-process** to the exact target (`scripts/video-postprocess.sh`): trim,
   correct aspect/resolution, transcode, mute/strip audio, cap size. For loops
   use `scripts/make-loop.sh`; for an `<video poster>` use
   `scripts/poster-frame.sh`. Then place/upload per the discovered convention
   (don't commit/upload without the user's go-ahead).

## Tradeoffs to confirm (ask before generating)

Video is expensive and slow — confirm up front (mirror the user's language):

- **Duration & count** — each second costs money and time. Generate **one**
  short proof first (≤ the target, often 4–6s), review, then scale. Don't batch
  a set of 8s 1080p clips on spec.
- **Audio?** Usually **no** for web heroes/backgrounds (they autoplay muted) —
  pick a quiet backend/model and strip audio in post. For social, native audio
  (Veo 3.1 / Seedance / Kling / LTX) may be wanted.
- **Text in the video?** Almost always **no** — generated on-screen text warps
  and flickers. Overlay titles/captions in post or via the `hyperframes` skill.
- **People / faces** — motion artifacts on faces/hands are common; prefer
  image-to-video from a fixed still, shorter shots, and locked framing.

## `video_generate` essentials (read before generating)

- **One tool, two modalities**: pass `image_url` to **animate a still**
  (image-to-video); omit it for **text-to-video**. The active backend
  auto-routes to the right endpoint.
- **Backend is not agent-selectable**: it uses the user's configured chain
  (here: `video_gen.provider: vid-xai-fal` — **Grok Imagine → FAL.ai** with
  failover; `vid-fal-xai` is the reverse). **Do not hardcode `model=`** — a name
  valid for one backend is invalid for the other and breaks failover. To change
  the model family, switch `video_gen.provider` or pin a backend (see
  `references/backends.md`).
- **Capabilities differ by backend** — aspect ratios, resolutions, max duration,
  audio, and reference-image support are **not** uniform. The tool description is
  rebuilt at session start to reflect the *active* backend; still check
  `references/backends.md` before promising a 4K/audio/portrait clip.
- **Params you control per call**: `prompt`, `image_url`, `aspect_ratio`,
  `duration` (seconds), `resolution`, `negative_prompt` (FAL only), `audio`
  (FAL only), `reference_image_urls` (xAI), `seed` (reproducibility).
- **Return value**: a result whose `video` is **either a URL or a local absolute
  path**. **Hosted URLs expire (hours/days) — save locally immediately** via
  `scripts/video-postprocess.sh` (it accepts a URL or a path).
- **Reproducibility**: save each final prompt + params to `prompts/NN-<slug>.md`
  before calling, so you can regenerate or switch backends later.

## Tuning dials (iterate, don't restart)

- Too much warping/morphing → shorter duration, lower motion, image-to-video
  from a clean still, locked camera.
- Dead/static → name an explicit camera move (slow push-in, pan) **or** subject
  motion; don't ask for both at once.
- Off-brand drift (text-to-video) → switch to image-to-video from a brand frame,
  or add `reference_image_urls` (xAI).
- Flicker on fine detail/logos → keep logos out of the generated frame; composite
  them in post.
- Wrong vibe/pacing → adjust shot length and one motion verb; keep prompts
  concrete and short.

## Pitfalls (hard-won)

- Generated on-screen **text** is unreliable — keep words out, overlay in post.
- **Hosted URLs expire** — always localize the result before doing anything else.
- **Cost/latency compounds** — a "quick set of variations" at 1080p/8s is slow
  and pricey; prove at low res/short duration first.
- **Aspect/resolution mismatch** — generate at the nearest supported ratio
  (`references/backends.md`), then crop/pad to the exact target in post.
- **Audio assumptions** — xAI Grok Imagine has **no audio**; only some FAL models
  do. Don't promise sound without checking the active backend.
- **Seamless loops** aren't free — generated clips rarely loop cleanly; build the
  loop with `scripts/make-loop.sh` (crossfade or palindrome).

## Files

- `references/delivery-types.md` — router: delivery type → duration/aspect/codec → strategy.
- `references/discovery.md` — find playback constraints + brand/source assets.
- `references/text-to-video.md` — prompt motion from scratch (camera, subject, pacing, seed).
- `references/image-to-video.md` — animate a still / reference-guided for brand consistency.
- `references/social-specs.md` — platform duration/aspect/codec tables (Reels/TikTok/Shorts/X/YT/LinkedIn).
- `references/backends.md` — the `vid-xai-fal` / `vid-fal-xai` chain + per-backend capability matrix.
- `references/loops-and-posters.md` — seamless loops, poster frames, autoplay-muted-loop HTML.
- `scripts/video-postprocess.sh` — localize → trim → scale/crop → transcode → mute → size-cap.
- `scripts/make-loop.sh` — seamless loop (crossfade or palindrome) → web mp4 + webm.
- `scripts/poster-frame.sh` — extract a poster/preview still (jpg/webp) for `<video poster>`.

Run scripts via `${HERMES_SKILL_DIR}/scripts/<name>` (pass `--help` for usage).
Tooling (ffmpeg, ImageMagick, cwebp) is declared in the repo Brewfile.
