# Social & web video specs

Target these at **post-process** time (`video-postprocess.sh`). Generate at the
nearest backend-supported aspect/resolution (`backends.md`), then crop/scale to
the exact target. Generated clips are short (≤ 15s) — for longer placements,
generate beats and stitch.

## Platform table

| Platform | Aspect | Resolution | Duration (gen → final) | FPS | Container / codec | Audio |
|---|---|---|---|---|---|---|
| Instagram Reels | 9:16 | 1080×1920 | ≤15s gen, ≤90s final | 30 | mp4 / H.264 | often on |
| TikTok | 9:16 | 1080×1920 | ≤15s gen, stitch longer | 30 | mp4 / H.264 | usually on |
| YouTube Shorts | 9:16 | 1080×1920 | ≤15s gen → ≤60s | 30 | mp4 / H.264 | optional |
| IG / LinkedIn feed | 1:1 | 1080×1080 | 5–15s | 30 | mp4 / H.264 | optional |
| IG / FB feed (landscape) | 16:9 | 1920×1080 | 5–15s | 30 | mp4 / H.264 | optional |
| X / Twitter | 16:9 or 1:1 | 1280×720 / 720×720 | 5–15s | 30 | mp4 / H.264 | optional |
| YouTube (standard) | 16:9 | 1920×1080 | stitch beats | 24–30 | mp4 / H.264 | yes |
| **Web hero / background** | 16:9 (or 21:9 crop) | 1920×1080 → ≤2–5 MB | 4–8s, **looped** | 24–30 | **mp4 (H.264) + webm (VP9)** | **muted** |

## Notes

- **Web heroes**: autoplay requires **muted**; ship an **mp4 + webm pair** for
  `<video>` coverage and a **poster frame** (`poster-frame.sh`) for first paint.
  Keep it under the size budget — short loop, sensible bitrate, 720–1080p.
- **Vertical (9:16)**: generate at 9:16 where the backend supports it (xAI and
  FAL both do); otherwise generate 16:9 and crop — but cropping to vertical loses
  a lot, so prefer native 9:16.
- **Square (1:1)**: xAI supports 1:1 natively; FAL supports 1:1. Otherwise
  center-crop from 16:9.
- **Frame rate**: generated clips are typically ~24–30fps; don't upsample fps in
  post (it won't add real motion) — just match the container's expected fps.
- **Captions/lower-thirds**: overlay in post or via the `hyperframes` skill, not
  inside the generated frame.
- **Audio**: only some FAL models produce audio; xAI Grok Imagine has none. If a
  platform wants sound and the active backend is silent, add a track in post.
