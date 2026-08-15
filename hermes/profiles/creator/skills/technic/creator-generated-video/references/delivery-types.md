<Goal>

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
| **GIF** (chat / README / docs demo) | 2–6s, any | silent | generate (or image-to-video) → `to-gif.sh` | `gifs.md` |
| **GIF sticker / emote** | 1–3s, 1:1, looped | silent | image-to-video or Ken Burns → GIF | `gifs.md` |

</Goal>

<StrategyMeanings>

- **text-to-video** — prompt-only generation through the approved Backend. Best
  for atmosphere/concept clips with no source; hardest to keep on-brand. See
  `text-to-video.md`.
- **image-to-video** — animate an existing brand still/first frame through the
  approved Backend. **Best brand consistency**; prefer this whenever a still
  exists. See `image-to-video.md`.
- **reference-guided** — use only the approved Backend's supported reference
  inputs or local workflow nodes to persist identity. See `image-to-video.md`.

</StrategyMeanings>

<RoutingNotes>

- One destination can need several deliverables (e.g. a landing page wants a 16:9
  hero loop **and** a 9:16 social cut). Handle each by its own type; don't force
  one clip to serve all ratios — generate or crop per target.
- **Loops are a post step**, not a prompt: generate a clip, then build a seamless
  loop with `scripts/make-loop.sh`. Don't trust a raw clip to loop cleanly.
- Web heroes almost always autoplay **muted + looped** — pick a quiet model and
  strip audio; ship an mp4 (H.264) **and** webm (VP9) pair + a poster frame.
- **GIF is a post-format, not a backend** — no model outputs GIF. Generate a clip
  (or Ken Burns a still), then convert with `scripts/to-gif.sh`; prefer mp4/webm
  for the web. See `gifs.md`.
- When unsure of the type, duration, or size, ask the user before generating —
  video is metered.

</RoutingNotes>
