# MediaBrief - shared intake contract

The Assistant writes the card body; Creator never sees the originating chat.
This reference is the single intake contract for all creator technics. A leaf
technic validates its medium-specific fields but does not invent a second
brief schema.

## Common fields

- **Purpose and audience** - what the viewer should understand, feel, or do.
- **Deliverable** - asset types, count, and whether files or media judgment are
  requested.
- **Destination** - platform/placement, display context, and where outputs land.
- **Specifications** - dimensions/aspect, format/container, size cap, duration
  and playback contract where applicable.
- **Creative direction** - style, tone, palette, brand assets, exact references,
  and prohibited motifs.
- **Technique** - canonical creator technic when known. It is a routing request,
  not permission to skip capability validation.
- **Inputs** - attached source assets and previous-card/anchor pointers.
- **Invariants** - what a revision or animation must preserve unchanged.
- **Budget** - generation caps; absent means the kernel defaults.
- **Review** - required gate and what evidence must be shown.
- **Done criteria** - observable acceptance checks, not "looks good" alone.

## Destination discovery

Use evidence in this order: task/card attachments and explicit user facts,
destination code/config, brand/design docs, then one batched question round.
Record discovered facts in the first `STATE:` or `PROGRESS:` comment.

For a codebase-backed destination, inspect the actual rendering component,
schema/upload constraints, design tokens, existing media, and storage path.
Do not infer a platform spec from habit when the repository states one.

## Image additions

- all rendered ratios and crop behavior (`cover`, `contain`, fixed),
- target format, alpha/background rule, and file-size cap,
- brand colors, typography, logo source, and existing visual language,
- exact text separated from generated artwork.

## Video additions

- duration, aspect/resolution, container/codec, and file-size cap,
- autoplay/mute/loop/playsinline/poster requirements,
- source still/reference frames and one motion statement,
- audio requirement and backend capability constraints.

## Interactive/browser additions

- target browsers/devices, viewport and pixel density, responsive behavior,
- interaction methods (mouse, touch, keyboard, mic) and accessibility fallback,
- reproducibility seed/parameters, performance floor, and offline/CDN policy,
- runnable HTML/source assets plus any still, vector, GIF, or video exports.

## Generated audio/music additions

- mode (instrumental, melody/style-conditioned, ambience/SFX, or vocal song),
- duration, structure/sections, mood/genre/instrumentation, and prohibited style
  or living-artist/voice imitation,
- exact approved lyrics and tags for songs; lyric writing routes to writer,
- model/version, seed/sampling parameters, conditioning sources and their rights,
- output format, sample rate, channel layout, loudness/peak, looping/fades, and
  whether a qualified listen-through is part of Review,
- generated-audio/song render cap, hardware/runtime ceiling, and permission for
  any model download or environment change.

## Voice additions

- exact script, language, pronunciations, voice identity, and pacing,
- output format, sample rate, channel count, loudness, and duration target,
- requested file count (each output file is one voice asset for Budget),
- whether voice is standalone or supports a video/animation deliverable.

## Pixel additions

- native grid and integer-scale destination,
- fixed palette/palette cap and transparency,
- still vs animation, effective fps, loop requirement, and protected cells,
- master vs compatibility output and whether a supplied source is a reduction
  target or only a visual reference.

## Missing fields

Fill low-risk destination defaults only when the platform contract makes them
objective, and state them. Any missing choice that changes subject, style,
motion, spend, or source fidelity goes through the kernel's single batched
`Q<n>:` block. Never let a technic call `clarify` inside a worker run.
