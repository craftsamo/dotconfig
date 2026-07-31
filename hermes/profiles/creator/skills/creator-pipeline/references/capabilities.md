# Creator capability routing

This is the only in-profile router from a MediaBrief to production technics.
`technic/` contains directly selectable leaves; a leaf may have internal modes
only when they share tools, spend class, and verification.

## Canonical technics

| Deliverable / production method | Canonical technic | Notes |
| --- | --- | --- |
| generated cover, hero, illustration, thumbnail, text-free social/document art | `creator-generated-image` | metered `image_generate`; exact text stays out |
| favicon, Apple, PWA, maskable, or app-icon set from an approved first-party SVG | `creator-logo-icons` | deterministic; zero generation spend |
| OG/social/title card with exact copy and typography | `creator-text-card` | deterministic composition; generated background is an explicit supporting technic |
| text-to-video, image-to-video, or reference-guided generated clip | `creator-generated-video` | metered `video_generate`; GIF/loop/poster may be delivery post-steps |
| still sprite, avatar, icon, logo reduction, or scene on a pixel grid | `creator-pixel-art` | native master + nearest-neighbor preview |
| sprite/cel animation, procedural pixel loop, pixel MP4/GIF | `creator-pixel-video` | deterministic native-grid animation; never ordinary AI video |
| official third-party logo/mark acquisition and provenance | `creator-brand-asset-sourcing` | source, do not redraw |

Voice lines currently use the `tts` toolset under the pipeline contract and
identify as `core:tts`, without a dedicated technic. HTML/CSS motion identifies
as `external:hyperframes` after preflight; `media-use` remains its external
asset/TTS/caption support. Other niche assets may use an `external:<skill>`
identity only after an availability preflight.

## Selection rules

1. Route by the requested final deliverable and production method, not file
   extension alone. A GIF made from pixel frames is `creator-pixel-video`; a GIF
   converted from a generated clip remains `creator-generated-video`.
2. Styles and presets are not technics. NES/Game Boy/PICO-8 stay inside
   `creator-pixel-art`; text/image/reference modes stay inside
   `creator-generated-video`.
3. Stack a supporting technic only when the brief truly spans methods. Example:
   a generated background plus exact title card loads
   `creator-generated-image` and `creator-text-card`, with separate spend lines.
4. The task body's `Technique:` is a request. Validate it against this table;
   correct an objective mismatch in `STATE:`, and block only when the choice
   changes user intent or spend.

## Capability handshake

Before production, `STATE:` or the first `PROGRESS:` must include:

```text
capability: <creator-leaf>@<version> | core:tts | external:<skill>
backend: <tool/provider or exact external script path>
preflight: pass | blocked - <reason>
```

For a routed leaf, if its pin was skipped, missing, ambiguous, disabled, or lacks
a required backend, load the canonical name explicitly. If that still fails,
block before spend. A core/external route must pass its own tool/prerequisite
preflight. Never fall back silently to generic image/video generation.

External opt-in skills are implementation/catalog inputs, not stable dispatch
identities unless this file explicitly names them. In particular, never pin or
`skill_view` the ambiguous bare `pixel-art`; the canonical pixel technics own
its optional scripts.
