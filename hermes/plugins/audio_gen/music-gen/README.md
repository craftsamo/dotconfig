# Music Generation Plugin

Standalone `music-gen`, toolset `music_gen`, registered only for
`audio-creator`. It does not import the SFX plugin, mix audio, generate speech,
install models, start a daemon, or fall back to another engine.

## Tool Contract

Both handlers accept exactly one positional JSON dictionary:
`catalog(args, **kwargs)` and `generate(args, **kwargs)`. Tool results are JSON
strings. `music_engines` accepts `{}` and performs readiness checks, not media
generation or a paid provider health check.

`music_generate` accepts only these fields:

| Action | Required | Optional |
| --- | --- | --- |
| `start` | `action`, `job_dir`, `approved_plan`, `approval_sha256` | `paid_approved: true` for fal only |
| `next` | `action`, `job_dir` | Both approval fields together for a corrected proposal |
| `resume` | `action`, `job_dir` | None |

Start requires a new absolute directory with an existing parent. Protected,
traversing and symlinked paths are rejected. An existing job is never replaced.
Do not put job state or media in this source directory.

The plugin dynamically imports
`profiles/audio-creator/skills/audio-creator-pipeline/scripts/music_plan.py`
and calls `load_approved(path, sha256, "generate")`. Its returned version-1
manifest must contain `kind: generate`, `form`, `settings`, `artifact_text`,
`artifact_sha256`, `approval_sha256`, and `approved_plan`. The helper owns
Markdown, embedded artifact and reference-file verification. The plugin also
checks prompt hash, supported settings and returned proposal identity.

Settings are `engine`, `duration_seconds`, `seed`, `max_calls`, and `max_usd`.
Local is the default engine, seed defaults to zero, and the local take cap
defaults to three (two variants plus one correction). Duration must be approved and within 1..60 seconds; prompt
length is 1..450 characters. Seed is an integer in 0..2^32-1 and `max_calls` is
an integer in 1..8. Unknown settings and tool controls fail before generation.

Each new attempt revalidates the proposal and artifacts. Corrective reapproval
may replace form and prompt, but not engine, duration, base seed, call cap or
dollar cap. Omitted approval fields on `next` reuse the last approved prompt.
Attempt index is zero-based: `(base_seed + index) % 2**32` on both engines.

## Engines And Payment

- `local:stable-audio-3-medium`: calls `stable_audio3.render_music`, fixed
  Medium/SAME-L recipe, 8 steps, 44.1 kHz 16-bit stereo WAV, the same runtime
  root lock and inherited child lock as SFX, and the same 180-second timeout.
- `fal:stable-audio-3-medium`: explicitly selected endpoint
  `fal-ai/stable-audio-3/medium/text-to-audio`. Sends `prompt`, `duration`,
  `seed`, WAV output, 8 steps, guidance 1, empty negative prompt, safety checker
  enabled, sync mode disabled, and prompt expansion disabled.

The fal estimate is **$0.0376 per audio**, as published on
[the official model schema](https://fal.ai/models/fal-ai/stable-audio-3/medium/text-to-audio/llms.txt)
on 2026-09-08. This is an estimate, not an invoice or a provider-enforced cap.
The live [OpenAPI input schema](https://fal.ai/api/openapi/queue/openapi.json?endpoint_id=fal-ai/stable-audio-3/medium/text-to-audio)
also confirms WAV output, seed and the fixed controls above; its duration limit
is 380 seconds, while this plugin deliberately caps v1 at 60 seconds.
Fal requires explicit current-work paid approval, an explicit `max_calls`, and
a finite `max_usd` no greater than $10 covering the entire approved call cap.
Local rejects any `paid_approved` key, including false, and accepts `max_usd`
only when absent or null. Credentials come only from
`agent.secret_scope.get_secret("FAL_KEY", "")`, never environment fallback.

## Recovery And Evidence

Attempts are persisted and fsynced **before** inference or paid submission;
failures consume attempts and the reserved cost estimate. Paid POSTs run once,
without SDK retries or redirects. Request IDs are checkpointed immediately.
An ambiguous submission stops the job; neither `next` nor `resume` resubmits it.
Pending work can be retrieved with `resume`; explicit completed-request
400/422 rejections mark the counted attempt failed. Other retrieval failures
remain resumable. A failed attempt allows an explicit `next` within the grant.

Successful bundles are `take-NN/raw.wav` and `take-NN/take.json`; local also
retains `inference.log`, fal retains `response.json`. State binds each attempt
to its approved manifest, exact payload, and output hashes. Local receipt
validation includes runtime identity, PCM hash, frame count and format.
Completed outputs are rechecked against checkpointed hashes on resume. A
failed or uncheckpointed attempt cannot become successful merely by placing
files in its directory. A hard interruption between publishing output and
checkpointing its hashes requires manual evidence recovery; files are retained,
not adopted automatically or regenerated. Resume of checkpointed work does not
need the original approval files or an unchanged installed runtime.

Raw downloads and WAV reads are bounded to 32 MiB, metadata to 1 MiB, and WAV
duration to 60 seconds. Downloads accept only HTTPS `*.fal.media` URLs and no
redirects. Output is `raw-needs-qa`, never a listening verdict. An instrumental
prompt does not guarantee the absence of vocals or prove seamless looping.

Approval hashes bind bytes, not human identity. Job hashes detect accidental
or isolated tampering; they do not authenticate against an operator who can
rewrite every local state file and receipt together.

## Runtime Activation

The runtime fingerprints its full adapter source. A maintainer can activate an
adapter-only change with `stable_audio3.py refresh --previous-adapter PATH`
(`--root PATH` optional). Supply the exact old adapter source: its hash with
the current pins and lock must reproduce the existing marker. Refresh requires
an existing installation, verifies checkout/weight/dependency drift and full
weight/RECORD hashes under the runtime lock, and atomically updates only the
marker fingerprint. No install, download, Git update, pip, or terms acceptance
runs. Ordinary status checks remain strict. Old completed SFX evidence remains
resumable, but old jobs cannot generate another take under the new identity;
no job receipt is migrated. Refresh is maintainer-only, never a tool fallback.
