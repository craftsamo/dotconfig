---
name: media-craft-audio
description: >-
  Give craft-level feedback and concrete revision direction for spoken
  performance, sound design, music composition, arrangement, and mix balance
  in audio and video work — judging emphasis/pause/breath in narration,
  attack/body/tail/material/density in sound effects, motif/register/harmony
  in a score, foreground/midground/background roles in a mix, and
  listening-based balance between takes. Use when someone shares audio (or a
  scene/video with audio) and wants it to sound better, or wants a generation
  prompt turned into an actual sonic result. Do not use for transcription-only
  requests, meter-only/loudness-only measurement requests with no craft
  question, or for rewriting an already-approved script's words when only
  performance was asked for. Owns sonic execution of a chosen effect, not the
  choice of the overall creative concept.
license: MIT
---

# Media Craft: Audio

## Purpose

Turn a vague complaint ("this doesn't land," "it sounds cheap," "the mix feels
busy") into a concrete, listening-grounded diagnosis and a revision that a
host's actual tools can execute. This skill supplies craft judgment across six
audio disciplines; it does not supply new tools, models, or workflows — those
belong to the host that invoked it.

## Scope

Use this skill when a request involves any of:

- Spoken performance: emphasis, pacing, pause, breath, emotional read.
- Sound design: one-shot or looping sound effects, foley, ambience texture.
- Composition: melody, harmony, motif, phrasing for an original score or cue.
- Arrangement: how multiple audio layers (music, dialogue, effects, beds)
  share space and priority in a scene or mix.
- Listening review: comparing candidate takes, judging whether a mix or
  master actually sounds right, distinguishing that from a bare measurement.

Do not use it for a request that only wants a transcript of existing audio, a
bare technical measurement (loudness, sample rate, duration) with no craft
question attached, or a request to change the words of an already-approved
script when the actual complaint is about delivery, not content — direct that
back to whoever owns script approval instead of rewriting it unasked.

## Core discipline (applies to every reference below)

- **The host owns grants, scripts, models, and QA commands.** This skill
  directs craft; it never invents a new tool, plugin parameter, DSP command,
  SSML tag, or generation route the host has not already demonstrated it
  supports. If a lever isn't confirmed to exist, say so and offer the nearest
  supported alternative instead of guessing at syntax.
- **No generic style palettes or universal numeric targets.** Don't reach for
  a stock genre, a fixed loudness number, or a fixed BPM as a default —
  every target comes from the specific request, scene, or reference material
  in front of you.
- **Measurement is not listening.** A meter reading, a waveform screenshot, or
  a file hash tells you a number matched, not that the audio sounds right.
  Craft judgments in every reference below are grounded in an actual listen
  (by the host, the user, or a human reviewer) — never asserted from a static
  image or a numeric readout alone.
- **Preserve what wasn't asked to change.** Don't alter approved words,
  retime an unrelated recording, add unsupported markup, or touch a source's
  actual content to fix a balance or performance problem that a supported
  control could fix instead.
- **Know when not to revise.** A weak-sounding first impression is not always
  a defect — some repetition, density, or plainness is the intended function
  (a loopable ambient bed, a deliberately flat safety-briefing tone). State
  the evidence for "no change needed" as clearly as a revision would be
  stated, and leave the source untouched.

## References

Read the matching reference before giving a domain-specific critique. Each
one carries at least two worked cases showing a weak result, the cause, and
the concrete revision, plus a case where no revision applies.

- [speech-performance.md](references/speech-performance.md) — narration,
  dialogue, or voiceover delivery: emphasis, pacing, pause, breath, and the
  boundary between changing performance and changing words.
- [sound-design.md](references/sound-design.md) — foley, effects, and
  ambience: attack/body/tail, implied material, distance, density/repetition.
- [composition.md](references/composition.md) — melody, harmony, and phrase
  craft: motif, register, common-tone/stepwise/contrast movement, cadences.
- [arrangement.md](references/arrangement.md) — multiple layers sharing a
  scene: foreground/midground/background roles, space, density, dynamic beds.
- [generation.md](references/generation.md) — turning a mood into a
  generation prompt: timbre choice, plausible time evolution, why prompt
  ≠ guaranteed output.
- [listening-review.md](references/listening-review.md) — comparing takes,
  judging a mix, and the boundary between a meter reading and an actual
  listen.

## Workflow

1. Identify which discipline(s) the request actually touches — a single
   complaint ("the ad feels off") can span performance, arrangement, and
   review at once; read every reference that applies before answering.
2. Ground the diagnosis in the actual audio: listen to (or have the host/user
   listen to) the delivered material. Do not diagnose from a waveform image,
   a transcript, or the generation prompt alone.
3. State the observed problem in concrete terms (which word, which layer,
   which moment) rather than a mood adjective alone.
4. State the cause: why the current result produces that observed problem.
5. Direct a revision using only controls the host has already confirmed it
   exposes. If no such control exists for the fix you'd otherwise recommend,
   say so plainly rather than inventing one.
6. When nothing needs to change, say that explicitly and preserve the
   original — don't manufacture a revision to seem thorough.
7. For finite-attempt work (a batch of generation variants, several take
   comparisons), stay within whatever number the host's workflow actually
   authorized; do not keep producing new attempts past that grant, and do not
   substitute your own judgment for a human's stated preference between
   options they already reviewed.
