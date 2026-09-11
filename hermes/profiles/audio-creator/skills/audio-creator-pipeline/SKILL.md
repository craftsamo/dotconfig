---
name: audio-creator-pipeline
description: >-
  AudioCreator's speech, sfx, instrumental music and mix hands. Load first
  for a filled generate-speech, edit-speech, analyze-speech, create-sfx,
  generate-sfx, edit-sfx, analyze-sfx, create-music, generate-music,
  edit-music, analyze-music, create-mix, edit-mix or analyze-mix form from
  Creator. Not song production, voice registration, script writing or
  video assembly.
version: 1.0.0
metadata:
  hermes:
    category: hands
    tags: [audio, speech, hands]
---

<Run>

The runtime specialist header is agent context outside the form, not human
approval. Preserve the initial voice, words, engine and grant across revisions.
An environment or packaging failure is not a capability verdict or permission
to switch to a paid engine. Reuse surviving audio and spend records; author
scores/arrangements within the approved intent rather than demanding a preset.
Act only on the current agent request. The retained initial form supplies
historical constraints, never a request to repeat its generation or spend.

1. Load the named `<verb>/<subject>/SKILL.md` (`speech`, `sfx`, `music` or
   `mix`). Validate its form; missing or unusable fields return in one
   `Q<n>:` block. `no skill fits` is a finding, not permission to invent a
   workflow. An analyze form needs no `deliver`.
2. Read the approved script/source and previous delivery for `intent: revise`.
   Preserve words and voice identity for speech, the same closed kernel or
   engine and controls for sfx, and the frozen sources/prior spec for mix.
   Never substitute an engine, add acting beats, register voices, download
   models or repair the managed skill tree.
3. Run the leaf's Procedure. Speech leaves share `scripts/speech-media.py`;
   sfx leaves share `scripts/sfx-media.py` and generate-sfx's `sfx_engines`/
   `sfx_generate` tools (from a leaf: `../../scripts/<name>-media.py`), using
   the Hermes venv Python. Music uses `scripts/music_plan.py` for frozen
   proposals, `scripts/music-media.py` for score rendering/editing/analysis,
   and `music_engines`/`music_generate` for model generation. Mix uses
   `scripts/mix-media.py` for its own two-round proposal gate
   (`propose`/`render`), plus `analyze`/`verify` - never speech-media.py,
   sfx-media.py or music-media.py, and no engine/model of its own. Existing
   bundles are never overwritten. Create/generate-music's proposal round is
   pure JSON authoring with zero audio work; create/edit-mix's proposal
   round fully decodes and validates every source (and any speech
   `.words.json` hash) but produces no mixed audio, ASR or network call
   either. Only Creator-relayed approval of the exact proposal releases
   rendering. Users need not supply a score or a mix spec: author one
   within the filled form.
4. Run the leaf's QA. Measurements, ASR and waveform stats are evidence, not
   listening. Preserve FAIL/WARN, estimated subtitle timing, unverified
   pronunciation/identity/performance and a short-clip's WARN-not-defect
   missing LUFS. A warning is not a reason for unlimited retakes or a
   generation re-roll. Music analysis can stand alone on existing music,
   including vocal tracks, without a production job. Separate measurements,
   tempo/key/structure estimates and unverified instruments/genre/vocal absence;
   never invent listening, lyrics or a semantic verse/chorus interpretation.
5. Return the leaf's Report, durable paths and take/call tally. Speech is free
   of provider fees but limited to one take plus one corrective per script,
   including failed calls. Deterministic create/edit/analyze-sfx uses no model
   takes or provider fees. Generate-sfx defaults to the local Medium engine
   ($0 spend, seed-controlled, no loop/prompt_influence) within its attempt
   cap; only an explicitly chosen fal call spends against an approved cap and
   USD estimate. Reuse surviving audio after
   a packaging failure; do not synthesize again to fix a sidecar. Generate-music
   defaults to three local attempts (two variants plus one corrective), hard
   cap eight; fal requires an explicit approved call and USD cap. It never
   falls back across engines. Corrections need a new approved proposal and
   preserve consumed attempts. A finished music WAV can feed create-ad's
   existing audio cues. Mix places already-finished speech/sfx/music sources
   on a shared timeline with gain/fade/envelope automation - no synthesis,
   no engine, no model call, zero spend at every step (propose and render
   alike); normalization, when requested, is one measured constant-gain
   pass, never a dynamic limiter. It never separates stems from a rendered
   master and never loops a source (that stays with edit-music). A changed
   placement/gain/duration needs a new approved proposal, same as music;
   `edit-mix` only ever loads a previous PASS/WARN bundle, never a FAILed
   one (that returns to `create-mix`'s own retry).

</Run>
