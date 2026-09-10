---
name: edit-sfx
description: >-
  Edit one existing SFX file: trim, pitch shift, reverse, pad both ends,
  fade, true-peak normalize or convert format. Preserves the original and
  delivers a new 48 kHz master. Not resynthesis, loop-to-length stretching,
  music/mix, or concatenation of multiple sources.
version: 1.0.0
metadata:
  hermes:
    category: hands
    hands: audio-creator
    cost: free
    output: "new sfx_<slug>.wav + .take.json; optional .mp3/.ogg"
    form:
      source:
        required: true
        type: file
        label: "one local audio file, at most 22 seconds and 16 MiB"
      start:
        required: false
        type: text
        label: "trim start, seconds, 0 to end; default 0 (no trim start)"
      end:
        required: false
        type: text
        label: "trim end, seconds, 0 to source duration; default the full source"
      pad_ms:
        required: false
        type: int
        label: "silence added to BOTH the start and end, 0-10000 ms; default 0"
      fade_in_ms:
        required: false
        type: int
        label: "fade-in length after padding, 0-22000 ms; default 0"
      fade_out_ms:
        required: false
        type: int
        label: "fade-out length after padding, 0-22000 ms; default 0"
      pitch_semitones:
        required: false
        type: text
        label: "-24 to 24 semitones; asetrate+aresample, so this CHANGES duration (no tempo preservation)"
      reverse:
        required: false
        options: [no, yes]
        label: "reverse the sample order after trim/pitch"
      target_peak:
        required: false
        type: text
        label: "true-peak normalization target in dBTP, -30 to -1; omit to leave loudness untouched — there is no hidden default target"
      format:
        required: false
        options: [wav, mp3, ogg]
        label: "derivative format to also write; the WAV master is always kept regardless"
      slug:
        required: false
        label: "lowercase ASCII filename slug; default sfx"
      note:
        required: false
        type: text
---

<Procedure>

1. Confirm at least one operation was actually requested (trim, pitch,
   reverse, pad, fade, normalize, or a non-wav format) — a form with no
   nondefault control is refused rather than producing a byte-identical
   copy. This leaf takes exactly one `source`; a multi-file mix or a
   concatenation request does not fit here.
2. The operations always apply in this FIXED order regardless of the
   order fields were given: **trim, pitch, reverse, pad, fade,
   peak-normalize, convert**. Document that order back if the request
   assumed a different sequence (e.g. "fade then trim" is not honored).
   Padding with `pad_ms` always adds silence to BOTH ends, never one.
   `pitch_semitones` changes duration (asetrate+aresample, no tempo
   preservation) — if the edited clip feeds a video/timed asset, a pitch
   change needs a fresh downstream duration approval, not a silent
   re-sync. Loop-to-length stretching, music mixing and multi-track
   assembly are out of scope for this leaf.
3. Run through the Hermes venv Python:

   ```sh
   ~/ghq/github.com/NousResearch/hermes-agent/venv/bin/python "${HERMES_SKILL_DIR}/../../scripts/sfx-media.py" edit <source> --out <deliver>/take-01 --slug <slug> [--start S] [--end E] [--pad-ms N] [--fade-in-ms N] [--fade-out-ms N] [--pitch-semitones N] [--reverse] [--target-peak N] [--format wav|mp3|ogg]
   ```

   Do not use command substitution in executable paths; if `ghq root`
   differs on this machine, resolve it with a separate `ghq root` call
   first and then invoke the literal absolute Python path — never repeat
   the model generation to fix a packaging step. (Actual live failure:
   "Nested executable body could not be resolved.")

   Add only the flags the form actually set; never invent a
   `--target-peak` — normalization is always an explicit ask, there is no
   hidden default target applied silently. `--target-peak` accepts at
   most -1 dBTP; the source must decode to <=22s and <=16 MiB or the
   helper refuses before writing anything.
4. Never overwrite the source or a prior bundle; each run uses a fresh
   `--out`. `intent: revise` reruns with the changed control(s) only.

</Procedure>

<QA>

- Quote the actual operations applied, in the fixed order, and the
  resulting duration; a `pitch_semitones` edit's duration ratio must
  match `2 ** (-semitones/12)` (report the measured value).
- Full decode, positive non-silent PCM master, correct channel count;
  clipping is FAIL. A short/transient result legitimately reports
  `integrated_lufs: null` and status `WARN` — that is not a defect to
  re-roll, and it is not this leaf's job to add duration to fix it.
- With `target_peak`, the actual measured true peak must land within 0.1
  dB of the target or the bundle is FAIL, never a claimed target reported
  as if it were the measurement.
- Any derivative format's own decode/peak is measured independently —
  lossy encoding can shift the peak above the requested target.
- A boundary-sample check is descriptive only ("NOT seamless-loop
  verification"); it never proves a loop point is actually seamless.
- A `FAIL` bundle is retained for diagnosis, never presented as finished.

</QA>

<Report>

Return `edit-sfx`, the operations and controls actually applied (in fixed
order), the delivered path(s), the `RESULT:` measurements and status
(PASS/WARN/FAIL, with FAIL and dependency errors distinguished), and
`spend: free`. A downstream duration change from `pitch_semitones` is
called out explicitly, not left implicit.

</Report>
