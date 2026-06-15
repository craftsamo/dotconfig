# Loops & posters

Generated clips rarely loop cleanly and don't ship a poster — both are **post
steps**.

## Seamless loops

A raw generated clip usually jumps at the wrap. Two ways to fix it
(`scripts/make-loop.sh`):

- **crossfade** (default) — blends the last N seconds back into the start.
  General-purpose; slightly shortens the clip. Good for ambient/atmospheric
  backgrounds.
  `make-loop.sh in.mp4 out.mp4 --mode crossfade --xfade 0.5`
- **palindrome** (boomerang) — plays forward then reversed, so the ends always
  meet. Doubles the duration; great for short ambient motion (steam, particles),
  bad for directional motion (a push-in becomes a push-in-then-out).
  `make-loop.sh in.mp4 out.mp4 --mode palindrome`

Tips:
- Generate motion that **starts and ends calm** (ambient drift, slow push-in) —
  it loops far better than directional/energetic motion.
- Keep loops short (4–8s) and **muted** for web heroes.
- Ship an **mp4 (H.264) + webm (VP9) pair** for `<video>` coverage.

## Poster / preview frame

Web players show a `poster` until playback starts; many feeds need a thumbnail.
Extract one with `scripts/poster-frame.sh`:

- `poster-frame.sh in.mp4 poster.jpg --time 0.0` — first frame (matches an
  autoplay hero's first painted frame).
- `poster-frame.sh in.mp4 poster.webp --time 1.2` — a representative mid-clip
  frame as WebP (smaller).

Pick a frame that looks good static (the hero's first frame is usually safest for
autoplay so there's no jump from poster → video).

## Web embed (autoplay, muted, looped)

```html
<video
  autoplay
  muted
  loop
  playsinline
  poster="/hero-poster.jpg"
  class="h-full w-full object-cover"
>
  <source src="/hero.webm" type="video/webm" />
  <source src="/hero.mp4"  type="video/mp4" />
</video>
```

- `muted` is **required** for autoplay; `playsinline` keeps it inline on iOS.
- List **webm first, mp4 second** (browser picks the first it supports).
- `object-cover` crops to the container — keep the subject center-safe (design
  for the crop, like the image skill's center-safe area).
- Size budget: short loop, 720–1080p, sensible bitrate; verify the final bytes
  with `video-postprocess.sh --max-bytes`.
