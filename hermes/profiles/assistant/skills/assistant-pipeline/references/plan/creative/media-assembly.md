# Media assembly — decision surface

Deterministic combination of **QA-passed parts**: mux voice onto
video, concat scenes, mix music beds, overlay captions/logos, trim
and re-container for a destination. No creative generation — a part
that needs changing goes back to its own family unit, never gets
"fixed" during assembly.

Technic `creator-media-assembly` · QA `assembly` · deterministic
ffmpeg work, zero generation spend · resident-only.

## Fix before release

- The part inventory: every input by durable path, each already
  through your QA gate — an assembly unit with an ungated input is
  not releasable (`composite-media.md` owns the sequencing).
- The edit spec, exact: cut list/order with timecodes, sync points
  (voice-to-scene alignment), transitions (cut/crossfade +
  durations), audio mix (levels, ducking, fades), overlay
  placement/timing.
- The output contract: container/codec, resolution/aspect,
  duration, size cap, loudness target — and which intermediates (if
  any) ship alongside the master.
- Re-encode policy: parts are consumed verbatim; any transform
  beyond the edit spec (a crop, a speed change) is a spec change
  that comes back to you.

## Defaults

- Anchor: none — determinism replaces it; a draft low-res assembly
  may precede the final render for long edits.
- Budget shape: zero generation; iteration is turns. Defective
  parts discovered here are findings routed back to their family
  unit with the evidence.
