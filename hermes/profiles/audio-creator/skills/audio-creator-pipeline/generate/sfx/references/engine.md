# SFX generation engines

Read this before proposing anything to Creator. `sfx_engines` is free and
returns the live, authoritative list; this file is background, not a
substitute for calling it.

## Default: `local:stable-audio-3-medium`

Installed and ready; used automatically when `engine` is omitted from
`sfx_generate`. Runs entirely on this machine through
the maintainer-owned `stable_audio3.py` adapter (pinned code + weights, hash-locked
dependencies; see `PROFILES.md` "SFX family" for the install/runtime
detail). Inference uses local files with no per-call fee. The optimized
weights download anonymously, but use still accepts the Community License
and Gemma terms. Commercial registration is separate and was not performed
by the personal-evaluation installation.

- Inputs it accepts: `text` (prompt, 1-450 chars), `duration_seconds`
  (0.5-21.5), `seed` (integer 0 to 4,294,967,295, default 0). Attempt N of
  a job uses `(base seed + N - 1) mod 2^32`; the actual seed used is
  returned with every result, so a specific take can be identified, but
  replaying it exactly means starting a fresh job with that seed as the
  new base — `resume`/`next` never accept a `seed` argument, and they
  never reset or extend a job's own attempt count to "get back" a
  discarded take.
- Inputs it refuses outright (never silently dropped): `loop` (any value
  other than absent/`false`), `prompt_influence`, `paid_approved`,
  `max_usd`. A request naming any of these for local is a `Q<n>` back to
  Creator — offer the fal alternative instead if the client needs looping
  or a prompt-adherence dial.
- Cost: $0 per call. Still bounded by the job's `max_calls` (default 4:
  3 variants + 1 corrective, hard cap 8) — every attempt counts, including
  a failed render, so "free" is not "unlimited takes".
- `resume` never regenerates. It only re-validates the existing
  `take-NN/raw.wav` + `take.json` on disk against the job's frozen
  runtime/request receipt. An attempt that was `running` with no result
  and no live render process is marked `failed` (still counted); use
  `next` to spend the remaining grant rather than starting a new job.
- Output: `take-NN/raw.wav` (44.1 kHz 16-bit stereo PCM) + `take.json`
  (the receipt) + `inference.log`, inside the job dir. Package with
  `sfx-media.py track --take-file <that take.json>` — never fabricate an
  evidence file for a local take the way fal packaging does.

## Alternative: `fal:elevenlabs-sfx-v2`

Must be named explicitly — never the implicit default, and never a
silent substitute when local is unavailable or when a client merely
prefers not to wait.

- Model: `fal-ai/elevenlabs/sound-effects/v2`.
- Model page / official docs, including the published OpenAPI schema under
  its "API" tab: https://fal.ai/models/fal-ai/elevenlabs/sound-effects/v2
- Inputs the API actually accepts: `text` (prompt, 1-450 chars),
  `duration_seconds` (0.5-22), `loop` (bool), `prompt_influence` (0-1).
  There is no `seed` input — this API does not support reproducible
  takes; a request for one is a `Q<n>`, never silently dropped.
- Cost is metered per second. Published estimate used for approval math:
  **$0.002/second**, checked 2026-09-08. This is an estimate for the
  approval conversation, not an invoice — actual provider billing may
  differ. Every call needs explicit current-work client approval of
  engine/prompt/seconds/loop/attempt cap/USD estimate before any spend —
  `sfx_engines` reporting `FAL_KEY` as present is not that approval.

## No automatic fallback in either direction

`sfx_engines` reports both engines' live `available`/cost/seed/loop
fields. A declined or unavailable local request never silently becomes a
paid fal call, and a client preference for local never blocks an
explicitly approved fal request. Omitted `engine` means local Medium only;
any alternative must be named explicitly from the live list and must never
be substituted without the client's decision.
