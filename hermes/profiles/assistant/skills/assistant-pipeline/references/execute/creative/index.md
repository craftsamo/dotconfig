---
card_units:
  - name: anchored-image-batch
    required_inputs: [approved-style-anchor, per-item-spec-list, durable-output-path]
    unit_cap: "one batch of independent images, all from the same approved anchor; per-item specs fixed in the body"
    runtime_cap: 1800
  - name: tts-voice
    required_inputs: [final-script-text, voice-preset-name, durable-output-path]
    unit_cap: "one voice track from one final script"
    runtime_cap: 900
  - name: deterministic-render
    required_inputs: [final-data, template-or-format-spec, durable-output-path]
    unit_cap: "one diagram/chart/render from fixed data — no creative interpretation"
    runtime_cap: 900
---

# Creative — execute

All media production runs through the **creator** profile; the assistant
produces no media itself, ever. Default tier is a resident session;
the card units above are the only creator work that may ride kanban.

## Resident session

Start `resident-session.sh start <topic>-creator …` with the SessionBrief
carrying the MediaBrief (`../../plan/creative/index.md`). Then supervise:

- Production lands as files at the durable path named in `Deliverable:`
  (default `~/Workspaces/.deliverables/<job>/`); the reply names every
  file. Scratch-only output is a defect — say so in the next turn.
- Feedback and revisions are turns in the same session, itemized per
  asset ("C2: 白紙束ではなく開いた本に", "C9: 最後2秒は開眼"). Everything
  unnamed is preserved — the session already holds the style anchors,
  seeds, and history, so revisions cost only the changed assets.
- Budget expansion requests come back as a question in the reply; approve
  within what the user sanctioned, relay beyond it.
- A wholesale direction change («全面組み直し», new concept) re-anchors:
  new cheap sample + sign-off before any full re-render.

## Card units

- `anchored-image-batch` — mass-parallel independent images AFTER the
  style anchor passed QA and the user approved it. The body carries the
  anchor (path/reference), the complete per-item spec list, and a
  `Budget:` line. Anchor exploration, first-of-kind samples, and anything
  whose look is still being decided are NOT this unit.
- `tts-voice` — voice generation from a **final** script (your QA already
  passed the text). Voice preset named; no script editing on the card.
- `deterministic-render` — a render fully determined by its inputs
  (settled data + named template/format). If taste enters, it is not
  deterministic.

Revisions of card output go to the resident session
(`../resident-sessions.md`), seeded with the artifact paths + itemized
defects — never a fresh card, except a purely mechanical re-render with
identical spec.

## Pitfalls

- Generating or improvising media yourself, whatever the tier.
- Starting production without a Budget the user's plan sanctions.
- Letting a batch run — session or card — before its style anchor passed.
- Re-briefing style in a revision turn — the session holds the anchors;
  name only what changes.
- Accepting "done" replies without files at durable paths.
