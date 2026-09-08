---
name: analyze-music
description: >-
  Inspect an existing music file locally: format/loudness/clipping, plus
  numpy-based tempo, beat, key/chord and structural-boundary estimates.
  Returns findings only, never a new or modified file. Works standalone
  on any existing song for arrangement/harmony-style analysis. Not
  semantic listening (verse/chorus/genre/mood/instrument identification),
  lyrics or vocal-delivery analysis, transcription/ASR, or any repair.
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
        label: "one local music file, at most 600 seconds and 128 MiB"
      focus:
        required: false
        type: text
        label: "overview (default) or a custom focus in words, e.g. rhythm, harmony, structure, timbre, technical"
      start:
        required: false
        type: text
        label: "analysis window start, seconds, 0 to end; default 0"
      end:
        required: false
        type: text
        label: "analysis window end, seconds, 0 to source duration; default the full source"
      note:
        required: false
        type: text
---

<Procedure>

1. Read the form. Never modify `source` and never create a `deliver`
   directory - this leaf produces no file. This works standalone on any
   existing song a client hands over for arrangement/harmony-style
   analysis, not only on this pipeline's own delivered cues. Run:

   ```sh
   ~/ghq/github.com/NousResearch/hermes-agent/venv/bin/python "${HERMES_SKILL_DIR}/../../scripts/music-media.py" analyze <source> [--start S] [--end E] [--focus TEXT]
   ```

   Do not use command substitution in executable paths; if `ghq root`
   differs on this machine, resolve it with a separate `ghq root` call
   first and then invoke the literal absolute Python path. This runs
   entirely locally (numpy STFT/onset/chroma estimation) - no external
   inference call, upload or ASR is ever made by this leaf.
2. Read the whole `RESULT:` JSON regardless of its exit code, distinguishing
   a measured finding from a dependency/input error raised before any
   measurement completed. Tempo comes back as a candidate BPM with its
   half/double alternatives, never a single asserted number; beat, key/
   chord and structural-boundary candidates are estimates from
   spectral/onset evidence, not a verified transcription. Energy/spectral
   windows and boundary candidates describe measurable change over time,
   never a semantic verse/chorus/section label.
3. Voice-containing input is fine for general music analysis (rhythm,
   harmony, structure, timbre) - this is not a song-lyrics or vocal-
   performance analyzer, and no ASR/transcription is run or promised.
   Build a findings table: check, evidence (the actual number/candidate
   set), confidence (measured/estimated/unverified), and a short note on
   what remains outside this leaf's scope (genre, mood, instrument
   identity, lyrics, verse/chorus structure) rather than guessing at it.

</Procedure>

<QA>

- Full decode and nonempty audio are required. Silence/low signal is a
  valid finding with unavailable musical estimates, not a request to generate
  audio. Clipping and format facts retain their actual measured numbers.
- Tempo is reported with its half/double ambiguity disclosed, never
  collapsed to one confident BPM without noting the alternative.
  Beat/key/chord candidates and structural-boundary candidates are
  labeled estimated, never asserted as verified transcription or
  semantic section labels (no "chorus", "verse", "genre", "mood",
  "instrument" claim from this local estimator).
- `analysis.chords.windows` contains two-second major/minor triad candidates,
  not a global chord or exact transcription. Preserve each window's
  `unavailable_reason` for low energy, diffuse/sparse pitch evidence or weak
  overlap. Similarities are not calibrated probabilities; inversions,
  extensions and rapid chord changes are not verified. Unavailable is not a
  tool failure and does not authorize a remote fallback or invented chords.
- No finding without a named measurement/candidate set or an explicitly
  disclosed limitation; never fabricate a number the estimator did not
  actually return.
- No listening/perceptual verdict is ever claimed, even when several
  measurements point the same direction.

</QA>

<Report>

Return `analyze-music`, the source and analysis window, a default
overview summary (overall character + timecoded development across the
window + explicit uncertainty) when `focus` was omitted, or the
requested custom focus's findings otherwise. Separate measured, estimated
and unverified items clearly; name what stays out of scope (lyrics,
genre, mood, semantic structure). State `spend: free`; no delivery path
is required. Propose `create-music`/`generate-music`/`edit-music` as
separate next steps rather than executing one.

</Report>
