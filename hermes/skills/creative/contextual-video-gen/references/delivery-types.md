# Delivery types — router

Identify the delivery type first, then follow its **strategy** and reference.
Durations/sizes are typical defaults; always prefer values discovered from the
destination (`discovery.md`). Confirm exact specs per platform in
`social-specs.md` and per backend in `backends.md`.

| Delivery type | Typical duration / ratio | Audio | Strategy | Reference |
|---|---|---|---|---|
| Web **hero loop** / background | 4–8s, 16:9 (or 21:9 crop), seamless | muted | text- or image-to-video → loop | `text-to-video.md`, `loops-and-posters.md` |
| **Product demo** (animate a UI/still) | 4–8s, 16:9 | usually muted | image-to-video | `image-to-video.md` |
| **Explainer / teaser** clip | 5–15s, 16:9 | optional | text-to-video | `text-to-video.md` |
| **Social reel** (IG/TikTok) | 5–15s, 9:16 | often on | text- or image-to-video | `social-specs.md` |
| **Shorts** (YouTube) | ≤60s (gen ≤15s, stitch) | optional | text-to-video | `social-specs.md` |
| **Square social** (IG/LinkedIn feed) | 5–15s, 1:1 | optional | either | `social-specs.md` |
| **Logo/brand sting** (animate a mark) | 2–5s | optional | image-to-video from the mark | `image-to-video.md` |
| **Animated avatar / loop sticker** | 2–4s, 1:1, seamless | muted | image-to-video → loop | `loops-and-posters.md` |

## Strategy meanings

- **text-to-video** — `video_generate(prompt=…)`. Best for atmosphere/concept
  clips with no source. Hardest to keep on-brand. See `text-to-video.md`.
- **image-to-video** — `video_generate(prompt=…, image_url=…)`. Animate an
  existing brand still/first frame. **Best brand consistency** — prefer this
  whenever a still exists. See `image-to-video.md`.
- **reference-guided** — `reference_image_urls=[…]` (xAI Grok Imagine, up to 7)
  to persist a subject/identity across generations. See `image-to-video.md`.

## Routing notes

- One destination can need several deliverables (e.g. a landing page wants a 16:9
  hero loop **and** a 9:16 social cut). Handle each by its own type; don't force
  one clip to serve all ratios — generate or crop per target.
- **Loops are a post step**, not a prompt: generate a clip, then build a seamless
  loop with `scripts/make-loop.sh`. Don't trust a raw clip to loop cleanly.
- Web heroes almost always autoplay **muted + looped** — pick a quiet model and
  strip audio; ship an mp4 (H.264) **and** webm (VP9) pair + a poster frame.
- When unsure of the type, duration, or size, ask the user before generating —
  video is metered.
