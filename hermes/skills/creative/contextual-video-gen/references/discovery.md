# Discovery — gather preconditions

Goal: produce two fact sets before generating — **playback constraints** and the
**source/brand** material. Source order: codebase → brand doc/Figma → ask the
user. Video is metered, so a missing fact that matters is worth one focused
question, not a guess.

## A. Playback constraints

What to find:

- **Duration** — exact target length, and whether it must **loop seamlessly**.
- **Aspect ratio & resolution** — all the shapes the clip plays at (16:9 hero,
  9:16 social cut, …) and the max resolution actually rendered.
- **Container & codec** — `mp4` (H.264/H.265) and/or `webm` (VP9/AV1). The web
  usually wants an **mp4 + webm** pair for `<video>` compatibility.
- **Playback contract** — autoplay (⇒ must be **muted**), `loop`, `playsinline`,
  and whether a **poster/preview frame** is needed.
- **File-size budget** — heroes/backgrounds are often capped (e.g. ≤ 2–5 MB) to
  protect load time.
- **Storage / upload path** — bucket, public URL pattern, signed-upload flow, or
  a framework convention (e.g. `public/hero.mp4`).

### In a codebase (web/app)

Use `search_files` / `terminal` grep; delegate big repos to an `explore` task.

- The player & flags: search `<video`, `autoplay`, `muted`, `loop`,
  `playsinline`, `poster=`, `source type="video/(mp4|webm)"`.
- Background patterns: `object-cover|aspect-video|background video|<video`.
- Limits/convention: hero/loop asset names, CDN/bucket builders
  (`storage.googleapis.com|S3|bucket|signed`), and any size guidance in docs.

Record exact `file:line` so the user can verify.

### Brand doc / Figma / none

- Ask for target length, frame size, codec/container, and placement.
- If nothing exists, ask the user for duration + size + where it will live. Do
  not assume — wrong specs are costly to regenerate.

## B. Source & motion material

What to find:

- **A still to animate** — a hero image, product screenshot, key art, or logo
  frame. Image-to-video from a brand still keeps identity far better than
  text-to-video; prefer it whenever one exists. (`image-to-video.md`)
- **Reference frames** — extra images to persist a subject/identity (xAI Grok
  Imagine accepts up to 7 `reference_image_urls`).
- **Palette & subject** — brand colours (hex) and the focal subject, so the
  motion stays on-brand.
- **Motion language** — locked vs moving camera, how much subject motion, and
  pacing (calm push-in vs energetic). One motion idea per clip.

Grep hints (brand/source): `hero|poster|key-?art|public/**/*.{png,jpg,webp}`,
`--primary|--accent|#[0-9a-fA-F]{6}`, `logo|brand`.

## Output (feed into the chosen strategy)

- **Target spec**: duration, aspect, resolution, container/codec, size cap,
  loop? audio?
- **Source**: still path/URL for image-to-video (or "none → text-to-video"),
  plus any reference frames.
- **Motion**: one line — camera + subject + pacing.
- **Backend note**: confirm the active chain can hit the spec
  (`backends.md`) — e.g. portrait 9:16, 1080p, or audio.

If a fact is missing and matters, ask one focused question rather than guessing.
