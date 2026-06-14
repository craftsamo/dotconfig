# Image-to-video & reference-guided — keep it on-brand

Animating an existing still is the **best way to stay on-brand** — the first
frame *is* your art, so colours, composition, and product stay exact. Prefer this
whenever a usable still exists (hero image, product screenshot, key art, logo
frame). This is the motion analogue of the image skill's "derive-from-logo".

## Image-to-video

Call: `video_generate(prompt=…, image_url=…, aspect_ratio=…, duration=…)`.

- `image_url` accepts an **http(s) URL, a `data:image/…` URI, or a local file
  path**. Generate/clean the still first (e.g. via `contextual-image-gen` +
  `img-postprocess.sh`) so the first frame is already correct.
- The **prompt now describes motion only** — what should *move* and how the
  camera behaves — not the scene (the image defines the scene):
  > Gentle parallax push-in; soft particles drift; subtle shimmer on the logo.
- Match the still's **aspect ratio** to avoid letterboxing; crop the still to the
  target ratio before animating if needed.
- Keep motion **subtle** for product/brand stills — small camera moves and
  ambient motion read as "premium"; large motion warps the product.

### Backend routing (automatic)

- **xAI Grok Imagine**: image-to-video routes to `grok-imagine-video-1.5-preview`
  (latest); up to **7 `reference_image_urls`**; no audio.
- **FAL.ai**: image-to-video on the configured model family (Pixverse v6, Veo
  3.1, Seedance 2.0, Kling v3, LTX 2.3); some support **audio** and
  **negative_prompt**. See `backends.md`.

The `vid-xai-fal` chain tries Grok first, then FAL — so an image-to-video call
animates via Grok 1.5 and falls back to a FAL model on error/limit.

## Reference-guided (persist identity across shots)

To keep a character/product **consistent across multiple generations**, pass
`reference_image_urls=[url1, url2, …]` (xAI Grok Imagine, up to 7). Use when you
need several clips that share one identity (a mascot, a product from angles).
FAL backends don't take reference images (`max_reference_images: 0`) — for those,
reuse the same `image_url` first frame and a fixed `seed`.

## Dials

- **Motion amount** — start minimal; increase only if the clip feels dead.
- **duration** — short (4–6s) keeps the product from morphing.
- **seed** — fix it to reproduce a good animation while tuning.
- **aspect_ratio** — match the source still; otherwise crop the still first.

## Pitfalls

- Busy stills morph — simpler first frames animate cleaner.
- Text/logos in the still can still flicker — if they wobble, keep them out of
  the animated region and composite them back in post.
- Don't promise audio from Grok image-to-video (it has none) — use a FAL model or
  add audio in post.

## Then

Localize + finish with `scripts/video-postprocess.sh`; loop with
`scripts/make-loop.sh`; poster via `scripts/poster-frame.sh`.
