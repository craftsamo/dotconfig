<Goal>

Animating an existing still is the **best way to stay on-brand** — the first
frame *is* your art, so colours, composition, and product stay exact. Prefer this
whenever a usable still exists (hero image, product screenshot, key art, logo
frame). This is the motion analogue of the image skill's "derive-from-logo".

</Goal>

<ImageToVideo>

Core call: `video_generate(prompt=…, image_url=…, aspect_ratio=…,
duration=…)`. With `external:comfyui`, upload/reference the source image through
the preflighted local API workflow instead. The motion and framing guidance
below applies to both backends.

- `image_url` accepts an **http(s) URL, a `data:image/…` URI, or a local file
  path**. Generate/clean the still first (for example with the separately
  loaded `creator-generated-image` technic) so the first frame is already
  correct.
- The **prompt now describes motion only** — what should *move* and how the
  camera behaves — not the scene (the image defines the scene):
  > Gentle parallax push-in; soft particles drift; subtle shimmer on the logo.
- Match the still's **aspect ratio** to avoid letterboxing; crop the still to the
  target ratio before animating if needed.
- Keep motion **subtle** for product/brand stills — small camera moves and
  ambient motion read as "premium"; large motion warps the product.

**Core provider routing (automatic):**

- **xAI Grok Imagine**: image-to-video routes to `grok-imagine-video-1.5-preview`
  (latest); up to **7 `reference_image_urls`**; no audio.
- **FAL.ai**: image-to-video on the configured model family (Pixverse v6, Veo
  3.1, Seedance 2.0, Kling v3, LTX 2.3); some support **audio** and
  **negative_prompt**. See `backends.md`.

The configured core chain owns this provider fallback. It does not cross to or
from `external:comfyui`.

</ImageToVideo>

<ReferenceGuided>

To keep a character/product **consistent across multiple generations**, core
may pass `reference_image_urls=[url1, url2, …]` when its active provider supports
them. A ComfyUI workflow may instead use its approved local reference/control
nodes. In either case, use the exact Backend and reference mechanism fixed in
the brief; never switch methods after seeing a result.

</ReferenceGuided>

<Dials>

- **Motion amount** — start minimal; increase only if the clip feels dead.
- **duration** — short (4–6s) keeps the product from morphing.
- **seed** — fix it to reproduce a good animation while tuning.
- **aspect_ratio** — match the source still; otherwise crop the still first.

</Dials>

<Pitfalls>

- Busy stills morph — simpler first frames animate cleaner.
- Text/logos in the still can still flicker — if they wobble, keep them out of
  the animated region and composite them back in post.
- Don't promise audio from Grok image-to-video (it has none) — use a FAL model or
  add audio in post.

</Pitfalls>

<PostProcess>

Localize + finish with `scripts/video-postprocess.sh`; loop with
`scripts/make-loop.sh`; poster via `scripts/poster-frame.sh`.

</PostProcess>
