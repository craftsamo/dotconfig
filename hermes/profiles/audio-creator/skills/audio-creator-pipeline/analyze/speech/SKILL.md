---
name: analyze-speech
description: >-
  Inspect an existing spoken-audio file for format, loudness, clipping,
  silence and optional script readback. Return findings, not a new asset.
  Not listening-based performance certification, song analysis or repair.
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
        label: "one local speech audio file, at most 600 seconds"
      script:
        required: false
        type: file
        label: "approved UTF-8 words for readback; without it script fidelity is unverified"
      what_for:
        required: false
        options: [narration-track, voice-message, dialogue-line]
        other: true
        label: "destination determines blocking format checks; omit for descriptive measurements"
      language:
        required: false
        label: "ASR language code, omit for detection"
      prosody:
        required: false
        options: ["yes", "no"]
        label: "yes adds per-segment pitch and level with jump candidates (measured, for listening); default no"
      note:
        required: false
        type: text
---

<Procedure>

1. Read the form and approved script if supplied. Never modify the input or
   create a deliver directory. Run:

   ```sh
   hermes-python "${HERMES_SKILL_DIR}/../../scripts/speech-media.py" analyze <source>
   ```

   Add `--script-file <path>` and `--language <code>` only when supplied,
   and `--prosody` when `prosody: yes`.
   Text stays in files. Use a resident session/background polling when ASR
   would exceed the reply window; do not install/download a missing model.
2. Read the whole `RESULT:` JSON even on a readback failure. Distinguish
   source `input_measure` from the mono analysis decode in `measure`.
   Stereo downmix cannot prove either original channel is unclipped.
   Original-format facts come from input metadata, not the analysis WAV.
3. Build a findings table: check, evidence, PASS/WARN/FAIL/unverified, proposed
   next action. Normalized text equality is not a pronunciation verdict.
   Japanese coverage cannot excuse omitted foreign words. ASR substitutions
   need review, not automatic rewriting of the approved script.
4. With `prosody: yes`, read `prosody`: per ASR segment, the median pitch in
   semitones from the file's median and the voiced level, and `candidates`
   where pitch or level jumps from the previous segment or sits well above
   the file. Report each candidate as one line,
   `m:ss | voice | <reasons> (ASR: <segment text>) | prosody | confirm`,
   with `m:ss` the segment start floored to whole seconds (12.64 → 0:12)
   and the ASR text flattened to one line, and say that music under the
   voice and a change of speaker also move these numbers.
   `status: unmeasured` is a gap, not a pass.

</Procedure>

<QA>

- Full decode/nonempty/non-silent is blocking for every destination. Clipping
  and unexpectedly long boundary silence are findings with numbers.
- `narration-track`: mono 48 kHz PCM WAV is the format contract. `voice-message`:
  mono 48 kHz Opus Ogg. `dialogue-line`: inspect duration and script match;
  format depends on the client's use. Unknown use has no invented format cap.
- Report measured LUFS/true peak descriptively; -16 LUFS/-1 dBTP are suggested
  edit targets, not universal delivery requirements. Nonfinite/silent loudness
  is unmeasurable, never zero. Mark downmixed sample/peak evidence as such.
- With a script, quote readback, transcript and CPS; without one, no fidelity
  PASS. Listening, emotion, identity and pronunciation are always unverified.
- Prosody numbers are measurements and its candidates are places to listen;
  never call a delivery too excited, flat or unnatural from them.
- No finding without named measurements or a disclosed limitation. No new
  speech, normalization, trim or output file is allowed during analysis.

</QA>

<Report>

Return `analyze-speech`, the source, findings table and blocking defects first,
then the prosody candidate lines when requested, then proposed
edit-speech/generate-speech handoffs (not execution). State the
perceptual gap and `spend: free; takes 0`. No delivery path is required.

</Report>
