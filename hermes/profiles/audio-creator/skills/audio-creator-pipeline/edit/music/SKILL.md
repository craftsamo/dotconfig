---
name: edit-music
description: >-
  Edit one existing music file: trim, repeat-to-length with a crossfaded
  loop seam, fade in/out, apply gain or two-pass true-peak normalize.
  Preserves the original and delivers a new 48 kHz master. Not
  resynthesis/regeneration, speed or pitch change, multi-file mixing, or
  a musical seamlessness proof - only a numerical boundary-sample check.
version: 1.0.0
metadata:
  hermes:
    category: hands
    hands: audio-creator
    cost: free
    output: "new music_<slug>.wav + .take.json"
    form:
      source:
        required: true
        type: file
        label: "one local music file, at most 600 seconds and 128 MiB"
      start:
        required: false
        type: text
        label: "trim start, seconds, 0 to end; default 0 (no trim start)"
      end:
        required: false
        type: text
        label: "trim end, seconds, 0 to source duration; default the full source"
      loop_seconds:
        required: false
        type: text
        label: "repeat the trimmed source to at least this total length with a crossfaded seam at each repeat boundary; must be >= the trimmed source's own duration"
      crossfade_ms:
        required: false
        type: int
        label: "crossfade length at each repeat boundary; only applies with loop_seconds, ignored otherwise"
      fade_in_ms:
        required: false
        type: int
        label: "fade-in length applied after trim/repeat, 0-600000 ms"
      fade_out_ms:
        required: false
        type: int
        label: "fade-out length applied after trim/repeat, 0-600000 ms"
      gain_db:
        required: false
        type: text
        label: "flat gain adjustment in dB, applied after fades; no default, omit to leave gain untouched"
      target_lufs:
        required: false
        type: text
        label: "two-pass integrated loudness normalization target, applied last, true-peak capped at -1 dBTP; omit to leave loudness untouched - there is no hidden default target"
      slug:
        required: false
        label: "lowercase ASCII filename slug; default music"
      note:
        required: false
        type: text
---

<Procedure>

1. Confirm at least one operation was actually requested (trim, loop,
   fade, gain, or normalize) - a form with no nondefault control is
   refused rather than producing a byte-identical copy. This leaf takes
   exactly one `source`; a multi-file mix or concatenation of separate
   tracks does not fit here (that scope stays with a future mix family,
   not this leaf). No speed or pitch change is available - that is a
   different, unsupported request, never approximated by resampling.
2. The operations always apply in this FIXED order regardless of the
   order fields were given: **trim, repeat/crossfade, fade, gain,
   two-pass true-peak normalize**. Document that order back if the
   request assumed a different sequence. `crossfade_ms` only has an
   effect when `loop_seconds` is also set - a crossfade request with no
   `loop_seconds` is a `Q<n>`, never silently applied to a plain trim.
   `loop_seconds` must be greater than or equal to the trimmed source's
   own duration; a shorter value would require actually cutting material,
   which this leaf does not do - return `Q<n>` instead of shortening it.
   `target_lufs` has no hidden default; omit it to leave loudness
   untouched rather than guessing a target.
3. Run through the Hermes venv Python:

   ```sh
   ~/ghq/github.com/NousResearch/hermes-agent/venv/bin/python "${HERMES_SKILL_DIR}/../../scripts/music-media.py" edit <source> --out <deliver>/take-01 --slug <slug> [--start S] [--end E] [--loop-seconds S] [--crossfade-ms N] [--fade-in-ms N] [--fade-out-ms N] [--gain-db DB] [--target-lufs LUFS]
   ```

   Do not use command substitution in executable paths; if `ghq root`
   differs on this machine, resolve it with a separate `ghq root` call
   first and then invoke the literal absolute Python path - never repeat
   generation to fix a packaging step (this leaf never generates in the
   first place). Add only the flags the form actually set. The source
   must decode to <=600s and <=128 MiB or the helper refuses before
   writing anything.
4. A loop-seam claim from this leaf is a numerical boundary-sample delta
   check only, never a musical "sounds seamless" proof - state that
   explicitly regardless of how small the measured delta is.
5. Never overwrite the source or a prior bundle; each run uses a fresh
   `--out`. `intent: revise` reruns with the changed control(s) only.

</Procedure>

<QA>

- Quote the actual operations applied, in the fixed order, and the
  resulting duration; for `loop_seconds`, confirm the result's duration
  is >= the requested value and report the actual repeat count.
- Full decode, positive non-silent PCM master, correct channel count;
  clipping is FAIL.
- With `target_lufs`, the actual measured integrated loudness must land
  within a small tolerance of the target and true peak must be <= -1
  dBTP, or the bundle is FAIL, never a claimed target reported as if it
  were the measurement.
- With `loop_seconds`/`crossfade_ms`, report the boundary-sample delta at
  each seam explicitly labeled "NOT seamless-loop verification" - a small
  delta is descriptive evidence only, never a listening claim.
- Originals and prior bundles remain unchanged. A `FAIL` bundle is
  retained for diagnosis, never presented as finished.

</QA>

<Report>

Return `edit-music`, the operations and controls actually applied (in
fixed order), the delivered path, the measurements and status (PASS/
WARN/FAIL), and `spend: free`. State the boundary-sample check's
"not seamless-loop verification" caveat whenever `loop_seconds` was used.

</Report>
