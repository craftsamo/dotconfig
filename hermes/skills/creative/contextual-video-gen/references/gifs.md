# GIFs — when and how

GIF is a **delivery format**, produced in post from a clip (or a still). The
`video_generate` backends never output GIF directly — generate a clip, then
convert with `scripts/to-gif.sh`.

## GIF vs mp4/webm — pick deliberately

| Use GIF when… | Use mp4/webm when… |
|---|---|
| The destination *requires* a GIF: chat (Slack/Discord/iMessage), README / docs, email, old CMSes, stickers/emotes | Anything on the web — a `<video>` hero, social, product page |
| Tiny, short, looping, silent motion | Longer, higher-quality, or with audio |

GIF is **universally embeddable but expensive**: 256 colours max, no audio, large
files, banding. For the web, an autoplay-muted-loop `<video>` (mp4+webm) is far
smaller and sharper — see `loops-and-posters.md`. Reach for GIF only when the
target won't take a `<video>`.

## Generating a GIF

1. Generate a clip (`text-to-video.md` or `image-to-video.md`). Keep it short and
   loop-friendly (calm, ambient motion loops best).
2. Convert: `scripts/to-gif.sh CLIP out.gif [--fps --width --max-colors --trim --loop --max-bytes]`.
3. For a seamless GIF loop, build the loop first (`scripts/make-loop.sh`,
   palindrome works well for GIF), then convert that to GIF.

```
# generated clip (or any video / expiring URL) -> GIF, capped at 2 MB
to-gif.sh "$VIDEO_URL" demo.gif --width 600 --fps 15 --max-bytes 2M
```

## Image → GIF — two routes

- **(A) AI motion** — animate a brand still, then convert:
  `video_generate(image_url=still)` → clip → `to-gif.sh clip out.gif`.
  Real, content-aware motion. Costs a generation. See `image-to-video.md`.
- **(B) No-AI Ken Burns** — synthesize a slow zoom/pan on the still, no model call:
  `to-gif.sh logo.png out.gif --ken-burns --kb-seconds 4 --width 480`.
  Free and instant; ideal for logos/photos that just need gentle life. Input
  should be png/jpg (some ffmpeg builds can't decode webp — convert first).

## Size discipline (GIFs balloon fast)

Levers, in the order to reach for them:

1. **Duration** — shorter is the biggest win. Trim to the essential beat (`--trim`).
2. **fps** — 10–15 is plenty for a GIF (`--fps`).
3. **width** — 360–600px for chat/README (`--width`; height auto, aspect kept).
4. **colours** — drop below 256 for flat/graphic content (`--max-colors`).
5. **`--max-bytes`** — best-effort cap: steps colours down (to 32), then width,
   re-encoding until under the cap (warns if it can't reach it).

```
to-gif.sh clip.mp4 sticker.gif --width 320 --fps 12 --max-bytes 500K
```

## Quality

`to-gif.sh` uses the **two-pass palettegen → paletteuse** pipeline (per-clip
optimal 256-colour palette + dithering) — far cleaner than a naive single-pass
GIF. Lanczos scaling keeps edges crisp. For further shrinking, `gifsicle -O3`
(optional, not in the Brewfile) can post-optimize.

## Pitfalls

- Don't ship GIF to a web `<video>` slot — it's needlessly huge; use mp4+webm.
- Photographic/gradient content bands badly at 256 colours — keep it short and
  small, or question whether GIF is the right format.
- Ken Burns input must be decodable by ffmpeg (png/jpg safe; webp may not be).
