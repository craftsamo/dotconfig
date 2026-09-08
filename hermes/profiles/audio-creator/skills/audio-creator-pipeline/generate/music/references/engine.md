# Music generation engines

Read this before proposing anything to Creator. `music_engines` is free
and returns the live, authoritative list; this file is background, not a
substitute for calling it.

## Default: `local:stable-audio-3-medium`

Installed and ready; used automatically when `engine` is omitted. Runs
entirely on this machine through the maintainer-owned `stable_audio3.py`
adapter's `render_music` entry point (fixed Medium/SAME-L recipe, 8
steps, 44.1 kHz 16-bit stereo WAV), the same runtime root lock and
inherited child lock as the SFX engine, and the same 180-second timeout.
Official docs/pins: see `PROFILES.md` "SFX family" for the shared install
detail (this engine is the same pinned local model, extended to music).

- Inputs: text prompt (1-450 chars), `duration_seconds` (1-60), `seed`
  (integer 0 to 4,294,967,295, default 0). Unlike the SFX fal engine,
  **both** the local and fal music engines accept a seed.
- Cost: $0 per call. Still bounded by the approved `max_calls` - every
  attempt counts, including a failed render.
- License: Community License and Gemma terms; commercial registration is
  a separate step not performed by this evaluation install. No
  royalty-free guarantee is made for local or fal output.

## Alternative: `fal:stable-audio-3-medium`

Must be named explicitly - never the implicit default, and never a silent
substitute when local is unavailable or a client merely prefers not to
wait.

- Model: `fal-ai/stable-audio-3/medium/text-to-audio`.
- Model page / official schema:
  https://fal.ai/models/fal-ai/stable-audio-3/medium/text-to-audio/llms.txt
- Inputs: `prompt` (1-450 chars), `duration` (1-60s), `seed` (supported,
  unlike the SFX fal engine's endpoint), fixed WAV output/8 steps/guidance
  1/empty negative prompt/safety checker on/no prompt expansion.
- Cost: published estimate **$0.0376 per audio**, checked 2026-09-08 -
  an estimate for the approval conversation, not an invoice or a
  provider-enforced cap. Every call needs explicit current-work client
  approval of engine/prompt/duration/seed/attempt cap/USD estimate before
  any spend; `music_engines` reporting the key as present is not that
  approval. No benchmark claim beyond this published estimate is asserted.

## No automatic fallback in either direction

`music_engines` reports both engines' live readiness/cost/seed fields. A
declined or unavailable local request never silently becomes a paid fal
call, and a client preference for local never blocks an explicitly
approved fal request. Omitted `engine` means local Medium only; fal must
be named explicitly and must never be substituted without the client's
decision.

## What neither engine promises

An "instrumental" direction in the prompt is a requirement to ask for,
not a guarantee the model omits vocals - QA the returned take's actual
content rather than assuming silence of vocals from the prompt alone. No
audio-conditioned generation (humming/reference-audio-guided render) is
supported in this version - `reference_audio` is never uploaded to either
engine. Neither engine takes a reference sound; both take text only.
