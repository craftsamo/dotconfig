# Creator capability routing

This is the only in-profile router from a MediaBrief to production technics.
`technic/` contains directly selectable leaves; a leaf may have internal modes
only when they share tools, spend class, and verification.

## Families served by hands (checked FIRST — `plan.md` / `build.md`)

| Deliverable | Hands leaf | Notes |
| --- | --- | --- |
| a published library icon (Iconify) as SVG + PNG | image-creator: source-icon | free; a word instead of an id comes back as candidates |
| favicon / Apple / PWA / maskable set from a first-party SVG | image-creator: create-icon | free (the former `creator-logo-icons`) |
| an icon drawn in a named style (flat-minimal, glass, pixel, line, clay, …) | image-creator: generate-icon | metered; icons never go through `creator-generated-image` |
| recolour / background / cut-out / resize of an existing icon | image-creator: edit-icon | free |
| findings on an icon or icon set, no file | image-creator: analyze-icon | free |
| a custom-emoji pack of ONE character (a face / pet / mascot photo, or described) in a style, across a pack of expressions, for Slack / Discord / Telegram / LINE | image-creator: generate-emoji | metered, TWO rounds: without `anchor` it draws 3 character sheets and stops; the client approves one, then `intent: revise` + `anchor:` draws the pack (default anchor 3 + 1/item + ceil(n/4) correctives) |
| text emoji (承認 / LGTM / 助かる) as a set | image-creator: create-emoji | free; text travels in the `items` field, never as generated pixels |
| a photo cropped to a circle / rounded emoji, a flat-background cut-out, an outline, or a delivered pack re-finished for another platform | image-creator: edit-emoji | free; real background removal is not this leaf |
| findings on an emoji file or pack against a platform (size / format / cap / alpha, 32 px read, identity vs anchor, light / dark), no file | image-creator: analyze-emoji | free |
| a published emoji glyph (Twemoji, Noto, OpenMoji, Fluent) | image-creator: source-icon | free — `icon: twemoji:rocket`, `size: 128`; there is no source-emoji leaf on purpose |
| a mascot character designed from a concept (a brand's / product's / team's; species, personality, features, palette) in a style (game-2d, chibi, retro-cartoon, flat-vector, painterly, pixel, …), full body, transparent / chroma-key / flat | image-creator: generate-mascot | metered, TWO rounds: without `anchor` it draws 3 full-body concepts + a silhouette sheet and stops; the client approves one, then `intent: revise` + `anchor:` + `pack:` (turnaround 4 / poses 8 / custom) draws the pack on it (default concept 3 + 1/item + ceil(n/4) correctives). The approved anchor is the `reference:` every later asset of the character takes — `generate-emoji`, stickers, video |
| a delivered mascot re-keyed for video (chroma key), cropped to a head / bust avatar, resized, outlined, re-cut | image-creator: edit-mascot | free; never recolours — a shaded character is redrawn, not recoloured |
| findings on a mascot file, a concept round or a pack (square, cut-out, silhouette, 64 px read, light / dark, measured palette vs asked, identity vs anchor), no file | image-creator: analyze-mascot | free |
| a mascot from a stock library, or one drawn from a first-party SVG | — | there is no source-mascot or create-mascot on purpose: a mascot is designed, not fetched, and a first-party mark becomes an icon set (`create-icon`), not a character |
| a client's PHOTO (a person, a pet, an object, a place) re-rendered in a style (3d-character, comic-book, chibi, 70s-street, 80s-anime, or described) — the same subject, pose and composition, or `keep: identity` for the style's own scene; one or several styles | image-creator: generate-reimagine | metered (default 2 per style + 1 corrective per style); the photo goes to the backend as the edit input — a human client is told it leaves the machine BEFORE the handoff; output at the photo's own size next to a photo-plus-candidates sheet per style |
| a reimagined photo resized / reformatted, or findings on one | — | there is no edit- or analyze-reimagine on purpose: size and format are the leaf's own `size` / `format` fields (a `revise` on the same lock is free of a new look), and identity against the photo is the leaf's own QA — an emoji or sticker OF the person is `generate-emoji` with the photo as `reference:` |
| a game props/UI asset kit in one style, including world props, inventory icons, buttons, panels or bars | image-creator: generate-kit | metered; style-sheet approval, then individually generated PNGs. Confirm expanded item/state list and call budget; generated states can drift. Not 3D meshes or web components |
| exact game UI chrome from colours and geometry, including state pairs and 9-slice borders | image-creator: create-kit | free; flat-vector or pixel buttons/panels/bars as SVG + PNG; props and arbitrary art styles go to generate-kit |
| an existing kit cut out, fitted, palette-mapped or packed into a texture atlas | image-creator: edit-kit | free; atlas preserves original pixels; fitting may invalidate pivots and slicing metadata |
| findings on kit consistency, canvases, alpha, state alignment or frame/fill registration | image-creator: analyze-kit | free; no redraw; missing expectations are GAP, not invented PASS |
| existing CC0 game asset packs or a selected subset from Kenney | image-creator: source-kit | free; unknown pack returns search candidates; verified page license + archive provenance, not generated art |
| one short silent generated shot, from text or a starting still, in a named/described style | video-creator: generate-clip | metered, 1-15 seconds, 720p request, default 2 variants + 1 corrective; input-upload and remote-analysis consent are distinct |
| trim/fit/mute/re-encode one existing segment as MP4/WebM/GIF | video-creator: edit-clip | free of generation, at most 60 seconds; contain by default; GIF repeat is playback metadata, not seamless motion |
| technical and visual findings on one short clip, no new video | video-creator: analyze-clip | at most 60 seconds; local samples or one consented remote full-clip analysis; timestamps and explicit unverified checks |

The clip scope above is served, not the whole former generated-video
technic. Named legacy methods below (ComfyUI, authored HTML motion,
grid-exact pixels, montage/audio assembly) remain available for requests
that explicitly need them. Unsupported fields or a failed clip production
are findings back to the client, never a silent switch to legacy.

## Canonical technics

| Deliverable / production method | Canonical technic | Notes |
| --- | --- | --- |
| generated cover, hero, illustration, thumbnail, text-free social/document art | `creator-generated-image` | metered `core:image_generate` or preflighted `external:comfyui`; exact text stays out |
| consistent illustration set placed against an article | `creator-article-illustration` | metered `image_generate`; article analysis + placement map + shared style block |
| information-led visual summary with a layout x style grammar | `creator-infographic` | metered `image_generate`; dense exact labels route to deterministic SVG |
| precise architecture, scientific, educational, or general concept diagram | `creator-svg-diagram` | deterministic self-contained HTML + inline SVG; rendered preview required |
| editable hand-drawn architecture, flow, sequence, or concept diagram | `creator-excalidraw-diagram` | deterministic `.excalidraw` JSON; compatible rendered preview required |
| OG/social/title card with exact copy and typography | `creator-text-card` | deterministic composition; generated background is an explicit supporting technic |
| classic-template or custom-scene meme with deterministic captions | `creator-meme` | sourced template or separately budgeted generated background; provenance required |
| static banner, framed/message art, image conversion, or sourced ASCII art | `creator-ascii-art` | deterministic UTF-8 text master; ANSI only when requested |
| spectrogram, mel/chroma, loudness, MFCC, or other view of existing audio | `creator-audio-visualization` | deterministic `songsee` render; never audio generation |
| instrumental music, ambience, or sound effects generated with AudioCraft | `creator-audio-generation` | metered local MusicGen/AudioGen compute; model weights and reference rights require preflight |
| full vocal song generated from approved lyrics and musical tags | `creator-song-generation` | metered HeartMuLa compute; high-cost work uses the plan/anchor gate |
| existing reaction or communication GIF sourced from Tenor | `creator-gif-sourcing` | retrieval with provenance and rights caveat; never asset generation |
| generated video outside the served short-shot contract, notably an explicitly requested local ComfyUI workflow | `creator-generated-video` | retained until coverage is migrated; core short shots use generate-clip, not this technic; no silent backend substitution |
| deterministic motion graphics, product/site tours, overlays, or captioned video authored in HTML/CSS/JS | `creator-html-motion` | HyperFrames source project + MP4/WebM; supporting generation is separately budgeted |
| generative art, interactive canvas/WebGL experience, custom data visual, or p5.js export | `creator-p5js-experience` | seeded browser-native source; PNG/GIF/MP4/SVG are optional exports |
| video-to-ASCII, audio-reactive, generative, hybrid, lyric, or TTS-backed ASCII motion | `creator-ascii-video` | deterministic Python/ffmpeg render; supporting generation/TTS is separately budgeted |
| mathematical, algorithmic, data, paper, or 3D educational animation | `creator-manim-explainer` | deterministic Manim render; supporting TTS is separately budgeted |
| still sprite, avatar, icon, logo reduction, or scene on a pixel grid | `creator-pixel-art` | native master + nearest-neighbor preview |
| sprite/cel animation, procedural pixel loop, pixel MP4/GIF | `creator-pixel-video` | deterministic native-grid animation; never ordinary AI video |
| educational, biography, or tutorial comic with storyboarded panels | `creator-knowledge-comic` | metered page art + deterministic lettering; multi-page work uses the plan/anchor gate |
| official third-party logo/mark acquisition and provenance | `creator-brand-asset-sourcing` | source, do not redraw |
| assembly of QA-passed parts — mux, concat, mix, overlay, trim, re-container per a fixed edit spec | `creator-media-assembly` | deterministic ffmpeg; parts consumed verbatim; zero generation spend |

Voice lines currently use the `tts` toolset under the pipeline contract and
identify as `core:tts`, without a dedicated technic. `creator-html-motion`
loads the external HyperFrames router and its `media-use` asset/TTS/caption
support as implementation engines. Other niche assets may use an
`external:<skill>` identity only after an availability preflight.

## Selection rules

1. Route by the requested final deliverable and production method, not file
   extension alone. A sourced Tenor GIF is `creator-gif-sourcing`; a GIF made
   from pixel frames is `creator-pixel-video`; a GIF converted from a generated
    short served clip uses `generate-clip` then `edit-clip`; explicitly
    legacy production keeps its canonical technic.
2. Styles and presets are not technics. NES/Game Boy/PICO-8 stay inside
   `creator-pixel-art`; text/image/reference modes stay inside
    `generate-clip` for the served short-shot contract, otherwise the named
    legacy `creator-generated-video` method.
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
    `generate-clip` within its short-shot contract; a requested legacy
    backend stays `creator-generated-video`. Seekable HTML timeline motion is
   `creator-html-motion`; p5.js canvas/WebGL work is
   `creator-p5js-experience`; mathematical teaching animation is
   `creator-manim-explainer`.
8. ComfyUI is an implementation backend, never a canonical capability. An image
   generated through it remains `creator-generated-image`; a clip remains
   `creator-generated-video`. Use only the Backend approved in the MediaBrief.
   `core:image_generate` / `core:video_generate` may use their configured
   in-chain fallback. `external:comfyui` stops on failed preflight or execution
   and returns the finding; it never crosses to a core/cloud backend silently.

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

For `external:comfyui`, the existing handshake fields carry the local-boundary
evidence; do not invent a second schema. `backend:` names the exact external
runner, loopback host, workflow path, and workflow SHA-256. `preflight:` records
the non-CPU device, dependency result, and a same-host `/object_info` audit of
every workflow `class_type`. Reject any `api_node: true`, Partner/API category,
cloud host, Partner key, skipped node check, missing dependency, or model-folder
query error. `health_check.py` is only reachability/dependency evidence: also run
`extract_schema.py` and inspect model loaders plus output/container nodes before
submission. Every non-core custom node requires either an explicit trusted
package allowlist entry or source review for outbound HTTP clients, cloud SDKs,
API-key reads, subprocesses, and hidden hosted-generation calls; local
installation alone is not locality evidence.

Hash the source workflow immediately before execution. After execution,
preserve the runner result and same-host raw history entry, then separately hash
the effective submitted graph from history. Compare node IDs, classes, and
wiring semantically; only the recorded prompt/seed/input/parameter injections
may differ. Record both hashes and the allowed injection diff rather than
expecting the parameterized graph to equal the source-file hash.

External opt-in skills are implementation/catalog inputs, not stable dispatch
identities unless this file explicitly names them. In particular, never pin or
`skill_view` the ambiguous bare `pixel-art`; the canonical pixel technics own
its optional scripts. Likewise, report ComfyUI as the backend of
`creator-generated-image` or `creator-generated-video`, never as
`capability: external:comfyui`.
