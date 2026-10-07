# Generated video — decision surface

Enter only through the confirmed legacy route in [index](index.md).

This leaf is legacy-only, and only AFTER a Creator coverage check
([Client plan](../../SKILL.md)): a short generated clip or MV
that Creator's hands cover is handled by a Creator brief, with no
assistant-side parts or Backend decisions. What follows is the
canonical technic for genuinely broader work, or work the user
explicitly asks be planned this way.

Model-generated clips: text-to-video, image-to-video,
reference-guided. Deterministic HTML timelines → `html-motion.md`;
pixel animation → `pixel-video.md`; math explainers →
`manim-explainer.md`; editing existing footage → `media-assembly.md`.

Technic `creator-generated-video` · QA `video` · metered generation
through the selected Backend (expensive, slow) · resident-only.

## Fix before release

- Destination + playback contract: exact duration, aspect,
  resolution, container/codec, size cap — and autoplay/mute/loop/
  poster requirements. A seamless loop needs evidence, not a metadata flag.
- Strategy: settle text-to-video, image-to-video or reference-guided work
  with Creator against the actual identity and motion requirements. Fix the
  authorized source stills/reference frames without imposing one method on
  every brand job or treating a reference as proof of identity preservation.
- Describe desired camera and subject motion and pacing. Ask Creator about
  the chosen backend's constraints rather than forcing an old single-motion
  or locked-camera rule.
- State whether sound is required; ground actual audio support with Creator
  before promising it, never silently mute an explicitly audible result.
- Preserve exact wording requirements. Have Creator propose a feasible text
  treatment, such as an approved overlay/assembly, instead of assuming a
  generation model can produce exact lettering or banning requested text.
- For people/faces, state identity and performance invariants and actual
  permissions; let Creator assess the method without a blanket framing rule.
- **Backend** — name exactly one:
  - `core:video_generate` for the Creator profile's configured cloud
    chain. Prefer it for subject motion, a small number of finished clips,
    or deadline-sensitive work. Its existing in-chain fallback remains
    enabled.
  - `external:comfyui` only when a specific local API workflow, its models
    and nodes, expected motion class, and per-render runtime have been
    preflighted. It never falls through to cloud; an unavailable or
    over-budget local route comes back to Plan.
  Local still-image speed is not evidence of local video speed. Ground an
  uncertain choice with Creator advisory and do not release an open Backend.

## Defaults

- Anchor: REQUIRED beyond one cheap clip — one short low-cost proof
  (4–6 s) before any set or long render (`asset-set.md`).
- Budget shape: 2 renders per asset, 1 corrective pass. GIF only
  where the destination demands it (chat, README) — otherwise
  mp4/webm.
