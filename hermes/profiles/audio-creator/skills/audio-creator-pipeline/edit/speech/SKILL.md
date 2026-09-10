---
name: edit-speech
description: >-
  Edit existing speech: concatenate ordered tracks, trim boundary silence,
  adjust speed, normalize loudness or convert format. Preserve originals and
  deliver a new mono WAV with updated timing sidecars. Not resynthesis,
  rewriting words, voice conversion, denoising, music mixing or video muxing.
version: 1.0.0
metadata:
  hermes:
    category: hands
    hands: audio-creator
    cost: free
    output: "new speech_<slug>.wav + .words.json + .srt + .take.json; optional .ogg/.mp3"
    form:
      source:
        required: true
        type: path
        label: "one audio file, or directory for concat; max 64 inputs and 600 seconds total"
      order:
        required: false
        type: file
        label: "UTF-8 file with one absolute audio path per line in approved concat order; required for a directory source"
      operations:
        required: true
        options: [concat, trim, speed, normalize, convert]
        other: true
        label: "comma-list; applied in fixed order concat,trim,speed,normalize,convert; trim removes boundary silence only"
      target_lufs:
        required: false
        label: "normalize target, finite -36 to -5, default -16 LUFS; true-peak target -1 dBTP"
      gap_ms:
        required: false
        type: int
        label: "concat gap in milliseconds, 0-10000, default 200; not for other operations"
      speed:
        required: false
        label: "speed multiplier 0.25-4, default 1; requires speed operation, preserves pitch"
      format:
        required: false
        options: [wav, ogg, mp3]
        label: "convert target; WAV master always retained, default wav when convert is requested"
      script:
        required: false
        type: file
        label: "approved combined transcript; otherwise inherit only complete verified source sidecars"
      language:
        required: false
        label: "ASR language code; omit for detection"
      slug:
        required: false
        label: "lowercase ASCII filename slug, default speech"
      note:
        required: false
        type: text
---

<Procedure>

1. Validate the operations and their parameters. A directory never implies
   sorting: read the approved `order` file and confirm every entry is a local
   audio file in that directory. Pass paths as separate quoted arguments,
   never an eval/inline shell loop. Multiple inputs require `concat`. Reject
   contradictory/inapplicable options and requests outside this leaf.
2. Use a fresh bundle below `deliver`, never overwrite inputs or prior takes.
   Run the shared helper through the Hermes venv:

   ```sh
   "$(ghq root)/github.com/NousResearch/hermes-agent/venv/bin/python" "${HERMES_SKILL_DIR}/../../scripts/speech-media.py" edit <source-1> <source-2> --out <new-bundle-dir> --slug <slug> --operations <comma-list>
   ```

   Use one input without concat. Add only applicable flags: `--target-lufs`,
   `--gap-ms`, `--speed`, `--format` (required for convert, default wav),
   `--script-file` and `--language`. Keep text in files. Long work runs with
   `background: true` and polling. Never re-run a still-running process.
3. Order is fixed: concat, boundary trim, pitch-preserving speed, two-pass
   loudness normalization, derivative conversion. Interior pauses remain.
   Mono 48 kHz PCM is the master; stereo preservation is outside this leaf.
   Silence without finite loudness is not normalizable. Existing malformed
   or stale timing sidecars are a finding; do not delete them to bypass it.
4. Unchanged timing reuses validated sidecars and shifts concat timestamps by
   decoded durations plus the gaps. Trim/speed or missing sidecars requires
   fresh local ASR. Without a complete approved script, captions are marked
   transcript-derived and textual fidelity stays unverified. Do not replace
   that missing script with your own writing. No new synthesis is allowed.

</Procedure>

<QA>

- Quote the actual operations, input order and resulting duration; for concat
  verify the second track starts after the first duration plus its gap.
- Full decode, positive non-silent mono 48000 Hz PCM master, no clipped
  samples. With normalize, actual LUFS must be within 0.7 of target and true
  peak <= -0.7 dBTP; otherwise report FAIL, not a claimed target as measurement.
- Check derivative codec/rate/channels and its separately measured peak;
  lossy encoding can change peaks. Flag a derivative above -0.7 dBTP.
- Quote readback WARN/FAIL and CPS warnings. Timing is estimated, within the
  new duration. Changed audio never carries stale synthesis identity claims.
- Originals and older bundles remain unchanged. Listening/performance and
  pronunciation remain unverified, even when every mechanical check passes.

</QA>

<Report>

Return `edit-speech`, absolute output paths, input order, operations, actual
measurements, sidecar reuse/re-ASR result and every QA gap. `spend: free;
takes 0`. An unresolved defect is a finding, not silent resynthesis.

</Report>
