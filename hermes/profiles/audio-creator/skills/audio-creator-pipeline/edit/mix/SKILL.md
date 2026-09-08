---
name: edit-mix
description: >-
  Revise one existing mix bundle: change source placement, gain/fade/
  envelope automation, added or removed cues, or overall duration/
  loudness targets, from a plain-language change request. Loads the
  frozen sources and previous spec, authors a full revised plan and a
  proposal, and renders locally only after Creator relays approval.
  Never separates stems from the master or synthesizes new audio; not a
  from-scratch mix (create-mix) or a single-file edit (edit-music/
  edit-sfx/edit-speech).
version: 1.0.0
metadata:
  hermes:
    category: hands
    hands: audio-creator
    cost: free
    output: "proposal-v<N>/proposal.md + SHA-256; after approval, revised mix_<slug>.wav + mix.json + mix.take.json"
    form:
      source:
        required: true
        type: path
        label: "the previous complete mix bundle directory (mix.json + frozen sources/ + a PASS or WARN mix.take.json); a FAILed bundle cannot be revised here"
      changes:
        required: true
        type: text
        label: "the requested change, in words - what to move/add/remove/reweight and why"
      timing:
        required: false
        type: file
        label: "optional exact timing JSON constraining matching cues' start/source_start/duration; never changed behind approval"
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

1. Confirm `source` is a complete, PASS-or-WARN previous mix bundle:
   run `mix-media.py verify --bundle <source>` first. The helper itself
   refuses a FAILed or incomplete bundle - stop with a finding rather
   than authoring a revision against one. A FAILed initial take has no
   valid master to revise at all; that case goes back to `create-mix`'s
   own proposal/render steps, never here. Load the verified `mix.json`
   (the previous spec) - never re-supplied, re-uploaded or
   re-synthesized audio, and this leaf never separates stems out of the
   rendered master.
2. Round A (no `approved_plan`): author a full revised `<deliver>/
   spec.json` reflecting `changes` against the previous spec (not a
   partial patch - `mix-media.py` takes the complete spec every time)
   and a `<deliver>/description.md` stating both the new arrangement and
   a plain-language diff against the previous one. **Expand every
   source's path before writing it**: the previous `mix.json` stores
   each source's `path`/`words` as bundle-relative names
   (`sources/<id>.audio`, `sources/<id>.words.json`) - `mix-media.py
   propose` resolves a source's `path` against the process's own
   working directory, not the previous bundle, so the revised
   `spec.json` must set each `sources[].path`/`words` to the ABSOLUTE
   filesystem path of that file under the PREVIOUS bundle directory
   (e.g. `<source>/sources/<id>.audio`), never the bare bundle-relative
   name copied as-is. Where `timing` was supplied, matching cues must
   already equal its exact values before calling `propose`. An
   audio-inert `changes` request (e.g. wording only, no actual
   placement/gain/duration/source change) is refused by the helper as a
   no-op revision - report that rather than forcing a proposal. Then
   run:

   ```sh
   ~/ghq/github.com/NousResearch/hermes-agent/venv/bin/python "${HERMES_SKILL_DIR}/../../scripts/mix-media.py" propose --spec-file <deliver>/spec.json --description-file <deliver>/description.md --out <deliver>/proposal-v<N> --previous <source>
   ```

   Do not use command substitution in executable paths; if `ghq root`
   differs on this machine, resolve it with a separate `ghq root` call
   first and then invoke the literal absolute Python path. This step
   fully decodes and validates every source again (not zero audio
   work), but produces no mixed audio, no ASR, no network call. Report
   the returned proposal path and its SHA-256, and STOP.
3. Round B requires both `approved_plan` and `approval_sha256` from
   Creator and `intent: revise <previous delivery>`, in the same work
   conversation. Run:

   ```sh
   ~/ghq/github.com/NousResearch/hermes-agent/venv/bin/python "${HERMES_SKILL_DIR}/../../scripts/mix-media.py" render --approved-plan <approved_plan> --approval-sha256 <approval_sha256> --kind edit --out <deliver>/take-01 --slug <slug>
   ```

   Use a fresh, previously unused `--out` directory; never overwrite the
   prior bundle. The delivered artifact is `mix.json` (not `spec.json`).
4. A further `intent: revise` after a FAIL/mismatch reruns step 3
   against the same approved plan only for a packaging/tooling failure;
   an actual mix defect returns to step 2 for a new proposal.

</Procedure>

<QA>

- Same integrity/loudness/caption/determinism/authorization checks as
  `create-mix`'s QA (including the measured constant-gain
  normalization rule and the `output_policy` cross-check), applied to
  the revised spec and render.
- The plain-language diff in `description.md` actually matches what
  changed between the previous `mix.json` and the revised `spec.json` -
  report a mismatch rather than trusting the stated diff.
- Every source path in the revised `spec.json` actually resolves (the
  absolute-path expansion from step 2 was done correctly) - a path
  copied verbatim from the previous `mix.json` without expansion is a
  defect to catch before calling `propose`, not after it fails.
- The previous bundle and its frozen sources remain unchanged; a FAIL
  bundle from this leaf is retained for diagnosis, never presented as
  finished.

</QA>

<Report>

Round A: `edit-mix / awaiting approval` (or blocked); proposal path and
SHA-256; the plain-language diff against the previous mix; `spend:
free; calls 0`.

Round B: proposal/digest, the delivered `mix.json`/`mix_<slug>.wav`
paths, measured duration/format/peak/true-peak/LUFS against
`output_policy`, the QA findings, and `spend: free`. Never claim you
listened to the render.

</Report>
