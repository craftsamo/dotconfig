---
name: create-music
description: >-
  Compose instrumental BGM or a short melodic cue as a deterministic
  electronic score. Return a proposal first; render locally only after
  Creator relays its approval. No user-written score required. No model
  or network. Not songs, SFX, mixing, edit-music or generate-music.
version: 1.0.0
metadata:
  hermes:
    category: hands
    hands: audio-creator
    cost: free
    output: "proposal-v<N>/proposal.md + SHA-256; after approval, music_<slug>.wav + score.json + take evidence"
    form:
      what_for:
        required: true
        label: "what the music is for, in one sentence"
        example: "A 12-second looping BGM bed for a settings menu"
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
        options: [minimal-electronic, chiptune, ambient-synth]
        other: true
        references: references/styles/*.md
        label: "electronic palette; unsupported realistic instruments go to generate-music"
      instrumentation:
        required: false
        label: "which of the five waveforms (sine/triangle/pulse/fm-bell/noise) to feature or avoid"
      direction:
        required: false
        options: [steady, gradual-build, contrast, motif-return]
        other: true
        references: references/direction/*.md
        label: "musical development; omit to have AudioCreator propose it"
      tempo:
        required: false
        label: "speed/rhythm or exact BPM; omitted choices enter the proposal"
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
      key:
        required: false
        label: "musical key, e.g. C major, A minor; AudioCreator chooses one if omitted"
      meter:
        required: false
        label: "4/4, 3/4 or 6/8; AudioCreator chooses one if omitted"
      melody:
        required: false
        label: "melodic direction in words; AudioCreator composes the exact notes"
      harmony:
        required: false
        label: "harmonic/chordal direction in words; AudioCreator composes the exact voicing"
      score:
        required: false
        type: file
        label: "optional exact score.json per references/score.md; never silently rewrite"
      reference_audio:
        required: false
        type: file
        label: "local reference only; never uploaded or automatically analyzed"
      reference_focus:
        required: false
        label: "required with reference_audio: what to borrow; analyze-music handles measurements"
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

1. Confirm scope before anything else: this leaf composes **instrumental**
   BGM or a melodic opener/closer only. A request for a full song with
   lyrics/singing, standalone sound design/SFX, or audio mixing is `no
   skill fits` - a finding for Creator, never an approximated substitute.
   A described real-world/sampled instrument, or any `style`/
   `instrumentation` outside the five score waveforms
   (sine/triangle/pulse/fm-bell/noise), routes to `generate-music`
   instead; say so before writing a proposal, never render an
   approximated kernel to stand in for it.
2. Load only the selected local references before drafting: theme from
   [warm](references/themes/warm.md), [playful](references/themes/playful.md),
   [dreamy](references/themes/dreamy.md), [tense](references/themes/tense.md),
   [uplifting](references/themes/uplifting.md); style from
   [minimal-electronic](references/styles/minimal-electronic.md),
   [chiptune](references/styles/chiptune.md),
   [ambient-synth](references/styles/ambient-synth.md); direction from
   [steady](references/direction/steady.md),
   [gradual-build](references/direction/gradual-build.md),
   [contrast](references/direction/contrast.md),
   [motif-return](references/direction/motif-return.md); ending from
   [resolve](references/ending/resolve.md), [fade](references/ending/fade.md),
   [loop](references/ending/loop.md); and the score schema in
   [score.md](references/score.md). These are authored recipes, not
   guaranteed effects; a `theme`/`direction`/`style` given as `other` gets
   an equally concrete written treatment, never coerced onto a listed one.
   Themes never imply a forced tempo or key; `gradual-build` adds parts/
   density, never an implied tempo change (this schema's `bpm` is fixed
   for the whole score). `theme_detail`/`must_keep` override conflicting
   defaults; resolve contradictions before approval.
3. `reference_audio` is never uploaded anywhere and this leaf never
   auto-analyzes it. A description of mood/instrumentation from a human
   listen is enough for `reference_focus`; if the client instead needs an
   objective measurement (tempo/key/structure) from the file, that is a
   separate `analyze-music` call in its own turn, with its findings
   supplied back into this form - never a silent remote/local inference
   folded into this leaf's own round.
4. Round A (no `approved_plan`): no rendering, no network, no uploads.
   Resolve the complete effective form, proposing concrete defaults for
   any omitted `direction`/`tempo`/`ending`/`key`/`meter` (never leaving
   them implicit) and write it to a fresh `<deliver>/form.json`. Write a
   short `<deliver>/arrangement.md` narrating the piece section by section
   (opening, development per `direction`, the `ending`) in plain
   language. Compose the exact `<deliver>/score.json` per
   `references/score.md` - at most 8 tracks, at most 2048 notes total,
   every note fully inside `duration_seconds`, all beats in quarter-notes
   even under 6/8. If a `score` file was supplied and it already validates
   against that schema exactly, prefer it verbatim over composing a new
   one; do not patch a nonconforming supplied score into shape silently -
   report the mismatch instead. Then run:

   ```sh
   ~/ghq/github.com/NousResearch/hermes-agent/venv/bin/python "${HERMES_SKILL_DIR}/../../scripts/music_plan.py" propose --kind create --form-file <deliver>/form.json --arrangement-file <deliver>/arrangement.md --score-file <deliver>/score.json --out <deliver>/proposal-v<N>
   ```

   Do not use command substitution in executable paths; if `ghq root`
   differs on this machine, resolve it with a separate `ghq root` call
   first and then invoke the literal absolute Python path. Choose the
   next unused `N` even after a rejected proposal; never overwrite a
   previous proposal directory. This helper writes the resolved
   settings/hashes and refuses conflicts on its own; it makes no audio
   call. Report the returned proposal path and its SHA-256, and STOP.
5. Round B requires both `approved_plan` and `approval_sha256` from
   Creator and `intent: revise <previous delivery>`, in the same work
   conversation as the client's approval. A changed creative field
   (theme/style/direction/tempo/duration/ending/key/meter/melody/
   harmony/must_keep) needs a new proposal and approval, never a
   generation against stale approval text. Run:

   ```sh
   ~/ghq/github.com/NousResearch/hermes-agent/venv/bin/python "${HERMES_SKILL_DIR}/../../scripts/music-media.py" create --approved-plan <approved_plan> --approval-sha256 <approval_sha256> --out <deliver>/take-01 --slug <slug>
   ```

   Use a fresh, previously unused `--out` directory under `<deliver>` for
   each render; never overwrite a prior take. This is local synthesis
   only - no `music_generate` tool call, no engine selection, no seed
   negotiation, no paid approval gate; the score is deterministic given
   the approved plan.
6. `intent: revise` after a FAIL/mismatch reruns step 5 against the same
   approved plan only if the defect is a packaging/tooling failure; a
   defect in the actual composed music (wrong notes, wrong structure)
   needs a new proposal at step 4, never a hand-patched score.json run
   through the execution step without going back through `music_plan.py`.

</Procedure>

<QA>

- Proposal: theme/style/direction/ending expanded into the actual score
  (instrument choices, note density, structure), not just the label;
  `score.json` validates against `references/score.md` bounds (track/note
  counts, all notes inside `duration_seconds`, quarter-note beats).
  Approval matches the exact proposal text/hash before any render.
- Structural fit: consult the selected theme/style/direction/ending
  reference's own QA cue (e.g. `gradual-build`'s density comparison,
  `resolve`'s release margin, `chiptune`'s lead-instrument check) and
  report whether the composed score actually satisfies it.
- Integrity: the rendered WAV's own measured duration, sample rate,
  channels and decode must match what `music-media.py create` reports;
  never report the requested `duration_seconds` as the measured one
  without checking.
- Determinism: replay claims are scoped to the same score + renderer +
  environment producing byte-identical PCM, never to a different
  free-text description "sounding the same".
- No auditory/listening verdict: composition correctness against the
  schema and structural QA cues is not proof anyone listened; state that
  explicitly even on a PASS.

</QA>

<Report>

Round A: `create-music / awaiting approval` (or blocked); proposal path
and SHA-256; the resolved theme/style/direction/ending with any AudioCreator-
proposed defaults called out explicitly; `spend: free; calls 0`. This is
a proposal, not a delivered cue.

Round B: proposal/digest, `score.json`/rendered WAV paths, measured
duration/format, the structural QA findings from step 2 above, and
`spend: free`. State any `must_keep` or reference-audio-derived
requirement that remains unmet, and recommend `analyze-music` or
`edit-music` as separate next steps rather than folding them in here.
Never claim you listened to the render.

</Report>
