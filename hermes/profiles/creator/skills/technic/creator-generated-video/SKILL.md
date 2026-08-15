---
name: creator-generated-video
description: >-
  Creator's leaf technic for metered generated video: text-to-video,
  image-to-video, and reference-guided clips, followed by exact ffmpeg delivery.
  The creator-pipeline owns intake, Budget, review, and delivery.
version: 1.0.0
author: CraftSamo
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [creator, technic, video-generation, motion, image-to-video, branding]
    category: technic
---

<Goal>

Produce a generated clip that fits its destination and source identity. This is
a leaf technic: text-to-video, image-to-video, and reference-guided are modes of
the same generated-video capability and share one verification floor. The
approved Backend is either `core:video_generate` or `external:comfyui`.

</Goal>

<Scope>
<UseWhen>

- The user asks to create/generate a hero loop, looping background, product
  demo, explainer clip, social reel, teaser, or any short branded video —
  especially "for our app / site / landing page / launch".
- Use it whenever the clip must match an existing product's look or slot into a
  specific place with fixed duration/aspect/codec.

</UseWhen>

<DoNotUseWhen>

- Pixel-art animation (`creator-pixel-video`).
- Editing/trimming a user-supplied video when no generation is requested (that's
  `creator-media-assembly`).
- Video *understanding* (that's `video_analyze`).
- HTML/canvas-composited motion graphics, title cards, captions, or shader
  transitions (`creator-html-motion`).
- A full multi-agent production pipeline (bundled `kanban-video-orchestrator`).

</DoNotUseWhen>
</Scope>

<CorePrinciple>

Never jump straight to a prompt. The released spec fixes two decision sets;
validate both before any spend:

1. **Destination** — where will it play? Exact **duration**, **aspect ratio**,
   **resolution**, **container/codec** (mp4/H.264, webm/VP9), **max file size**,
   and the **playback contract** (autoplay needs muted; loop = seamless;
   poster/preview frame; does it need an `<video>` `poster`?). See
   `references/delivery-types.md` and `references/discovery.md`.
2. **Source & motion** — is there a **brand still to animate** (image-to-video
   keeps brand identity far better than text-to-video)? Reference frames?
   Palette, subject, and the **motion language** (locked vs moving camera, how
   much subject motion, pacing). See `references/image-to-video.md`.
3. **Backend** — the MediaBrief must name `core:video_generate` or
   `external:comfyui`; it is not selected from runtime convenience. Core keeps
   its configured in-chain fallback. ComfyUI stays local and stops on a failed
   preflight or render.

If either set is absent or contradicted by discovery, that is a spec gap: use the
pipeline's single batched `Q<n>:` block protocol rather than guessing or calling
`clarify`.

</CorePrinciple>

<Steps>

1. **Identify the delivery type** → load `references/delivery-types.md` and
   route. If the destination is unclear, ask: "Where will this play (web hero,
   social reel, in-app demo), how long, and what exact size?"
2. **Discover preconditions** (`references/discovery.md`): codebase grep / stated
   specs → destination constraints + brand/source assets.
3. **Preflight the approved Backend** (`references/backends.md`). For ComfyUI,
   load `skill_view(name="comfyui")` and verify the local accelerator, server,
   API-format workflow, models, nodes, output node, and runtime estimate before
   model load. Pin the loopback host and workflow SHA-256; audit every
   `class_type` against that same host's `/object_info`. Partner/API nodes are a
   cloud backend and do not satisfy `external:comfyui`.
4. **Pick the strategy**:

   | Strategy | When | How |
   |---|---|---|
   | **image-to-video** | a brand still / first frame exists; brand consistency matters | selected backend + source image → `references/image-to-video.md` |
   | **text-to-video** | no source; concept/atmosphere clip | selected backend + prompt → `references/text-to-video.md` |
   | **reference-guided** | identity must persist across shots | backend-supported references/workflow → `references/image-to-video.md` |

5. **Validate tradeoffs** against the released spec (cost × duration × count;
   audio yes/no; text-in-video = no) — a tradeoff the spec left open goes back as
   a spec gap. See below.
6. **Produce → review → tune → iterate** on only the approved Backend. Write the
   final prompt + params to `prompts/NN-<slug>.md` first. For ComfyUI also record
   the workflow, model files, seed, sampler, steps, and runtime ceiling. Every
   submitted workflow counts as a render even when it has zero marginal API
   cost. Preserve the runner JSON and same-host raw history entry for the
   returned `prompt_id`; without them the submitted graph and runtime are not
   verified.
7. **Post-process** to the exact target (`scripts/video-postprocess.sh`): trim,
   correct aspect/resolution, transcode, mute/strip audio, cap size. For loops
   use `scripts/make-loop.sh`; for a `<video poster>` use
   `scripts/poster-frame.sh`; for a **GIF** use `scripts/to-gif.sh` (also does a
   no-AI Ken Burns image→GIF). Then place/upload per the discovered convention
   (don't commit/upload without the user's go-ahead).

</Steps>

<Tradeoffs>

Video is expensive and slow — these arrive decided in the spec; flag any the spec
missed before spending:

- **Duration & count** — each second costs money and time. Generate **one**
  short proof first (≤ the target, often 4–6s), review, then scale. Don't batch
  a set of 8s 1080p clips on spec.
- **Audio?** Usually **no** for web heroes/backgrounds (they autoplay muted) —
  pick a quiet backend/model and strip audio in post. For social, native audio
  (Veo 3.1 / Seedance / Kling / LTX) may be wanted.
- **Text in the video?** Almost always **no** — generated on-screen text warps
  and flickers. Overlay titles/captions in post or via
  `creator-html-motion`.
- **People / faces** — motion artifacts on faces/hands are common; prefer
  image-to-video from a fixed still, shorter shots, and locked framing.
- **Output format** — for the web prefer mp4/webm (autoplay-muted-loop); use
  **GIF only where required** (chat, README, stickers) — it's large and silent.
  See `references/gifs.md`.

</Tradeoffs>

<BackendEssentials>

- **Core has two modalities**: pass `image_url` to `video_generate` to animate a
  still; omit it for text-to-video. The configured core chain auto-routes and
  owns its internal fallback. **Do not hardcode `model=`** because a model name
  valid for one chain member can break another.
- **ComfyUI is workflow-routed**: use the external skill's local runner with the
  exact preflighted API workflow. Inputs, model names, dimensions, frame count,
  and sampler settings live in that workflow/args, not in `video_generate`.
  Hosted Partner nodes are not this backend.
- **Capabilities differ by backend** — aspect ratios, resolutions, max duration,
  audio, and reference-image support are **not** uniform. For core, the tool
  description reflects its active provider; for ComfyUI, the preflighted graph
  is authoritative. Check `references/backends.md` before promising a
  4K/audio/portrait clip.
- **Core params**: `prompt`, `image_url`, `aspect_ratio`, `duration`,
  `resolution`, `negative_prompt` (FAL only), `audio` (FAL only),
  `reference_image_urls` (xAI), and `seed`. ComfyUI parameters belong to its
  recorded workflow/args.
- **Return value**: core returns a URL or local absolute path; ComfyUI writes a
  local output. Hosted core URLs expire, so save them locally immediately via
  `scripts/video-postprocess.sh`.
- **Reproducibility**: save each final prompt + params to `prompts/NN-<slug>.md`
  before calling. A later backend change is a new planned decision, not a retry.

</BackendEssentials>

<TuningDials>

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

</TuningDials>

<Pitfalls>

- Generated on-screen **text** is unreliable — keep words out, overlay in post.
- **Hosted URLs expire** — always localize the result before doing anything else.
- **Cost/latency compounds** — a "quick set of variations" at 1080p/8s is slow
  and pricey; prove at low res/short duration first.
- **Aspect/resolution mismatch** — generate at the nearest supported ratio
  (`references/backends.md`), then crop/pad to the exact target in post.
- **Audio assumptions** — xAI Grok Imagine has **no audio**; only some FAL models
  and ComfyUI workflows do. Don't promise sound without checking the approved
  backend's actual capability.
- **Seamless loops** aren't free — generated clips rarely loop cleanly; build the
  loop with `scripts/make-loop.sh` (crossfade or palindrome).

</Pitfalls>

<Files>

- `references/delivery-types.md` — router: delivery type → duration/aspect/codec → strategy.
- `references/discovery.md` — find playback constraints + brand/source assets.
- `references/text-to-video.md` — prompt motion from scratch (camera, subject, pacing, seed).
- `references/image-to-video.md` — animate a still / reference-guided for brand consistency.
- `references/social-specs.md` — platform duration/aspect/codec tables (Reels/TikTok/Shorts/X/YT/LinkedIn).
- `references/backends.md` — core provider-chain capabilities + local ComfyUI preflight boundary.
- `references/loops-and-posters.md` — seamless loops, poster frames, autoplay-muted-loop HTML.
- `references/gifs.md` — GIF vs mp4/webm, the two image→GIF routes, size discipline.
- `scripts/video-postprocess.sh` — localize → trim → scale/crop → transcode → mute → size-cap.
- `scripts/make-loop.sh` — seamless loop (crossfade or palindrome) → web mp4 + webm.
- `scripts/poster-frame.sh` — extract a poster/preview still (jpg/webp) for `<video poster>`.
- `scripts/to-gif.sh` — clip→GIF (two-pass palette) or still→GIF via `--ken-burns`; `--max-bytes`.

Run scripts via `${HERMES_SKILL_DIR}/scripts/<name>` (pass `--help` for usage).
Tooling (ffmpeg, ImageMagick, cwebp) is declared in the repo Brewfile.

</Files>
