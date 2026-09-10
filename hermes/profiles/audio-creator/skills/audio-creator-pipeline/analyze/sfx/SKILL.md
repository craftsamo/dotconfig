---
name: analyze-sfx
description: >-
  Inspect an existing SFX file's native format, loudness, clipping and
  silence. Returns findings only, never a new or modified file. Not
  listening-based quality certification or loop-seamlessness proof.
version: 1.0.0
metadata:
  hermes:
    category: hands
    hands: audio-creator
    cost: free
    output: "findings in the reply; no deliverable file, deliver may be omitted"
    form:
      source:
        required: true
        type: file
        label: "one local audio file, at most 22 seconds and 16 MiB"
      note:
        required: false
        type: text
---

<Procedure>

1. Read the form. Never modify `source` and never create a `deliver`
   directory — this leaf produces no file. Run:

   ```sh
   ~/ghq/github.com/NousResearch/hermes-agent/venv/bin/python "${HERMES_SKILL_DIR}/../../scripts/sfx-media.py" analyze <source>
   ```

   Do not use command substitution in executable paths; if `ghq root`
   differs on this machine, resolve it with a separate `ghq root` call
   first and then invoke the literal absolute Python path — never repeat
   the model generation to fix a packaging step. (Actual live failure:
   "Nested executable body could not be resolved.")

2. Read the whole `RESULT:` JSON regardless of its exit code. This CLI
   exits 0 for a measured PASS or WARN, 1 for a measured FAIL (clipping,
   silence, or a true peak at/above 0 dBTP), and 2 for a dependency or
   input error raised before any measurement could complete — distinguish
   "the sound failed QA" from "the file/tooling could not be analyzed" in
   the report.
3. Build a findings table: check, evidence (the actual number), verdict,
   proposed next action (edit-sfx / create-sfx / generate-sfx / none).

</Procedure>

<QA>

- Full decode, nonempty, non-silent is blocking; clipping and unexpected
  boundary silence are findings with the measured numbers, not just a
  pass/fail label.
- A missing `integrated_lufs` on a short/transient sound is `WARN`, not
  proof of a defect — do not propose a re-roll or resynthesis for it.
- `boundary_sample_deltas` is descriptive only; it is never proof that a
  clip loops seamlessly, even when the deltas are small.
- `attack_estimate` is exactly that — an estimate from a relative
  threshold, not a verified transient onset.
- No finding without a named measurement or an explicitly disclosed
  limitation. A FAIL result is a diagnostic finding, never treated as a
  finished asset.

</QA>

<Report>

Return `analyze-sfx`, the source, the findings table with blocking
defects first, then a proposed handoff (edit-sfx/create-sfx/generate-sfx)
rather than executing one. State `spend: free`; no delivery path is
required.

</Report>
