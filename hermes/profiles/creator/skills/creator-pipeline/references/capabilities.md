# Creator capability routing

This is the only in-profile router from a MediaBrief to production technics.
`technic/` contains directly selectable leaves; a leaf may have internal modes
only when they share tools, spend class, and verification.

## Families served by hands (checked FIRST — [Plan](plan/index.md) / [Build](build/index.md))

| Deliverable | Hands leaf | Notes |
| --- | --- | --- |
| exact-copy OG/social/header/thumbnail/hero/title card from supplied text/assets | image-creator: create-card | free; named templates or task-authored static HTML/CSS, independent typography and exact copy blocks; ordered panorama tiles; authored work uses resident |
| the same card with a generated text-free background | image-creator: generate-card | proposed 3 variants + 1 corrective across resumes; explicit current-conversation user budget approval before paid calls; backend aspect preflight |
| an existing finished card fitted with cover/contain/pad/focus, optional text band | image-creator: edit-card | free; reject destructive protected-content crops; own editable source rerenders create-card |
| measured and visual findings on a single card, ordered tiles or a panorama | image-creator: analyze-card | free; files array + input_kind, no corrected media; platform crops remain unverified |
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
| a short generated MV with subject performance, a coherent world and evolving shots/highlights | video-creator: generate-music-video | metered, 5-15 seconds; unspent proposal then exact-plan approval; theme/style/direction are form values, default 2 variants + 1 corrective; native generated audio needs backend support, supplied music/exact lettering need separate finishing |
| trim/fit/mute/re-encode one existing segment as MP4/WebM/GIF | video-creator: edit-clip | free of generation, at most 60 seconds; contain by default; GIF repeat is playback metadata, not seamless motion |
| technical and visual findings on one short clip, no new video | video-creator: analyze-clip | at most 60 seconds; local samples or one consented remote full-clip analysis; timestamps and explicit unverified checks |
| timestamped advertising reference breakdown or ad review: copy, persuasion, visual construction and CTA | video-creator: analyze-ad | <=60 seconds, kind="work"; overview, bounded dense windows and native copy evidence; optional retained report; not factual/provenance/performance verification |
| exact-copy advertisement from approved product/logo/media assets | video-creator: create-ad | 6..30 seconds, 30fps; aspect 9:16 (default), 16:9, 1:1 or 4:5; native canvas per plan, no automatic crop/scale; kind="work", content-plan then preview approval; no generation/TTS/capture |
| a UI task walkthrough: recreate from reference/design/text, edit supplied local footage, or record an approved sanitized Web demo | video-creator: create-tour | free, <=60 seconds; task-local source/preview/MP4, always kind="work"; free-text intro/outro default ON; explicit mode/proposal/scope gates, isolated Web wrapper only; native capture/login/privacy redaction unavailable; optional finished audio-creator WAV/words.json |
| a bounded local-authored explanation of a topic for an audience with a learning_goal | video-creator: create-explainer-video | free, 1..180 seconds, always kind="work"; explicit v1 HyperFrames or v2 Motion Canvas render (never a silent switch; an old v1 Motion Canvas discussion-only proposal needs a fresh v2 proposal and approval), 16:9 (1280x720)/9:16 (720x1280) at 30fps; framing none/bust/full separate from performance still/puppet/animated and lip_sync off/cues/baked; missing character/script/grounding/audio inputs return as dependency requests, never invented; propose/freeze/snapshot/render mirrors Tour/Ad's proposal-then-approval shape |
| a house-voice or registered-character spoken line from an approved script (up to 600 characters), as narration or a voice message | audio-creator: generate-speech | free of provider cost, NOT free of an attempt allowance: 1 take + 1 corrective per script by default, counting every synthesis call including failures; house uses the language fallback chain, a qualified `<engine>:<voice>` id never falls back |
| concatenation, boundary trim, speed, loudness normalization or format conversion of existing speech | audio-creator: edit-speech | free of generation; no resynthesis, no word changes, no voice conversion |
| findings on an existing speech file against a destination format, with optional script readback | audio-creator: analyze-speech | free; measured and readback evidence only, never a listening verdict; deliver may be omitted |
| a deterministic short UI/game sound from a closed set of eight local kernels (click, beep, chime, whoosh, riser, pop, ui-tick, noise-burst) | audio-creator: create-sfx | free, zero model, no network call; a described real-world sound routes to generate-sfx instead |
| a described real-world or complex sound effect, default engine | audio-creator: generate-sfx (local Stable Audio 3 Medium, engine omitted) | free ($0), no paid approval needed; takes a seed (default 0), rejects loop/prompt_influence outright; still bounded by an attempt cap (default 3 variants + 1 corrective, hard cap 8) |
| the same, via the explicitly chosen paid engine (loop or prompt-adherence control needed) | audio-creator: generate-sfx (`engine: fal:elevenlabs-sfx-v2`) | metered; explicit current-work paid approval of engine/prompt/seconds/loop/attempt cap (default 3 variants + 1 corrective) and a USD estimate before any spend; no seed, no local fallback |
| trim / pitch shift / reverse / pad / fade / true-peak normalize / format-convert of an existing SFX file | audio-creator: edit-sfx | free; preserves the original, never re-synthesizes |
| findings on an existing SFX file's format, loudness, clipping and silence | audio-creator: analyze-sfx | free; measured findings only, never a listening verdict; deliver may be omitted |
| a deterministic instrumental cue composed of five closed electronic waveforms (sine/triangle/pulse/fm-bell/noise), from an authored score | audio-creator: create-music | free, zero network calls; instrumental BGM/melodic opener-closer only, at most 60s; two-round proposal-then-approval gate |
| a described instrumental cue/BGM in real-world/sampled instrumentation, default engine | audio-creator: generate-music (local Stable Audio 3 Medium, engine omitted) | free ($0), no paid approval needed; takes a seed (default 0); two-round proposal-then-approval gate; default attempt cap 2 variants + 1 corrective, hard cap 8 |
| the same, via the explicitly chosen paid engine | audio-creator: generate-music (`engine: fal:stable-audio-3-medium`) | metered; explicit current-work paid approval of engine/prompt/duration/seed/attempt cap/USD estimate before any spend; no local fallback |
| trim / loop-crossfade / fade / gain / two-pass LUFS normalization of an existing music file | audio-creator: edit-music | free; preserves the original, never resynthesizes |
| tempo/beat/key/structural-boundary findings on an existing music file, standalone or from this pipeline | audio-creator: analyze-music | free; measured/estimated findings only with half/double BPM and key ambiguity disclosed, never a listening, genre, mood, instrument, lyrics or vocal-performance verdict; deliver may be omitted |
| already-finished speech/sfx/music sources placed on a shared timeline with authored gain/fade/envelope automation, from a one-sentence purpose and plain-language direction | audio-creator: create-mix | free; two-round proposal-then-approval gate, zero-render `proposal-v<N>/proposal.md` first, renders locally only after Creator relays approval; no new synthesis, looping, EQ, reverb or source separation |
| revision of an existing frozen mix bundle from a plain-language change request | audio-creator: edit-mix | free; loads the frozen sources and previous spec, authors a full revised plan; same two-round proposal-then-approval gate; a FAILed bundle cannot be revised; original sources are preserved, never re-synthesized |
| measured findings on an existing mix — format/loudness/clipping/true-peak, and with its own bundle the recorded source/cue placement from mix.json | audio-creator: analyze-mix | free; findings only, no deliverable file, deliver may be omitted; not a listening/perceptual verdict, not repair, not a fresh ASR pass over the mixed master |

Ad means a specific audience, promise and intended action. PV primarily
introduces qualities/experience/world: neither duration nor a CTA alone decides.
Only create-ad and analyze-ad are served; generate-ad and a PV leaf are not yet
implemented. Never silently route a requested generated ad to MV or create-ad.
Technical-only checks stay analyze-clip even for its what_for: ad option.

The clip, MV and explainer-video scopes above are served, not the whole
former generated-video technic. create-explainer-video's HyperFrames- or
Motion-Canvas-authored scope does not retire `creator-manim-explainer` for
explicit Manim or its existing mathematical/3D animation scope. An
unsupported renderer request is a capability finding, not permission to
substitute Manim, HyperFrames or Motion Canvas for one another.
Named legacy methods below (ComfyUI, authored HTML motion, grid-exact
pixels, montage/audio assembly) remain available for requests
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
| historical OG/social/title-card dispatch identity | `creator-text-card` | retained mapping only; new Card work uses hands FIRST; no fallback after a Card failure |
| classic-template or custom-scene meme with deterministic captions | `creator-meme` | sourced template or separately budgeted generated background; provenance required |
| static banner, framed/message art, image conversion, or sourced ASCII art | `creator-ascii-art` | deterministic UTF-8 text master; ANSI only when requested |
| existing reaction or communication GIF sourced from Tenor | `creator-gif-sourcing` | retrieval with provenance and rights caveat; never asset generation |
| generated video outside the served clip/MV contracts, notably an explicitly requested local ComfyUI workflow | `creator-generated-video` | retained until coverage is migrated; core short shots use generate-clip and bounded MVs use generate-music-video; no silent backend substitution |
| deterministic motion graphics, product/site tours, overlays, or captioned video authored in HTML/CSS/JS | `creator-html-motion` | HyperFrames source project + MP4/WebM; supporting generation is separately budgeted |
| generative art, interactive canvas/WebGL experience, custom data visual, or p5.js export | `creator-p5js-experience` | seeded browser-native source; PNG/GIF/MP4/SVG are optional exports |
| video-to-ASCII, audio-reactive, generative, hybrid, lyric, or TTS-backed ASCII motion | `creator-ascii-video` | deterministic Python/ffmpeg render; supporting generation/TTS is separately budgeted |
| mathematical, algorithmic, data, paper, or 3D educational animation | `creator-manim-explainer` | deterministic Manim render; supporting TTS is separately budgeted |
| still sprite, avatar, icon, logo reduction, or scene on a pixel grid | `creator-pixel-art` | native master + nearest-neighbor preview |
| sprite/cel animation, procedural pixel loop, pixel MP4/GIF | `creator-pixel-video` | deterministic native-grid animation; never ordinary AI video |
| educational, biography, or tutorial comic with storyboarded panels | `creator-knowledge-comic` | metered page art + deterministic lettering; multi-page work uses the plan/anchor gate |
| official third-party logo/mark acquisition and provenance | `creator-brand-asset-sourcing` | source, do not redraw |
| assembly of QA-passed parts — mux, concat, mix, overlay, trim, re-container per a fixed edit spec | `creator-media-assembly` | deterministic ffmpeg; parts consumed verbatim; zero generation spend |

Spoken lines with a durable deliverable route to the hands above
(audio-creator: generate-speech / edit-speech / analyze-speech); only an
ordinary conversational spoken reply that is not a delivered asset still
identifies as `core:tts`. `creator-html-motion` consumes a finished
narration file from audio-creator as an input rather than synthesizing
speech itself; its `media-use` support remains an implementation engine
for its own non-speech asset/caption handling. Short sound effects route
to audio-creator's create-sfx / generate-sfx / edit-sfx / analyze-sfx,
and instrumental music routes to its create-music / generate-music /
edit-music / analyze-music, both above; the technic table below carries
no SFX- or music-production entry. Vocal-song generation and standalone
audio visualization remain withdrawn without a hands replacement — a
request for either is `no skill fits`, never routed to a core/external
route as a stand-in. Other niche assets may use an `external:<skill>`
identity only after an availability preflight.

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
   audio-reactive ASCII render is `creator-ascii-video`. A delivered speech
   asset routes to audio-creator's generate-speech (`core:tts` only for an
   undelivered conversational reply); a short sound effect routes to
   audio-creator's create-sfx (closed local kernel) or generate-sfx
   (described sound, local Medium default at $0, or explicit paid fal on
   request); a short instrumental cue routes to audio-creator's
   create-music (closed five-waveform score) or generate-music (described
   real-world/sampled instrumentation, local Medium default at $0, or
   explicit paid fal on request). Lyrics-to-song generation and standalone
   audio visualization remain withdrawn without a hands replacement —
   `no skill fits`, never a fallback to a technic, core route, or external
   skill.
4. Stack a supporting technic only when the brief truly spans methods.
   Generated backdrop plus exact card copy is ONE generate-card form, not
   creator-generated-image + creator-text-card. Text-free illustrations alone
   remain legacy generated-image. A static card is not an infographic or deck.
5. The task body's `Technique:` is a request. Validate it against this table;
   correct an objective mismatch in `STATE:`, and block only when the choice
   changes user intent or spend.
6. A canonical leaf may load an official skill from `external_dirs` as its
   implementation engine. Report the canonical leaf as `capability` and the
   official skill plus concrete tool/path as `backend`; never expose the
   engine's bare name as the stable dispatch identity.
7. Bounded UI task walkthroughs select create-tour before the legacy table;
   this new subject does not retire creator-html-motion or its 1:1 mapping.
   Route by authorship method as well as container. A model-generated MP4 is
    `generate-clip` within its short-shot contract; a requested legacy
      backend stays `creator-generated-video`. Short model-generated MV progression
    uses `generate-music-video`, even with several generated cuts; it does not route
    through generate-clip or guarantee exact music/lettering. Broader seekable HTML motion is
   `creator-html-motion`; p5.js canvas/WebGL work is
   `creator-p5js-experience`; mathematical teaching animation is
   `creator-manim-explainer` unless the request is a bounded
   topic/audience/learning_goal explanation authored through HyperFrames or
   Motion Canvas, which is `create-explainer-video` instead. A UI task walkthrough is
   `create-tour`, not `create-explainer-video`, even when it explains a
   feature; an explainer is never routed to a generated MV or clip merely
   because it has motion.
8. ComfyUI is an implementation backend, never a canonical capability. An image
   generated through it remains `creator-generated-image`; a clip remains
   `creator-generated-video`. Use only the Backend approved in the MediaBrief.
   `core:image_generate` / `core:video_generate` may use their configured
   in-chain fallback. `external:comfyui` stops on failed preflight or execution
   and returns the finding; it never crosses to a core/cloud backend silently.

## Capability handshake

Card destinations share one subject, not separate leaves. X article's 5:2
recommendation is USER VERIFIED; its 1500x600 pixels are chosen defaults.
X pair's 7:8 tiles remain UNVERIFIED CANDIDATES. Carousel portrait/square and
3/4 counts are authoring options; only 3-image scrolling is user-observed.
Gap previews simulate a configurable gap, never claim a measured X gap.
Retirement gate: retain creator-text-card files and private-overlay 1:1 mappings
until discovery/handoff coverage, generated-backdrop paid validation and legacy
call-site migration have been proven. Do not break the generic validator or
delete mappings merely because the new served route exists.

Before production, `STATE:` or the first `PROGRESS:` must include:

```text
capability: <creator-leaf>@<version> | external:<skill>
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
