# MediaBrief — the released unit's spec (validation contract)

The assistant fixes every deliverable-defining decision in its own
planning layer and releases it here as the unit's spec; Creator never
sees the originating chat. This reference is the single intake contract
for all creator technics, and it validates **completeness** — decision
guidance lives with the assistant, not here. A leaf technic validates its
family fields but does not invent a second brief schema, and never
decides an open field (kernel <UnitDiscipline>).

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
- **Inputs** - attached source assets, QA-passed part paths, and
  previous-card/anchor pointers.
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
Do not infer a platform spec from habit when the repository states one — and
when a discovered fact CONTRADICTS the released spec (the component crops
square, the spec says 16:9), that is a finding back to the assistant, not a
silent correction.

## Family field checklists

Field names only — each arrives decided in the spec. An unsettled field is
a spec gap for the single batched `Q<n>:` round; never a local default.

- **Image**: rendered ratios + crop behavior (`cover`/`contain`/fixed);
  format; alpha/background rule; size cap; brand/style inputs; exact text
  separated from generated artwork.
- **Video**: duration; aspect/resolution; container/codec; size cap;
  autoplay/mute/loop/playsinline/poster contract; source stills or
  reference frames; one motion statement; audio requirement + backend
  capability constraint.
- **Interactive/browser**: target browsers/devices; viewport + pixel
  density; responsive behavior; interaction methods + accessibility
  fallback; reproducibility seed/parameters; performance floor;
  offline/CDN policy; runnable source + requested exports.
- **Generated audio/music**: mode (instrumental / melody / style /
  ambience-SFX / vocal song); duration; structure/sections;
  mood/genre/instrumentation; prohibited styles and living-artist/voice
  imitation; exact approved lyrics + tags for songs (lyric writing routes
  to writer); model/version + seed/sampling parameters; conditioning
  sources + their rights; output format, sample rate, channels, loudness;
  looping/fades; render cap + runtime ceiling + CPU-fallback and
  model-download authorization.
- **Voice**: exact script; language + pronunciations; voice identity +
  pacing; output format, sample rate, channels, loudness; duration
  target; file count (each file is one Budget asset); standalone vs
  composite-part role.
- **Pixel**: native grid + integer-scale destination; fixed palette or
  cap + transparency; still vs animation, effective fps, loop; protected
  cells/regions; master vs compatibility outputs; supplied source =
  reduction target vs visual reference.
- **Assembly**: part inventory (QA-passed durable paths); the edit spec
  (cut list/order + timecodes, sync points, transitions, mix
  levels/ducking, overlay placement/timing); output contract; re-encode
  policy (parts consumed verbatim).

## Missing fields

Fill low-risk destination defaults only when the platform contract makes
them objective, and state them. Any missing choice that changes subject,
style, motion, spend, or source fidelity is the assistant's decision: it
goes through the kernel's single batched `Q<n>:` block. Never let a
technic call `clarify` inside a worker run.
