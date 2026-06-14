# Text-to-video — prompt motion from scratch

For concept/atmosphere clips with **no source still**. Hardest mode to keep
on-brand — if a brand still exists, prefer `image-to-video.md`.

Call: `video_generate(prompt=…, aspect_ratio=…, duration=…, resolution=…)`
(omit `image_url`). The active backend picks the model family; **don't hardcode
`model=`** (`backends.md`).

## Prompt structure

Keep it concrete and short. Cover, in order:

1. **Subject** — what's on screen (one clear focal subject).
2. **Setting / style** — environment, lighting, palette (use brand hexes as
   words: "deep indigo background"), and look (cinematic, flat-graphic, macro).
3. **Camera** — one explicit move: *slow push-in*, *gentle pan left*, *orbit*,
   or *locked/static*. Don't stack moves.
4. **Subject motion** — one action (*steam rising*, *ribbon unfurling*). If the
   camera moves, keep the subject calm (and vice-versa) to limit artifacts.
5. **Pacing** — "slow, calm" vs "energetic"; matches the duration.

Example:
> Macro shot of a single matte-indigo coffee bean on a seamless light-grey
> backdrop, soft studio light. Slow push-in. A thin wisp of steam drifts upward.
> Calm, premium, minimal.

## Dials

- **Duration** — start short (4–6s). Longer = more drift and more cost.
- **aspect_ratio** — generate at the **nearest supported** ratio (`backends.md`),
  crop/pad to exact in post (`video-postprocess.sh`).
- **resolution** — prove at low res (480p/540p), then re-run the winner at the
  target res. Don't iterate at 1080p.
- **negative_prompt** — FAL only; use to suppress "text, watermark, distorted
  hands, flicker". (xAI ignores it — keep such constraints out of the prompt.)
- **audio** — FAL only, and off by default for muted web heroes. Leave unset
  unless the destination wants sound.
- **seed** — set it to make a good result reproducible while you tune other
  params; record it in `prompts/NN-<slug>.md`.

## Keep out of the prompt

- **On-screen text / logos / UI** — they warp and flicker. Overlay in post or via
  the `hyperframes` skill.
- **Real faces / hands doing fine motion** — high artifact risk; prefer locked
  framing and short shots, or switch to image-to-video from a clean still.
- **Multiple simultaneous camera + subject moves** — pick one.

## Then

Localize and finish the clip with `scripts/video-postprocess.sh` (hosted URLs
expire). For loops, `scripts/make-loop.sh`; for a poster, `scripts/poster-frame.sh`.
