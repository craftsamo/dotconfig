---
name: analyze-mix
description: >-
  Inspect an existing mix locally: format/loudness/clipping/true-peak
  measurements, and, when its own bundle is supplied, the actual
  recorded spec (source/cue placement) from that bundle's mix.json.
  Returns findings only, never a new or modified file. Works on any
  finished mix, not only this pipeline's own deliveries. Not a
  listening/perceptual verdict, not repair, and not a fresh ASR pass
  over the mixed master.
version: 1.0.0
metadata:
  hermes:
    category: hands
    hands: audio-creator
    cost: free
    output: "findings in the reply; no deliverable file, deliver may be omitted"
    form:
      source:
        required: true
        type: file
        label: "one local finished mix audio file, at most 600 seconds and 128 MiB"
      bundle:
        required: false
        type: path
        label: "optional PASS/WARN mix bundle directory; when given, source must be byte-identical to that bundle's own delivered master (hash-verified) - a different file with someone else's bundle is refused"
      focus:
        required: false
        type: text
        label: "overview (default) or a custom focus in words, e.g. loudness, placement, technical; shapes the report only, never a helper flag"
      note:
        required: false
        type: text
---

<Procedure>

1. Read the form. Never modify `source` or `bundle`, and never create a
   `deliver` directory - this leaf produces no file. Run:

   ```sh
   ~/ghq/github.com/NousResearch/hermes-agent/venv/bin/python "${HERMES_SKILL_DIR}/../../scripts/mix-media.py" analyze <source> [--bundle <bundle>]
   ```

   Do not use command substitution in executable paths; if `ghq root`
   differs on this machine, resolve it with a separate `ghq root` call
   first and then invoke the literal absolute Python path. This runs
   entirely locally - no upload, no re-synthesis, no ASR is ever run on
   the mixed master by this leaf.
2. Read the whole `RESULT:` JSON. Without `bundle`, findings are
   audio-only measurements (format, duration, channels, peak/true-peak,
   clipping, integrated LUFS) with no claim about which cue or source
   produced any section. With `bundle`, the helper first verifies the
   bundle is a complete PASS/WARN delivery and that `source`'s bytes
   hash-match its own delivered master exactly - report a refusal
   rather than substituting a different file's audio for that bundle's
   spec - then additionally returns the recorded spec (`sources`/`cues`
   placement, `what_for`/`direction`) from that bundle's `mix.json`.
   Captions provenance is not part of this leaf's output even with a
   bundle; use the bundle's own `captions.json` directly for that. None
   of this is a claim that the audio was listened to.
3. `focus` only shapes which findings the report leads with (e.g.
   loudness, placement, technical); it is never forwarded to the
   helper as a flag (there is no such CLI flag), and an omitted `focus`
   gets the default overview.

</Procedure>

<QA>

- Full decode and nonempty audio are required; silence/low signal is a
  valid finding, not a request to render a new mix. Whole silence is
  flagged explicitly.
- Measured peak/true-peak/clipping/LUFS keep their actual numbers; a
  short/ungated clip's missing integrated LUFS is a disclosed
  limitation, not a defect.
- Recorded spec/placement findings are only ever reported when `bundle`
  was supplied AND `source` hash-matched that bundle's own delivered
  master - never inferred from the audio alone, and never reported
  against a `source` that turned out to differ from the bundle.
- No listening/perceptual verdict is ever claimed, even when several
  measurements point the same direction.

</QA>

<Report>

Return `analyze-mix`, the source (and bundle, if supplied and matched)
and the findings: measured facts always, plus the recorded spec
(source/cue placement) when a matching bundle was given. Separate
measured from unavailable/unverified items clearly. State `spend:
free`; no delivery path required. Propose `create-mix`/`edit-mix` as
separate next steps rather than executing one.

</Report>
