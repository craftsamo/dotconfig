---
name: generate-music
description: >-
  Generate instrumental BGM or a short melodic cue with local Stable
  Audio 3 Medium, or explicitly approved paid fal. Return a proposal
  first; generate only after Creator relays approval. Both engines take
  a seed; no fallback. Not songs, SFX, mixing, edit-music or create-music.
version: 1.0.0
metadata:
  hermes:
    category: hands
    hands: audio-creator
    cost: metered
    output: "proposal-v<N>/proposal.md + SHA-256; after approval, music_<slug>.wav + take evidence; raw/job ledger retained"
    form:
      what_for:
        required: true
        label: "what the music is for, in one sentence"
        example: "A 20-second uplifting montage closer"
      theme:
        required: true
        options: [warm, playful, dreamy, tense, uplifting]
        other: true
        references: references/themes/*.md
        label: "mood vocabulary; listed defaults are starting points, never fixed presets"
      theme_detail:
        required: false
        label: "client details override conflicting theme defaults"
      style:
        required: true
        options: [ambient, electronic, lofi, acoustic, jazz, orchestral]
        other: true
        references: references/styles/*.md
        label: "real-world sound direction sent to the model; not a guaranteed model output"
      instrumentation:
        required: false
        label: "instruments to feature or avoid, in words"
      direction:
        required: false
        options: [steady, gradual-build, contrast, motif-return]
        other: true
        references: references/direction/*.md
        label: "musical development; omit to have AudioCreator propose it"
      tempo:
        required: false
        label: "free text, may include a BPM figure the prompt names; approximate only, never frame-accurate"
      duration:
        required: true
        type: text
        label: "1-60 seconds, including release/tail"
        example: "20"
      ending:
        required: false
        options: [resolve, fade, loop]
        references: references/ending/*.md
        label: "closing behavior; omit to have AudioCreator propose it"
      must_keep:
        required: false
        label: "requirements that must never be silently dropped"
      reference_audio:
        required: false
        type: file
        label: "local reference only; never uploaded or automatically analyzed"
      reference_focus:
        required: false
        label: "required with reference_audio: what to borrow; analyze-music handles measurements"
      engine:
        required: false
        type: text
        label: "music_engines ID; default local:stable-audio-3-medium; fal needs paid approval"
        example: "local:stable-audio-3-medium"
      seed:
        required: false
        type: int
        label: "uint32 base seed, default 0; attempt N uses (base+N-1) mod 2^32, both engines"
        example: "0"
      approved_plan:
        required: false
        type: file
        label: "approved proposal-v<N>/proposal.md; absent means proposal only"
      approval_sha256:
        required: false
        label: "SHA-256 of the exact proposal approved by the client; required with approved_plan"
      slug:
        required: false
        label: "lowercase ASCII filename slug; default music"
      note:
        required: false
        type: text
---

<Procedure>

1. Confirm scope before anything else: this leaf generates **instrumental**
   BGM or a melodic opener/closer only. A request for a full song with
   lyrics/singing, standalone sound design/SFX, or audio mixing is `no
   skill fits` - a finding for Creator, never an approximated substitute.
   An "instrumental" direction in the prompt is a requirement to ask for,
   not a guarantee the returned take actually omits vocals - QA the
   actual content, never assume it from the prompt alone.
2. Read `references/engine.md` before proposing anything - it names both
   engines, confirms both take a `seed` (unlike SFX's fal endpoint, which
   has none), and the published fal per-audio estimate. Call
   `music_engines` (free) for the live list and its `available` fields;
   report an unavailable local engine as a setup finding, never a silent
   substitution to fal.
3. Load only the selected local references before drafting: theme from
   [warm](references/themes/warm.md), [playful](references/themes/playful.md),
   [dreamy](references/themes/dreamy.md), [tense](references/themes/tense.md),
   [uplifting](references/themes/uplifting.md); style from
   [ambient](references/styles/ambient.md), [electronic](references/styles/electronic.md),
   [lofi](references/styles/lofi.md), [acoustic](references/styles/acoustic.md),
   [jazz](references/styles/jazz.md), [orchestral](references/styles/orchestral.md);
   direction from [steady](references/direction/steady.md),
   [gradual-build](references/direction/gradual-build.md),
   [contrast](references/direction/contrast.md),
   [motif-return](references/direction/motif-return.md); ending from
   [resolve](references/ending/resolve.md), [fade](references/ending/fade.md),
   [loop](references/ending/loop.md). These are authored prompt recipes,
   not claims of proven model output; an `other` value gets an equally
   concrete written treatment, never coerced onto a listed one. Themes
   never imply a forced tempo or key; `gradual-build` is arrangement/
   energy language, never an automatic BPM-increase instruction.
   `theme_detail`/`must_keep` override conflicting defaults; resolve
   contradictions before approval.
4. `reference_audio` is never uploaded to the generation provider and
   this leaf never auto-analyzes it. A description of mood/instrumentation
   from a human listen is enough for `reference_focus`; if the client
   instead needs an objective measurement (tempo/key/structure) from the
   file, that is a separate `analyze-music` call in its own turn, with
   its findings supplied back into this form - never a silent
   remote/local inference folded into this leaf's own round. No audio-
   conditioned generation (humming/reference-guided render) is supported.
5. Round A (no `approved_plan`): no `music_generate` call, no network, no
   uploads. Resolve the complete effective form, proposing concrete
   defaults for any omitted `direction`/`tempo`/`ending` (never leaving
   them implicit). Write it to a fresh `<deliver>/form.json` and a short
   `<deliver>/arrangement.md` narrating the piece section by section.
    Distill a compact `<deliver>/prompt-v<N>.txt` (1-450 characters, the exact
   text that will be sent) separately from the fuller `arrangement.md` -
   do not concatenate the whole narrative into the model prompt. Then run:

   ```sh
    ~/ghq/github.com/NousResearch/hermes-agent/venv/bin/python "${HERMES_SKILL_DIR}/../../scripts/music_plan.py" propose --kind generate --form-file <deliver>/form.json --arrangement-file <deliver>/arrangement.md --prompt-file <deliver>/prompt-v<N>.txt --out <deliver>/proposal-v<N>
   ```

   Do not use command substitution in executable paths; if `ghq root`
   differs on this machine, resolve it with a separate `ghq root` call
   first and then invoke the literal absolute Python path. Choose the
   next unused `N` even after a rejected proposal; never overwrite a
   previous proposal directory. Include the resolved `engine` (default
   local) and `seed` (default 0) in `form.json`; the outer approval grant
   (not a form field) sets `max_calls`/`max_usd` for generation
   settings - never add a `variants`/`budget` field to this form. Local
   default allowance is **2 variants + 1 corrective, max 3, hard cap 8**,
   every attempt including failures counted; fal requires an explicit
   approved cap and a finite USD estimate before any paid call, and never
   an implicit default budget. Report the returned proposal path and its
   SHA-256, and STOP - zero generation, zero spend in round A.
6. Round B requires both `approved_plan` and `approval_sha256` from
   Creator and `intent: revise <previous delivery>`, in the same work
   conversation as the client's approval. A changed creative field or a
   materially different engine/duration/seed/budget needs a new proposal,
   never a generation against stale approval text. Inventory any existing
   job state first; never start a new `job_dir` to reset an attempt count.
   Start a new job:

   ```
   music_generate({action: "start", job_dir: <new absolute dir>, approved_plan: <path>, approval_sha256: <hash>})
   ```

   Add `paid_approved: true` only for an explicitly approved fal engine;
   local rejects that key outright, including `false`. `job_dir`'s parent
   must exist and `job_dir` itself must not.
7. Poll a `pending` fal job with `music_generate({action: "resume",
   job_dir: ...})` a few times with a short pause; stop polling in the
   foreground past that and resume later from a resident session rather
   than looping. `resume` never submits a new request and, on local,
   never regenerates - it only re-validates the existing take against the
   job's frozen receipt. An interrupted local attempt with no result and
   no running process is marked `failed` automatically and stays counted.
8. For each additional approved variant within the grant, call
   `music_generate({action: "next", job_dir: ...})` with no approval
   fields to reuse the last approved prompt, or with both `approved_plan`
   and `approval_sha256` together for a corrected proposal - engine,
   duration, base seed and the call/dollar cap stay frozen from `start`;
   only the creative/prompt fields may change on a corrective reapproval,
   and attempts never reset on resume or correction.
9. A `success: false` "submission outcome unknown" result (fal only) is a
   manual finding - stop and report it; never start a new `job_dir` to
   reset the attempt count around a stuck submission.
10. Once a result reports `status: raw-needs-qa`, package that attempt's
    raw take (never re-generate to fix a packaging problem - reuse the
     existing raw file). Use the frozen `artifact` path returned by that
     attempt's proposal (`proposal-v<N>/generation-prompt.txt`), not a newer
     correction's scratch prompt. Match its approval hash to the attempt:

    ```sh
    ~/ghq/github.com/NousResearch/hermes-agent/venv/bin/python "${HERMES_SKILL_DIR}/../../scripts/music-media.py" track <raw> --take-file <take_json> --prompt-file <deliver>/proposal-v<N>/generation-prompt.txt --out <deliver>/take-NN --slug <slug>
    ```

    Do not use command substitution in executable paths; if `ghq root`
    differs on this machine, resolve it with a separate `ghq root` call
    first and then invoke the literal absolute Python path. Pass the
    receipt exactly as returned - never fabricate or edit `take.json`.
    Keep the job's `state.json` and every raw take file as the audit
    trail; a QA failure on a packaged bundle is never grounds to
    regenerate rather than report the finding.

</Procedure>

<QA>

- Proposal: theme/style/direction/ending expanded into concrete prompt
  language, not just the label; the compact prompt is 1-450 characters
  and matches its approved hash exactly. Approval matches the exact
  proposal text/settings before any spend.
- Structural intent: consult the selected theme/style/direction/ending
  reference's own QA cue and report the requested character explicitly,
  separate from whether the returned take actually delivers it
  perceptually (unverified without a listen).
- Per packaged attempt: full decode, positive non-silent duration close
  to the requested `duration_seconds` (report the actual measured value),
  no clipping; quote peak/true-peak/LUFS from the packaging result.
- Provenance: engine/model/attempt count/seed (and, for fal, `request_id`)
  are the tool's own returned values, never invented.
- No auditory/listening verdict is ever claimed; vocals-absence,
  instrument identity and perceived mood stay unverified even on a PASS
  bundle - state that explicitly.

</QA>

<Report>

Round A: `generate-music / awaiting approval` (or blocked); proposal path
and SHA-256; the resolved theme/style/direction/ending with any
AudioCreator-proposed defaults called out explicitly; engine and seed;
planned allowance; `spend: local $0` or `spend: fal 0/<approved cap>;
~$0`. This is a proposal, not a delivered cue.

Round B: proposal/digest, prompt/job/packaged-bundle paths, each
attempt's outcome (including failed/pending/unknown-submission ones)
with the QA measurements above, `spend: local $0` or `spend: fal
<calls>/<approved cap>; ~$<estimate>` and remaining budget. State any
`must_keep` or reference-audio-derived requirement that remains unmet,
recommend `analyze-music` or `edit-music` as separate next steps, and
never claim you listened or propose a further attempt outside the
approved cap without going back for approval.

</Report>
