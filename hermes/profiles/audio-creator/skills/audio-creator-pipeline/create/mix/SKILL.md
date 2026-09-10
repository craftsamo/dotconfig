---
name: create-mix
description: >-
  Combine already-finished speech, sfx and music sources into one placed,
  gain-automated master on a shared timeline. Returns a proposal first;
  renders locally only after Creator relays its approval. AudioCreator
  authors cue placement from intent when no exact arrangement is
  supplied; no user-written spec required. No new sound synthesis,
  generation, looping, EQ, reverb, source separation or video assembly.
version: 1.0.0
metadata:
  hermes:
    category: hands
    hands: audio-creator
    cost: free
    output: "proposal-v<N>/proposal.md + SHA-256; after approval, mix_<slug>.wav + mix.json + mix.take.json + frozen sources/ + optional timing.json/captions.json/mix_<slug>.srt"
    form:
      what_for:
        required: true
        label: "what the mix is for, in one sentence"
        example: "A 20-second intro bed: VO over a music cushion with a UI tick accent"
      sources:
        required: true
        type: file
        label: "local JSON file inventorying 1-16 available source files: [{id, path, role: speech|music|sfx|other, words: optional local path to the source's own .words.json}] - a voice/speech source is never required"
      direction:
        required: true
        type: text
        label: "how the cues should relate - what leads, what layers underneath, pacing/ducking intent in words; AudioCreator authors exact placement from this unless arrangement is supplied"
      duration:
        required: true
        type: text
        label: "total mix duration, 1-600 seconds"
        example: "20"
      timing:
        required: false
        type: file
        label: "optional exact timing JSON constraining matching cues' start/source_start/duration; never changed behind approval"
      must_keep:
        required: false
        type: text
        label: "requirements that must never be silently dropped"
      arrangement:
        required: false
        type: file
        label: "optional local file with the exact per-cue arrangement (start/source_start/duration/gain_db/fade_in/fade_out/envelope); supplied values are copied into the authored cues verbatim, never reinterpreted - a control the schema does not accept returns Q<n>"
      approved_plan:
        required: false
        type: file
        label: "approved proposal-v<N>/proposal.md; absent means proposal only"
      approval_sha256:
        required: false
        type: text
        label: "SHA-256 of the exact proposal approved by the client; required with approved_plan"
      slug:
        required: false
        type: text
        label: "lowercase ASCII filename slug; default mix"
      note:
        required: false
        type: text
---

<Procedure>

1. Confirm scope: this leaf places already-finished speech/sfx/music
   WAV/FLAC/Ogg/MP3/AIFF sources on a shared timeline with gain/fade/
   envelope automation and renders one master. It never creates or
   generates a component sound (that stays with generate-speech/
   create-sfx/generate-sfx/create-music/generate-music), never loops a
   single source to length (that is edit-music), and never applies EQ,
   reverb, source separation, or assembles video. A request needing new
   audio content or those operations is `no skill fits` - route to the
   fitting leaf first, never approximate it here. A mix needs no
   speech/voice source at all - a pure music+sfx mix is fine. Sources
   need not come from this pipeline's own prior deliveries; any
   qualifying local file is acceptable, but a source of unknown
   provenance (not one of AudioCreator's own prior takes) is disclosed
   as such in the proposal, never presented as pre-vetted.
2. Read `sources` (the inventory file): 1-16 entries, each `{id, path,
   role, words?}` exactly - no other keys (a `slug` key is not part of
   this shape). Every `id` is a lowercase-hyphen slug, unique; `role` is
   speech/music/sfx/other; `words` is only valid on a `role: speech`
   entry, and only when that source's own `.words.json` sidecar
   actually exists locally. Every declared source must end up used by
   at least one cue - the helper refuses an unused source. Each file
   must be a standalone local WAV/FLAC/Ogg/MP3/AIFF, <=128 MiB, <=512
   MiB combined, decoding to <=600 seconds.
3. Round A (no `approved_plan`): author the complete spec v1 (see
   [arrangement](references/arrangement.md) for the exact schema, a
   concrete example, and cue-placement guidance, and
   [delivery](references/delivery.md) for what the render actually
   produces) as `<deliver>/spec.json`, and a plain-language
   `<deliver>/description.md` narrating what plays when and why.
   `target_lufs` has no hidden default and must always be present as an
   explicit choice (`null` is a valid explicit choice - it means no
   normalization pass); `true_peak_dbtp` is always a number and
   defaults to -1 unless the direction/note calls for something else.
   Every cue needs all nine of its fields set explicitly (`gain_db`,
   `fade_in`, `fade_out`, `envelope` included - an empty `envelope` is
   the normal, valid way to say "flat," not an omission). Copy
   `arrangement` in verbatim per cue when supplied - an invalid
   requested control (out-of-range gain/envelope, a cue outside
   `duration_seconds`, a nonexistent `source`) is a `Q<n>`, never
   silently coerced into range - otherwise author relative placement
   from `direction`/`note`/`must_keep`. Where `timing` was supplied, the
   matching cues in `spec.json` must already equal its exact
   `start`/`source_start`/`duration` before you call `propose` - the
   helper validates this itself and refuses a mismatch. Then run:

   ```sh
   ~/ghq/github.com/NousResearch/hermes-agent/venv/bin/python "${HERMES_SKILL_DIR}/../../scripts/mix-media.py" propose --spec-file <deliver>/spec.json --description-file <deliver>/description.md --out <deliver>/proposal-v<N>
   ```

   Do not use command substitution in executable paths; if `ghq root`
   differs on this machine, resolve it with a separate `ghq root` call
   first and then invoke the literal absolute Python path. Choose the
   next unused `N` even after a rejected proposal; never overwrite a
   previous proposal directory. This step fully decodes and validates
   every source (and any speech `.words.json` PCM hash) as part of
   proposal validation - it is not zero audio work - but it produces no
   mixed audio, runs no ASR, and makes no network call. The frozen,
   approved-facing spec inside the bundle is always named `mix.json`
   (your `--spec-file` is only the local staging input; its own
   filename does not matter). Report the returned proposal path and its
   SHA-256, and STOP.
4. Round B requires both `approved_plan` and `approval_sha256` from
   Creator and `intent: revise <previous delivery>`, in the same work
   conversation as the client's approval. A changed creative field (any
   source, cue placement, gain/fade/envelope, duration, target_lufs,
   true_peak_dbtp) needs a new proposal and approval, never a render
   against stale approval text. Run:

   ```sh
   ~/ghq/github.com/NousResearch/hermes-agent/venv/bin/python "${HERMES_SKILL_DIR}/../../scripts/mix-media.py" render --approved-plan <approved_plan> --approval-sha256 <approval_sha256> --kind create --out <deliver>/take-01 --slug <slug>
   ```

   Use a fresh, previously unused `--out` directory under `<deliver>`
   for each render; never overwrite a prior take.
5. `intent: revise` after a FAIL/mismatch reruns step 4 against the same
   approved plan only if the defect is a packaging/tooling failure; a
   defect in the actual composed mix (wrong placement, wrong gain, wrong
   source) needs a new proposal at step 3, never a hand-patched
   `spec.json` run through the render step without going back through
   `mix-media.py propose`. A FAILed take has no valid deliverable bundle
   (`edit-mix` refuses to load it) - always return to this leaf's own
   step 3/4 for it, never route a FAILed take to `edit-mix`. If
   surviving intermediates from an earlier attempt already form a
   complete PASS/WARN bundle, run `mix-media.py verify --bundle
   <deliver>/take-NN` and reuse it instead of rerendering.

</Procedure>

<QA>

- Proposal: `direction`/`arrangement`/`must_keep` expanded into the
  actual cue list (placement, gain, fades, envelope), not just the
  label; `spec.json` validates against the v1 schema (source/cue
  counts, every cue's `id`/`source`/`start`/`source_start`/`duration`/
  `gain_db`/`fade_in`/`fade_out`/`envelope` present, every cue inside
  `duration_seconds`, envelope points strictly increasing from exactly
  `0` to exactly the cue's own `duration`, <=64 points). Approval
  matches the exact proposal text/hash before any render.
- Integrity: the rendered master's own measured duration, sample rate,
  channel count, and exact sample count against the planned timeline
  must match what `mix-media.py render` reports; input files are
  hash-verified against the frozen `sources/` copies before use, and an
  existing input defect (e.g. a source's own clipping) is retained and
  reported, never silently corrected.
- Loudness/peak: `mix-media.py`'s measured peak/true-peak/clipping and
  integrated LUFS are the actual numbers, never the requested target
  reported as if measured; quote `mix.take.json`'s `output_policy`
  (the approved `target_lufs`/`true_peak_dbtp`) next to what was
  actually measured. When `target_lufs` is set, normalization is a
  single measured constant-gain pass (never ffmpeg's dynamic
  two-pass/limiter loudnorm) - if that one gain cannot hit both the
  loudness target and the true-peak ceiling at once, the render is FAIL
  with a request for a revised target/gain, never a silently applied
  limiter. A short/ungated clip's missing integrated LUFS is WARN;
  whole-silence delivery is FAIL. A stereo-to-mono fold's
  `mono_fold_energy_delta_db` >6 dB loss is a disclosed possible-
  cancellation WARN, not a FAIL.
- Captions (when produced): `captions.json`/`mix_<slug>.srt` come only
  from an existing `.words.json` sidecar on a speech source, adjusted
  to that cue's placement, marked `estimated: true` - never a fresh ASR
  pass on the mixed master. A cue's own trim crossing a word/caption/
  segment boundary in its source's sidecar is refused outright; once
  any source in the mix carries a sidecar, no two speech-role cues may
  overlap on the mix timeline at all (even one without a sidecar) - the
  helper refuses that too. A source with no sidecar simply yields no
  captions for its cue, disclosed rather than fabricated.
- Determinism: replay claims are scoped to the same spec + frozen
  sources + helper version + environment producing byte-identical PCM,
  never to a different free-text description "sounding the same" or to
  a claim that holds across a helper upgrade.
- Authorization: a matching approval hash confirms the proposal text
  was not altered, never who approved it.
- No auditory/listening verdict: measured integrity/loudness/caption
  checks are not proof anyone listened; state that explicitly even on a
  PASS. A FAIL bundle is retained for diagnosis, never presented as
  finished.

</QA>

<Report>

Round A: `create-mix / awaiting approval` (or blocked); proposal path
and SHA-256; the resolved sources/cue placement with any
AudioCreator-authored defaults (`target_lufs`, `true_peak_dbtp`,
channels, relative placement) called out explicitly; `spend: free;
calls 0`. This is a proposal, not a delivered mix - source decode/
validation already happened, but no mixed audio exists yet.

Round B: proposal/digest, the delivered `mix.json`/`mix_<slug>.wav`/
captions paths, measured duration/format/peak/true-peak/LUFS against
`output_policy`, the QA findings above, and `spend: free`. State any
`must_keep` or timing constraint that remains unmet, and recommend
`edit-mix`/`analyze-mix` as separate next steps rather than folding
them in here. Never claim you listened to the render.

</Report>
