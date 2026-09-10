---
name: generate-sfx
description: >-
   Generate one prompted SFX with the installed local Stable Audio 3 Medium
   engine by default, or an explicitly chosen paid fal ElevenLabs SFX v2
   engine. Package the raw take for QA. Local spends $0 and takes a seed;
   fal is metered, gated on explicit current-work client approval, and has
   no seed. No music, no speech, no cross-engine fallback.
version: 1.0.0
metadata:
  hermes:
    category: hands
    hands: audio-creator
    cost: metered
    output: "local: take-NN/raw.wav + take.json + inference.log inside the job dir, packaged via sfx-media.py into <deliver>/take-NN + .take.json; fal: state.json + take-NN.mp3/.tool.json retained in the job dir, packaged the same way"
    form:
      what_for:
        required: true
        label: "what the sound is for, in one sentence"
        example: "A cartoon whoosh for a card-flip transition"
      sound:
        required: true
        type: text
        label: "the sound itself, 1-450 characters, sent verbatim as the model prompt"
        example: "a heavy wooden door creaking open slowly, then a soft thud closing"
      seconds:
        required: true
        type: text
        label: "requested duration, 0.5 to 21.5; reserve 0.5s below the 22s packaging cap for MP3 padding/drift"
        example: "3"
      engine:
        required: false
        type: text
        label: "engine id from sfx_engines; omitted = local:stable-audio-3-medium (the default); an explicit fal:elevenlabs-sfx-v2 needs its own paid approval"
        example: "local:stable-audio-3-medium"
      seed:
        required: false
        type: text
        label: "local engine only: base seed 0 to 4294967295, default 0; attempt N uses (base + N - 1) mod 2^32, returned with each result; never send this to fal"
        example: "0"
      loop:
        required: false
        options: [no, yes]
        label: "fal only: yes requests a seamlessly loopable render; the API accepting this is not proof the result actually loops; local rejects loop=yes outright"
      prompt_influence:
        required: false
        type: text
        label: "fal only: 0 to 1, how closely the model follows `sound` verbatim; default 0.3; local rejects this field outright"
      variants:
        required: false
        type: int
        label: "attempts to propose, default 3 (plus 1 corrective, hard cap 8 including failures)"
      slug:
        required: false
        label: "lowercase ASCII filename slug; default sfx"
      note:
        required: false
        type: text
---

<Procedure>

1. Read `references/engine.md` before anything else — it names both
   engines, which controls belong to which, and the published fal
   per-second estimate. Do not fabricate a control the named engine does
   not accept.
2. Call `sfx_engines` (free) for the live list and its `runtime`/
   `available` fields. Report a `local:stable-audio-3-medium`
   `available: false` result (e.g. drift/no install) to Creator as a
   setup finding — never silently substitute fal, and never invent an
   engine id.
3. Pick the engine:
   - No `engine` requested, or explicitly `local:stable-audio-3-medium`
     (the default): local. It takes `seed` (default 0) and rejects
      `loop: yes`/`prompt_influence` — a request for either is a
     `Q<n>` back to Creator, never silently dropped. It needs no
     `paid_approved`/`max_usd` and spends $0.
   - Explicitly `fal:elevenlabs-sfx-v2`: this API has no `seed` — a
     request for a reproducible/seeded take on fal is a `Q<n>`, never
     silently dropped or answered by re-running until it "sounds
     close". Before any spend, get explicit current-work client
     approval of: the engine, the exact `sound` prompt, `seconds`,
     `loop`, `prompt_influence`, the attempt cap (default 3 variants +
     1 corrective = 4, hard ceiling 8, every attempt including failures
     counted), and a USD estimate at the published $0.002/second
     (checked 2026-09-08 — an estimate for approval, not an invoice).
     Never issue a paid call merely because `FAL_KEY` exists in
     `sfx_engines`, or from an implicit default budget.
4. Write `<deliver>/prompt.txt` with only the exact `sound` text; record
   approved/effective controls in a separate JSON file BEFORE the first call (local calls are
   unpriced but still count against the attempt cap and are worth
   recording the same way).
5. Start the job:
   - Local: `sfx_generate(action="start", job_dir=<new absolute dir>,
     text=<sound>, duration_seconds=<seconds>, seed=<seed or 0>,
     max_calls=<cap>)`. Omit `engine` or pass
     `local:stable-audio-3-medium` explicitly; never send `loop`,
      `prompt_influence`, `paid_approved` or `max_usd`. Only omitted/false
      loop is accepted; the other controls are refused rather than dropped.
   - fal: `sfx_generate(action="start", job_dir=<new absolute dir>,
     engine="fal:elevenlabs-sfx-v2", text=<sound>,
     duration_seconds=<seconds>, loop=<loop>,
     prompt_influence=<prompt_influence or 0.3>, paid_approved=true,
     max_calls=<approved cap>, max_usd=<approved estimate>)`.
   Either call freezes the engine and controls for the whole job;
   `job_dir`'s parent must exist and `job_dir` itself must not.
6. Poll with `sfx_generate(action="resume", job_dir=...)` up to about 3
   times with a short pause between calls. If still `status: pending`
   after that, stop polling in the foreground and report `pending`;
   resume the same `job_dir` later from a resident session rather than
   looping — `resume` never submits a new request and, on local, never
   regenerates: it only re-validates the existing take against the
   job's frozen receipt.
7. For each additional approved variant, call `sfx_generate(action="next",
   job_dir=...)` without changing text. On local this automatically
   advances the seed by `(base + attempt_count) mod 2^32`; do not pass a
   `seed` to `next`/`resume` — only `start` accepts it. For one
   corrective attempt (still within the approved cap), call
   `sfx_generate(action="next", job_dir=..., text=<corrective prompt>)`
   — only the prompt text may change; engine and every other control
    stay frozen from `start`. Write each corrective prompt into a new
    `prompt-NN.txt` before calling and use that file when packaging its take;
    do not append controls or past prompts to a take's actual prompt file.
8. A `success: false` result with an "unknown submission outcome" error
   (fal only) is a manual finding — the tool refuses to guess whether the
   provider received it. Stop and report it; do not start a NEW
   `job_dir` to reset the attempt count around a stuck one. On local, an
   attempt lost to interruption (no result, no running process) is
   marked `failed` automatically and stays counted — call `next` within
   the remaining grant rather than starting a fresh job.
9. Once a result reports `status: raw-needs-qa`, package that attempt's
   raw take (never re-generate to "fix" a packaging problem — reuse the
   existing raw file):

   - Local: the `sfx_generate` result already names `raw` and
     `take_json` (the job's real `take-NN/raw.wav` and `take-NN/take.json`,
     written by `stable_audio3.py`). Package with:

     ```sh
     ~/ghq/github.com/NousResearch/hermes-agent/venv/bin/python "${HERMES_SKILL_DIR}/../../scripts/sfx-media.py" track <raw> --out <deliver>/take-NN --slug <slug> --take-file <take_json> --prompt-file <deliver>/prompt.txt
     ```

     Do not use command substitution in executable paths; if `ghq root`
     differs on this machine, resolve it with a separate `ghq root` call
     first and then invoke the literal absolute Python path — never repeat
     the model generation to fix a packaging step. (Actual live failure:
     "Nested executable body could not be resolved.")

     Pass the receipt exactly as `stable_audio3.py` wrote it — never
     fabricate or edit `take.json`. It already carries `engine`, the
     model commit/revision, the runtime fingerprint, the frozen request
     (including the actual `seed` used for that attempt) and the raw
     WAV's own hashes.

   - fal: package `<job_dir>/take-NN.mp3` the same way, but build
     `<evidence.json>` yourself from the ACTUAL job state — engine,
     model, the frozen request payload, `request_id`, attempt number and
     status read back from `sfx_generate`'s response and the job's own
     `state.json`/`take-NN.tool.json` — never invent a field it did not
     return:

     ```sh
     ~/ghq/github.com/NousResearch/hermes-agent/venv/bin/python "${HERMES_SKILL_DIR}/../../scripts/sfx-media.py" track <job_dir>/take-NN.mp3 --out <deliver>/take-NN --slug <slug> --take-file <evidence.json> --prompt-file <deliver>/prompt.txt
     ```

     Do not use command substitution in executable paths; if `ghq root`
     differs on this machine, resolve it with a separate `ghq root` call
     first and then invoke the literal absolute Python path — never repeat
     the model generation to fix a packaging step. (Actual live failure:
     "Nested executable body could not be resolved.")

   Never mix the two engines' arguments — a local `take.json` and a fal
   `evidence.json` are shaped differently and belong to different job
   dirs. Keep `state.json` (fal) / the job's `state.json` (local) and
   every raw take file; they are the audit trail, not scratch files to
   delete.
10. Do not report a duration/loop request as guaranteed: only the
    packaged bundle's own measurement proves actual duration, and
    nothing here proves a seamless loop boundary on fal. State the
    provider/licensing terms as unknown beyond what each engine
    publishes (`references/engine.md`); neither engine takes a reference
    sound — both take text only.

</Procedure>

<QA>

- Per packaged attempt: full decode, positive non-silent duration close
  to `seconds` (report the actual measured value, never assume the
  request was honored exactly), no clipping; quote peak/true-peak/LUFS
  and the `WARN` case for a short/ungated transient.
- Local: when replay is requested and granted, compare the two decoded PCM
  hashes at the same runtime fingerprint and controls. Seed equality alone
  is not proof of identical output, and matching hashes are not listening.
- fal `loop: yes` requested is not evidence of a working loop — report
  the helper's `boundary_sample_deltas` as descriptive only, explicitly
  labeled "NOT seamless-loop verification".
- Provenance: engine/model/attempt count (and, for fal, `request_id`)
  are the tool's own returned values, never invented; `evidence_provided`
  and the take's `evidence` block are quoted, not summarized away.
- No hearing/auditory verdict is ever claimed; `auditory_quality` stays
  `unverified` even on a PASS bundle.

</QA>

<Report>

Return `generate-sfx` + engine used (and seed, for local; loop/
prompt_influence, for fal) + prompt/seconds, `<deliver>` paths (prompt,
job dir, packaged bundle(s)), each attempt's outcome (including failed/
pending/unknown-submission ones) with QA measurements and warnings,
`spend: local $0` or `spend: fal <calls>/<approved cap>; ~$<estimate>`,
and remaining budget. Never claim you listened, and never propose a
further attempt outside the approved cap without going back for approval
(fal only — local has no paid approval to exceed, only its `max_calls`
cap).

</Report>
