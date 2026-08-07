---
card_units:
  - name: anchored-image-batch
    assignee: creator
    required_inputs: [approved-style-anchor, per-item-spec-list, durable-output-path]
    unit_cap: "one batch of independent images, all from the same approved anchor; per-item specs fixed in the body"
    runtime_cap: 1800
  - name: tts-voice
    assignee: creator
    required_inputs: [final-script-text, voice-preset-name, durable-output-path]
    unit_cap: "one voice track from one final script"
    runtime_cap: 900
  - name: deterministic-render
    assignee: creator
    required_inputs: [final-data, template-or-format-spec, durable-output-path]
    unit_cap: "one diagram/chart/render from fixed data — no creative interpretation"
    runtime_cap: 900
---

# Creative — execute

The specialist is the **creator** resident session — your hands on
the generation tools. You release the approved decomposition **one
unit at a time** (anchor, part, assembly — `../../plan/creative/`)
and hold the QA gate between units. Everything around the units —
part handoff, packaging, delivery, the Budget ledger — is yours,
per `media-ops.md`: content-altering work through the creator,
byte-preserving handling direct. The card units above are the only
creator work that may ride kanban.

## Resident session

Start `resident-session.sh start <topic>-creator …` with the
SessionBrief carrying the first unit's spec (decision core + family
leaf decisions + `Budget:` line). **One session per job**, spanning
its units: the session context IS the asset — anchors, seeds, locked
specs, and spend history live there, which is why revisions cost
only the changed assets. Close it when the job is accepted; never
carry unrelated jobs in one session.

## The unit loop

1. **Release one unit** — "produce the anchor", "produce parts C1–C8
   from the locked anchor", "assemble per this edit spec". Never
   hand the whole composite ("make the video") — sequencing is
   yours; the creator returns wholesale briefs as spec-gap findings.
   Release a unit only when its family-leaf decisions are complete
   and its inputs passed your QA (the frontier rule).
2. **Receive the report** — files at durable paths, verification
   evidence, spend tally, reuse anchors. A reply without files at
   durable paths, or a tally that doesn't reconcile, is a defect.
3. **Gate** — the QA contract for the family
   (`../../quality-assurance/creative/index.md`). Feedback is
   itemized per asset in the next turn ("C2: 白紙束ではなく開いた本に");
   everything unnamed is preserved. A failed gate is a course
   correction on the SAME unit.
4. **Close out** per `media-ops.md` (ledger, packaging when due),
   then release the next unit — assembly last, only when every
   input part passed.

Mid-unit questions: answer in-spec ones yourself; relay taste and
Budget-expansion beyond the sanctioned plan to the user. A spec gap
or capability signal pulls the work back to Plan, not into another
turn. A wholesale direction change re-anchors (new sample +
sign-off) before any full re-render.

## Parallel units

Independent parts may run in parallel — a second resident session
(`<topic>-creator-<part>`, style-independent parts only) or the
card units:

- `anchored-image-batch` — mass-parallel images AFTER the anchor
  passed QA and was approved; body carries anchor, complete
  per-item specs, `Budget:`.
- `tts-voice` — one voice track from a **final** (QA-passed)
  script; preset named; no script editing on the card.
- `deterministic-render` — output fully determined by settled data
  + named template; if taste enters, it is not deterministic.

Parts sharing an anchor or feeding the same assembly stage
sequence through your gate; never parallelize what shares an
unsettled dependency. Card revisions go to the resident session
seeded with artifact paths + itemized defects — never a fresh card
(except a purely mechanical re-render with identical spec).

## Pitfalls

- Producing or altering media yourself, whatever the tier — the
  production boundary (`media-ops.md`) is absolute.
- Releasing a unit whose family decisions are still open — that is
  Plan work; the bounce-back costs a turn.
- Letting a batch run before its anchor passed, or an assembly run
  before every part passed.
- Starting production without a sanctioned `Budget:` line, or
  approving expansion beyond what the user sanctioned.
- Re-briefing style in a revision turn — the session holds the
  anchors; name only what changes.
- Accepting "done" without files at durable paths and a reconciled
  tally.
