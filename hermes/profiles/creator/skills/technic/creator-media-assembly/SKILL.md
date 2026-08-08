---
name: creator-media-assembly
description: >-
  Creator's deterministic leaf technic for assembling QA-passed parts into a
  composite deliverable: mux, concat, mix, overlay, trim, and re-container per
  a fixed edit spec, with verbatim part consumption and measurable join QA.
version: 1.0.0
author: CraftSamo
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [creator, technic, assembly, edit, ffmpeg, mux, composite]
    category: technic
---

<Goal>

Combine verified parts into exactly the composite the edit spec describes —
no creative interpretation, no part "improvement". The canonical dispatch
identity is `creator-media-assembly`; ffmpeg and the bundled scripts are the
implementation engine. Assembly is where composites become real: its value is
fidelity, sync, and clean joins, all measurable.

</Goal>

<Scope>

Use when the deliverable combines existing verified media: voice over scenes,
scene concatenation, music beds and ducking, caption/logo overlays, trims, and
destination re-containering. Do not use to create content — generation routes
to the part's canonical technic; authored motion to `creator-html-motion`;
pixel encoding to `creator-pixel-video`. Editing a user-supplied video without
any generation is this technic.

</Scope>

<Inputs>

The assembly spec must provide: the part inventory (QA-passed durable paths),
the edit spec (cut list/order with timecodes, sync points, transitions with
durations, audio mix levels/ducking/fades, overlay placement and timing), the
output contract (container/codec, resolution/aspect, duration, size cap,
loudness target), and the re-encode policy. An input not in the inventory, or
an open edit decision, is a spec gap — never a local call.

</Inputs>

<Contract>

- `creator-pipeline` owns MediaBrief, Budget, Q<n>, Review, V1-V6, and
  delivery. Assembly has zero generation spend.
- **Parts are consumed verbatim.** Decode/re-encode only as the edit spec
  requires for the output contract; never regenerate, re-crop, retime, color-
  grade, or denoise a part beyond the spec. A defective part is a finding
  back through the pipeline reply — the fix belongs to the part's own unit.
- Record every input's path and a content hash before work; the report maps
  each inventory part to its place in the output.
- Never install dependencies. Missing `ffmpeg`/`ffprobe`, an unreadable part,
  or a part failing its declared container check blocks production.

</Contract>

<Procedure>

1. Inventory: verify every part path exists, decodes (`ffprobe`), and matches
   its declared role; record hashes and stream properties. Reconcile the
   inventory against the edit spec — an orphan part or an unfed slot blocks.
2. Save the assembly as a task-local script (filtergraph/concat file included;
   no inline interpreters) so the exact edit is reproducible.
3. For long or complex edits, render a low-res draft first and inspect the
   joins and sync before the full-quality render.
4. Render the final to the output contract. Keep the parts untouched; keep
   the script and intermediates in the workspace, out of the delivery.
5. Verify: probe the output (streams, duration, resolution, codec, size,
   loudness); sample frames around every cut/transition timecode; check each
   sync point (voice-to-scene via transcript timing, music ducking, overlay
   timecodes); check the loop wrap when specified.

</Procedure>

<Verification>

- Every inventory part appears in the output exactly where the edit spec
  places it; nothing was silently dropped, reordered, or altered beyond the
  spec — spot checks against the source parts confirm fidelity.
- Output contract measured, not eyeballed: container, codec, dimensions,
  duration, fps, size cap, loudness.
- Every join sampled (no glitch/dup/dropped frames; transitions match type
  and duration); named sync points verified with evidence.
- The assembly script, part inventory with hashes, and probe/QA evidence are
  preserved for the pipeline's V1-V6 handoff; only the final (and requested
  derivatives) are delivered.

</Verification>
