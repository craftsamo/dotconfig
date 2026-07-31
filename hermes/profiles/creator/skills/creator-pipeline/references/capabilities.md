# Creator capability routing

This is the only in-profile router from a MediaBrief to production technics.
`technic/` contains directly selectable leaves; a leaf may have internal modes
only when they share tools, spend class, and verification.

## Canonical technics

| Deliverable / production method | Canonical technic | Notes |
| --- | --- | --- |
| generated cover, hero, illustration, thumbnail, text-free social/document art | `creator-generated-image` | metered `image_generate`; exact text stays out |
| consistent illustration set placed against an article | `creator-article-illustration` | metered `image_generate`; article analysis + placement map + shared style block |
| information-led visual summary with a layout x style grammar | `creator-infographic` | metered `image_generate`; dense exact labels route to deterministic SVG |
| precise architecture, scientific, educational, or general concept diagram | `creator-svg-diagram` | deterministic self-contained HTML + inline SVG; rendered preview required |
| editable hand-drawn architecture, flow, sequence, or concept diagram | `creator-excalidraw-diagram` | deterministic `.excalidraw` JSON; compatible rendered preview required |
| favicon, Apple, PWA, maskable, or app-icon set from an approved first-party SVG | `creator-logo-icons` | deterministic; zero generation spend |
| OG/social/title card with exact copy and typography | `creator-text-card` | deterministic composition; generated background is an explicit supporting technic |
| classic-template or custom-scene meme with deterministic captions | `creator-meme` | sourced template or separately budgeted generated background; provenance required |
| static banner, framed/message art, image conversion, or sourced ASCII art | `creator-ascii-art` | deterministic UTF-8 text master; ANSI only when requested |
| spectrogram, mel/chroma, loudness, MFCC, or other view of existing audio | `creator-audio-visualization` | deterministic `songsee` render; never audio generation |
| instrumental music, ambience, or sound effects generated with AudioCraft | `creator-audio-generation` | metered local MusicGen/AudioGen compute; model weights and reference rights require preflight |
| full vocal song generated from approved lyrics and musical tags | `creator-song-generation` | metered HeartMuLa compute; high-cost work uses the plan/anchor gate |
| existing reaction or communication GIF sourced from Tenor | `creator-gif-sourcing` | retrieval with provenance and rights caveat; never asset generation |
| text-to-video, image-to-video, or reference-guided generated clip | `creator-generated-video` | metered `video_generate`; GIF/loop/poster may be delivery post-steps |
| deterministic motion graphics, product/site tours, overlays, or captioned video authored in HTML/CSS/JS | `creator-html-motion` | HyperFrames source project + MP4/WebM; supporting generation is separately budgeted |
| generative art, interactive canvas/WebGL experience, custom data visual, or p5.js export | `creator-p5js-experience` | seeded browser-native source; PNG/GIF/MP4/SVG are optional exports |
| video-to-ASCII, audio-reactive, generative, hybrid, lyric, or TTS-backed ASCII motion | `creator-ascii-video` | deterministic Python/ffmpeg render; supporting generation/TTS is separately budgeted |
| mathematical, algorithmic, data, paper, or 3D educational animation | `creator-manim-explainer` | deterministic Manim render; supporting TTS is separately budgeted |
| still sprite, avatar, icon, logo reduction, or scene on a pixel grid | `creator-pixel-art` | native master + nearest-neighbor preview |
| sprite/cel animation, procedural pixel loop, pixel MP4/GIF | `creator-pixel-video` | deterministic native-grid animation; never ordinary AI video |
| educational, biography, or tutorial comic with storyboarded panels | `creator-knowledge-comic` | metered page art + deterministic lettering; multi-page work uses the plan/anchor gate |
| official third-party logo/mark acquisition and provenance | `creator-brand-asset-sourcing` | source, do not redraw |

Voice lines currently use the `tts` toolset under the pipeline contract and
identify as `core:tts`, without a dedicated technic. `creator-html-motion`
loads the external HyperFrames router and its `media-use` asset/TTS/caption
support as implementation engines. Other niche assets may use an
`external:<skill>` identity only after an availability preflight.

## Selection rules

1. Route by the requested final deliverable and production method, not file
   extension alone. A sourced Tenor GIF is `creator-gif-sourcing`; a GIF made
   from pixel frames is `creator-pixel-video`; a GIF converted from a generated
   clip remains `creator-generated-video`.
2. Styles and presets are not technics. NES/Game Boy/PICO-8 stay inside
   `creator-pixel-art`; text/image/reference modes stay inside
   `creator-generated-video`.
3. Static terminal-safe ASCII output is `creator-ascii-art`; any timed or
   audio-reactive ASCII render is `creator-ascii-video`. Audio visualization
   reads an existing source; speech synthesis is `core:tts`, instrumental/SFX
   generation is `creator-audio-generation`, and lyrics-to-song generation is
   `creator-song-generation`.
4. Stack a supporting technic only when the brief truly spans methods. Example:
   a generated background plus exact title card loads
   `creator-generated-image` and `creator-text-card`, with separate spend lines.
5. The task body's `Technique:` is a request. Validate it against this table;
   correct an objective mismatch in `STATE:`, and block only when the choice
   changes user intent or spend.
6. A canonical leaf may load an official skill from `external_dirs` as its
   implementation engine. Report the canonical leaf as `capability` and the
   official skill plus concrete tool/path as `backend`; never expose the
   engine's bare name as the stable dispatch identity.
7. Route by authorship method as well as container. A model-generated MP4 is
   `creator-generated-video`; seekable HTML timeline motion is
   `creator-html-motion`; p5.js canvas/WebGL work is
   `creator-p5js-experience`; mathematical teaching animation is
   `creator-manim-explainer`.

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
